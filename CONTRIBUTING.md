# Contributing to nextfake

Thanks for helping! nextfake is a Rust core (`src/`, PyO3 + rayon + Arrow) with a thin, typed
Python layer (`python/nextfake/`).

## Development setup

```bash
# Rust stable (1.85+) and Python 3.10+ required
uv venv && source .venv/bin/activate          # or: python -m venv .venv
uv pip install --group dev --group bench       # or: pip install maturin pytest ruff mypy ...
maturin develop --release                      # build & install the extension in-place
```

Use `maturin develop` (debug) for fast iteration and `--release` for benchmarks.

## Quality gates (all must pass — CI enforces them)

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo clippy --all-targets --features python -- -D warnings
cargo test
ruff check python tests benches
mypy --strict python/nextfake tests/test_typing.py
pytest -v
```

`cargo test` exercises the pure-Rust core; the PyO3 bindings live behind the `python` cargo
feature (enabled automatically by maturin), so Rust tests never need to link libpython.

## Project layout

| Path | What lives there |
|---|---|
| `src/rng.rs` | Deterministic `ChaCha8Rng` keyed by (seed, chunk), per-column streams |
| `src/providers.rs` | All value providers, Luhn, UUIDv7, ISO formatting |
| `src/locales/` | Compiled locale tables (`en_US`, `en_GB`, `de_DE`, `fr_FR`, `ja_JP`) |
| `src/schema.rs` | Column plans, parallel generation, Arrow conversion, thread pools |
| `src/writers.rs` | Arrow IPC, Parquet (parallel column encoding), CSV, JSONL |
| `src/lib.rs` | PyO3 module (`Engine`, `CompiledPlan`, `ArrowStream`) |
| `python/nextfake/` | `Faker` API, schema introspection & heuristics, specs, exceptions |
| `benches/run_benchmarks.py` | Head-to-head benchmarks → `benches/RESULTS.md` |

## Ground rules

* **Determinism is a contract.** For a given seed, output must be identical for any thread
  count, and existing columns must not change when unrelated columns are added. Changes to
  `CHUNK_ROWS`, RNG keying or a provider's sampling logic change generated data. Such changes
  belong in a minor release only: `tests/test_golden.py` fails until you regenerate its digests
  (`NEXTFAKE_UPDATE_GOLDEN=1 pytest tests/test_golden.py -s`) and add a **Changed data** entry
  to `CHANGELOG.md`.
* **No per-row Python objects on bulk paths.** Arrow / Parquet / CSV / JSONL paths must stay in
  Rust with the GIL released (`py.detach`).
* **Keep the Python layer typed.** Public APIs need annotations that pass `mypy --strict`, and
  stubs in `python/nextfake/_nextfake.pyi` must match the Rust bindings.
* Add tests for new providers in both Rust (`#[cfg(test)]`) and Python (`tests/`).

## Adding a locale

1. Create `src/locales/xx_yy.rs` with a `pub static XX_YY: Locale` (copy an existing locale).
2. Register it in `LOCALES` in `src/locales/mod.rs` (and an alias in `get()` if useful).
3. Provide romanised name tables (`first_names_romanized`) for non-Latin scripts so e-mails and
   usernames stay ASCII.
4. Extend `tests/test_locales.py` with format checks for postcodes and phone numbers.

## Adding a provider

1. Add a variant to `Provider` in `src/providers.rs`, parse it in `Provider::parse`, give it a
   `Kind`, and implement generation.
2. Add the name to `PROVIDER_NAMES`, optional aliases to `canonical()`, and field-name
   heuristics in `python/nextfake/schema.py` if appropriate.
3. Add typed `Faker` methods (single + batch) in `python/nextfake/faker.py`.

## Releasing

Releases are published by `.github/workflows/wheels.yml` when a `v*` tag is pushed: it builds
manylinux/musllinux (x86_64, aarch64), macOS (x86_64, arm64), Windows x64 wheels and the sdist,
then uploads them to PyPI via Trusted Publishing with PEP 740 attestations and GitHub build
provenance (see [SECURITY.md](SECURITY.md#verifying-releases)).

1. Bump `version` in `Cargo.toml` — the single source of truth (the Python package version is
   read from it by maturin). Run `cargo check` so `Cargo.lock` updates, move the
   `Unreleased` notes in `CHANGELOG.md` under the new version, and run the quality gates.
2. Commit, then tag the commit: `git tag -a vX.Y.Z -m "nextfake X.Y.Z"` and push the tag.
3. Approve the `pypi` environment deployment in the Actions run if reviewers are required.

The publish job fails fast if the tag does not match the built version. Re-running a partially
failed publish is safe (`skip-existing`).

## Commit messages

Reference the tracking key (e.g. `NXFK-402: ...`) and describe user-visible behaviour changes.
