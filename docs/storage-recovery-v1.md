# Curator V2 local SQLite recovery procedure, version 1

**Status: approved local development procedure.** SQLite is authoritative;
consumer Markdown is a readable projection. On mismatch, preserve both and
require `eaglesvn` to review before rebuilding Markdown from SQLite. Never
restore SQLite from Markdown automatically.

## Guarantees of the helper

`curatormd_v2.backup_database(source, destination)` takes a SQLite online
snapshot, verifies `integrity_check` and `foreign_key_check`, and installs the
result at a new path with mode `0600`. The destination is created atomically
without replacing an existing file. The source remains openable and is not
modified by the helper.

`curatormd_v2.restore_database(backup, destination)` applies the same checks to
an existing snapshot and restores it to a new path. It never restores in place
or overwrites an existing path. Both operations reject symlink paths, and
temporary snapshot files are private and removed after failed operations.

The `curatormd-v2-storage` command exposes these operations without printing
database paths or raw SQLite errors:

```sh
curatormd-v2-storage backup \
  --database /private/curator.sqlite3 \
  --destination /private/backups/curator.sqlite3

curatormd-v2-storage restore \
  --backup /private/backups/curator.sqlite3 \
  --destination /private/recovery/curator-review.sqlite3 \
  --restore-to-new-path
```

Restore requires the explicit `--restore-to-new-path` confirmation. Both
commands refuse existing destinations and report only the operation and
verification status. A successful restore creates an isolated review copy; it
does not authorize switching the live system to that copy.

The six-hour local maintenance service creates one online backup per
UTC day under `<database-directory>/backups/`. The directory and backup files
are private to the Curator OS account. After a new backup passes both SQLite
integrity checks, older dated backups are pruned so the newest seven daily copies remain. A
failed backup leaves existing copies untouched and stops that maintenance pass.
The pass reports only `backup_status: verified`; it never prints the path.

Restore is never scheduled. `eaglesvn` must select the exact backup and run the
explicit restore command to a new path. Curator does not replace the active
database or switch the local service to the restored copy.

Example from a Python maintenance process:

```python
from curatormd_v2 import backup_database, restore_database

backup_database("/private/curator.sqlite3", "/private/backups/curator-2026-10-18.sqlite3")
restore_database(
    "/private/backups/curator-2026-10-18.sqlite3",
    "/private/recovery/curator-review.sqlite3",
)
```

The immediate destination directory is created with owner-only permissions if
missing; existing directories are not chmodded, and ancestor permissions remain
the caller's responsibility. The temporary snapshot and destination must be on
the same filesystem because the final install uses an atomic hard link. If that
operation is unsupported, it fails closed and does not fall back to an
overwrite-capable copy.

## Local recovery fixture map

These references map current source-level fixtures to their evidence boundary;
they are not a fresh test run or a production-readiness result.

| Scenario | Fixture reference | What it covers | What remains open |
| --- | --- | --- | --- |
| Consistent online snapshot and restore to a new path | [`tests/test_backup.py`](../tests/test_backup.py), `test_backup_and_restore_are_consistent_private_and_non_overwriting` | A goal/fact snapshot is internally consistent, private, and does not include writes made after the snapshot; existing destinations are preserved. | Concurrent production writers, off-host backup integrity, and restore authorization. |
| Corrupt snapshot, destination race, and symlink paths | [`tests/test_backup.py`](../tests/test_backup.py), `test_corrupt_snapshot_is_rejected_without_creating_restore_target`, `test_concurrent_destination_creation_preserves_winner_and_cleans_temp`, `test_symlink_sources_and_destinations_are_rejected` | The corrupt input is retained, no restore target or leaked temporary is left, a concurrent destination wins without overwrite, and symlink paths fail closed. | Filesystem/device failure and unsupported production filesystems. |
| Migration rollback and newer-schema refusal | [`tests/test_migrations.py`](../tests/test_migrations.py), `test_failed_migration_rolls_back_ddl_data_repairs_and_version_stamp`, `test_newer_schema_version_is_refused_without_downgrade` | Injected migration failure leaves the old schema/data/version in place; an unsupported future version is not downgraded. | Production upgrade/rollback on deployment data and an approved version-support window. |
| SQLite/Markdown drift and interrupted projection receipt | [`tests/test_markdown_persistence.py`](../tests/test_markdown_persistence.py), `test_read_only_reconciliation_reports_missing_synced_and_divergent`, `test_projection_recovers_ledger_first_update_after_backup_restore`, `test_plugin_persists_review_receipt_before_releasing_purge_gate`, `test_recovers_projection_after_process_dies_before_receipt_commit` | Drift comparison is read-only; a restored backup can project a ledger-first update; a review receipt remains unpersisted and keeps artifacts untouched across backup/restore before projection, then completes on the restored store while the original database retains its unpersisted receipt; a worker process can terminate after Markdown replacement before receipt commit, and retry after database reopen reconciles the projection and receipt. | Power loss, owner-approved conflict resolution, and a production cross-store authority decision. |
| Delete succeeded before purge receipt update | [`tests/test_purge.py`](../tests/test_purge.py), `test_retry_recovers_crash_after_delete_before_receipt_update` | Reopening the store exposes `purge_pending`, and retry records the already-missing artifact as complete. | Host-level interruption, production filesystem behavior, and scheduler supervision. |
| WAL checkpoint blocked by reader and retried after restart | [`tests/test_event_payload_scrub.py`](../tests/test_event_payload_scrub.py), `test_busy_reader_keeps_scrub_pending_until_checkpoint_can_truncate`, `test_blocked_scrub_survives_restart_and_startup_retries_it` | A blocked checkpoint remains pending and startup retries it after the reader releases the WAL. | Process/power loss, production database load, and a deployed retry scheduler. |

Fixture presence establishes local scenarios encoded in the test source; this
document does not assert that the suite was run in the current work cycle. A
deployment drill must add process-level interruption, real storage/identity,
backup custody, event pause/resume, and cross-store recovery evidence.

## Operator sequence for a future deployment

1. Stop or pause event producers and obtain the deployment owner's approval for
   a recovery window. Record the source database path and incident/recovery ID.
2. Create a new verified snapshot with `backup_database`; retain the source
   database and its current WAL/SHM files. Do not copy only the main SQLite
   file while a writer is active.
3. Restore to a distinct, empty review path with `restore_database`. Do not
   replace, rename over, or open the active service path for write.
4. Open the restored database through `CuratorStore` in an isolated review
   process. Compare project IDs, goal/fact counts, event status, archive
   integrity, receipts, and expected goal reports with the recovery manifest.
   Integrity pragmas prove SQLite structure, not application-level correctness.
5. Separately inspect the affected canonical Markdown targets and purge
   receipts. `ProjectPlugin.reconcile_goal(goal_id, target)` can report whether
   one goal block is `synced`, `missing`, `divergent`, or `malformed`, with the
   expected and observed block hashes. This is read-only drift detection, not a
   recovery decision: it cannot prove which store is authoritative and must not
   be used to overwrite either side. New managed blocks include an unkeyed
   SHA-256 content checksum: projection rejects checksum mismatches and will not
   replace stale legacy blocks whose prior contents cannot be verified. An exact
   legacy block matching the current ledger may be upgraded. This detects
   accidental edits, not malicious rewrites by a party able to recompute the
   checksum. This helper includes no Markdown files,
   staging artifacts, secrets, logs, or backups.
   For the narrower known interruption where a goal block replacement succeeded
   but the SQLite receipt update did not, retry `persist_goal`; its deterministic
   upsert is idempotent and the purge gate remains closed until receipt persistence
   succeeds. This local failure-injection path is tested, but does not authorize
   automatic repair of hand-edited or otherwise divergent blocks.
6. Have the repository owner approve any service-path switch. Keep the original
   database and snapshot intact until the new deployment passes its own
   authorized read/write smoke test and a rollback point is recorded.

On any failed check, leave the original and snapshot untouched, preserve the
restored review copy for diagnosis if it was created, pause replay, and escalate
to the repository owner. Never delete receipts, inbox records, or canonical
Markdown to make counts match.

## Still-open recovery gates

- The local unversioned-to-v1 SQLite migration and its rollback fixture are
  described in [`schema-migrations-v1.md`](schema-migrations-v1.md); this is not
  a production migration or rollback drill.
- Approve, revise, or reject the proposed authority policy below and define
  deterministic conflict recovery. The current local comparator detects
  divergence but deliberately performs no repair.
- Define production migration support/version policy.
- Run restart, corruption, backup/restore, and recovery drills on the actual
  production storage and deployment identity.
- Define backup encryption, access control, retention, integrity manifests,
  off-host storage, restore authorization, and audit receipt requirements.
- Add Host Steward/operator observability without granting it Curator knowledge
  write authority.

### Owner decision checklist (proposed)

Before adopting the policy, the product and repository owners need to decide:

- Whether SQLite owns structured goal lifecycle, criteria, evidence references,
  facts, review decisions, and cleanup receipts; whether managed Markdown is
  solely a projection; and whether all unmarked text remains consumer-owned.
- How to handle edited, duplicated, missing, or orphaned managed blocks; which
  cases may use an authorized projection retry; and when a second reviewer is
  required before writes or purge resume.
- Whether a restored database can be activated when all managed blocks match,
  or whether additional application-level and event-cursor evidence is required.
- Which owner may pause producers, resolve a record conflict, authorize a
  database switch, and resume processing; how those decisions bind to the
  database and target digests.
- Which minimal incident, decision, and recovery receipts must be retained, who
  can read them, and their approved retention period.

### Authority options for owner review

These choices are design alternatives, not product decisions:

| Option | Authority model | Consequence |
| --- | --- | --- |
| A. Typed-ledger authority (current draft) | SQLite owns structured lifecycle, evidence, review, and purge state; consumers own unmarked Markdown; managed goal blocks project selected SQLite fields. | Fits current write direction. Human edits to managed blocks remain conflicts and are never imported as verification. |
| B. Markdown authority | Consumer Markdown owns managed goal content; SQLite is a derived workflow index. | Requires a bounded, provenance-preserving Markdown importer, explicit identity/revision rules, and new conflict, replay, and deletion tests. Current source renders and compares managed blocks but has no importer that treats Markdown as authoritative. |
| C. No automatic authority | Neither side is automatically preferred during a conflict; each mismatch is frozen for record-level owner adjudication. | Preserves both sides but requires durable conflict receipts and a manual repair procedure before writes or purge resume. |

The current proposal is Option A for structured fields combined with consumer
ownership of unmarked text. Owners may choose another option or define a
field-by-field model; the selected option, covered fields, and recovery path
must be captured in an approved, versioned decision before deployment use.

## Proposed authority and conflict policy (not approved)

This proposal is a design draft. It does not authorize a live-store switch,
Markdown overwrite, or cleanup:

- SQLite is authoritative for typed goal lifecycle, criterion evidence,
  immutable fact and review records, event dispositions, and purge receipts.
- A consuming repository owns its Markdown file and all unmarked text. A
  Curator-managed goal block is a projection of the corresponding SQLite goal;
  it is not an independent source for lifecycle state or evidence.
- A missing managed block may be regenerated only through the existing
  project-authorized projection operation. A divergent or malformed block
  freezes writes and purge for that target. Preserve the database, Markdown,
  and their hashes; do not choose a winner by timestamp or overwrite either
  side automatically.
- A repository owner must review the bounded comparison and approve a
  record-level resolution. Preserve the original target, make any repair to a
  new review copy, and reconcile it against SQLite before an authorized
  projection is installed. A human edit is not imported as a verified fact;
  new facts require the normal evidence and lifecycle path.
- A database restore remains isolated at a new path. It does not become active
  until an owner-approved recovery procedure verifies its records and the
  matching consumer projections, records a rollback point, and authorizes the
  service switch.

### Proposed recovery decision table

Use this table only as a review draft. It does not add automatic recovery
behavior to the local library:

| Observed state | Proposed operator action | Stop condition |
| --- | --- | --- |
| SQLite passes integrity checks and each managed block is `synced`. | Preserve the recovery snapshot and comparison hashes; resume only after the incident owner records the verification. | Any missing, divergent, malformed, or unscanned portion of the target. |
| SQLite passes checks and a managed block is `missing`. | Verify project, goal, target, and current SQLite revision; request owner approval, then use the project-authorized projection path and reconcile again. | The target changed since comparison or the project/goal binding is uncertain. |
| A block is `divergent` or `malformed`, or project inventory is incomplete. | Pause writes and purge for the affected target. Preserve both stores and hashes; prepare a restricted review copy and require a repository-owner decision before resolving the record. | No record-level decision, no complete inventory, or no auditable resolution receipt. |
| SQLite fails integrity checks, is unreadable, or has an unsupported schema version. | Keep it isolated; restore a verified backup to a new path and inspect it read-only. Do not reconstruct lifecycle state from Markdown or lower the schema version. | The restored copy fails integrity/application checks, migration support is unknown, or its expected project/goal set cannot be explained. |
| A restored database and its managed projections still disagree. | Keep the old database, restored copy, and Markdown target unchanged; escalate with the incident ID and bounded comparison. | Any proposed service switch or overwrite before owner approval and a tested rollback point. |

Before a production rehearsal, the owner must define the incident record fields
and receipt format, identify who may pause producers and approve a switch, and
exercise each row with disposable data. This procedure must not delete or
rewrite evidence to make the stores appear consistent.

### Proposed recovery record

The following bounded record is a review template, not an implemented receipt
schema. Keep it in the deployment's access-controlled operations system; do not
copy database contents, Markdown bodies, event payloads, or raw exception text
into Curator facts:

- **Identity and scope:** opaque recovery ID, project ID, recovery owner,
  affected database/target references, and start/end times.
- **Before-state evidence:** database schema version and snapshot digest;
  `integrity_check` and `foreign_key_check` outcomes; bounded project/goal
  counts; Markdown target digest, scan byte/marker counts, completeness, and
  per-goal reconciliation status/hash pairs.
- **Decision and authorization:** incident/reason code, selected recovery path,
  approver identity reference, approval receipt reference, and the exact database
  and projection revisions covered by that approval.
- **Actions and after-state:** operation IDs and times, source/restore snapshot
  digests, resulting schema/integrity outcomes, refreshed reconciliation
  statuses, and the authorized smoke-test result.
- **Rollback and handoff:** preserved pre-change snapshot reference, rollback
  point, switch decision, unresolved gates, named next owner, and next action.

The deployment owner must approve the final field set, access/retention policy,
and receipt linkage before the template is used for production recovery. A
missing approval, incomplete marker scan, or unmatched before/after digest
leaves the recovery outcome open.

The source currently implements read-only divergence reports and fail-closed
projection checks, not this complete owner-approved workflow. Product and
repository-owner review, conflict-resolution receipts, and deployment drills
remain open gates.
