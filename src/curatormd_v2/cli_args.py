"""Shared bounded argument parsers for Curator V2 command-line tools."""

from __future__ import annotations

import argparse


def positive_integer_limit(value: str, maximum: int) -> int:
    """Parse a positive integer ceiling without retaining rejected input."""

    parse_failed = False
    parsed = 0
    try:
        parsed = int(value)
    except ValueError:
        parse_failed = True
    if parse_failed or not 1 <= parsed <= maximum:
        raise argparse.ArgumentTypeError(
            f"limit must be an integer from 1 to {maximum}"
        )
    return parsed
