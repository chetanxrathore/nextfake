"""Golden-output test: pins the exact bytes generated for a fixed seed.

nextfake promises that a seed produces identical data on every OS, CPU architecture and thread
count, and only changes in a minor release with a changelog entry. CI runs this test on Linux
and Windows (x86_64) and macOS (arm64), so any platform-dependent or accidental change in
generated data fails here.

If a change to generated data is *intended*, regenerate the digests with::

    NEXTFAKE_UPDATE_GOLDEN=1 pytest tests/test_golden.py -s

paste them into ``GOLDEN`` and describe the change under "Changed data" in CHANGELOG.md.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
from pathlib import Path

import pytest

import nextfake

PARAMETERIZED = {
    "choice": nextfake.Choice(["a", "b", "c"], weights=[0.6, 0.3, 0.1]),
    "choice_int": nextfake.Choice([1, 2, 3]),
    "pattern": nextfake.Pattern("ID-####-??-!!-*%^\\#"),
    "constant": nextfake.Constant("k"),
    "int_step": nextfake.Int(-100, 100, multiple_of=7),
    "float_dec": nextfake.Float(0.01, 99.99, decimals=2),
    "float_step": nextfake.Float(0, 10, multiple_of=0.25),
    "datetime_ms": nextfake.DateTime("2021-01-01", "2021-12-31", resolution="ms"),
    "datetime_utc": nextfake.DateTime(utc=True),
    "time_us": nextfake.Time(resolution="us"),
    "duration_ms": nextfake.Duration(dt.timedelta(0), dt.timedelta(days=3), resolution="ms"),
    "fit_email": nextfake.Provider("email").length(min_length=10, max_length=20),
    "fit_name": nextfake.Provider("name").truncate(8),
    "nullable_city": nextfake.Nullable("city", 0.3),
}
SKIP = {"choice", "pattern", "constant"}  # need parameters; covered above
SCHEMA = {
    **{p: p for p in nextfake.PROVIDERS if p not in SKIP},
    **PARAMETERIZED,
}

GOLDEN: dict[str, str] = {
    "en_US": "a95361eaa2ad0f1811d6bc567956484be5fb4173292755d6d07894176f73f086",
    "en_GB": "86ad30e72697eba091369127ecae77d12565961ae5ea5dd3e96b7d1baa453bfa",
    "de_DE": "e0228d268243cb2fbd21ad31ec598dd6d86d6ed3bb555012e4a9355ba30403d5",
    "fr_FR": "05783888f1301d22d213ae5044f46158f2220d0ed842f5bfba392b2e2e6995f4",
    "ja_JP": "f084862ed2cc7ca2e0e5b5af603d8e6d51f796691f1687297aeabb80cadefbfc",
}


def _digest(locale: str, tmp: Path) -> str:
    gen = nextfake.Faker(locale, seed=20_261_123, threads=3)
    h = hashlib.sha256()
    # Two bulk batches (> 1 chunk each) through the Rust text writers...
    h.update(gen.to_csv(SCHEMA, 20_000, tmp / "g.csv").read_bytes())
    h.update(gen.to_jsonl(SCHEMA, 17_000, tmp / "g.jsonl").read_bytes())
    # ...then the sequential session stream used by single-value calls.
    for p in sorted(SCHEMA):
        spec = SCHEMA[p]
        value = gen.value(spec)
        h.update(repr((p, str(value))).encode())
    return h.hexdigest()


@pytest.mark.parametrize("locale", nextfake.LOCALES)
def test_golden_output(locale: str, tmp_path: Path) -> None:
    got = _digest(locale, tmp_path)
    if os.environ.get("NEXTFAKE_UPDATE_GOLDEN"):
        print(f'    "{locale}": "{got}",')
        return
    assert got == GOLDEN[locale], (
        f"generated data for {locale} changed; if intended, update GOLDEN (see module docs) "
        "and add a CHANGELOG entry"
    )


def test_golden_is_thread_count_invariant(tmp_path: Path) -> None:
    a = nextfake.Faker("en_US", seed=7, threads=1).to_csv(SCHEMA, 40_000, tmp_path / "a.csv")
    b = nextfake.Faker("en_US", seed=7, threads=None).to_csv(SCHEMA, 40_000, tmp_path / "b.csv")
    assert a.read_bytes() == b.read_bytes()
