# SQLite schema migration policy

**Status: local migration behavior is implemented and tested; production
upgrade/rollback support is not approved.** SQLite's `PRAGMA user_version` is
the database schema version. The current supported value is exported as
`SQLITE_SCHEMA_VERSION` and is `34`.

## Version 1 migration

Databases created before schema versioning have `user_version = 0`. Opening one
with `CuratorStore` runs the legacy table/column creation, column additions,
criteria backfill, and receipt-state repair in a single SQLite write
transaction. The `user_version = 1` stamp is written only after all migration
work succeeds. Fresh databases continue through the ordered v2, v3, v4, v5, v6,
v7, v8, v9, v10, v11, v12, v13, v14, v15, v16, v17, v18, v19, v20, v21, v22,
v23, v24, v25, v26, v27, v28, v29, v30, v31, v32, v33, and v34 migrations below before the store is exposed.

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

All supported schema upgrades through version 29 run inside the store's SQLite
write transaction. A failed migration rolls back its schema/data changes and
does not advance `PRAGMA user_version`; the failure-injection fixtures exercise
this boundary. There are no reverse SQL migrations. An older application
version also refuses a database whose `user_version` is newer than it supports,
so pointing old code at an upgraded database is not a rollback procedure.

For a local review, preserve the source and restore a verified pre-upgrade
backup to a new path using [`storage-recovery-v1.md`](storage-recovery-v1.md).
Compare that copy and its consumer projections before any service switch.
Switching a live service requires a deployment-specific owner-approved
procedure, a recorded rollback point, and a separate smoke test. Production
migration safety, cross-store consistency, and a deployment rollback drill are
not established by local fixtures.

## Evidence

- [Migration implementation](../src/curatormd_v2/store.py)
- [Migration fixtures](../tests/test_migrations.py)
- [WAL scrub fixtures](../tests/test_event_payload_scrub.py)
- [Legacy fact-archive upgrade regression](../tests/test_fact_compaction.py)
- `uv run --locked --group test python -m unittest tests.test_migrations tests.test_event_payload_scrub tests.test_fact_compaction -v`

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

## Version 14 migration

Version 14 adds a nullable applied/suppressed disposition to processed event
receipts. Existing receipts remain readable with an unknown disposition; the
migration does not reconstruct it from discarded payloads.

## Version 15 migration

Version 15 adds nullable `facts.source_event_id` and a partial lookup index.
New facts created while processing a durable event retain that first event ID;
semantic duplicates do not rewrite their original source. Existing facts and
facts created outside the event router remain null rather than receiving
inferred provenance. The v14-to-v15 regression preserves an existing fact and
checks its unknown source remains null.

## Version 16 migration

Version 16 replaces the free-form exception detail on already-failed purge
targets with the fixed `legacy_failure_detail_redacted` code. It preserves the
target path, retry state, attempt timestamps, holds, and receipt; the target
remains visibly failed and retryable. New purge failures persist only a
recognized content-free code. The migration is transactional with the schema
version update and prevents old filesystem paths or exception text from
continuing to appear in status responses and future backups. Take a verified
backup before any production database upgrade; production upgrade/rollback is
not approved by this local migration evidence. The v15-to-v16 regression
injects an update-trigger failure, verifies both the legacy detail and version
stamp are unchanged, then retries after removing the trigger and checks that
only the failure detail changed.

## Version 17 migration

Version 17 adds a nullable semantic idempotency digest to event receipts. For
still-retained event payloads, migration parses the bounded typed envelope and
stores a digest over its canonical content without `occurred_at`; transport
retries can therefore reuse an event ID when only the locally generated
occurrence time differs. Processed legacy receipts have already discarded their
payload and keep a null semantic digest, so they retain strict raw-payload
digest comparison rather than guessing their original semantic identity. The
migration and v16-to-v17 retry behavior are covered by local fixtures. This is
not production upgrade/rollback approval.

## Version 18 migration

Version 18 adds nullable `impact` and `retrieval_value` columns to
`sde_candidates`. New significant-event proposals require both compact fields;
existing rows remain readable with null values and are not retroactively
rewritten. The v17-to-v18 fixture covers the migration. This local behavior is
not production upgrade/rollback approval.

## Version 19 migration

Version 19 adds a content-free `staging_artifact_times` ledger keyed by project
and exact staged path, with the SHA-256 and immutable publication timestamp.
Only files published through the V2 producer adapter receive trusted age
metadata; legacy or direct-writer files remain visible in normal inventories
but make an expiry scan incomplete. Purging an exact receipt target removes
its matching age record so safe path reuse begins with a fresh timestamp. The
v18-to-v19 fixture checks the new schema while preserving legacy SDE proposal
fields. This local metadata and read-only 72-hour eligibility scan do not
authorize file deletion, implement expiry scheduling, or approve production
migration/rollback.

## Version 20 migration

Version 20 adds project-scoped expiry purge receipts and exact path/hash
targets. An attended local reviewer must approve the complete 72-hour inventory
hash before a receipt is recorded; the receipt is durable before the first
unlink. Failed targets retain content-free error codes and bounded retry
backoff. Retries can process only targets from an existing approval receipt,
and recheck active artifact holds before every attempt. Successful deletion
clears only the matching age metadata. The v19-to-v20 fixture verifies the
new tables and preservation of age records. This local migration does not
approve production database upgrade/rollback or a production retention policy.

## Version 21 migration

Version 21 adds `cleanup_authorizations`, a separate reviewer decision bound
to an SDE receipt, project, and exact path/hash manifest. It records the
reviewer and approval time plus a distinct canonical target/hash proof for the
projection containing that authorization. SDE disposition, canonical facts,
and expiry eligibility cannot authorize deletion. Retry selection requires a
cleanup authorization whose canonical projection proof is durable. The
v20-to-v21 migration creates the table without inventing authorizations for
existing SDE receipts; those receipts therefore remain pending until explicitly
reviewed under the new workflow. A focused v20-to-v21 fixture preserves a
legacy receipt and verifies that migration creates no cleanup authorization for
it. A conflicting pre-existing object with the same name but an incompatible
columns, defaults, nullability, primary key, or receipt foreign key now fails
closed without advancing the schema version. These local tests do not approve
production database upgrade/rollback.

## Version 22 migration

Version 22 adds a content-free `event_payload_scrub_queue` for retrying SQLite
WAL truncation after transient event payloads have been removed. When a legacy
database has event inbox rows, migration queues one database-wide scrub receipt;
it does not copy or delete `event_inbox.payload_json` values. At runtime, the
store records event-scoped scrub work when it clears a payload, attempts a
bounded `wal_checkpoint(TRUNCATE)`, and retains a pending receipt with a fixed
error code when another connection prevents completion. Startup retries pending
work. The v21-to-v22 fixture verifies the global receipt contains no event
content and that the legacy payload row is unchanged. This is local retry
behavior, not a production migration, privacy-erasure, or recovery drill.

## Version 23 migration

Version 23 adds nullable `device_id` and `inode_id` fields to SDE purge targets.
New reviewed inventories persist the file identity captured during no-follow
hashing; purge retries reject targets whose current file identity differs.
Legacy rows remain unchanged and visible, but the purger refuses to unlink them
because they lack a captured identity. The v22-to-v23 migration adds fields only
when the purge-target table exists, preserving partial legacy databases.

## Version 24 migration

Version 24 adds the same nullable identity fields to expiry purge targets. New
expiry receipts preserve the identity across store reopen and retry, and the
purger refuses a same-content replacement at an approved path. Legacy expiry
targets remain visible but cannot be safely deleted without identity. These
device/inode checks do not provide a content-free generation ID that survives
copy or restore; the broader occurrence-binding gate remains open.

## Version 25 migration

Version 25 associates producer age metadata with the observed device and inode.
A same-content replacement at the same path receives new age metadata when it
is staged, and untrusted legacy identity does not inherit an old retention
clock. A timestamp is returned only when path, hash, and captured file identity
match. Re-recording the same path/hash with a different known identity resets
its age; legacy rows with unknown identity do not make a scanned file expiry-
eligible. This remains a local filesystem identity check.

## Version 26 migration

Version 26 adds nullable `occurrence_id` columns to staging age, SDE purge, and
expiry purge records where those tables exist. Existing receipts are preserved
with null IDs; migration does not infer identity for legacy approvals. New
producer writes bind a generated content-free ID to their exact staging file.

## Version 27 migration

Version 27 creates `staging_artifact_occurrences`, a content-free registry keyed
by project and path with the observed digest, device, inode, occurrence ID, and
observation time. Complete scans reuse the ID only when all file identity
fields match; a same-byte replacement with a new filesystem identity gets a
new ID. Directly written files receive identity on inventory but do not gain
producer age metadata or expiry eligibility. Registry IDs persist through a
SQLite reopen or database copy. Filesystem copy/restore reconciliation remains
an open policy and release gate; a changed identity is not silently treated as
the prior occurrence.

## Version 28 migration

Version 28 adds `approval_stale` to SDE and expiry purge targets. Any unpurged
legacy target without an occurrence ID is marked stale and loses its retry
deadline; already-purged targets keep their completed outcome, and active holds
remain held. Stale targets remain visible in receipt status but are excluded
from manual and scheduled deletion attempts. Releasing a legacy hold records
the separate release audit while leaving its cleanup approval stale. A fresh
inventory and explicit review must create new cleanup authority. This migration
does not infer identity for old receipts.

## Version 29 migration

Version 29 adds the reviewed dependency-map digest to cleanup authorization
receipts. Existing authorizations have no such digest; migration keeps their
receipts readable but marks their unpurged targets stale and clears retry
deadlines. New review decisions must present a map digest that matches the
current evidence/criterion links and exact artifact inventory, and the cleanup
receipt preserves that digest. The migration does not infer an old map or
transfer its approval to a new review.

## Version 30 migration

Version 30 adds a per-target `reacquisition_action` to reviewed purge targets.
Legacy unpurged targets without an explicit action become stale and lose their
retry deadline; completed targets remain completed. New SDE cleanup authorization
requires an action for every target, retains held files only under an explicit
hold action, and records source reacquisition when an open criterion depends on
the staged evidence. The action is persisted with target status so it remains
visible after restart. Expiry cleanup remains separate and does not invent an
SDE evidence-reacquisition decision.

## Version 31 migration

Version 31 adds a monotonically increasing project registration revision and
stores the resulting revision with each project registry audit entry. Existing
audit entries receive deterministic per-project revisions in timestamp and
audit-ID order; each current registration is backfilled to the number of its
retained audit entries, with a minimum revision of one. Config updates,
suspensions, and reactivations require the revision observed during review and
advance it atomically with their audit receipt. Stale revisions are rejected
without changing registration state or appending an audit record. This fences
project-level admin changes locally; it does not add consumer-binding revisions
or prove trusted deployment identity.

## Version 32 migration

Version 32 adds an optional caller-supplied `transition_id` to project registry
audit records and a unique project-scoped index. Existing audit rows retain a
null transition ID because their original request key cannot be inferred.
Config updates, suspension, and reactivation require a stable transition ID.
An exact retry with the same actor, action, revision, rationale, and reviewed
fingerprint values returns the original immutable receipt and does not append a
second audit row. Reusing an ID with different input is rejected. This supports
local retry recovery; it does not make an untrusted caller authenticated or
provide consumer-binding lifecycle receipts.

## Version 33 migration

Version 33 creates consumer binding state and append-only lifecycle receipts,
separate from project status and project revisions. Existing project
registrations are backfilled as active binding epoch 1, revision 1; historical
enrollment receipts are not fabricated. Fresh project registration creates both
project and binding state atomically. Deregistration transitions use their own
compare-and-set revisions and stable transition IDs.
