//! `nextfake` — Rust core of a multi-core synthetic data generator for Python.

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
