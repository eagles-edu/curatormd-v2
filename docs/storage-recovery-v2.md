# Curator V2 local storage and projection recovery

**Approved local alpha procedure.** SQLite is authoritative for structured
goals, facts, review decisions, and cleanup receipts. Consumer
`persistence/HISTORY.md` is a readable projection. If they disagree, preserve
both, stop automatic projection and purge for the affected target, and ask
`eaglesvn` to review the bounded comparison. After review, SQLite may be
projected again through the authorized Curator operation. Never rebuild SQLite
from Markdown or switch to a restored database automatically.

## Backups and restore

The local six-hour maintenance run creates one verified online backup per UTC
day in the private Curator state directory. It retains the newest seven daily
copies and removes older copies only after the new snapshot passes SQLite
integrity checks. A backup failure leaves existing copies intact and stops that
maintenance pass before purge retries.

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
| Online backup, private restore, existing destination, corrupt backup, symlink, and destination race | [`tests/test_backup.py`](../tests/test_backup.py) | Snapshot is consistent and verified; restore never overwrites and invalid inputs remain available for review. |
| SQLite/Markdown comparison, projection retry, and interruption before receipt commit | [`tests/test_markdown_persistence.py`](../tests/test_markdown_persistence.py) | Comparison is read-only; retries reconcile the projection and receipt after reopen. |
| Purge interruption and retry after deletion before receipt update | [`tests/test_purge_lifecycle.py`](../tests/test_purge_lifecycle.py) | Pending work remains visible and exact retry records the already-absent target. |
| Blocked WAL cleanup across restart | [`tests/test_event_payload_scrub.py`](../tests/test_event_payload_scrub.py) | Cleanup stays pending while a reader blocks truncation and is retried after restart. |

The local failure-injection matrix and backup suites are run and recorded in
[`curator-v2-plan.md`](curator-v2-plan.md). These tests cover the local SQLite
and filesystem adapters; they do not promise host power-loss durability.
