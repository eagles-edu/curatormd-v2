# Curator V2 history

## 2026-10-19

- Hardened host resolver receipts at construction: bounded safe single-line
  fields, lowercase SHA-256, timezone-aware timestamps, and exact boolean
  revocation state are required before attestation. Added malformed-receipt
  regressions. The full 285-test suite passes on Python 3.12.3, 3.13.15, and
  3.14.7; strict Pyright, errors-only Pylint, Bandit, locked dependency audit,
  and `git diff --check` pass. These checks validate receipt shape, not host
  authentication or real evidence sources.
  The persistence recorder refused the existing dirty history, so this entry
  was appended manually under SOP.
- Corrected `docs/project-plugin-v1.md` to separate the implemented durable
  project registry and exact subject/project/action grants from still-open
  trusted Hermes identity and repository/config fingerprint binding. Local
  fixture and consumer-checkout probes do not establish released installation
  or runtime isolation.
- `persistence_status` observed that all four canonical stores were absent and
  capture was degraded; initialized the stores under this repository's declared
  persistence boundary. A follow-up confirms the four files exist, but the
  available legacy `persistence_status` bridge still reports degraded capture;
  this does not verify the V2 runtime, which remains unbound and unverified.
- Hermes Core's source checkout contains an opt-in, root-account-scoped
  Host Steward prototype for bounded metadata-only directory inventory and
  non-executable cleanup proposals. Six focused Host Steward tests and 30
  adjacent `disk-cleanup` tests pass, with Ruff and strict type checks passing.
- The Host Steward prototype is not enabled in the live Hermes account. Human
  approval, managed cleanup, post-action service verification, receipts, and
  end-to-end project isolation remain open; see `docs/curator-v2-plan.md`.
- The installed `curatormd-v2-mcp` launcher passed a local stdio goal write/read
  test against an isolated temporary consumer. The test confirmed the configured
  project ID and goal criteria round-trip, omitted project/caller arguments from
  the MCP schema, and exited through the client shutdown path. This does not
  establish live Hermes identity, production routing, or deployment.
- Curator V2 now provides a tested reference adapter from bounded Hermes Codex
  turn hooks to compact `intent`, non-verifying `change`, and `open_gate` facts.
  It requires a host-supplied binding and producer sequence/timestamp, derives
  deterministic opaque IDs, rejects unknown fields/session mismatches, and
  omits transient runtime metadata. A local acceptance test routes start/end
  events through the durable inbox/router into the goal ledger and confirms no
  criterion verification or completion is inferred. The full local suite passes
  228 tests on Python 3.14.7, Pyright reports 0 errors, and errors-only Pylint
  passes. Hermes identity resolution, durable outbox, hook invocation, backend
  delivery, and deployment remain unverified.
- Curator V2 schema v11 adds a durable project registry, host-supplied
  repository/config fingerprints, exact action grants, explicit suspension,
  registration audit, and append-only grant revocation. Grant administration is
  separated behind an injected host policy and is not exposed through MCP; this
  does not authenticate Hermes callers or bind the existing stdio launcher.
  Current local evidence is 237 passing tests on Python 3.12.3, 3.13.15, and
  3.14.7 plus clean Pyright, errors-only Pylint, Bandit, lockfile audit, and
  whitespace checks. Hermes binding, launcher integration, and deployment
  evidence remain open. Curator's legacy persistence status still reports
  `capture_status: degraded`; V2 unit checks do not establish that runtime.
- Repository-plugin inspection remains read-only by default; optional action
  adapter IDs require both repository config opt-in and trusted-host
  registration. No action execution API is exposed. All 238 tests pass on Python
  3.12.3, 3.13.15, and 3.14.7; Pyright, errors-only Pylint, and diff checks
  pass. Real consumer installation and host action execution remain open.
- Schema v12 adds append-only, reviewer-authorized SDE quality labels after a
  durable decision, with exact replay and project-scoped aggregate counts; the
  labels remain human QA observations, not ground truth or model-training data.
  The v11-to-v12 migration, API/MCP path, store-reopen persistence, and
  content-free metrics pass within a 239-test Python 3.12/3.13/3.14 matrix;
  Pyright, errors-only Pylint, Bandit, lock audit, and diff checks pass. Live
  Hermes reviewer identity and owner-approved retention/evaluation policy remain
  open.
- 2026-10-19: Project metrics now separate failed/quarantined event receipts
  into fixed evidence-rejected, trusted-adapter-error, and other categories.
  Resolver exception details are suppressed; regressions prove rejected or
  operationally failed evidence never becomes a verification fact and counts
  remain project-scoped. All 240 tests pass on Python 3.12.3, 3.13.15, and
  3.14.7; Pyright, errors-only Pylint, Bandit, lock audit, and diff checks pass.
  Deployed scrape, dashboards, and alert delivery remain open.
- 2026-10-19: Added a project-read-authorized API and MCP `goal_reconcile` tool
  for configured Markdown targets. Tests verify missing/synced/divergent
  results, ignore unrelated document edits, deny unauthorized callers, and
  prove reconciliation never rewrites manual block edits. All 241 tests pass
  on Python 3.12.3, 3.13.15, and 3.14.7; Pyright, errors-only Pylint, Bandit,
  lock audit, and diff checks pass. Conflict repair and authoritative-store
  policy remain open.
- 2026-10-19: Added a project-read-authorized, bounded `project_reconcile`
  operation. It pages structured goals, scans one configured Markdown target,
  reports orphaned/malformed marker hashes, and explicitly flags inventories
  beyond its 5,000-marker limit. Tests cover API/MCP access, pagination, orphan
  detection, over-limit state, and read-only behavior. All 244 tests pass on
  Python 3.12.3, 3.13.15, and 3.14.7; Pyright, errors-only Pylint, Bandit,
  lock audit, and diff checks pass. Conflict repair and authoritative-store
  policy remain open.
- 2026-10-19: The published `goal.started` fixture now uses an exact checklist
  digest and passes through the authenticated local API with durable,
  idempotent replay and zero retained payload bytes. Separately, the event
  shape passed through GPTMD's actual repository-owned plugin config and exact
  checklist revision using a disposable SQLite store. The 245-test Python
  3.12/3.13/3.14 matrix, Pyright, errors-only Pylint, Bandit, lock audit, and
  diff checks pass. Shared-plugin interoperability, installed-package
  lifecycle, and live Hermes delivery remain open.
- 2026-10-19: Added a review-authorized `sde_review_packet` operation that
  combines selected candidate facts/evidence with a fresh bounded staging
  manifest. API/MCP tests prove read-only denial and exact inventory agreement;
  all 246 tests pass on Python 3.12.3, 3.13.15, and 3.14.7, with Pyright,
  errors-only Pylint, Bandit, lock audit, and diff checks passing. The inventory
  remains point-in-time, and live authenticated reviewer UX is still open.
- 2026-10-19: Built the Curator V2 wheel, installed it in a clean Python 3.12.3
  environment, and ran the installed `curatormd-v2-mcp` launcher against a
  temporary repository config with `PYTHONPATH` unset; project-bound goal
  start/status passed. The 246-test suite passes locally. This is
  package/fixture evidence only: no consumer repository was modified or
  installed, and Hermes identity and production rollout remain open.
- 2026-10-19: Reference-plugin review inventories now require a valid project
  goal and scan only `.curatormd-v2/staging/<goal-id>/`; SDE review packets
  declare `scope_goal_id`, and decision/finalization re-scan the same scope.
  Missing directories yield complete-empty manifests; symlinked goal scopes
  fail closed. An API lifecycle regression proves canonical persistence purges
  only the reviewed goal's file while another goal's file remains. The local
  producer API now streams atomic no-clobber artifacts into goal/class scope,
  with hard ceilings of 64 MiB per file, 256 MiB and 500 files per goal; these
  are not age-retention policy. An exclusive advisory staging-directory lock
  serializes cooperating plugin writers, review/finalization, and purge; a
  concurrency test confirms review waits for an atomic write. Direct filesystem
  writers and network-filesystem lock semantics remain open. All 255 tests pass
  on Python 3.12.3, 3.13.15, and 3.14.7. Pyright, errors-only
  Pylint, Bandit, `uv audit`, and diff checks pass. Authorized staging usage
  now includes fixed-class file/byte totals in API/MCP output and content-free
  metrics; this enables measurement, not retention or purge policy. The local
  launcher now suppresses startup exception details, and a backup test confirms
  processed event snapshots retain the digest receipt but not the serialized
  event envelope. Failed/quarantined payload backup policy and full WAL/log/
  trace/upstream data-flow coverage remain open. A fresh wheel from this code
  installed in an isolated Python 3.12.3 environment and passed the launcher
  fixture with `PYTHONPATH` unset. External producer routing, owner-approved
  retention policy, and complete out-of-root artifact coverage remain open.
- 2026-10-19: Added authorized `goal_list_page`, which returns at most 100
  compact goal cards, matching total, and next offset after lifecycle filtering;
  detailed facts and review history remain per-goal reads. The legacy full-
  snapshot listing queries at most 101 goal IDs and fails closed above 100.
  API/MCP coverage verifies pagination, filtering, authorization, compact output,
  stable capacity errors, and the over-limit path. All 257 tests pass on Python
  3.12.3, 3.13.15, and 3.14.7; Pyright, errors-only Pylint, Bandit, and
  `git diff --check` pass. This bounds overview reads but does not establish a
  production dashboard or a goal-retention budget.
- 2026-10-19: Added authorized `goal_children_page` with compact direct-child
  cards, filtered totals, and next offsets; the legacy child full-snapshot list
  now fails closed above 100 after a bounded database query. Internal parent
  completion checks still inspect every child. API/MCP tests cover pagination,
  filtering, authorization, compact output, and the compatibility ceiling. All
  258 tests pass on Python 3.12.3, 3.13.15, and 3.14.7; Pyright, errors-only
  Pylint, Bandit, lock audit, and diff checks pass. Production dashboards and a
  project goal-retention budget remain open.
- 2026-10-19: Goal reports now fetch bounded child (32), pending-SDE (16), and
  receipt (16) pages with exact SQL aggregates, instead of hydrating unbounded
  histories before rendering. Pagination offsets are exposed through the
  service, API, MCP tool, and project plugin. Regression coverage forbids the
  old unpaged store calls and checks child totals/continuation. All 259 tests
  pass on Python 3.12.3, 3.13.15, and 3.14.7; Pyright, errors-only Pylint,
  Bandit, and `git diff --check` pass. Capture remains degraded; no deployment
  or consumer integration is claimed.
- 2026-10-19: Bounded `goal_status` and its truth projection too: SDE candidates
  and purge-pending receipts now return 32/16-record pages with exact totals,
  SDE-state counts, and next offsets through service/API/MCP/project plugin.
  A 105-row regression proves page sizes, totals, continuation, and no calls to
  unpaged history readers; MCP integration accepts explicit offsets. All 260
  tests pass on Python 3.12.3, 3.13.15, and 3.14.7; Pyright, errors-only
  Pylint, Bandit, `uv audit`, and `git diff --check` pass. Local repository
  evidence only; deployment and consumer installation remain open.
- 2026-10-19: Added optional consumer-configured staging byte and file-count
  budgets. Budgeted plugin writes require a complete bounded staging scan,
  stop before exceeding configured limits, and expose observed totals and
  limits through authorized storage reads and content-free metrics. No
  artifacts are auto-deleted; age retention and cleanup approval remain open.
  The final tree passes 263 tests on Python 3.12.3, 3.13.15, and 3.14.7,
  plus Pyright, errors-only Pylint, Bandit, lockfile audit, and diff checks.
- 2026-10-19: Strengthened Markdown projection recovery tests for both update
  orders. Ledger-first changes survive store reopen and can be projected; an
  interruption after Markdown replacement leaves the canonical receipt
  uncommitted across store reopen, then an idempotent retry commits proof
  before purge. The 15-test projection suite passes on Python 3.12.3 and
  3.14.7; the full 264-test suite passes on Python 3.13.15. Pyright,
  errors-only Pylint, Bandit, dependency audit, and diff checks pass locally.
  Process-kill/power-loss, production recovery, and authoritative-store policy
  remain open.
- 2026-10-19: A locally built Curator V2 wheel was installed into GPTMD's
  ignored `.curatormd-v2/venv` using pinned runtime dependencies. The installed
  launcher completed a real MCP stdio handshake against GPTMD's repository-
  owned config and exposed 42 tools. Read-only probes returned project `gptmd`,
  zero goals/records/artifacts, and `health=unknown` with host dependencies
  unobserved; an attempted goal write was denied without a write grant. The
  disposable database was removed at process exit; GPTMD source and canonical
  Markdown were untouched. This verifies a local consumer install/read path
  only, not release packaging, Hermes identity or activation, evidence ingestion,
  canonical persistence, purge, or deployment. The Curator V2 plan's consumer
  integration gate remains open.
- 2026-10-19: Reconciled release gate F with the installed GPTMD consumer
  evidence recorded above; the earlier statement that no consumer installation
  existed was stale. The locked local suite passes all 264 tests on Python
  3.14.7. Release packaging/rollback, trusted host identity, evidence-backed
  persistence and purge through a consumer, retention policy, and deployment
  remain open.
- 2026-10-19: Added a subprocess-level cross-project isolation regression using
  two distinct consumer configs and launchers against one SQLite backend. Each
  launcher writes and lists only its own project goal; cross-project status
  requests return not-found. The full locked suite passes 265 tests on Python
  3.14.7; the new integration test passes strict Pyright with 0 errors.
  This is local MCP/process-boundary evidence, not live Hermes identity or
  deployment evidence; trusted project persistence and lifecycle remain open.
- 2026-10-19: Added a packaged `curatormd-v2-stage` stdin-only producer
  entrypoint. It validates the repository config and existing project goal,
  then delegates to the plugin's locked, bounded, no-clobber staging writer;
  output contains only path and SHA-256, and failures do not echo producer
  payloads. Tests verify exact bytes, digest, `0600` file mode, sanitized
  failure, and no partial artifact on an unbound goal. The full locked suite
  passes 267 tests on Python 3.14.7, strict Pyright reports 0 errors, and the
  installed console command's help smoke passes. This enables a local producer
  integration path but does not integrate any real producer or authenticate a
  remote source; real producer audits, retention, approval, persistence, and
  purge lifecycle remain open.
- 2026-10-19: The end-to-end MCP SDE/review/persistence/purge regression now
  stages its import using `curatormd-v2-stage`, then carries that artifact
  through reviewer inventory, immutable decision, canonical Markdown write,
  explicit operational hold, and immediate exact-file purge after hold
  release. The full suite passes 267 tests on Python 3.14.7; Pyright reports 0
  errors and focused errors-only Pylint passes. This fixture proves local
  lifecycle composition only; reviewer authorization is synthetic and no real
  producer or Hermes identity is integrated.
- 2026-10-19: Managed Markdown goal projections now include an unkeyed SHA-256
  block checksum. Valid stale generated blocks remain updatable; checksum-
  mismatched edits fail closed; exact legacy blocks may be upgraded only when
  they match the current projection, while stale unsealed legacy blocks are
  preserved. Reconciliation classifies checksum mismatch as malformed. Tests
  cover exact legacy upgrade, stale legacy refusal, manual-edit preservation,
  read-only drift, and purge retry. The full suite passes 269 tests on Python
  3.14.7; Pyright reports 0 errors and focused errors-only Pylint passes. This
  checksum detects accidental edits, not authentication or system-of-record
  authority.
- 2026-10-19: Added ADR 0001 documenting the managed Markdown projection
  checksum and legacy-block policy. The decision applies to the local Curator
  V2 reference implementation only: the unkeyed checksum detects accidental
  edits but is not authentication and does not select deployment-wide
  system-of-record authority or authorize conflict recovery. The plan's
  architecture-decision-record item is complete; deployment-owner retention,
  privacy, threat, and operator requirements remain open. The persistence
  recording tool refused because this history file has unresolved edits, so
  this factual entry was added manually under the repository SOP.
- 2026-10-19: The full locked unit suite passes 269 tests independently on
  Python 3.12.3, 3.13.15, and 3.14.7. Strict Pyright, errors-only Pylint,
  Bandit, locked dependency audit, and `git diff --check` pass locally. The
  full Pylint inventory exits 28 with 261 non-blocking findings, leaving the
  repository-wide lint cleanup open. The release ledger now records this
  matrix; hosted GitHub Actions remain unverified. The persistence recording
  tool again refused because this history file has unresolved edits, so this
  result was added manually under the repository SOP.
- 2026-10-19: Added `SQLiteTokenBucket` for local cross-process request quotas
  and wired the stdio factory to share the default 120 requests per
  subject/project per 60 seconds through schema v13. Bucket state is bounded to
  10,000 identities; idle rows are removed only after a complete refill period.
  Tests cover separate connections, concurrent consumption, restart, clock
  rollback, full-refill pruning, invalid bounds, and migration/rollback. All 277
  tests pass on Python 3.12.3, 3.13.15, and 3.14.7; strict Pyright, errors-only
  Pylint, Bandit, dependency audit, and diff checks pass. Full Pylint remains at
  261 non-blocking findings. This is same-host SQLite coordination, not live
  Hermes authentication, distributed limiting, or production quota policy.
  The persistence recorder refused because `HISTORY.md` has unresolved edits;
  this factual entry was added manually under the repository SOP.
- 2026-10-19: Rebuilt the Curator V2 wheel from the current worktree and
  installed it into GPTMD's ignored `.curatormd-v2/venv`. Through GPTMD's
  repository-owned config and exact configured checklist line, the installed
  MCP server recorded and activated a project-bound goal, appended a change
  fact, and kept an unsupported completion open with its criterion unmet. The
  integration database was temporary; GPTMD source and canonical Markdown
  were unchanged. Hermes identity/runtime, evidence/review, canonical
  persistence, purge, and deployment remain unverified. All 277 V2 unit tests
  pass. The persistence recorder refused because `HISTORY.md` has unresolved
  edits, so this factual entry was added manually under the repository SOP.
- 2026-10-19: Removed eight concrete full-Pylint findings (line length,
  missing test-helper docstrings, and import style) without changing behavior.
  The complete suite still passes 277 tests; the full Pylint inventory is now
  253 non-blocking findings, chiefly structural design/refactor and duplicate
  code diagnostics. Errors-only Pylint remains the enforced CI gate; broad
  exception boundaries remain deliberately fail-closed and are documented in
  code. The persistence recorder refused because this history file has
  unresolved edits, so this verified result was added manually under SOP.
- 2026-10-19: Added `curatormd-v2-maintenance`, an explicit one-shot runner for
  bounded, due-only retries of previously reviewed and canonically persisted
  purge targets. Project staging operations are locked; backoff and holds are
  respected; output is aggregate-only and pending work returns an alertable
  exit code. A disposable integration test injected a transient purge failure,
  reopened the SQLite store through the CLI, and confirmed the exact approved
  artifact was removed on due retry. The current local wheel was installed in
  GPTMD's ignored V2 environment and the command loaded its actual config with
  zero due work using a temporary database. All 282 tests, Pyright, errors-only
  Pylint, and Bandit pass; full Pylint remains at 253 non-blocking findings.
  Production scheduling, alert delivery, Hermes authorization, and crash/retry
  reconciliation remain open. Curator's recorder cannot append while this
  history file has unresolved edits, so this result was added manually under
  SOP.
- 2026-10-19: User reconfirmed the ownership boundary: CuratorMD V2 owns the
  global backend and reusable plugin package/interface; each consumer owns its
  repository-local plugin binding/config, runtime state, and project records.
  GPTMD is a consumer only, not part of the CuratorMD V2 system or repository;
  use it only as a scoped compatibility/pilot target. Host Steward remains
  Hermes Core-owned. The recorder is unavailable while this history file has
  uncommitted edits, so this decision was recorded manually under SOP.
- 2026-10-19: Re-ran the current 282-test suite sequentially on Python 3.12.3,
  3.13.15, and 3.14.7; all three runs pass. Strict Pyright, errors-only
  Pylint, Bandit, locked dependency audit, and whitespace checks pass in the
  restored default Python 3.12 environment. A full Pylint inventory still has
  253 non-blocking findings (9.78/10); the focused errors-only gate is clean.
  These checks cover local V2 code,
  not hosted CI or live Hermes/consumer deployment. The recorder still cannot
  append to this uncommitted history file, so this verification update was
  added manually under SOP.
- 2026-10-19: Added project-authorized `project_activity_status` across the
  Curator V2 store, repository plugin adapter, API, and MCP. It reports
  content-free retained event counts/state/recency plus goal/fact/SDE totals;
  `events_observed` does not imply producer connectivity or complete capture.
  It is separate from operational `project_health`. The 283-test suite passes
  sequentially on Python 3.12.3, 3.13.15, and 3.14.7; strict Pyright,
  errors-only Pylint, Bandit, and whitespace checks pass. The persistence
  recorder still refuses while this history file has uncommitted edits, so
  this update was added manually under SOP.
- 2026-10-19: Reverified the 283-test suite on Python 3.14.7 without concurrent
  quality jobs; it passes in 30.6 seconds. A simultaneous test/type/lint run
  caused one 15-second producer-subprocess timeout; the exact SDE/review/
  persistence/purge test passed alone in 2.0 seconds, then all tests passed
  sequentially. Pyright, errors-only Pylint, Bandit, `uv audit`, and
  `git diff --check` pass. Avoid competing CPU-intensive checks with tests that
  enforce short subprocess deadlines; rerun sequentially to establish whether
  a timeout is a product defect. No consumer or Hermes runtime was changed or
  verified. The recorder still cannot append to this uncommitted history file,
  so this result was added manually under SOP.
- 2026-10-19: Built the current V2 wheel and installed it in a fresh temporary
  Python 3.12 environment. Its packaged MCP server loaded GPTMD's actual
  repository-owned plugin config and exposed 43 tools; a disposable-database
  read-only probe reported project `gptmd`, zero retained events/goals/facts/SDEs,
  `health=unknown`, and denied goal creation. No GPTMD files changed. This did
  not update or verify the separate already-running Hermes MCP process, which
  uses the Curator V2 source checkout, nor prove authenticated identity, capture,
  production review, persistence, purge, or deployment. The persistence
  recorder cannot append while this history file has uncommitted edits, so this
  result was added manually under SOP.
- 2026-10-19: Curator V2's MCP initialization guidance now carries the task
  workflow: bind the user/checklist item, define observable criteria before
  work, record typed fact bullets, reconcile verified/open status and next
  action, and keep human SDE review, canonical persistence, and purge separate.
  An MCP end-to-end regression checks the guidance. All 283 tests, strict
  Pyright, errors-only Pylint, Bandit, `uv audit`, and `git diff --check` pass.
  This guides assistants but does not produce events automatically or
  authenticate Hermes. The recorder refused because history has uncommitted
  edits, so this fact was added manually under SOP.
- 2026-10-19: Added a bounded-memory regression for staging a generated 24 MiB
  import through the repository plugin. The stream rejects reads above 64 KiB,
  the staged file's exact size and SHA-256 are verified, and peak traced Python
  allocations stay below 4 MiB. Event envelopes remain capped at 16 KiB and
  staged files at 64 MiB. The full 284-test suite passes sequentially on Python
  3.12.3, 3.13.15, and 3.14.7; strict Pyright, errors-only Pylint, Bandit,
  `uv audit`, and `git diff --check` pass. These are local allocation and test
  results, not whole-process RSS or real producer/deployment proof. The
  persistence recorder refused because HISTORY.md has uncommitted edits; this
  verified result was recorded manually under SOP.

## 2026-10-19 — Curator V2 hosted CI and SDE review boundary

**Decision:** - **Verified (2026-10-19):** Curator V2 commit `c5c7ede` passed hosted CI run `39277608798`, including the Python 3.12/3.13/3.14 test matrix, clean-wheel launcher smoke test, Pyright, blocking Pylint, Bandit, and dependency audit. The current local suite passes 287 tests on Python 3.13.15; full Pylint still reports 258 non-blocking findings.
- **Implementation boundary:** project-scoped SDE review queue/detail/packet/decision API and MCP tools exist and are covered by tests. Production Hermes identity/role binding and reviewer UI remain open; local profile IDs and synthetic test authorizers are not production authentication.

**Rationale:** Confirmed the current worktree, local test/quality results, and successful hosted workflow against its exact commit; inspected the API/MCP review methods and tests.

**Impact:** Keeps hosted verification distinct from release readiness and avoids misreporting an implemented review MCP surface as missing.

<!-- curatormd:record_id=4566f029608c9811829adba3b35e19b0;content_sha256=4566f029608c9811829adba3b35e19b00dee54c4e25886a6e1a9b5a9d2a2102e -->

## 2026-10-19 — MCP failure-log privacy regression

**Decision:** - **Verified (2026-10-19):** `tests.test_hosted_mcp` passes all 8 tests. The sanitized MCP tool-failure regression now captures the emitted warning and confirms only the public error code and exception type are logged; sensitive exception text is absent from both the MCP response and log record.

**Rationale:** The focused test and complete hosted-MCP module passed after adding an explicit log-capture assertion.

**Impact:** Protects the no-raw-exception-content boundary at the MCP response and logging edges.

<!-- curatormd:record_id=d41c030cf22a85ec05f70049bde979a8;content_sha256=d41c030cf22a85ec05f70049bde979a8b2f8ede057036ffcf46a6953c59ee34c -->

## 2026-10-19 — Router claim recovery after worker process death

**Decision:** Verified locally on 2026-10-19: the complete Curator V2 suite passes 288 tests on Python 3.13.15, the router module passes all 6 tests, strict Pyright reports 0 diagnostics, and the full Pylint scan reports 257 non-blocking findings with no errors or fatals. A new subprocess test kills a worker after its event-claim transaction commits, waits for lease expiry, recovers through a fresh router, and confirms stable-ID replay does not insert a duplicate.

**Rationale:** The full unit suite, focused router module, strict Pyright, and fresh whole-repository Pylint inventory passed on the current worktree.

**Impact:** Adds process-death recovery evidence while keeping production scheduler, multi-host, load, and power-loss claims open.

<!-- curatormd:record_id=28596b7df7cf3a2cbc4fb8f702c4cf66;content_sha256=28596b7df7cf3a2cbc4fb8f702c4cf66dbd94454feaaac5e1c838d30429988cf -->

## 2026-10-19 — Final cross-process router recovery verification

**Decision:** Verified locally on 2026-10-19: the full suite passes 288 tests on Python 3.13.15, all 6 router tests pass, strict Pyright reports 0 diagnostics, and a fresh full Pylint scan reports 258 non-blocking findings with zero errors/fatals. The recovery regression uses SIGKILL on the claiming worker, then a separate subprocess opens the same SQLite database, routes the expired event, and the parent confirms stable-ID replay is idempotent. The latest test remains uncommitted and has no hosted CI result yet.

**Rationale:** Confirmed the updated subprocess integration with the complete test suite, router module, strict Pyright, and whole-repository Pylint inventory.

**Impact:** Establishes cross-process local recovery while keeping hosted/deployment claims separate.

<!-- curatormd:record_id=6e4f45054eeef52d9270472708312570;content_sha256=6e4f45054eeef52d92704727083125709fa0f30a84e2e98ac0ed5e876f9d7034 -->

## 2026-10-19 — Crash-recovery snapshot and restore regression

**Decision:** Verified locally on 2026-10-19: all 288 tests pass on Python 3.13.15, Pyright reports 0 diagnostics, and full Pylint reports 258 non-blocking findings with zero errors or fatals. The router test kills the claiming worker with SIGKILL, processes the event from a replacement subprocess after lease expiry, then snapshots/restores SQLite to a new file and verifies the processed receipt and goal state.

**Rationale:** The complete suite and the router/backup integration tests pass on the current worktree; type and lint checks were rerun.

**Impact:** Connects crash recovery to the tested non-overwriting backup/restore path without claiming production power-loss durability.

<!-- curatormd:record_id=8ea2c9fc3b49e39a14f5af683488e64f;content_sha256=8ea2c9fc3b49e39a14f5af683488e64fdef244ceaa8eeea93a66a69381cf1f0f -->

## 2026-10-19 — Hermes Codex lifecycle outbox prototype

**Decision:** - 2026-10-19: Hermes Core source adds opt-in, profile-local SQLite delivery for Codex lifecycle hooks; bounded source envelopes are committed before dispatch, assigned stable IDs/sequences/timestamps, and retried in order until durable consumers explicitly return `True`.
- Hermes local verification: focused Codex lifecycle/MCP/profile-isolation checks passed; A→B→A tests verify separate outboxes. Curator translator tests passed independently.
- Scope remains local source/test evidence only: no Curator durable hook consumer, authenticated identity, session-to-goal binding, live lifecycle delivery, deployment, or end-to-end privacy/replay acceptance is verified.

**Rationale:** Keep source/test evidence distinct from live deployment and avoid overstating Hermes-to-Curator integration.

**Impact:** Records implemented Hermes producer-side progress and preserves remaining Curator integration gates.

<!-- curatormd:record_id=62226707849a04f55378ff6163975c87;content_sha256=62226707849a04f55378ff6163975c876805f710f9954fbc7799f4bc01b2e42b -->

## 2026-10-20 — 2026-10-20 Curator V2 fact source provenance

**Decision:** - 2026-10-20: Local Curator V2 SQLite v15 now retains the first durable source-event ID on event-created facts. Reports and canonical Markdown render the ID; reviewer-approved compaction preserves it through hash-verified archive retrieval. Legacy/local facts remain null rather than receiving inferred provenance. Event, migration, schema, compaction, and Markdown regressions pass; the full local suite previously passed 296 tests. This is local test evidence, not deployed Hermes integration.

**Rationale:** Record only verified implementation and test evidence while preserving the explicit deployment boundary.

**Impact:** Improves fact auditability across event intake, canonical projection, and approved archival.

<!-- curatormd:record_id=fb13e239970b2c113b4119cd8e2a20fb;content_sha256=fb13e239970b2c113b4119cd8e2a20fb5fe8f10b54d7cf32b9ca0d5709601b53 -->

## 2026-10-20 — 2026-10-20 Hermes Core integration regression batch

**Decision:** - 2026-10-20: The dirty Hermes development checkout at `/home/eaglesvn/.hermes/hermes-agent` passed its repository test runner for six affected files (86 tests, 0 failures) covering Codex app-server hooks, profile scope, MCP trust, runtime migration, and Host Steward. Pinned Ruff 0.15.10 passed on the changed Python files. Curator V2's full local suite passed 296 tests; the event, archive, and Markdown regression batch passed 59 tests. All are local source/test evidence only; no live gateway event or deployment was exercised.

**Rationale:** Update the implementation evidence to the actual Hermes development checkout and the current grouped regression results.

**Impact:** Keeps the Hermes integration gate evidence accurate without implying runtime deployment.

<!-- curatormd:record_id=acaeac718ec274237a9c99ae903dc997;content_sha256=acaeac718ec274237a9c99ae903dc997638880d3e4328265bd7ffd0a4f0a89c1 -->

## 2026-10-20 — Host Steward cleanup approval contract

**Decision:** - Host Steward remains a Hermes Core account concern; CuratorMD does not own or invoke host cleanup.
- Hermes source integration requires a proposal-bound one-time `once` decision plus a plugin-owned receipt; global approval bypasses and remembered approvals alone do not authorize cleanup.
- Managed cleanup is restricted to the registered `empty_configured_cache` action on the exact configured target, with an unchanged inventory manifest and bounded receipts.
- Hermes approval hooks expose the decision and surface but not an authenticated human subject to this plugin; owner-authenticated identity and live deployment remain open gates.

**Rationale:** Verified against the Hermes approval implementation and local Host Steward tests. This records source-level integration state only; no live host cleanup or deployment occurred.

**Impact:** Preserves the Hermes/Curator ownership boundary while enabling reviewable, fail-closed host cleanup.

<!-- curatormd:record_id=988c58d6101c2832a2cd8338bff9d4ab;content_sha256=988c58d6101c2832a2cd8338bff9d4abc963f54cc6cab56ba40974d75057c632 -->

## 2026-10-20 — Local Hermes MCP request identity binding

**Decision:** - The local Curator V2 profile launcher now rejects every tools/call request unless Hermes-injected profile and bounded session metadata are present and the profile matches the launcher-pinned caller; focused stdio tests and the 297-test suite passed, strict Pyright/Pylint/Bandit passed.

**Rationale:** Record verified local request-path enforcement while preserving the limit that MCP metadata is not cryptographic identity and live Hermes transport/deployment remain unverified.

**Impact:** Missing or mismatched local Hermes context fails before Curator tool dispatch; production identity and transport gates remain open.

<!-- curatormd:record_id=66320e41cfc43e4af85adf2ce7c10726;content_sha256=66320e41cfc43e4af85adf2ce7c1072672f49ae93593eae7dae4d02f45256901 -->

## 2026-10-20 — Local launcher durable project binding

**Decision:** - The local Curator V2 launcher now requires an existing active registry record matching the canonical repository-root fingerprint, exact `.curatormd-v2.toml` SHA-256, and backend API version; runtime API authorization reads exact durable profile grants and current registration state, with launcher write access only a cap. The plugin never self-registers or grants. Tests cover missing registration, config drift, cross-project stdio isolation, and suspension; the full 298-test suite, Pyright, Pylint, and Bandit passed.

**Rationale:** Record the verified local activation boundary and keep trusted Hermes authentication, authenticated admin provisioning, and deployment validation separate.

**Impact:** Local consumer access is no longer derived from CLI flags alone; durable host-provisioned exact grants and matching repository/config identity are required.

<!-- curatormd:record_id=887784e15e1d1aa6373717071075579a;content_sha256=887784e15e1d1aa6373717071075579ab5aebda4008affefbc8b23ecea03ec73 -->

## 2026-10-20 — Local project-access CLI and enforcement verification

**Decision:** 2026-10-20: Added the attended `curatormd-v2-access` operator command for local project registration, fingerprint updates, suspension/reactivation, exact grants/revocations, and audit viewing outside MCP. Every operation requires a TTY and exact typed confirmation; the recorded administrator is only the effective local Unix UID. Confirmation prompts go to stderr so command stdout remains machine-readable JSON. The local profile launcher now uses the durable active registration and exact grants; focused access/MCP tests and the full 300-test Python 3.13.15 suite pass, along with strict Pyright, errors-only Pylint, Bandit, `uv audit`, `uv lock --check`, and `git diff --check`. This is local source/test evidence, not authenticated Hermes identity or deployment proof.

**Rationale:** Record the verified operator path and local enforcement while preserving the open gates for deployment identity, verified administrator identity, and live Hermes transport.

**Impact:** Operators can provision the local SQLite registry without exposing administration through MCP; the command does not elevate a profile assertion or local UID into verified human identity.

<!-- curatormd:record_id=5b7795bf4ab86cc1b0d58577db583f49;content_sha256=5b7795bf4ab86cc1b0d58577db583f4993eef3ad449bf5a6eeb13fcd2c0e3d0e -->

## 2026-10-20 — Content-free purge failure status and schema v16

**Decision:** 2026-10-20: Purge failures now persist fixed content-free `PurgeFailureCode` values rather than exception messages; the SQLite store rejects unrecognized error strings. The v15-to-v16 migration replaces legacy failed-target details with `legacy_failure_detail_redacted` without changing failed status, attempts, or retryability. Migration failure injection proves the data and version stamp roll back before a successful retry. MCP status regression injects a sensitive exception marker and verifies only `filesystem_error` is returned, then confirms retry succeeds. The full local suite passes 301 tests; strict Pyright, errors-only Pylint, Bandit, lock/dependency audit, and diff checks pass. This is local evidence only; raw payload retention in failed/quarantined events, broader logging/WAL/backup/trace/upstream review, and production migration approval remain open.

**Rationale:** Close the specific purge exception-detail leak at persistence and MCP status boundaries, while retaining retry state and explicitly leaving wider privacy/deployment gates open.

**Impact:** Artifact purge failures remain actionable by stable code and retry state without retaining arbitrary exception/path details in new or migrated purge status.

<!-- curatormd:record_id=0a1a76c152c79a7caa8abb139b15e7d8;content_sha256=0a1a76c152c79a7caa8abb139b15e7d86f7019721e5e54551a84929f2370603f -->

## 2026-10-20 — 2026-10-20 Hermes Core local Codex usage ledger

**Decision:** - In the Hermes Core fork, Codex app-server turn-end usage is now recorded locally by explicit project binding in the profile-local `curatormd/codex-outbox.sqlite3`; aggregate reads separate totals by project and provider/model, and missing/invalid counts remain `unknown` rather than zero.
- Token counts are excluded from hook deliveries and Curator event envelopes; 75 focused tests passed, the final outbox test passed again (8 tests), the full Hermes `scripts/check` passed (12 checks), and the post-final-edit Ruff/health checks passed.
- This implementation covers Codex app-server turns only. Cross-provider aggregation, a user-facing read interface, budgets, retention/alerts, active-profile installation, and production identity verification remain open.

**Rationale:** This provides verified project-attributed usage measurement without moving token telemetry into Curator or Host Steward, while preserving explicit open gates for the broader plan.

**Impact:** Local, content-free Codex token totals can now support future Hermes Core project budgets without exposing counts to Curator handlers.

<!-- curatormd:record_id=f124ed1321eff5ad79ca795f1384f132;content_sha256=f124ed1321eff5ad79ca795f1384f13299bdb2d12a78cb811f0ae1bbaa3eea6d -->

## 2026-10-20 — 2026-10-20 Hermes Core project usage read interface

**Decision:** - 2026-10-20: Added an opt-in Hermes Core `project-usage` plugin on the existing Hermes fork. It pins reads to one project ID in the current profile, opens the local Codex usage ledger read-only, reports provider/model token aggregates, distinguishes unknown measurements from zero, and omits goal/session/event identifiers. Missing ledger/schema is reported unavailable without creating storage. Focused plugin, lifecycle-hook, and app-server integration tests passed (46 total); the Hermes plugin validator passed; full `scripts/check` passed (12 checks), and both worktrees passed `git diff --check`. These are local source and test results only; the plugin is not enabled or verified in a real project profile, other providers remain unmeasured, and usage budgets/retention/alerts remain open.

**Rationale:** The Curator V2 plan assigns provider/model token accounting to Hermes Core local project usage, separate from Curator persistence and Host Steward.

**Impact:** Records a verified Hermes Core fork implementation and leaves the real-profile enablement gate open.

<!-- curatormd:record_id=9c919b62faf0313b87522d4737f6ee47;content_sha256=9c919b62faf0313b87522d4737f6ee4783826041077bb48b03dd1b6ff0de949c -->

## 2026-10-20 — 2026-10-20 Hermes usage ledger reopen and replay regression

**Decision:** - 2026-10-20: Added a Hermes gateway regression that closes and reopens the profile-local Codex outbox, verifies provider/model usage totals survived, replays the same turn-end event, and confirms counts did not increase. The combined project-usage plugin and gateway-hook test run passed 12 tests; Hermes Ruff/health checks passed with zero blocking/advisory findings. This is local SQLite/unit evidence only; cross-process delivery, end-to-end Curator integration, production restart, locking, and load remain open.

**Rationale:** Usage totals are useful only if the local ledger recovers across a runtime restart without double-counting replayed lifecycle events.

**Impact:** Adds verified local persistence and duplicate-delivery evidence while keeping end-to-end recovery gates open.

<!-- curatormd:record_id=86c6aeb815b57988b4f0a88b9f7ce682;content_sha256=86c6aeb815b57988b4f0a88b9f7ce6820ca72197a4d16e44774d22c1cdd880b8 -->

## 2026-10-20 — 2026-10-20 Hermes profile outbox startup replay

**Decision:** - 2026-10-20: Hermes Core durable hook delivery now drains after both `gateway:startup` and profile-scoped `agent:start`. A registry restart regression leaves ordered events pending in the first registry, reopens the registry, then proves `agent:start` drains them in source order and acknowledges them. The grouped hook/multiplex-scope suite passed 14 tests; Ruff/health checks passed. This is local code/test evidence only; a real gateway restart and deployed-profile delivery remain open.

**Rationale:** The gateway process startup event is emitted in the launch profile; profile-local durable outboxes also need a retry point when a routed profile begins a turn.

**Impact:** Closes a profile-level retry timing gap in source while preserving live deployment and identity gates.

<!-- curatormd:record_id=08e738325e4ba93c6a33680d098b054d;content_sha256=08e738325e4ba93c6a33680d098b054d477d103ad36d4f27bdcc241e7cb6d855 -->

## 2026-10-20 — 2026-10-20 project health evaluation refactor

**Decision:** - 2026-10-20: Refactored `AuthenticatedCuratorAPI._collect_project_health_snapshot` into separate local queue/staging and required dependency-probe evaluators. Existing fail-closed behavior is preserved: pending local work degrades health, missing/stale/malformed probes stay unknown, and only complete fresh positive observations are healthy. All 30 API tests and four MCP server tests passed; strict Pyright reports 0 diagnostics, repository errors-only Pylint passes, and `git diff --check` is clean. Targeted full Pylint no longer reports complexity findings on the snapshot aggregator. The full configured Pylint run still reports structural/interface/duplicate-code findings and broad-catch warnings elsewhere; repository-wide cleanup remains open.

**Rationale:** The full Pylint inventory identified the project-health aggregator as a high-complexity function; health correctness is a direct release requirement.

**Impact:** Reduces complexity in the API gate that prevents false-green health while preserving the existing local and host-probe decisions.

<!-- curatormd:record_id=5408851774628ed71d877bc195dfaff6;content_sha256=5408851774628ed71d877bc195dfaff69af70fbc87debe9eb84c8bb3f31400c1 -->

## 2026-10-20 — Event dispatch phase decomposition

**Decision:** - 2026-10-20: Decomposed `CuratorService.process_event` into explicit inbox claim, evidence preparation, transactional dispatch, source-fact attribution, and retryable-failure phases. The full 301-test suite passed; strict Pyright reports 0 diagnostics, repository errors-only Pylint passes, and `git diff --check` is clean. Focused full Pylint no longer reports dispatcher complexity/size findings; repository-wide warning-level cleanup remains open.

**Rationale:** The event lifecycle dispatcher was a high-complexity path combining idempotency claims, evidence I/O, writes, provenance, and retry receipts.

**Impact:** Makes event transaction and retry phases explicit while preserving the existing regression-tested event contract; no deployed behavior is claimed.

<!-- curatormd:record_id=68059bf239cfc3ce6717c839803fb8d1;content_sha256=68059bf239cfc3ce6717c839803fb8d153b5921f611dd649e03b40dac3845d19 -->

## 2026-10-20 — Truthful goal bullet projection decomposition

**Decision:** - 2026-10-20: Split the goal bullet projection into criterion, fact, lifecycle status, pending-review, purge, and capacity-gate helpers. Added coverage proving the user-facing bullets expose SDE/purge pagination continuations and fact-capacity open gates. All 301 unit tests passed; strict Pyright, repository errors-only Pylint, and `git diff --check` pass. Full warning-level Pylint cleanup remains open.

**Rationale:** The compact goal projection is the user-facing truth surface; pending reviews, purge work, and capacity gates must remain visible and maintainable.

**Impact:** Preserves the distinction between recorded facts, verified facts, claims, and open work while making pagination and capacity state explicit.

<!-- curatormd:record_id=283e93ba60ceae74f5363b62d49fd7e5;content_sha256=283e93ba60ceae74f5363b62d49fd7e5615a4f7caef1e2890da9d25f5ca96d82 -->

## 2026-10-20 — Hermes Core Host Steward cleanup verification

**Decision:** - 2026-10-20: In the Hermes Core fork worktree, corrected Host Steward ownership descriptions and expanded disposable-directory regressions for post-approval symlink substitution, unhealthy services, absent service verification, and sanitized partial-cleanup receipts. All 14 focused Host Steward tests pass; `python scripts/check` passes all 12 checks with zero blocking/advisory findings. Curator's Host Steward gate is now recorded as in progress, not complete. No real host cleanup, authenticated approver identity, live install, or deployment recovery was verified.

**Rationale:** Host Steward belongs to Hermes Core; Curator should track the boundary and verified integration state without claiming ownership or production readiness.

**Impact:** Keeps approval, deletion, verification, and receipt evidence scoped to Hermes while documenting the remaining identity and deployment gates.

<!-- curatormd:record_id=e093d6cbd70f96248373253347b6e9b3;content_sha256=e093d6cbd70f96248373253347b6e9b3496472263e0ea1153f132918f6fc04a2 -->

## 2026-10-20 — Hermes Host Steward interrupted-cleanup reconciliation

**Decision:** 2026-10-20: On the existing eagles-edu/hermes-agent fork branch codex/curator-v2-hermes-integration-upstream, added explicit Host Steward receipt reconciliation for cleanup left running after operator-confirmed process stop. A regression simulates interruption after deletion: the original receipt remains durable, is transitioned to interrupted_requires_review with fresh inventory/service verification instructions, and cleanup is not retried. All 15 focused Host Steward tests pass; Hermes python scripts/check passes all 12 checks with zero blocking/advisory findings. This is local test evidence only. Cross-process supervision, authenticated approver identity, measured host owner attribution, live installation, and deployment recovery remain open; no push, installation, or real-host cleanup was performed.

**Rationale:** Record verified Hermes Core recovery behavior in Curator's progress history without moving Host Steward ownership into Curator.

**Impact:** Documents a fail-closed recovery path and keeps deployment and identity gates visible.

<!-- curatormd:record_id=14daa3c188dd7c10020ee09954e2b422;content_sha256=14daa3c188dd7c10020ee09954e2b42259b4ae8396653bc36e9b47743bda3dbf -->

## 2026-10-20 — Curator V2 immediate purge acceptance coverage

**Decision:** 2026-10-20: Expanded the local MCP SDE lifecycle acceptance test to inventory a held and an unheld transient artifact. After canonical Markdown persistence, the unheld artifact is removed in the same operation while the held artifact remains pending; a unique transient-content canary is absent from canonical Markdown. The focused test and full 301-test Curator suite pass. Strict Pyright reports zero errors; repository errors-only Pylint, Bandit, and git diff --check complete successfully. This is local test evidence, not a live consumer or production scheduler result.

**Rationale:** Verify the normal immediate-cleanup path alongside the retained-hold path without weakening the canonical-write-before-purge gate.

**Impact:** Makes the lifecycle test prove immediate purge of eligible artifacts, preservation of approved holds, and non-persistence of transient contents.

<!-- curatormd:record_id=d18d2d2ee21d2e4c8d72683f991ad963;content_sha256=d18d2d2ee21d2e4c8d72683f991ad963dc6f432cd898c05be4628e34306252c5 -->

## 2026-10-20 — Component-specific failure and recovery paths

**Decision:** 2026-10-20: Added a component recovery map for Hermes Core delivery, the Curator SQLite backend, repository plugins, and Hermes Core Host Steward. It links each local recovery procedure and keeps production recovery, identity, retention, and deployment authority open. Curator strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and git diff --check pass.

**Rationale:** The V2 plan requires independent failure and recovery paths for each owner boundary; repository guidance must not imply production authority or recovery evidence.

**Impact:** Makes the local recovery boundaries reviewable while preserving owner-specific production gates.

<!-- curatormd:record_id=6f93bc18cf9affa3e92667f6e7db422a;content_sha256=6f93bc18cf9affa3e92667f6e7db422aa6c0198a2847a284fe6843cb6609fb46 -->

## 2026-10-20 — Curator V2 boundary clarity and access CLI lint cleanup

- Decision: Clarified that Curator V2 is a standalone rewrite; `*-v1` names
  version 1 of V2-owned interfaces, while any V1 cutover remains an independent
  owner-operated gate. Renamed recovery and consumer-operation document titles
  to identify them as Curator V2 guidance.
- Changed: Centralized the attended access CLI operation map and confirmation
  caller construction; documented its single-method authorization protocol.
- Verified: The access CLI test module passes 2 tests, its focused Pylint score
  is 10.00/10, and strict Pyright reports 0 diagnostics.
- Open: Repository-wide Pylint exits 28 at 9.77/10 with non-blocking findings;
  deployment, identity, retention, and live-runtime gates are unchanged.

## 2026-10-20 — Reusable producer/backend contract assertions

- Intent: Add a bounded, importable contract check that consumer plugin suites
  can run against the Curator V2 backend.
- Changed: Added `curatormd_v2.testing.assert_goal_started_event_contract`, a
  consumer usage guide, and a reference-plugin regression. The assertion
  covers event JSON round-trip, exact-retry receipt stability, persisted goal
  fields and project scope, received-byte accounting, and zero retained event
  payload bytes.
- Verified: The focused regression and all 302 Curator tests pass; strict
  Pyright, errors-only Pylint, Bandit, locked dependency audit, and
  `git diff --check` pass. `uv build --wheel` includes `testing.py` in the
  backend wheel.
- Open: The shared assertion has not yet run in a consumer plugin suite; real
  producer routing, Hermes delivery, deployment, trusted identity, and
  retention policy remain unverified.

## 2026-10-20 — Producer contract helper warning cleanup

- Changed: Replaced the helper's long boolean comparison with explicit tuples
  of persisted and producer-supplied goal fields.
- Verified: The focused regression and full 302-test suite pass; strict
  Pyright and focused Pylint pass. Full warning-level Pylint rates the
  repository at 9.78/10 and exits 28 with the remaining non-blocking inventory.
- Open: Repository-wide structural, duplicate-code, and design findings remain
  unresolved.

## 2026-10-20 — Hermes Host Steward growth attribution estimate

- Intent: Make filesystem growth outside configured Host Steward targets
  visible as unknown instead of leaving it implicit.
- Changed: In the Hermes Core Host Steward plugin, compare root filesystem
  used-byte growth with allocated-byte growth in unchanged, complete configured
  target scans; group measured growth by configured owner and expose the
  remainder as an unattributed estimate. Baseline and partial coverage are
  explicit. Updated the Hermes plugin guide and this plan's ownership gate.
- Verified: All 18 focused Host Steward tests pass with disposable directories;
  Hermes `scripts/check` passes all 12 checks with no blocking/advisory
  findings. No real host inventory or cleanup was performed.
- Open: This estimates only configured target contribution. Attribution of
  unconfigured paths, service growth, authenticated owner identity, and live
  deployment remain open.

## 2026-10-20 — Backup destination race recovery coverage

- Changed: Added a failure-injection test for a backup destination created
  after initial validation but before atomic installation.
- Verified: The competing destination remains byte-for-byte intact and the
  temporary verified snapshot is removed. The focused test and full 303-test
  Curator suite pass; strict Pyright, errors-only Pylint, Bandit, locked
  dependency audit, and `git diff --check` pass. Local migrations are covered
  through schema version 16, including injected rollback for legacy purge-error
  redaction.
- Open: Production backup/restore drills, deployment migration rollback, and
  system-of-record recovery policy remain open.

## 2026-10-20 — Host Steward overlapping-target attribution guard

- Changed: Added a regression for nested configured inventory targets. Because
  their scans overlap, Host Steward marks coverage partial, suppresses owner
  attribution, and reports the filesystem delta as unattributed.
- Verified: All 19 focused Host Steward tests pass with disposable paths;
  Hermes `scripts/check` passes all 12 checks with no blocking/advisory
  findings. No live inventory or cleanup was performed.
- Open: Configured-scope deltas remain estimates; unconfigured-path and service
  growth attribution and live deployment are still unverified.

## 2026-10-20 — Shared temporary consumer test layout

- Changed: Extracted repeated temporary consumer-repository directory creation
  into `tests/project_fixtures.py` and reused it across six test modules.
- Verified: The affected modules pass 96 tests and the full suite passes 303;
  strict Pyright, errors-only Pylint, and `git diff --check` pass. Repository-
  wide duplicate-code findings decreased from 35 to 24; full warning-level
  Pylint decreased from 288 to 279 messages and remains 9.78/10 (exit 28).
- Open: Repository-wide interface, complexity, and duplicate-code findings
  remain unresolved.

## 2026-10-20 — Shared deterministic test adapters

- Changed: Reused the same test-only `TestVerifier` and
  `TestReviewAuthorizer` from `tests/purge_fixtures.py` in lifecycle and
  Markdown tests where the authorization and evidence behavior matches.
- Verified: The focused lifecycle, Markdown, and purge suites pass 79 tests;
  the full suite passes 303. Strict Pyright, errors-only Pylint, and
  `git diff --check` pass. Full warning-level Pylint fell from 279 to 276
  messages and from 24 to 22 duplicate-code findings; it remains 9.78/10
  (exit 28).
- Open: Remaining repository-wide interface, complexity, and duplicate-code
  diagnostics require further refactoring.

## 2026-10-20 — Hermes event mapper decomposition

- Intent: Make the Hermes lifecycle translation boundary easier to inspect
  while preserving its bounded, non-verifying event contract.
- Changed: Split supported event selection, bound context validation, lifecycle
  fact classification, and stable event/fact ID derivation into private
  helpers. The public translator and serialized facts retain the same shape.
- Verified: All 6 direct Hermes event tests and the full 303-test Curator suite
  pass. Strict Pyright, errors-only Pylint, Bandit, locked dependency audit,
  and `git diff --check` pass. Full warning-level Pylint decreased from 276 to
  274 findings and reports 9.79/10 (exit 28).
- Open: Repository-wide warning-level Pylint cleanup, authenticated Hermes
  identity, live gateway delivery, and deployment remain unverified.

## 2026-10-20 — Goal retirement transaction decomposition

- Intent: Clarify the validation stages in goal cancellation and supersession
  without weakening their atomic lifecycle rules.
- Changed: Extracted immutable request checks, same-project active replacement
  and ancestry validation, and unresolved child/dependency guards into named
  store helpers. `retire_goal` still runs relational checks, fact append, and
  state update in one transaction with the original check ordering.
- Verified: The focused lifecycle and event suites pass 76 tests; the full
  303-test suite passes. Strict Pyright, errors-only Pylint, Bandit, locked
  dependency audit, and `git diff --check` pass. Full warning-level Pylint fell
  from 274 to 272 findings and remains 9.79/10 (exit 28).
- Open: Repository-wide structural findings and all external identity,
  retention-policy, and deployment gates remain open.

## 2026-10-20 — Sensitive event persistence boundary coverage

- Intent: Strengthen local evidence that a credential-like event rejected
  before ingestion does not reach persistent V2 project state.
- Changed: Extended the API regression to scan the live SQLite database, WAL,
  SHM, configured canonical Markdown target, and SQLite backup for the injected
  canary, in addition to checking receipt/goal absence and project metrics.
- Verified: The focused API suite passes 30 tests and the full Curator suite
  passes 303. Strict Pyright, errors-only Pylint, Bandit, locked dependency
  audit, and `git diff --check` pass.
- Open: This proves one rejected-event path only. Retry/quarantine payloads,
  full logging and trace flows, other artifact classes, and deployment-level
  privacy review remain open.

## 2026-10-20 — Hermes outbox process-crash recovery

- Intent: Verify that the Hermes Core profile-local lifecycle outbox recovers
  its committed event and acknowledgment state after real process exits.
- Changed: Added a subprocess regression that terminates workers abruptly
  after enqueue, retry, and acknowledgment commits, then reopens the same
  profile outbox from fresh processes and checks exact replay/idempotency.
- Verified: The new subprocess test and the 8-test gateway hook suite pass via
  Hermes `scripts/run_tests.sh`. Hermes `scripts/check` passes all 12 checks
  with zero blocking or advisory findings.
- Open: This is local SQLite/outbox evidence, not running gateway supervision,
  cross-process Curator MCP delivery, authenticated identity, or deployment.

## 2026-10-20 — Hermes adapter to Curator stdio process

- Intent: Verify the Curator-side Hermes adapter and durable event receiver
  across the actual MCP stdio process boundary.
- Changed: Added an acceptance test that creates a synthetic Hermes-format
  envelope, binds its test profile/session to an active goal, sends it through
  the repository-configured hook adapter into a separate Curator MCP process,
  repeats the event, then reopens the child's SQLite database.
- Verified: The adapter suite passes 3 tests and the full Curator suite passes
  304. Strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and
  `git diff --check` pass. The child database contains the durable receipt and
  exactly one Hermes turn fact after duplicate delivery.
- Open: This does not launch Hermes or its durable outbox; profile metadata is
  synthetic. Live gateway dispatch, authenticated identity, and deployment
  remain open.

## 2026-10-20 — Hermes public hook MCP context for Curator lifecycle delivery

**Decision:** - Intent: Route the Curator V2 Hermes adapter through a supported Hermes gateway hook API.
- Changed: Added a public profile-scoped hook `ctx.call_mcp` capability with per-hook default-deny allowlists, bounded session context, and delegation to Hermes' existing managed MCP handler; extended PluginContext.call_mcp additively. The Curator adapter now requires the injected public capability and retains an asynchronous test seam only for in-memory fixtures.
- Verified: Hermes focused hook/MCP/trust tests passed (52), Ruff and `scripts/check` (12 checks) passed. Curator's full suite passed (304), the Hermes adapter suite passed (3), Pyright reported 0 diagnostics, and errors-only Pylint, Bandit, and both `git diff --check` checks passed. The adapter acceptance test uses the public call shape across a separate Curator stdio MCP process and verifies duplicate delivery leaves one durable fact and receipt.
- Open: Profile identity in tests is synthetic. Authenticated Hermes identity, real gateway/outbox delivery, deployment, and production permission binding remain open.

**Rationale:** The existing Curator adapter imported a private Hermes handler. Hermes gateway hooks do not receive PluginContext, so the integration needs an explicit public per-hook capability.

**Impact:** Improves adapter compatibility with Hermes' documented gateway hook surface while retaining default-deny MCP grants and host-derived profile metadata.

<!-- curatormd:record_id=06ed8fb52610c2f5925d5a62e1bda8f2;content_sha256=06ed8fb52610c2f5925d5a62e1bda8f2df60191fd5eef3a17dfeef3f82038e99 -->

## 2026-10-20 — Hermes hook context preserves host-derived profile metadata

**Decision:** - Changed: Added a Hermes trust-gate regression that invokes the gateway hook's public `HookContext.call_mcp` through the managed MCP handler.
- Verified: The MCP request contains only the tool event arguments plus Hermes-derived profile ID, supplied host session ID, and literal durable-event marker in request metadata; the focused trust-gate suite passes 24 tests.
- Open: The test uses a synthetic profile and fake MCP transport. Authenticated identity and live profile/gateway delivery remain unverified.

**Rationale:** The context capability and the trust gate had previously been tested separately; an integrated regression now verifies their joined request behavior.

**Impact:** Proves the public gateway hook call path carries the exact trusted metadata required by the Curator adapter without exposing profile selection to hook arguments.

<!-- curatormd:record_id=6609f68cdea50bce026284db5b88ba77;content_sha256=6609f68cdea50bce026284db5b88ba77ecc8a8a3e7af94d56fb723761d21d741 -->

## 2026-10-20 — Keep Curator lifecycle MCP context on the gateway hook API

**Decision:** - Changed: Removed the optional PluginContext.call_mcp extension after Hermes `scripts/check` correctly rejected growth in an already-over-target facade; the method is back at its prior behavior and baseline length. The supported Curator integration uses the profile gateway hook's public `HookContext.call_mcp` with its per-hook default-deny allowlist.
- Verified: Hermes `scripts/check` passes all 12 checks after the removal. The final grouped gateway hook, plugin MCP, and MCP trust suites pass 46 tests; Ruff and `git diff --check` pass.
- Open: Profile identity remains synthetic in tests; authenticated identity, live gateway delivery, and deployment remain unverified.

**Rationale:** The first implementation pass extended PluginContext.call_mcp, but Hermes' actual durable lifecycle transport uses profile gateway hooks. The hook-specific public context is the required API.

**Impact:** Keeps the integration's final ownership and API boundary accurate while preserving Hermes Core's file-size health constraint.

<!-- curatormd:record_id=f296f36d3531cec1ce1b13fc49866365;content_sha256=f296f36d3531cec1ce1b13fc49866365a221c8fa550ddc72b754527a15024718 -->

## 2026-10-20 — Prove local health degrades for pending review and held purge work

**Decision:** - Changed: Extended API health coverage for an outstanding SDE review and a held artifact with a pending purge receipt and artifact.
- Verified: Both cases return `degraded` with all dependency probes healthy and expose the exact review/purge/staging gate codes. The focused API suite passes 31 tests; the full Curator suite passes 305; Pyright reports 0 diagnostics; errors-only Pylint and Bandit pass.
- Open: Production scheduler health, alert delivery, and production storage-adapter failure accounting remain unverified.

**Rationale:** The health plan item already had local aggregate counts, but lacked direct regressions for pending review and pending held-purge states under otherwise healthy dependency probes.

**Impact:** Strengthens evidence that local operational health cannot report green while required reviewer or purge work remains.

<!-- curatormd:record_id=ee92b8c406aa726f1014af8a245454af;content_sha256=ee92b8c406aa726f1014af8a245454afd42768a47cfeb96cf6768ed5bc3b3512 -->

## 2026-10-20 — V2 event input exceptions no longer retain raw source

**Decision:** Curator V2 event JSON decoding and API UTF-8 validation now raise sanitized errors without retaining request text through exception cause/context; duplicate JSON keys produce a generic error without echoing the key. Regression checks cover the event decoder and API boundary. Focused tests passed (69), the full suite passed (308), and strict Pyright, errors-only Pylint, Bandit, and git diff --check passed. Broader privacy review across archives, logs, traces, backups, and upstream data flow remains open.

**Rationale:** JSONDecodeError and UnicodeEncodeError retain the full input in exception fields, while duplicate-key error text previously echoed caller-controlled field names.

**Impact:** Closes a bounded raw-source retention path in V2 event-input exceptions while keeping the broader privacy checklist open.

<!-- curatormd:record_id=53aa3d19c379dbb8a6c2d37c7e0f077c;content_sha256=53aa3d19c379dbb8a6c2d37c7e0f077c986fa5affc70430aa973516ebfb71730 -->

## 2026-10-20 — Sanitize config and checklist decoder failures

**Decision:** Curator V2 configuration and checklist parsing now raise generic errors without retaining raw TOML or checklist bytes through chained decoder exceptions. Regression tests cover malformed TOML and invalid UTF-8 checklist content, including empty exception cause/context. Focused event/API/config tests pass (104), full suite passes (310), and Pyright, errors-only Pylint, Bandit, and git diff --check pass. Broader logging, archive, backup, trace, and upstream privacy review remains open.

**Rationale:** TOMLDecodeError and UnicodeDecodeError can retain source text or bytes in exception fields, so wrapping them with explicit causes keeps raw material reachable.

**Impact:** Closes two additional local raw-source retention paths while preserving the broader privacy gate.

<!-- curatormd:record_id=0bca07a5da2111aa4c6c57d63ee83b25;content_sha256=0bca07a5da2111aa4c6c57d63ee83b2596db2d118038e7dd008cc427591dd5af -->

## 2026-10-20 — Sanitize archived fact decoder exceptions

**Decision:** Curator V2 fact archive retrieval now converts decompression, JSON parsing, and record-domain validation failures into generic integrity errors without retaining raw archive input through exception causes or context. Regressions cover malformed JSON and an invalid archive enum value. Focused archive tests pass (9), the full suite passes (312), and Pyright, errors-only Pylint, Bandit, and git diff --check pass. Broader archive, backup, logging, trace, and upstream privacy review remains open.

**Rationale:** JSONDecodeError and enum ValueError instances may retain attacker-controlled archive bytes or field values when chained.

**Impact:** Closes selected source-retention paths during V2 archive retrieval without claiming complete archive privacy coverage.

<!-- curatormd:record_id=50a8e5f1dbf76315a1612b2c90cdfce7;content_sha256=50a8e5f1dbf76315a1612b2c90cdfce78469d8671d6076c10c6042a496aa74c2 -->

## 2026-10-20 — Sanitize V2 validation and canonical decode exceptions

**Decision:** Curator V2 event/domain enum and timestamp validation, model timestamps, maintenance batch-limit parsing, and canonical Markdown UTF-8 decoding now return fixed errors without retaining source-bearing parser exceptions. Regression coverage checks event timestamps/types, evidence timestamps, invalid goal status, CLI limits, and malformed canonical Markdown. Focused suites pass (114), the full suite passes (317), and strict Pyright, errors-only Pylint, Bandit, and git diff --check pass. Broader logging, tracing, upstream, and remaining exception-boundary review stays open.

**Rationale:** Built-in enum, ISO timestamp, integer, and UTF-8 decoding errors may keep rejected values or complete source bytes reachable through chained exceptions.

**Impact:** Closes selected source-retention paths across V2 input validation and Markdown parsing while preserving the overall privacy gate.

<!-- curatormd:record_id=25ad9d00689d1d752aab4f62d1c669d9;content_sha256=25ad9d00689d1d752aab4f62d1c669d9db055f0e083930a0220b3048fef2fee1 -->

## 2026-10-20 — Verify Hermes events cannot cross project boundaries

**Decision:** Curator V2's separate-process Hermes adapter acceptance test now places a goal in a second project in the shared SQLite backend, routes an outbox-shaped event for that foreign goal through the project-A MCP process, verifies the adapter does not acknowledge it, and confirms the foreign project's facts remain unchanged. Focused Hermes adapter tests pass (3), the full Curator suite passes (317), and Pyright, errors-only Pylint, Bandit, and git diff --check pass. The test uses synthetic profile identity and a stdio harness; authenticated identity, live profile wiring, and deployed behavior remain open.

**Rationale:** Unit adapter filtering alone did not prove a foreign project goal remains untouched by the project-bound MCP process.

**Impact:** Adds local cross-project isolation evidence for the Hermes-to-Curator process boundary without closing identity or runtime gates.

<!-- curatormd:record_id=fd3f405e4a55bbc1d35500955ebe3e1e;content_sha256=fd3f405e4a55bbc1d35500955ebe3e1e05942063074adfe451e2a9bfd23499f8 -->

## 2026-10-20 — Sanitize API error and configured path validation

**Decision:** Curator V2 API error envelopes now reject unsupported code/schema values with fixed errors, and config path-resolution failures no longer echo the configured path or retain OS error context. Focused errors/config tests pass (40), the full suite passes (319), and strict Pyright, errors-only Pylint, Bandit, and git diff --check pass. Persistence status remains degraded with zero pending reviews and cues. Broader privacy review remains open.

**Rationale:** Enum conversion errors can retain invalid API code values, and filesystem resolution errors carry paths supplied by repository config.

**Impact:** Closes two local untrusted-value disclosure paths while preserving the broader privacy gate.

<!-- curatormd:record_id=2d31062e5f5d91d2bf3e91b2951a0a5a;content_sha256=2d31062e5f5d91d2bf3e91b2951a0a5a57686ac034e5f2ac716bd1be4e52998f -->

## 2026-10-20 — Verify Host Steward stays owned by Hermes Core

**Decision:** Curator's real stdio MCP tool catalog now explicitly excludes Host Steward inventory/proposal/cleanup/receipt/reconciliation tools. Hermes Core Host Steward tests pass (19), including named project profile tool isolation, and Hermes scripts/check passes all 12 checks. Curator's full suite passes 319; strict Pyright, errors-only Pylint, Bandit, locked audit, and git diff --check pass. This verifies local code ownership only; live root-account installation and runtime isolation remain open.

**Rationale:** The V2 plan requires Host Steward to remain in Hermes Core's root account and forbids Curator from owning or executing host cleanup.

**Impact:** Closes the local source/tool ownership boundary between CuratorMD and Hermes Core Host Steward while preserving deployment gates.

<!-- curatormd:record_id=da4048c03294b31696678a458ff85ab7;content_sha256=da4048c03294b31696678a458ff85ab779707e076ec3c2d1263561875ded91e9 -->

## 2026-10-20 — Reduce repository-wide Pylint style findings

**Decision:** The current full Pylint inventory initially reported 292 findings. Curator V2 source and test formatting cleanup removed the remaining long-line, local import-order, and missing helper documentation findings, reducing the inventory to 274. The remaining findings are primarily design/interface complexity and duplicate-code warnings. The 98 affected focused tests and full 319-test suite pass; strict Pyright, errors-only Pylint, and git diff --check pass. Full warning-level cleanup remains open.

**Rationale:** The current plan requires repository-wide Pylint cleanup, and the last recorded inventory predated recent source/test changes.

**Impact:** Reduces warning-level Pylint findings without weakening the blocking errors-only CI gate; structural cleanup remains open.

<!-- curatormd:record_id=88cbf09e2592c880a49d9a123dba2172;content_sha256=88cbf09e2592c880a49d9a123dba2172567d36e0b87ddc3c8d98530bdfc9ba15 -->

## 2026-10-20 — Verify canonical persistence precedes unheld artifact purge

**Decision:** - The MCP SDE lifecycle acceptance test stages a held artifact and an unheld transient-content canary; it verifies canonical Markdown persistence before immediate purge of the unheld file, while the held file remains pending and the canary is absent from canonical Markdown.
- Current Curator quality checks pass: Pyright reports 0 diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` exit successfully. Full warning-level Pylint cleanup and production purge scheduling remain open.

**Rationale:** The V2 purge contract requires canonical persistence before cleanup, distinct held-artifact behavior, and no raw transient content in canonical facts. The completed local quality checks establish the current static baseline without closing live-runtime or deployment gates.

**Impact:** Preserves a compact verification fact for purge ordering and current static quality state; production consumer and scheduler behavior remain unverified.

<!-- curatormd:record_id=193835595deff78817bc9c693448b0ca;content_sha256=193835595deff78817bc9c693448b0ca4c74295337f3801ecdd7008b0c0b5f53 -->

## 2026-10-20 — Scope Curator SQLite connections with the store context manager

**Decision:** - `CuratorStore` now supports `with` blocks and closes its SQLite connection on exit; project-access test setup uses `TestCase.enterContext` to own the store through teardown.
- `ProjectActivitySnapshot` keeps exact built-in boolean validation through the shared runtime type guard. The full suite passes 320 tests; Pyright, errors-only Pylint, targeted resource/type Pylint, Bandit, and locked dependency audit pass. Full warning-level Pylint reports 272 findings, down from 274.

**Rationale:** The store owns an open SQLite connection and tests had to manage cleanup manually. Context-manager support makes connection lifetime explicit; the shared exact-type guard retains runtime rejection of non-boolean values without relaxing validation.

**Impact:** Improves connection cleanup ergonomics and removes two non-blocking Pylint findings while keeping repository-wide design and complexity warnings open.

<!-- curatormd:record_id=6b8b955b60aa3f2d9c8b2e7fe26fd2e6;content_sha256=6b8b955b60aa3f2d9c8b2e7fe26fd2e656d40373aeecbe9897fde4aadc06f389 -->

## 2026-10-20 — Refactor the Hermes project-hook adapter

**Decision:** - Curator's Hermes hook adapter now separates bounded payload construction, public MCP invocation, and durable-receipt validation while preserving skip (`None`) and retry (`False`) behavior and retaining only allowlisted event context.
- The three focused adapter tests and full 320-test Curator suite pass; Pyright, errors-only Pylint, targeted adapter complexity checks, Bandit, and `git diff --check` pass. Full warning-level Pylint reports 270 findings, down from 272.
- This is local adapter/source evidence; Hermes runtime activation, authenticated profile identity, and live outbox-to-Curator delivery remain open.

**Rationale:** The single adapter handler had excess branches and early returns around an ownership-sensitive boundary. Extracted helpers make its field filtering, MCP envelope checks, and durable acknowledgment rule independently readable without changing the contract.

**Impact:** Reduces integration-adapter complexity while preserving project scoping and ack-after-durable-receipt behavior; it does not assert deployment or authenticated identity.

<!-- curatormd:record_id=cce502e2dda6684ff05bb99e367449d3;content_sha256=cce502e2dda6684ff05bb99e367449d3ece9b411bd930a138997658a527974cf -->

## 2026-10-20 — Exercise Hermes durable hook dispatch through managed MCP

**Decision:** - Added a Hermes gateway regression that binds a session and goal in the profile-local outbox, persists a bounded Codex event, dispatches it through a durable hook receiving public `ctx`, calls the allowlisted managed MCP handler with session/durable-event context, and acknowledges only a processed receipt.
- `scripts/run_tests.sh tests/gateway/test_hooks.py` passes all 12 tests; Hermes `scripts/check` passes 12 checks. The managed MCP handler factory is stubbed at its connection seam, so configured Curator stdio, authenticated identity, and live profile activation remain unverified.

**Rationale:** The existing Hermes tests covered durable outbox delivery and public managed-MCP capability in isolation. Combining those paths verifies the real gateway hook dispatcher passes its public context and only clears the durable event after an explicit successful receipt.

**Impact:** Strengthens locally verifiable Hermes Core integration without asserting an authenticated profile, configured Curator server process, or deployed runtime.

<!-- curatormd:record_id=ce012a58cd2a082a7df70cefdc49a6f6;content_sha256=ce012a58cd2a082a7df70cefdc49a6f60b54ec8048d74781e585ec43834c34ee -->

## 2026-10-20 — Verify reference producer artifact-class inventory

**Decision:** The reference producer regression stages raw-chat, cue, import, scratch, generated, and duplicate classes through atomic publication, then confirms a complete manifest preserves each path and the common digest for identical payloads. Focused plugin tests pass 37 and the full suite passes 321 on Python 3.12.3; strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and diff check pass. Full Pylint remains at 270 non-blocking findings. Real producer routing and out-of-root inventory remain open.

**Rationale:** The open staging-inventory plan item previously had six-class scanner coverage using manually created files, while the reference producer write API was tested for one class.

**Impact:** Connects every supported reference producer class to complete inventory evidence without asserting external producer routing, consumer installation, or production cleanup.

<!-- curatormd:record_id=91d7756c976595d46cabe2f889b60af7;content_sha256=91d7756c976595d46cabe2f889b60af73e8ed025959d5e64540e75e4bec1ae3a -->

## 2026-10-20 — Exercise Hermes managed MCP handler in durable hook test

**Decision:** - The Hermes gateway regression now runs the production `_make_tool_handler` and managed MCP dispatch against a fake connected session/background test loop, and verifies the processed receipt clears the persisted event while request metadata contains Hermes-derived profile/session plus the durable marker.
- `scripts/run_tests.sh tests/gateway/test_hooks.py` passes all 12 tests; `python3 scripts/check` passes 12 checks; Hermes and Curator `git diff --check` pass.
- This is local source/test evidence only. Configured Curator stdio launch, authenticated identity, profile authorization, live gateway delivery, and deployment remain open.

**Rationale:** The earlier regression stubbed the managed MCP handler factory. Exercising its production path strengthens the local Hermes integration evidence while keeping the fake transport boundary explicit.

**Impact:** Removes the handler-factory stub from the gateway regression without claiming configured stdio, authenticated identity, or runtime delivery.

<!-- curatormd:record_id=648df7b420e628f2f16cd4ef204e0db5;content_sha256=648df7b420e628f2f16cd4ef204e0db5d61474d1faca48bf1780ea5b52345e99 -->

## 2026-10-20 — Host Steward service-target growth metadata

**Decision:** - 2026-10-20: Hermes Core Host Steward inventory snapshots now retain configured service-unit bindings and report positive allocated-byte growth for stable, complete configured targets; a changed binding suppresses attribution. The README and V2 plan state that this is operator-supplied metadata association, not proof a service caused writes. `scripts/run_tests.sh tests/plugins/test_host_steward_plugin.py` passed 20 tests and `python3 scripts/check` passed 12 checks locally. Actual service-owned growth, unconfigured paths, authenticated identity, live installation/runtime, and deployment remain open.

**Rationale:** The Hermes Core Host Steward change associates positive growth from stable configured targets with operator-supplied systemd unit names. The V2 plan must preserve the distinction between metadata association and causal service ownership.

**Impact:** Records local verification without claiming causal service attribution or live installation.

<!-- curatormd:record_id=f949fbcf7f0055dc31a21a59aea3f1c7;content_sha256=f949fbcf7f0055dc31a21a59aea3f1c7a922b07eecccab6d9ea72f8ea31e9c8c -->

## 2026-10-20 — Prepare and verify Curator V2 alpha candidate

**Decision:** Curator V2 package metadata is now `0.1.0a1`. The wheel and source archive build; a clean Python 3.12.3 environment installs the wheel and passes the packaged MCP launcher acceptance test. The full Curator suite passes 321 tests; Pyright, errors-only Pylint, Bandit, locked dependency audit, lock validation, and `git diff --check` pass locally. GitHub Actions run 39389283097 passes on alpha commit `8733875`, including the Python 3.12/3.13/3.14 matrix, quality/security checks, and clean-wheel launcher acceptance.

**Rationale:** Establish an evidence-backed alpha package and local consumer-plugin baseline before the planned Vhost Manager integration test.

**Impact:** The alpha candidate is ready for a controlled consumer integration test. No package was published and no consumer, live Hermes profile, deployment, identity, retention, or capture gate was enabled; those remain open.

<!-- curatormd:record_id=daedad2856eac9ed665a022fe5e6e86a;content_sha256=daedad2856eac9ed665a022fe5e6e86a7f77e5210d9f90b7112e17f4eee1b34a -->

## 2026-10-20 — Install Curator V2 alpha in the Vhost Manager test profile

**Decision:** Installed the local `0.1.0a1` wheel in an isolated `renew-ssl-coding` Hermes profile environment. The Vhost Manager repository now has a repository-owned `.curatormd-v2.toml` with a unique V2 project ID, read scope limited to `vhost-manager/` and `docs/`, and separate V2 staging and Markdown persistence paths. The profile uses a separate test database, selects five read-only tools, omits `--allow-write`, and has only a durable read grant. Hermes `mcp test` connected to the packaged launcher; a stdio `goal_list` read with supplied matching profile/session metadata returned no goals.

**Rationale:** Verify the alpha package and local repository plugin against the intended first consumer without changing its application source or reusing V1 state.

**Impact:** Local consumer/profile integration is verified for startup and one authorized read. No Vhost Manager source, V1 persistence, or live gateway process was changed; metadata is supplied by the test client, so authenticated identity, live gateway activation, capture, and deployment-runtime gates remain open.

<!-- curatormd:record_id=9b0d6ed61a6743e5ce6b668aefd6c7ac;content_sha256=9b0d6ed61a6743e5ce6b668aefd6c7ac13942b0c03af71fccfd9074d7bfc72b8 -->

## 2026-10-20 — Verify V2 semantic event retries and Vhost Manager alpha consumer

**Decision:** Curator V2 now persists an occurrence-time-independent idempotency digest for bounded lifecycle events. Schema v17 backfills retained payloads; processed legacy receipts with discarded payloads keep raw-digest conflict behavior. Typed MCP tests prove exact retries remain idempotent and changed content conflicts. The full Curator suite passes 323 tests; Pyright, errors-only Pylint, Bandit, locked audit, lock validation, and `git diff --check` pass.

**Rationale:** The installed local tool factory regenerated `occurred_at` for each invocation, causing exact MCP retries to conflict after the event had been processed and its payload discarded. The semantic digest preserves idempotency without treating changed event content as a retry.

**Impact:** The rebuilt alpha wheel is installed in the isolated Vhost Manager profile environment. Hermes `mcp test` connects and the configured V2 read succeeds. A separate V2-only lifecycle database retains 2 goals and 5 processed event receipts after fresh stdio processes; exact goal/fact retries pass and changed payload is rejected. V2 `project_health` remains `unknown` because router, purge scheduler, host identity, human review, and producer inventory are unobserved. The normal profile database remains read-only with zero events/goals. Authenticated identity, live profile gateway delivery, capture, and deployed Vhost Manager runtime remain open; no V1 persistence or consumer application source was changed.

<!-- curatormd:record_id=4ac1331d2e44a37a1e2ce157f3397212;content_sha256=4ac1331d2e44a37a1e2ce157f339721298ef494ebc6ef30dbb2593c754dac5fb -->

## 2026-10-20 — Pass hosted CI for Curator V2 alpha retry fix

**Decision:** GitHub Actions run `39392148597` passes on Curator V2 source commit `3ce95b9`: Python 3.12/3.13/3.14 suite, blocking type/lint/security/audit checks, and clean-wheel installed consumer-launcher acceptance.

**Rationale:** Hosted matrix evidence confirms the v17 event-retry change and packaged launcher beyond the local Python 3.12 run.

**Impact:** The alpha retry fix is pushed and hosted CI is green. Authentication, policy, live profile delivery, and deployment gates remain open.

<!-- curatormd:record_id=fd38bbb94da6e500ccee6a1385f86c79;content_sha256=fd38bbb94da6e500ccee6a1385f86c79bed798dbaa88a70d9694c8bfe5da51f4 -->

## 2026-10-20 — Verify Vhost Manager open-status workflow and conservative v16 replay migration

**Decision:** The installed Curator V2 alpha launcher, using the actual Vhost Manager repository config and an isolated V2 smoke database, processed a goal and fact, accepted their retries across fresh MCP subprocesses, and rejected changed content for the same event ID. A completion request without criterion evidence kept the goal and criterion open; `goal_report` exposed the open TODO. The reopened database reports 2 goals and 6 processed event receipts; project health remains unknown for five unobserved dependencies. A new migration regression proves processed v16 receipts with discarded payloads keep strict raw-digest conflict behavior. The full Curator suite passes 324 tests; Pyright, errors-only Pylint, Bandit, locked audit, lock check, and diff check pass.

**Rationale:** The alpha consumer smoke needed evidence of truthful status output after persistent request, change, and incomplete finish events. The migration fallback must not infer semantic identity after raw event content has been discarded.

**Impact:** This verifies an installed package workflow against the real consumer config in a separate test database. Hermes metadata is synthetic, writes use explicit test-only access, and no Vhost Manager application source changed. The real producer workflow, authenticated identity, live profile delivery, retention policy, and deployed runtime remain open. Hosted CI for the new migration regression is pending.

<!-- curatormd:record_id=a1d735d3c7fd21051deb3c1cfb45f3ce;content_sha256=a1d735d3c7fd21051deb3c1cfb45f3cee5ba6fe473a47bf2c1003d7b6c40fafd -->

## 2026-10-20 — Pass hosted verification for Vhost lifecycle and v16 retry migration

**Decision:** GitHub Actions run `39392957765` passed on Curator V2 commit `0e98bf0`, including the Python 3.12/3.13/3.14 suite, blocking type/lint/security/audit jobs, and clean-wheel consumer launcher acceptance.

**Rationale:** The hosted run covers the conservative processed-v16-receipt regression and the updated alpha release evidence after the local 324-test verification.

**Impact:** The latest Curator V2 migration test commit is pushed and hosted checks pass. Vhost Manager application integration, authenticated identity, live profile delivery, retention policy, and deployment gates remain open.

<!-- curatormd:record_id=270c81348deb1e2f8cca5b6075876c2e;content_sha256=270c81348deb1e2f8cca5b6075876c2efc761a325c1b36b61d85893b5b81b751 -->

## 2026-10-20 — Rebuild and recheck the Vhost Manager V2 alpha binding

**Decision:** Rebuilt the `0.1.0a1` wheel from the current Curator V2 checkout and reinstalled it into the isolated `renew-ssl-coding` profile environment. Hermes MCP connection passed and discovered 45 tools. A fresh stdio `goal_list` call using the Vhost Manager repository config and the profile's matching test metadata returned an empty list from the isolated V2 database. The profile continues to expose only five read-only tools. Hosted Curator CI run `39393130048` completed successfully after the prior source-code run.

**Rationale:** Reconfirm that the local consumer binding is using the current alpha package before the planned Vhost Manager integration test.

**Impact:** Local package startup, tool discovery, and project-bound read are verified. The actual Vhost Manager application producer, authenticated Hermes identity, live gateway delivery, write-granted pilot, and deployed runtime remain open. The Vhost Manager app worktree was not changed, and no GPTMD or V1 repository/runtime was modified.

<!-- curatormd:record_id=35fc8182174e439210248c663e354021;content_sha256=35fc8182174e439210248c663e354021e8f1d6c7d4e08a1c122c09bb21faf7a1 -->

## 2026-10-20 — Keep Hermes durable outbox pending until Curator receipt is terminal

**Decision:** In Hermes Core's managed-MCP Codex lifecycle test, a Curator result with status `queued` now leaves the durable event in the profile-local outbox; a later `duplicate` receipt acknowledges and clears that same event. The focused gateway hook module passes 12 tests, and `python3 scripts/check` passes all 12 checks.

**Rationale:** A successful MCP call is not necessarily a processed Curator receipt. Hermes must retain the original durable event until Curator confirms `processed` or `duplicate`.

**Impact:** Local Hermes source coverage now proves the retry/ack boundary through Hermes' production managed-MCP handler. It still uses an in-memory session and synthetic context; a configured Curator stdio process, authenticated identity, live gateway route, and deployment acceptance remain open. The Hermes change is in `/home/eaglesvn/.hermes/hermes-agent`; no GPTMD or V1 repository/runtime was modified.

<!-- curatormd:record_id=27e79cd45afaee903554c716334c980f;content_sha256=27e79cd45afaee903554c716334c980f369cc1825fe0f1d889990b536e94029d -->

## 2026-10-20 — Remove legacy V1 migration from the Curator V2 plan

**Decision:** Per owner direction, V1 is deprecated/inoperable and is not a Curator V2 import source, fallback, or rollback target. Removed the ten V1 inventory/migration/cutover checklist entries and changed V2 rollback guidance to disable only the V2 binding while retaining V2 receipts and consumer-owned records. The direct Vhost Manager profile evidence is that its legacy Curator MCP entry is disabled; this does not prove shutdown of every possible V1 runtime. No V1 repository or runtime state was inspected or changed.

**Rationale:** Keep the V2 rewrite and consumer integration plan within their owning repositories and avoid making V2 alpha depend on an obsolete V1 path.

**Impact:** A direct recount before this edit found 219 checklist items (124 complete, 95 open); after removing ten out-of-scope items the plan has 209 (124 complete, 85 open). The previously reported 221 total was inaccurate. V2 deployment, identity, retention policy, and live-runtime gates remain open.

<!-- curatormd:record_id=2941989564ce16aebe4463f68e39cda7;content_sha256=2941989564ce16aebe4463f68e39cda7e434adcae4fabc3595d851c52c8c3a31 -->

## 2026-10-20 — Correct the Curator V2 checklist count

**Decision:** The direct checkbox recount of committed `HEAD` is 221 total (124 complete, 97 open). The current working plan is 211 total (124 complete, 87 open) after removing ten V1-only cutover items. The prior HISTORY entry's 219-to-209 count and claim that 221 was inaccurate were wrong; this record supersedes those figures.

**Rationale:** Reconcile progress against exact committed and working plan files so the V1 scope removal and V2 checklist count are auditable.

**Impact:** The current V2 plan stands at 124/211 complete (87 open). No V1 repository or runtime was inspected or changed. Curator persistence MCP was unavailable with `Transport closed`, so this correction was appended locally and its status remains unverified.

<!-- curatormd:record_id=e5dd61f8c3d71ccac796e4a26f4f6d23;content_sha256=e5dd61f8c3d71ccac796e4a26f4f6d2352e568fe275515b6f9b394e551f97907 -->

## 2026-10-20 — Exercise the installed alpha plugin with Vhost Manager config

**Decision:** The installed V2 stdio launcher loaded Vhost Manager's actual `.curatormd-v2.toml` and passed goal start, exact event replay, and project-bound status against a disposable database. The test used synthetic test-only project registration/grants and wrote no Vhost Manager persistence or staging files.

**Rationale:** Verify the consumer-owned config and installed alpha package together before a writable Vhost Manager pilot.

**Impact:** Local Vhost plugin write/read and retry behavior is verified. Hermes MCP tool discovery and the profile's read-only config are separately verified; authenticated identity, app-side producer, live gateway delivery, canonical consumer persistence, and pilot write authorization remain open. Curator persistence status could not be checked because the MCP transport returned `Transport closed`.

<!-- curatormd:record_id=c578bcddebc2772990b2d8d287861202;content_sha256=c578bcddebc2772990b2d8d28786120281191bd677a0d1ad57239f8250138af2 -->

## 2026-10-20 — Run the shared producer contract in Vhost Manager

**Decision:** Added a consumer-side unittest in `/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_contract.py`. It loads Vhost Manager's own `.curatormd-v2.toml`, binds the installed alpha `ProjectPlugin`, and runs `assert_goal_started_event_contract` against disposable SQLite. The test passes.

**Rationale:** Verify the shared producer/backend contract at a real consumer boundary rather than only through Curator's reference-plugin suite.

**Impact:** Marked the shared consumer contract test plan item complete; the direct plan recount is 125/211 complete (86 open). Vhost application code and canonical state were not changed. This is fixture-backed consumer contract evidence, not app event production, authenticated identity, live Hermes delivery, or deployment verification. Curator persistence status remains unverified because its MCP transport is closed.

<!-- curatormd:record_id=6e35d4bbe5544cb8ddfbea122f2b09cb;content_sha256=6e35d4bbe5544cb8ddfbea122f2b09cbf7d8b40aefbc6a63d7a85a817fb600a0 -->

## 2026-10-20 — Reverify local Hermes profile and project routing boundaries

**Decision:** Re-ran `tests/test_hermes_hook.py`; all three tests pass. They cover bound-project routing, a separate Curator MCP process, durable event replay, and denial/non-acknowledgment of a foreign-project goal while confirming the foreign project's facts remain unchanged.

**Rationale:** Confirm the local Hermes adapter and Curator project boundary against current source before closing the plan's code-level profile/project isolation item.

**Impact:** Marked the local profile/project routing plan item complete; the working checklist is 126/211 complete (85 open). Test identity is synthetic. Authenticated Hermes identity, a live profile route, and deployed cross-project behavior remain open. Curator persistence status is unavailable because its MCP transport returns `Transport closed`.

<!-- curatormd:record_id=29b51d62763431b86e801a4c58599363;content_sha256=29b51d62763431b86e801a4c58599363f7a69f680594f42f6ea6002dbb5615ca -->

## 2026-10-20 — Disable the known V1 observer in the Vhost Hermes profile

**Decision:** At the owner's request, changed `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/hooks/curatormd-observer/HOOK.yaml` to declare no events. The Hermes hook loader, run with that profile as `HERMES_HOME`, reports `Skipping curatormd-observer: no events declared`. The profile's legacy Curator MCP entry was already disabled. The V2 MCP profile test still connects and discovers its tools.

**Rationale:** Stop the known Vhost profile's V1 observer path while keeping Curator V2 and V1 in their proper owners; the observer files remain available for recovery.

**Impact:** Hermes gateway status showed only the default profile process; no V1-named systemd unit, Docker container, or matching process appeared in host checks. No V1 repository was inspected or changed. These checks do not prove every possible V1 runtime elsewhere is stopped; V2 identity, live hook delivery, and deployment gates remain open.

<!-- curatormd:record_id=f4472b306c240f7224f2e2d262319e57;content_sha256=f4472b306c240f7224f2e2d262319e5745abf56de7a9a7c2b89466c34167d189 -->

## 2026-10-20 — Make the Vhost alpha stdio smoke repeatable

**Decision:** Extended `/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_contract.py` with a second consumer test that seeds only synthetic project registration/read/write grants in a disposable database, launches the installed alpha MCP stdio server with Vhost Manager's config, then verifies goal start, exact replay, and project-bound status. Both consumer tests pass.

**Rationale:** Keep the earlier installed-wheel smoke reproducible in the consuming repository and exercise the actual stdio boundary without changing live profile permissions or consumer persistence.

**Impact:** The Vhost Manager local plugin now has repeatable contract and installed-launcher write/read coverage. Synthetic authorization is test-only; app-side producer routing, authenticated Hermes identity, live gateway delivery, canonical consumer persistence, and deployment remain open. No Vhost Manager application source was changed.

<!-- curatormd:record_id=6076dfa20e454f1ac781d781e3d26702;content_sha256=6076dfa20e454f1ac781d781e3d26702c4e2de78cfd7a84dba28b70344d00d1f -->

## 2026-10-20 — Verify the Vhost Manager local V2 alpha route

**Decision:** The Vhost Manager local alpha uses the installed Curator V2 package, its consumer-owned hook, an isolated Hermes profile, a bounded `curator_v2` MCP allowlist, and an exact project write grant. The shared Hermes gateway is active. Hermes config validation and MCP discovery pass; all three consumer contract/hook/stdio tests pass. A synthetic bounded event traversed the loaded hook and managed MCP call, persisted to the V2 store, and a duplicate receipt cleared the Hermes durable outbox.

**Rationale:** Establish a usable local integration candidate for owner testing while keeping real-session identity, canonical consumer persistence, retention, rollback, and production claims evidence-gated.

**Impact:** The local profile/plugin/managed-MCP integration item is complete; the full deployment-level integration item remains open. A direct recount of `docs/curator-v2-plan.md` is 127 complete of 209 total (82 open). For count reconciliation, committed `HEAD` directly recounts to 124/219; the working plan removes ten V1-only checklist items and marks three evidenced V2 items complete. Earlier HISTORY assertions of 221/211 do not match the current files and are superseded by these direct counts. Curator persistence status and recall still return `Transport closed`; capture state is therefore unavailable, not verified degraded or healthy. No V1 repository/runtime, GPTMD, or Vhost Manager application source was changed. No commit or push was made.

## 2026-10-20 — Verify sensitive MCP input is absent from response and warning log

**Intent:** Continue the open plan item proving raw material is not copied into logs, exceptions, metrics, traces, backups, or canonical persistence.

**Changed fact:** Added `test_sensitive_event_is_absent_from_mcp_error_and_warning_log` in `tests/test_mcp_server.py`. It submits a credential-like canary through the MCP `event_ingest` tool and captures the MCP warning logger.

**Verification:** The canary is absent from the public tool error and captured warning. The focused regression passes; the full Curator suite passes 325 tests, Pyright reports 0 diagnostics, errors-only Pylint and Bandit pass, and `git diff --check` passes.

**Open gate:** This verifies one MCP log/error path only. V2 has no trace exporter; trace safety is not established. WAL/retry payloads, upstream sources, other logs, backups, and canonical persistence still need broader data-flow review.

**Outcome:** Privacy checklist item remains open. Curator persistence MCP still returns `Transport closed`, so this fact is recorded locally and persistence status remains unverified. No consumer or V1 source was changed.

## 2026-10-20 — Strengthen the Host Steward and Curator ownership boundary

**Intent:** Verify the Hermes Core root-account Host Steward cannot write Curator project knowledge.

**Changed fact:** Added a Host Steward regression asserting its manifest and registered tools are exactly the five host-owned tools. Read, proposal, receipt, and reconciliation handlers leave a consumer history sentinel unchanged; the separate approved-cleanup test verifies the same sentinel remains unchanged while deleting only a configured disposable cache.

**Verification:** All 21 tests in `tests/plugins/test_host_steward_plugin.py` pass on the Hermes Core branch. The test uses a temporary Hermes home, a separate temporary consumer sentinel, and a disposable cache target.

**Open gate:** This proves local plugin behavior in tests. It does not prove live root-account installation, real host attribution, authenticated approval identity, or deployment recovery.

**Outcome:** The existing local ownership checklist evidence is strengthened without moving Host Steward into CuratorMD or changing Vhost Manager/GPTMD. Curator persistence MCP remains unavailable with `Transport closed`; no commit or push was made.

## 2026-10-20 — Correct checklist totals and verify local false-green health gates

**Intent:** Continue the V2 alpha backend verification and reconcile checklist totals directly from the checked-out plan.

**Changed fact:** Added API regressions for an unprocessed event and for a staging scan stopped by its entry limit, then marked the local no-false-green health item complete. Direct counts before this update were 127/211 in the working plan and 124/221 at committed `HEAD`; after the item closure, the working plan is 128/211 (83 open). This corrects prior inaccurate 124/211, 127/209, and 124/219 figures in this history. The ten-item total difference is the V1-only cutover checklist removal; three other V2 items were already newly complete before this health item. The committed plan history contains snapshots at 220 and then 221 items, but no 173-item snapshot; the earlier 173 working-tree report cannot be substantiated from the current checkout or Git history.

**Verification:** The full Curator suite passes 327 tests; Pyright reports 0 diagnostics; errors-only Pylint, Bandit, and `git diff --check` pass. Hermes Core `scripts/check` passes 12 checks. Vhost Manager's isolated V2 consumer contract passes 3 tests, its JavaScript Vhost suite passes 22 tests, and Prettier passes. The Vhost Manager-wide `npm run check` stops at ESLint `no-empty` in the pre-existing dirty `vhost-manager/server/security.cjs` security-dashboard change; that file was left untouched.

**Open gate:** Curator persistence status and recall remain unavailable (`Transport closed`). The Vhost profile tests and prior synthetic managed-MCP route do not prove real interactive event capture, authenticated identity, canonical consumer persistence, retention approval, rollback/recovery, or production runtime. The V1 runtime remains outside Curator V2 and GPTMD remains a separate consumer.

**Outcome:** Local Curator V2 health false-green coverage is complete. Alpha testing remains limited to the isolated Vhost Manager profile and synthetic route. No V1 repository, GPTMD, or unrelated security-dashboard source was changed; no commit or push was made.

## 2026-10-20 — Exercise the Vhost consumer hook against the installed alpha server

**Intent:** Strengthen repeatable local evidence for the Vhost Manager plugin path before an interactive alpha session.

**Changed fact:** Extended the end-to-end consumer test to invoke Vhost Manager's installed hook handler and bridge its managed-MCP calls into the installed `curatormd-v2-mcp` stdio process. The test starts and activates a disposable project goal, binds a synthetic test session, delivers turn-start and turn-end in source order, and replays each event exactly. It verifies both processed receipts and the resulting intent/change facts. Prompt, response, and failure-detail canaries are absent from the SQLite database and sidecars.

**Verification:** All four tests in Vhost Manager's `test_curatormd_v2_contract.py` pass using the isolated `renew-ssl-coding` alpha environment. The integration test uses synthetic grants and a test bridge; it does not claim authenticated Hermes identity or exercise a real interactive application session.

**Open gate:** Real Hermes identity/role binding, app-side event production, canonical consumer persistence, approved retention, and deployment/recovery remain open. Curator persistence status and recall still return `Transport closed`.

**Outcome:** Repeatable local evidence now covers consumer hook to installed Curator V2 stdio processing and receipt handling. The existing checklist count is unchanged. No V1 or GPTMD source/state was changed, and no commit or push was made.

## 2026-10-20 — Correct Hermes MCP metadata typing and preserve identity boundary

**Intent:** Keep the Hermes-to-Curator transport contract accurately typed while checking whether its host context supplies an authenticated user identity.

**Changed fact:** Updated Hermes Core MCP metadata annotations to allow the boolean `hermes/durable_event` marker alongside string profile/session values. The trusted metadata helper derives profile/session from Hermes host context and does not provide a user subject. Updated the V2 release ledger's current local suite count from 324 to 327, matching the latest full-suite run.

**Verification:** Hermes trust-gating and gateway-hook suites pass 36 tests; Hermes `scripts/check` passes 12 checks. Curator's focused Hermes MCP binding test passes. `git diff --check` passes in the edited worktrees.

**Open gate:** Profile/session context is host-owned metadata, not cryptographic user authentication. Verified Hermes user/role binding, authenticated administration, real interactive Vhost testing, retention approval, and production deployment remain open. Curator V2 persistence status and recall still return `Transport closed`.

**Outcome:** The local metadata type now matches runtime values without changing authentication semantics. No checklist item was marked complete. No V1 or GPTMD source/state was changed; no commit or push was made.

## 2026-10-20 — Reverify the current V2 alpha package boundary

**Intent:** Establish current-checkout evidence for the global V2 package before any consuming-project deployment test.

**Changed fact:** No application code changed in this verification step. The current Curator V2 worktree builds package version `0.1.0a1` and installs the wheel into a clean temporary Python 3.12.3 environment.

**Verification:** The installed consumer-bound MCP launcher acceptance test passes. The locked suite passes 327 tests; strict Pyright reports 0 diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. Hermes Core trust-gating/gateway-hook tests pass 36 cases, and `python3 scripts/check` passes all 12 checks. The isolated Vhost Manager profile's `hermes mcp test curator_v2` connects and discovers 45 tools; its four consumer contract tests pass against disposable state and the installed alpha package. Hermes reports `Auth: none` for this MCP connection. The current working checklist remains 128/211 complete (83 open).

**Open gate:** Curator persistence status and recall still return `Transport closed`, so MCP persistence state is unknown. The Vhost checks use synthetic authorization and disposable test state; they do not prove Hermes user identity, retention policy, a real interactive session, deployment, or live-runtime behavior. Those gates remain open.

**Outcome:** Current V2 package and local launcher evidence is refreshed without deploying to a consumer or changing the checklist count. No GPTMD or V1 source/state was accessed. No commit or push was made.

## 2026-10-20 — Audit Hermes identity handoff and extend MCP privacy coverage

**Intent:** Trace which host-owned identity reaches Curator V2 and strengthen evidence that rejected sensitive input does not persist through MCP.

**Changed fact:** Hermes Core's opted-in MCP metadata carries profile/session values and an optional durable-event flag, not an authenticated subject. Gateway agents carry source `user_id`/platform values, but registry dispatch passes only session/turn identifiers to MCP handlers; the Vhost alpha route is local stdio. Extended the MCP sensitive-event regression to scan SQLite main/WAL/SHM/journal files, canonical history, and staging for the rejected canary.

**Verification:** The focused MCP privacy regression and full locked 327-test suite pass. Strict Pyright reports 0 diagnostics, errors-only Pylint passes, and `git diff --check` passes.

**Open gate:** Do not treat profile/session coordinates or unqualified source user IDs as verified identity. Identity mapping, exact per-user grants, real interactive session evidence, retention policy, and deployment remain open. This canary covers one rejected-event path only; retry/quarantine payload and broad source-to-sink privacy review remain open.

**Outcome:** Recorded the missing identity handoff and expanded one bounded privacy regression without changing the alpha checklist count. No Vhost application, GPTMD, or V1 source/state was modified. No commit or push was made.

## 2026-10-20 — Make open criterion blockers explicit in goal reports

**Intent:** Ensure every success criterion is visibly complete with evidence or open with a blocker and a concrete next action.

**Changed fact:** Bounded V2 `goal_report` now renders, for each open criterion, the linked open-gate bullet or a clear no-passing-evidence fallback, the owner or `unassigned`, a criterion-specific verification action, and the stored goal-level next action as a separate field. The V2 plan item is complete based on these report semantics and regression coverage.

**Verification:** The locked V2 suite passes 327 tests. Strict Pyright reports 0 diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. Tests cover linked-gate and fallback blockers with distinct criterion and goal actions.

**Open gate:** Report rendering is local V2 evidence only. Authenticated identity, approved retention, deployment, real interactive Vhost Manager session delivery, and owner release approval remain open.

**Outcome:** The report checklist item is complete; one checked item was added without changing the 211-item checklist total. No consumer repository or V1 source/state was changed. No commit or push was made.

## 2026-10-20 — Refresh the installed Vhost Manager V2 alpha package

**Intent:** Put the verified current V2 package into the isolated Vhost Manager Hermes profile and test the local consumer plugin wiring without disturbing the default gateway.

**Changed fact:** Rebuilt `curatormd-v2` version `0.1.0a1` from the current Curator V2 worktree and reinstalled it into `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/curator-v2-alpha-venv`. The profile config enables `curator_v2` with 10 selected tools; fresh stdio discovery sees the server's 45-tool surface. The wheel SHA-256 is `852e795eef0db1ea02292304cce958ef23d118a6cd90b265a1f9c926af8eb34d`.

**Verification:** Hermes `mcp test` connects to the refreshed isolated launcher. All four Vhost Manager Curator V2 consumer contract tests pass using disposable SQLite state. The full Curator suite passes 327 tests; strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass.

**Open gate:** MCP reports `Auth: none`. `hermes -p renew-ssl-coding gateway status` lists only the default gateway process, so it was not restarted. No real interactive Vhost Manager session, authenticated identity, production deployment, or retention/recovery approval is established.

**Outcome:** The current alpha package is installed and locally testable in the Vhost Manager profile. No Vhost Manager application source, GPTMD, V1 source/state, or default gateway was changed. No commit or push was made.

## 2026-10-20 — Verify the Vhost Manager V2 persistence status

**Intent:** Determine whether the installed Vhost Manager alpha uses its persistent V2 database and report its health without reading goal contents or consulting a legacy status interface.

**Changed fact:** Identified the `renew-ssl-coding` profile's configured V2 database at `/home/eaglesvn/.local/share/curatormd-v2-alpha/global.sqlite3`. The database is schema v17 and contains one registered `vhost-manager-alpha` project, one active goal, one fact, and two processed receipts; event payload retention is zero. This probe did not read or modify goal/fact content.

**Verification:** Read-only `PRAGMA quick_check` returns `ok`. Through the installed V2 stdio launcher, `project_health` returns `unknown` and `project_storage_usage` reports the same project and aggregates. The five unknown health dependencies are event router, purge scheduler, host identity, human review, and artifact-producer inventory.

**Open gate:** V2 persistence integrity is verified for this local database, but the V2 runtime is not healthy/ready: dependency observations are absent. No live gateway delivery, authenticated identity, retention/recovery policy, or production deployment is established. This result does not reuse a legacy `capture_status` value.

**Outcome:** V2 alpha persistence is present and integrity-checked; its honest V2 health state is `unknown`, not green. No database writes, record-content reads, consumer source edits, V1 access, or default gateway restart occurred.

## 2026-10-20 — Verify goal intake and reporting through the installed Vhost plugin

**Intent:** Exercise the local Vhost Manager consumer's complete bounded goal intake/report path through its installed Curator V2 stdio launcher.

**Changed fact:** Extended the Vhost consumer contract to start and replay a goal with named criteria, owner, and next action; activate it; append a typed change fact; and render `goal_report`. The report assertions cover project/owner, the change fact, the open criterion's no-passing-evidence blocker, and the separate goal-level action. The V2 plan's local consumer intake/report item is complete.

**Verification:** All four Vhost Manager consumer contract tests pass against the installed `0.1.0a1` launcher and disposable SQLite state. The exercised registration, grants, and Hermes session metadata are synthetic test inputs.

**Open gate:** This proves the installed local consumer contract only. It does not establish an interactive Vhost Manager request, authenticated identity, live gateway delivery, or canonical persistence in a live user session.

**Outcome:** The intake/report consumer item is complete; current working checklist progress is 130/211 (81 open). No consumer application source, V1 source/state, or GPTMD was changed. No gateway restart, commit, or push occurred.

## 2026-10-20 — Add an explicitly bounded local event-router command

**Intent:** Make the durable V2 event router operable for a local alpha without claiming a production worker or scheduler.

**Changed fact:** Added `curatormd-v2-router`, an opt-in one-shot command that loads up to 128 operator-specified project configs and routes at most 1,000 events per pass. Router claims are now filtered to the fixed service-map project IDs through a temporary SQLite binding table and static parameterized SQL; events for omitted projects remain untouched. The command reports only aggregate counts and sanitizes runtime errors.

**Verification:** The locked Curator suite passes 330 tests; 9 focused router/CLI tests cover opt-in, ordered processing, retries, and unbound-project preservation. Strict Pyright, errors-only Pylint, Bandit, dependency audit, and `git diff --check` pass. The rebuilt wheel is installed in the isolated Vhost Manager profile; the installed router `--help` works, Hermes MCP connects and discovers 45 tools, and all four Vhost consumer contracts pass.

**Open gate:** This is a manual local pass, not a supervised worker, production scheduler, dead-letter alert delivery, health observation, or deployed-lag probe. Authenticated Hermes identity, retention policy, and real interactive delivery remain open. Current wheel SHA-256: `62f435fde38c9dd0ad2fe363a348bc96c3ef1cb5cc01fcff529412e64549f28c`.

**Outcome:** Added a safe local routing operation and explicit operator guidance while preserving production routing gates. Current checklist progress is 130/211 (81 open). No Vhost application code, GPTMD, or V1 source/state was changed. No default gateway restart, commit, or push occurred.

## 2026-10-20 — Exercise the installed router against Vhost project bindings

**Intent:** Verify the packaged one-shot router against the Vhost Manager's actual project config while proving that other-project events remain untouched.

**Changed fact:** Added a Vhost consumer contract that seeds two project events in a disposable SQLite database, invokes the installed `curatormd-v2-router` executable with only the Vhost repository root, then checks that the Vhost receipt is processed and the other project's receipt remains received with zero attempts.

**Verification:** All five installed-package Vhost consumer contracts pass. The test uses a disposable database and actual Vhost config; it does not invoke the router against the persistent alpha inbox.

**Open gate:** The installed command is an opt-in one-shot pass only. Production worker scheduling/alerts, authenticated identity, real interactive profile delivery, and retention/recovery approval remain open.

**Outcome:** Installed-wheel router scope is verified for the local Vhost consumer without changing persistent project data or Vhost application code. Checklist progress remains 130/211 (81 open). No GPTMD or V1 source/state was accessed. No default gateway restart, commit, or push occurred.

## 2026-10-20 — Ensure the Vhost Manager alpha profile runtime

**Intent:** Start the authorized Vhost Manager alpha runtime test after the installed package, local plugin contract, and source quality checks passed.

**Changed fact:** `hermes -p renew-ssl-coding gateway ensure --json --timeout 45` returned `state=ready` with a profile-scoped endpoint under the Hermes supervisor. The ordinary gateway status command still lists only the default gateway process; no default process restart was performed.

**Verification:** `hermes -p renew-ssl-coding mcp test curator_v2` connected to the installed V2 stdio launcher and discovered 45 tools. Curator V2's 330-test suite, strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and diff check pass; Hermes Core `scripts/check` passes 12 checks; all five Vhost consumer contract tests pass against disposable state. The read-only V2 SQLite check reports schema v17 and `quick_check=ok`.

**Open gate:** No real interactive Vhost Manager event has traversed the ready profile endpoint. Authenticated identity, production scheduling/health, retention/recovery approval, canonical live consumer persistence, and release approval remain open. Curator persistence MCP status still returns `Transport closed`; V2 database integrity was checked independently and no legacy capture status was consulted.

**Outcome:** The isolated Vhost alpha endpoint is ready for an interactive test without restarting the default gateway. The V2 checklist remains 130/211 (81 open). No V1 or GPTMD source/state was accessed or modified; no commit or push was made.

## 2026-10-20 — Persist explicit evidence-gated task outcomes

**Intent:** Make finish results durable and reviewable so a completion claim cannot hide unmet criteria or appear complete without passing evidence.

**Changed fact:** `goal_finish` now records a typed `outcome` fact for both evidence-backed completion and an open result. Reports render that outcome alongside current verified/open criteria, recorded facts, owner, open gates, and next action. Explicit block/defer actions continue to use their structured goal status plus reason and recovery open-gate fact.

**Verification:** The 42 lifecycle tests, 5 MCP server tests, 7 property tests, and full locked suite of 330 tests pass. Strict Pyright, errors-only Pylint, Bandit, dependency audit, lock check, and `git diff --check` pass. Rebuilt wheel SHA-256 is `d6af5b1b5a598fe1ec611b4788f4c88af5235ddb06f3be656e6bc0e2dedf2599`; after reinstall into the isolated Vhost alpha environment, all five consumer contracts pass and Hermes MCP discovery connects with 45 tools.

**Open gate:** No real interactive Vhost event has traversed the profile endpoint. Authenticated identity, production scheduling/health, retention/recovery approval, live canonical consumer persistence, and release approval remain open. Curator persistence MCP status still returns `Transport closed`; no legacy capture status was used.

**Outcome:** The explicit task-outcome plan item is complete. V2 checklist progress is 131/211 (80 open). The current alpha package is installed in the isolated Vhost profile; no V1 or GPTMD source/state was accessed or modified, and no commit or push was made.

## 2026-10-20 — Verify active and reopened goal checkpoint reports

**Intent:** Keep current verified facts and unresolved checklist work visible in the user-facing report both during active work and after a completed goal is reopened.

**Changed fact:** `goal_report` exposes status/outcome, criterion proof state, bounded facts, current open gates, and TODOs from stored records. Extended the reopened-goal regression to verify that the earlier proof remains visible as history but no longer counts as current verification, with the reopen action and current open criteria visible.

**Verification:** The lifecycle module passes 42 tests; the full locked Curator suite passes 330 tests; errors-only Pylint and `git diff --check` pass. The rebuilt alpha wheel is installed in the isolated Vhost profile and all five consumer contracts pass, including installed-MCP incomplete finish/report. Hermes Core `scripts/check` passes 12 checks; gateway-hook and Host Steward focused tests pass 33 cases.

**Open gate:** A broader Hermes shell-hook run had 85 passes, 2 skips, and 1 failure: its routed-profile environment test hit the test guard for `/home/eaglesvn/.hermes/manifest.json`; an isolated rerun reproduced this guard failure. No Hermes files were changed in this turn. No real interactive Vhost event has traversed the profile endpoint. Curator persistence MCP continues to return `Transport closed`.

**Outcome:** The active/reopened checkpoint-report plan item is complete. V2 checklist progress is 132/211 (79 open). The Vhost database remains untouched by consumer tests. No V1 or GPTMD source/state was accessed or modified; no commit or push was made.

## 2026-10-21 — Verify the Vhost Manager V2 alpha test candidate

**Intent:** Confirm that the global Curator V2 package and the Vhost Manager local plugin are ready for a bounded live alpha test, while preserving the distinction between synthetic contract coverage and a real user session.

**Changed fact:** The Vhost profile gateway endpoint reports ready under Hermes' shared host gateway. The installed `curator_v2` MCP server discovers 45 tools. The Vhost consumer contract covers the installed launcher, project-scoped one-shot router, and bounded hook-to-MCP receipt path.

**Verification:** All five Vhost consumer contracts pass against disposable databases. The Curator suite passes 330 tests; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. The installed MCP connection test succeeds. No persistent Vhost project database or canonical persistence target was changed.

**Open gate:** No real interactive Vhost Manager request has traversed the profile endpoint. Authenticated identity, production scheduling/monitoring, retention/recovery approval, and deployment-level source trust remain open. V2 checklist progress is unchanged at 132/211 (79 open).

**Outcome:** The installed alpha is locally verified and ready for a live Vhost test session; this is not live-event or production evidence. No GPTMD state or V1 repository source was changed. At the user's prior request, the V1 Curator cron jobs in the `curatormd-coding` and `renew-ssl-coding` Hermes profiles were paused; their existing data was retained. No commit or push was made.

## 2026-10-21 — Verify the installed Vhost persistence adapter

**Intent:** Exercise the Vhost Manager project's configured Markdown target through the installed Curator V2 package without writing into the real consumer checkout or enabling review privileges in its Hermes profile.

**Changed fact:** Added an installed-package contract that copies Vhost's actual plugin config into a disposable Git checkout, creates a typed goal through the stdio MCP launcher, and runs the configured `ProjectPlugin` persistence adapter against a temporary SQLite database and target file. The test verifies synchronization, rejects a target absent from the config, and checks that the real alpha's read/write-only MCP boundary rejects `goal_persist` without review authorization.

**Verification:** All six installed-package Vhost consumer contracts pass. The persistence test reads and writes only under its temporary directory; Vhost's real Markdown files and persistent database are unchanged. `git diff --check` passes in both repositories.

**Open gate:** This proves the local Vhost config mapping and Markdown adapter, not an authenticated review decision through the live profile. A second real consumer and live Hermes identity/runtime isolation remain open. Checklist progress remains 132/211 (79 open).

**Outcome:** Vhost configured-target persistence and least-privilege denial are now covered without granting review access or touching persistent consumer data. No GPTMD or V1 source/state was changed; no commit or push was made.

## 2026-10-21 — Extend consumer and router privacy coverage

**Intent:** Advance the locally verifiable Vhost plugin contract and close another narrow raw-input disclosure path without broadening production permissions.

**Changed fact:** The installed Vhost contract now covers six cases and proves its configured Markdown adapter on disposable state, with an explicit denial when the launcher lacks the separate review grant. The Curator one-shot router test now injects a private marker through a config exception and checks that stderr contains only the generic failure category.

**Verification:** All six installed-package Vhost contracts and all three Curator router CLI tests pass. The full Curator suite passes 331 tests; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. The new Vhost test also compiles and has no trailing whitespace. No Vhost persistent database or canonical file was changed.

**Open gate:** These tests do not prove live Hermes identity/runtime isolation, authorized canonical persistence in the active Vhost profile, or universal privacy across logs, retry payloads, traces, backups, and upstream providers. V2 checklist progress remains 132/211 (79 open).

**Outcome:** Local evidence now covers the Vhost configured persistence adapter and router CLI error sanitization while preserving the review gate. No GPTMD or V1 source/state was changed; no commit or push was made.

## 2026-10-21 — Add an operator-safe SQLite recovery command

**Intent:** Make the existing verified backup and restore-to-new-file helpers usable from a local maintenance shell without creating an in-place restore or exposing database paths/errors.

**Changed fact:** Added `curatormd-v2-storage backup` and `restore` subcommands. Restore requires an explicit `--restore-to-new-path` flag. Both operations use the existing online snapshot, integrity and foreign-key checks, private temporary file, atomic non-overwriting install, and generic error boundary. The runbook now documents invocation and confirms that restore creates an isolated review copy only.

**Verification:** The full locked Curator suite passes 335 tests. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. The rebuilt alpha wheel (`cf06d826406bdd59e9390a196ac72f931345c499059ec9c56601516ca37db3af`) is installed in the isolated `renew-ssl-coding` profile. Its four storage CLI tests pass; Hermes MCP connects and discovers 45 tools; all six Vhost consumer contracts pass against disposable state, including configured-target persistence, bounded hook receipt delivery, and router project isolation. Read-only checks of the V2 profile database report schema 17, `quick_check=ok`, and no foreign-key violations. A direct `project_health` MCP call without Hermes-trusted context is correctly denied as unauthenticated, so no profile health status is inferred from that call.

**Open gate:** The CLI does not determine whether SQLite or Markdown is authoritative, repair disagreement, or switch a live service. Production restore drills, off-host/encrypted backup policy, retention, identity, and rollback approval remain open. Checklist progress is unchanged until the final verification run.

**Outcome:** Local recovery now has a bounded operator CLI that restores only to a new path while preserving existing evidence. The alpha package and local Vhost plugin are ready for a real Vhost Manager test session. This is not evidence of a real event or production readiness; no persistent Vhost database or canonical file was changed, and no gateway restart, data migration, V1/GPTMD change, commit, or push occurred. V2 checklist progress remains 132/211 (79 open).

## 2026-10-21 — Exercise isolation across installed consumer launchers

**Intent:** Strengthen the locally verifiable consumer boundary by proving two independently configured launchers cannot read or persist each other's project records through a shared backend.

**Changed fact:** Extended the Vhost Manager installed-package contract with two disposable repository roots and separate project IDs, fingerprints, profile grants, and configured Markdown targets. Both launchers share only a temporary SQLite database. Each can start and read its own goal; cross-project status reads return not-found without exposing the other project's problem text. The configured persistence adapter writes only each consumer's own goal, and cross-project persistence attempts fail.

**Verification:** All seven Vhost consumer contracts pass with the isolated alpha environment's Python 3.12.3 interpreter. Both repositories, the shared database, and both Markdown targets are temporary; the real Vhost checkout and persistent alpha database are unchanged. Curator and Vhost `git diff --check` pass.

**Open gate:** The first config is copied from Vhost Manager; the second is a synthetic consumer, not a second real repository. Trusted Hermes identity, live cross-project runtime isolation, authorized review through the live profile, and production persistence remain open. Checklist progress remains 132/211 (79 open).

**Outcome:** Local installed-launcher tests now combine cross-project access denial with independent configured persistence. This closes no deployment, identity, retention, or live-runtime gate. No GPTMD/V1 source or state, Vhost application source, persistent consumer data, commit, or push was changed.

## 2026-10-21 — Reverify Hermes Core local integration boundaries

**Intent:** Recheck the current Hermes Core gateway, trusted MCP metadata, and root-account Host Steward changes against the Curator V2 integration contract without treating local tests as identity or runtime proof.

**Changed fact:** The dirty Hermes Core checkout still contains the managed-MCP gateway path, durable profile-local outbox acknowledgment behavior, and root-account-only Host Steward tool registration. No Hermes source was changed in this verification pass.

**Verification:** The Hermes gateway-hook, MCP trust-gating, and Host Steward focused suites pass 57 tests together. `python3 scripts/check` passes all 12 checks with zero blocking or advisory findings. The Vhost installed consumer contract passes seven cases, including cross-project denial and independent configured persistence in disposable roots. No live event or persistent Vhost write was performed.

**Open gate:** Trusted Hermes user identity, the real profile/project authorization path, a live Vhost event, service-managed gateway operation, deployment recovery, and retention approval remain open. Checklist progress remains 132/211 (79 open).

**Outcome:** Current local Hermes Core and Vhost consumer integration checks pass while preserving the ownership boundary: Host Steward remains in Hermes Core, and Vhost application code and persistent data were not changed. No GPTMD/V1 state, commit, or push was involved.

## 2026-10-21 — Verify recovery commands from a clean wheel install

**Intent:** Ensure all packaged operational commands are usable after a clean alpha wheel install, including a real backup/restore-to-new-path round trip.

**Changed fact:** Extended the wheel-install CI job to exercise all five installed operational entrypoints: stage, maintenance, access, router, and storage. The storage smoke creates a disposable SQLite row, backs up to a new snapshot, restores to another new path, and checks both database integrity and row preservation. Updated the CI policy and alpha plan evidence.

**Verification:** Rebuilt the wheel and installed it into a clean Python 3.12.3 environment. The installed consumer-bound MCP acceptance test passes; all five CLI `--help` commands load; backup and restore each report `verified`; the restored row and `PRAGMA quick_check` pass. The updated workflow YAML parses. No project or profile database was used.

**Open gate:** This validates packaging and local CLI behavior, not production backup policy, off-host storage, owner-approved retention, restore drills, or live service rollback. Checklist progress remains 132/211 (79 open).

**Outcome:** The alpha wheel acceptance path now covers all five operational command entrypoints and a recovery round trip without enabling writes to the persistent Vhost profile. No deployment, V1/GPTMD change, commit, or push occurred.

## 2026-10-21 — Preserve exact router project-binding container checks

**Intent:** Remove a repository-wide Pylint diagnostic without weakening the router's project-scoped event claim boundary.

**Changed fact:** Kept `claim_pending_events` restricted to an exact built-in tuple for project bindings, documented the intentional strict-type check, and added a regression showing tuple subclasses are rejected. Extracted the V2 router CLI's project-bound queue counter aggregation from its one-shot runner so routing output stays the same with fewer locals.

**Verification:** The focused store resource and router CLI tests pass; the full locked Curator suite passes 336 tests. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, the locked dependency audit, and `git diff --check` pass. Focused router CLI Pylint reports 10.00/10. A fresh warning-level Pylint inventory falls from 279 to 277 findings: 19 convention, 252 refactor, and 6 warning findings remain.

**Open gate:** Repository-wide Pylint cleanup remains open. This local change does not close authenticated identity, retention, deployment, or live-runtime gates. Checklist progress remains 132/211 (79 open).

**Outcome:** Two nonblocking repository-wide Pylint findings are resolved while preserving exact project-binding validation and router output. No Hermes, Vhost application, V1, GPTMD, persistent consumer data, commit, or push was changed.

## 2026-10-21 — Verify Hermes Core Host Steward owner attribution

**Intent:** Reconcile the open V2 plan item for Host Steward inventory attribution against the current Hermes Core implementation and its focused tests.

**Changed fact:** Host Steward in Hermes Core attributes measured growth only across complete, unchanged configured filesystem targets, labels owner and associated service-unit growth, and reports the remaining filesystem increase as unattributed. Changed bindings, incomplete scans, and overlapping roots suppress attribution. Host Steward remains outside CuratorMD under the Hermes Core root-account boundary.

**Verification:** `scripts/run_tests.sh tests/plugins/test_host_steward_plugin.py -q` passes 21 tests; `python3 scripts/check` passes all 12 checks with zero blocking or advisory findings. The test runner completed its profile isolation setup; only its ignored timing cache was generated.

**Open gate:** This closes the local configured-target attribution behavior only. Live root-account inventory, automatic service discovery, observation of real host growth, and approval-gated cleanup remain separate gates. The checklist is now 133/211 complete with 78 open.

**Outcome:** The previously open Host Steward inventory-attribution item is closed for the tested local behavior. No Curator code/runtime, Vhost application, V1, GPTMD, persistent consumer data, commit, or push was changed.

## 2026-10-21 — Reverify Curator V2 quality and inspect the Vhost live route

**Intent:** Re-run the current Curator quality chain and determine whether the installed Vhost Manager alpha profile can produce a fresh Hermes lifecycle receipt without fabricating session identity.

**Changed fact:** No Curator implementation or persistent project data changed. Inspection confirms the Vhost profile declares the V2 local-stdio MCP server, its Hermes context opt-in, and the hook MCP allowlist. Its existing active outbox binding references a session Hermes no longer recognizes; the bounded resume probe returned `Session not found` and did not enqueue a new outbox event.

**Verification:** The full locked Curator suite passes 336 tests. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, the locked dependency audit, and `git diff --check` pass. Read-only SQLite checks report `quick_check=ok`; the Curator inbox remains at two processed events, and the Hermes outbox remains at one acknowledged event. The profile runtime setting is restored to `codex_app_server`.

**Open gate:** No fresh live Hermes session or Vhost event was exercised. The active binding and preexisting alpha records were preserved. Trusted Hermes identity, live profile/session binding, retention policy, production scheduling/monitoring, and deployment approval remain open. V2 checklist progress remains 133/211 (78 open).

**Outcome:** Curator V2's local quality baseline is current and the Vhost route gap is concretely identified as a missing live session binding. No V1 or GPTMD source/state was used; no Vhost project data was modified, and no commit or push was made.

## 2026-10-21 — Keep profile-bound MCP startup diagnostics private

**Intent:** Continue the open V2 warning-level Pylint cleanup without weakening the local MCP launcher's sanitized startup-error boundary.

**Changed fact:** Documented the intentional broad exception catch at the launcher boundary with a focused Pylint suppression; users still receive only the generic startup error category.

**Verification:** All 11 hosted-MCP tests pass. The launcher module rates 10.00/10 under full Pylint, and `git diff --check` passes.

**Open gate:** Repository-wide warning-level Pylint cleanup remains open. This change does not establish verified Hermes identity or a live profile/session binding. Checklist progress remains 133/211 (78 open).

**Outcome:** The local launcher has no warning-level Pylint finding while preserving the generic failure response. No external service, persistent consumer data, V1/GPTMD source, commit, or push was changed.

## 2026-10-21 — Add explicit Vhost session binding to the local plugin

**Intent:** Make the Vhost Hermes plugin's goal/session binding actionable while requiring a human-selected active goal and preventing Codex turns from other project roots from entering the Vhost route.

**Changed fact:** The Vhost consumer hook accepts only the exact `curator-v2 bind <goal-id>` message, then calls `hermes_goal_bind` through allowlisted managed MCP with the host session ID. Hermes Core's public `HookContext.call_mcp` now preserves only the bounded `bound`/`not_recorded` status emitted after its outbox write. Codex lifecycle delivery requires a working directory under a repository whose V2 config names the Vhost project; neither the path nor message text is sent to Curator.

**Verification:** All seven Vhost installed-package contracts pass; Hermes gateway-hook and MCP trust-gating suites pass 36 tests, and Hermes `scripts/check` passes all 12 checks. The updated Vhost hook files were copied to the profile for deployment inspection, then restored after verifying the active system service loads `/usr/local/lib/hermes-agent`, which lacks the required public `ctx` capability. No gateway restart occurred.

**Open gate:** The active Hermes service and the locally changed Hermes Core source are different builds. The matching Core runtime must be deployed before the new profile hook can be exercised. Real Vhost session binding/event delivery, authenticated identity, deployment recovery, and retention policy remain open. Checklist progress remains 133/211 (78 open).

**Outcome:** The local consumer/Core contract now defines an explicit binding path and fails closed for foreign project working directories. No Vhost application source or persistent Vhost/Curator data changed; the profile hook was restored to its previous contents, no service restart occurred, and no commit or push was made.

## 2026-10-21 — Verify the managed Hermes goal-binding path end to end

**Intent:** Close the local test gap between Hermes' public hook MCP capability and the profile-local outbox binding side effect.

**Changed fact:** Added a composed Hermes Core regression that invokes `HookContext.call_mcp` through the production MCP tool handler, validates the bounded `hermes_goal_binding` response, and reads a turn event back from the temporary outbox to confirm its persisted project, goal, and session binding.

**Verification:** The Hermes MCP trust-gating module passes 25 tests through `scripts/run_tests.sh`; Ruff lint passes on the changed gateway/MCP/test files, and `git diff --check` passes. All test state is under the isolated temporary profile home.

**Open gate:** The active Hermes gateway service still runs a different installed build without the source worktree's managed hook context. The regression proves the local Hermes Core source path only; live profile activation, verified identity, deployment, and retention policy remain open. Checklist progress remains 133/211 (78 open).

**Outcome:** The public managed-MCP path now has direct local evidence from call through durable outbox persistence. No active profile data or gateway service changed; no V1/GPTMD source, commit, or push was involved.

## 2026-10-21 — Deploy and probe the Vhost Manager V2 alpha route

**Intent:** Make the global Curator V2 backend and Vhost-owned plugin usable together in the local Hermes profile, then verify a real profile session without broadening capture.

**Changed fact:** Installed the bounded Hermes Core lifecycle-hook/outbox files and Hermes-root Host Steward plugin into `/usr/local/lib/hermes-agent`; backed up replaced files at `/home/eaglesvn/.hermes/curator-v2-alpha-runtime-backup.0KzV1U`. Updated the isolated Vhost profile hook. Fixed its binding response parser to handle the actual JSON-text MCP result while requiring both persisted `hermes_goal_binding=bound` and Curator `binding=validated`.

**Verification:** Curator's locked suite passes 336 tests; strict Pyright, errors-only Pylint, Bandit, dependency audit, and `git diff --check` pass. The Vhost installed-consumer contract passes seven tests. Hermes focused hook/trust/Host Steward suites pass 58 tests and `python3 scripts/check` passes 12 checks. The system gateway is active after restart; the Vhost profile endpoint reports `state=ready`; Curator MCP connects and exposes 45 tools. The Curator alpha database remains `quick_check=ok` with two earlier processed receipts. Two real profile sessions produced Hermes goal bindings and bounded lifecycle outbox entries, but no new Curator receipt; source sequence 2 remains unacknowledged after eight attempts and later events remain pending. The focused Hermes shell-hook suite has one real-home profile-isolation failure (52 passed, 2 skipped); a direct `hooks.entries` compatibility probe passes.

**Open gate:** Live event acknowledgment, authenticated profile/session identity, canonical persistence, retention approval, and deployment recovery remain open. A CLI session also returned a rejected MCP tool request; it does not prove a gateway-hook failure or success. Keep the Hermes outbox entries intact and use its retry path only after the rejection is identified. Do not mark the alpha route healthy from profile readiness or tool discovery.

**Outcome:** The local Core and Vhost plugin are installed and the live route probe found the next delivery issue without writing a new Curator receipt. No V1 or GPTMD source/state was used; no commit or push was made.

## 2026-10-21 — Align Vhost delivery with Hermes durable event fields

**Intent:** Resolve the live Vhost alpha delivery blocker using only the durable Hermes event contract and keep project routing explicit.

**Changed fact:** Hermes Core's durable outbox strips `cwd` before storing lifecycle events and reattaches the explicit `project_id` and `goal_id` from its persisted session-to-goal binding during delivery. The Vhost consumer previously required `cwd`, so it returned without forwarding every durable event. Updated the consumer to gate on the exact configured `vhost-manager-alpha` project ID and added fixtures that contain no `cwd`.

**Verification:** The installed-package Vhost consumer contract suite passes all seven tests, including the end-to-end hook → MCP launcher → durable Curator receipt path. This test uses disposable storage and synthetic Hermes context; it does not verify the live profile replay.

**Open gate:** Install the updated consumer hook into the isolated Vhost Hermes profile and verify an actual pending outbox event is acknowledged with a new Curator receipt. Authenticated identity, retention approval, and deployment recovery remain open. Checklist progress remains 133/211 (78 open).

**Outcome:** The consumer now matches Hermes' actual durable envelope while retaining exact project scope and bounded payload forwarding. No V1 or GPTMD source/state was used; no commit or push was made.

## 2026-10-21 — Verify live Vhost alpha lifecycle delivery

**Intent:** Complete a real Vhost profile replay after aligning the consumer hook with Hermes' durable event envelope, and verify the resulting global persistence state.

**Changed fact:** Installed the corrected consumer hook into the isolated `renew-ssl-coding` Hermes profile with a timestamped backup. The deployed hook SHA-256 matches its repository source. Restarted `hermes-gateway.service`; a fresh Vhost profile session then replayed the ordered queue. Hermes source sequences 1 through 9 are acknowledged, including the previously stuck sequence 2. The current Hermes session has an active binding to `vhost-manager-alpha` and the intended active goal.

**Verification:** Hermes profile MCP connects and discovers 45 tools. Curator's global V2 SQLite store passes `PRAGMA quick_check=ok`; the Vhost event cursor is at sequence 9 and all 10 inbox receipts are processed. The installed Vhost consumer contract passes seven tests. The full Curator suite passes 336 tests; strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. Hermes Core `scripts/check` passes all 12 checks.

**Open gate:** This verifies the isolated local alpha event route. It does not establish cryptographic human identity, owner-approved retention policy, production backup/recovery, or release approval. V2 checklist progress remains 133/211 (78 open).

**Outcome:** The deployed Vhost alpha route now produces acknowledged Hermes outbox events and processed Curator receipts. The natural-language CLI response claimed the bind had failed, while the persisted Hermes binding and Curator receipts show it completed; persisted state is the verification evidence. No V1 or GPTMD source/state was used.


## 2026-10-21 — Verify Curator V2 profile health after live receipt replay

**Intent:** Confirm current V2 operational readiness independently from successful event receipts and avoid treating a working route as an overall healthy service.

**Changed fact:** The installed Vhost profile's read-only `project_health` path returns `unknown`, while reporting zero pending, failed, or quarantined events. Its explicit dependency gates are `event_router`, `purge_scheduler`, `host_identity`, `human_review`, and `artifact_producer_inventory`. The profile assertion and local grants do not provide cryptographic identity or fresh host-owned readiness probes.

**Verification:** A read-only call to the installed `curator_v2` stdio launcher returned status `unknown` and exactly those five `dependency_unknown:*` gate codes. The V2 SQLite database remains integrity-clean; the Vhost inbox cursor remains at 9 with 10 processed receipts.

**Open gate:** Supply independently trusted readiness observations and approved identity/retention/recovery policy before claiming the global service is healthy or production-ready. V2 checklist progress remains 133/211 (78 open).

**Outcome:** V2 persistence has verified processed lifecycle receipts, while overall readiness correctly remains unknown. This fact concerns the Curator V2 profile and does not report V1 status.


## 2026-10-21 — Compose Hermes lifecycle delivery with Vhost persistence

**Intent:** Extend the Vhost installed-consumer contract to verify that bounded Hermes lifecycle facts can reach the repository-configured canonical Markdown adapter after durable processing.

**Changed fact:** The end-to-end Vhost consumer test now runs against a disposable Git clone of the Vhost config. It drives the consumer hook through a managed-MCP test bridge into the installed Curator stdio launcher, verifies processed start/end receipts and compact facts, projects the goal to its configured history target, reconciles the projection, and checks canary exclusion plus an unchanged out-of-scope target.

**Verification:** The full installed Vhost consumer contract passes all seven tests. The composed flow writes and reconciles only within its temporary checkout and disposable SQLite database.

**Open gate:** This does not launch Hermes Core or its production router, write the live Vhost canonical target, establish authenticated identity, or close retention/recovery policy. The deployment-level integration checklist remains open; V2 progress is still 133/211 (78 open).

**Outcome:** Local consumer integration now composes bounded Hermes event handling with configured Vhost Markdown persistence without touching Vhost project data.

## 2026-10-21 — Verify canonical-write-before-purge regression and V2 status

**Intent:** Record the end-to-end purge regression and refresh global Curator V2 quality and persistence evidence before continuing alpha-readiness work.

**Changed fact:** The MCP lifecycle acceptance test asserts that canonical Markdown persistence finishes before an unheld transient artifact is immediately purged, a held artifact remains, and a unique transient-content canary is absent from Markdown. The V2 activity read reports 10 processed receipts, zero received/failed/quarantined events, one goal, two facts, and zero SDE candidates for `vhost-manager-alpha`.

**Verification:** The full locked Curator V2 suite passes 336 tests. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. Read-only `project_activity_status` and `project_health` calls used the installed `renew-ssl-coding` V2 MCP launcher. The SQLite-backed V2 status reports activity as above and health as `unknown`; `event_router`, `purge_scheduler`, `host_identity`, `human_review`, and `artifact_producer_inventory` have no observed dependency status.

**Open gate:** Synthetic review authorization and the local purge test do not establish a production scheduler, approved retention policy, authenticated identity, live canonical Vhost write, or deployment recovery. Health remains unknown until required host-owned probes are observed. The exact plan count is 133/211 complete and 78 open, counting indented and unindented checkbox lines in `docs/curator-v2-plan.md`.

**Outcome:** The local persistence-before-purge contract and global V2 ledger activity are verified independently from service readiness. No checklist item was closed; V1, GPTMD, Host Steward state, and Vhost application data were not used or changed.

## 2026-10-21 — Verify the clean Curator V2 alpha wheel

**Intent:** Verify the exact local alpha package and its consumer-facing launcher in a clean environment before the planned Vhost Manager test.

**Changed fact:** Built Curator V2 `0.1.0a1` as a wheel, installed it into a disposable Python 3.12 environment, and exercised the installed profile-bound MCP launcher and operational entrypoints.

**Verification:** The clean-environment installed-launcher lifecycle test passes. All five packaged command entrypoints return help successfully. The installed backup and restore commands complete a disposable SQLite round trip; the restored database passes `PRAGMA quick_check` and preserves its test row. The existing Vhost profile connects to installed Curator V2 `0.1.0a1` and discovers 45 tools; all seven repository-owned Vhost contracts pass. Hermes reports transport auth as `none`. Temporary wheel, venv, and database files were removed by the temporary-directory context.

**Open gate:** This validates the local package, not Hermes cryptographic identity, approved retention policy, Vhost application behavior, production scheduling, or deployment recovery. Existing profile readiness remains `unknown`; the five host-owned dependency probes are unobserved. V2 plan progress remains 133/211 complete (78 open).

**Outcome:** The clean wheel and installed Vhost project plugin pass their local alpha contracts and are ready for a separately scoped Vhost application workflow test. No Vhost deployment or application data was changed in this check; no V1 or GPTMD work was performed.

## 2026-10-21 — Reverify Hermes Core and Vhost alpha integration

**Intent:** Recheck the locally installed Curator V2 consumer path and its Hermes Core source integration before the Vhost application workflow test.

**Changed fact:** No runtime or application code changed. The Vhost profile remains bound to installed Curator V2 `0.1.0a1`; its selected read/write lifecycle tools and the `project_activity_status` read are available under the profile config.

**Verification:** `hermes --profile renew-ssl-coding mcp test curator_v2` connects and discovers 45 tools; Hermes reports transport auth as `none`. The seven installed-package Vhost contracts pass. Hermes Core `scripts/run_tests.sh tests/gateway/test_hooks.py tests/gateway/test_codex_lifecycle_outbox_process.py tests/tools/test_mcp_trust_gating.py -q` passes 38 tests, and `python3 scripts/check` passes all 12 checks. Its runner refreshed a stale disposable test environment and wrote only an ignored timing cache.

**Open gate:** This verifies local source and consumer integration only. Trusted Hermes identity, Vhost application workflow, approved retention policy, production scheduling, deployment recovery, and final release approval remain open. The current V2 status remains `unknown`; its five host-owned dependency probes are unobserved. Progress is unchanged at 133/211 complete and 78 open.

**Outcome:** Local Curator, Vhost plugin, and Hermes Core integration checks pass for the alpha boundary. V1, GPTMD, Host Steward state, Vhost application data, and the unrelated Hermes shell-hook edits were not changed.

## 2026-10-21 — Install the current Curator V2 wheel in the Vhost profile

**Intent:** Deploy the current verified Curator V2 alpha artifact into the isolated Vhost Manager Hermes profile and verify the installed package, consumer contract, and persistent V2 status.

**Changed fact:** The profile had `0.1.0a1` installed with three stale modules. Rebuilt `dist/curatormd_v2-0.1.0a1-py3-none-any.whl` from current V2 source and installed that exact artifact into the profile environment. Its SHA-256 is `fcce3c0e343c79a7e800153131e0dd4b43a02087055dd6a6a257f9cbe01e688f`; all 32 installed Python module hashes now match the source tree.

**Verification:** `hermes --profile renew-ssl-coding mcp test curator_v2` connects and discovers 45 tools; transport auth remains `none`. All seven Vhost installed-package contracts pass against the exact wheel. Read-only V2 status remains 10 processed receipts, 1 goal, and 2 facts, with zero received/failed/quarantined events; `project_health=unknown` for five unobserved host-owned dependency probes. The global V2 SQLite database remains schema 17 with `PRAGMA quick_check=ok`.

**Open gate:** This is an isolated local profile deployment and consumer contract test, not a Vhost application workflow or production deployment. Authenticated identity, retention approval, production scheduling, recovery, and release approval remain open. Checklist progress remains 133/211 complete and 78 open.

**Outcome:** The Vhost alpha profile now runs the current Curator source artifact and its seven local integration contracts pass. No canonical Vhost application data was changed; V1, GPTMD, Host Steward state, and unrelated dirty files were left untouched.

## 2026-10-21 — Verify one-shot Hermes profile event delivery

**Intent:** Verify whether the isolated Vhost Manager Hermes profile can deliver a real one-shot session event through the installed Curator V2 route before starting the application workflow test.

**Changed fact:** Ran one Hermes Codex app-server turn from the Vhost Manager checkout. Hermes durable outbox sequences 10 (`codex:turn:start`) and 11 (`codex:turn:end`) match the persisted active Vhost project/goal binding. Both were acknowledged once. Curator activity is now 12 processed receipts, with the two new receipts applied and their payload JSON cleared; the existing intent/change facts remain deduplicated.

**Verification:** Read-only Hermes outbox and Curator receipt/status records confirm the route despite the CLI's natural-language response claiming the bind failed. The V2 SQLite store reports schema version 17 and `PRAGMA quick_check=ok`. Hermes gateway status reports only the default-profile PID; the isolated `renew-ssl-coding` profile route was exercised by the one-shot CLI session. `project_health=unknown`.

**Open gate:** This is profile CLI route evidence, not gateway attachment, a Vhost Manager UI/request workflow, canonical application-target persistence, authenticated identity, production health, retention approval, or deployment recovery. No plan checkbox closes from this session; progress remains 133/211 complete (78 open).

**Outcome:** Local one-shot Hermes-to-Curator V2 event delivery and receipt disposal are verified. V1, GPTMD, Host Steward state, Vhost application data, and unrelated dirty files were not changed.

## 2026-10-21 — Exercise read-only Vhost goal status and clean Hermes test lint

**Intent:** Continue local alpha verification by checking a real profile goal-status request and reducing an existing V2 quality finding.

**Changed fact:** The `renew-ssl-coding` Hermes prompt attempted a read-only `goal_report` for the existing Vhost smoke goal. Hermes returned `user rejected MCP tool call`. Separately, `tests/test_hermes_hook.py` now imports MCP and Curator modules at module scope instead of inside two test methods.

**Verification:** Read-only V2 SQLite still reports the smoke goal `active` at lifecycle revision 1, with 12 processed/applied receipts and `PRAGMA quick_check=ok`; the attempted report left the V2 database unchanged. The three focused Hermes-hook tests pass. Full focused Pylint no longer reports import-outside-toplevel findings in that module, but still reports six structural findings. The full Curator checklist remains 133/211 complete (78 open); `git diff --check` passes.

**Open gate:** Hermes profile approval prevented the `goal_report` call, so this does not verify a read-only tool workflow through the model session. No approval boundary was bypassed. Vhost application workflow, authenticated identity, retention policy, production scheduling/recovery, and `project_health` remain open.

**Outcome:** One focused non-blocking Pylint class was removed without changing behavior; the profile's refusal is recorded as a live integration limitation. No Vhost project file or application data was changed.

## 2026-10-21 — Add the selected Vhost lifecycle report tool

**Intent:** Restore the Vhost profile's intended read-only goal-report capability after its allowlist omission was found during the live alpha check.

**Changed fact:** Added `goal_report` to the `renew-ssl-coding` profile's `curator_v2` tool selection, increasing the selected Curator V2 tools from 11 to 12. Before editing, saved the exact profile config with its existing mode 0600 at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/config/config.yaml.before-goal-report-20261021T104917Z`.

**Verification:** `hermes --profile renew-ssl-coding mcp test curator_v2` connects and discovers 45 tools. A subsequent one-shot model request to `goal_report` is still rejected; read-only V2 SQLite confirms the smoke goal remains active at revision 1 and the database remains unchanged with 12 processed/applied receipts and `PRAGMA quick_check=ok`.

**Open gate:** The missing allowlist entry was a real configuration defect but not the complete cause of the rejected call. The model-session MCP approval/runtime path and real consumer status workflow remain unresolved. `project_health` is still `unknown`; authenticated identity, retention policy, production scheduling, recovery, and deployment gates remain open.

**Outcome:** The profile now explicitly selects the read-only report tool and can be rolled back from the private backup. No Vhost application files or project data changed; the call rejection was not bypassed.

## 2026-10-21 — Confirm the rejected Vhost report call in Hermes session state

**Intent:** Determine whether the rejected status read was a missing tool-selection issue or an actual rejected profile call.

**Changed fact:** Hermes' profile session database records an assistant call to `mcp.curator_v2.goal_report` followed by a tool result containing `user rejected MCP tool call`. This record exists after `goal_report` was added to the profile allowlist.

**Verification:** The profile config selects 12 Curator V2 tools, including `goal_report`; `hermes --profile renew-ssl-coding mcp test curator_v2` connects and discovers 45 tools. Read-only Curator SQLite remains valid (`PRAGMA quick_check=ok`), with source cursor 11, 12 processed/applied receipts, and the smoke goal active at lifecycle revision 1. The rejected attempt added no receipt and changed no goal.

**Open gate:** Tool availability and discovery are verified, but the actual Hermes model-session call is refused after dispatch. The reason is outside the Curator V2 handler's observable result; do not infer or bypass a user approval decision. The real consumer status workflow remains open.

**Outcome:** The missing allowlist selection is fixed, while the profile call refusal is confirmed as a separate unresolved integration boundary. Authenticated identity, retention policy, production scheduling/recovery, and live health remain open.

## 2026-10-21 — Reverify the installed Vhost consumer contracts

**Intent:** Verify the installed Curator V2 plugin's actual tool/report path after adding `goal_report` to the Vhost profile allowlist.

**Changed fact:** No runtime code or Vhost application data changed. The current installed Curator V2 wheel and consumer profile were exercised by the repository-owned Vhost integration contract.

**Verification:** `PYTHONDONTWRITEBYTECODE=1 /home/eaglesvn/.hermes/profiles/renew-ssl-coding/curator-v2-alpha-venv/bin/python -m unittest -v tests/vhost-manager/test_curatormd_v2_contract.py` passes all seven tests. Coverage includes `goal_report` through the installed stdio launcher, exact lifecycle replay, bounded hook delivery/receipt acknowledgment, configured Markdown persistence in disposable state, two-consumer authorization/isolation, and routing only the configured project. The logged `forbidden` and `not_found` MCP cases are expected denial assertions. The Hermes model-session `goal_report` call remains rejected separately.

**Open gate:** The consumer contracts are synthetic/disposable tests, not a real Vhost UI/request workflow or proof that Hermes can execute the tool call in an attended session. Authenticated identity, retention policy, production scheduling/recovery, and `project_health` remain open.

**Outcome:** The installed Vhost plugin and report tool pass local consumer contracts; the model-session approval/call path remains the separate open integration gate. V1, GPTMD, Host Steward, and Vhost application data were not changed.

## 2026-10-21 — Reconfirm Curator V2 local alpha readiness

**Intent:** Confirm that the global Curator V2 backend, repository-local plugin, and Hermes Core route meet the local acceptance bar before the Vhost Manager application smoke test.

**Changed fact:** No runtime code, package, consumer config, or application data changed. Re-ran the locked Curator suite and blocking quality/security checks, the installed Vhost consumer contracts, and the focused Hermes Core integration and health checks against the current worktrees.

**Verification:** `uv run --locked --group test python -m unittest discover -s tests -v` passes all 336 Curator tests on Python 3.12. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv audit --locked --preview-features audit-command`, `uv lock --check`, and `git diff --check` pass. The installed Vhost contract suite passes 7/7. Hermes Core's gateway/outbox/MCP suite passes 38 tests and `python3 scripts/check` passes 12/12 checks. After the readiness checks, `hermes -p renew-ssl-coding gateway ensure --json --timeout 45` returned `state=ready` with a profile-scoped systemd endpoint; `hermes --profile renew-ssl-coding mcp test curator_v2` connected and discovered 45 tools with transport auth `none`. A read-only probe of `/home/eaglesvn/.local/share/curatormd-v2-alpha/global.sqlite3` reports schema 17, `quick_check=ok`, an active Vhost project registration, one goal, two facts, 12 processed/applied receipts, zero retained event-payload bytes, and source cursor 11. The checklist parser finds 133 checked and 78 open items in the current V2 plan; no checklist item was closed by these reruns.

**Open gate:** This meets local alpha readiness for a Vhost application smoke test. The isolated Vhost profile already has the matching alpha wheel, but this verification did not exercise the Vhost UI/request workflow or write canonical application data. `project_health` remains `unknown`; authenticated identity, production retention/scheduling/recovery, and release approval remain open.

**Outcome:** The local backend, consumer plugin, and Hermes route are verified for the next Vhost alpha smoke-test step. V1 and GPTMD were not touched; Host Steward remains Hermes Core-owned. No commit or push was made.

## 2026-10-21 — Extend Hermes Core project usage to provider API turns

**Intent:** Implement the next locally testable part of the V2 per-project usage plan by extending Hermes Core's profile-local ledger to provider API responses while keeping token data out of Curator events and hook payloads.

**Changed fact:** Hermes Core now aggregates main provider API response usage by selected provider/model for each turn, represents missing or unassignable usage as unknown, and writes only for a session with an active project/goal binding. The opt-in, read-only `project_usage` profile plugin reports Codex app-server and Hermes provider API sources, excludes auxiliary calls and unbound sessions, and keeps session/goal/turn identifiers private. Schema migration backfills legacy usage rows and replay of a migrated envelope does not add a duplicate. The plugin README now matches this coverage. An eight-way replay regression across two SQLite connections verifies only one usage row is inserted. Curator's plan records this partial concurrency evidence without closing the budget or deployment-like load items; checklist progress remains 133/211 complete (78 open).

**Verification:** Hermes Core focused gateway, accounting, and project-usage tests pass (23 tests). `python3 scripts/check` passes all 12 checks; after the final integration/test updates, `python3 scripts/check --only ruff,health` passes both relevant checks. The Vhost installed-package contract passes 7/7; `hermes --profile renew-ssl-coding mcp test curator_v2` connects and discovers 45 tools with auth `none`. `git diff --check` passes in both implementation worktrees. Read-only Curator V2 SQLite reports `PRAGMA quick_check=ok`, schema 17, one active project and goal, two facts, 12 processed receipts with no retained payload JSON, and cursor 11.

**Open gate:** The Hermes `project_usage` tool is enabled and its read path is verified in the Vhost test profile, but no Hermes provider API turn has yet been recorded by the new writer there and real provider billing reconciliation remains open. Auxiliary calls, incomplete provider responses, token budgets, owner-approved retention thresholds, alerts, production scheduling, authenticated identity, attended Vhost request workflow, and live-runtime acceptance remain open. V2 profile health/capture readiness is not inferred from the database snapshot.

**Outcome:** Hermes Core's local accounting and read-only plugin now cover the locally tested provider API path. No V1 service, process, or container was found; the active Curator MCP process is the V2 alpha profile. No V1 or GPTMD source/state, Host Steward state, Vhost application data, commit, or push was changed.

## 2026-10-21 — Enable the read-only usage tool in the isolated Vhost profile

**Intent:** Verify the Hermes Core `project_usage` plugin against the actual Vhost test profile and its existing profile-local ledger, without exposing usage through Curator events or changing Vhost application data.

**Changed fact:** Enabled the bundled `project-usage` plugin only in the `renew-ssl-coding` Hermes profile and pinned its settings to the repository's exact `vhost-manager-alpha` project ID. The profile's previous ledger lacked `turn_id` and `usage_source`; migrated it using the current Hermes Core outbox initialization. Before changing profile state, created mode-0600 backups at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-project-usage/20261021T112320Z/` for both `config.yaml` and `codex-outbox.sqlite3`.

**Verification:** `hermes --profile renew-ssl-coding tools --summary list` reports `project_usage` enabled. The current profile-scoped `PluginManager` registers the tool, and a direct read-only invocation reports `status=available`, project `vhost-manager-alpha`, six Codex turns, five reported and one unknown, `tokens_complete=false`. The profile ledger passes `PRAGMA quick_check=ok`; both backups remain mode 0600. The V2 plan records this as local profile/read-path evidence only; the checklist item remains open.

**Open gate:** No Hermes provider API turn has yet been recorded by the new writer in this profile, so real provider billing reconciliation remains open. This does not exercise an attended Vhost UI/request workflow, authenticated identity, production scheduling, approved retention policy, or production deployment.

**Outcome:** The Vhost test profile now has a working read-only, project-pinned usage tool. Curator V2 event data and Vhost application data were not modified; no V1/GPTMD state, Host Steward state, commit, or push was changed.

## 2026-10-21 — Document and verify the Hermes hook failure boundary

**Intent:** Reduce one repository-wide Pylint finding without weakening the Hermes-to-Curator durable delivery contract.

**Changed fact:** Documented the Hermes hook's intentional fail-closed catch at the untrusted host/MCP boundary. Added a regression proving that an adapter exception containing private diagnostic text returns no acknowledgment and does not expose that text.

**Verification:** All three `tests/test_hermes_hook.py` tests pass. Focused full Pylint on `src/curatormd_v2/hermes_hook.py` reports no findings; errors-only Pylint passes for the hook and its test. Strict Pyright reports zero diagnostics and `git diff --check` passes. A fresh full Pylint JSON inventory falls from 267 to 266 findings, and broad-exception warnings fall from five to four. The V2 checklist remains 133/211 complete (78 open); the broader repository-wide Pylint item remains open.

**Open gate:** Remaining repository-wide structural, duplication, and warning findings are not resolved. This local quality result does not establish authenticated Hermes identity, production routing, retention policy, or live runtime behavior.

**Outcome:** One intentional host-boundary exception is now explicit and regression-tested. No Vhost application data, GPTMD, V1 state, commit, or push was changed.

## 2026-10-21 — Compose Hermes provider accounting through the local outbox

**Intent:** Verify that token groups produced from provider responses reach the bound profile-local usage ledger through the finalizer handoff.

**Changed fact:** Extended the provider accounting regression to pass reported and missing provider responses through `record_response_usage`, `_attach_profile_usage`, and `CodexLifecycleOutbox.record_agent_usage` for a bound test session. The reported provider/model group persists, while the group with missing usage remains unknown. Existing Gateway coverage separately verifies that its post-turn writer consumes and removes the private fields before ordinary hook dispatch.

**Verification:** The focused provider-accounting, Gateway, and project-usage suites pass (23 tests). Hermes Ruff and code-health checks pass; Curator strict Pyright reports zero diagnostics, focused full Pylint for the hook is clean, and `git diff --check` passes. This is mocked source-to-ledger evidence, not a live provider API request.

**Open gate:** The Vhost profile has not yet recorded a Hermes provider API turn through the new source instrumentation. Provider billing reconciliation, auxiliary-call coverage, budgets, approved retention, authenticated identity, attended Vhost workflow, and production runtime remain open.

**Outcome:** The local provider-response-to-profile-ledger path is now composed and regression-tested without adding usage data to Curator events. The checklist remains 133/211 complete (78 open); no commit or push was made.

## 2026-10-21 — Clarify cache-aware token totals

**Intent:** Reconcile the profile usage display with Hermes' canonical token bucket semantics before relying on totals for budgets.

**Changed fact:** The `project-usage` README and tool description now state that `input` may exclude cache buckets, while `total` is source-reported/normalized and may already include cache counts. Corrected the provider fixture's total and aggregate assertion to match its uncached input, cache-read, and output buckets.

**Verification:** The project-usage and provider-accounting suites pass (7 tests). Hermes Ruff and code-health checks pass. The isolated Vhost profile still reports `tokens_complete=false` because one Codex turn has unknown usage; its observed values are not presented as a billing total reconciled against a provider invoice.

**Open gate:** Source-specific total semantics outside Hermes' normalized provider API path and real provider billing reconciliation remain open. This documentation and fixture change does not define budgets, alerts, or retention policy.

**Outcome:** Cached token sub-buckets can no longer be mistaken for disjoint values that should be added to the total. No Vhost application data, V1, or GPTMD state changed.

## 2026-10-21 — Preserve provider uncertainty across failed Hermes calls

**Intent:** Close a local accounting gap where a provider request could be processed before its transport failed, and terminal retry/error paths could return before usage reached the profile-local ledger handoff.

**Changed fact:** Hermes Core now marks a provider/model usage group unknown when an exception follows entry into the transport. The common `run_conversation` result boundary attaches per-turn usage for early-return results as well as finalized turns. Added a regression for an attempted provider call that fails and verifies its unknown group remains available to the private Gateway handoff.

**Verification:** The focused Hermes provider-accounting, project-usage, and Gateway suites pass 24 tests. Hermes `python3 scripts/check` passes all 12 checks. Curator's locked full suite passes 336 tests; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv audit --locked --preview-features audit-command`, `uv lock --check`, and both repositories' `git diff --check` pass. A read-only Curator V2 database probe reports schema 17 and `quick_check=ok`, one active project, one active goal, two facts, 12 processed receipts, source cursor 11, no stored event payload JSON, and no purge targets. The V2 checklist remains 133/211 complete (78 open).

**Open gate:** This is mocked provider-failure and local source evidence; no live provider call or billing reconciliation was performed. The Vhost application workflow, authenticated identity, production retention/scheduling/recovery, and production runtime remain open.

**Outcome:** Provider attempts that may have incurred usage are no longer silently omitted from local totals on failure paths. This is Hermes Core-owned accounting; no V1 or GPTMD source/state, Host Steward state, or Vhost application data was changed. No commit or push was made.

## 2026-10-21 — Refresh the installed Vhost alpha consumer

**Intent:** Put the locally verified Curator V2 source into the dedicated Vhost alpha test environment and confirm the consumer-side integration still works against the current package.

**Changed fact:** Rebuilt the alpha wheel from the current Curator V2 checkout and force-reinstalled it only in `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/curator-v2-alpha-venv`. No Vhost Manager application source, configuration, or canonical project data changed.

**Verification:** The installed consumer contract passes all seven tests, including the disposable configured Markdown target, isolated project grants, the Hermes hook receipt boundary, and the installed MCP/router processes. `hermes --profile renew-ssl-coding mcp test curator_v2` connects to the refreshed launcher and discovers 45 tools. A fresh `hermes -p renew-ssl-coding gateway ensure --json --timeout 45` returns `state=ready` with a profile-scoped systemd endpoint. The separate `gateway status` still reports only the default manual gateway PID, so this ensure result does not prove live profile event dispatch. Read-only profile outbox SQLite reports `quick_check=ok`, 11 acknowledged events at source sequences 1-11, and zero pending events; read-only Curator V2 SQLite reports cursor 11 and 12 processed receipts.

**Open gate:** This confirms the installed Vhost Hermes profile route and disposable consumer contracts. It does not exercise a Vhost Manager UI/request workflow or establish authenticated human identity, production authorization, retention policy, backup/recovery, scheduling, or production deployment.

**Outcome:** The current Curator V2 alpha package is installed and verified in the isolated Vhost consumer environment for the next application smoke test. V1 and GPTMD were not touched; Host Steward remains Hermes Core-owned. No commit or push was made.

## 2026-10-21 — Mark project usage coverage as partial

**Intent:** Prevent a clean set of captured token rows from implying that the profile ledger covers every project-related model call.

**Changed fact:** Hermes Core's read-only `project_usage` tool now returns `coverage_complete=false` and explicit `auxiliary_calls` and `unbound_sessions` exclusions. The existing `tokens_complete` field remains scoped to unknown usage among captured turns. README and tool description explain this distinction.

**Verification:** `tests/plugins/test_project_usage.py`, `tests/agent/test_profile_usage_accounting.py`, and `tests/gateway/test_hooks.py` pass 24 tests. Hermes `python3 scripts/check --only ruff,health` passes both checks; Hermes `git diff --check` passes.

**Open gate:** The tool still does not account for auxiliary calls or sessions without an explicit project/goal binding. Project-wide token totals, budgets, alerts, provider billing reconciliation, retention policy, and live capture remain open.

**Outcome:** The read-only plugin now makes known gaps visible even when its recorded rows have no unknown token usage. This improves reporting fidelity without claiming complete project-wide coverage or altering Vhost application data. No V1 or GPTMD source/state, Host Steward state, commit, or push was changed.

## 2026-10-21 — Include active-turn auxiliary usage in project totals

**Intent:** Reduce the known gap in Hermes project usage by carrying reported auxiliary provider responses into the same bounded per-turn provider/model groups as the main conversation call.

**Changed fact:** Hermes Core's active turn now passes a turn-bound, thread-safe usage callback through the existing auxiliary accounting context. Normalized auxiliary usage is grouped by the auxiliary route and response model, not charged to the main route; a returned response with missing or unnormalizable usage marks that auxiliary group unknown. The profile plugin remains explicit that coverage is partial: unbound sessions, auxiliary calls outside the active-turn callback, and attempts without a response remain excluded.

**Verification:** The focused provider-accounting, project-usage, Gateway, and auxiliary session-accounting suites pass 36 tests. Hermes `python3 scripts/check` passes all 12 checks; the final Ruff/health rerun passes both checks with zero blocking or advisory findings. `git diff --check` passes.

**Open gate:** This verifies the mocked active-turn callback and local ledger handoff, not every auxiliary request path or unbound/subagent work. Project-wide usage completeness, budgets, provider invoice reconciliation, retention, and alerting remain open. An exploratory expanded test command also ran unrelated image-provider tests that failed because the test home guard blocked reads of `/home/eaglesvn/.hermes/manifest.json`; no image-generation code or fixture was changed. The focused V2 usage suites pass independently.

**Outcome:** Reported active-turn auxiliary tokens now contribute to the bound project ledger under their own route, and missing response usage cannot look like zero. No Vhost application data, V1/GPTMD state, or Host Steward state changed. No commit or push was made.

## 2026-10-21 — Verify the profile-local plugin and V2 alpha persistence

**Intent:** Bring the local Hermes profile plugin into a discoverable state and verify the V2 alpha persistence boundary before the Vhost application smoke test.

**Changed fact:** Installed only the existing read-only `project-usage` plugin files under the `renew-ssl-coding` profile's plugin directory. Hermes now lists it enabled for that profile; no shared plugin directory, Hermes runtime source, Vhost application source, or Curator V1 state was changed.

**Verification:** `hermes --profile renew-ssl-coding plugins doctor project-usage --ci` confirms discovery, manifest parsing, import, and one tool registration. A bounded handler call reads six `vhost-manager-alpha` turns (five reported, one unknown), with `coverage_complete=false` and `tokens_complete=false`; token values were not printed. The Vhost installed consumer contract passes all seven tests. Curator's V2 store was read-only checked: schema 17, `PRAGMA quick_check=ok`, 12 processed/applied receipts, source cursor 11, one active goal, two facts, zero inbox payload JSON, zero SDE candidates, and zero purge targets. Current Curator quality checks pass: strict Pyright, errors-only Pylint, Bandit, `uv audit`, lock check, and `git diff --check`.

**Open gate:** The installed Hermes runtime has not captured a provider API turn through the newer source writer; the local plugin currently reports only `codex_app_server` rows and explicitly reports incomplete coverage. No Vhost application request workflow or live canonical target write was performed. Authenticated identity, project health probes, retention policy, production routing/scheduling, recovery drills, and release approval remain open.

**Outcome:** The profile-local read-only plugin is discoverable and returns its configured project's existing ledger; Curator V2 persistence remains intact. This is local readiness evidence, not a production-green or completed Vhost pilot result. No commit or push was made.

## 2026-10-21 — Preserve the rejected Vhost profile smoke boundary

**Intent:** Exercise one real Vhost checkout request through the installed Curator V2 profile endpoint after local plugin registration passed.

**Changed fact:** The one-shot `renew-ssl-coding` request asked the profile to create one planned alpha smoke goal and read its status. Hermes rejected `goal_start`; no goal or receipt was added. A read-only V2 database check confirmed the requested ID is absent, the existing goal count is one, all 12 receipts remain processed, and `PRAGMA quick_check=ok`.

**Verification:** The profile command exited normally with an explicit rejected-tool response. No other MCP tool was called. The Vhost consumer contract remains 7/7 from the independent disposable-state run; that does not substitute for this live-profile request.

**Open gate:** The real Vhost consumer workflow still needs an allowed profile-mediated tool call. Do not replay the denied write through direct MCP or SQLite. The app UI/request workflow, canonical application-target write, authenticated identity, retention policy, and production health remain unverified.

**Outcome:** The approval boundary was preserved and the attempted smoke left Curator V2 state unchanged. No Vhost application source/data, V1, GPTMD, or Host Steward state was changed. No commit or push was made.

## 2026-10-21 — Recheck Hermes Core Host Steward ownership

**Intent:** Verify the separate Host Steward slice in Hermes Core while preserving its root-account ownership and the open live-installation gate.

**Changed fact:** Read-only inspection confirms `/root/.hermes` is root-owned mode 0700 and its config is root-owned mode 0600. The root config has no `host-steward` enablement, and its plugin directory has no Host Steward manifest. Curator V2 still has no Host Steward executor or registration.

**Verification:** `scripts/run_tests.sh tests/plugins/test_host_steward_plugin.py` passes 21 tests. `python3 scripts/check` passes all 12 repository checks with zero blocking or advisory findings. No root-account inventory or cleanup was invoked.

**Open gate:** Host Steward's live root-account enablement, authenticated approver identity, real inventory attribution, cross-process supervision, and deployment recovery remain unverified. The Vhost profile smoke was separately rejected by Hermes at `goal_start`; its attempted goal is absent and Curator V2 state is unchanged.

**Outcome:** Local Hermes Core Host Steward behavior and ownership separation remain verified; live root activation remains open. No Host Steward cleanup, Vhost application write, V1/GPTMD change, commit, or push occurred.

## 2026-10-21 — Preserve partial child progress in goal reporting

**Intent:** Close the local reporting gap for a parent goal with both completed and unfinished child work.

**Changed fact:** Added a lifecycle regression that finishes one child only after its criterion has passing evidence, leaves a second child active, and verifies the parent report retains both child states and its open-child TODO while the paged goal list keeps the parent active.

**Verification:** The focused `test_partial_child_completion_stays_visible_without_completing_parent` passes on Python 3.12. The full locked Curator suite passes 337 tests; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv audit`, lock check, and `git diff --check` pass. An initial assertion expected new children to start planned; the service contract starts them active, and the regression now asserts the actual documented lifecycle state.

**Open gate:** This closes local service/report rendering behavior only. Hosted dashboard behavior, authenticated identity, and a real Vhost request workflow remain open.

**Outcome:** Partially completed work remains visible without closing or rewriting the parent. The checklist changes from 133/211 to 134/211 complete (77 open); no application source or persistent Vhost data changed.

## 2026-10-21 — Reconcile transition acceptance coverage

**Intent:** Check the remaining local lifecycle acceptance item against the actual regression suite before changing its checklist status.

**Changed fact:** Mapped the required cases to named tests for the lifecycle action matrix, evidence-free completion, criteria amendment/revision, partial child completion, missing reviewer, incomplete artifact inventory, receipt-before-purge ordering, and failed purge/retry. The new partial-child regression closes the last missing named case in this set.

**Verification:** The locked Curator suite passes 337 tests. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv audit`, lock check, and `git diff --check` pass. The corresponding plan item is now checked; total checklist size remains 211.

**Open gate:** This closes local acceptance coverage only. Authenticated reviewer identity, interactive review UX, live Vhost workflow, retention approval, and production purge scheduling remain open.

**Outcome:** The specified contradictory-state and transition cases are individually traceable to regression tests. Checklist progress is 135/211 complete (76 open); no live Vhost or Host Steward state changed.

## 2026-10-21 — Recheck the Vhost alpha deployment boundary

**Intent:** Confirm that the installed Curator V2 backend and Vhost-owned plugin are ready for a bounded alpha application smoke test.

**Changed fact:** The `renew-ssl-coding` profile gateway endpoint is `ready`; its configured Curator V2 stdio server connects and exposes 45 tools. No Curator, Hermes Core, Vhost application, or profile configuration source was changed in this recheck.

**Verification:** Curator's locked suite passes 337 tests; all seven installed Vhost consumer contracts pass. Hermes Core's focused lifecycle-hook/outbox/trusted-MCP suites pass 42 tests and `python3 scripts/check` passes 12 checks. Read-only Curator V2 SQLite reports schema 17, `quick_check=ok`, one active Vhost alpha goal, 12 processed receipts, source cursor 11, no retained inbox payload JSON, and zero purge targets. The interactive profile binding attempt returned no result and was stopped; no goal, receipt, or binding change is evidenced. The checklist remains 135/211 complete (76 open).

**Open gate:** The profile-mediated live goal operation and Vhost application request workflow remain unverified. `project_health` is `unknown`; authenticated identity, retention policy, recovery, and release approval remain open. The profile interaction did not produce a result, so it was not retried through a different tool path.

**Outcome:** The local alpha backend, consumer plugin contracts, Hermes hook/outbox integration, gateway endpoint, and MCP discovery are ready for an application smoke test, but no successful interactive request is claimed. V1 and GPTMD were not touched; Host Steward remains Hermes Core-owned. No commit or push was made.

## 2026-10-21 — Keep router exception detail out of failed-delivery status

**Intent:** Verify that a failed durable delivery can preserve its event for retry without exposing exception text through router logs or its public status objects.

**Changed fact:** Added a router regression with a private exception marker. The router stores only the exception type as the failure code, emits no content-bearing log, and keeps the original inbox payload available for retry.

**Verification:** The focused failed-event quarantine/retry test and new failure-detail test both pass. The new case confirms `EventRoutingResult`, `EventInboxReceipt`, and `last_error` contain no exception detail, while the retryable `payload_json` still contains the source marker by design. Existing API metrics tests verify adapter and rejection failures expose only fixed categories and counts. The full locked Curator suite passes 338 tests; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv audit`, lock check, and `git diff --check` pass.

**Open gate:** This adds evidence for one local failed-delivery path only. Trace/exporter safety and broader retry, quarantine, backup, canonical-persistence, and upstream source-to-sink review remain open. No checklist item is closed; progress remains 135/211 complete (76 open).

**Outcome:** Failed router delivery remains retryable without copying exception detail into the router result, logs, or failure receipt. This is Curator V2-only local evidence; no Vhost or Hermes runtime state changed. No commit or push was made.

## 2026-10-21 — Keep exception detail out of quarantine status

**Intent:** Extend the V2 router privacy regression through the second failed delivery and durable quarantine transition.

**Changed fact:** The failure-detail regression now advances the same event from `failed` to `quarantined`, confirms both public routing results and the receipt omit the private exception marker, and confirms the retry payload remains in the inbox. The production router behavior is unchanged.

**Verification:** The focused regression passes. The pinned quality command passes: strict Pyright (zero diagnostics), errors-only Pylint, Bandit, `uv audit --locked --preview-features audit-command`, and `uv lock --check`. The final `git diff --check` is recorded after this history update.

**Open gate:** This proves one local failure-to-quarantine path only. Broader log, trace/exporter, backup, canonical persistence, upstream, and full retry/quarantine data-flow review remain open. Checklist progress remains 135/211 complete (76 open).

**Outcome:** Exception details remain absent from public routing/quarantine status while payload retention supports retry. V1, GPTMD, Vhost runtime, and Hermes runtime state were not changed. No commit or push was made.

## 2026-10-21 — Cover privacy through audited quarantine retry

**Intent:** Extend the failed-delivery privacy probe across operator retry and a subsequent delivery failure.

**Changed fact:** The router regression now distinguishes the private source-payload marker from the exception-detail marker. It drives the event through `failed`, `quarantined`, audited retry, and another failed delivery; routing results, receipts, and retry audit omit the exception marker, while retryable inbox JSON retains only the source payload marker and `last_error` retains the exception type.

**Verification:** The focused regression passes; the full locked Curator suite passes 338 tests. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, and lock check pass. `git diff --check` is run after this history update.

**Open gate:** This covers one local delivery/retry path. Trace/exporter safety, other retry and quarantine paths, backup/WAL, canonical persistence, and upstream source-to-sink review remain open. Checklist progress remains 135/211 complete (76 open).

**Outcome:** The tested operator retry retains required event data without copying exception text into its result or audit record. No checklist item was closed, and no Vhost or Hermes runtime state changed.

## 2026-10-21 — Remove duplicate retry-audit test code

**Intent:** Keep the new router privacy regression from increasing the open repository-wide Pylint inventory.

**Changed fact:** Extracted the repeated project-scoped retry-audit lookup into one `DurableEventRouterTests` helper used by both retry tests. Runtime behavior is unchanged.

**Verification:** All eight router tests and the full 338-test Curator suite pass. A full warning-level Pylint scan falls from 267 messages to 265; `duplicate-code` messages fall from 30 to 28, and `tests/test_router.py` has no findings. The repository-wide Pylint item remains open.

**Open gate:** Structural, interface, and duplicate-code findings remain across the repository. Checklist progress remains 135/211 complete (76 open).

**Outcome:** The privacy coverage remains intact while the router tests remove two Pylint duplicate-code findings. No checklist item was closed, and no runtime, deployment, identity, or retention gate changed.

## 2026-10-21 — Verify the rebuilt alpha consumer package and bounded CLI limits

**Intent:** Verify the latest V2 package and shared positive-integer limit parser in the isolated Vhost Manager alpha consumer.

**Changed fact:** Router and maintenance CLI limit parsing now shares `src/curatormd_v2/cli_args.py`, keeping each command's existing maximum while applying one strict positive-integer parser. The matching installed module hash is `b0492667c355411951430c031f8d2dedafa5cda9f3fd2110cc93b655400b23c0`.

**Verification:** The full locked Curator suite passes 339 tests. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv audit --locked --preview-features audit-command`, and `uv lock --check` pass. All seven installed Vhost consumer contracts pass against the isolated alpha profile; Hermes MCP discovery connects and exposes 45 tools. Hermes Core `python3 scripts/check` passes all 12 checks. The rebuilt profile wheel SHA-256 is `3f3c14135c2c36b6ccfc3ddc4ee3d3d11d8df863e110737cbd00f38eaaca696a`; `git diff --check` is rerun after this record.

**Open gate:** The contract suite uses disposable consumer repositories. A real Vhost application request and canonical application-target write remain unverified. `project_health` remains `unknown`; authenticated identity, retention approval, production scheduling/recovery, and release approval remain open. Checklist progress remains 135/211 complete (76 open).

**Outcome:** The current CLI parser is installed and the local alpha consumer contract remains green. No checklist item is closed by this verification. V1, GPTMD, Vhost application source/data, and Host Steward state were not changed; no commit or push was made.

## 2026-10-21 — Close SQLite stores through the CLI context manager

**Intent:** Remove duplicated one-shot CLI resource cleanup while preserving explicit opt-in, sanitized errors, and existing command behavior.

**Changed fact:** The router and maintenance CLIs now use `CuratorStore` as a context manager, centralizing connection closure in its existing resource lifecycle. Maintenance CLI mocks now model `__enter__`/`__exit__` and verify sanitized failures still close the store.

**Verification:** All 17 CLI tests and both store-resource tests pass. The full locked Curator suite passes 339 tests. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, and lock check pass. Full Pylint passes on the three changed source/test files. The fresh repository-wide Pylint inventory falls from 264 to 261 findings and from 27 to 24 duplicate-code findings; the repository-wide inventory remains open. `git diff --check` is run after this history update.

**Open gate:** The Vhost application request and canonical target write remain unverified. Identity, retention, production scheduling/recovery, and release approval remain open; no checklist item is closed and overall checklist progress remains 135/211 (76 open).

**Outcome:** Resource closure now follows the store's tested context-manager contract without changing the CLI output or authorization behavior. No Vhost/GPTMD/V1 state or Hermes Core source was changed; no commit or push was made.

## 2026-10-21 — Reinstall the resource-managed alpha package

**Intent:** Keep the isolated Vhost alpha profile on the exact Curator V2 source that passed the resource-lifecycle change.

**Changed fact:** Rebuilt and reinstalled the `0.1.0a1` wheel in the `renew-ssl-coding` alpha environment. The wheel SHA-256 is `514961f85a78cd61efeefa07f714f2c481b683f441f750a4ea03338bf4790889`. Installed hashes for `cli_args.py`, `maintenance_cli.py`, and `router_cli.py` match the source files.

**Verification:** All seven installed Vhost consumer contracts pass using disposable state. Hermes MCP discovery connects and exposes 45 tools. This follows the full 339-test Curator suite and 12/12 Hermes repository checks from the same source worktree.

**Open gate:** No Vhost application request or canonical application-target write was exercised. The profile transport reports `auth=none`; identity, retention, production scheduling/recovery, and release approval remain open. `project_health` remains `unknown`.

**Outcome:** The isolated local alpha package and Vhost consumer contracts use the latest source. Checklist progress remains 135/211 (76 open); no checklist item was closed. No Vhost application source/data, V1, GPTMD, or Host Steward state was changed; no commit or push was made.

## 2026-10-21 — Bound exception diagnostics to fixed labels

**Intent:** Prevent plugin-controlled exception class names from carrying private source markers into Curator logs or durable event failure codes.

**Changed fact:** Added `safe_exception_label` with an explicit set of stable diagnostic labels and a generic fallback. The event router, service failure receipt, and MCP warning logger use it instead of emitting `type(exc).__name__` directly. Router and MCP regressions raise dynamically named exception classes containing private markers and verify that only `unexpected_exception` is exposed.

**Verification:** Router (8), MCP (6), and API (34) focused suites pass; the full locked Curator suite passes 340 tests. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, and lock check pass. The rebuilt alpha wheel (`ad6ee0e214757e007765dafa806539be3fcea6fdfb2134a48484ad08dcfa1192`) is installed in the isolated Vhost profile; all seven consumer contracts pass, and Hermes MCP discovery exposes 45 tools.

**Open gate:** This bounds exception labels for the tested router, service, and MCP paths only. Retry payload disposal, trace/exporter behavior, backup/WAL, canonical and upstream flows, Vhost application writes, authenticated identity, retention, production recovery, and release approval remain open. Checklist progress remains 135/211 (76 open).

**Outcome:** Arbitrary exception type names no longer flow into the covered public logs or retry receipts. This closes no checklist item and does not establish end-to-end privacy. No commit or push was made.

## 2026-10-21 — Reverify Hermes Core integration ownership boundaries

**Intent:** Revalidate the locally modified Hermes Core gateway/outbox integration and its separately owned Host Steward plugin in the current checkout.

**Changed fact:** The Hermes repository test environment was rebuilt by its required test runner because its previous environment was missing or stale. The run left no tracked test artifacts; the Hermes worktree changes remain intact.

**Verification:** `scripts/run_tests.sh tests/gateway/test_hooks.py tests/plugins/test_project_usage.py tests/plugins/test_host_steward_plugin.py` passes 42 tests across three files. Hermes `python3 scripts/check` passes all 12 checks with zero blocking or advisory findings. The Hermes worktree `git diff --check` is clean.

**Open gate:** These are local source/test checks only. Live gateway identity, profile authorization, production supervision, root-account Host Steward activation, retention approval, and deployment recovery remain unverified. No Vhost application request or canonical target write was performed.

**Outcome:** The current Hermes Core integration checkout is locally verified at the focused test and repository-check level. Host Steward remains Hermes Core-owned, and Curator's checklist remains 135/211 complete (76 open); no plan item is closed by this verification. No commit or push was made.

## 2026-10-21 — Suppress filesystem paths in persistence failures

**Intent:** Keep private filesystem paths out of public persistence and staging errors, including exception chains retained by callers or traceback logging.

**Changed fact:** Markdown persistence now raises sanitized errors after leaving OS exception handlers for target open/read and atomic replacement failures. Temporary-file cleanup errors also use fixed messages. Project staging-root open failures no longer chain the original `OSError`.

**Verification:** The Markdown persistence module passes 19 tests and the project-plugin module passes 38 tests, including regressions that inject a private path into `OSError` and assert it is absent from error text, `__cause__`, and `__context__`. The full locked Curator suite passes 342 tests; strict Pyright reports zero diagnostics; errors-only Pylint on all Curator source and the changed test modules, Bandit, locked dependency audit, lock check, and `git diff --check` pass. Rebuilt wheel SHA-256 `2773a8e05fc28dc8e45c236b75e208428c276cfa201a98de96891c616cc2bb0e` is installed in the isolated Vhost profile; all seven consumer contracts pass against it, Hermes MCP discovery exposes 45 tools, and the installed Markdown/staging module hashes match source.

**Open gate:** A one-shot Hermes session from the Vhost Manager checkout reached the isolated profile, but the first Curator V2 `goal_list` call was rejected as `user rejected MCP tool call`. No goal or binding was created. The profile approval path and Vhost application request/canonical target write remain open; authenticated identity, retention, production recovery, and release approval remain open. Checklist progress remains 135/211 (76 open); no item is closed by this work.

**Outcome:** The covered local exception paths no longer chain private OS path text. This is partial privacy evidence and not an end-to-end privacy claim. No V1, GPTMD, Vhost application source/data, or Hermes Core source was changed; no commit or push was made.

## 2026-10-21 — Suppress paths in purge failures

**Intent:** Prevent rejected purge paths and filesystem exceptions from retaining private paths through chained exceptions.

**Changed fact:** Artifact path-confinement failures and filesystem inspection/removal failures now raise fixed `PurgeError` messages after leaving the original exception handler. Error codes and idempotent delete behavior are unchanged.

**Verification:** The purge module passes 22 tests, including regressions for outside-root and path-bearing filesystem errors. The full locked Curator suite passes 343 tests; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, lock check, and `git diff --check` pass. Wheel SHA-256 `ed728e38b88ef208e47d6a48ae6ee2982531703cd6eedf51ceb82aca5f695d77` is installed in the isolated Vhost profile. All seven consumer contracts pass, MCP discovery exposes 45 tools, and installed purge, Markdown persistence, and project-plugin modules match source hashes.

**Open gate:** The profile-mediated `goal_list` smoke call remains rejected as `user rejected MCP tool call`; no goal, binding, or receipt was created. The Vhost application request/canonical target write, authenticated identity, retention, production recovery, and release approval remain open. Checklist progress remains 135/211 (76 open); no item is closed.

**Outcome:** The purge paths covered by these regressions no longer expose path text through exception chaining. This is partial local privacy evidence; no claim is made for all logs, traces, backups, WAL state, or upstream surfaces. No V1, GPTMD, Vhost application source/data, or Hermes Core source was changed; no commit or push was made.

## 2026-10-21 — Suppress paths in direct-store purge errors

**Intent:** Keep caller-supplied filesystem paths out of direct-store missing purge-target errors.

**Changed fact:** Direct-store purge-target `NotFoundError` messages now use fixed text instead of interpolating the requested path.

**Verification:** The full locked Curator suite passes 344 tests; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, and lock check pass. The rebuilt alpha wheel SHA-256 `f2c4ffa40bf33bb35d5925436911eabc9c93dcbeed149aa6212ef2bd275a5383` is installed in the isolated Vhost profile; all seven consumer contracts pass, MCP discovery exposes 45 tools, and installed store, purge, Markdown persistence, and project-plugin module hashes match source.

**Open gate:** The profile-mediated `goal_list` call remains approval-rejected. No Vhost application request or canonical target write is verified. Retry/quarantine payloads, trace/exporter behavior, backup/WAL, canonical and upstream flows, authenticated identity, retention, production recovery, and release approval remain open. Checklist progress remains 135/211 (76 open); no item closes from this work.

**Outcome:** This covers direct-store error text only and is partial local privacy evidence. No V1, GPTMD, Vhost application source/data, or Hermes Core source was changed; no commit or push was made.

## 2026-10-21 — Reverify Hermes Core project usage accounting

**Intent:** Verify the locally implemented Hermes Core provider/model token accounting path that supplies the V2 per-project usage ledger without copying private usage into Curator event payloads.

**Changed fact:** No source changed in this verification. The current Hermes worktree implementation groups provider/model usage by turn, marks missing or failed attempts unknown, and hands bounded aggregates to the bound project-usage ledger.

**Verification:** Hermes `scripts/run_tests.sh tests/agent/test_profile_usage_accounting.py tests/gateway/test_hooks.py tests/plugins/test_project_usage.py` passes 26 tests across three files. Hermes `python3 scripts/check` passes all 12 checks, and Hermes `git diff --check` is clean. A read-only Curator V2 `project_health` call from this Codex context returns `unauthenticated` because trusted Hermes profile context is required.

**Open gate:** This is local source/test evidence only; it does not prove live provider capture, complete project-wide usage, billing reconciliation, identity, retention policy, production recovery, or Vhost runtime. Current Curator runtime health and persistence status remain unknown. Checklist progress remains 135/211 (76 open); no item closes from this verification.

**Outcome:** The Hermes Core usage integration is verified locally for the scoped files while all external/runtime gates remain open. No V1, GPTMD, Vhost application source/data, or Host Steward state was changed; no commit or push was made.

## 2026-10-21 — Compose Hermes managed MCP with the Vhost V2 consumer

**Intent:** Verify the Vhost-owned Curator V2 lifecycle hook through Hermes Core's real managed MCP client and the installed Curator V2 stdio launcher, using only disposable state.

**Changed fact:** Added the Vhost-owned `tests/vhost-manager/test_curatormd_v2_hermes_managed_integration.py` harness. It creates a temporary Hermes profile, Vhost repository clone, project registration, grants, SQLite stores, and Markdown target; loads the actual Vhost hook through Hermes `HookRegistry`; and routes through `HookContext.call_mcp` to the installed Curator server.

**Verification:** Ran the harness with Hermes Core's `.venv/bin/python`, the Hermes source root, and the installed `renew-ssl-coding` Curator V2 Python. It passed goal start/activation and persisted session binding; two lifecycle events and exact replays were acknowledged, both Curator receipts were processed, the configured Vhost Markdown projection was written through `ProjectPlugin` and reconciled through managed MCP, private model/cwd canaries were absent, and the out-of-scope target remained unchanged. A write-only MCP `goal_persist` call returned `forbidden` without changing the target; SDE persistence remains reviewer-gated. All writes were under one temporary directory. Curator `git diff --check` passes.

**Open gate:** This composes source-level Hermes managed MCP with the installed local consumer in a disposable process; it does not exercise the Hermes gateway service, the actual Vhost application request, the production persistence target, or verified identity. The profile-mediated live request remains approval-rejected; retention, production recovery, deployment, and release approval remain open. Checklist progress remains 135/211 (76 open); no item closes from this local integration.

**Outcome:** The local Hermes-to-Curator-to-Vhost adapter path is now repeatably testable without touching the active profile or Vhost project data. This is not live-runtime evidence. No V1, GPTMD, Host Steward, or production Vhost state was changed; no commit or push was made.

## 2026-10-21 — Verify Curator hook isolation across Hermes profiles

**Intent:** Ensure a Curator lifecycle hook loaded for one Hermes profile cannot receive events routed through another profile's hook registry.

**Changed fact:** Added a Hermes Core gateway regression that creates two temporary profile homes, loads the same Curator hook name through `ProfileHookRegistries`, and dispatches a lifecycle event in each profile scope. Each handler receives only its own profile's event.

**Verification:** `scripts/run_tests.sh tests/gateway/test_hooks.py` passes all 17 tests, including the new two-profile isolation regression. Hermes `python3 scripts/check` passes all 12 checks; both Hermes and Curator `git diff --check` pass.

**Open gate:** This verifies profile-local hook discovery and dispatch in the registry. It does not run the Hermes gateway service, establish authenticated user/project identity, or verify a live Vhost application request and canonical write. The deployment-level integration checklist remains open; V2 checklist progress remains 135/211 (76 open).

**Outcome:** Hermes profile hook isolation now has a focused behavioral regression relevant to the Curator V2 managed-hook integration. No V1, GPTMD, Host Steward, or production Vhost state was changed; no commit or push was made.

## 2026-10-21 — Exercise the Hermes gateway lifecycle callback in Vhost integration

**Intent:** Verify that the Vhost Curator hook works when lifecycle events enter through Hermes Core's production turn callback and scheduled gateway-loop drain.

**Changed fact:** Extended the Vhost-owned disposable integration harness to invoke `GatewayTurnProgressMixin._event_callback_sync` from a worker thread. The test captures and awaits the scheduled delivery future, then requeues the same callback payload and verifies that the Hermes outbox row count does not increase before replaying it through managed MCP.

**Verification:** The Hermes-managed integration harness passes with the installed Curator V2 launcher. Both lifecycle events are processed, exact replays are acknowledged, the write-only grant remains denied for reviewer-gated persistence, the Vhost Markdown target reconciles, and private metadata and out-of-scope targets remain absent/unchanged. Ruff check and formatting pass for the harness; Vhost `git diff --check` passes.

**Open gate:** This exercises the real gateway callback method and managed MCP client in disposable state, not a running Hermes gateway service or a real Vhost application request. Production deployment, authenticated identity, retention policy, recovery, and release gates remain open. V2 checklist progress remains 135/211 (76 open); this local integration does not close the deployment-level checklist item.

**Outcome:** The Vhost integration now covers the production lifecycle callback and scheduled delivery path as well as the hook registry, outbox, managed MCP client, installed Curator launcher, and consumer projection. No V1, GPTMD, Host Steward, or production Vhost data was changed; no commit or push was made.

## 2026-10-21 — Preserve interrupted Hermes runtime outcomes as open gates

**Intent:** Prove the end-to-end Hermes-to-Curator integration does not treat a Codex runtime interruption as successful goal completion.

**Changed fact:** Extended the disposable Vhost integration to dispatch and replay a third `codex:turn:end` event with outcome `interrupted` through Hermes Core's worker-thread lifecycle callback. The Curator report and Vhost Markdown projection must show the bounded interrupted-runtime open-gate fact while omitting model and working-directory markers.

**Verification:** The Hermes-managed Vhost harness passes and reports three processed events, exact replay acknowledgment, reconciled projection, absent private metadata, unchanged out-of-scope target, and denied reviewer-gated MCP persistence. Ruff check and format pass for the harness.

**Open gate:** This proves local event semantics through the installed alpha launcher and disposable consumer state. It does not prove that a real Vhost request succeeds, that a live Hermes gateway is running the updated route, or that authenticated identity, retention, production recovery, or release policies are satisfied. Checklist progress remains 135/211 (76 open).

**Outcome:** Local end-to-end evidence now covers intent, normal runtime completion without criterion success, and interruption as an open gate. No V1, GPTMD, Host Steward, or production Vhost data was changed; no commit or push was made.

## 2026-10-21 — Verify Hermes managed-MCP failure retention and retry

**Intent:** Confirm a failed Vhost lifecycle delivery remains pending in Hermes' durable outbox and can be retried after the managed MCP authorization path recovers.

**Changed fact:** Extended the disposable Vhost integration to temporarily remove the Curator server from that profile's hook MCP allowlist for the interrupted-turn event. The harness checks that the real callback drain leaves the row at one attempt and unacknowledged, restores the allowlist, drains again, and checks the row reaches two attempts and acknowledged before exact replay.

**Verification:** The integration harness passes with three processed lifecycle events and reports `failed_delivery_retried=true`. The denied first delivery remained unacknowledged, the restored managed-MCP delivery was acknowledged, and the retry plus exact replay produced a processed/duplicate Curator receipt without extra outbox rows. Ruff check and formatting pass for the harness.

**Open gate:** This tests the hook allowlist failure and retry using a disposable Hermes profile, not a live service outage, production router, or real Vhost request. Authenticated identity, retention policy, deployment recovery, and release approval remain open. Checklist progress remains 135/211 (76 open).

**Outcome:** Local integration now verifies that an MCP authorization failure does not falsely acknowledge or lose a Curator event and that outbox recovery succeeds after access returns. No V1, GPTMD, Host Steward, or production Vhost data was changed; no commit or push was made.

## 2026-10-21 — Verify explicit Vhost session binding through the consumer hook

**Intent:** Exercise the Vhost user's `curator-v2 bind <goal-id>` flow through Hermes Core, instead of relying only on binding as a side effect of goal activation.

**Changed fact:** The disposable managed-MCP harness now activates a goal in one session, emits the Vhost `agent:start` command for a second session, and confirms Hermes persists the second session's exact project/goal binding before lifecycle delivery. The three lifecycle events then use that explicitly bound session.

**Verification:** The final harness passes twice consecutively after moving binding and lifecycle callbacks onto the same event loop. It verifies the explicit binding, three processed lifecycle receipts, failed-delivery retry, exact replay, truthful interrupted/normal outcome facts, reconciled Vhost projection, private-metadata exclusion, and unchanged out-of-scope target. Ruff check/format and Vhost diff check pass.

**Open gate:** This verifies local hook-to-managed-MCP behavior in temporary state only. It does not establish that the interactive live profile can issue the binding request, prove the running gateway service or real Vhost workflow, or satisfy authenticated identity, retention, production recovery, or release gates. Checklist progress remains 135/211 (76 open).

**Outcome:** The Vhost-owned explicit session-binding command and the event delivery that depends on its persisted binding now have a local end-to-end regression. No V1, GPTMD, Host Steward, or production Vhost data was changed; no commit or push was made.

## 2026-10-21 — Reject explicit binding until goal activation

**Intent:** Verify the Vhost session-binding hook cannot attach a Hermes session to a planned goal before the goal is active.

**Changed fact:** The disposable integration now issues `curator-v2 bind <goal-id>` through the actual `agent:start` hook while the goal is still planned and asserts that Hermes persists no binding. It then activates the goal, repeats the same command for that session, and requires the exact project/goal binding before any Codex lifecycle delivery.

**Verification:** The managed-MCP harness passes twice consecutively with the planned-goal denial, active-goal binding, three lifecycle events, outbox failure/retry, exact replay, truthful completion/interruption facts, reconciled Vhost projection, and privacy/out-of-scope checks. The output reports `planned_goal_binding_rejected=true` and `explicit_goal_binding_verified=true`; Ruff check/format and diff checks pass.

**Open gate:** This proves the Vhost hook and Hermes profile outbox behavior in disposable local state. It does not establish interactive live-profile authorization, a real Vhost application request, verified human identity, retention policy, production recovery, or release approval. Checklist progress remains 135/211 (76 open).

**Outcome:** The explicit binding command is verified to fail closed for planned goals and succeed only after activation in local integration. No V1, GPTMD, Host Steward, or production Vhost data was changed; no commit or push was made.

## 2026-10-21 — Bound Hermes lifecycle failure labels

**Intent:** Keep arbitrary failure details out of Hermes lifecycle callbacks and the profile-local durable event outbox.

**Changed fact:** Hermes Core now permits only `exception`, `postprocess_exception`, and `codex_error` as Codex lifecycle `failure_kind` values. The producer omits unrecognized values, and the durable outbox applies the same closed allowlist before serializing the event. The routed shell-hook profile-isolation regression now bypasses the installed-command discovery seam, keeping that temporary-home test away from the real installation manifest while dedicated tests cover command discovery.

**Verification:** Six focused producer/outbox/usage tests pass, including a secret-like canary assertion against the SQLite `context_json`. The Hermes routed shell-hook suite passes 53 tests with two Windows-only skips. Targeted Ruff lint passes, Hermes `python3 scripts/check` passes all 12 checks, Curator's locked suite passes 344 tests, Pyright, errors-only Pylint, Bandit, `uv audit --locked --preview-features audit-command`, `uv lock --check`, and both repository diff checks pass. The disposable Vhost managed-MCP harness also passes with planned-goal rejection, explicit binding, three lifecycle events, failed-delivery retry, exact replay, denied reviewer persistence, and reconciled Markdown projection. Whole-file Ruff format checking still reports existing formatting differences in four dirty Hermes files; no mass reformat was applied.

**Open gate:** This is local event privacy evidence only. It does not prove Vhost application behavior, live Hermes delivery, identity, retention, production recovery, or release readiness; no checklist item closes and progress remains 135/211 (76 open). A read-only Curator `goal_list` call in this Codex session returned `unauthenticated` because trusted Hermes profile context was unavailable, so backend goal persistence could not be verified in this session.

**Outcome:** Both the callback producer and durable sink now fail closed for unrecognized failure labels. No V1, GPTMD, Host Steward, or production Vhost state was changed; no commit or push was made.

## 2026-10-21 — Check goal reports against persisted cleanup state

**Intent:** Ensure the MCP-facing final summary agrees with the stored goal, evidence, current gates, canonical receipt, and purge status.

**Changed fact:** Extended the end-to-end MCP SDE/purge regression to check the exact problem, completed outcome, verified criterion and fact ID, terminal next action, pending purge gate, canonical target, and `purge_pending` receipt before releasing a held artifact. After the authorized release/retry completes, the test requires the report to show `complete` and clear the purge gate and TODO.

**Verification:** The focused end-to-end MCP test passes. The full locked Curator suite passes 344 tests; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, lock check, and `git diff --check` pass.

**Open gate:** This validates local report consistency with disposable SQLite and a test reviewer. It does not establish authenticated reviewer identity, a real Vhost application workflow, retention policy, production recovery, live runtime, or release approval. The V2 checklist advances to 136/211 complete (75 open).

**Outcome:** The final-summary consistency item is verified for the local MCP SDE/purge path. No V1, GPTMD, Host Steward, or production Vhost data was changed; no commit or push was made.

## 2026-10-21 — Surface reached staging budgets in local health

**Intent:** Make configured staging-capacity pressure visible to the project health and metrics surfaces without inventing a retention threshold.

**Changed fact:** Local health now adds `staging_budget_reached` when a complete bounded staging scan observes bytes or regular-file count at or above the consumer's configured project limit. Incomplete inventory continues to produce its existing degraded gate.

**Verification:** The focused authorized API/Prometheus regression passes for both byte and file limits and confirms below-limit staging does not produce the new gate.

**Open gate:** This is a local observation over operator-configured limits. It does not define retention or deletion policy, provide alert delivery, or prove production scheduler, storage-adapter, identity, deployment, or live-runtime behavior. V2 checklist progress remains 136/211 (75 open).

**Outcome:** Configured staging budget exhaustion is now distinct in local health gates and the open-gate metric. No automatic deletion or budget policy was added. No V1, GPTMD, Host Steward, or production Vhost state was changed; no commit or push was made.

## 2026-10-21 — Inventory all project staging artifacts

**Intent:** Ensure project staging inventory includes artifacts outside currently registered goal scopes without permitting automatic cleanup.

**Changed fact:** Added `ProjectPlugin.discover_project_staging_artifacts()`, which uses the bounded, no-follow scanner and returns a complete hashed project manifest, including orphaned goal directories.

**Verification:** The focused project-root inventory regression covers every configured temporary class plus an unrecognized orphan file; strict Pyright reports zero diagnostics.

**Open gate:** The method is read-only and does not authorize purge or set age-based retention. Producer adoption, policy approval, deployment, identity, and live-runtime gates remain open. V2 checklist progress remains 136/211 (75 open).

**Outcome:** Local project-wide inventory now has a callable plugin adapter surface. No V1, GPTMD, Host Steward, or production Vhost state was changed; no commit or push was made.

## 2026-10-21 — Expose project staging inventory to reviewers

**Intent:** Make the complete project staging snapshot usable from the local consumer API while retaining the review authorization boundary.

**Changed fact:** Added an authenticated API operation and read-only MCP tool for project-wide staging manifests. Both require the exact project's `review` grant; they return only bounded artifact paths, hashes, and scan metadata.

**Verification:** The API regression confirms an orphaned artifact is included and a read-only-only caller is denied. The composed MCP goal workflow discovers and reads the project manifest. Focused API/MCP tests pass; Pyright, errors-only Pylint, and `git diff --check` pass.

**Open gate:** Local authorization uses the configured host authorizer and does not prove authenticated Hermes identity, producer adoption, out-of-root inventory, deployment, retention policy, purge scheduling, or live runtime. Checklist remains 136/211 (75 open).

**Outcome:** Reviewers can inspect the complete local staging manifest before making any separate disposition decision. No purge or retention behavior was added; no V1, GPTMD, Host Steward, or production Vhost state was changed; no commit or push was made.

## 2026-10-21 — Gate installed review tools by exact opt-in

**Intent:** Make review-gated project inventory usable from the packaged local consumer launcher without widening its default permissions.

**Changed fact:** Added `--allow-review` to the local MCP launcher. It enables `REVIEW` only when the profile has the exact durable project grant, and defaults off. The clean-wheel acceptance test now invokes project-wide staging inventory through the installed stdio launcher.

**Verification:** All 12 hosted-MCP tests pass, including default-deny and exact-grant cases. A clean Python 3.12 wheel install passes the installed launcher goal/inventory acceptance and all five operational CLI `--help` checks. Strict Pyright, errors-only Pylint, Bandit, and `git diff --check` pass.

**Open gate:** This proves local host-grant enforcement and package behavior only. It does not authenticate Hermes identity or authorize enabling review in a consumer profile; deployment, SDE disposition, retention, purge, and live-runtime gates remain open. Checklist remains 136/211 (75 open).

**Outcome:** Authorized local reviewers can opt into the read-only staging inventory tool. Review remains disabled without explicit launcher configuration and an exact durable grant. No Vhost runtime, V1, GPTMD, or Host Steward state was changed; no commit or push was made.

## 2026-10-21 — Report staging adapter failures in project health

**Intent:** Preserve a truthful health response when the configured staging root or its coordination lock is unavailable.

**Changed fact:** Health input collection now converts typed staging-root and lock failures into fixed, content-free staging error codes. The local health evaluator adds `staging_adapter_unavailable` while retaining the incomplete-inventory gate, so the project remains readable but degraded.

**Verification:** All 35 API facade tests pass. The regression confirms degraded project health and the Prometheus open-gate metric when the staging lock cannot open. Strict Pyright, errors-only Pylint, Bandit, and `git diff --check` pass.

**Open gate:** This covers local staging-root/lock failures only. Other storage adapters, production scheduling, alert delivery, identity, retention policy, deployment, and live runtime remain open. Checklist remains 136/211 (75 open).

**Outcome:** Local health no longer fails without accounting when staging coordination is unavailable. No purge or retention behavior changed; no V1, GPTMD, Host Steward, or production Vhost state changed; no commit or push was made.

## 2026-10-21 — Verify local immutable Git diff evidence

**Intent:** Add one usable repository-diff evidence source without accepting caller-written receipts or storing patch contents.

**Changed fact:** Added `GitCommitDiffResolver` for full commit-ID ranges in one host-configured worktree. It rechecks commit objects, streams a bounded diff into SHA-256, and returns only project/goal/criterion-bound receipt metadata. Added `LocalGitTestRunnerResolver`, which runs only its host-configured argv in an isolated checkout of the exact commit, bounds runtime/output, kills the process group on timeout, rejects nonzero exits, and returns a digest without retaining runner output. The existing `RepositoryEvidenceAdapter` validates both receipts.

**Verification:** The evidence tests prove exact diff digest, exact-commit runner execution despite later worktree edits, project/runner rejection, nonzero-run rejection, process-group timeout cleanup, content/path-free receipts, and fail-closed output limits. The 13-test evidence module and full 350-test Curator suite pass. Strict Pyright, errors-only Pylint, Bandit, locked dependency audit, lock check, and `git diff --check` pass.

**Open gate:** These are local Git/worktree and runner assertions, not signed provider receipts or authenticated identities. Deployment-owned runner credentials, revocation, service/browser adapters, human confirmation, and end-to-end runtime remain open. Checklist remains 136/211 (75 open).

**Outcome:** Curator can locally verify exact immutable repository diffs and run a configured test command at a selected commit without retaining patch or output text. No V1, GPTMD, Host Steward, Vhost runtime, or live identity state changed.

## 2026-10-21 — Reverify Curator V2 suite, quality chain, and wheel import

**Intent:** Verify the current Curator V2 source and built alpha package before publishing a scoped local checkpoint.

**Changed fact:** No implementation code changed during this verification. The disposable wheel install included declared runtime dependencies and imported both packaged Git evidence resolvers successfully.

**Verification:** The locked Curator suite passes 350 tests. Strict Pyright, errors-only Pylint, Bandit, locked dependency audit, `uv lock --check`, `git diff --check`, and `uv build` pass. The isolated Python 3.12 wheel import succeeds.

**Open gate:** Curator V2 MCP tracker access returned `unauthenticated: Trusted Hermes profile context is required`, so live project-ledger persistence is unverified. Deployment-owned identity and trust, owner-approved retention, production scheduling/recovery, and real consumer workflow remain open. The V2 plan remains 136/211 complete (75 open); no gated checkbox is closed by local tests.

**Outcome:** Local suite, blocking quality/security checks, and package import are verified for this tree. No V1, GPTMD, Host Steward, or Vhost runtime state was changed.

## 2026-10-21 — Install pushed Curator V2 wheel in isolated Vhost alpha profile

**Intent:** Run the conditional local Vhost consumer check after the pushed Curator backend, package, and repository plugin met their local verification bar.

**Changed fact:** Rebuilt the `0.1.0a1` wheel from Curator commit `aa12cd8` (SHA-256 `ae07285be32d624884ebfef9ec1a44c4b9ea146a03257d84903008bbd595d10f`) and installed it in the isolated `renew-ssl-coding` Hermes profile environment. No Vhost source or application data changed.

**Verification:** The installed Vhost consumer contract passes 7/7. The Hermes-managed integration harness reports explicit goal binding, bounded lifecycle delivery, safe exact replay, failed-delivery retry, processed receipts, disposable Vhost projection reconciliation, and denial of reviewer-only persistence to the write-only profile. All 34 installed package modules match Curator source hashes. Hermes MCP discovery connects with `auth=none` and exposes 46 tools.

**Open gate:** The harness uses disposable state and does not exercise the real Vhost application request/UI workflow. MCP discovery does not authenticate Hermes identity. Production identity, approved retention, scheduler/recovery, live health, and release approval remain open; checklist progress remains 136/211 (75 open).

**Outcome:** The locally verified Curator package is installed and passes the Vhost plugin composition contracts in the isolated alpha profile. The Curator MCP tracker remains unauthenticated outside the trusted Hermes profile context. No GPTMD, V1, Host Steward, or Vhost application data changed.

## 2026-10-21 — Add explicit impact and retrieval value to SDE proposals

**Intent:** Make significance assessment distinguish verified facts, claimed or expected impact, and future retrieval value while keeping ordinary progress on the goal ledger.

**Changed fact:** New significant SDE candidates now require compact impact and retrieval-value fields alongside selected same-goal facts and a currently verified passing fact. These fields persist immutably and conflicting replay context is rejected. Routine progress still creates no candidate. Schema v18 adds nullable columns so existing proposals remain readable without invented context. The V2 plan's corresponding local checklist item is closed; human disposition, retention policy, and runtime gates remain separate.

**Verification:** All 353 Curator tests pass. Strict Pyright reports 0 diagnostics; errors-only Pylint, Bandit, locked dependency audit, `uv lock --check`, `git diff --check`, and `uv build` pass. The built alpha wheel SHA-256 is `b141087b8f9359097d5246195d8c9a09cc60a8fae37dfb128539956c267f94b3`.

**Open gate:** The current authenticated Curator V2 goal tracker is unavailable in this session; this history update is repository-local evidence, not live tracker persistence. Production migration/rollback, authenticated identity, human review, retention policy, scheduler/recovery, and live runtime remain open. The checklist is 137/211 complete (74 open).

**Outcome:** Local SDE proposal context, migration, API/MCP paths, tests, and package build are verified. No V1 runtime, GPTMD, Host Steward, Vhost application data, or production state changed.

## 2026-10-21 — Close local SDE canonical-write and purge lifecycle item

**Intent:** Verify the checklist's local cleanup guarantee from review receipt through canonical persistence, exact inventory purge, hold retention, and retry recovery.

**Changed fact:** The plan now records the local lifecycle item as complete based on the existing MCP and purge regressions. Those tests show canonical goal facts and the immutable review receipt are persisted before eligible transient data is purged; held artifacts remain, and injected purge failures stay pending until retry succeeds.

**Verification:** `test_mcp_sde_assessment_review_persistence_and_purge_are_end_to_end` and `test_interrupted_purge_is_visible_and_retryable` are included in the passing 353-test locked suite. `git diff --check` passes for this plan/history update.

**Open gate:** Tests use a test review authorizer and disposable local state. Live authenticated reviewer UX, approved retention policy, production cleanup scheduling/recovery, and live runtime remain open. Checklist is 138/211 complete (73 open).

**Outcome:** The local canonical-write-before-purge and retry lifecycle row is closed; this does not close deployment, identity, retention, or live-runtime gates.

## 2026-10-21 — Reverify Hermes Core lifecycle integration

**Intent:** Refresh the V2 release evidence for Hermes Core's locally implemented Codex lifecycle outbox and managed MCP hook path.

**Changed fact:** Curator's plan and release ledger now record current evidence from Hermes source head `9b8fc71e30` and the successful Curator CI run on `94bb816`. The Hermes checkout was clean after verification. No Hermes source or runtime configuration changed.

**Verification:** `scripts/run_tests.sh` passes 61 tests across gateway hooks, profile usage accounting, and Codex app-server integration. Hermes `python3 scripts/check` passes all 12 checks. Curator GitHub Actions run [39628941504](https://github.com/eagles-edu/curatormd-v2/actions/runs/39628941504) passes quality/security checks, clean-wheel acceptance, and Python 3.12/3.13/3.14 suites. Curator's local suite passes 353 tests.

**Open gate:** Read-only Curator V2 goal listing returns `unauthenticated: Trusted Hermes profile context is required`; live tracker persistence is unverified. These checks do not prove cryptographic Hermes identity, production scheduling/recovery, owner-approved retention, or the Vhost application workflow. Checklist remains 138/211 complete (73 open).

**Outcome:** Local Hermes Core integration and Curator package/repository checks are current and verified. Deployment, identity, retention-policy, and live-runtime gates remain open.
