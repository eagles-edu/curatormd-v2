"""Shared owner-only regular-file checks for local evidence receipts."""

from __future__ import annotations

import os
import stat


def require_private_regular_file(
    metadata: os.stat_result,
    *,
    maximum_bytes: int,
    description: str,
) -> None:
    """Reject files not privately owned by the effective Curator account."""

    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
        or metadata.st_nlink != 1
        or metadata.st_size > maximum_bytes
    ):
        raise ValueError(f"{description} ownership, mode, or size is invalid")
