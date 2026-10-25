"""Shared bounded subprocess output handling for local evidence sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping
import hashlib
import os
import selectors
import subprocess  # nosec B404
import time

from .process_control import kill_process_group

EvidenceProcessLabel = Literal["configured service probe", "configured browser proof"]
EmptyEvidenceMessage = Literal[
    "configured service probe returned no evidence",
    "configured browser proof returned no rendered DOM",
]


@dataclass(frozen=True, slots=True)
class BoundedEvidenceProcessRequest:
    """Host-selected command and strict output/time bounds for one evidence run."""

    command: tuple[str, ...]
    working_directory: Path
    environment: Mapping[str, str]
    timeout_seconds: int
    max_output_bytes: int
    label: EvidenceProcessLabel
    empty_output_message: EmptyEvidenceMessage


def hash_bounded_stdout(request: BoundedEvidenceProcessRequest) -> str:
    """Stream stdout into SHA-256 and fail closed on process or limit errors."""

    try:
        process = subprocess.Popen(  # nosec B603  # pylint: disable=consider-using-with
            request.command,
            cwd=request.working_directory,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=dict(request.environment),
            start_new_session=True,
        )
    except OSError:
        raise RuntimeError(f"{request.label} could not start") from None
    if process.stdout is None:
        kill_process_group(process)
        process.wait()
        raise RuntimeError(f"{request.label} output is unavailable")

    selector = selectors.DefaultSelector()
    digest = hashlib.sha256()
    total_bytes = 0
    deadline = time.monotonic() + request.timeout_seconds
    try:
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"{request.label} timed out")
            for key, _ in selector.select(min(remaining, 0.1)):
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                total_bytes += len(chunk)
                if total_bytes > request.max_output_bytes:
                    raise RuntimeError(f"{request.label} output exceeded its limit")
                digest.update(chunk)
        try:
            return_code = process.wait(
                timeout=max(0.1, deadline - time.monotonic())
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{request.label} timed out") from None
        if return_code != 0:
            raise RuntimeError(f"{request.label} returned failure")
        if total_bytes == 0:
            raise RuntimeError(request.empty_output_message)
        return digest.hexdigest()
    except Exception:
        kill_process_group(process)
        process.wait()
        raise
    finally:
        selector.close()
        process.stdout.close()
