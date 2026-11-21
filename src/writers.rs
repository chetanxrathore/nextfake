//! Direct-to-Arrow IPC, Parquet, JSONL and CSV writers.
//!
//! All writers generate data chunk-by-chunk on the current rayon pool and stream it to disk in
//! bounded "waves", so peak memory is proportional to `threads x chunk size`, independent of
//! the total row count. Output is byte-for-byte deterministic for a given seed regardless of the
//! number of threads, because every chunk is generated from its own keyed RNG and written in
//! chunk order.

use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::Path;
use std::sync::mpsc;
use std::sync::{Arc, Mutex};

use arrow_array::RecordBatch;
use arrow_schema::SchemaRef;
use parquet::arrow::arrow_writer::{compute_leaves, ArrowColumnChunk, ArrowRowGroupWriterFactory};
use parquet::arrow::{add_encoded_arrow_schema_to_metadata, ArrowSchemaConverter};
use parquet::basic::{Compression, GzipLevel, ZstdLevel};
use parquet::file::properties::{EnabledStatistics, WriterProperties};
use parquet::file::writer::SerializedFileWriter;
use parquet::schema::types::ColumnPath;
use rayon::prelude::*;

use crate::errors::{NfError, Result};
use crate::providers::{push_date, push_datetime, Column, Ctx, Data, Kind};
use crate::rng::{chunks, Chunk, CHUNK_ROWS};
use crate::schema::{to_array, Plan};

// ---------------------------------------------------------------------------------------------
// Arrow IPC
// ---------------------------------------------------------------------------------------------

/// Serialize record batches as an Arrow IPC *stream*.
pub fn ipc_stream_bytes(schema: &SchemaRef, batches: &[RecordBatch]) -> Result<Vec<u8>> {
    let size: usize = batches.iter().map(RecordBatch::get_array_memory_size).sum();
    let mut w = arrow_ipc::writer::StreamWriter::try_new(Vec::with_capacity(size + 1024), schema)?;
    for b in batches {
        w.write(b)?;
    }
    w.finish()?;
    Ok(w.into_inner()?)
}

// ---------------------------------------------------------------------------------------------
// Shared streaming machinery
// ---------------------------------------------------------------------------------------------

/// Number of chunks generated concurrently per wave.
fn wave_chunks() -> usize {
    (rayon::current_num_threads() * 2).max(2)
}

/// Generate & serialize chunks in parallel waves; a dedicated I/O thread writes the buffers in
/// chunk order while the next wave is being generated. Serialization buffers are recycled
/// through a pool, so steady-state memory is ~2 waves of buffers regardless of row count.
fn stream_chunks<F>(path: &Path, header: Option<Vec<u8>>, count: usize, serialize: F) -> Result<()>
where
    F: Fn(Chunk, Vec<u8>) -> Vec<u8> + Sync,
{
    let file = File::create(path)?;
    let all = chunks(count);
    let wave = wave_chunks();
    let pool: Mutex<Vec<Vec<u8>>> = Mutex::new(Vec::new());
    let take = || {
        let mut b = pool
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .pop()
            .unwrap_or_default();
        b.clear();
        b
    };
    std::thread::scope(|scope| -> Result<()> {
        let (tx, rx) = mpsc::sync_channel::<Vec<Vec<u8>>>(0);
        let pool_ref = &pool;
        let io = scope.spawn(move || -> std::io::Result<()> {
            let mut out = BufWriter::with_capacity(1 << 20, file);
            if let Some(h) = header {
                out.write_all(&h)?;
            }
            for bufs in rx {
                for b in &bufs {
                    out.write_all(b)?;
                }
                pool_ref
                    .lock()
                    .unwrap_or_else(|e| e.into_inner())
                    .extend(bufs);
            }
            out.flush()
        });
        let mut send_err = false;
        for group in all.chunks(wave) {
            let bufs: Vec<Vec<u8>> = group.par_iter().map(|c| serialize(*c, take())).collect();
            if tx.send(bufs).is_err() {
                send_err = true;
                break;
            }
        }
        drop(tx);
        let res = io
            .join()
            .map_err(|_| NfError::Io(std::io::Error::other("writer thread panicked")))?;
        res?;
        if send_err {
            return Err(NfError::Io(std::io::Error::other(
                "writer thread stopped early",
            )));
        }
        Ok(())
    })
}

/// Text formatting of a non-string value (dates, numbers, booleans). Returns `false` for null.
fn format_scalar(col: &Column, i: usize, buf: &mut String) -> bool {
    buf.clear();
    if !col.is_valid(i) {
        return false;
    }
    match &col.data {
        Data::Int(v) => buf.push_str(itoa::Buffer::new().format(v[i])),
        Data::Float(v) => {
            if v[i].is_finite() {
                buf.push_str(ryu::Buffer::new().format_finite(v[i]));
            } else {
                return false;
            }
        }
        Data::Bool(v) => buf.push_str(if v[i] { "true" } else { "false" }),
        Data::Date(v) => push_date(buf, v[i]),
        Data::Timestamp(v) => push_datetime(buf, v[i]),
        Data::Str { .. } | Data::Cat { .. } => buf.push_str(col.str_at(i).unwrap_or_default()),
    }
    true
}

// ---------------------------------------------------------------------------------------------
// CSV
// ---------------------------------------------------------------------------------------------

/// CSV writer options.
#[derive(Debug, Clone)]
pub struct CsvOptions {
    pub header: bool,
    pub delimiter: u8,
}

impl Default for CsvOptions {
    fn default() -> Self {
        CsvOptions {
            header: true,
            delimiter: b',',
        }
    }
}

fn csv_writer(delimiter: u8, buf: Vec<u8>) -> csv::Writer<Vec<u8>> {
    csv::WriterBuilder::new()
        .delimiter(delimiter)
        .has_headers(false)
        .terminator(csv::Terminator::Any(b'\n'))
        .quote_style(csv::QuoteStyle::Necessary)
        .from_writer(buf)
}

fn finish_csv(w: csv::Writer<Vec<u8>>) -> Result<Vec<u8>> {
    w.into_inner()
        .map_err(|e| NfError::Io(std::io::Error::other(e.to_string())))
}

/// Stream `count` rows to a CSV file.
pub fn write_csv(
    plan: &Plan,
    count: usize,
    seed: u64,
    ctx: &Ctx,
    path: &Path,
    opts: &CsvOptions,
) -> Result<()> {
    let header = if opts.header {
        let mut w = csv_writer(opts.delimiter, Vec::with_capacity(256));
        w.write_record(plan.columns.iter().map(|c| c.name.as_bytes()))
            .map_err(|e| NfError::Io(std::io::Error::other(e.to_string())))?;
        Some(finish_csv(w)?)
    } else {
        None
    };
    let delimiter = opts.delimiter;
    stream_chunks(path, header, count, |chunk, buf| {
        let cols = plan.chunk_columns(chunk, seed, ctx);
        let mut w = csv_writer(delimiter, buf);
        let mut scratch = String::with_capacity(64);
        for i in 0..chunk.len {
            for col in &cols {
                let field: &[u8] = match &col.data {
                    Data::Str { .. } | Data::Cat { .. } if col.is_valid(i) => {
                        col.str_at(i).unwrap_or_default().as_bytes()
                    }
                    _ => {
                        if format_scalar(col, i, &mut scratch) {
                            scratch.as_bytes()
                        } else {
                            b""
                        }
                    }
                };
                w.write_field(field).expect("writing to a Vec cannot fail");
            }
            w.write_record(None::<&[u8]>)
                .expect("writing to a Vec cannot fail");
        }
        w.into_inner().expect("flushing a Vec cannot fail")
    })
}

// ---------------------------------------------------------------------------------------------
// JSON Lines
// ---------------------------------------------------------------------------------------------

#[inline]
fn push_json_str(out: &mut Vec<u8>, s: &str) {
    serde_json::to_writer(&mut *out, s).expect("writing to a Vec cannot fail");
}

/// Stream `count` rows to a JSON Lines file (one object per line).
pub fn write_jsonl(plan: &Plan, count: usize, seed: u64, ctx: &Ctx, path: &Path) -> Result<()> {
    let keys: Vec<Vec<u8>> = plan
        .columns
        .iter()
        .enumerate()
        .map(|(i, c)| {
            let mut k = Vec::new();
            k.push(if i == 0 { b'{' } else { b',' });
            push_json_str(&mut k, &c.name);
            k.push(b':');
            k
        })
        .collect();
    stream_chunks(path, None, count, |chunk, mut out| {
        let cols = plan.chunk_columns(chunk, seed, ctx);
        out.reserve(chunk.len * 24 * plan.len());
        let mut scratch = String::with_capacity(64);
        for i in 0..chunk.len {
            for (ci, col) in cols.iter().enumerate() {
                out.extend_from_slice(&keys[ci]);
                if !col.is_valid(i) {
                    out.extend_from_slice(b"null");
                    continue;
                }
                match &col.data {
                    Data::Str { .. } | Data::Cat { .. } => {
                        push_json_str(&mut out, col.str_at(i).unwrap_or_default());
                    }
                    Data::Date(_) | Data::Timestamp(_) => {
                        format_scalar(col, i, &mut scratch);
                        out.push(b'"');
                        out.extend_from_slice(scratch.as_bytes());
                        out.push(b'"');
                    }
                    _ => {
                        if format_scalar(col, i, &mut scratch) {
                            out.extend_from_slice(scratch.as_bytes());
                        } else {
                            out.extend_from_slice(b"null");
                        }
                    }
                }
            }
            out.extend_from_slice(b"}\n");
        }
        out
    })
}

// ---------------------------------------------------------------------------------------------
// Parquet
// ---------------------------------------------------------------------------------------------

/// Parquet writer options.
#[derive(Debug, Clone)]
pub struct ParquetOptions {
    pub compression: Compression,
    /// Target rows per row group (rounded up to a multiple of [`CHUNK_ROWS`]).
    pub row_group_size: usize,
}

impl Default for ParquetOptions {
    fn default() -> Self {
        ParquetOptions {
            compression: Compression::ZSTD(ZstdLevel::default()),
            row_group_size: 8 * CHUNK_ROWS,
        }
    }
}

/// Parse a compression codec name (`zstd`, `snappy`, `lz4`, `gzip`, `none`) and optional level.
pub fn parse_compression(name: &str, level: Option<i32>) -> Result<Compression> {
    let bad_level = |e: parquet::errors::ParquetError| {
        NfError::InvalidParameter(format!("invalid {name} compression level: {e}"))
    };
    Ok(match name.to_ascii_lowercase().as_str() {
        "zstd" | "zstandard" => Compression::ZSTD(match level {
            Some(l) => ZstdLevel::try_new(l).map_err(bad_level)?,
            None => ZstdLevel::default(),
        }),
        "snappy" => Compression::SNAPPY,
        "lz4" | "lz4_raw" => Compression::LZ4_RAW,
        "gzip" | "gz" => Compression::GZIP(match level {
            Some(l) => {
                GzipLevel::try_new(u32::try_from(l).unwrap_or(u32::MAX)).map_err(bad_level)?
            }
            None => GzipLevel::default(),
        }),
        "none" | "uncompressed" | "" => Compression::UNCOMPRESSED,
        other => {
            return Err(NfError::InvalidParameter(format!(
                "unknown parquet compression {other:?} (use zstd, snappy, lz4, gzip or none)"
            )))
        }
    })
}

/// Stream `count` rows to a Parquet file, encoding and compressing columns in parallel.
///
/// Each `(row group, column)` pair is an independent task that generates its values chunk by
/// chunk and encodes them with its own `ArrowColumnWriter`; finished column chunks are appended
/// to the file in order. Only a bounded number of row groups is in flight at any time.
pub fn write_parquet(
    plan: &Plan,
    count: usize,
    seed: u64,
    ctx: &Ctx,
    path: &Path,
    opts: &ParquetOptions,
) -> Result<()> {
    let schema = plan.arrow_schema();
    let mut builder = WriterProperties::builder()
        .set_compression(opts.compression)
        .set_statistics_enabled(EnabledStatistics::Chunk)
        .set_created_by(format!("nextfake {}", crate::VERSION));
    for c in &plan.columns {
        // Dictionary encoding only pays off for low-cardinality columns.
        let low_cardinality = matches!(c.provider.kind(), Kind::Cat | Kind::Bool | Kind::Date);
        builder = builder
            .set_column_dictionary_enabled(ColumnPath::from(c.name.as_str()), low_cardinality);
    }
    let mut props = builder.build();
    add_encoded_arrow_schema_to_metadata(&schema, &mut props);
    let props = Arc::new(props);
    let parquet_schema = ArrowSchemaConverter::new()
        .with_coerce_types(props.coerce_types())
        .convert(&schema)?;

    let file = BufWriter::with_capacity(1 << 20, File::create(path)?);
    let mut writer =
        SerializedFileWriter::new(file, parquet_schema.root_schema_ptr(), Arc::clone(&props))?;
    let factory = ArrowRowGroupWriterFactory::new(&writer, Arc::clone(&schema));

    let rg_rows = opts.row_group_size.max(1).div_ceil(CHUNK_ROWS) * CHUNK_ROWS;
    let n_groups = count.div_ceil(rg_rows);
    let ncols = plan.len();
    let in_flight = (2 * rayon::current_num_threads())
        .div_ceil(ncols)
        .clamp(1, 16);
    let all_chunks = chunks(count);
    let chunks_per_group = rg_rows / CHUNK_ROWS;

    let mut group = 0;
    while group < n_groups {
        let wave_end = (group + in_flight).min(n_groups);
        let mut tasks = Vec::with_capacity((wave_end - group) * ncols);
        for rg in group..wave_end {
            for (ci, w) in factory.create_column_writers(rg)?.into_iter().enumerate() {
                tasks.push((rg, ci, w));
            }
        }
        let encoded: Vec<Result<ArrowColumnChunk>> = tasks
            .into_par_iter()
            .map(|(rg, ci, mut w)| -> Result<ArrowColumnChunk> {
                let first = rg * chunks_per_group;
                let last = ((rg + 1) * chunks_per_group).min(all_chunks.len());
                let field = schema.field(ci);
                for chunk in &all_chunks[first..last] {
                    let array = to_array(plan.column_chunk(ci, *chunk, seed, ctx));
                    for leaf in compute_leaves(field, &array)? {
                        w.write(&leaf)?;
                    }
                }
                Ok(w.close()?)
            })
            .collect();
        let mut it = encoded.into_iter();
        for _ in group..wave_end {
            let mut rg_writer = writer.next_row_group()?;
            for _ in 0..ncols {
                it.next()
                    .expect("one chunk per task")?
                    .append_to_row_group(&mut rg_writer)?;
            }
            rg_writer.close()?;
        }
        group = wave_end;
    }
    writer.close()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::locales;
    use crate::providers::{Params, Provider};
    use crate::schema::install;

    fn plan() -> Plan {
        let p = |n: &str| Provider::parse(n, &Params::new()).unwrap();
        Plan::new(vec![
            ("id".into(), p("serial"), 0.0),
            ("name".into(), p("name"), 0.0),
            ("email".into(), p("email"), 0.2),
            ("city".into(), p("city"), 0.0),
            ("price".into(), p("price"), 0.1),
            ("created_at".into(), p("datetime"), 0.0),
            ("born".into(), p("date"), 0.0),
            ("ok".into(), p("bool"), 0.0),
            ("bio".into(), p("sentence"), 0.0),
        ])
        .unwrap()
    }

    fn ctx() -> Ctx {
        Ctx {
            locale: locales::get("fr_FR").unwrap(),
            uuid7_base_ms: 0,
        }
    }

    fn tmp(name: &str) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!("nextfake-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        dir.join(name)
    }

    #[test]
    fn csv_and_jsonl_are_thread_invariant() {
        let plan = plan();
        let n = CHUNK_ROWS * 2 + 99;
        let (a, b) = (tmp("a.csv"), tmp("b.csv"));
        install(Some(1), || {
            write_csv(&plan, n, 1, &ctx(), &a, &CsvOptions::default())
        })
        .unwrap()
        .unwrap();
        install(Some(6), || {
            write_csv(&plan, n, 1, &ctx(), &b, &CsvOptions::default())
        })
        .unwrap()
        .unwrap();
        let (ca, cb) = (std::fs::read(&a).unwrap(), std::fs::read(&b).unwrap());
        assert_eq!(ca, cb);
        let text = String::from_utf8(ca).unwrap();
        assert_eq!(text.lines().count(), n + 1);
        assert!(text.starts_with("id,name,email,city,price,created_at,born,ok,bio\n1,"));

        let (ja, jb) = (tmp("a.jsonl"), tmp("b.jsonl"));
        install(Some(1), || write_jsonl(&plan, n, 1, &ctx(), &ja))
            .unwrap()
            .unwrap();
        install(Some(5), || write_jsonl(&plan, n, 1, &ctx(), &jb))
            .unwrap()
            .unwrap();
        let (xa, xb) = (std::fs::read(&ja).unwrap(), std::fs::read(&jb).unwrap());
        assert_eq!(xa, xb);
        for (i, line) in String::from_utf8(xa).unwrap().lines().enumerate() {
            let v: serde_json::Value = serde_json::from_str(line).unwrap();
            assert_eq!(v["id"], serde_json::json!(i + 1));
        }
    }

    #[test]
    fn parquet_is_thread_invariant() {
        let plan = plan();
        let n = CHUNK_ROWS * 9 + 5;
        let opts = ParquetOptions {
            row_group_size: CHUNK_ROWS * 2,
            ..Default::default()
        };
        let (a, b) = (tmp("a.parquet"), tmp("b.parquet"));
        install(Some(1), || write_parquet(&plan, n, 3, &ctx(), &a, &opts))
            .unwrap()
            .unwrap();
        install(Some(7), || write_parquet(&plan, n, 3, &ctx(), &b, &opts))
            .unwrap()
            .unwrap();
        assert_eq!(std::fs::read(&a).unwrap(), std::fs::read(&b).unwrap());
        let reader =
            parquet::file::reader::SerializedFileReader::new(File::open(&a).unwrap()).unwrap();
        use parquet::file::reader::FileReader;
        let md = reader.metadata();
        assert_eq!(md.file_metadata().num_rows() as usize, n);
        assert_eq!(md.num_row_groups(), 5);
    }

    #[test]
    fn ipc_roundtrip() {
        let plan = plan();
        let batches = plan.record_batches(1000, 1, &ctx()).unwrap();
        let bytes = ipc_stream_bytes(&plan.arrow_schema(), &batches).unwrap();
        let reader =
            arrow_ipc::reader::StreamReader::try_new(std::io::Cursor::new(bytes), None).unwrap();
        let back: Vec<RecordBatch> = reader.map(|b| b.unwrap()).collect();
        assert_eq!(back, batches);
    }

    #[test]
    fn compression_parsing() {
        assert!(parse_compression("zstd", Some(3)).is_ok());
        assert!(parse_compression("SNAPPY", None).is_ok());
        assert!(parse_compression("none", None).is_ok());
        assert!(parse_compression("brotli9000", None).is_err());
        assert!(parse_compression("zstd", Some(99)).is_err());
    }
}
