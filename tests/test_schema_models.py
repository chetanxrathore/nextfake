"""Schema introspection & field-name heuristics (NXFK-302)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import decimal
import enum
import ipaddress
import uuid
from typing import Annotated, Any, Literal, Optional, TypedDict

import pytest
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, IPvAnyAddress
from typing_extensions import NotRequired  # typing.NotRequired is 3.11+

import nextfake
from nextfake.schema import infer_provider


class Plan(enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Priority(enum.IntEnum):
    LOW = 1
    HIGH = 2


class Address(BaseModel):
    street: str
    city: str
    zip_code: str
    country_code: str


class User(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    city: str
    ip_address: IPvAnyAddress
    created_at: dt.datetime
    age: int = Field(ge=18, le=65)
    balance: decimal.Decimal = Field(ge=0, le=500)
    is_active: bool
    plan: Plan
    priority: Priority
    tier: Literal["a", "b", "c"]
    website: HttpUrl | None = None
    uid: uuid.UUID
    nickname: Optional[str] = Field(default=None, max_length=6)  # noqa: UP045
    reference: Annotated[str, nextfake.Pattern("REF-####")]
    display: str = Field(alias="displayName")
    home: Address
    tags: list[str] = Field(default_factory=list)  # unsupported -> uses default


@dataclasses.dataclass
class DCUser:
    id: int
    full_name: str
    email: str
    city: str
    ip_address: ipaddress.IPv4Address
    created_at: dt.datetime
    uid: uuid.UUID
    plan: Plan
    amount: decimal.Decimal
    birthday: dt.date
    login_time: dt.time
    sku: str = dataclasses.field(metadata={"nextfake": nextfake.Pattern("SKU-###")})
    notes: str | None = None


class TDUser(TypedDict):
    id: int
    full_name: str
    email: str
    city: str
    ip_address: str
    created_at: dt.datetime
    plan: Plan
    comment: NotRequired[str]


class Strict(BaseModel):
    model_config = ConfigDict(strict=False, extra="forbid")
    code: str = Field(min_length=10, max_length=12)
    small: int = Field(gt=0, lt=5)
    ratio: float = Field(ge=0.25, le=0.5)


class Tree(BaseModel):
    value: int
    child: Tree | None = None


def test_pydantic_generate_1000_valid(gen: nextfake.Faker) -> None:
    users = gen.generate(User, count=1_000)
    assert len(users) == 1_000
    assert all(isinstance(u, User) for u in users)
    # round-trip through validation again: zero errors
    for u in users[:200]:
        User.model_validate(u.model_dump(by_alias=True))
    assert [u.id for u in users] == list(range(1, 1001))
    assert all(18 <= u.age <= 65 for u in users)
    assert all(0 <= u.balance <= 500 for u in users)
    assert {u.plan for u in users} == set(Plan)
    assert {u.priority for u in users} == set(Priority)
    assert {u.tier for u in users} == {"a", "b", "c"}
    assert all(u.reference.startswith("REF-") for u in users)
    assert all(u.nickname is None or len(u.nickname) <= 6 for u in users)
    assert 30 < sum(u.website is None for u in users) < 200
    assert all(isinstance(u.home, Address) for u in users)
    assert all(u.tags == [] for u in users)
    assert len({u.uid for u in users}) == 1_000


def test_pydantic_without_validation(gen: nextfake.Faker) -> None:
    users = gen.generate(User, 50, validate=False)
    assert all(isinstance(u, User) for u in users)
    assert isinstance(users[0].plan, Plan)
    assert isinstance(users[0].uid, uuid.UUID)


def test_dataclass_generate(gen: nextfake.Faker) -> None:
    rows = gen.generate(DCUser, 1_000)
    assert all(isinstance(r, DCUser) for r in rows)
    r = rows[0]
    assert isinstance(r.ip_address, ipaddress.IPv4Address)
    assert isinstance(r.uid, uuid.UUID)
    assert isinstance(r.plan, Plan)
    assert isinstance(r.amount, decimal.Decimal)
    assert isinstance(r.birthday, dt.date)
    assert isinstance(r.login_time, dt.time)
    assert all(x.sku.startswith("SKU-") for x in rows)
    assert "@" in r.email


def test_typeddict_generate(gen: nextfake.Faker) -> None:
    rows = gen.generate(TDUser, 1_000)
    assert len(rows) == 1_000
    assert isinstance(rows[0], dict)
    assert set(rows[0]) == {"id", "full_name", "email", "city", "ip_address", "created_at",
                            "plan", "comment"}  # fmt: skip
    assert isinstance(rows[0]["plan"], Plan)
    assert isinstance(rows[0]["created_at"], dt.datetime)


def test_identical_values_across_schema_kinds() -> None:
    """Same field names + same seed => same values, whatever the schema container."""
    a = nextfake.Faker(seed=3).generate(User, 100)
    b = nextfake.Faker(seed=3).generate(DCUser, 100)
    c = nextfake.Faker(seed=3).generate(TDUser, 100)
    assert [u.full_name for u in a] == [u.full_name for u in b] == [u["full_name"] for u in c]
    assert [u.city for u in a] == [u.city for u in b] == [u["city"] for u in c]


def test_dict_schema(gen: nextfake.Faker) -> None:
    rows = gen.to_dicts({"id": "int", "email": "email", "created_at": "datetime"}, 500)
    assert [r["id"] for r in rows] == list(range(1, 501))
    assert all("@" in r["email"] for r in rows)
    assert all(isinstance(r["created_at"], dt.datetime) for r in rows)
    nullable = gen.to_dicts({"maybe": "email?"}, 5000)
    nulls = sum(r["maybe"] is None for r in nullable)
    assert 350 < nulls < 650


def test_dict_schema_types_and_nested(gen: nextfake.Faker) -> None:
    rows = gen.to_dicts(
        {
            "user_email": "str",
            "signup_date": "datetime",
            "price": float,
            "geo": {"lat": "latitude", "lng": "longitude"},
            "age": nextfake.Int(30, 31),
        },
        100,
    )
    r = rows[0]
    assert "@" in r["user_email"]
    assert isinstance(r["signup_date"], dt.datetime)
    assert set(r["geo"]) == {"lat", "lng"}
    assert r["age"] in (30, 31)
    assert list(r) == ["user_email", "signup_date", "price", "geo", "age"]


def test_overrides(gen: nextfake.Faker) -> None:
    users = gen.generate(User, 200, overrides={"age": nextfake.Int(20, 21), "city": "country"})
    assert all(u.age in (20, 21) for u in users)
    countries = set(gen.countries(5000))
    assert all(u.city in countries for u in users)
    with pytest.raises(nextfake.SchemaError, match="unknown fields"):
        gen.generate(User, 1, overrides={"nope": nextfake.Int()})


def test_constraints(gen: nextfake.Faker) -> None:
    rows = gen.generate(Strict, 2000)
    assert all(10 <= len(r.code) <= 12 for r in rows)
    assert {r.small for r in rows} == {1, 2, 3, 4}
    assert all(0.25 <= r.ratio <= 0.5 for r in rows)


def test_null_probability_configurable() -> None:
    none_ = nextfake.Faker(seed=1, null_probability=0.0).generate(User, 500)
    assert all(u.website is not None for u in none_)
    all_ = nextfake.Faker(seed=1).generate(User, 500, null_probability=1.0)
    assert all(u.website is None and u.nickname is None for u in all_)


def test_recursive_optional_model(gen: nextfake.Faker) -> None:
    trees = gen.generate(Tree, 10)
    assert all(t.child is None for t in trees)


def test_unsupported_required_type_raises() -> None:
    @dataclasses.dataclass
    class Bad:
        payload: dict[str, Any]

    with pytest.raises(nextfake.UnsupportedTypeError, match="payload"):
        nextfake.compile_schema(Bad)


def test_regex_constraint_requires_override(gen: nextfake.Faker) -> None:
    class WithPattern(BaseModel):
        code: str = Field(pattern=r"^[A-Z]{3}$")

    with pytest.raises(nextfake.UnsupportedTypeError, match="pattern"):
        gen.generate(WithPattern, 1)
    rows = gen.generate(WithPattern, 20, overrides={"code": nextfake.Pattern("???")})
    assert all(len(r.code) == 3 for r in rows)


def test_one(gen: nextfake.Faker) -> None:
    assert isinstance(gen.one(User), User)


def test_to_columns_and_tuples(gen: nextfake.Faker) -> None:
    cols = gen.to_columns(TDUser, 10)
    assert list(cols) == ["id", "full_name", "email", "city", "ip_address", "created_at",
                          "plan", "comment"]  # fmt: skip
    assert all(len(v) == 10 for v in cols.values())
    tuples = gen.to_tuples(TDUser, 3)
    assert len(tuples[0]) == 8
    with pytest.raises(nextfake.UnsupportedTypeError, match="nested"):
        gen.to_columns(User, 10)


@pytest.mark.parametrize(
    ("field_name", "provider"),
    [
        ("full_name", "name"),
        ("user_email", "email"),
        ("contactEmail", "email"),
        ("ip", "ipv4"),
        ("ip_address", "ipv4"),
        ("client_ip", "ipv4"),
        ("signup_date", "datetime"),
        ("created_at", "datetime"),
        ("updatedAt", "datetime"),
        ("price", "price"),
        ("amount", "price"),
        ("total_amount", "price"),
        ("country_code", "country_code"),
        ("billing_country_code", "country_code"),
        ("is_active", "bool"),
        ("has_children", "bool"),
        ("first_name", "first_name"),
        ("surname", "last_name"),
        ("company_name", "company"),
        ("job_title", "job_title"),
        ("phone", "phone_number"),
        ("mobile_phone", "phone_number"),
        ("zip", "postcode"),
        ("postal_code", "postcode"),
        ("homepage_url", "url"),
        ("user_agent", "user_agent"),
        ("description", "paragraph"),
        ("title", "sentence"),
        ("dob", "date_of_birth"),
        ("latitude", "latitude"),
        ("currency", "currency_code"),
        ("username", "username"),
    ],
)
def test_field_name_heuristics(field_name: str, provider: str) -> None:
    spec = infer_provider(field_name)
    assert spec is not None
    assert spec.provider == provider


def test_heuristics_respect_annotations(gen: nextfake.Faker) -> None:
    @dataclasses.dataclass
    class Mixed:
        created_at: int
        signup_date: str
        user_id: str
        account_id: int
        birthday: dt.date

    m = gen.generate(Mixed, 50)
    assert all(isinstance(x.created_at, int) and x.created_at > 1_500_000_000 for x in m)
    dt.datetime.fromisoformat(m[0].signup_date)
    uuid.UUID(m[0].user_id)
    assert all(1 <= x.account_id <= 1_000_000 for x in m)
    assert isinstance(m[0].birthday, dt.date)


def test_validation_failure_is_wrapped(gen: nextfake.Faker) -> None:
    class Narrow(BaseModel):
        email: EmailStr

    with pytest.raises(nextfake.SchemaError, match="failed validation"):
        gen.generate(Narrow, 5, overrides={"email": "word"})


def test_invalid_schema() -> None:
    with pytest.raises(nextfake.SchemaError):
        nextfake.compile_schema(42)
    with pytest.raises(nextfake.SchemaError):
        nextfake.compile_schema({})
