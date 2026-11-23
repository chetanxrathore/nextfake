<div align="center">

# nextfake

**Rust-powered, multi-core synthetic data for Python.**
A Faker-style API that understands your Pydantic models, dataclasses and TypedDicts —
and writes straight to Arrow, Polars, Pandas, Parquet, CSV and JSONL at millions of rows per second.

[![CI](https://github.com/chetanxrathore/nextfake/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/chetanxrathore/nextfake/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)
![License](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-green)
![Typed](https://img.shields.io/badge/typing-mypy%20--strict-informational)

</div>

---

**Measured speedups** (6-column `User` schema, Apple M2 Max, release build — see [Benchmarks](#benchmarks)):

<!-- HEADLINE:START -->
| Benchmark | vs Faker | vs Mimesis | vs Polyfactory | nextfake time |
|---|---:|---:|---:|---:|
| 100,000 Python dicts | **414x** | **35x** | — | 41 ms |
| 100,000 Pydantic v2 models (validated) | — | — | **17x** | 1,787 ms |
| 1,000,000 rows -> Polars DataFrame | **3,674x**\* | **308x** | — | 44 ms |
| 1,000,000 rows -> Parquet on disk (zstd) | **2,380x**\* | **197x** | — | 70 ms |
<!-- HEADLINE:END -->

\* Faker's 1M-row times are linear extrapolations from a measured 100k-row run (a full run
would take ~3 minutes). The Pydantic benchmark validates every model, so nextfake's time there
is dominated by Pydantic + `email-validator` (`validate=False` is 4.5x faster).

## Why nextfake?

* **Fast by construction.** Generation runs in Rust on every core (rayon), with the GIL
  released. Bulk paths never create intermediate Python strings or dicts: Arrow buffers are
  built directly in Rust and handed to pyarrow / Polars zero-copy through the Arrow PyCapsule
  interface, and files are streamed to disk from Rust.
* **Schema-aware.** `gen.generate(User, count=10_000)` reads your Pydantic v2 model, dataclass
  or TypedDict — `Optional`, `Literal`, `Enum`, nested models, aliases, `ge/gt/le/lt`,
  `min_length/max_length` — and picks realistic providers from field names
  (`user_email` → e-mail, `signup_date` → datetime, `ip_address` → IPv4, `is_active` → bool).
* **Reproducible everywhere.** A seed produces byte-for-byte identical data on 1 thread or 64,
  on any machine, in any output format.
* **Typed.** Ships `py.typed` and complete stubs; `gen.generate(User, 100)` is inferred as
  `list[User]` under `mypy --strict`.
* **Zero required dependencies.** Pydantic, Polars, pyarrow and pandas are optional
  integrations detected at runtime. Five locales (`en_US`, `en_GB`, `de_DE`, `fr_FR`,
  `ja_JP`) are compiled into the binary — no data files, no runtime I/O.

## Installation

```bash
pip install nextfake                    # core (no dependencies)
pip install "nextfake[all]"             # + pydantic, polars, pyarrow, pandas
```

Wheels are built for CPython ≥ 3.10 (abi3) on Linux (manylinux & musllinux, x86_64/aarch64),
macOS (arm64/x86_64) and Windows x64. Building from source needs a Rust toolchain:
`pip install maturin && maturin develop --release`.

## Quick start

```python
import nextfake

gen = nextfake.Faker(locale="en_US", seed=42)       # threads=None -> all cores

gen.name()            # 'Charlotte Palmer'
gen.email()           # 'vincent_robinson@parker.com'
gen.credit_card_number()  # Luhn-valid
gen.uuid7()           # time-ordered, monotonically sortable
gen.emails(100_000)   # parallel batch -> list[str]

# Schema-driven generation
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class User(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    city: str
    ip_address: str
    age: int = Field(ge=18, le=65)
    created_at: datetime

users = gen.generate(User, count=1_000)        # list[User], validated by Pydantic
rows  = gen.to_dicts(User, 100_000)            # list[dict]
df    = gen.to_polars(User, 1_000_000)         # polars.DataFrame (built in Rust)
table = gen.to_arrow(User, 1_000_000)          # pyarrow.Table (zero-copy)
gen.to_parquet(User, 5_000_000, "users.parquet")   # streamed, bounded memory
gen.to_csv(User, 1_000_000, "users.csv")
gen.to_jsonl(User, 1_000_000, "users.jsonl")

# No model? Use a dict schema (provider names or types; "?" = nullable)
gen.to_polars({"id": "int", "email": "email", "created_at": "datetime", "phone": "phone_number?"}, 10)
```

Module-level shortcuts use a shared default generator: `nextfake.name()`,
`nextfake.seed(1)`, `nextfake.generate(User, 10)`, `nextfake.to_polars(...)`, ...

## Side by side

<table>
<tr><th>Faker + Polyfactory</th><th>nextfake</th></tr>
<tr><td>

```python
from faker import Faker
import polars as pl

fake = Faker()
rows = [
    {
        "id": i,
        "full_name": fake.name(),
        "email": fake.email(),
        "city": fake.city(),
        "ip_address": fake.ipv4(),
        "created_at": fake.date_time(),
    }
    for i in range(1_000_000)
]
df = pl.DataFrame(rows)
df.write_parquet("users.parquet")
```

</td><td>

```python
import nextfake

gen = nextfake.Faker()
gen.to_parquet(
    {
        "id": "int",
        "full_name": "name",
        "email": "email",
        "city": "city",
        "ip_address": "ipv4",
        "created_at": "datetime",
    },
    1_000_000,
    "users.parquet",
)
```

</td></tr>
<tr><td>

```python
from polyfactory import Use
from polyfactory.factories.pydantic_factory import (
    ModelFactory,
)

class UserFactory(ModelFactory[User]):
    __model__ = User
    # semantic fields must be wired by hand
    full_name = Use(ModelFactory.__faker__.name)
    city = Use(ModelFactory.__faker__.city)

users = UserFactory.batch(100_000)
```

</td><td>

```python
import nextfake

gen = nextfake.Faker()

# full_name, city, email, ip_address, ...
# are inferred from field names + types
users = gen.generate(User, 100_000)
```

</td></tr>
</table>

## Schema inference

| Source | Supported |
|---|---|
| Pydantic v2 `BaseModel` | field types, `Field(ge/gt/le/lt/multiple_of/min_length/max_length/decimal_places/max_digits)`, aliases (incl. `AliasChoices`, `AliasPath`), strict mode, defaults, nested models, `EmailStr`, `HttpUrl`/`AnyUrl`, `IPvAnyAddress`, `SecretStr`, `PaymentCardNumber`, `AwareDatetime`/`NaiveDatetime`, `PastDate`/`FutureDate`/`PastDatetime`/`FutureDatetime` |
| `dataclasses` | all `init` fields, defaults, `field(metadata={"nextfake": spec})` |
| `TypedDict` | `Required`/`NotRequired`, nested TypedDicts |
| `dict` schema | `{"col": "provider" \| "type" \| Spec \| python_type \| {nested}}`, `"provider?"` for nullable |
| Types | `int`, `float`, `bool`, `str`, `bytes`, `Decimal`, `date`, `datetime`, `time`, `timedelta`, `UUID`, `IPv4Address`, `IPv6Address`, `Literal[...]` (incl. `None` and mixed types), `Enum`, `Optional[T]`, `T \| None`, `Annotated[T, spec]` |

Provider selection order: explicit `overrides=` → `Annotated[..., nextfake.Spec]` →
`Literal`/`Enum` → **field-name heuristics** (reconciled with the annotation) → type default,
narrowed by constraints.

A few of the heuristics (see `nextfake.infer_provider("field_name")`):

| Field name | Provider | Field name | Provider |
|---|---|---|---|
| `full_name`, `customer_name`, `author` | `name` | `created_at`, `signup_date`, `updatedAt` | `datetime` |
| `user_email`, `contactEmail` | `email` | `price`, `amount`, `total_amount` | `price` |
| `ip`, `ip_address`, `client_ip` | `ipv4` | `is_active`, `has_children`, `verified` | `bool` |
| `country_code`, `billing_country_code` | `country_code` | `zip`, `postal_code` | `postcode` |
| `phone`, `mobile_phone` | `phone_number` | `description`, `bio`, `notes` | `paragraph` |
| `id` (int) / `user_id` (str) | `serial` / `uuid4` | `dob`, `birthday` | `date_of_birth` |

Heuristics respect the annotation: `created_at: int` becomes a Unix timestamp,
`signup_date: str` an ISO-8601 string, `user_id: str` a UUID.

Constraints are honoured so generated models always validate:

* **Lengths** keep providers meaningful: `email: str = Field(max_length=20)` redraws until a
  whole address fits instead of cutting one in half. Only when no draw fits (a 2-letter
  country code with `min_length=3`) is the value padded or truncated.
* **Numbers** respect `ge`/`gt`/`le`/`lt`, `multiple_of`, and for `Decimal` also
  `decimal_places` and `max_digits`; values are drawn on the exact grid, never rounded past a
  bound.
* **Strict models** (`ConfigDict(strict=True)` or `Field(strict=True)`) receive exact types
  (`UUID`, `Decimal`, `Enum` members, ...).
* **Past/future types**: `PastDate`/`PastDatetime` use the fixed default ranges, so they
  reproduce forever. `FutureDate`/`FutureDatetime` are relative to today unless you pin
  `Faker(reference_date=date(2030, 1, 1))`.

### Overrides, constraints and nulls

```python
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

import nextfake

class Order(BaseModel):
    reference: Annotated[str, nextfake.Pattern("ORD-????-####")]   # inline spec
    quantity: int = Field(ge=1, le=10)                            # constraints honoured
    coupon: Optional[str] = None                                  # None with p = null_probability
    status: Literal["new", "paid", "shipped"]

gen = nextfake.Faker(seed=1, null_probability=0.2)
orders = gen.generate(
    Order,
    count=10_000,
    overrides={
        "quantity": nextfake.Int(1, 3),
        "status": nextfake.Choice(["new", "paid", "shipped"], weights=[0.7, 0.2, 0.1]),
        "coupon": nextfake.Pattern("SAVE##").nullable(0.9),
    },
)
```

Specs: `Provider(name, **params)`, `Int(min, max, multiple_of=)`,
`Float(min, max, decimals=, multiple_of=)`, `Price`, `Bool`, `Choice`, `Date`,
`DateTime(..., utc=)`, `Time`, `Duration`, `UnixTime`, `Serial`, `Pattern`, `Sentence`,
`Paragraph`/`Text`, `String`, `Constant`, `Nullable`, plus `.nullable(p)`,
`.length(min_length, max_length)`, `.truncate(n)`, `.with_params(...)`.

## Exports

| Method | Returns | Notes |
|---|---|---|
| `generate(schema, n)` | `list[Model]` | Pydantic-validated (`validate=False` → `model_construct`), dataclass instances, converted TypedDicts |
| `to_dicts` / `to_tuples` / `to_columns` | Python objects | Built directly from Rust buffers; immutable strings & dates are shared |
| `to_arrow_stream` | `ArrowStream` | `__arrow_c_stream__` PyCapsule — no dependency needed (DuckDB, pyarrow, Polars, ...) |
| `to_arrow` / `to_polars` / `to_pandas` | tables / DataFrames | Zero-copy Arrow import (Polars needs no pyarrow) |
| `to_arrow_ipc` | `bytes` | Arrow IPC stream |
| `to_parquet(path, compression="zstd")` | `Path` | Row groups × columns encoded in parallel; `zstd`, `snappy`, `lz4`, `gzip`, `none` |
| `to_csv(path, delimiter=",")` / `to_jsonl(path)` | `Path` | RFC-4180 quoting / ISO-8601 dates |

Disk writers stream in bounded waves with a dedicated I/O thread and recycled buffers:
peak memory is flat whether you write 1M or 100M rows.

Arrow types: `int64`, `float64`, `bool`, `string`, `date32`, `timestamp[us]` (naive UTC),
`timestamp[us, tz=UTC]` (`DateTime(utc=True)`, `AwareDatetime`), `time64[us]`, `duration[us]`.
CSV / JSONL write ISO-8601 dates, times and durations (`P1DT2H3M4S`).

## Determinism & parallelism

```python
a = nextfake.Faker(seed=7, threads=1).to_polars(User, 1_000_000)
b = nextfake.Faker(seed=7, threads=32).to_polars(User, 1_000_000)
assert a.equals(b)                       # identical, any thread count / CPU
```

* Rows are split into fixed 16,384-row chunks; every `(chunk, column)` pair has its own
  `ChaCha8Rng`, keyed by `(seed, chunk)` with a 64-bit stream derived from the column *name*.
  Work is scheduled across all cores, results are reassembled in order.
* Adding or reordering columns never changes the values of existing columns, and the first
  *k* rows of a dataset don't depend on how many rows you generate.
* The same seed gives the same data in `to_dicts`, `to_arrow`, `to_polars`, `to_parquet`, ...
* Default date ranges are fixed (2020–2025 for datetimes), not relative to "now", so a seed
  reproduces forever. UUIDv7 timestamps start at 2025-01-01 for seeded generators.
  `FutureDate`/`FutureDatetime` fields are the one calendar-relative exception — pin them
  with `Faker(reference_date=...)`.
* Single-value calls (`gen.name()`) use a sequential session RNG; each bulk call draws a new
  batch seed from it. Reproducibility therefore means: same seed, same nextfake version, same
  sequence of calls on the `Faker`.
* Identical output on Linux, macOS and Windows, x86_64 and arm64 is enforced in CI by a
  golden-output test (`tests/test_golden.py`).

### Stability policy (1.x)

* **API:** semantic versioning. Public names in `nextfake.__all__` and their documented
  behaviour only change in a major release; deprecations warn for at least one minor release.
* **Generated data:** for a given seed, schema and locale, patch releases (`1.0.x`) never
  change generated values. Minor releases (`1.x`) may — for example to fix a provider or add
  realism — and every such change is listed under **Changed data** in
  [CHANGELOG.md](CHANGELOG.md). Pin `nextfake~=1.0.0` if your snapshots must never move.

## Providers

| Category | Providers |
|---|---|
| Person | `first_name`, `last_name`, `name`, `username`, `email`, `phone_number` |
| Internet & tech | `ipv4`, `ipv6`, `mac_address`, `domain_name`, `url`, `user_agent`, `uuid4`, `uuid7`, `password`, `hex_color` |
| Location & business | `street_address`, `city`, `state`, `state_abbr`, `postcode`, `country`, `country_code`, `address`, `latitude`, `longitude`, `company`, `job_title` |
| Finance & commerce | `credit_card_number` (Luhn-valid Visa/MC/Amex/Discover), `currency_code`, `price(min, max)` |
| Primitives | `int(min, max, multiple_of)`, `float(min, max, decimals, multiple_of)`, `bool(probability)`, `choice(values, weights)`, `serial(start, step)`, `pattern("??-###")`, `string(min_length, max_length)`, `constant(value)` |
| Time & text | `date`, `date_of_birth`, `datetime(utc)`, `iso8601`, `iso_date`, `time`, `duration`, `unix_time`, `word`, `sentence`, `paragraph` |

Every provider has a typed single-value method and (for most) a batch method on `Faker`
(`gen.email()` / `gen.emails(n)`), plus `gen.value("int", min=1, max=6)` /
`gen.values(spec, n)` for anything else. The full list is in `nextfake.PROVIDERS`.

## Locales

| Locale | Name | Address | Postcode | Phone numbers |
|---|---|---|---|---|
| `en_US` | Frank Weaver | 2101 11th Lane Apt. 867, Sioux Falls, CA 92500 | `04840` | `1-269-419-9039`, `+1-613-633-5552` |
| `en_GB` | Ollie Grant | 58 Victoria Rise, Blackpool SW18 8BY | `EX1 7AR` | `01319 903945`, `020 8363 3555` |
| `de_DE` | Johannes Busch | Lange Straße 39, 45829 Dortmund | `86886` | `0176 09960706`, `+49 (0)3199 039451` |
| `fr_FR` | Jacques Le Roux | 91 rue du Lac, 09280 Lille | `88600` | `+33 1 69 21 99 03`, `09 45 13 63 35` |
| `ja_JP` | 村田 悠斗 | 〒841-1940 東京都宮崎市南町9丁目19番15号 | `692-1990` | `03-9451-3633`, `052-552-9947` |

Samples are real output of `Faker(locale, seed=2026)`.

E-mails and usernames are ASCII everywhere (accents are folded; Japanese names use romaji
tables). `Faker("en-gb")`, `Faker("de")` etc. are accepted.

## Typing

```python
users = gen.generate(User, count=100)          # list[User]
points = gen.generate(Point, count=3)          # list[Point]  (dataclass)
rows = gen.generate(RowTD, count=3)            # list[RowTD]  (TypedDict)
dicts = gen.generate({"id": "int"}, count=3)   # list[dict[str, Any]]
df = gen.to_polars(User, 10)                   # polars.DataFrame
```

`mypy --strict python/nextfake tests/test_typing.py` passes with zero errors; the compiled
extension ships complete `.pyi` stubs.

## Benchmarks

<!-- BENCHMARKS:START -->
Measured on Apple M2 Max (12 logical cores), Darwin 25.6.0 (arm64), Python 3.13.5, 2026-11-21 — nextfake 0.1.0, faker 40.63.0, mimesis 22.2.0, polyfactory 3.5.0, pydantic 2.14.4, polars 2.1.0, pyarrow 26.0.1. Full environment and methodology: [benches/RESULTS.md](benches/RESULTS.md).

| Benchmark | vs Faker | vs Mimesis | vs Polyfactory | nextfake time |
|---|---:|---:|---:|---:|
| 100,000 Python dicts | **414x** | **35x** | — | 41 ms |
| 100,000 Pydantic v2 models (validated) | — | — | **17x** | 1,787 ms |
| 1,000,000 rows -> Polars DataFrame | **3,674x**\* | **308x** | — | 44 ms |
| 1,000,000 rows -> Parquet on disk (zstd) | **2,380x**\* | **197x** | — | 70 ms |

Speedup = competitor wall time / nextfake wall time (fastest variant of each competitor). \* = competitor time extrapolated from a 100k-row run. In the detailed tables, rows for nextfake's own variants show their time relative to the default configuration instead.

### 100,000 Python dicts

| Library | Wall time (s) | Throughput (rows/s) | nextfake speedup | Peak RSS (MB) | RSS after imports (MB) |
|---|---:|---:|---:|---:|---:|
| **nextfake** `to_dicts` | 0.041 | 2.46 M | baseline | 115 | 32 |
| nextfake (1 thread) | 0.055 | 1.83 M | *1.3x slower* | 106 | 30 |
| Faker | 16.8 | 5.9 k | **413.9x** | 114 | 94 |
| Mimesis (`Schema.create`) | 1.440 | 69.5 k | **35.4x** | 120 | 68 |

### 100,000 Pydantic v2 models (validated)

| Library | Wall time (s) | Throughput (rows/s) | nextfake speedup | Peak RSS (MB) | RSS after imports (MB) |
|---|---:|---:|---:|---:|---:|
| **nextfake** `generate` | 1.787 | 56.0 k | baseline | 249 | 59 |
| nextfake (1 thread) | 1.830 | 54.6 k | *1.0x slower* | 272 | 62 |
| nextfake `validate=False` | 0.400 | 249.9 k | *4.5x faster* | 232 | 55 |
| Polyfactory (default) | 40.3 | 2.5 k | **22.5x** | 228 | 93 |
| Polyfactory + Faker fields | 29.5 | 3.4 k | **16.5x** | 210 | 91 |

### 1,000,000 rows -> Polars DataFrame

| Library | Wall time (s) | Throughput (rows/s) | nextfake speedup | Peak RSS (MB) | RSS after imports (MB) |
|---|---:|---:|---:|---:|---:|
| **nextfake** `to_polars` | 0.044 | 22.71 M | baseline | 264 | 79 |
| nextfake (1 thread) | 0.202 | 4.94 M | *4.6x slower* | 356 | 79 |
| Faker + `pl.DataFrame` | 161.8 *(extrap.)* | 6.2 k | **3,673.8x** | 163 | 94 |
| Mimesis + `pl.DataFrame` | 13.6 | 73.6 k | **308.4x** | 745 | 87 |

* Faker + `pl.DataFrame`: extrapolated linearly from 100,000 rows (16.18s); RSS measured at 100,000 rows

### 1,000,000 rows -> Parquet on disk (zstd)

| Library | Wall time (s) | Throughput (rows/s) | nextfake speedup | Peak RSS (MB) | RSS after imports (MB) |
|---|---:|---:|---:|---:|---:|
| **nextfake** `to_parquet` | 0.070 | 14.36 M | baseline | 165 | 31 |
| nextfake (1 thread) | 0.437 | 2.29 M | *6.3x slower* | 143 | 31 |
| Faker -> Polars -> Parquet | 165.7 *(extrap.)* | 6.0 k | **2,379.7x** | 214 | 117 |
| Mimesis -> Polars -> Parquet | 13.7 | 72.9 k | **197.0x** | 751 | 87 |

* Faker -> Polars -> Parquet: extrapolated linearly from 100,000 rows (16.57s); RSS measured at 100,000 rows
<!-- BENCHMARKS:END -->

Reproduce with:

```bash
maturin develop --release
pip install faker mimesis polyfactory email-validator
python benches/run_benchmarks.py     # rewrites benches/RESULTS.md and these tables
```

## Architecture

```text
 Python                                     Rust (_nextfake, PyO3 abi3, GIL released)
 ───────────────────────────────            ────────────────────────────────────────────
 Faker / generate / to_*      ──spec──▶     CompiledPlan  (validated column plan)
 schema.py  (Pydantic, dataclass,           │
            TypedDict, dict, heuristics)    ├─ rng.rs        ChaCha8Rng per (seed, chunk, column)
                                            ├─ providers.rs  formatting into column buffers
                                            ├─ locales/      static tables (5 locales)
                                            ├─ schema.rs     rayon fan-out over chunk×column
                                            │                → Arrow arrays (zero-copy)
 pyarrow / polars  ◀── __arrow_c_stream__ ──┤
 list[dict] / models ◀── direct builders ───┤
 files  ◀──────────────── writers.rs ───────┘ Parquet (parallel column encoding), CSV, JSONL
```

## Limitations & roadmap

* Columnar exports (`to_arrow`, `to_polars`, `to_parquet`, ...) require flat schemas; nested
  models are supported by `generate()` / `to_dicts()`. Struct / list columns are on the roadmap.
* `list[...]`, `dict[...]` and union-of-models fields are skipped when they have a default and
  otherwise need an override.
* Regex-constrained strings (`Field(pattern=...)`) need an explicit `Pattern` override.
* Enum / `Literal` fields that mix value types (e.g. `Literal[1, "x"]`) work in `generate()`
  and `to_dicts()`, but columnar exports need one type per column (override with `Choice`).
* `bytes` fields export as UTF-8 strings in columnar formats.
* No foreign keys / multi-table relationships or cross-field rules (e.g. `end > start`) yet;
  pick related values with `Choice(values=parent_ids)` and non-overlapping ranges meanwhile.
* Values are uniformly random within their tables — no cross-column correlation yet (e.g. a
  city does not determine its postcode).

### Optimization opportunities

Measured headroom identified while benchmarking v0.1.0:

* **Polars import (~50% of `to_polars` time).** `to_arrow` hands 1M rows to pyarrow in ~23 ms;
  `to_polars` takes ~45 ms because Polars converts `Utf8` columns to its string-view layout on
  import. Emitting Arrow `Utf8View` directly would make the Polars hand-off zero-copy as well.
* **Validated models.** For `generate(Model)`, Pydantic validation (and `email-validator` for
  `EmailStr`) is ~80% of the time and single-threaded. Because generated values are valid by
  construction, a "trusted" construction path, or chunked validation on free-threaded CPython
  3.14t, could close most of the gap to `validate=False` (4.5x faster).
* **Python object creation.** `to_dicts` spends most of its time creating `str` and `datetime`
  objects under the abi3 limited API (e.g. `datetime` construction is a Python-level call).
  Version-specific wheels could use the `datetime` C-API; free-threaded builds could build rows
  in parallel.
* **Parquet.** Row groups x columns are already encoded in parallel; page-level statistics and
  dictionary probing could be tuned per provider, and Utf8View/zero-copy page assembly would
  save another copy.
* **Cross-column realism** (city ↔ postcode ↔ phone area code) is a feature gap, not a speed
  issue, and would come at a small cost.

## Contributing, security & license

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). nextfake is dual-licensed
under [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your option.
