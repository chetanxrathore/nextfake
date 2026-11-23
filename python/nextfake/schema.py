"""Schema introspection: Pydantic v2 models, dataclasses, TypedDicts and raw ``dict`` schemas.

:func:`compile_schema` turns any supported schema into a :class:`CompiledSchema` — an ordered
list of :class:`FieldPlan` objects, each describing which Rust provider generates the field,
its nullability, an optional post-conversion (e.g. ``str`` -> ``uuid.UUID`` for dataclasses)
and, for nested models, a nested :class:`CompiledSchema`.

Provider selection, in priority order:

1. explicit ``overrides={"field": Spec}`` passed by the caller,
2. a :class:`~nextfake.types.Spec` found in ``Annotated[...]`` metadata (or dataclass
   ``field(metadata={"nextfake": Spec})``),
3. ``Literal[...]`` / ``Enum`` values,
4. field-name heuristics (``user_email`` -> ``email``, ``created_at`` -> ``datetime``, ...)
   reconciled with the annotated type,
5. the annotated type's default provider, narrowed by numeric / length constraints
   (``ge``, ``gt``, ``le``, ``lt``, ``min_length``, ``max_length``).
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import decimal
import enum
import functools
import ipaddress
import math
import re
import types
import typing
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal, Union, get_args, get_origin

from nextfake._nextfake import CompiledPlan
from nextfake.exceptions import SchemaError, UnsupportedTypeError
from nextfake.types import (
    Bool,
    Choice,
    Constant,
    Date,
    DateTime,
    Float,
    Int,
    Price,
    Provider,
    Serial,
    Spec,
    String,
)

__all__ = ["CompiledSchema", "FieldPlan", "SchemaKind", "compile_schema", "infer_provider"]

SchemaKind = Literal["pydantic", "dataclass", "typeddict", "mapping"]
KeyMode = Literal["name", "input"]
Converter = Callable[[Any], Any]

_NONE_TYPE = type(None)
_MISSING = object()

# Anchor for Pydantic's ``FutureDate`` / ``PastDate`` / ``FutureDatetime`` / ``PastDatetime``;
# ``None`` = today (future types) or the fixed default ranges (past types).
_REFERENCE_DATE: ContextVar[_dt.date | None] = ContextVar("nextfake_reference_date", default=None)


@contextmanager
def _reference_date(value: _dt.date | None) -> Iterator[None]:
    token = _REFERENCE_DATE.set(value)
    try:
        yield
    finally:
        _REFERENCE_DATE.reset(token)


@dataclass
class FieldPlan:
    """How one field is generated."""

    name: str
    """Attribute / output key."""
    input_key: str
    """Key used when the data is validated (the Pydantic validation alias)."""
    spec: Spec | None
    """Provider spec for flat fields (``None`` for nested models)."""
    null_probability: float = 0.0
    converter: Converter | None = None
    """Applied to non-null values when building unvalidated objects (dataclasses, ...)."""
    always_convert: bool = False
    """Apply ``converter`` even before Pydantic validation."""
    nested: CompiledSchema | None = None
    input_path: tuple[str | int, ...] | None = None
    """Nested input location for a Pydantic ``AliasPath`` validation alias."""
    columnar: bool = True
    """Whether columnar exports (Arrow, Parquet, ...) can represent the field's values."""


@dataclass
class CompiledSchema:
    """A compiled schema, ready for generation."""

    kind: SchemaKind
    target: Any
    fields: list[FieldPlan]
    _plans: dict[str, CompiledPlan | None] = field(default_factory=dict, repr=False)

    @property
    def names(self) -> list[str]:
        return [f.name for f in self.fields]

    @property
    def flat_fields(self) -> list[FieldPlan]:
        return [f for f in self.fields if f.nested is None]

    @property
    def nested_fields(self) -> list[FieldPlan]:
        return [f for f in self.fields if f.nested is not None]

    def columns(self, keys: KeyMode = "name") -> list[dict[str, Any]]:
        """Rust column specs for the flat fields."""
        out = []
        for f in self.flat_fields:
            assert f.spec is not None
            key = f.input_key if keys == "input" else f.name
            out.append(f.spec.to_column(key, null_probability=f.null_probability, seed_key=f.name))
        return out

    def plan(self, keys: KeyMode = "name") -> CompiledPlan | None:
        """The compiled Rust plan for the flat fields (cached), or ``None`` if there are none."""
        if keys not in self._plans:
            cols = self.columns(keys)
            self._plans[keys] = CompiledPlan(cols) if cols else None
        return self._plans[keys]

    def require_flat(self, operation: str) -> CompiledPlan:
        """Return the plan, raising if the schema has nested fields (columnar exports)."""
        if self.nested_fields:
            names = ", ".join(f.name for f in self.nested_fields)
            raise UnsupportedTypeError(
                f"{operation} does not support nested model fields ({names}); "
                "use generate()/to_dicts(), or flatten the schema / add overrides"
            )
        mixed = [f.name for f in self.flat_fields if not f.columnar]
        if mixed:
            raise UnsupportedTypeError(
                f"{operation} needs one value type per column, but {', '.join(mixed)} mix "
                "value types (Enum / Literal); add an override such as nextfake.Choice([...])"
            )
        plan = self.plan("name")
        if plan is None:
            raise SchemaError("schema has no fields")
        return plan


# ---------------------------------------------------------------------------------------------
# Field-name heuristics
# ---------------------------------------------------------------------------------------------

_ID = Spec("__id__")  # marker: resolved per annotated type (serial / int / uuid4)


def _p(name: str, **params: Any) -> Spec:
    return Provider(name, **params)


_EXACT: dict[str, Spec] = {}


def _register(spec: Spec, *names: str) -> None:
    for n in names:
        _EXACT[n] = spec


_register(_ID, "id", "pk", "key")
_register(_p("uuid4"), "uuid", "guid")
_register(_p("first_name"), "first_name", "firstname", "fname", "given_name", "forename")
_register(_p("last_name"), "last_name", "lastname", "lname", "surname", "family_name")
_register(
    _p("name"),
    "name", "full_name", "fullname", "display_name", "customer_name", "contact_name",
    "author", "author_name", "owner", "owner_name", "employee_name", "person_name",
    "real_name", "legal_name", "account_name", "recipient", "recipient_name",
)  # fmt: skip
_register(
    _p("username"),
    "username", "user_name", "login", "handle", "screen_name", "nickname", "nick",
)  # fmt: skip
_register(_p("email"), "email", "e_mail", "email_address", "mail")
_register(
    _p("phone_number"),
    "phone", "phone_number", "telephone", "tel", "mobile", "mobile_number", "cell",
    "cell_phone", "fax", "phone_no",
)  # fmt: skip
_register(
    _p("ipv4"),
    "ip", "ip_address", "ipv4", "ip_addr", "client_ip", "remote_addr", "remote_ip",
    "source_ip", "src_ip", "dst_ip", "dest_ip", "host_ip", "ipv4_address",
)  # fmt: skip
_register(_p("ipv6"), "ipv6", "ipv6_address")
_register(_p("mac_address"), "mac", "mac_address", "mac_addr")
_register(
    _p("url"),
    "url", "website", "homepage", "web_site", "link", "uri", "profile_url", "avatar_url",
    "image_url", "photo_url", "href", "site",
)  # fmt: skip
_register(_p("domain_name"), "domain", "domain_name", "hostname", "host")
_register(_p("user_agent"), "user_agent", "useragent", "ua", "browser")
_register(
    _p("street_address"),
    "street", "street_address", "address_line1", "address_line_1", "address1", "line1",
)  # fmt: skip
_register(
    _p("address"),
    "address", "full_address", "mailing_address", "billing_address", "shipping_address",
    "home_address", "postal_address",
)  # fmt: skip
_register(_p("city"), "city", "town", "municipality", "locality")
_register(_p("state"), "state", "province", "region", "county", "prefecture")
_register(_p("state_abbr"), "state_code", "state_abbr", "state_abbreviation")
_register(
    _p("postcode"),
    "zip", "zipcode", "zip_code", "postcode", "post_code", "postal_code", "postalcode",
)  # fmt: skip
_register(_p("country"), "country", "country_name", "nation", "nationality")
_register(_p("country_code"), "country_code", "country_iso", "iso_country", "iso_country_code")
_register(
    _p("company"),
    "company", "company_name", "employer", "organization", "organisation", "org",
    "business_name", "firm", "vendor", "supplier", "manufacturer",
)  # fmt: skip
_register(
    _p("job_title"),
    "job", "job_title", "occupation", "position", "profession", "role_title", "designation",
)  # fmt: skip
_register(_p("latitude"), "latitude", "lat")
_register(_p("longitude"), "longitude", "lng", "lon", "long")
_register(
    _p("credit_card_number"),
    "credit_card", "credit_card_number", "card_number", "cc_number", "card_no", "pan",
)  # fmt: skip
_register(_p("currency_code"), "currency", "currency_code", "currency_iso")
_register(
    Price(),
    "price", "amount", "cost", "total", "subtotal", "balance", "salary", "fee", "revenue",
    "unit_price", "total_price", "order_total", "payment", "income", "budget", "tax",
    "discount", "wage",
)  # fmt: skip
_register(
    _p("paragraph"),
    "description", "bio", "about", "summary", "body", "content", "text", "comment",
    "comments", "notes", "note", "message", "review", "details", "biography", "abstract",
)  # fmt: skip
_register(_p("sentence"), "title", "subject", "headline", "caption", "tagline", "slogan")
_register(_p("word"), "word", "tag", "keyword", "label", "category", "slug")
_register(_p("password"), "password", "passwd", "pwd", "secret", "passphrase")
_register(_p("hex_color"), "color", "colour", "hex_color", "hex_colour")
_register(Int(18, 90), "age")
_register(Int(1970, 2025), "year")
_register(Int(1, 100), "quantity", "qty")
_register(Int(0, 1000), "count", "stock", "inventory", "num_items", "views", "likes")
_register(Int(1, 5), "rating", "stars")
_register(Float(0.0, 100.0, decimals=2), "score", "percent", "percentage", "ratio")
_register(_p("date_of_birth"), "dob", "date_of_birth", "birth_date", "birthdate", "birthday")
_register(
    DateTime(),
    "created", "updated", "modified", "deleted", "timestamp", "datetime", "last_login",
    "last_seen", "date",
)  # fmt: skip
_register(
    Bool(),
    "active", "enabled", "verified", "deleted_flag", "archived", "published", "subscribed",
    "visible", "approved", "confirmed", "flag", "admin", "premium",
)  # fmt: skip
_register(_p("uuid4"), "token", "api_key", "session_id", "request_id", "trace_id")

_BOOL_PREFIXES = {"is", "has", "can", "should", "was", "allow", "allows", "use", "uses", "show"}
_BOOL_SUFFIXES = {
    "flag", "enabled", "active", "verified", "deleted", "archived", "visible", "published",
    "subscribed", "confirmed", "approved", "opted",
}  # fmt: skip
_MONEY = {
    "price", "amount", "cost", "total", "subtotal", "balance", "salary", "fee", "revenue",
    "payment", "income", "budget", "tax", "discount", "wage", "spend", "value",
}  # fmt: skip
_TEXT = {
    "description", "bio", "summary", "body", "content", "comment", "comments", "notes",
    "note", "message", "review", "details", "text", "about",
}  # fmt: skip
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _snake(name: str) -> str:
    s = _CAMEL.sub("_", name.strip()).lower().replace("-", "_").replace(" ", "_")
    return re.sub(r"_+", "_", s).strip("_")


def infer_provider(field_name: str) -> Spec | None:
    """Guess a provider from a field name alone (``"user_email"`` -> ``email``).

    Returns ``None`` when no heuristic applies. The returned spec may be the internal
    ``__id__`` marker for identifier-like names, which is resolved by the field's type.
    """
    n = _snake(field_name)
    if not n:
        return None
    if n in _EXACT:
        return _EXACT[n]
    toks = n.split("_")
    first, last = toks[0], toks[-1]
    if len(toks) > 1 and first in _BOOL_PREFIXES:
        return Bool()
    if last in _BOOL_SUFFIXES and len(toks) > 1:
        return Bool()
    if last in {"at", "on"} or last in {"time", "timestamp", "datetime", "ts", "date"}:
        return DateTime()
    if last in {"email", "mail"}:
        return _p("email")
    if last in {"phone", "mobile", "tel", "telephone", "fax"}:
        return _p("phone_number")
    if last in {"url", "uri", "link", "website", "homepage", "href"}:
        return _p("url")
    if last == "ip" or n.endswith("ip_address") or last == "ipv4":
        return _p("ipv4")
    if last == "ipv6":
        return _p("ipv6")
    if last == "mac":
        return _p("mac_address")
    if last in {"city", "town"}:
        return _p("city")
    if n.endswith("country_code"):
        return _p("country_code")
    if last == "country":
        return _p("country")
    if last in {"zip", "zipcode", "postcode"} or n.endswith("postal_code"):
        return _p("postcode")
    if last in {"state", "province", "region", "county", "prefecture"}:
        return _p("state")
    if last == "street":
        return _p("street_address")
    if last == "address":
        return _p("ipv4") if "ip" in toks else _p("address")
    if last == "name":
        if first in {"first", "given", "fore"}:
            return _p("first_name")
        if first in {"last", "family", "sur"}:
            return _p("last_name")
        if first in {"company", "business", "org", "organization", "organisation", "employer"}:
            return _p("company")
        if first in {"user", "login", "screen", "account"} and len(toks) == 2:
            return _p("username")
        if first in {"domain", "host"}:
            return _p("domain_name")
        if first == "city":
            return _p("city")
        if first == "country":
            return _p("country")
        if first == "street":
            return _p("street_address")
        if first in {"file", "product", "item", "project", "app", "event", "team", "brand"}:
            return _p("word")
        return _p("name")
    if last in {"username", "login", "handle"}:
        return _p("username")
    if last in {"id", "uuid", "guid", "pk"}:
        return _p("uuid4") if last in {"uuid", "guid"} else _ID
    if last in _MONEY:
        return Price()
    if last in {"lat", "latitude"}:
        return _p("latitude")
    if last in {"lng", "lon", "longitude"}:
        return _p("longitude")
    if last in _TEXT:
        return _p("paragraph")
    if last in {"title", "subject", "headline", "caption"}:
        return _p("job_title") if first == "job" else _p("sentence")
    if last in {"company", "employer", "organization", "organisation", "vendor", "supplier"}:
        return _p("company")
    if last == "currency":
        return _p("currency_code")
    if last in {"quantity", "qty"}:
        return Int(1, 100)
    if last in {"count", "stock", "inventory", "views", "likes", "clicks"}:
        return Int(0, 1000)
    if last == "age":
        return Int(18, 90)
    if last == "year":
        return Int(1970, 2025)
    if last in {"rating", "stars"}:
        return Int(1, 5)
    if last in {"score", "percent", "percentage", "ratio"}:
        return Float(0.0, 100.0, decimals=2)
    if last in {"color", "colour"}:
        return _p("hex_color")
    if last in {"password", "passwd", "pwd", "secret"}:
        return _p("password")
    if last == "agent" and "user" in toks:
        return _p("user_agent")
    if last in {"job", "occupation", "profession", "position"}:
        return _p("job_title")
    if last in {"domain", "hostname", "host"}:
        return _p("domain_name")
    if last in {"card"} and ("credit" in toks or "debit" in toks):
        return _p("credit_card_number")
    if last in {"tag", "keyword", "label", "category", "word", "slug"}:
        return _p("word")
    if last in {"token", "key"} and len(toks) > 1:
        return _p("uuid4")
    return None


_PROVIDER_KIND: dict[str, str] = {
    "serial": "int", "int": "int", "unix_time": "int",
    "float": "float", "price": "float", "latitude": "float", "longitude": "float",
    "bool": "bool",
    "date": "date", "date_of_birth": "date",
    "datetime": "datetime", "time": "time", "duration": "duration",
}  # fmt: skip


def _kind(spec: Spec) -> str:
    if spec.provider == "choice":
        vals = spec.params.get("values", [])
        if vals and all(isinstance(v, int) for v in vals):
            return "int"
        if vals and all(isinstance(v, (int, float)) for v in vals):
            return "float"
    return _PROVIDER_KIND.get(spec.provider, "str")


# ---------------------------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------------------------


@dataclass
class _Constraints:
    ge: float | None = None
    gt: float | None = None
    le: float | None = None
    lt: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    decimal_places: int | None = None
    max_digits: int | None = None
    multiple_of: float | None = None
    multiple_of_decimals: int | None = None
    strict: bool = False
    explicit: Spec | None = None

    def absorb(self, meta: Any) -> None:
        if isinstance(meta, Spec):
            self.explicit = meta
            return
        for attr in ("ge", "gt", "le", "lt"):
            v = getattr(meta, attr, None)
            if isinstance(v, (int, float, decimal.Decimal)) and not isinstance(v, bool):
                setattr(self, attr, float(v))
        for attr in ("min_length", "max_length", "decimal_places", "max_digits"):
            v = getattr(meta, attr, None)
            if isinstance(v, int) and not isinstance(v, bool):
                setattr(self, attr, v)
        m = getattr(meta, "multiple_of", None)
        if isinstance(m, (int, float, decimal.Decimal)) and not isinstance(m, bool) and m > 0:
            self.multiple_of = float(m)
            exponent = decimal.Decimal(str(m)).normalize().as_tuple().exponent
            self.multiple_of_decimals = -exponent if isinstance(exponent, int) else None
            if self.multiple_of_decimals is not None and self.multiple_of_decimals < 0:
                self.multiple_of_decimals = 0
        if getattr(meta, "strict", None) is True:
            self.strict = True
        pat = getattr(meta, "pattern", None)
        if isinstance(pat, str):
            self.pattern = pat
        elif pat is not None and hasattr(pat, "pattern"):
            self.pattern = str(pat.pattern)

    @property
    def has_numeric(self) -> bool:
        return any(v is not None for v in (self.ge, self.gt, self.le, self.lt, self.multiple_of))


def _numeric_bounds(c: _Constraints, integer: bool) -> tuple[float | None, float | None]:
    lo = c.ge
    if c.gt is not None:
        g = math.floor(c.gt) + 1 if integer else math.nextafter(c.gt, math.inf)
        lo = g if lo is None else max(lo, g)
    hi = c.le
    if c.lt is not None:
        g = math.ceil(c.lt) - 1 if integer else math.nextafter(c.lt, -math.inf)
        hi = g if hi is None else min(hi, g)
    return lo, hi


def _apply_numeric(spec: Spec, c: _Constraints, integer: bool) -> Spec:
    if not c.has_numeric:
        return spec
    lo, hi = _numeric_bounds(c, integer)
    if spec.provider == "serial":
        if hi is None and c.multiple_of is None:
            start = max(int(spec.params.get("start", 1)), int(lo or 1))
            return Serial(start=start)
        spec = Int()
    defaults = {"int": (0, 10_000), "float": (0.0, 1000.0), "price": (1.0, 1000.0)}
    provider = spec.provider if spec.provider in defaults else ("int" if integer else "float")
    d_lo, d_hi = defaults[provider]
    cur_lo = float(spec.params.get("min", d_lo)) if spec.provider == provider else float(d_lo)
    cur_hi = float(spec.params.get("max", d_hi)) if spec.provider == provider else float(d_hi)
    new_lo = cur_lo if lo is None else max(cur_lo, lo)
    new_hi = cur_hi if hi is None else min(cur_hi, hi)
    if new_lo > new_hi:  # heuristic range incompatible with constraints: honour constraints
        span = d_hi - d_lo
        new_lo = lo if lo is not None else (hi if hi is not None else 0.0) - span
        new_hi = hi if hi is not None else new_lo + span
    m = c.multiple_of
    if provider == "int":
        step = int(m) if m is not None and m == int(m) else None
        # Widen a heuristic range that holds no multiple (e.g. rating 1..5, multiple_of=10).
        if step is not None and step > 1 and math.floor(new_hi / step) < math.ceil(new_lo / step):
            new_hi = new_lo + step * 10 if hi is None else new_hi
            new_lo = new_hi - step * 10 if lo is None else new_lo
        return Int(math.ceil(new_lo), math.floor(new_hi), multiple_of=step)
    if provider == "price" and m is None:
        lo_c, hi_c = math.ceil(new_lo * 100) / 100, math.floor(new_hi * 100) / 100
        if lo_c <= hi_c:
            return Price(lo_c, hi_c)
    decimals = spec.params.get("decimals") if spec.provider == "float" else None
    if provider == "price":
        decimals = 2
    if m is not None and c.multiple_of_decimals is not None:
        decimals = max(decimals or 0, c.multiple_of_decimals)
    return Float(new_lo, new_hi, decimals=decimals, multiple_of=m)


def _apply_length(spec: Spec, c: _Constraints, field_name: str, *, semantic: bool) -> Spec:
    """Honour ``min_length`` / ``max_length``.

    Semantic providers (e-mail, name, city, ...) keep their meaning: out-of-range values are
    redrawn in Rust (and only truncated / padded as a last resort). Fields without a semantic
    provider use random alphanumerics of a fitting length instead.
    """
    if c.pattern is not None:
        raise UnsupportedTypeError(
            f"field {field_name!r} has a regex pattern constraint ({c.pattern!r}); add an "
            f"override such as overrides={{{field_name!r}: nextfake.Pattern('???-####')}}"
        )
    lo, hi = c.min_length, c.max_length
    if lo is None and hi is None:
        return spec
    if spec.provider == "string":
        cur_lo = int(spec.params.get("min_length", 8))
        cur_hi = int(spec.params.get("max_length", 16))
        new_lo = max(cur_lo, lo or 0) if hi is None or max(cur_lo, lo or 0) <= hi else (lo or 0)
        new_hi = min(cur_hi, hi) if hi is not None else max(cur_hi, new_lo)
        if new_lo > new_hi:
            new_hi = new_lo
        return String(new_lo, new_hi)
    if not semantic and lo is not None and lo > 3:
        upper = hi if hi is not None else lo + 16
        return String(lo, max(lo, min(upper, lo + 24)))
    fit_lo = max(lo or 0, spec.min_length or 0)
    fit_hi: int | None = hi
    if spec.max_length is not None:
        fit_hi = spec.max_length if hi is None else min(hi, spec.max_length)
    if fit_hi is not None and fit_lo > fit_hi:
        fit_lo = fit_hi
    return spec.length(min_length=fit_lo or None, max_length=fit_hi)


# ---------------------------------------------------------------------------------------------
# Type -> spec resolution
# ---------------------------------------------------------------------------------------------


def _to_decimal(v: Any) -> decimal.Decimal:
    return decimal.Decimal(repr(v))


def _to_bytes(v: Any) -> bytes:
    return str(v).encode()


def _decimal_spec(spec: Spec, c: _Constraints) -> Spec:
    """Narrow a ``Decimal`` field's spec by ``decimal_places`` / ``max_digits``."""
    places = c.decimal_places
    if c.max_digits is not None:
        if places is None:
            places = max(0, min(2, c.max_digits - 1))
        whole = max(0, c.max_digits - places)
        bound = 10.0**whole - 10.0**-places
        c.le = bound if c.le is None else min(c.le, bound)
        c.ge = -bound if c.ge is None else max(c.ge, -bound)
    spec = _apply_numeric(spec, c, integer=False)
    if places is not None:
        if spec.provider == "price" and places < 2:
            spec = Float(float(spec.params["min"]), float(spec.params["max"]), decimals=places)
        elif spec.provider == "float":
            current = spec.params.get("decimals")
            spec = spec.with_params(decimals=places if current is None else min(current, places))
    return spec


def _past_future(tname: str) -> Spec | None:
    """Specs for Pydantic's past / future date and datetime types."""
    ref = _REFERENCE_DATE.get()
    day = _dt.timedelta(days=1)
    if tname == "PastDate":
        return Date(end=ref - day) if ref is not None else Date()
    if tname == "PastDatetime":
        return (
            DateTime(end=_dt.datetime.combine(ref, _dt.time()) - _dt.timedelta(seconds=1))
            if ref is not None
            else DateTime()
        )
    base = ref if ref is not None else _dt.date.today()
    if tname == "FutureDate":
        return Date(base + day, base + 3650 * day)
    if tname == "FutureDatetime":
        start = _dt.datetime.combine(base + day, _dt.time())
        return DateTime(start, start + 3650 * day)
    return None


def _type_name(tp: Any) -> tuple[str, str]:
    return getattr(tp, "__name__", ""), getattr(tp, "__module__", "")


def _is_pydantic_model(tp: Any) -> bool:
    if not isinstance(tp, type):
        return False
    try:
        from pydantic import BaseModel
    except ImportError:  # pragma: no cover - optional dependency
        return False
    return issubclass(tp, BaseModel)


def _is_typeddict(tp: Any) -> bool:
    if typing.is_typeddict(tp):
        return True
    try:
        import typing_extensions
    except ImportError:  # pragma: no cover
        return False
    return bool(typing_extensions.is_typeddict(tp))


def _is_schema_class(tp: Any) -> bool:
    return (
        _is_pydantic_model(tp)
        or (isinstance(tp, type) and dataclasses.is_dataclass(tp))
        or _is_typeddict(tp)
    )


_QUALIFIERS = {"Required", "NotRequired", "ReadOnly", "ClassVar", "Final"}
_TYPE_ALIAS: Any = getattr(typing, "TypeAliasType", None)


def _unwrap(tp: Any, c: _Constraints) -> tuple[Any, bool]:
    """Strip Annotated / Optional / TypedDict qualifiers; collect metadata."""
    nullable = False
    for _ in range(16):
        origin = get_origin(tp)
        if origin is typing.Annotated:
            base, *meta = get_args(tp)
            for m in meta:
                c.absorb(m)
                for inner in getattr(m, "metadata", ()) or ():
                    c.absorb(inner)
            tp = base
            continue
        if origin is Union or origin is types.UnionType:
            args = get_args(tp)
            non_none = [a for a in args if a is not _NONE_TYPE]
            if len(non_none) != len(args):
                nullable = True
            if not non_none:
                return Any, True
            tp = non_none[0]
            continue
        if origin is not None and getattr(origin, "_name", None) in _QUALIFIERS:
            tp = get_args(tp)[0]
            continue
        if _TYPE_ALIAS is not None and isinstance(tp, _TYPE_ALIAS):
            tp = tp.__value__
            continue
        break
    return tp, nullable


def _resolve_id(tp: Any, exact: bool) -> Spec:
    if tp is int:
        return Serial() if exact else Int(1, 1_000_000)
    return Provider("uuid4")


def _spec_for_type(
    name: str, tp: Any, c: _Constraints
) -> tuple[Spec, Converter | None, bool] | None:
    """Return ``(spec, converter, always_convert)`` for a resolved (unwrapped) type."""
    heuristic = infer_provider(name)
    exact_id = _snake(name) in {"id", "pk", "key"}
    hk = _kind(heuristic) if heuristic is not None and heuristic is not _ID else None
    tname, tmod = _type_name(tp)

    if tp is bool:
        return Bool(), None, False
    if tp is int:
        if heuristic is _ID:
            spec = _resolve_id(int, exact_id)
        elif hk == "int" and heuristic is not None:
            spec = heuristic
        elif hk == "datetime":
            spec = Provider("unix_time")
        else:
            spec = Int()
        return _apply_numeric(spec, c, integer=True), None, False
    if tp is float:
        spec = heuristic if hk == "float" and heuristic is not None else Float()
        return _apply_numeric(spec, c, integer=False), None, False
    if tp is decimal.Decimal:
        spec = heuristic if hk == "float" and heuristic is not None else Price()
        return _decimal_spec(spec, c), _to_decimal, False
    if tp is _dt.datetime:
        spec = heuristic if hk == "datetime" and heuristic is not None else DateTime()
        return spec, None, False
    if tp is _dt.date:
        if hk == "date" and heuristic is not None:
            return heuristic, None, False
        return Date(), None, False
    if tp is _dt.time:
        return Provider("time"), None, False
    if tp is _dt.timedelta:
        return Provider("duration"), None, False
    if tp is uuid.UUID:
        return Provider("uuid4"), uuid.UUID, False
    if tp is bytes:
        return _apply_length(String(), c, name, semantic=False), _to_bytes, True
    if tp is ipaddress.IPv4Address:
        return Provider("ipv4"), ipaddress.IPv4Address, False
    if tp is ipaddress.IPv6Address:
        return Provider("ipv6"), ipaddress.IPv6Address, False
    if tmod.startswith("pydantic"):
        if tname in {"EmailStr"}:
            return Provider("email"), None, False
        if tname in {"IPvAnyAddress", "IPvAnyInterface"}:
            return Provider("ipv4"), ipaddress.ip_address, False
        if "Url" in tname or "Dsn" in tname:
            return Provider("url"), None, False
        if tname == "SecretStr":
            return Provider("password"), None, False
        if tname == "PaymentCardNumber":
            return Provider("credit_card_number"), None, False
        if tname == "AwareDatetime":
            return DateTime(utc=True), None, False
        if tname == "NaiveDatetime":
            return DateTime(), None, False
        past_future = _past_future(tname)
        if past_future is not None:
            return past_future, None, False
    if tp is str or (isinstance(tp, type) and issubclass(tp, str)):
        semantic = True
        if heuristic is _ID:
            spec = Provider("uuid4")
        elif heuristic is not None and hk == "str":
            spec = heuristic
        elif hk == "datetime":
            spec = Provider("iso8601")
        elif hk == "date" and heuristic is not None:
            spec = Provider("iso_date", **dict(heuristic.params))
            if heuristic.provider == "date_of_birth":
                spec = Spec("iso_date", Date(_dt.date(1940, 1, 1), _dt.date(2007, 12, 31)).params)
        else:
            spec, semantic = Provider("word"), False
        return _apply_length(spec, c, name, semantic=semantic), None, False
    if tp is Any or tp is object:
        if heuristic is _ID:
            return _resolve_id(int, exact_id), None, False
        return (heuristic or Provider("word")), None, False
    return None


def _field_plan(
    name: str,
    input_key: str,
    annotation: Any,
    *,
    metadata: tuple[Any, ...] = (),
    has_default: bool,
    override: Spec | None,
    null_probability: float,
    stack: tuple[Any, ...],
    strict: bool = False,
) -> FieldPlan | None:
    c = _Constraints()
    for m in metadata:
        c.absorb(m)
    tp, nullable = _unwrap(annotation, c)
    null_p = null_probability if nullable else 0.0
    strict = strict or c.strict

    spec = override or c.explicit
    if spec is not None:
        p = spec.null_probability if spec.null_probability is not None else null_p
        return FieldPlan(name, input_key, spec, p)

    if get_origin(tp) is Literal:
        values = list(get_args(tp))
        if any(v is None for v in values):
            values = [v for v in values if v is not None]
            null_p = null_probability
        if not values:  # Literal[None]
            return FieldPlan(name, input_key, Constant("").nullable(1.0), 1.0)
        return _choice_plan(name, input_key, values, null_p, converter=None, strict=strict)
    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        members = list(tp)
        if not members:
            raise UnsupportedTypeError(f"field {name!r}: enum {tp.__name__} has no members")
        values = [m.value for m in members]
        if _homogeneous(values):
            return FieldPlan(
                name, input_key, Choice(values), null_p, converter=tp, always_convert=strict
            )
        return _choice_plan(name, input_key, members, null_p, converter=None, strict=strict)
    if _is_schema_class(tp):
        if tp in stack:
            if has_default or nullable:
                return None
            raise SchemaError(f"field {name!r}: recursive model {tp.__name__} must be Optional")
        nested = _compile_class(tp, overrides=None, null_probability=null_probability, stack=stack)
        return FieldPlan(name, input_key, None, null_p, nested=nested)

    resolved = _spec_for_type(name, tp, c)
    if resolved is None:
        if has_default:
            return None
        raise UnsupportedTypeError(
            f"field {name!r} has unsupported type {tp!r}; add an override, e.g. "
            f"overrides={{{name!r}: nextfake.Provider('word')}}"
        )
    spec, converter, always = resolved
    # Strict-mode models accept only exact types (UUID, Decimal, ...), so convert up front.
    always = always or (strict and converter is not None)
    return FieldPlan(name, input_key, spec, null_p, converter=converter, always_convert=always)


def _homogeneous(values: list[Any]) -> bool:
    kinds = {type(v) for v in values}
    return len(kinds) == 1 and kinds <= {str, int, float, bool}


def _choice_plan(
    name: str,
    input_key: str,
    values: list[Any],
    null_p: float,
    *,
    converter: Converter | None,
    strict: bool,
) -> FieldPlan:
    """A field drawn from fixed values: native choice if homogeneous, else by index."""
    if _homogeneous(values):
        return FieldPlan(name, input_key, Choice(values), null_p, converter=converter)
    return FieldPlan(
        name, input_key, Int(0, len(values) - 1), null_p,
        converter=values.__getitem__, always_convert=True, columnar=False,
    )  # fmt: skip


# ---------------------------------------------------------------------------------------------
# Schema compilers
# ---------------------------------------------------------------------------------------------


def _normalize_overrides(overrides: Mapping[str, Spec | str] | None) -> dict[str, Spec]:
    if not overrides:
        return {}
    out: dict[str, Spec] = {}
    for k, v in overrides.items():
        if isinstance(v, Spec):
            out[k] = v
        elif isinstance(v, str):
            out[k] = Provider(v)
        else:
            raise SchemaError(f"override for {k!r} must be a nextfake Spec or provider name")
    return out


def _check_overrides(overrides: dict[str, Spec], names: list[str], target: str) -> None:
    unknown = sorted(set(overrides) - set(names))
    if unknown:
        raise SchemaError(f"overrides refer to unknown fields of {target}: {', '.join(unknown)}")


def _compile_pydantic(
    model: Any, overrides: dict[str, Spec], null_probability: float, stack: tuple[Any, ...]
) -> CompiledSchema:
    fields_info = model.model_fields
    _check_overrides(overrides, list(fields_info), model.__name__)
    config = getattr(model, "model_config", {}) or {}
    model_strict = bool(config.get("strict"))
    by_alias = config.get("validate_by_alias", True) is not False
    plans: list[FieldPlan] = []
    for name, fi in fields_info.items():
        key, path = _input_location(name, fi, by_alias)
        fp = _field_plan(
            name,
            key,
            fi.annotation,
            metadata=tuple(fi.metadata),
            has_default=not fi.is_required(),
            override=overrides.get(name),
            null_probability=null_probability,
            stack=(*stack, model),
            strict=model_strict,
        )
        if fp is not None:
            fp.input_path = path
            plans.append(fp)
    return CompiledSchema("pydantic", model, plans)


def _input_location(name: str, fi: Any, by_alias: bool) -> tuple[str, tuple[str | int, ...] | None]:
    """The key (or nested ``AliasPath``) under which Pydantic validates a field."""
    if not by_alias:
        return name, None
    alias: Any = fi.validation_alias
    if type(alias).__name__ == "AliasChoices":
        alias = alias.choices[0] if alias.choices else None
    if isinstance(alias, str):
        return alias, None
    if type(alias).__name__ == "AliasPath":
        path = tuple(alias.path)
        if len(path) == 1 and isinstance(path[0], str):
            return path[0], None
        return name, path
    return fi.alias or name, None


def _compile_dataclass(
    cls: Any, overrides: dict[str, Spec], null_probability: float, stack: tuple[Any, ...]
) -> CompiledSchema:
    try:
        hints = typing.get_type_hints(cls, include_extras=True)
    except Exception as exc:  # pragma: no cover - unresolved forward references
        raise SchemaError(f"cannot resolve type hints of {cls.__name__}: {exc}") from exc
    fields_ = [f for f in dataclasses.fields(cls) if f.init]
    _check_overrides(overrides, [f.name for f in fields_], cls.__name__)
    plans: list[FieldPlan] = []
    for f in fields_:
        meta_spec = f.metadata.get("nextfake") if f.metadata else None
        if isinstance(meta_spec, str):
            meta_spec = Provider(meta_spec)
        has_default = (
            f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING
        )
        fp = _field_plan(
            f.name,
            f.name,
            hints.get(f.name, Any),
            has_default=has_default,
            override=overrides.get(f.name) or meta_spec,
            null_probability=null_probability,
            stack=(*stack, cls),
        )
        if fp is not None:
            plans.append(fp)
    return CompiledSchema("dataclass", cls, plans)


def _compile_typeddict(
    td: Any, overrides: dict[str, Spec], null_probability: float, stack: tuple[Any, ...]
) -> CompiledSchema:
    try:
        hints = typing.get_type_hints(td, include_extras=True)
    except Exception as exc:  # pragma: no cover
        raise SchemaError(f"cannot resolve type hints of {td.__name__}: {exc}") from exc
    _check_overrides(overrides, list(hints), td.__name__)
    required = getattr(td, "__required_keys__", frozenset(hints))
    plans: list[FieldPlan] = []
    for name, tp in hints.items():
        fp = _field_plan(
            name,
            name,
            tp,
            has_default=name not in required,
            override=overrides.get(name),
            null_probability=null_probability,
            stack=(*stack, td),
        )
        if fp is not None:
            plans.append(fp)
    return CompiledSchema("typeddict", td, plans)


_TYPE_NAMES: dict[str, Any] = {
    "str": str, "string": str,
    "int": int, "integer": int,
    "float": float, "number": float,
    "bool": bool, "boolean": bool,
    "date": _dt.date, "datetime": _dt.datetime, "timestamp": _dt.datetime,
    "uuid": uuid.UUID, "decimal": decimal.Decimal, "any": Any,
}  # fmt: skip


def _compile_mapping(
    schema: Mapping[str, Any], overrides: dict[str, Spec], null_probability: float
) -> CompiledSchema:
    if not schema:
        raise SchemaError("schema dict is empty")
    _check_overrides(overrides, [str(k) for k in schema], "the schema dict")
    plans: list[FieldPlan] = []
    for raw_name, value in schema.items():
        name = str(raw_name)
        override = overrides.get(name)
        nullable = False
        if isinstance(value, str) and value.endswith("?"):
            value, nullable = value[:-1], True
        null_p = null_probability if nullable else 0.0
        if override is not None:
            plans.append(FieldPlan(name, name, override, override.null_probability or null_p))
            continue
        if isinstance(value, Spec):
            p = value.null_probability if value.null_probability is not None else null_p
            plans.append(FieldPlan(name, name, value, p))
        elif isinstance(value, Mapping):
            nested = _compile_mapping(value, {}, null_probability)
            plans.append(FieldPlan(name, name, None, null_p, nested=nested))
        elif isinstance(value, str) and value.lower() in _TYPE_NAMES:
            fp = _field_plan(
                name, name, _TYPE_NAMES[value.lower()], has_default=False, override=None,
                null_probability=null_probability, stack=(),
            )  # fmt: skip
            assert fp is not None
            fp.converter, fp.always_convert = None, False  # raw schemas keep raw values
            fp.null_probability = null_p
            plans.append(fp)
        elif isinstance(value, str):
            plans.append(FieldPlan(name, name, Provider(value), null_p))
        else:
            fp = _field_plan(
                name, name, value, has_default=False, override=None,
                null_probability=null_probability, stack=(),
            )  # fmt: skip
            assert fp is not None
            if nullable:
                fp.null_probability = null_p
            plans.append(fp)
    return CompiledSchema("mapping", None, plans)


def _compile_class(
    schema: Any,
    *,
    overrides: Mapping[str, Spec | str] | None,
    null_probability: float,
    stack: tuple[Any, ...] = (),
) -> CompiledSchema:
    ov = _normalize_overrides(overrides)
    if _is_pydantic_model(schema):
        return _compile_pydantic(schema, ov, null_probability, stack)
    if isinstance(schema, type) and dataclasses.is_dataclass(schema):
        return _compile_dataclass(schema, ov, null_probability, stack)
    if _is_typeddict(schema):
        return _compile_typeddict(schema, ov, null_probability, stack)
    raise SchemaError(
        f"unsupported schema {schema!r}: expected a Pydantic v2 model, dataclass, TypedDict "
        "or a dict mapping field names to providers / types"
    )


@functools.lru_cache(maxsize=512)
def _compile_cached(
    schema: Any, null_probability: float, reference_date: _dt.date | None, today: _dt.date
) -> CompiledSchema:
    # ``today`` is part of the cache key: future-date ranges move with the calendar.
    with _reference_date(reference_date):
        return _compile_class(schema, overrides=None, null_probability=null_probability)


def compile_schema(
    schema: Any,
    *,
    overrides: Mapping[str, Spec | str] | None = None,
    null_probability: float = 0.1,
    reference_date: _dt.date | None = None,
) -> CompiledSchema:
    """Compile a Pydantic model, dataclass, TypedDict or ``dict`` schema.

    Args:
        schema: The schema to introspect.
        overrides: Per-field provider overrides (``Spec`` objects or provider names).
        null_probability: Probability of ``None`` for ``Optional[...]`` fields.
        reference_date: "Today" for Pydantic ``PastDate`` / ``FutureDate`` /
            ``PastDatetime`` / ``FutureDatetime`` fields. ``None`` keeps past types on fixed
            ranges (reproducible forever) and anchors future types to the real today.
    """
    if not 0.0 <= null_probability <= 1.0:
        raise SchemaError(f"null_probability must be within [0, 1], got {null_probability!r}")
    if isinstance(reference_date, _dt.datetime):
        reference_date = reference_date.date()
    with _reference_date(reference_date):
        if isinstance(schema, Mapping):
            return _compile_mapping(schema, _normalize_overrides(overrides), null_probability)
        if not overrides:
            try:
                return _compile_cached(
                    schema, float(null_probability), reference_date, _dt.date.today()
                )
            except TypeError:  # unhashable schema object
                pass
        return _compile_class(schema, overrides=overrides, null_probability=null_probability)
