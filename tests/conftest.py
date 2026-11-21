from __future__ import annotations

import pytest

import nextfake


@pytest.fixture
def gen() -> nextfake.Faker:
    return nextfake.Faker(seed=1234)
