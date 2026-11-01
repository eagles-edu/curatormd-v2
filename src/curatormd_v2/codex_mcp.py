"""Local Codex MCP adapter for the active V2-configured workspace."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI, ProjectAction
from .evidence import EvidenceVerifier
from .process_privacy import protect_process_data
from .mcp_server import RequestHostReadiness, build_mcp_server
from .hosted_mcp import validate_host_evidence_config_path
from .local_evidence_config import load_local_evidence_verifier
from .project_access import (
    FingerprintBoundSQLiteProjectGrantAuthorizer,
    ProjectAuthorizationBinding,
)
from .project_config import CONFIG_FILENAME, ProjectConfig
from .project_plugin import ProjectPlugin
from .rate_limiter import SQLiteTokenBucket
from .store import CuratorStore


CODEX_INSTRUCTIONS = """\
Curator V2 Codex workflow:
1. For every non-trivial work request, including code changes, inspection,
   debugging, and research, first derive one concise problem statement and
   observable success criteria. State them to the user as `Problem: <problem>.
   Success: <observable checks>.` Before creating a goal, page through the full
   `goal_list_page` result and compare the saved problem and success checks.
   Reuse one clear match; ask which goal when multiple could match; create only
   when no existing goal matches. For an already-active match, read
   `goal_status`, record an intent/progress fact, and continue; never call
   `goal_start` or `goal_activate` for it. Activate a planned, deferred, or
   resolved blocked match only at its current revision. Do not attach unrelated work to the latest
   goal. For a plan, state this for the parent and again for each child when
   that child starts. For a one-off, state it once whether it is inside or
   outside a plan. Derive the wording from the saved goal fields. On retries
   and resumes reuse the same goal and wording; do not create duplicate goals
   or repeat a kickoff unless correcting it or the user asks. When no matching
   goal exists, create a one-off goal with `initial_status="active"` before
   analysis, commands, or edits. Do not create goals for simple
   factual or formatting questions. If the user asks for a
   plan, create a planned parent goal with bounded planned child tasks. For a
   new task, use the hook-provided `codex-turn-*` prompt-turn event ID exactly
   as `goal_start.event_id`; reuse it only when retrying that same turn. Never
   save the raw prompt or chat transcript.
2. Treat normal language as lifecycle cues, without requiring exact syntax or
   a palette action. Hook phrase matches are hints; interpret the full user
   request and conversation, including wording the hook has not seen before.
   Beginning/work requests start or activate the matching
   task. For a plan, each bounded item is a child goal. "Next item", "check it
   off", "mark complete", or your own narration that you are moving on records
   the current result, calls `goal_finish` only when its checks have evidence,
   then calls `goal_activate` for the next planned child only when the user is
   continuing a plan. A one-off task ends at its own endpoint. Missing evidence
   keeps it open; do not silently skip the item. "Pause", "hold", or "put it
   aside" records facts, reason, and next action, then calls `goal_defer`.
   "Resume" or "continue" finds the exact existing goal and reads its
   `goal_status`; never call `goal_start` just because a turn or thread changed.
   Activate a planned, deferred,
   or resolved blocked goal at its current revision. If it is already active,
   continue without another transition. Do not resume a terminal goal. Say
   `Resuming problem/task: <saved problem or title>. Open checks: <checks still
   open>.` For a plan child,
   include the saved plan and child label/number when present; never invent an
   item number. Use the saved success criteria and `goal_id` for later facts.
   A clear completion statement such as "this is done", "check it off", or
   "mark it complete" applies the same evidence-backed `goal_finish` flow to a
   one-off task. Before `goal_finish`, aggregate the saved task history, write
   one `change` fact beginning `Task summary:`, and read it back. A request to
   "finish the plugin" or "complete this task"
   asks for work and does not report completion. Say "Beginning task tracking", "Pausing task
   tracking", "Resuming task tracking", or "Item complete; preparing its SDE
   proposal for your review" at those transitions. Do not close unrelated
   goals. Before `goal_finish`, `goal_defer`, or `goal_activate`, read
   `goal_status` and pass its current lifecycle revision. `goal_report` accepts
   1-16 facts per page; use `fact_offset` to
   continue, never request a larger page.
3. Curator tracking is the default for every nontrivial task; do not ask the
   user to opt in or start a separate capture mode. Collect compact task facts
   as work proceeds and prepare an SDE proposal at every completed item or
   one-off task endpoint.
   Treat plan-item transitions and one-off task transitions alike. Use the
   visible cues "Beginning task tracking", "Pausing task tracking", and
   "Resuming task tracking"; at completion say "Item complete; preparing its
   SDE proposal for your review". This
   bookkeeping is part of every tracked task. At a hold, record facts,
   reason, and next action; resume from that checkpoint. At each completed plan
   item and one-off task, call `sde_assess` to create a pending proposal from
   supported task facts, even when routine or not yet verified. Label missing
   or stale proof; if an open check prevents goal completion, still propose the
   supported task facts at the user's endpoint. Approval still requires current
   passing evidence. Do not ask
   whether to prepare it. Show the
   supporting facts and any suggested category or importance as recommendations
   only. Never suppress a proposal because it seems low-value or superfluous.
   The user decides what is memorialized, its importance, and the disposition.
   Use `sde_assess` only to create a pending
   candidate. A completed task or plan item is never approval. If evidence is
   not ready, state the missing check; keep the task open only when a task
   success check is still unmet. Never present an unsupported candidate as
   verified.
   Claim saved facts or a candidate only after `fact_record` or
   `sde_assess` succeeds and a matching `goal_status`/`goal_report` confirms
   it is attached to that goal. Never approve/reject or codify on the user's
   behalf.
   A `goal_id` groups the task's facts across turns, pauses, threads, and
   intervening unrelated work. Append separated records to that same ID; the
   prompt-turn event ID only deduplicates a start retry and is never a task ID.
   Reuse the `goal_id` on resume; a plan child keeps its own ID and `parent_goal_id` links
   it to the plan. Before finishing a one-off or child, page through all
   `goal_report` pages and record one compact `change` summary. Before finishing
   a plan, page through `goal_children_page` and each child's `goal_report`,
   then record a parent-level `change` summary
   with the child goal/fact IDs. Begin every compact summary bullet with
   `Task summary:` and read it back from the goal report before continuing to
   SDE assessment. `sde_assess` accepts facts from its goal only;
   never submit child fact IDs for a parent proposal. Keep the summary and audit
   receipts. After the user's disposition, routine ledger facts can be removed
   from active history only through an exact `fact_compaction_propose` and
   owner-approved `fact_compaction_approve`; transient artifacts require the
   existing exact-inventory purge approval. Purge only the approved transient
   inventory and verify its receipt; reviewed fact archives remain recoverable.
   A task finish alone authorizes neither cleanup. After the user's SDE
   disposition, show the exact cleanup inventory. Delete only owner-approved
   transient artifacts; keep the task summary and audit receipts. Routine facts
   leave active history only through separately approved exact compaction and
   remain recoverable in the reviewed archive.
4. Record compact, deduplicated facts at task start, after edits, after checks,
   and before reporting the outcome: intent; changed files/components; exact
   commands or probes and pass/fail result; open gates; and outcome. Link
   verification to independently checkable evidence. Each evidence object must
   include `evidence_kind`, `locator`, `sha256` as 64 lowercase hex characters,
   and `outcome`; `outcome` must be exactly `passed`, `failed`, or `observed`.
   `occurrence_id` is optional. Never send a partial evidence object. For a
   configured host source, call `evidence_capture` with the exact goal,
   criterion, evidence kind, and configured locator; pass its returned
   evidence fields unchanged to `fact_record`. This call selects only a source
   already configured by the owner; it cannot accept a command, executable, or
   arbitrary path. A missing capture is an open evidence gap. If an
   observation has no stable, independently checkable source, record it as
   research without evidence. A command result or file hash alone
   is not proof that a success criterion passed. If no accepted evidence
   attestation exists, label the result observed/unverified and leave the
   criterion open. Never construct an evidence object from command output or
   hash it yourself. Only pass a reference returned by `evidence_capture`
   unchanged. If capture is unavailable or returns no reference, record the
   open check as a compact `open_gate` or `research` fact without evidence.
   Use only host-accepted receipts; raw command output and invented hashes are
   not verification. Do not store raw prompts, transcripts, imports, or scratch
   content.
5. If a Curator tool call fails, report the failure and do not claim that the
   task or decision was saved. This server is bound to the active working
   directory, local OS account, configured V2 project ID, and exact durable
   grant. A workspace mismatch or missing grant must fail closed.
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="curatormd-v2-codex-mcp",
        description="Run a local Curator V2 server for the active Codex workspace.",
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument(
        "--evidence-config",
        type=Path,
        help="owner-only host evidence config outside the repository",
    )
    parser.add_argument("--allow-write", action="store_true")
    return parser


def _load_evidence_verifier(
    selected_path: Path | None, project_root: Path, project_id: str
) -> EvidenceVerifier | None:
    """Load only the owner-managed evidence sources for this configured project."""

    if selected_path is None:
        selected_path = Path.home() / ".config" / "curatormd-v2" / f"{project_id}-evidence.json"
        if not selected_path.exists() and not selected_path.is_symlink():
            return None
    host_path = validate_host_evidence_config_path(selected_path, project_root)
    return load_local_evidence_verifier(host_path, project_id=project_id)


def _codex_parent_workspace() -> Path | None:
    """Return the parent Codex process working directory on local Linux."""

    if not sys.platform.startswith("linux"):
        return None
    parent = Path("/proc") / str(os.getppid())
    try:
        process_name = (parent / "comm").read_text(encoding="utf-8").strip()
        if process_name not in {"codex", "codex-cli"}:
            return None
        return (parent / "cwd").resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None


def _workspace_root(selected: Path | None) -> Path:
    """Use the explicit root or nearest configured V2 project above cwd."""

    if selected is not None:
        return selected.expanduser().resolve(strict=True)
    roots: list[Path] = []
    codex_parent = _codex_parent_workspace()
    if codex_parent is not None:
        roots.append(codex_parent)
    roots.append(Path.cwd().resolve(strict=True))
    inherited_pwd = os.environ.get("PWD")
    if inherited_pwd:
        try:
            session_root = Path(inherited_pwd).resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            session_root = roots[0]
        if session_root not in roots:
            roots.append(session_root)
    for root in roots:
        for candidate in (root, *root.parents):
            if (candidate / CONFIG_FILENAME).is_file():
                return candidate
    raise ValueError("active workspace has no Curator V2 project config")


def _bound_codex_instructions(config: ProjectConfig) -> str:
    """Expose verified binding fingerprints for content-free acceptance records."""

    return (
        f"{CODEX_INSTRUCTIONS}\n"
        "Verified local project binding (server-enforced): "
        f"project_id={config.project_id}; "
        f"repository_fingerprint={config.repository_fingerprint}; "
        f"config_sha256={config.config_sha256}. "
        "These values are evidence metadata, not credentials or caller-supplied authority. "
        "For repository checks, use a host-configured repository_test receipt for "
        "the exact commit under review; raw command output or its hash is not a "
        "verification attestation."
    )


def main(argv: list[str] | None = None) -> int:
    """Serve only the project declared by the current workspace's V2 config."""

    try:
        if not protect_process_data():
            raise RuntimeError("local Codex privacy limits are unavailable")
        args = _parser().parse_args(argv)
        root = _workspace_root(args.project_root)
        database = args.database.expanduser()
        if not database.is_absolute():
            raise ValueError("database path must be absolute")
        if os.getuid() != os.geteuid():
            raise ValueError("set-user-ID execution cannot establish local identity")

        config = ProjectConfig.load(root)
        evidence_verifier = _load_evidence_verifier(
            args.evidence_config, config.project_root, config.project_id
        )
        store = CuratorStore(database)
        try:
            caller = AuthenticatedCaller(
                f"local-uid:{os.geteuid()}", profile_id="codex-local"
            )
            actions = {ProjectAction.READ}
            if args.allow_write:
                actions.add(ProjectAction.WRITE)
            authorizer = FingerprintBoundSQLiteProjectGrantAuthorizer(
                store,
                ProjectAuthorizationBinding.from_project_config(
                    config, frozenset(actions)
                ),
            )
            if not authorizer.authorize(caller, config.project_id, ProjectAction.READ):
                raise PermissionError("local account lacks an active project read grant")
            if args.allow_write and not authorizer.authorize(
                caller, config.project_id, ProjectAction.WRITE
            ):
                raise PermissionError("local account lacks an active project write grant")
            api = AuthenticatedCuratorAPI(
                {
                    config.project_id: ProjectPlugin.bind(
                        config, store, evidence_verifier=evidence_verifier
                    ),
                },
                authorizer=authorizer,
                limiter=SQLiteTokenBucket(store),
                dependency_readiness=RequestHostReadiness(),
            )
            server = build_mcp_server(
                api,
                caller,
                config.project_id,
                "codex-local",
                instructions=_bound_codex_instructions(config),
            )
            server.run()
        finally:
            store.close()
        return 0
    except Exception:  # pylint: disable=broad-exception-caught
        print(
            "Curator V2 Codex server could not bind the active workspace.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
