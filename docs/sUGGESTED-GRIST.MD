# Suggested Grist for pending approval

Here is the extended curator_v2_schema.py module with token-budget enforcement and a warning/archive switch, followed by a complete pytest unit test suite

## (test_curator_v2_schema.py)

### 1. Extended Module with Token-Budget Switch (curator_v2_schema.py)

This adds a BudgetPolicy mode ("warn", "auto_archive", or "strict_block") and returns a structured CommitResult so your VS Code plugin can display non-blocking notifications or archive confirmations cleanly.

```python
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


BudgetAction = Literal["warn", "auto_archive", "strict_block"]


@dataclass
class CommitResult:
    written_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    archived_files: list[str] = field(default_factory=list)


# --- Level 4: Directive Blocks per Persistence Target ---

class LessonsDirectives(BaseModel):
    always_never_remember_CHECK: list[str] = Field(default_factory=list)
    reason: str
    lifecycleGate: Literal["pre_diff_and_post_error"] = "pre_diff_and_post_error"
    tokenBudget: int = 800


class AgentsDirectives(BaseModel):
    plan_function_changes: list[str] = Field(default_factory=list)
    reason: str
    lifecycleGate: Literal["planning_phase"] = "planning_phase"
    tokenBudget: int = 1200


class HistoryDirectives(BaseModel):
    milestones_progress_context_SDE: list[str] = Field(default_factory=list)
    reason: str
    lifecycleGate: Literal["post_commit"] = "post_commit"
    tokenBudget: int = 500


class SopDirectives(BaseModel):
    ensure_prevent_always_never: list[str] = Field(default_factory=list)
    reason: str
    lifecycleGate: Literal["always_active"] = "always_active"
    tokenBudget: int = 1000


# --- Level 3: Target Gating & Write Policy ---

class LessonsTarget(BaseModel):
    enabled: bool = False
    writePolicy: Literal["staged_approval"] = "staged_approval"
    directives: LessonsDirectives


class AgentsTarget(BaseModel):
    enabled: bool = False
    writePolicy: Literal["staged_approval"] = "staged_approval"
    directives: AgentsDirectives


class HistoryTarget(BaseModel):
    enabled: bool = True
    writePolicy: Literal["staged_approval"] = "staged_approval"
    directives: HistoryDirectives


class SopTarget(BaseModel):
    enabled: bool = False
    writePolicy: Literal["staged_approval"] = "staged_approval"
    directives: SopDirectives


# --- Level 2: Meta, Payload & Persistence Containers ---

class ProposalMeta(BaseModel):
    sdeId: str
    startedAt: str
    evidenceReceipt: Literal["verified"] = "verified"
    significance: int = Field(ge=1, le=5)
    rationale: str


class ProposalPayload(BaseModel):
    title: str
    problem: str
    completion: list[str] = Field(default_factory=list)
    difficulties: list[str] = Field(default_factory=list)
    planChanges: list[str] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    futureUtility: str


class PersistenceMap(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    lessons_learned: LessonsTarget = Field(alias="persistence/LESSONS-LEARNED.md")
    agents: AgentsTarget = Field(alias="persistence/AGENTS.md")
    history: HistoryTarget = Field(alias="persistence/HISTORY.md")
    sop: SopTarget = Field(alias="persistence/SOP.md")


# --- Level 1: Root Envelope ---

class SdeProposalBody(BaseModel):
    meta: ProposalMeta
    payload: ProposalPayload
    persistence: PersistenceMap


class SdeProposalEnvelope(BaseModel):
    sdeProposal: SdeProposalBody


# --- Token Estimation & Archiving Helpers ---

def estimate_tokens(text: str) -> int:
    """Fast, dependency-free token estimator (~4 chars per token for English/Markdown)."""
    return max(1, (len(text) + 3) // 4) if text else 0


def _archive_oldest_sections(target_file: Path, max_tokens: int) -> Path | None:
    """Moves oldest `## [...]` entries into `persistence/archive/` until under max_tokens."""
    if not target_file.exists():
        return None

    content = target_file.read_text(encoding="utf-8")
    if estimate_tokens(content) <= max_tokens:
        return None

    sections = re.split(r"(?=\n## \[)", content)
    header = sections[0] if not sections[0].startswith("\n## [") else ""
    entries = sections[1:] if header else sections

    archived_entries: list[str] = []
    while len(entries) > 1 and estimate_tokens(header + "".join(entries)) > max_tokens:
        archived_entries.append(entries.pop(0))

    if not archived_entries:
        return None

    archive_dir = target_file.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    archive_file = archive_dir / f"{target_file.stem}-{stamp}.md"

    with archive_file.open("a", encoding="utf-8") as af:
        af.write("".join(archived_entries))

    target_file.write_text(header + "".join(entries), encoding="utf-8")
    return archive_file


# --- Markdown Renderer & Decision Parser ---

def render_review_markdown(project_name: str, proposals: list[SdeProposalEnvelope]) -> str:
    """Renders the low-noise dual-JSON review document for VS Code."""
    lines = [
        "# Pending SDE reviews\n",
        f"Project: {project_name}\n",
        "Review the complete proposal JSON, adjust the editable copy below if needed, "
        "and trigger **Accept**, **Reject**, **Withdraw**, or **Refresh evidence**.\n",
    ]

    for idx, item in enumerate(proposals, start=1):
        sde_id = item.sdeProposal.meta.sdeId
        pretty_json = item.model_dump_json(by_alias=True, indent=2)

        lines.extend([
            f"<!-- curator-v2-candidate: {sde_id} -->",
            f"## SDE candidate {idx}\n",
            "### 1. Complete proposal (Read-only reference)\n",
            "```json",
            pretty_json,
            "```\n",
            f"<!-- curator-v2-actions: {sde_id} -->",
            "### 2. Editable decision (Approve / Modify)\n",
            f"<!-- curator-v2-decision:{sde_id}:start -->",
            "```json",
            pretty_json,
            "```",
            f"<!-- curator-v2-decision:{sde_id}:end -->\n",
        ])

    return "\n".join(lines)


def parse_approved_decision(markdown_text: str, sde_id: str) -> SdeProposalEnvelope:
    """Extracts and validates your edited JSON block when Accept is triggered in VS Code."""
    pattern = (
        rf"<!-- curator-v2-decision:{re.escape(sde_id)}:start -->\s*"
        r"```json\s*(.*?)\s*```\s*"
        rf"<!-- curator-v2-decision:{re.escape(sde_id)}:end -->"
    )
    match = re.search(pattern, markdown_text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Decision block not found for SDE ID: {sde_id}")

    raw_json = json.loads(match.group(1))
    return SdeProposalEnvelope.model_validate(raw_json)


def commit_approved_proposal(
    workspace_root: Path,
    envelope: SdeProposalEnvelope,
    on_budget_exceeded: BudgetAction = "warn",
) -> CommitResult:
    """Appends approved directives to enabled persistence/*.md files with token-budget controls."""
    prop = envelope.sdeProposal
    result = CommitResult()

    routing = [
        (
            "persistence/LESSONS-LEARNED.md",
            prop.persistence.lessons_learned.enabled,
            prop.persistence.lessons_learned.directives.always_never_remember_CHECK,
            prop.persistence.lessons_learned.directives.tokenBudget,
        ),
        (
            "persistence/AGENTS.md",
            prop.persistence.agents.enabled,
            prop.persistence.agents.directives.plan_function_changes,
            prop.persistence.agents.directives.tokenBudget,
        ),
        (
            "persistence/HISTORY.md",
            prop.persistence.history.enabled,
            prop.persistence.history.directives.milestones_progress_context_SDE,
            prop.persistence.history.directives.tokenBudget,
        ),
        (
            "persistence/SOP.md",
            prop.persistence.sop.enabled,
            prop.persistence.sop.directives.ensure_prevent_always_never,
            prop.persistence.sop.directives.tokenBudget,
        ),
    ]

    for rel_path, is_enabled, bullets, token_budget in routing:
        if not is_enabled or not bullets:
            continue

        target_file = workspace_root / rel_path
        target_file.parent.mkdir(parents=True, exist_ok=True)

        entry_block = "\n".join([
            f"\n## [{prop.meta.startedAt}] {prop.payload.title} (SDE: `{prop.meta.sdeId[:8]}` | Sig: {prop.meta.significance}/5)",
            *[f"- {bullet}" for bullet in bullets],
            "",
        ])

        existing_text = target_file.read_text(encoding="utf-8") if target_file.exists() else ""
        projected_tokens = estimate_tokens(existing_text + entry_block)

        if projected_tokens > token_budget:
            if on_budget_exceeded == "strict_block":
                raise ValueError(
                    f"Budget exceeded for {rel_path}: {projected_tokens} > {token_budget} tokens."
                )
            elif on_budget_exceeded == "warn":
                result.warnings.append(
                    f"{rel_path} reached {projected_tokens}/{token_budget} tokens (warning only; write allowed)."
                )

        with target_file.open("a", encoding="utf-8") as f:
            f.write(entry_block)

        if projected_tokens > token_budget and on_budget_exceeded == "auto_archive":
            archived_path = _archive_oldest_sections(target_file, token_budget)
            if archived_path:
                result.archived_files.append(str(archived_path.relative_to(workspace_root)))

        result.written_files.append(rel_path)

    return result
```

Use code with caution.

### 2. Unit Test Suite (test_curator_v2_schema.py)

Run with pytest -v in your Linux workspace to verify schema validation, round-trip Markdown rendering, manual JSON edits in the decision block, and all three on_budget_exceeded switches ("warn", "auto_archive", "strict_block").

```python
import json
import pytest
from pathlib import Path
from curator_v2_schema import (
    SdeProposalEnvelope,
    render_review_markdown,
    parse_approved_decision,
    commit_approved_proposal,
)

@pytest.fixture
def sample_envelope() -> SdeProposalEnvelope:
    raw = {
        "sdeProposal": {
            "meta": {
                "sdeId": "10cb433892ef4c059c0801ffd5f279bb",
                "startedAt": "2026-11-02T18:20:57+07:00",
                "evidenceReceipt": "verified",
                "significance": 4,
                "rationale": "Project-bound wrapper and monitor replace scattered alpha scripts.",
            },
            "payload": {
                "title": "Complete remaining open requirements in Curator V2",
                "problem": "Scattered alpha operations lacked automated health monitoring.",
                "completion": [
                    "Installed curatormd-v2-ops with 60s resident monitor and 6h maintenance path."
                ],
                "difficulties": [],
                "planChanges": [],
                "lessons": [],
                "futureUtility": "Useful for local-alpha maintenance and operations.",
            },
            "persistence": {
                "persistence/LESSONS-LEARNED.md": {
                    "enabled": False,
                    "writePolicy": "staged_approval",
                    "directives": {
                        "always_never_remember_CHECK": [],
                        "reason": "No reusable rule supported by candidate facts.",
                        "lifecycleGate": "pre_diff_and_post_error",
                        "tokenBudget": 800,
                    },
                },
                "persistence/AGENTS.md": {
                    "enabled": False,
                    "writePolicy": "staged_approval",
                    "directives": {
                        "plan_function_changes": [],
                        "reason": "No agent routing change explicit.",
                        "lifecycleGate": "planning_phase",
                        "tokenBudget": 1200,
                    },
                },
                "persistence/HISTORY.md": {
                    "enabled": True,
                    "writePolicy": "staged_approval",
                    "directives": {
                        "milestones_progress_context_SDE": [
                            "Installed curatormd-v2-ops wrapper and 60s resident monitor."
                        ],
                        "reason": "Records SDE milestone in project timeline.",
                        "lifecycleGate": "post_commit",
                        "tokenBudget": 500,
                    },
                },
                "persistence/SOP.md": {
                    "enabled": True,
                    "writePolicy": "staged_approval",
                    "directives": {
                        "ensure_prevent_always_never": [
                            "Prevent unapproved destructive changes (owner-gated)."
                        ],
                        "reason": "Records repeatable recovery controls.",
                        "lifecycleGate": "always_active",
                        "tokenBudget": 1000,
                    },
                },
            },
        }
    }
    return SdeProposalEnvelope.model_validate(raw)

def test_roundtrip_render_and_manual_decision_edit(sample_envelope: SdeProposalEnvelope):
    md = render_review_markdown("curatormd-v2-dev-alpha", [sample_envelope])
    sde_id = sample_envelope.sdeProposal.meta.sdeId

    # Simulate owner editing the decision block in VS Code:
    # 1) Disable SOP.md
    # 2) Enable LESSONS-LEARNED.md and add a new rule
    marker_start = f"<!-- curator-v2-decision:{sde_id}:start -->\n```json\n"
    marker_end = f"\n```\n<!-- curator-v2-decision:{sde_id}:end -->"

    prefix, rest = md.split(marker_start)
    decision_json_str, suffix = rest.split(marker_end)

    edited_data = json.loads(decision_json_str)
    edited_data["sdeProposal"]["persistence"]["persistence/SOP.md"]["enabled"] = False
    edited_data["sdeProposal"]["persistence"]["persistence/LESSONS-LEARNED.md"]["enabled"] = True
    edited_data["sdeProposal"]["persistence"]["persistence/LESSONS-LEARNED.md"]["directives"][
        "always_never_remember_CHECK"
    ] = ["Always verify queue freshness before maintenance runs."]

    edited_md = prefix + marker_start + json.dumps(edited_data, indent=2) + marker_end + suffix

    parsed = parse_approved_decision(edited_md, sde_id)
    assert parsed.sdeProposal.persistence.sop.enabled is False
    assert parsed.sdeProposal.persistence.lessons_learned.enabled is True
    assert len(parsed.sdeProposal.persistence.lessons_learned.directives.always_never_remember_CHECK) == 1

def test_commit_writes_only_enabled_targets(tmp_path: Path, sample_envelope: SdeProposalEnvelope):
    res = commit_approved_proposal(tmp_path, sample_envelope, on_budget_exceeded="warn")

    assert res.written_files == ["persistence/HISTORY.md", "persistence/SOP.md"]
    assert res.warnings == []
    assert not (tmp_path / "persistence/LESSONS-LEARNED.md").exists()
    assert not (tmp_path / "persistence/AGENTS.md").exists()

    history_text = (tmp_path / "persistence/HISTORY.md").read_text(encoding="utf-8")
    assert "Installed curatormd-v2-ops wrapper" in history_text

def test_budget_warn_switch(tmp_path: Path, sample_envelope: SdeProposalEnvelope):
    # Force a tiny token budget on HISTORY.md
    sample_envelope.sdeProposal.persistence.history.directives.tokenBudget = 10

    res = commit_approved_proposal(tmp_path, sample_envelope, on_budget_exceeded="warn")

    assert "persistence/HISTORY.md" in res.written_files
    assert len(res.warnings) == 1
    assert "persistence/HISTORY.md" in res.warnings[0]

def test_budget_strict_block_switch(tmp_path: Path, sample_envelope: SdeProposalEnvelope):
    sample_envelope.sdeProposal.persistence.history.directives.tokenBudget = 10

    with pytest.raises(ValueError, match="Budget exceeded for persistence/HISTORY.md"):
        commit_approved_proposal(tmp_path, sample_envelope, on_budget_exceeded="strict_block")

def test_budget_auto_archive_switch(tmp_path: Path, sample_envelope: SdeProposalEnvelope):
    history_file = tmp_path / "persistence/HISTORY.md"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(
        "# Project History\n\n## [2026-10-01] Old Milestone (SDE: `00001111` | Sig: 3/5)\n- Old entry bullet.\n",
        encoding="utf-8",
    )

    # Set budget tight enough to trigger archiving of the old section while keeping the new one
    sample_envelope.sdeProposal.persistence.history.directives.tokenBudget = 45

    res = commit_approved_proposal(tmp_path, sample_envelope, on_budget_exceeded="auto_archive")

    assert len(res.archived_files) == 1
    archive_path = tmp_path / res.archived_files[0]
    assert archive_path.exists()
    assert "Old Milestone" in archive_path.read_text(encoding="utf-8")
    assert "Old Milestone" not in history_file.read_text(encoding="utf-8")
    assert "Installed curatormd-v2-ops wrapper" in history_file.read_text(encoding="utf-8")
```

Use code with caution.

### Summary of Budget Switch Options`

• on_budget_exceeded="warn" (Default). Appends your approved decision immediately so your workflow is never blocked, and populates CommitResult.warnings so your VS Code extension can pop a yellow toast notification when a file crosses its tokenBudget.
• on_budget_exceeded="auto_archive". Appends the new entry, splits older ## [...] sections off the top of the Markdown file, and moves them into persistence/archive/`<FILE>-YYYYMMDD.md` until the active file sits back under tokenBudget.
• on_budget_exceeded="strict_block". Raises a ValueError before touching disk, forcing manual pruning or a budget bump in your editable JSON block before committing.
If you want to connect this to your Hermes LLM prompt or VS Code extension next, I can provide:
• A Hermes system-prompt template paired with SdeProposalEnvelope.model_json_schema() so Codex populates the directives arrays accurately
• A VS Code TypeScript snippet that displays CommitResult.warnings and archived_files in an information/warning toast after you click Accept
Which would you like to tackle next?

### 3. JSON output example

Here is the complete, end-to-end JSON output example produced by SdeProposalEnvelope with your verified evidenceReceipt, completion array, payload positioned above persistence, and all four 4-level target blocks (enabled, writePolicy, directives, lifecycleGate, tokenBudget).

```json
{OPEN PENDING REVIEW
  "sdeProposal": {
    "meta": {
      "sdeId": "10cb433892ef4c059c0801ffd5f279bb",
      "startedAt": "2026-11-02T18:20:57+07:00",
      "evidenceReceipt": "verified",
      "significance": 4,
      "rationale": "One project-bound wrapper, monitor, scheduled maintenance path, manifest, and operational inventory replace scattered alpha operations; local regression and packaging checks pass."
    },
    "payload": {
      "title": "Complete remaining open requirements in Curator V2 at docs/curator-v2-plan.md and docs/Repair V2 dashboard health and queue feeds PLAN.md.",
      "problem": "Complete remaining open requirements in Curator V2 at docs/curator-v2-plan.md and docs/Repair V2 dashboard health and queue feeds PLAN.md.",
      "completion": [
        "Added and installed curatormd-v2-ops for curatormd-v2-dev-alpha: an owner-private exact-binding manifest, 60-second resident monitor, six-hour maintenance path, seven-dependency and complete-queue freshness checks, resource limits, and one runbook inventory. Incident diagnosis is deduplicated and bounded; identity, grant, deployment, and destructive changes remain owner-gated."
      ],
      "difficulties": [],
      "planChanges": [],
      "lessons": [],
      "futureUtility": "Useful for future Curator V2 local-alpha maintenance and operations."
    },
    "persistence": {
      "persistence/LESSONS-LEARNED.md": {
        "enabled": false,
        "writePolicy": "staged_approval",
        "directives": {
          "always_never_remember_CHECK": [],
          "reason": "No reusable always, never, remember, or check rule is supported by the candidate facts.",
          "lifecycleGate": "pre_diff_and_post_error",
          "tokenBudget": 800
        }
      },
      "persistence/AGENTS.md": {
        "enabled": false,
        "writePolicy": "staged_approval",
        "directives": {
          "plan_function_changes": [],
          "reason": "No agent instruction, behavior, scope, routing, or planning-function change is explicit.",
          "lifecycleGate": "planning_phase",
          "tokenBudget": 1200
        }
      },
      "persistence/HISTORY.md": {
        "enabled": true,
        "writePolicy": "staged_approval",
        "directives": {
          "milestones_progress_context_SDE": [
            "Installed curatormd-v2-ops wrapper, 60-second resident monitor, six-hour maintenance path, and runbook inventory for curatormd-v2-dev-alpha."
          ],
          "reason": "Records this SDE outcome in the project timeline.",
          "lifecycleGate": "post_commit",
          "tokenBudget": 500
        }
      },
      "persistence/SOP.md": {
        "enabled": true,
        "writePolicy": "staged_approval",
        "directives": {
          "ensure_prevent_always_never": [
            "Ensure seven-dependency and complete-queue freshness checks remain active on the 60-second monitor and six-hour maintenance path.",
            "Prevent unapproved identity, grant, deployment, or destructive changes by keeping them strictly owner-gated."
          ],
          "reason": "Records repeatable operational steps and recovery controls.",
          "lifecycleGate": "always_active",
          "tokenBudget": 1000
        }
      }
    }
  }
}
```

Use code with caution.

#### Quick Structure Recap

• Level 1 (sdeProposal). Single top-level root key wrapping the proposal.
• Level 2 (meta, payload, persistence). Groups receipt metadata first, verified task facts second, and file routing third.
• Level 3 (persistence/*.md). Holds the enabled toggle and "writePolicy": "staged_approval" for each target file.
• Level 4 (directives). Contains the file-specific rule array (always_never_remember_CHECK, plan_function_changes, milestones_progress_context_SDE, ensure_prevent_always_never), disposition reason, lifecycleGate, and tokenBudget.

If you would like to wire this JSON directly into your Hermes prompt or VS Code plugin next, I can share the Hermes system-prompt instructions that guide Codex to populate those four directive arrays accurately. Would that be helpful?
