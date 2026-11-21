"""Seeded reproducibility across runs and thread counts (NXFK-201 AC)."""

from __future__ import annotations

import os

import pytest

import nextfake

SCHEMA = {
    "id": "int",
    "full_name": "name",
    "email": "email?",
    "city": "city",
    "ip_address": "ipv4",
    "created_at": "datetime",
    "uid": "uuid7",
    "score": nextfake.Float(0, 1),
    "dob": "date_of_birth",
    "card": "credit_card_number",
}

THREADS = [1, 2, 3, 8, os.cpu_count() or 4]


def test_same_seed_same_single_values() -> None:
    a = nextfake.Faker(seed=7)
    b = nextfake.Faker(seed=7)
    assert [a.name() for _ in range(100)] == [b.name() for _ in range(100)]
    assert [a.email() for _ in range(100)] == [b.email() for _ in range(100)]


def test_different_seed_differs() -> None:
    assert nextfake.Faker(seed=1).names(100) != nextfake.Faker(seed=2).names(100)


def test_unseeded_generators_differ() -> None:
    assert nextfake.Faker().names(50) != nextfake.Faker().names(50)


@pytest.mark.parametrize("threads", THREADS)
def test_thread_count_invariance_dicts(threads: int) -> None:
    n = nextfake.CHUNK_ROWS * 3 + 17
    ref = nextfake.Faker(seed=42, threads=1).to_dicts(SCHEMA, n)
    got = nextfake.Faker(seed=42, threads=threads).to_dicts(SCHEMA, n)
    assert got == ref


@pytest.mark.parametrize("threads", [1, 4, None])
def test_thread_count_invariance_batches(threads: int | None) -> None:
    ref = nextfake.Faker(seed=5, threads=1)
    gen = nextfake.Faker(seed=5, threads=threads)
    assert gen.emails(40_000) == ref.emails(40_000)
    assert gen.uuid7s(1000) == ref.uuid7s(1000)
    assert gen.credit_card_numbers(1000) == ref.credit_card_numbers(1000)


def test_reseed_restarts_stream() -> None:
    gen = nextfake.Faker(seed=11)
    first = gen.to_dicts(SCHEMA, 500)
    gen.seed(11)
    assert gen.to_dicts(SCHEMA, 500) == first


def test_successive_batches_differ() -> None:
    gen = nextfake.Faker(seed=3)
    assert gen.names(100) != gen.names(100)


def test_prefix_stability() -> None:
    small = nextfake.Faker(seed=9).to_dicts(SCHEMA, 100)
    large = nextfake.Faker(seed=9).to_dicts(SCHEMA, 50_000)
    assert large[:100] == small


def test_column_independence() -> None:
    base = nextfake.Faker(seed=4).to_dicts({"a": "email", "b": "city"}, 1000)
    extended = nextfake.Faker(seed=4).to_dicts({"x": "uuid4", "a": "email", "b": "city"}, 1000)
    assert [r["a"] for r in base] == [r["a"] for r in extended]
    assert [r["b"] for r in base] == [r["b"] for r in extended]


def test_negative_and_large_seeds() -> None:
    assert nextfake.Faker(seed=-1).name() == nextfake.Faker(seed=2**64 - 1).name()
    nextfake.Faker(seed=2**70).name()
