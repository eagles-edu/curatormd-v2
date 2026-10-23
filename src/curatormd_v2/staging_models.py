"""Content-free measurements for one bounded project staging scan."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re

from .validation import is_exact_bool, is_exact_int
from .record_validation import parse_aware_timestamp


MAX_STAGING_SCAN_ENTRIES = 10_000
_STAGING_ERROR_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class StagingArtifactClass(StrEnum):
    """Bounded temporary artifact classes used for staging attribution."""

    RAW_CHAT = "raw-chat"
    CUE = "cue"
    IMPORT = "import"
    SCRATCH = "scratch"
    GENERATED = "generated"
    DUPLICATE = "duplicate"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class StagingClassUsage:
    """Content-free staging totals for one fixed temporary artifact class."""

    artifact_class: StagingArtifactClass
    regular_file_count: int
    observed_file_bytes: int

    def __post_init__(self) -> None:
        """Reject negative or non-integer observed totals."""

        if type(self.artifact_class) is not StagingArtifactClass:  # pylint: disable=unidiomatic-typecheck
            raise ValueError("artifact_class must be a StagingArtifactClass")
        if not is_exact_int(self.regular_file_count) or self.regular_file_count < 0:
            raise ValueError("staging class file count must be a non-negative integer")
        if not is_exact_int(self.observed_file_bytes) or self.observed_file_bytes < 0:
            raise ValueError("staging class byte count must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class StagingUsage:
    """Content-free, bounded scan results for one configured staging tree."""

    entries_scanned: int
    regular_file_count: int
    observed_file_bytes: int
    directory_count: int
    symlink_count: int
    special_file_count: int
    inventory_complete: bool
    error_code: str | None = None
    classes: tuple[StagingClassUsage, ...] = ()
    observed_at: str | None = None

    def __post_init__(self) -> None:
        """Keep per-class observations consistent with scan totals."""

        _validate_staging_counts(self)
        _validate_staging_classes(self)


def _validate_staging_counts(usage: StagingUsage) -> None:
    """Validate bounded aggregate counts and completeness metadata."""

    counts = (
        ("entries_scanned", usage.entries_scanned),
        ("regular_file_count", usage.regular_file_count),
        ("observed_file_bytes", usage.observed_file_bytes),
        ("directory_count", usage.directory_count),
        ("symlink_count", usage.symlink_count),
        ("special_file_count", usage.special_file_count),
    )
    for name, value in counts:
        if not is_exact_int(value) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if usage.entries_scanned > MAX_STAGING_SCAN_ENTRIES:
        raise ValueError(
            f"entries_scanned exceeds the limit of {MAX_STAGING_SCAN_ENTRIES}"
        )
    if not is_exact_bool(usage.inventory_complete):
        raise ValueError("inventory_complete must be a boolean")
    if usage.error_code is not None and (
        type(usage.error_code) is not str  # pylint: disable=unidiomatic-typecheck
        or _STAGING_ERROR_CODE_RE.fullmatch(usage.error_code) is None
    ):
        raise ValueError("error_code must be a bounded lowercase category")
    if usage.inventory_complete and usage.error_code is not None:
        raise ValueError("complete staging inventory must not have an error_code")
    if not usage.inventory_complete and usage.error_code is None:
        raise ValueError("incomplete staging inventory must include an error_code")
    if usage.observed_at is not None:
        parse_aware_timestamp("staging observed_at", usage.observed_at)


def _validate_staging_classes(usage: StagingUsage) -> None:
    """Validate the bounded class breakdown and its aggregate totals."""

    if type(usage.classes) is not tuple:  # pylint: disable=unidiomatic-typecheck
        raise ValueError("staging classes must be a tuple")
    if len(usage.classes) > len(StagingArtifactClass):
        raise ValueError("staging usage has too many artifact classes")
    if any(
        type(item) is not StagingClassUsage  # pylint: disable=unidiomatic-typecheck
        for item in usage.classes
    ):
        raise ValueError("staging classes must contain StagingClassUsage records")
    if len({item.artifact_class for item in usage.classes}) != len(usage.classes):
        raise ValueError("staging usage must not repeat an artifact class")
    classified_entries = (
        usage.regular_file_count
        + usage.directory_count
        + usage.symlink_count
        + usage.special_file_count
    )
    if classified_entries > usage.entries_scanned:
        raise ValueError("classified staging entries exceed the scan total")
    if sum(item.regular_file_count for item in usage.classes) != usage.regular_file_count:
        raise ValueError("staging class file counts must match scan totals")
    if sum(item.observed_file_bytes for item in usage.classes) != usage.observed_file_bytes:
        raise ValueError("staging class byte totals must match scan totals")
