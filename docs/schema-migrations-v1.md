# SQLite schema migration policy

**Status: local migration behavior is implemented and tested; production
upgrade/rollback support is not approved.** SQLite's `PRAGMA user_version` is
the database schema version. The current supported value is exported as
`SQLITE_SCHEMA_VERSION` and is `13`.

## Version 1 migration

Databases created before schema versioning have `user_version = 0`. Opening one
with `CuratorStore` runs the legacy table/column creation, column additions,
criteria backfill, and receipt-state repair in a single SQLite write
transaction. The `user_version = 1` stamp is written only after all migration
work succeeds. Fresh databases continue through the ordered v2, v3, v4, v5, v6,
v7, v8, v9, v10, v11, v12, and v13 migrations below before the store is
exposed.

If any DDL or data repair fails, the transaction rolls back. Store construction
closes its SQLite connection before propagating the error. On the next open, the
database remains at version zero and can be retried after the underlying issue
is repaired. The migration tests inject a trigger failure after schema changes
have begun, then check the original columns/data, absence of partial tables,
and unchanged `user_version` before retrying successfully.

Opening a database whose `user_version` is greater than the implementation's
supported version raises an error and does not lower the version or attempt a
downgrade. A migration from a nonzero version without an explicit path is also
rejected. Future schema changes must add an ordered migration step and a
fixture for every supported prior version before increasing the constant.

## Version 7 migration

Version 7 adds nullable `goals.initial_status` and `goals.source_event_id` plus
a partial unique index for project/source-event pairs. New goals persist the
state at intake and the originating event ID when one exists; recognized
sensitive patterns are rejected before the ID is stored, and the report shows
these alongside project, owner, and checklist revision. The migration leaves
both fields null on old rows instead of guessing their historical intake state
or associating an event by inference. The v6-to-v7 fixture checks legacy goal
preservation and verifies new intake metadata can be written after migration.
This retains only bounded identifiers and status metadata, never the event
payload or request transcript.

## Version 8 migration

Version 8 adds `facts.verification_attestations_json`, a bounded JSON array
containing compact host-authenticated provenance for each newly accepted
verification fact. Existing facts receive the empty-array default; migration
does not invent a runner, reviewer, repository revision, or other historical
identity. A legacy verification fact remains visible as history but cannot
satisfy a current criterion until freshly verified through an injected trusted
verifier. The v7-to-v8 regression verifies fact identity and bullet
preservation, the default empty provenance, and fail-closed criterion status
after migration.

## Rollback boundary

There is no reverse SQL migration for versions 1 through 9. Rollback means
preserving the original database and restoring a verified backup to a new review path using
the procedures in [`storage-recovery-v1.md`](storage-recovery-v1.md). Switching
a live service to that path requires deployment-specific owner approval and a
separate smoke test. The tested local fixture does not prove production
migration safety, cross-store consistency, or a deployment rollback drill.

## Evidence

- [Migration implementation](../src/curatormd_v2/store.py)
- [Migration fixtures](../tests/test_migrations.py)
- [Legacy fact-archive upgrade regression](../tests/test_fact_compaction.py)
- `uv run --locked --group test python -m unittest tests.test_migrations tests.test_fact_compaction -v`

## Version 2 migration

Version 2 adds durable-router metadata: per-event delivery attempts, producer
identity and optional sequence columns, a source-order index, and an operator
retry-audit table. Opening a version-1 store applies these changes inside the
schema transaction and stamps version 2 only after success. Existing event
receipts remain intact; legacy rows receive `attempts = 0`, the `unspecified`
producer ID, and no sequence. New unversioned stores run the v0 upgrade and
v1-to-v2 upgrade atomically in the same opening transaction.

The regression fixture downgrades a local v2 database to the v1 shape, reopens
it, and checks receipt digest/status preservation, defaulted metadata, audit
table creation, and the version stamp. It does not constitute a production
migration or rollback drill.

## Version 3 migration

Version 3 adds per-artifact `created_at` and `last_attempt_at` fields plus an
index for purge-queue age inspection. Existing targets are backfilled with the
parent audit receipt's creation timestamp; their attempt count and pending or
failed state remain unchanged, and `last_attempt_at` starts as null. New
attempts increment and timestamp durably before filesystem deletion begins, so
a process exit after deletion cannot erase evidence that an attempt occurred.
Fresh databases and upgrades from v0, v1, and v2 apply the ordered migrations
atomically. The migration fixture verifies the v2-to-v3 backfill and preserves
the receipt and target state.

## Version 4 migration

Version 4 adds nullable `event_inbox.next_attempt_at` and an index for due retry
selection. When delivery fails with a retained payload, the store records a
retry time using capped exponential backoff: 5 seconds after the first failure,
then 10, 20, and so on up to 900 seconds. Processed events and operator-released
quarantined events clear the schedule. Legacy failed receipts receive null and
remain immediately eligible, avoiding an invented delay during upgrade. The
field is included in retained logical-byte accounting. The migration fixture
verifies v1/v2 stores reach the current version and preserve prior receipts and
purge targets.

## Version 5 migration

Version 5 adds nullable `lease_owner` and `lease_expires_at` fields and an
expiry index for the event inbox. A router atomically claims due, in-order
events inside a SQLite write transaction. Only the matching unexpired owner may
commit a claimed event as processed or failed; crashed claims become eligible
after expiry, and normal completion/failure clears the claim. Queue status
reports aggregate active and expired claim counts without exposing event IDs.
Existing v4 retry deadlines are preserved, and legacy rows without claims
remain immediately eligible. The tests exercise v4-to-v5 retry preservation and
two-connection claim/reclaim behavior. This is local database coordination, not
evidence of a production scheduler or deployed worker topology.

## Version 6 migration

Version 6 adds nullable `purge_targets.next_attempt_at` and an index for due
purge selection. When an artifact purge fails, the store persists a capped
exponential retry deadline (5 seconds, doubling to a 900-second ceiling).
Legacy failures with no deadline remain immediately due. Starting an attempt
clears the prior deadline before touching the file, so a process exit after
deletion remains immediately recoverable; success also clears the deadline.
The bounded scheduler-facing `retry_due_purges` pass selects only receipts
whose inventory and canonical-write gates are complete and which have at least
one due artifact. The authenticated explicit `retry_pending_purges` operation
remains an immediate human override. The v5-to-v6 fixture verifies that pending
targets are preserved and are immediately eligible. This is local retry
behavior, not a running scheduler, alert integration, or dead-letter policy.

Production backup retention, migration signing/review, backup encryption,
schema support windows, irreversible data-transform approval, and live rollback
remain open release gates.

## Version 9 migration

Version 9 adds nullable `purge_targets.retention_hold` and an index for
hold-aware purge-queue scans. Existing artifacts remain unheld and preserve
their prior status. New artifacts may be explicitly marked `legal` or
`operational`; the target is stored with status `held`, excluded from scheduled
and explicit retries, and keeps its receipt in `purge_pending`. Version 10 adds
hold-release authorization and audit. There is no automatic expiry or implicit
release.

## Version 10 migration

Version 10 adds nullable hold-placement and hold-release audit fields to
`purge_targets`: placement timestamp and reviewer, release timestamp and actor,
and release rationale. Existing v9 holds retain their class and remain held;
historical actor/time values are left unknown rather than inferred. The hold
queue index now includes `hold_released_at`, allowing purge selectors to include
only unheld or explicitly released targets. A release records its audit fields
in one transaction before filesystem purge is attempted. Migration never
expires or releases a hold.

## Version 11 migration

Version 11 adds the local durable project registry, append-only registry audit,
exact project/action grants, and separate grant-revocation records. A project
binds one opaque project ID to a host-supplied repository fingerprint, config
SHA-256, and backend API version. The fingerprint and config digest are shape-
validated only; this migration does not authenticate or derive them. Existing
goal and event rows are left untouched and are not implicitly registered or
granted access. Suspended registrations deny all persisted grants without
deleting grant history. Revocation preserves the original grant and a separate
actor/rationale/timestamp record; a later grant creates a new immutable ID.
The v10-to-v11 fixture verifies transactional table creation and the schema
version stamp. Host identity verification, project-root fingerprinting policy,
operator authorization, and production migration approval remain open.

## Version 12 migration

Version 12 adds a bounded, append-only `sde_quality_feedback` table for one
human-authenticated label per reviewer and decided candidate. Existing SDE
decisions are not converted into feedback labels; historical quality is
unknown. The migration adds a project-query index and performs no data rewrite
or purge. The v11-to-v13 fixture verifies the final schema stamp, an empty
feedback table, and no inferred limiter identities. These labels are explicit
human QA observations, not ground truth, model output, or a training signal.
Feedback retention and evaluation policy still require owner approval.

## Version 13 migration

Version 13 adds a bounded `request_rate_buckets` table keyed by opaque
subject/project IDs, with token balance and wall-clock timestamps, plus an idle
index for bounded cleanup. No historical identity or request data is imported.
The migration runs in the same transaction as the schema version update; local
tests verify v12 upgrade and rollback when an incompatible table prevents index
creation. The table is used by the local stdio `SQLiteTokenBucket` to coordinate
requests across processes sharing one SQLite file. This is same-host local
coordination only; it is not a distributed limiter or a production quota policy.
