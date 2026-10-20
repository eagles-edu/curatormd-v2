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
