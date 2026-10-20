# Curator V2 MCP tools, version 1

`curatormd_v2.mcp_server.build_mcp_server(api, caller, project_id, source_id)`
creates a real MCP Python SDK `MCPServer` with a fixed host identity, project
binding, and producer stream. The host is responsible for authenticating the
session, loading the correct project plugin, applying the project's role
policy, and passing a unique stable `source_id` for that producer. Call
`server.run(transport="stdio")` when the host launches the server as a local
subprocess.

Neither `caller`, `project_id`, nor `source_id` is exposed as a tool argument.
Each operation also passes through `AuthenticatedCuratorAPI`; project/action
authorization and request limits are rechecked per invocation. The default
project authorizer rejects all operations. The test-only subprocess fixture
uses a fake identity and must never be used as a deployment entrypoint.
[`sde-review-policy-v1.md`](sde-review-policy-v1.md) defines qualification
examples and the evidence/claim language expected in review packets.
[`content-safety-v1.md`](content-safety-v1.md) defines current reject-only
secret/PII checks and their explicit detection limits.

## Model-facing work protocol

The server's MCP initialization instructions carry a compact work cycle to the
connected assistant: bind the exact request/checklist item, record the problem
and observable success criteria before implementation, add deduplicated typed
fact bullets at meaningful checkpoints, and reconcile verified versus open
criteria with `goal_report`. Unsupported completion stays open with its unmet
work and next action. SDE review, canonical persistence, and artifact purge are
separate gates; approval and a complete inventory must precede cleanup. This
guidance does not itself cause a host to emit events or authenticate a user, so
the Hermes delivery and identity gates remain independent.

## Local Hermes profile launcher

The `curatormd-v2-mcp` entrypoint binds one local stdio process to the project
declared in that repository's `.curatormd-v2.toml`. Hermes should configure one
server instance per profile/repository pair and keep the launcher arguments in
operator-controlled profile configuration. Before launching it, a trusted
host administrator must register this project and grant the profile exact
`read` and, when requested, `write` access in the global backend database.
Use the attended `curatormd-v2-access` command below; it is built on
`ProjectAccessManager` and is deliberately not available through MCP. The
launcher never self-registers or creates grants. Registration binds the
project ID to a fingerprint of the canonical repository path, the SHA-256 of
the exact `.curatormd-v2.toml` bytes, and the backend API version. Missing,
suspended, revoked, or mismatched bindings fail closed; updating the repository
config requires a separately authorized registration update.

```yaml
mcp_servers:
  curatormd_v2:
    command: uv
    args:
      - run
      - --project
      - /path/to/curatormd-v2
      - --locked
      - curatormd-v2-mcp
      - --project-root
      - /path/to/consumer-repository
      - --database
      - /path/to/global-curator-v2.sqlite3
      - --profile-id
      - consumer-coding
      - --allow-write
    hermes_context: true
    hermes_project_id: <project_id-from-.curatormd-v2.toml>
    transport: stdio
```

Replace every path and the profile ID with the exact operator-managed values;
set `hermes_project_id` to the exact ID in this repository's `.curatormd-v2.toml`;
use a private database path owned by the Hermes account. `--profile-id` is an
operator assertion, not authentication. This launcher is only for a trusted
local orchestrator that owns the MCP subprocess configuration; it must not be
exposed as a remote endpoint or reused across principals. Omit `--allow-write`
for read-only access. This flag is only an upper bound: `--allow-write` still
requires a durable `write` grant, and without the flag the launcher denies
writes even if one exists in the registry. The process cannot use grants for
other scopes. Canonical `goal_persist`, SDE review,
fact-archive approval, purge retry, retention-hold release, and event retry
require separate reviewer/operation grants and remain denied by this launcher;
there is no MCP tool parameter for selecting another caller or project. An
absent/invalid repository config fails startup. The local event router and
purge scheduler are not started by this entrypoint.

Every `tools/call` request must also carry Hermes-injected `hermes/profile_id`
and a bounded `hermes/session_id`; the profile must exactly match
`--profile-id`. Configure `hermes_context: true` only for this local stdio
server. This fail-closed request-context check prevents tool execution when
Hermes identity context is absent or mismatched, but the metadata is not a
cryptographic credential. It does not authenticate a remote MCP client or
replace registered project grants, owner identity, or deployment-level
authorization.

### Durable local project access

The local launcher now consults the durable SQLite project registration and
exact subject/project/action grants on every request. Its loaded repository
root and `.curatormd-v2.toml` fingerprints must match an active registration;
registration drift, suspension, missing grants, and revocation fail closed.
`--allow-write` only permits the launcher to honor an existing write grant;
it does not create a registration or grant.

Use the separate attended local operator command to provision this ledger. It
is not exposed through MCP and requires an interactive TTY plus exact typed
confirmation for each operation:

```sh
curatormd-v2-access register \
  --project-root /absolute/path/to/consumer-repository \
  --database /absolute/path/to/global-curator-v2.sqlite3 \
  --rationale "Owner-approved local project registration"
curatormd-v2-access grant \
  --project-root /absolute/path/to/consumer-repository \
  --database /absolute/path/to/global-curator-v2.sqlite3 \
  --subject-id consumer-coding --action read \
  --rationale "Approve read-only project access"
```

Grant `write` separately only after review. The command records its actor as
the effective local Unix UID. That is an account-level audit label, not a
verified human identity; shared accounts cannot distinguish operators. It does
not authenticate a Hermes profile or replace a deployment identity provider.
Use `curatormd-v2-access view`, `revoke`, `suspend`, `reactivate`, or `update`
for the corresponding attended audit or administrative action. The local
ledger integration is tested, but remote authentication, verified Hermes
profile-to-project authorization, reviewer identity, distributed rate limits,
operator scheduling, and deployment probes remain open gates.

### Hermes durable Codex hook adapter

For each project enabled under a Hermes profile, configure `hermes_context: true`
and `hermes_project_id` as above, then install a profile-local gateway hook:

```yaml
# <Hermes profile home>/hooks/curator-v2/HOOK.yaml
name: curator-v2
events: [codex:turn:start, codex:turn:end]
durable_events: [codex:turn:start, codex:turn:end]
```

```python
# <Hermes profile home>/hooks/curator-v2/handler.py
from curatormd_v2.hermes_hook import build_hermes_hook_handler

handle = build_hermes_hook_handler(
    "/path/to/consumer-repository",
    "curatormd_v2",
)
```

The adapter reads the repository-owned `.curatormd-v2.toml`, ignores events
bound to other project IDs, and calls the already-connected local MCP server's
`hermes_codex_event` tool. Hermes host metadata supplies the current profile and
session; a separate host-only `_meta` marker distinguishes durable dispatch
from a model-authored call. `hermes_goal_bind` validates an explicit active
goal, while successful goal activation can bind the goal automatically in the
profile-local outbox. The Codex event tool accepts only that host-dispatched
marker and verifies deterministic event identity. Curator atomically records
an activity bullet only while the bound goal is active; for a non-active goal
it stores a `suppressed_nonactive_goal` receipt without adding a fact, allowing
the ordered outbox to advance. Neither a turn end nor a successful event
receipt completes the goal.

The Curator package must be importable by the Hermes gateway interpreter and
the hook files/configuration must be installed by the operator; this document
does not claim a live install. Hermes profile IDs remain operator assertions,
and the host profile-to-project permission and deployment gates remain open.

## Tool inventory

| Tool | Function |
| --- | --- |
| `goal_start` | Capture a goal with caller-supplied criteria, optional next action/checklist snapshot/parent/dependencies, and `planned` status by default. `initial_status=active` is for already accepted work. Requires stable event ID. |
| `goal_activate` | Explicitly accept a planned goal for execution with a reason and expected lifecycle revision; records the intent and atomically changes status to active. |
| `hermes_goal_bind` | Validate that an explicit goal is active in this configured project and that trusted MCP request metadata names the fixed caller profile plus current session. Hermes records the returned binding in its profile-local host outbox; profile/session values are never tool arguments. |
| `fact_record` | Add one typed fact; verification facts require criterion and evidence references. |
| `goal_finish` | Evaluate claim against verified criteria, children, and dependencies; unsupported completion stays open; requires the observed lifecycle revision. |
| `goal_defer` | Set deferred state with reason and next action; requires the observed lifecycle revision. |
| `goal_block` | Set blocked state with dependency and recovery path; requires the observed lifecycle revision. |
| `goal_cancel` | Cancel unfinished work with an immutable reason; cancellation never means success. |
| `goal_supersede` | Retire unfinished work in favor of an existing active same-project replacement. |
| `goal_reopen` | Reopen a completed goal into a new evidence epoch; earlier facts stay visible but earlier verification no longer satisfies criteria; requires the observed lifecycle revision. |
| `goal_amend_criteria` | Replace criteria on a non-complete goal with criteria- and lifecycle-revision guards, immutable criteria history, a reason, and next action; all prior verification is retained but must be re-established. |
| `event_ingest` | Advanced escape hatch for a complete bounded version-1 event JSON envelope; returned receipts include `next_attempt_at` after a retryable failure. |
| `goal_status` | Read goal state and `lifecycle_revision`, evidence-derived criterion progress, bounded facts, criteria history, fact-capacity state, and one page of up to 32 SDE candidates and 16 purge-pending receipts. Includes exact totals, candidate state counts, and next offsets; pass `sde_offset` and/or `purge_offset` to continue. |
| `goal_bullet_projection` | Read one compact bullet view separating recorded facts, evidence-verified facts, unverified claims, and current open gates. Large SDE/purge queues are summarized with exact totals; use paged `goal_status` to inspect IDs. |
| `goal_report` | Read a bounded Markdown report with the problem, criteria, paged fact bullets, TODOs, dependencies, SDE review, and canonical-write/purge state. It omits evidence locators and hashes; use `goal_status` for those references. |
| `fact_compaction_propose` | Preview exact eligible routine research/advice bullets, stable IDs, source hash, and byte count; this read never mutates the ledger. |
| `fact_compaction_approve` | Require project `review` authorization and atomically archive the exact preview as compressed, hash-verified source records before removing active rows; the durable receipt binds reviewer and reason. |
| `fact_archive_receipts` | Read bounded, integrity-checked archive receipts with source/archive hashes, fact IDs, reviewer, and approval reason. |
| `goal_list` | Compatibility listing of full snapshots for projects with at most 100 matching goals; larger result sets fail with a capacity error instead of loading unbounded history. |
| `goal_list_page` | Preferred listing: returns at most 100 compact goal cards plus the matching total and `next_offset`; filter by lifecycle status and load detailed facts only through per-goal reads. |
| `goal_children` | Compatibility listing of full snapshots for parents with at most 100 direct children; larger result sets fail with a capacity error. |
| `goal_children_page` | Preferred child-task listing: returns at most 100 compact cards, matching total, and `next_offset`, with optional lifecycle filtering. |
| `project_storage_usage` | Report project-attributed logical record counts/bytes and fact-history limits by data class and event class/state, aggregate global event-inbox capacity/gate without other project IDs, a bounded content-free staging scan with fixed-class file/byte totals, plus global SQLite database/WAL file sizes. |
| `goal_persist` | Requires project `review` authorization; project the goal to a configured canonical Markdown target and may release a previously reviewed purge gate. |
| `goal_reconcile` | Requires project `read` authorization; compare one configured Markdown projection with its structured goal and return `synced`, `missing`, `divergent`, or `malformed` plus hashes. It never edits either store. |
| `project_reconcile` | Requires project `read` authorization; scan one configured target once, return a page of per-goal comparisons and identify valid orphaned/malformed marker hashes plus unrecognized marker counts. The goal page is limited to 100 records and the marker inventory is bounded; incomplete scans are explicit. It never edits either store. |
| `sde_assess` | Requires project `write` scope. Assess up to 32 unique, selected same-goal facts; routine materiality returns `null`, otherwise at least one independently verified passing verification fact is required and only a pending review proposal is created. It never approves or persists an SDE. |
| `sde_review_queue` | List pending review packets. |
| `sde_review_detail` | Inspect one candidate's selected facts and evidence. |
| `sde_review_packet` | Under project `review` scope, return one bounded packet containing candidate facts/provenance and a freshly hashed staging inventory scoped to the candidate goal. The inventory is point-in-time and must still match at decision time; incomplete scans cannot authorize cleanup. |
| `sde_correction_record` | Append an authenticated, immutable correction linked to a decided candidate. |
| `sde_quality_feedback_record` | Record one authenticated post-disposition reviewer label; identical retries are idempotent and changed/duplicate submissions conflict. |
| `sde_quality_feedback_summary` | Return project-scoped counts by explicit label without reviewer IDs or rationale. |
| `artifact_inventory_discover(goal_id)` | Reviewer-scoped, bounded streaming hash inventory of regular files in `.curatormd-v2/staging/<goal_id>/`; files belonging to other goals cannot enter this receipt's manifest. Incomplete scans cannot release purge. |
| `sde_confirm` | Record human-approved/rejected decision and exact artifact manifest. An artifact may carry `retention_hold: legal` or `retention_hold: operational`; the hold is reviewer-selected and never inferred by the backend. |
| `artifact_inventory_complete` | Declare a receipt's full inventory; may release purge after canonical persistence. Newly assigned holds are attributed to the authenticated reviewer; unchanged existing hold attribution is preserved. |
| `artifact_purge_status` | Inspect the receipt plus each artifact's status (including `held`), retention category, attempt count, creation/last-attempt timestamps and ages, persisted retry deadline/countdown, content-free last error code, and next safe recovery action. |
| `release_artifact_hold` | Release one exact held path in a receipt after dedicated project `retention_hold_release` scope and plugin reviewer authorization; persist actor, timestamp, and rationale, then resume eligible purge. Exact replay is idempotent; changed actor/rationale conflicts. |
| `retry_pending_purges` | Immediately retry reviewed, canonically persisted manifests; authenticated use overrides an automatic retry deadline. |
| `event_queue_status` | Read this bound project's received/failed/quarantined counts, oldest pending age, and aggregate active/expired worker claims without exposing event content. |
| `project_activity_status` | Read retained event receipt/processing counts and recency, goal/fact totals, and pending/approved/rejected SDE totals. `events_observed=false` means no event receipt is retained; it does not assert capture completeness. This is activity, not readiness or a `project_health` signal. |
| `project_health` | Read an authorized, content-free aggregate of local queue/review/purge/capacity/staging state and trusted timestamped host dependency probes. Missing, malformed, or older-than-60-second probes are `unknown`; known backlog/failure is `degraded`; `healthy` requires complete fresh positive observations. |
| `project_metrics` | Render a content-free Prometheus exposition snapshot for this authorized project, including explicit reviewer-feedback label counts; excludes user content, reviewer IDs/rationale, artifact paths, and global database/WAL sizes. It does not provide an HTTP scrape server, dashboards, alerts, or model/token usage. |
| `event_quarantine_retry` | Retry one retained quarantined event; requires `event_retry` authorization and records the host-authenticated actor. |

Tool outputs are compact JSON text. Input dictionaries are validated again by
Curator's bounded domain/event models; MCP-generated JSON schemas are not the
only validation layer. In addition to the 16 KiB event envelope, direct tool
calls obey domain caps: 32 criteria and dependencies per goal, 16 evidence
references per fact, 16 criteria revisions per goal, 32 supporting facts per
SDE candidate, a single-line SDE rationale of at most 1,000 characters, and 500
unique artifact paths per receipt. Fact history is also
limited to 512 facts/512 KiB per goal and 10,000 facts/16 MiB per project.
SDE corrections are bounded to 32 per candidate and 1,000 per project; each
record contains one compact correction, rationale, authenticated reviewer ID,
and timestamp. Review detail exposes the linked correction records, while the
canonical goal block includes them on the next explicit `goal_persist` call.
Exhaustion rejects new facts without deleting old ones and appears in goal and
project-usage status. `event_id` must be
stable across retries. If
`source_sequence` is supplied, it must increase by one for the bound
`source_id`; omit it rather than inventing an ordering sequence. These are
local backend ceilings, not a complete global retention policy: event receipt
retention/recovery at the hard ceiling and budgets for other permanent data
classes remain open, so broad automatic capture remains gated. Fact compaction
is limited to the reviewer-approved routine-fact flow described below. The
global inbox stops accepting new event IDs at 250,000 receipts or 128 MiB of
retained logical row bytes across projects; project usage exposes aggregate
count/bytes and the capacity gate without exposing other project identifiers.
Exact idempotent replays remain available at the ceiling, and no rows are
silently pruned.
Capacity-failed event receipts retain only their digest and safe error code;
the producer must resubmit the same event ID and payload after an approved
capacity remedy.
The local durable router is not started by the MCP server. A host/operator may
invoke it through a fixed, authenticated project-to-service binding;
retryable failures use persisted capped exponential backoff, and SQLite
expiring claims coordinate concurrent router processes sharing the same
database. Quarantined events remain retained until an authorized retry.
Production scheduling, alert delivery, deployment-level worker coordination
and recovery evidence, and live Hermes identity binding are not provided by
these tools.
At active fact capacity, `fact_compaction_propose` previews only routine
`research` and `advice` facts with no criterion/evidence links and no SDE support
reference. Reviewers approve exact IDs plus the source SHA-256; the approval
transaction rechecks both and stores compressed exact source records and hashes,
reviewer identity, and reason before removing active rows. `goal_status` and
`goal_report` return archived facts only after verifying the compressed and
source hashes. Active fact limits count live rows; project usage reports archive
batches, items, and compressed bytes separately. The archive is capped at 64 MiB
per project and each source batch at 64 facts/256 KiB. Archive-capacity failure
leaves facts untouched. This reuses SQLite pages and does not promise to shrink
an already allocated database file; SQLite vacuum remains separate,
operator-controlled maintenance.
Criteria amendments require current `expected_revision` and
`expected_lifecycle_revision`; concurrent stale amendments conflict rather than
overwrite each other. Successful status and criteria transitions increment the
goal's lifecycle revision, returned by `goal_status`; ordinary fact appends do
not. The comparison and update are atomic, and stale requests write neither
facts nor status. Completed goals must first be reopened, and every amendment
starts a new evidence epoch. Raw schema-v1 events may omit the revision only for
legacy compatibility; omission is treated as revision 1 and stale events fail
closed rather than adopting the current revision.

`complete`, `cancelled`, and `superseded` are terminal. Cancellation and
supersession preserve an append-only fact; supersession also exposes the
replacement goal ID. Terminal goals cannot accept facts or be reopened. A
parent cannot be retired with unfinished children, and a goal cannot be retired
while unfinished dependents still reference it. Competing terminal transitions
are serialized and the first wins; later requests return a failed receipt.
Cancelled/superseded children do not satisfy parent criteria, and retired
dependencies do not satisfy dependents. Criteria amendments use both revision
guards; nonterminal status changes use an expected lifecycle revision.

`goal_persist` requires project `review` authorization. `goal_persist`,
`sde_confirm`, `artifact_inventory_complete`, and
`retry_pending_purges` carry MCP `destructive_hint` annotations for client UI.
Annotations are advisory, not enforcement: project permissions, immutable
review receipts, canonical persistence proof, full inventory, path/hash checks,
and the purge adapter remain the security gates.

## Verification boundary

The SDK `Client` in-memory test verifies the registered schemas and full goal
lifecycle. A second test launches the server as a subprocess over actual stdio
and confirms project/caller are absent from the tool schema. Neither test
connects to Hermes Core or proves its profile authentication, profile/project
selection, permission adapter, shared rate limiter, or production rollout.
Those host integration gates remain open.
