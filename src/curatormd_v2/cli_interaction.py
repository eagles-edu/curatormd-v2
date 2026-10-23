"""Shared attended terminal interactions for local Curator V2 commands."""

from __future__ import annotations

from typing import TextIO


def confirm_exact_phrase(
    phrase: str,
    input_stream: TextIO,
    errors: TextIO,
    refusal_message: str,
) -> bool:
    """Require a TTY and exact bounded phrase before an attended operation."""

    if not input_stream.isatty():
        errors.write(refusal_message)
        return False
    errors.write(f"Type exactly: {phrase}\n> ")
    errors.flush()
    try:
        return input_stream.readline(512).rstrip("\r\n") == phrase
    except (OSError, ValueError):
        return False
