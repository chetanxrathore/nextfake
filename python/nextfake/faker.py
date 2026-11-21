"""The :class:`Faker` generator and module-level convenience helpers."""

from __future__ import annotations

import datetime as _dt
import functools
import importlib
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast, overload

from nextfake import _nextfake as _nf
from nextfake.exceptions import MissingDependencyError, SchemaError
from nextfake.schema import CompiledSchema, KeyMode, compile_schema
from nextfake.types import Spec

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
    import pyarrow as pa
    from typing_extensions import Self

__all__ = ["Faker", "get_default", "seed"]

T = TypeVar("T")

_U64 = (1 << 64) - 1

#: Values accepted wherever a schema is expected.
SchemaLike = Any
Overrides = Mapping[str, "Spec | str"]
StrPath = str | os.PathLike[str]
Compression = Literal["zstd", "snappy", "lz4", "gzip", "none"]


def _norm_seed(seed: int | None) -> int | None:
    if seed is None:
        return None
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError(f"seed must be an int or None, got {type(seed).__name__}")
    return seed & _U64


def _check_count(count: int) -> int:
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError(f"count must be an int, got {type(count).__name__}")
    if count < 0:
        raise ValueError(f"count must be >= 0, got {count}")
    return count


@functools.lru_cache(maxsize=256)
def _list_adapter(model: Any) -> Any:
    from pydantic import TypeAdapter

    return TypeAdapter(list[model])


class Faker:
    """Rust-powered fake data generator.

    Args:
        locale: One of ``nextfake.LOCALES`` (``en_US``, ``en_GB``, ``de_DE``, ``fr_FR``,
            ``ja_JP``); ``"en-gb"`` / ``"de"`` style codes are accepted too.
        seed: Seed for fully reproducible output. ``None`` uses OS entropy.
        threads: Worker threads for bulk generation (``None`` = all CPU cores). Output for a
            given seed is identical for every thread count.
        null_probability: Default probability of ``None`` for ``Optional[...]`` fields.

    Single values (``gen.name()``) come from a sequential session RNG; bulk calls
    (``gen.names(10_000)``, ``gen.generate(User, 1_000)``, ``gen.to_polars(...)``) draw a
    fresh batch seed from that RNG and then generate in parallel with the GIL released.
    """

    __slots__ = ("_engine", "_null_probability")

    def __init__(
        self,
        locale: str = "en_US",
        seed: int | None = None,
        threads: int | None = None,
        *,
        null_probability: float = 0.1,
    ) -> None:
        if threads is not None and (isinstance(threads, bool) or threads < 1):
            raise ValueError("threads must be a positive int or None")
        if not 0.0 <= null_probability <= 1.0:
            raise ValueError("null_probability must be within [0, 1]")
        self._engine = _nf.Engine(locale, _norm_seed(seed), threads)
        self._null_probability = float(null_probability)

    # ------------------------------------------------------------------ configuration

    @property
    def locale(self) -> str:
        """The active locale code."""
        return self._engine.locale

    @property
    def threads(self) -> int | None:
        """Requested worker threads (``None`` = all cores)."""
        return self._engine.threads

    @property
    def effective_threads(self) -> int:
        """Worker threads actually used for bulk generation."""
        return self._engine.effective_threads

    @property
    def null_probability(self) -> float:
        """Default ``None`` probability for ``Optional`` fields."""
        return self._null_probability

    def seed(self, seed: int | None) -> None:
        """Re-seed this generator (``None`` = fresh OS entropy)."""
        self._engine.reseed(_norm_seed(seed))

    seed_instance = seed

    def __repr__(self) -> str:
        return f"Faker(locale={self.locale!r}, threads={self.threads!r})"

    # ------------------------------------------------------------------ generic access

    def value(self, provider: str | Spec, **params: Any) -> Any:
        """One value from any provider: ``gen.value("int", min=1, max=6)``."""
        if isinstance(provider, Spec):
            return self._engine.value(provider.provider, {**provider.params, **params})
        return self._engine.value(provider, params or None)

    def values(self, provider: str | Spec, n: int, **params: Any) -> list[Any]:
        """``n`` values from any provider, generated in parallel."""
        n = _check_count(n)
        if isinstance(provider, Spec):
            return self._engine.values(
                provider.provider,
                n,
                {**provider.params, **params},
                provider.null_probability or 0.0,
            )
        return self._engine.values(provider, n, params or None)

    def _s(self, provider: str, params: dict[str, Any] | None = None) -> str:
        return cast(str, self._engine.value(provider, params))

    def _ls(self, provider: str, n: int, params: dict[str, Any] | None = None) -> list[str]:
        return cast("list[str]", self._engine.values(provider, _check_count(n), params))

    # ------------------------------------------------------------------ person

    def first_name(self) -> str:
        return self._s("first_name")

    def last_name(self) -> str:
        return self._s("last_name")

    def name(self) -> str:
        return self._s("name")

    def username(self) -> str:
        return self._s("username")

    def email(self) -> str:
        return self._s("email")

    def phone_number(self) -> str:
        return self._s("phone_number")

    def first_names(self, n: int) -> list[str]:
        return self._ls("first_name", n)

    def last_names(self, n: int) -> list[str]:
        return self._ls("last_name", n)

    def names(self, n: int) -> list[str]:
        return self._ls("name", n)

    def usernames(self, n: int) -> list[str]:
        return self._ls("username", n)

    def emails(self, n: int) -> list[str]:
        return self._ls("email", n)

    def phone_numbers(self, n: int) -> list[str]:
        return self._ls("phone_number", n)

    # ------------------------------------------------------------------ internet & tech

    def ipv4(self) -> str:
        return self._s("ipv4")

    def ipv6(self) -> str:
        return self._s("ipv6")

    def mac_address(self) -> str:
        return self._s("mac_address")

    def domain_name(self) -> str:
        return self._s("domain_name")

    def url(self) -> str:
        return self._s("url")

    def user_agent(self) -> str:
        return self._s("user_agent")

    def uuid4(self) -> str:
        return self._s("uuid4")

    def uuid7(self) -> str:
        return self._s("uuid7")

    def ipv4s(self, n: int) -> list[str]:
        return self._ls("ipv4", n)

    def ipv6s(self, n: int) -> list[str]:
        return self._ls("ipv6", n)

    def mac_addresses(self, n: int) -> list[str]:
        return self._ls("mac_address", n)

    def domain_names(self, n: int) -> list[str]:
        return self._ls("domain_name", n)

    def urls(self, n: int) -> list[str]:
        return self._ls("url", n)

    def user_agents(self, n: int) -> list[str]:
        return self._ls("user_agent", n)

    def uuid4s(self, n: int) -> list[str]:
        return self._ls("uuid4", n)

    def uuid7s(self, n: int) -> list[str]:
        return self._ls("uuid7", n)

    # ------------------------------------------------------------------ location & business

    def street_address(self) -> str:
        return self._s("street_address")

    def city(self) -> str:
        return self._s("city")

    def state(self) -> str:
        return self._s("state")

    def state_abbr(self) -> str:
        return self._s("state_abbr")

    def postcode(self) -> str:
        return self._s("postcode")

    zipcode = postcode

    def country(self) -> str:
        return self._s("country")

    def country_code(self) -> str:
        return self._s("country_code")

    def address(self) -> str:
        return self._s("address")

    def company(self) -> str:
        return self._s("company")

    def job_title(self) -> str:
        return self._s("job_title")

    job = job_title

    def latitude(self) -> float:
        return cast(float, self._engine.value("latitude"))

    def longitude(self) -> float:
        return cast(float, self._engine.value("longitude"))

    def street_addresses(self, n: int) -> list[str]:
        return self._ls("street_address", n)

    def cities(self, n: int) -> list[str]:
        return self._ls("city", n)

    def states(self, n: int) -> list[str]:
        return self._ls("state", n)

    def postcodes(self, n: int) -> list[str]:
        return self._ls("postcode", n)

    def countries(self, n: int) -> list[str]:
        return self._ls("country", n)

    def country_codes(self, n: int) -> list[str]:
        return self._ls("country_code", n)

    def addresses(self, n: int) -> list[str]:
        return self._ls("address", n)

    def companies(self, n: int) -> list[str]:
        return self._ls("company", n)

    def job_titles(self, n: int) -> list[str]:
        return self._ls("job_title", n)

    # ------------------------------------------------------------------ finance & commerce

    def credit_card_number(self) -> str:
        """A Luhn-valid Visa / Mastercard / Amex / Discover number."""
        return self._s("credit_card_number")

    def currency_code(self) -> str:
        return self._s("currency_code")

    def price(self, min: float = 1.0, max: float = 1000.0) -> float:
        """A price with two decimal places in ``[min, max]``."""
        return cast(float, self._engine.value("price", {"min": min, "max": max}))

    def credit_card_numbers(self, n: int) -> list[str]:
        return self._ls("credit_card_number", n)

    def currency_codes(self, n: int) -> list[str]:
        return self._ls("currency_code", n)

    def prices(self, n: int, min: float = 1.0, max: float = 1000.0) -> list[float]:
        return cast(
            "list[float]", self._engine.values("price", _check_count(n), {"min": min, "max": max})
        )

    # ------------------------------------------------------------------ primitives

    def random_int(self, min: int = 0, max: int = 9999) -> int:
        """Uniform integer in ``[min, max]``."""
        return cast(int, self._engine.value("int", {"min": min, "max": max}))

    def random_ints(self, n: int, min: int = 0, max: int = 9999) -> list[int]:
        return cast(
            "list[int]", self._engine.values("int", _check_count(n), {"min": min, "max": max})
        )

    def pyfloat(
        self,
        min: float = 0.0,
        max: float = 1000.0,
        decimals: int | None = None,
    ) -> float:
        """Uniform float in ``[min, max)``."""
        params: dict[str, Any] = {"min": min, "max": max, "decimals": decimals}
        return cast(float, self._engine.value("float", params))

    def pyfloats(
        self,
        n: int,
        min: float = 0.0,
        max: float = 1000.0,
        decimals: int | None = None,
    ) -> list[float]:
        params: dict[str, Any] = {"min": min, "max": max, "decimals": decimals}
        return cast("list[float]", self._engine.values("float", _check_count(n), params))

    def pybool(self, probability: float = 0.5) -> bool:
        """``True`` with the given probability."""
        return cast(bool, self._engine.value("bool", {"probability": probability}))

    boolean = pybool

    def pybools(self, n: int, probability: float = 0.5) -> list[bool]:
        return cast(
            "list[bool]",
            self._engine.values("bool", _check_count(n), {"probability": probability}),
        )

    def random_element(self, values: Sequence[T]) -> T:
        """A uniformly random element of ``values``."""
        if not values:
            raise ValueError("random_element() requires a non-empty sequence")
        idx = cast(int, self._engine.value("int", {"min": 0, "max": len(values) - 1}))
        return values[idx]

    choice = random_element

    def random_elements(self, values: Sequence[T], n: int) -> list[T]:
        """``n`` random elements of ``values`` (with replacement)."""
        if not values:
            raise ValueError("random_elements() requires a non-empty sequence")
        idx = cast(
            "list[int]",
            self._engine.values("int", _check_count(n), {"min": 0, "max": len(values) - 1}),
        )
        return [values[i] for i in idx]

    def pattern(self, template: str) -> str:
        """Expand a template: ``#`` digit, ``%`` 1-9, ``?`` A-Z, ``!`` a-z, ``*`` alnum."""
        return self._s("pattern", {"pattern": template})

    bothify = pattern

    def password(self, length: int = 12) -> str:
        return self._s("password", {"length": length})

    def hex_color(self) -> str:
        return self._s("hex_color")

    # ------------------------------------------------------------------ time & text

    def date(self) -> _dt.date:
        """A ``datetime.date`` between 2000-01-01 and 2025-12-31."""
        return cast(_dt.date, self._engine.value("date"))

    date_object = date

    def date_of_birth(self) -> _dt.date:
        return cast(_dt.date, self._engine.value("date_of_birth"))

    def date_time(self) -> _dt.datetime:
        """A naive UTC ``datetime`` between 2020-01-01 and 2025-12-31."""
        return cast(_dt.datetime, self._engine.value("datetime"))

    datetime = date_time

    def iso8601(self) -> str:
        return self._s("iso8601")

    def unix_time(self) -> int:
        return cast(int, self._engine.value("unix_time"))

    def word(self) -> str:
        return self._s("word")

    def sentence(self, min_words: int = 4, max_words: int = 10) -> str:
        return self._s("sentence", {"min_words": min_words, "max_words": max_words})

    def paragraph(self, min_sentences: int = 3, max_sentences: int = 6) -> str:
        return self._s(
            "paragraph", {"min_sentences": min_sentences, "max_sentences": max_sentences}
        )

    text = paragraph

    def dates(self, n: int) -> list[_dt.date]:
        return cast("list[_dt.date]", self._engine.values("date", _check_count(n)))

    def date_times(self, n: int) -> list[_dt.datetime]:
        return cast("list[_dt.datetime]", self._engine.values("datetime", _check_count(n)))

    datetimes = date_times

    def words(self, n: int) -> list[str]:
        return self._ls("word", n)

    def sentences(self, n: int) -> list[str]:
        return self._ls("sentence", n)

    def paragraphs(self, n: int) -> list[str]:
        return self._ls("paragraph", n)

    # ------------------------------------------------------------------ schema-driven

    def compile(
        self,
        schema: SchemaLike,
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> CompiledSchema:
        """Compile (and cache) a schema without generating anything."""
        if isinstance(schema, CompiledSchema):
            return schema
        p = self._null_probability if null_probability is None else null_probability
        return compile_schema(schema, overrides=overrides, null_probability=p)

    def _flat_rows(self, cs: CompiledSchema, count: int, keys: KeyMode) -> list[dict[str, Any]]:
        plan = cs.plan(keys)
        if plan is None:
            return [{} for _ in range(count)]
        return self._engine.dicts(plan, count)

    def _build(
        self,
        cs: CompiledSchema,
        count: int,
        *,
        objects: bool,
        validate: bool,
        keys: KeyMode | None = None,
    ) -> list[Any]:
        if keys is None:
            keys = "input" if (objects and validate and cs.kind == "pydantic") else "name"
        rows = self._flat_rows(cs, count, keys)
        parent_validates = objects and validate and cs.kind == "pydantic"
        nested = cs.nested_fields
        for f in nested:
            assert f.nested is not None
            key = f.input_key if keys == "input" else f.name
            if parent_validates:
                sub = self._build(f.nested, count, objects=False, validate=validate, keys="input")
            else:
                sub = self._build(f.nested, count, objects=objects, validate=validate, keys=keys)
            if f.null_probability > 0.0:
                mask = self._engine.values("bool", count, {"probability": f.null_probability})
                sub = [None if m else s for s, m in zip(sub, mask, strict=True)]
            for r, s in zip(rows, sub, strict=True):
                r[key] = s
        if nested:
            order = [f.input_key if keys == "input" else f.name for f in cs.fields]
            rows = [{k: r[k] for k in order} for r in rows]
        convert_all = objects and not parent_validates
        for f in cs.flat_fields:
            conv = f.converter
            if conv is None or not (convert_all or f.always_convert):
                continue
            key = f.input_key if keys == "input" else f.name
            for r in rows:
                v = r[key]
                if v is not None:
                    r[key] = conv(v)
        if not objects:
            return rows
        if cs.kind == "pydantic":
            if parent_validates:
                return self._validate(cs, rows)
            construct = cs.target.model_construct
            return [construct(**r) for r in rows]
        if cs.kind == "dataclass":
            cls = cs.target
            return [cls(**r) for r in rows]
        return rows

    @staticmethod
    def _validate(cs: CompiledSchema, rows: list[dict[str, Any]]) -> list[Any]:
        from pydantic import ValidationError

        try:
            return cast("list[Any]", _list_adapter(cs.target).validate_python(rows))
        except ValidationError as exc:
            raise SchemaError(
                f"generated data failed validation for {cs.target.__name__}; add overrides "
                f"for the failing fields:\n{exc}"
            ) from exc

    @overload
    def generate(
        self,
        schema: type[T],
        count: int,
        *,
        overrides: Overrides | None = ...,
        null_probability: float | None = ...,
        validate: bool = ...,
    ) -> list[T]: ...

    @overload
    def generate(
        self,
        schema: Mapping[str, Any] | CompiledSchema,
        count: int,
        *,
        overrides: Overrides | None = ...,
        null_probability: float | None = ...,
        validate: bool = ...,
    ) -> list[dict[str, Any]]: ...

    def generate(
        self,
        schema: Any,
        count: int,
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
        validate: bool = True,
    ) -> list[Any]:
        """Generate ``count`` instances of ``schema``.

        * Pydantic v2 model -> ``list[Model]`` (validated by Pydantic unless ``validate=False``,
          which uses ``model_construct``),
        * dataclass -> ``list[Dataclass]``,
        * TypedDict -> ``list[dict]`` with values converted to the annotated types,
        * ``dict`` schema -> ``list[dict]``.
        """
        cs = self.compile(schema, overrides=overrides, null_probability=null_probability)
        if cs.kind == "pydantic":
            _require("pydantic", "generate() with a Pydantic model")
        return self._build(cs, _check_count(count), objects=True, validate=validate)

    def one(
        self,
        schema: type[T],
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> T:
        """Generate a single instance of ``schema``."""
        return self.generate(schema, 1, overrides=overrides, null_probability=null_probability)[0]

    def to_dicts(
        self,
        schema: SchemaLike,
        count: int,
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> list[dict[str, Any]]:
        """Generate ``count`` rows as plain dicts (raw values, nested models as dicts)."""
        cs = self.compile(schema, overrides=overrides, null_probability=null_probability)
        return cast(
            "list[dict[str, Any]]",
            self._build(cs, _check_count(count), objects=False, validate=False),
        )

    def to_tuples(
        self,
        schema: SchemaLike,
        count: int,
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> list[tuple[Any, ...]]:
        """Generate ``count`` rows as tuples in field order (flat schemas only)."""
        cs = self.compile(schema, overrides=overrides, null_probability=null_probability)
        return self._engine.tuples(cs.require_flat("to_tuples()"), _check_count(count))

    def to_columns(
        self,
        schema: SchemaLike,
        count: int,
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> dict[str, list[Any]]:
        """Generate ``count`` rows as a dict of column lists (flat schemas only)."""
        cs = self.compile(schema, overrides=overrides, null_probability=null_probability)
        return self._engine.columns(cs.require_flat("to_columns()"), _check_count(count))

    # ------------------------------------------------------------------ columnar & disk export

    def _flat_plan(
        self,
        schema: SchemaLike,
        operation: str,
        overrides: Overrides | None,
        null_probability: float | None,
    ) -> _nf.CompiledPlan:
        cs = self.compile(schema, overrides=overrides, null_probability=null_probability)
        return cs.require_flat(operation)

    def to_arrow_stream(
        self,
        schema: SchemaLike,
        count: int,
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> _nf.ArrowStream:
        """Generate an Arrow PyCapsule stream (``__arrow_c_stream__``).

        Built entirely in Rust with the GIL released; consumable zero-copy by any library that
        speaks the Arrow PyCapsule interface (pyarrow, polars, duckdb, ...). Needs no
        optional dependency.
        """
        plan = self._flat_plan(schema, "to_arrow_stream()", overrides, null_probability)
        return self._engine.arrow(plan, _check_count(count))

    def to_arrow(
        self,
        schema: SchemaLike,
        count: int,
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> pa.Table:
        """Generate a ``pyarrow.Table`` (zero-copy via the Arrow C stream interface)."""
        pa_mod = _import("pyarrow", "to_arrow()")
        stream = self.to_arrow_stream(
            schema, count, overrides=overrides, null_probability=null_probability
        )
        return pa_mod.RecordBatchReader.from_stream(stream).read_all()

    def to_arrow_ipc(
        self,
        schema: SchemaLike,
        count: int,
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> bytes:
        """Generate rows serialized as Arrow IPC *stream* bytes."""
        plan = self._flat_plan(schema, "to_arrow_ipc()", overrides, null_probability)
        return self._engine.ipc(plan, _check_count(count))

    def to_polars(
        self,
        schema: SchemaLike,
        count: int,
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> pl.DataFrame:
        """Generate a ``polars.DataFrame`` (Arrow C stream import, no pyarrow needed)."""
        pl_mod = _import("polars", "to_polars()")
        stream = self.to_arrow_stream(
            schema, count, overrides=overrides, null_probability=null_probability
        )
        return cast("pl.DataFrame", pl_mod.DataFrame(stream))

    def to_pandas(
        self,
        schema: SchemaLike,
        count: int,
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> pd.DataFrame:
        """Generate a ``pandas.DataFrame`` (via pyarrow when installed)."""
        pd_mod = _import("pandas", "to_pandas()")
        if _has("pyarrow"):
            table = self.to_arrow(
                schema, count, overrides=overrides, null_probability=null_probability
            )
            return cast("pd.DataFrame", table.to_pandas())
        cols = self.to_columns(
            schema, count, overrides=overrides, null_probability=null_probability
        )
        return cast("pd.DataFrame", pd_mod.DataFrame(cols))

    def to_parquet(
        self,
        schema: SchemaLike,
        count: int,
        path: StrPath,
        *,
        compression: Compression | str = "zstd",
        compression_level: int | None = None,
        row_group_size: int = 131_072,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> Path:
        """Stream ``count`` rows straight from Rust to a Parquet file.

        Rows are generated and columns encoded/compressed in parallel in bounded waves, so
        memory stays flat even for many millions of rows. Returns the output path.
        """
        plan = self._flat_plan(schema, "to_parquet()", overrides, null_probability)
        out = Path(path)
        self._engine.write_parquet(
            plan, _check_count(count), out, compression, compression_level, row_group_size
        )
        return out

    def to_jsonl(
        self,
        schema: SchemaLike,
        count: int,
        path: StrPath,
        *,
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> Path:
        """Stream ``count`` rows to a JSON Lines file (dates as ISO-8601 strings)."""
        plan = self._flat_plan(schema, "to_jsonl()", overrides, null_probability)
        out = Path(path)
        self._engine.write_jsonl(plan, _check_count(count), out)
        return out

    def to_csv(
        self,
        schema: SchemaLike,
        count: int,
        path: StrPath,
        *,
        header: bool = True,
        delimiter: str = ",",
        overrides: Overrides | None = None,
        null_probability: float | None = None,
    ) -> Path:
        """Stream ``count`` rows to a CSV file (nulls are empty fields)."""
        plan = self._flat_plan(schema, "to_csv()", overrides, null_probability)
        out = Path(path)
        self._engine.write_csv(plan, _check_count(count), out, header, delimiter)
        return out

    def __copy__(self) -> Self:
        raise TypeError("Faker instances hold RNG state and cannot be copied; create a new one")


def _import(module: str, feature: str) -> Any:
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise MissingDependencyError(
            f"{feature} requires the optional dependency {module!r}: pip install {module}"
        ) from exc


def _require(module: str, feature: str) -> None:
    _import(module, feature)


@functools.cache
def _has(module: str) -> bool:
    try:
        importlib.import_module(module)
    except ImportError:
        return False
    return True


# ---------------------------------------------------------------------------------------------
# Module-level default generator
# ---------------------------------------------------------------------------------------------

_default: Faker | None = None


def get_default() -> Faker:
    """The shared module-level :class:`Faker` used by ``nextfake.name()`` etc."""
    global _default
    if _default is None:
        _default = Faker()
    return _default


def seed(value: int | None) -> None:
    """Seed the module-level default generator."""
    get_default().seed(value)


# ---------------------------------------------------------------------------------------------
# Module-level single-value helpers (delegate to the default generator)
# ---------------------------------------------------------------------------------------------


def first_name() -> str:
    """Shortcut for ``Faker.first_name()`` on the shared default generator."""
    return get_default().first_name()


def last_name() -> str:
    """Shortcut for ``Faker.last_name()`` on the shared default generator."""
    return get_default().last_name()


def name() -> str:
    """Shortcut for ``Faker.name()`` on the shared default generator."""
    return get_default().name()


def username() -> str:
    """Shortcut for ``Faker.username()`` on the shared default generator."""
    return get_default().username()


def email() -> str:
    """Shortcut for ``Faker.email()`` on the shared default generator."""
    return get_default().email()


def phone_number() -> str:
    """Shortcut for ``Faker.phone_number()`` on the shared default generator."""
    return get_default().phone_number()


def ipv4() -> str:
    """Shortcut for ``Faker.ipv4()`` on the shared default generator."""
    return get_default().ipv4()


def ipv6() -> str:
    """Shortcut for ``Faker.ipv6()`` on the shared default generator."""
    return get_default().ipv6()


def mac_address() -> str:
    """Shortcut for ``Faker.mac_address()`` on the shared default generator."""
    return get_default().mac_address()


def domain_name() -> str:
    """Shortcut for ``Faker.domain_name()`` on the shared default generator."""
    return get_default().domain_name()


def url() -> str:
    """Shortcut for ``Faker.url()`` on the shared default generator."""
    return get_default().url()


def user_agent() -> str:
    """Shortcut for ``Faker.user_agent()`` on the shared default generator."""
    return get_default().user_agent()


def uuid4() -> str:
    """Shortcut for ``Faker.uuid4()`` on the shared default generator."""
    return get_default().uuid4()


def uuid7() -> str:
    """Shortcut for ``Faker.uuid7()`` on the shared default generator."""
    return get_default().uuid7()


def street_address() -> str:
    """Shortcut for ``Faker.street_address()`` on the shared default generator."""
    return get_default().street_address()


def city() -> str:
    """Shortcut for ``Faker.city()`` on the shared default generator."""
    return get_default().city()


def state() -> str:
    """Shortcut for ``Faker.state()`` on the shared default generator."""
    return get_default().state()


def postcode() -> str:
    """Shortcut for ``Faker.postcode()`` on the shared default generator."""
    return get_default().postcode()


def country() -> str:
    """Shortcut for ``Faker.country()`` on the shared default generator."""
    return get_default().country()


def country_code() -> str:
    """Shortcut for ``Faker.country_code()`` on the shared default generator."""
    return get_default().country_code()


def address() -> str:
    """Shortcut for ``Faker.address()`` on the shared default generator."""
    return get_default().address()


def company() -> str:
    """Shortcut for ``Faker.company()`` on the shared default generator."""
    return get_default().company()


def job_title() -> str:
    """Shortcut for ``Faker.job_title()`` on the shared default generator."""
    return get_default().job_title()


def credit_card_number() -> str:
    """Shortcut for ``Faker.credit_card_number()`` on the shared default generator."""
    return get_default().credit_card_number()


def currency_code() -> str:
    """Shortcut for ``Faker.currency_code()`` on the shared default generator."""
    return get_default().currency_code()


def iso8601() -> str:
    """Shortcut for ``Faker.iso8601()`` on the shared default generator."""
    return get_default().iso8601()


def word() -> str:
    """Shortcut for ``Faker.word()`` on the shared default generator."""
    return get_default().word()


def price(min: float = 1.0, max: float = 1000.0) -> float:
    """Module-level shortcut for :meth:`Faker.price`."""
    return get_default().price(min, max)


def random_int(min: int = 0, max: int = 9999) -> int:
    """Module-level shortcut for :meth:`Faker.random_int`."""
    return get_default().random_int(min, max)


def date() -> _dt.date:
    """Module-level shortcut for :meth:`Faker.date`."""
    return get_default().date()


def date_time() -> _dt.datetime:
    """Module-level shortcut for :meth:`Faker.date_time`."""
    return get_default().date_time()


def sentence() -> str:
    """Module-level shortcut for :meth:`Faker.sentence`."""
    return get_default().sentence()


def paragraph() -> str:
    """Module-level shortcut for :meth:`Faker.paragraph`."""
    return get_default().paragraph()


@overload
def generate(
    schema: type[T],
    count: int,
    *,
    overrides: Overrides | None = ...,
    null_probability: float | None = ...,
    validate: bool = ...,
) -> list[T]: ...


@overload
def generate(
    schema: Mapping[str, Any] | CompiledSchema,
    count: int,
    *,
    overrides: Overrides | None = ...,
    null_probability: float | None = ...,
    validate: bool = ...,
) -> list[dict[str, Any]]: ...


def generate(
    schema: Any,
    count: int,
    *,
    overrides: Overrides | None = None,
    null_probability: float | None = None,
    validate: bool = True,
) -> list[Any]:
    """Module-level shortcut for :meth:`Faker.generate`."""
    return get_default().generate(
        schema, count, overrides=overrides, null_probability=null_probability, validate=validate
    )


def to_dicts(
    schema: SchemaLike,
    count: int,
    *,
    overrides: Overrides | None = None,
    null_probability: float | None = None,
) -> list[dict[str, Any]]:
    """Module-level shortcut for :meth:`Faker.to_dicts`."""
    return get_default().to_dicts(
        schema, count, overrides=overrides, null_probability=null_probability
    )


def to_columns(
    schema: SchemaLike,
    count: int,
    *,
    overrides: Overrides | None = None,
    null_probability: float | None = None,
) -> dict[str, list[Any]]:
    """Module-level shortcut for :meth:`Faker.to_columns`."""
    return get_default().to_columns(
        schema, count, overrides=overrides, null_probability=null_probability
    )


def to_arrow(
    schema: SchemaLike,
    count: int,
    *,
    overrides: Overrides | None = None,
    null_probability: float | None = None,
) -> pa.Table:
    """Module-level shortcut for :meth:`Faker.to_arrow`."""
    return get_default().to_arrow(
        schema, count, overrides=overrides, null_probability=null_probability
    )


def to_polars(
    schema: SchemaLike,
    count: int,
    *,
    overrides: Overrides | None = None,
    null_probability: float | None = None,
) -> pl.DataFrame:
    """Module-level shortcut for :meth:`Faker.to_polars`."""
    return get_default().to_polars(
        schema, count, overrides=overrides, null_probability=null_probability
    )


def to_pandas(
    schema: SchemaLike,
    count: int,
    *,
    overrides: Overrides | None = None,
    null_probability: float | None = None,
) -> pd.DataFrame:
    """Module-level shortcut for :meth:`Faker.to_pandas`."""
    return get_default().to_pandas(
        schema, count, overrides=overrides, null_probability=null_probability
    )


def to_parquet(
    schema: SchemaLike,
    count: int,
    path: StrPath,
    *,
    compression: Compression | str = "zstd",
    compression_level: int | None = None,
    row_group_size: int = 131_072,
    overrides: Overrides | None = None,
    null_probability: float | None = None,
) -> Path:
    """Module-level shortcut for :meth:`Faker.to_parquet`."""
    return get_default().to_parquet(
        schema,
        count,
        path,
        compression=compression,
        compression_level=compression_level,
        row_group_size=row_group_size,
        overrides=overrides,
        null_probability=null_probability,
    )


def to_jsonl(
    schema: SchemaLike,
    count: int,
    path: StrPath,
    *,
    overrides: Overrides | None = None,
    null_probability: float | None = None,
) -> Path:
    """Module-level shortcut for :meth:`Faker.to_jsonl`."""
    return get_default().to_jsonl(
        schema, count, path, overrides=overrides, null_probability=null_probability
    )


def to_csv(
    schema: SchemaLike,
    count: int,
    path: StrPath,
    *,
    header: bool = True,
    delimiter: str = ",",
    overrides: Overrides | None = None,
    null_probability: float | None = None,
) -> Path:
    """Module-level shortcut for :meth:`Faker.to_csv`."""
    return get_default().to_csv(
        schema,
        count,
        path,
        header=header,
        delimiter=delimiter,
        overrides=overrides,
        null_probability=null_probability,
    )
