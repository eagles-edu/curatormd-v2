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

## Backups and restore

The local six-hour maintenance run creates one verified online backup per UTC
day in the private Curator state directory. It retains the newest seven daily
copies and removes older copies only after the new snapshot passes SQLite
integrity checks. A backup failure leaves existing copies intact and stops that
maintenance pass before purge retries.

The host-authorized attended storage view also measures the sibling `backups`
directory without opening snapshot contents. It reports recognized daily-file
count, logical file bytes, and allocated disk bytes. The scan examines at most
32 entries and follows no symlinks. An unexpected entry, non-owner or
non-private snapshot, unsafe directory, read error, or scan overflow makes the
inventory incomplete or unavailable;
partial measurements must not be treated as a full total. This view is
observational only and never prunes, repairs, or verifies snapshots.

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

Live local-alpha restore (2026-10-28 13:14 UTC): the installed
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
