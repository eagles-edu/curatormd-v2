"""Reject recognizable secrets and personal data before durable writes.

This is a conservative high-confidence pattern gate, not a general-purpose DLP
system. It never redacts: callers must remove or safely reference sensitive
material and retry, preserving the meaning of evidence explicitly.
"""

from __future__ import annotations

import re
from typing import BinaryIO


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("credential_url", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@", re.IGNORECASE)),
    ("credential_assignment", re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|passwd|pwd|secret)"
        r"\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    )),
    ("credential_prose", re.compile(
        r"\b(?:password|passwd|pwd|api[_-]?key|access[_-]?token|refresh[_-]?token)"
        r"\s+is\s+(?!not\b|required\b|unknown\b|unset\b|redacted\b|managed\b)"
        r"[^\s,;]{6,}",
        re.IGNORECASE,
    )),
    ("dns_challenge", re.compile(
        r"\b(?:TXT(?:\s+(?:record|value))?|DNS\s+(?:challenge|TXT)"
        r"(?:\s+(?:value|code|token))?)\s*[:=]\s*[\"']?[A-Za-z0-9_-]{32,}\b",
        re.IGNORECASE,
    )),
    ("dns_challenge", re.compile(
        r"\b(?:manual\s+)?DNS\s+(?:TXT\s+)?(?:code|challenge|value)"
        r"\s*(?::|=|\bis\b)\s*[\"']?[A-Za-z0-9_-]{12,}\b",
        re.IGNORECASE,
    )),
    ("dns_challenge", re.compile(
        r"\b(?:manual[-_ ]dns|dns)[-_ ](?:txt|challenge|code|token|value)"
        r"[-_]+[A-Za-z0-9_-]{12,}\b",
        re.IGNORECASE,
    )),
    ("email_address", re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]+(?:\.[\w-]+)+")),
    ("us_ssn", re.compile(r"(?<!\d)(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?!\d)")),
    ("provider_token", re.compile(
        r"\b(?:(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}|"
        r"sk-[A-Za-z0-9_-]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"ghs_[A-Za-z0-9_.-]{20,}|gh[pour]_[A-Za-z0-9]{20,}|"
        r"AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{16,}|AIza[A-Za-z0-9_-]{30,}|"
        r"glpat-[A-Za-z0-9_-]{20})\b"
    )),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("labeled_phone", re.compile(
        r"\b(?:phone|mobile|cell|telephone)\s*[:=]\s*\+?[0-9][0-9(). -]{7,}[0-9]",
        re.IGNORECASE,
    )),
)
_PERSONAL_DATA_CATEGORIES = frozenset({"email_address", "us_ssn", "labeled_phone"})


class SensitiveContentError(ValueError):
    """A field contains a recognized secret or personal-data pattern."""

    def __init__(self, field_name: str, category: str) -> None:
        self.field_name = field_name
        self.category = category
        # Never echo the rejected value: it may itself be a credential or PII.
        super().__init__(f"sensitive content rejected in {field_name}: {category}")


class SensitiveContentCheckingReader:
    """Check a binary input stream in bounded overlapping chunks before writes."""

    _OVERLAP_BYTES = 512

    def __init__(self, source: BinaryIO, field_name: str) -> None:
        self._source = source
        self._field_name = field_name
        self._tail = b""

    def read(self, size: int = -1) -> bytes:
        """Read and check one chunk while retaining enough tail for split labels."""
        chunk = self._source.read(size)
        window = self._tail + chunk
        validate_safe_text(
            window.decode("utf-8", errors="ignore"),
            self._field_name,
            include_personal_data=False,
        )
        self._tail = window[-self._OVERLAP_BYTES:]
        return chunk


def validate_safe_text(
    value: str, field_name: str, *, include_personal_data: bool = True
) -> None:
    """Reject recognized sensitive patterns without altering source text."""

    for category, pattern in _PATTERNS:
        if not include_personal_data and category in _PERSONAL_DATA_CATEGORIES:
            continue
        if pattern.search(value):
            raise SensitiveContentError(field_name, category)
