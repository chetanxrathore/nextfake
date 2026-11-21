"""Compiled locale tables (NXFK-202)."""

from __future__ import annotations

import re

import pytest

import nextfake


def _is_cjk(s: str) -> bool:
    return any("぀" <= ch <= "ヿ" or "一" <= ch <= "鿿" for ch in s)


@pytest.mark.parametrize("locale", nextfake.LOCALES)
def test_every_provider_in_every_locale(locale: str) -> None:
    gen = nextfake.Faker(locale=locale, seed=1)
    for provider in nextfake.PROVIDERS:
        params = {"values": ["a", "b"], "pattern": "##", "value": "c"}
        assert len(gen.values(provider, 64, **params)) == 64


def test_locale_aliases() -> None:
    assert nextfake.Faker("en-gb").locale == "en_GB"
    assert nextfake.Faker("de").locale == "de_DE"
    assert nextfake.Faker("ja").locale == "ja_JP"
    with pytest.raises(nextfake.LocaleError, match="available"):
        nextfake.Faker("xx_XX")


def test_en_us() -> None:
    gen = nextfake.Faker("en_US", seed=1)
    assert all(re.fullmatch(r"\d{5}", p) for p in gen.postcodes(1000))
    phones = gen.phone_numbers(500)
    assert all(len(re.sub(r"\D", "", p.split(" x")[0])) in (10, 11) for p in phones)
    assert "California" in set(gen.states(5000))


def test_en_gb() -> None:
    gen = nextfake.Faker("en_GB", seed=1)
    pattern = re.compile(r"[A-Z]{1,2}\d{1,2} \d[A-Z]{2}")
    assert all(pattern.fullmatch(p) for p in gen.postcodes(2000))
    assert any(p.startswith(("07", "+44", "020", "01")) for p in gen.phone_numbers(200))
    cities = set(gen.cities(5000))
    assert {"London", "Manchester"} <= cities
    assert "New York" not in cities


def test_de_de() -> None:
    gen = nextfake.Faker("de_DE", seed=1)
    assert all(re.fullmatch(r"\d{5}", p) for p in gen.postcodes(1000))
    assert any(ch in "".join(gen.last_names(2000)) for ch in "äöüß")
    streets = gen.street_addresses(500)
    assert all(re.search(r"\d+[a-c]?$", s) for s in streets)
    assert "München" in set(gen.cities(5000))
    assert all(p.startswith(("0", "+49")) for p in gen.phone_numbers(500))


def test_fr_fr() -> None:
    gen = nextfake.Faker("fr_FR", seed=1)
    codes = gen.postcodes(2000)
    assert all(re.fullmatch(r"\d{5}", p) and p[:2] != "20" for p in codes)
    phones = gen.phone_numbers(500)
    assert all(re.fullmatch(r"(\+33 \d|0\d)( \d\d){4}", p) for p in phones)
    assert any(
        w in s for s in gen.street_addresses(500) for w in (" rue ", " avenue ", " boulevard ")
    )


def test_ja_jp() -> None:
    gen = nextfake.Faker("ja_JP", seed=1)
    names = gen.names(200)
    assert all(_is_cjk(n) or "さくら" in n for n in names)
    assert all(re.fullmatch(r"\d{3}-\d{4}", p) for p in gen.postcodes(1000))
    phones = gen.phone_numbers(500)
    assert all(re.fullmatch(r"(\+81-)?0?\d{1,4}-\d{2,4}-\d{4}", p) for p in phones)
    assert "東京都" in set(gen.states(5000))
    # e-mails are romanised
    assert all(e.isascii() for e in gen.emails(500))
    assert gen.sentence().endswith("。")
    assert gen.address().startswith("〒")
