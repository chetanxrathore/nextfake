"""Columnar & direct-to-disk exporters (NXFK-401, NXFK-402)."""

from __future__ import annotations

import csv
import dataclasses
import datetime as dt
import ipaddress
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

import nextfake

pl = pytest.importorskip("polars")
pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")


class User(BaseModel):
    id: int
    full_name: str
    email: str
    city: str
    ip_address: str
    created_at: dt.datetime


@dataclasses.dataclass
class Wide:
    id: int
    score: float
    is_active: bool
    birthday: dt.date
    created_at: dt.datetime
    country_code: str
    price: float
    notes: str | None = None


def test_to_polars_100k_rows() -> None:
    df = nextfake.Faker(seed=1).to_polars(User, count=100_000)
    assert df.shape == (100_000, 6)
    assert df.columns == ["id", "full_name", "email", "city", "ip_address", "created_at"]
    assert df.schema == {
        "id": pl.Int64,
        "full_name": pl.String,
        "email": pl.String,
        "city": pl.String,
        "ip_address": pl.String,
        "created_at": pl.Datetime("us"),
    }
    assert df["id"].to_list() == list(range(1, 100_001))
    assert df["email"].str.contains("@").all()
    assert df.null_count().sum_horizontal().item() == 0
    for ip in df["ip_address"].sample(1000, seed=1).to_list():
        ipaddress.IPv4Address(ip)
    assert df["created_at"].min() >= dt.datetime(2020, 1, 1)
    assert df["full_name"].str.len_chars().min() > 3


def test_to_arrow_schema_and_nulls() -> None:
    table = nextfake.Faker(seed=2).to_arrow(Wide, 50_000, null_probability=0.25)
    assert table.num_rows == 50_000
    types = {f.name: str(f.type) for f in table.schema}
    assert types == {
        "id": "int64",
        "score": "double",
        "is_active": "bool",
        "birthday": "date32[day]",
        "created_at": "timestamp[us]",
        "country_code": "string",
        "price": "double",
        "notes": "string",
    }
    assert not table.schema.field("id").nullable
    assert table.schema.field("notes").nullable
    assert 10_000 < table.column("notes").null_count < 15_000


def test_to_pandas() -> None:
    df = nextfake.Faker(seed=3).to_pandas(Wide, 1000)
    assert len(df) == 1000
    assert str(df["id"].dtype) == "int64"
    assert str(df["created_at"].dtype).startswith("datetime64")


def test_same_seed_same_data_across_sinks(tmp_path: Path) -> None:
    arrow = nextfake.Faker(seed=7).to_arrow(Wide, 40_000)
    pq_path = nextfake.Faker(seed=7).to_parquet(Wide, 40_000, tmp_path / "w.parquet")
    assert pq.read_table(pq_path).equals(arrow)
    df = nextfake.Faker(seed=7).to_polars(Wide, 40_000)
    assert df.equals(pl.from_arrow(arrow))
    dicts = nextfake.Faker(seed=7).to_dicts(Wide, 40_000)
    assert dicts == arrow.to_pylist()


@pytest.mark.parametrize("compression", ["zstd", "snappy", "lz4", "gzip", "none"])
def test_parquet_roundtrip(tmp_path: Path, compression: str) -> None:
    path = nextfake.Faker(seed=4).to_parquet(
        User, 70_000, tmp_path / "u.parquet", compression=compression, row_group_size=32_768
    )
    df = pl.read_parquet(path)
    assert df.shape == (70_000, 6)
    assert df.schema["created_at"] == pl.Datetime("us")
    meta = pq.ParquetFile(path).metadata
    assert meta.num_rows == 70_000
    assert meta.num_row_groups == 3
    assert pq.read_table(path).schema.field("id").type == pa.int64()


def test_parquet_bad_compression(tmp_path: Path) -> None:
    with pytest.raises(nextfake.ProviderError, match="compression"):
        nextfake.Faker().to_parquet(User, 10, tmp_path / "x.parquet", compression="bogus")


def test_jsonl_roundtrip(tmp_path: Path) -> None:
    gen_a, gen_b = nextfake.Faker(seed=5), nextfake.Faker(seed=5)
    path = gen_a.to_jsonl(Wide, 30_000, tmp_path / "w.jsonl", null_probability=0.5)
    expected = gen_b.to_dicts(Wide, 30_000, null_probability=0.5)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 30_000
    for line, exp in zip(lines[:2000], expected[:2000], strict=True):
        row = json.loads(line)
        assert row["id"] == exp["id"]
        assert row["created_at"] == exp["created_at"].isoformat()
        assert row["birthday"] == exp["birthday"].isoformat()
        assert row["notes"] == exp["notes"]
        assert row["score"] == exp["score"]
    assert pl.read_ndjson(path).height == 30_000


def test_csv_roundtrip(tmp_path: Path) -> None:
    path = nextfake.Faker(seed=6).to_csv(User, 25_000, tmp_path / "u.csv")
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 25_000
    assert list(rows[0]) == ["id", "full_name", "email", "city", "ip_address", "created_at"]
    assert rows[-1]["id"] == "25000"
    dt.datetime.fromisoformat(rows[0]["created_at"])
    df = pl.read_csv(path, try_parse_dates=True)
    assert df.height == 25_000
    assert df.schema["created_at"] == pl.Datetime("us")


def test_csv_quoting_and_options(tmp_path: Path) -> None:
    schema = {"addr": "address", "txt": nextfake.Choice(['he said "hi"', "a,b", "line\nbreak"])}
    path = nextfake.Faker(seed=1).to_csv(schema, 3000, tmp_path / "q.tsv", delimiter="\t")
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    assert len(rows) == 3000
    assert {r["txt"] for r in rows} == {'he said "hi"', "a,b", "line\nbreak"}
    no_header = nextfake.Faker(seed=1).to_csv(schema, 10, tmp_path / "h.csv", header=False)
    assert len(list(csv.reader(no_header.open(newline="")))) == 10
    with pytest.raises(ValueError, match="delimiter"):
        nextfake.Faker().to_csv(schema, 1, tmp_path / "bad.csv", delimiter="ab")


@pytest.mark.parametrize("fmt", ["parquet", "csv", "jsonl"])
def test_files_are_thread_invariant(tmp_path: Path, fmt: str) -> None:
    out = []
    for threads in (1, 4):
        gen = nextfake.Faker(seed=11, threads=threads)
        path = tmp_path / f"t{threads}.{fmt}"
        if fmt == "parquet":
            gen.to_parquet(Wide, 100_000, path)
        elif fmt == "csv":
            gen.to_csv(Wide, 100_000, path)
        else:
            gen.to_jsonl(Wide, 100_000, path)
        out.append(path.read_bytes())
    assert out[0] == out[1]


def test_arrow_stream_interface() -> None:
    stream = nextfake.Faker(seed=1).to_arrow_stream({"id": "int", "e": "email"}, 40_000)
    assert stream.num_rows == 40_000
    assert stream.num_batches == 3
    assert stream.column_names == ["id", "e"]
    table = pa.table(stream)
    assert table.num_rows == 40_000
    assert stream.consumed
    with pytest.raises(RuntimeError, match="consumed"):
        pa.table(stream)


def test_arrow_ipc_bytes() -> None:
    data = nextfake.Faker(seed=1).to_arrow_ipc(User, 1234)
    table = pa.ipc.open_stream(data).read_all()
    assert table.num_rows == 1234


def test_nested_schema_rejected_for_columnar() -> None:
    class Inner(BaseModel):
        city: str

    class Outer(BaseModel):
        name: str
        inner: Inner

    with pytest.raises(nextfake.UnsupportedTypeError, match="nested"):
        nextfake.Faker().to_polars(Outer, 10)


def test_empty_export(tmp_path: Path) -> None:
    gen = nextfake.Faker(seed=1)
    assert gen.to_polars(User, 0).shape == (0, 6)
    assert pq.read_table(gen.to_parquet(User, 0, tmp_path / "e.parquet")).num_rows == 0
    assert gen.to_csv(User, 0, tmp_path / "e.csv").read_text().count("\n") == 1


def test_module_level_exporters(tmp_path: Path) -> None:
    nextfake.seed(3)
    df = nextfake.to_polars({"id": "int", "name": "name"}, 10)
    assert df.height == 10
    assert nextfake.to_parquet({"id": "int"}, 10, tmp_path / "m.parquet").exists()


_PEAK_RSS_SNIPPET = """
import sys
if sys.platform.startswith("linux"):
    # ru_maxrss inherits the parent's (pytest's) high-water mark across fork/exec on Linux;
    # VmHWM only covers this process image.
    with open("/proc/self/status", encoding="ascii") as fh:
        hwm = next(int(line.split()[1]) for line in fh if line.startswith("VmHWM:"))
    print(hwm / 1024)
else:
    import resource
    print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024))
"""


def _peak_rss_mb(code: str) -> float:
    script = textwrap.dedent(code) + _PEAK_RSS_SNIPPET
    res = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    return float(res.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(sys.platform == "win32", reason="resource module unavailable")
@pytest.mark.parametrize("fmt", ["parquet", "csv", "jsonl"])
def test_streaming_writers_use_bounded_memory(tmp_path: Path, fmt: str) -> None:
    """Peak RSS must not grow with the row count (5M rows ~= 1M rows)."""
    schema: dict[str, Any] = {
        "id": "int", "full_name": "name", "email": "email", "city": "city",
        "ip_address": "ipv4", "created_at": "datetime",
    }  # fmt: skip
    peaks = {}
    for n in (1_000_000, 5_000_000):
        path = tmp_path / f"big_{n}.{fmt}"
        peaks[n] = _peak_rss_mb(
            f"""
            import nextfake
            nextfake.Faker(seed=1).to_{fmt}({schema!r}, {n}, {str(path)!r})
            """
        )
        size_mb = path.stat().st_size / 1e6
    # 5M rows is ~400 MB as in-memory Arrow and >=150 MB on disk in every format here.
    assert size_mb > 140
    assert peaks[5_000_000] - peaks[1_000_000] < 64, peaks
    assert peaks[5_000_000] < 400, peaks


TEMPORAL = {
    "at": nextfake.Time("09:00", "17:30"),
    "took": nextfake.Duration(dt.timedelta(minutes=1), dt.timedelta(days=2)),
    "seen": nextfake.DateTime("2024-01-01", "2024-12-31", utc=True),
}


def test_time_duration_and_utc_columns(gen: nextfake.Faker, tmp_path: Path) -> None:
    table = gen.to_arrow(TEMPORAL, 1_000)
    assert [str(t) for t in table.schema.types] == [
        "time64[us]",
        "duration[us]",
        "timestamp[us, tz=UTC]",
    ]
    df = gen.to_polars(TEMPORAL, 1_000)
    assert df["at"].min() >= dt.time(9)
    assert df["at"].max() <= dt.time(17, 30)
    assert df["took"].min() >= dt.timedelta(minutes=1)
    rows = gen.to_dicts(TEMPORAL, 100)
    assert all(r["seen"].tzinfo is dt.timezone.utc for r in rows)

    pq_path = gen.to_parquet(TEMPORAL, 5_000, tmp_path / "t.parquet")
    assert pq.read_table(pq_path).schema.types == table.schema.types

    seeded = nextfake.Faker(seed=3)
    line = json.loads(seeded.to_jsonl(TEMPORAL, 1, tmp_path / "t.jsonl").read_text())
    assert dt.time.fromisoformat(line["at"])
    assert line["took"].startswith("P")
    assert line["seen"].endswith("Z")
    csv_rows = list(csv.DictReader(seeded.to_csv(TEMPORAL, 3, tmp_path / "t.csv").open()))
    assert all(r["seen"].endswith("Z") and r["took"].startswith("P") for r in csv_rows)
