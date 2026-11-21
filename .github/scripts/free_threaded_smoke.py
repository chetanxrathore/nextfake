"""Smoke test for free-threaded CPython (3.14t): the extension must not re-enable the GIL and
must generate correct, deterministic data when called from many Python threads at once."""

import sys
import threading

import nextfake

assert not sys._is_gil_enabled(), "importing nextfake re-enabled the GIL"

SCHEMA = {"id": "int", "name": "name", "email": "email", "created_at": "datetime"}
expected = nextfake.Faker(seed=7).to_dicts(SCHEMA, 20_000)
shared = nextfake.Faker(seed=1)
results: list[object] = []
errors: list[BaseException] = []


def work() -> None:
    try:
        # independent generators: must reproduce the seeded reference exactly
        assert nextfake.Faker(seed=7).to_dicts(SCHEMA, 20_000) == expected
        # one shared generator used concurrently: must stay consistent and not crash
        rows = shared.to_dicts(SCHEMA, 5_000)
        assert len(rows) == 5_000
        assert all("@" in r["email"] for r in rows)
        results.append(len(shared.names(1_000)))
    except BaseException as exc:  # re-raised in the main thread
        errors.append(exc)


threads = [threading.Thread(target=work) for _ in range(16)]
for t in threads:
    t.start()
for t in threads:
    t.join()
if errors:
    raise errors[0]
assert results == [1_000] * 16
assert not sys._is_gil_enabled()
print(f"free-threaded OK: GIL disabled, 16 concurrent threads, sample {expected[0]['name']!r}")
