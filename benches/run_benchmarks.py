#!/usr/bin/env python
"""Head-to-head benchmarks: nextfake vs Faker, Mimesis and Polyfactory (NXFK-501).

Usage::

    maturin develop --release
    python benches/run_benchmarks.py            # full suite -> benches/RESULTS.md + results.json
    python benches/run_benchmarks.py --quick    # 10x smaller sizes (smoke test, no files written)
    python benches/run_benchmarks.py --only dicts,polars

Methodology
-----------
* Every (benchmark, library) measurement runs in its **own Python subprocess**, so peak RSS
  (``ru_maxrss``) is isolated and includes only that library's imports and work.
* Generator construction / factory class definition happens before the timer starts; a small
  warm-up call is made (also untimed). The timed region is the full user-visible operation,
  e.g. "build 1M rows *and* turn them into a Polars DataFrame".
* nextfake runs 5 times (median reported). Competitors run once, and up to 3 times when a run
  takes under 2 s (median reported).
* 1M-row competitor runs: we first measure at 100k rows. If the linear 1M estimate exceeds
  60 s we report the *extrapolated* 1M time (clearly marked) with the RSS measured at 100k;
  otherwise the full 1M rows are generated and measured.
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import importlib.metadata
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXTRAPOLATE_LIMIT_S = 60.0
PROBE_ROWS = 100_000

SCHEMA = {
    "id": "int",
    "full_name": "name",
    "email": "email",
    "city": "city",
    "ip_address": "ipv4",
    "created_at": "datetime",
}

# ---------------------------------------------------------------------------------------------
# Worker side (runs inside an isolated subprocess)
# ---------------------------------------------------------------------------------------------


def _maxrss_mb() -> float:
    import resource

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024


def _pydantic_user() -> Any:
    from datetime import datetime
    from ipaddress import IPv4Address

    from pydantic import BaseModel, EmailStr

    class User(BaseModel):
        id: int
        full_name: str
        email: EmailStr
        city: str
        ip_address: IPv4Address
        created_at: datetime

    return User


def _faker_rows() -> Callable[[int], list[dict[str, Any]]]:
    from faker import Faker

    Faker.seed(1)
    fake = Faker("en_US")

    def rows(n: int) -> list[dict[str, Any]]:
        return [
            {
                "id": i,
                "full_name": fake.name(),
                "email": fake.email(),
                "city": fake.city(),
                "ip_address": fake.ipv4(),
                "created_at": fake.date_time(),
            }
            for i in range(1, n + 1)
        ]

    return rows


def _mimesis_rows() -> Callable[[int], list[dict[str, Any]]]:
    from mimesis import Field, Locale
    from mimesis.schema import Schema

    f = Field(Locale.EN, seed=1)

    def make() -> dict[str, Any]:
        return {
            "id": f("increment"),
            "full_name": f("full_name"),
            "email": f("email"),
            "city": f("city"),
            "ip_address": f("ip_v4"),
            "created_at": f("datetime"),
        }

    def rows(n: int) -> list[dict[str, Any]]:
        return Schema(schema=make, iterations=n).create()

    return rows


def build_case(bench: str, impl: str, n: int, workdir: Path) -> Callable[[], Any]:
    """Return the timed callable for (bench, impl) at ``n`` rows. Setup is untimed."""
    parquet_path = workdir / f"{bench}-{impl}.parquet"

    if impl.startswith("nextfake"):
        import nextfake

        threads = 1 if impl.endswith("_1t") else None
        gen = nextfake.Faker(seed=1, threads=threads)
        if bench == "dicts":
            return lambda: gen.to_dicts(SCHEMA, n)
        if bench == "pydantic":
            user = _pydantic_user()
            validate = not impl.startswith("nextfake_construct")
            gen.generate(user, 10, validate=validate)  # warm schema + TypeAdapter caches
            return lambda: gen.generate(user, n, validate=validate)
        if bench == "polars":
            import polars as pl  # import outside the timer

            del pl

            return lambda: gen.to_polars(SCHEMA, n)
        if bench == "parquet":
            return lambda: gen.to_parquet(SCHEMA, n, parquet_path, compression="zstd")

    if impl in {"faker", "mimesis"}:
        rows = _faker_rows() if impl == "faker" else _mimesis_rows()
        rows(10)  # warm-up
        if bench == "dicts":
            return lambda: rows(n)
        import polars as pl

        if bench == "polars":
            return lambda: pl.DataFrame(rows(n))
        if bench == "parquet":
            return lambda: pl.DataFrame(rows(n)).write_parquet(parquet_path, compression="zstd")

    if impl.startswith("polyfactory") and bench == "pydantic":
        from polyfactory import Use
        from polyfactory.factories.pydantic_factory import ModelFactory

        user = _pydantic_user()
        ModelFactory.seed_random(1)
        if impl == "polyfactory":

            class UserFactory(ModelFactory[user]):  # type: ignore[valid-type]
                __model__ = user

            factory: Any = UserFactory
        else:
            fake = ModelFactory.__faker__

            class SemanticUserFactory(ModelFactory[user]):  # type: ignore[valid-type]
                __model__ = user
                full_name = Use(fake.name)
                email = Use(fake.email)
                city = Use(fake.city)
                ip_address = Use(fake.ipv4)

            factory = SemanticUserFactory
        factory.batch(10)  # warm-up
        return lambda: factory.batch(n)

    raise SystemExit(f"unknown case {bench}/{impl}")


def _row_count(bench: str, result: Any, workdir: Path, impl: str) -> int:
    if bench == "parquet":
        import pyarrow.parquet as pq

        return int(pq.ParquetFile(workdir / f"{bench}-{impl}.parquet").metadata.num_rows)
    if bench == "polars":
        return int(result.height)
    return len(result)


def worker(bench: str, impl: str, n: int, repeat: int, workdir: Path) -> dict[str, Any]:
    run = build_case(bench, impl, n, workdir)
    gc.collect()
    baseline = _maxrss_mb()
    times: list[float] = []
    rows = 0
    for i in range(repeat):
        gc.collect()
        t0 = time.perf_counter()
        result = run()
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
        if i == 0:
            peak_after_first = _maxrss_mb()
            rows = _row_count(bench, result, workdir, impl)
        del result
        # Adaptive repeats for slow competitors: stop after one run if it took >= 2s.
        if not impl.startswith("nextfake") and elapsed >= 2.0:
            break
    return {
        "times": times,
        "rows": rows,
        "baseline_rss_mb": baseline,
        "peak_rss_mb": max(_maxrss_mb(), peak_after_first),
    }


# ---------------------------------------------------------------------------------------------
# Orchestrator side
# ---------------------------------------------------------------------------------------------


@dataclass
class Bench:
    key: str
    title: str
    rows: int
    impls: list[tuple[str, str]]


BENCHES = [
    Bench(
        "dicts",
        "100,000 Python dicts",
        100_000,
        [
            ("nextfake", "**nextfake** `to_dicts`"),
            ("nextfake_1t", "nextfake (1 thread)"),
            ("faker", "Faker"),
            ("mimesis", "Mimesis (`Schema.create`)"),
        ],
    ),
    Bench(
        "pydantic",
        "100,000 Pydantic v2 models (validated)",
        100_000,
        [
            ("nextfake", "**nextfake** `generate`"),
            ("nextfake_1t", "nextfake (1 thread)"),
            ("nextfake_construct", "nextfake `validate=False`"),
            ("polyfactory", "Polyfactory (default)"),
            ("polyfactory_faker", "Polyfactory + Faker fields"),
        ],
    ),
    Bench(
        "polars",
        "1,000,000 rows -> Polars DataFrame",
        1_000_000,
        [
            ("nextfake", "**nextfake** `to_polars`"),
            ("nextfake_1t", "nextfake (1 thread)"),
            ("faker", "Faker + `pl.DataFrame`"),
            ("mimesis", "Mimesis + `pl.DataFrame`"),
        ],
    ),
    Bench(
        "parquet",
        "1,000,000 rows -> Parquet on disk (zstd)",
        1_000_000,
        [
            ("nextfake", "**nextfake** `to_parquet`"),
            ("nextfake_1t", "nextfake (1 thread)"),
            ("faker", "Faker -> Polars -> Parquet"),
            ("mimesis", "Mimesis -> Polars -> Parquet"),
        ],
    ),
]


@dataclass
class Result:
    bench: str
    impl: str
    label: str
    rows: int
    seconds: float
    measured_rows: int
    runs: list[float]
    peak_rss_mb: float
    baseline_rss_mb: float
    extrapolated: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def throughput(self) -> float:
        return self.rows / self.seconds if self.seconds else float("inf")


def spawn(bench: str, impl: str, n: int, repeat: int, workdir: Path) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        f"{bench}:{impl}:{n}:{repeat}",
        "--workdir",
        str(workdir),
    ]
    env = {**os.environ, "PYTHONHASHSEED": "0"}
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{bench}/{impl} failed:\n{proc.stdout}\n{proc.stderr}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def measure(bench: Bench, impl: str, label: str, scale: float, workdir: Path) -> Result:
    n = int(bench.rows * scale)
    is_ours = impl.startswith("nextfake")
    if is_ours:
        out = spawn(bench.key, impl, n, 5, workdir)
        return _result(bench, impl, label, n, out)
    probe_n = int(PROBE_ROWS * scale)
    if n <= probe_n:
        return _result(bench, impl, label, n, spawn(bench.key, impl, n, 3, workdir))
    probe = spawn(bench.key, impl, probe_n, 3, workdir)
    estimate = statistics.median(probe["times"]) * n / probe_n
    if estimate <= EXTRAPOLATE_LIMIT_S * scale:
        print(f"      full run ({n:,} rows, est. {estimate:.1f}s)", flush=True)
        return _result(bench, impl, label, n, spawn(bench.key, impl, n, 1, workdir))
    res = _result(bench, impl, label, probe_n, probe)
    res.rows = n
    res.seconds = estimate
    res.extrapolated = True
    res.measured_rows = probe_n
    res.notes.append(
        f"extrapolated linearly from {probe_n:,} rows "
        f"({statistics.median(probe['times']):.2f}s); RSS measured at {probe_n:,} rows"
    )
    return res


def _result(bench: Bench, impl: str, label: str, n: int, out: dict[str, Any]) -> Result:
    if out["rows"] != n:
        raise RuntimeError(f"{bench.key}/{impl}: expected {n} rows, got {out['rows']}")
    return Result(
        bench=bench.key,
        impl=impl,
        label=label,
        rows=n,
        seconds=statistics.median(out["times"]),
        measured_rows=n,
        runs=out["times"],
        peak_rss_mb=out["peak_rss_mb"],
        baseline_rss_mb=out["baseline_rss_mb"],
    )


def _version(dist: str) -> str:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def environment() -> dict[str, Any]:
    cpu = platform.processor() or platform.machine()
    if sys.platform == "darwin":
        with contextlib.suppress(OSError, subprocess.CalledProcessError):
            cpu = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
    elif Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    import nextfake

    return {
        "cpu": cpu,
        "logical_cores": os.cpu_count(),
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": platform.python_version(),
        "versions": {
            d: _version(d)
            for d in (
                "nextfake",
                "faker",
                "mimesis",
                "polyfactory",
                "pydantic",
                "polars",
                "pyarrow",
            )
        },
        "nextfake_debug_build": bool(getattr(nextfake._nextfake, "DEBUG_BUILD", False)),
        "date": time.strftime("%Y-%m-%d"),
    }


def _fmt_time(r: Result) -> str:
    s = f"{r.seconds:.3f}" if r.seconds < 10 else f"{r.seconds:.1f}"
    return f"{s} *(extrap.)*" if r.extrapolated else s


def _fmt_rate(r: Result) -> str:
    rate = r.throughput
    if rate >= 1e6:
        return f"{rate / 1e6:.2f} M"
    if rate >= 1e3:
        return f"{rate / 1e3:.1f} k"
    return f"{rate:.0f}"


def markdown(results: list[Result], env: dict[str, Any], scale: float) -> str:
    lines = [
        "# nextfake benchmark results",
        "",
        "Generated by `python benches/run_benchmarks.py` — **real, measured numbers** "
        "(see methodology below). Schema for every benchmark: the 6-column `User` "
        "(`id`, `full_name`, `email`, `city`, `ip_address`, `created_at`).",
        "",
        "## Environment",
        "",
        f"* **CPU:** {env['cpu']} ({env['logical_cores']} logical cores)",
        f"* **OS:** {env['os']}",
        f"* **Python:** {env['python']}",
        "* **Libraries:** " + ", ".join(f"{k} {v}" for k, v in env["versions"].items()),
        f"* **nextfake build:** {'DEBUG (numbers not representative!)' if env['nextfake_debug_build'] else 'release (`maturin develop --release`, LTO)'}",  # noqa: E501
        f"* **Date:** {env['date']}",
        "",
        "## Summary — nextfake speedup",
        "",
        "| Benchmark | vs Faker | vs Mimesis | vs Polyfactory | nextfake time |",
        "|---|---:|---:|---:|---:|",
    ]
    by_bench: dict[str, list[Result]] = {}
    for r in results:
        by_bench.setdefault(r.bench, []).append(r)
    titles = {b.key: b.title for b in BENCHES}
    for key, rs in by_bench.items():
        ours = next(r for r in rs if r.impl == "nextfake")

        def sp(prefix: str, rs: list[Result] = rs, ours: Result = ours) -> str:
            cands = [r for r in rs if r.impl.startswith(prefix)]
            if not cands:
                return "—"
            best = min(cands, key=lambda r: r.seconds)
            mark = "\\*" if best.extrapolated else ""
            return f"**{best.seconds / ours.seconds:,.0f}x**{mark}"

        lines.append(
            f"| {titles[key]} | {sp('faker')} | {sp('mimesis')} | {sp('polyfactory')} "
            f"| {ours.seconds * 1000:,.0f} ms |"
        )
    lines += [
        "",
        "Speedup = competitor wall time / nextfake wall time (fastest variant of each "
        "competitor). \\* = competitor time extrapolated from a 100k-row run. In the detailed "
        "tables, rows for nextfake's own variants show their time relative to the default "
        "configuration instead.",
        "",
    ]
    for key, rs in by_bench.items():
        ours = next(r for r in rs if r.impl == "nextfake")
        lines += [
            f"## {titles[key]}",
            "",
            "| Library | Wall time (s) | Throughput (rows/s) | nextfake speedup "
            "| Peak RSS (MB) | RSS after imports (MB) |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for r in rs:
            ratio = r.seconds / ours.seconds
            if r.impl == "nextfake":
                speed = "baseline"
            elif r.impl.startswith("nextfake"):  # our own variants: relative time, not speedup
                speed = f"*{ratio:.1f}x slower*" if ratio >= 1 else f"*{1 / ratio:.1f}x faster*"
            else:
                speed = f"**{ratio:,.1f}x**"
            lines.append(
                f"| {r.label} | {_fmt_time(r)} | {_fmt_rate(r)} | {speed} "
                f"| {r.peak_rss_mb:,.0f} | {r.baseline_rss_mb:,.0f} |"
            )
        notes = [f"* {r.label}: {n}" for r in rs for n in r.notes]
        if notes:
            lines += ["", *notes]
        lines.append("")
    lines += [
        "## Methodology",
        "",
        "* Each (benchmark, library) pair runs in an isolated subprocess; *Peak RSS* is that "
        "process's `ru_maxrss` (imports + data), *RSS after imports* is the high-water mark "
        "right before the first timed run.",
        "* Generator / factory setup and a tiny warm-up call are excluded from timing. Timed "
        "regions cover the whole user-visible operation (e.g. rows **and** DataFrame "
        "construction **and** Parquet write).",
        "* nextfake: median of 5 runs. Competitors: median of up to 3 runs (1 run when a run "
        "takes ≥ 2 s).",
        f"* 1M-row competitor runs are probed at 100k rows; when the linear 1M estimate exceeds "
        f"{EXTRAPOLATE_LIMIT_S:.0f} s the extrapolated value is reported and marked "
        "*(extrap.)*, otherwise the full 1M rows are generated.",
        "* `nextfake (1 thread)` uses `Faker(threads=1)` to separate algorithmic gains from "
        "multi-core parallelism. Output is identical for any thread count.",
        "* Polyfactory (default) fills `full_name`/`city` with random strings; "
        "*Polyfactory + Faker fields* wires the same semantic Faker providers nextfake "
        "infers automatically, for an apples-to-apples comparison.",
        "* Pydantic benchmarks validate every model (`EmailStr` validation via "
        "`email-validator` dominates nextfake's time there); `validate=False` uses "
        "`model_construct`.",
    ]
    if scale != 1.0:
        lines.insert(2, f"> **Quick mode** — all sizes scaled by {scale}.\n")
    return "\n".join(lines) + "\n"


README = HERE.parent / "README.md"


def _section(md: str, start: str, stop: str | None) -> str:
    body = md.split(start, 1)[1]
    if stop is not None:
        body = body.split(stop, 1)[0]
    return body.strip()


def _replace_block(text: str, name: str, content: str) -> str:
    begin, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    if begin not in text or end not in text:
        return text
    head, rest = text.split(begin, 1)
    _, tail = rest.split(end, 1)
    return f"{head}{begin}\n{content}\n{end}{tail}"


def sync_readme(md: str, env: dict[str, Any]) -> bool:
    """Copy the measured tables from RESULTS.md into README.md (between marker comments)."""
    if not README.exists():
        return False
    summary = _section(md, "## Summary — nextfake speedup", "## 100,000 Python dicts")
    details = _section(md, "## 100,000 Python dicts", "## Methodology")
    env_line = (
        f"Measured on {env['cpu']} ({env['logical_cores']} logical cores), {env['os']}, "
        f"Python {env['python']}, {env['date']} — "
        + ", ".join(f"{k} {v}" for k, v in env["versions"].items())
        + ". Full environment and methodology: [benches/RESULTS.md](benches/RESULTS.md)."
    )
    text = README.read_text(encoding="utf-8")
    new = _replace_block(text, "HEADLINE", summary.split("\n\nSpeedup =", 1)[0])
    new = _replace_block(
        new,
        "BENCHMARKS",
        f"{env_line}\n\n{summary}\n\n### 100,000 Python dicts\n\n"
        + details.replace("\n## ", "\n### "),
    )
    if new != text:
        README.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--worker", help=argparse.SUPPRESS)
    ap.add_argument("--workdir", help=argparse.SUPPRESS)
    ap.add_argument("--quick", action="store_true", help="10x smaller sizes; no files written")
    ap.add_argument("--only", help="comma-separated benchmark keys: dicts,pydantic,polars,parquet")
    ap.add_argument("--output", default=str(HERE / "RESULTS.md"))
    ap.add_argument(
        "--render", action="store_true", help="re-render RESULTS.md from results.json only"
    )
    args = ap.parse_args()

    if args.worker:
        bench, impl, n, repeat = args.worker.split(":")
        out = worker(bench, impl, int(n), int(repeat), Path(args.workdir))
        print(json.dumps(out))
        return

    if args.render:
        raw = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
        rendered = [Result(**r) for r in raw["results"]]
        md = markdown(rendered, raw["environment"], 1.0)
        Path(args.output).write_text(md, encoding="utf-8")
        if sync_readme(md, raw["environment"]):
            print(f"synced {README}")
        print(f"re-rendered {args.output}")
        return

    env = environment()
    if env["nextfake_debug_build"]:
        print("WARNING: nextfake is a debug build; run `maturin develop --release` first.")
    scale = 0.1 if args.quick else 1.0
    only = set(args.only.split(",")) if args.only else None
    results: list[Result] = []
    workdir = Path(tempfile.mkdtemp(prefix="nextfake-bench-"))
    try:
        for bench in BENCHES:
            if only and bench.key not in only:
                continue
            print(f"\n== {bench.title} ==", flush=True)
            for impl, label in bench.impls:
                print(f"   {label} ...", flush=True)
                r = measure(bench, impl, label, scale, workdir)
                results.append(r)
                tag = " (extrapolated)" if r.extrapolated else ""
                print(
                    f"      {r.seconds:9.3f}s{tag}  {r.throughput:14,.0f} rows/s  "
                    f"peak RSS {r.peak_rss_mb:7.1f} MB",
                    flush=True,
                )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    md = markdown(results, env, scale)
    print("\n" + md)
    if not args.quick:
        Path(args.output).write_text(md, encoding="utf-8")
        raw = {"environment": env, "results": [asdict(r) for r in results]}
        (HERE / "results.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
        print(f"wrote {args.output} and {HERE / 'results.json'}")
        if not args.only and sync_readme(md, env):
            print(f"synced benchmark tables into {README}")


if __name__ == "__main__":
    main()
