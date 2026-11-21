//! Typed errors for the Rust core and their mapping onto the Python exception hierarchy
//! defined in `nextfake/exceptions.py`.

use std::fmt;

/// All errors produced by the Rust core.
#[derive(Debug)]
pub enum NfError {
    /// A provider name that does not exist.
    UnknownProvider(String),
    /// A locale code that is not compiled into the binary.
    UnknownLocale(String),
    /// A provider parameter is missing, has the wrong type, or is out of range.
    InvalidParameter(String),
    /// The column plan itself is invalid (duplicate names, bad probabilities, ...).
    Schema(String),
    /// Filesystem error while writing an export.
    Io(std::io::Error),
    /// Error raised by the Arrow implementation.
    Arrow(arrow_schema::ArrowError),
    /// Error raised by the Parquet implementation.
    Parquet(parquet::errors::ParquetError),
}

/// Crate-wide result alias.
pub type Result<T> = std::result::Result<T, NfError>;

impl fmt::Display for NfError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            NfError::UnknownProvider(p) => write!(f, "unknown provider: {p:?}"),
            NfError::UnknownLocale(l) => write!(
                f,
                "unknown locale: {l:?} (available: {})",
                crate::locales::codes().join(", ")
            ),
            NfError::InvalidParameter(m) => write!(f, "invalid provider parameter: {m}"),
            NfError::Schema(m) => write!(f, "invalid schema: {m}"),
            NfError::Io(e) => write!(f, "I/O error: {e}"),
            NfError::Arrow(e) => write!(f, "Arrow error: {e}"),
            NfError::Parquet(e) => write!(f, "Parquet error: {e}"),
        }
    }
}

impl std::error::Error for NfError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            NfError::Io(e) => Some(e),
            NfError::Arrow(e) => Some(e),
            NfError::Parquet(e) => Some(e),
            _ => None,
        }
    }
}

impl From<std::io::Error> for NfError {
    fn from(e: std::io::Error) -> Self {
        NfError::Io(e)
    }
}

impl From<arrow_schema::ArrowError> for NfError {
    fn from(e: arrow_schema::ArrowError) -> Self {
        NfError::Arrow(e)
    }
}

impl From<parquet::errors::ParquetError> for NfError {
    fn from(e: parquet::errors::ParquetError) -> Self {
        NfError::Parquet(e)
    }
}

#[cfg(feature = "python")]
mod python {
    use super::NfError;
    use pyo3::PyErr;

    // The exception classes are defined once, in Python (`nextfake/exceptions.py`), and are
    // imported lazily on first use so Rust and Python share a single hierarchy.
    pyo3::import_exception!(nextfake.exceptions, ProviderError);
    pyo3::import_exception!(nextfake.exceptions, LocaleError);
    pyo3::import_exception!(nextfake.exceptions, SchemaError);
    pyo3::import_exception!(nextfake.exceptions, ExportError);

    impl From<NfError> for PyErr {
        fn from(e: NfError) -> PyErr {
            let msg = e.to_string();
            match e {
                NfError::UnknownProvider(_) | NfError::InvalidParameter(_) => {
                    ProviderError::new_err(msg)
                }
                NfError::UnknownLocale(_) => LocaleError::new_err(msg),
                NfError::Schema(_) => SchemaError::new_err(msg),
                NfError::Io(_) | NfError::Arrow(_) | NfError::Parquet(_) => {
                    ExportError::new_err(msg)
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn display_messages() {
        assert!(NfError::UnknownProvider("nope".into())
            .to_string()
            .contains("nope"));
        assert!(NfError::UnknownLocale("xx".into())
            .to_string()
            .contains("en_US"));
    }
}
