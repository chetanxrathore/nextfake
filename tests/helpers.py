"""Shared test helpers."""

from __future__ import annotations


def luhn_valid(number: str) -> bool:
    """Reference (pure-Python) Luhn checksum."""
    checksum = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0
