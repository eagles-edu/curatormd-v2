# Curator V2 local SQLite recovery procedure, version 1

**Status: local-library procedure only.** This is not an approved production
runbook. It does not reconcile SQLite with canonical project Markdown or
authorize switching a live service to a restored database.

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
- Decide whether SQLite or project-owned Markdown is authoritative when they
  disagree, and define deterministic conflict recovery. The current local
  comparator detects divergence but deliberately performs no repair.
- Define production migration support/version policy.
- Run restart, corruption, backup/restore, and recovery drills on the actual
  production storage and deployment identity.
- Define backup encryption, access control, retention, integrity manifests,
  off-host storage, restore authorization, and audit receipt requirements.
- Add Host Steward/operator observability without granting it Curator knowledge
  write authority.
