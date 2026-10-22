# Curator V2 transport-neutral API boundary, version 1

`AuthenticatedCuratorAPI` is an in-process facade over configured
`ProjectPlugin` instances. It centralizes authorization checks, project
binding, lifecycle event size/schema validation, and request budgets. It is not
an HTTP or MCP server, and it does not authenticate credentials.

## Trusted identity and project policy

- A Hermes or other host authentication adapter verifies the session/token and
  constructs `AuthenticatedCaller(subject_id)` from its verified subject.
- Never deserialize `AuthenticatedCaller` from a request body, tool argument,
  repository config, or project ID. The class is only a typed handoff from the
  trusted host.
- `ProjectAuthorizer` must check subject, project, and action. The default
  `RejectAllProjectAccess` denies every request until the host supplies a real
  policy adapter.
- `ProjectGrantAuthorizer` is a local reference adapter for exact
  `(subject_id, project_id, action)` grants. It rejects malformed IDs and
  unknown actions, has no wildcard grants, and snapshots the supplied grants
  at startup. `SQLiteProjectGrantAuthorizer` resolves exact scopes from the
  durable project registry/grant ledger and denies suspended or unregistered
  projects. `ProjectAccessManager` provides audited registration, update,
  suspension/reactivation, grant, and revocation operations behind a separate
  injected host-administration policy. Neither component authenticates
  subjects; the manager is not exposed through MCP and must not be constructed
  from caller-controlled identity, project config, or project ID.
  `FingerprintBoundSQLiteProjectGrantAuthorizer` additionally checks the
  current active registration against the repository path fingerprint, exact
  config digest, and backend API version on every authorization decision.
- The API registry maps project IDs to independently configured plugins. A
  project ID is routing context only; it grants no access.
- Review decisions pass the verified subject ID into the plugin's
  `ReviewAuthorizer`; the returned reviewer ID must equal that subject or the
  decision is rejected. Purge retry uses its own `purge_retry` permission and
  can affect only reviewed, canonically persisted manifests in that project's
  staging root.
- SDE corrections pass the verified subject through the plugin's correction
  authorizer. They require a durable decision receipt and a stable correction
  ID; identical retries are idempotent and changed-content reuse conflicts.
  Corrections are append-only and do not rewrite the candidate or receipt.
- Post-disposition SDE quality feedback passes through a separate trusted-host
  reviewer authorization check. One reviewer may submit one immutable label per
  candidate (`useful`, `not_useful`, `inaccurate`, or `duplicate`); identical
  retries are idempotent. Aggregate summaries and Prometheus samples omit
  reviewer identity and rationale. These are explicit human labels, not ground
  truth or model-training signals.

The `curatormd-v2-review` local CLI binds attended review to the current
non-setuid Linux UID (`local-uid:<euid>`), exact project grants, and a visible
terminal. It displays selected facts and the complete hashed artifact
inventory; SDE disposition and cleanup each require an explicit decision, and
cleanup approval is bound to the exact inventory.
This is a local-alpha host adapter, not a Hermes authenticator. Hermes-
authenticated human identity remains a separate integration gate.

## Operations and MCP mapping

| API method | Required action | Intended tool/route |
| --- | --- | --- |
| Lifecycle event tools | `write` | `goal_start`, `fact_record`, `goal_finish`, `goal_defer`, `goal_block`, `goal_cancel`, `goal_supersede`, `goal_reopen`, `goal_amend_criteria`, `event_ingest` |
| Goal reads | `read` | `goal_status` (paged SDE/purge detail), `goal_list`, `goal_list_page`, `goal_children` |
| Compact truth projection | `read` | `goal_bullet_projection` |
| Bounded user-readable goal report | `read` | `goal_report` (paged facts; evidence locators/hashes remain in `goal_status`) |
| Fact archive preview | `read` | `fact_compaction_propose` (exact source facts and hash) |
| Fact archive approval | `review` | `fact_compaction_approve` (authenticated reviewer, exact fact IDs/hash, atomic archive-before-removal) |
| Fact archive audit | `read` | `fact_archive_receipts` (bounded, hash-verified receipts) |
| Project usage | `read` | `project_storage_usage` (includes a bounded repository staging-size scan) |
| SDE significance assessment | `write` | `sde_assess` (up to 32 unique same-goal facts; routine progress returns no candidate; significant proposals require compact impact and retrieval value plus verified evidence, and remain pending human review) |
| SDE review reads | `read` | `sde_review_queue`, `sde_review_detail` |
| Combined SDE review packet | `review` | `sde_review_packet` (selected candidate facts/evidence plus a fresh hashed artifact inventory) |
| `sde_confirm` | `review` plus plugin review authorizer | `sde_confirm` |
| `sde_correction_record` | `review` plus plugin correction authorizer | `sde_correction_record` |
| `sde_quality_feedback_record` | `review` plus plugin feedback authorizer | `sde_quality_feedback_record` |
| `sde_quality_feedback_summary` | `read` | `sde_quality_feedback_summary` |
| `goal_persist` | `review` | `goal_persist` |
| Markdown reconciliation | `read` | `goal_reconcile` (read-only configured target comparison with status and hashes) |
| Project Markdown reconciliation | `read` | `project_reconcile` (bounded paged goal comparison plus orphan/malformed marker inventory) |
| `artifact_inventory_complete` | `review` | `artifact_inventory_complete` |
| Purge receipt reads | `read` | `artifact_purge_status` |
| Exact held-artifact release | `retention_hold_release` plus plugin hold-release authorizer | `release_artifact_hold` |
| `retry_pending_purges` | `purge_retry` | `retry_pending_purges` |
| Event queue status | `read` | `event_queue_status` (project-scoped counts, oldest pending age, active claims, expired claims) |
| Project activity | `read` | `project_activity_status` (retained event/goal/fact/SDE counts and event recency; content-free and separate from readiness) |
| Project operational health | `read` | `project_health` (local event/review/SDE-purge/expiry-purge/capacity/staging observations plus host dependency probes) |
| Project metrics exposition | `read` | `project_prometheus_metrics` (content-free, project-authorized Prometheus text snapshot) |
| Quarantined event retry | `event_retry` | `event_quarantine_retry` (authenticated actor recorded in retry audit) |

`build_mcp_server(api, caller, project_id, source_id)` registers the tool set on
the official MCP Python SDK's `MCPServer`. The verified caller, project, and
stable producer identity are captured by the host-side factory and are never
tool arguments. The host may launch the returned server over stdio using
`server.run(transport="stdio")`.
[`mcp-tools-v1.md`](mcp-tools-v1.md) documents the concrete MCP contract.

`goal_list_page` and `goal_children_page` are the preferred overview reads:
they filter before pagination and return only bounded `GoalCard` records, a
total count, and a next offset (page size 1–100). Detailed facts, evidence, and
review history are loaded only by per-goal reads. The compatibility full-
snapshot list operations remain available for at most 100 matching goals;
above that they fail with a stable `capacity_exceeded` error before loading
snapshots.

`goal_status` is itself bounded: it returns up to 32 SDE candidates and 16
purge-pending receipts per read, plus exact totals, SDE counts by state, and
continuation offsets. Pass `sde_offset` and `purge_offset` independently to
continue either history. Fact history is capped per goal and criteria history
is capped at 16 versions.

`process_event_json` rejects invalid UTF-8, payloads over 16 KiB, unsupported
schema versions, unknown/duplicate fields, project mismatch, and unauthorized
project access. Accepted events are still processed atomically by the
project-bound service; retry semantics and source sequence rules are defined in
[`event-contract-v1.md`](event-contract-v1.md).
`event_queue_status` is project-scoped and reveals neither event identifiers nor
payloads. It includes aggregate active and expired worker-claim counts.
`project_activity_status` is a separate, project-authorized read. It exposes
bounded event processing-state counts and last receipt/processing timestamps,
goal/fact totals, and SDE candidate counts by review outcome. It returns no
event, goal, fact, or candidate identifiers or content. `events_observed=false`
means the local inbox contains no retained receipt; it is not proof that a
producer was connected or that all development activity was captured. A zero
SDE count is valid activity data and does not affect operational readiness.
`project_health` is a bounded, content-free point-in-time aggregate. Healthy
requires complete staging inventory, available event/fact capacity, no
event/review/purge backlog or expired claims, and explicit healthy readings for
every required host dependency (`event_router`, `purge_scheduler`,
`host_identity`, `human_review`, and `artifact_producer_inventory`). Missing or
failed probes are `unknown`; probe timestamps must be timezone-aware and no
older than 60 seconds (a clock more than five seconds ahead is also `unknown`).
The local SQLite counters are read in one database snapshot; staging is scanned
separately with a bounded no-follow filesystem traversal. Known backlog or
unavailable dependencies are `degraded`. Production probes and schedulers are
not implemented here.
`project_prometheus_metrics` renders the same local health/storage snapshot as
Prometheus text for a project-authorized caller. Labels are bounded or
allowlisted; problem statements, fact text, event payloads, evidence locators,
artifact names/paths, and global SQLite/WAL file sizes are excluded. This is an
in-process snapshot operation, not an HTTP scrape endpoint. The
`curatormd_event_failures` gauge reports the current failed/quarantined receipt
count in three fixed categories (`evidence_rejected`, `evidence_adapter_error`,
`other`); it is not a lifetime attempt counter. It uses only sanitized
exception type codes and never emits exception messages. Scrape scheduling,
dashboard wiring, alert delivery, and model/token usage metrics are not
implemented.
`goal_reconcile` compares one allowlisted target block with the current
structured goal. `project_reconcile` scans one configured target (bounded by
the 8 MiB Markdown limit), returns at most 100 paged goal comparisons, reports
orphaned/malformed marker hashes and unrecognized marker counts, and sets
`inventory_complete=false` when the managed-marker inventory exceeds 5,000.
Neither operation chooses an authoritative store or modifies either side.
`retry_quarantined_event` requires the separate `event_retry` action;
the caller's verified subject is the immutable audit actor. These API methods
do not start a worker scheduler. The local durable router uses expiring SQLite
leases to coordinate claims across connections/processes sharing that database;
this is not proof of a deployed worker topology or production operation.
Retryable failed receipts expose their durable `next_attempt_at`; local due
selection applies capped exponential delays of 5, 10, 20, ... seconds up to 900
seconds. Legacy failed rows with no scheduled time remain immediately eligible.
`goal_amend_criteria` is a write-authorized in-process operation; the MCP
version uses an idempotent lifecycle event and checks the caller's expected
criteria revision before replacing the active contract.

`artifact_inventory_complete` binds newly added hold-placement audit to the
authenticated `review` caller. Existing hold attribution is preserved when an
incomplete inventory is finalized with the same exact held path, hash, and hold
class.

Goal reads include a `lifecycle_revision`. MCP finish/defer/block/reopen and
criteria-amend tools require the revision observed by the caller. Successful
status/criteria transitions increment it atomically; ordinary facts do not.
Stale writes return a conflict without appending facts. Raw version-1 events
that omit the new optional field are interpreted as revision 1 for
compatibility, so they fail closed after the goal's first state transition.

`project_storage_usage` also reports aggregate-only global event-inbox usage
and whether new event IDs are accepted. The inbox has hard count/retained-byte
ceilings across projects; reaching either gate rejects new IDs without pruning
receipts. Exact same-ID/same-payload replays continue to work. Retention and
recovery at that ceiling remain an operator policy gate.

`artifact_purge_status` is project-scoped and reports per-target status,
including `held` plus its `legal`/`operational` retention class, durable attempt count, creation and last-attempt timestamps with age in
seconds, the persisted next retry deadline and remaining delay, the last error,
and a `safe_recovery_action`. That action is a
read-only recommendation selected from the current gates
(`artifact_inventory_complete`, `goal_persist`, `retry_pending_purges`,
`release_artifact_hold`, or `none`); it does not execute recovery. A held target
can be released only for its exact receipt and path, after project
`retention_hold_release` authorization and plugin reviewer authorization. The
release actor, timestamp, and bounded single-line rationale are persisted
before eligible purge resumes. The original hold class remains in the audit
record. Replaying the same release is idempotent; a different actor or
rationale conflicts. The attempt timestamp is committed before the filesystem
operation, allowing an interrupted deletion to remain observable as pending
until reconciliation or retry.

## Rate limits and deployment boundary

The transport-neutral API defaults to a bounded per-process token bucket (120
requests per subject/project per 60-second refill period, at most 10,000 tracked
pairs). The local stdio factory instead injects `SQLiteTokenBucket`, which
atomically shares that quota across processes using the same SQLite database.
Its persistent state contains only subject/project IDs and token timestamps;
the bucket registry fails closed at its 10,000-row bound and prunes an idle
bucket only after a full refill period. This is same-host SQLite coordination,
not a distributed or network-filesystem limiter. A production transport still
needs host-controlled quota configuration and operational monitoring.

Host token/session verification, trusted fingerprint derivation, Hermes
permission binding, shared production rate-limit policy/configuration,
audit/metrics integration, remote transport policy, and deployment-level host
integration remain open.
The local persistent registry is reference backend functionality, not a
Hermes identity integration. MCP stdio framing is exercised
by a local subprocess test. Direct plugin/service access is an internal library
boundary and bypasses this facade.
