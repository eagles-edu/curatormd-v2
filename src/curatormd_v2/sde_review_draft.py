"""Bounded owner-edited SDE review text for a bound decision receipt.

This value object does not approve, persist, or project a candidate. A caller
must validate every destination against the active project configuration and
bind the resulting digest to the authenticated review action.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields as dataclass_fields
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import TYPE_CHECKING, cast

from .content_safety import validate_safe_text
from .record_validation import REVIEWER_ID_RE
from .validation import is_exact_int

if TYPE_CHECKING:
    from .project_config import ProjectConfig

MAX_REVIEW_DOCUMENTS = 16
MAX_REVIEW_BULLETS = 32
MAX_REVIEW_TEXT = 4_000
MAX_REVIEW_TOTAL_BYTES = 64 * 1024
MAX_REVIEW_TARGET_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SDEReviewDraft:
    """Owner-editable proposal fields before review and authorization."""

    title: str
    significance: int
    documents: tuple[str, ...]
    problem: str
    completed: tuple[str, ...]
    difficulties: tuple[str, ...] = ()
    plan_changes: tuple[str, ...] = ()
    lessons: tuple[str, ...] = ()
    future_utility: str = ""

    @classmethod
    def from_json(cls, raw: str) -> SDEReviewDraft:
        """Parse a bounded decision block, rejecting ambiguous or unknown fields."""

        if type(raw) is not str or len(raw.encode("utf-8")) > MAX_REVIEW_TOTAL_BYTES:
            raise ValueError("SDE review draft is missing or too large")

        def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("SDE review draft contains duplicate keys")
                result[key] = value
            return result

        try:
            value: object = json.loads(raw, object_pairs_hook=unique_object)
        except (json.JSONDecodeError, RecursionError) as error:
            raise ValueError("SDE review draft is not valid JSON") from error
        required = {
            "title", "significance", "documents", "problem", "completed",
            "difficulties", "plan_changes", "lessons", "future_utility",
        }
        if not isinstance(value, dict):
            raise ValueError("SDE review draft has missing or unknown fields")
        fields = cast(dict[str, object], value)
        if set(fields) != required:
            raise ValueError("SDE review draft has missing or unknown fields")

        def text(name: str) -> str:
            result = fields[name]
            if not isinstance(result, str):
                raise ValueError(f"SDE {name} must be text")
            return result

        def texts(name: str) -> tuple[str, ...]:
            result = fields[name]
            if not isinstance(result, list):
                raise ValueError(f"SDE {name} must be a list of text")
            items = cast(list[object], result)
            if any(type(item) is not str for item in items):
                raise ValueError(f"SDE {name} must be a list of text")
            return tuple(cast(str, item) for item in items)

        significance = fields["significance"]
        if not is_exact_int(significance):
            raise ValueError("SDE significance must be an integer")
        return cls(
            title=text("title"), significance=significance, documents=texts("documents"),
            problem=text("problem"), completed=texts("completed"),
            difficulties=texts("difficulties"), plan_changes=texts("plan_changes"),
            lessons=texts("lessons"), future_utility=text("future_utility"),
        )

    def __post_init__(self) -> None:
        if not is_exact_int(self.significance) or not 0 <= self.significance <= 5:
            raise ValueError("SDE significance must be an integer from 0 to 5")
        for field_name, value, required in (
            ("title", self.title, True),
            ("problem", self.problem, True),
            ("future_utility", self.future_utility, False),
        ):
            self._validate_text(field_name, value, required=required)
        if len(self.documents) > MAX_REVIEW_DOCUMENTS:
            raise ValueError("SDE review requires a bounded tuple of documents")
        for document in self.documents:
            self._validate_text("document", document, required=True)
            target = PurePosixPath(document)
            if (
                len(document) > 512
                or document in {".", ".."}
                or "\\" in document
                or target.is_absolute()
                or str(target) != document
                or any(part in {".", ".."} for part in target.parts)
            ):
                raise ValueError("SDE document must be a normalized relative path")
        if len(set(self.documents)) != len(self.documents):
            raise ValueError("SDE document destinations must be unique")
        for field_name, values in (
            ("completed", self.completed),
            ("difficulties", self.difficulties),
            ("plan_changes", self.plan_changes),
            ("lessons", self.lessons),
        ):
            if len(values) > MAX_REVIEW_BULLETS:
                raise ValueError(f"SDE {field_name} must be a bounded tuple")
            for value in values:
                self._validate_text(field_name, value, required=True)
        if len(self.canonical_bytes()) > MAX_REVIEW_TOTAL_BYTES:
            raise ValueError("SDE review draft exceeds its total size limit")

    @staticmethod
    def _validate_text(name: str, value: str, *, required: bool) -> None:
        if type(value) is not str or len(value) > MAX_REVIEW_TEXT:
            raise ValueError(f"SDE {name} must be bounded text")
        if required and not value.strip():
            raise ValueError(f"SDE {name} must not be empty")
        if "\n" in value or "\r" in value:
            raise ValueError(f"SDE {name} must be a single line")
        validate_safe_text(value, f"sde_review_draft.{name}")

    def canonical_bytes(self) -> bytes:
        """Return a stable representation for binding to the review receipt."""

        return json.dumps(
            asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def sha256(self) -> str:
        """Return the digest of the exact bounded draft."""

        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def validated_targets(self, config: ProjectConfig) -> tuple[Path, ...]:
        """Revalidate every selected path against the current project allowlist."""

        targets = tuple(config.validated_persistence_target(path) for path in self.documents)
        if len(set(targets)) != len(targets):
            raise ValueError("SDE destinations must resolve to distinct targets")
        return targets

    def projection_state_sha256(self, config: ProjectConfig) -> str:
        """Fingerprint the exact allowlisted target states without changing them.

        The result must be rechecked at the actual effect fence; this read alone
        does not reserve any target or authorize a write.
        """

        if not hasattr(os, "O_NOFOLLOW"):
            raise ValueError("safe projection reads are unavailable")
        states: list[dict[str, object]] = []
        for relative, target in zip(self.documents, self.validated_targets(config), strict=True):
            try:
                descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
            except FileNotFoundError:
                states.append({"path": relative, "exists": False})
                continue
            try:
                before = os.fstat(descriptor)
                if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_REVIEW_TARGET_BYTES:
                    raise ValueError("SDE projection target is invalid or too large")
                digest = hashlib.sha256()
                total = 0
                while chunk := os.read(descriptor, 64 * 1024):
                    total += len(chunk)
                    if total > MAX_REVIEW_TARGET_BYTES:
                        raise ValueError("SDE projection target exceeds its size limit")
                    digest.update(chunk)
                after = os.fstat(descriptor)
                current = os.stat(target, follow_symlinks=False)
                if (
                    (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                    or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino)
                    or not stat.S_ISREG(current.st_mode)
                    or total != after.st_size
                ):
                    raise ValueError("SDE projection target changed during review")
                states.append({"path": relative, "exists": True, "sha256": digest.hexdigest()})
            finally:
                os.close(descriptor)
        encoded = json.dumps(states, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SDEReviewBinding:
    """Inputs that must remain unchanged through an attended draft decision.

    This value does not confer authority or itself record a decision.
    """

    project_id: str
    candidate_id: str
    decision: str
    reviewer_id: str
    review_rationale: str
    project_config_sha256: str
    supporting_facts_sha256: str
    evidence_state_sha256: str
    projection_state_sha256: str
    inventory_sha256: str
    dependency_map_sha256: str
    draft_sha256: str
    evidence_override_reason: str = ""

    @classmethod
    def from_json(cls, raw: str) -> SDEReviewBinding:
        """Read the exact bounded binding stored with a review receipt."""

        if type(raw) is not str or len(raw.encode("utf-8")) > 8192:
            raise ValueError("SDE binding is missing or too large")
        def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("SDE binding contains duplicate keys")
                result[key] = value
            return result
        try:
            value: object = json.loads(raw, object_pairs_hook=unique_object)
        except (json.JSONDecodeError, RecursionError) as error:
            raise ValueError("SDE binding is not valid JSON") from error
        names = tuple(field.name for field in dataclass_fields(cls))
        if not isinstance(value, dict):
            raise ValueError("SDE binding has missing or unknown fields")
        fields = cast(dict[str, object], value)
        if set(fields) not in (set(names), set(names) - {"evidence_override_reason"}):
            raise ValueError("SDE binding has missing or unknown fields")
        fields.setdefault("evidence_override_reason", "")
        if not all(isinstance(fields[name], str) for name in names):
            raise ValueError("SDE binding fields must be text")
        def text(name: str) -> str:
            item = fields[name]
            if not isinstance(item, str):
                raise ValueError("SDE binding fields must be text")
            return item
        return cls(
            project_id=text("project_id"), candidate_id=text("candidate_id"),
            decision=text("decision"), reviewer_id=text("reviewer_id"),
            review_rationale=text("review_rationale"),
            project_config_sha256=text("project_config_sha256"),
            supporting_facts_sha256=text("supporting_facts_sha256"),
            evidence_state_sha256=text("evidence_state_sha256"),
            projection_state_sha256=text("projection_state_sha256"),
            inventory_sha256=text("inventory_sha256"),
            dependency_map_sha256=text("dependency_map_sha256"),
            draft_sha256=text("draft_sha256"),
            evidence_override_reason=text("evidence_override_reason"),
        )

    def __post_init__(self) -> None:
        if type(self.project_id) is not str or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", self.project_id
        ):
            raise ValueError("SDE binding requires a bounded project ID")
        if type(self.candidate_id) is not str or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", self.candidate_id
        ):
            raise ValueError("SDE binding requires a bounded candidate ID")
        if self.decision not in {"approved", "rejected"}:
            raise ValueError("SDE binding requires an explicit decision")
        if type(self.reviewer_id) is not str or not REVIEWER_ID_RE.fullmatch(self.reviewer_id):
            raise ValueError("SDE binding requires a bounded reviewer ID")
        validate_safe_text(self.review_rationale, "sde_review_binding.review_rationale")
        if self.evidence_override_reason:
            validate_safe_text(self.evidence_override_reason, "sde_review_binding.evidence_override_reason")
            if not self.evidence_override_reason.strip() or len(self.evidence_override_reason) > 1000 or "\n" in self.evidence_override_reason or "\r" in self.evidence_override_reason:
                raise ValueError("SDE override reason must be bounded single-line text")
        if not self.review_rationale.strip() or "\n" in self.review_rationale or "\r" in self.review_rationale:
            raise ValueError("SDE review rationale must be non-empty single-line text")
        if len(self.review_rationale) > 1000:
            raise ValueError("SDE binding rationale must not exceed 1000 characters")
        for name, value in (
            ("project config", self.project_config_sha256),
            ("supporting facts", self.supporting_facts_sha256),
            ("evidence state", self.evidence_state_sha256),
            ("projection state", self.projection_state_sha256),
            ("inventory", self.inventory_sha256),
            ("dependency map", self.dependency_map_sha256),
            ("draft", self.draft_sha256),
        ):
            if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(f"SDE binding {name} digest must be SHA-256")

    def sha256(self) -> str:
        """Identify the exact project, decision, packet, and edited entry."""

        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def canonical_bytes(self) -> bytes:
        """Return deterministic bytes suitable for receipt storage."""

        value = asdict(self)
        if not self.evidence_override_reason:
            del value["evidence_override_reason"]
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
