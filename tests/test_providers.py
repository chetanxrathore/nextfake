"""Core provider behaviour (NXFK-201)."""

from __future__ import annotations

import datetime as dt
import importlib.metadata
import ipaddress
import re
import uuid

import pytest

import nextfake
from tests.helpers import luhn_valid


def test_import_and_version() -> None:
    # The compiled module and the installed distribution metadata must agree (single source:
    # Cargo.toml), which also catches a stale `maturin develop` build.
    assert nextfake.__version__ == importlib.metadata.version("nextfake")
    assert "email" in nextfake.PROVIDERS
    assert set(nextfake.LOCALES) == {"en_US", "en_GB", "de_DE", "fr_FR", "ja_JP"}


def test_single_value_types(gen: nextfake.Faker) -> None:
    for method in (
        "first_name", "last_name", "name", "username", "email", "phone_number", "ipv4", "ipv6",
        "mac_address", "domain_name", "url", "user_agent", "uuid4", "uuid7", "street_address",
        "city", "state", "postcode", "country", "country_code", "address", "company",
        "job_title", "credit_card_number", "currency_code", "word", "sentence", "paragraph",
        "iso8601", "hex_color", "password",
    ):  # fmt: skip
        value = getattr(gen, method)()
        assert isinstance(value, str), method
        assert value, method
    assert isinstance(gen.price(), float)
    assert isinstance(gen.random_int(), int)
    assert isinstance(gen.pyfloat(), float)
    assert isinstance(gen.pybool(), bool)
    assert isinstance(gen.date(), dt.date)
    assert isinstance(gen.date_time(), dt.datetime)
    assert isinstance(gen.unix_time(), int)
    assert isinstance(gen.latitude(), float)


def test_batch_methods(gen: nextfake.Faker) -> None:
    assert len(gen.names(10_000)) == 10_000
    assert len(gen.emails(0)) == 0
    assert all(isinstance(x, str) for x in gen.cities(1000))
    assert len(set(gen.uuid4s(50_000))) == 50_000
    with pytest.raises(ValueError, match="count"):
        gen.names(-1)
    with pytest.raises(TypeError):
        gen.names(1.5)  # type: ignore[arg-type]


def test_credit_cards_are_luhn_valid(gen: nextfake.Faker) -> None:
    cards = gen.credit_card_numbers(20_000)
    assert all(luhn_valid(c) for c in cards)
    assert {len(c) for c in cards} <= {15, 16}
    prefixes = {c[0] for c in cards}
    assert {"3", "4", "5", "6"} <= prefixes | {"2"}


def test_uuid4_and_uuid7_valid(gen: nextfake.Faker) -> None:
    for u in gen.uuid4s(1000):
        assert uuid.UUID(u).version == 4
    v7 = gen.uuid7s(20_000)
    assert all(uuid.UUID(u).version == 7 for u in v7)
    assert v7 == sorted(v7), "UUIDv7 values must be monotonically sortable"
    singles = [gen.uuid7() for _ in range(100)]
    assert singles == sorted(singles)
    assert singles[0] > v7[-1], "monotonic across calls on the same generator"


def test_network_values_parse(gen: nextfake.Faker) -> None:
    for ip in gen.ipv4s(5000):
        addr = ipaddress.IPv4Address(ip)
        assert not addr.is_loopback
    for ip in gen.ipv6s(2000):
        ipaddress.IPv6Address(ip)
    for mac in gen.mac_addresses(500):
        assert re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", mac)
    for url in gen.urls(500):
        assert url.startswith(("http://", "https://"))


def test_emails_validate_with_email_validator(gen: nextfake.Faker) -> None:
    email_validator = pytest.importorskip("email_validator")
    for e in gen.emails(2000):
        email_validator.validate_email(e, check_deliverability=False)


def test_numeric_ranges(gen: nextfake.Faker) -> None:
    ints = gen.random_ints(50_000, 18, 65)
    assert min(ints) == 18
    assert max(ints) == 65
    floats = gen.pyfloats(10_000, -1.5, 2.5, decimals=2)
    assert all(-1.5 <= f <= 2.5 for f in floats)
    assert all(round(f, 2) == f for f in floats)
    prices = gen.prices(10_000, 5, 10)
    assert all(5 <= p <= 10 and round(p, 2) == p for p in prices)
    bools = gen.pybools(20_000, 0.8)
    assert 0.77 < sum(bools) / len(bools) < 0.83


def test_dates_and_datetimes(gen: nextfake.Faker) -> None:
    dates = gen.dates(5000)
    assert all(dt.date(2000, 1, 1) <= d <= dt.date(2025, 12, 31) for d in dates)
    dts = gen.date_times(5000)
    assert all(dt.datetime(2020, 1, 1) <= d < dt.datetime(2026, 1, 1) for d in dts)
    custom = gen.values(nextfake.DateTime("2024-01-01", "2024-01-31T23:59:59"), 2000)
    assert all(dt.datetime(2024, 1, 1) <= d <= dt.datetime(2024, 1, 31, 23, 59, 59) for d in custom)
    iso = gen.iso8601()
    dt.datetime.fromisoformat(iso)


def test_choice_pattern_and_generic(gen: nextfake.Faker) -> None:
    assert gen.random_element(["a", "b"]) in {"a", "b"}
    picks = gen.values(nextfake.Choice(["x", "y"], weights=[0.9, 0.1]), 10_000)
    assert 0.87 < picks.count("x") / 10_000 < 0.93
    assert re.fullmatch(r"ORD-[A-Z]{3}-\d{4}", gen.pattern("ORD-???-####"))
    assert gen.value("int", min=1, max=1) == 1
    assert gen.value(nextfake.Constant("k")) == "k"
    short = gen.values(nextfake.Provider("paragraph").truncate(5).nullable(0.5), 2000)
    assert all(v is None or len(v) <= 5 for v in short)
    assert 800 < sum(v is None for v in short) < 1200
    assert nextfake.Faker(seed=8).values(nextfake.Provider("email"), 50) == nextfake.Faker(
        seed=8
    ).values("email", 50)
    with pytest.raises(nextfake.ProviderError):
        gen.value("does_not_exist")
    with pytest.raises(nextfake.ProviderError):
        gen.value("int", min=10, max=1)


def test_sentences_and_paragraphs(gen: nextfake.Faker) -> None:
    s = gen.sentence()
    assert s[0].isupper()
    assert s.endswith(".")
    p = gen.paragraph()
    assert p.count(".") >= 3


def test_module_level_helpers() -> None:
    nextfake.seed(99)
    a = [nextfake.name(), nextfake.email(), nextfake.city()]
    nextfake.seed(99)
    b = [nextfake.name(), nextfake.email(), nextfake.city()]
    assert a == b
    assert isinstance(nextfake.date(), dt.date)
    assert isinstance(nextfake.price(), float)
