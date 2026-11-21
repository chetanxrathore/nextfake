//! `nextfake` — Rust core of a multi-core synthetic data generator for Python.
//!
//! The crate is usable as a plain Rust library (`rng`, `locales`, `providers`, `schema`,
//! `writers`); the PyO3 bindings that form the `nextfake._nextfake` extension module are
//! compiled only with the `python` cargo feature (enabled automatically by maturin).

pub mod errors;
pub mod locales;
pub mod providers;
pub mod rng;
pub mod schema;
pub mod writers;

/// Crate version, exposed to Python as `nextfake.__version__`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// PyO3 module registration: `nextfake._nextfake`.
#[cfg(feature = "python")]
#[pyo3::pymodule(gil_used = false)]
mod _nextfake {
    use std::collections::HashMap;
    use std::path::PathBuf;
    use std::sync::{Arc, Mutex, MutexGuard};

    use arrow_array::ffi_stream::FFI_ArrowArrayStream;
    use arrow_array::{RecordBatch, RecordBatchIterator};
    use arrow_schema::SchemaRef;

    use pyo3::exceptions::{PyKeyError, PyRuntimeError, PyTypeError, PyValueError};
    use pyo3::prelude::*;
    use pyo3::types::{
        PyBool, PyBytes, PyCapsule, PyDate, PyDateTime, PyDict, PyFloat, PyInt, PyList, PyString,
        PyTuple,
    };

    use crate::errors::NfError;
    use crate::locales::{self, Locale};
    use crate::providers::{
        self, civil_from_days, civil_from_micros, generate_column, Column, Ctx, Data, Kind, Param,
        Params, Provider,
    };
    use crate::rng::{self, FastRng};
    use crate::schema::{self, ColumnSpec, Plan};
    use crate::writers::{self, CsvOptions, ParquetOptions};

    #[pymodule_init]
    fn init(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add("__version__", super::VERSION)?;
        m.add("CHUNK_ROWS", rng::CHUNK_ROWS)?;
        m.add("PROVIDERS", providers::PROVIDER_NAMES.to_vec())?;
        m.add("LOCALES", locales::codes())?;
        m.add("DEBUG_BUILD", cfg!(debug_assertions))?;
        Ok(())
    }

    // -----------------------------------------------------------------------------------------
    // Argument parsing
    // -----------------------------------------------------------------------------------------

    fn extract_param(v: &Bound<'_, PyAny>) -> PyResult<Param> {
        if v.is_none() {
            return Ok(Param::Null);
        }
        if let Ok(b) = v.cast::<PyBool>() {
            return Ok(Param::Bool(b.is_true()));
        }
        if v.is_instance_of::<PyInt>() {
            return Ok(Param::Int(v.extract::<i64>()?));
        }
        if v.is_instance_of::<PyFloat>() {
            return Ok(Param::Float(v.extract::<f64>()?));
        }
        if let Ok(s) = v.cast::<PyString>() {
            return Ok(Param::Str(s.to_str()?.to_owned()));
        }
        if v.is_instance_of::<PyList>() || v.is_instance_of::<PyTuple>() {
            let items: Vec<Bound<'_, PyAny>> = v.try_iter()?.collect::<PyResult<_>>()?;
            let is_int =
                |i: &Bound<'_, PyAny>| i.is_instance_of::<PyInt>() && !i.is_instance_of::<PyBool>();
            if items.iter().all(|i| i.is_instance_of::<PyString>()) {
                return Ok(Param::StrList(
                    items.iter().map(|i| i.extract()).collect::<PyResult<_>>()?,
                ));
            }
            if items.iter().all(is_int) {
                return Ok(Param::IntList(
                    items.iter().map(|i| i.extract()).collect::<PyResult<_>>()?,
                ));
            }
            if items
                .iter()
                .all(|i| is_int(i) || i.is_instance_of::<PyFloat>())
            {
                return Ok(Param::FloatList(
                    items.iter().map(|i| i.extract()).collect::<PyResult<_>>()?,
                ));
            }
            return Err(PyTypeError::new_err(
                "list parameters must contain only str, only int, or only numbers",
            ));
        }
        Err(PyTypeError::new_err(format!(
            "unsupported parameter value of type {}",
            v.get_type().name()?
        )))
    }

    fn extract_params(d: Option<&Bound<'_, PyDict>>) -> PyResult<Params> {
        let mut params = Params::new();
        if let Some(d) = d {
            for (k, v) in d.iter() {
                params.insert(k.extract::<String>()?, extract_param(&v)?);
            }
        }
        Ok(params)
    }

    fn required<'py>(d: &Bound<'py, PyDict>, key: &str) -> PyResult<Bound<'py, PyAny>> {
        d.get_item(key)?
            .ok_or_else(|| PyKeyError::new_err(format!("column spec is missing {key:?}")))
    }

    fn optional<'py, T: FromPyObjectOwned<'py>>(
        d: &Bound<'py, PyDict>,
        key: &str,
    ) -> PyResult<Option<T>> {
        match d.get_item(key)? {
            Some(v) if !v.is_none() => Ok(Some(v.extract::<T>().map_err(Into::into)?)),
            _ => Ok(None),
        }
    }

    fn parse_plan(columns: &Bound<'_, PyAny>) -> PyResult<Plan> {
        let mut specs = Vec::new();
        for item in columns.try_iter()? {
            let item = item?;
            let d = item.cast::<PyDict>()?;
            let name: String = required(d, "name")?.extract()?;
            let provider_name: String = required(d, "provider")?.extract()?;
            let params = match d.get_item("params")? {
                Some(p) if !p.is_none() => extract_params(Some(p.cast::<PyDict>()?))?,
                _ => Params::new(),
            };
            let null_probability: f64 = optional(d, "null_probability")?.unwrap_or(0.0);
            let max_length: Option<usize> = optional(d, "max_length")?;
            let seed_key: Option<String> = optional(d, "seed_key")?;
            let mut provider =
                Provider::parse(&provider_name, &params).map_err(|e| with_column(e, &name))?;
            if let Some(n) = max_length {
                provider = Provider::truncated(provider, n).map_err(|e| with_column(e, &name))?;
            }
            specs.push(ColumnSpec {
                stream: rng::stream_id(seed_key.as_deref().unwrap_or(&name)),
                name,
                provider,
                null_probability,
            });
        }
        Ok(Plan::from_specs(specs)?)
    }

    fn with_column(e: NfError, name: &str) -> NfError {
        match e {
            NfError::UnknownProvider(p) => {
                NfError::UnknownProvider(format!("{p} (column {name:?})"))
            }
            NfError::InvalidParameter(m) => {
                NfError::InvalidParameter(format!("column {name:?}: {m}"))
            }
            other => other,
        }
    }

    fn plan_schema(plan: &Plan) -> SchemaRef {
        plan.arrow_schema()
    }

    fn arrow_type_name(kind: Kind) -> &'static str {
        match kind {
            Kind::Int => "int64",
            Kind::Float => "float64",
            Kind::Bool => "bool",
            Kind::Str | Kind::Cat => "string",
            Kind::Date => "date32",
            Kind::Timestamp => "timestamp[us]",
        }
    }

    // -----------------------------------------------------------------------------------------
    // Rust column -> Python object conversion
    // -----------------------------------------------------------------------------------------

    /// Per-column caches so immutable values (table strings, dates) are created once.
    enum Cache<'py> {
        Empty,
        Cat(Vec<Option<Bound<'py, PyAny>>>),
        Date(HashMap<i32, Bound<'py, PyAny>>),
    }

    struct Converter<'py> {
        py: Python<'py>,
        none: Bound<'py, PyAny>,
        caches: Vec<Cache<'py>>,
    }

    impl<'py> Converter<'py> {
        fn new(py: Python<'py>, ncols: usize) -> Self {
            Converter {
                py,
                none: py.None().into_bound(py),
                caches: (0..ncols).map(|_| Cache::Empty).collect(),
            }
        }

        #[inline]
        fn value(&mut self, ci: usize, col: &Column, i: usize) -> PyResult<Bound<'py, PyAny>> {
            let py = self.py;
            if !col.is_valid(i) {
                return Ok(self.none.clone());
            }
            Ok(match &col.data {
                Data::Int(v) => v[i].into_pyobject(py)?.into_any(),
                Data::Float(v) => PyFloat::new(py, v[i]).into_any(),
                Data::Bool(v) => PyBool::new(py, v[i]).to_owned().into_any(),
                Data::Str { offsets, data } => {
                    PyString::new(py, &data[offsets[i] as usize..offsets[i + 1] as usize])
                        .into_any()
                }
                Data::Cat { idx, table } => {
                    if !matches!(self.caches[ci], Cache::Cat(_)) {
                        self.caches[ci] = Cache::Cat(vec![None; table.len()]);
                    }
                    let Cache::Cat(cache) = &mut self.caches[ci] else {
                        unreachable!()
                    };
                    let k = idx[i] as usize;
                    match &cache[k] {
                        Some(s) => s.clone(),
                        None => {
                            let s = PyString::new(py, table.get(k)).into_any();
                            cache[k] = Some(s.clone());
                            s
                        }
                    }
                }
                Data::Date(v) => {
                    if !matches!(self.caches[ci], Cache::Date(_)) {
                        self.caches[ci] = Cache::Date(HashMap::new());
                    }
                    let Cache::Date(cache) = &mut self.caches[ci] else {
                        unreachable!()
                    };
                    match cache.get(&v[i]) {
                        Some(d) => d.clone(),
                        None => {
                            let (y, m, d) = civil_from_days(i64::from(v[i]));
                            let obj = PyDate::new(py, y as i32, m as u8, d as u8)?.into_any();
                            cache.insert(v[i], obj.clone());
                            obj
                        }
                    }
                }
                Data::Timestamp(v) => {
                    let c = civil_from_micros(v[i]);
                    PyDateTime::new(
                        py,
                        c.year as i32,
                        c.month as u8,
                        c.day as u8,
                        c.hour as u8,
                        c.minute as u8,
                        c.second as u8,
                        c.micro,
                        None,
                    )?
                    .into_any()
                }
            })
        }
    }

    // -----------------------------------------------------------------------------------------
    // CompiledPlan
    // -----------------------------------------------------------------------------------------

    /// A validated, reusable column plan (list of column specs compiled in Rust).
    #[pyclass(module = "nextfake._nextfake", name = "CompiledPlan", frozen)]
    pub struct CompiledPlan {
        plan: Arc<Plan>,
    }

    #[pymethods]
    impl CompiledPlan {
        #[new]
        fn new(columns: &Bound<'_, PyAny>) -> PyResult<Self> {
            Ok(CompiledPlan {
                plan: Arc::new(parse_plan(columns)?),
            })
        }

        /// Column names, in order.
        #[getter]
        fn names(&self) -> Vec<String> {
            self.plan.columns.iter().map(|c| c.name.clone()).collect()
        }

        /// Arrow type names of the output columns, in order.
        #[getter]
        fn arrow_types(&self) -> Vec<&'static str> {
            self.plan
                .columns
                .iter()
                .map(|c| arrow_type_name(c.provider.kind()))
                .collect()
        }

        fn __len__(&self) -> usize {
            self.plan.len()
        }

        fn __repr__(&self) -> String {
            let cols: Vec<String> = self
                .plan
                .columns
                .iter()
                .map(|c| format!("{}: {}", c.name, arrow_type_name(c.provider.kind())))
                .collect();
            format!("CompiledPlan({})", cols.join(", "))
        }
    }

    // -----------------------------------------------------------------------------------------
    // ArrowStream (Arrow PyCapsule C Stream Interface)
    // -----------------------------------------------------------------------------------------

    /// Generated Arrow record batches exposed through the Arrow PyCapsule interface
    /// (``__arrow_c_stream__``), consumable zero-copy by pyarrow, polars, duckdb, ...
    ///
    /// The stream can be consumed exactly once.
    #[pyclass(module = "nextfake._nextfake", name = "ArrowStream", frozen)]
    pub struct ArrowStream {
        inner: Mutex<Option<(Vec<RecordBatch>, SchemaRef)>>,
        num_rows: usize,
        num_batches: usize,
        column_names: Vec<String>,
    }

    #[pymethods]
    impl ArrowStream {
        #[pyo3(signature = (requested_schema = None))]
        fn __arrow_c_stream__<'py>(
            &self,
            py: Python<'py>,
            requested_schema: Option<Bound<'py, PyAny>>,
        ) -> PyResult<Bound<'py, PyCapsule>> {
            // The requested schema is advisory; we always produce our own schema.
            let _ = requested_schema;
            let (batches, schema) = self
                .inner
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .take()
                .ok_or_else(|| PyRuntimeError::new_err("ArrowStream was already consumed"))?;
            let reader = RecordBatchIterator::new(batches.into_iter().map(Ok), schema);
            let stream = FFI_ArrowArrayStream::new(Box::new(reader));
            PyCapsule::new_with_value(py, stream, c"arrow_array_stream")
        }

        /// Total number of rows in the stream.
        #[getter]
        fn num_rows(&self) -> usize {
            self.num_rows
        }

        /// Number of record batches in the stream.
        #[getter]
        fn num_batches(&self) -> usize {
            self.num_batches
        }

        /// Column names.
        #[getter]
        fn column_names(&self) -> Vec<String> {
            self.column_names.clone()
        }

        /// Whether the stream has already been exported.
        #[getter]
        fn consumed(&self) -> bool {
            self.inner
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .is_none()
        }

        fn __len__(&self) -> usize {
            self.num_rows
        }
    }

    // -----------------------------------------------------------------------------------------
    // Engine
    // -----------------------------------------------------------------------------------------

    /// 2025-01-01T00:00:00Z — UUIDv7 time base for seeded engines (keeps seeds reproducible).
    const SEEDED_UUID7_BASE_MS: u64 = 1_735_689_600_000;

    struct State {
        rng: FastRng,
        uuid7_ms: u64,
    }

    impl State {
        fn new(seed: Option<u64>) -> State {
            match seed {
                Some(s) => State {
                    rng: rng::session_rng(s),
                    uuid7_ms: SEEDED_UUID7_BASE_MS,
                },
                None => State {
                    rng: rng::session_rng(rng::entropy_seed()),
                    uuid7_ms: std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .map_or(SEEDED_UUID7_BASE_MS, |d| d.as_millis() as u64),
                },
            }
        }
    }

    /// The stateful generation engine behind `nextfake.Faker`.
    ///
    /// Single values are drawn from a sequential session RNG. Every bulk call draws a fresh
    /// 64-bit batch seed from that RNG and then generates rows in parallel with the GIL
    /// released, deterministically for any thread count.
    #[pyclass(module = "nextfake._nextfake", name = "Engine", frozen)]
    pub struct Engine {
        locale: &'static Locale,
        threads: Option<usize>,
        state: Mutex<State>,
    }

    impl Engine {
        fn lock(&self) -> MutexGuard<'_, State> {
            self.state.lock().unwrap_or_else(|e| e.into_inner())
        }

        /// Draw `(batch_seed, uuid7_base_ms)` for a bulk call of `count` rows.
        fn next_batch(&self, count: usize) -> (u64, u64) {
            use rand_core::Rng;
            let mut st = self.lock();
            let seed = st.rng.next_u64();
            let base = st.uuid7_ms;
            st.uuid7_ms = st.uuid7_ms.wrapping_add(count as u64);
            (seed, base)
        }

        fn ctx(&self, uuid7_base_ms: u64) -> Ctx {
            Ctx {
                locale: self.locale,
                uuid7_base_ms,
            }
        }

        /// Generate `count` rows with the GIL released.
        fn generate(
            &self,
            py: Python<'_>,
            plan: &Arc<Plan>,
            count: usize,
        ) -> PyResult<Vec<Vec<Column>>> {
            let (seed, base) = self.next_batch(count);
            let ctx = self.ctx(base);
            let threads = self.threads;
            let plan = Arc::clone(plan);
            Ok(py.detach(move || schema::install(threads, || plan.generate(count, seed, &ctx)))?)
        }

        /// Generate Arrow record batches with the GIL released.
        fn batches(
            &self,
            py: Python<'_>,
            plan: &Arc<Plan>,
            count: usize,
        ) -> PyResult<(Vec<RecordBatch>, SchemaRef)> {
            let (seed, base) = self.next_batch(count);
            let ctx = self.ctx(base);
            let threads = self.threads;
            let schema = plan_schema(plan);
            let plan = Arc::clone(plan);
            let batches = py.detach(move || {
                schema::install(threads, || plan.record_batches(count, seed, &ctx))
            })??;
            Ok((batches, schema))
        }

        /// Run a streaming file writer with the GIL released.
        fn write_with<F>(&self, py: Python<'_>, count: usize, f: F) -> PyResult<()>
        where
            F: FnOnce(u64, &Ctx) -> crate::errors::Result<()> + Send,
        {
            let (seed, base) = self.next_batch(count);
            let ctx = self.ctx(base);
            let threads = self.threads;
            py.detach(move || schema::install(threads, || f(seed, &ctx)))??;
            Ok(())
        }

        fn single_column_plan(provider: &str, params: &Params, null_p: f64) -> PyResult<Arc<Plan>> {
            let p = Provider::parse(provider, params)?;
            Ok(Arc::new(Plan::new(vec![(
                provider.to_string(),
                p,
                null_p,
            )])?))
        }
    }

    #[pymethods]
    impl Engine {
        #[new]
        #[pyo3(signature = (locale = "en_US", seed = None, threads = None))]
        fn new(locale: &str, seed: Option<u64>, threads: Option<usize>) -> PyResult<Self> {
            let loc = locales::get(locale).ok_or_else(|| NfError::UnknownLocale(locale.into()))?;
            if threads == Some(0) {
                return Err(
                    NfError::Schema("threads must be >= 1 (or None for all cores)".into()).into(),
                );
            }
            Ok(Engine {
                locale: loc,
                threads,
                state: Mutex::new(State::new(seed)),
            })
        }

        /// Locale code, e.g. ``"en_US"``.
        #[getter]
        fn locale(&self) -> &'static str {
            self.locale.code
        }

        /// Requested worker threads (``None`` = all cores).
        #[getter]
        fn threads(&self) -> Option<usize> {
            self.threads
        }

        /// Number of worker threads bulk calls will use.
        #[getter]
        fn effective_threads(&self) -> usize {
            schema::effective_threads(self.threads)
        }

        /// Reset the session RNG (``None`` = fresh OS entropy).
        #[pyo3(signature = (seed = None))]
        fn reseed(&self, seed: Option<u64>) {
            *self.lock() = State::new(seed);
        }

        /// Generate a single value from the sequential session RNG.
        #[pyo3(signature = (provider, params = None))]
        fn value<'py>(
            &self,
            py: Python<'py>,
            provider: &str,
            params: Option<&Bound<'py, PyDict>>,
        ) -> PyResult<Bound<'py, PyAny>> {
            let p = Provider::parse(provider, &extract_params(params)?)?;
            let col = {
                let mut st = self.lock();
                let ctx = self.ctx(st.uuid7_ms);
                st.uuid7_ms = st.uuid7_ms.wrapping_add(1);
                generate_column(&p, &ctx, &mut st.rng, 0, 1, 0.0)
            };
            Converter::new(py, 1).value(0, &col, 0)
        }

        /// Generate ``n`` values of one provider in parallel.
        #[pyo3(signature = (provider, n, params = None, null_probability = 0.0))]
        fn values<'py>(
            &self,
            py: Python<'py>,
            provider: &str,
            n: usize,
            params: Option<&Bound<'py, PyDict>>,
            null_probability: f64,
        ) -> PyResult<Bound<'py, PyList>> {
            let plan =
                Self::single_column_plan(provider, &extract_params(params)?, null_probability)?;
            let chunks = self.generate(py, &plan, n)?;
            let mut conv = Converter::new(py, 1);
            let mut out = Vec::with_capacity(n);
            for chunk in &chunks {
                let col = &chunk[0];
                for i in 0..col.len() {
                    out.push(conv.value(0, col, i)?);
                }
            }
            PyList::new(py, out)
        }

        /// Generate ``count`` rows as a list of dicts.
        fn dicts<'py>(
            &self,
            py: Python<'py>,
            plan: &CompiledPlan,
            count: usize,
        ) -> PyResult<Bound<'py, PyList>> {
            let chunks = self.generate(py, &plan.plan, count)?;
            let keys: Vec<Bound<'py, PyString>> = plan
                .plan
                .columns
                .iter()
                .map(|c| PyString::intern(py, &c.name))
                .collect();
            let mut conv = Converter::new(py, keys.len());
            let mut out = Vec::with_capacity(count);
            for chunk in &chunks {
                for i in 0..chunk[0].len() {
                    let d = PyDict::new(py);
                    for (ci, col) in chunk.iter().enumerate() {
                        d.set_item(&keys[ci], conv.value(ci, col, i)?)?;
                    }
                    out.push(d);
                }
            }
            PyList::new(py, out)
        }

        /// Generate ``count`` rows as a list of tuples (column order).
        fn tuples<'py>(
            &self,
            py: Python<'py>,
            plan: &CompiledPlan,
            count: usize,
        ) -> PyResult<Bound<'py, PyList>> {
            let chunks = self.generate(py, &plan.plan, count)?;
            let ncols = plan.plan.len();
            let mut conv = Converter::new(py, ncols);
            let mut out = Vec::with_capacity(count);
            let mut row = Vec::with_capacity(ncols);
            for chunk in &chunks {
                for i in 0..chunk[0].len() {
                    row.clear();
                    for (ci, col) in chunk.iter().enumerate() {
                        row.push(conv.value(ci, col, i)?);
                    }
                    out.push(PyTuple::new(py, row.drain(..))?);
                }
            }
            PyList::new(py, out)
        }

        /// Generate ``count`` rows as a dict of column lists.
        fn columns<'py>(
            &self,
            py: Python<'py>,
            plan: &CompiledPlan,
            count: usize,
        ) -> PyResult<Bound<'py, PyDict>> {
            let chunks = self.generate(py, &plan.plan, count)?;
            let mut conv = Converter::new(py, plan.plan.len());
            let out = PyDict::new(py);
            for (ci, spec) in plan.plan.columns.iter().enumerate() {
                let mut values = Vec::with_capacity(count);
                for chunk in &chunks {
                    let col = &chunk[ci];
                    for i in 0..col.len() {
                        values.push(conv.value(ci, col, i)?);
                    }
                }
                out.set_item(&spec.name, PyList::new(py, values)?)?;
            }
            Ok(out)
        }

        /// Generate ``count`` rows as an Arrow PyCapsule stream (one batch per 16,384 rows).
        fn arrow(
            &self,
            py: Python<'_>,
            plan: &CompiledPlan,
            count: usize,
        ) -> PyResult<ArrowStream> {
            let (batches, schema) = self.batches(py, &plan.plan, count)?;
            Ok(ArrowStream {
                num_rows: batches.iter().map(RecordBatch::num_rows).sum(),
                num_batches: batches.len(),
                column_names: schema.fields().iter().map(|f| f.name().clone()).collect(),
                inner: Mutex::new(Some((batches, schema))),
            })
        }

        /// Generate ``count`` rows serialized as Arrow IPC stream bytes.
        fn ipc<'py>(
            &self,
            py: Python<'py>,
            plan: &CompiledPlan,
            count: usize,
        ) -> PyResult<Bound<'py, PyBytes>> {
            let (batches, schema) = self.batches(py, &plan.plan, count)?;
            let bytes = py.detach(move || writers::ipc_stream_bytes(&schema, &batches))?;
            Ok(PyBytes::new(py, &bytes))
        }

        /// Stream ``count`` rows to a Parquet file (columns encoded in parallel).
        #[pyo3(signature = (plan, count, path, compression = "zstd", compression_level = None, row_group_size = 131_072))]
        #[allow(clippy::too_many_arguments)] // mirrors the Python keyword arguments
        fn write_parquet(
            &self,
            py: Python<'_>,
            plan: &CompiledPlan,
            count: usize,
            path: PathBuf,
            compression: &str,
            compression_level: Option<i32>,
            row_group_size: usize,
        ) -> PyResult<()> {
            if row_group_size == 0 {
                return Err(PyValueError::new_err("row_group_size must be >= 1"));
            }
            let opts = ParquetOptions {
                compression: writers::parse_compression(compression, compression_level)?,
                row_group_size,
            };
            let plan = Arc::clone(&plan.plan);
            self.write_with(py, count, move |seed, ctx| {
                writers::write_parquet(&plan, count, seed, ctx, &path, &opts)
            })
        }

        /// Stream ``count`` rows to a CSV file.
        #[pyo3(signature = (plan, count, path, header = true, delimiter = ","))]
        fn write_csv(
            &self,
            py: Python<'_>,
            plan: &CompiledPlan,
            count: usize,
            path: PathBuf,
            header: bool,
            delimiter: &str,
        ) -> PyResult<()> {
            let delimiter = match delimiter.as_bytes() {
                [b] if b.is_ascii() && *b != b'"' && *b != b'\n' && *b != b'\r' => *b,
                _ => {
                    return Err(PyValueError::new_err(
                        "delimiter must be a single ASCII character other than quote/newline",
                    ))
                }
            };
            let opts = CsvOptions { header, delimiter };
            let plan = Arc::clone(&plan.plan);
            self.write_with(py, count, move |seed, ctx| {
                writers::write_csv(&plan, count, seed, ctx, &path, &opts)
            })
        }

        /// Stream ``count`` rows to a JSON Lines file.
        fn write_jsonl(
            &self,
            py: Python<'_>,
            plan: &CompiledPlan,
            count: usize,
            path: PathBuf,
        ) -> PyResult<()> {
            let plan = Arc::clone(&plan.plan);
            self.write_with(py, count, move |seed, ctx| {
                writers::write_jsonl(&plan, count, seed, ctx, &path)
            })
        }

        fn __repr__(&self) -> String {
            format!(
                "Engine(locale={:?}, threads={})",
                self.locale.code,
                self.threads.map_or("None".to_string(), |t| t.to_string())
            )
        }
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn version_is_set() {
        assert_eq!(super::VERSION, "0.1.0");
    }
}
