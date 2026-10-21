"""Atomic, idempotent Markdown projection for one configured project target."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
from html import escape
import os
from pathlib import Path
import re
import stat
import tempfile

from .evidence import (
    EvidenceVerifier,
    RejectUnverifiedEvidence,
    evidence_has_current_attestations,
)
from .models import (
    AuditReceipt,
    CriterionProgress,
    CriterionStatus,
    EvidenceOutcome,
    Fact,
    FactKind,
    GoalCard,
    SDECandidate,
    SDECorrection,
    SDEStatus,
)
from .project_config import ProjectConfig
from .store import CuratorStore, NotFoundError
from .validation import is_exact_int


MAX_MARKDOWN_BYTES = 8 * 1024 * 1024
MAX_PROJECT_RECONCILIATION_PAGE = 100
MAX_PROJECT_RECONCILIATION_MARKERS = 5000
_GOAL_MARKER_PATTERN = re.compile(
    r"^<!-- curatormd-v2:goal:([0-9a-f]{64}):(start|end) -->$"
)
_BLOCK_INTEGRITY_PATTERN = re.compile(
    r"^<!-- curatormd-v2:block-sha256:([0-9a-f]{64}) -->$"
)
_GOAL_HEADING_PATTERN = re.compile(r"^### Goal `([^`\r\n]+)`$")
_GOAL_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


class MarkdownPersistenceError(RuntimeError):
    """A canonical Markdown projection could not be safely applied."""


class MarkdownReconciliationStatus(StrEnum):
    """Read-only comparison result for one structured goal projection."""

    SYNCED = "synced"
    MISSING = "missing"
    DIVERGENT = "divergent"
    MALFORMED = "malformed"


@dataclass(frozen=True, slots=True)
class MarkdownProjectionResult:
    """Receipt for one deterministic goal block projection."""

    target: Path
    project_id: str
    goal_id: str
    sha256: str
    changed: bool
    size_bytes: int


@dataclass(frozen=True, slots=True)
class MarkdownReconciliationResult:
    """Bounded hashes and status; reconciliation never changes either store."""

    target: Path
    project_id: str
    goal_id: str
    status: MarkdownReconciliationStatus
    expected_sha256: str
    actual_sha256: str | None


@dataclass(frozen=True, slots=True)
class MarkdownProjectReconciliation:
    """Bounded read-only comparison of one Markdown target and a project page."""

    project_id: str
    target: Path
    total_goals: int
    offset: int
    limit: int
    next_offset: int | None
    goals: tuple[MarkdownReconciliationResult, ...]
    orphan_marker_sha256: tuple[str, ...]
    malformed_marker_sha256: tuple[str, ...]
    malformed_marker_count: int
    unrecognized_marker_count: int
    inventory_complete: bool
    scanned_bytes: int


class MarkdownPersistenceAdapter:
    """Upsert one compact per-goal block without rewriting unrelated content.

    A SQLite write transaction serializes project writers across store
    connections. The target replacement is atomic and repeatable, so a process
    crash after replacement but before transaction commit can safely rerun.
    """

    def __init__(
        self,
        config: ProjectConfig,
        store: CuratorStore,
        target: str | Path,
        evidence_verifier: EvidenceVerifier | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.project_id = config.project_id
        self.target = config.validated_persistence_target(target)
        self.evidence_verifier = evidence_verifier or RejectUnverifiedEvidence()

    def persist_goal(self, goal_id: str) -> MarkdownProjectionResult:
        """Render current facts/receipts and atomically upsert the goal block."""

        target = self.config.validated_persistence_target(self.target)
        initial_goal = self.store.get_goal(goal_id, self.project_id)
        initial_facts = self.store.list_facts(goal_id, self.project_id)
        progress = self._criterion_progress(initial_goal, initial_facts)
        with self.store.transaction():
            current_goal = self.store.get_goal(goal_id, self.project_id)
            current_facts = self.store.list_facts(goal_id, self.project_id)
            if (
                current_goal.criteria_revision != initial_goal.criteria_revision
                or current_goal.lifecycle_revision != initial_goal.lifecycle_revision
                or tuple(fact.fact_id for fact in current_facts)
                != tuple(fact.fact_id for fact in initial_facts)
            ):
                raise MarkdownPersistenceError(
                    "goal changed during evidence verification; retry projection"
                )
            block = self._render_goal(goal_id, progress=progress)
            start_marker, end_marker = _goal_markers(goal_id)
            current, mode = self._read_target(target)
            updated = _upsert_block(current, block, start_marker, end_marker)
            encoded = updated.encode("utf-8")
            if len(encoded) > MAX_MARKDOWN_BYTES:
                raise MarkdownPersistenceError(
                    f"canonical Markdown target exceeds {MAX_MARKDOWN_BYTES} bytes"
                )
            digest = hashlib.sha256(encoded).hexdigest()
            changed = updated != current
            if changed:
                self._atomic_replace(target, encoded, mode)
        return MarkdownProjectionResult(
            target=target,
            project_id=self.project_id,
            goal_id=goal_id,
            sha256=digest,
            changed=changed,
            size_bytes=len(encoded),
        )

    def render_goal(self, goal_id: str) -> str:
        """Preview the bounded Markdown block without modifying its target."""

        return self._render_goal(goal_id)

    def reconcile_goal(self, goal_id: str) -> MarkdownReconciliationResult:
        """Compare one Markdown block with SQLite without repairing either side.

        This detects a missing or interrupted/stale projection, but deliberately
        does not choose an authoritative store or overwrite conflicting data.
        A caller must handle ``DIVERGENT`` or ``MALFORMED`` through an explicit
        recovery policy.
        """

        target = self.config.validated_persistence_target(self.target)
        goal = self.store.get_goal(goal_id, self.project_id)
        content, _mode = self._read_target(target)
        return self._reconcile_goal_from_content(goal, target, content)

    def reconcile_project(
        self, *, offset: int = 0, limit: int = 50
    ) -> MarkdownProjectReconciliation:
        """Compare a bounded goal page and scan for orphaned managed blocks.

        The operation is informational only. It never repairs the Markdown or
        SQLite side, and an over-limit marker inventory is explicitly incomplete.
        """

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if (
            not is_exact_int(limit)
            or not 1 <= limit <= MAX_PROJECT_RECONCILIATION_PAGE
        ):
            raise ValueError(
                f"limit must be between 1 and {MAX_PROJECT_RECONCILIATION_PAGE}"
            )
        target = self.config.validated_persistence_target(self.target)
        total_goals, goal_page = self.store.list_goal_page(
            self.project_id, offset, limit
        )
        content = self._read_target(target)[0]
        goals = tuple(
            self._reconcile_goal_from_content(goal, target, content)
            for goal in goal_page
        )
        (
            orphan_markers,
            malformed_markers,
            malformed_count,
            unrecognized_count,
            inventory_complete,
        ) = self._scan_project_markers(content)
        next_offset = (
            offset + len(goal_page)
            if offset + len(goal_page) < total_goals
            else None
        )
        return MarkdownProjectReconciliation(
            project_id=self.project_id,
            target=target,
            total_goals=total_goals,
            offset=offset,
            limit=limit,
            next_offset=next_offset,
            goals=goals,
            orphan_marker_sha256=orphan_markers,
            malformed_marker_sha256=malformed_markers,
            malformed_marker_count=malformed_count,
            unrecognized_marker_count=unrecognized_count,
            inventory_complete=inventory_complete,
            scanned_bytes=len(content.encode("utf-8")),
        )

    def _reconcile_goal_from_content(
        self, goal: GoalCard, target: Path, content: str
    ) -> MarkdownReconciliationResult:
        """Compare one already loaded goal against a shared target snapshot."""

        expected_block = self._render_goal(goal.goal_id)
        expected_digest = hashlib.sha256(
            (expected_block + "\n").encode("utf-8")
        ).hexdigest()
        actual_block, status = _read_goal_block(
            content, *_goal_markers(goal.goal_id), expected_block
        )
        actual_digest = (
            hashlib.sha256(actual_block.encode("utf-8")).hexdigest()
            if actual_block is not None
            else None
        )
        return MarkdownReconciliationResult(
            target=target,
            project_id=self.project_id,
            goal_id=goal.goal_id,
            status=status,
            expected_sha256=expected_digest,
            actual_sha256=actual_digest,
        )

    def _scan_project_markers(
        self, content: str
    ) -> tuple[tuple[str, ...], tuple[str, ...], int, int, bool]:
        """Find valid Markdown blocks whose goal IDs are absent from SQLite."""

        lines = content.splitlines()
        marker_groups, unrecognized_count, inventory_complete = (
            self._collect_project_marker_groups(lines)
        )
        orphan_hashes, malformed_hashes, malformed_count = (
            self._classify_project_marker_groups(
                lines, marker_groups, unrecognized_count
            )
        )
        return (
            tuple(sorted(orphan_hashes)),
            tuple(sorted(malformed_hashes)),
            malformed_count,
            unrecognized_count,
            inventory_complete,
        )

    @staticmethod
    def _collect_project_marker_groups(
        lines: list[str],
    ) -> tuple[dict[str, dict[str, list[int]]], int, bool]:
        """Collect a bounded marker index without interpreting block contents."""

        marker_groups: dict[str, dict[str, list[int]]] = {}
        marker_count = 0
        unrecognized_count = 0
        inventory_complete = True
        for index, line in enumerate(lines):
            if "curatormd-v2:goal:" not in line:
                continue
            marker_count += 1
            if marker_count > MAX_PROJECT_RECONCILIATION_MARKERS:
                inventory_complete = False
                break
            match = _GOAL_MARKER_PATTERN.fullmatch(line)
            if match is None:
                unrecognized_count += 1
                continue
            marker_hash, marker_side = match.groups()
            marker_groups.setdefault(marker_hash, {"start": [], "end": []})[
                marker_side
            ].append(index)
        return marker_groups, unrecognized_count, inventory_complete

    def _classify_project_marker_groups(
        self,
        lines: list[str],
        marker_groups: dict[str, dict[str, list[int]]],
        unrecognized_count: int,
    ) -> tuple[list[str], list[str], int]:
        """Classify paired markers and find orphans already absent from SQLite."""

        malformed_count = unrecognized_count
        orphan_hashes: list[str] = []
        malformed_hashes: list[str] = []
        for marker_hash, sides in marker_groups.items():
            starts = sides["start"]
            ends = sides["end"]
            if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
                malformed_count += 1
                malformed_hashes.append(marker_hash)
                continue
            block_lines = lines[starts[0] : ends[0] + 1]
            headings = [
                match.group(1)
                for line in block_lines
                if (match := _GOAL_HEADING_PATTERN.fullmatch(line)) is not None
            ]
            if len(headings) != 1:
                malformed_count += 1
                malformed_hashes.append(marker_hash)
                continue
            goal_id = headings[0].replace(r"\-", "-").replace(r"\.", ".")
            if (
                not _GOAL_ID_PATTERN.fullmatch(goal_id)
                or _goal_markers(goal_id)[0]
                != f"<!-- curatormd-v2:goal:{marker_hash}:start -->"
            ):
                malformed_count += 1
                malformed_hashes.append(marker_hash)
                continue
            try:
                self.store.get_goal(goal_id, self.project_id)
            except NotFoundError:
                orphan_hashes.append(marker_hash)
        return orphan_hashes, malformed_hashes, malformed_count

    def verify_projection(self, result: MarkdownProjectionResult) -> None:
        """Re-read the configured target before using its hash as purge proof."""

        target = self.config.validated_persistence_target(result.target)
        content, _mode = self._read_target(target)
        actual = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if actual != result.sha256:
            raise MarkdownPersistenceError(
                "canonical Markdown changed before its purge proof was recorded"
            )

    def _render_goal(
        self,
        goal_id: str,
        *,
        progress: tuple[CriterionProgress, ...] | None = None,
    ) -> str:
        """Render the current project-scoped goal and its durable evidence."""

        goal = self.store.get_goal(goal_id, self.project_id)
        facts = self.store.list_facts(goal_id, self.project_id)
        candidates = self.store.list_sde_candidates(goal_id, self.project_id)
        pending = self.store.pending_receipts_for_goal(goal_id, self.project_id)
        receipts = self.store.receipts_for_goal(goal_id, self.project_id)
        corrections = tuple(
            correction
            for candidate in candidates
            for correction in self.store.list_sde_corrections(
                candidate.candidate_id, self.project_id
            )
        )
        return self._render_block(
            goal, facts, candidates, pending, receipts, corrections, progress
        )

    def _render_block(
        self,
        goal: GoalCard,
        facts: tuple[Fact, ...],
        candidates: tuple[SDECandidate, ...],
        pending: tuple[AuditReceipt, ...],
        receipts: tuple[AuditReceipt, ...],
        corrections: tuple[SDECorrection, ...],
        progress_snapshot: tuple[CriterionProgress, ...] | None = None,
    ) -> str:
        start_marker, end_marker = _goal_markers(goal.goal_id)
        lines = [
            start_marker,
            f"### Goal `{_markdown_text(goal.goal_id)}`",
            f"- Project: `{_markdown_text(goal.project_id)}`",
            f"- Problem: {_markdown_text(goal.problem)}",
            f"- Status: `{goal.status.value}`",
            f"- Lifecycle revision: `{goal.lifecycle_revision}`",
        ]
        if goal.owner:
            lines.append(f"- Owner: {_markdown_text(goal.owner)}")
        if goal.parent_goal_id:
            lines.append(f"- Parent goal: `{_markdown_text(goal.parent_goal_id)}`")
        if goal.superseded_by_goal_id:
            lines.append(
                "- Superseded by goal: "
                f"`{_markdown_text(goal.superseded_by_goal_id)}`"
            )
        if goal.depends_on_goal_ids:
            lines.append(
                "- Depends on: "
                + ", ".join(
                    f"`{_markdown_text(goal_id)}`"
                    for goal_id in goal.depends_on_goal_ids
                )
            )
        if goal.checklist_id:
            lines.append(f"- Checklist: `{_markdown_text(goal.checklist_id)}`")
        if goal.checklist_version and goal.checklist_source_text:
            lines.append(
                f"- Checklist source revision: `{_markdown_text(goal.checklist_version)}`"
            )
            lines.append(
                "- Checklist item (captured verbatim): "
                f"{_markdown_text(goal.checklist_source_text)}"
            )
        progress = {
            item.criterion_id: item.status.value
            for item in (
                progress_snapshot
                if progress_snapshot is not None
                else self._criterion_progress(goal, facts)
            )
        }
        lines.append("- Success criteria:")
        lines.extend(
            "  - "
            + f"`{_markdown_text(item.criterion_id)}`: "
            + f"`{progress[item.criterion_id]}` — "
            + _markdown_text(item.description)
            for item in goal.success_criteria
        )
        if goal.next_action:
            lines.append(f"- Next: {_markdown_text(goal.next_action)}")
        lines.extend(_render_facts(facts))
        lines.extend(_render_candidates(candidates))
        lines.extend(_render_receipts(receipts, self.store, self.project_id))
        lines.extend(_render_corrections(corrections))
        if pending:
            lines.append(
                f"- Open gate: `{len(pending)}` purge receipt(s) remain pending."
            )
        lines.append(end_marker)
        return _seal_goal_block("\n".join(lines))

    def _criterion_progress(
        self, goal: GoalCard, facts: tuple[Fact, ...]
    ) -> tuple[CriterionProgress, ...]:
        """Derive criterion state from evidence accepted by the trusted adapter."""

        progress: list[CriterionProgress] = []
        for criterion in goal.success_criteria:
            proof_ids = tuple(
                fact.fact_id
                for fact in facts
                if fact.kind is FactKind.VERIFICATION
                and fact.criterion_id == criterion.criterion_id
                and fact.evidence
                and all(
                    evidence.outcome is EvidenceOutcome.PASSED
                    for evidence in fact.evidence
                )
                and fact.verification_attestations
                and evidence_has_current_attestations(
                    self.evidence_verifier,
                    project_id=self.project_id,
                    goal_id=goal.goal_id,
                    criterion_id=criterion.criterion_id,
                    evidence=fact.evidence,
                    stored=fact.verification_attestations,
                )
            )
            progress.append(
                CriterionProgress(
                    criterion.criterion_id,
                    criterion.description,
                    CriterionStatus.VERIFIED if proof_ids else CriterionStatus.OPEN,
                    proof_ids,
                )
            )
        return tuple(progress)

    @staticmethod
    def _read_target(target: Path) -> tuple[str, int]:
        descriptor = MarkdownPersistenceAdapter._open_target(target)
        if descriptor is None:
            return "", 0o600

        decoded = ""
        mode = 0o600
        read_failed = False
        try:
            source = os.fdopen(descriptor, "rb")
            descriptor = -1
            with source:
                metadata = os.fstat(source.fileno())
                if not stat.S_ISREG(metadata.st_mode):
                    raise MarkdownPersistenceError(
                        "canonical Markdown target must be a regular file"
                    )
                if metadata.st_size > MAX_MARKDOWN_BYTES:
                    raise MarkdownPersistenceError(
                        f"canonical Markdown target exceeds {MAX_MARKDOWN_BYTES} bytes"
                    )
                data = source.read(MAX_MARKDOWN_BYTES + 1)
                if len(data) > MAX_MARKDOWN_BYTES:
                    raise MarkdownPersistenceError(
                        f"canonical Markdown target exceeds {MAX_MARKDOWN_BYTES} bytes"
                    )
                decode_failed = False
                decoded = ""
                try:
                    decoded = data.decode("utf-8")
                except UnicodeDecodeError:
                    # UnicodeDecodeError retains the complete canonical target.
                    decode_failed = True
                if decode_failed:
                    raise MarkdownPersistenceError(
                        "canonical Markdown target must be UTF-8"
                    )
                mode = stat.S_IMODE(metadata.st_mode)
        except OSError:
            read_failed = True
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if read_failed:
            raise MarkdownPersistenceError("cannot read canonical Markdown target")
        return decoded, mode

    @staticmethod
    def _open_target(target: Path) -> int | None:
        """Open a Markdown target without following links or leaking OS errors."""

        no_follow = getattr(os, "O_NOFOLLOW", None)
        if no_follow is None:
            raise MarkdownPersistenceError("platform lacks no-follow Markdown reads")
        open_failed = False
        descriptor = -1
        try:
            descriptor = os.open(target, os.O_RDONLY | no_follow)
        except FileNotFoundError:
            return None
        except OSError:
            open_failed = True
        if open_failed:
            raise MarkdownPersistenceError("cannot safely open Markdown target")
        return descriptor

    @staticmethod
    def _atomic_replace(target: Path, data: bytes, mode: int) -> None:
        temporary_path: str | None = None
        descriptor = -1
        replacement_failed = False
        cleanup_failed = False
        try:
            descriptor, temporary_path = tempfile.mkstemp(
                prefix=".curatormd-v2-write-", dir=target.parent
            )
            os.fchmod(descriptor, mode)
            with os.fdopen(descriptor, "wb") as destination:
                descriptor = -1
                destination.write(data)
                destination.flush()
                os.fsync(destination.fileno())
            if target.is_symlink():
                raise MarkdownPersistenceError(
                    "canonical Markdown target became a symlink"
                )
            os.replace(temporary_path, target)
            temporary_path = None
            directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            directory_fd = os.open(target.parent, directory_flags)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except (OSError, ValueError):
            replacement_failed = True
        finally:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    cleanup_failed = True
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
                except OSError:
                    cleanup_failed = True
        if replacement_failed:
            message = "atomic canonical Markdown replacement failed"
            if cleanup_failed:
                message += " and temporary cleanup failed"
            raise MarkdownPersistenceError(message)
        if cleanup_failed:
            raise MarkdownPersistenceError("temporary canonical Markdown cleanup failed")


def _markdown_text(value: str) -> str:
    safe = escape(value, quote=False)
    for character in "\\`*_{}[]()#+-.!|~":
        safe = safe.replace(character, "\\" + character)
    return safe


def _goal_markers(goal_id: str) -> tuple[str, str]:
    goal_key = hashlib.sha256(goal_id.encode("utf-8")).hexdigest()
    return (
        f"<!-- curatormd-v2:goal:{goal_key}:start -->",
        f"<!-- curatormd-v2:goal:{goal_key}:end -->",
    )


def _integrity_marker_index(lines: list[str]) -> int | None:
    """Return the sole integrity marker line, rejecting duplicate markers."""

    indices = [
        index
        for index, line in enumerate(lines)
        if line.startswith("<!-- curatormd-v2:block-sha256:")
    ]
    if not indices:
        return None
    if len(indices) != 1 or _BLOCK_INTEGRITY_PATTERN.fullmatch(lines[indices[0]]) is None:
        return -1
    return indices[0]


def _block_integrity(block: str) -> bool | None:
    """Validate a generated-block checksum; ``None`` identifies legacy blocks."""

    lines = block.splitlines()
    marker_index = _integrity_marker_index(lines)
    if marker_index is None:
        return None
    if marker_index < 0:
        return False
    match = _BLOCK_INTEGRITY_PATTERN.fullmatch(lines[marker_index])
    if match is None:
        return False
    unsealed = lines[:marker_index] + lines[marker_index + 1 :]
    actual = hashlib.sha256("\n".join(unsealed).encode("utf-8")).hexdigest()
    return actual == match.group(1)


def _unsealed_block(block: str) -> str:
    """Remove the generated checksum line from a block for legacy comparison."""

    lines = block.splitlines()
    marker_index = _integrity_marker_index(lines)
    if marker_index is None or marker_index < 0:
        return block
    return "\n".join(lines[:marker_index] + lines[marker_index + 1 :])


def _seal_goal_block(block: str) -> str:
    """Add an accidental-edit checksum to a generated goal block."""

    lines = block.splitlines()
    if len(lines) < 2 or not lines[-1].endswith(":end -->"):
        raise MarkdownPersistenceError("rendered goal block has invalid markers")
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    marker = f"<!-- curatormd-v2:block-sha256:{digest} -->"
    return "\n".join(lines[:-1] + [marker, lines[-1]])


def _render_facts(facts: tuple[Fact, ...]) -> list[str]:
    lines = ["- Facts:"]
    if not facts:
        lines.append("  - No facts recorded.")
        return lines
    for fact in facts:
        lines.append(f"  {_markdown_text(fact.as_bullet())}")
        lines.extend(
            "    - Evidence: "
            + f"`{_markdown_text(evidence.evidence_kind)}`; "
            + f"`{_markdown_text(evidence.locator)}`; "
            + f"SHA-256 `{evidence.sha256}`; `{evidence.outcome.value}`"
            for evidence in fact.evidence
        )
    return lines


def _render_candidates(candidates: tuple[SDECandidate, ...]) -> list[str]:
    approved = tuple(
        candidate
        for candidate in candidates
        if candidate.status is SDEStatus.APPROVED
    )
    if not approved:
        return []
    return [
        "- SDE review:",
        *(
            "  - Candidate "
            + f"`{candidate.candidate_id}`: `{candidate.status.value}`; "
            + f"`{candidate.materiality.value}`; "
            + f"Impact: {_markdown_text(candidate.impact or 'not recorded')}; "
            + "Retrieval value: "
            + f"{_markdown_text(candidate.retrieval_value or 'not recorded')}; "
            + _markdown_text(candidate.rationale)
            for candidate in approved
        ),
    ]


def _render_receipts(
    receipts: tuple[AuditReceipt, ...], store: CuratorStore, project_id: str
) -> list[str]:
    if not receipts:
        return []
    lines = ["- Review receipts:"]
    for receipt in receipts:
        lines.append(
            "  - "
            + f"`{receipt.receipt_id}`: `{receipt.decision.value}`; "
                    + f"reviewer `{receipt.reviewer_id or 'legacy-unattributed'}`; "
            + f"facts SHA-256 `{receipt.facts_sha256}`; "
            + f"purge `{receipt.purge_status.value}`; "
            + f"inventory complete `{str(receipt.artifact_inventory_complete).lower()}`; "
            + f"artifacts `{len(receipt.artifacts)}`"
        )
        if receipt.review_rationale:
            lines.append(
                "    - Review rationale: "
                + _markdown_text(receipt.review_rationale)
            )
        if receipt.canonical_persisted:
            lines.append(
                "    - Pre-purge canonical facts/receipt persisted to "
                + f"`{_markdown_text(receipt.canonical_target or '')}`; "
                + f"projection SHA-256 `{receipt.canonical_sha256}`"
            )
        lines.extend(
            "    - Artifact SHA-256 "
            + f"`{artifact.sha256}`; `{status.value}`; attempts `{attempts}`"
            for artifact, status, attempts, _error in store.get_purge_targets(
                receipt.receipt_id, project_id=project_id
            )
        )
    return lines


def _render_corrections(corrections: tuple[SDECorrection, ...]) -> list[str]:
    """Render reviewer corrections as separate linked, attributable bullets."""

    lines: list[str] = []
    if corrections:
        lines.append("- SDE corrections (append-only):")
    for item in corrections:
        lines.append(
            "  - "
            f"`{_markdown_text(item.correction_id)}` for candidate "
            f"`{_markdown_text(item.candidate_id)}`: "
            f"{_markdown_text(item.correction)} "
            f"(rationale: {_markdown_text(item.rationale)}; "
            f"reviewer: `{_markdown_text(item.reviewer_id)}`; "
            f"at: `{_markdown_text(item.created_at)}`)"
        )
    return lines


def _upsert_block(text: str, block: str, start: str, end: str) -> str:
    lines = text.splitlines(keepends=True)
    marker_lines = [
        (index, line.rstrip("\r\n"))
        for index, line in enumerate(lines)
        if start in line or end in line
    ]
    starts = [index for index, marker in marker_lines if marker == start]
    ends = [index for index, marker in marker_lines if marker == end]
    if len(marker_lines) != len(starts) + len(ends) or len(starts) > 1 or len(ends) > 1:
        raise MarkdownPersistenceError("goal projection markers are duplicated or incomplete")
    if not starts and not ends:
        if not text:
            return block + "\n"
        separator = "\n" if text.endswith("\n") else "\n\n"
        return text + separator + block + "\n"
    if len(starts) != 1 or len(ends) != 1:
        raise MarkdownPersistenceError("goal projection markers are duplicated or incomplete")
    start_index, end_index = starts[0], ends[0]
    if end_index < start_index:
        raise MarkdownPersistenceError("goal projection markers are out of order")
    existing_block = "".join(lines[start_index : end_index + 1]).rstrip("\r\n")
    integrity = _block_integrity(existing_block)
    if integrity is False:
        raise MarkdownPersistenceError(
            "managed goal block checksum mismatch; preserving edited content"
        )
    if integrity is None and existing_block != _unsealed_block(block):
        raise MarkdownPersistenceError(
            "legacy goal block cannot be safely replaced; reconcile it first"
        )
    prefix = "".join(lines[:start_index])
    suffix = "".join(lines[end_index + 1 :])
    return prefix + block + "\n" + suffix


def _read_goal_block(
    text: str, start: str, end: str, expected_block: str
) -> tuple[str | None, MarkdownReconciliationStatus]:
    """Extract one exact goal block, classifying unsafe marker layouts."""

    lines = text.splitlines(keepends=True)
    marker_lines = [
        (index, line.rstrip("\r\n"))
        for index, line in enumerate(lines)
        if start in line or end in line
    ]
    starts = [index for index, marker in marker_lines if marker == start]
    ends = [index for index, marker in marker_lines if marker == end]
    if not marker_lines:
        return None, MarkdownReconciliationStatus.MISSING
    if (
        len(marker_lines) != len(starts) + len(ends)
        or len(starts) != 1
        or len(ends) != 1
        or ends[0] < starts[0]
    ):
        return None, MarkdownReconciliationStatus.MALFORMED

    actual_block = "".join(lines[starts[0] : ends[0] + 1])
    integrity = _block_integrity(actual_block)
    if integrity is False:
        return actual_block, MarkdownReconciliationStatus.MALFORMED
    expected_with_newline = expected_block + "\n"
    legacy_expected = _unsealed_block(expected_block) + "\n"
    status = (
        MarkdownReconciliationStatus.SYNCED
        if actual_block == expected_with_newline
        or (integrity is None and actual_block == legacy_expected)
        else MarkdownReconciliationStatus.DIVERGENT
    )
    return actual_block, status
