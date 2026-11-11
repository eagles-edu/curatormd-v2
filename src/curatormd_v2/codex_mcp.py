"""Local Codex MCP adapter for the active V2-configured workspace."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI, ProjectAction
from .cli_interaction import SafeArgumentParser, parse_safe_arguments
from .evidence import EvidenceVerifier
from .process_privacy import protect_process_data
from .mcp_server import RequestHostReadiness, build_mcp_server
from .hosted_mcp import validate_host_evidence_config_path
from .host_database_bindings import resolve_project_database
from .local_evidence_config import load_local_evidence_verifier
from .project_access import (
    FingerprintBoundSQLiteProjectGrantAuthorizer,
    ProjectBindingStartupError,
    ProjectAuthorizationBinding,
    require_active_project_action,
    require_active_project_read,
)
from .project_config import CONFIG_FILENAME, ProjectConfig
from .project_plugin import ProjectPlugin
from .rate_limiter import SQLiteTokenBucket
from .store import CuratorStore


CODEX_INSTRUCTIONS = """\
Curator V2 Codex workflow:
Codex uses the local OS identity and does not own a Hermes session. Do not call
`hermes_goal_bind` from this Codex adapter; only a real Hermes host may bind its
own session using host-injected profile and session metadata.
1. For every non-trivial work request, including code changes, inspection,
   debugging, and research, first derive one concise problem statement and
   observable success criteria. State them to the user as `Problem: <problem>.
   Success: <observable checks>.` Before creating a goal, page through the full
   `goal_list_page` result in pages of 10. Reduce each page to goal ID, status,
   saved problem, success checks, and parent ID; follow every `next_offset`.
   Compare only after every page is read, and never create from a truncated or
   partially reviewed list.
   Reuse one clear same-task match; ask which goal when multiple could match.
   Repository or topic similarity alone is not a match. A distinct bounded
   task within an active broader goal gets its own active child via
   `parent_goal_id`; an unrelated task gets a top-level active one-off. Keep
   each task's checks and facts on its own goal. Reuse the parent itself only
   when the request advances its saved criteria.
   `ootask:` explicitly means a distinct one-off with its own goal lifecycle;
   link it to a named parent only when it is a bounded task within that scope.
   `aatask:` is an aside unrelated to this repository and must not create or
   change this project's goals, facts, lifecycle, or SDEs; preserve existing work.
   `aotask <parent-or-child>:` means progress on that existing goal's scope and
   criteria; keep its same goal ID and do not start another goal.
   For an already-active match, read `goal_status`, record an intent/progress fact, and continue; never call
   `goal_start` or `goal_activate` for it. Activate a planned, deferred, or
   resolved blocked match only at its current revision. Do not attach unrelated work to the latest
   goal. For a plan, state this for the parent and again for each child when
   that child starts. For a one-off, state it once whether it is inside or
   outside a plan. Derive the wording from the saved goal fields. On retries
   and resumes reuse the same goal and wording; do not create duplicate goals
   or repeat a kickoff unless correcting it or the user asks. When no matching
   goal exists, create a one-off goal with `initial_status="active"` before
   analysis, commands, or edits. Formatting work is a task even when quick;
   a simple factual question need not create a goal. If the user asks for a
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
   the current result, calls `goal_finish` when its practical check passed,
   then prepares a pending SDE proposal from that completed goal's supported
   facts and confirms its goal ID and pending status with `sde_review_detail`
   before activating another plan item. For
   an `ootask` interrupting a plan child, resume that exact deferred child only
   when the user says to continue; do not skip to a later child. A one-off task
   ends at its own endpoint. An observed result or the owner moving on can
   indicate completion; missing automated evidence does not block it. If the
   outcome is uncertain, ask for guidance. "Pause", "hold", or "put it
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
   "mark it complete" applies the same `goal_finish` flow to a one-off task.
   Record one concise result fact; a separate summary artifact and report-page
   readback are not required. A request to
   "finish the plugin" or "complete this task"
   asks for work and does not report completion. Say "Beginning task tracking",
   "Pausing task tracking", or "Resuming task tracking" for the matching
   transition; report completion after its checks pass. Do not close unrelated
   goals. Before `goal_finish`, `goal_defer`, or `goal_activate`, read
   `goal_status` and pass its current lifecycle revision. `goal_report` accepts
   1-16 facts per page; use `fact_offset` to
   continue, never request a larger page.
3. Curator tracking is the default for every nontrivial task; do not ask the
   user to opt in or start a separate capture mode. Collect compact task facts
   as work proceeds. When `goal_finish` and `goal_status` confirm completion,
   prepare a pending SDE proposal from supported facts belonging to that goal.
   The proposal remains for owner review; Codex never approves or codifies it.
   Treat plan-item transitions and one-off task transitions alike. Use the
   visible cues "Beginning task tracking", "Pausing task tracking", and
   "Resuming task tracking". This bookkeeping is part of every tracked task.
   At a hold, record facts, reason, and next action; resume from that
   checkpoint. Use one practical success check per task. A relevant passing
   result, local check, or owner confirmation can be recorded as an outcome.
   Use `evidence_capture` when useful, but never require it for completion or
   a proposal. Keep unverified claims distinct from verified evidence. When `goal_finish` succeeds
   and `goal_status` confirms complete, create a pending proposal using only
   supported facts from that goal. The proposal is for owner review; the user decides what is
   memorialized, its importance, and the disposition. A completed task is not
   SDE approval. Never present unsupported facts as verified.
   For an explicitly relayed SDE, use `sde_record_user_report` on the active
   goal with a concise normalized report and a fresh operation ID. It records
   a `user_report` fact and creates a pending proposal without an artifact
   packet; it does not complete the goal or approve the candidate. Read it back
   with `sde_review_detail` and leave it pending.
   Claim saved facts or a candidate only after `fact_record`, `sde_assess`, or
   `sde_record_user_report` succeeds and a matching `goal_status`/`goal_report` confirms
   it is attached to that goal. Never approve/reject or codify on the user's
   behalf.
   A `goal_id` groups the task's facts across turns, pauses, threads, and
   intervening unrelated work. Append separated records to that same ID; the
   prompt-turn event ID only deduplicates a `goal_start` retry; never reuse it
   for a later operation or as the task ID. Give every later `fact_record`,
   lifecycle transition, and SDE operation its own fresh event ID. Reuse an
   operation's ID only when retrying that same operation with the same payload.
   Reuse the `goal_id` on resume; a plan child keeps its own ID and `parent_goal_id` links
   it to the plan. `sde_assess` accepts facts from its goal only and
   can propose facts from active or completed goals;
   never submit child fact IDs for a parent proposal. Keep the compact outcome
   fact and audit receipts. After the user's SDE approval, transfer approved
   facts to the pertinent persistence document and read it back to verify the
   saved content. Routine ledger facts can be removed
   from active history only through an exact `fact_compaction_propose` and
   owner-approved `fact_compaction_approve`; transient artifacts require the
   existing exact-inventory purge approval. Purge only the approved transient
   inventory and verify its receipt; reviewed fact archives remain recoverable.
   A task finish alone authorizes neither cleanup. After the user's SDE
   disposition, show the exact cleanup inventory. Delete only owner-approved
   transient artifacts; keep the compact outcome fact and audit receipts. Routine facts
   leave active history only through separately approved exact compaction and
   remain recoverable in the reviewed archive.
4. Record compact facts at task start, after changes/checks, and at the
   outcome. One concise fact can state the change and a passing local test/lint
   result or owner confirmation. Use configured evidence sources when useful,
   but do not require a host receipt for ordinary local checks. Never invent
   hashes or persist raw prompts, transcripts, imports, or scratch content.
5. If a Curator tool call fails, report the failure and do not claim that the
   task or decision was saved. This server is bound to the active working
   directory, local OS account, configured V2 project ID, and exact durable
   grant. A workspace mismatch or missing grant must fail closed.
"""


def _parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="curatormd-v2-codex-mcp",
        description="Run a local Curator V2 server for the active Codex workspace.",
    )
    database_route = parser.add_mutually_exclusive_group(required=True)
    database_route.add_argument(
        "--database",
        type=Path,
        help="explicit database for this workspace (single-project route)",
    )
    database_route.add_argument(
        "--database-bindings",
        type=Path,
        help="owner-only host map from exact project IDs to database paths",
    )
    parser.add_argument("--project-root", type=Path)
    parser.add_argument(
        "--evidence-config",
        type=Path,
        help="owner-only host evidence config outside the repository",
    )
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument(
        "--allow-purge-retry",
        action="store_true",
        help="allow only retries covered by an exact durable purge-retry grant",
    )
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
        "These values are evidence metadata, not credentials or caller-supplied authority."
    )


def main(argv: list[str] | None = None) -> int:
    """Serve only the project declared by the current workspace's V2 config."""

    try:
        if not protect_process_data():
            raise RuntimeError("local Codex privacy limits are unavailable")
        args = parse_safe_arguments(
            _parser(),
            argv,
            sys.stderr,
            "Curator V2 Codex server could not bind the active workspace.\n",
        )
        if args is None:
            return 2
        root = _workspace_root(args.project_root)
        if os.getuid() != os.geteuid():
            raise ValueError("set-user-ID execution cannot establish local identity")

        config = ProjectConfig.load(root)
        if args.database_bindings is not None:
            database = resolve_project_database(
                config.project_id, args.database_bindings
            )
        else:
            database = args.database.expanduser()
            if not database.is_absolute():
                raise ValueError("database path must be absolute")
        evidence_verifier = _load_evidence_verifier(
            args.evidence_config, config.project_root, config.project_id
        )
        store = CuratorStore(database)
        try:
            caller = AuthenticatedCaller(
                f"local-uid:{os.geteuid()}", profile_id="codex-local"
            )
            require_active_project_read(store, config, caller)
            actions = {ProjectAction.READ}
            if args.allow_write:
                actions.add(ProjectAction.WRITE)
            if args.allow_purge_retry:
                actions.add(ProjectAction.PURGE_RETRY)
            authorizer = FingerprintBoundSQLiteProjectGrantAuthorizer(
                store,
                ProjectAuthorizationBinding.from_project_config(
                    config, frozenset(actions)
                ),
            )
            if not authorizer.authorize(caller, config.project_id, ProjectAction.READ):
                require_active_project_read(store, config, caller)
                raise ProjectBindingStartupError("project-binding-changed")
            if args.allow_write:
                require_active_project_action(
                    store,
                    config,
                    caller,
                    ProjectAction.WRITE,
                    "project-write-grant-missing",
                )
                if not authorizer.authorize(
                    caller, config.project_id, ProjectAction.WRITE
                ):
                    require_active_project_action(
                        store,
                        config,
                        caller,
                        ProjectAction.WRITE,
                        "project-write-grant-missing",
                    )
                    raise ProjectBindingStartupError("project-binding-changed")
            if args.allow_purge_retry:
                require_active_project_action(
                    store,
                    config,
                    caller,
                    ProjectAction.PURGE_RETRY,
                    "project-purge-retry-grant-missing",
                )
                if not authorizer.authorize(
                    caller, config.project_id, ProjectAction.PURGE_RETRY
                ):
                    require_active_project_action(
                        store,
                        config,
                        caller,
                        ProjectAction.PURGE_RETRY,
                        "project-purge-retry-grant-missing",
                    )
                    raise ProjectBindingStartupError("project-binding-changed")
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
    except ProjectBindingStartupError as exc:
        print(f"CURATOR_STARTUP_ERROR={exc.code}", file=sys.stderr)
        return 2
    except Exception:  # pylint: disable=broad-exception-caught
        print(
            "CURATOR_STARTUP_ERROR=runtime",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
