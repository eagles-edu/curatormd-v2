# Curator V2 local storage and projection recovery

**Approved local alpha procedure.** SQLite is authoritative for structured
goals, facts, review decisions, and cleanup receipts. Consumer
`persistence/HISTORY.md` is a readable projection. If they disagree, preserve
both, stop automatic projection and purge for the affected target, and ask
`eaglesvn` to review the bounded comparison. After review, SQLite may be
projected again through the authorized Curator operation. Never rebuild SQLite
from Markdown or switch to a restored database automatically.

Owner confirmation (2026-10-28): keep seven daily copies in the private Curator
state directory. A restore requires `eaglesvn` to select the backup and
destination and review it before use; Curator must never overwrite or switch
the live database automatically.

Owner confirmation (2026-10-28): those seven snapshots may retain raw event
payloads whose inbox status is still pending retry or quarantine. This extends
the backup copy's lifetime beyond the 72-hour limit for live transient source
files. Each snapshot is retained only while it is among the newest seven daily
copies, but a payload that remains pending can be copied into each new backup,
so the rolling set has no fixed maximum age for unresolved payloads. Once the
live payload is scrubbed, snapshots containing it roll out within seven days.
The payload remains operational recovery data, not canonical knowledge;
processed event backups retain only the digest receipt after payload scrubbing.

Owner confirmation (2026-10-29): failed or quarantined inbox payloads may
remain in SQLite until the event is processed or explicitly resolved; they
must not be discarded solely because of age. The seven-copy rotation may
continue carrying unresolved payloads. Processing or explicit resolution
scrubs the live payload; snapshots containing it then roll out within seven
days. This is an approved recovery exception to the 72-hour live transient-file
limit and is not canonical knowledge. Existing hard capacity limits remain in
force.

## Current local-alpha storage census (2026-10-29)

This is a content-free snapshot of the configured `vhost-manager-alpha` ledger.
The profile-bound `project_storage_usage` read and host-authorized access view
are separate because project grants do not authorize control-plane storage
details. A query-only SQLite metadata read reported schema version 38,
`quick_check=ok`, and 30 application tables. Logical bytes count stored record
fields and payload bytes as documented by the source queries; they are not
SQLite allocation. Physical B-tree allocation includes each table's indexes.

| Data class and tables | Rows | Logical bytes | Physical B-tree bytes |
| --- | ---: | ---: | ---: |
| Goals and criteria (`goals`, `goal_criteria_versions`; 31 goals and 31 criteria versions) | 62 | 22,474 | 53,248 |
| Facts (`facts`) | 28 | 8,794 | 32,768 |
| Approved archives (`fact_archives`, `fact_archive_items`) | 0 | 0 | 28,672 |
| SDE/review/cleanup (`sde_candidates`, `sde_corrections`, `sde_quality_feedback`, `audit_receipts`, `purge_targets`, `cleanup_authorizations`) | 0 | 0 | 81,920 |
| Event receipts and replay state (`event_inbox`, `event_retry_audit`, `event_payload_scrub_queue`, `event_cursors`, `terminal_event_dispositions`) | 71 | 23,683 | 151,552 |
| Artifact/expiry metadata (`staging_artifact_occurrences`, `staging_artifact_times`, `expiry_purge_receipts`, `expiry_purge_targets`) | 0 | 0 | 45,056 |
| Project access and rate limits (`consumer_bindings`, `consumer_binding_audit`, `consumer_drain_sessions`, `consumer_drain_events`, `project_retirement_tombstones`, `project_registry`, `project_registry_audit`, `project_grants`, `project_grant_revocations`, `request_rate_buckets`) | 14 | 3,145 | 114,688 |
| **Totals** | **175** | **58,096** | **507,904** |

The event-class total includes 70 inbox receipts, one cursor, and zero rows in
the other three tables. Its logical bytes are 23,559 for inbox records plus
124 for the cursor. The event payload source-byte total is 47,281; zero source
payload bytes remain in the live inbox. The global inbox cap is 250,000
receipts or 134,217,728 retained logical bytes, whichever is reached first;
this snapshot uses 70 receipts and 23,559 bytes. The access-class logical total
is the sum of the 11 content-free per-class values in the authorized view.

SQLite reports a 540,672-byte main file: 507,904 attributed B-tree bytes plus
32,768 unattributed/shared bytes. The WAL measured 284,312 bytes during the
project read and changes as writers/checkpoints run. These are global file
sizes, not per-project or per-table capacity. The backup scan observed 32
entries, 5,215,696 file bytes, and 5,259,264 allocated bytes, but could classify
only two managed daily snapshots (1,064,960 bytes); 30 files remain
unclassified. The measured size is below the approved 262,144,000-byte
warning-only backup-tree threshold. No legacy entry was read, moved, or removed.
At 2026-10-29 16:35 +07, a separate no-follow metadata walk grouped the 30
non-daily files by type and suffix: three older SQLite snapshots, ten WAL/SHM
sidecars, five rollback archives, one YAML file, one VS Code settings file,
and eight nested files in two extension-backup directories (two JavaScript,
two JSON, two Markdown, and two suffixless files). Twelve entries are not
owner-only. A 2026-10-29 20:13 +07 header-only listing of the five `.tar.gz`
archives counted 455 regular members: 211 `.py`, 189 `.pyc`, 10 `.txt`, eight
`.json`, and 37 suffixless files. No member names containing `codex`,
`proposal`, `transcript`, `chat`, or `history` were found; names were not
retained, and no member payload was extracted or read except for the standard
package metadata headers. All five metadata headers identify the distribution
as `curatormd-v2` version `0.1.0a1`; all 211 `.py` members are under the
`curatormd_v2` package path, and there are no other Python source files. This
classifies them as Curator V2 package/source snapshots, not raw transcript or
proposal collections. The exact source revisions and contents of the text and
suffixless members remain unknown. It does not justify permission changes or
make the V2 managed-snapshot inventory complete.

| Class | Retention/replay rule | Current limit or alert | Recovery source |
| --- | --- | --- | --- |
| Goals, criteria, facts, archives, SDE/review/cleanup decisions and receipts | Keep durable records until `eaglesvn` approves cleanup of an exact inventory; never auto-prune. Event-backed facts retain their source event reference. | Facts: 10,000/project and 16 MiB/project; archives: 64 MiB/project. No separate row cap is implemented for every receipt class. | Verified daily SQLite snapshot; restore manually to a new path. Fact archives additionally retain the approved, hash-verified compacted source. |
| Event receipts, cursors, retry audit, scrub queue, terminal dispositions | Keep receipts, archive decisions, and replay cursors until exact approved cleanup. Keep failed/quarantined source payloads until processed or explicitly resolved; age alone does not discard them. | Active inbox: 250,000 unarchived receipts / 128 MiB active logical row bytes. Event payload input: 16 KiB/event. Archive rows remain in SQLite and in project logical totals; the shared database-plus-WAL warning is 250 MiB, warning only. | Source retry/redelivery while pending; verified SQLite snapshots. Resolved events scrub live payloads; copies roll out within seven days. Archived receipts keep their exact event ID and payload/idempotency hashes for replay matching. |
| Staging files and artifact/expiry metadata | Remove transient source files promptly after facts are recorded and SDE disposition completes, with a 72-hour live-file maximum. Honor explicit artifact holds. Keep durable cleanup receipts until exact approved cleanup. | Project staging: 250 MiB warning only, with warning at 75%; no file-count limit. Per-file/per-goal hard limits remain. | Exact staged-file manifest and purge receipts; reacquire from the producer if needed. SQLite backup preserves receipts, not staging file contents. |
| Project registry, grants, bindings, audits, drain history, retirement state | Keep access and lifecycle receipts until exact approved cleanup; retain source epoch/cursor state needed to reject stale replay. | Request-rate buckets: 10,000 rows with idle-only pruning. No other independent class threshold is implemented. | Verified SQLite snapshot and reviewed restore to a new path. |
| SQLite pages, indexes, WAL, and SHM | Shared storage for all classes; preserve the database and active sidecars together during recovery. | Warn when the main database plus WAL exceeds 262,144,000 bytes (250 MiB). Warning only: writes continue and Curator does not checkpoint, prune, or delete SQLite files; SQLite manages WAL checkpointing. Existing schema/inbox/fact/archive caps above remain in force. | SQLite online backup, integrity and foreign-key checks, then owner-reviewed restore to a new path. Never auto-switch the active database. |
| Backup tree | Keep newest seven verified daily snapshots. Legacy/unclassified files remain until an exact deletion inventory is reviewed. | 250 MiB allocated-byte warning only; never prune due to the warning. | Select a verified snapshot and restore to a new path. |

This census supplies current counts, logical sizes where the API defines them,
and physical table/index allocation for all 30 schema tables. It does not turn
shared page allocation into project data, identify the contents of unclassified
backups, or prove seven-copy rotation from the present directory scan. The
SQLite warning is policy-approved and displayed by the Curator V2 dashboard;
boundary behavior is covered by its focused test. This census is a schema-v38
runtime snapshot from its recorded observation time. Schema v39 adds six
archive-audit fields to `event_inbox`; source-level logical accounting includes
those fields, and archival leaves the receipts and references in place. The
alpha database has since migrated to schema 39; its current integrity and
foreign-key result is recorded in
[`local-alpha-evidence-2026-10-28.md`](local-alpha-evidence-2026-10-28.md).
This older census does not establish live archive-capacity recovery.

## Backups and restore

The local six-hour maintenance run creates one verified online backup per
`Asia/Ho_Chi_Minh` calendar day in the private Curator state directory. It
retains the newest seven daily copies and removes older copies only after the new snapshot passes SQLite
integrity checks. A backup failure leaves existing copies intact and stops
that maintenance pass before purge retries.

The host-authorized attended storage view also measures the sibling `backups`
directory without opening snapshot contents. It reports recognized daily-file
count, logical file bytes, and allocated disk bytes. The scan examines at most
32 entries and follows no symlinks. An unexpected entry, non-owner or
non-private snapshot, unsafe directory, read error, or scan overflow makes the
inventory incomplete or unavailable;
partial measurements must not be treated as a full total. This view is
observational only and never prunes, repairs, or verifies snapshots.

When the active inbox reaches its count or byte limit, new event IDs are
rejected before insertion; exact existing replays continue to return their
stored receipt. An attended reviewer can call `event_receipt_compaction_propose`
to inspect a bounded page of processed receipts whose source payloads have been
scrubbed. `event_receipt_compaction_archive` accepts only the exact event IDs,
offset, and manifest digest shown for the current proposal, requires the exact
project review grant, and records the reviewer, reason, digest, and archive ID
on those same SQLite rows. It marks the rows outside active inbox capacity but
does not delete or rewrite their receipt, payload hash, idempotency hash, retry
audit, terminal decision, or consumer-drain references. Exact replay still
resolves to the original processed receipt. A stale manifest, changed reference
count, or mismatched page is rejected atomically; review and retry must start
from a fresh proposal. No archive is automatic. Archiving frees active inbox
capacity but does not reduce SQLite file size; the warning-only shared size
threshold and reviewed backup/restore process remain the disk-recovery controls.

`curatormd_v2.backup_database(source, destination)` makes a consistent SQLite
online snapshot, verifies `integrity_check` and `foreign_key_check`, and installs
it at a new path with owner-only permissions. It refuses to overwrite an
existing destination or follow symlinks. `restore_database(backup, destination)`
uses the same checks and restores only to a new path. Restore is an attended
`eaglesvn` action; Curator never replaces the active database or switches the
service to the restored copy automatically.

The operator command is:

```sh
curatormd-v2-storage restore \
  --backup /private/backups/curator-v2.sqlite3 \
  --destination /private/recovery/curator-v2-review.sqlite3 \
  --restore-to-new-path
```

Choose the exact backup and review destination before running it. The command
refuses an existing destination and reports only operation and verification
status, not paths or raw SQLite errors.

## Recovery steps

1. Stop the action that produced the error. Do not approve new cleanup or retry
   purge against a mismatched projection.
2. Preserve the live database and its WAL/SHM files, the affected Markdown, and
   the relevant receipts. Do not copy only the main SQLite file while writers
   are active.
3. If SQLite opens, create a verified online snapshot. Check database and
   foreign-key integrity. If it does not open or fails integrity, preserve it
   and restore a selected daily backup to a distinct review path.
4. Open the review copy read-only for inspection. Compare project and goal
   records with their consumer projections using `project_reconcile` and
   `goal_reconcile`. These comparisons do not repair either side.
5. For a mismatch, keep both versions unchanged until `eaglesvn` reviews the
   bounded comparison. SQLite remains authoritative for structured fields;
   human-edited Markdown is not imported as verified data. After an explicit
   decision, use the authorized projection operation for the exact goal and
   target, then reconcile again.
6. Resume normal work only after the reviewed database and projection agree and
   required receipts are durable. A restored review copy does not replace or
   activate the live database by itself.

## Local verification evidence

| Case | Evidence | Result |
| --- | --- | --- |
| Online backup, private restore, existing destination, corrupt backup, symlink, destination race, and retry/quarantine payload recovery | [`tests/test_backup.py`](../tests/test_backup.py) | Snapshot is consistent and verified; failed and quarantined payloads survive restore and remain in each of the newest seven snapshots while pending; processed payloads are scrubbed, restore never overwrites, and invalid inputs remain available for review. |
| Bounded backup-directory accounting and authorized storage-view exposure | [`tests/test_backup.py`](../tests/test_backup.py), [`tests/test_project_access.py`](../tests/test_project_access.py) | Recognized backup count and file/allocated bytes are reported; unexpected entries are surfaced as incomplete; a read grant alone cannot access the host storage view. |
| SQLite/Markdown comparison, projection retry, and interruption before receipt commit | [`tests/test_markdown_persistence.py`](../tests/test_markdown_persistence.py) | Comparison is read-only; retries reconcile the projection and receipt after reopen. |
| Purge interruption and retry after deletion before receipt update | [`tests/test_purge_lifecycle.py`](../tests/test_purge_lifecycle.py) | Pending work remains visible and exact retry records the already-absent target. |
| Blocked WAL cleanup across restart | [`tests/test_event_payload_scrub.py`](../tests/test_event_payload_scrub.py) | Cleanup stays pending while a reader blocks truncation and is retried after restart. |
| Exact event-receipt page archive, stale-manifest rejection, review authorization, and replay | [`tests/test_event_payload_scrub.py`](../tests/test_event_payload_scrub.py), [`tests/test_api_goal_access.py`](../tests/test_api_goal_access.py), [`tests/test_mcp_client_workflow.py`](../tests/test_mcp_client_workflow.py) | Archiving moves only reviewed processed/payload-free receipts outside active capacity, keeps each durable receipt and its exact replay behavior, and rejects stale pages without partial updates. |

Live local-alpha restore (2026-10-28 20:14 +07:00): the installed
`curatormd-v2-storage` command restored the verified daily backup
`curator-v2-2026-10-28.sqlite3` to the new owner-only path
`/home/eaglesvn/.local/share/curatormd-v2-alpha/recovery-review-2026-10-28.sqlite3`.
The command verified SQLite integrity and foreign keys. The result is owned by
UID 1000 with mode `0600`; the active database hash was unchanged before and
after, and the restored copy was not activated. This verifies restore to a new
path for this local snapshot; it does not establish seven-copy rotation or
broader backup recovery behavior.

The local failure-injection matrix and backup suites are run and recorded in
[`curator-v2-plan.md`](curator-v2-plan.md). These tests cover the local SQLite
and filesystem adapters; they do not promise host power-loss durability.
