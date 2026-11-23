"""Field constraints: string lengths, decimal grids, ``multiple_of`` and ``max_digits``."""

from __future__ import annotations

import decimal
from typing import Annotated

import pytest
from pydantic import BaseModel, Field

import nextfake


class Contact(BaseModel):
    email: str = Field(min_length=5, max_length=100)
    city: str = Field(max_length=6)
    country_code: str = Field(min_length=3, max_length=3)
    code: str = Field(min_length=12, max_length=12)
    tag: Annotated[str, Field(min_length=2)]


def test_length_constraints_keep_semantic_providers(gen: nextfake.Faker) -> None:
    rows = gen.generate(Contact, 5_000)
    # Semantic providers stay semantic: whole e-mail addresses, real city names.
    assert all("@" in r.email and "." in r.email.split("@")[1] for r in rows)
    cities = set(nextfake.Faker(seed=1).cities(5_000))
    assert sum(r.city in cities for r in rows) > 0.95 * len(rows)
    # Bounds always hold, even when the provider cannot reach them (2-letter codes, min 3).
    assert all(len(r.country_code) == 3 for r in rows)
    assert all(len(r.city) <= 6 for r in rows)
    # Fields without a semantic provider get random strings of a fitting length.
    assert all(len(r.code) == 12 for r in rows)
    assert all(len(r.tag) >= 2 for r in rows)


def test_spec_length_bounds(gen: nextfake.Faker) -> None:
    spec = nextfake.Provider("name").length(min_length=12, max_length=14)
    names = gen.values(spec, 2_000)
    assert all(12 <= len(n) <= 14 for n in names)
    assert sum(" " in n for n in names) > 1_900  # redrawn whole names, rarely padded
    with pytest.raises(ValueError, match="min_length"):
        nextfake.Provider("name").length(min_length=5, max_length=2)
    with pytest.raises(nextfake.ProviderError, match="string providers"):
        gen.to_dicts({"n": nextfake.Int().length(max_length=2)}, 1)


class Money(BaseModel):
    score: decimal.Decimal = Field(gt=0, decimal_places=2)
    amount: decimal.Decimal = Field(max_digits=4, decimal_places=1)
    total: decimal.Decimal = Field(max_digits=5)
    ratio: float = Field(ge=0, le=1, multiple_of=0.05)


def test_decimal_places_and_max_digits_always_validate() -> None:
    # 200k rows: the old round-then-clamp bug produced 5e-324 for ~5 in 100k rows.
    rows = nextfake.Faker(seed=3).generate(Money, 200_000)
    assert min(r.score for r in rows) >= decimal.Decimal("0.01")
    assert max(r.amount for r in rows) <= decimal.Decimal("999.9")
    assert max(r.total for r in rows) <= decimal.Decimal("999.99")
    assert all(abs(r.ratio * 20 - round(r.ratio * 20)) < 1e-9 for r in rows[:1_000])


def test_float_decimals_grid(gen: nextfake.Faker) -> None:
    values = gen.values(nextfake.Float(0.15, 0.45, decimals=1), 5_000)
    assert set(values) <= {0.2, 0.3, 0.4}
    with pytest.raises(nextfake.ProviderError, match="grid"):
        gen.values(nextfake.Float(0.11, 0.19, decimals=1), 1)


class Steps(BaseModel):
    qty: int = Field(multiple_of=5)
    rating: int = Field(multiple_of=10)
    bounded: int = Field(ge=-17, le=42, multiple_of=5)
    weight: float = Field(ge=0, le=10, multiple_of=0.1)
    amount: decimal.Decimal = Field(multiple_of=decimal.Decimal("0.25"), max_digits=6)
    serial_id: int = Field(multiple_of=2)


def test_multiple_of(gen: nextfake.Faker) -> None:
    rows = gen.generate(Steps, 20_000)
    assert all(r.qty % 5 == 0 and r.rating % 10 == 0 for r in rows)
    assert {r.bounded for r in rows} <= set(range(-15, 41, 5))
    assert all(r.amount % decimal.Decimal("0.25") == 0 for r in rows)
    assert all(r.serial_id % 2 == 0 for r in rows)
    sevens = gen.values(nextfake.Int(1, 100, multiple_of=7), 1_000)
    assert set(sevens) == set(range(7, 99, 7))
