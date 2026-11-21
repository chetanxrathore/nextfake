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

/// Crate version, exposed to Python as `nextfake.__version__`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

#[cfg(feature = "python")]
#[pyo3::pymodule(gil_used = false)]
mod _nextfake {
    use pyo3::prelude::*;

    #[pymodule_init]
    fn init(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add("__version__", super::VERSION)
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn version_is_set() {
        assert_eq!(super::VERSION, "0.1.0");
    }
}
