# Curator V2 lifecycle event contract, version 1

This document describes the typed envelope implemented in
`curatormd_v2.events`. It is a serialization contract, not a production
HTTP/MCP ingress, authentication mechanism, broker, or claim that Hermes is
deployed with CuratorMD. Hermes source now has an opt-in project-scoped local
hook adapter to the Curator MCP event tool; this does not establish live
deployment or authenticated host identity. The SQLite store provides a durable inbox: it deduplicates
`(project_id, event_id)`, rejects ID reuse with different content, exposes
bounded received/failed events, tracks delivery attempts, and discards payload
text after processing while retaining its digest receipt. `CuratorService.process_event` applies
supported goal/fact events and marks them processed in one SQLite transaction;
a failure rolls back goal/fact changes and leaves a retryable receipt with only
a bounded exception-type code. Fact-capacity failures discard the structured
payload as well as retaining the digest/error receipt; the producer must replay
the same event ID and content after an approved capacity remedy. The local
`DurableEventRouter` consumes the inbox using a fixed, trusted project-to-service
map, preserves source sequence order, retries failures, quarantines exhausted
events without deleting their payload, and exposes aggregate queue counts and
oldest pending age. SQLite expiring owner claims coordinate concurrent router
processes sharing the same database; stale workers cannot finalize a claim they
no longer own. An authorized retry is separately audited. This is an
explicitly invoked local consumer, not a production scheduler, alerting
service, deployed worker-topology guarantee, or live Hermes integration.

## Envelope

```json
{
  "schema_version": 1,
  "event_id": "evt-unique-to-the-producing-project",
  "project_id": "gptmd",
  "source_id": "codex-session-2026-10-18",
  "source_sequence": 12,
  "occurred_at": "2026-10-18T12:00:00+00:00",
  "event_type": "goal.started",
  "payload": {
    "goal_id": "goal-stable-id",
    "problem": "Add the readiness route",
    "success_criteria": [
      {"criterion_id": "readyz", "description": "Readiness returns ready"}
    ],
    "initial_status": "planned",
    "next_action": "Inspect the existing readiness route and required probes",
    "owner": "gptmd-coding",
    "checklist_id": "ops-12",
    "checklist_version": "sha256:<64 lowercase hex characters>",
    "checklist_source_text": "- [ ] Add readiness endpoint",
    "parent_goal_id": "release-goal",
    "depends_on_goal_ids": ["config-goal"]
  }
}
```

- `schema_version` is currently exactly `1`; unknown versions are rejected.
- `event_id` is a caller-stable identity, limited to 128 characters. The local
  store makes same-ID/same-payload retries idempotent and conflicting reuse a
  visible error.
- `project_id` is a bounded opaque ID. It is routing context, not proof of
  caller identity or authorization, and does not by itself provide tenant
  isolation.
- `source_id` is an optional bounded producer identity; old version-1 payloads
  without it decode as `unspecified`. `source_sequence` is optional for
  compatibility. Producers that provide it must start at 1 and increment by
  one within each `(project_id, source_id)` stream. The service advances that
  cursor in the same SQLite transaction as the goal/fact change. Gaps and
  repeated sequence numbers fail visibly and remain retryable; they never
  partially apply facts. Producers omitting sequence numbers have no ordering
  guarantee.
- `occurred_at` must be an ISO-8601 timestamp with an explicit timezone.
- `event_type` must match the payload schema exactly; unknown or extra fields
  and duplicate JSON object keys are rejected.
- `goal.started.initial_status` is optional for existing clients. If absent it
  retains the legacy `active` behavior; producers may set `planned` to capture
  agreed work before implementation begins. Repository-plugin and MCP goal
  intake defaults to `planned`.
- `goal.started.next_action` is optional and backward-compatible. When supplied,
  it is a bounded single-line task step, preserved on the goal and shown in the
  report; a missing action is reported as unrecorded rather than invented.
- The UTF-8 encoded serialized envelope is limited to 16 KiB. Payloads contain
compact goal/fact data and evidence references, never raw chats, transcripts,
command output, imports, or scratch content.

## Domain resource limits

The domain models enforce these limits even when a local caller bypasses JSON
serialization (for example, direct MCP tool calls):

- 32 success criteria and 32 dependency links per goal.
- 16 immutable criteria revisions per goal, including the original contract.
- 512 unique facts and 512 KiB of retained fact-record content per goal.
- 10,000 unique facts and 16 MiB of retained fact-record content per project.
- 16 evidence references per fact; each evidence kind is at most 64 characters
  and each locator at most 1,000 characters.
- 32 selected fact IDs per SDE candidate.
- One single-line SDE rationale of at most 1,000 characters; the review packet
  links the rationale to selected fact bullets and their evidence references.
- 500 unique artifact paths per review receipt; each path is a single line of at
  most 4,096 characters.
- Each goal problem, criterion description, fact bullet, and review rationale
  also has its own character limit enforced by the domain model.

These are rejection ceilings, not recommended target sizes. On either
per-goal or per-project limit, an append is rejected without pruning prior
facts; goal status exposes the exhausted capacity and required open gate, and
project usage reports the project ceiling. Automatic compaction is not
implemented. The global inbox is capped at 250,000 receipts and 128 MiB of
retained logical row bytes across projects; the capacity gate reserves 160
bytes per event for safe failure metadata. At the cap, new event IDs fail before
receipt writes, while exact idempotent replays remain available. No receipts
are automatically pruned. Budgets for facts across projects, other permanent
data classes, and retention/recovery at the event ceiling remain open, so broad
automatic capture is still gated.

For checklist-backed goal starts, the repository plugin verifies that the
selected one-line item occurs exactly in the configured checklist file and
supplies its SHA-256 file revision plus the exact item text. The backend stores
the selected line and revision, not a copy of the entire checklist. Both fields
are optional together only for legacy/non-checklist goal starts; if either is
present, both and `checklist_id` are required.

## Event types

| Event | Required payload | Meaning |
| --- | --- | --- |
| `goal.started` | Stable goal ID, problem, non-empty unique success criteria; optional initial status, next action, owner, checklist ID/revision/source line, parent goal ID, and dependency goal IDs | Starts a scoped goal while preserving caller criteria, optional next action, and lineage; new MCP/plugin intake defaults to planned. |
| `goal.activated` | Goal ID, explicit acceptance reason, expected lifecycle revision | Moves only a planned goal to active, records an intent fact and advances lifecycle revision atomically. |
| `fact.recorded` | Goal ID, stable fact ID, fact kind, one-line bullet; optional criterion ID; evidence array | Adds one compact lifecycle fact. Verification facts require evidence references and a criterion. |
| `goal.activity_observed` | Goal ID, stable fact ID, one of `intent`, `change`, or `open_gate`, and one-line bullet | Status-independent Hermes activity envelope. In one transaction, active goals receive the fact; non-active goals receive a processed receipt with `suppressed_nonactive_goal`, no fact, and an advanced source cursor. Exact replay preserves that disposition even after reopening. |
| `goal.finish_requested` | Goal ID, completion claim, expected lifecycle revision | Requests evaluation; the claim is not proof and cannot itself close the goal. |
| `goal.deferred` | Goal ID, reason, next action, expected lifecycle revision | Records an explicit deferred state and follow-up. |
| `goal.blocked` | Goal ID, dependency, recovery, expected lifecycle revision | Records the dependency and recovery path for a blocked state. |
| `goal.reopened` | Goal ID, reason, next action, expected lifecycle revision | Reopens a completed goal in a new evidence epoch; prior facts remain, but prior verification does not count. |
| `goal.criteria_amended` | Goal ID, expected criteria revision, expected lifecycle revision, replacement criteria, reason, next action | Explicitly amends a non-complete goal contract with optimistic concurrency; records immutable criteria history and starts a fresh evidence epoch. |
| `goal.cancelled` | Goal ID and reason | Retires unfinished work without implying success. The immutable cancellation fact remains on the goal. |
| `goal.superseded` | Goal ID, existing replacement goal ID, and reason | Retires unfinished work in favor of an active same-project replacement and records the immutable successor link. |

## Proposed Hermes Codex-turn mapping

The current Hermes Core hook producer emits `codex:turn:start` and
`codex:turn:end` with bounded runtime metadata only. The translation in the
table is implemented by `curatormd_v2.hermes_events.codex_hook_to_event` and
covered by tests. Hermes source now includes a project-config-bound adapter to
the local Curator MCP event tool. It validates host-supplied profile/session
metadata and a previously accepted session-to-goal binding, derives the same opaque source ID as the producer,
and acknowledges only a durable processed/duplicate receipt. The profile-local
SQLite outbox assigns stable event IDs, source sequence/timestamp, persists
before dispatch, and retries until a durable consumer returns literal `True`.
A local in-memory MCP acceptance test exercises the adapter, event translation,
project authorization, and durable fact write; terminal activity suppression,
source advancement, retry replay, and reopening are covered by lifecycle tests.
Hermes tests cover outbox replay,
profile isolation, and activation-bound sessions. The local profile ID is still
an operator assertion, not authenticated identity. No active profile hook,
running gateway event, production scheduler/router, or deployed integration has
been verified.

| Hermes hook | Curator fact | Required meaning and guard |
| --- | --- | --- |
| `codex:turn:start` | `goal.activity_observed`, kind `intent` | Record only that a bound goal received a Codex turn. Do not infer a new goal from the user's prompt or copy the prompt, model, provider, or working directory into the fact. |
| `codex:turn:end`, outcome `completed` | `goal.activity_observed`, kind `change` | Record only that the runtime turn returned normally. This is not criterion evidence and must not emit `goal.finish_requested` or `goal.completed`. |
| `codex:turn:end`, outcome `interrupted` or `failed` | `goal.activity_observed`, kind `open_gate` | Record a bounded interruption/failure fact without exception text; the goal remains in its existing nonterminal status. |

Before translating either hook, the Hermes producer must resolve an explicit,
current `(authenticated profile, project, session, goal)` binding. Project ID
comes from the repository-owned config; identity comes from the trusted Hermes
host, never from a hook or MCP argument. Missing, stale, ambiguous, or
cross-project binding means no event is sent. Goal creation remains an
explicit intake operation requiring the user-approved problem and named
success criteria; hooks alone cannot supply that contract.

For any non-active goal, the event is acknowledged only after Curator stores a
`suppressed_nonactive_goal` receipt and advances the source cursor in the same
transaction. It appends no activity fact. Exact replay retains the original
disposition after reopening, and the next sequence can be applied to the active
goal. This prevents a late turn event from blocking the ordered Hermes outbox
without writing activity against a retired goal.

The producer must assign a stable event/fact ID, source ID, per-source sequence,
and occurrence timestamp before queueing the event, then retry the exact
serialized envelope. The hook's `session_id`, `attempt_id`, `turn_id`,
`failure_kind`, and other runtime metadata are correlation inputs only; do not
retain them in canonical facts. No arbitrary hook context is forwarded. A turn
end is never evidence that a test, service probe, browser check, or other
criterion passed. End-to-end acceptance must prove correct binding, ordering,
deduplication, no raw content in the queue/logs/ledger, and no goal completion
from a runtime outcome alone.

Criteria revisions are append-only and returned in goal status. An amendment
must name the revision it observed; a stale revision is rejected without
changing criteria. Completed goals must be reopened before amendment. Both
reopening and amendment retain the old verification facts for audit, but only
passing verification recorded after the latest evidence-epoch boundary may
satisfy current criteria. Criteria amendment is not cancellation or
supersession; those lifecycle semantics are defined below. A goal is limited
to 16 total criteria versions to bound this history; total lifetime fact and
goal retention remains an open policy gate.

Planned goals cannot receive change, verification, completion-claim, or outcome
facts and cannot finish. The `goal.activated` event requires the currently
observed lifecycle revision; stale activation or a second activation under a
new event ID conflicts and leaves state unchanged. Replaying the exact same
event ID and payload remains idempotent. Existing internal
`CuratorService.goal_start` callers default to active for compatibility, while
project-plugin intake and the MCP `goal_start` tool default to planned.
`goal.started` may link a child task to an existing same-project parent and to
existing same-project dependency goals. Parent completion remains open until
all direct children are complete or explicitly retired and all declared
dependencies are complete; a child task also remains open while its dependencies
are incomplete. These are application-service semantics and do not provide
cross-project authorization.

The local lifecycle action matrix is explicit:

| Action | Planned | Active / open / blocked / deferred | Complete | Cancelled / superseded |
| --- | --- | --- | --- | --- |
| Activate | Allowed; moves to active | Rejected | Rejected | Rejected |
| Change or verification fact | Rejected until activation | Allowed; verification still requires passing trusted evidence | Rejected | Rejected |
| Finish evaluation | Rejected until activation | Allowed; becomes complete only when criteria, children, and dependencies pass, otherwise open | Idempotent read; no new fact or revision | Rejected |
| Block or defer | Allowed | Allowed | Rejected | Rejected |
| Amend criteria | Allowed; retains planned status | Allowed; retains current status | Rejected until reopened | Rejected |
| Cancel or supersede | Allowed | Allowed | Rejected until reopened | Rejected |
| Reopen | Rejected | Rejected | Allowed; moves to active with a fresh evidence epoch | Rejected |

Every rejected action leaves the goal, revision, and facts unchanged. Successful
status or criteria transitions advance `lifecycle_revision`; appending an
ordinary fact does not. Supersession additionally requires its replacement to
be active and in the same project. Dedicated activation, reopening, and
retirement paths enforce their extra invariants; the generic transition store
primitive cannot target those dedicated statuses or move planned work directly
to finish evaluation.

## Cancellation, supersession, and conflicts

`complete`, `cancelled`, and `superseded` are terminal statuses. Cancellation
and supersession are permitted only from unfinished goals; a completed goal
must first be explicitly reopened, which starts a fresh evidence epoch. A
cancelled or superseded goal cannot be reopened or accept new facts. Resume work
by starting a new goal so the original contract and disposition remain intact.

Cancellation requires a bounded, single-line reason. Supersession additionally
requires an existing active replacement in the same project; self-links and
replacement descendants are rejected. A parent cannot be retired while it has
unfinished children, and a goal cannot be retired while unfinished goals depend
on it. Resolve those children/dependents first. New dependency links cannot
target cancelled or superseded goals. The old goal retains `superseded_by_goal_id`
and an append-only fact; it is never rewritten or deleted.

Retirement runs under the store's SQLite write transaction. If cancellation,
supersession, completion, or another terminal transition races, the first
serialized terminal transition commits and later transitions conflict; its
facts and inbox receipt commit atomically. Exact retries of the winning event ID
return its processed receipt. Criteria changes use an expected criteria
revision, while all nonterminal status/contract updates additionally use a
lifecycle revision to reject stale writes.

Each goal status snapshot exposes `lifecycle_revision`, initially `1`. A
successful status-changing defer, block, finish evaluation, criteria amendment,
reopen, cancellation, or supersession advances the revision; appending an
ordinary fact or re-reading an already-complete goal does not. MCP status-changing tools require the revision observed by the caller.
The store compares it under the same write transaction as the fact/status
update. A mismatch fails with a conflict and writes no goal fact or state
change. Criteria amendments must match both the criteria revision and lifecycle
revision. Cancellation/supersession remain terminal first-writer-wins operations
because they can never overwrite another terminal result.

For compatibility with existing schema-version-1 event producers, raw event
payloads may omit `expected_lifecycle_revision`; omission is treated as revision
`1`, not as "use whatever is current". Such an event can therefore apply only
before the goal's first state/criteria transition. Stale legacy events fail
closed; callers should read `goal_status` and submit the current revision.
Database goals migrated from a schema without lifecycle revisions receive a
revision fence of `2`, because their prior transition count cannot be inferred;
those goals require a fresh status read before a write.

Cancelled or superseded child goals do not provide evidence for parent success
criteria. A parent can finish only when its own criteria have passing evidence
and no unfinished child remains. Cancelled/superseded dependencies do not
unblock dependents; unfinished dependents must be handled before retiring the
dependency. A completed dependent remains historical; it cannot be reopened
while a dependency is cancelled or superseded.

Fact kinds include `intent`, `research`, `advice`, `proposal`, `change`,
`verification`, `open_gate`, `completion_claim`, and `outcome`. Research,
advice, proposals, and completion claims are not verification. Evidence
references contain only `evidence_kind`, `locator`, `sha256`, and `outcome`.
The backend's configured evidence verifier remains authoritative; the
serialized `passed` value alone must never close a success criterion.

## Local router behavior and remaining production requirements

- Authenticate the caller independently of `project_id`, then authorize the
  project binding and allowed event types.
- The local service atomically applies each supported event and its processed
  receipt. `DurableEventRouter.route_once()` performs bounded delivery through
  a fixed project binding. A failed dispatch increments the receipt attempt;
  after the configured limit the event moves to `quarantined` with its payload
  retained. Only the project `event_retry` action can release it, and the
  authenticated actor is written to `event_retry_audit`.
- Exact event IDs and source sequences remain idempotency/order fences. An event
  is eligible only when its sequence is next; later events wait for the missing
  predecessor. Queue status reports received, failed, quarantined, and oldest
  pending age without exposing event contents.
- Local multi-process claim coordination is implemented with expiring SQLite
  leases. A production router still needs process scheduling, alert policy,
  restart/load/failure-injection probes, deployment-observed lag, and shared
  authorization/rate-limit integration.
- Preserve source order/version where required and make delayed/out-of-order
  events explicit rather than silently overwriting current state.
- Keep event acceptance, processing, and health states distinct. A queued or
  failed event cannot imply that its goal/fact mutation succeeded.
- Verify project isolation and bounded memory/latency under integration tests
  before enabling automatic lifecycle capture.

The backend defines and validates the envelope, provides a local SQLite inbox
and bounded in-process router, and atomically applies supported events plus
optional per-source ordering cursors through a project-scoped service.
Direct fact writes also recheck goal status under the SQLite write transaction
that appends the fact, so completion on another connection serializes before or
after the fact instead of allowing a late append to a completed goal. A
two-connection regression test covers that ordering.
Production MCP/HTTP authentication and transport, project registry, scheduler
operation and deployment-specific worker coordination, consumer installation,
and Hermes mapping remain open plan items.
