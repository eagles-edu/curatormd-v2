"""Shared output formatting for Curator V2 command-line adapters."""

from __future__ import annotations

import json
from typing import TextIO


def write_json_line(output: TextIO, value: object) -> None:
    """Write one compact, key-sorted JSON value followed by a newline."""

    output.write(json.dumps(value, separators=(",", ":"), sort_keys=True))
    output.write("\n")
