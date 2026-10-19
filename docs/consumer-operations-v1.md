# Consumer repository operations, version 1

Status: operator guidance for the local reference plugin and stdio launcher.
This is not a production deployment runbook or proof that a Hermes profile is
authenticated, that an event router is running, or that V2 capture is active.
The global backend belongs in this repository; each consuming repository owns
its `.curatormd-v2.toml`, project plugin binding, and canonical Markdown.

## Install one local profile binding

1. Confirm the consumer repository is a trusted Git worktree with the required
   project persistence files and read-only evidence sources. Do not copy its
   source, config, Curator state, or persistence records into this backend
   repository.
2. Create `.curatormd-v2.toml` from
   [`examples/curatormd-v2.toml`](examples/curatormd-v2.toml), set the unique
   project ID and repository-local paths, and set its owner-only mode (`0600`).
   Checklists and persistence targets must resolve inside that repository.
3. Choose a private absolute database path owned by the Hermes account. Use one
   local server instance per profile/repository pair. Do not share the launcher
   across principals or expose its stdio process as a network endpoint.
4. Add the launcher to that profile's operator-controlled Hermes config using
   the exact repository root, database path, and profile ID. Start without
   `--allow-write`; use the read-only binding first. The example command and
   authorization boundary are in [`mcp-tools-v1.md`](mcp-tools-v1.md#local-hermes-profile-launcher).
5. Validate the consumer TOML and backend API version, run Hermes config
   validation, and test the MCP handshake for that profile. Read `goal_list`,
   `event_queue_status`, and `project_health`; an empty ledger is not evidence
   of event capture, and `unknown` health is correct until every required host
   probe is supplied and fresh.
6. Before enabling `--allow-write`, review the exact profile-to-project binding
   and the profile's filesystem/process trust. This flag grants only local
   `read` and `write` actions for the configured project; it does not grant
   canonical persistence, SDE review, archive approval, purge, hold release, or
   event retry. `--profile-id` is an operator assertion, not authentication.
   A production host must replace both assertions with verified identity and
   project authorization.

For each task, capture the user-approved problem, source checklist item, and
observable success criteria before implementation. Record concise typed fact
bullets during work; at handoff, leave incomplete criteria open with the
evidence still needed and a concrete next action. A runtime turn ending is not
goal completion evidence. SDE disposition, canonical persistence, and artifact
purge are separately authorized operations; do not represent them as automatic
consequences of a goal update.

## Run one due-purge retry pass

The package includes a one-shot scheduler entrypoint for transient purge
failures. It can process only targets whose immutable review receipt exists,
whose complete artifact inventory and canonical-persistence proof are recorded,
whose retry deadline has elapsed, and whose retention hold is absent or
explicitly released. The project plugin serializes the pass with its staging
lock. It does not create or change review decisions, override backoff, inspect
other projects, or run the host router.

An operator-controlled service or timer may invoke the command with the
repository and shared-backend database paths pinned explicitly:

```sh
curatormd-v2-maintenance \
  --project-root /absolute/path/to/consumer-repo \
  --database /absolute/path/to/private/curatormd-v2.sqlite3 \
  --batch-limit 100 \
  --execute-due-purges
```

The execution flag is required. The command emits project ID and aggregate
processed/complete/pending counts only; exit code `1` means a processed receipt
is still pending and should trigger operator alert/reconciliation, while `2`
means startup or execution failed. The worker is a local one-shot mechanism,
not an installed systemd timer, production scheduler, or alert-delivery setup.
Use the same trusted account that owns the database, repository config, and
staging tree; never expose the command as an unauthenticated network service.
Keep V2 capture disabled until the retention and recovery policy is approved.

## Upgrade the backend or plugin contract

1. Select an explicitly reviewed backend revision and read its versioned
   contracts and migration notes. Do not track an unpinned working tree as a
   production dependency.
2. In a maintenance copy, run the locked test, type, and security checks from
   [`ci-v2.md`](ci-v2.md), then run the real consumer's config and plugin tests.
   Confirm the consumer's `backend_api_version` is supported. Unknown versions
   fail closed; do not edit the version merely to bypass startup validation.
3. Before a schema/database upgrade, stop producers through the host's approved
   maintenance process, make a verified online backup to a new path, and test
   restore to another new path. Follow
   [`storage-recovery-v1.md`](storage-recovery-v1.md); never replace the active
   database in place or copy only its main SQLite file while writers are live.
4. Keep the old backend, consumer config, database, and backup until the new
   profile passes its authorized read/write smoke test and its rollback point
   is recorded. A local unit test or MCP handshake alone is not a deployment
   acceptance test.

## Disable or roll back a profile binding

1. Record the exact profile, consumer project, config path, database path, and
   active-session state. Preserve a private rollback copy of the profile
   config. Do not delete the V2 database, receipts, review records, or canonical
   Markdown as part of disabling capture.
2. Disable/remove only that profile's V2 MCP entry using the host's supported
   configuration mechanism. Validate the edited config and inspect the
   profile's MCP listing. An on-disk change is not proof that an already-running
   gateway unloaded its MCP process or cached hooks.
3. Verify the profile cannot start or call the V2 server and that the V2 child
   process has exited. If this requires restarting a multiplexed gateway, use
   an operator-approved maintenance window after draining affected sessions;
   do not restart a shared gateway solely to make this check pass.
4. Keep the V2 database and consumer records unchanged. If restoring an earlier
   profile config, first confirm that the restored config cannot write to the
   V2 database under incompatible semantics. V1 inboxes and artifacts are
   separate: do not import raw V1 material, delete it, or reactivate V1 capture
   as an implicit rollback step.

## Recover data without overwriting evidence

Use the isolated backup/restore procedure in
[`storage-recovery-v1.md`](storage-recovery-v1.md). Restore only to a new
review path, inspect integrity and application-level records there, and
reconcile canonical Markdown read-only. The project owner must decide conflicts
before any production path switch; this repository has no approved automatic
conflict repair or production recovery authority.

## Current support boundary

- Supported here: strict repository config loading, the reference project
  plugin, local SQLite ledger, local stdio MCP launcher, explicit in-process
  authorization checks, `curatormd-v2-stage` for bounded stdin-only local
  producer streaming, and `curatormd-v2-maintenance` for an explicitly enabled,
  bounded due-purge retry pass.
- Not established by install or handshake: authenticated Hermes identity,
  runtime event mapping, global event routing, installed scheduling/alerts,
  source-specific producer integration, evidence-source verification, review
  identity, cross-project isolation in a deployed host, or truthful production
  monitoring.
- Keep capture disabled until the consumer owner and Hermes Core owner approve
  the identity, retention, event, review, and recovery policies and the
  corresponding release gates have direct runtime evidence.
