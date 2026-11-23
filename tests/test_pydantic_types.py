"""Pydantic-specific types and configuration: literals, enums, strict mode, aliases, dates."""

from __future__ import annotations

import datetime as dt
import decimal
import enum
import ipaddress
import uuid
from typing import Literal

import pytest
from pydantic import (
    AliasChoices,
    AliasPath,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    FutureDate,
    FutureDatetime,
    NaiveDatetime,
    PastDate,
    PastDatetime,
)

import nextfake


class Mixed(enum.Enum):
    ONE = 1
    TWO = "two"


class Choices(BaseModel):
    status: Literal["new", "paid", None]
    anything: Literal[1, "x", True]
    always_none: Literal[None]
    mixed: Mixed


def test_literals_with_none_and_mixed_types(gen: nextfake.Faker) -> None:
    rows = gen.generate(Choices, 3_000)
    assert {r.status for r in rows} == {"new", "paid", None}
    assert {repr(r.anything) for r in rows} == {"1", "'x'", "True"}
    assert all(r.always_none is None for r in rows)
    assert {r.mixed for r in rows} == {Mixed.ONE, Mixed.TWO}
    # Columnar exports need one value type per column and say so clearly.
    with pytest.raises(nextfake.UnsupportedTypeError, match="anything, mixed"):
        gen.to_arrow_stream(Choices, 10)


class Color(enum.Enum):
    RED = "r"
    GREEN = "g"


class Inner(BaseModel):
    model_config = ConfigDict(strict=True)
    ref: uuid.UUID


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True)
    id: uuid.UUID
    price: decimal.Decimal
    color: Color
    ip: ipaddress.IPv4Address
    when: dt.datetime
    inner: Inner


class StrictField(BaseModel):
    token: uuid.UUID = Field(strict=True)


def test_strict_models_validate(gen: nextfake.Faker) -> None:
    rows = gen.generate(StrictModel, 500)
    assert all(isinstance(r.id, uuid.UUID) and isinstance(r.color, Color) for r in rows)
    assert all(isinstance(r.inner.ref, uuid.UUID) for r in rows)
    assert all(isinstance(r.token, uuid.UUID) for r in gen.generate(StrictField, 100))


class Temporal(BaseModel):
    aware: AwareDatetime
    naive: NaiveDatetime
    past_date: PastDate
    future_date: FutureDate
    past_dt: PastDatetime
    future_dt: FutureDatetime
    at: dt.time
    took: dt.timedelta


def test_temporal_pydantic_types(gen: nextfake.Faker) -> None:
    rows = gen.generate(Temporal, 2_000)
    assert all(r.aware.tzinfo is dt.timezone.utc for r in rows)
    assert all(r.naive.tzinfo is None for r in rows)
    today = dt.date.today()
    assert all(r.past_date < today < r.future_date for r in rows)
    assert all(isinstance(r.at, dt.time) and isinstance(r.took, dt.timedelta) for r in rows)
    assert all(dt.timedelta(0) <= r.took <= dt.timedelta(days=30) for r in rows)


class PastOnly(BaseModel):
    born: PastDate
    seen: PastDatetime


def test_past_types_reproduce_without_reference_date() -> None:
    a = nextfake.Faker(seed=9).to_dicts(PastOnly, 200)
    b = nextfake.Faker(seed=9).to_dicts(PastOnly, 200)
    assert a == b
    # Fixed default ranges: independent of the calendar.
    assert max(r["born"] for r in a) <= dt.date(2025, 12, 31)


def test_reference_date_pins_future_types() -> None:
    ref = dt.date(2030, 6, 1)
    a = nextfake.Faker(seed=4, reference_date=ref)
    b = nextfake.Faker(seed=4, reference_date=dt.datetime(2030, 6, 1, 12))
    assert a.reference_date == b.reference_date == ref
    rows_a = a.to_dicts(Temporal, 500)
    assert rows_a == b.to_dicts(Temporal, 500)
    assert all(r["future_date"] > ref and r["past_date"] < ref for r in rows_a)
    assert all(r["future_dt"].date() > ref for r in rows_a)
    with pytest.raises(TypeError, match="reference_date"):
        nextfake.Faker(reference_date="2030-01-01")  # type: ignore[arg-type]


class Aliased(BaseModel):
    plain: int = Field(alias="Plain")
    choice: int = Field(validation_alias=AliasChoices("first", "second"))
    city: str = Field(validation_alias=AliasPath("address", 0, "city"))
    zip_code: str = Field(validation_alias=AliasPath("address", 0, "zip"))
    flat: str = Field(validation_alias=AliasPath("flat_key"))


class ByName(BaseModel):
    model_config = ConfigDict(validate_by_alias=False, validate_by_name=True)
    value: int = Field(alias="Value")


def test_validation_aliases(gen: nextfake.Faker) -> None:
    rows = gen.generate(Aliased, 200)
    assert all(isinstance(r.choice, int) and r.city and r.zip_code for r in rows)
    raw = gen.to_dicts(Aliased, 3)
    assert set(raw[0]) == {"plain", "choice", "city", "zip_code", "flat"}  # output keys = names
    assert len(gen.generate(ByName, 10)) == 10
