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
