# Curator V2 consumer repository operations, version 1

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
5. Before the first MCP call, use the attended `curatormd-v2-access` command
   documented in [`mcp-tools-v1.md`](mcp-tools-v1.md#durable-local-project-access)
   to register the exact repository/config and grant only `read` to the
   configured profile subject. Registration and grants are not inferred from
   `--profile-id` and are never self-created by the launcher.
6. Validate the consumer TOML and backend API version, run Hermes config
   validation, and test the MCP handshake for that profile. Read `goal_list`,
   `event_queue_status`, and `project_health`; an empty ledger is not evidence
   of event capture, and `unknown` health is correct until every required host
   probe is supplied and fresh.
7. Enable `--allow-write` only after the attended access command grants exact
   `write` access to the configured profile subject. Grant `review` separately
   and add `--allow-review` only when that profile needs review-gated inventory,
   canonical persistence, SDE disposition, or archive approval. Both flags are
   upper bounds and neither creates grants. Purge retry, hold release, and event
   retry retain separate grants. `--profile-id` is an operator assertion, not
   authentication. A production host must replace local UID administration
   and profile assertions with verified identity and project authorization.

## Review one local alpha candidate

The attended `curatormd-v2-review` command is for local alpha use under the
selected Linux account only; for the current alpha, that account is `eaglesvn`.
Register the exact project and grant that account both `read` and `review`
using `curatormd-v2-access`. The reviewer CLI checks
the account's effective UID, requires a visible interactive terminal, and
uses the configured global database plus this consumer's validated project
config. Do not grant review to a Hermes profile with `Auth: none`.

List pending candidates:

```sh
curatormd-v2-review \
  --project-root /absolute/path/to/consumer \
  --database /absolute/private/path/to/curator.sqlite3 \
  queue
```

Review one candidate:

```sh
curatormd-v2-review \
  --project-root /absolute/path/to/consumer \
  --database /absolute/private/path/to/curator.sqlite3 \
  review CANDIDATE_ID
```

The command displays selected facts, the complete hashed staging inventory,
and the canonical Markdown target. The approve/reject action records only SDE
disposition. After canonical facts and that receipt are written, the command
displays the exact inventory again and asks for a separate cleanup approval
bound to its manifest hash. The plugin re-scans before recording approval and
projects that approval receipt before purge. Held artifacts stay in place;
incomplete or changed inventories fail closed. Use `--target` only
when the consumer config has more than one canonical target. The local UID
binding does not authenticate Hermes sessions or close production identity,
retention-policy, scheduling, or deployment gates.

For each task, capture the user-approved problem, source checklist item, and
observable success criteria before implementation. Record concise typed fact
bullets during work; at handoff, leave incomplete criteria open with the
evidence still needed and a concrete next action. A runtime turn ending is not
goal completion evidence. SDE disposition, canonical persistence, and artifact
purge are not automatic consequences of a goal update. In the local attended
review CLI, one decision authorizes cleanup of the displayed exact inventory;
canonical persistence still completes before purge begins.

## Inspect expiry eligibility

The project-review-authorized MCP operation
`project_expiry_inventory_discover` reports and hashes the exact inventory of
unheld staged files that are ready for expiry. Files become eligible promptly
after compact facts are recorded following publication and any related SDE is
approved or rejected. Pending SDE review delays prompt expiry but does not
extend the hard 72-hour maximum age; at that ceiling, transient sources may
expire while their SDE remains reviewable from canonical facts. If no
record/disposition event makes an artifact ready sooner, it reaches that
threshold after 72 hours. Every file must have matching V2 producer age metadata; any unknown
age or incomplete filesystem scan withholds the entire eligible list.

Run the attended local review command to display the exact inventory and
confirm its hash. It requires visible input, output, and error terminals, and
the current Linux UID must hold project `read` and `review` grants. The same
explicit confirmation approves only the displayed inventory; V2 records the
reviewer and receipt before deleting any file. Active legal or operational
holds are omitted from eligibility and checked again before each deletion.
Failed deletions remain `purge_pending` with retry backoff.

```sh
curatormd-v2-review \
  --project-root /path/to/consumer \
  --database /path/to/private/curator-v2.sqlite3 \
  expire
```

To retry a prior approval receipt, pass its ID. This command cannot authorize a
new inventory:

```sh
curatormd-v2-review \
  --project-root /path/to/consumer \
  --database /path/to/private/curator-v2.sqlite3 \
  expiry-retry RECEIPT_ID
```

This flow is local-alpha behavior. Immediate expiry after compact facts and SDE
disposition, authenticated Hermes reviewer identity, production retention
policy, and live scheduling remain separate gates.

## Run one due-purge retry pass

The package includes a one-shot scheduler entrypoint for transient SDE and
expiry purge failures. It can process only targets whose immutable attended
receipt exists, whose retry deadline has elapsed, and whose retention hold is
absent or explicitly released. The project plugin serializes each pass with its
staging lock. It does not create or change review decisions, override backoff,
inspect other projects, or run the host router. Output reports separate
aggregate SDE and expiry counts without paths or receipt contents.

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
Keep production and broadly enabled V2 capture disabled until the retention and
recovery policy is approved. The bounded Vhost Manager local alpha hook is
limited to session/goal lifecycle metadata and excludes prompt/response content;
do not broaden its event scope or enable destructive cleanup without the same
policy approval.

## Run one bounded event-router pass

The package includes an explicit one-shot router command. It requires
`--route-events`, a private absolute database path, and one or more trusted
consumer roots. Repeat `--project-root` for every project the pass may process;
events for projects not in that fixed list remain untouched in the shared inbox.
The batch limit is 1–1000. The command emits content-free aggregate counts and
returns nonzero when bound-project events remain pending/quarantined or a claim
is lost.

```sh
curatormd-v2-router \
  --database /absolute/path/to/private/curatormd-v2.sqlite3 \
  --project-root /absolute/path/to/consumer-a \
  --project-root /absolute/path/to/consumer-b \
  --batch-limit 100 \
  --route-events
```

This runs one bounded pass only. It does not start a worker, timer, production
scheduler, or alert delivery. Do not run it with a partial project map as a
substitute for the trusted production router configuration.

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
  producer streaming, `curatormd-v2-maintenance` for an explicitly enabled,
  bounded due-purge retry pass, `curatormd-v2-review` for attended local-UID
  SDE review under exact grants, and `curatormd-v2-router` for an explicitly
  enabled, bounded one-shot event pass over named project bindings.
  `curatormd-v2-storage` creates integrity-checked backups and restores only
  to an explicitly confirmed new path; it does not switch the active database.
- Not established by install or handshake: authenticated Hermes identity,
  runtime event mapping, continuously operated global routing, installed
  scheduling/alerts,
  source-specific producer integration, evidence-source verification, review
  identity, cross-project isolation in a deployed host, or truthful production
  monitoring.
- Keep capture disabled until the consumer owner and Hermes Core owner approve
  the identity, retention, event, review, and recovery policies and the
  corresponding release gates have direct runtime evidence.
