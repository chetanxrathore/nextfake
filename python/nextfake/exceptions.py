"""Exception hierarchy shared by the Python layer and the Rust core.

The Rust extension raises these exact classes (it imports them lazily), so callers only ever
need to catch :class:`NextFakeError` or one of its subclasses.
"""

from __future__ import annotations

__all__ = [
    "ExportError",
    "LocaleError",
    "MissingDependencyError",
    "NextFakeError",
    "ProviderError",
    "SchemaError",
    "UnsupportedTypeError",
]


class NextFakeError(Exception):
    """Base class for all nextfake errors."""


class SchemaError(NextFakeError, ValueError):
    """The schema (model, dataclass, TypedDict or mapping) could not be compiled."""


class UnsupportedTypeError(SchemaError, TypeError):
    """A field type cannot be generated automatically; supply an override."""


class ProviderError(NextFakeError, ValueError):
    """Unknown provider name or invalid provider parameters."""


class LocaleError(NextFakeError, ValueError):
    """The requested locale is not compiled into nextfake."""


class ExportError(NextFakeError, OSError):
    """Writing Arrow / Parquet / CSV / JSONL output failed."""


class MissingDependencyError(NextFakeError, ImportError):
    """An optional integration (pydantic, polars, pyarrow, pandas) is not installed."""
