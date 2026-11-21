"""Static typing contract (checked by ``mypy --strict``) plus runtime checks (NXFK-301)."""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any, TypedDict

from pydantic import BaseModel
from typing_extensions import assert_type

import nextfake


class User(BaseModel):
    id: int
    full_name: str
    email: str


@dataclasses.dataclass
class Point:
    x: float
    y: float


class Row(TypedDict):
    id: int
    city: str


def test_generate_is_statically_typed() -> None:
    gen = nextfake.Faker(seed=1)
    users = gen.generate(User, count=100)
    assert_type(users, list[User])
    points = gen.generate(Point, count=3)
    assert_type(points, list[Point])
    rows = gen.generate(Row, count=3)
    assert_type(rows, list[Row])
    dicts = gen.generate({"id": "int", "email": "email"}, count=3)
    assert_type(dicts, list[dict[str, Any]])
    one = gen.one(User)
    assert_type(one, User)
    module_level = nextfake.generate(User, 2)
    assert_type(module_level, list[User])
    assert len(users) == 100
    assert isinstance(users[0], User)


def test_provider_methods_are_typed() -> None:
    gen = nextfake.Faker(locale="en_GB", seed=2, threads=2)
    assert_type(gen.name(), str)
    assert_type(gen.names(3), list[str])
    assert_type(gen.random_int(1, 6), int)
    assert_type(gen.random_ints(3), list[int])
    assert_type(gen.price(), float)
    assert_type(gen.pybool(), bool)
    assert_type(gen.date(), dt.date)
    assert_type(gen.date_time(), dt.datetime)
    assert_type(gen.dates(2), list[dt.date])
    assert_type(gen.random_element([1, 2, 3]), int)
    assert_type(gen.to_dicts(User, 2), list[dict[str, Any]])
    assert_type(gen.to_columns(User, 2), dict[str, list[Any]])
    assert_type(gen.locale, str)
    assert_type(gen.threads, int | None)
    spec: nextfake.Spec = nextfake.Int(1, 2).nullable(0.5)
    assert spec.null_probability == 0.5
