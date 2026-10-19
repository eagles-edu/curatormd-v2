"""Small shared validators for external Python values."""

from __future__ import annotations

from typing import TypeGuard


def is_exact_int(value: object) -> TypeGuard[int]:
    """Accept built-in integers only, excluding booleans and integer subclasses."""

    return type(value) is int  # pylint: disable=unidiomatic-typecheck


def is_exact_bool(value: object) -> TypeGuard[bool]:
    """Accept only built-in bool values at untrusted runtime boundaries."""

    return type(value) is bool  # pylint: disable=unidiomatic-typecheck


def is_exact_number(value: object) -> TypeGuard[int | float]:
    """Accept built-in integers/floats only, excluding booleans and subclasses."""

    return type(value) in (int, float)  # pylint: disable=unidiomatic-typecheck
