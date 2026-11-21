//! Compiled column plans and the parallel, deterministic row/column generator.

use std::collections::{HashMap, HashSet};
use std::sync::{Arc, Mutex, OnceLock};

use arrow_array::{
    ArrayRef, BooleanArray, Date32Array, Float64Array, Int64Array, RecordBatch, StringArray,
    TimestampMicrosecondArray,
};
use arrow_buffer::{BooleanBuffer, Buffer, NullBuffer, OffsetBuffer, ScalarBuffer};
use arrow_schema::{DataType, Field, Schema, SchemaRef, TimeUnit};
use rayon::prelude::*;

use crate::errors::{NfError, Result};
use crate::providers::{generate_column, Column, Ctx, Data, Kind, Provider};
use crate::rng::{chunk_rng, chunks, stream_id, Chunk};

/// One compiled output column.
#[derive(Debug, Clone)]
pub struct ColumnSpec {
    pub name: String,
    pub provider: Provider,
    /// Probability in `[0, 1]` that a value is null.
    pub null_probability: f64,
    /// RNG stream id (derived from the column name).
    pub stream: u64,
}

/// A compiled, validated generation plan.
#[derive(Debug, Clone)]
pub struct Plan {
    pub columns: Vec<ColumnSpec>,
}

impl Plan {
    /// Build a plan from `(name, provider, null_probability)` triples.
    pub fn new(cols: Vec<(String, Provider, f64)>) -> Result<Plan> {
        if cols.is_empty() {
            return Err(NfError::Schema("a schema needs at least one column".into()));
        }
        let mut seen = HashSet::new();
        let mut columns = Vec::with_capacity(cols.len());
        for (name, provider, null_probability) in cols {
            if !seen.insert(name.clone()) {
                return Err(NfError::Schema(format!("duplicate column name {name:?}")));
            }
            if !(0.0..=1.0).contains(&null_probability) || null_probability.is_nan() {
                return Err(NfError::Schema(format!(
                    "null_probability for {name:?} must be within [0, 1], got {null_probability}"
                )));
            }
            columns.push(ColumnSpec {
                stream: stream_id(&name),
                name,
                provider,
                null_probability,
            });
        }
        Ok(Plan { columns })
    }

    /// Build a plan from pre-assembled column specs (custom RNG streams), validating it.
    pub fn from_specs(columns: Vec<ColumnSpec>) -> Result<Plan> {
        let streams: Vec<u64> = columns.iter().map(|c| c.stream).collect();
        let mut plan = Plan::new(
            columns
                .into_iter()
                .map(|c| (c.name, c.provider, c.null_probability))
                .collect(),
        )?;
        for (c, s) in plan.columns.iter_mut().zip(streams) {
            c.stream = s;
        }
        Ok(plan)
    }

    pub fn len(&self) -> usize {
        self.columns.len()
    }

    pub fn is_empty(&self) -> bool {
        self.columns.is_empty()
    }

    /// The Arrow schema of the generated data.
    pub fn arrow_schema(&self) -> SchemaRef {
        Arc::new(Schema::new(
            self.columns
                .iter()
                .map(|c| {
                    Field::new(
                        c.name.clone(),
                        data_type(c.provider.kind()),
                        c.null_probability > 0.0,
                    )
                })
                .collect::<Vec<_>>(),
        ))
    }

    /// Generate column `ci` for one chunk.
    pub fn column_chunk(&self, ci: usize, chunk: Chunk, seed: u64, ctx: &Ctx) -> Column {
        let col = &self.columns[ci];
        let mut rng = chunk_rng(seed, chunk.index as u64, col.stream);
        generate_column(
            &col.provider,
            ctx,
            &mut rng,
            chunk.start as u64,
            chunk.len,
            col.null_probability,
        )
    }

    /// Generate every column of one chunk (sequentially).
    pub fn chunk_columns(&self, chunk: Chunk, seed: u64, ctx: &Ctx) -> Vec<Column> {
        (0..self.len())
            .map(|ci| self.column_chunk(ci, chunk, seed, ctx))
            .collect()
    }

    /// Generate `count` rows in parallel on the current rayon pool.
    ///
    /// Returns one `Vec<Column>` (all columns) per chunk, in chunk order. Work is split into
    /// independent `(chunk, column)` tasks for good load balancing on wide and narrow schemas.
    pub fn generate(&self, count: usize, seed: u64, ctx: &Ctx) -> Vec<Vec<Column>> {
        let cs = chunks(count);
        let ncols = self.len();
        let mut flat: Vec<Option<Column>> = (0..cs.len() * ncols)
            .into_par_iter()
            .map(|t| Some(self.column_chunk(t % ncols, cs[t / ncols], seed, ctx)))
            .collect();
        (0..cs.len())
            .map(|c| {
                (0..ncols)
                    .map(|ci| {
                        flat[c * ncols + ci]
                            .take()
                            .expect("each task produced once")
                    })
                    .collect()
            })
            .collect()
    }

    /// Generate `count` rows as Arrow record batches (one batch per chunk).
    pub fn record_batches(&self, count: usize, seed: u64, ctx: &Ctx) -> Result<Vec<RecordBatch>> {
        let schema = self.arrow_schema();
        let chunked = self.generate(count, seed, ctx);
        chunked
            .into_par_iter()
            .map(|cols| to_record_batch(&schema, cols))
            .collect()
    }
}

/// Arrow data type for a provider output kind.
pub fn data_type(kind: Kind) -> DataType {
    match kind {
        Kind::Int => DataType::Int64,
        Kind::Float => DataType::Float64,
        Kind::Bool => DataType::Boolean,
        Kind::Str | Kind::Cat => DataType::Utf8,
        Kind::Date => DataType::Date32,
        Kind::Timestamp => DataType::Timestamp(TimeUnit::Microsecond, None),
    }
}

/// Convert a generated column into an Arrow array without copying numeric/string buffers.
pub fn to_array(col: Column) -> ArrayRef {
    let validity = col.validity;
    match col.data {
        Data::Int(v) => Arc::new(Int64Array::new(
            ScalarBuffer::from(v),
            validity.map(NullBuffer::from),
        )),
        Data::Float(v) => Arc::new(Float64Array::new(
            ScalarBuffer::from(v),
            validity.map(NullBuffer::from),
        )),
        Data::Bool(v) => Arc::new(BooleanArray::new(
            BooleanBuffer::from(v),
            validity.map(NullBuffer::from),
        )),
        Data::Date(v) => Arc::new(Date32Array::new(
            ScalarBuffer::from(v),
            validity.map(NullBuffer::from),
        )),
        Data::Timestamp(v) => Arc::new(TimestampMicrosecondArray::new(
            ScalarBuffer::from(v),
            validity.map(NullBuffer::from),
        )),
        Data::Str { offsets, data } => string_array(offsets, data.into_bytes(), validity),
        Data::Cat { idx, table } => {
            let mut total = 0usize;
            for (i, &k) in idx.iter().enumerate() {
                if validity.as_ref().is_none_or(|v| v[i]) {
                    total += table.get(k as usize).len();
                }
            }
            let mut data = Vec::with_capacity(total);
            let mut offsets = Vec::with_capacity(idx.len() + 1);
            offsets.push(0i32);
            for (i, &k) in idx.iter().enumerate() {
                if validity.as_ref().is_none_or(|v| v[i]) {
                    data.extend_from_slice(table.get(k as usize).as_bytes());
                }
                offsets.push(i32::try_from(data.len()).expect("chunk string data exceeds 2 GiB"));
            }
            string_array(offsets, data, validity)
        }
    }
}

fn string_array(offsets: Vec<i32>, data: Vec<u8>, validity: Option<Vec<bool>>) -> ArrayRef {
    // SAFETY: offsets start at 0, are monotonically non-decreasing, end at `data.len()` and
    // always fall on UTF-8 character boundaries because `data` was assembled exclusively by
    // appending whole `&str` values.
    unsafe {
        let offsets = OffsetBuffer::new_unchecked(ScalarBuffer::from(offsets));
        Arc::new(StringArray::new_unchecked(
            offsets,
            Buffer::from_vec(data),
            validity.map(NullBuffer::from),
        ))
    }
}

/// Assemble one record batch from one chunk's columns.
pub fn to_record_batch(schema: &SchemaRef, cols: Vec<Column>) -> Result<RecordBatch> {
    let arrays: Vec<ArrayRef> = cols.into_iter().map(to_array).collect();
    Ok(RecordBatch::try_new(Arc::clone(schema), arrays)?)
}

// ---------------------------------------------------------------------------------------------
// Thread pools
// ---------------------------------------------------------------------------------------------

type PoolMap = Mutex<HashMap<usize, Arc<rayon::ThreadPool>>>;

fn pool(n: usize) -> Result<Arc<rayon::ThreadPool>> {
    static POOLS: OnceLock<PoolMap> = OnceLock::new();
    let pools = POOLS.get_or_init(|| Mutex::new(HashMap::new()));
    let mut guard = pools.lock().unwrap_or_else(|e| e.into_inner());
    if let Some(p) = guard.get(&n) {
        return Ok(Arc::clone(p));
    }
    let p = Arc::new(
        rayon::ThreadPoolBuilder::new()
            .num_threads(n)
            .thread_name(move |i| format!("nextfake-{n}-{i}"))
            .build()
            .map_err(|e| NfError::Schema(format!("could not build a {n}-thread pool: {e}")))?,
    );
    guard.insert(n, Arc::clone(&p));
    Ok(p)
}

/// Run `f` on a rayon pool with `threads` workers (`None` = global pool, all cores).
pub fn install<T: Send, F: FnOnce() -> T + Send>(threads: Option<usize>, f: F) -> Result<T> {
    match threads {
        None | Some(0) => Ok(f()),
        Some(n) => Ok(pool(n)?.install(f)),
    }
}

/// Number of worker threads that `install(threads, ..)` will use.
pub fn effective_threads(threads: Option<usize>) -> usize {
    match threads {
        None | Some(0) => rayon::current_num_threads(),
        Some(n) => n,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::locales;
    use crate::providers::Params;
    use crate::rng::CHUNK_ROWS;
    use arrow_array::Array;

    fn plan() -> Plan {
        let p = |n: &str| Provider::parse(n, &Params::new()).unwrap();
        Plan::new(vec![
            ("id".into(), p("serial"), 0.0),
            ("name".into(), p("name"), 0.0),
            ("email".into(), p("email"), 0.1),
            ("city".into(), p("city"), 0.0),
            ("ip".into(), p("ipv4"), 0.0),
            ("created_at".into(), p("datetime"), 0.0),
            ("active".into(), p("bool"), 0.0),
            ("score".into(), p("float"), 0.0),
            ("dob".into(), p("date_of_birth"), 0.0),
        ])
        .unwrap()
    }

    fn ctx() -> Ctx {
        Ctx {
            locale: locales::get("en_US").unwrap(),
            uuid7_base_ms: 0,
        }
    }

    #[test]
    fn thread_count_does_not_change_output() {
        let plan = plan();
        let n = CHUNK_ROWS * 3 + 123;
        let one = install(Some(1), || plan.record_batches(n, 99, &ctx()).unwrap()).unwrap();
        let many = install(Some(8), || plan.record_batches(n, 99, &ctx()).unwrap()).unwrap();
        let global = plan.record_batches(n, 99, &ctx()).unwrap();
        assert_eq!(one, many);
        assert_eq!(one, global);
        assert_eq!(one.iter().map(RecordBatch::num_rows).sum::<usize>(), n);
        let other_seed = plan.record_batches(n, 100, &ctx()).unwrap();
        assert_ne!(one, other_seed);
    }

    #[test]
    fn prefix_stability() {
        // The first k rows do not depend on the total row count.
        let plan = plan();
        let small = plan.record_batches(1000, 5, &ctx()).unwrap();
        let large = plan.record_batches(50_000, 5, &ctx()).unwrap();
        assert_eq!(small[0], large[0].slice(0, 1000));
    }

    #[test]
    fn column_independence() {
        // Adding a column does not change existing columns.
        let base = plan();
        let mut extended = base.clone();
        extended.columns.push(ColumnSpec {
            name: "extra".into(),
            provider: Provider::Uuid4,
            null_probability: 0.0,
            stream: stream_id("extra"),
        });
        let a = base.record_batches(500, 1, &ctx()).unwrap();
        let b = extended.record_batches(500, 1, &ctx()).unwrap();
        for i in 0..base.len() {
            assert_eq!(a[0].column(i), b[0].column(i));
        }
    }

    #[test]
    fn schema_and_nulls() {
        let plan = plan();
        let batches = plan.record_batches(10_000, 3, &ctx()).unwrap();
        let schema = plan.arrow_schema();
        assert_eq!(schema.field(0).data_type(), &DataType::Int64);
        assert_eq!(
            schema.field(5).data_type(),
            &DataType::Timestamp(TimeUnit::Microsecond, None)
        );
        assert!(schema.field(2).is_nullable());
        assert!(!schema.field(1).is_nullable());
        let nulls: usize = batches.iter().map(|b| b.column(2).null_count()).sum();
        assert!((800..1200).contains(&nulls), "{nulls}");
        let ids = batches[0]
            .column(0)
            .as_any()
            .downcast_ref::<Int64Array>()
            .unwrap();
        assert_eq!(ids.value(0), 1);
        assert_eq!(ids.value(9_999), 10_000);
    }

    #[test]
    fn duplicate_columns_rejected() {
        let p = Provider::parse("name", &Params::new()).unwrap();
        assert!(Plan::new(vec![("a".into(), p.clone(), 0.0), ("a".into(), p, 0.0)]).is_err());
        assert!(Plan::new(vec![]).is_err());
    }
}
