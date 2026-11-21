"""Field specifications: provider choices, parameters, constraints and nullability.

A :class:`Spec` tells nextfake *how* to generate one column. Specs are used as per-field
``overrides``, as values of raw ``dict`` schemas, and inside ``typing.Annotated`` metadata::

    import nextfake

    gen.generate(User, count=1_000, overrides={"age": nextfake.Int(18, 65)})
    gen.to_polars({"sku": nextfake.Pattern("SKU-#####"), "price": nextfake.Price(5, 50)}, 10)

    class Order(BaseModel):
        reference: Annotated[str, nextfake.Pattern("ORD-????-####")]
"""

from __future__ import annotations

import datetime as _dt
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal

__all__ = [
    "Bool",
    "Choice",
    "Constant",
    "Date",
    "DateTime",
    "Float",
    "Int",
    "Nullable",
    "Paragraph",
    "Pattern",
    "Price",
    "Provider",
    "Sentence",
    "Serial",
    "Spec",
    "String",
    "Text",
    "UnixTime",
]

_EPOCH_DATE = _dt.date(1970, 1, 1)
_EPOCH_DT = _dt.datetime(1970, 1, 1)


@dataclass(frozen=True)
class Spec:
    """A provider name plus parameters, nullability and an optional maximum length.

    Attributes:
        provider: Provider name (see ``nextfake.PROVIDERS``), e.g. ``"email"``.
        params: Provider parameters, e.g. ``{"min": 18, "max": 65}``.
        null_probability: Probability of ``None``; ``None`` inherits the field default
            (``0`` for required fields, the generator's ``null_probability`` for ``Optional``).
        max_length: Truncate generated strings to at most this many characters.
    """

    provider: str
    params: Mapping[str, Any] = field(default_factory=dict)
    null_probability: float | None = None
    max_length: int | None = None

    def nullable(self, probability: float = 0.1) -> Spec:
        """Return a copy that yields ``None`` with the given probability."""
        _check_probability(probability)
        return replace(self, null_probability=probability)

    def with_params(self, **params: Any) -> Spec:
        """Return a copy with extra/overridden provider parameters."""
        return replace(self, params={**self.params, **params})

    def truncate(self, max_length: int) -> Spec:
        """Return a copy whose string values are truncated to ``max_length`` characters."""
        if max_length < 0:
            raise ValueError("max_length must be >= 0")
        return replace(self, max_length=max_length)

    def to_column(
        self,
        name: str,
        *,
        null_probability: float = 0.0,
        seed_key: str | None = None,
    ) -> dict[str, Any]:
        """Serialize into the column-spec dict understood by the Rust core."""
        p = self.null_probability if self.null_probability is not None else null_probability
        col: dict[str, Any] = {
            "name": name,
            "provider": self.provider,
            "params": dict(self.params),
            "null_probability": float(p),
        }
        if self.max_length is not None:
            col["max_length"] = self.max_length
        if seed_key is not None and seed_key != name:
            col["seed_key"] = seed_key
        return col


def _check_probability(p: float) -> None:
    if not 0.0 <= p <= 1.0 or math.isnan(p):
        raise ValueError(f"probability must be within [0, 1], got {p!r}")


def _days(value: _dt.date | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = _dt.date.fromisoformat(value)
    if isinstance(value, _dt.datetime):
        value = value.date()
    return (value - _EPOCH_DATE).days


def _micros(value: _dt.datetime | _dt.date | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = _dt.datetime.fromisoformat(value)
    if not isinstance(value, _dt.datetime):
        value = _dt.datetime(value.year, value.month, value.day)
    if value.tzinfo is not None:
        value = value.astimezone(_dt.timezone.utc).replace(tzinfo=None)
    delta = value - _EPOCH_DT
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


def _clean(params: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


def Provider(name: str, /, **params: Any) -> Spec:
    """Any provider by name, e.g. ``Provider("email")`` or ``Provider("int", min=1, max=6)``."""
    return Spec(name, _clean(params))


def Int(min: int = 0, max: int = 10_000) -> Spec:
    """Uniform integer in ``[min, max]`` (inclusive)."""
    if min > max:
        raise ValueError(f"Int: min ({min}) must be <= max ({max})")
    return Spec("int", {"min": int(min), "max": int(max)})


def Float(
    min: float = 0.0,
    max: float = 1000.0,
    *,
    decimals: int | None = None,
) -> Spec:
    """Uniform float in ``[min, max)``, optionally rounded to ``decimals`` places."""
    if min > max:
        raise ValueError(f"Float: min ({min}) must be <= max ({max})")
    return Spec("float", _clean({"min": float(min), "max": float(max), "decimals": decimals}))


def Price(min: float = 1.0, max: float = 1000.0) -> Spec:
    """A price with exactly two decimal places in ``[min, max]``."""
    if min > max:
        raise ValueError(f"Price: min ({min}) must be <= max ({max})")
    return Spec("price", {"min": float(min), "max": float(max)})


def Bool(probability: float = 0.5) -> Spec:
    """``True`` with the given probability."""
    _check_probability(probability)
    return Spec("bool", {"probability": float(probability)})


def Choice(
    values: Sequence[str] | Sequence[int] | Sequence[float] | Sequence[bool],
    weights: Sequence[float] | None = None,
) -> Spec:
    """Pick from ``values`` (homogeneous str / int / float / bool), optionally weighted."""
    vals = list(values)
    if not vals:
        raise ValueError("Choice requires at least one value")
    if weights is not None and len(weights) != len(vals):
        raise ValueError("Choice: weights must have the same length as values")
    if all(isinstance(v, bool) for v in vals):
        if weights is None:
            p_true = sum(1 for v in vals if v) / len(vals)
        else:
            total = float(sum(weights))
            p_true = (
                sum(w for v, w in zip(vals, weights, strict=True) if v) / total if total else 0.0
            )
        return Bool(p_true)
    params: dict[str, Any] = {"values": vals}
    if weights is not None:
        params["weights"] = [float(w) for w in weights]
    return Spec("choice", params)


def Date(
    start: _dt.date | str | None = None,
    end: _dt.date | str | None = None,
) -> Spec:
    """A ``datetime.date`` in ``[start, end]`` (default 2000-01-01 .. 2025-12-31)."""
    return Spec("date", _clean({"start": _days(start), "end": _days(end)}))


def DateTime(
    start: _dt.datetime | _dt.date | str | None = None,
    end: _dt.datetime | _dt.date | str | None = None,
    *,
    resolution: Literal["s", "ms", "us"] = "s",
) -> Spec:
    """A naive UTC ``datetime`` in ``[start, end]`` (default 2020-01-01 .. 2025-12-31)."""
    return Spec(
        "datetime",
        _clean({"start": _micros(start), "end": _micros(end), "resolution": resolution}),
    )


def UnixTime(
    start: _dt.datetime | _dt.date | str | None = None,
    end: _dt.datetime | _dt.date | str | None = None,
) -> Spec:
    """Integer seconds since the Unix epoch."""
    s, e = _micros(start), _micros(end)
    params = {
        "start": None if s is None else s // 1_000_000,
        "end": None if e is None else e // 1_000_000,
    }
    return Spec("unix_time", _clean(params))


def Serial(start: int = 1, step: int = 1) -> Spec:
    """Row-number sequence ``start, start+step, ...`` (unique per generated batch)."""
    return Spec("serial", {"start": int(start), "step": int(step)})


def Pattern(pattern: str) -> Spec:
    """Template string: ``#`` digit, ``%`` 1-9, ``?`` A-Z, ``!`` a-z, ``*`` alphanumeric."""
    return Spec("pattern", {"pattern": pattern})


def Sentence(min_words: int = 4, max_words: int = 10) -> Spec:
    """A locale-appropriate sentence."""
    return Spec("sentence", {"min_words": min_words, "max_words": max_words})


def Paragraph(min_sentences: int = 3, max_sentences: int = 6) -> Spec:
    """A paragraph of several sentences."""
    return Spec("paragraph", {"min_sentences": min_sentences, "max_sentences": max_sentences})


Text = Paragraph


def String(min_length: int = 8, max_length: int = 16) -> Spec:
    """Random alphanumeric string with length in ``[min_length, max_length]``."""
    return Spec("string", {"min_length": min_length, "max_length": max_length})


def Constant(value: str) -> Spec:
    """Always the same string."""
    return Spec("constant", {"value": value})


def Nullable(spec: Spec | str, probability: float = 0.1) -> Spec:
    """Make any spec (or provider name) nullable."""
    base = Provider(spec) if isinstance(spec, str) else spec
    return base.nullable(probability)
