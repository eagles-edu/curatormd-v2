"""Reject recognizable secrets and personal data before durable writes.

This is a conservative high-confidence pattern gate, not a general-purpose DLP
system. It never redacts: callers must remove or safely reference sensitive
material and retry, preserving the meaning of evidence explicitly.
"""

from __future__ import annotations

import re


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("credential_url", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@", re.IGNORECASE)),
    ("credential_assignment", re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|passwd|pwd|secret)"
        r"\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    )),
    ("dns_challenge", re.compile(
        r"\b(?:TXT(?:\s+(?:record|value))?|DNS\s+(?:challenge|TXT)"
        r"(?:\s+(?:value|code|token))?)\s*[:=]\s*[\"']?[A-Za-z0-9_-]{32,}\b",
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


class SensitiveContentError(ValueError):
    """A field contains a recognized secret or personal-data pattern."""

    def __init__(self, field_name: str, category: str) -> None:
        self.field_name = field_name
        self.category = category
        # Never echo the rejected value: it may itself be a credential or PII.
        super().__init__(f"sensitive content rejected in {field_name}: {category}")


def validate_safe_text(value: str, field_name: str) -> None:
    """Reject recognized sensitive patterns without altering source text."""

    for category, pattern in _PATTERNS:
        if pattern.search(value):
            raise SensitiveContentError(field_name, category)
