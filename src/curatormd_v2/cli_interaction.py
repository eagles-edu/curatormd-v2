"""Shared attended terminal interactions for local Curator V2 commands."""

from __future__ import annotations

import argparse
from typing import NoReturn
from typing import TextIO


class SafeArgumentParser(argparse.ArgumentParser):
    """Reject malformed CLI input without echoing its untrusted value."""

    def error(self, message: str) -> NoReturn:
        del message
        raise ValueError("invalid command arguments")


def parse_safe_arguments(
    parser: argparse.ArgumentParser,
    argv: list[str] | None,
    errors: TextIO,
    failure_message: str,
) -> argparse.Namespace | None:
    """Parse argv and emit only the caller-selected fixed failure message."""

    try:
        return parser.parse_args(argv)
    except ValueError:
        errors.write(failure_message)
        return None


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
