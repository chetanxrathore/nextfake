# Changelog

All notable changes to nextfake are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Changes to generated data for an existing seed are
always listed under **Changed data** (see the stability policy in the README).

## [1.0.0] - 2026-11-23

First stable release. From 1.0 on, the public API follows semantic versioning and generated data
only changes in minor releases, with a **Changed data** entry here.

### Added

- `Time` and `Duration` specs (`time` / `duration` providers): native `datetime.time` /
  `timedelta` values and `time64[us]` / `duration[us]` Arrow and Parquet columns; ISO-8601 in
  CSV and JSONL.
- `DateTime(utc=True)`: timezone-aware UTC datetimes and `timestamp[us, tz=UTC]` columns.
- `Int(multiple_of=...)`, `Float(multiple_of=...)` and `Spec.length(min_length, max_length)`
  (`Spec.min_length`).
- `Faker(reference_date=...)` / `compile_schema(reference_date=...)` to pin Pydantic
  `PastDate`, `FutureDate`, `PastDatetime` and `FutureDatetime` fields.
- Pydantic support for `multiple_of`, `max_digits`, strict mode (model or field),
  `AliasChoices`, `AliasPath`, `validate_by_alias=False`, `AwareDatetime`, `NaiveDatetime`,
  `PastDatetime`, `FutureDatetime`, and `Literal[...]` with `None` or mixed value types.
- Golden-output test run in CI on Linux, macOS and Windows (x86_64 and arm64), enforcing
  byte-identical output across platforms.
- Stability policy (README) and this changelog.

### Fixed

- String fields with `min_length > 3` (e.g. `email: str = Field(min_length=5)`) produced
  random alphanumerics instead of e-mails, names, cities, ...
- Fields with a small `min_length` the provider cannot reach (e.g. a 2-letter country code with
  `min_length=3`) failed validation.
- `Decimal` / float fields with `decimal_places` (or `decimals`) and a `gt` bound could produce
  a value like `5e-324` and fail validation.
- `Literal["a", None]` and mixed-type literals crashed schema compilation with a `TypeError`.
- `datetime.time`, `timedelta` and mixed-value `Enum` fields were exported as raw integers by
  `to_arrow`, `to_polars`, `to_parquet`, `to_csv` and `to_jsonl`. Times and durations now use
  native column types; mixed-type enums raise a clear error in columnar exports.
- Strict-mode Pydantic models (`ConfigDict(strict=True)`) always failed validation.
- `AwareDatetime` fields were rejected as unsupported.
- `multiple_of` constraints were ignored, so such fields failed validation.
- Fields with an `AliasChoices` or `AliasPath` validation alias failed validation.
- Pydantic `PastDate` fields changed from day to day for a fixed seed.

### Changed data

Generated values differ from 0.1.0 for the same seed in these cases:

- Floats with `decimals` (and `Decimal` fields with `decimal_places`) are drawn on an exact
  decimal grid; floats without `decimals` use a slightly different interpolation (last-bit
  differences).
- String fields with `max_length` / `min_length` redraw out-of-range values instead of cutting
  them, so whole values are kept.
- `datetime.time` and `timedelta` fields use the new `time` / `duration` providers.
- `PastDate` uses the fixed default range (2000-01-01 to 2025-12-31) unless `reference_date`
  is set.
- Mixed-type `Enum` / `Literal` fields are drawn by index.

## [0.1.0] - 2026-11-21

Initial release: Rust core with deterministic multi-core generation, Faker-style API, Pydantic /
dataclass / TypedDict / dict schemas, Arrow / Polars / pandas / Parquet / CSV / JSONL exports,
five compiled locales, and signed wheels with PEP 740 attestations.

[1.0.0]: https://github.com/chetanxrathore/nextfake/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/chetanxrathore/nextfake/releases/tag/v0.1.0
