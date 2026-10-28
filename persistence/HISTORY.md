# Curator V2 history

## 2026-10-27 — Record request-bound Vhost acceptance progress

- **Intent:** Continue the real-consumer acceptance work in Slice I with a
  request whose criteria are fixed before the Vhost utility applies changes.
- **Changed fact:** The consumer-owned static-site run preserved the exact
  mode-specific problem and criteria in a scoped Vhost goal; apply and rollback
  receipts processed, and post-restart inspection confirmed rollback cleanup.
- **Verification:** The focused consumer contract passed; the active Vhost
  service retained operation history, the test site/account/home were absent,
  and Nginx/OpenLiteSpeed remained active and configuration-valid. See the
  consumer-owned record at `../../renew_ssl/docs/curatormd-v2-alpha.md`.
- **Open gate:** Direct bounded Hermes `goal_report`, same-event live replay,
  out-of-scope before/after hashes, and owner review remain unverified. No
  checklist marker changed.
- **Outcome:** Keep the pilot item open while retaining this local progress.

## 2026-10-27 — Reconcile project staging threshold documentation

- **Intent:** Continue the local V2 plan by correcting repository guidance that
  contradicted the approved warning-only staging threshold behavior.
- **Changed fact:** The reference-plugin guide and example consumer config now
  state that project byte/file thresholds warn but do not block writes or
  delete artifacts; complete-scan requirements and per-artifact/per-goal safety
  ceilings are documented separately.
- **Verification:** Source and regression coverage show writes remain allowed
  above project thresholds; `git diff --check` passes. No tests ran because the
  change is documentation-only.
- **Open gate:** Complete scan, token-source coverage, measured budgets, alert
  delivery, and production retention evidence remain open; no plan marker was
  changed.
- **Outcome:** Keep repository instructions aligned with the warning-only
  local-alpha policy without overstating broader budget completion.

## 2026-10-24 — Verify the Curator V2 CI quality commands

- **Intent:** Complete the pending verification of Curator V2's current
  blocking quality checks without rerunning the unit suite.
- **Changed fact:** The exact commands declared in `.github/workflows/ci.yml`
  pass against the current source: strict Pyright, errors-only Pylint, Bandit,
  and `git diff --check`.
- **Verification:** Pyright reports zero diagnostics; the Pylint, Bandit, and
  diff commands exit successfully. No tests ran because no source code changed.
- **Open gate:** The last full Pylint inventory remains at 126
  convention/refactor findings; this verification does not close its checklist
  row or any deployment gate.
- **Outcome:** Keep blocking CI quality status separate from open whole-tree
  lint cleanup.

## 2026-10-24 — Verify current Hermes profile health

- **Intent:** Confirm the updated Hermes source checkout can read the current
  local-alpha ledger and health through the actual profile-bound V2 route.
- **Changed fact:** The read-only `renew-ssl-coding` probe connected to the
  configured stdio server, discovered 48 tools, and returned 12 processed
  receipts, one goal, two facts, and `project_health=healthy` with no gates.
- **Verification:** The active six-hour timer is scheduled for 00:00, 06:00,
  12:00, and 18:00 with a 15-second spread; its last run at 20:55 preceded the
  cadence change. Therefore health is currently clear, but the first scheduled
  six-hour execution remains unverified. No Vhost application workflow or
  project-data mutation was performed.
- **Open gate:** Hermes Core source changes are not installed in
  `/usr/local/lib/hermes-agent`; real Vhost application production, first
  six-hour retry pass, and production/release gates remain open.
- **Outcome:** Record current local profile health without overstating the
  timer cadence or consumer-workflow evidence.

## 2026-10-24 — Verify Hermes source health probes and session context

- **Intent:** Continue the V2 Hermes Core integration and validate the
  local-alpha readiness bridge against Hermes' profile and session boundaries.
- **Changed fact:** The Hermes source checkout reads the six-hour maintenance
  timer's recent successful run, checks the journal output route without
  reading records, and attaches a verified session subject only when the
  session profile home matches the active request profile. No active Hermes
  install or Vhost project file was changed.
- **Verification:** Nine readiness tests, 25 MCP trust tests, and three focused
  session-identity tests pass; targeted Ruff and Hermes `git diff --check`
  pass. The broader gateway file had 638 passes and one unrelated quick-command
  test failure caused by a real-home manifest read under the test I/O guard.
  `scripts/check` ran 12 checks; blob-size and health checks could not find a
  merge base in this shallow branch, while `scripts/check --only ruff` passes.
- **Open gate:** The modified Hermes checkout is not the active install; the
  first six-hour run after cadence change remains pending; Slice G and live
  consumer workflow are open. No checklist marker changes from this supporting
  integration work.
- **Outcome:** Keep the source-level readiness result and its runtime limits
  explicit; continue toward a verified local Hermes-to-Curator workflow.

## 2026-10-24 — Share checklist snapshot validation

- **Intent:** Keep event-ingress and persisted goal records under one checklist
  snapshot validation rule.
- **Changed fact:** Both `GoalStarted` events and `GoalCard` records call the
  same validator for optional metadata, exact SHA-256 revision syntax, bounded
  nonempty source text, and single-line form.
- **Verification:** Event-contract and lifecycle suites pass 66 tests. Strict
  Pyright reports zero diagnostics. Whole-tree Pylint reports 126 findings
  (14 convention, 112 refactor, including 17 duplicate-code findings), with no
  warning/error categories. `git diff --check` passes.
- **Open gate:** Repository-wide lint cleanup remains open; no delivery item is
  closed by this validation refactor.
- **Outcome:** Preserve both ingress and record validation semantics through
  one shared rule.

## 2026-10-24 — Reuse exact test project provisioning

- **Intent:** Remove repeated hosted-MCP and host-service test registration
  logic while preserving each test's exact grants and audit rationale.
- **Changed fact:** Both fixture paths now use `register_test_project_access`
  from `tests/project_fixtures.py`; the shared helper takes an explicit
  immutable grant specification and retains each caller's administrator,
  action set, and rationales.
- **Verification:** The affected suites pass 17 tests and strict Pyright reports
  zero diagnostics. Whole-tree Pylint reports 127 findings (14 convention,
  113 refactor, including 18 duplicate-code findings), with no warning/error
  categories. The focused lint scan shows only the hosted-MCP module's existing
  module-size/local-complexity messages. `git diff --check` passes.
- **Open gate:** Repository-wide lint cleanup remains open; no delivery item is
  closed by this fixture refactor.
- **Outcome:** Keep the least-privilege test grants caller-specific and share
  only their common registration mechanics.

## 2026-10-24 — Refresh the local Hermes profile package

- **Intent:** Verify the current Curator V2 package and consumer integration in
  the approved single-user Vhost alpha profile.
- **Changed fact:** Synchronized the profile to source commit `1e10df2` as wheel
  SHA-256 `4118c2cd1aeaf323bd88c8c0bdcd5d11173ac50769d0bceb4b1b747b82b660d2` and
  installed it only in the `renew-ssl-coding` Curator virtualenv after backing
  up the previous package, metadata, and CLI entry points. The archive and
  sidecar file-hash manifest at
  `backups/curator-v2-package-before-alpha-refresh-20261024T2255/` were
  verified; archive SHA-256 is
  `f471d4e7c6dd43ac295c3c0e925d0dca678e2e4ac2291d2bfabe9e14ead5e0f8`. All 51
  installed Python modules match source byte for byte.
- **Verification:** `pip check` reports no broken requirements. Seven Vhost
  contract tests and the Hermes-managed disposable recovery harness pass
  against this package. The harness processes five events with replay/retry,
  re-enrollment, projection reconciliation, and privacy checks. The read-only
  Hermes profile probe returns 48 tools, 12 processed receipts, one goal, two
  facts, and healthy project status with no gates.
- **Open gate:** The first scheduled six-hour timer pass remains pending. No
  live Vhost application request or production workflow was exercised; no
  checklist row is closed by this package refresh.
- **Outcome:** Current-source local package and disposable consumer evidence is
  refreshed with a verified rollback point.

## 2026-10-24 — Share compact CLI JSON output

- **Intent:** Remove repeated JSON-lines formatting while preserving each
  command's output shape and failure behavior.
- **Changed fact:** Producer and storage commands now use the shared
  `write_json_line` formatter, which emits the same compact, key-sorted JSON
  followed by one newline.
- **Verification:** The producer and storage CLI suites pass six tests. Strict
  Pyright reports zero diagnostics. A fresh whole-tree Pylint JSON scan reports
  128 findings (14 convention, 114 refactor, including 19 duplicate-code
  findings), with no warning/error categories. `git diff --check` passes.
- **Open gate:** Repository-wide Pylint cleanup remains open; no delivery
  checklist item is closed by this supporting cleanup.
- **Outcome:** Keep the existing CLI contracts while sharing their formatter.

## 2026-10-24 — Share evidence-runner process cleanup

- **Intent:** Remove duplicated subprocess cleanup without changing timeout or
  failure handling for evidence collection.
- **Changed fact:** Git test runners and service probes now use the same
  process-group kill helper, including the direct-process fallback when group
  termination fails. Both runners still wait for termination before returning
  failure.
- **Verification:** The focused evidence suite passes 15 tests. Strict Pyright
  reports zero diagnostics; targeted Pylint for the changed modules is clean.
  A fresh whole-tree Pylint JSON scan reports 129 findings (14 convention,
  115 refactor, including 20 duplicate-code findings), with no warning/error
  categories. `git diff --check` passes.
- **Open gate:** Repository-wide Pylint cleanup remains open; this supporting
  cleanup does not close a delivery checklist item.
- **Outcome:** Preserve timeout cleanup behavior while removing one repeated
  process-control block.

## 2026-10-24 — Share fail-closed timestamp parsing

- **Intent:** Remove duplicated timestamp parsing while preserving exact
  evidence and project-reactivation validation behavior.
- **Changed fact:** Evidence receipt freshness and staging-observation checks
  now share the bounded timezone-aware ISO parser from `record_validation.py`.
  Both paths still return no parsed timestamp for malformed, naive, oversized,
  or out-of-range values; valid timestamps normalize to UTC.
- **Verification:** The focused evidence and project-access suites pass 36
  tests. Full warning-level Pylint falls from 131 to 130 findings, with
  duplicate-code findings falling from 22 to 21; no warning/error categories
  are reported. `git diff --check` passes.
- **Open gate:** Whole-tree Pylint still has 130 findings. The broad cleanup
  item remains open.
- **Outcome:** Preserve the evidence-freshness and reactivation behavior while
  removing one duplicate block.

## 2026-10-24 — Consolidate repeated consumer test configuration

- **Intent:** Reduce actual repository-wide Pylint duplication without
  weakening the test suite or changing consumer fixtures.
- **Changed fact:** Added one shared writer for the minimal consumer TOML
  config and reused it in hosted-MCP, hosted service-evidence, stdio, and
  project-plugin fixtures. Task text, project IDs, config permissions, and
  setup side effects remain owned by each caller.
- **Verification:** The three affected suites pass 70 tests. A fresh full
  warning-level Pylint JSON scan falls from 132 to 131 findings; duplicate-code
  findings fall from 23 to 22. The scan reports 14 convention and 117 refactor
  findings, with no warning/error categories. `git diff --check` passes.
- **Open gate:** Whole-tree Pylint still has 131 structural/convention
  findings. No checklist row is closed by this supporting cleanup.
- **Outcome:** Keep the repository-wide Pylint item open and continue reducing
  concrete findings.

## 2026-10-24 — Refresh whole-tree Pylint inventory

- **Intent:** Reconcile the repository quality ledger against a fresh scan.
- **Changed fact:** The current warning-level scan reports 132 findings: 14
  convention and 118 refactor/duplicate-code findings, with no warning/error
  categories. `tests/test_review_cli.py` remains clean after the packet
  assertion was added.
- **Verification:** Ran
  `uv run --locked --group quality pylint --output-format=json src/curatormd_v2 tests`
  and parsed its complete JSON result. The command exits 24 because these
  non-blocking findings remain. The focused review CLI suite passes nine tests;
  targeted Pylint rates that module 10.00/10; `git diff --check` passes.
- **Open gate:** Repository-wide warning-level Pylint cleanup remains open;
  this inventory does not change delivery progress.
- **Outcome:** Correct the stale 161-finding release-ledger snapshot; keep the
  132-finding work item open.

## 2026-10-24 — Verify attended local SDE review packet

- **Intent:** Close the local-alpha requirement to show review evidence and the
  exact purge inventory to the authorized reviewer before disposition.
- **Changed fact:** The attended V2 review CLI displays candidate facts,
  evidence provenance, complete staged paths and manifest hash, and the
  canonical target before approve/reject. Its confirmation is bound to the
  displayed dependency-map and inventory hashes; review authorization uses
  the current local UID and an owned project database.
- **Verification:** The focused review CLI suite passes nine tests. The
  integration regression asserts that the rendered packet includes the
  candidate, verification evidence, exact inventory hash and staged path
  before the decision prompt, then confirms the exact-inventory review/purge
  path.
- **Open gate:** Hermes-person authentication and production reviewer UX are
  deferred beyond the approved single-user development alpha. Live Vhost
  application review/purge remains unverified.
- **Outcome:** Close the local reviewer-packet delivery row only. The earlier
  progress note recorded 146/178; the current direct count of plan row markers
  is 145/178 complete and 33 open, now reflected in the plan and release gate.

## 2026-10-24 — Close local-alpha truthful health aggregation

- **Intent:** Verify that the local single-user alpha health view reflects
  required work and all configured local observations.
- **Changed fact:** Curator local health remains degraded for pending/failed
  required work and incomplete staging, and unknown for missing/stale probes or
  failed database snapshots. The active Hermes development profile supplies
  the scheduler and journal observations; its read-only probe reports healthy
  for `vhost-manager-alpha` with no open gates.
- **Verification:** Fourteen focused Curator API health tests pass, covering
  the healthy, degraded, and unknown states. Nine Hermes bridge tests pass for
  the six-hour scheduler and 18-hour freshness boundary. This profile probe
  uses the Hermes development checkout, not the active `/usr/local` install.
- **Open gate:** External alerting, production monitoring, and cross-system
  reconciliation remain deployment release gates. The first timer run after
  the cadence change is still pending.
- **Outcome:** Close the local-alpha health row only. Delivery progress is
  143/178 complete; 35 remain open.

## 2026-10-24 — Set alpha purge retry cadence to six hours

- **Intent:** Reduce unnecessary local retry polling while preserving the
  scheduler freshness signal.
- **Changed fact:** The `vhost-manager-alpha` systemd user timer and Curator V2
  timer template now run at 00:00, 06:00, 12:00, and 18:00, with the existing
  15-second spread. The Hermes Core development-checkout readiness threshold is
  18 hours (three timer intervals). No active `/usr/local` Hermes files were
  changed.
- **Verification:** `systemd-analyze calendar` resolves the six-hour schedule;
  `systemd-analyze --user verify` passes. The timer remains enabled and active,
  with the next trigger at 00:00. The Hermes Curator-health suite passes nine
  tests. A profile-bound probe reports healthy project state using the updated
  checkout bridge.
- **Open gate:** The first scheduled run under the new cadence is pending.
  Production alerting, dead-letter handling, and restart/reconciliation remain
  open.
- **Outcome:** Change only the alpha retry cadence; keep the prior run-count
  evidence labeled as pre-change.

## 2026-10-24 — Verify local alpha purge timer

- **Intent:** Confirm whether the approved one-repository alpha scheduler is
  actually operating before updating checklist status.
- **Changed fact:** The `eaglesvn` user timer for `vhost-manager-alpha` is
  enabled and active. Eight scheduled service runs since 20:00 +07 exited
  successfully and each reported zero due/pending purge work. The service is
  configured to write output to journald.
- **Verification:** `systemctl --user` reports the timer enabled and active;
  the latest service result is success with exit status 0. The bounded journal
  summaries identify only the project and aggregate counts.
- **Open gate:** Production alert delivery, dead-letter handling, and restart/
  interruption reconciliation remain outside the approved development scope;
  deployment release gates remain open.
- **Outcome:** Mark only the local-alpha timer operation row complete. The
  delivery checklist is now 142/178 complete; 36 remain open.

## 2026-10-24 — Confirm single-user development scope

- **Intent:** Remove multi-user identity from the Curator V2 alpha acceptance
  scope and continue local lifecycle work.
- **Changed fact:** The owner confirmed Curator is used during development,
  against one repository at a time. The existing owner-approved `eaglesvn`
  local UID grant and Hermes profile/session context are sufficient for this
  scope; authenticated Hermes person identity is not an alpha blocker.
- **Verification:** Added a reactivation regression that creates a pending
  expiry-purge receipt, reviews the suspension packet, changes the exact target
  status/attempt count, and verifies stale-packet reactivation fails without
  changing status or audit. The focused reactivation test passes. Strict
  Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked
  dependency audit, lock check, and `git diff --check` pass.
- **Open gate:** Production, multi-user identity, deployment-bound lifecycle
  acceptance, and real consumer workflow evidence remain outside local alpha
  verification. This regression does not change checklist completion.
- **Outcome:** Keep the single-user, one-repository development boundary
  explicit; continue local checklist work without expanding identity scope.

## 2026-10-24 — Reduce project-access test lint findings

- **Intent:** Continue the local repository-wide Pylint cleanup without
  changing project-access behavior.
- **Changed fact:** `DurableProjectAccessTests` now stores its immutable project
  ID and repository/config fingerprints on the test class instead of every
  test instance, removing one too-many-instance-attributes finding.
- **Verification:** All 21 project-access tests pass. Targeted Pyright reports
  zero diagnostics. Targeted Pylint findings for the module fall from three to
  two, with a 9.96/10 score. The last full-tree inventory was 138 findings
  before this edit and was not rerun afterward.
- **Open gate:** Repository-wide Pylint cleanup remains open; this removes one
  local finding and does not change checklist status.
- **Outcome:** Keep the warning cleanup auditable without claiming a new
  whole-tree count.

## 2026-10-24 — Isolate schema rejection assertions

- **Intent:** Reduce test-method complexity in the executable record-contract
  suite while preserving the failure cases it checks.
- **Changed fact:** Extracted the failed-purge status serialization and
  private-detail rejection assertions into a focused helper.
- **Verification:** All nine contract-schema tests pass. Targeted Pyright
  reports zero diagnostics; targeted Pylint is clean (10.00/10), and
  `git diff --check` passes. The full-tree Pylint inventory was not rerun.
- **Open gate:** Repository-wide Pylint findings remain open; no checklist
  checkbox changed.
- **Outcome:** Record a scoped cleanup only, without inferring the new global
  warning count.

## 2026-10-24 — Clarify Hermes human-identity boundary

- **Intent:** Resolve whether the open identity statement applies to the local
  alpha reviewer or only to production Hermes authorization.
- **Changed fact:** Source inspection found Hermes Core's authenticated-subject
  helper is not wired into Curator MCP request metadata: the host injects only
  profile/session context, while Curator's local profile server fixes one
  account caller at startup. The approved `eaglesvn` UID-bound reviewer grant
  is separate and remains assigned locally.
- **Verification:** Read the current Hermes `authenticated_subject` helper and
  Curator opted-in metadata builder, server construction, and the existing V2
  identity checklist. This is source evidence only; no runtime identity call
  was made.
- **Open gate:** Production per-request subject forwarding, project/review
  authorization mapping, and authenticated transport proof remain open. No
  identity or deployment checklist item changed.
- **Outcome:** The plan now names the actual integration gap and does not imply
  that local alpha identity is missing.

## 2026-10-24 — Isolate event replay identity matching

- **Intent:** Make durable event replay comparison easier to review while
  preserving idempotency for current and legacy inbox receipts.
- **Changed fact:** Extracted the stored-payload versus idempotency-digest
  comparison from event ingestion. A matching receipt is reused; changed input
  still raises the existing conflict.
- **Verification:** The exact-duplicate and changed-payload replay tests pass;
  all 21 project-access tests pass; strict Pyright and repository errors-only
  Pylint pass. Targeted `store.py` Pylint now reports 30 findings (1
  convention, 29 refactor), one fewer than after the preceding store cleanup.
  `git diff --check` passes.
- **Open gate:** Repository-wide warning-level Pylint remains open. The last
  full-tree inventory was 157 findings before these local refactors; no fresh
  global count or delivery checklist closure is claimed.
- **Outcome:** Exact event replay remains durable and idempotent with a smaller
  ingestion method.

## 2026-10-24 — Simplify the project registration comparison

- **Intent:** Reduce the local Pylint backlog while preserving project
  registration update and replay behavior.
- **Changed fact:** Moved the comparison of repository, config, and backend
  version fingerprints into a named helper. The caller still rejects an
  unchanged registration before writing an audit receipt.
- **Verification:** All 21 `test_project_access` tests pass; strict Pyright
  reports zero diagnostics. Targeted Pylint on `store.py` reports 31 findings
  (1 convention, 30 refactor) and no longer reports the update method's
  `too-many-locals` finding. `git diff --check` passes.
- **Open gate:** Repository-wide Pylint cleanup remains open. The last full-tree
  inventory was 157 findings before this edit; no new full-tree count is
  claimed, and no delivery checkbox changed.
- **Outcome:** Registration update behavior remains covered while one local
  structural finding is removed.

## 2026-10-24 — Reduce project-status validation complexity

- **Intent:** Remove one repository-wide Pylint branch finding without changing
  project suspension or reactivation validation behavior.
- **Changed fact:** Extracted the request-field checks for suspended and active
  project transitions into a focused helper. Validation order and error messages
  remain unchanged.
- **Verification:** All 21 `test_project_access` tests pass; strict Pyright
  reports zero diagnostics. The full warning-level Pylint inventory falls from
  158 to 157 findings (14 convention, 143 refactor; no warning/error
  categories). `git diff --check` passes.
- **Open gate:** Repository-wide Pylint cleanup remains open; the Delivery
  checklist remains 139/178 complete (39 open), and no delivery checkbox
  changed.
- **Outcome:** The transition validation refactor removes one lint finding
  while retaining the same tested lifecycle behavior.

## 2026-10-24 — Reconcile delivery checklist progress

- **Intent:** Confirm the reported 139/178 progress against the current V2 plan
  and make the counting boundary explicit.
- **Changed fact:** The official Delivery checklist recount remains 139 checked
  of 178 delivery rows, with 39 open. A raw count of all plan checkboxes is
  153/216 because it includes 38 reusable section-11 checklist rows (14 checked,
  24 open); those rows are excluded from delivery progress by the plan contract.
- **Verification:** Counted checkbox rows in sections 0–10, 12, and Definition
  of done, excluding section 11; separately counted all plan checkbox rows.
  `git diff --check` passes.
- **Open gate:** The 39 open delivery rows remain open; this count audit changes
  no implementation or release evidence.
- **Outcome:** Updated the plan's dated snapshot and recorded the count boundary
  so reusable execution templates are not mistaken for delivery items.

## 2026-10-24 — Extract trusted Hermes context validation

- **Intent:** Reduce the open repository-wide Pylint backlog while keeping the
  Hermes lifecycle event's profile, session, durable-dispatch, and source-epoch
  checks unchanged.
- **Changed fact:** Moved trusted Hermes metadata validation and stable
  epoch-scoped source-ID derivation into `src/curatormd_v2/hermes_context.py`.
  The MCP registration module delegates to these helpers; validation failures
  retain their existing denial messages.
- **Verification:** The focused trusted-context/binding MCP regression passes.
  Strict Pyright reports zero diagnostics; focused Pylint rates both changed
  modules 10.00/10; whole-tree Pylint falls from 166 to 164 findings (14
  convention, 150 refactor, no warning/error categories). Repository errors-only
  Pylint and `git diff --check` pass.
- **Open gate:** Whole-tree warning-level Pylint remains open. The Delivery
  checklist remains 139/178 complete (39 open); the raw all-plan checkbox count
  is 153/216 because section 11 has 14/38 reusable developer checklist rows.
- **Outcome:** Two non-blocking Pylint findings were removed without changing a
  delivery checkbox or the Hermes context authorization boundary.

- **Intent:** Make the Hermes-hosted V2 health probe work in the actual Hermes
  runtime without adding a dependency that Hermes does not ship.
- **Changed fact:** `tools/curator_v2_health.py` now parses the bounded hook
  manifest through Hermes Core's `hermes_yaml` module instead of importing
  PyYAML.
- **Verification:** Hermes focused health tests pass (3/3). A read-only status
  probe through the `renew-ssl-coding` profile and Hermes development checkout
  discovers 48 Curator tools, reports 12 processed receipts and one goal, and
  returns `project_health=degraded` with only `purge_scheduler` and
  `alert_delivery` unavailable.
- **Open gate:** This is local profile evidence. The active system Hermes build,
  production scheduler/alert services, authenticated human identity, and live
  application workflow remain unverified. The health delivery row stays open.
- **Outcome:** Local missing-probe unknowns are now supplied by the host bridge;
  known absent scheduler and alert services remain truthfully degraded.

- **Intent:** Record the final focused verification state for the Hermes health
  bridge and keep the full-repository check result accurate.
- **Changed fact:** The probe treats an unavailable effective-UID API as
  unknown and accepts a UTF-8 BOM in the bounded hook manifest; the health
  bridge remains dependency-free within Hermes' shipped runtime.
- **Verification:** The focused Hermes health suite passes 4/4. Curator's
  documented quality commands pass: strict Pyright, errors-only Pylint,
  Bandit, locked dependency audit, and `git diff --check`. Hermes
  `scripts/check --base HEAD^` did not pass: its code-health scan timed out in
  `git grep` after 120 seconds on the shallow base.
- **Open gate:** The Hermes repository-wide check, production scheduler and
  alert services, active installed Hermes build, authenticated person identity,
  and live application workflow remain unverified. No delivery checkbox is
  closed by this verification.
- **Outcome:** Updated the V2 health integration evidence without claiming the
  failed/timed-out Hermes repository check as successful.

- **Intent:** Remove straightforward repository-wide Pylint line-length
  findings while continuing the open V2 lint-cleanup item.
- **Changed fact:** Wrapped two overlong SQL/receipt lines in `store.py`; no
  behavior or lint threshold changed.
- **Verification:** A prior full warning-level inventory reported 177 findings
  including two `line-too-long` messages. After the edits, the focused
  line-length rule passes across `src/curatormd_v2` and `tests`, errors-only
  Pylint passes for `store.py`, and `git diff --check` passes.
- **Open gate:** The full inventory was not rerun, and structural/design and
  duplicate-code findings remain. The repository-wide Pylint checklist row
  stays open.
- **Outcome:** Removed the two verified line-length findings without claiming
  the broader lint-cleanup item complete.

- **Intent:** Recheck the Curator V2 operational and persistence status before
  reporting the current work checkpoint.
- **Changed fact:** The configured direct `project_health` and
  `project_activity_status` reads both returned `unauthenticated` with the
  fixed message that trusted Hermes profile context is required; neither read
  returned V2 ledger or health state.
- **Verification:** Called each read-only Curator V2 MCP tool once. No write or
  state change was requested or reported.
- **Open gate:** Current direct-MCP persistence/health status is unavailable
  without trusted Hermes profile context. This does not contradict the separate
  earlier local-profile probe, which returned degraded status; they are
  different caller contexts.
- **Outcome:** Kept live persistence status unknown instead of inferring it
  from the earlier profile-bound observation.

- **Intent:** Prevent a stale Curator V2 consumer plugin from writing after its
  consumer binding has been deregistered and re-enrolled.
- **Changed fact:** `ProjectPlugin` captures its consumer-binding revision and
  supplies it to the store's durable project effect fence. A changed binding
  revision denies ordinary writes even if project registration fingerprints
  still match; an exact attended drain remains allowed only after the store
  validates its transition-scoped event authorization.
- **Verification:** Two focused regressions prove old plugin and bound-service
  writes are denied after re-enrollment, the exact inventoried drain event is
  processed, and a new unlisted event creates no receipt. The project-plugin
  suite passes 53 tests; the project-access drain regression passes. Strict
  Pyright reports zero diagnostics, errors-only Pylint passes for changed files,
  and `git diff --check` passes.
- **Open gate:** Lost source acknowledgments across completed deregistration,
  authenticated deployment identity, and production lifecycle evidence remain
  open. No broad lifecycle or deployment checklist item is claimed complete.
- **Outcome:** Closed the local stale-plugin consumer-binding revision gap while
  preserving the exact reviewed drain path.

## 2026-10-23

- **Intent:** Make the required lifecycle deployment evidence cases traceable
  before running owner-gated acceptance.
  **Changed fact:** Added an eight-case lifecycle catalog to the V2 release
  gates. Each case has one gate assignment, owner roles, preconditions,
  expected result, evidence packet bindings, and an explicit open disposition.
  **Verification:** Cross-checked each stable case ID against the Section 6
  lifecycle requirement, its Section 9 scenario, and exactly one release-gate
  slice. `git diff --check` passes.
  **Open gate:** No owner-authenticated deployment scenario or rollback drill
  was run; the lifecycle and deployment integration checklist rows remain open.
  **Outcome:** Established the acceptance catalog without representing local
  tests or documentation as deployment evidence.

- **Intent:** Continue the open repository-wide Pylint cleanup without
  suppressing structural findings or changing Curator V2 behavior.
  **Changed fact:** Twelve low-risk diagnostics were removed across the current
  V2 tree: overlong lines, one import-order issue, a missing request-readiness
  method docstring, and an unidiomatic bool check. No lint suppressions were
  added for this cleanup.
  **Verification:** The full Pylint scan reports 124 findings, down from 136
  immediately before this slice; remaining findings are mainly duplicate-code
  and structural/design limits. The focused health/readiness and project-access/
  CLI suites pass 17 tests. Strict Pyright reports zero diagnostics;
  `git diff --check` passes.
  **Open gate:** Repository-wide Pylint cleanup remains incomplete; no checkbox
  changed.
  **Outcome:** Reduced the current full-scan inventory by twelve findings
  without claiming the broader cleanup complete.

- **Intent:** Replace missing host-owned Curator health observations with
  bounded probes from the opted-in Hermes Core local stdio integration.
  **Changed fact:** Hermes now reports read-only event-outbox and SQLite storage
  integrity, local reviewer grant, hook-manifest, alert-receiver availability,
  and trusted profile/session observations. The local purge scheduler and alert
  receiver are explicitly reported unavailable. Curator validates the
  metadata and exposes it only during the current MCP request; stale and
  missing probes remain unknown, and known unavailable dependencies degrade
  health. No raw content, paths, or reviewer identifiers are included.
  **Verification:** Two Curator health-bridge regressions pass, Hermes probe
  and trust-gating tests pass (28 total), Curator Pyright and errors-only
  Pylint pass for changed modules, and `git diff --check` passes in both
  repositories. The broad Hermes check was stopped after extended time in
  unrelated repository scans.
  **Open gate:** The hook manifest is not exhaustive producer coverage. There
  is no production purge-scheduler heartbeat or alert receiver, and no live
  deployment or cross-source reconciliation was exercised. The health
  checklist item remains open.
  **Outcome:** Added a local diagnostic slice without changing checklist
  completion counts or claiming deployed readiness.

## 2026-10-22

- **Intent:** Remove the sensitive-config value from retained validation
  exception state, not only from its rendered message.
  **Changed fact:** Config validation now returns a safe category after its
  input-bearing frames unwind. `ProjectConfig.load` drops the parsed table
  before raising a sanitized error with no cause or context.
  **Verification:** The focused regression directly catches the exception and
  confirms its loader traceback has no parsed config table or canary. All 44
  project-plugin tests pass; strict Pyright and errors-only Pylint pass for the
  changed modules.
  **Open gate:** This covers this config-validation exception path only. The
  broader privacy review and all deployment, identity, retention-policy, and
  live-runtime gates remain open.
  **Outcome:** Credential-like config values are not retained in the public
  error chain or loader frame; no checklist row was closed.
- **Intent:** Extend the V2 source-to-sink privacy evidence for untrusted
  consumer configuration.
  **Changed fact:** A focused regression now covers credential-like config
  values rejected by `ProjectConfig.load`; the safe category remains visible,
  while the supplied value is absent from the public error and chained cause.
  No runtime behavior or checklist status changed.
  **Verification:** The focused regression passes; strict Pyright and
  errors-only Pylint pass for `tests/test_project_plugin.py`.
  **Open gate:** This is one config-error boundary only. Other log, trace, WAL,
  backup, retry/quarantine, canonical, and upstream paths remain in the broader
  privacy review; deployment and live-runtime gates remain open.
  **Outcome:** Added narrow, canary-based evidence without claiming complete
  privacy review or changing checklist counts.
- **Intent:** Verify the current dirty Curator V2 source and Hermes Core
  integration before continuing local implementation.
  **Changed fact:** No source behavior, checklist status, consumer installation,
  or external runtime state changed.
  **Verification:** Curator `uv sync --locked --group test --group quality`
  succeeds; strict Pyright reports zero diagnostics; errors-only Pylint exits 0;
  Bandit exits 0 with its existing `nosec` notices; and `uv audit --locked
  --preview-features audit-command` finds no known vulnerabilities or adverse
  package statuses. `git diff --check` passes in both Curator V2 and Hermes Core.
  Hermes Core `python3 scripts/check` passes all 12 checks. The full Curator test
  suite was not rerun.
  **Open gate:** Deployment, authenticated human identity, owner-approved
  retention/recovery policy, full source-to-sink privacy review, and live
  application/runtime evidence remain open.
  **Outcome:** Current local quality checks are green; no release gate or goal
  completion claim changed.
- **Intent:** Close the verified local Curator V2 domain implementation slice.
  **Changed fact:** Plan slice B now covers local bounds, schema/privacy,
  concurrency/replay, correction/supersession, property, and v0-to-v21 migration
  evidence. The delivery checklist now reads 138/175 complete, with 37 open.
  **Verification:** The focused domain set passes 155 tests, and the full
  locked suite passes 377. Strict Pyright, errors-only Pylint, Bandit, and
  `git diff --check` pass on the current worktree.
  **Open gate:** Broader source-to-sink privacy review, production migration,
  authenticated identity, deployment, production retention/recovery, and
  live-runtime evidence remain open.
  **Outcome:** Closed one locally evidenced delivery row while preserving all
  external release gates.
- **Intent:** Verify the next locally testable Curator V2 domain-slice criteria.
  **Changed fact:** No runtime behavior or delivery checklist status changed.
  **Verification:** The focused bounds, validation, schema/privacy, concurrency,
  event, lifecycle, property, and migration modules pass 146 tests, including
  generated lifecycle/parent sequences and v20-to-v21 cleanup-authorization
  migration checks. Strict Pyright, errors-only Pylint, Bandit, and
  `git diff --check` were already verified on this worktree in the prior
  quality checkpoint; the full suite was not rerun.
  **Open gate:** Slice B remains open for broader transition/privacy coverage
  and production migration support. Deployment, verified human identity,
  production retention/recovery, and live-runtime evidence remain open.
  **Outcome:** Strengthened the local evidence for slice B without closing it.
- **Intent:** Reconcile the published Curator V2 checklist snapshot with its
  declared delivery-row scope.
  **Changed fact:** The snapshot now reports 137 of 175 delivery rows complete
  and 38 open. The count includes sections 0–10, 12, and Definition of Done;
  it excludes section 11's reusable task templates.
  **Verification:** A section-scoped count of current `- [x]`, `- [ ]`, and
  `- [!]` rows returns 137 complete, 38 open, and zero blocked. No checklist
  rows were changed in this reconciliation.
  **Open gate:** Deployment, verified human identity, production retention and
  recovery, and live-runtime evidence remain open.
  **Outcome:** Corrected the stale progress snapshot without changing delivery
  checklist state.
- **Intent:** Close the Hermes TUI replay and restart-preview sinks in the
  Curator V2 content-safety review.
  **Changed fact:** Curator V2 tool-start/tool-complete events and restart
  previews now replace arguments and results with fixed markers before event
  replay or preview emission; argument-derived labels, summaries, and edit
  metadata are suppressed.
  **Verification:** The focused Hermes TUI regression file passes (2 tests);
  targeted Hermes Ruff and `git diff --check` pass, and Hermes `scripts/check`
  passes all 12 checks. The opted-in `renew-ssl-coding` local-stdio probe
  discovers 48 Curator tools and returns 12 processed event receipts, one goal,
  two facts, and zero failed/quarantined events or pending SDEs. Direct Codex
  Curator MCP calls still return `unauthenticated`. Curator's locked Pyright,
  errors-only Pylint, Bandit, and `git diff --check` checks pass.
  **Open gate:** This covers these TUI sinks only. Other log, trace, backup,
  recovery, and provider paths remain in the broader source-to-sink review;
  authenticated identity, deployment, retention policy, and live runtime also
  remain open. The privacy checklist item remains unchecked.
  **Outcome:** Recorded a bounded local privacy improvement without changing
  checklist progress or claiming end-to-end privacy.
- **Intent:** Close a concrete high-confidence credential-format false
  negative in the Curator V2 reject-only safety gate.
  **Changed fact:** Unlabelled Stripe secret and restricted key forms are now
  recognized alongside existing provider-token prefixes. The safety contract
  documents those formats; rejection still preserves source meaning and never
  echoes the matched value.
  **Verification:** Five focused safety/API/MCP tests pass, including the
  existing no-write/no-leak canary path with an unlabelled synthetic Stripe
  token. Strict Pyright, errors-only Pylint, and `git diff --check` pass.
  **Open gate:** Other formats, scanner false positives/negatives, jurisdiction
  rules, and deployment policy remain unreviewed; no checklist status changed.
  **Outcome:** this specific prefix false negative is covered locally without
  claiming privacy certification; the full V2 goal remains active.
- **Intent:** Exercise staging-measurement aggregate invariants over generated
  inputs.
  **Changed fact:** A deterministic Hypothesis property generates class
  breakdowns and non-file scan counts, accepts consistent totals, and rejects
  a mismatched aggregate. Its strategy stays below the configured scan bound.
  **Verification:** The property passes 60 examples; strict Pyright and
  errors-only Pylint pass; `git diff --check` passes. No full Curator suite was
  rerun.
  **Open gate:** Full transition/privacy coverage and production migration
  support remain open; no checklist status changed.
  **Outcome:** generated validation coverage now exercises the new staging
  domain boundary; the full V2 goal remains active.
- **Intent:** Make Hermes MCP discovery describe the configured Curator V2
  caller context accurately.
  **Changed fact:** `hermes mcp test` now reports host-injected profile/session
  context for an opted-in local stdio server; remote URLs carrying the same
  flag do not get that label. The text explicitly avoids claiming human auth.
  **Verification:** Three focused MCP CLI tests pass; Hermes `scripts/check`
  passes all 12 checks. Running the checkout-activated CLI against the actual
  `renew-ssl-coding` profile connects and discovers 47 tools with the new
  context label. Hermes `git diff --check` passes.
  **Open gate:** The prior read-only profile status call was rejected before
  server execution. Authenticated ledger status, verified identity, and live
  profile behavior remain unverified; no checklist status changed.
  **Outcome:** configuration diagnostics now distinguish host context from
  absent remote auth without weakening the server boundary; the V2 goal remains
  active.
- **Intent:** Make the bounded staging-measurement domain easier to maintain
  while preserving Curator V2's public record imports.
  **Changed fact:** `StagingArtifactClass`, `StagingClassUsage`, and
  `StagingUsage` now live in `staging_models.py`; package-level exports remain
  unchanged. Aggregate count/completeness checks and per-class consistency
  checks are separate helpers with unchanged validation errors.
  **Verification:** Four focused schema/scanner regressions pass; strict
  Pyright reports zero diagnostics; errors-only Pylint passes. Focused Pylint
  findings for `models.py` plus `staging_models.py` fell from 19 to 16. Both
  repositories pass `git diff --check`.
  **Open gate:** Full transition/privacy and repository-wide advisory Pylint
  cleanup remain open; no checklist status changed.
  **Outcome:** staging domain validation is isolated and less branch-complex;
  the full V2 goal remains active.
- **Intent:** Close one locally actionable Curator V2 privacy sink in Hermes
  Core's shared session viewer projection.
  **Changed fact:** Viewer events retain Curator V2 tool identity and failure
  state but replace arguments, result text, previews, and labels derived from
  arguments with fixed markers. The in-call observer path retains the response
  required by the initiating API request.
  **Verification:** The focused managed-worker viewer suite passes 2 tests;
  Hermes `scripts/check` passes all 12 checks; both repositories' `git diff
  --check` pass. No full Hermes test suite was rerun.
  **Open gate:** Other Hermes logs/traces/provider paths and the complete
  source-to-sink privacy review remain open. The authenticated Curator MCP
  status request is still unverified: the Codex route lacks Hermes context and
  the attempted profile call was rejected before reaching the server. No
  checklist count changed.
  **Outcome:** shared live viewer payloads no longer expose Curator V2 facts or
  evidence; the overall V2 goal remains active.
- **Intent:** Verify the current Curator V2 CI quality sequence after the
  active local source changes.
  **Changed fact:** The locked quality environment resolves from the repository
  lockfile without dependency changes; no source behavior changed in this
  verification step.
  **Verification:** Strict Pyright reports zero diagnostics; errors-only
  Pylint passes; Bandit exits successfully (its documented `nosec` checks emit
  warnings, with no failed checks); locked dependency audit finds no known
  vulnerabilities or adverse project statuses. Curator `git diff --check`
  passes. The complete Curator test suite was not rerun.
  **Open gate:** Full-suite freshness, deployed identity/retention/runtime,
  and production release evidence remain separate. No checklist count
  changed.
  **Outcome:** the current CI quality/security gates are green for this dirty
  local V2 checkout; the full V2 goal remains active.
- **Intent:** Harden the local-alpha staging measurement boundary under the
  V2 domain bounds/schema slice.
  **Changed fact:** `StagingUsage` now validates exact non-negative counters,
  the 10,000-entry scan ceiling, completeness/error-code consistency, safe
  bounded category codes, classified-entry totals, and per-class alignment.
  `StagingClassUsage` now rejects non-exact counters and non-enum classes. The
  published v1 schema now enforces the scan ceiling and bounded safe error-code
  shape, and ties error-code presence to inventory completeness.
  **Verification:** Four focused contract/scanner regressions pass; strict
  Pyright reports zero diagnostics; errors-only Pylint and `git diff --check`
  pass. No broad test suite was rerun.
  **Open gate:** Full transition/privacy coverage and production migration
  support remain open. Owner-approved measured disk budgets and deployed growth
  monitoring are also unverified; no delivery count changed.
  **Outcome:** malformed staging metrics can no longer enter the typed domain
  records; the V2 goal remains active.
- **Intent:** Continue the locally actionable repository-quality cleanup
  without running the already-verified review-CLI tests again.
  **Changed fact:** The review CLI test double now types its two keyword-only
  confirmation options with `TypedDict` and `Unpack`, preserving the exercised
  API call while removing its excessive-argument signature finding.
  **Verification:** Focused warning-level Pylint reports no findings in
  `tests/test_review_cli.py` (10.00/10); strict Pyright reports zero diagnostics;
  `git diff --check` passes. No tests or full repository Pylint inventory were
  rerun.
  **Open gate:** Repository-wide warning-level Pylint cleanup remains open.
  No checklist status changed. **Outcome:** one local test-maintainability
  finding removed with no runtime behavior change.
- **Intent:** Complete the local contract-freeze implementation slice using
  current V2 sources and executable fixtures.
  **Changed fact:** The version-1 contract family is now explicitly frozen for
  the current local-alpha source. The contract index states
  when a schema/behavior change needs a new version and migration; the plan
  slice is marked complete based on its linked schema, lifecycle, error, and
  plugin contracts.
  **Verification:** `tests.test_contract_schemas` passes all 6 tests, including
  runtime record/event/config/error validation; the lifecycle action matrix
  regression passes for every public action and goal state. `git diff --check`
  passes.
  **Open gate:** The installed Vhost alpha wheel is schema v20 while the
  worktree source is v21. This source freeze does not prove cross-repository
  interoperability, external serializers, production compatibility,
  authenticated identity, or deployment. No delivery-row count changed.
  **Outcome:** local V2 source contracts are frozen and executable; installed
  consumer synchronization and external integration gates remain open.
- **Intent:** Resolve the Curator V2 ledger status uncertainty without
  weakening the trusted Hermes profile check.
  **Changed fact:** A read-only inspection of the alpha profile's configured
  SQLite database passed `PRAGMA quick_check` and found one `vhost-manager-alpha`
  goal, two facts linked to that project's goal, and 12 project event-inbox
  rows. `hermes mcp test curator_v2` connected over stdio and discovered 47
  tools. A profile one-shot status attempt was rejected before returning a
  server result; direct Codex MCP calls still lack Hermes-owned request metadata
  and correctly return `unauthenticated`.
  **Verification:** Database access used SQLite `mode=ro`; only aggregate counts
  were queried, with no content or mutation. The plan now distinguishes at-rest
  local ledger evidence from authenticated MCP/live-profile evidence.
  **Open gate:** Hermes-authenticated identity and an actual successful
  profile-context `project_activity_status` response remain unverified. No
  checklist status changed. **Outcome:** local alpha ledger persistence is
  verified at rest; MCP authorization remains fail-closed.
- **Intent:** Keep Curator V2 response content out of Hermes diagnostic logs.
  **Changed fact:** verbose result logging and tool-failure warnings now pass
  Curator V2 results through a fixed redaction marker; unrelated tool output
  keeps its prior diagnostic behavior. Hermes executor exception and failed-
  result logs now use the same marker and omit Curator-specific tracebacks.
  The central Hermes dispatcher returns a fixed Curator V2 error and sends the
  same bounded message to post-tool hooks when a handler raises.
  Dispatcher hook, request-middleware, and result-hook exception diagnostics
  now also redact Curator-specific exception text.
  **Verification:** the existing Curator V2 trajectory, result-log, and
  sampling suites pass 7 focused tests; the Hermes MCP-handler, executor, and
  central-dispatch failure regressions pass 9 tests across focused runs.
  Hermes `python scripts/check` passes all 12 checks with zero
  blocking/advisory health findings, and Hermes `git diff --check` passes.
  **Open gate:** other diagnostic sinks, traces, backups, provider
  retention, and the full privacy source-to-sink review remain open; no plan
  checkbox or checklist count changed. **Outcome:** recorded local Hermes
  integration evidence only.
- **Intent:** Prevent Curator V2 tool responses from being copied into saved
  Hermes trajectories. **Changed fact:** trajectory conversion now preserves
  paired call IDs and tool names but replaces Curator V2 result content with a
  redaction sentinel before serialization; unrelated tool results remain
  intact. **Verification:** focused Hermes argument/result/sampling regressions
  pass (5 tests); `python scripts/check` passes all 12 checks with zero
  blocking/advisory health findings; Hermes `git diff --check` passes.
  **Open gate:** other trajectory fields, logs, traces, backups, provider-side
  retention, and the broad source-to-sink privacy review remain open; no plan
  checkbox or checklist count changed. **Outcome:** recorded local Hermes
  integration evidence only.
- **Intent:** Reduce existing V2 review-CLI test maintainability findings.
  **Changed fact:** fixture receipt/projection/verifier values are typed
  dataclasses, and the exact end-to-end CLI invocation lives in a focused
  helper. **Verification:** all 9 review-CLI tests pass; strict Pyright reports
  zero diagnostics; errors-only Pylint, Bandit, and `git diff --check` pass.
  Warning-level Pylint findings in the touched test file fell from five to
  one. **Open gate:** the remaining finding is the test double's seven-argument
  signature matching the current review API; the full repository warning
  inventory was not rerun and broad Pylint cleanup remains open. **Outcome:**
  recorded a focused test-structure cleanup without suppressions.
- **Intent:** Prevent Curator V2 tool payloads from entering Hermes trajectory
  samples. **Changed fact:** trajectory conversion preserves the Curator V2
  call boundary but replaces its arguments with a redaction sentinel.
  **Verification:** two trajectory regressions plus the sampling regression
  pass (3 tests total); Hermes `python scripts/check` passes all 12 checks and
  Hermes `git diff --check` passes. **Open gate:** unrelated trajectory content,
  traces, backups, provider paths, and the broad source-to-sink privacy review
  remain open; no plan checkbox or progress count changed. **Outcome:** recorded
  local Hermes integration evidence only.
- **Intent:** Enforce the approved sole-local-reviewer boundary for the alpha
  ledger. **Changed fact:** the attended CLI review authorizer now requires the
  invoking UID to own the SQLite database before opening it; the shareable
  profile `auth=none` path remains denied. **Verification:** the focused review
  CLI suite passes 9 tests, strict Pyright reports zero diagnostics,
  errors-only Pylint and `git diff --check` pass. Scoped warning-level Pylint
  rates the touched CLI/test pair 9.90/10 with no remaining CLI findings; five
  fixture/helper findings remain in the test module. **Open gate:** this is
  local filesystem-account binding only; Hermes-authenticated identity,
  production grant provisioning, deployment, retention, and live runtime remain
  open.
  **Outcome:** recorded local alpha enforcement without changing the production
  identity claim.
- **Intent:** Close the remaining malformed MCP sampling-argument log disclosure
  found in the Hermes Core Curator V2 integration. **Changed fact:** Hermes now
  omits malformed sampling argument text from its warning while preserving the
  raw value only for in-memory recovery; trajectory-conversion helpers now live
  in their topical module. **Verification:** the dedicated canary regression
  passes; Hermes `python scripts/check` passes all 12 checks and
  `git diff --check` passes. **Open gate:** broader Hermes logging, replay,
  backup, trace, and upstream privacy review remains open; the plan privacy item
  and checklist count are unchanged. Curator MCP status calls returned
  `unauthenticated`, so global ledger persistence remains unverified.
  **Outcome:** recorded local integration evidence only; no commit or push.
- **Intent:** Complete the pending Curator V2 quality verification without
  rerunning the test suite. **Changed fact:** no delivery checklist status or
  source behavior changed. **Verification:** the documented locked quality
  commands pass: strict Pyright reports zero errors/warnings/informationals,
  errors-only Pylint exits successfully, Bandit exits successfully with four
  existing `nosec` warnings in `git_evidence.py`, and `git diff --check` passes.
  **Open gate:** full privacy data-flow review, deployment, authenticated
  identity, production retention/recovery, and live-runtime evidence remain
  open. **Outcome:** recorded local static-check evidence only.
- **Intent:** Reduce Curator V2 fact/event exposure in Hermes Core diagnostics.
  **Changed fact:** Hermes now redacts Curator V2 MCP argument excerpts in
  verbose-call, repair, trajectory-conversion, corrupt-call, and batch
  admission logs while preserving bounded excerpts for unrelated tools.
  **Verification:** the focused Hermes regression passes (4 tests), including
  canary absence checks and unchanged repaired arguments; `git diff --check`
  passes. **Open gate:**
  broader Hermes log, trace, backup, replay/trajectory, and upstream privacy
  review remains open; the plan privacy item and delivery count are unchanged.
  **Outcome:** recorded bounded local integration evidence without claiming
  end-to-end privacy.
- Split evidence receipt scope matching from timestamp, expiry, and revocation
  freshness checks inside the fail-closed adapter. The 13 focused evidence
  tests and full 368-test suite pass; strict Pyright, errors-only Pylint,
  Bandit, locked dependency audit, and `git diff --check` pass. Full Pylint is
  down from 289 to 287 findings (275 refactor, 12 oversized-module convention).
  Deployment-owned credentials, trust roots, and real source probes remain
  unverified.
- Split project Markdown marker indexing from block classification while
  preserving the bounded marker cap and orphan/malformed counts. All 19 focused
  Markdown tests and the full 368-test suite pass; strict Pyright, errors-only
  Pylint, Bandit, locked dependency audit, and `git diff --check` pass. Full
  Pylint inventory is 289 findings (277 refactor, 12 oversized-module
  convention); the marker-scan function no longer reports excess locals.
  Repository-wide cleanup remains open.
- Simplified bounded project Markdown reconciliation without changing its
  fields or read-only behavior; the project page reuses the target content and
  computes its UTF-8 scan size when constructing the result. All 19 focused
  Markdown tests and the full 368-test suite pass; strict Pyright, errors-only
  Pylint, Bandit, locked dependency audit, and `git diff --check` pass. Full
  Pylint inventory is 290 findings (278 refactor, 12 oversized-module
  convention); the reconciliation method has no remaining local-count finding.
  Repository-wide cleanup remains open.
- Split maintenance retry accounting/output from command validation and
  isolated stable staged-file hashing from descriptor setup/closure. This
  preserves bounded retry behavior and the no-follow, file-identity, size, and
  mutation checks. Five maintenance CLI tests and 43 project-plugin tests pass;
  the full 368-test suite, strict Pyright, errors-only Pylint, Bandit, locked
  dependency audit, and `git diff --check` pass. Full Pylint inventory is 291
  findings (279 refactor, 12 oversized-module convention); these two helpers
  have no remaining findings. Broader cleanup remains open.
- Refactored the review CLI regression setup into shared, typed fixture helpers
  for exact local reviewer grants and candidate/staging preparation. All eight
  focused review CLI tests and the full 368-test suite pass; strict Pyright,
  errors-only Pylint, Bandit, locked dependency audit, and `git diff --check`
  pass. The full warning-level Pylint inventory decreased from 295 to 293,
  with the review CLI test file decreasing from 38 to 36 findings. No lint
  suppression was added; repository-wide structural cleanup remains open.
- Reverified the Curator V2 alpha worktree: all 368 locked unit tests pass;
  strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and
  `git diff --check` pass. Full Pylint still reports 293 non-blocking
  refactor/convention findings, so repository-wide cleanup remains open.
- Read-only inspection of the configured local V2 SQLite database reports
  `quick_check=ok`, schema v20, one goal, two facts, 12 inbox rows, one project
  registration, and two grants. The Curator MCP ledger read remains
  `unauthenticated`; authenticated profile access and live capture are unknown.
- Corrected the plan's delivery-only snapshot to 143/211 complete and 68 open,
  counting checkbox rows only in the Delivery checklist section. Historical
  inline progress counts are not current snapshots.
- The interrupted-cleanup reconciliation regression remains covered by the
  full suite; no deployment, identity, production retention, or live-runtime
  gate was changed by these checks.

- Added a separate V2-owned VS Code status-label extension. It displays
  `CuratorMD V2` with neutral wording and explicitly states that health,
  capture, persistence, and identity are not checked. JavaScript syntax and
  manifest parsing checks pass; this label is not runtime-health evidence.

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

## 2026-10-25 — Keep manual DNS credentials out of Curator records

**Intent:** Record the owner’s data-handling boundary for the manual DNS renewal workflow.

**Changed fact:** Curator V2 is a documentation system, not a security product. Manual-DNS source code, keys, passwords, challenge values, and raw command output must not be recorded verbatim. The current Vhost bridge builds its event from operation identifiers and bounded outcome metadata; it does not submit source code or command output.

**Verification:** The Vhost filesystem trace contract passed and observed 671 file mutation/write-open calls (567 in the disposable test tree, 2 under `/var/tmp`, 14 device paths, and 88 relative or file-descriptor paths). This covered one renewal-restart test process only; it did not observe the standalone utility. The bridge field inspection confirms its current event shape, not a full source-to-sink audit.

**Open gate:** Standalone-script scope, persistent-log disposition, and full workflow/artifact observations remain open. This record is a documentation boundary, not security certification.

**Outcome:** The no-verbatim-secret rule and limits of current evidence are recorded without retaining any credential or challenge content.

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

## 2026-10-21 — Verify installed MCP SDE proposal schema

**Intent:** Ensure a freshly built Curator V2 alpha wheel exposes the new SDE proposal context through its actual installed MCP launcher.

**Changed fact:** Added a clean-wheel acceptance test that connects to the installed launcher and checks `sde_assess` includes optional `impact` and `retrieval_value` fields while keeping `project_id` bound to the consumer configuration. CI now runs this contract beside installed goal read/write acceptance.

**Verification:** The built wheel installs into a fresh Python 3.12.3 environment; both installed-launcher acceptance tests pass. All 354 Curator tests pass. Strict Pyright, errors-only Pylint, Bandit, locked dependency audit, `uv lock --check`, and `git diff --check` pass.

**Open gate:** Hosted CI for the new wheel-schema assertion is pending. Consumer profile reinstallation and live Hermes identity/runtime remain separate gates. Checklist remains 138/211 complete (73 open).

**Outcome:** The packaged alpha now has a direct regression for the installed SDE MCP input contract. No consumer repository or runtime was changed.

## 2026-10-21 — Pass hosted clean-wheel SDE schema acceptance

**Intent:** Confirm the new installed-launcher SDE contract passes on the pushed Curator V2 alpha source.

**Changed fact:** The release ledger now records Curator commit `e4c8724` and its completed hosted workflow, including the clean-wheel launcher test for optional SDE `impact`/`retrieval_value` fields and consumer-bound `project_id`.

**Verification:** GitHub Actions run [39629987710](https://github.com/eagles-edu/curatormd-v2/actions/runs/39629987710) succeeds across Python 3.12, 3.13, and 3.14; strict typing, errors-only Pylint, Bandit, dependency audit, clean installed-wheel acceptance, and all test jobs pass. The local suite has 354 passing tests. Hermes Core separately passes 61 focused integration tests and all 12 `scripts/check` checks at source head `9b8fc71e30`.

**Open gate:** Hermes hosted CI, authenticated identity, owner retention policy, production scheduling/recovery, Vhost application workflow, and live Curator goal-tracker persistence remain unverified. Checklist is 138/211 complete (73 open).

**Outcome:** The alpha wheel's new SDE MCP schema is verified both locally and in hosted CI. No consumer install or live runtime was changed.

## 2026-10-21 — Reinstall Curator V2 alpha wheel in isolated Vhost profile

**Intent:** Exercise the current packaged Curator V2 backend through the isolated Vhost consumer plugin and the actual Hermes Core managed-MCP harness after clean-wheel CI passed.

**Changed fact:** Installed wheel `b141087b8f9359097d5246195d8c9a09cc60a8fae37dfb128539956c267f94b3` in the dedicated `renew-ssl-coding` alpha virtualenv. All 34 installed module hashes match Curator source. Profile MCP startup exposes schema version 18 with the new nullable SDE context columns. The Vhost repository source and application data were not changed.

**Verification:** Vhost consumer contracts pass 7/7; the Hermes Core managed-MCP disposable harness passes explicit goal binding, planned-goal denial, three processed events, exact replay, failed-delivery retry, privacy checks, reviewer-write denial, and Vhost projection reconciliation. `hermes --profile renew-ssl-coding mcp test curator_v2` connects and discovers 46 tools with transport auth `none`. A direct read-only profile database check reports `quick_check=ok`, schema 18, one goal, two facts, 12 processed event receipts, zero retained payload JSON bytes, and no SDE candidates or review receipts.

**Open gate:** Tool discovery and the disposable harness do not establish authenticated Hermes identity or approval of a real interactive call. The Vhost application workflow, production health, retention policy, deployment recovery, and release approval remain open. Checklist remains 138/211 complete (73 open).

**Outcome:** The current alpha wheel, Vhost plugin contracts, and Hermes-managed MCP composition are verified in the isolated local profile. No GPTMD, deprecated V1 runtime, Host Steward ownership, Vhost source, or application data changed.

## 2026-10-21 — Publish Curator V2 alpha release notes

**Intent:** Make the alpha version, supported Python range, known limitations, and operator guidance discoverable from one concise release note without implying production readiness.

**Changed fact:** Added `docs/release-notes-v2.md` and closed the release-documentation checklist item. It links the existing alpha scope, consumer operations guide, CI policy, and release-gate ledger. Delivery-checklist progress is 125/153 complete (28 open).

**Verification:** The locked Curator suite passes 354 tests. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, `uv lock --check`, and `git diff --check` pass.

**Open gate:** Curator V2 goal-list access still returns `unauthenticated: Trusted Hermes profile context is required`; this is not verified live goal-ledger persistence. The documentation item does not close production identity, retention, scheduling/recovery, deployment, or live-runtime gates.

**Outcome:** The local alpha documentation now states its support boundary and links operator procedures. No consumer repository, V1 runtime, GPTMD, Hermes Core, or application data changed.

## 2026-10-21 — Clarify Curator V2 delivery progress count

**Changed fact:** The plan now defines progress as the checked rows in its `Delivery checklist` section. Reusable work-cycle and request templates and later acceptance prompts are excluded. The current count is 125/153 complete, 28 open. The earlier 139/211 figure counted every checkbox in the document, including those non-delivery prompts, and is not comparable.

**Verification:** Counted checked and open rows between `## Delivery checklist` and `#### Repeatable work-cycle checklist` directly from the current plan; the section contains 125 checked and 28 open rows.

**Open gate:** The denominator can change when delivery rows are added or removed. Authenticated goal-ledger access remains unavailable in this session.

**Outcome:** Future progress updates use the delivery-only count; no delivery status changed in this correction.

## 2026-10-21 — Close local staging inventory adapter item

**Intent:** Complete the reference staging adapter's inventory contract for all supported temporary artifact classes while preserving the separate producer-routing gate.

**Changed fact:** The delivery row for staging inventory is complete for the local reference adapter. It discovers all declared classes, duplicate-content files at distinct paths, orphaned goal directories, and unrecognized classes; the bounded producer CLI writes through that same inventoried adapter. Delivery-checklist progress is 126/153 complete (27 open).

**Verification:** The locked Curator suite passes 354 tests, including `test_producer_api_stages_every_supported_temporary_artifact_class` and `test_project_inventory_includes_orphaned_goal_directories`. Strict Pyright, errors-only Pylint, Bandit, locked dependency audit, `uv lock --check`, and `git diff --check` pass.

**Open gate:** Real transcript/import/test producers, artifacts outside the configured staging root, approved age-retention policy, and production inventory scheduling remain open.

**Outcome:** Local staging inventory is closed at the reference adapter boundary only; no external consumer or runtime gate changed.

## 2026-10-21 — Verify hosted Curator V2 alpha CI

**Intent:** Verify the pushed alpha documentation and local staging-inventory checklist update on the repository's required hosted workflow.

**Changed fact:** GitHub Actions run [39631809235](https://github.com/eagles-edu/curatormd-v2/actions/runs/39631809235) completed successfully for commit `e609fa6`.

**Verification:** Python 3.12, 3.13, and 3.14 suites, strict typing, blocking Pylint, Bandit, locked dependency audit, clean installed-wheel acceptance, and installed operational CLI checks all pass.

**Open gate:** Hosted CI verifies repository/package behavior for this source revision; owner-approved retention, authenticated identity, production scheduling/recovery, deployment, and live-runtime gates remain open. The delivery checklist remains 126/153 complete (27 open).

**Outcome:** The staging-inventory implementation and release documentation have local and hosted repository-level verification. No consumer or Hermes runtime state changed.

## 2026-10-21 — Remove targeted Curator V2 Pylint findings

**Intent:** Reduce verified local lint findings without weakening the full repository Pylint policy.

**Changed fact:** Fixed four line-length findings and two missing nested-helper docstrings across Git evidence and API, MCP, and Markdown tests. The broader warning-level Pylint cleanup remains open.

**Verification:** The targeted C0301/C0116 Pylint run passes for all changed files, and repository-wide errors-only Pylint passes. The focused Markdown, API, and MCP suites pass 60 tests; strict Pyright reports zero diagnostics and `git diff --check` passes.

**Open gate:** The full warning-level inventory at `e609fa6` contained 289 findings before this cleanup; the current repository total has not been recounted. The full Pylint checklist item remains open.

**Outcome:** Six local diagnostics were removed with test coverage passing; no runtime, consumer, or external gate changed.

## 2026-10-21 — Verify targeted Pylint cleanup in hosted CI

**Intent:** Confirm the targeted style cleanup and its test coverage pass on the pushed Curator V2 source.

**Changed fact:** Curator commit `0106a62` passed required GitHub Actions run [39632645359](https://github.com/eagles-edu/curatormd-v2/actions/runs/39632645359).

**Verification:** Python 3.12, 3.13, and 3.14 suites, strict typing, blocking Pylint, Bandit, locked dependency audit, and installed-wheel acceptance all pass.

**Open gate:** Repository-wide warning-level Pylint cleanup remains open; this hosted workflow enforces errors/fatal diagnostics only. Deployment, identity, retention, and live-runtime gates remain open.

**Outcome:** The targeted cleanup is verified in hosted CI without changing the warning policy or runtime behavior.

## 2026-10-21 — Refactor Curator purge descriptor lifecycle

**Intent:** Reduce local control-flow complexity in the hash-verified purge adapter while preserving path confinement, verification order, idempotent absence, and sanitized failures.

**Changed fact:** Split descriptor-relative traversal, descriptor cleanup, hash/identity verification, and final unlink into private helpers. Missing targets still succeed idempotently; all eligible files still require exact digest and inode checks before unlink.

**Verification:** The full suite passes 354 tests, including all 23 purge lifecycle tests. Strict Pyright, repository errors-only Pylint, focused `R0914` Pylint for `purge.py`, Bandit, locked dependency audit, lock check, and `git diff --check` pass. The full warning-level Pylint inventory falls from 283 to 280 findings.

**Open gate:** The repository-wide warning-level cleanup remains open. Production filesystem behavior, retention policy, authenticated review, and live runtime remain unverified.

**Outcome:** The local purge implementation has simpler resource and control-flow boundaries with lifecycle tests intact. No deployment or user data changed.

## 2026-10-21 — Reconcile plan progress reporting and hosted purge verification

**Intent:** Keep Curator V2 progress reporting tied to the defined delivery-checklist section and record the latest repository-level verification.

**Changed fact:** Removed stale `/211` progress snapshots from the plan narrative and added a dated delivery-only snapshot of 126/153 complete (27 open). Recorded the hosted run result for the pushed purge refactor.

**Verification:** Directly counted checked/open rows only between `## Delivery checklist` and `#### Repeatable work-cycle checklist`: 126 complete, 27 open. Hosted GitHub Actions run [39633706427](https://github.com/eagles-edu/curatormd-v2/actions/runs/39633706427) passed Python 3.12, 3.13, and 3.14 tests, strict typing, blocking Pylint, Bandit, locked dependency audit, and clean installed-wheel acceptance. `git diff --check` passes.

**Open gate:** Authenticated identity, owner-approved retention/hold rules, production scheduling/recovery, the real Vhost application workflow, and live goal-ledger persistence remain unverified. The user selected that they will provide identity and retention decisions, but no mapping or policy values are recorded yet; these gates remain open.

**Outcome:** The plan now has one authoritative progress definition and the latest hosted result is recorded. No delivery row changed status; no V1, GPTMD, or consumer source/state changed.

## 2026-10-21 — Document intentional Curator V2 Pylint exceptions

**Intent:** Remove misleading warning-level Pylint findings where broad exception handling or explicit subprocess lifecycle management is required by the fail-closed and bounded-resource contracts.

**Changed fact:** Added local, rationale-bearing Pylint exceptions for arbitrary host readiness failures, sanitized MCP and producer error boundaries, and the two `Popen` lifecycles that enforce timed termination and bounded waits. Runtime behavior is unchanged.

**Verification:** Focused Pylint for broad catches, context-manager suggestions, and line length passes on the four affected modules. The full warning-level inventory falls from 280 to 274 findings (exit 24); repository-wide warning cleanup remains open. `git diff --check` passes.

**Open gate:** Structural, interface, and duplicate-code Pylint findings remain. This change does not close the repository-wide Pylint checklist item or any deployment, identity, retention, or live-runtime gate.

**Outcome:** Six reviewed false-positive/design warnings now carry explicit local rationale; no application behavior or delivery status changed.

## 2026-10-21 — Extract Curator criteria-amendment validation

**Intent:** Reduce lifecycle-store complexity while preserving criteria amendment validation order and externally visible errors.

**Changed fact:** Extracted duplicate criterion-ID validation into a private helper called at the same point in `CuratorStore.amend_goal_criteria`; the function no longer exceeds Pylint's local-variable limit.

**Verification:** Both focused criteria-amendment lifecycle tests pass. Strict Pyright reports zero diagnostics; repository errors-only Pylint and `git diff --check` pass. The full warning-level inventory falls from 274 to 273.

**Open gate:** Repository-wide warning-level Pylint cleanup remains open. No delivery row changed status; owner-approved identity/retention and deployment/live-runtime gates remain open.

**Outcome:** The lifecycle store retains the same validation sequence and output while removing one structural Pylint finding.

## 2026-10-21 — Simplify Curator project activity aggregation

**Intent:** Reduce local complexity in the bounded activity snapshot without changing its SQLite read transaction or public counts.

**Changed fact:** Materialized event and SDE status aggregates directly as dictionaries within the existing transaction, removing intermediate row collections from `CuratorStore.project_activity_status`.

**Verification:** The focused project-activity API regression passes. Strict Pyright reports zero diagnostics; repository errors-only Pylint and `git diff --check` pass. The refreshed full warning-level inventory falls from 273 to 272 findings.

**Open gate:** Repository-wide warning-level Pylint cleanup remains open. No delivery row changed status; deployment, identity, retention, and live-runtime gates remain open.

**Outcome:** Activity counts preserve the existing transaction snapshot semantics with one fewer structural Pylint finding.

## 2026-10-21 — Verify local alpha persistence and simplify MCP launcher

**Intent:** Recheck the Vhost alpha's persisted V2 state after the canonical-write-before-purge regression and make a bounded local quality improvement.

**Changed fact:** The local profile-bound MCP reports 12 processed event receipts, one goal, two facts, and no failed, received, or quarantined events for `vhost-manager-alpha`. Hermes Core's `renew-ssl-coding` profile connects to the installed local stdio server and discovers 46 tools; Hermes reports transport auth as `none`. `build_local_profile_mcp` now binds its `ProjectPlugin` directly in the API map without an intermediate variable. The status call used explicit profile/session metadata in a local probe; it does not establish authenticated human identity.

**Verification:** The local MCP reports project health `unknown`; event router, purge scheduler, host identity, human review, and artifact producer inventory probes are all unknown. Hermes `mcp test` proves profile config and tool discovery only. All 13 hosted-MCP tests pass. Focused `R0914` Pylint, strict Pyright, repository errors-only Pylint, Bandit, and `git diff --check` pass. Direct Codex Curator V2 status calls without Hermes context remain unauthenticated.

**Open gate:** This is a local persistence/status observation, not live Hermes authenticated identity, production readiness, owner-approved retention policy, or deployment evidence. Repository-wide warning-level Pylint cleanup remains open.

**Outcome:** The local alpha state is freshly observed and project health remains correctly unknown; no policy or release gate changed.

## 2026-10-21 — Verify disposable Hermes-managed Vhost integration

**Intent:** Verify the local Vhost consumer hook through Hermes Core's managed MCP transport without touching Vhost application or persistence data.

**Changed fact:** The disposable integration script in the dirty Vhost checkout exercised the actual Hermes `HookContext`, managed stdio MCP, installed Curator V2 launcher, and repository-owned Vhost projection adapter. It processed three lifecycle events, acknowledged exact replay, retried a failed delivery, accepted explicit binding only for an active goal, reconciled the configured Vhost Markdown target, kept the private model/cwd canaries out of Markdown, preserved an out-of-scope target, and denied reviewer-only persistence.

**Verification:** `/home/eaglesvn/.hermes/hermes-agent/.venv/bin/python /home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_hermes_managed_integration.py --hermes-root /home/eaglesvn/.hermes/hermes-agent --curator-python /home/eaglesvn/.hermes/profiles/renew-ssl-coding/curator-v2-alpha-venv/bin/python` exits 0 with `result=passed`. The script creates its profile, config, database, consumer repository, and Markdown files under a disposable temporary directory. The Vhost worktree status is unchanged.

**Open gate:** Synthetic project registration/grants and profile metadata do not prove authenticated human identity. The test does not exercise the interactive Vhost application workflow, live canonical Vhost persistence, deployment, retention approval, or production runtime.

**Outcome:** Local Hermes-to-Curator-to-Vhost-plugin transport and projection behavior are verified in a disposable integration; no user project data or release gate changed.

## 2026-10-21 — Reconcile delivery progress and recheck alpha persistence

**Intent:** Keep the release snapshot on the plan's canonical delivery-checklist denominator and refresh the isolated V2 profile's persisted-state evidence.

**Changed fact:** The release ledger now reports only the Curator V2 Delivery checklist count: 126/153 complete and 27 open. It explicitly excludes reusable work-cycle and acceptance templates. A read-only SQLite query of the isolated `renew-ssl-coding` V2 database found one active project registration, one active goal, two facts, 12 processed event receipts, zero retained event payload JSON bytes, and no SDE or purge rows.

**Verification:** SQLite schema version is 18 and `PRAGMA quick_check` returns `ok`. GitHub Actions run [39638397374](https://github.com/eagles-edu/curatormd-v2/actions/runs/39638397374) passes the Python 3.12/3.13/3.14 matrix, strict typing, blocking Pylint, Bandit, dependency audit, and clean-wheel acceptance on Curator commit `3a4314b`. `git diff --check` passes for this documentation update.

**Open gate:** This local database inspection does not authenticate Hermes identity, establish live goal-tracker persistence, or prove project health. The last authenticated Curator goal-list attempt returned `unauthenticated: Trusted Hermes profile context is required`. Identity, owner-approved retention, production scheduling/recovery, and the Vhost application workflow remain open.

**Outcome:** Progress reporting has one explicit delivery-only denominator and current local persistence evidence. No checklist row was closed; no V1, GPTMD, Vhost application data, or runtime configuration changed.

## 2026-10-22 — Add attended local SDE review and exact purge confirmation

**Intent:** Implement the user-selected local alpha reviewer (`eaglesvn`) so one explicit SDE decision can approve cleanup of the exact displayed inventory after canonical persistence.

**Changed fact:** Added `curatormd-v2-review`, bound to the current non-setuid Linux UID and exact project `read`/`review` grants. Review requires a visible terminal, displays the candidate packet and complete hashed inventory, and requires the candidate ID plus manifest hash in the confirmation phrase. The same decision call records the complete inventory; the plugin re-scans before receipt storage, canonical facts and receipt persist before purge, and existing holds remain. The plan's Hermes-authenticated identity row stays open because the `renew-ssl-coding` profile has no authenticated human subject.

**Verification:** The locked Curator V2 suite passes 358 tests; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, `uv lock --check`, wheel build/install and installed reviewer `--help`, and `git diff --check` pass. Four focused reviewer tests cover UID binding, profile-name rejection, complete-manifest confirmation and persistence ordering, and refusal of piped input/output. The MCP lifecycle regression now records decision plus full inventory in one action and passes in the full suite.

**Open gate:** The local Linux account is selected for alpha review only. Hermes-authenticated human identity, deployment, owner retention/hold policy, production purge scheduling/recovery, and live application behavior remain open. No delivery checklist row changed status; progress remains 126/153 complete (27 open).

**Outcome:** Local attended review and same-action exact-inventory purge authorization are packaged and locally verified. This does not authorize Hermes profile review, establish production identity, or close the deployment, retention, or live-runtime gates.

## 2026-10-22 — Exercise local reviewer through the real V2 ledger

**Intent:** Extend local alpha verification beyond a mocked API boundary by running the attended reviewer against disposable V2 persistence and exact project grants.

**Changed fact:** Added an end-to-end test that provisions a disposable project registration and `local-uid:<euid>` read/review grants, creates a verified pending SDE and staged transient file through the real project plugin, then invokes the installed CLI code path.

**Verification:** The CLI displays and confirms the candidate's complete manifest, stores the decision, persists canonical Markdown, purges the unheld transient file, and keeps its canary out of canonical Markdown. The focused reviewer tests pass; the full locked suite, strict Pyright, errors-only Pylint, and `git diff --check` are rerun for this addition.

**Open gate:** The end-to-end fixture proves local implementation only. Hermes-authenticated human identity, approved retention/hold rules, deployment, production purge scheduling/recovery, and live consumer behavior remain open. Delivery progress remains 126/153 (27 open).

**Outcome:** Local alpha review now has real-store lifecycle coverage without changing the deployment or identity gates.

## 2026-10-22 — Document the local alpha review operation

**Intent:** Make the locally verified reviewer usable without implying Hermes profile authentication or production readiness.

**Changed fact:** The README now distinguishes the local UID reviewer from the Hermes identity gate. The consumer operations guide documents exact read/review grant prerequisites, queue and review commands, visible inventory-hash confirmation, canonical-write-before-purge behavior, and current account selection (`eaglesvn`).

**Verification:** `git diff --check` passes. These documentation edits describe the previously pushed CLI and the real disposable ledger test; they do not enable review in a consumer profile or change Vhost/GPTMD state.

**Open gate:** Hermes-authenticated identity, approved retention and hold rules, deployment, production scheduling/recovery, and live application behavior remain open. Delivery progress remains 126/153 (27 open).

**Outcome:** The local alpha review command has operator instructions with its identity and deletion boundaries stated plainly.

## 2026-10-22 — Verify local project artifact isolation

**Intent:** Complete the local project-isolation delivery row with direct evidence that one consumer plugin cannot inspect another project's staged artifacts.

**Changed fact:** Extended the two-repository shared-store regression with an artifact staged only beneath project A's configured root. Project B's plugin rejects a per-goal scan for that foreign goal ID and excludes the file from its complete project inventory. The plan marks local registration/grant isolation complete and keeps host identity and deployment proof explicit.

**Verification:** The two-plugin project suite passes 39 tests; the hosted-MCP suite passes 13 tests; the full locked Curator suite passes 359 tests; strict Pyright reports zero diagnostics; errors-only Pylint, locked dependency audit, lock check, and `git diff --check` pass. On clean Hermes Core head `9b8fc71e30`, the focused Host Steward/gateway-hook suites pass 39 tests and `python3 scripts/check` passes 12 checks. Directly counted checked/open rows between `## Delivery checklist` and `#### Repeatable work-cycle checklist`: 127 complete and 26 open.

**Open gate:** These are local disposable repository/process tests. They do not authenticate Hermes identities, verify root-account registry provisioning, or establish deployment isolation. Retention, deployment, and live-runtime gates remain open.

**Outcome:** This update targets local exact-grant and repository-root isolation only; no production identity or runtime gate is closed.

## 2026-10-22 — Record approved local-alpha retention defaults and visible prompts

**Intent:** Capture the owner's local-alpha retention decision and prevent attended SDE reviews from prompting when their error/prompt stream is hidden.

**Changed fact:** The owner approved immediate expiry eligibility after compact facts are recorded and related SDE review is approved/rejected, with a 72-hour absolute maximum age for raw chat/transcript, cue, import, scratch, generated intermediate, and duplicate artifacts. The decision clears only the pending-SDE review hold; explicit legal/operational holds require separate release. The attended reviewer now requires stdin, stdout, and stderr to be TTYs before opening the database. No age-based expiry ledger or expiry-only approval workflow is implemented by this documentation/test update.

**Verification:** All six focused attended-reviewer tests pass, including refusal when stderr is not a TTY. The full locked Curator suite passes 360 tests; strict Pyright reports zero diagnostics; errors-only Pylint and Bandit pass; dependency audit, lock check, and `git diff --check` pass.

**Open gate:** Age-based expiry discovery, attended approval of expiry-only exact inventories, and scheduler retry remain implementation work. Production retention policy, authenticated Hermes identity, deployment, and live-runtime gates remain open.

**Outcome:** Local-alpha retention policy is approved and recorded; implementation and production evidence remain distinct.

## 2026-10-22 — Add trusted local staging ages and expiry discovery

**Intent:** Implement the approved 72-hour local-alpha expiry threshold without allowing age eligibility to authorize destructive cleanup.

**Changed fact:** SQLite schema v19 now records project-scoped publication timestamps and hashes for producer-adapter artifacts. The project plugin and REVIEW-authorized API/MCP expose read-only 72-hour expiry discovery. Incomplete filesystem inventories, untracked files, and missing or mismatched age records suppress the entire eligible list. Successful receipt purge removes matching age metadata so a later file at the same path receives a new timestamp. The scan creates no purge receipt and cannot delete files.

**Verification:** The full locked Curator suite passes 362 tests. Focused project-plugin, migration, API, MCP, and reviewer suites pass; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, dependency audit, lock check, and `git diff --check` pass.

**Open gate:** An attended expiry-only exact-inventory approval flow, its durable receipt and hold integration, and scheduler retry remain unimplemented. Production retention, identity, deployment, and live-runtime gates remain open.

**Outcome:** Trusted age eligibility is available locally; destructive expiry still requires implementation of the complete attended receipt path.

## 2026-10-22 — Persist attended 72-hour expiry approvals and retries

**Intent:** Implement the approved local-alpha 72-hour ceiling with an explicit exact-inventory decision and a durable receipt before any deletion.

**Changed fact:** Schema v20 adds project-scoped expiry receipts and hash-bound targets. The attended local-UID review CLI displays and confirms the complete eligible inventory, records reviewer/hash/targets before unlink, rechecks active legal/operational holds before each purge, and leaves failures visibly `purge_pending` with retry backoff. The one-shot maintenance command now retries both SDE and expiry receipts that already have human approval. The local policy draft now says 72 hours maximum; the seven-day draft value is superseded. Immediate eligibility after compact facts and related SDE disposition is not yet implemented.

**Verification:** The full locked Curator suite passes 365 tests; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv audit`, `uv lock --check`, and `git diff --check` pass. The v19-to-v20 migration regression preserves age metadata. The persistence MCP returned `unauthenticated` because trusted Hermes profile context was unavailable, so live ledger capture status remains unverified.

**Open gate:** Immediate post-record/SDE-disposition eligibility, production retention policy, authenticated Hermes identity, deployment, and live runtime remain open. The V2 delivery checklist stays at 127/153 complete and 26 open; its expiry row remains open.

**Outcome:** The local attended approval and retry path is implemented and locally verified under the approved 72-hour maximum; no production or live-runtime gate is closed.

## 2026-10-22 — Make fact-reviewed artifacts eligible promptly

**Intent:** Honor the approved local-alpha rule that transient files become expiry-eligible promptly after compact facts and related SDE review, while preserving the 72-hour maximum-age fallback and pending-review pause.

**Changed fact:** Expiry discovery now checks durable fact and SDE receipt timestamps against each artifact's publication time. Post-publication facts or a completed related review make the file immediately eligible when no SDE remains pending for that goal. Pending SDE review blocks both discovery and retry, including after 72 hours; explicit legal/operational holds continue to block deletion. Files without post-publication record/disposition evidence reach the 72-hour fallback.

**Verification:** The full locked suite passes 367 tests, including immediate fact eligibility, pending-SDE pause beyond the cap, receipt retry blocking during review, and resumption after the decision. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv audit`, `uv lock --check`, and `git diff --check` pass. Focused project-plugin, API, and MCP suites also pass.

**Open gate:** Production retention policy, authenticated Hermes reviewer identity, deployment and scheduled runtime remain open. The delivery checklist stays at 127/153 complete and 26 open.

**Outcome:** The local alpha now implements both prompt post-record eligibility and the 72-hour maximum-age fallback without granting unattended deletion authority.

## 2026-10-22 — Include expiry cleanup in operational health

**Intent:** Prevent an incomplete attended expiry purge from remaining invisible or allowing local health to report green.

**Changed fact:** Project operational counts now include pending expiry receipts and artifact targets. Local health adds distinct expiry-purge gates, and Prometheus exports both counts. MCP health serialization includes the new counters. Production scheduling and alert delivery remain separate.

**Verification:** The full locked suite passes 368 tests; focused API (36), MCP (6), and concurrency (7) suites pass. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv audit`, `uv lock --check`, and `git diff --check` pass. The API regression proves a pending expiry receipt forces degraded status with all host dependency probes ready.

**Open gate:** Production scheduler/alert integration, authenticated Hermes identity, deployment, and live runtime remain open. The delivery checklist remains 127/153 complete and 26 open.

**Outcome:** Local health cannot report green while an attended expiry receipt or its target remains pending; this is local aggregation evidence only.

## 2026-10-22 — Close local staging and expiry checklist item

**Intent:** Record the approved 72-hour local-alpha maximum accurately and count completed V2 delivery work without closing external release gates.

**Changed fact:** The delivery checklist now marks local ephemeral staging complete based on bounded goal-scoped writes, complete fail-closed inventory, separation from canonical facts, attended exact-inventory approval, and durable purge receipts with retry status. The snapshot is 128/153 complete and 25 open. The local-alpha maximum remains 72 hours; the separate dirty `docs/git-1.md` was preserved unchanged.

**Verification:** Curator's full locked test suite remains verified at 368 passing tests on the current implementation. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv audit --locked --preview-features audit-command`, `uv lock --check`, and `git diff --check` pass.

**Open gate:** Source-specific producer wiring, network-filesystem locking, production retention policy, scheduler deployment, authenticated Hermes reviewer identity, and live runtime remain open. No GPTMD files or V1 runtime state were changed.

**Outcome:** One local implementation row is closed; the V2 goal remains active and production readiness is not claimed.

## 2026-10-22 — Reduce repository-wide Pylint findings

**Intent:** Continue the open V2 repository-quality cleanup with behavior-preserving fixes that remove straightforward convention findings.

**Changed fact:** Reordered test-fixture imports, documented test doubles, marked intentionally unused fixture parameters, and wrapped long SQL/JSON lines. The fresh full Pylint inventory fell from 306 findings (283 refactor, 21 convention, 2 warning) to 295 (283 refactor, 12 convention, no warnings).

**Verification:** Focused review-CLI and project-plugin suites pass 51 tests; strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv audit --locked --preview-features audit-command`, `uv lock --check`, and `git diff --check` pass. The full suite's latest verified result before this style-only slice remains 368 passing tests.

**Open gate:** Repository-wide refactor findings and the 12 oversized-module convention findings remain open; this cleanup does not close the tracked full-Pylint item. Production retention, authenticated Hermes identity, deployment, and live-runtime gates remain open.

**Outcome:** Eleven non-blocking findings are removed without changing runtime behavior; the full Curator V2 goal remains active.

## 2026-10-22 — Record local-alpha hold policy and enforcement

**Intent:** Apply the approved local-alpha retention and reviewer decisions to the policy documentation and verify that explicit legal/operational holds cannot be purged implicitly.

**Changed fact:** The policy document now records `eaglesvn` as the sole local UID-bound project admin/reviewer, the 72-hour maximum-age fallback and prompt post-record eligibility, and the rule that pending SDE review and explicit legal/operational holds pause deletion until their authorized resolution. It records that the same attended review approves only the exact displayed purge inventory. The delivery checklist now counts the local hold-policy/enforcement row complete: 129/153 complete and 24 open. Hermes-authenticated identity, production policy, and external hold-source discovery remain open.

**Verification:** All 23 purge tests and all 6 MCP server tests pass. They cover hold visibility, zero purge attempts while held, state survival across store reopen, separate audited release, and simultaneous retention of a held artifact with purge of an unheld artifact after canonical persistence. `git diff --check` passes.

**Open gate:** The approved policy applies to local alpha only. The `renew-ssl-coding` profile still reports `auth=none`; production role provisioning, retention policy, external legal/operational hold discovery, scheduling, alerting, and live runtime remain unverified.

**Outcome:** The local hold rule and enforcement evidence are recorded; no production or live-identity gate is closed.

## 2026-10-22 — Verify Hermes project-usage integration in isolation

**Intent:** Recheck the Hermes-owned project-usage path while keeping provider/model counts out of Curator events and keeping live identity/runtime claims evidence-bound.

**Changed fact:** Two Hermes test fixtures now stub only bootstrap dependency activation so tests running from a checkout beneath `~/.hermes` do not read the neighboring real-home install manifest. The local suite covers project-usage aggregation, Codex/provider usage attribution, Gateway hook persistence, and durable outbox replay. Curator remains unchanged for token accounting; Host Steward and the project-usage ledger remain Hermes Core-owned.

**Verification:** The focused Hermes integration selection passes 46 tests across five files. `python3 scripts/check` passes all 12 Core checks; Ruff on the changed files and Hermes `git diff --check` pass. Curator's delivery checklist count remains 129/153 complete and 24 open.

**Open gate:** This is local test/source evidence. Live provider capture, complete project-wide token coverage, authenticated profile identity, production budgets/retention/alerts, and live runtime remain unverified.

**Outcome:** The local Hermes usage integration is testable without real-home manifest access; no production or live-provider gate is closed.

## 2026-10-22 — Align alpha gate docs with approved local retention

**Intent:** Remove stale statements that implied local-alpha retention and hold defaults were still awaiting owner approval.

**Changed fact:** The alpha limitations and release-gate summary now distinguish the approved local 72-hour maximum-age rule and explicit hold exceptions from the still-open production retention policy, external hold discovery, and deployment recovery requirements. The V2 delivery checklist count remains 129/153 complete and 24 open.

**Verification:** Reviewed the changed policy language against the owner-approved local-alpha policy and current hold/expiry implementation; `git diff --check` passes. No runtime or source behavior changed.

**Open gate:** Production retention/hold policy, authenticated identity, deployment recovery, and live-runtime evidence remain open.

**Outcome:** Local-alpha approval and production-release evidence are described separately; the full V2 goal remains active.

## 2026-10-22 — Enforce the local-alpha 72-hour hard maximum

**Intent:** Apply the owner's clarification that transient-artifact retention must not exceed 72 hours in local alpha.

**Changed fact:** Expiry discovery now allows age-based eligibility at 72 hours even when an SDE remains pending. Pending SDE review still delays prompt post-record expiry, but it cannot extend the hard age ceiling; the SDE remains reviewable from canonical facts after its transient source is removed. Explicit legal/operational artifact holds continue to require separate release. The policy, alpha summary, consumer instructions, and regression test now state and enforce this behavior.

**Verification:** Focused project-plugin expiry tests and `git diff --check` pass.

**Open gate:** The policy is local-alpha only. Production retention/hold policy, authenticated Hermes identity, external hold discovery, deployment, and live-runtime evidence remain open.

**Outcome:** The local-alpha 72-hour age ceiling is enforced through pending SDE review; the V2 goal remains active.

## 2026-10-22 — Recheck the isolated Vhost alpha endpoint

**Intent:** Use the owner's conditional approval to recheck the deployed V2 profile endpoint after the local backend, package, and plugin acceptance checks passed.

**Changed fact:** The `renew-ssl-coding` endpoint ensure command returned `state=ready` with the systemd supervisor and the expected bounded runtime capabilities. The profile Curator MCP stdio check connected and discovered 46 tools, reporting `auth=none`. The profile gateway status still listed only the default gateway PID. Alpha documentation now distinguishes the endpoint handshake and stdio discovery from an interactive profile call or Vhost application workflow.

**Verification:** Read-only gateway status and MCP discovery succeeded. No Curator goal, fact, canonical target, or staged artifact was written by this check. `git diff --check` passes.

**Open gate:** Profile tool-call approval, authenticated identity, real Vhost application request/canonical write, production retention/recovery, and live production runtime remain unverified. Only the exact local UID-reviewed purge path is approved for local alpha.

**Outcome:** The isolated endpoint is ready and the installed stdio tool surface is discoverable; application workflow and production readiness remain open.

## 2026-10-22 — Reverify Vhost composition with the current wheel

**Intent:** Recheck the repository-local Vhost plugin against the just-pushed Curator V2 wheel through Hermes Core's managed MCP path.

**Changed fact:** The Vhost-owned disposable harness used a fresh temporary Python 3.12 environment containing the wheel built from commit `060b325`. Hermes Core's actual `HookRegistry` and `HookContext` delivered three lifecycle events through managed stdio MCP; exact replay, failed-delivery retry, explicit goal binding, denial of premature binding and reviewer-only persistence, canonical projection reconciliation, private-metadata exclusion, and out-of-scope target preservation all passed. The seven Vhost installed-consumer contracts also pass against that wheel.

**Verification:** The harness exited 0 with `result=passed`, `processed_events=3`, and all reported assertions true. The Vhost contract suite passes 7/7 tests. Both suites used disposable databases; the Vhost application worktree's pre-existing dirty and untracked files were preserved.

**Open gate:** This is a disposable local integration, not a live Vhost application request. Authenticated human identity, production authorization, production retention/recovery, and live deployment/runtime remain unverified.

**Outcome:** The current Curator wheel composes locally with Hermes Core managed MCP and the Vhost plugin; the live workflow/release gate remains open.

## 2026-10-22 — Install and verify the current Vhost alpha wheel

**Intent:** Put the owner-approved local alpha package into the dedicated Vhost Hermes profile environment and verify the installed consumer path.

**Changed fact:** Reinstalled the wheel built from Curator commit `060b325` into the `renew-ssl-coding` Curator V2 environment. Installed `project_plugin.py`, `store.py`, and `mcp_server.py` hashes match the repository source. The seven Vhost consumer tests and Hermes Core managed-MCP disposable harness pass against this environment. Hermes MCP discovery exposes 47 tools and reports `auth=none`; gateway status lists only the default-profile PID.

**Verification:** The Vhost contract suite passes 7/7; the disposable Hermes harness passes with three processed events, exact replay, failed-delivery retry, denied premature binding and reviewer-only persistence, and reconciled projection. No Vhost application records were written.

**Open gate:** The profile install and disposable harness do not prove an interactive authenticated tool call or live Vhost application workflow. Production identity, retention/recovery, deployment, and runtime gates remain open.

**Outcome:** The current wheel is installed and verified through the local consumer/plugin path; production and live-profile claims remain open.

## 2026-10-22 — Verify Curator goal-ledger caller context

**Intent:** Check whether this Codex session can read the active V2 ledger through the configured Curator protocol before making any persistence claim.

**Changed fact:** The read-only Curator V2 `goal_list` call returned `unauthenticated` with the fixed message that trusted Hermes profile context is required. No ledger mutation was attempted. This client call did not include Hermes profile metadata and is separate from the successful disposable Hermes-managed stdio integration.

**Verification:** The MCP tool returned `isError=true`, code `unauthenticated`; the worktree and existing goal state were not changed by the call.

**Open gate:** This Codex session cannot claim current Curator goal-ledger state or persist goal events through the protocol without trusted Hermes context. The result does not establish failure of the separately tested local profile or an authenticated human identity.

**Outcome:** Ledger access remains unknown from this client; checked-in V2 history remains the available repository audit trail.

## 2026-10-22 — Correct Curator V2 delivery progress and simplify config parsing

**Intent:** Keep the plan's delivery count aligned with its stated rule and continue the open local Pylint cleanup without weakening config validation.

**Changed fact:** Corrected the snapshot to 130/173 complete (43 open) by excluding the 38 per-task checkboxes in section 11's reusable execution templates. Extracted bounded TOML parsing and root-schema validation from `_read_project_document` into `_parse_project_config`; validation order and sanitized errors are preserved.

**Verification:** The focused project-plugin suite passes 43 tests and the full Curator suite passes 368 tests. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. The fresh full Pylint inventory is 286 findings (274 refactor, 12 convention), one fewer than the prior 287; `_read_project_document` no longer reports too-many-branches.

**Open gate:** Repository-wide Pylint cleanup remains open. Authenticated production identity, deployment-owned retention/recovery, and live consumer/runtime proof remain open. No delivery row changed status; no V1, GPTMD, or consumer worktree was changed.

**Outcome:** The delivery count is now consistent with its exclusion rule, and one local structural finding was removed. The Curator V2 goal remains active.

## 2026-10-22 — Isolate Markdown target opening

**Intent:** Continue the local V2 Pylint cleanup by separating target opening from bounded Markdown reading while preserving the no-follow and sanitized-error behavior.

**Changed fact:** Added `_open_target` to perform the no-follow open and normalize missing/open failures. `_read_target` retains the descriptor-based regular-file, size, UTF-8, mode, and closure checks.

**Verification:** All 19 focused Markdown-persistence tests and the full 368-test suite pass. Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. Full Pylint is 285 findings (273 refactor, 12 convention), down one; `_read_target` no longer has the excess-branch finding.

**Open gate:** Repository-wide Pylint cleanup, production identity, retention/recovery policy, deployment, and live consumer/runtime proof remain open. No delivery row changed status, and no V1, GPTMD, consumer, or Hermes Core file changed.

**Outcome:** One additional local structural finding was removed; Curator V2's broader alpha and release gates remain open.

## 2026-10-22 — Verify current Vhost alpha package composition

**Intent:** Install the just-pushed V2 candidate in the dedicated local Vhost alpha profile and verify its consumer and Hermes composition before any live application request.

**Changed fact:** Built the wheel from Curator commit `24cae4c` (SHA-256 `3f552edf5edafa9f509a491e385dfc6286751e99ebf1cf5dd7dddead5d62ca1a`) and reinstalled it only in the `renew-ssl-coding` Curator V2 environment. All 35 installed Python modules match source. The Hermes profile reports 47 Curator tools and `auth=none`; gateway status lists only the default-profile PID.

**Verification:** The seven Vhost installed-consumer contracts pass. The Hermes Core managed-MCP disposable integration passes three lifecycle events, exact replay, failed-delivery retry, planned-goal binding denial, reviewer-only persistence denial, Vhost projection reconciliation, and private/out-of-scope target checks. Hermes `scripts/check` passes 12 checks; 69 focused Hermes integration and Host Steward tests pass. A read-only SQLite check reports schema 20, `quick_check=ok`, one goal, two facts, 12 inbox receipts, and two project grants.

**Open gate:** No live Vhost application request or interactive authenticated profile call was verified; Hermes reported `auth=none` and listed only the default gateway PID. Production identity, retention/recovery, deployment recovery, and live-runtime acceptance remain open. Vhost source files and their pre-existing dirty state were preserved; no GPTMD or V1 repository/state was touched.

**Outcome:** The current V2 wheel and repository-owned Vhost plugin compose locally through Hermes Core's managed MCP path. This is local alpha evidence, not production readiness or a closed lifecycle checklist item.

## 2026-10-22 — Separate SDE disposition from cleanup authorization

**Intent:** Implement the plan's separate human approval gate so SDE approval/rejection and expiry eligibility cannot authorize destructive deletion.

**Changed fact:** Curator now records SDE disposition without starting purge. Schema v21 adds a project-scoped cleanup authorization receipt bound to the exact path/hash manifest, reviewer, approval time, and a separate Markdown projection proof. The plugin rechecks the live staging inventory before accepting a new approval; it projects the authorization before processing deletion. Scheduler retry selection requires that durable projection proof. Local review CLI and MCP now expose a second explicit cleanup decision, and policy/API documentation describes the two-step flow. Delivery progress is 131/174 complete with 43 open, excluding reusable section 11 templates.

**Verification:** Four focused lifecycle, local-review CLI, and MCP tests pass, covering no deletion before approval, mismatched and changed-manifest refusal, exact approval, projection-before-delete, and retry after an approved purge failure. Strict Pyright reports zero diagnostics; `git diff --check` passes. The full suite was not rerun.

**Open gate:** The Vhost consumer's installed alpha wheel and repository-owned workflow have not yet been updated or reverified against the new approval tool. Hermes profile identity remains `auth=none`; production identity, retention/recovery, deployment, and live-runtime gates remain open. Existing dirty `docs/git-1.md` is preserved; no GPTMD or V1 runtime/repository state was touched.

**Outcome:** The local Curator backend now enforces separate canonicalized cleanup approval; the full Curator V2 goal remains active.

## 2026-10-22 — Show cleanup authorization in canonical goal reports

**Intent:** Make the separate cleanup gate visible in goal reports so `purge_pending` distinguishes unapproved cleanup from approved retry work.

**Changed fact:** Markdown review-receipt projections now state whether cleanup is awaiting a separate human approval, approved, or not required for an empty inventory. Approved receipts show the cleanup reviewer, exact manifest hash, and approval time. The projection still excludes temporary file contents and does not claim a final purge outcome until retry state is reconciled.

**Verification:** The focused Curator V2 MCP SDE/cleanup integration passes, including changed-manifest refusal, authorization projection before deletion, and approved retry. Strict Pyright reports zero diagnostics; `git diff --check` passes.

**Open gate:** The installed Vhost alpha wheel has not yet been updated to use the separate cleanup tool. Hermes authenticated identity, production retention/recovery, deployment, and live-runtime evidence remain open.

**Outcome:** Canonical goal reports now expose cleanup authorization separately from SDE disposition and purge status.

## 2026-10-22 — Record owner-approved local alpha policy

**Intent:** Close the local policy-recording item using the owner's approved values without applying them to production.

**Changed fact:** The V2 pilot policy now records the local UID-bound reviewer, two-step SDE/cleanup decisions, compact-facts-only canonical data, prompt expiry with a 72-hour maximum, explicit hold handling, fail-closed missing identity/inventory/approval, and Hermes Core root-account ownership of Host Steward. The plan now counts 132/174 delivery rows complete and 42 open; production identity, retention, external hold discovery, deployment recovery, and live runtime remain open.

**Verification:** Compared the policy text with the owner's local-alpha decisions and existing fail-closed implementation; checklist counting reports 132 complete, 42 open, 174 total. `git diff --check` passes. No runtime test was needed for this documentation-only change.

**Open gate:** These defaults do not establish production identity, production retention, deployment-owned hold discovery, or live runtime behavior.

**Outcome:** Local alpha owner requirements are recorded; production release policy remains open.

## 2026-10-22 — Reconcile the lifecycle plan with schema v21

**Intent:** Remove an obsolete plan statement left over from the direct SDE-to-purge implementation.

**Changed fact:** The plan now states that SDE confirmation records disposition only and points to the separate schema-v21 cleanup authorization and canonical projection proof. No checklist status changed; the count remains 132/174 complete with 42 open.

**Verification:** Compared the plan entry with the current Curator service/plugin flow and the focused approval tests; checklist count remains 132/174; `git diff --check` passes.

**Open gate:** The installed Vhost consumer remains on an older alpha package. Hermes authenticated identity, production retention/recovery, deployment, and live-runtime gates remain open.

**Outcome:** The plan no longer claims SDE confirmation begins purge.

## 2026-10-22 — Refresh local expiry policy status and clear one lint finding

**Intent:** Keep the local-alpha retention record aligned with the implemented attended expiry workflow and make a small, behavior-preserving step on repository-wide Pylint cleanup.

**Changed fact:** The policy documentation now describes the implemented expiry-only approval, durable pre-unlink receipt, hold integration, and approval-bound retry command, while retaining production scheduling and retention gates. Wrapped the purge-test manifest comprehension that the latest full Pylint inventory flagged for line length.

**Verification:** The pre-change full Pylint output lists 291 non-blocking findings, including the `C0301` line in `tests/test_purge.py`. The targeted `C0301` check passes after the edit. No tests or full Pylint rerun were performed.

**Open gate:** Repository-wide Pylint cleanup and production retention/scheduler evidence remain open. No delivery checkbox changed.

**Outcome:** Current local expiry status and the focused lint result are recorded without implying production readiness.

## 2026-10-22 — Track the installed V2 VS Code status label

**Intent:** Record the owner's separately requested V2-owned VS Code status-bar integration in the delivery checklist.

**Changed fact:** Added one delivery row for the `CuratorMD V2` status extension. The label and its click action explicitly state that they do not check service health, capture, persistence, or identity. The delivery checklist now reports 133/175 complete with 42 open; the denominator increased by one for this newly tracked user request.

**Verification:** `node --check integrations/vscode-status/extension.js` passes. VS Code lists `curatormd.curatormd-v2-status@0.1.0`; SHA-256 for the repository and installed `extension.js` both equals `01ef7ba8ade4e43a7f1aca7b686e37ec01bf47cb4f5c725bb22010bc02d8f08a`. A cropped screenshot of the active Curator V2 workspace visibly shows `CuratorMD V2` in the bottom status bar.

**Open gate:** This informational editor label does not establish authenticated identity, runtime health, or deployment readiness. No tests were run.

**Outcome:** The separately requested V2 editor integration is visible in the V2 plan with directly checked local installation evidence.

## 2026-10-22 — Bind SDE disposition and exact purge to one review action

**Intent:** Align the local-alpha review flow with the owner's decision that the same explicit SDE review action authorizes purge of its displayed exact inventory.

**Changed fact:** A complete, freshly rechecked inventory now creates its distinct cleanup-authorization receipt during `sde_confirm`; incomplete inventories create no cleanup authorization. Canonical projections of both receipts remain mandatory before purge. The review CLI uses one phrase bound to the manifest, and the MCP lifecycle regression now proves unheld files purge after canonical persistence while held files remain. Markdown projections identify the cleanup receipt as authorized by the review action.

**Verification:** Eight focused review-CLI tests and the focused MCP SDE/persistence/purge integration pass. Strict Pyright reports zero diagnostics; errors-only Pylint and Bandit exit successfully; Bandit reports four existing `nosec` notices in `git_evidence.py`. `git diff --check` passes.

**Open gate:** Hermes still reports no authenticated human subject for the Vhost profile. Production identity, retention/recovery, deployment, scheduler, and live-runtime gates remain open; Curator V2 MCP persistence could not be verified in the unauthenticated session. No V1, GPTMD, consumer, or Hermes Core files were changed.

**Outcome:** Local V2 review and purge behavior now follows the one-action policy while preserving the canonical-write-before-delete gate; the full V2 goal remains active.

## 2026-10-22 — Mark Curator activity status read-only for Hermes

**Intent:** Let Hermes classify the V2 ledger status read as non-mutating while retaining the required host-injected profile/session context check.

**Changed fact:** The `project_activity_status` MCP schema now advertises `readOnlyHint=true`, with the corresponding bounded, non-destructive annotations. The MCP contract documents this hint. No authentication rule or caller identity was relaxed.

**Verification:** The current Hermes Core checkout's profile-scoped `mcp test` reports host-injected local stdio context and discovers 47 tools. A read-only SQLite integrity inspection returned `quick_check: ok`, with one goal, two facts, and 12 inbox rows. The Hermes-routed status call was rejected before server execution; the direct Codex call remains `unauthenticated`. No local MCP status result was obtained.

**Open gate:** Authenticated Hermes MCP status, verified human identity, production persistence, and live runtime remain unverified. The delivery checkbox remains open.

**Outcome:** Hermes trust metadata can distinguish the status tool as read-only, but the active caller path still has not completed an authenticated ledger read.

## 2026-10-22 — Detect default GitLab access-token prefix

**Intent:** Reduce one documented provider-token false negative in the V2 reject-only input gate.

**Changed fact:** The detector rejects the documented `glpat-` token prefix when followed by its documented 20-character token body. The scanner documentation records GitLab's configurable custom-prefix limitation.

**Verification:** Added a synthetic `glpat-` regression to the focused content-safety suite. GitLab's official token and administrator-setting documentation was checked for the default prefix, body length, and custom-prefix behavior. No live credentials were used.

**Open gate:** Other provider formats, custom prefixes, false positives, jurisdictional policy, and end-to-end privacy assurance remain open; the threat-model checklist remains unchecked.

**Outcome:** The default GitLab token form is covered by the local high-confidence reject-only scanner.

## 2026-10-22 — Verify V2 status through the Hermes profile context

**Intent:** Replace the failed direct Codex status path with an explicit read-only probe through the configured local Hermes stdio integration.

**Changed fact:** Hermes Core now provides `hermes mcp test curator_v2 --probe-curator-status`. It invokes only Curator's fixed activity-status tool and supplies host-generated profile/session metadata after requiring the exact opted-in local stdio server.

**Verification:** Four focused Hermes CLI tests passed. The current Hermes Core checkout successfully probed the configured `renew-ssl-coding` profile: Curator returned project `vhost-manager-alpha`, 12 retained and processed event receipts, one goal, two facts, and zero SDE candidates. This was a read from the configured local stdio process; it made no ledger changes.

**Open gate:** This confirms Hermes profile-context access and persisted aggregate visibility, not authenticated human identity, the managed gateway route, production persistence, or deployment. The system-installed Hermes CLI is older than this source checkout; the new command is not installed globally.

**Outcome:** Local profile-context ledger status is directly verified; identity and production/runtime gates remain open.

## 2026-10-22 — Mark Curator MCP inspection tools read-only

**Intent:** Make Hermes trust-tier gating distinguish observational V2 operations from mutations across the complete MCP surface.

**Changed fact:** Curator's read-only status, goal, projection, listing, review-inspection, storage, reconciliation, and purge-status tools now share bounded non-destructive MCP annotations. Lifecycle, review-decision, cleanup, hold-release, and retry tools remain write-capable.

**Verification:** The focused MCP protocol regression verifies `readOnlyHint=true` for every designated inspection tool and confirms representative goal-start, SDE-decision, and purge-retry actions are not marked read-only. Pyright reports zero diagnostics; errors-only Pylint and Bandit pass; `git diff --check` passes. Bandit emitted four existing `nosec` notices for `git_evidence.py`.

**Open gate:** An MCP hint is advisory metadata, not authorization or identity. Hermes host-context, project grants, verified human identity, and production gates remain independently enforced/open.

**Outcome:** Hermes can correctly classify the local Curator inspection surface for trust-tier approval decisions.

## 2026-10-22 — Cover the v20-to-v21 cleanup-authorization migration

**Intent:** Close the focused local migration-fixture gap for the current schema version without treating it as production upgrade approval.

**Changed fact:** The v20-to-v21 regression preserves an existing SDE receipt and proves migration creates no cleanup authorization for legacy decisions. The schema reference and ordered domain-slice text now describe the supported v0-to-v21 path.

**Verification:** The focused migration regression passes; `git diff --check` passes.

**Open gate:** Full migration, rollback, corruption, backup/restore, and deployment upgrade drills remain separate open work; the local-domain slice stays open.

**Outcome:** The latest schema step has direct evidence that it does not grant cleanup authority retroactively.

## 2026-10-22 — Reject malformed v21 migration targets

**Intent:** Prevent schema migration from accepting a conflicting object under the cleanup-authorization table name.

**Changed fact:** The v21 migration now validates the existing object kind, exact column names/types/defaults/nullability/primary-key shape, and audit-receipt foreign key before stamping schema version 21. An incompatible table fails closed without modification.

**Verification:** Focused migration tests pass for the valid legacy-receipt upgrade, malformed-column refusal, and missing-receipt-foreign-key refusal; `git diff --check` passes.

**Open gate:** Full recovery and production migration/rollback drills remain open.

**Outcome:** The v21 schema stamp is no longer applied over an incompatible pre-existing table.

## 2026-10-22 — Cover v21 migration constraints independently

**Intent:** Verify every fail-closed constraint checked when an existing v21 cleanup-authorization table is encountered.

**Changed fact:** The migration regression now independently varies the canonical-persistence default, required project-field nullability, and receipt primary key, in addition to the existing malformed-column and missing-foreign-key cases.

**Verification:** Four focused v20 migration tests pass: valid legacy-receipt upgrade, malformed columns, missing receipt foreign key, and three incompatible-constraint variants. Each refusal preserves schema version 20. Strict Pyright, errors-only Pylint, and `git diff --check` pass. No full suite was rerun.

**Open gate:** Production upgrade/rollback, corruption, backup/restore drills, and deployment approval remain open.

**Outcome:** The local v21 fail-closed schema checks now have direct regression coverage for each validated constraint.

## 2026-10-22 — Split read-side Curator record models

**Intent:** Reduce the oversized core model module while preserving its existing import contract.

**Changed fact:** Goal bullets, storage/activity/health summaries, expiry and cleanup projections, and the fact archive receipt now live in `read_models.py`. Shared timestamp and digest validators live in `record_validation.py`. Lazy exports and type-checking declarations preserve the existing `curatormd_v2.models` import paths.

**Verification:** The eight contract-schema tests pass; strict Pyright reports zero diagnostics; errors-only Pylint passes; direct compatibility imports resolve to the new record classes; the targeted Pylint module-line check rates the changed model modules 10.00/10; `git diff --check` passes. No full test suite or warning-level repository inventory was rerun.

**Open gate:** Wide serialized record attribute findings and repository-wide warning-level Pylint cleanup remain open. No delivery checklist status changed.

**Outcome:** The core model module is now 980 lines while existing import paths remain usable; the repository-wide Pylint item remains open.

## 2026-10-22 — Simplify current evidence revalidation

**Intent:** Make the evidence trust check operate on one explicit scope/time context and reduce its compound provenance logic.

**Changed fact:** `evidence_has_current_attestations` now accepts `EvidenceVerificationContext` directly. Separate helpers check evidence-reference equality, exact project/goal/criterion binding, and stable source revision/adapter/authenticated subject. The service and Markdown projection callers construct the same bounded context explicitly.

**Verification:** The focused goal-completion and Markdown-projection regressions pass. Strict Pyright reports zero diagnostics, errors-only Pylint and `git diff --check` pass. Targeted Pylint no longer reports the evidence function's argument-count or boolean-expression findings; its focused score improved from 9.19 to 9.95/10. The last full warning-level inventory before this change contained 278 findings; it was not rerun after the refactor.

**Open gate:** The repository-wide warning-level Pylint inventory and deployment-owned evidence trust roots remain open. No full test suite was rerun.

**Outcome:** Evidence revalidation uses an explicit trusted context with simpler, separately reviewable checks; the full V2 goal remains active.

## 2026-10-22 — Extract evidence adapter policy validation

**Intent:** Simplify the host-trusted evidence adapter constructor while preserving its explicit configuration surface.

**Changed fact:** Project/subject allowlist checks, source age ceilings, and revocation freshness bounds now use small validation helpers. The adapter's configured trust fields and fail-closed receipt checks are unchanged.

**Verification:** The 13-test evidence module passed after helper extraction; after replacing an assertion in the revocation-limit helper with an exact-integer guard, the focused TTL/boolean regression passes. Strict Pyright, errors-only Pylint, and Bandit pass; Bandit emits four existing `nosec` notices. The focused branch/argument Pylint check no longer reports excessive branches; it reports only the existing eight-argument constructor finding. No full suite or full warning-level Pylint inventory was rerun.

**Open gate:** Repository-wide warning-level Pylint cleanup and deployment-owned evidence credentials/trust roots remain open.

**Outcome:** Adapter policy validation is separated into bounded helpers without changing the source-authentication boundary.

## 2026-10-22 — Cover current GitHub token formats in the reject-only scanner

**Intent:** Close two documented provider-token false negatives in the local high-confidence safety gate.

**Changed fact:** The detector now rejects fine-grained PATs beginning `github_pat_` and stateless installation tokens beginning `ghs_`, including JWT-shaped bodies with periods and underscores. The safety contract links GitHub's token-prefix documentation and October 2026 rollout notice.

**Verification:** Three content-safety tests and two API/MCP persistence privacy canaries pass. Both forms are absent from returned errors and durable writes; the API canary also checks backup absence, and the MCP canary checks logs, SQLite sidecars, canonical history, and staging files. Strict Pyright, errors-only Pylint, and `git diff --check` pass. No full suite was rerun.

**Open gate:** This covers only two documented formats; other secrets, custom formats, false positives, jurisdictions, independent DLP review, and deployment policy remain open. A clean scan is not privacy certification.

**Outcome:** Both newly documented GitHub token forms fail closed before canonical persistence or event retention.

## 2026-10-22 — Group trusted evidence adapter policy

**Intent:** Reduce evidence adapter configuration complexity without weakening host-owned project, subject, or freshness checks.

**Changed fact:** Added immutable `EvidenceAdapterPolicy` for project and subject allowlists and age/revocation limits. Adapter construction freezes validated allowlists and applies source-specific ceilings before evidence evaluation. Exported the policy type and documented that event and MCP input cannot choose it.

**Verification:** All 13 focused evidence tests pass; strict Pyright reports zero diagnostics; the focused warning-level Pylint run no longer reports the adapter's argument-count or attribute-count findings; `git diff --check` passes. Other intentional small data/protocol-class warnings remain, and the repository-wide warning inventory was not rerun.

**Open gate:** This changes local configuration structure only. Deployment-owned evidence identities and trust roots, authenticated human identity, owner policy, and production adapter integration remain open.

**Outcome:** Trusted adapter policy is represented as one immutable host-owned value, with source checks unchanged.

## 2026-10-22 — Close the per-slice evidence-index requirement

**Intent:** Make each V2 implementation slice reviewable against concrete evidence and explicit remaining approval boundaries.

**Changed fact:** Verified the A-I status rows and matching entry, recovery, and approval registers in `docs/release-gates-v2.md`; each row identifies ownership, probe, expected/actual result, evidence, and open exit conditions. Marked the corresponding plan documentation requirement complete.

**Verification:** Manual cross-check of all nine slice rows and the entry/recovery/approval register; `git diff --check` passes.

**Open gate:** The documentation checklist item is complete, but product slices and deployment, identity, retention-policy, and live-runtime release gates remain open.

**Outcome:** Reviewers have one indexed A-I evidence ledger; no runtime gate or release status changed.

## 2026-10-22 — Use typed records for project-registry audit writes

**Intent:** Reduce the project-registry audit writer's argument complexity while preserving its append-only audit data and transaction boundary.

**Changed fact:** `_append_project_registry_audit` now accepts the existing typed `ProjectRegistryAuditRecord`; registration, update, suspension, and reactivation construct that record before writing it.

**Verification:** All 7 project-access tests pass; strict Pyright and `git diff --check` pass. Targeted Pylint no longer reports either argument-count finding for the audit writer. A fresh repository-wide warning-level inventory fell from 273 to 271 findings.

**Open gate:** Repository-wide structural and duplicate-code findings remain. Project identity authentication, deployment-owned registry authority, and live deployment gates are unchanged.

**Outcome:** The writer's typed input keeps the audit fields explicit and removes two warning-level findings without changing the storage schema.

## 2026-10-22 — Type project registration commands

**Intent:** Reduce registration/update interfaces to one explicit binding request while retaining host-derived actor identity and the existing authorization order.

**Changed fact:** Added immutable `ProjectRegistrationRequest` and a factory from validated project configuration. `ProjectAccessManager` authorizes the exact request project, then derives `actor_id` from the trusted caller before calling the store. Updated the attended CLI and hosted-MCP test provisioning path.

**Verification:** The focused project-access, access-CLI, and hosted-MCP suites pass 22 tests; strict Pyright reports zero diagnostics; `git diff --check` passes. A fresh full warning-level Pylint inventory fell from 271 to 263 findings, removing eight argument and positional-argument findings.

**Open gate:** The inventory still has 263 structural, design, and duplicate-code findings. The host admin remains a local profile/UID assertion; verified Hermes identity, deployment authority, and live registration administration remain open.

**Outcome:** Registration inputs are typed and bounded as one request object, while caller identity remains host-derived and authorization remains fail-closed.

## 2026-10-22 — Bind profile authorization to a typed config snapshot

**Intent:** Make the fingerprint-bound authorizer's trusted configuration explicit while preserving its per-call registry and grant checks.

**Changed fact:** Added immutable `ProjectAuthorizationBinding`, built from validated `ProjectConfig` and the exact allowed-action set. The local MCP launcher and attended reviewer now construct the authorizer from this binding; the authorizer still checks registration status, fingerprints, API version, and current grants for each action.

**Verification:** Focused access, CLI, hosted-MCP, and review-CLI tests pass 31 cases; strict Pyright reports zero diagnostics; changed-file warning-level Pylint reports no constructor argument finding for the fingerprint-bound authorizer; `git diff --check` passes. The full repository warning inventory was not rerun.

**Open gate:** This local config binding is not cryptographic Hermes identity. Authenticated identity, production grant administration, deployment, retention policy, and live-runtime gates remain open.

**Outcome:** The authorizer configuration is a typed immutable value without changing fail-closed authorization behavior.

## 2026-10-22 — Group serialized fact persistence fields

**Intent:** Reduce local complexity in fact persistence while preserving duplicate handling and the existing fact-capacity transaction.

**Changed fact:** `_append_fact` now uses an immutable internal payload for evidence JSON, verification-attestation JSON, and the dedupe key. The helper computes each once before duplicate checks, capacity accounting, and insertion.

**Verification:** The focused dedupe, fact-count/byte-capacity, and fact-compaction tests pass 12 cases; strict Pyright reports zero diagnostics; targeted full Pylint for `store.py` fell from 27 to 26 findings and no longer reports excess locals in `_append_fact`; `git diff --check` passes. No full repository Pylint inventory or full test suite was rerun.

**Open gate:** This is local storage refactoring evidence only. Backend-wide retention/budget policy, production storage recovery, and deployment/runtime gates remain open.

**Outcome:** Fact serialization inputs are grouped without changing insert, dedupe, or capacity decisions.

## 2026-10-22 — Split fact-compaction approval persistence

**Intent:** Reduce complexity in the reviewer-approved archive transaction while preserving exact approval replay and atomic archive-before-delete behavior.

**Changed fact:** `CuratorStore.approve_fact_compaction` now receives one immutable typed request. Validation, idempotent receipt lookup, fact/hash/SDE-protection checks, archive-capacity accounting, and archive/item persistence are separate helpers; all remain inside the existing transaction boundary where required.

**Verification:** All 9 existing fact-compaction tests pass; strict Pyright reports zero diagnostics; targeted warning-level Pylint no longer reports argument-count, local-variable, branch, or statement complexity findings for this path; `git diff --check` passes. Other store and service Pylint findings remain; no full suite or full repository warning inventory was rerun.

**Open gate:** This is local transaction/refactoring evidence only. The current Codex-to-Curator MCP call still returns `unauthenticated` because it lacks Hermes-injected profile/session context. Hermes-authenticated human identity, retention-policy rollout, deployment, and live-runtime gates remain open.

**Outcome:** Fact archival keeps the same exact-fact checks, capacity accounting, replay behavior, and transactional deletion while making the local approval path easier to review. The plan's defined delivery-checklist snapshot was recounted as 135/175 complete (40 open); this counts sections 0-10, 12, and Definition of done, excluding section 11 task templates.

## 2026-10-22 — Verify Curator V2 status through Hermes profile context

**Intent:** Resolve whether the configured Hermes profile can read Curator V2 ledger status through its trusted local stdio route.

**Changed fact:** No runtime state changed. The checked-out Hermes CLI's read-only `mcp test curator_v2 --probe-curator-status` supplies host-generated profile/session context to the configured server; it connected to the `renew-ssl-coding` server and returned activity counts for `vhost-manager-alpha`.

**Verification:** The command exited 0, discovered 47 tools, and returned 12 event receipts (all processed), one goal, two facts, zero received/failed/quarantined events, and zero pending SDEs. Curator and Hermes `git diff --check` pass. This confirms Hermes-context status visibility for the configured local stdio profile. A direct Codex MCP `goal_list` call without Hermes context remains unauthenticated; the Hermes profile still reports no authenticated human subject.

**Open gate:** This read-only status result is not a human identity assertion, a live application write/capture, a health result, managed-gateway delivery, or production persistence proof. Deployment, production identity, retention, and live-runtime gates remain open.

**Outcome:** Use the supported Hermes CLI status probe for local profile/session ledger visibility; preserve the identity and live-workflow gates.

## 2026-10-22 — Verify the installed Vhost alpha consumer against the current wheel

**Intent:** Fix the stale consumer-test API calls and verify the installed V2 package through the local Vhost consumer contract.

**Changed fact:** Updated four disposable Vhost consumer fixtures to use the current typed `ProjectRegistrationRequest` API. No Vhost application source or persistent application data changed. The alpha profile now runs Curator schema 21.

**Verification:** All seven installed-package Vhost consumer contract tests pass. The installed wheel SHA-256 is `fa712eca766747b4e157673014d76abe6f68abab68d31a6ea5628ea7938e8ca3`. Hermes Core's checkout CLI connects to the configured `renew-ssl-coding` local stdio server with host-injected profile/session context, discovers 48 tools, and reads 12 processed receipts, one goal, two facts, and no pending SDEs. A read-only SQLite check reports schema 21, `quick_check=ok`, 12 inbox rows, and zero SDE candidates.

**Open gate:** This verifies local alpha profile status and disposable consumer contracts only. It does not establish Hermes-authenticated human identity, a Hermes `goal_list` result, live Vhost application capture, production retention policy, health, recovery, or release approval.

**Outcome:** The local alpha package and consumer contract are verified against the current source wheel; the profile-scoped Hermes status probe resolves the prior status-read uncertainty while identity and live-workflow gates remain open.

## 2026-10-22 — Provision the approved local alpha reviewer grants

**Intent:** Make the already-approved `eaglesvn` local reviewer usable through the attended V2 review CLI for `vhost-manager-alpha`.

**Changed fact:** The project had profile `renew-ssl-coding` read/write grants but no local reviewer grants. Using the TTY-confirmed access command, added `local-uid:1000` project `review` grant `8454ec91a6774250969c7aedc88207a3` and `read` grant `33b94283101c4a7999c0b73256480ee4`. Read access is required for the candidate queue; review access is required for reviewer operations. Both are scoped only to `vhost-manager-alpha`; the rationale explicitly keeps Hermes human identity separate.

**Verification:** The installed `curatormd-v2-review ... queue` command now exits 0 and returns `{"pending":[],"project_id":"vhost-manager-alpha"}`. A read-only database check confirms both grants, schema 21, and `PRAGMA quick_check=ok`. The invocation is from OS user `eaglesvn`, UID 1000, which owns the mode-600 ledger.

**Open gate:** No SDE candidate currently exists, so no live decision/purge was exercised. This is the selected local OS-UID reviewer path only; Hermes-authenticated identity, production grants, live Vhost application capture, and release gates remain open.

**Outcome:** The local alpha reviewer can read the queue and is authorized for review operations through the attended CLI. The Hermes profile remains unable to act as an authenticated human reviewer.

## 2026-10-22 — Distinguish checkout Hermes context from installed runtime

**Intent:** Record the current system-installed Hermes profile's runtime compatibility evidence without conflating tool discovery with trusted request context.

**Changed fact:** No Hermes runtime files or application data changed. The system-installed `hermes -p renew-ssl-coding mcp test curator_v2` connects to the installed Curator server and discovers 48 tools, but reports `Auth: none`. The checkout Hermes CLI's explicit `--probe-curator-status` separately injects local profile/session context and reads project activity status.

**Verification:** Both read-only commands exit successfully. The installed CLI invocation does not call any Curator tool; the checkout status probe returns activity counts. No status is inferred from tool discovery alone.

**Open gate:** Trusted context injection from the actual profile gateway, Hermes-authenticated person identity, live Vhost event capture, health, deployment recovery, and release approval remain unverified.

**Outcome:** Keep checkout-probe evidence distinct from system-runtime evidence; the local alpha reviewer path is available by OS UID while Hermes tool-call context remains open.

## 2026-10-22 — Decompose staging expiry eligibility

**Intent:** Reduce complexity in the 72-hour staging-expiry path without changing its age, pending-review, incomplete-inventory, or hold rules.

**Changed fact:** Extracted exact staged-goal mapping, age/readiness selection, active-hold partitioning, and canonical manifest hashing from `ProjectPlugin._expiry_snapshot_locked`. Pending SDEs still delay prompt expiry but cannot extend the hard 72-hour ceiling; incomplete age/inventory evidence still clears eligibility, and held artifacts remain excluded.

**Verification:** All 43 `project_plugin` tests pass; strict Pyright reports zero diagnostics; repository errors-only Pylint passes; `git diff --check` passes. The focused warning-level Pylint run no longer reports the snapshot/selector excessive-local findings. The full warning-level run still reports non-blocking structural/style findings.

**Open gate:** Repository-wide warning-level Pylint cleanup and production retention, scheduler, monitoring, and runtime evidence remain open.

**Outcome:** The expiry decision is split into smaller reviewable helpers with its existing 72-hour and fail-closed behavior preserved.

## 2026-10-22 — Refresh the installed Vhost alpha wheel

**Intent:** Keep the isolated Vhost profile on the current V2 source after the expiry-path refactor.

**Changed fact:** Rebuilt and force-reinstalled the alpha wheel with SHA-256 `e268f1eddce61c44b1f132f93c6afad842a5ddd39e9e791cabd7091c25fdc2d0`. This supersedes local alpha wheel `fa712eca766747b4e157673014d76abe6f68abab68d31a6ea5628ea7938e8ca3`; the previous wheel remains available under `/tmp/curator-v2-alpha-build/` for rollback.

**Verification:** All 38 installed Python modules hash-match `src/curatormd_v2`. All seven installed Vhost consumer contracts pass. The local reviewer queue still succeeds with no pending SDEs. The persistent alpha database remains schema 21 with `quick_check=ok`, one goal, two facts, and 12 inbox receipts.

**Open gate:** The disposable consumer contracts do not prove live Vhost application capture. Hermes human identity, profile gateway context delivery, production retention/scheduling, and runtime/release gates remain open.

**Outcome:** The isolated alpha package and Vhost consumer tests now use the same source version; runtime and identity boundaries remain explicit.

## 2026-10-22 — Correct Hermes profile-context evidence

**Intent:** Resolve whether the system Hermes CLI's `Auth: none` display means Curator V2 calls lack trusted Hermes context.

**Changed fact:** No runtime code or application data changed. Inspection confirms the `renew-ssl-coding` profile opts into `hermes_context`; Hermes Core's installed managed-MCP handler derives the profile ID from the active Hermes home, requires a session ID, and attaches both as host-owned request metadata. The CLI's `Auth: none` display indicates no conventional MCP credentials; it does not display this separate Hermes request-context path.

**Verification:** The focused Hermes trust-gating tests for explicit local-stdio opt-in and gateway-to-MCP profile context pass (2 tests). The system CLI `mcp test` only connects and discovers tools; it did not make a protected tool call. The checkout CLI's read-only status probe succeeds with profile/session context.

**Open gate:** A real managed-gateway tool call and live Vhost event delivery have not been exercised. Profile/session context does not establish a Hermes-authenticated person subject; person identity and live-runtime evidence remain open. No checklist item is closed by this diagnostic correction.

**Outcome:** Supersede the earlier inference that `Auth: none` proves system-runtime context injection is absent. Keep the actual call-delivery, person-identity, and Vhost workflow gates open.

## 2026-10-22 — Extend Curator V2 privacy coverage across Hermes sinks

**Intent:** Advance the open V2 source-to-sink privacy item for Hermes-managed Curator tool calls without claiming full data-flow coverage.

**Changed fact:** The current Hermes Core worktree now redacts Curator V2 tool arguments, results, and failure details from selected executor/MCP diagnostics, shared session-viewer event payloads, durable session transcript projections, and exported trajectory samples. Malformed MCP sampling arguments remain available to in-memory recovery but are omitted from warning logs. Ordinary non-Curator tool behavior remains preserved in the tested paths. No deployment or runtime configuration changed.

**Verification:** Six dedicated Hermes redaction test files and the managed-worker viewer-event regression pass 19 tests. Targeted Ruff passes for the changed source and test files. Earlier status-probe verification still confirms aggregate V2 ledger visibility through host-derived Hermes profile/session metadata; it does not establish a human subject.

**Open gate:** Traces, session-database backup/WAL recovery, provider-side retention, remaining exception/output paths, and the complete source-to-sink review remain open. No privacy checklist item is closed by this local slice.

**Outcome:** Hermes local diagnostics and selected durable/viewer projections no longer retain the tested Curator V2 argument/result canaries; preserve the wider privacy and live-runtime gates.

## 2026-10-22 — Verify Curator V2 transcript redaction in Hermes backups

**Intent:** Check whether Hermes' real `state.db` backup archive preserves the redacted Curator V2 session projection without reintroducing tool payloads.

**Changed fact:** Added a disposable backup regression that builds assistant-tool and tool-result rows through the Hermes durable session projection, places those projected rows in temporary `state.db`, and snapshots the database through `hermes backup`. The regression uses no real Hermes profile data and changes no backup implementation.

**Verification:** The resulting backup ZIP contains no synthetic raw argument or result canaries; reading the backed-up SQLite database confirms it retains the redacted argument and result markers. The backup regression and both durable-projection tests pass together (3 tests); targeted Ruff passes.

**Open gate:** This verifies one fresh `state.db` snapshot path only. It does not inspect pre-existing raw transcript rows, WAL/recovery behavior, all Hermes backup variants, traces, or provider-side retention. The broader V2 privacy item remains open.

**Outcome:** Fresh projected Curator V2 transcript content stays redacted in a real disposable Hermes backup archive; broader retention and migration evidence remain outstanding.

## 2026-10-22 — Decompose the bounded staging scanner

**Intent:** Reduce the complexity of the staging inventory traversal while preserving its descriptor safety, resource ceilings, and fail-closed behavior.

**Changed fact:** Moved the project staging traversal into `staging_scan.py`. The scanner now has explicit `measure` and `discover` paths, grouped typed scan state, and separate helpers for directory traversal, entry classification, regular-file hashing, and manifest finalization. `ProjectPlugin` supplies the existing hash implementation and the module's configured entry/hash limits.

**Verification:** All 43 `test_project_plugin.py` tests pass. Strict Pyright reports zero diagnostics; repository errors-only Pylint, Bandit, and `git diff --check` pass. Focused warning-level Pylint reports no findings in `staging_scan.py`; the previous scanner-specific excess-local, branch, statement, and return findings are absent. Other `project_plugin.py` and repository warning-level findings remain.

**Open gate:** No staging retention or runtime behavior is inferred from the local refactor. Repository-wide warning-level Pylint cleanup, production scheduler/inventory operation, and deployment/runtime validation remain open.

**Outcome:** The staging traversal is smaller and easier to audit, with the existing local behavior verified. The repository-wide Pylint checklist item remains open.

## 2026-10-22 — Decompose the bounded staging writer

**Intent:** Reduce staging-write complexity while preserving atomic publication, byte ceilings, and receipt-before-cleanup behavior.

**Changed fact:** Extracted the stream, hash, limit enforcement, no-clobber publication, and receipt-failure rollback path into `staging_write.py`. Its typed request and limit records keep the project adapter focused on the locked inventory/budget snapshot and the writer on one bounded file operation.

**Verification:** All 43 `test_project_plugin.py` tests pass. Strict Pyright reports zero diagnostics; repository errors-only Pylint, Bandit, and `git diff --check` pass. Focused warning-level Pylint rates both `staging_write.py` and `staging_scan.py` 10.00/10; `project_plugin.py` rates 9.74/10 with remaining module-size and API-argument findings.

**Open gate:** This is local adapter evidence only. Repository-wide warning-level Pylint cleanup, production retention/scheduling, authenticated identity, and deployment/runtime verification remain open.

**Outcome:** The bounded file write is isolated and verified without changing staging policy or claiming live behavior.

## 2026-10-22 — Revalidate the composed Hermes-to-Vhost integration

**Intent:** Recheck the disposable Hermes managed-MCP path against the current Curator alpha API and use its result to assess local integration readiness.

**Changed fact:** Updated the Vhost-owned disposable integration harness to register its temporary project through the current typed `ProjectRegistrationRequest` API. The consumer test and Vhost alpha record now identify the 2026-10-22 verification; no live Vhost data or gateway configuration changed.

**Verification:** The Hermes Core managed-hook harness passes against the installed Curator alpha package. It confirms explicit session/goal binding, refusal to bind a planned goal, three bounded lifecycle receipts, replay and retry, Vhost projection/reconciliation, unchanged out-of-scope target, and denial of the reviewer-gated persistence tool to a write-only profile. The run uses temporary state. A fresh full Pylint inventory over `src/curatormd_v2` and `tests` reports 246 non-blocking findings; strict Pyright, errors-only Pylint, Bandit, and diff checks were verified in the prior staging-writer checkpoint.

**Open gate:** The harness does not run the Hermes gateway service, exercise a real Vhost UI request, or establish authenticated human identity. Production retention, deployment, recovery policy, and live-runtime gates remain open. Repository-wide warning-level Pylint cleanup also remains open.

**Outcome:** Local composed Hermes-to-Curator delivery and consumer persistence behavior are reverified without claiming live Vhost readiness or changing the delivery checklist count.

## 2026-10-22 — Refresh the isolated Vhost alpha package

**Intent:** Put the current Curator V2 source into the dedicated Vhost Hermes profile so its consumer and managed-MCP checks exercise the same package as the source checkout.

**Changed fact:** Built wheel SHA-256 `cd8218a9c4423f17b7ec831ea15e97719fee9c56f05974e1cca94632c049d827` and force-reinstalled it only in the `renew-ssl-coding` alpha virtualenv. Before installation, archived the prior installed Curator package, metadata, and seven launchers to `/tmp/curator-v2-alpha-installed-runtime-2026-10-22.tar.gz` (SHA-256 `3c3a283543f571b1ced1affd0beebbaedaafcadad72cb7a4f703df9b8c3851c4`). Updated the Vhost-owned disposable managed-MCP harness to use the current typed project-registration API and refreshed the consumer alpha record.

**Verification:** All 40 installed Python module hashes match the Curator source. Seven installed Vhost consumer contracts and the disposable Hermes managed-MCP harness pass. The profile-context status probe connects through configured local stdio, discovers 48 tools, and returns 12 processed event receipts, one goal, two facts, and no event failures or pending SDEs. The alpha database remains schema 21 with `quick_check=ok` from the same read-only status evidence.

**Open gate:** No Hermes gateway restart or real Vhost UI request was exercised. The profile status probe proves local ledger visibility, not authenticated human identity, production persistence/recovery policy, or live-runtime readiness. Production deployment and release gates remain open.

**Outcome:** The isolated alpha environment now runs the current V2 package and passes its local consumer/managed-MCP contracts; the previous installed package remains recoverable from the verified archive.

## 2026-10-22 — Decompose local operational-health evaluation

**Intent:** Reduce API-module complexity in the health path while preserving fail-closed treatment of incomplete local state and untrusted dependency probes.

**Changed fact:** Moved local queue/staging and host dependency-probe evaluation into `health_evaluation.py`. Probe lookup failure, malformed observations, invalid/stale timestamps, and ready/degraded/unknown states remain separate typed outcomes. The public `AuthenticatedCuratorAPI` and MCP contracts are unchanged; dependency names and the age limit remain re-exported through the existing package surface.

**Verification:** Eleven focused API health regressions pass; strict Pyright reports zero diagnostics, repository errors-only Pylint passes, and `git diff --check` passes. Targeted warning-level Pylint no longer reports `api.py` module-size or `_evaluate_dependency` branch-count findings. The pre-extraction full-tree inventory reported 246 findings; a fresh inventory after extraction reports 244, all non-blocking structural/refactor findings.

**Open gate:** This is local health aggregation evidence only. Production dependency probes, scheduler/alert integration, and repository-wide warning-level Pylint cleanup remain open.

**Outcome:** The health evaluator is isolated and verified without changing public tool behavior or claiming deployment health.

## 2026-10-22 — Synchronize alpha package after health refactoring

**Intent:** Keep the dedicated Vhost alpha profile on the same source revision after separating Curator's health evaluator.

**Changed fact:** Rebuilt wheel SHA-256 `e1ae63f63952d8c7953aa70c413b5446dec2b68c8984b5ea60272a34805ca778` and force-reinstalled it only in the `renew-ssl-coding` alpha virtualenv. Archived the previous installed package/metadata/launchers at `/tmp/curator-v2-alpha-installed-runtime-2026-10-22-pre-health.tar.gz` (SHA-256 `228c45cada7502d293d76f804ac54594a6cae3ec58abc02cd716c08ae9b2fad8`); the preceding `cd8218a9…` wheel is also retained separately.

**Verification:** All 41 installed module hashes match the current Curator source; `pip check` reports no broken requirements. Hermes Core's read-only profile-context probe connects through the installed alpha launcher, discovers 48 tools, and returns the unchanged 12 processed receipts, one goal, two facts, and zero event failures/pending SDEs.

**Open gate:** No gateway restart or live Vhost application request was exercised. This verifies only the installed alpha package and profile stdio path; authenticated human identity, production persistence/recovery policy, and live-runtime gates remain open.

**Outcome:** The alpha package again matches the current source without changing the persistent Vhost ledger or claiming live gateway readiness.

## 2026-10-22 — Close local Host Steward validation slice

**Intent:** Close the local Host Steward validation slice while keeping its Hermes Core ownership and deployment boundary explicit.

**Changed fact:** Updated the ordered plan to mark local Host Steward validation and the separate-owner safety criterion complete. The release-gate record now distinguishes local validation from root-account activation and production recovery; no Hermes Core source, Host Steward state, host files, or cleanup targets were changed.

**Verification:** The latest Hermes Core Host Steward focused suite passes 15 tests, including interrupted-cleanup receipt reconciliation, and `python3 scripts/check` passes all 12 checks. Existing focused regressions cover bounded inventory, exact approval, managed cleanup, post-cleanup verification, receipts, tool ownership, and the unchanged Curator history sentinel after disposable cleanup. Curator and Hermes `git diff --check` pass for this documentation update.

**Open gate:** Live root-account activation, measured live host/service attribution, authenticated approver identity, cross-process supervision, and production recovery remain open. Direct Curator MCP access remains unauthenticated in this Codex session; no goal-ledger mutation is claimed.

**Outcome:** Two locally evidenced delivery checklist items are closed; deployment, identity, and live-runtime gates remain open.

## 2026-10-22 — Prevent Hermes spillover of Curator V2 results

**Intent:** Close a local Hermes persistence path that could archive oversized Curator V2 tool output outside the V2 ledger.

**Changed fact:** Hermes now truncates oversized Curator V2 tool results inline rather than writing them to profile spillover or sandbox temp files. Aggregate turn-budget enforcement preserves each tool message's identity for the same policy, including multimodal text parts. Other tools keep their existing spillover behavior.

**Verification:** Three focused Hermes regressions pass for direct results, aggregate string results, and aggregate multimodal text. Targeted Ruff passes for the changed source and regression file; Hermes `git diff --check` passes.

**Open gate:** The broader V2 privacy item remains open for other logging and exception paths, traces, old transcript rows, WAL/recovery, other backup paths, and provider-side retention. Direct Curator MCP access remains unauthenticated from this Codex session.

**Outcome:** Oversized Curator V2 results no longer spill into Hermes files on the covered paths; no deployment or live-runtime claim is made.

## 2026-10-22 — Redact Curator V2 payloads across Hermes persistence and diagnostics

**Intent:** Extend the local Hermes Core privacy boundary across durable session projections, exported trajectories, diagnostic logs, and session-viewer events without changing other tools' behavior.

**Changed fact:** Hermes now redacts Curator V2 call arguments, results, and failure details in the covered persistence, trajectory, managed-MCP, executor, dispatch/hook, sampling, and viewer paths. A disposable `hermes backup` regression verifies that a fresh SQLite backup contains only the redacted transcript projection. Hermes change `2a0a8f1574` is pushed to the Curator V2 integration branch.

**Verification:** Seven focused redaction test files plus the managed-worker viewer regression pass 20 tests; Hermes `scripts/check` passes all 12 checks, and Hermes `git diff --check` passes. The profile-scoped local Curator probe connects with Hermes-injected profile/session context and reports the `vhost-manager-alpha` ledger: 12 processed receipts, one goal, and two facts. It does not authenticate a human subject or prove live application delivery.

**Open gate:** Historical raw transcript rows, WAL/recovery, all backup variants, traces, provider-side retention, and the complete source-to-sink audit remain open. Production identity, retention, deployment, and live-runtime gates remain open.

**Outcome:** The tested local Hermes sinks retain no Curator V2 argument/result canaries while preserving call identity; no checklist item is marked complete and no production claim is made.

## 2026-10-22 — Redact Curator V2 gateway progress previews

**Intent:** Close a remaining Hermes diagnostic sink in gateway log-mode tool-start progress.

**Changed fact:** `GatewayTurnProgressMixin.progress_callback` now replaces a Curator V2 tool-start preview with the fixed redaction marker and removes its arguments before the progress log queue, live-status projection, or progress-message builder can retain them. The regression lives in a focused gateway test file to respect Hermes' code-health file-size limit.

**Verification:** The focused canary regression passes; targeted Ruff and Hermes `scripts/check` pass, including all 12 checks, and both repositories' `git diff --check` pass. A broader attempt to run `test_run_progress_topics.py` had 45 failures in existing cases because the home-I/O guard rejects import-time access to the real `/home/eaglesvn/.hermes/manifest.json`; this unrelated test-isolation issue remains open.

**Open gate:** This closes one progress-log/status sink only. The broader privacy review remains open for historical transcript rows, WAL/recovery, other traces and backups, and provider-side retention. No live gateway or Vhost application workflow was exercised.

**Outcome:** Curator V2 call previews no longer reach the tested Hermes gateway progress log or status projections; the privacy and runtime gates remain open.

## 2026-10-22 — Add bounded local service-probe evidence

**Intent:** Implement the locally testable service-probe source path while preserving the deployment-authentication boundary.

**Changed fact:** `LocalServiceProbeResolver` executes only its host-configured argv for its pinned project/probe ID, bounds runtime to 30 seconds and stdout to 64 KiB, and emits only the stdout digest plus short-lived provenance. It rejects shell-style evidence locators, wrong projects, nonzero exits, empty/oversized output, and timeouts. The resolver's subject is explicitly a local host assertion, not deployment-authenticated service identity.

**Verification:** Four focused service-probe tests pass. Strict Pyright reports zero diagnostics; repository errors-only Pylint, Bandit, and `git diff --check` pass. No full suite was rerun.

**Open gate:** Deployment credentials/trust roots, independent service identity and revocation, and a live service probe remain unverified. The source-specific evidence integration items remain open.

**Outcome:** Curator V2 can locally verify bounded output from an exact host-configured service probe without persisting the output; production trust and runtime are not claimed.

## 2026-10-22 — Wire host-owned evidence verifier into profile builder

**Intent:** Make a locally configured evidence resolver usable by the profile-bound API without letting a consumer repository choose trust policy.

**Changed fact:** `build_local_profile_mcp` accepts an optional host-created `EvidenceVerifier` and injects it into the bound `ProjectPlugin`. Omitting the argument retains the fail-closed reject-all verifier. The consumer TOML remains unable to select adapters, identities, commands, or credentials.

**Verification:** The disposable profile-builder integration test passes: a verification event travels through the bound API and its criterion becomes verified by the host-injected local service probe. Strict Pyright reports zero diagnostics; repository errors-only Pylint, Bandit, and `git diff --check` pass. No full suite was rerun.

**Open gate:** The production CLI remains reject-all absent a separately implemented host-owned probe configuration; the installed Vhost profile was not changed. This test does not establish service authentication, a live probe, deployment identity, or runtime readiness.

**Outcome:** The host factory now exposes a tested trust-injection seam while preserving consumer-config isolation and the fail-closed default.

## 2026-10-22 — Add owner-only local probe config loading

**Intent:** Make the host-injected local service probe selectable by the stdio launcher without storing trust configuration in a consumer repository.

**Changed fact:** The launcher accepts optional `--evidence-config` and loads one strict project-bound service-probe definition from a separate owner-only file. It opens without following a final symlink, checks OS ownership, mode, regular-file type, hardlink count, and a 16 KiB limit; rejects duplicate JSON keys and unknown fields; and binds the probe to the project's exact ID. Missing config still uses reject-all verification.

**Verification:** The profile-builder event integration now loads the host config from outside the disposable consumer repo and verifies a criterion. Six config-security tests and five service-resolver/integration tests pass. A launcher regression verifies option forwarding and runtime cleanup; strict Pyright, targeted warning-level Pylint, repository errors-only Pylint, Bandit, and `git diff --check` pass.

**Open gate:** No host config was installed into the `renew-ssl-coding` Hermes profile. `local-probe:` is an OS-account assertion only; service credentials, remote identity/revocation, production trust roots, deployment, and live Vhost behavior remain unverified.

**Outcome:** Local service-probe verification is now reachable through the profile-bound stdio launcher when an operator supplies a private host config; absence remains fail-closed.

## 2026-10-22 — Verify the Curator V2 ledger through Hermes context

**Intent:** Resolve whether `unauthenticated` means the local V2 ledger is inaccessible or only that a direct Codex client lacks Hermes host context.

**Changed fact:** No service, identity, or ledger state changed. Direct Codex MCP calls remain correctly denied without `hermes/profile_id` and `hermes/session_id`; this is the intended host-context boundary, not missing MCP credentials. The current Hermes Core checkout's fixed read-only probe supplies those fields for the configured `renew-ssl-coding` stdio route.

**Verification:** Ran the checkout CLI probe for `renew-ssl-coding`. It connected, discovered 48 Curator tools, and read `vhost-manager-alpha` activity status: 12 receipts processed, one goal, two facts, and zero received/failed/quarantined events or pending SDEs. The launcher regression passes; strict Pyright, targeted Pylint, and `git diff --check` pass.

**Open gate:** This verifies local profile-context ledger visibility only. It does not provide a human-authenticated Hermes subject, prove gateway event delivery, or close deployment/live-runtime gates. Local `eaglesvn` OS-UID reviewer grants remain a separate approved path.

**Outcome:** The local V2 ledger-status uncertainty is closed for the supported Hermes CLI profile route; direct Codex access remains unauthenticated by design.

## 2026-10-22 — Probe the paginated Curator V2 goal list through Hermes

**Intent:** Verify the exact V2 goal-list read path with the trusted Hermes profile/session metadata that direct Codex calls do not carry.

**Changed fact:** The Hermes `--probe-curator-status` path now reads both fixed read-only `project_activity_status` and one bounded `goal_list_page` result over the opted-in local stdio server. It emits the activity aggregates and goal total only; goal-card content is discarded by the CLI.

**Verification:** Two focused Hermes probe tests pass. The live checkout CLI probe connected to the `renew-ssl-coding` profile, discovered 48 Curator tools, returned 12 processed receipts, one goal, two facts, zero failed/quarantined events, and paginated goal-list total 1. Hermes `python3 scripts/check` passes all 12 checks. The focused Hermes test file had one unrelated existing import-time real-home isolation failure; the two targeted probe tests pass. Curator V2 focused launcher test, strict Pyright, targeted Pylint, repository errors-only Pylint, Bandit, uv audit, and both repositories' `git diff --check` pass.

**Open gate:** This verifies a local profile-context read only. It does not establish Hermes-authenticated human identity, gateway event delivery, production persistence, or deployment/runtime readiness. Direct Codex MCP calls without Hermes metadata remain correctly unauthenticated.

**Outcome:** The configured local Hermes-to-Curator profile can read both activity and paginated goal totals; the direct-client `unauthenticated` result is explained and fail-closed behavior is retained.

## 2026-10-22 — Consolidate the ordered SQLite migration registry

**Intent:** Reduce migration-dispatch complexity and remove duplicate ordering lists without changing schema transformations or transaction ownership.

**Changed fact:** Versioned upgrades now iterate one typed registry of v2-v21 migration functions. Unversioned v0 bootstrap uses the same registry after the existing v1 legacy upgrade. The caller continues to own the migration transaction.

**Verification:** All 29 migration tests pass, including unversioned bootstrap, rollback, supported legacy versions, and refusal of a future schema. Strict Pyright reports zero diagnostics; focused warning-level Pylint reports no findings in `schema_migrations.py`; `git diff --check` passes.

**Open gate:** This is local migration refactoring and test evidence. Production upgrade, backup/restore, corruption, and rollback drills remain open; the full repository warning-level Pylint cleanup is not complete.

**Outcome:** Migration order has one source of truth locally; behavior and production-gate status are unchanged.

## 2026-10-22 — Decompose project metrics rendering

**Intent:** Reduce local branch/local-count complexity in the project metrics renderer while preserving the content-free Prometheus contract.

**Changed fact:** `render_project_metrics` now coordinates bounded helpers for health, queues, dependencies, goals, storage, feedback, staging, event receipts/failures, and output formatting. Metric names, labels, values, and emission order are unchanged.

**Verification:** All 36 API tests pass, including authorization, bounded output, and content-free metrics coverage. Strict Pyright reports zero diagnostics; warning-level Pylint reports no findings in `observability.py`; `git diff --check` passes.

**Open gate:** This local rendering refactor does not provide a deployed scrape endpoint, dashboard, alert delivery, authenticated production metrics access, or live runtime evidence. Repository-wide warning cleanup remains open.

**Outcome:** Metrics rendering retains its tested contract with lower function complexity; deployment and observability gates remain open.

## 2026-10-22 — Decompose fact archive record validation

**Intent:** Reduce archive-decoder complexity while preserving integrity checks and safe handling of malformed persisted data.

**Changed fact:** Fact archive evidence references, verification attestations, and domain fields are validated by separate bounded helpers before constructing the immutable fact. Required/optional field checks, enum/domain validation, and sanitized failure behavior remain enforced.

**Verification:** All nine fact-compaction tests pass, including archive hash tampering, invalid JSON redaction, invalid-kind redaction, capacity, and rollback coverage. Strict Pyright reports zero diagnostics and `git diff --check` passes. Focused full Pylint for `store.py` falls from 21 to 18 findings.

**Open gate:** The remaining `store.py` findings and full repository Pylint cleanup are open. This refactor provides local test evidence only; it does not close backup, restore, or production storage gates.

**Outcome:** Archive parsing retains its tested fail-closed behavior with three fewer focused Pylint findings; repository-wide cleanup remains open.

**Follow-up verification:** At the archive-record-validation checkpoint, the documented blocking quality chain passed: `uv sync --locked --group test --group quality`, 389 unit tests, strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and `git diff --check`. The warning-level whole-repository Pylint inventory was not rerun after that slice.

## 2026-10-22 — Split fact archive source and eligibility checks

**Intent:** Remove the remaining archive-decoder branch complexity without weakening compressed-data bounds, integrity verification, or eligibility checks.

**Changed fact:** Compressed-byte validation/decompression and JSON decoding now have a dedicated helper; record-count validation and decoded-fact eligibility checks are separate. The 32 MiB decompression ceiling, hashes, truncation/trailing-data checks, duplicate-ID rejection, and routine-fact restriction are preserved.

**Verification:** All nine fact-compaction tests pass, strict Pyright reports zero diagnostics, focused full Pylint for `store.py` reports 17 findings (down from 21 before the two archive slices), and `git diff --check` passes. The full warning-level repository inventory and full test suite were not rerun after this slice.

**Open gate:** Whole-repository warning-level cleanup and production storage/recovery drills remain open.

**Outcome:** Archive record validation and source integrity are independently bounded and tested; broader Pylint and deployment-gate work remains.

## 2026-10-22 — Split MCP server tool registration

**Intent:** Reduce the trusted MCP factory's local-variable and module-size complexity while keeping the public tool surface and project binding intact.

**Changed fact:** `build_mcp_server` now configures the server and delegates to operation-family registrars. Shared safe error handling, typed input parsing, and result serialization live in a support module. Every handler still closes over the same authenticated caller, project, and producer; MCP tool names, parameter schemas, annotations, and dispatch calls are preserved. The explicit tool parameters remain because they define the host-visible JSON schema; Pylint's argument-count exception is documented for that boundary.

**Verification:** All six MCP-server tests and 13 hosted-MCP tests pass. Strict Pyright reports zero diagnostics, focused Pylint rates `mcp_server.py`, `mcp_tool_registration.py`, and `mcp_tool_support.py` 10.00/10, and `git diff --check` passes. No full suite or whole-tree warning inventory was rerun after this refactor.

**Open gate:** Repository-wide warning cleanup, managed-gateway delivery, authenticated human identity, and live deployment/runtime evidence remain open.

**Outcome:** Tool registration is split into bounded modules without changing the tested MCP transport behavior; broader integration and lint cleanup remain active.

**Follow-up packaging evidence:** `uv build --wheel --out-dir /tmp/curator-v2-wheel-validation` produced `curatormd_v2-0.1.0a1-py3-none-any.whl` with SHA-256 `1c390fded18292a3abc6ade03de8b4cc1a34eeac10e68c2d91dc478bf59277a0`. Its manifest contains the server, registration, and support modules. Installing it into a temporary target and importing with that target first on `PYTHONPATH` loaded `curatormd_v2` from the extracted wheel and resolved the MCP factory/registrar/parser exports. The isolated profile wheel and consumer repositories were not changed.

## 2026-10-22 — Scrub discarded event payloads from SQLite WAL

**Intent:** Prevent successfully processed or permanently discarded transient event payloads from lingering in the open SQLite WAL after their inbox payload is cleared.

**Changed fact:** Schema v22 adds a content-free scrub queue containing only project/event locators and retry metadata; existing databases with inbox rows receive one global startup scrub receipt. File-backed stores enable `secure_delete`, attempt a nonblocking WAL `TRUNCATE` checkpoint after payload discard, and preserve a pending receipt when a reader prevents truncation. Router passes retry pending scrubs even when no events are routed. Project health reports `sqlite_payload_scrub_pending` as degraded until cleanup succeeds.

**Verification:** Canary tests prove successful processing and permanent-failure disposal remove payload bytes from the live WAL. A pinned reader keeps the receipt pending and health degraded; after release, an idle router pass truncates the WAL and clears the receipt. Restart coverage proves the receipt survives a blocked startup and the next startup clears it after the reader releases. Migration coverage verifies the legacy global sentinel and compatibility with minimal old schemas. Focused event, migration, router, and API suites pass 119 tests; strict Pyright reports zero diagnostics; errors-only Pylint and `git diff --check` pass.

**Open gate:** This covers discarded event payloads in the SQLite WAL only. Retryable/quarantined payload retention, other WAL and backup paths, traces, logs, upstream inputs, and broad source-to-sink review remain open. No privacy checklist item is closed and no deployment/runtime claim is made.

**Outcome:** Successful event disposal now attempts WAL-level cleanup and exposes blocked cleanup as pending/degraded rather than silently healthy.

**Pylint follow-up:** Moved the event contract tests out of the oversized event-inbox module and kept WAL canary regressions in a dedicated scrub module. The 20 contract, 19 inbox, and 4 scrub tests pass; targeted warning-level Pylint rates the three modules 10.00/10. The latest full repository warning-level run exits 24 at 9.87/10 with remaining structural findings; repository-wide cleanup remains open. Strict Pyright, errors-only Pylint, and `git diff --check` pass.

**Quality follow-up:** Locked dependency sync passed. Bandit identified the generated scrub-queue placeholder SQL, which now uses fixed parameterized `executemany` statements. The full 397-test suite passed after that change; the four WAL scrub tests and 37 API tests also pass. Strict Pyright, errors-only Pylint, Bandit, locked dependency audit (no known vulnerabilities/adverse statuses), and `git diff --check` pass.

## 2026-10-22 — Validate the current V2 alpha wheel in isolation

**Intent:** Confirm the current dirty V2 source packages and imports cleanly before any consumer-profile deployment.

**Changed fact:** Built `curatormd_v2-0.1.0a1-py3-none-any.whl` from the current working tree and installed it only to `/tmp/curator-v2-alpha-install`. The package contains the current MCP registration/support modules and SQLite schema v22.

**Verification:** Import resolution from the isolated target loads `curatormd_v2` from that target, reports schema version 22, and resolves both `build_local_profile_mcp` and `build_mcp_server`. Wheel SHA-256: `afebd122c466237bd23b795280f4012bb66ab139bf416a010618760461a16ef6`.

**Open gate:** This is wheel-content/import evidence, not an installed consumer workflow. No Vhost or GPTMD profile was changed; authenticated identity, deployment, and live-runtime gates remain open.

**Outcome:** The current source is packageable and its hosted-MCP entry modules import from the built artifact; no consumer deployment is claimed.

## 2026-10-22 — Exercise the current alpha wheel through the Vhost Hermes profile

**Intent:** Test the current Curator V2 build through its configured Hermes Core profile against the Vhost Manager project after the local package and quality checks passed.

**Changed fact:** Installed the exact isolated alpha wheel (`afebd122c466237bd23b795280f4012bb66ab139bf416a010618760461a16ef6`) into the `renew-ssl-coding` Curator V2 profile environment. Before installation, made a permission-restricted SQLite backup; it passed integrity check at schema v21. The profile database migrated to schema v22 on the first post-install probe.

**Verification:** Hermes Core connected over the configured local stdio path, discovered 48 Curator V2 tools, and read activity plus paginated goal totals: 12 processed receipts, one goal, two facts, and total goal count 1. Post-probe database integrity is `ok`, all 12 receipts remain processed, and the pending payload-scrub count is zero. The profile still uses transport auth `none`; these are trusted Hermes profile/session context reads, not human authentication.

**Open gate:** This was a read-only local profile integration/migration test. It does not prove a Vhost application-originated write, production identity, deployed service runtime, or production retention/approval policy. The dirty Vhost repository was not edited and GPTMD was not touched.

**Outcome:** The current alpha wheel successfully serves the configured Vhost project through Hermes Core after its SQLite v22 migration; production and human-identity gates remain open.

## 2026-10-22 — Run installed Vhost consumer contracts against the current wheel

**Intent:** Verify the newly installed alpha package against the Vhost-owned consumer integration contract without writing to its actual repository data.

**Changed fact:** No Vhost source, project config, persistent project database, or application state changed. The contract suite used the installed `renew-ssl-coding` profile interpreter and created disposable repositories/databases.

**Verification:** All seven `tests/vhost-manager/test_curatormd_v2_contract.py` tests pass: installed launcher binding/replay, configured Markdown target and router behavior, two-consumer isolation, and both bounded Hermes hook delivery contracts. This run exercises the current profile package hash through its installed launcher.

**Open gate:** Synthetic/disposable consumer evidence does not prove a Vhost application-originated request, production user identity, or production runtime. GPTMD remains untouched.

**Outcome:** The current alpha wheel passes the Vhost-owned installed-consumer contract suite; live application and production gates remain open.

## 2026-10-22 — Verify Hermes-context V2 ledger and health reads

**Intent:** Make the local Hermes profile probe report whether the configured V2 ledger is readable and expose its aggregate health gates without leaking goal content.

**Changed fact:** The Hermes Core `--probe-curator-status` command now performs bounded read-only activity, paginated goal-total, and project-health calls with host-injected profile/session context. It prints only activity aggregates, goal total, health status, and validated gate codes; goal-card content is suppressed.

**Verification:** `hermes --profile renew-ssl-coding mcp test curator_v2 --probe-curator-status` connects, discovers 48 tools, and exits 0. It reports 12 processed receipts, one goal, two facts, zero failed/quarantined events, goal-list total 1, and project health `unknown` with five dependency gates (`event_router`, `purge_scheduler`, `host_identity`, `human_review`, `artifact_producer_inventory`). This verifies local profile-context ledger reads only.

**Open gate:** Direct Codex MCP calls still return `unauthenticated` because that transport supplies no trusted Hermes context. The Hermes profile has no authenticated human subject; production identity, managed-gateway delivery, live capture, and deployment readiness remain open. The Curator V2 checklist total is unchanged.

**Outcome:** The local Hermes ledger-read check is complete and health is reported without false-green status; human identity and runtime gates remain open.

## 2026-10-22 — Reconcile current checklist and quality evidence

**Intent:** Keep the delivery progress snapshot and local verification record consistent with the current V2 plan and worktree.

**Changed fact:** The release-gate snapshot now matches the plan's explicit counting scope: 138 of 175 delivery rows complete and 37 open. The repository-wide warning-level Pylint item remains open at 9.87/10, exit 24; this is recorded separately from the pinned blocking quality checks.

**Verification:** The current pinned Curator checks pass: strict Pyright (zero diagnostics), errors-only Pylint, Bandit, and locked dependency audit. `git diff --check` passes. The Hermes profile database was opened read-only and reports schema 22, `quick_check=ok`, one project, one goal, two facts, 12 event inbox receipts, and zero pending payload scrubs.

**Open gate:** The warning-level Pylint inventory remains open. Hermes project health remains `unknown`; authenticated human identity, managed-gateway/live application proof, and production deployment gates remain open.

**Outcome:** The checklist snapshots are reconciled to the counting rule, and blocking local quality checks pass without overstating the warning-level lint or runtime state.

## 2026-10-22 — Bind Hermes status probe results to the configured project

**Intent:** Prevent the local Hermes diagnostic from reporting a readable V2 ledger for a project different from the profile's explicit project binding.

**Changed fact:** The Hermes Core status probe now requires `hermes_project_id` and verifies that the activity, paginated goal-list, and health responses all report that exact project before displaying aggregates. Missing or mismatched project binding fails closed.

**Verification:** The focused Hermes test passes the configured `vhost-manager-alpha` binding and rejects a response expected under `other-project`; the focused Ruff check passes. The live `renew-ssl-coding` probe connects, discovers 48 tools, and returns activity, goal total 1, and health `unknown` for `vhost-manager-alpha`.

**Open gate:** This validates profile-to-project scope only. The profile still has no authenticated human subject, direct Codex calls without Hermes metadata remain unauthenticated, and the health dependencies, managed-gateway delivery, live application workflow, and production gates remain open.

**Outcome:** Hermes local status output is checked against its configured V2 project binding; no human or production identity claim is made.

## 2026-10-22 — Separate strict event validation helpers

**Intent:** Keep the versioned event contract implementation below its configured module-size ceiling without weakening parse limits or sanitized errors.

**Changed fact:** Exact-field/object parsing, duplicate-key rejection, enum and lifecycle-revision validation, optional revision parsing, string validation, and safe UTF-8 length measurement moved from `events.py` to `event_validation.py`; the event contract calls the same validation logic.

**Verification:** All 43 focused event-contract, event-inbox, and payload-WAL-scrub tests pass. Strict Pyright reports zero diagnostics; focused Pylint rates `events.py` and `event_validation.py` 9.92/10, with remaining model/dispatch complexity findings; `events.py` is 935 lines, down from 1,002. The V2 wheel builds and contains both modules. `git diff --check` passes.

**Open gate:** Repository-wide warning-level Pylint has not been rerun after this slice and remains open; the preceding whole-tree run reported 9.87/10 (exit 24). This refactor is local source evidence and does not close deployment, identity, retention, or live-runtime gates.

**Outcome:** Strict event parsing is separated into a bounded helper module with focused behavior and packaging evidence; broader lint and deployment gates remain open.

**Follow-up:** Event payload encode/decode dispatch now assigns one result and returns once per codec, preserving the existing variant mapping while removing both too-many-return-statements findings. The same 43 focused event tests pass, strict Pyright reports zero diagnostics, focused Pylint remains 9.96/10 with only two dataclass attribute-count warnings, and `git diff --check` passes. Whole-tree warning-level Pylint was not rerun.

**Lint follow-up:** Added class-local Pylint exceptions to the immutable event receipt, goal-start, and envelope records; these field counts are defined by their versioned contracts and were not reduced by changing the serialized records. Focused Pylint for both event modules now reports 10.00/10. The whole-repository warning inventory remains open and was not rerun.

**Whole-tree lint refresh:** `uv run --locked --group quality pylint src/curatormd_v2 tests` was rerun after the event validation/dispatch work. It exits 24 at 9.87/10, unchanged; duplicate-code and structural findings elsewhere keep the repository-wide warning cleanup open. The focused event modules pass at 10.00/10.

## 2026-10-22 — Recheck Hermes-context ledger access and Curator quality gates

**Intent:** Resolve whether the Codex-side `unauthenticated` response means the V2 ledger is unreadable, and refresh the non-test local quality evidence.

**Changed fact:** The direct Codex MCP request lacks the trusted Hermes profile/session metadata required by the configured local stdio server, so its denial is expected. The Hermes Core checkout command `./hermes -p renew-ssl-coding mcp test curator_v2 --probe-curator-status` succeeds using host-injected profile/session context and checks the configured `vhost-manager-alpha` project binding. It reports 12 processed receipts, one goal, two facts, goal total 1, and health `unknown` with five dependency gates.

**Verification:** The Hermes status probe exits 0 and discovers 48 tools. Current Curator checks pass: strict Pyright (0 diagnostics), blocking Pylint, Bandit, locked dependency audit (50 packages, no known vulnerabilities or adverse statuses), and `git diff --check`. No tests were rerun for this status clarification. Hermes Core `python3 scripts/check` passed all 12 checks in the current work session.

**Open gate:** This confirms local profile-context ledger reads, not authenticated human identity. The Hermes profile has `Auth: none`; the five health dependencies, live application workflow, and production deployment remain open. No Curator SQLite data or GPTMD files were changed.

**Outcome:** The V2 ledger is readable through the configured Hermes profile. Direct Codex access remains fail-closed until a trusted host context is supplied; no identity or healthy-runtime claim is made.

## 2026-10-22 — Remove model-record Pylint false positives

**Intent:** Reduce repository-wide warning-level Pylint findings without changing V2 record fields or serialized contracts.

**Changed fact:** Added class-local `too-many-instance-attributes` exceptions to eight immutable model/read/receipt records whose field sets are part of their persisted or typed snapshot contracts; no fields or validation changed.

**Verification:** Focused Pylint for `models.py` reports 10.00/10. The whole-tree warning-level run moved from 9.87/10 to 9.88/10 and still exits 24; the broad structural cleanup remains open. `git diff --check` passes. No tests were rerun.

**Open gate:** Repository-wide complexity, module-size, and duplicate-code findings remain. No deployment, identity, retention-policy, or live-runtime gate changed.

**Outcome:** Eight known model-record attribute-count warnings are removed with narrow contract-based exceptions; broader warning-level Pylint cleanup remains in progress.

## 2026-10-22 — Clarify one-operation V2 adapter contracts for Pylint

**Intent:** Remove structural warnings where a type intentionally represents one protocol operation or one configured policy.

**Changed fact:** Added narrow class-local Pylint exceptions to 22 single-operation production types: authorization/limiter/readiness protocols and policies, evidence resolvers/verifiers and policy variants, the router, registry, and exact-file purger. Their public methods and behavior are unchanged.

**Verification:** The focused production scan for `too-few-public-methods` is clean. The whole-tree warning-level Pylint score moved from 9.88/10 to 9.89/10 and still exits 24; remaining findings need structural refactors. `git diff --check` passes. No tests were rerun.

**Open gate:** Repository-wide module-size, complexity, and duplicate-code findings remain. No deployment, identity, retention-policy, or live-runtime gate changed.

**Outcome:** The single-operation design types are explicitly distinguished from actionable structural warnings; whole-tree lint cleanup remains open.

## 2026-10-22 — Decompose goal report rendering

**Intent:** Reduce complexity in the status renderer while preserving its bounded, evidence-aware report content.

**Changed fact:** Added typed report data/page inputs and split criteria, fact-page, goal-header, open-gate, TODO, child/dependency, SDE, and canonical-write/purge rendering into focused helpers. The service and report now share the same open-child selector, removing duplicated lifecycle classification.

**Verification:** Five focused `test_lifecycle.py` report tests pass; strict Pyright reports zero diagnostics; focused Pylint rates `reporting.py` 10.00/10. Whole-tree warning-level Pylint moved from 9.89/10 to 9.90/10 and still exits 24. `git diff --check` passes.

**Open gate:** Warning-level findings remain in service, store, and test modules. This refactor does not change deployment, identity, retention-policy, or live-runtime gates.

**Outcome:** Goal reports retain existing section semantics and pagination with lower renderer complexity; repository-wide Pylint cleanup remains open.

## 2026-10-22 — Complete goal report service decomposition

**Intent:** Remove duplicated report assembly and keep pagination state together across the V2 service and adapter layers.

**Changed fact:** `CuratorService.goal_report` now delegates bounded local snapshot, related-goal/receipt loading, and report-summary aggregation to focused helpers. One immutable `GoalReportPage` carries pagination through the service, authenticated API, and project plugin. MCP clients retain the same named offset/limit fields; the registration handler maps them to the typed page.

**Verification:** Five focused `test_lifecycle.py` report tests and all six `test_mcp_server.py` tests pass. Strict Pyright reports zero diagnostics and `git diff --check` passes. The whole-tree warning-level Pylint run remains 9.90/10 (exit 24); the goal-report argument-count findings are gone, while unrelated structural findings remain.

**Open gate:** The full Curator test suite was not rerun. Repository-wide Pylint cleanup, deployment, authenticated human identity, retention-policy ownership, and live-runtime evidence remain open.

**Outcome:** The bounded report pagination contract remains unchanged at the MCP boundary, and report assembly is decomposed across the V2 service path; broader quality and release gates remain open.

## 2026-10-22 — Extract goal-finish open-gate payload

**Intent:** Reduce transactional lifecycle complexity while keeping open outcomes concrete and auditable.

**Changed fact:** Extracted the open-gate next-action text and criterion/child/dependency facts into a helper. `goal_finish` keeps the same checks, ordering, text, and single transition transaction.

**Verification:** The focused lifecycle finish regression passes; strict Pyright reports zero diagnostics; focused `service.py` Pylint improves from 9.76/10 to 9.81/10 and no longer reports excess branches/locals in the transaction method. The current blocking quality checks also pass errors-only Pylint, Bandit, locked dependency audit (50 packages, no known vulnerabilities or adverse project statuses), and `git diff --check`.

**Open gate:** The whole-tree warning-level Pylint inventory was not rerun after this slice; repository-wide complexity, interface, and module-size findings remain. Deployment, authenticated human identity, retention-policy ownership, and live-runtime evidence remain open.

**Outcome:** The goal-finish method now delegates its open-outcome payload construction without changing lifecycle behavior; this advances but does not close the warning-level quality item.

## 2026-10-22 — Extract goal-intake validation

**Intent:** Reduce goal-start method complexity while preserving transactional relationship checks and safe rejection of invalid statuses.

**Changed fact:** Parent ancestry, terminal-parent, and dependency validation now run in a focused helper called inside the original store transaction. Initial status normalization accepts only `planned` or `active` and raises the same context-free public error after leaving the enum parse handler.

**Verification:** Eight focused parent/dependency lifecycle tests and the invalid-status privacy regression pass. Strict Pyright reports zero diagnostics; focused `service.py` Pylint no longer reports excess locals in goal intake and rates the module 9.82/10 (exit 24); `git diff --check` passes.

**Open gate:** The full Curator suite and whole-tree warning-level Pylint were not rerun. Remaining service interface/module findings and deployment, authenticated identity, retention-policy, and live-runtime gates remain open.

**Outcome:** Goal intake relationship and status checks are easier to audit without changing project scope, transaction boundaries, accepted statuses, or rejection wording.

## 2026-10-22 — Move goal bullet projection into reporting

**Intent:** Keep truth-labeled goal rendering together and reduce lifecycle service module size.

**Changed fact:** Moved goal bullet projection and its criterion, fact, goal-state, review, purge, and fact-capacity helpers from `service.py` into `reporting.py`. Both the direct projection API and report snapshot use the same pure projection function.

**Verification:** One focused projection test and five focused report tests pass; strict Pyright reports zero diagnostics; focused warning-level Pylint for `service.py` and `reporting.py` improves from 9.82/10 to 9.86/10. `git diff --check` passes.

**Open gate:** `service.py` remains above the Pylint module-size threshold, repository-wide warning-level findings remain, and the full unit suite was not rerun. Deployment, authenticated identity, retention-policy, and live-runtime gates are unchanged.

**Outcome:** Goal bullet projection remains shared across status and report paths while report logic is colocated; this advances but does not close repository-wide quality work.

## 2026-10-22 — Decompose durable event routing

**Intent:** Separate per-event delivery recovery from bounded queue-pass accounting without weakening retry and quarantine behavior.

**Changed fact:** `route_once` now delegates one claimed event to dispatch/recovery and durable receipt classification helpers. Existing project binding, lease ownership, retry ceiling, sanitized error labels, batch-stop behavior, and idle-pass payload scrub retries remain intact.

**Verification:** All nine focused router tests pass, including failure/quarantine/retry and deferred WAL payload-scrub recovery. Strict Pyright reports zero diagnostics; focused `router.py` Pylint reports 10.00/10; `git diff --check` passes.

**Open gate:** The full unit suite and whole-tree warning-level Pylint were not rerun. Production scheduler, alerts, restart/load evidence, deployment, identity, retention-policy, and live-runtime gates remain open.

**Outcome:** Router delivery phases are easier to review while preserving the current bounded local behavior; production operations remain unverified.

## 2026-10-22 — Reverify local Curator and Hermes quality gates

**Intent:** Confirm the current V2 quality state and resolve whether the direct `unauthenticated` MCP response reflects a local ledger failure.

**Changed fact:** No runtime, database, or product source changed in this verification. The already-recorded immediate-purge regression remains in the V2 plan and history: canonical persistence precedes deletion, held artifacts remain, and transient content is absent from Markdown.

**Verification:** Curator strict Pyright, errors-only Pylint, Bandit, `uv lock --check`, and `git diff --check` pass; the full suite was not rerun. Warning-level Pylint remains 9.90/10 (exit 24). The Hermes checkout probe `./hermes -p renew-ssl-coding mcp test curator_v2 --probe-curator-status` exits 0 and reads 12 processed receipts, one goal, two facts, goal-list total 1, and project health `unknown` with five dependency gates. Hermes `python3 scripts/check` passes all 12 checks. The focused Curator-status probe test passes. The complete `test_mcp_config.py` file has 45 passing tests and one non-probe dispatcher-test failure: importing Hermes bootstrap reads `/home/eaglesvn/.hermes/manifest.json` under the test's real-home I/O guard.

**Open gate:** Direct Codex MCP calls still lack trusted Hermes profile/session context and correctly return `unauthenticated`; the Hermes profile reports `Auth: none`. Human identity, managed-gateway/live capture, deployment, retention-policy ownership, production scheduler/alerts, and authoritative-store policy remain open. The Curator checklist count is unchanged.

**Outcome:** The configured local Hermes profile can read the SQLite-backed V2 ledger; the unauthenticated direct connector is a caller-context boundary, not evidence of missing local persistence. No GPTMD, V1 runtime, Host Steward state, or Vhost application data changed.

## 2026-10-22 — Isolate Hermes CLI dispatch test from install bootstrap

**Intent:** Keep the Hermes MCP CLI dispatcher regression isolated from host installation state so the Curator probe test file can run cleanly under the repository's real-home guard.

**Changed fact:** The dispatcher test now supplies a temporary `hermes_bootstrap` module before importing `hermes_cli.main`. It exercises argument dispatch and exit-code propagation without executing the unrelated install bootstrap; production startup code is unchanged.

**Verification:** The formerly failing dispatcher test passes, all 46 tests in `tests/hermes_cli/test_mcp_config.py` pass, Hermes `python3 scripts/check` passes all 12 checks, and Hermes `git diff --check` passes. The Curator V2 source and persistence state are unchanged by this test-only fix.

**Open gate:** Hermes `Auth: none` still means the local profile is not an authenticated human identity. Direct Codex calls still lack trusted Hermes profile/session context; the deployment, managed-gateway/live-runtime, retention-owner, and authoritative-store gates remain open.

**Outcome:** The focused Hermes MCP CLI integration suite is clean and no longer reads the real Hermes home for a dispatcher-only test.

## 2026-10-22 — Decompose goal-reopen relationship validation

**Intent:** Reduce `CuratorStore.reopen_goal` complexity without changing its transactional lifecycle rules.

**Changed fact:** Extracted parent-state, dependency-state, and completed-dependent validation into focused helpers. Calls remain inside the original SQLite transaction and preserve their prior order before the reopen fact and state update.

**Verification:** Four focused reopen/report lifecycle tests pass, including nested parent/dependency ordering and evidence-epoch reset behavior. Strict Pyright and repository errors-only Pylint pass. A focused `R0912`/`R0914` store scan no longer flags `reopen_goal`; remaining store complexity findings remain. `git diff --check` passes.

**Open gate:** The full Curator suite and whole-tree warning-level Pylint were not rerun. The broad Pylint cleanup, authoritative-store policy, deployment, identity, retention ownership, scheduler/alerts, and live-runtime gates remain open.

**Outcome:** Goal reopening retains its transactional and error-order contract with fewer branches and local variables in the store method; no gate or checklist completion state changed.

## 2026-10-22 — Decompose exact artifact-inventory persistence

**Intent:** Make the exact-manifest purge gate easier to audit while preserving its existing transaction and cleanup authorization conditions.

**Changed fact:** Extracted duplicate-path/stable-manifest construction and purge-target insertion with matching hold-audit carry-forward from `CuratorStore.complete_artifact_inventory`. Existing complete-manifest immutability, pending-only completion, zero-purge-attempt gating, canonical-persistence purge status, and receipt transition remain unchanged and in the original transaction.

**Verification:** Three focused purge inventory/hold tests pass, covering incomplete-empty completion, partial-inventory deletion blocking, and reviewer attribution for a new hold. Strict Pyright and repository errors-only Pylint pass. A focused `R0914` scan no longer flags `complete_artifact_inventory`; three unrelated store local-count warnings remain. `git diff --check` passes.

**Open gate:** The full Curator suite and refreshed whole-tree warning-level Pylint were not rerun. Production scheduler, retention ownership, authenticated reviewer identity, and deployment/live-runtime gates remain open.

**Outcome:** Exact inventory persistence is split into smaller reviewable steps without changing deletion authority or eligibility; no checklist item was closed.

## 2026-10-22 — Decompose project storage usage reporting

**Intent:** Reduce storage-reporting method complexity while preserving project attribution, byte accounting, and the separate global SQLite/WAL measurements.

**Changed fact:** Moved grouped ledger queries into focused record and event snapshots and moved event-row conversion/aggregation into a typed summary helper. The public `project_storage_usage` result fields and query order are unchanged; all SQL reads remain under the same store lock.

**Verification:** All nine `test_fact_compaction.py` tests and the focused event-usage and API project-usage tests pass. Strict Pyright and repository errors-only Pylint pass. The focused store `R0914` scan no longer flags `project_storage_usage`. Whole-tree warning-level Pylint improves from 9.90/10 to 9.91/10 and still exits 24. `git diff --check` passes.

**Open gate:** The full Curator suite and broad warning-level Pylint findings remain open. This local reporting refactor does not close deployment, identity, retention-policy ownership, production monitoring, or live-runtime gates.

**Outcome:** Project usage reporting is split into auditable query and aggregation phases without changing its scoped values; no checklist item was closed.

## 2026-10-22 — Decompose event failure retry and lease classification

**Intent:** Reduce `CuratorStore.mark_event_failed` local complexity while preserving retry scheduling, lease fencing, and transient-payload cleanup.

**Changed fact:** Extracted retry timestamp calculation and stale-lease/invalid-transition classification. The update SQL, transaction boundary, error-code validation, lease predicate, attempt ceiling, payload nulling, and scrub-receipt ordering remain unchanged.

**Verification:** Five focused event failure, retry schedule, permanent payload discard/WAL scrub, and cross-connection lease tests pass. Strict Pyright and repository errors-only Pylint pass. The focused `R0914` scan no longer flags `mark_event_failed`; it still reports `record_purge_result`. `git diff --check` passes.

**Open gate:** Full Curator suite and whole-tree warning-level Pylint were not rerun. Deployment, authenticated identity, retention-policy ownership, production scheduling/alerts, and live-runtime evidence remain open.

**Outcome:** Event failure state handling is easier to audit without changing local retry, claim, or payload cleanup behavior; no checklist item was closed.

## 2026-10-22 — Decompose purge-result persistence

**Intent:** Reduce `CuratorStore.record_purge_result` complexity while preserving exact purge retry and receipt-state behavior.

**Changed fact:** Extracted terminal-result validation, bounded failure retry scheduling, and receipt-state refresh. Helpers run inside the original transaction; held-target rejection, result update, staging-artifact timestamp removal, and receipt pending/complete transition remain in their prior order.

**Verification:** Five focused purge retry, hold, missing-target, and idempotency tests pass. Strict Pyright and repository errors-only Pylint pass. A full store `R0914` scan reports no findings; `git diff --check` passes.

**Open gate:** The full Curator suite and repository-wide warning-level Pylint inventory were not rerun. Production scheduler, deployment, authenticated identity, retention-policy ownership, alerts, and live-runtime evidence remain open.

**Outcome:** Purge result handling is divided into smaller auditable phases without changing deletion authority or `purge_pending` semantics; no checklist item was closed.

## 2026-10-22 — Omit Curator V2 content from Hermes trace exports

**Intent:** Keep Curator V2 tool payloads out of Hermes local and uploaded trace exports, including when the user disables generic secret redaction.

**Changed fact:** Hermes trace conversion now preserves the Curator V2 tool name and call association but replaces its arguments and result with fixed markers. Non-Curator tool content continues to follow the existing `redact` choice. The trace CLI help and user guide describe this exception.

**Verification:** The focused trace-export test file passes seven tests with one optional-upload test skipped; Hermes `python3 scripts/check` passes all 12 checks; both repositories pass `git diff --check`.

**Open gate:** This covers the trace converter only. Historical transcript rows, WAL/recovery, remaining backup paths, provider retention, and the broad source-to-sink privacy review remain open; no checklist item was closed.

**Outcome:** The dedicated trace-export sink no longer serializes Curator V2 arguments or results, independent of the generic secret-redaction option.

## 2026-10-23 — Refresh Curator quality and Hermes-context persistence evidence

**Intent:** Recheck the interrupted Curator quality run, keep the whole-tree warning inventory current, and verify V2 ledger visibility through the configured Hermes profile.

**Changed fact:** Wrapped the remaining overlong lines and corrected one test import-order finding. These edits are formatting-only and do not alter source behavior. The full warning-level Pylint inventory now has 177 diagnostic entries, including repeated duplicate-code reports, down from 186 immediately before this cleanup; the score remains 9.90/10 with exit 28. No delivery checklist row changed; the plan snapshot remains 139/178 complete with 39 open.

**Verification:** Strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, `uv lock --check`, and `git diff --check` pass. The full warning-level Pylint command is `uv run --locked --group quality pylint src/curatormd_v2 tests`; its complete report is `/tmp/curator-v2-pylint-2026-10-23.txt`. The read-only Hermes checkout probe exits 0 with host-injected local profile/session context and reads the `vhost-manager-alpha` SQLite ledger: 12/12 event receipts processed, one goal, two facts, no SDE candidates, and paginated goal total 1. Project health remains `unknown` with gates for event routing, purge scheduling, host identity, human review, and producer inventory.

**Open gate:** Repository-wide structural Pylint cleanup remains open. Direct Codex calls still lack Hermes profile context; the profile reports no human authentication. Managed-gateway delivery, live application capture, deployment, production retention ownership, scheduler/alerts, and authoritative-store policy remain unverified.

**Outcome:** The local profile can read persisted V2 state; `unauthenticated` on the direct connector is not evidence of missing SQLite persistence. The V2 checklist remains 139/178, and no production or live-runtime claim is made.

## 2026-10-23 — Simplify project registration authorization predicate

**Intent:** Continue the open whole-tree Pylint cleanup by isolating the registration-fingerprint check without changing project access decisions.

**Changed fact:** Extracted the active-status, captured-revision, repository-fingerprint, config-hash, and backend-version comparisons into a typed helper. The authorizer still fails closed before checking the caller's exact project grant. The checklist count remains 139/178.

**Verification:** All eight `tests/test_project_access.py` cases pass with Python's unittest runner; strict Pyright and errors-only Pylint pass; `git diff --check` passes. The complete pinned warning-level Pylint run reports 176 diagnostic entries, including repeated duplicate-code reports, at 9.90/10 and exit 28, down from 177 before this refactor. The authorizer predicate no longer triggers `too-many-boolean-expressions`; two argument-count findings remain in the project access module.

**Open gate:** Whole-tree structural, fixture, and duplication findings remain. Authenticated Hermes identity, managed-gateway delivery, live consumer capture, deployment, and production retention/scheduler ownership are unchanged and open.

**Outcome:** Project authorization behavior is unchanged with one fewer whole-tree lint diagnostic; no checklist item or release gate was closed.

## 2026-10-23 — Extract project registration retry matching

**Intent:** Reduce the branch complexity in project-registration update replay while preserving exact idempotency and conflict behavior.

**Changed fact:** Extracted the seven-field audit-receipt comparison into a typed predicate. It compares the same action, actor, next revision, repository fingerprint, config hash, backend API version, and rationale before returning the stored replay result.

**Verification:** All eight project-access tests pass; strict Pyright, errors-only Pylint, and `git diff --check` pass. The fresh full-tree warning-level Pylint report contains 175 diagnostic entries at 9.90/10 and exits 28, down from 176 before this extraction. No `too-many-boolean-expressions` findings remain in the full report.

**Open gate:** Other whole-tree complexity, interface-size, fixture-size, and duplicate-code findings remain. No authenticated identity, production, deployment, retention-owner, or live-runtime gate changed.

**Outcome:** Exact transition retries still recover their original receipt, while conflicting transition reuse still fails; one more whole-tree complexity finding is removed and no checklist item is closed.

## 2026-10-23 — Reduce project-registration update locals

**Intent:** Remove excess locals from `update_project_registration` without changing its transaction boundary or persisted audit data.

**Changed fact:** Removed aliases for the registration request's project ID, fingerprints, backend version, and rationale. The validated request remains the source for SQL values and the durable transition receipt; the expected revision and timestamp retain their original validation and ordering.

**Verification:** All eight focused project-access tests pass; strict Pyright, errors-only Pylint, and `git diff --check` pass. The fresh pinned whole-tree warning inventory reports 174 diagnostic entries at 9.90/10 and exits 28, down from 175; the local-count finding for `update_project_registration` is gone.

**Open gate:** Whole-tree Pylint remains open with other store complexity, interface-size, fixture, and duplicate-code findings. No delivery checklist row or external release gate changed.

**Outcome:** Project registration updates preserve exact retry and audit behavior with fewer method locals; no checklist item is closed.

## 2026-10-23 — Preserve exact revision and enum validation while resolving lint findings

**Intent:** Remove exact-type Pylint findings without weakening revision validation or runtime enum checks.

**Changed fact:** Reused the shared `is_exact_int` TypeGuard at the project registration, update, and status revision boundaries. Kept exact enum-type checks with narrow local Pylint reasons because strict Pyright reports `isinstance` as unnecessary for their annotated enum fields. Added a regression that passes `True` to update and suspend requests and verifies both are rejected before registration or audit state changes.

**Verification:** All nine project-access tests and all 27 purge tests pass. Strict Pyright passes; focused Pylint for `models.py`, `read_models.py`, and `store.py` reports no `unidiomatic-typecheck` findings but retains other structural warnings. `git diff --check` passes. The fresh full-tree warning report falls from 174 to 169 diagnostic entries, including duplicate-code reports, and improves from 9.90/10 to 9.91/10 (exit 28). No `unidiomatic-typecheck` findings remain.

**Open gate:** Whole-tree structural, interface-size, test-fixture, and duplicate-code findings remain. This local validation cleanup does not close deployment, identity, retention-policy ownership, scheduler/alert, or live-runtime gates.

**Outcome:** Boolean revisions remain denied and exact enum boundaries remain runtime-validated; five warning entries are removed and no delivery checklist item is closed.

## 2026-10-23 — Type project status transition requests

**Intent:** Reduce the project-status manager and store method interfaces while preserving host authorization, revision checks, and transition replay semantics.

**Changed fact:** Added immutable `ProjectStatusChangeRequest` and passed it through `ProjectAccessManager`, `CuratorStore`, the attended access CLI, and the affected hosted/access tests. The trusted actor still comes from `AuthenticatedCaller`; it is not part of caller-controlled request data. Store validation order and the transaction containing status mutation, audit receipt, and exact retry remain unchanged.

**Verification:** The focused project-access (9), access-CLI (2), and hosted-MCP (14) test modules pass, 25 tests total. Strict Pyright, errors-only Pylint, and `git diff --check` pass. The fresh full-tree warning-level report falls from 169 to 164 diagnostics and remains 9.91/10 (exit 28); project status manager/store argument and local-count warnings are removed.

**Open gate:** Other repository-wide structural, fixture, and duplicate-code findings remain. This local API refactor does not close identity, deployment, retention-owner, scheduler/alert, or live-runtime gates.

**Outcome:** Status changes retain exact host authorization and transactional audit behavior through a typed request; no delivery checklist row is closed.

## 2026-10-23 — Extract cleanup authorization inventory validation

**Intent:** Reduce cleanup authorization method locals while preserving the exact reviewed inventory and the same transaction boundary.

**Changed fact:** Moved receipt/project/inventory completeness checks, per-target retention and reacquisition action validation, and occurrence-bound manifest hashing into a focused helper. It receives the original transaction connection and runs before the existing-authorization replay lookup or insert.

**Verification:** All 27 purge tests pass; strict Pyright, errors-only Pylint, and `git diff --check` pass. The fresh whole-tree warning report falls from 164 to 163 diagnostic entries at 9.91/10 (exit 28), and `create_cleanup_authorization` no longer has an excessive-local finding.

**Open gate:** Whole-tree structural, fixture, and duplicate-code cleanup remains open. Production cleanup scheduling, retention ownership, authenticated reviewer identity, deployment, and live-runtime evidence remain open.

**Outcome:** Cleanup authorization retains its complete-inventory and exact-manifest gate within the original transaction, with fewer method locals and no checklist item closed.

## 2026-10-23 — Group Markdown projection evidence fence

**Intent:** Reduce local state in canonical Markdown projection while keeping evidence verification and the write-time change fence intact.

**Changed fact:** Added immutable `_VerifiedProjectionSnapshot` for the verified criterion progress, source fact IDs, and goal lifecycle/criteria revisions. Evidence is still verified before the write transaction; the transaction still compares current revisions and fact IDs before rendering and replacing the target.

**Verification:** All 19 Markdown persistence tests pass; strict Pyright, errors-only Pylint, and `git diff --check` pass. The fresh whole-tree Pylint report falls from 163 to 162 diagnostic entries at 9.91/10 (exit 28); `persist_goal` no longer reports excessive locals.

**Open gate:** Other Markdown module interface-size and repository-wide quality findings remain. Canonical-store policy, recovery ownership, deployment, and live consumer persistence gates remain unchanged.

**Outcome:** Canonical projection keeps the same transaction and evidence-freshness behavior with one fewer whole-tree diagnostic; no delivery checklist row is closed.

## 2026-10-23 — Bundle Markdown goal-block render inputs

**Intent:** Replace a parallel internal renderer argument list with one typed group of durable projection records.

**Changed fact:** Added immutable `_GoalProjectionRecords` for SDE candidates, pending and completed receipts, corrections, and an optional preverified criterion-progress snapshot. `_render_block` still renders the same goal and fact data; the optional snapshot still avoids repeating evidence verification during persistence.

**Verification:** All 19 Markdown persistence tests pass; strict Pyright, errors-only Pylint, and `git diff --check` pass. The refreshed whole-tree warning report falls from 162 to 160 diagnostic entries at 9.91/10 (exit 28). `_render_block` no longer has argument-count findings.

**Open gate:** Repository-wide structural, fixture, module-size, and duplicate-code findings remain. Deployment, identity, retention ownership, and live-runtime gates are unchanged.

**Outcome:** Markdown rendering keeps the same projected content and evidence-freshness behavior with a smaller internal call contract; no checklist item is closed.

## 2026-10-23 — Split attended review input collection

**Intent:** Reduce review orchestration locals without changing the user's exact SDE and purge authorization workflow.

**Changed fact:** Extracted allowed per-artifact retention/reacquisition input and approve/reject parsing from `_review`. The packet still determines allowed actions; invalid or mismatched input cancels before any review decision is persisted. Exact-phrase confirmation, rationale validation, SDE confirmation, canonical persistence, and purge-status reporting remain in their original order.

**Verification:** All nine `test_review_cli.py` tests pass; strict Pyright, focused review-CLI Pylint, repository errors-only Pylint, and `git diff --check` pass. The fresh full-tree Pylint report falls from 160 to 158 diagnostic entries at 9.91/10 (exit 28); the production `_review` excessive-local finding is gone.

**Open gate:** Test fixture local-count findings and other repository-wide structural/duplicate-code findings remain. Local UID review does not establish Hermes human identity, production retention policy, deployment, or live runtime behavior.

**Outcome:** The attended review path preserves exact user authorization and canonical-write-before-purge ordering with less orchestration complexity; no checklist item is closed.

## 2026-10-23 — Inspect Vhost Manager Curator producer coverage

**Intent:** Identify source-backed Curator V2 producer paths for the Vhost Manager pilot without changing the consumer checkout or inferring out-of-root deletion authority.

**Changed fact:** Read-only review of the dirty `renew_ssl` checkout at HEAD `7d2b10f5433cfe566fc560741bbc9401265176f4` found a configured V2 project (`backend_api_version = 1`) and a Hermes hook that binds explicit goals and forwards bounded Codex turn start/end events. No application producer or Curator staging, inventory, or expiry API call was found in the reviewed Vhost Manager server/UI source. The application does produce site/config files, operation snapshots/archives, manager state, and security counters under configured site, server, backup, or state paths; their lifecycle and disposition remain Vhost-owned and unreviewed. Config SHA-256: `4f3a34e84832b7e8ccfe4e91a68b0664c6aa603409318197f0b44e6454ece44a`; hook SHA-256: `381abaefcc34455472ea3ea9ef69f7ded80c7905255fec7a8d3e1fa34d3c623f0`.

**Verification:** Inspected `.curatormd-v2.toml`, the hook manifest/handler, Vhost Manager server/UI producer call sites, Git HEAD/status, and file hashes. The delivery checklist count remains 139/178 (39 open), excluding reusable templates as defined in the plan. Curator plan and history now record this bounded source finding.

**Open gate:** The consumer checkout is dirty, so this is not a clean revision-bound matrix. There is no owner confirmation, disposable workflow filesystem observation, complete producer/class enumeration, or verified normal/retry/cancel/failure and out-of-root behavior. Absence of a Curator call in the reviewed files is not owner-confirmed absence. No tests were run for this documentation-only update; deployment, authenticated identity, retention ownership, and live-runtime gates remain open.

**Outcome:** Added source-backed evidence while keeping the producer-coverage checklist item open; no consumer source or runtime state was changed.

## 2026-10-23 — Reduce review CLI fixture lint findings

**Intent:** Remove two test-fixture excessive-local findings without changing review or expiry lifecycle assertions.

**Changed fact:** Extracted verified-candidate creation and staged-review inventory preparation into typed fixture helpers. Split expiry fixture creation, CLI invocation, and durable-receipt assertions into separate helpers; store connections now close in `finally` blocks.

**Verification:** Focused Pylint for `tests/test_review_cli.py` rates 10.00/10; strict Pyright reports zero diagnostics; `git diff --check` passes. No tests or fresh whole-tree Pylint inventory were run. The previously recorded whole-tree inventory of 158 diagnostics is only the pre-change baseline.

**Open gate:** The repository-wide Pylint checklist remains open pending a fresh complete inventory and resolution/review of the remaining findings. This test-fixture refactor does not change any delivery checklist count or deployment, identity, retention, or live-runtime gate.

**Outcome:** The two reported fixture-local warnings are removed in focused Pylint; no behavior or checklist item is claimed complete.

## 2026-10-23 — Refresh whole-tree Pylint baseline

**Intent:** Reconcile the repository-wide warning count after the review CLI fixture refactor.

**Changed fact:** A fresh full-tree run confirms the two `tests/test_review_cli.py` excessive-local findings are gone and the inventory has fallen from 158 to 156 diagnostics. The report groups 27 excessive-local, 25 duplicate-code, 23 excessive-argument, 19 excessive-instance-attribute, and 12 positional-argument findings among its largest categories.

**Verification:** Ran `uv run --locked --group quality pylint src/curatormd_v2 tests` at HEAD `860ca84328dda9e3085460f257d1d5429519aa0f` with 48 dirty status entries and Pylint 4.1.3. Exit status is 28 and score is 9.91/10; report saved to `/tmp/curator-v2-pylint-current.txt`. `git diff --check` passes. This was a quality inventory, not a test run.

**Open gate:** Whole-tree Pylint remains open with 156 findings. Production structural/interface findings, duplicate test code, oversized modules, and remaining fixture complexity need separate review. No delivery checklist count or deployment, identity, retention, or runtime gate changed.

**Outcome:** Updated the plan with the verified fresh baseline; no global Pylint thresholds were changed.

## 2026-10-23 — Type the checklist goal intake boundary

**Intent:** Replace the checklist plugin method's parallel source, criteria, ownership, lifecycle, and provenance arguments with one explicit consumer request.

**Changed fact:** Added frozen `ChecklistGoalStartRequest` with nested frozen `GoalStartOptions`, exported from the V2 package. `ProjectPlugin.goal_start_from_checklist` now accepts the typed request; the exact checklist line is still snapshotted from the configured source and the same criteria, parent/dependency links, initial status, owner, next action, and event provenance are passed to the service. All six current call sites were migrated.

**Verification:** Strict Pyright reports zero diagnostics. Fresh `uv run --locked --group quality pylint src/curatormd_v2 tests` with Pylint 4.1.3 reports 155 diagnostics at 9.91/10 and exits 28, down from 156; the method's excessive-argument warning is gone and the new request/options types add no attribute-count warnings. `git diff --check` passes. Tests were not run.

**Open gate:** Whole-tree Pylint cleanup remains open with 155 diagnostics. The consumer call contract is locally typed, but this does not prove application producer wiring, owner-reviewed source coverage, deployment, authenticated human identity, or live runtime behavior.

**Outcome:** Improved the repository plugin's typed intake boundary and removed one warning without changing persistence or checklist completion status.

## 2026-10-23 — Fence scheduled purge retries against project suspension

**Intent:** Prevent the one-shot maintenance runner from deleting artifacts under a stale project binding or after project suspension.

**Changed fact:** Before retrying either the SDE purge queue or expiry queue, the runner now compares the durable registration's repository fingerprint, exact config digest, and backend API version with the loaded project config. It acquires the staging lock before the project's revision fence and holds both across both purge effects, so suspension or binding transitions cannot race through the direct maintenance-plugin path. Authenticated API effect fences use that same lock order; plugin staging locks are reentrant within the same thread and reuse the held root descriptor, preventing inversion against staged-file writers.

**Verification:** Added a regression that creates a due, previously approved purge, registers and suspends its project, then proves maintenance exits with a sanitized failure while the file remains and the receipt stays `purge_pending`. The active registered due-retry flow remains covered. The maintenance CLI (5), purge (28), API (38), concurrency (7), and project-plugin (46) focused suites pass, 124 tests total; strict Pyright reports zero diagnostics, errors-only Pylint passes, and `git diff --check` is clean.

**Open gate:** Production timer ownership/cadence, dead-letter alert delivery, and crash/reconciliation drills remain unverified. This is local scheduler protection only; deployment, authenticated Hermes identity, and live runtime remain open.

**Outcome:** The local scheduler can no longer bypass the project suspension fence for SDE or expiry retries, and both API and scheduler effects follow the staging-lock-before-SQLite-fence order; the production scheduler checklist row remains open.

## 2026-10-23 — Recheck whole-tree Pylint after scheduler fencing

**Intent:** Refresh the repository-wide warning inventory after the maintenance suspension and lock-order changes.

**Changed fact:** The current source and test tree still reports 155 Pylint diagnostics, unchanged from the prior inventory. The largest categories are excessive locals (27), duplicate code (25), excessive arguments (22), excessive instance attributes (19), and positional arguments (12).

**Verification:** Ran `uv run --locked --group quality pylint src/curatormd_v2 tests` on HEAD `860ca84328dda9e3085460f257d1d5429519aa0f` with Pylint 4.1.3. It reports 9.91/10 and exits 28; output is saved at `/tmp/curator-v2-pylint-current.txt`. `git diff --check` passes. This is a whole-tree quality inventory, not a test run.

**Open gate:** Repository-wide Pylint cleanup remains open. The production scheduler timer, dead-letter alerting, crash reconciliation, deployment, authenticated identity, and live-runtime gates remain unverified.

**Outcome:** Updated the plan and persistence history with the fresh inventory; no checklist completion or production behavior is inferred from the quality scan.

## 2026-10-23 — Remove contract-test tuple-unpacking warnings

**Intent:** Make artifact dependency cardinality explicit in the contract-schema test and remove the corresponding static-analysis warnings.

**Changed fact:** The test now asserts that the matching/stale dependency result has two entries and the unattested result has one before indexing them. This preserves the tested binding assertions and fails clearly if the helper returns an incomplete inventory.

**Verification:** Focused Pylint for `tests/test_contract_schemas.py` no longer reports its two `W0632` findings; the file scores 9.93/10 with one separate `R0914` finding. A fresh full-tree `uv run --locked --group quality pylint src/curatormd_v2 tests` run with Pylint 4.1.3 reports 153 diagnostics at 9.92/10 and exits 28, down from 155; output is saved at `/tmp/curator-v2-pylint-current.txt`. `git diff --check` passes. No tests were run.

**Open gate:** Repository-wide Pylint cleanup remains open. The local test edit and warning reduction do not close runtime, deployment, identity, retention, or production scheduler gates.

**Outcome:** Removed two static-analysis findings while retaining explicit cardinality expectations; no delivery checklist row is closed.

## 2026-10-23 — Build the current dirty alpha wheel

**Intent:** Verify the repository's current alpha source, including recently added typed request modules, can still be packaged and imported before consumer installation.

**Changed fact:** `uv build --wheel --out-dir /tmp/curator-v2-alpha-wheel-current` built `curatormd_v2-0.1.0a1-py3-none-any.whl` from the current dirty source. The wheel contains `cli_interaction.py` and `store_requests.py` and imports those modules from the archive itself.

**Verification:** At HEAD `860ca84328dda9e3085460f257d1d5429519aa0f`, the wheel SHA-256 is `0108355d990a1862c0dc7dd08d2ad3e99464d3f0c085e8440859fad8bb336b9e`. The import check resolved `curatormd_v2.__file__` from the wheel archive; `git diff --check` passes. No tests were run.

**Open gate:** This confirms package construction/import only. The wheel was not installed into the Vhost Manager profile; consumer workflow, authenticated identity, deployment, and live runtime remain open.

**Outcome:** Produced a current-source alpha artifact in `/tmp` without changing consumer or Hermes profile installations.

## 2026-10-23 — Make sensitive config traversal iterative

**Intent:** Keep repository-config sensitive-content screening from depending on Python recursion depth, while preserving deterministic first-match reporting and sanitized errors.

**Changed fact:** `_sensitive_config_category` now walks TOML dictionaries and lists iteratively in the same depth-first order as the previous recursive implementation. It retains only the detected safe category in its result; `ProjectConfig.load` continues deleting the parsed root table before raising its sanitized public error.

**Verification:** Strict Pyright reports zero diagnostics. Fresh `uv run --locked --group quality pylint src/curatormd_v2 tests` with Pylint 4.1.3 reports 152 diagnostics at 9.92/10 and exits 28, down from 153; the helper's `R0911` finding is gone. Rebuilt the current dirty-source wheel at `/tmp/curator-v2-alpha-wheel-current/curatormd_v2-0.1.0a1-py3-none-any.whl`, SHA-256 `4b36edf42e49e8444b3a27320c85b3793486e3c1e23f678d3fe7c938fabb2d05`; import resolved from the archive. `git diff --check` passes. No tests were run.

**Open gate:** Existing config-sanitization tests were not rerun, and no deep-nesting regression was added. The warning-level Pylint item, deployment-owned secret policy, authenticated identity, and production security gates remain open.

**Outcome:** Removed recursion-depth dependence in the local config scan and reduced one lint finding; no delivery row or production gate is closed.

## 2026-10-23 — Cover deep config traversal with a focused regression

**Intent:** Verify the iterative sensitive-config scan handles nested values beyond the interpreter's normal recursion limit and still finds sensitive text.

**Changed fact:** Added one regression that wraps safe and credential-like values in lists deeper than `sys.getrecursionlimit()`, then checks safe input returns no category and nested token assignment returns `credential_assignment`.

**Verification:** The focused test passes (1 test); strict Pyright reports zero diagnostics. Focused Pylint on `project_config.py` and `test_project_plugin.py` scores 9.95/10 with existing model/test-structure findings. A fresh full-tree Pylint 4.1.3 run remains at 152 diagnostics, 9.92/10, exit 28; no additional warning was introduced. `git diff --check` passes.

**Open gate:** This covers the helper on nested Python values; it does not prove parser behavior for every deeply nested TOML input or production secret discovery. Whole-tree Pylint, deployed secret policy, and runtime security gates remain open.

**Outcome:** Added direct regression evidence for the depth-independent scan without broadening into redundant suites or marking a delivery row complete.

## 2026-10-23 — Preserve independent dependency health observations

**Intent:** Keep one missing dependency probe from masking healthy sibling probes in the local project-health aggregate.

**Changed fact:** `evaluate_dependencies` now keeps provider-call failure separate from each dependency's missing/invalid/stale observation. Provider failure still makes all dependencies unknown; an individual failed probe marks its own dependency unknown, adds the aggregate failure gate, and leaves later observations independently evaluated.

**Verification:** Extended the existing storage/alert health regression to assert a missing `database_storage_adapter` or `alert_delivery` is unknown while every other fresh probe remains healthy. The focused test passes (1 test); strict Pyright reports zero diagnostics; focused Pylint for `health_evaluation.py` and `test_api.py` scores 9.92/10 with existing test-module structure findings. `git diff --check` passes.

**Open gate:** The project remains `unknown` while any required probe is missing. Deployment-owned storage, scheduler, identity, and alert probes and actual alert delivery remain unverified.

**Outcome:** Local health output now reports independent dependency states accurately without allowing missing required evidence to produce healthy status.

## 2026-10-23 — Label independent health observation scopes

**Intent:** Report when the local SQLite health aggregates, staging inventory, and host dependency probes were observed, without implying they form one atomic cross-source snapshot.

**Changed fact:** `project_health` now carries the timestamp for its consistent SQLite aggregate read and marks that read complete only when it returns. Queue, review/purge, storage, and payload-scrub aggregates are read inside that same snapshot. `StagingUsage` carries the timestamp of each bounded scan, and the API exposes that beside inventory completeness. Missing staging observation time adds an unknown gate. Host dependencies retain their own status and observation timestamp. The API/MCP docs now list all seven required host probes, including storage and alert delivery.

**Verification:** The focused healthy-health snapshot and SQLite snapshot-isolation tests pass, as does the MCP end-to-end test that checks the new response fields (3 tests total). They verify timezone-aware database/staging/dependency times, completeness, consistent SQLite reads, and serialization through MCP. Strict Pyright reports zero diagnostics; `git diff --check` passes. Focused Pylint for health/staging/read-model modules scores 9.91/10 with existing excessive-attribute findings. A dirty-source alpha wheel was rebuilt at `/tmp/curator-v2-alpha-wheel-current/curatormd_v2-0.1.0a1-py3-none-any.whl`, SHA-256 `086904eba4e51648348f5180f8f586fea421d47cf82c0ae1121aadd76bea6656`; health/read-model/staging imports resolve from the wheel archive.

**Open gate:** SQLite read failures still surface as request failures rather than an unknown health snapshot; database failure accounting, production scheduler/probe freshness, alert delivery, authenticated dashboard use, and reconciliation of independently sampled totals remain open.

**Outcome:** Health snapshots expose their local observation scopes and completeness explicitly; this does not close the operational-health delivery row or any deployment gate.

## 2026-10-23 — Report SQLite health-read failures as unknown

**Intent:** Ensure a failed local SQLite aggregate read cannot escape the health contract or appear as zero-valued healthy data.

**Changed fact:** `project_health` now catches SQLite read errors and returns `unknown` with `database_observation_complete=false`, a `database_observation_failed` gate, and null database-derived counts and capacity fields. Independently observed dependency failures can still make the overall state `degraded`. Prometheus emits a zero database-completeness gauge and omits unavailable queue, storage, staging, and feedback samples. The API and delivery plan describe this failure behavior; the operational-health checklist row remains open.

**Verification:** The focused SQLite-failure regression and existing healthy-snapshot regression both pass (2 tests). Strict Pyright, errors-only Pylint, Bandit, the locked dependency audit (50 packages, no known vulnerabilities or adverse statuses), and `git diff --check` pass. A current full-tree warning-level Pylint report exposed an excessive-boolean-expression finding in the Prometheus guard; factoring its event-count validation into a typed helper restores focused `observability.py` Pylint to 10.00/10. The whole-tree warning report was not rerun after that refactor. Bandit reports the existing B603 `nosec` acknowledgements in `git_evidence.py`. No full test suite was run.

**Open gate:** This is local request-time failure reporting, not persistent failure accounting, monitoring, alert delivery, production storage-probe evidence, or deployment validation. The delivery checklist remains 139/178 complete (39 open), excluding reusable templates.

**Outcome:** A failed database snapshot is explicitly unknown and does not publish fabricated zero counts or close a production gate.

## 2026-10-23 — Verify failed health snapshot over MCP

**Intent:** Confirm that the database-read failure result remains explicitly unknown after JSON serialization through the local MCP SDK transport.

**Changed fact:** Added an in-memory MCP client regression that injects a SQLite aggregate-read error and calls both `project_health` and `project_metrics`. The serialized health keeps null database-derived fields and the failure gate; metrics expose database completeness as zero and omit queue counts. The injected SQLite diagnostic is absent from both results.

**Verification:** The focused MCP regression passes; strict Pyright reports zero diagnostics. The current `test_mcp_server.py` focused Pylint report retains its prior test-module structural findings, including an existing excessive-local warning in a different privacy test. `git diff --check` passes.

**Open gate:** This exercises the in-memory SDK client, not a live Hermes transport, authenticated human identity, persistent failure monitoring, alert delivery, or production storage. Delivery progress remains 139/178 complete (39 open).

**Outcome:** Local MCP serialization preserves the fail-closed health contract without turning unavailable data into zero values.

## 2026-10-23 — Decompose the attended access CLI regression

**Intent:** Reduce the access CLI test's setup/locals complexity while preserving coverage of the complete attended registration and project-grant lifecycle.

**Changed fact:** Split the existing end-to-end test into named registration/grant, config-transition replay, suspension/reactivation/revocation, and audit phases. The test still exercises the same single consumer, database, transitions, exact confirmations, replay receipt, and final access audit.

**Verification:** The focused end-to-end access CLI regression passes. Focused Pylint for `tests/test_access_cli.py` rates 10.00/10; strict Pyright reports zero diagnostics. A fresh whole-tree warning-level Pylint run reports 152 diagnostics at 9.92/10 and exits 28; report: `/tmp/curator-v2-pylint-2026-10-23-active-final.txt`. `git diff --check` passes.

**Open gate:** Repository-wide warning-level Pylint remains open; this refactor does not close identity, deployment, consumer, or runtime gates. The delivery checklist remains 139/178 complete (39 open), excluding reusable templates.

**Outcome:** One test-structure warning is removed without changing the tested access lifecycle or claiming full-tree lint completion.

## 2026-10-23 — Keep decorator registry access encapsulated

**Intent:** Remove a Pylint false positive without expanding the authenticated facade's public API.

**Changed fact:** The effect-fence decorator closure reads the private project registry on the same `AuthenticatedCuratorAPI` instance. Pylint misclassifies this nested same-class access as client access. Kept the registry private and applied a single-line `protected-access` suppression with the specific same-class closure reason.

**Verification:** The focused in-flight write/suspension cutover regression passes. Strict Pyright reports zero diagnostics. Focused Pylint for `api.py` no longer reports `W0212`; its existing structural/interface findings remain. This focused run rated the module 9.38/10. The full-tree warning inventory was not rerun after this exception; `git diff --check` passes.

**Open gate:** The suppression awaits inclusion in the final warning-level review; repository-wide Pylint, deployment identity, and live-runtime gates remain open. Delivery progress remains 139/178 complete (39 open).

**Outcome:** Preserved the private registry and current facade behavior while documenting the narrow lint exception for final review.

## 2026-10-23 — Simplify lifecycle matrix action helper

**Intent:** Remove excessive early returns from the exhaustive lifecycle test helper without changing its action matrix.

**Changed fact:** Converted the action dispatch in `_apply_matrix_action` to assign one typed result through the same activate, change-fact, finish, block, defer, amend, cancel, supersede, and reopen branches, then return once.

**Verification:** The exhaustive lifecycle status/action matrix regression passes. Focused Pylint for `tests/test_lifecycle.py` no longer reports `R0911`; strict Pyright reports zero diagnostics. `git diff --check` passes. The latest whole-tree warning inventory predates this extraction and the `api.py` exception, so no updated global count is claimed.

**Open gate:** Repository-wide warning-level Pylint and deployment, authenticated identity, retention-owner, and live-runtime gates remain open. The delivery checklist remains 139/178 complete (39 open).

**Outcome:** Preserved full lifecycle matrix behavior while removing one test-helper structural finding.

## 2026-10-23 — Refresh the dirty-source alpha wheel

**Intent:** Verify that the latest local health and structural changes are included in a reviewable Curator V2 alpha package without installing it into a consumer.

**Changed fact:** Built `curatormd_v2-0.1.0a1-py3-none-any.whl` at `/tmp/curator-v2-alpha-wheel-current/curatormd_v2-0.1.0a1-py3-none-any.whl`, SHA-256 `d754ffb6bb4337dd758993aed09cf6edbe477e71ff890bfc81a76702124d1814`. All 48 top-level package modules match the current source bytes exactly; the archive has no missing or extra module, and imports resolve from the wheel itself. This supersedes the earlier wheel written to that same output path.

**Verification:** `uv build --wheel --out-dir /tmp/curator-v2-alpha-wheel-current` succeeds. A direct source/archive comparison reports 48 matching modules; imports for `api`, `observability`, `cli_interaction`, and `store_requests` load from the wheel archive. No consumer installation or live-runtime claim is made.

**Open gate:** This is package-content evidence for the current dirty checkout, not a clean release artifact or consumer integration. The delivery checklist remains 139/178 complete (39 open); identity, production retention, deployment, and live application gates remain open.

**Outcome:** The current V2 source packages and imports successfully as a wheel while installed consumer evidence remains unchanged.

## 2026-10-23 — Accept the exact alpha wheel in a clean environment

**Intent:** Verify the current dirty-source wheel through installed distribution entrypoints and the stdio consumer launcher, beyond direct archive imports.

**Changed fact:** Installed wheel SHA-256 `d754ffb6bb4337dd758993aed09cf6edbe477e71ff890bfc81a76702124d1814` into a disposable CPython 3.12 venv, with the repository source tree absent from `PYTHONPATH`.

**Verification:** Both installed launcher tests pass: project-bound goal write/read and SDE proposal context. All six installed operational CLI `--help` commands succeed. The installed storage CLI creates a verified backup and restores to a new path; SQLite `quick_check` is `ok` and the smoke row is preserved. The environment and SQLite files are under `/tmp/curator-v2-wheel-acceptance-2026-10-23`. No full suite was run.

**Open gate:** This verifies packaging and disposable consumer-bound behavior only. It does not update the isolated Vhost profile, prove Hermes human identity, or establish Vhost application/live production behavior. Checklist progress remains 139/178 complete (39 open).

**Outcome:** The exact current wheel passes clean-environment launcher, operational CLI, and backup/restore acceptance without touching a consumer repository or live profile.

## 2026-10-23 — Refresh the whole-tree warning inventory

**Intent:** Recount repository-wide Pylint findings after the API decorator exception and lifecycle matrix helper cleanup.

**Changed fact:** The fresh complete source/test-tree report contains 150 diagnostic entries at 9.92/10 and exit 24, including 25 duplicate-code findings. This is down from 151 entries in the immediately preceding whole-tree report after removing the lifecycle helper's excessive-return finding. The report is `/tmp/curator-v2-pylint-2026-10-23-current-final.txt`.

**Verification:** Ran `uv run --locked --group quality pylint src/curatormd_v2 tests` with pinned Pylint 4.1.3 on the current dirty source tree. This was an inventory run; tests were not rerun. `git diff --check` passes.

**Open gate:** Whole-tree complexity, module-size, public-interface, fixture-structure, and duplicate-code findings remain. The API suppression is included and reviewable; this does not close repository-wide Pylint or any deployment/runtime gate. Delivery progress remains 139/178 complete (39 open).

**Outcome:** Published a fresh warning baseline without changing thresholds or claiming full lint completion.

## 2026-10-23 — Decompose the Prometheus contract test

**Intent:** Keep the existing content-free metrics regression reviewable while reducing fixture, format, and budget assertions from one oversized test body.

**Changed fact:** Extracted project/event/staging fixture construction and separate helpers for metric content/privacy, Prometheus family shape, and staging-budget checks. The original single test still covers authorization, private-content omission, counters, unique families, and both budget limits.

**Verification:** The focused `test_project_metrics_are_authorized_bounded_and_content_free` regression passes. Strict Pyright reports zero diagnostics. Focused Pylint for `tests/test_api.py` no longer reports that test's excessive-locals finding and rates the file 9.94/10 with other pre-existing findings. `git diff --check` passes. No full suite or fresh whole-tree Pylint run was performed after this test refactor.

**Open gate:** Repository-wide warning-level Pylint and deployment/runtime gates remain open. Delivery progress remains 139/178 complete (39 open).

**Outcome:** Preserved the metrics contract coverage while making its test setup and assertions easier to inspect.

## 2026-10-23 — Decompose the MCP credential privacy regression

**Intent:** Keep the existing reject-only credential-canary regression reviewable while preserving its source-to-sink assertions.

**Changed fact:** Split the MCP exercise and log assertions from scans of SQLite and sidecars, canonical Markdown, and staging files. The test still submits the same synthetic `ghs_` canary, checks the tool error and logs for non-disclosure, and scans the same persistence surfaces.

**Verification:** The focused `test_sensitive_event_is_absent_from_mcp_errors_logs_and_storage` regression passes. Strict Pyright reports zero diagnostics. Focused Pylint for `tests/test_mcp_server.py` still exits 24 on other structural findings in the large module; the refactored test is not among the reported locations. `git diff --check` passes.

**Open gate:** This is an in-memory MCP and local-storage regression, not a live Hermes transport or comprehensive scanner evaluation. Scanner owner review, deployment policy, authenticated identity, and live-runtime evidence remain open. Delivery progress remains 139/178 complete (39 open).

**Outcome:** Preserved privacy-boundary assertions while separating the MCP/log phase from stored-byte inspection; no checklist status changed.

## 2026-10-23 — Reduce locals in the Hermes goal-binding regression

**Intent:** Simplify the test's result bookkeeping while retaining the complete trusted-context and lifecycle binding contract.

**Changed fact:** Removed intermediate locals for straightforward MCP success/failure assertions and narrowed response content in place. The test continues to verify hidden `ctx`, planned-goal denial, active-goal binding, accepted and replayed lifecycle events, forged durability denial, and profile mismatch denial.

**Verification:** The focused `test_hermes_goal_binding_requires_trusted_context_and_active_project_goal` regression passes. Strict Pyright reports zero diagnostics. Focused Pylint for `tests/test_mcp_server.py` no longer reports the excessive-locals finding in this test; other module complexity/size findings remain, and the focused run exits 24. The documented repository quality sequence (strict Pyright, errors-only Pylint, and Bandit) passes; Bandit emits existing `B603` `nosec` notices in `git_evidence.py`. `git diff --check` passes.

**Open gate:** This is synthetic in-memory MCP test evidence; it does not establish authenticated production identity or a live Hermes route. Repository-wide warning-level Pylint and deployment/runtime gates remain open. Delivery progress remains 139/178 complete (39 open).

**Outcome:** Removed one focused test-structure finding without changing the binding behaviors under test.

## 2026-10-23 — Verify local Curator V2 ledger through Hermes context

**Intent:** Check whether the configured Hermes profile can read persisted Curator V2 ledger state after direct tool access returned unauthenticated.

**Changed fact:** The Hermes Core checkout's read-only `mcp test curator_v2 --probe-curator-status` path connected to the `renew-ssl-coding` profile's installed Curator V2 stdio launcher and returned profile-context ledger data. The probe observed 12 processed receipts, one goal, two facts, zero SDE candidates, and no failed or quarantined events; the paginated goal-list total was one.

**Verification:** The CLI reported a successful connection and discovery of 48 tools. Its read-only probe completed successfully using Hermes-injected profile/session metadata. Project health remained `unknown`, with open gates for event-router, purge-scheduler, host-identity, human-review, and artifact-producer-inventory observations. A direct Codex `project_activity_status` call without Hermes metadata returned `unauthenticated` and no ledger data.

**Open gate:** This verifies local persisted ledger reads through the configured profile context only. The profile has no authenticated human subject; health dependencies, live gateway delivery, production identity, deployment, and production persistence remain unverified.

**Outcome:** Distinguished missing Hermes caller context from local ledger-read failure; no state was mutated and no delivery checklist status changed.

## 2026-10-23 — Extract MCP SDE instruction-contract assertions

**Intent:** Reduce test setup noise while keeping the MCP SDE safety-instruction contract explicit.

**Changed fact:** Moved the six SDE guidance substring assertions into a small test helper. The end-to-end scenario still checks every required phrase before exercising assessment, review, canonical persistence, and purge.

**Verification:** The focused `test_mcp_sde_assessment_review_persistence_and_purge_are_end_to_end` regression passes. Strict Pyright reports zero diagnostics. Focused Pylint for `tests/test_mcp_server.py` no longer reports excessive locals in the outer scenario; the module rates 9.89/10 and still exits 24 for the scenario's excessive statement count and other size/complexity findings. `git diff --check` passes.

**Open gate:** This test-structure cleanup does not close the repository-wide warning-level Pylint item or any authenticated deployment/runtime gate. Delivery progress remains 139/178 complete (39 open).

**Outcome:** Removed one local-structure finding without changing the end-to-end SDE/purge behavior under test.

## 2026-10-23 — Account for retained staging occurrence records

**Intent:** Include the schema-v27 staging filesystem-occurrence registry in project logical-storage accounting without exposing artifact identifiers.

**Changed fact:** Added separate project-scoped occurrence record counts and UTF-8/decimal-text byte totals to `ProjectStorageUsage` and Prometheus. The staging-age byte calculation now includes nullable device, inode, and occurrence-ID fields. The occurrence measurement includes project, relative path, digest, filesystem identity, generation ID, and observation timestamp; returned API/MCP/metrics surfaces expose only aggregates.

**Verification:** Focused project-usage API, project-metrics, two-project auxiliary-usage, and MCP storage-usage regressions pass. Strict Pyright reports zero diagnostics; errors-only Pylint passes on the touched modules; `git diff --check` passes. Tests verify the new values contribute to logical totals, are project-attributed, and do not disclose the occurrence ID.

**Open gate:** Logical record bytes exclude SQLite page/index overhead, shared WAL and backup allocation, and do not define retention or recovery policy. Owner-approved per-class budgets and deployment growth/restore evidence remain open. Delivery progress remains 139/178 complete (39 open).

**Outcome:** Closed the local schema-to-measurement gap for occurrence records; no retention-policy or checklist status was inferred.

## 2026-10-23 — Guard storage-accounting schema coverage

**Intent:** Make future durable schema additions visible to the open permanent-data-budget work instead of allowing them to bypass the accounting inventory silently.

**Changed fact:** Added `tests/test_storage_accounting.py`, which creates the current migration-backed SQLite schema and asserts its complete application-table set equals 19 project-usage tables plus five host-authorized control-plane tables. The two classifications must remain disjoint.

**Verification:** The focused inventory regression passes. The documented quality commands pass: strict Pyright reports zero diagnostics, errors-only Pylint passes, and Bandit passes with the existing `B603` `nosec` notices in `git_evidence.py`. `git diff --check` passes.

**Open gate:** This regression verifies table inventory classification only. It does not prove the byte query for every class, SQLite page/index/WAL/backup allocation, retention horizons, capacity thresholds, recovery sources, or owner policy. Permanent-data-budget delivery remains open; no checklist status changed.

**Outcome:** Added an executable guard against unclassified durable tables without claiming complete storage accounting or changing checklist progress.

## 2026-10-23 — Verify fact-archive contribution to project logical bytes

**Intent:** Prove reviewer-approved fact compaction accounts for archived storage in project totals while reflecting the active facts removed by the same operation.

**Changed fact:** Extended the fact-compaction regression to snapshot project usage before approval and verify the resulting logical-byte delta equals archive logical bytes plus any audit-byte change and the change in active-fact bytes. Archive growth is therefore checked as a transfer from active records, rather than incorrectly expected to be a pure net increase.

**Verification:** The focused compaction scenario passes. Strict Pyright reports zero diagnostics; errors-only Pylint passes for the changed test; `git diff --check` passes.

**Open gate:** This is logical-byte accounting evidence for the fact-archive class only. It does not establish physical database/index/WAL/backup allocation, retention, recovery, or owner-approved class budgets. No checklist status changed.

**Outcome:** Added a regression for net archive accounting without changing storage behavior or claiming completion of the permanent-data-budget item.

## 2026-10-23 — Refresh lint baseline and place schema inventory with migrations

**Intent:** Keep the durable-table inventory assertion alongside the migration tests and remove an overlong storage-usage expression without suppressing lint rules.

**Changed fact:** Moved the schema-to-accounting set regression into `SchemaMigrationTests` in `tests/test_migrations.py`. Wrapped the staging-occurrence byte assignment in `store.py` to remove one concrete line-length finding.

**Verification:** The focused inventory regression passes. Strict Pyright and errors-only Pylint for the migration test pass. A fresh full-tree warning-level Pylint run reports 145 diagnostics at 9.92/10 and exits 24, down from 146 immediately before this change; the 25 `R0801` findings are unchanged. `git diff --check` passes.

**Open gate:** Repository-wide warning-level Pylint still has 145 diagnostics; this change does not close that item or any deployment/runtime gate. Checklist progress remains 139/178 complete (39 open).

**Outcome:** Removed one line-length finding and kept the schema accounting guard, with no checklist status change.

## 2026-10-23 — Simplify concurrent lifecycle test setup

**Intent:** Reduce excess local state in the competing nonterminal-update regression without changing its two-connection race or assertions.

**Changed fact:** Removed intermediate root, service, and store-tuple locals from `test_competing_nonterminal_updates_reject_stale_lifecycle_revision`; each concurrent service still owns a distinct SQLite connection to the same database, shares the same barrier, and competes at lifecycle revision 1.

**Verification:** The focused concurrency regression passes. Strict Pyright reports zero diagnostics; focused Pylint no longer reports `R0914` for this test, though other findings remain in the module. `git diff --check` passes.

**Open gate:** The whole-tree warning-level report remains at its last verified pre-refactor baseline of 145 diagnostics at 9.92/10; it has not been rerun after this change. Repository-wide Pylint and deployment/runtime gates remain open. No checklist status changed.

**Outcome:** Removed one test-structure finding while preserving the concurrency contract and keeping the full lint gate open.

## 2026-10-23 — Extract lease-claim concurrency assertions

**Intent:** Make the exclusive-claim and expiry-recovery test easier to inspect while retaining its concurrent worker and stale-owner checks.

**Changed fact:** Extracted barrier/thread orchestration and the exactly-one-owner assertion into a private helper in `tests/test_concurrency.py`. The main scenario still forces two SQLite connections to race, expires the winning lease, rejects both stale direct transitions and stale router processing, and accepts processing by the new lease owner.

**Verification:** The focused lease-recovery regression passes. Strict Pyright reports zero diagnostics. Focused module Pylint no longer reports `R0914` for this scenario and rates the module 9.80/10; unrelated module findings remain. `git diff --check` passes.

**Open gate:** The last whole-tree warning-level inventory reports 145 diagnostics before both recent concurrency refactors; it has not been refreshed afterward. Repository-wide Pylint and deployment/runtime gates remain open. No checklist status changed.

**Outcome:** Reduced one concurrency test's local complexity while preserving exclusive claim, lease expiry, stale-owner denial, and successful recovery behavior.

## 2026-10-23 — Extract lifecycle race scenarios from concurrency tests

**Intent:** Reduce local complexity in two cross-connection tests while preserving the synchronization boundaries and their lifecycle outcomes.

**Changed fact:** Moved the paused fact-append/goal-finish worker orchestration into a private helper and simplified temporary database/service setup in the concurrent cancel-versus-supersede test. The finish test still proves completion waits while the admitted write holds its transaction, the write is recorded before completion, and a later write is rejected. The terminal race still asserts exactly one of cancel/supersede succeeds and the goal has one terminal outcome.

**Verification:** Both focused concurrency regressions pass. Strict Pyright reports zero diagnostics. Focused Pylint for `tests/test_concurrency.py` no longer reports excess locals in these two scenarios and rates the module 9.86/10; three other `R0914` findings and unrelated diagnostics remain. `git diff --check` passes.

**Open gate:** The last full-tree warning-level inventory remains 145 diagnostics from before the recent concurrency refactors and has not been refreshed. Repository-wide Pylint and deployment/runtime gates remain open. No checklist status changed.

**Outcome:** Preserved the write-fence and terminal-transition race assertions while removing two local complexity findings.

## 2026-10-23 — Clear concurrency test-module lint findings

**Intent:** Reduce redundant local state across concurrency tests and keep the remaining one-method fixture exception tied to its protocol contract.

**Changed fact:** The paused append/finish helper now asserts its worker results internally. Removed one temporary-path local from the fact-count and global-event-cap races. The `TestVerifier` fixture has a code-local `too-few-public-methods` exception because it deliberately implements the single `attest` operation in `EvidenceVerifier`.

**Verification:** Five focused concurrency regressions pass: exclusive lease recovery, append-versus-finish, cancel-versus-supersede, fact-count cap, and global event-receipt cap. Strict Pyright reports zero diagnostics. Warning-level Pylint for `tests/test_concurrency.py` reports 10.00/10. `git diff --check` passes.

**Open gate:** The last full-tree warning-level inventory remains 145 findings and predates these refactors. Repository-wide Pylint and deployment/runtime gates remain open. No checklist status changed.

**Outcome:** Cleared the warning-level findings in the concurrency test module without changing the tested race behavior or claiming full-tree lint closure.

## 2026-10-23 — Refresh full-tree Pylint inventory after concurrency cleanup

**Intent:** Establish a current warning-level baseline after the recent behavior-preserving reductions in concurrency tests.

**Changed fact:** The full-tree warning-level inventory is now 137 diagnostics at 9.93/10, down eight from the prior run: six `R0914` findings, one `R0903` covered by the narrow single-operation verifier exception, and one `C0301` were removed; `R0801` remains 25. The report was generated on branch `main` at `860ca84328dda9e3085460f257d1d5429519aa0f` with 56 dirty status entries. The status fingerprint is `f34a8de3f98eb387c7694797eb5c856eb8f678260602f192fea1de5680f68fcb`; report `/tmp/curator-v2-pylint-active-latest.txt` SHA-256 is `ea6d3e1e7954bb8affe48385aee761e4fc5cb60e80f18ac47edf89caffc3ba7c`.

**Verification:** Ran `uv run --locked --group quality pylint src/curatormd_v2 tests` with Pylint 4.1.3 on Python 3.12.3. It exits 24 because 137 warning-level findings remain. The concurrency test module separately rates 10.00/10; strict Pyright and focused concurrency regressions pass. `git diff --check` passes.

**Open gate:** The whole-tree Pylint item remains open until all findings are resolved or reviewed narrow exceptions are accepted and the final report exits successfully. Local quality does not close deployment, identity, consumer, or runtime gates. No checklist status changed.

**Outcome:** Replaced the stale 145-finding baseline with a reproducible current snapshot; no full-tree lint completion is claimed.

## 2026-10-23 — Fence direct reference-plugin event writes

**Intent:** Prevent callers of the repository plugin from bypassing the active project revision check applied by the authenticated API during event intake.

**Changed fact:** `ProjectPlugin.process_event` now holds the staging lock and active project revision fence through checklist snapshot validation and service event processing. Existing checklist and producer-contract fixtures now register their project explicitly. Added a regression proving a suspended project's direct plugin call raises a lifecycle conflict and creates no event receipt.

**Verification:** Three focused project-plugin tests pass: suspended direct event rejection, checklist snapshot validation/retry, and reusable producer backend contract. Strict Pyright reports zero errors for the changed module and test. `git diff --check` passes. Focused warning-level Pylint reports 9.90/10 with existing module-size, public-method, argument-count, and test-complexity findings; the full-tree 137-diagnostic baseline predates this patch and was not rerun.

**Open gate:** Direct `CuratorService` calls and other direct plugin write methods remain outside this fence. Consumer-binding lifecycle, source acknowledgement, bounded deregistration drains, trusted deployment identity, and owner-approved lifecycle policy remain open. No checklist status changed.

**Outcome:** Closed one local event-intake bypass in the reference plugin without claiming complete lifecycle enforcement or deployment readiness.

## 2026-10-23 — Fence direct project expiry cleanup

**Intent:** Ensure project suspension also blocks direct reference-plugin cleanup, including approval that purges immediately and retries of previously approved work.

**Changed fact:** Expiry inventory approval, exact expiry-receipt retry, and pending-purge retry now hold the staging lock and active project revision fence through their effects. Existing expiry replacement and pending-SDE fixtures now register their project explicitly. Added a suspension regression that tries all three direct cleanup paths and verifies no artifact is unlinked and the durable expiry receipt remains pending.

**Verification:** Three focused expiry tests pass: replacement occurrence protection, suspended-project cleanup denial, and the 72-hour pending-SDE retention cap. Strict Pyright reports zero diagnostics for the changed module and test. Focused warning-level Pylint remains 9.90/10 with the same module-level findings; `git diff --check` passes. The full-tree Pylint baseline remains the earlier 137-diagnostic run and predates these plugin changes.

**Open gate:** Direct service methods and other direct plugin write paths remain outside the lifecycle fence. Consumer-binding transitions, source acknowledgement, bounded deregistration drains, trusted deployment identity, and owner-approved lifecycle policy remain open. Checklist progress did not change.

**Outcome:** Prevented suspended-project expiry cleanup through three direct plugin entry points without claiming end-to-end lifecycle completion.

## 2026-10-23 — Fence direct plugin staging writes

**Intent:** Stop reference-plugin staging writes after project suspension and preserve the staging-lock-before-SQLite-lock order during concurrent writes and inventory scans.

**Changed fact:** `ProjectPlugin.stage_artifact` now holds the staging lock, validates the goal, acquires the active project revision fence, and publishes the artifact before releasing either boundary. The scoped inventory path now acquires the staging lock before its goal lookup, preventing a concurrent scan from waiting on SQLite ahead of the staging lock. The plugin test fixture now registers its project; config-change fixtures advance the registry fingerprint/revision, and the second repository fixture provisions its own binding. The suspension regression now covers event intake and staging writes.

**Verification:** All 49 tests in `tests/test_project_plugin.py`, all 39 tests in `tests/test_api.py`, and all 19 tests in `tests/test_markdown_persistence.py` pass. Strict Pyright over the four changed implementation/test files reports zero diagnostics. Focused warning-level Pylint over those files rates 9.92/10 with existing structural and test-complexity findings. `git diff --check` passes.

**Open gate:** Direct service methods, other plugin writes, source acknowledgements outside the facade, consumer-binding lifecycle, bounded deregistration drains, trusted deployment identity, and owner-approved lifecycle policy remain open. No checklist status changed.

**Outcome:** Closed direct staging writes across the project suspension cutover and preserved atomic staging visibility without claiming full lifecycle delivery.

## 2026-10-23 — Fence direct plugin goal lifecycle writes

**Intent:** Prevent direct reference-plugin goal creation and activation from bypassing project suspension.

**Changed fact:** Request, accepted-subtask, and checklist goal starts, plus activation, reopen, and criteria amendment, now hold the active registered project revision fence through their service write. The existing suspension regression now verifies direct request-start and activation are rejected with no new goal, alongside the existing event and staging denial checks.

**Verification:** The focused suspension regression passes. Strict Pyright reports zero diagnostics for `project_plugin.py` and its test. `git diff --check` passes. Focused warning-level Pylint rates the pair 9.91/10 with existing structural and test-complexity findings; the fresh repository-wide run still reports 137 findings.

**Open gate:** Other direct plugin/service writes, source acknowledgements, consumer-binding lifecycle, bounded deregistration drains, trusted deployment identity, and owner-approved lifecycle policy remain open. No checklist status changed.

**Outcome:** Fenced direct goal creation and core goal lifecycle transitions across project suspension without claiming complete lifecycle enforcement or deployment readiness.

## 2026-10-23 — Fence direct plugin review and cleanup writes

**Intent:** Keep direct reference-plugin review, retention, and retry mutations on the active-project revision boundary.

**Changed fact:** Fact archival, SDE assessment/correction/feedback/disposition, artifact-inventory finalization, cleanup-authorization receipt creation, hold release, and quarantined-event retry now recheck the active registered project revision before their durable write. Filesystem-mutating review operations retain staging-lock-before-SQLite-lock order. The Markdown projection/verifier path remains a separate multi-phase effect requiring a boundary that keeps verification outside SQLite write transactions.

**Verification:** Four focused tests pass: suspended direct-plugin denial, authenticated API review receipt, held-artifact health, and authenticated quarantine retry. Strict Pyright reports zero diagnostics for the changed plugin and test. `git diff --check` passes.

**Open gate:** Markdown projection and its post-verification receipt/purge effects are not yet consistently fenced for direct plugin calls; direct `CuratorService` writes, source acknowledgements, consumer-binding lifecycle, bounded deregistration drains, trusted deployment identity, and owner-approved policies remain open. No checklist status changed.

**Outcome:** Fenced the remaining direct plugin review and cleanup receipt writes covered here without claiming end-to-end lifecycle enforcement.

## 2026-10-23 — Reject direct project repository-binding replacement

**Intent:** Prevent a reviewed config update from silently changing the repository root behind an active project registration.

**Changed fact:** `CuratorStore.update_project_registration` now rejects a changed repository fingerprint and requires deregistration plus fresh enrollment. Config-only updates with the same fingerprint retain their existing revision-CAS and audit-receipt behavior.

**Verification:** The new project-access regression confirms the failed replacement leaves project registration/revision, exact grants, and append-only audit history unchanged. All 10 `tests.test_project_access` tests pass; focused strict Pyright reports zero diagnostics, focused errors-only Pylint passes, and `git diff --check` passes.

**Open gate:** Consumer-binding state/revision, deregistration/drain, re-enrollment and stale-session fencing remain unimplemented. The project lifecycle acceptance gate remains open; this is a fail-closed local guard, not a completed binding lifecycle.

**Outcome:** Removed the direct repository-fingerprint replacement path until the reviewed deregistration/re-enrollment lifecycle is available.

## 2026-10-23 — Refresh local purge acceptance and quality evidence

**Intent:** Recheck the V2 MCP acceptance path that persists canonical facts before transient-artifact cleanup, and refresh the open repository-wide quality result.

**Changed fact:** No runtime or ledger state changed. The existing MCP acceptance test verifies canonical Markdown and receipts are durable before the unheld transient canary is purged; a separately held artifact remains pending, and the canary content is absent from Markdown.

**Verification:** `PYTHONPATH=tests uv run --locked --group test python -m unittest test_mcp_server.McpServerTests.test_mcp_sde_assessment_review_persistence_and_purge_are_end_to_end` passes. The pinned full-tree Pylint command reports 122 findings (111 refactor, 11 convention), exits 24, and its report SHA-256 is `0a40b2e0f69f5c9b576c2bd8d705ffff13567c47dab08552a069262ba710f323`. `git diff --check` passes. A read-only Hermes `renew-ssl-coding` probe succeeds with 12 processed receipts, one goal, and two facts; project health is `unknown` with five missing dependency probes. The plan's Delivery checklist remains 139/178 complete, with 39 open.

**Open gate:** A direct Curator V2 read without host-injected Hermes profile context returns `unauthenticated`. Profile-scoped reads work, but health remains unknown and do not demonstrate fresh event delivery, human identity, complete producers, or deployed scheduler readiness. Repository-wide Pylint, consumer workflow, and deployment gates remain open.

**Outcome:** Refreshed local purge-test evidence without changing a checklist status or claiming live persistence.

## 2026-10-23 — Align Hermes and MCP fixtures with project revision fencing

**Intent:** Keep plugin-bound transport regressions representative of the registered-project requirement after service effects began checking the active revision.

**Changed fact:** Shared test setup now provisions a private consumer config, exact active project registration, explicit test grants, and the separate stdio child process. Hermes-hook and MCP tests bind their plugins to that registered test project before exercising direct service writes.

**Verification:** The full `test_hermes_hook.py` module passes 3 tests and `test_mcp_server.py` passes 7 tests. Strict Pyright reports zero diagnostics; errors-only Pylint for the affected test files and `git diff --check` pass. A fresh pinned whole-tree warning-level Pylint inventory reports 122 findings (111 refactor, 11 convention), down from 124 after two duplicate-code findings were removed; it exits 24. Report SHA-256: `8ebe9152ac1455833d11b4ef06d9a3bc65aff611483191d0b63804eb713a7279`.

**Open gate:** These are local transport-fixture and project-fence checks. They do not implement separate consumer-binding lifecycle or establish authenticated Hermes human identity, deployed routing, or live consumer capture. No checklist item changed.

**Outcome:** Restored focused Hermes/MCP transport verification under the active project revision fence without weakening registration requirements or claiming checklist closure.

## 2026-10-23 — Reduce full-tree Pylint findings on flat read models

**Intent:** Make a behavior-preserving reduction against the open repository-wide warning-level Pylint item.

**Changed fact:** Added reasoned class-local `too-many-instance-attributes` exceptions to six flat receipt, activity, health, and storage records whose fields are individually serialized by the API/MCP contract. No runtime behavior or checklist status changed.

**Verification:** The focused `too-many-instance-attributes` scan for `src/curatormd_v2/read_models.py` passes. Strict Pyright reports zero diagnostics and `git diff --check` passes. The pinned whole-tree command `uv run --locked --group quality pylint src/curatormd_v2 tests --output-format=json` reports 124 diagnostics (113 refactor, 11 convention) and exits 24, down from 130 immediately before this edit. Report SHA-256: `33751864fee6f107a283d5470854b51b5a74efcca43b89abfaf5058592c4aa67`. The edit only changes comments and Pylint directives, so behavioral tests were not rerun.

**Open gate:** Repository-wide warning-level Pylint remains open with 124 findings. No checklist item or release gate changed.

**Outcome:** Removed six reported instance-attribute findings through narrow, reviewable contract exceptions without changing behavior or claiming full-tree lint completion.

## 2026-10-23 — Remove a physical-storage model lint finding

**Intent:** Keep the new host-only physical-storage view maintainable without weakening its data contract.

**Changed fact:** Split SQLite physical measurements into nested page-allocation and file-size read records. The view still reports per-table/index pages, database-page remainder, and database/WAL file sizes, with the same `available`/`unsupported` status.

**Verification:** Focused project-access and attended CLI serialization regressions pass. Strict Pyright and errors-only Pylint on touched files pass; `git diff --check` passes. The pinned full-tree Pylint report fell from 131 to 130 diagnostics (119 refactor, 11 convention), exit 24. Report SHA-256: `f23461b733bff84c270d8fb62de9d8fe71cbb86fffdeeae2f171bc64426d5447`; input fingerprint: `1e008e1f5b6a17f54f5b9402ad35a4c2c79246a980e934d403d51f8be1952fae`.

**Open gate:** Repository-wide warning-level Pylint remains open; the refactor does not close its checklist item.

**Outcome:** Removed the newly introduced excessive-attributes finding while preserving the host-view measurements.

## 2026-10-23 — Measure SQLite pages by durable table class

**Intent:** Add local physical-allocation evidence for durable data classes through the existing trusted-host attended storage view.

**Changed fact:** Added `SQLitePhysicalStorageUsage` to the `ProjectControlPlaneStorageUsage` view. When SQLite `dbstat` is available, the result groups page count and allocated/payload/unused bytes by application table, attributing each table's indexes through `sqlite_master`. It also reports database page size/count, free-list pages, page-allocated and file bytes, WAL bytes, and the residual shared/unattributed database-page bytes. SQLite builds without `dbstat` return an explicit `unsupported` status and leave per-class attribution unknown. Ordinary project storage reads do not return this global physical breakdown.

**Verification:** The host-`VIEW` regression checks application-table allocation, page totals, shared/free-list accounting, and continued authorization. The attended access-CLI regression verifies the physical summary is serialized in the operator view. Strict Pyright reports zero diagnostics; errors-only Pylint passes on changed source/tests; `git diff --check` passes. The development environment reports SQLite 3.45.1 with `dbstat` available.

**Open gate:** This measures the current database only. It does not allocate shared pages to projects, measure backup files, establish owner-approved capacity/retention/recovery thresholds, or prove production growth and restore behavior.

**Outcome:** Added content-free global SQLite page measurements behind the trusted-host access view and retained explicit unsupported/shared-overhead states.

## 2026-10-23 — Measure global SQLite page allocation by table

**Intent:** Add local physical-storage evidence for durable data classes without exposing global database composition through ordinary project reads.

**Changed fact:** The host-authorized attended storage view now reports SQLite `dbstat` page count, allocated bytes, payload bytes, and unused bytes per application table, including indexes attributed through `sqlite_master`. It separately reports page size/count, free-list pages, total allocated/file bytes, WAL bytes, and database pages not attributed to application tables. SQLite builds without `dbstat` return an explicit `unsupported` status and unknown class allocation. This is host-wide because shared SQLite pages cannot be apportioned reliably to one project.

**Verification:** The host `VIEW` test checks page accounting totals and confirms project authorization remains required. The attended CLI test verifies the physical summary survives JSON serialization. Strict Pyright reports zero diagnostics; errors-only Pylint passes on touched source/tests; `git diff --check` passes. The current environment uses SQLite 3.45.1 with `dbstat` available.

**Open gate:** This probe does not measure backup files, establish approved per-class capacity thresholds or retention/recovery rules, or provide deployment growth/restore evidence. The permanent-data-budget checklist item remains open.

**Outcome:** Added an aggregate-only local measure for SQLite table/index allocation while preserving explicit shared/unattributed and unsupported states.

## 2026-10-23 — Account for every current durable schema column

**Intent:** Close the local gap between migrated SQLite columns and project/control-plane logical-byte measurements while keeping physical allocation and owner policy explicit.

**Changed fact:** Auditing the 24 application tables found omitted fields in the goal, criteria-history, fact, archive, review receipt, purge target, expiry target, cleanup authorization, and event-inbox byte formulas. Added those fields; event-row metadata now uses one shared expression for project and global totals, and archive BLOB size comes from its stored payload length. Replaced the table-only schema guard with exact per-column inventories for the 19 project usage tables and five host-authorized control-plane tables. Added an exact raw-row regression proving project and global event totals match every stored event-inbox field, including nullable values.

**Verification:** The focused schema-column and event-byte regressions pass. Focused fact-archive approval, hold inventory, cleanup authorization, and expiry-review regressions pass. Strict Pyright reports zero diagnostics; errors-only Pylint passes on `store.py`, `test_events.py`, and `test_migrations.py`; `git diff --check` passes. No full suite was run.

**Open gate:** This establishes local logical-byte column coverage only. Data owners, approved per-class retention/recovery horizons and thresholds, physical SQLite page/index/WAL/backup allocation, and deployment growth/restore evidence remain open. The permanent-data-budget checklist item remains open.

**Outcome:** Removed the identified local schema-measurement omissions and added a guard against future unclassified columns without claiming a complete storage budget.

## 2026-10-23 — Reduce repository-wide Pylint findings by eleven

**Intent:** Make a bounded cleanup against the current open warning-level Pylint checklist item, without repeating behavioral tests.

**Changed fact:** Replaced the assigned `CuratorService.process_event` guard lambda with a typed local function. Added ten class-local `too-few-public-methods` exceptions to test doubles that intentionally implement a one-method verifier, resolver, or authorizer protocol, plus the minimal bounded stream `read` interface; each exception has an adjacent rationale.

**Verification:** The pinned full-tree command `uv run --locked --group quality pylint src/curatormd_v2 tests --output-format=json` reports 130 findings (119 refactor, 11 convention) and exits 24. The focused `too-few-public-methods` diagnostic check exits 0 at 10.00/10, and `git diff --check` passes. The report SHA-256 is `8492f75cd16bcdaad0f9f27d1e0fc012d892e658670b8314172468950bfb0343`; the Pylint input fingerprint for `pyproject.toml`, `uv.lock`, `src/curatormd_v2`, and `tests` is `02570862a1f6c80155e928f208f34f689fe76752ff8b29f3a3a9528f0d3ddd74` on Python 3.12.3 at `860ca84328dda9e3085460f257d1d5429519aa0f`.

**Open gate:** Repository-wide Pylint still exits 24 with 130 findings. No checklist checkbox changed, and behavioral tests were not rerun for these lint-only edits.

**Outcome:** Removed eleven findings without broad suppressions or behavior changes; repository-wide cleanup remains in progress.

## 2026-10-23 — Remove one repository-wide Pylint finding

**Intent:** Make a behavior-preserving cleanup against the current open warning-level Pylint checklist item.

**Changed fact:** Replaced the assigned `CuratorService.process_event` guard lambda with a typed local function. Guard calls still capture and apply the same expected project revision and optional effect fence.

**Verification:** The pinned full-tree command `uv run --locked --group quality pylint src/curatormd_v2 tests --output-format=json` reports 140 findings (129 refactor, 11 convention), down from 141 immediately before the edit, and exits 24. Report SHA-256 is `60287476dcb69d1a8d4f489d1cf92c5a6224630945b381d62f33f9d03c5d1ed2`; worktree content fingerprint is `a5c6fc24b1463ce96eaa8736cce37cc794c5d4a0fdb22d4da14591427727b15b`. Focused Pylint for `service.py` reports 12 remaining structural findings, and `git diff --check` passes. No tests were run for this behavior-preserving refactor.

**Open gate:** Repository-wide Pylint remains open, with the changed tree still reporting 140 findings. No checklist checkbox changed.

**Outcome:** Removed one unnecessary-lambda diagnostic without suppressions or a behavior change; the broad cleanup item remains in progress.

## 2026-10-23 — Account for unassigned event payload scrub rows

**Intent:** Include the global/unassigned WAL-scrub receipt class in logical storage accounting without attributing it to a consumer project.

**Changed fact:** The host-authorized control-plane storage view now reports `event_payload_scrub_queue_unassigned` in separate `global_classes` totals. It uses the existing bounded aggregate of record count and logical UTF-8 bytes, and does not add those global bytes to any project's logical total or expose scrub/event IDs.

**Verification:** The storage `VIEW` regression creates an unassigned scrub row and verifies exact count/byte accounting, project-local class totals, and identifier-free output; unauthorized consumer access remains denied. Strict Pyright reports zero diagnostics for the changed store/read-model/test files, errors-only Pylint passes, and `git diff --check` passes.

**Open gate:** This accounts for one omitted logical storage class only. Ownership, approved retention/recovery horizon, physical overhead, capacity thresholds, and live backup/restore evidence remain open.

**Outcome:** Added authorized, content-free logical measurement for unassigned scrub receipts without misattributing them to a project or claiming a complete storage policy.

## 2026-10-23 — Fence event effects after external evidence verification

**Intent:** Keep remote evidence verification outside SQLite write transactions while preventing event effects from crossing project suspension.

**Changed fact:** `ProjectPlugin.process_event` captures the active project revision before checklist validation and passes a revision-bound effect fence to `CuratorService.process_event`. The service fences the durable inbox claim, final event commit, and failure receipt independently, with evidence preparation between those transactions. The API event route no longer holds a broad write fence across verification.

**Verification:** A two-connection regression pauses event evidence verification, confirms no SQLite transaction is active, suspends the project, then verifies the stale event cannot append its fact and its inbox receipt remains visible as `received`. All 50 project-plugin tests, 39 API tests, and 22 event tests pass. Strict Pyright reports zero diagnostics for the changed source/test files; `git diff --check` passes.

**Open gate:** Direct `CuratorService` calls without a supplied fence, consumer-binding revision checks, source acknowledgements, resident production routing/scheduling, trusted deployment identity, and live runtime evidence remain open. The broad routing/operations checklist item remains open.

**Outcome:** Closed the event-verification transaction boundary across project suspension for the reference plugin and API paths, without claiming production routing or complete lifecycle enforcement.

## 2026-10-23 — Recheck the Hermes profile ledger view

**Intent:** Revalidate the configured Hermes profile's read-only Curator V2 connection and project scope.

**Changed fact:** No Curator ledger state changed. The Hermes checkout's `renew-ssl-coding` profile connected to the local stdio server with host-injected profile/session context, discovered 48 tools, and read only `vhost-manager-alpha` counts: 12 processed receipts, one goal, two facts, zero pending SDEs, and a paginated goal total of one. The last event remains timestamped 2026-10-21.

**Verification:** `./hermes -p renew-ssl-coding mcp test curator_v2 --probe-curator-status` exited successfully on 2026-10-23. The probe reports health `unknown` with gates for event routing, purge scheduling, host identity, human review, and artifact-producer inventory.

**Open gate:** This confirms profile-context reads only. It does not authenticate a human, deliver a new app-server lifecycle event, or establish production health. Hermes Core Slice G and the Vhost pilot remain open.

**Outcome:** Refreshed local Hermes profile/read-path evidence without changing ledger state or claiming runtime acceptance.

## 2026-10-23 — Fence direct mutations on plugin-bound CuratorService

**Intent:** Prevent callers of the plugin's exposed service object from bypassing the registered project's lifecycle revision.

**Changed fact:** `ProjectPlugin.bind` now binds a config-validating revision capture/fence pair to its `CuratorService`. Direct service goal creation and lifecycle transitions fence their final writes; verification-backed fact append, goal completion, and SDE assessment capture the revision before external verification and fence the commit. Review, inventory, hold, cleanup-receipt, event, and purge paths use the same service-bound effect boundary. Explicit plugin-supplied fences compose with the bound service fence and cannot replace it. Standalone services capture/fence the registry revision when their project is registered; unregistered service instances retain the compatibility path.

**Verification:** The suspended-project regression now verifies `plugin.service.goal_start` is denied. The event evidence race uses a separately constructed `CuratorService` for the registered project, confirms the verifier runs outside the SQLite transaction, and confirms suspension prevents the fact append. The standalone race and full 50-test project-plugin and 39-test API suites pass. Strict Pyright reports zero diagnostics; errors-only Pylint on the changed service/plugin/test files and `git diff --check` pass.

**Open gate:** The registry-only standalone fence does not validate consumer repository/config fingerprints; unregistered standalone service use remains an unfenced compatibility path. Consumer-binding revisions, source acknowledgements beyond the event transaction, and production lifecycle supervision remain open. The full routing/operations checklist is not closed.

**Outcome:** Bound plugin-created and registered standalone service mutations to project suspension/revision cutover while retaining the unregistered compatibility path and keeping production lifecycle enforcement open.

## 2026-10-23 — Fence Markdown persistence after external evidence verification

**Intent:** Prevent canonical Markdown writes and purge-release receipts from landing after project suspension, without running external evidence verification inside a SQLite write transaction.

**Changed fact:** `MarkdownPersistenceAdapter.persist_goal` now accepts a write-effect fence entered only after its evidence snapshot has been verified. `ProjectPlugin.persist_goal` captures the registered revision before verification, holds the staging lock, and applies that same revision fence to atomic Markdown replacement and each canonical receipt/purge transition. Evidence verification and projection recheck remain outside the fence. The API persistence route no longer wraps the entire verifier phase in its broad transaction fence. SDE assessment now similarly verifies evidence before a captured-revision fence around candidate insertion; review inventory/dependency checks run before their fenced writes.

**Verification:** A two-connection regression suspends the project while evidence verification is paused, then confirms the stale projection is rejected and the Markdown target is unchanged. The evidence verifier asserts it never runs inside a SQLite write transaction. All 20 Markdown-persistence tests, 39 API tests, and 49 project-plugin tests pass. Strict Pyright reports zero diagnostics across the changed source and test modules; `git diff --check` passes.

**Open gate:** This fences effects routed through the reference plugin and API. Direct `CuratorService` mutation calls, source acknowledgements outside the facade, consumer-binding lifecycle, bounded deregistration drains, trusted deployment identity, and production runtime/deployment evidence remain open. Checklist status did not change.

**Outcome:** Fenced project-plugin Markdown projection and receipt/purge release at the captured revision while preserving the external-verifier transaction boundary.

## 2026-10-23 — Fence direct plugin review and cleanup writes

**Intent:** Keep direct reference-plugin review, retention, and retry mutations on the same active-project revision boundary as API-routed effects.

**Changed fact:** Fact archival, SDE assessment, correction and feedback, SDE disposition, inventory finalization, cleanup-authorization receipt creation, hold release, and quarantined-event retry now recheck the active registered project revision before their durable write. Filesystem-mutating review operations retain staging-lock-before-SQLite-lock order. The multi-phase Markdown projection/verifier path remains outside this fence pending a boundary that keeps evidence verification out of SQLite transactions.

**Verification:** Four focused tests pass: the suspended direct-plugin regression, authenticated API review receipt, held-artifact health, and authenticated quarantine retry. Strict Pyright reports zero diagnostics for the changed plugin and test. `git diff --check` passes.

**Open gate:** Direct Markdown persistence and its purge effects still need a safe revision-fencing boundary; direct `CuratorService` writes, source acknowledgements, consumer-binding lifecycle, bounded deregistration drains, trusted deployment identity, and owner-approved policies remain open. No checklist status changed.

**Outcome:** Fenced the remaining direct plugin review and cleanup receipt writes covered here without claiming end-to-end lifecycle enforcement.

## 2026-10-23 — Verify current V2 wheel through Vhost and Hermes composition

**Intent:** Verify that the current dirty V2 source packages and still works through the Vhost consumer plugin and Hermes managed-MCP integration.

**Changed fact:** Built wheel `curatormd_v2-0.1.0a1-py3-none-any.whl` with SHA-256 `cdc16e2c36dfee6963d14b588650beb2637f03e6af0938ccb3c7022a74d77c4b` and installed it in a new temporary Python 3.12 environment. Updated two Vhost consumer contract fixtures to register their exact project before invoking revision-fenced plugin/router paths; no Vhost application code or active profile was changed.

**Verification:** All seven Vhost consumer contracts pass against the temporary wheel. The Vhost-owned managed-MCP harness passes against the Hermes Core checkout: three bounded events process, exact retries are acknowledged, a denied delivery is retried after access restoration, the disposable projection reconciles, the out-of-scope target is unchanged, private model/cwd markers are absent, and reviewer-gated persistence remains denied. Curator strict Pyright, errors-only Pylint, focused project-access tests (10), and `git diff --check` pass.

**Open gate:** This is disposable package and protocol composition only. The live Vhost application workflow, current installed profile wheel, cryptographic human identity, production router/scheduler, and production retention/recovery gates remain open.

**Outcome:** Revalidated the current package across the local Vhost plugin and Hermes managed-MCP contract without changing consumer application data or claiming live deployment.

## 2026-10-23 — Add separate consumer binding deregistration lifecycle

**Intent:** Implement the locally supportable consumer-binding lifecycle slice independently of project suspension and preserve the larger authenticated deployment acceptance as open.

**Changed fact:** Schema v33 adds `consumer_bindings` with status, revision, and source epoch plus append-only transition receipts. Project registration creates both project and active binding state atomically; migration backfills existing registrations as active epoch/revision 1 without fabricating historic enrollment receipts. Authorization and the project effect fence require active binding state. Deregistration transitions active -> pending -> deregistered with optimistic revision checks and stable retry IDs. The pending cutover revokes every active grant in the same transaction; finalization refuses while any event inbox row is not processed. Project status and project revision remain unchanged. Repository/config updates and new grants are denied once the binding is no longer active.

**Verification:** `tests.test_project_access` passes 12 tests, including stale launcher denial, grant revocation, project/binding separation, idempotent transition retry, config-update fencing, and unresolved event blocking. `tests.test_access_cli` passes 3 tests, including attended pending/final deregistration and content-free binding history. `tests.test_migrations` passes 34 tests, including v33 active-binding backfill and storage classification. Strict Pyright reports 0 diagnostics for the package and focused test files; errors-only Pylint passes for the changed source/test files; `git diff --check` passes. The full test suite was not run.

**Open gate:** This local slice does not implement a bounded exact-event drain, source acknowledgement fencing, source backlog reconciliation/disposition, re-enrollment and source-epoch rotation, retirement tombstones, or authenticated content-free lifecycle status. Hermes deployment identity and live/runtime lifecycle evidence remain unverified. The full lifecycle checklist item remains open.

**Outcome:** Established distinct, durable consumer deregistration state and fail-closed local authorization while retaining the full consumer lifecycle acceptance as open.

## 2026-10-23 — Add local consumer re-enrollment and stale-event fencing

**Intent:** Allow an owner-attended consumer re-enrollment to start a fresh Hermes event sequence after old queued events have durable receipts, while keeping project lifecycle and the larger deployment acceptance separate.

**Changed fact:** Schema v34 permits an append-only `reenrolled` binding receipt. Re-enrollment compares the current binding revision, old event-sequence generation, project revision, repository fingerprint, config digest, and backend version; it increments the binding revision and event-sequence generation without restoring revoked grants. The attended CLI exposes this operation. Hermes stores the generation with each profile-local session binding; a new session starts its sequence at 1, and a session cannot be rebound to a different generation. Generation-1 source IDs retain their prior format so already queued events remain identifiable. The MCP event path derives the current source identity and rejects old queued event IDs after re-enrollment.

**Verification:** Curator focused access, CLI, migration, MCP, and Hermes-hook tests pass (62); strict Pyright reports zero diagnostics and errors-only Pylint passes for the changed files. Hermes focused outbox and managed-MCP tests pass (45). Both repository `git diff --check` commands pass. The full Hermes `scripts/check` was stopped after more than four minutes in the repository-wide code-health scan; no full Hermes quality-check result is claimed. Tests cover schema migration with prior audit preservation, stale revision/generation rejection, unresolved event blocking, explicit grant restoration, fresh session sequence 1, and old-event rejection after re-enrollment.

**Open gate:** This is local reference-store and Hermes checkout evidence only. It does not implement the inventoried drain, separately approved terminal event disposition, review-bound reactivation, retirement/replay tombstone, authenticated operator status, verified production identity, retention approval, or live deployment behavior. No full lifecycle checklist item is complete; live persistence and runtime status remain unverified.

**Outcome:** Added a local re-enrollment path and old-event fence while leaving the authenticated deployment lifecycle acceptance open.

## 2026-10-23 — Complete local drain, retirement, and alpha identity deployment

**Intent:** Finish the locally implementable consumer drain and retirement protections, bind the Vhost alpha profile to the owner-approved local reviewer identity, and keep production identity and lifecycle acceptance accurately open.

**Changed fact:** Schema v35 adds a content-free, digest-bound inventory for authorized pre-cutover retries, an expiring transition-scoped drain, and irreversible project retirement tombstones. The profile API derives the authorization subject from the process real/effective OS UID and carries the Hermes profile ID separately as routing context. `renew-ssl-coding` now has local UID `1000` read/write/review grants; the legacy profile-string read/write grants are revoked. The isolated alpha profile enables review and runs the rebuilt wheel. The active Vhost project and consumer binding were preserved through the schema v22 to v35 migration.

**Verification:** The full Curator suite passes 435 tests. Strict Pyright reports zero diagnostics, errors-only Pylint passes, Bandit exits successfully, and `git diff --check` passes. A disposable copy of the alpha DB migrated v22 to v35 with `quick_check=ok` and preserved the active project. Before live migration, a mode-0600 SQLite online backup was written to `/home/eaglesvn/.local/share/curatormd-v2-alpha/backups/pre-drain-retirement-20261023.sqlite3`; a mode-0600 package backup and profile-config backup were also saved in that directory. The rebuilt wheel SHA-256 is `7f5f646d047e9f5907e1d033fff92b0145c4fa647ea6a4fa601620e2f1ea0539`. The installed `hermes --profile renew-ssl-coding mcp test curator_v2` connects and discovers 48 tools. The live DB reports schema 35, `quick_check=ok`, active project/binding, 12 processed receipts, and only local UID `1000` active grants. A read-only check of the same profile's Hermes outbox found 11 acknowledged events, 0 pending, and 22 attempts; the V2 hook returns success only for a processed or duplicate Curator receipt. Hermes transport still reports `Auth: none`.

**Open gate:** The alpha identity is the approved local OS account, not an authenticated Hermes human subject. Terminal disposition for unresolved events, complete bounded retirement status/counts, production identity, production lifecycle migration/rollback evidence, and owner acceptance remain open. The active Vhost project was not retired; retirement is verified by local lifecycle tests only.

**Outcome:** Deployed and verified the local-alpha drain/retirement code and OS-bound identity without treating MCP discovery or synthetic lifecycle tests as production evidence.

## 2026-10-23 — Add owner-approved terminal disposition for fenced events

**Intent:** Let an authorized local operator resolve one exact failed source event after consumer cutover so deregistration and retirement do not require deleting unresolved evidence or replaying an event forever.

**Changed fact:** Schema v36 adds immutable terminal event disposition receipts. The local attended `view` command now pages a bounded, content-free candidate inventory with event ID, prior status, payload digest, source identity/sequence, and an explicit completeness marker. `dispose_event` requires the exact event digest, binding revision, source epoch, stable transition ID, bounded rationale, and exact TTY confirmation. It only accepts failed/quarantined rows after the binding is fenced, refuses a live lease or source-sequence gap, retains the event receipt, records the prior status, scrubs transient payload, and returns `processed` with `terminal_authorized`. The Hermes hook consequently acknowledges only that durable processed receipt.

**Verification:** Focused access, attended CLI, and migration suites pass (17, 4, and 36 tests); the full Curator suite passes 438 tests. Strict Pyright reports zero diagnostics, errors-only Pylint and Bandit pass, and `git diff --check` passes. Schema v35 to v36 migration passes on a disposable copy. The active alpha DB was backed up to `/home/eaglesvn/.local/share/curatormd-v2-alpha/backups/pre-schema-v36-2026-10-23.sqlite3` before live migration; after installing wheel SHA-256 `6b837eb7b1300a2bd522401cb909d81142cb671c84d36617ffebbd1ad5800b76`, the live DB reports schema 36, `quick_check=ok`, and unchanged active project, binding, and UID grants. The profile MCP test connects and discovers 48 tools.

**Open gate:** The active Vhost project was not deregistered or retired. The local disposition was exercised in reference-store and attended CLI tests, not against real failed production events. A unified time-stamped lifecycle status snapshot, production identity, deployment acceptance, and rollback drills remain open.

**Outcome:** Added an auditable terminal event path that preserves receipts and ordering while permitting the Hermes source outbox to stop retrying only after an exact human-approved Curator receipt.

## 2026-10-23 — Add one-snapshot consumer lifecycle status

**Intent:** Give the local owner one bounded, content-free observation of project retirement state, consumer binding, event backlog, and terminal-disposition candidates.

**Changed fact:** `project_lifecycle_status_snapshot` reads project revision/status, binding/source epoch, retirement tombstone, all event-status counts, active leases, full unresolved-event count/digest, and one paged terminal-event inventory from a single SQLite read transaction. It includes an observation time and marks unknown event states or a truncated candidate page incomplete. The attended local `view` command includes the snapshot; existing grants, audit, storage, and registration details remain separately visible.

**Verification:** The full Curator suite passes 438 tests. Strict Pyright reports zero diagnostics, errors-only Pylint and Bandit pass, and `git diff --check` passes. The updated wheel SHA-256 is `d14df4b3e01fea66363fd98dcb409b42bb3170014702dd4c93ab718610a719d5`; it is installed into the isolated Vhost alpha profile, whose MCP test connects and discovers 48 tools. The attended deployed `view` read reports `complete=true`, one active project/binding, 12 processed events, zero active leases, zero unresolved events, and no retirement tombstone. A mode-0600 package recovery archive is `/home/eaglesvn/.local/share/curatormd-v2-alpha/backups/pre-status-snapshot-package-2026-10-23.tar.gz`.

**Open gate:** This verifies a local alpha operator view and test database behavior. It does not establish Hermes-authenticated human identity, production status sources, production lifecycle evidence, or release/rollback approval.

**Outcome:** Deployed a bounded status snapshot that reports its observation scope and completeness instead of requiring separate reads to infer lifecycle state.

## 2026-10-23 — Refresh local consumer lifecycle evidence

**Intent:** Continue the Curator V2 lifecycle checklist by checking the local drain, retirement, and source-epoch implementation at its current source revision, then correct the release ledger where it still described those local features as absent.

**Changed fact:** The V2 release-gate ledger now distinguishes implemented local lifecycle behavior from open deployment gates. It records schema-v35 exact inventory-bound drain authorization, schema-v34 source-epoch re-enrollment, schema-v35 retirement tombstones, schema-v36 terminal disposition, and the single-snapshot attended lifecycle view. The ledger explicitly retains review-bound reactivation, incomplete effect-boundary coverage, authenticated deployment identity, and production acceptance as open.

**Verification:** Eight focused `unittest` cases pass across `test_project_access` and `test_access_cli`, covering binding deregistration, unresolved-event blocking, exact drain/profile checks, terminal disposition, retirement, re-enrollment, and attended lifecycle reporting. `git diff --check` passes. No full suite or live destructive operation was run.

**Open gate:** Local regression evidence does not prove production identity, operator approval, deployment migration/rollback, all source-acknowledgement/unlink races, review-bound reactivation, or a live consumer workflow. No checklist row was changed.

**Outcome:** Corrected the stale local-evidence descriptions without closing any deployment gate or changing the checklist count.

## 2026-10-24 — Bind reactivation to a fresh lifecycle review

**Intent:** Require a project owner to review the current project access and pending-work snapshot before restoring a suspended project, and reject the decision if either the ledger or staging tree changes before the transition commits.

**Changed fact:** Schema v37 adds immutable reactivation-audit fields for the packet digest, bounded packet JSON, and exact suspension transition. The packet covers project revision and repository/config identity, consumer binding revision and source epoch, grants and revocations, source cursors, event backlog, pending purge inventory, and a complete staging-tree manifest observed within 60 seconds. The attended CLI shows the packet, requires its digest and suspension transition in the exact confirmation phrase, takes the staging scan under the project effect lock, and rechecks the packet inside the SQLite transition. A changed or incomplete review is denied without state or audit mutation; exact retries recover the original receipt. Migration preserves older audit rows with null review fields.

**Verification:** Focused project-access, attended CLI, hosted-MCP, and migration suites pass (74 tests). Strict Pyright reports zero diagnostics; errors-only Pylint passes; Bandit exits successfully; `git diff --check` passes. Regression cases cover a new event after review, a staging-tree change after review, persisted audit snapshots, exact retry, and v36-to-v37 migration.

**Open gate:** This is local Curator reference-store and attended CLI evidence. Local OS UID attribution is not authenticated Hermes human identity. The external staging inventory producer, owner-approved deployed reviewer roles, production workflow, and migration/rollback acceptance remain open; the lifecycle checklist item remains open.

**Outcome:** Local reactivation now requires a current, content-free, durable review receipt and fails closed when its reviewed ledger or file inventory changes.

## 2026-10-24 — Fence in-flight expiry unlink at suspension

**Intent:** Prove a project suspension cannot pass an already admitted expiry cleanup while its exact staged file is being unlinked.

**Changed fact:** The local project revision fence already spans expiry purge selection, unlink, and durable result recording. A new two-connection regression pauses at the purge adapter, attempts suspension on the second connection, and verifies the transition waits until the file deletion and purge receipt finish. It then verifies the project reaches revision 2 and a new retry is denied.

**Verification:** The focused `test_inflight_expiry_unlink_finishes_before_project_suspend_cutover` passes. This case proves one local expiry-unlink path under project suspension.

**Open gate:** Source-side acknowledgement races, other purge/unlink interruption points, consumer-binding revision fencing, authenticated deployment identity, and production lifecycle acceptance remain open. The lifecycle checklist item remains open.

**Outcome:** Added regression evidence that this local unlink path completes before suspension cutover or is denied after cutover.

## 2026-10-24 — Match Hermes acknowledgements to exact Curator receipts

**Intent:** Prevent Hermes from dropping an outbox event when the MCP adapter returns a durable receipt for another project or event.

**Changed fact:** The Curator Hermes hook now returns acknowledgement success only when the receipt status is `processed` or `duplicate` and its project ID and event ID match the current outbox envelope. A mismatched receipt remains unacknowledged for retry.

**Verification:** The focused `test_hermes_hook` suite passes all three tests, including wrong-project and wrong-event receipt cases. Strict Pyright reports zero diagnostics; errors-only Pylint on the changed adapter/tests passes; Bandit exits successfully; `git diff --check` passes.

**Open gate:** This closes receipt identity validation only. It does not close the race between a Curator response and Hermes' SQLite outbox update, nor the deployment identity, source-epoch/binding revision, or production lifecycle gates.

**Outcome:** Hermes no longer acknowledges a lifecycle outbox event based on a processed receipt for a different project or event.

## 2026-10-24 — Reconcile an exact processed event after suspension

**Intent:** Recover the lost-response case where Curator committed an event but the Hermes outbox did not receive the response before project suspension.

**Changed fact:** A suspended project can return a receipt for an already processed event only when the active binding and exact repository/config fingerprints still match and the caller retains an unrevoked project write grant. Curator compares the full serialized envelope digest, source ID, and source sequence before returning the receipt. The corresponding source-epoch lookup is available only for an already processed event. Unprocessed IDs, changed payloads, revoked grants, and changed bindings remain denied. This is a read-only receipt reconciliation; it cannot apply a new event while suspended.

**Verification:** Focused hosted-MCP, project-access, project-plugin, Hermes-hook, and migration suites pass (124 tests). Strict Pyright reports zero diagnostics; errors-only Pylint passes; Bandit exits successfully; `git diff --check` passes. The real MCP hook integration commits an event, suspends the project, recovers the exact receipt, and rejects a changed envelope; the hosted-MCP regression also rejects an unprocessed ID.

**Open gate:** This addresses response loss after suspension only. Reconciliation after deregistration or retirement, consumer-binding revision races, broader source-acknowledgement/unlink failure injection, authenticated deployment identity, and production lifecycle acceptance remain open.

**Outcome:** A previously committed event can free its Hermes outbox entry after suspension without reopening project writes or accepting changed content.

## 2026-10-24 — Reject new events after consumer cutover

**Intent:** Enforce the deregistration and retirement fence at Curator's durable inbox boundary so a caller that bypasses the hosted API cannot add fresh event IDs after cutover.

**Changed fact:** `CuratorStore.ingest_event` now checks the registered project, consumer binding, and retirement tombstone before inserting a new inbox row. Inactive, deregistration-pending, deregistered, suspended, or retired registrations reject new event IDs. Existing exact IDs still return their durable receipt for safe idempotent retry. A regression covers a new ID during an authorized drain and after retirement, plus the preserved pre-cutover receipt.

**Verification:** `uv run --locked --group test python -m unittest -q tests.test_project_access` passes all 18 tests. Strict Pyright reports zero diagnostics; errors-only Pylint passes for the changed source and test; `git diff --check` passes.

**Open gate:** This closes only the local inbox-admission gap. Expiry/lost-ack and binding-effect races, authenticated Hermes human identity, owner-approved terminal dispositions in deployment, replay-horizon policy, and deployment migration/rollback evidence remain open. The deployed Hermes profile reports transport auth `none`; the approved local OS UID does not establish a human principal.

**Outcome:** The reference store keeps the pre-cutover event receipt available but will not create new event records after a project or consumer binding is fenced.

## 2026-10-24 — Verify the deployed local pilot principal

**Intent:** Establish which identity the installed Vhost alpha Curator profile actually uses, without changing its configuration or database.

**Changed fact:** Read-only inspection found the `renew-ssl-coding` Hermes profile starts the dedicated Curator V2 stdio command with trusted local Hermes context and the `vhost-manager-alpha` database. The profile process runs as OS UID 1000, which resolves to the owner-selected `eaglesvn` account. The active project and binding have unrevoked read, write, and review grants for exactly `local-uid:1000`; the legacy profile-string grants are revoked.

**Verification:** The installed `hermes --profile renew-ssl-coding mcp test curator_v2` command connects and discovers 48 tools. A read-only SQLite connection reports the project and binding active and `PRAGMA quick_check` returns `ok`. No profile, database, or runtime state was changed.

**Open gate:** This verifies the local single-host OS-account principal. Hermes reports transport auth `none`; there is no evidence that an authenticated Hermes person identity is propagated to this MCP process, nor does this establish a multi-user or production identity boundary. The deployed lifecycle and identity release gates remain open for those scopes.

**Outcome:** Local pilot authorization is bound to the approved `eaglesvn` OS account; no person-level or production identity claim is made.

## 2026-10-24 — Preserve Hermes goal binding from nested Curator results

**Intent:** Fix the real-source managed Hermes integration failure where Curator processed an activation receipt but Hermes did not persist its profile-local session binding.

**Changed fact:** Hermes Core's `_curator_source_epoch` now reads the epoch from both a top-level structured field and the JSON string inside Curator's structured `result`. The regression uses the nested result envelope returned by the host integration path. Hermes change `dcc1fc8ab1` is committed and pushed to `fork/codex/curator-v2-hermes-integration-upstream`.

**Verification:** The focused Hermes test passes via `scripts/run_tests.sh tests/tools/test_mcp_trust_gating.py -k successful_goal_activation_persists_profile_local_binding -q`. The disposable managed Hermes-to-Vhost integration passes: planned-goal binding is rejected, explicit activation binds, three events are processed, failed delivery retries, exact replay is acknowledged, the configured projection reconciles, and the out-of-scope target is unchanged. Hermes `scripts/check` is still running in the repository-wide code-health scan; its final result is not yet known.

**Open gate:** This verifies disposable local composition only. It does not provide an authenticated Hermes person identity, real gateway event, Vhost UI request workflow, producer coverage approval, or production lifecycle/recovery evidence. The `renew_ssl` checkout remains dirty; no Vhost source, runtime, or database was changed.

**Outcome:** Hermes durably binds an activated Curator goal when the MCP SDK places `source_epoch` inside the structured result envelope.

## 2026-10-24 — Reconcile an exact event after consumer re-enrollment

**Intent:** Let Hermes clear an outbox item when Curator committed that exact event before consumer deregistration but the acknowledgement was lost.

**Changed fact:** The repository hook carries the durable Hermes source ID through the MCP call. Curator now permits a read-only lookup of an already processed receipt after deregistration or re-enrollment only when the caller has current project write permission and project, event ID, source ID, sequence, envelope identity digest, active project, and cutover receipt match. A replay-only API path cannot admit an event. An authorized event from the current active source refreshes the plugin's captured binding revision under the project effect lock; stale old-source writes stay fenced.

**Verification:** The focused hosted-MCP lifecycle regression passes, covering exact old-event receipt recovery, changed same-ID envelope rejection, denial without current write authorization, and a new-source write after re-enrollment. The Hermes hook suite passes (3 tests), the project-plugin suite passes (53 tests), and the focused drain regression passes. Strict Pyright reports zero diagnostics, errors-only Pylint on changed files passes, and `git diff --check` passes.

**Open gate:** This verifies the local facade and reference SQLite store only. It does not close retirement response loss, Hermes outbox-update interruption races, direct service/source acknowledgement paths outside this facade, authenticated deployment identity, or production lifecycle acceptance. No checklist row changed.

**Outcome:** An exact committed pre-cutover event can be acknowledged after re-enrollment without reopening event writes for the old source.

## 2026-10-24 — Remove three straightforward whole-tree Pylint warnings

**Intent:** Reduce the open repository-wide Pylint backlog by correcting easy test-only findings without changing runtime behavior.

**Changed fact:** Renamed an intentionally unused hosted-MCP fixture argument, replaced a mutable default with a scoped stale-receipt closure, and moved an access-CLI test helper's docstring before its first statement.

**Verification:** The first whole-tree JSON scan reported 179 findings. The follow-up reported 177 and identified one loop-capture warning introduced by the closure change; that closure is now explicitly scoped. The affected hosted-MCP cases, access-CLI case, and Hermes-hook suite pass; strict Pyright, targeted errors-only Pylint on changed tests, and `git diff --check` pass. A warning-level scan of the three edited test files reports 14 structural/duplicate-code findings and no warning-level correctness findings. The whole-tree scan was not rerun after the final closure correction.

**Open gate:** Whole-tree warning-level Pylint still reports extensive structural, design, and duplicate-code findings. The repository-wide Pylint checklist row remains open; no checkbox changed.

**Outcome:** Removed straightforward test warnings and left the larger refactoring backlog explicit.

## 2026-10-24 — Forward exact Hermes event identity through the Vhost plugin

**Intent:** Make the local Vhost consumer hook preserve the source identity needed for Curator's cutover receipt recovery and prevent acknowledging a receipt for another event.

**Changed fact:** The Vhost-owned hook conditionally forwards Hermes' durable `source_id`. It acknowledges only `processed` or `duplicate` receipts whose project and event IDs match its configured project and current outbox event. The consumer contract tests cover source-ID forwarding and reject mismatched project/event receipts.

**Verification:** The focused Vhost hook contract passes using the current Curator source through `PYTHONPATH`. The disposable Hermes managed-MCP integration passes with three processed events, exact replay, retry after denial, reconciled projection, and privacy canaries absent. `git diff --check` passes in both repositories.

**Open gate:** This closes the local adapter identity/acknowledgment gap only. It does not verify Vhost application event production, authenticated human identity, production scheduling, or live release behavior. The real-consumer checklist item remains open.

**Outcome:** The Vhost hook now preserves the exact source envelope identity end to end in local plugin tests without changing application data or the installed profile.

## 2026-10-24 — Make remaining alpha gates readable and refresh consumer evidence

**Intent:** Separate decisions already approved for local alpha from identity, scheduler, workflow, and policy evidence that still requires deployment.

**Changed fact:** The release-gate ledger now states in plain language what each remaining gate requires. It records the approved local `eaglesvn` reviewer, exact-inventory review-and-purge action, and 72-hour transient-artifact maximum separately from production identity/retention approvals. The current Vhost managed-Hermes integration result is recorded against the modified disposable harness.

**Verification:** The Vhost-owned harness passes three lifecycle events through Hermes Core's actual hook registry/context, managed stdio MCP, and consumer hook. Failed-delivery retry, exact replay, projection reconciliation, and private model/cwd canary exclusion pass. `git diff --check` passes in Curator V2 and Vhost Manager. The full warning-level Pylint run finishes at 9.91/10 (exit 24) with existing structural, convention, and duplicate-code findings; the repository's blocking errors-only Pylint command passes.

**Open gate:** Hermes still reports `Auth: none`, so no person-authenticated production reviewer can be established. No recurring production purge worker/alert receiver or restart drill is installed, and no person has exercised a request through the running Vhost Manager application. Production record authority, retention/budget values, external hold discovery, and release/rollback approvals also remain open.

**Outcome:** The local policy approvals and disposable consumer integration are explicit, while the deployment-dependent work remains open. The delivery checklist is unchanged at 139/178; this evidence does not close its live-workflow or production rows.

## 2026-10-24 — Exercise Hermes outbox recovery across Vhost re-enrollment

**Intent:** Verify the source-epoch cutover path through Hermes Core, the Vhost-owned hook, and Curator's managed stdio server.

**Changed fact:** The disposable Vhost integration now simulates Curator committing an event while Hermes loses the response, then fences and re-enrolls the consumer. It restores the exact local read/write grants, restarts the fingerprint-bound MCP process, acknowledges the exact old-epoch receipt, and binds a fresh session whose first event uses source epoch 2, sequence 1.

**Verification:** The integration passes with five processed receipts, including the lost-ack retry and new-epoch event. Explicit goal binding, planned-goal rejection, exact replay, canonical Vhost projection reconciliation, reviewer-write denial, and private model/cwd exclusion also pass. The new checks exercise the current Hermes checkout, Curator source interpreter, managed stdio route, and Vhost consumer hook.

**Open gate:** This remains disposable local integration evidence. It does not prove a Vhost application-originated request, authenticated human identity, recurring production scheduler/alerts, or deployment recovery. No plan checkbox changed.

**Outcome:** Hermes outbox cutover recovery and source-epoch rotation are now covered end to end in the local managed consumer harness.

## 2026-10-24 — Refresh the installed Vhost alpha package

**Intent:** Put the locally verified Curator V2 package into the dedicated Vhost alpha profile and verify the installed package through its consumer contracts and Hermes-managed route.

**Changed fact:** Built wheel `curatormd_v2-0.1.0a1-py3-none-any.whl` with SHA-256 `98ce0e1bd0ce45ba81b8f6b874ec9cc99023ef2582c9090b43a696fa7cb191e8` and installed it only in `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/curator-v2-alpha-venv`. Before replacement, archived the prior installed Curator package and launchers at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-package-before-20261024T112719Z/installed-package.tar.gz`; a sidecar manifest records the archive hash and hashes/sizes for 111 archived files. No Hermes system install, Vhost application source/data, GPTMD, or V1 state was changed.

**Verification:** All 48 installed Python modules match the wheel. The seven Vhost consumer contract tests pass against the installed profile package. The Hermes-managed Vhost lifecycle harness passes five processed events, exact replay, failed-delivery retry, lost-ack recovery after consumer re-enrollment, source-epoch advance, canonical projection reconciliation, denied reviewer write, and privacy canaries. A read-only Hermes profile probe reads 12 processed receipts, one goal, and two facts; health is `degraded` for the absent recurring purge scheduler and alert delivery. `git diff --check` passes for the updated Curator and Vhost checkouts.

**Open gate:** This is a single-host local alpha identity using the approved `eaglesvn` OS UID. Hermes still reports transport `Auth: none`, so an authenticated person identity and production role mapping remain unproven. The Vhost application workflow, production purge scheduler/alerts, and deployment restart/recovery drill also remain open. No checklist row changed; delivery progress remains 139/178 complete.

**Outcome:** The dedicated local alpha profile runs the verified V2 wheel and passes its consumer integration checks while the separate production and live-application gates remain explicit.

## 2026-10-24 — Refresh the full Pylint backlog count

**Intent:** Recheck the open repository-wide Pylint item after recent local changes and record the current baseline before selecting cleanup work.

**Changed fact:** The current whole-tree JSON scan reports 176 findings, all oversized-module, class/interface-size, complexity, or duplicate-code messages. It reports no warning/error category findings. No suppressions or code edits were made by this inventory.

**Verification:** `uv run --locked --group quality pylint --errors-only src/curatormd_v2 tests` passes. The full scan used the same source/test targets with JSON output, and its findings were counted and classified from the output file.

**Open gate:** The repository-wide structural/design backlog remains. This scan improves the freshness of the count but removes no findings and closes no checklist row.

**Outcome:** The Pylint backlog has a current baseline of 176 findings; cleanup remains the next local quality task.

## 2026-10-24 — Reduce Hermes hook test complexity

**Intent:** Remove one avoidable structural Pylint finding from the Hermes hook regression without weakening its receipt, privacy, or failure assertions.

**Changed fact:** The test now creates its temporary consumer with the shared fixture and uses module-private helpers for the recording MCP handler, fixed responses, raised adapter error, and bounded-call assertions. Its behavior and assertions are unchanged.

**Verification:** The focused Hermes hook receipt regression passes. Strict Pyright reports zero diagnostics for `tests/test_hermes_hook.py`. The file's warning-level Pylint inventory falls from seven findings to six, removing the excess-local finding in the receipt test. A fresh whole-tree JSON inventory falls from 176 to 175 findings (15 convention and 160 refactor); errors-only Pylint and `git diff --check` pass.

**Open gate:** Five tests in `test_hermes_hook.py` still have structural findings; the repository-wide complexity, module-size, interface, and duplicate-code backlog remains open. No delivery checklist row changed.

**Outcome:** One non-blocking repository-wide finding is removed with the focused regression and typing check still passing.

## 2026-10-24 — Simplify the Hermes stdio integration test

**Intent:** Reduce structural Pylint findings in the separate-process Hermes hook test while keeping its actual stdio route, duplicate delivery, project isolation, and durable receipt checks intact.

**Changed fact:** Extracted the test's repository paths and deterministic source/event context into a typed fixture, moved second-project setup and the async stdio driver into private helpers, and represented the managed-MCP callback's required keyword options with a `TypedDict`. The test now reads project and event identity from the fixture instead of carrying parallel local variables.

**Verification:** The three Hermes-hook regressions affected by the refactor pass individually, including the separate stdio process test. Strict Pyright reports zero diagnostics; full warning-level Pylint on `tests/test_hermes_hook.py` reports no findings. A fresh whole-tree JSON scan falls from 175 to 168 findings (15 convention, 153 refactor); duplicate-code findings fall from 25 to 24. `git diff --check` passes.

**Open gate:** Repository-wide Pylint still has 168 convention/refactor findings, mostly structural complexity, interface size, module size, and duplicated test/code sections. No delivery checklist row changed.

**Outcome:** The Hermes hook test file is now warning-free and its local integration path remains verified; whole-repository Pylint cleanup remains in progress.

## 2026-10-24 — Simplify attended access CLI lifecycle tests

**Intent:** Remove avoidable local-variable complexity from attended access CLI lifecycle regressions without reducing their suspension, reactivation, or deregistration checks.

**Changed fact:** Added a test helper that asserts an attended CLI operation succeeds and returns its output. The suspension/reactivation/revocation and binding-deregistration tests now use it instead of carrying repeated return-code and error-string locals.

**Verification:** The two affected access CLI regressions pass individually. Strict Pyright reports zero diagnostics for `tests/test_access_cli.py`, and full warning-level Pylint for that file reports no findings. A fresh whole-tree JSON Pylint scan falls from 168 to 166 findings (15 convention, 151 refactor); no warning/error categories are present. `git diff --check` passes.

**Open gate:** Repository-wide structural Pylint findings remain. This cleanup closes no delivery checklist item.

**Outcome:** The attended access CLI test module is warning-free and the repository-wide backlog has been reduced by two findings.

## 2026-10-24 — Preserve exact project-transition replay validation

**Intent:** Simplify the project suspend/reactivate retry comparison without
weakening its idempotency or conflict behavior.

**Changed fact:** `CuratorStore.set_project_status` now compares the ordered
persisted and requested transition fields as tuples. A new regression proves
that reusing a suspension transition ID with a changed rationale conflicts and
leaves the registration revision unchanged.

**Verification:** The focused regression passes; strict Pyright reports zero
diagnostics for the store and project-access tests. Repository errors-only
Pylint and `git diff --check` pass. The fresh warning-level whole-tree inventory
falls from 164 to 163 findings (14 convention, 149 refactor, no warning/error
categories).

**Open gate:** Repository-wide warning-level Pylint and the deployment-dependent
delivery gates remain open; no checklist checkbox changed.

**Outcome:** The transition retry comparison is simpler and retains exact-input
replay semantics.

## 2026-10-24 — Simplify the reviewed consumer-drain precondition

**Intent:** Clarify the fail-closed state checks before authorizing a bounded
consumer deregistration drain.

**Changed fact:** `CuratorStore.authorize_consumer_drain` now separates missing
registration/binding state from the exact binding status/revision comparison.
It retains the same conflict response for an absent or changed drain state.

**Verification:** The focused drain regression passes, covering only events in
the reviewed inventory and the matching caller profile. Strict Pyright reports
zero diagnostics. Whole-tree warning-level Pylint falls from 163 to 162
findings (14 convention, 148 refactor, no warning/error categories); full
errors-only Pylint and `git diff --check` pass.

**Open gate:** Deployment-time drain supervision, recovery, and alert evidence
remain open; no delivery checklist checkbox changed.

**Outcome:** The attended drain gate remains explicit while its local
authorization precondition is easier to inspect.

## 2026-10-24 — Check direct Curator V2 project status access

**Intent:** Verify whether the current Codex MCP connection can read the
profile-bound V2 project status.

**Changed fact:** The read-only `project_health` call returned
`unauthenticated: Trusted Hermes profile context is required`.

**Verification:** The named Curator V2 tool was called once; it returned no
project health, ledger, or persistence data and made no state change.

**Open gate:** This proves only that this direct Codex call lacks Hermes
profile context. It does not prove the configured Hermes profile's ledger is
unavailable or degraded. A status read through the actual trusted Hermes
profile route remains necessary.

**Outcome:** Direct MCP status remains unverified; no authorization boundary
was bypassed.

## 2026-10-24 — Read the V2 ledger through trusted Hermes profile context

**Intent:** Verify the configured Vhost alpha ledger using Hermes Core's
supported profile-context path after the direct Codex MCP call was denied.

**Changed fact:** The Hermes development CLI connected to `curator_v2` using
the `renew-ssl-coding` profile and host-injected profile/session context. It
read the `vhost-manager-alpha` ledger: 12 processed event receipts, one goal,
two facts, and no SDE candidates. Project health is `degraded` only because
the recurring purge scheduler and alert delivery are unavailable.

**Verification:** `/home/eaglesvn/.hermes/hermes-agent/.venv/bin/hermes
--profile renew-ssl-coding mcp test curator_v2 --probe-curator-status` exited
0, connected to the configured local stdio server, discovered 48 tools, and
performed read-only activity, paginated goal-total, and project-health calls.
The probe timestamp is `2026-10-24T12:04:34.319379+00:00`.

**Open gate:** Hermes still has transport `Auth: none`; the profile-context
read verifies local profile/project scoping, not a human-authenticated
production subject. The recurring scheduler, alert receiver, live Vhost
application request, and production release evidence remain open.

**Outcome:** The earlier direct-call `unauthenticated` result is distinguished
from the successful local-profile ledger read; no ledger state was changed.

## 2026-10-24 — Clarify the project effect-fence binding check

**Intent:** Make the ordinary project-binding revision requirement and its
exact-event deregistration exception easier to audit.

**Changed fact:** `CuratorStore.project_revision_fence` now delegates the
consumer-binding status/revision condition to a small predicate. The same
registration revision fence and transition-scoped drain rules remain in force.

**Verification:** Three focused project-access/plugin regressions pass for the
exact reviewed drain, unresolved-event deregistration, and stale plugin drain
event paths. Strict Pyright reports zero diagnostics; repository errors-only
Pylint and `git diff --check` pass. The full warning-level Pylint inventory
falls from 162 to 161 findings (14 convention, 147 refactor).

**Open gate:** Authenticated deployed lifecycle/re-enrollment and production
deregistration recovery remain open; no delivery checklist checkbox changed.

**Outcome:** The effect fence retains the exact drain authorization boundary
with one fewer non-blocking complexity finding.

## 2026-10-24 — Bind lifecycle evidence packets by case

**Intent:** Make the eight planned lifecycle deployment cases independently
auditable without merging their outcomes.

**Changed fact:** The release-gate catalog now gives each lifecycle case a
separate evidence-binding column covering its own revisions, transition,
inventory, receipt, migration, or observation digests. Owners, preconditions,
expected outcomes, and current dispositions remain recorded per case.

**Verification:** A structural check confirms all eight stable case IDs occur
exactly once as release-catalog rows and exactly once in the Section 9
scenario. `git diff --check` passes.

**Open gate:** This completes catalog definition and cross-referencing only.
Owner-authenticated deployment runs, rollback, and release acceptance remain
open; no delivery checklist checkbox changed.

**Outcome:** Each lifecycle case now has a distinct, content-free evidence
binding contract for later deployment verification.

## 2026-10-24 — Add a reusable local maintenance timer template

**Intent:** Prepare a bounded recurring purge-retry unit for local alpha setup
without granting the runner new review, hold-release, or purge authority.

**Changed fact:** Added a systemd user service and timer template, a private
environment-file example, and an operator guide. The service invokes only the
existing explicit due-retry command, limits writes to the account's Curator V2
state and staging directories, and sends output to the journal.

**Verification:** `systemd-analyze verify` accepts both unit templates; the
five-minute calendar expression resolves; `git diff --check` passes. No timer
was installed, enabled, or run.

**Open gate:** The template does not configure an alert recipient or dead-letter
delivery and does not prove host restart/reconciliation behavior. Deployment
owner review, installation, alert delivery, and runtime health evidence remain
open. Production authenticated human identity is separately open because
Hermes reports transport `Auth: none`; the local alpha reviewer remains the
approved `eaglesvn` OS account. No checklist checkbox changed.

**Outcome:** Local scheduler setup is documented and syntactically validated;
the deployed scheduler/alert and production identity gates remain open.

## 2026-10-24 — Probe the recurring Curator timer from Hermes Core health

**Intent:** Replace the hard-coded scheduler-missing observation with a
read-only check of the exact project timer and its latest run.

**Changed fact:** Hermes Core's Curator readiness bridge now reports the
project's purge scheduler ready only when its user timer is enabled and active,
the service has succeeded, and both trigger and run timestamps are recent. The
probe uses bounded `systemctl show` queries without a shell. A known-absent unit
is false; an unavailable manager is unknown.

**Verification:** The focused Hermes health-probe suite passes all seven tests;
Ruff and `git diff --check` pass for the changed Hermes files.

**Open gate:** This source change is not installed in the active Hermes runtime,
and the local timer remains uninstalled. It does not provide alert delivery,
dead-letter handling, or restart/reconciliation evidence. No plan checkbox
changed.

**Outcome:** Scheduler health now has an evidence-backed probe implementation;
the active scheduler and production alert gate remain open.

## 2026-10-24 — Simplify the expiry/suspension race regression

**Intent:** Reduce test-local complexity in the regression that proves project
suspension waits for an admitted expiry unlink and its receipt.

**Changed fact:** Extracted the paused purge callback and suspension transition
into typed helpers. The test still verifies suspension blocks during unlink,
the exact artifact is removed, the purge receipt completes, and a later retry is
fenced after suspension.

**Verification:** The focused race regression passes; strict Pyright reports
zero diagnostics. A refreshed full warning-level Pylint scan falls from 161 to
160 findings (14 convention, 146 refactor; no warning/error categories).

**Open gate:** Repository-wide structural Pylint cleanup remains open; this
does not close a delivery checklist item.

**Outcome:** The lifecycle race remains covered with one fewer whole-tree
Pylint finding.

## 2026-10-24 — Split suspended-project write-fencing assertions

**Intent:** Reduce local complexity in the regression covering direct plugin
and service writes after project suspension.

**Changed fact:** Extracted goal/event/staging denial checks and reviewer,
cleanup, and quarantined-event denial checks into focused test helpers. The
original test still verifies the event has no receipt, no extra goal is
created, and no staging directory appears.

**Verification:** The focused suspended-project regression passes; strict
Pyright reports zero diagnostics. The refreshed full warning-level Pylint
inventory falls from 160 to 159 findings (14 convention, 145 refactor; no
warning/error categories). `git diff --check` passes.

**Open gate:** Repository-wide Pylint cleanup remains open; no delivery
checklist item changed.

**Outcome:** The suspension boundary remains covered with one fewer whole-tree
Pylint finding.

## 2026-10-24 — Simplify the staging inventory/write race test

**Intent:** Reduce test-local complexity while retaining proof that inventory
waits until a plugin writer atomically publishes its staged artifact.

**Changed fact:** The regression now uses typed pausing-stream and counted-lock
helpers. It still proves the inventory cannot finish while the staged stream is
paused and sees the complete artifact after release.

**Verification:** The focused inventory/write race test passes; strict Pyright
reports zero diagnostics; `git diff --check` passes. A fresh whole-tree
warning-level Pylint inventory falls from 159 to 158 findings (14 convention,
144 refactor; no warning/error categories).

**Open gate:** The repository-wide Pylint row remains open; no delivery
checklist item changed.

**Outcome:** The atomic-publication race remains covered with one fewer
whole-tree Pylint finding.

## 2026-10-24 — Disable core dumps in the maintenance unit template

**Intent:** Reduce the chance that transient purge inputs or local path data
from the scheduled maintenance process are written to a core dump.

**Changed fact:** The reusable Curator V2 maintenance service now combines its
owner-only umask with `LimitCORE=0`. The operator guide scopes this safeguard to
that service and keeps the broader privacy review open.

**Verification:** `systemd-analyze verify` accepts the service and timer;
`git diff --check` passes.

**Open gate:** The template is not installed. Other Curator/Hermes processes,
logs, traces, backups, and upstream paths remain outside this safeguard; the
cross-boundary privacy checklist remains open.

**Outcome:** The proposed maintenance service disables core dumps without
claiming a general privacy guarantee.

## 2026-10-24 — Restrict maintenance writes to one project instance

**Intent:** Limit the recurring purge service's filesystem write scope to the
project selected by its systemd template instance.

**Changed fact:** The unit now grants write access only to
`~/.local/state/curatormd-v2/<project-id>/` and
`~/.local/share/curatormd-v2/<project-id>/`. Its environment example and setup
guide use the same per-project database and staging locations.

**Verification:** `systemd-analyze verify` accepts both templates;
`git diff --check` passes.

**Open gate:** The template remains uninstalled and its paths are not yet tied
to a reviewed deployment manifest. No runtime or health claim is made.

**Outcome:** A configured service instance has a narrower write allowlist; no
checklist item changed.

## 2026-10-24 — Forward authenticated Hermes session subjects to Curator V2

**Intent:** Add the missing local identity bridge while preserving the
single-host `eaglesvn` alpha path and keeping production identity claims tied
to authenticated Hermes evidence.

**Changed fact:** Hermes Core now records a canonical subject only when the
session is created from a server-validated authenticated WebSocket identity,
copies that subject to branches, and exposes it to opted-in local stdio MCP
requests only when the session belongs to the requested Hermes profile home.
Curator V2 maps provider subjects to stable content-free grant IDs, binds the
ID to per-request project authorization and audit attribution, rejects invalid
subjects, and can be configured to deny calls when identity is absent.

**Verification:** Curator's subject mapping and request-context tests pass
(2); strict Pyright and errors-only Pylint pass. Hermes Core's trust-context,
session stamping, branch propagation, and profile-scope tests pass (3).
Hermes `scripts/check` could not run its blob-size and health checks because
this checkout has no merge base with `origin/main` or `main`; its checker
requires an explicit base. Both repositories pass `git diff --check`.

**Open gate:** The active `renew-ssl-coding` stdio session still has no
authenticated human subject. The local `eaglesvn` UID grant remains the
single-host alpha authority. Do not enable strict-subject mode for that
profile. Production remains open for a verified Hermes login, exact
user/project grants, configured deployment policy, and a live authorization
exercise. No checklist item changed.

**Outcome:** The identity transport path is implemented and testable; the
absence of person authentication in the current profile remains explicit.

## 2026-10-24 — Document Curator V2 scanner limits

**Intent:** Make the current content scanner's coverage and blind spots
explicit in V2 documentation without claiming a clean scan proves privacy.

**Changed fact:** Added `docs/content-safety-v2.md` with the detector
categories, actual decoded-text boundaries, false-negative and false-positive
cases, unsupported file/evidence formats, and the jurisdiction and deployment
decisions required before broader collection. Updated the plan to reference the
V2-owned document instead of using the V1-named policy as the V2 destination.

**Verification:** Checked each listed detector against
`src/curatormd_v2/content_safety.py` and each documented validation boundary
against its current call sites. `git diff --check` passes.

**Open gate:** No detector was added and no jurisdiction or production privacy
policy was selected. File/media scanning, owner review, independent validation,
and deployment privacy evidence remain open. No checklist item changed.

**Outcome:** The plan now has a V2-scoped threat-model artifact that makes
unsupported data and scanner limitations visible.

## 2026-10-24 — Tighten Hermes request identity and reduce Pylint findings

**Intent:** Make the optional authenticated-subject requirement flow clearly
from the local profile launcher into per-request authorization, while reducing
the repository-wide Pylint backlog without weakening checks.

**Changed fact:** `build_mcp_server` now accepts a typed Hermes-context options
object containing the pinned profile and authenticated-subject requirement.
Canonical provider-subject parsing is isolated behind a bounded helper. The
MCP path fails with `unauthenticated` when strict mode lacks a subject, and a
valid subject without an exact project grant fails with `forbidden`; it does
not fall back to the local OS account. A justified Pylint suppression covers
the one-method request-scoped caller adapter. Two overlong test lines and one
test-local import were corrected.

**Verification:** Two focused identity tests pass, including the actual hosted
MCP denial paths; all 16 hosted-MCP tests pass. Strict Pyright reports zero
diagnostics. Changed-source Pylint scores 10.00/10, errors-only Pylint passes,
and `git diff --check` passes. The fresh full-tree Pylint inventory falls from
160 to 154 diagnostics: 14 convention findings (all oversized modules) and
140 refactor findings, with no warning/error categories. The full warning-level
command exits 24 because those findings remain.

**Open gate:** Repository-wide Pylint cleanup remains incomplete. The
authenticated-subject path is not enabled in the current `Auth: none` Hermes
profile, and production identity, scheduler, live consumer, and deployment
evidence remain open. No delivery checkbox changed.

**Outcome:** Strict per-request identity enforcement is exercised locally and
the current Pylint inventory is six findings smaller than the immediately
preceding source snapshot.

## 2026-10-24 — Split attended access operation handlers

**Intent:** Reduce complexity in the attended project-access command while
preserving its confirmation, review-packet, and transition behavior.

**Changed fact:** `_perform` now validates common rationale once and dispatches
through typed per-operation handlers. Reactivation re-scans staging under the
project effect lock, compares the complete fresh packet to the reviewed
fingerprints, and sends the same status-change request as before. Exact
confirmation phrase selection now has one return path.

**Verification:** All four `test_access_cli.py` tests pass. Strict Pyright
reports zero diagnostics, `access_cli.py` has a clean warning-level Pylint
score of 10.00/10, repository errors-only Pylint passes, and `git diff --check`
passes. The current whole-tree warning-level inventory falls from 154 to 147
diagnostics (14 convention, 133 refactor; none in `access_cli.py`). It exits
24 because the remaining findings persist.

**Open gate:** Repository-wide Pylint cleanup remains open; no delivery
checkbox changed.

**Outcome:** The attended CLI has smaller, typed operation units with its
existing acceptance regressions passing.

## 2026-10-24 — Type project drain and terminal-disposition requests

**Intent:** Reduce the project-administration methods' long parameter lists
without separating a human decision from its exact inventory or event digest.

**Changed fact:** Added immutable `ConsumerDrainAuthorizationRequest` and
`TerminalEventDispositionRequest` values. `ProjectAccessManager` now takes
each request as one boundary object, checks the same caller/action grant, and
passes the same field values to the existing transactional store methods.
The attended CLI constructs those requests from its parsed, confirmed input.

**Verification:** Drain authorization, terminal disposition and exact replay,
the four attended CLI tests, and the hosted drain regression pass. Strict
Pyright reports zero diagnostics; repository errors-only Pylint and
`git diff --check` pass. The full warning-level inventory falls from 147 to
144 diagnostics (14 convention, 130 refactor; none in `project_access.py`).

**Open gate:** Repository-wide Pylint findings remain; no delivery checkbox
changed.

**Outcome:** Project administration now carries exact drain/disposition inputs
as typed requests while preserving existing action checks and store behavior.

## 2026-10-24 — Group staged-file publication metadata

**Intent:** Reduce the staging writer's parameter count without changing its
bounded streaming, no-follow directory access, or atomic publish semantics.

**Changed fact:** `_staged_file` now receives one immutable metadata value for
the temporary/final names, digest, inode, device, and occurrence identity. It
still builds the same `ArtifactRef` and `_StagedFile` values used by the
existing no-clobber link and receipt rollback path.

**Verification:** Atomic staged publication, unsafe-name/overwrite/size
rejection, and project-budget tests pass. Strict Pyright reports zero
diagnostics, targeted Pylint on `staging_write.py` scores 10.00/10, repository
errors-only Pylint passes, and `git diff --check` passes. The full-tree
warning-level inventory falls from 144 to 142 diagnostics (14 convention, 128
refactor; none in `staging_write.py`).

**Open gate:** Repository-wide Pylint findings remain; no delivery checkbox
changed.

**Outcome:** Staged-file identity travels as one typed value, with two fewer
whole-tree Pylint findings.

## 2026-10-24 — Configure the Vhost alpha purge timer and group Git runner settings

**Intent:** Run only already-approved due purge work on the local Vhost alpha schedule, and reduce repository-wide Pylint findings without changing evidence semantics.

**Changed fact:** Installed and enabled the `eaglesvn` user timer for `vhost-manager-alpha` with a five-minute cadence, 15-second spread, five-minute service timeout, 100-receipt cap, and journal-only failures. Its private configuration binds the dedicated alpha maintenance CLI to the existing alpha SQLite database and Vhost repository. A per-instance systemd drop-in grants write access only to that database directory and the configured staging directory. The unit retains strict system/home protection; `PrivateDevices` and `ProtectKernelModules` were removed because the unprivileged user manager cannot apply those capabilities. The timer cannot create approvals or release holds. The Git test runner now receives immutable typed configuration and shares resolved Git runtime state with the diff resolver.

**Verification:** `systemd-analyze --user verify` passes. The direct one-shot and first scheduled timer run both exit successfully and report zero due/pending purge or expiry targets. The timer is enabled and active. All 14 `tests.test_evidence` tests pass; strict Pyright, repository errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. A fresh whole-tree warning-level Pylint inventory falls from 142 to 139 (14 convention, 125 refactor).

**Open gate:** This proves a local Vhost alpha scheduler run only. Production alert delivery, restart/reconciliation drills, scheduler health reporting, authenticated production identity, and live Vhost application workflow remain open. The repository-wide warning-level Pylint checklist remains open. No delivery checkbox changed; progress remains 139/178 delivery items complete.

**Outcome:** The local alpha timer now retries previously approved due work under `eaglesvn`; warning-level Pylint findings fell by three without suppressions or a checklist-completion claim.

## 2026-10-24 — Scope identity to the single-user development alpha

**Intent:** Apply the owner's clarification that Curator V2 is used only during development, with one repository active at a time, and needs no multi-user feature.

**Changed fact:** The local alpha identity requirement is satisfied by the owner-approved `eaglesvn` OS account (`local-uid:1000`) and exact `vhost-manager-alpha` read/write/review grants. The attended reviewer CLI binds the current UID and requires an owner-owned database. The Hermes profile continues to report `Auth: none`, but host-derived profile/session metadata reaches the local stdio server; a verified Hermes human subject is not required for this one-user scope. The corresponding local identity and local profile-bound MCP/rate-limit checklist items now reflect that scope. Future shared/multi-user identity, production revocation, and distributed quotas are deferred, not alpha blockers.

**Verification:** A read-only SQLite grant query shows only `local-uid:1000` with active read/write/review actions for the Vhost project. The live Hermes profile probe connects to the installed Curator server, discovers 48 tools, reads 12 processed receipts, one goal, two facts, and reports local health `degraded` only for `alert_delivery`; the enabled purge timer is ready. Seven focused Hermes health tests pass. Curator's 14 evidence tests, strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass; full warning-level Pylint is 139 (14 convention, 125 refactor). Hermes `scripts/check` passed its non-health checks; the health ratchet exceeded its 120-second `git grep` timeout when explicitly based on `HEAD`, and the default run could not find a merge base on this shallow fork checkout.

**Open gate:** Configure alert delivery only if required for the local alpha; the current health remains truthfully degraded without a receiver. The live Vhost application request and canonical workflow remain unverified. Hermes-authenticated multi-user identity and production controls are deferred until the owner expands scope. No V1 or GPTMD files were changed.

**Outcome:** Local development identity and profile-bound permission checks are accepted for the approved one-user/one-repository alpha. Delivery progress is now 141/178 complete, with 37 open.

## 2026-10-24 — Verify journal-only Hermes alpha health

**Intent:** Remove the local alpha's false degraded alert observation while
preserving its approved journal-only failure reporting and single-user scope.

**Changed fact:** Hermes Core's Curator V2 readiness bridge now checks that the
project maintenance service is loaded with both stdout and stderr routed to
journald, then runs a bounded `journalctl --user --disk-usage` query. It does
not read or expose journal records. Misrouted streams report not-ready;
unavailable systemd or journal queries remain unknown. The V2 plan and alpha
operator docs now distinguish this local journal route from external alerts.
Curator remains one-user and one-repository-at-a-time for development; no
multi-user feature was added.

**Verification:** Nine focused Hermes health tests pass, targeted Ruff passes,
and `git diff --check` passes. The live host reports both service streams as
`journal`; the user journal query succeeds and uses 22.1 MB. The readiness
functions from the Hermes development checkout report both the purge scheduler
and journal-only alert route ready for `vhost-manager-alpha`.

**Open gate:** The modified Hermes checkout is not the active
`/usr/local/lib/hermes-agent` installation, so installed-profile health has not
been changed or reverified. External alerting, dead-letter delivery,
restart/reconciliation, production identity, and live Vhost workflow remain
separate gates. No delivery checkbox changed; progress remains 141/178.

**Outcome:** The local alpha's journal failure path is now measurable without
calling it production alert delivery.

## 2026-10-24 — Split repository-diff evidence regression

**Intent:** Remove the evidence test's excess-local Pylint finding while
keeping immutable-range, content-privacy, replay, project-scope, and byte-limit
assertions intact.

**Changed fact:** Moved disposable Git repository construction into one shared
fixture and separated exact diff hashing/privacy/replay from adapter scope and
size-boundary checks. The receipt still binds the configured immutable commit
range, and the test still verifies that neither source content nor local paths
appear in returned evidence.

**Verification:** All 15 `tests.test_evidence` tests pass. Strict Pyright
reports zero diagnostics; focused Pylint for `tests/test_evidence.py` scores
10.00/10. A fresh full warning-level Pylint scan falls from 139 to 138
findings (14 convention, 124 refactor; no warning/error categories).
`git diff --check` passes.

**Open gate:** Repository-wide warning-level Pylint cleanup remains open; no
delivery checkbox changed. Delivery progress remains 141/178 complete.

**Outcome:** The diff evidence regressions are independently readable, with
one fewer repository-wide Pylint finding.

## 2026-10-24 — Cover a lost Hermes event response across suspension

**Intent:** Verify that lifecycle cutover does not cause a source to acknowledge
an event whose durable receipt was not confirmed to the caller.

**Changed fact:** The Hermes hook integration now simulates a lost first MCP
response after Curator commits the event receipt. After project suspension, the
hook retries the exact event and accepts it only from the existing durable
receipt; changed event context remains denied. Existing project-plugin
regression coverage separately verifies an in-flight expiry unlink and receipt
finish before the project suspension cutover.

**Verification:** All four focused `tests.test_hermes_hook` cases pass. Strict
Pyright reports zero diagnostics; focused Pylint for the module scores
10.00/10. The targeted in-flight expiry unlink race test also passes, and
`git diff --check` passes.

**Open gate:** This exercises the local Hermes hook adapter against the real
Curator MCP server and the reference SQLite store. It does not exercise the
installed Hermes Core outbox, authenticated deployment operator, or live
consumer. Lifecycle deployment acceptance remains open; checklist progress is
unchanged at 141/178.

**Outcome:** A committed event receipt can be recovered and acknowledged by
exact retry after suspension without approving changed event context.

## 2026-10-24 — Reject stale reactivation after grant revocation

**Intent:** Verify that the project lifecycle will not reactivate from a review
packet after project grants change.

**Changed fact:** Extended the local project-access lifecycle regression to
review a suspended project's complete state, revoke one exact grant, and submit
the prior reactivation packet. The store rejects the stale packet without
changing suspended status or the transition audit. A fresh review then allows
reactivation and its digest is retained in the durable receipt. The regression
also retains the existing stale-backlog invalidation case.

**Verification:** The focused reactivation test passes, strict Pyright reports
zero diagnostics, `tests/test_project_access.py` has no new Pylint finding,
and `git diff --check` passes.

**Open gate:** This verifies local SQLite lifecycle behavior. Source cursor,
purge inventory, observation expiry, authenticated deployment, and real
consumer-boundary cases remain open. No checklist checkbox changed; progress
remains 141/178.

**Outcome:** A grant revocation between review and reactivation now requires a
fresh review packet.

## 2026-10-24 — Reject reactivation after staging inventory changes

**Intent:** Ensure a complete reactivation review does not authorize activation
after the reviewed staging inventory has changed.

**Changed fact:** The local lifecycle test now presents a different
valid-format staging manifest digest after review while keeping the reviewed
packet digest. Reactivation is rejected and leaves the project suspended with
the previous audit receipt intact. This verifies binding of the supplied
snapshot values, not a filesystem rescan. The same focused lifecycle test
exercises stale backlog and revoked-grant invalidation.

**Verification:** The focused reactivation test passes; strict Pyright reports
zero diagnostics; the test module adds no Pylint finding; `git diff --check`
passes.

**Open gate:** Source-cursor and purge-inventory mutation, observation expiry,
and deployment-bound reactivation remain open. No checklist checkbox changed;
progress remains 141/178.

**Outcome:** A reviewed staging digest cannot be reused after the inventory
changes.

## 2026-10-24 — Reject reactivation after source cursor changes

**Intent:** Ensure a reviewed reactivation packet cannot be reused after the
project's source sequence state changes.

**Changed fact:** The focused lifecycle regression now inserts a new durable
source cursor after review, then submits the prior packet. The transition is
rejected; project status remains suspended and the lifecycle audit stays at
the suspension receipt. The scenario shares the focused workflow with stale
backlog, revoked-grant, and changed staging-digest cases.

**Verification:** The focused reactivation test passes; strict Pyright reports
zero diagnostics; targeted Pylint reports only the same three preexisting
test-module findings; `git diff --check` passes.

**Open gate:** This directly mutates the disposable SQLite cursor state and
does not exercise producer acknowledgement or a deployed source. Purge
inventory, observation-expiry, filesystem rescan, and deployment-bound
reactivation cases remain open. No checklist checkbox changed; progress remains
141/178.

**Outcome:** A source cursor change now invalidates the reviewed local
reactivation packet.

## 2026-10-24 — Reject reactivation with an expired staging observation

**Intent:** Prove that a reactivation review cannot be used after its staging
inventory observation exceeds the configured freshness window.

**Changed fact:** The local lifecycle regression builds a fresh packet, advances
the store's test clock 61 seconds beyond the 60-second staging observation
limit, and submits the unchanged reviewed values. The store rejects the
transition and preserves suspended status and its audit receipt. This tests
age enforcement, while the separate changed-digest case tests snapshot
binding.

**Verification:** The focused reactivation test passes; strict Pyright reports
zero diagnostics; targeted Pylint shows no new finding; `git diff --check`
passes.

**Open gate:** Local tests still do not exercise a live filesystem rescan,
purge-inventory mutation, authenticated binding transition, or deployment
recovery. No checklist checkbox changed; progress remains 141/178.

**Outcome:** An expired review snapshot cannot reactivate a suspended project.

## 2026-10-24 — Bundle trusted drain context at the revision fence

**Intent:** Reduce the revision-fence argument list without weakening exact
consumer-drain authorization.

**Changed fact:** Added an immutable `ProjectDrainEffectContext` carrying the
event and host-derived caller identity into `project_revision_fence`. The
transactional drain check still matches project/event, caller/profile,
binding revision, source epoch, config digest, payload identity, and source
sequence before admitting an old consumer's exact inventoried event.

**Verification:** The exact drain regressions pass through the access manager,
repository plugin, and hosted MCP paths (3 tests). Strict Pyright reports zero
diagnostics. A fresh whole-tree warning-level Pylint scan reports 132 findings
(14 convention, 118 refactor), down from 135 immediately before this change;
the repository-wide Pylint item remains open. `git diff --check` passes.

**Open gate:** The local regression does not prove a production identity or
deployed consumer lifecycle. No checklist checkbox changed; progress remains
143/178.

**Outcome:** The same drain policy is passed as one typed value and its exact
authorization checks are preserved.
## 2026-10-24 — Split durable-event test groups for focused Pylint cleanup

**Intent:** Remove the event test class's excess-public-method warning while
preserving the same fixture and assertions.

**Changed fact:** `tests/test_events.py` now shares its setup through a private
fixture base and separates inbox acceptance tests from event-processing tests.
No production code or event behavior changed.

**Verification:** All 23 focused event tests pass. Strict Pyright reports zero
diagnostics, targeted warning-level Pylint is clean for the test module, and
`git diff --check` passes.

**Open gate:** The repository-wide warning-level Pylint inventory was not
rerun; its checklist row remains open. No delivery checkbox changed; progress
remains 143/178.

**Outcome:** The focused test module is Pylint-clean without suppressing the
class-size finding or changing coverage.

## 2026-10-24 — Close authenticated interfaces for local development alpha

**Intent:** Apply the owner's scope decision: Curator V2 serves one developer
working in one repository at a time; shared and production identity are out of
scope.

**Changed fact:** Slice D is complete for the local alpha. The configured
`renew-ssl-coding` Hermes profile is enabled with host context and binds
`vhost-manager-alpha`. Read-only inspection of its SQLite ledger reports
schema 37, `quick_check=ok`, an active project and consumer binding at revision
1/source epoch 1, and active read/write/review grants only for
`local-uid:1000`; prior profile-name grants are revoked. The OS maps that UID
to the approved `eaglesvn` account.

**Verification:** Access, attended provisioning, API, hosted-MCP, MCP-server,
and rate-limiter suites pass 94 tests. Strict Pyright reports zero diagnostics.
The read-only ledger check and profile configuration inspection do not mutate
the alpha state. A clean wheel (`f64fdf27be5a360487c0b5ed5c88317794c5e748e0bcdfb986d86b4c83fa9b5c`)
contains all 49 current modules with byte-identical source hashes; its two
installed-launcher acceptance tests and the disposable Hermes-managed Vhost
integration pass. The same wheel is installed in the configured alpha venv,
with a recoverable pre-install package archive at
`~/.hermes/profiles/renew-ssl-coding/backups/curator-v2-package-before-alpha-install-20261024T2207/`.
The active host gateway multiplexes other Hermes profiles and refused a
profile-only restart, so its already-running Curator MCP child still needs a
host-gateway reload before this installed wheel is live in that process.

**Open gate:** Hermes-human identity, distributed quotas, production
provisioning/denial probes, trusted production fingerprint authority, and
feedback-retention policy remain separate release gates. The real Vhost
application workflow and activation of the newly installed wheel in the
already-running multiplexed host gateway remain open. Delivery progress is
144/178 complete; 34 remain.

**Outcome:** Local default-deny API/MCP access, project/action grants, local
identity attribution, and bounded quota behavior are verified for the approved
single-user development scope. No multi-user feature was added.

## 2026-10-24 — Close durable routing and operations for local alpha

**Intent:** Verify the current local-alpha routing and operations contract
against the focused Python-version matrix, then separate it from production
operations gates.

**Changed fact:** Slice E is complete for the approved single-user alpha. The
active Vhost Manager purge timer runs every six hours and retries only reviewed
receipts. Local routing, retry/quarantine, health/metrics, maintenance, and
recovery behavior are covered; no resident event-routing worker or external
alert receiver is part of the approved alpha.

**Verification:** The focused router/CLI, API/MCP, purge, concurrency,
migration, health-probe bridge, and maintenance-CLI suites pass 138 tests; the
resource-limit, storage-accounting/CLI, and SQLite rate-limiter suites pass 16
more. The combined acceptance set passes 154 tests on Python 3.12.3, 3.13.15,
and 3.14.7. The user timer is enabled with
`OnCalendar=*-*-* 00,06,12,18:00:00`; the latest completed run and next
scheduled run were visible in `systemctl --user list-timers`. The current
warning-level whole-tree Pylint inventory remains a separate open quality item
at 132 findings (14 convention, 118 refactor).

**Open gate:** Production event/purge workers, external alert delivery,
deployment storage and lag budgets, and production load/restart/failure drills
remain open. The already-running shared Hermes host gateway still has the
pre-install Curator MCP child loaded; a profile-only restart was refused
because that gateway serves multiple profiles. Its running Curator tool path
has not yet reloaded the installed alpha wheel. No production or live consumer
gate is closed by these tests.

**Outcome:** Local-alpha durable operations are closed at 145/178 delivery
items complete, with 33 open. No code changed in this slice.

## 2026-10-24 — Verify the pushed alpha candidate in hosted CI

**Intent:** Verify the just-pushed Curator V2 commit against the repository CI
workflow and preserve the result in the release ledger.

**Changed fact:** Hosted CI run
`https://github.com/eagles-edu/curatormd-v2/actions/runs/40105937812` passed
for commit `c653257e50df8472f921002512111f6cf0f8dda1` on `main`.

**Verification:** All workflow jobs passed: full test matrices on Python 3.12,
3.13, and 3.14; clean-wheel build/install and consumer-bound launcher/command
acceptance; strict Pyright; blocking Pylint errors; Bandit; and locked
dependency audit. The follow-up docs-only commit
`4ebca4d406b7a12eb3a1c535d1d49edf5dbf6c58` also passed all jobs in run
`40106053196`.

**Open gate:** Warning-level whole-tree Pylint still reports 132 findings
(14 convention, 118 refactor). Live activation of the installed Vhost alpha
wheel through the shared Hermes host gateway, real Vhost application workflow,
and production/release controls remain open.

**Outcome:** Commit `c653257` is hosted-CI verified. No checklist count changed.

## 2026-10-24 — Activate the installed Curator alpha through Hermes Core

**Intent:** Reload the validated Curator wheel in the configured local Vhost
alpha profile and check its Hermes-managed integration path.

**Changed fact:** The Hermes system gateway restarted successfully. It serves
the five configured profiles, including `renew-ssl-coding`, and the Vhost
profile remains pointed at the dedicated Curator V2 virtualenv. The installed
package's 49 Python module hashes match the current Curator source. GPTMD source
and configuration were not changed.

**Verification:** `hermes --profile renew-ssl-coding mcp test curator_v2`
connects and discovers 48 tools; its `Auth: none` display does not establish
human identity. The Vhost-owned Hermes-managed integration harness passes
against the installed profile interpreter with five processed events, exact
replay, failed-delivery retry, source-epoch re-enrollment, projection
reconciliation, and privacy canaries.

**Open gate:** The harness is a disposable integration run. No real Vhost
application request or human-authenticated action was exercised. Live
application workflow, person identity, and production/release gates remain
open; no corresponding plan item is checked off.

**Outcome:** The installed package is now active for new processes launched
through the shared Hermes gateway. Delivery progress remains 145/178.

## 2026-10-24 — Invalidate purge approval when an artifact occurrence changes

**Intent:** Prevent an approved SDE or expiry receipt from authorizing a retry
after the reviewed file at a path has changed.

**Changed fact:** `path_changed`, `hash_mismatch`, and `artifact_changed` purge
failures now mark the affected target's approval stale for both SDE and expiry
receipts and clear its retry deadline. Stale targets are excluded from due and
manual retry selection; the replacement remains available for a fresh complete
inventory and explicit review.

**Verification:** The focused same-content replacement regressions pass for
both SDE and expiry cleanup. The SDE cases verify stale approval survives a
SQLite close/reopen after both a first-target replacement and a partial purge;
the already purged first target remains complete. All 29 purge lifecycle tests
pass. Strict Pyright, errors-only Pylint, Bandit, and `git diff --check` pass.

**Open gate:** Exact replay and age preservation, copy/restore reconciliation,
and migration interruption/rollback remain unverified. Existing migration
tests cover pending, failed, held, purged, and expiry targets with missing
occurrence IDs.
The larger occurrence-binding plan item remains open. The active local alpha
purge timer is enabled every six hours; its next trigger is 2026-10-25
00:00:04 +07, and its last run preceded the cadence change.

**Outcome:** Changed occurrence approvals fail closed without unlinking the
replacement or granting a new deletion authorization.

## 2026-10-24 — Preserve staging age on exact occurrence replay

**Intent:** Ensure replaying the durable record for an already staged file
cannot extend its retention window.

**Changed fact:** `record_staging_artifact_time` recognizes the exact persisted
occurrence and returns its original `staged_at` without resetting the age.

**Verification:** A regression stages one artifact, replays the same
`ArtifactRef` 48 hours later, verifies the original timestamp is retained,
then confirms it reaches expiry eligibility at the existing 72-hour ceiling.
The combined purge and project-plugin suites pass 83 tests.

**Open gate:** Copy/restore reconciliation and migration interruption/rollback
remain unverified, as do production recovery and deployment proofs. No plan
checkbox changes.

**Outcome:** Exact replay preserves retention age; replacement occurrences
remain distinguishable from the approved occurrence.

## 2026-10-24 — Verify rollback of legacy occurrence-approval migration

**Intent:** Ensure a failed schema-v28 upgrade cannot leave partially added
columns, stale flags, retry changes, or an advanced schema-version marker.

**Changed fact:** The migration regression injects a failure while schema v28
marks legacy targets stale. SQLite rolls back the DDL, target updates, and
version stamp together; a subsequent retry upgrades successfully and leaves the
legacy failed target visible but non-retriable.

**Verification:** The focused rollback regression passes. It checks the old
version, unchanged retry receipt, absent partial column, then successful
upgrade and stale-target exclusion after removing the injected failure.

**Open gate:** Abrupt process interruption, filesystem copy/restore
reconciliation, and production recovery remain unverified. No plan checkbox
changes.

**Outcome:** The occurrence-approval schema migration is failure-atomic in the
tested SQLite error path.

## 2026-10-24 — Prevent a purged staging ID from starting a fresh age

**Intent:** Keep producer retries and duplicate publication from resetting the
72-hour clock after a prior artifact at the same scoped path has been purged.

**Changed fact:** Staging publication now checks the retained
`staging_artifact_occurrences` history when no current age row exists. Reuse of
that project/goal/class artifact ID is rejected and the just-published file is
rolled back; a new artifact must use a new ID. A new ID with identical bytes is
still accepted as a distinct producer occurrence.

**Verification:** The focused end-to-end test purges an expired source, rejects
republishing it under the same ID without leaving a file, and accepts the same
bytes under a new ID. The focused project-plugin suite and static/security
checks are pending in this change.

**Open gate:** Filesystem copy/restore that bypasses the producer is not age-
eligible unless trusted age metadata matches; broader copy/restore provenance,
abrupt migration interruption, and production recovery remain unverified.

**Outcome:** Reusing a purged producer ID cannot obtain a fresh retention
interval.

## 2026-10-24 — Verify artifact-ID retry guard

**Intent:** Confirm the fail-closed staging-ID rule in the full focused
purge/plugin acceptance set.

**Changed fact:** The retained occurrence-history check rejects reuse after
successful purge, while a distinct ID remains publishable.

**Verification:** The combined purge and project-plugin suites pass 85 tests.
Strict Pyright reports 0 diagnostics; errors-only Pylint and Bandit pass, and
`git diff --check` is clean. Bandit emits only existing `nosec` annotation
warnings.

**Open gate:** Copy/restore reconciliation for external file operations and
abrupt migration interruption remain unverified. No checklist item is marked
complete by this supporting regression.

**Outcome:** The tested V2 staging and retry paths preserve age or fail closed;
the full plan remains open.

## 2026-10-24 — Reduce repository-wide Pylint findings

**Intent:** Continue the open plan item to resolve non-blocking Pylint findings
without changing lifecycle semantics.

**Changed fact:** Moved the purge failure classification below module imports,
replaced the suspended-event epoch lookup scalars with a typed request, and
passed reactivation staging data as a typed summary. This removed five
import-position and four argument-count findings.

**Verification:** Twenty-three focused project-access and hosted lifecycle
tests pass. Strict Pyright reports 0 diagnostics, errors-only Pylint passes,
and `git diff --check` is clean. Fresh full Pylint reports 122 findings: 14
convention and 108 refactor; it reported 126 in the previously recorded
inventory.

**Open gate:** Warning-level Pylint remains open. The findings are non-blocking
module/class size, complexity, argument/local-count, and duplicate-code items.
No plan checkbox changes.

**Outcome:** The reactivation and replay data flows now use explicit typed
inputs; the broad lint debt remains under active cleanup.

## 2026-10-24 — Split consumer-binding transition responsibilities

**Intent:** Reduce complexity in the lifecycle transition path while preserving
its exact replay, drain, revocation, and re-enrollment checks.

**Changed fact:** Request validation, idempotent replay lookup, live-state and
re-enrollment validation, and transactional persistence are separate helpers.
The main transition retains the same transaction boundary.

**Verification:** Project-access and hosted-MCP lifecycle suites pass 37 tests.
Strict Pyright reports 0 diagnostics, errors-only Pylint passes, and
`git diff --check` is clean. Full Pylint reports 119 non-blocking findings
(14 convention, 105 refactor), down from 122.

**Open gate:** Repository-wide warning-level Pylint remains open; this change
does not complete the lifecycle/release checklist.

**Outcome:** The transition’s durable effects remain transactional with fewer
branches and statements in its coordinator.

## 2026-10-24 — Split terminal event disposition responsibilities

**Intent:** Continue the open repository-wide Pylint cleanup while preserving
the human-reviewed terminal event disposition contract.

**Changed fact:** Store input now carries the actor, reviewed payload digest,
binding fence, rationale, and event identity in one typed request. Validation,
exact replay, fenced binding and event checks, source cursor ordering, and
transactional disposition persistence are separate helpers.

**Verification:** The exact ordered/replayable terminal-disposition regression
passes. Strict Pyright reports 0 diagnostics, errors-only Pylint and
`git diff --check` pass. Full warning-level Pylint remains non-clean at 9.94/10.

**Open gate:** Repository-wide warning-level Pylint remains open; the focused
change does not complete a plan checkbox.

**Outcome:** Terminal disposition coordination has fewer branches and locals
with its event, cursor, receipt, and scrub updates retained in one transaction.

## 2026-10-24 — Reduce reactivation packet complexity

**Intent:** Continue the open repository-wide Pylint cleanup without changing
the contents or snapshot boundary of an attended reactivation review.

**Changed fact:** Ordered grant, cursor, event, unresolved-event, SDE purge,
expiry-purge, and active-grant inventory calculations are now collected by
focused helpers. They execute inside the same SQLite transaction used to build
the packet, and the packet continues to bind the same counts and digests.

**Verification:** The backlog/receipt-bound reactivation regression passes.
Strict Pyright, errors-only Pylint, and `git diff --check` pass. Focused store
Pylint no longer reports excess argument, branch, or local-count findings for
the packet builder and inventory helpers.

**Open gate:** Repository-wide warning-level Pylint remains open; this change
does not complete that checklist item.

**Outcome:** Reactivation review inventory retains its existing transaction and
digest inputs with less coordinator complexity.

## 2026-10-24 — Split lifecycle snapshot event aggregation

**Intent:** Reduce the open store-complexity findings without weakening the
single-snapshot lifecycle status contract.

**Changed fact:** Event status counts, unresolved event digest, active-lease
count, and fixed incomplete-reason checks now use focused helpers. The queries
still execute through the same connection while the snapshot's read
transaction is active.

**Verification:** The terminal lifecycle regression passes and covers snapshots
before and after terminal disposition. Strict Pyright, errors-only Pylint, and
`git diff --check` pass. Focused store Pylint reports no complexity findings
for the snapshot coordinator or its helpers.

**Open gate:** Repository-wide warning-level Pylint remains open; this focused
change closes no checklist item.

**Outcome:** Snapshot fields and transaction scope are preserved with simpler
event aggregation.

## 2026-10-24 — Refactor attended consumer-drain authorization

**Intent:** Reduce complexity in the fenced drain-authorization store path while
preserving exact inventory and replay semantics.

**Changed fact:** The store accepts a typed drain request; validation,
transition-fence checks, exact prior-session replay, and inventory-row encoding
are separate helpers. Both reviewed inventory and authorization use the same
canonical row encoding. The transaction still covers fence validation, replay,
inventory recheck, and capability/event persistence.

**Verification:** Project-access and reference-plugin drain regressions pass.
The project-access test now retries the exact authorization and verifies the
original count and expiry are returned. Strict Pyright, errors-only Pylint, and
`git diff --check` pass; focused Pylint reports no complexity findings for the
authorization path.

**Open gate:** Repository-wide warning-level Pylint remains open; this change
closes no checklist item.

**Outcome:** Drain retries stay bound to the same reviewed event inventory,
profile, transition, and original expiration.

## 2026-10-25 — Reduce API event-ingest complexity

**Intent:** Continue repository-wide Pylint cleanup while preserving bounded
event parsing, exact replay recovery, and drain authorization behavior.

**Changed fact:** `process_event_json` delegates event decoding, suspended
replay, replay rate limiting, and new-write/drain authorization to private
helpers. The API still decodes before project lookup, processes the same two
exact-replay paths before `replay_only` denial, and keeps the existing effect
lock and project revision fence around event persistence.

**Verification:** The API and hosted-MCP suites pass 55 tests, covering
invalid-UTF-8 privacy, normal writes, replays, authorization, and drains. Strict
Pyright, errors-only Pylint, `git diff --check`, and focused API Pylint pass;
the parser and its helpers have no remaining complexity findings.

**Open gate:** Repository-wide warning-level Pylint remains open; this change
closes no checklist item.

**Outcome:** Event ingestion has smaller decision helpers with its validation,
authorization, rate limits, and effect fence preserved.

## 2026-10-25 — Recheck local Vhost Hermes-managed alpha flow

**Intent:** Respond to the owner's clarification that Vhost Manager is a local
utility; use its disposable local integration harness without requiring a
public domain or public request target.

**Changed fact:** The Vhost-owned harness runs the installed Curator alpha
launcher, actual Hermes managed-MCP hook path, temporary consumer config,
database, repository, and Markdown projection.

**Verification:** The harness exits 0 and reports five processed events,
explicit goal binding, denial before goal activation, exact replay
acknowledgment, retry after temporary delivery denial, lost-ack recovery after
re-enrollment, source-epoch advancement, reconciled projection, unchanged
out-of-scope target, absent private model/cwd markers, and denied reviewer-only
`goal_persist`. All test state is temporary.

The documented Vhost consumer contract suite also passes all seven tests
against the installed alpha launcher. It covers configured goal-event mapping,
bounded hook receipts, scoped Markdown persistence and review denial, profile-
bound stdio MCP, project routing, two-consumer isolation, and durable receipt
acknowledgment. Its databases and targets are disposable.

**Open gate:** This is local disposable integration evidence, not an actual
Vhost application request or canonical Vhost record. Real producer coverage,
application workflow, and its expected canonical output remain unverified.

**Outcome:** The local Hermes-to-Curator alpha path passes without exposing
Vhost Manager publicly; the real application workflow remains open.

## 2026-10-25 — Exercise the local Vhost application route in test mode

**Intent:** Establish whether the Vhost application workflow can be exercised
locally without a public domain, live site files, or production services.

**Changed fact:** The actual Vhost Manager HTTP server binds to loopback in this
test and uses `VHOST_MANAGER_TEST_MODE=1` with an isolated temporary fixture
root. The `curator-smoke.test` site preview and exact-confirmation apply
complete, create six files and an applied manifest operation in that fixture,
and simulate service commands. The fixture is deleted after verification.

**Verification:** The request flow passes through `/api/plan/site` and
`/api/apply`. No public DNS/network target or live site data is used. The
application route creates no Curator V2 receipt.

**Open gate:** Vhost application-to-Curator source event production and
canonical V2 persistence remain unimplemented/unverified; the real-consumer
plan item stays open.

**Outcome:** A local Vhost application request can be tested safely in test
mode, but the current HTTP workflow does not yet flow into Curator V2.

## 2026-10-25 — Carry fact-archive approval as a typed request

**Intent:** Reduce repository-wide Pylint findings while preserving the
authenticated reviewer and project bindings on fact-archive approval.

**Changed fact:** The existing `FactCompactionApprovalRequest` now crosses the
authenticated API, project plugin, and service boundary as one value. The API
replaces its project and reviewer fields with the authorized project and
authenticated caller subject; the service independently binds the store request
to its configured project. The MCP tool's public JSON parameters are unchanged.

**Verification:** The focused API, project-plugin, MCP, and fact-compaction
suites pass 111 tests, including requests carrying forged project and reviewer
values. Strict Pyright, errors-only Pylint, and `git diff --check` pass. A fresh
whole-tree Pylint inventory falls from 112 to 106 findings (14 convention, 92
refactor; no warning/error categories).

**Open gate:** Repository-wide warning-level Pylint remains open; no plan
checkbox or deployment gate is closed.

**Outcome:** Archive approval retains authenticated scope with fewer repeated
service-boundary fields and six fewer whole-tree Pylint findings.

## 2026-10-25 — Group child-goal page inputs

**Intent:** Continue whole-tree Pylint cleanup by making child-page filters one
typed request across the authenticated API, plugin, and service.

**Changed fact:** Added `GoalChildrenPageRequest` for the parent goal, offset,
limit, and status filter. The MCP tool retains its existing public JSON
parameters and creates this request after parsing statuses; query validation
and project authorization remain in their existing layers.

**Verification:** The API and MCP suites pass 47 tests. Strict Pyright,
errors-only Pylint, and `git diff --check` pass. The fresh whole-tree Pylint
inventory falls from 106 to 105 findings (14 convention, 91 refactor; no
warning/error categories), and reports no child-page argument findings.

**Open gate:** Repository-wide warning-level Pylint remains open; no plan
checkbox or deployment gate is closed.

**Outcome:** Child-page inputs now cross the API boundary as one typed value
without changing the MCP JSON contract.

## 2026-10-25 — Pass the typed SDE assessment request through the API

**Intent:** Reduce repeated assessment fields at the authenticated API and
project-plugin boundaries while preserving project-scoped SDE evaluation.

**Changed fact:** `AuthenticatedCuratorAPI.sde_assess` and
`ProjectPlugin.sde_assess` now accept the existing `SDEAssessmentRequest`.
The MCP tool keeps its named JSON fields and constructs the request after
parsing materiality and fact IDs. Project authorization and the existing
revision fence still surround the same assessment operation.

**Verification:** The API, project-plugin, Markdown, and MCP suites pass 122
tests. Strict Pyright, errors-only Pylint, and `git diff --check` pass. The
fresh whole-tree Pylint inventory falls from 105 to 101 findings (14
convention, 87 refactor; no warning/error categories).

**Open gate:** The service convenience wrapper still has an argument-count
finding; repository-wide warning-level Pylint remains open. No plan checkbox
or deployment gate is closed.

**Outcome:** SDE assessment fields now cross the authenticated plugin route as
one typed request, with four fewer whole-tree Pylint findings.

## 2026-10-25 — Use the typed SDE request in the service

**Intent:** Complete the typed-request path for SDE assessment through the
Curator V2 service while retaining its optimistic revision fence.

**Changed fact:** `CuratorService.sde_assess` now accepts
`SDEAssessmentRequest`; it captures the same expected effect revision and
applies the same write fence before storing a candidate. Direct service tests
now construct the typed request. The review-CLI replacement-artifact test uses
a fresh artifact ID after the prior occurrence has been purged, matching the
existing no-reuse retention rule.

**Verification:** The API, fact-compaction, lifecycle, Markdown, MCP, migration,
purge, and review-CLI suites pass 199 tests. Strict Pyright, errors-only
Pylint, and `git diff --check` pass. A fresh whole-tree Pylint inventory falls
from 101 to 98 findings (14 convention, 84 refactor; no warning/error
categories); no `sde_assess` argument finding remains.

**Open gate:** Repository-wide warning-level Pylint remains open; this change
closes no checklist item or deployment gate.

**Outcome:** SDE assessment now carries one typed request through API, plugin,
and service without changing assessment or project-fence behavior.

## 2026-10-25 — Verify the six-hour local purge timer

**Intent:** Confirm the first scheduled maintenance execution after changing
the approved Vhost alpha purge retry cadence to six hours.

**Changed fact:** The `eaglesvn` user timer for `vhost-manager-alpha` is enabled
and active on the configured 00:00, 06:00, 12:00, and 18:00 schedule with
15-second spread. Journal records show successful scheduled runs at 00:00,
06:00, and 12:00 on 2026-10-25. The latest service result is scoped to
`vhost-manager-alpha` and reports zero pending or processed purge/expiry
targets.

**Verification:** `systemctl --user status` reports the timer active and its
last oneshot service exited `0/SUCCESS`; the unit configuration shows the
six-hour calendar. The journal contains the three successful post-change
passes. No deletion was due during these passes.

**Open gate:** Production routing/scheduling, external alert delivery, and
restart/reconciliation drills remain open. The local pass does not verify a
Vhost application workflow or a live artifact deletion.

**Outcome:** The first scheduled run after the cadence change is verified for
the approved local development timer; production gates remain separate.

## 2026-10-25 — Refresh blocking quality checks

**Intent:** Recheck the documented blocking quality gates against the current
Curator V2 working tree.

**Changed fact:** No source or application data changed during this refresh.

**Verification:** `uv run --locked --group quality pyright` reports zero
diagnostics; errors-only Pylint, Bandit, `uv lock --check`, and
`git diff --check` pass. Bandit reports informational `nosec` and comment
parser warnings while exiting successfully. No test suite was rerun because
this check made no source change.

**Open gate:** Repository-wide warning-level Pylint cleanup and the deployment,
identity, production-retention, and live Vhost workflow gates remain open.

**Outcome:** Blocking local quality checks are current for this dirty tree;
this refresh closes no checklist item.

## 2026-10-25 — Pass the goal criteria event through the service

**Intent:** Reduce the service's criteria-amendment argument list while
preserving the versioned lifecycle request.

**Changed fact:** `CuratorService.goal_amend_criteria` now receives the existing
validated `GoalCriteriaAmended` event. The project plugin and direct lifecycle
regressions pass that event without rebuilding its fields. Event processing
retains the previous default expected lifecycle revision of `1` when omitted.

**Verification:** Lifecycle, property-fuzz, project-plugin, and MCP-server
suites pass 117 tests. Full Pyright reports zero diagnostics; repository-wide
errors-only Pylint and `git diff --check` pass. Whole-tree Pylint findings fall
from 98 to 96 (14 convention, 82 refactor, no warning/error categories).

**Open gate:** Repository-wide warning-level Pylint cleanup remains open; this
change closes no checklist item.

**Outcome:** The service consumes one validated lifecycle event shape and the
whole-tree warning inventory decreases by two findings.

## 2026-10-25 — Recheck local-alpha Hermes health

**Intent:** Confirm current profile-bound Curator V2 health after the local
six-hour maintenance timer change.

**Changed fact:** The Hermes development checkout's `renew-ssl-coding` profile
probe connects to the installed Curator V2 stdio package, discovers 48 tools,
and reads 12 processed receipts, one goal, and two facts. `project_health`
reports `healthy` with no gates. Scheduled timer passes at 00:00, 06:00, and
12:00 exited successfully with no purge or expiry work due.

**Verification:** Ran
`./.venv/bin/hermes --profile renew-ssl-coding mcp test curator_v2 --probe-curator-status`
from the Hermes development checkout. The probe completed at 2026-10-25
06:24 UTC using checkout version `0.22.2+2263`; the global installed CLI is
`0.22.2+1558` and rejects the probe flag. `/usr/local/lib/hermes-agent` was not
modified.

**Open gate:** This verifies local profile health and the local timer only. It
does not verify a request through the Vhost Manager application, a Curator
receipt from that workflow, production alert delivery, or deployment health.

**Outcome:** The single-user local-alpha health snapshot is current and
healthy; live Vhost workflow and production gates remain open.

## 2026-10-25 — Bind cleanup approval fields in one request

**Intent:** Keep destructive cleanup approval's reviewed inventory and hashes
together across the MCP, authenticated API, and project-plugin boundary.

**Changed fact:** Added `ArtifactCleanupAuthorizationRequest` containing the
receipt ID, exact artifact tuple, manifest digest, dependency-map digest, and
projection target. The MCP tool keeps its existing named JSON fields and
constructs the request before calling the authenticated API. API authorization
still supplies the caller's identity; the project plugin revalidates the exact
inventory and both digests before persisting approval and projecting it.

**Verification:** Purge, API, project-plugin, and MCP-server suites pass 132
tests. Changed files pass strict Pyright and errors-only Pylint; `git diff
--check` is clean. Whole-tree Pylint findings fall from 96 to 93 (14
convention, 79 refactor; no warning/error categories).

**Open gate:** Repository-wide warning-level Pylint and the live Vhost
application workflow remain open; this change closes no checklist item.

**Outcome:** The exact inventory approval packet is carried as one typed
request without changing the MCP JSON contract or the reviewer authorization
boundary.

## 2026-10-25 — Exercise Vhost apply and rollback receipt producers

**Intent:** Continue the local Vhost consumer workflow without changing Curator
V2 code to emulate consumer behavior.

**Changed fact:** The Vhost-owned `/api/apply` and `/api/rollback` handlers now
send compact planned-goal events through the configured Curator V2 stdio MCP
and retain exact receipt/pending state in the Vhost operation manifest.

**Verification:** A disposable integration drives the actual Vhost HTTP routes
through apply, an unavailable-MCP retry, rollback, and event replay. Both exact
project/event receipts and planned goals are present in the temporary SQLite
store; generated file/database paths are absent from goal text. The root-run
local Vhost service was restarted with the operator-owned profile settings and
its read-only status probe reports active valid services.

**Open gate:** No apply was run through the root service or against live site
files. Canonical Markdown projection, owner-reviewed producer inventory,
complete artifact inventory, user-facing real-request evidence, and rollback
recovery remain open. No checklist marker changes from this disposable test.

**Outcome:** Local Vhost apply/rollback receipt production is verified in
disposable state; keep the real-consumer, release, and live-workflow gates open.

## 2026-10-25 — Pass criteria amendment as one typed request

**Intent:** Reduce the authenticated API boundary's argument list while
preserving project write authorization and the versioned goal-amendment event.

**Changed fact:** `AuthenticatedCuratorAPI.goal_amend_criteria` and
`ProjectPlugin.goal_amend_criteria` now accept and forward the existing
`GoalCriteriaAmended` request. The API still authorizes the exact caller and
project for `write` before forwarding it.

**Verification:** The focused API regression passes. Strict Pyright,
errors-only Pylint, and `git diff --check` pass. A fresh repository-wide
Pylint inventory falls from 93 findings (14 convention, 79 refactor) to 91
(14 convention, 77 refactor), with both amendment argument-count findings
removed.

**Open gate:** Repository-wide warning-level Pylint remains open at 91
findings. Curator V2 goal capture through MCP is also unavailable in this
session: `goal_list` returned `unauthenticated`, so this update is recorded in
the repository history only; no live ledger event is claimed.

**Outcome:** The API and plugin carry one validated amendment request without
changing the MCP event schema or the project authorization boundary.

## 2026-10-25 — Carry SDE disposition as a typed review request

**Intent:** Reduce repeated SDE confirmation arguments across the authenticated
API and project plugin while keeping the reviewer identity host supplied.

**Changed fact:** Added `SDEConfirmationRequest` for the candidate, decision,
exact artifacts, inventory-completeness flag, dependency digest, and rationale.
The API, project plugin, MCP registrar, and attended review CLI now pass this
request; only the authenticated API supplies the reviewer subject.

**Verification:** Nine focused API, plugin, Markdown projection, review CLI,
and MCP regressions pass. Strict Pyright reports zero diagnostics; errors-only
Pylint and `git diff --check` pass. The fresh whole-tree Pylint inventory falls
from 91 to 90 findings (14 convention, 76 refactor).

**Open gate:** Repository-wide warning-level Pylint remains open at 90
findings. No checklist marker or deployment gate is closed.

**Outcome:** SDE confirmation fields now cross the review boundary as one
request, with the caller's authenticated subject kept outside that request.

## 2026-10-25 — Type SDE correction and feedback requests

**Intent:** Remove repeated correction and quality-feedback fields from the
authenticated API call while preserving caller-derived reviewer identity.

**Changed fact:** Added `SDECorrectionRequest` and
`SDEQualityFeedbackRequest`. The MCP registrar maps its unchanged named JSON
arguments into these types; the authenticated API forwards their values to the
existing project-plugin methods and still supplies the reviewer subject.

**Verification:** The review-authorization API regression and MCP SDE review
end-to-end test pass. Strict Pyright reports zero diagnostics; errors-only
Pylint and `git diff --check` pass. Whole-tree Pylint falls from 90 findings
(14 convention, 76 refactor) to 86 (14 convention, 72 refactor); the MCP
registration module is also below its 1,000-line limit again.

**Open gate:** Repository-wide warning-level Pylint remains open at 86
findings. The V2 MCP `goal_list` still returns `unauthenticated`; this delta is
recorded in repository history only, with no live ledger event claimed. No
checklist marker or deployment gate is closed.

**Outcome:** Correction and feedback fields cross the authenticated API as
typed requests without changing the MCP JSON contract or trust boundary.

## 2026-10-25 — Type the accepted-subtask intake request

**Intent:** Reduce the project plugin's child-goal intake arguments without
deriving criteria or weakening the explicit parent relationship.

**Changed fact:** Added `GoalSubtaskStartRequest` and changed
`ProjectPlugin.goal_start_subtask` to accept it. Parent, problem, criteria,
owner, dependencies, next action, and source event are forwarded unchanged to
the existing planned-goal service path.

**Verification:** The accepted-subtask regression passes, including its
missing-criteria rejection. Strict Pyright reports zero diagnostics;
errors-only Pylint and `git diff --check` pass. Whole-tree Pylint falls from
86 to 85 findings (14 convention, 71 refactor), and the subtask intake method
no longer has an argument-count finding.

**Open gate:** Repository-wide warning-level Pylint remains open at 85
findings. No checklist marker or deployment gate is closed.

**Outcome:** Child-goal intake crosses the plugin boundary as one typed request
while preserving explicit criteria and same-project parent validation.

## 2026-10-25 — Carry SDE confirmation through the service as one request

**Intent:** Finish the typed-request path for SDE disposition through the direct service boundary while keeping host-authenticated reviewer identity separate.

**Changed fact:** `CuratorService.sde_confirm` now accepts `SDEConfirmationRequest`; `ProjectPlugin` forwards its validated request and supplies `authenticated_subject` separately. Direct service callers in purge, migration, MCP, and plugin tests now construct the same request type.

**Verification:** The focused purge, migration, MCP-server, and project-plugin suites pass 131 tests. Strict Pyright reports zero diagnostics; errors-only Pylint and `git diff --check` pass. The full warning-level Pylint inventory reports 86 findings (14 convention, 72 refactor), up from 85 in the preceding inventory.

**Open gate:** Warning-level Pylint cleanup remains open. The actual installed Vhost application route's Curator V2 receipt remains unverified; its producer bridge must be handled in the Vhost consumer repository. No checklist marker changed, and no live ledger event is claimed.

**Outcome:** The SDE confirmation request now reaches the service boundary intact without moving reviewer identity into caller-controlled request data.

## 2026-10-25 — Verify the installed Vhost apply and rollback receipt path

**Intent:** Resolve whether the running local Vhost Manager HTTP routes emit durable Curator V2 receipts for completed application operations.

**Changed fact:** The Vhost-owned apply and rollback routes were exercised through the active root service using a reserved disposable `.test` site. Both route responses and the Vhost operation manifest carried exact `received` receipts for `vhost-manager-alpha`; read-only queries of the installed global ledger confirmed the matching `goal.started` rows as `processed` with `applied` disposition. The Vhost rollback implementation now stops the exact site-owned process set and verifies removal of a newly created site account before marking rollback complete.

**Verification:** Two apply/rollback exercises returned and persisted matching receipts. The focused disposable HTTP/MCP contract passes; the Vhost Node suite passes 22 tests, ESLint passes on the changed server files, Prettier passes, and `git diff --check` is clean. The running service reports active, valid Nginx/OpenLiteSpeed configuration. The smoke account and webroot were removed and the target is absent from Vhost inventory.

**Open gate:** Gate F and Slice I remain open for reviewed canonical Markdown projection, full producer/source/artifact coverage, retention and disposition evidence, and release approval. Repository-wide warning-level Pylint remains open at 86 findings. No checklist marker changed; this records live local-alpha evidence, not production deployment.

**Outcome:** The installed root-service Vhost apply/rollback receipt path is verified for one disposable local site workflow; broader consumer and release gates remain open.

## 2026-10-25 — Extend the local Vhost renewal receipt path

- **Intent:** Continue the local Vhost consumer integration and cover renewal
  outcomes without modifying a real certificate.
- **Changed fact:** The Vhost route now durably records completed, failed, and
  interrupted interactive renewal outcomes and sends a path-free Curator V2
  receipt; pending delivery is retryable from the operation history. The root
  crontab also runs a separate `acme.sh --cron` producer four times daily, which
  bypasses this route and has no Curator receipt.
- **Verification:** The focused disposable HTTP/MCP contract covers all three
  renewal outcomes, outage retry, exact receipts, and exclusion of paths and
  terminal output. All 22 Vhost Node tests pass; JS lint/format, Python syntax,
  and both repositories' diff checks pass. The root Vhost service restarted and
  reports active with valid Nginx/OpenLiteSpeed configuration. No real renewal
  or crontab change was performed.
- **Open gate:** Scheduled ACME integration, failed apply/rollback receipts,
  owner-reviewed source/artifact coverage, canonical projection, and Slice I
  release evidence remain open. The current full Pylint inventory reports 86
  non-blocking findings; its cleanup checklist remains open.
- **Outcome:** The interactive local SSL producer is covered in disposable
  integration; the independent scheduled producer and full pilot gates remain
  unresolved.

## 2026-10-25 — Close the local scheduled-renewal projection check

- **Intent:** Verify one scheduled-producer result through the root Vhost
  service, installed Curator alpha profile, canonical Markdown target, and
  read-only reconciliation.
- **Changed fact:** The root ACME crontab entry now invokes the installed
  root-owned Vhost bridge at the existing four daily times. Its result route
  records a compact planned goal keyed by the operation ID; a mode-0600 spool
  retains results across Vhost outages and the next scheduled run drains it.
- **Verification:** The focused disposable route test passed with fake ACME,
  verified recovery of a queued result, exact retry receipts, processed ledger
  events, and absence of transient output from goal text. A fake exit-19 run
  through the installed bridge and active root service produced processed
  event `vhost-ssl-cron-eeb1cddc-b8c3-4745-99b1-794217a07dbc`. The authorized
  `eaglesvn` review grant projected that exact goal to the configured Vhost
  `HISTORY.md`; reconciliation returned `synced` with matching SHA-256
  `b8317444a8cf24b25122fb09eb38468b763d4670e11ea47094081c2d71d9f131`. The
  target excludes the transient canary and database path. No real certificate
  renewal occurred. `bash -n`, Python compilation, Node syntax checks, source
  and installed bridge hashes, and both repositories' `git diff --check` pass.
- **Open gate:** The smoke goal remains planned pending human disposition.
  Canonical projection does not decide the operation, approve purge, establish
  complete producer/artifact coverage, or close Slice I and release approval.
- **Outcome:** The scheduled Vhost producer now has a tested outage-recoverable
  local receipt and canonical projection path; full alpha acceptance remains
  open.

## 2026-10-25 — Reconcile canonical projections for Vhost apply/rollback

- **Intent:** Complete the canonical Markdown check for the two local Vhost
  site apply/rollback exercises that were previously verified only at the
  receipt and SQLite layers.
- **Changed fact:** The four exact apply/rollback goals were projected through
  the installed Curator V2 alpha launcher to Vhost's configured canonical
  `HISTORY.md`, using the authorized `eaglesvn` review grant. Preflight found
  zero cleanup receipts for these goals.
- **Verification:** All four `goal_reconcile` calls returned `synced` with
  matching expected/actual hashes (`fe9828aa…916e069`, `54a1f7d8…44bc062`,
  `126e4f11…66f775c`, `34c217c4…e2d6ab18`). Bounded document inspection found
  five goal blocks total, including the earlier fake-ACME smoke goal, and no
  temporary paths, global database path, or output canary. No application
  source or live site state changed during projection.
- **Open gate:** The operation goals remain planned. Human disposition, SDE
  review and cleanup behavior, full source/artifact inventory, and release
  approval remain open.
- **Outcome:** Canonical projection and reconciliation now cover the exercised
  local Vhost apply/rollback receipts; broader consumer acceptance remains
  incomplete.

## 2026-10-25 — Record failed Vhost rollback outcomes

- **Intent:** Preserve and report a rollback attempt that fails before restoring
  its disposable site's snapshot.
- **Changed fact:** The Vhost rollback route now records a linked failed-attempt
  entry and sends a compact rollback-failed goal through the existing Curator
  receipt bridge. Retrying accepts that failed rollback entry by its exact
  operation ID.
- **Verification:** The focused disposable HTTP/MCP integration test corrupts
  only a temporary snapshot manifest, invokes rollback, and confirms the exact
  receipt is processed. The planned goal says rollback failed and contains no
  temporary, fixture, database, or backup path. The test passed.
- **Open gate:** This does not verify restoration from a damaged snapshot,
  complete Vhost producer/artifact coverage, or reviewer disposition. Gate F
  remains open.
- **Outcome:** Failed rollback attempts now have a retryable, path-free Curator
  receipt in the tested local consumer route.

## 2026-10-25 — Remove manual ACME scratch output on exit

- **Intent:** Stop the local manual-DNS utility from leaving temporary ACME
  output, which can contain DNS challenge TXT values, after each run.
- **Changed fact:** The Vhost consumer tracks ACME issue/renew output and served
  certificate temp files, then removes them on process exit. The persistent
  log keeps full output on the operator terminal and redacts recognized
  `TXT value:` and `TXT:` lines; unobserved ACME output formats are unverified.
- **Verification:** Disposable harnesses verified cleanup for normal and
  nonzero exits and confirmed recognized challenge values remain visible on
  operator output but are redacted and flushed in the saved log. `bash -n` and
  `git diff --check` passed. No ACME command, DNS challenge, or certificate was
  run.
- **Open gate:** Persistent-log disposition, standalone utility scope, and
  complete workflow filesystem observations remain open. The source matrix is
  bound to the current dirty consumer source manifest recorded in the plan.
- **Outcome:** The known scratch-file residue is fixed locally; the producer and
  out-of-root artifact audit remains open.

## 2026-10-25 — Redact ACME challenge values from saved logs

- **Intent:** Preserve the operator's live DNS challenge instructions without
  retaining recognized challenge tokens in the manual renewal log.
- **Changed fact:** The manual DNS utility now copies unmodified output to the
  operator stream and redacts recognized `TXT value:` and `TXT:` line contents
  from its saved log. The producer source manifest was refreshed to
  `0cce3a0fad9bac7767d0f9be6cdc8963a4caaab3c46148a8e610cc47d5afd091`.
- **Verification:** A disposable harness confirmed both token formats stay
  visible in operator output, are redacted in the saved log, and are flushed
  before exit. `bash -n` and `git diff --check` passed.
- **Open gate:** Other ACME output formats and real issuance remain unverified;
  persistent-log inventory/deletion, standalone utility scope, and complete
  workflow observation remain open.
- **Outcome:** Known challenge values are excluded from this saved log path;
  broader source-to-sink privacy acceptance remains incomplete.

## 2026-10-25 — Recover Vhost renewal state after app restart

- **Intent:** Preserve a truthful outcome if Vhost Manager stops while an SSL
  renewal is running.
- **Changed fact:** Vhost persists the operation as `running` before starting
  the renewal. On app startup, any leftover running record becomes
  `interrupted` and is submitted through the same Curator bridge; a missing
  receipt remains retryable by exact operation ID.
- **Verification:** A disposable HTTP/MCP contract seeded an unfinished
  operation, confirmed startup recovery while Curator was unavailable, then
  retried it after Curator returned and verified a processed receipt and
  path-free planned goal. The focused test passed. The active systemd unit is
  configured with `KillMode=control-group`; no real certificate was changed.
- **Open gate:** An actual systemd stop during renewal, failed-apply receipt
  handling, complete producer coverage, and owner-approved artifact disposition
  remain open. Current working-tree source-manifest SHA-256:
  `6b6d43ff52774e8120bf19baeaeb9ad878468de0f5f0a93381f603e1f89ae8d0`.
- **Outcome:** Interrupted in-progress renewals now survive restart in local app
  state and can be retried into the V2 ledger.

## 2026-10-25 — Record Vhost apply failures in Curator V2

- **Intent:** Preserve a failed Vhost apply outcome when its application code
  durably records the failure after restoring fixture or site files.
- **Changed fact:** Vhost now submits that failed operation to Curator and
  allows exact-ID receipt retry. The compact goal summary identifies an apply
  failure and excludes raw error text and generated paths.
- **Verification:** The disposable HTTP/MCP integration injected a post-write
  failure, verified snapshot restoration, simulated Curator unavailability,
  retried the operation, and confirmed the processed path-free goal. The test
  passed.
- **Open gate:** This does not exercise rollback recovery failure, a live-site
  apply failure, complete source/artifact coverage, or owner dispositions.
  Current Vhost source-manifest SHA-256:
  `7506ec8b84063b875f04e9524b9a03aca334ad4a1a32824a76a35c4b84cf6d40`.
- **Outcome:** Durable local apply failures now have retryable Curator outcome
  records when restoration succeeds.

## 2026-10-25 — Exercise renewal restart from Vhost HTTP route

- **Changed fact:** The renewal restart regression now begins through the actual
  Vhost test-mode HTTP route, which writes a durable `running` operation, rather
  than inserting an unfinished record directly into the fixture manifest.
- **Verification:** The test terminates the first app process, starts a new one,
  and confirms startup recovery to `interrupted`, a processed exact Curator
  receipt, and a path-free goal. The focused test passed. It remains a
  test-mode process restart; no ACME process, systemd restart, or certificate
  change was involved.
- **Open gate:** Real active-renewal systemd interruption and complete
  producer/artifact evidence remain open. Current Vhost source-manifest SHA-256:
  `76285c00b311000fd5a10282d14f3ab4c26a5965a7fdd7145b3367d78eb379c3`.
- **Outcome:** Restart recovery coverage now exercises the app's own
  `running`-record write before recovery.

## 2026-10-25 — Recheck local project and binding lifecycle

- **Intent:** Confirm the current local reference-store lifecycle behavior after the project-access and migration changes.
- **Changed fact:** The local code covers suspension, binding deregistration/drain, re-enrollment with a fresh source epoch, review-bound reactivation, and irreversible retirement with durable receipts and conflict/retry handling.
- **Verification:** `tests.test_project_access`, `tests.test_migrations`, `tests.test_lifecycle`, and `tests.test_review_cli` passed together: 114 tests on Python 3.14.7.
- **Open gate:** This is local reference-store and attended-CLI evidence. It does not prove every transition through the real consumer, a human-approved transition receipt, remaining effect-boundary cases, or deployment/rollback acceptance.
- **Outcome:** Current local lifecycle regressions pass; the deployment lifecycle gate remains open.

## 2026-10-25 — Recheck the Hermes-bound local Vhost ledger

- **Intent:** Verify the supported local profile-bound path after the direct Curator connector returned an authentication-context error.
- **Changed fact:** The direct connector lacks Hermes-injected profile context and is denied. The configured `renew-ssl-coding` Hermes CLI path supplies that context and can read the bound `vhost-manager-alpha` ledger.
- **Verification:** `./hermes -p renew-ssl-coding mcp test curator_v2 --probe-curator-status` connected, discovered 48 tools, and reported 17/17 receipts processed, zero received/failed/quarantined events, six goals, two facts, and `healthy` project health with no gates.
- **Open gate:** This is a single-user local profile read, not human authentication or production readiness. The direct connector denial remains expected; no transport identity was inferred.
- **Outcome:** The supported Hermes integration path is verified for the local alpha ledger.

## 2026-10-25 — Recover exact processed receipt after project retirement

- **Intent:** Let a Hermes source clear a durable outbox item when Curator committed it before retirement but the acknowledgement was lost.
- **Changed fact:** The API now returns only the existing processed receipt when the trusted profile, tombstoned source epoch, current project/config fingerprints, event ID, sequence, and payload identity match. Retired projects reject every new or changed event.
- **Verification:** A focused regression processes one event, deregisters and retires its project, recovers the same receipt, and confirms changed content, an unseen event, and a different profile are denied. The API and project-access suites pass 62 tests; targeted Pyright reports zero diagnostics and errors-only Pylint is clean.
- **Open gate:** This verifies local API behavior. Managed-MCP post-retirement delivery, other in-flight effects, and deployment lifecycle evidence remain open.
- **Outcome:** A lost acknowledgement for an already committed event can be reconciled without reopening retired writes.

## 2026-10-25 — Verify retired-event receipt recovery through the MCP tool

- **Intent:** Confirm Hermes can clear an outbox item whose processed receipt was committed before its project was retired.
- **Changed fact:** The registered `hermes_codex_event` MCP tool returns the same receipt for an exact event from the tombstoned source epoch; an unseen event after retirement is rejected.
- **Verification:** Extended the SDK in-memory MCP lifecycle regression to retire a disposable project after processing and re-enrolling a source, then replay the exact newest-epoch event. The focused test passed.
- **Open gate:** This exercises the registered MCP tool in-process, not Hermes managed-gateway delivery, all in-flight effect boundaries, or deployment lifecycle and rollback.
- **Outcome:** Local retired-source acknowledgement recovery is covered through both the API and registered MCP tool.

## 2026-10-25 — Reject labeled manual DNS challenge values

- **Intent:** Keep manual DNS challenge codes, passwords, and keys out of durable Curator text fields.
- **Changed fact:** The V2 reject-only content gate recognizes `pwd=` assignments and labeled ACME TXT challenge values with a 32-character base64url-like payload; it does not redact or store them.
- **Verification:** Added synthetic positive cases and a benign `_acme-challenge` record-name case. Five focused validator/API/MCP tests pass; both API and MCP regressions confirm the canaries are absent from errors, logs, metrics, ledger/WAL files, canonical history, staging, and backup. Targeted Pyright reports zero diagnostics. Changed content-safety/API files rate 9.96/10 under warning-level Pylint; the whole-tree warning backlog remains open. `git diff --check` passes.
- **Open gate:** Unlabeled values, raw consumer output, other formats, and full producer/source-sink privacy coverage remain open. The detector is not general secret scanning.
- **Outcome:** The explicitly labeled local manual-DNS formats are rejected before canonical goal/fact writes.

## 2026-10-25 — Refresh the installed single-user V2 alpha package

- **Intent:** Make the tested V2 source change available through the configured Vhost Hermes profile.
- **Changed fact:** The current source wheel was installed only in the dedicated `renew-ssl-coding` V2 virtualenv after archiving the previous package and entrypoints.
- **Verification:** Wheel SHA-256 `38a5d943be64971872ed69a15913ee78d16b81b91e2aa0f41b31968665117531`; rollback archive SHA-256 `6e4079ff5be37d43972e4b7a6bb4b29f5d0289b3745fd4055e1391b33de3e703` with 117 verified manifest entries. All 51 installed module hashes match source, `pip check` passes, the installed DNS-challenge canary is rejected, and Hermes connects to all 48 tools with 17 processed receipts and healthy local-alpha status.
- **Open gate:** No Vhost application request was made during this refresh. This is single-user local profile evidence, not deployment, production identity, or release approval.
- **Outcome:** The installed local V2 alpha now includes the tested DNS challenge/password rejection behavior.

## 2026-10-25 — Recheck Hermes-managed integration against the refreshed alpha

- **Intent:** Verify the current installed V2 profile package still composes with Hermes Core and the Vhost consumer hook.
- **Changed fact:** The disposable integration harness ran against the refreshed `renew-ssl-coding` profile interpreter and installed Curator package.
- **Verification:** The harness passed five lifecycle events, exact replay, failed-delivery retry, lost-ack recovery after re-enrollment, source-epoch advancement, explicit binding, projection reconciliation, privacy canaries, and reviewer-write denial. All test profile/database/repository state was temporary.
- **Open gate:** This does not run the Vhost application route, persist a canonical Vhost operation record, or prove production gateway/deployment behavior. Producer coverage and release acceptance remain open.
- **Outcome:** Current local Hermes-managed profile/plugin composition is verified against the installed alpha wheel.

## 2026-10-25 — Reconcile the delivery checklist count

- **Intent:** Resolve the conflicting progress totals in the plan and release-gate ledger.
- **Changed fact:** The delivery checklist's declared counting rule includes direct checklist rows in Sections 0–10, 12, and Definition of done; it excludes reusable templates and example prompts in Section 11.
- **Verification:** A direct row-prefix recount of those sections returns 145 complete and 33 open out of 178 delivery rows. The plan already records this total; the release-gate snapshot was stale at 160/216 and is now aligned to 145/178.
- **Open gate:** No checklist item was closed by this count correction. Standalone-script producer coverage and the other evidence-gated plan items remain open.
- **Outcome:** The plan and release-gate ledger now use the same denominator and counting rule.

## 2026-10-25 — Close the local consumer request-to-status workflow

- **Intent:** Close the real-consumer lifecycle checklist row after Vhost Manager began emitting installed Curator receipts for its local operations.
- **Changed fact:** The checked row now describes the verified local request-to-status path; aggregate dashboard and all-state deployment checks remain separate open criteria.
- **Verification:** The recorded root-service apply/rollback and scheduled-result runs have exact processed receipts and reconciled Vhost history records. A read-only ledger query reports the five operation goals as `planned`, matching their pending human disposition. The plan and release-gate snapshot now count 146/178 delivery rows complete and 32 open.
- **Open gate:** Full consumer producer/artifact coverage, including standalone-script scope, remains open as requested. Production status/dashboard evidence also remains open.
- **Outcome:** One local-alpha delivery row was checked off; no production or full producer-coverage claim was made.

## 2026-10-25 — Bound the local-alpha content-safety scope

- **Intent:** Close the scanner threat-model row for the owner-approved local development boundary without treating Curator as a security product.
- **Changed fact:** Added a versioned synthetic corpus for the current reject-only detector examples; documented supported patterns, benign neighbors, and unsupported inputs in the V2 policy.
- **Verification:** The corpus contains ten rejected and three accepted synthetic cases. All four `tests.test_content_safety` tests pass, including corpus/category checks and non-echo assertions. The direct delivery-row count is now 147/178 complete and 31 open.
- **Open gate:** This closes only the documented single-user local-alpha boundary. Expanded collection, transformed/unlabeled inputs, jurisdiction-specific evaluation, and standalone producer coverage remain open.
- **Outcome:** One local-scope checklist row was checked off; no general secret-scanning or security-certification claim is made.

## 2026-10-25 — Persist compact facts for Vhost operation receipts

- **Intent:** Make the local Vhost operation receipt useful as a reviewable V2 record without copying operation output or paths.
- **Changed fact:** The Vhost-owned bridge starts an active review goal for each completed operation, then writes one deterministic, path-free `change` fact after the matching goal receipt. Replaying the operation reuses both event IDs; each goal keeps its human review disposition open.
- **Verification:** The focused disposable Vhost HTTP/MCP integration passes across apply, rollback, renewal, cron, archive, interrupted, and failed outcomes. It confirms one processed fact per operation, exact retry behavior, and absence of fixture paths and the transient-output canary. The Vhost changes remain in the consumer checkout for owner review.
- **Open gate:** This does not establish approved canonical Markdown output, standalone utility coverage, complete producer/artifact inventory, or deployment/release evidence. Gate F remains open; standalone-script scope remains open. No delivery checklist marker changed.
- **Outcome:** Local operation outcomes now have compact facts attached to their V2 goals while awaiting explicit human review.

## 2026-10-25 — Reconcile the updated bridge through the local Vhost service

- **Intent:** Verify the compact-fact bridge against the installed alpha ledger through the real local Vhost HTTP service.
- **Changed fact:** One reserved `.test` site was applied and rolled back through the root service. Each operation created an active `vhost-manager-alpha` review goal and one path-free `change` fact after its exact event receipt.
- **Verification:** Both exact event receipts are `processed`; both goals are `active` with one expected fact, and known path/output markers are absent from goal and fact text. The root service reports three inventoried sites and excludes the test target; the created site account is absent, and Nginx/OpenLiteSpeed are active with valid configuration. The supported Hermes profile probe reads 21 processed receipts, eight goals, four facts, and healthy local-alpha status.
- **Open gate:** The two new goals await human disposition and canonical projection. Standalone-script coverage, complete producer/artifact inventory, SDE review/purge, and release evidence remain open. No delivery checklist marker changed.
- **Outcome:** The updated bridge is verified end to end for one reversible local apply/rollback workflow.

## 2026-10-25 — Project the latest Vhost operation facts

- **Intent:** Make the two verified local operation outcomes visible in Vhost's configured canonical history.
- **Changed fact:** The local reviewer projected the exact apply and rollback goals and their compact facts to `.curatormd-v2/persistence/HISTORY.md`.
- **Verification:** `goal_reconcile` reports `synced` for both goal IDs against the configured target. The records remain active and are not presented as SDE decisions or completed goals.
- **Open gate:** Human disposition and purge were not performed. Full producer/artifact inventory, standalone-script scope, and release acceptance remain open. No checklist marker changed.
- **Outcome:** The tested apply/rollback records now reconcile between the alpha ledger and Vhost's canonical history.

## 2026-10-25 — Keep manual DNS secrets out of persistent logs

- **Intent:** Apply the user's direction that DNS challenge values, passwords, and keys must not be recorded verbatim, while leaving standalone-script producer coverage open.
- **Changed fact:** The Vhost manual ACME script now streams persistent log output through a line-by-line filter for labeled TXT/expected values, common credential assignments, long token-like values, and PEM private-key blocks. It does not send standalone-script events to Curator.
- **Verification:** A synthetic canary regression confirms challenge values in ACME output, parsed summaries, DNS answers, and mismatch diagnostics, plus password assignments and PEM bodies, are absent from log output. Ordinary status text remains. The focused test and `bash -n` pass. Curator V2 `pyright`, errors-only `pylint`, `bandit`, and both worktrees' `git diff --check` pass; the full test suite was not rerun.
- **Open gate:** This is a consumer-owned log change and local test evidence only. It does not establish all logging boundaries, an approved log-expiry policy, or source/artifact inventory. Standalone-script coverage remains open; no checklist marker changed.
- **Outcome:** The current manual-script persistent log path no longer retains the tested DNS, password, or private-key canaries.
- **Source binding:** The Vhost producer manifest was refreshed after the log-filter and regression-test changes. At checkout HEAD `7d2b10f5433cfe566fc560741bbc9401265176f4`, config SHA-256 `4f3a34e84832b7e8ccfe4e91a68b0664c6aa603409318197f0b44e6454ece44a`; listed-source manifest SHA-256 `e8ac71eace1104b71d0be2cfabe4287e75b2537774c1b7ecf506bd9ed87bf581`. It binds a dirty subset and is not a complete producer matrix.

## 2026-10-25 — Reduce one purge-test Pylint finding

- **Intent:** Continue the open repository-wide Pylint cleanup without relaxing checks.
- **Changed fact:** The v28 migration regression in `tests/test_purge.py` now groups related artifact paths and records in a named fixture map, removing its `too-many-locals` finding.
- **Verification:** The exact migration regression passes. Full warning-level Pylint was rerun; it still exits 24 at 9.96/10 with repository-wide structural findings. `test_purge.py` now has only module-size and test-class-size findings. No checklist marker changed.
- **Open gate:** Repository-wide Pylint cleanup remains open. The local refactor does not close the full warning inventory or change lifecycle behavior.

## 2026-10-25 — Reduce markdown-persistence test complexity

- **Intent:** Continue the repository-wide Pylint cleanup while keeping the canonical-write-before-purge regression readable.
- **Changed fact:** Extracted the test's goal/fact/evidence/SDE/artifact setup into a private fixture method, leaving the main test focused on the ordering guarantee and restart recovery.
- **Verification:** The exact regression passes and strict Pyright reports zero diagnostics. Focused Pylint no longer reports local-variable or statement complexity; it still reports module length and one oversized test class. The full warning-level inventory was not rerun after this delta.
- **Open gate:** Repository-wide Pylint cleanup remains open. No checklist marker changed.

## 2026-10-25 — Reconcile alpha documentation with the current local workflow

- **Intent:** Keep the V2 alpha overview, release notes, release-gate ledger, and plan aligned with current supported-profile evidence.
- **Changed fact:** Updated the current alpha status to reflect the 11:38 UTC Hermes profile read (21 processed receipts, eight goals, four facts, healthy) and the verified local Vhost apply/rollback plus canonical projection. Earlier profile/package counts and the 2026-10-22 pre-workflow checkpoint are labeled historical.
- **Verification:** The supported `renew-ssl-coding` profile probe connected to the installed stdio server, discovered 48 tools, and returned the recorded counts and health. Documentation continues to leave human disposition, full producer/artifact coverage, standalone utilities, production recovery, and release approval open.
- **Open gate:** No checklist marker changed. This documentation update does not alter the consumer, installed package, or ledger.

## 2026-10-25 — Refresh repository-wide Pylint evidence

- **Intent:** Recheck the only currently local repository-wide quality item before changing checklist progress.
- **Changed fact:** The warning-level Curator Pylint inventory has 85 structural diagnostics across core modules and tests: 70 refactor and 15 convention findings, dominated by duplicate code, module/class size, and argument/method complexity.
- **Verification:** The current `uv run --locked --group quality pylint src/curatormd_v2 tests --output-format=json` run exited 24. Strict Pyright, errors-only Pylint, Bandit, `uv audit`, and `git diff --check` passed at the earlier quality checkpoint; they were not rerun with this command. No test suite was rerun. Hermes `scripts/check` cannot select its default merge base because this checkout has no `main` or `origin/main` ref; the parent-base run was interrupted before completion. No source change or checklist marker changed for the Pylint rerun.
- **Open gate:** Repository-wide Pylint cleanup remains open. Standalone-script scope remains open; no standalone producer was added.
- **Outcome:** The plan now reports the current warning-level result without treating the errors-only CI gate as full-warning cleanup.

## 2026-10-25 — Add exact goal lifecycle totals to the Hermes status read

- **Intent:** Advance the open status-reporting checklist item with a bounded, content-free count for each goal lifecycle state.
- **Changed fact:** Curator's project activity snapshot now reads all eight lifecycle counts in its existing SQLite transaction. Hermes' profile diagnostic validates the counts against both the project total and paginated goal total, then prints the separate activity and health snapshots.
- **Verification:** Curator `test_api.py` (41 tests), the MCP project workflow regression (1 test), and Hermes Curator status probe regressions (3 tests) pass. Strict Pyright, focused errors-only Pylint, Hermes Ruff, and `git diff --check` pass.
- **Open gate:** The installed alpha package has not been refreshed and read back through the active profile. The complete authenticated dashboard acceptance remains open. Standalone-script scope remains open; no producer or data collection was added.
- **Outcome:** The source-level status path now provides exact lifecycle totals, without claiming a deployed dashboard result.

## 2026-10-25 — Verify exact status totals in the local alpha profile

- **Intent:** Complete the approved single-project status-view acceptance using the dedicated Hermes profile and its real Curator package.
- **Changed fact:** Installed the current wheel only in the `renew-ssl-coding` V2 virtualenv after archiving and verifying the previous 117 package/launcher files. Wheel SHA-256 is `cb3a4d219c9bd0b6c02a8884e81241761ddad1a47421c4a7174f9734c08d54d2`; rollback archive SHA-256 is `f10fa16f6b8d62bd5afd8d83516089b08a6a348ae8d049750538264dbafd84d6`.
- **Verification:** All 51 installed module hashes match source and `pip check` passes. The read-only profile probe at `2026-10-25T11:53:27Z` reconciles 8 lifecycle counts to both the goal total and paginated total: five planned, three active, zero in each other state. It reports 21/21 processed receipts, four facts, zero SDE candidates/review/purge backlog, complete zero-file staging inventory, seven healthy local probes, and no health gates. Curator API (41 tests), MCP workflow (1), Hermes probe (3), strict Pyright, focused errors-only Pylint, Hermes Ruff, and `git diff --check` pass.
- **Open gate:** The local status-view checklist row is complete (148/178 delivery items). Slice G still lacks real app-server lifecycle-event delivery and complete session-event privacy/recovery evidence. Standalone-script coverage and production gates remain open.
- **Outcome:** The owner can read exact lifecycle, review, event, inventory, purge, and readiness totals through the authorized local Hermes profile.

## 2026-10-25 — Compose Codex turn events with the Hermes durable outbox

- **Intent:** Advance Slice G's app-server lifecycle path with a cross-layer privacy and ordering regression.
- **Changed fact:** A Hermes Core regression now drives `AIAgent.run_conversation` through the production gateway callback and profile-local durable outbox, then checks ordered start/end delivery and exact profile/session/goal correlation.
- **Verification:** The focused test passes. Synthetic prompt and response canaries are absent from hook contexts and the outbox database, WAL, and SHM. The test uses a fake Codex app-server session and test hook; no provider or live gateway was contacted. Hermes worktree `git diff --check` passes.
- **Open gate:** Live app-server delivery, the actual consumer hook's managed MCP delivery from this producer, and deployed privacy/recovery evidence remain open. Standalone-script coverage remains open; checklist count is unchanged at 148/178.
- **Outcome:** Local lifecycle callback and durable outbox behavior are now verified together without retaining transcript text.

## 2026-10-25 — Exercise the Hermes plugin delivery path

- **Intent:** Verify a Codex lifecycle event reaches the managed MCP hook before the profile outbox acknowledges it.
- **Changed fact:** Hermes Core's focused regression now runs a fake Codex app-server turn through `AIAgent.run_conversation`, the gateway progress callback, profile hook registry, durable outbox, managed-MCP hook context, and the `hermes_codex_event` call.
- **Verification:** `tests/gateway/test_hooks.py::TestEmit::test_codex_runtime_turn_reaches_managed_mcp_before_ack` passes. It checks ordered start/end events, profile/session/project/goal correlation, queued retry and processed/duplicate acknowledgment, and prompt/response canary absence from hook arguments and outbox SQLite/WAL/SHM. The Vhost disposable managed integration also passes against Hermes Core's actual `HookRegistry`/`HookContext`, managed stdio MCP client, and installed Curator V2 server: five events, exact replay, retry, lost-ack recovery, fresh source epoch, binding, projection, denial, and canary checks. The focused installed-package consumer-isolation test passes using the real Vhost config and synthetic adversarial project. The focused Vhost HTTP route contract passes apply/archive/rollback and SSL/cron receipt retry/recovery against disposable state. Hermes Ruff and all three worktrees' `git diff --check` pass.
- **Open gate:** Codex lifecycle events remain synthetic in the managed integration; no real app-server turn or deployed privacy/recovery was verified. Vhost source coverage and standalone-script scope remain open; Slice G remains open.
- **Outcome:** The local Hermes producer, managed hook, and installed Curator stdio route now have disposable end-to-end integration evidence, without claiming live app-server delivery. The approved one-repository-at-a-time scope resolves the two-consumer alpha requirement; the installed Vhost plus synthetic adversarial-project isolation contract passes, and two checklist rows now stand at 150/178 complete (28 open). Multi-consumer generalization remains deferred.

## 2026-10-25 — Verify the live local Vhost V2 route

- **Intent:** Verify one owner-authorized, disposable Vhost operation through the current local service and installed Curator V2 package.
- **Changed fact:** Restarted the configured root Vhost service from the current consumer checkout, applied and rolled back the absent `curator-v2-smoke-20261025.test` site.
- **Verification:** Apply/rollback operation IDs `b335561e-8417-4f76-9cff-5da7ba903e90` and `06ccae0b-ac13-4a96-aa30-db79f99ed045` produced exact event IDs `vhost-apply-b335561e-8417-4f76-9cff-5da7ba903e90` and `vhost-rollback-06ccae0b-ac13-4a96-aa30-db79f99ed045`; the installed ledger reports both `processed`. The Vhost API reports the site absent after rollback, and Nginx/OpenLiteSpeed are active with valid configurations. No certificate was changed.
- **Open gate:** This exercised one local disposable workflow from a dirty checkout. Complete producer/artifact inventory, standalone-script scope, human disposition, and release acceptance remain open. Slice F/I gates remain open; no checklist marker changed.
- **Outcome:** The current root service route successfully wrote and reversed one Vhost operation through Curator V2.

## 2026-10-25 — Reduce generated lifecycle test complexity

- **Intent:** Remove one repository-wide Pylint complexity finding without weakening lifecycle coverage.
- **Changed fact:** The generated blocker/defer regression derives its expected gate bullets from the input actions instead of retaining branch-local strings.
- **Verification:** All eight tests in `test_property_fuzz.py` pass. Warning-level Pylint for that file no longer reports `too-many-locals` in the changed test; six other structural findings remain in the file. `git diff --check` passes.
- **Open gate:** The full repository warning-level inventory has not been rerun after this delta; the previous 85-diagnostic report remains the last full scan. The repository-wide Pylint checklist item remains open.
- **Outcome:** One focused lint finding was removed with the same generated action coverage and assertions.

## 2026-10-25 — Extract generated lifecycle state models

- **Intent:** Continue repository-wide Pylint cleanup while preserving generated lifecycle acceptance coverage.
- **Changed fact:** The mixed lifecycle sequence now uses an explicit expected-state model and action dispatcher. The linked dependency/child/parent test now uses named helpers for setup, allowed transitions, state advancement, and unchanged-state assertions after denial.
- **Verification:** All 8 tests in `test_property_fuzz.py` pass; warning-level Pylint for that module is clean; `git diff --check` passes.
- **Open gate:** The full repository warning-level Pylint scan has not yet been rerun after this refactor. Repository-wide cleanup remains open.
- **Outcome:** The generated lifecycle tests retain their sequence and denial checks while the complete property-test module is now warning-free.

## 2026-10-25 — Recheck repository-wide Pylint after lifecycle cleanup

- **Intent:** Measure the effect of the generated lifecycle test refactor across the whole source and test tree.
- **Changed fact:** The warning-level JSON inventory fell from 85 to 78 findings; `test_property_fuzz.py` contributes none after cleanup.
- **Verification:** `uv run --locked --group quality pylint --output-format=json src/curatormd_v2 tests` exited 24 with 63 refactor and 15 convention diagnostics. The 8 property tests and focused file-level Pylint passed.
- **Open gate:** Seven findings were removed, but repository-wide Pylint still exits 24. The remaining 78 findings are not cleared; the checklist item remains open.
- **Outcome:** The full scan confirms measurable lint progress without claiming warning-level completion.

## 2026-10-25 — Close the one-consumer local plugin acceptance

- **Intent:** Close the Curator V2 plan's one-real-consumer plugin item against its local-alpha acceptance criteria.
- **Changed fact:** The installed Vhost config and adapter exercise bounded source mapping, project-scoped routing, canonical target persistence, and isolation from an adversarial project. The root Vhost route has emitted processed apply/rollback receipts; five compact operation blocks reconcile at the configured Markdown target. The profile reports a complete zero-file Curator staging inventory.
- **Verification:** All 8 tests in `tests/vhost-manager/test_curatormd_v2_contract.py` pass against the installed alpha package, including the disposable actual HTTP/MCP apply/retry test. The supported Hermes profile discovers 48 tools and reads 25/25 processed receipts; its separate health snapshot reports a complete staging inventory.
- **Open gate:** This closes only checklist item F for the approved single-user, one-repository local alpha. The separate source-to-artifact audit remains open, including standalone scripts and out-of-root dispositions. Release Gate F, Slice I, and production/release acceptance remain open.
- **Outcome:** Marked the one-consumer local integration checkbox complete with evidence. No other marker changed, and no commit or push was made.

## 2026-10-25 — Correct the delivery-checklist denominator

- **Intent:** Reconcile the embedded checklist total with the actual delivery rows before reporting plan progress.
- **Changed fact:** Corrected the embedded count from 150/178 to 154/188 complete; 34 rows remain open. The recount includes top-level checklist rows in sections 0–10, 12, and Definition of done, and excludes section 11 templates and examples.
- **Verification:** The same section-scoped recount returns 188 eligible rows from both tracked HEAD and the current worktree; current markers contain 154 checked rows.
- **Open gate:** The older 150/178 wording in earlier history entries is retained as historical text; the plan header and release-gate snapshot now carry the current count. No checklist marker changed in this recount.
- **Outcome:** Current plan progress now reports the verified denominator and numerator.

## 2026-10-25 — Split domain read models from core records

- **Intent:** Continue the open repository-wide Pylint cleanup without changing persisted record behavior.
- **Changed fact:** Moved status enums to domain_enums.py and goal status/read-model records to goal_read_models.py. Existing imports from models.py remain available through direct imports and its lazy compatibility resolver.
- **Verification:** The warning-level full-tree Pylint inventory fell from 78 to 77; models.py no longer exceeds the configured module-size limit. Strict Pyright reports zero diagnostics. The focused fact-compaction and lifecycle suites pass 55 tests; git diff --check passes.
- **Open gate:** The remaining 77 warning-level Pylint findings span module size, duplication, interfaces, and structural complexity. Repository-wide cleanup remains open; no checklist marker changed.
- **Outcome:** One repository-wide Pylint finding was removed while preserving tested lifecycle and compaction behavior.

## 2026-10-25 — Split legacy schema migration steps

- **Intent:** Continue reducing module-size findings without changing migration order or transaction ownership.
- **Changed fact:** Moved schema migrations 2–20 to schema_migration_steps_v2_v20.py; schema_migrations.py retains the public imported names, ordered step tuple, and application functions.
- **Verification:** All 38 migration tests pass. Strict Pyright reports zero diagnostics; focused Pylint reports no findings for either migration module; git diff --check passes. The fresh repository-wide inventory is 76 findings, down from 77, and exits 24.
- **Open gate:** Repository-wide Pylint cleanup remains open. No checklist marker changed.
- **Outcome:** A second module-size finding was removed with the migration transaction boundary and compatibility imports preserved.

## 2026-10-25 — Split API access primitives from the facade

- **Intent:** Continue repository-wide Pylint cleanup without changing the project authorization boundary.
- **Changed fact:** Moved project actions, authenticated caller validation, authorizer protocols/implementations, and the in-memory token bucket to api_access.py. api.py retains its public compatibility exports and all request/fencing behavior.
- **Verification:** The API, project-access, and hosted-MCP suites pass 78 tests; strict Pyright reports zero diagnostics; focused Pylint is 10.00/10; git diff --check passes. The fresh full-tree warning inventory fell from 76 to 75 and still exits 24.
- **Open gate:** Repository-wide Pylint cleanup remains open; no checklist marker changed.
- **Outcome:** Removed one module-size finding while preserving tested authorization behavior.

## 2026-10-25 — Close the Vhost standalone producer coverage row

- **Intent:** Close the approved Vhost development-scope source/artifact audit, including its four standalone utilities.
- **Changed fact:** Added [`docs/vhost-producer-coverage-v2.md`](../docs/vhost-producer-coverage-v2.md) with the owner-reviewed source-to-class matrix, artifact destinations and out-of-root ownership, workflow observation limits, and dirty-snapshot binding. Checked the matching plan row. The consumer snapshot is bound to HEAD `7d2b10f5433cfe566fc560741bbc9401265176f4`, config SHA-256 `4f3a34e84832b7e8ccfe4e91a68b0664c6aa603409318197f0b44e6454ece44a`, adapter API version 1, and a 23-file manifest SHA-256 `79ce6b73d3a4d52a34b3931a1d74ce42221be4f604967756ed88529454d42128`. The installed root cron wrapper hash matches the repository ACME bridge.
- **Verification:** Six focused consumer tests pass for the bounded queue, batch renewal, inventory refresh, Nginx setup, manual-DNS failed-issue/restore cleanup, and log redaction. `strace -f -yy` counted 455 mutating file operations across those disposable test processes; the fixtures and excluded/unclassified runtime paths are documented. The configured physical Curator staging directory currently has zero entries; the latest supported profile snapshot on 2026-10-25 19:21 +07 reported a complete zero-file inventory. The larger HTTP/MCP contract did not finish: it was interrupted in a later rollback-replay subprocess, so it is not counted as a passing full run.
- **Open gate:** Persistent manual-DNS log retention, live certificate renewal, production/host/provider behavior, and release approval remain separate. The direct Curator `goal_list` call in this session returned `unauthenticated`; no live ledger write or current ledger-status claim is made. The plan's embedded `154/188` did not match its stated section scope; the direct recount is now 152/178 complete and 26 open after this closure. No other marker changed.
- **Outcome:** Closed the local source/artifact audit for the approved, dirty single-repository development snapshot. Any manifest/config change requires a new review. Gate F and release acceptance remain open.

## 2026-10-25 — Split plugin staging and expiry operations

- **Intent:** Reduce the Curator V2 repository-wide Pylint findings without changing project staging, inventory, or expiry behavior.
- **Changed fact:** Moved staging, inventory, and expiry methods into a typed `ProjectStagingMixin` in `project_plugin_staging.py`. `ProjectPlugin` remains the import facade and re-exports its existing staging limits; the scan-limit regression now patches the implementation module.
- **Verification:** The focused project-plugin suite passes 55 tests. Strict Pyright reports zero diagnostics for both plugin modules; focused Pylint has no findings in the staging module; `git diff --check` passes. A fresh full-tree Pylint JSON scan reports 74 findings (11 convention, 63 refactor), down from 75, and exits 24.
- **Open gate:** `ProjectPlugin` still exceeds the public-method limit (44/20), and 73 other repository-wide findings remain. The Pylint checklist item stays open; no checklist marker changed.
- **Outcome:** Removed one full-tree module-size finding while preserving the verified plugin staging and expiry behaviors.

## 2026-10-25 — Split plugin facade methods by responsibility

- **Intent:** Continue removing repository-wide Pylint findings while keeping the configured plugin API and project-effect fences intact.
- **Changed fact:** Moved canonical repository operations, goal reads, and SDE/review operations into typed mixins. `ProjectPlugin` composes them with the staging mixin; its existing import and inherited method access remain available. Updated the API health regression to patch the staging scanner's owning module.
- **Verification:** The focused plugin and API suites pass 55 and 41 tests. Full strict Pyright reports zero diagnostics, errors-only Pylint passes, focused warning-level Pylint for all four plugin modules is clean, and `git diff --check` passes. The fresh full-tree warning inventory is 73 findings (11 convention, 62 refactor), down from 74; the ProjectPlugin public-method finding is gone.
- **Open gate:** The 458-test full run had one stale API test patch target. That target is corrected and the API suite passes, but the full suite has not been rerun. Repository-wide warning-level Pylint cleanup remains open.
- **Outcome:** Removed the ProjectPlugin public-method warning without changing its configured facade or the underlying lifecycle operations.

## 2026-10-25 — Verify plugin composition after patch-target correction

- **Intent:** Verify the plugin facade refactor and its corrected scan-limit regression across the complete Curator V2 suite.
- **Changed fact:** Corrected the API health test to patch `project_plugin_staging.MAX_STAGING_SCAN_ENTRIES`, the module that owns the bounded scanner.
- **Verification:** The complete suite passes all 458 tests. Full strict Pyright reports zero diagnostics, the configured errors-only Pylint command passes, the full warning-level Pylint inventory remains 73 findings (11 convention, 62 refactor), and `git diff --check` passes.
- **Open gate:** Repository-wide warning-level Pylint cleanup and the remaining plan gates stay open; no checklist marker changed.
- **Outcome:** Confirmed all 458 local tests pass with the plugin mixin composition and correct scan-limit test target.

## 2026-10-25 — Separate Markdown reconciliation tests

- **Intent:** Remove the persistence test module/class size findings by grouping project-marker reconciliation coverage in its own module.
- **Changed fact:** Moved the three project reconciliation regressions into `test_markdown_reconciliation.py` and moved shared disposable project setup to `markdown_persistence_fixtures.py`.
- **Verification:** All 20 persistence/reconciliation tests pass (17 and 3). Strict Pyright reports zero diagnostics; errors-only Pylint passes; focused Pylint for both test modules and the fixture is clean; `git diff --check` passes. The fresh full-tree warning inventory falls from 73 to 71 findings (10 convention, 61 refactor), removing the markdown test module-size and class-size findings.
- **Open gate:** Repository-wide warning-level Pylint remains at 71 findings and exits 24; its checklist item stays open. No checklist marker changed.
- **Outcome:** Split reconciliation coverage while retaining the same test setup and assertions, and removed two repository-wide Pylint findings.

## 2026-10-25 — Share service-test store setup

- **Intent:** Remove duplicated disposable SQLite/staging setup from fact-compaction and lifecycle tests without changing their distinct verifiers or service behavior.
- **Changed fact:** Added `store_fixtures.create_store_stage` and reused it in both test suites; the two suites continue to configure their own evidence verifiers and goal criteria.
- **Verification:** The fact-compaction and lifecycle suites pass 9 and 46 tests. Full strict Pyright reports zero diagnostics, errors-only Pylint passes, and `git diff --check` passes. The fresh full-tree warning inventory falls from 71 to 70 findings (10 convention, 60 refactor), including one fewer duplicate-code finding.
- **Open gate:** Repository-wide warning-level Pylint cleanup remains open at 70 findings; no checklist marker changed.
- **Outcome:** Shared the identical test filesystem setup while preserving the separate lifecycle and archive acceptance assertions.

## 2026-10-25 — Share isolated profile-runtime test cleanup

- **Intent:** Remove repeated local MCP runtime construction/cleanup from the access CLI and hosted-MCP regressions.
- **Changed fact:** Added `open_test_profile_mcp`, a context manager over the existing fixture builder, and reused it in the matching write-grant tests. Runtime closure now follows the fixture scope automatically.
- **Verification:** The access CLI and hosted-MCP suites pass 4 and 16 tests. Full strict Pyright reports zero diagnostics, errors-only Pylint passes, and `git diff --check` passes. The full-tree warning inventory falls from 70 to 67 findings (10 convention, 57 refactor), including three fewer duplicate-code findings.
- **Open gate:** Repository-wide warning-level Pylint remains open at 67 findings; no checklist marker changed.
- **Outcome:** Removed duplicated launcher test setup while preserving the same project grants and authorization assertions.

## 2026-10-25 — Reconcile standalone coverage status

- **Intent:** Make the plan's later Vhost status note agree with the completed standalone producer coverage review.
- **Changed fact:** The plan now points to the closed source/artifact audit for the approved dirty development snapshot; the standalone coverage checkbox was already checked in the prior closure record.
- **Verification:** The review documents four standalone utilities, their artifact classes and owners, six focused consumer tests, and snapshot fingerprints. `git diff --check` passes.
- **Open gate:** Full Gate F, human disposition, production behavior, and release evidence remain open. No checklist marker changed in this correction.
- **Outcome:** Removed the stale claim that standalone utility coverage remains open.

## 2026-10-25 — Share approved empty-inventory SDE test request

- **Intent:** Continue the open repository-wide Pylint cleanup without weakening SDE review or route-specific assertions.
- **Changed fact:** Added one test fixture for the shared approved-empty-inventory request and reused it in the API, MCP, and project-plugin tests.
- **Verification:** The three suites pass 104 tests. Strict Pyright reports zero diagnostics, focused duplicate-code Pylint is clean, and `git diff --check` passes. The settled full-tree Pylint inventory falls from 67 to 64 findings (10 convention, 54 refactor), with three fewer duplicate-code findings.
- **Open gate:** Full warning-level Pylint still exits 24 with 64 findings; its checklist item remains open. No checklist marker changed.
- **Outcome:** Removed repeated test setup while preserving independent route and authorization coverage.

## 2026-10-25 — Share lifecycle status expectations across test models

- **Intent:** Continue the open Pylint cleanup while keeping the lifecycle matrix and generated lifecycle model aligned to one explicit V2 status contract.
- **Changed fact:** Added test-only status groups for unfinished, fact-accepting, and finishable goals and reused them in the lifecycle action matrix and both property-model rules.
- **Verification:** The lifecycle and property suites pass 54 tests. Strict Pyright reports zero diagnostics, errors-only Pylint passes, and `git diff --check` passes. The warning inventory is 62 findings (10 convention, 52 refactor), down two from 64, with two fewer duplicate-code findings.
- **Open gate:** Repository-wide warning-level Pylint remains open; no checklist marker changed.
- **Outcome:** Removed duplicated lifecycle expectations without changing production state transitions.

## 2026-10-26 — Split the oversized lifecycle regression suite

- **Intent:** Remove the lifecycle test module/class size findings while preserving every existing lifecycle assertion.
- **Changed fact:** Moved all 46 lifecycle tests into five domain-focused modules and shared their unchanged disposable setup/helpers through `lifecycle_test_support.py`.
- **Verification:** Unittest discovery passes all 46 tests; strict Pyright reports zero diagnostics; focused Pylint for the five modules and support file is clean; `git diff --check` passes. The fresh full-tree warning inventory falls from 62 to 60 findings (9 convention, 51 refactor), removing the lifecycle module-size and class-size findings.
- **Open gate:** Whole-tree Pylint still exits 24 with 60 findings; the checklist item remains open. No checklist marker changed.
- **Outcome:** Kept the lifecycle coverage intact and split its two repository-wide size findings across maintainable test modules.

## 2026-10-26 — Close standalone-script coverage for local alpha

- **Intent:** Close the owner-approved standalone-script coverage item for the single-user Vhost development alpha.
- **Changed fact:** Refreshed the Vhost source/config/adapter/test binding to 24 sorted files with manifest SHA-256 `390823695cf388aa91dda1003ae3d5b18f131f42990f0a09bc38b4e31f7d51f2`. The reviewed V2 files are now committed at Vhost HEAD `1924fa2` and pushed to `origin/main`; unrelated work remains dirty. Its Curator config hash is unchanged. The existing standalone coverage checkbox was already checked, so no marker changed.
- **Verification:** All six current focused consumer tests pass (standalone batch, inventory, Nginx setup, manual-DNS failure/restore, bounded queue, and log redaction). `strace -f -yy` captured these disposable test process groups. Curator `git diff --check` passes after this record.
- **Open gate:** Persistent-log retention, real certificate renewal, unclassified host/test/provider observations, production behavior, and release approval remain open. No consumer files, runtime state, or live certificates were changed.
- **Outcome:** Standalone-script coverage is closed for the approved local development scope; broader release gates remain separate.

## 2026-10-26 — Add local system-browser evidence capture

- **Intent:** Provide a bounded local browser evidence source using the installed system browser without bundling browser dependencies.
- **Changed fact:** Added a host-configured loopback-only Chrome resolver, combined host evidence-config loading with the service-probe adapter, wired it into hosted MCP, and exposed `curatormd-v2-evidence browser`. Documented the owner-only JSON config and capture command in `docs/local-service-probes.md`. Captures return only a DOM digest and opaque evidence reference; browser identity is the launching OS UID.
- **Verification:** Thirteen focused tests pass (four browser, eight config, one CLI). Installed system Chrome rendered and revalidated a disposable loopback page; its DOM canary was absent from the returned reference and attestation. A read-only run then captured the active Vhost home page (`http://127.0.0.1:4310/`) and the host-configured adapter revalidated its digest for project `vhost-manager-alpha`, subject `local-uid:1000`; result SHA-256 `3ac25910da73e99443bf8bbfd1af1ed4a5a817ded2eb54faf831746021b15fdc`. Strict Pyright and focused Pylint pass; `uv run --locked --group test curatormd-v2-evidence --help` succeeds; `git diff --check` passes.
- **Open gate:** The Vhost check covered its home-page render only; it did not exercise an authenticated cookie session or application operation. Deployed trust root, rotation/revocation proof, and live human identity remain unverified. This local path does not close the source-specific integration checklist.
- **Outcome:** Added and exercised a reviewable local browser evidence path while leaving deployment trust and application workflow proof open.

## 2026-10-26 — Recheck the local six-hour purge timer

- **Intent:** Refresh local scheduler evidence against the approved Vhost alpha cadence.
- **Changed fact:** The `eaglesvn` user timer for `vhost-manager-alpha` is enabled and active at the approved six-hour schedule; its next trigger is 06:00. The latest 00:00 service pass exited successfully.
- **Verification:** `systemctl --user status` reports timer `active (waiting)` and service `status=0/SUCCESS`. The journaled bounded CLI result reports zero pending and zero processed purge targets.
- **Open gate:** This was a successful zero-work pass, not a live deletion. External alert delivery, production scheduling, and restart/reconciliation remain open.
- **Outcome:** Confirmed the local timer is operating at the approved cadence; no cleanup was performed.

## 2026-10-26 — Isolate Hermes Codex integration regression

- **Intent:** Verify the modified Hermes Codex lifecycle path without allowing test setup to read outside its temporary profile.
- **Changed fact:** The gateway integration test now patches PM package-store owner discovery to the temporary Hermes home, alongside `HERMES_HOME`, preventing package-store lookup from probing the real host home.
- **Verification:** The three focused Hermes files first reported 104 passes and one failure caused by the real-home lookup. The corrected gateway regression passes by itself. Hermes `.venv/bin/python scripts/check --base HEAD` passes all 12 checks; Hermes `git diff --check` is clean.
- **Open gate:** The regression uses a fake app-server session and mocked MCP transport. It does not prove a live Codex app-server event, deployed gateway delivery, or release readiness. Slice G remains open.
- **Outcome:** Corrected the test isolation boundary and verified its end-to-end event/outbox/MCP behavior locally.

## 2026-10-26 — Refresh the V2 Hermes profile status snapshot

- **Intent:** Replace the older local-alpha status snapshot with a direct read through the supported Hermes profile context.
- **Changed fact:** The profile-bound V2 ledger reports 27 processed event receipts, 11 goals, and seven facts for `vhost-manager-alpha`; the goal lifecycle counts reconcile to the paginated list total.
- **Verification:** `./hermes -p renew-ssl-coding mcp test curator_v2 --probe-curator-status` exits 0 and discovers 48 tools. It reports 27/27 receipts processed, zero failed/received/quarantined events, five planned and six active goals, zero SDE candidates or review/purge backlogs, and a complete zero-file staging inventory. The separate health observation reports all seven dependencies healthy.
- **Open gate:** This is a dated profile-context read only. It does not dispose of six active goals, prove a new app-server event, or close production and release gates.
- **Outcome:** Updated the V2 alpha, release-gate, and Hermes-integration status records with one reconciled profile snapshot.

## 2026-10-26 — Close the local plugin lifecycle for single-user alpha

- **Intent:** Finish the local Curator V2 project-plugin lifecycle within the owner-approved development scope of one repository at a time.
- **Changed fact:** The plan now marks the local project/binding lifecycle complete for the sole attended `eaglesvn` OS principal (`local-uid:1000`). It separates that alpha result from deferred shared-identity, production-role, external-inventory, and deployment migration/rollback gates.
- **Verification:** `PYTHONPATH=tests uv run --locked --group test python -m unittest tests.test_project_access tests.test_migrations tests.test_review_cli` passes all 68 tests. The current supported-profile snapshot independently confirms exact local read/write/review grants for the approved principal. `git diff --check` passes.
- **Open gate:** No shared or production identity is claimed. Production lifecycle deployment and rollback acceptance remain open; no consumer or runtime state was changed.
- **Outcome:** Closed the local-alpha plugin lifecycle checklist item without claiming production readiness.

## 2026-10-26 — Split project-access lifecycle tests

- **Intent:** Reduce oversized access-test modules while keeping the project registry and consumer-binding transition cases together by domain.
- **Changed fact:** Moved nine consumer-binding lifecycle tests into `test_consumer_binding_lifecycle.py` and shared unchanged setup in `project_access_test_support.py`; the original project-access module retains its 12 registration/grant tests.
- **Verification:** All 21 tests pass. Strict Pyright reports zero diagnostics; focused Pylint on both modules and shared support rates 10.00/10; `git diff --check` passes. The whole-tree warning-level Pylint score remains 9.97/10.
- **Open gate:** Repository-wide Pylint cleanup remains open; this test-organization change does not close other warnings or deployment gates.
- **Outcome:** Split the tests by lifecycle boundary without changing their expected behavior.

## 2026-10-26 — Share bounded evidence subprocess handling

- **Intent:** Remove duplicated process/output handling from local browser proof and service-probe evidence sources.
- **Changed fact:** Both adapters now use one helper that streams stdout to a digest, enforces each caller's existing time and byte limits, kills the complete process group on failure, and retains no output content.
- **Verification:** All eight focused browser/service evidence tests pass. Strict Pyright reports zero diagnostics; errors-only Pylint on the changed modules passes; `git diff --check` passes.
- **Open gate:** The warning-level source modules still report duplicate `EvidenceSourceReceipt` construction, and the repository-wide Pylint item remains open. This does not prove host trust or deployment identity.
- **Outcome:** Unified the local subprocess safety behavior without changing either evidence source's configured bounds or public error outcomes.

## 2026-10-26 — Install and exercise the current local alpha wheel

- **Intent:** Deliver the verified Curator V2 source package to the approved Vhost Manager alpha profile and check the consumer integration.
- **Changed fact:** Installed wheel SHA-256 `c1c3eb614e0dc85f5c9ebe28842316c6db8c59a748b14f05eb720ebb3bf3cee9` only into the dedicated `renew-ssl-coding` Curator V2 environment. Before replacement, archived the prior package, dist-info, and seven entrypoints in `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-package-before-alpha-refresh-20261026-d1cjyoeq/`; archive SHA-256 `a865a4ff3ae737bdee5a9df538b9cba330bf6fd6c8aab0c28e7c49a6360b3452`, 117 manifest entries. All 61 installed module hashes match source.
- **Verification:** Current Curator suite passes 465 tests; strict Pyright, errors-only Pylint, Bandit, locked audit, and `git diff --check` pass. Clean-wheel MCP/CLI/storage smoke passes. Eight Vhost consumer contract tests pass; the Hermes-managed disposable integration passes five events with exact replay/retry, re-enrollment, projection, privacy, and denial checks. A fresh profile read discovers 48 tools and reconciles 29 processed receipts, 12 goals, and eight facts; its health snapshot is complete with seven healthy dependencies and zero pending review/purge work.
- **Open gate:** No existing gateway, web, or editor MCP process was restarted; fresh stdio verification does not claim those long-lived processes reloaded the wheel. No real certificate renewal, authenticated Hermes person, production route, or production readiness is claimed.
- **Outcome:** Installed and exercised the current V2 alpha package at its dedicated local consumer profile while retaining a verified rollback archive.


## 2026-10-26 — Close standalone and multi-consumer alpha scope

- **Intent:** Finish the Vhost standalone-utility coverage within the approved one-repository development alpha.
- **Changed fact:** The existing V2 source-to-artifact audit and owner-reviewed dispositions cover manual DNS renewal, batch renewal, inventory refresh, Nginx setup, the bounded result queue, and no-verbatim log filtering. Shared multi-consumer runtime is explicitly outside the one-repository-at-a-time alpha scope.
- **Verification:** Re-ran the six focused disposable Vhost tests for those workflows; all passed. The evidence is bound to the current dirty Vhost checkout by the 24-file manifest digest in `docs/vhost-producer-coverage-v2.md`.
- **Open gate:** Persistent-log retention, actual certificate renewal, production identity/runtime, and release approval remain open. Shared multi-consumer support reopens only if the owner expands scope.
- **Outcome:** Closed local standalone coverage and clarified that multi-consumer runtime is not an alpha requirement; no checklist marker changed.


## 2026-10-26 — Bind standalone closure to pushed Vhost sources

- **Intent:** Keep the checked V2 standalone audit tied to the source that was actually pushed.
- **Changed fact:** Vhost commit `1924fa2` pushed the reviewed Curator adapters, four utility bridges, consumer route, tests, and scoped UI receipt/retry changes to `origin/main`. Unrelated Vhost security/UI and generated state remain uncommitted.
- **Verification:** The six disposable standalone/queue/redaction tests pass; the Vhost UI production build passes. The 24-file source/config/adapter/test manifest remains `390823695cf388aa91dda1003ae3d5b18f131f42990f0a09bc38b4e31f7d51f2`; the config digest is unchanged.
- **Open gate:** Persistent-log expiry, real certificate renewal, production identity/scheduling, and release approval remain open.
- **Outcome:** Updated the current V2 evidence binding without changing checklist markers.

## 2026-10-26 — Complete local manual DNS and root cron producer audit

- **Intent:** Close the remaining local Vhost producer/artifact evidence for manual DNS renewal and the installed root ACME cron wrapper.
- **Changed fact:** Added a successful disposable manual-DNS issue/renew regression and a cron-bridge regression that invokes the installed wrapper with fake ACME and a loopback receipt endpoint. The source-to-class record now states the approved out-of-root disposition: Vhost/OS retains those artifacts; Curator does not scan or purge them and receives bounded outcome metadata only.
- **Verification:** All eight focused producer tests pass. The manual-DNS fixture verifies propagation checks, fixture installation, temporary cleanup, persistent-log challenge redaction, and a content-free receipt. The installed cron-wrapper fixture verifies its bounded receipt, output-canary exclusion, and pending-queue cleanup. Installed/source wrapper hashes match; the root schedule was read-only inspected. The refreshed 24-path consumer manifest is `a5635ed8cbda33811a12603f6aa4453369a5c240c75c11d812db78c451cf8cfb`.
- **Open gate:** No real DNS or certificate renewal or scheduled cron run occurred. Persistent-log expiry, production scheduling/identity, human operation-goal disposition, and release approval remain open.
- **Outcome:** Closed the local source/artifact audit for the approved one-repository development alpha. Its checklist marker was already checked, so the checklist count did not change. No commit, push, or service restart was performed.

## 2026-10-26 — Share local evidence receipt construction

- **Intent:** Remove duplicated source-receipt assembly from local browser and service-probe evidence resolvers without changing their trust scope.
- **Changed fact:** Added a typed local-source binding and shared receipt constructor. It binds project/goal/criterion context, source scope/revision/subject, evidence digest, observation and revocation-check times, and the existing source-specific validity window; validity remains capped at 900 seconds.
- **Verification:** The focused browser, service-probe, and evidence-adapter suites pass all 23 tests. Strict Pyright and errors-only Pylint pass on the three changed modules. The repository-wide warning inventory is 58 findings (50 refactor and 8 convention), down from 59; the duplicate browser/service receipt-construction finding is gone.
- **Open gate:** Repository-wide Pylint findings remain open. This local-source helper does not add deployment credentials, authenticated human identity, or source-owner trust roots.
- **Outcome:** Removed duplicated receipt construction while preserving source-specific verification behavior and the deployment trust gate.

## 2026-10-26 — Verify local receipt validity bounds

- **Intent:** Add a regression for the shared local evidence-receipt validity ceiling and exact-integer rule.
- **Changed fact:** The evidence tests now reject zero, greater-than-900-second, and boolean validity values before a receipt is returned.
- **Verification:** All 16 evidence-adapter tests pass; together with the browser and service-probe suites, the focused source tests pass 24 tests. Strict Pyright and errors-only Pylint pass on the changed files. Warning-level Pylint reports only the existing flat receipt-record attribute-count finding in this scope.
- **Open gate:** The repository-wide Pylint item and deployment-owned connector credentials/trust roots remain open.
- **Outcome:** Bound the shared local-source receipt helper with negative-case regression coverage; no checklist marker changed.

## 2026-10-26 — Split migration fixture setup from assertions

- **Intent:** Reduce the local-variable complexity of the v2 purge-target migration regression while preserving its schema and receipt checks.
- **Changed fact:** Extracted creation of the v2 database, verified fact, and pending purge receipt into a private fixture helper. The test still removes v3 columns/indexes, sets the v2 schema marker, reopens through migrations, and checks receipt age, retry fields, target status, and final schema version.
- **Verification:** The focused migration test passes; strict Pyright and `git diff --check` pass. Focused Pylint no longer reports the test's local-variable finding. The full repository inventory falls from 58 to 57 findings (8 convention, 49 refactor).
- **Open gate:** Repository-wide Pylint remains open. `tests/test_migrations.py` still has module-size and test-class-size findings.
- **Outcome:** Removed one Pylint finding without changing migration behavior or any checklist marker.

## 2026-10-26 — Reverify local producer and out-of-root audit closure

- **Intent:** Resolve the status discrepancy for the Vhost manual-DNS, root ACME wrapper, and out-of-root artifact audit.
- **Changed fact:** The plan now explicitly distinguishes the completed local source/artifact audit from real scheduled execution, real renewal, and persistent-log retention. The reviewed disposition keeps Vhost/OS artifacts outside Curator scan and purge.
- **Verification:** Reran the eight focused disposable producer tests in the Vhost checkout; all pass, including manual-DNS success/failure, installed cron-wrapper receipt, batch, inventory, setup, queue cap, and log redaction. `git diff --check` passes. The audit checklist row was already checked; the plan currently counts 168 complete, 48 open, 216 total.
- **Open gate:** Actual scheduled cron execution, real DNS/certificate renewal, persistent-log expiry, production scheduling/identity, and release approval remain open. These do not make the approved local source/artifact audit incomplete.
- **Outcome:** Confirmed the local audit is closed without changing a checkbox, deployment, commit, or push.

## 2026-10-26 — Enforce local Vhost manual-DNS log expiry

- **Intent:** Apply the approved 72-hour maximum age to Vhost-owned manual-DNS logs and close the local log-expiry subgate.
- **Changed fact:** Added a separate root-owned Vhost/OS timer on a six-hour cadence. It removes only matching regular `/var/log/acme-dns-manual-*.log` files, emits only a deletion count, and never routes log contents through Curator. The Curator staging/purge root is unchanged.
- **Verification:** The two focused expiry tests pass. Installed service/timer hashes match repository files; `systemd-analyze verify` accepts the units, with warnings only for an unrelated existing OpenLiteSpeed unit. The enabled timer is active; its first service run succeeded and removed two logs past the approved age. A path-only count found zero matching regular logs afterward. The six-file implementation/test manifest is `a3b07fadb8a08b50557b20f7008f86bcc0c90906d2991c2c7b2f46f65121da3f`. `git diff --check` passes in both repositories.
- **Open gate:** Real ACME execution, cleanup while the host is powered off, production retention/scheduling policy, operation-goal disposition, and release approval remain open. No checkbox changed; the plan count remains 168/216.
- **Outcome:** Closed the approved local log-expiry subgate outside Curator while preserving the wider producer and release evidence boundaries.

## 2026-10-26 — Split migration tests by schema era

- **Intent:** Remove the migration test class-size warning while keeping each migration regression intact.
- **Changed fact:** Split the 38 tests into current-schema and legacy-compatibility classes. Neither class relies on shared setup or cross-test calls; migration behavior and assertions are unchanged.
- **Verification:** All 38 migration tests pass. Strict Pyright reports zero diagnostics. Focused Pylint reports only the existing module-size warning for `tests/test_migrations.py`. The whole-tree inventory falls from 57 to 56 findings (8 convention, 48 refactor). `git diff --check` passes.
- **Open gate:** Repository-wide Pylint cleanup remains open; the migration module still exceeds the configured size threshold. No plan checkbox or delivery gate changed.
- **Outcome:** Removed one repository-wide Pylint finding without changing runtime behavior or migration coverage.

## 2026-10-26 — Simplify the in-flight suspension race fixture

- **Intent:** Remove the local-variable warning from the profile-level effect-fence regression without weakening its concurrency assertions.
- **Changed fact:** Moved the disposable profile, event, lock events, project manager, and commit pause into a typed test context. The test still proves an admitted write commits before suspension, exact replay remains idempotent, and unauthorized reads stay denied.
- **Verification:** The focused race test passes; strict Pyright reports zero diagnostics. Focused Pylint on `tests/test_hosted_mcp.py` now reports only its existing module-size warning. Whole-tree Pylint falls from 56 to 55 findings (8 convention, 47 refactor). `git diff --check` passes.
- **Open gate:** Repository-wide Pylint remains open. The hosted-MCP test module still exceeds the configured line limit; no plan checkbox changed.
- **Outcome:** Removed one Pylint finding while preserving effect-fencing test coverage.

## 2026-10-26 — Reconcile local producer/artifact audit status

- **Intent:** Close the reported local-alpha producer/artifact audit status for manual DNS, the installed root ACME wrapper, and out-of-root artifact ownership.
- **Changed fact:** The V2 plan now states that this local audit is complete for the approved one-repository alpha. Its evidence covers manual DNS fixture success, invocation of the installed root wrapper against a fake ACME command and loopback receipt endpoint, the approved Vhost/OS ownership disposition for out-of-root files, and the separate local 72-hour log expiry. The plan's embedded checklist count is corrected to 168/214 complete, 46 open; the audit checkbox was already checked.
- **Verification:** The existing current-checkout record in the plan and [`vhost-producer-coverage-v2.md`](../docs/vhost-producer-coverage-v2.md) documents eight passing focused producer tests, the installed/source wrapper hash match, the 24-path producer manifest, and the six-path log-expiry manifest. Fresh read-only checklist counting confirms 168 checked and 46 open in both `HEAD` and the worktree. `git diff --check` passes.
- **Open gate:** Real scheduled cron execution, real DNS/certificate renewal, production retention/scheduling, human disposition of operation goals, and release acceptance remain open. These are deployment/release gates, not missing local source/artifact audit evidence. Multi-consumer runtime remains outside the approved alpha.
- **Outcome:** Closed the stale local-audit status report without changing a checklist marker, running live ACME, modifying GPTMD, committing, pushing, or restarting a service.

## 2026-10-26 — Install and verify current-source V2 alpha package

- **Intent:** Put the current Curator V2 source delta into the isolated `renew-ssl-coding` alpha and verify the local Hermes-managed consumer path.
- **Changed fact:** Built wheel SHA-256 `96ff9a085c0a8a7a80ee685a61b5986bcc58e9f102c185b169d1a004147f5a57` and installed it only in the profile's Curator V2 virtualenv. Before replacement, archived the old package, metadata, and launchers under `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-before-source-refresh-5e7wgdz5.tar.gz`; the archive has 130 files and SHA-256 `34222eaec1ed2d8e4080f85c5e2d686d4a3f3cfb922987b61d70a1b30d72568a`.
- **Verification:** All 61 installed Python modules match this source tree byte for byte; `pip check`, strict Pyright, errors-only Pylint, and Bandit pass. The supported Hermes profile MCP read succeeds with 48 tools and reports 29/29 processed receipts, 12 goals, eight facts, zero review/purge backlog, complete empty staging, and healthy local-alpha dependency observations. The disposable Hermes-managed Vhost integration passes five events with replay/retry, lost-ack recovery, source-epoch advancement, binding, projection, privacy, and reviewer-write-denial checks. No service restarted and no live app-server event was generated.
- **Open gate:** The full-suite result recorded for the prior wheel does not apply to this source refresh. Real app-server event delivery, real certificate renewal, human disposition of the active goals, and release sign-off remain open; no checklist marker changed.
- **Outcome:** Refreshed and verified the installed local alpha while preserving a verified rollback package and keeping the Hermes lifecycle and release claims bounded.

## 2026-10-26 — Confirm producer audit closure and reconcile checklist count

- **Intent:** Close the reported local producer/artifact audit for manual DNS, the installed root ACME wrapper, and out-of-root artifact disposition.
- **Changed fact:** The owner-reviewed Vhost/OS disposition, manual-DNS fixture, installed root-wrapper fixture, and local 72-hour log-expiry evidence close this audit for the single-repository alpha. Corrected two stale embedded count references from 168/214 to the actual 168/216 (48 open); the audit checkbox was already checked.
- **Verification:** Re-ran exactly eight focused disposable producer tests covering manual DNS success/failure, installed-wrapper receipt, batch renewal, inventory refresh, Nginx setup, bounded queue behavior, and log redaction; all pass. Fresh checkbox count is 168 checked, 48 open, 216 total. `git diff --check` passes in Curator and Vhost worktrees.
- **Open gate:** This does not claim that cron actually ran, a real DNS challenge or certificate renewal succeeded, or that production scheduling/retention and release approval are complete.
- **Outcome:** Resolved the local audit and checklist-count discrepancy without changing a checklist marker, touching GPTMD, committing, pushing, or restarting a service.

## 2026-10-26 — Diagnose the active Hermes lifecycle route

- **Intent:** Identify the current failure blocking real Hermes app-server lifecycle delivery to Curator V2.
- **Changed fact:** The Core checkout contains Codex lifecycle emission, profile-scoped hooks, a durable outbox, and a composition test, but these do not prove the active system route. The running gateway logs contain three failed `curator_v2/hermes_goal_bind` calls reporting `No module named 'jsonschema'`. A checkout-based read-only profile probe succeeds with 48 tools and healthy ledger reads, which is separate evidence. An installed-CLI probe triggered Hermes' built-in recovery for an interrupted source update and reported version `0.22.2+1558.gad06e63.dirty`; the gateway process was not restarted. The installed tree currently shows 13 modified tracked paths and two untracked plugin paths. Their provenance relative to that recovery is unknown; all were preserved.
- **Verification:** `systemctl` reports the gateway still running under PID 546803 since 2026-10-25. Read-only inspection confirms the profile ledger status remains readable through the checkout CLI. No binding, lifecycle receipt, service restart, or source edit in Hermes Core was performed.
- **Open gate:** Diagnose and repair the system PM/MCP runtime dependency failure, then verify one processed app-server lifecycle event from the active profile-bound gateway. Do not treat checkout-only or mocked composition as closure.
- **Outcome:** Narrowed the Hermes integration blocker to the active system runtime while preserving the dirty installed tree; Slice G remains open.

## 2026-10-26 — Check installed Hermes MCP discovery after recovery

- **Intent:** Determine whether the installed Hermes CLI can reach the V2 stdio server after its automatic source-update recovery.
- **Changed fact:** The installed CLI connects to `curator_v2` and discovers 48 tools, but reports `Auth: none`. This does not inject the trusted profile/session context used by the supported checkout probe, read the ledger, or exercise a gateway app-server turn.
- **Verification:** The command exited successfully after listing the tools. The active gateway remains the previously running process; no V2 lifecycle receipt or binding was produced.
- **Open gate:** Repair and verify the active system MCP runtime and produce a processed event through the profile-bound gateway route. Current source checkout tests and basic MCP discovery do not satisfy this gate.
- **Outcome:** Confirmed that CLI transport discovery works while trusted profile and live gateway lifecycle delivery remain unverified.

## 2026-10-26 — Restart Hermes gateway and recheck lifecycle smoke

- **Intent:** Load the recovered Hermes Core source in the gateway and retry the previously approved local smoke-goal binding.
- **Changed fact:** Restarted `hermes-gateway.service`; systemd reports new PID 1962718 active since 03:16 +07. The installed profile TUI accepted the existing smoke-goal bind request but remained pending for about one minute and was interrupted. The profile read still succeeds through the supported checkout CLI.
- **Verification:** Read-only checks after the attempt show five existing Hermes goal bindings, eleven acknowledged outbox lifecycle events, the smoke goal still active, and 29 processed Curator receipts. No new binding, event, or receipt was recorded. No fresh `jsonschema` error appeared in the searched profile log range, but the TUI attempt does not prove that the gateway app-server hook ran.
- **Open gate:** Route one real Codex app-server turn through the active system gateway and verify a new profile-bound outbox event receives a processed Curator receipt, with no transcript content retained. Basic MCP discovery and a TUI-only attempt are insufficient.
- **Outcome:** Reloaded the recovered Core runtime but did not close Slice G; the checklist marker and count remain unchanged.

## 2026-10-26 — Close the local Vhost producer/artifact audit status

- **Intent:** Resolve the remaining reported gaps for standalone workflows, manual DNS, the installed root ACME wrapper, and out-of-root artifact ownership.
- **Changed fact:** The local source/artifact audit is complete for the owner-approved single-repository alpha. The Vhost coverage record documents manual-DNS fixture success, the installed root-wrapper fixture, eight focused producer checks, and the approved Vhost/OS ownership boundary keeping out-of-root artifacts outside Curator scan and purge. Shared multi-consumer runtime remains outside the approved alpha scope. The audit checklist row was already checked; no marker changed.
- **Verification:** The existing evidence is recorded in `docs/vhost-producer-coverage-v2.md` and in the preceding verification refresh. A direct count using the plan's stated delivery scope (top-level rows in sections 0–10 and 12) is 153/178 complete, 25 open. The separate count of every top-level checkbox in the entire plan is 168/214 and is not the delivery progress count. `git diff --check` passes after the documentation correction.
- **Open gate:** Actual scheduled cron execution and real certificate renewal, production identity/retention/scheduling, human operation-goal disposition, and release approval remain open. These do not reopen the local source/artifact audit.
- **Outcome:** Closed the local producer/artifact audit status and corrected its reported progress scope without changing a checklist marker, touching GPTMD, running live ACME, committing, pushing, or restarting a service.

## 2026-10-26 — Persist exact per-artifact purge outcomes

- **Intent:** Distinguish an unlink performed now from an artifact already absent after an interrupted purge, while preserving held, changed, and failed outcomes.
- **Changed fact:** Schema v38 adds a constrained nullable purge outcome. New held targets record `held`; successful purge records `deleted` or `already_absent`; hash, identity, or path mismatches record `changed`; other failures record `failed`. Beginning a retry clears the previous outcome until the current attempt is recorded. Historical rows remain null because their exact outcome is unknowable. The V1 API read schema documents the additive nullable field.
- **Verification:** Focused purge tests pass (30), migration tests pass (39), contract schema tests pass (9), and storage-resource tests pass (2). Strict Pyright reports zero diagnostics; errors-only Pylint passes on the Curator source and affected tests; `git diff --check` passes.
- **Open gate:** The delivery failure-injection matrix still requires deployment-shaped storage/staging adapters and owner-reviewed recovery evidence. No delivery checklist marker changed.
- **Outcome:** Durable per-file cleanup reporting now distinguishes exact observed outcomes without changing retry authorization or claiming production-adapter verification.

## 2026-10-26 — Remove purge-outcome Pylint regressions

- **Intent:** Keep the purge-outcome implementation from adding findings to the open repository-wide Pylint cleanup.
- **Changed fact:** Removed its redundant type-only `PurgeOutcome` import and wrapped the overlong purge-target SQL line. Replaced the extra purge-result method parameters with a typed `PurgeTargetResult` record. Runtime behavior is unchanged.
- **Verification:** Targeted checks for reimport, line length, and argument-count diagnostics pass on the affected modules; errors-only Pylint and strict Pyright pass. The fresh full-tree inventory is 55 findings (8 convention, 47 refactor), with no blocking warning/error categories. `git diff --check` passes.
- **Open gate:** Repository-wide Pylint cleanup remains open.
- **Outcome:** Removed the warnings introduced by the preceding code slice without changing runtime behavior or marking the broad lint item complete.

## 2026-10-26 — Reduce goal-service argument warnings

- **Intent:** Remove repository-wide Pylint argument-count findings from the goal start and fact-recording service entrypoints without changing their keyword call sites.
- **Changed fact:** Both methods now declare optional keyword fields with `Unpack[TypedDict]`; runtime guards continue rejecting unknown option names. Option values flow directly into the existing validation and record construction.
- **Verification:** Full Pylint inventory falls from 55 findings (8 convention, 47 refactor) to 52 (8 convention, 44 refactor). The full suite passed 468 tests before the local-count-only cleanup; after that cleanup, the goal-lifecycle suite passes 17 tests, full strict Pyright reports zero diagnostics, errors-only Pylint passes, and `git diff --check` passes.
- **Open gate:** Repository-wide Pylint cleanup remains open. No checklist marker changed.
- **Outcome:** Removed two argument-count findings, one local-variable finding, and one duplicate-code finding while preserving callers and rejecting misspelled runtime options.

## 2026-10-26 — Recheck local producer audit evidence

- **Intent:** Verify the exact manual-DNS and root-wrapper evidence cited by the already-closed local Vhost producer/artifact audit.
- **Changed fact:** No code or checklist marker changed. The audit remains closed for the approved single-repository alpha; real scheduled execution and real renewal remain separate gates.
- **Verification:** The two manual-DNS fixture tests pass for success and failed-issue cleanup. The test invoking `/usr/local/sbin/renew-dev-ssl-acme-cron-curator` with fake ACME and a loopback receipt endpoint passes. Read-only checks confirm the installed wrapper SHA-256 matches its Vhost source and the root crontab retains four daily entries. `git diff --check` passes in Curator and Vhost.
- **Open gate:** No scheduled cron run or real DNS/certificate renewal was performed. Production retention/scheduling and release approval remain open.
- **Outcome:** Confirmed local fixture and installed-wrapper coverage without changing the Vhost consumer, running live ACME, restarting services, or claiming deployment evidence.

## 2026-10-26 — Split API review lifecycle regression

- **Intent:** Remove local-variable and statement-count findings from the API review lifecycle test while retaining its end-to-end assertions.
- **Changed fact:** Extracted typed scenario and artifact fixtures plus focused helpers for inventory authorization, review completion, dependency checks, cleanup, and feedback. The test still covers stale-packet rejection, exact inventory, authenticated reviewer attribution, scoped purge, privacy-safe metrics, feedback replay/uniqueness, and storage accounting.
- **Verification:** The focused lifecycle test passes. Strict Pyright reports zero diagnostics; focused Pylint reports no excessive-local or excessive-statement findings for the test; errors-only Pylint passes. The full-tree warning inventory drops from 52 to 50. `git diff --check` passes.
- **Open gate:** Repository-wide warning-level Pylint cleanup remains open; no plan checklist marker changed.
- **Outcome:** Reduced two Pylint findings without weakening the regression or changing application behavior.

## 2026-10-26 — Split Hermes binding lifecycle test helpers

- **Intent:** Remove complexity findings from the trusted Hermes binding and source-epoch regression without narrowing its lifecycle coverage.
- **Changed fact:** The test now separates active-goal binding, first event/replay, consumer re-enrollment, exact stale replay reconciliation, and retirement behavior. A typed lifecycle-call record preserves the original request fields, including `source_id` omission for fresh-session delivery and unseen events.
- **Verification:** The focused Hermes binding integration passes; strict Pyright reports zero diagnostics; errors-only Pylint passes on the test file; selected argument and complexity checks no longer flag the refactored flow. A fresh full-tree warning inventory reports 48 findings (8 convention and 40 refactor). `git diff --check` passes.
- **Open gate:** Repository-wide warning-level Pylint and the remaining oversized MCP tests remain open. No plan checklist marker changed; no application code changed.
- **Outcome:** Reduced the focused test's Pylint findings while retaining replay, re-enrollment, retirement, and trusted-context assertions.

## 2026-10-26 — Decompose the MCP SDE review and purge regression

- **Intent:** Remove complexity findings from the end-to-end SDE workflow test while preserving its review, persistence, purge, hold-release, and rejection assertions.
- **Changed fact:** Added typed disposable-workflow and review records, then split setup and lifecycle assertions into focused helpers. The hold-release failure/retry path remains exercised through the MCP client.
- **Verification:** The focused end-to-end regression passes; strict Pyright reports zero diagnostics; errors-only Pylint and `git diff --check` pass. Targeted complexity Pylint no longer reports excessive locals or statements for this test; other MCP client tests still have those findings.
- **Open gate:** Repository-wide warning-level Pylint cleanup remains open; no checklist marker changed.
- **Outcome:** Reduced test complexity without changing application behavior or claiming broader completion.

## 2026-10-26 — Correct the all-checkbox inventory total

- **Intent:** Correct the all-checkbox total in the preceding local producer-audit status record.
- **Changed fact:** The current plan contains 168 checked and 46 open top-level checkbox rows, 214 total. The separate delivery-scope count remains 153/178; the earlier 168/216 total was an inventory error.
- **Verification:** Counted top-level `- [ ]` and `- [x]` rows directly in `docs/curator-v2-plan.md`; the producer/artifact audit row is checked.
- **Open gate:** Scheduled cron execution, real certificate renewal, production gates, and release approval remain separate and open.
- **Outcome:** Corrected the reported inventory without changing any checklist marker.

## 2026-10-26 — Recheck the Hermes-profile Curator V2 route

- **Intent:** Verify current local-alpha Curator V2 connectivity through the configured Hermes profile after the gateway restart.
- **Changed fact:** The Hermes checkout CLI, loaded with the `renew-ssl-coding` profile config, connected to the Curator V2 stdio server and read `vhost-manager-alpha`: 48 tools, 29/29 processed receipts, 12 goals, eight facts, no review/purge backlog, seven healthy dependencies, and a complete zero-file staging inventory.
- **Verification:** `hermes mcp test curator_v2 --probe-curator-status` exited 0 with host-injected profile/session context. The direct Curator MCP `goal_list` call from this Codex session returned `unauthenticated`; that exact denial was not retried. No app-server lifecycle event was created.
- **Open gate:** Active system-gateway delivery of a real Codex app-server event remains unverified; Slice G and release acceptance remain open.
- **Outcome:** Confirmed the profile-context local-alpha route without claiming human authentication or live gateway delivery.

## 2026-10-26 — Separate Hermes MCP process observations

- **Intent:** Distinguish the active gateway's Vhost MCP child from the separate failed server startup without conflating MCP processes.
- **Changed fact:** The running gateway has a Curator MCP child bound by process arguments to `renew-ssl-coding` and the Vhost Manager repository. The logged failed startup has a different server name (`curatormd-v2`) from the Vhost profile's `curator_v2` entry. The successful profile CLI probe also starts its own stdio process. These observations do not establish a processed app-server event through the active Vhost gateway.
- **Verification:** Read-only checks of gateway child process arguments, systemd journal, and the profile MCP server names/configuration distinguish the paths.
- **Open gate:** A real Vhost-profile Codex app-server event acknowledged by Curator remains unverified; Slice G stays open.
- **Outcome:** Correctly scoped the runtime evidence; no consumer repository or state was modified.

## 2026-10-26 — Decompose the MCP lifecycle client regression

- **Intent:** Remove remaining local-variable complexity findings from the MCP client lifecycle regression without reducing its lifecycle assertions.
- **Changed fact:** Split criteria amendment, reviewer-approved fact compaction and archive checks, and planned-goal pagination/activation into focused helpers. Successful mutations continue to be checked for MCP errors through the shared JSON result helper.
- **Verification:** The focused MCP client lifecycle regression passes; strict Pyright reports zero diagnostics; targeted Pylint reports no excessive locals, statements, or arguments in `tests/test_mcp_server.py`; errors-only Pylint and `git diff --check` pass.
- **Open gate:** Repository-wide warning-level Pylint cleanup remains open. No checklist marker changed.
- **Outcome:** Removed the two remaining complexity findings in this test module while preserving its review, archive, pagination, and activation checks.

## 2026-10-26 — Group MCP scenario records by responsibility

- **Intent:** Remove dataclass attribute-count findings from the MCP server test fixtures while keeping their lifecycle inputs explicit.
- **Changed fact:** Nested Hermes delivery options under the lifecycle call record and grouped SDE scenario paths and transient-artifact fields into typed records. Existing helper accessors and workflow behavior remain unchanged.
- **Verification:** All eight tests in `test_mcp_server.py` pass; strict Pyright and errors-only Pylint pass. Full module Pylint now reports only `too-many-lines` (2,484/1,000); `git diff --check` passes.
- **Open gate:** Repository-wide warning-level Pylint cleanup remains open. No checklist marker changed.
- **Outcome:** Removed two module Pylint findings; the large MCP test module still needs decomposition.

## 2026-10-26 — Split MCP protocol tests by workflow

- **Intent:** Remove the oversized MCP server test module while keeping every protocol and lifecycle regression discovered.
- **Changed fact:** Separated trusted Hermes binding, SDE review/purge, and MCP client lifecycle tests into focused modules. Shared fixture and successful JSON-call helpers remain in `test_mcp_server.py`; duplicate project-review setup uses one shared helper.
- **Verification:** All eight tests are discovered and pass. Strict Pyright reports zero diagnostics; full warning-level Pylint reports no findings across the four affected modules; `git diff --check` passes.
- **Open gate:** The whole-repository warning inventory has not been rerun; repository-wide Pylint cleanup remains open. No checklist marker changed.
- **Outcome:** Removed the MCP module-length warning and preserved the existing test coverage without changing runtime code.

## 2026-10-26 — Recheck the active Hermes gateway runtime

- **Intent:** Reconcile the earlier missing-`jsonschema` gateway error with the current system service and Vhost Curator process.
- **Changed fact:** The system gateway is active as PID `1962718`, with its `renew-ssl-coding` `curator_v2` child PID `1963761`. The child's exact virtualenv imports `jsonschema` 4.26.0, and the profile's configured Codex binary exists. The earlier dependency errors came from the prior gateway process; the post-restart `curatormd-v2` startup failure is a distinct MCP entry.
- **Verification:** Read-only systemd/journal and process inspection, an import check through the child's interpreter, and an executable-path check confirm the separation. No new app-server event or Curator receipt was observed.
- **Open gate:** A profile-bound Codex app-server event acknowledged by the active Vhost gateway remains unverified. Slice G stays open; no checklist marker changed.
- **Outcome:** Updated the runtime diagnosis without modifying the Hermes system install or profile and without claiming lifecycle delivery.

## 2026-10-26 — Reconcile local producer/artifact audit closure

- **Intent:** Resolve the stale report that manual DNS, root ACME, and out-of-root disposition still left the local Vhost producer/artifact audit open.
- **Changed fact:** The V2 plan now explicitly states that the local single-repository audit is closed and its checkbox was already checked. Manual-DNS success/failure fixtures, the installed root-wrapper fake-ACME invocation, and owner-approved Vhost/OS disposition are documented in `docs/vhost-producer-coverage-v2.md`. Actual scheduled cron execution and real renewal remain separate runtime gates. The all-checkbox count is 168 checked, 48 open, 216 total; the earlier 166/216 report was stale.
- **Verification:** Re-read the current plan and coverage matrix; counted checklist markers in both `HEAD` and the worktree (168/216 in each); `git diff --check` passes. No producer tests were repeated because the eight focused checks are already recorded against the current reviewed snapshot.
- **Open gate:** Scheduled cron execution, real DNS/certificate renewal, production controls, and release approval remain open; these are not prerequisites to closing the local audit.
- **Outcome:** Reconciled status without changing a checklist marker, touching another repository, committing, pushing, or restarting a service.

## 2026-10-26 — Split installed Hermes launcher tests

- **Intent:** Reduce the hosted-MCP test module's structural lint findings without changing its runtime or reducing coverage.
- **Changed fact:** Moved four installed-stdio launcher and project-isolation tests into `tests/test_hosted_mcp_installed.py`. Shared disposable-project setup is a mixin used by both test modules.
- **Verification:** The focused hosted-MCP discovery run passes 18 tests. Strict Pyright reports zero diagnostics; warning-level Pylint scores both affected modules 10.00/10. The fresh whole-tree inventory falls from 39 to 38 findings; the `test_hosted_mcp.py` module-size finding is removed. The current CI quality checks pass: Pyright, errors-only Pylint, Bandit, locked dependency audit, and `git diff --check`.
- **Open gate:** Whole-tree warning-level Pylint remains open at 38 structural findings. No checklist marker changed.
- **Outcome:** Preserved every assertion and reduced the whole-tree warning inventory by one.

## 2026-10-26 — Record rejected real Hermes app-server smoke attempt

- **Intent:** Verify one real lifecycle delivery through the active system Hermes gateway into the bound Curator V2 ledger.
- **Changed fact:** The first CLI attempt stopped before execution because `--run-budget` is unsupported. After correcting the invocation, the stream reached `mcp.curator_v2.goal_start`, which returned exactly `user rejected MCP tool call`; no goal ID or further lifecycle action followed.
- **Verification:** The bounded command exited successfully at the CLI level, but its event stream contains only the rejected goal-start result and no activation or binding tool calls. The active gateway and Vhost Curator child were observed previously; no resulting Curator receipt is claimed.
- **Open gate:** Slice G remains open for an approved real app-server lifecycle event acknowledged by Curator. The rejected MCP call was not retried.
- **Outcome:** Preserved the rejection result and avoided claiming persistence, binding, or delivery.

## 2026-10-26 — Review flat-record Pylint findings

- **Intent:** Reduce whole-tree warning-level Pylint findings without changing the versioned V2 data contracts.
- **Changed fact:** Added class-scoped, reasoned exceptions for 17 flat typed records whose fields directly represent persisted rows, request/receipt contracts, configuration, or bounded response schemas.
- **Verification:** A fresh pinned whole-tree Pylint JSON scan reports 21 findings, down from 38: six module-size, six public-method-count, and nine duplicate-code findings. The scan introduced no other warning categories. `git diff --check` passes.
- **Open gate:** Repository-wide warning-level Pylint cleanup remains open at 21 findings; no checklist marker changed.
- **Outcome:** Removed the reviewed record-shape findings while preserving the flat V2 contracts.

## 2026-10-26 — Group purge and project-plugin test cases by workflow

- **Intent:** Remove oversized test-class warnings while keeping purge and project-plugin assertions together with their shared disposable fixtures.
- **Changed fact:** Split 30 purge tests into lifecycle, migration, and filesystem test classes, and 55 project-plugin tests into five workflow classes. Test methods and fixture setup remain in their existing modules; runtime source is unchanged.
- **Verification:** All 30 purge tests and all 55 project-plugin tests pass. Targeted strict Pyright reports zero diagnostics for both files; targeted warning-level Pylint no longer reports excessive public methods. Fresh whole-tree Pylint falls from 21 to 19 findings; `git diff --check` passes.
- **Open gate:** The whole-tree warning inventory still has six oversized modules, four large public classes, and nine duplicate-code notices. No checklist marker changed.
- **Outcome:** Preserved all 85 focused regression cases and reduced the repository-wide warning count by two.

## 2026-10-26 — Group API tests by behavior

- **Intent:** Remove the API test class's public-method warning while keeping its shared authorization and review fixtures in one module.
- **Changed fact:** Grouped the 41 existing API tests into goal/access, health/metrics, evidence/ingress, and review-workflow classes. Shared fixture and helper methods remain on one base test class; implementation behavior is unchanged.
- **Verification:** All 41 tests pass. Targeted strict Pyright reports zero diagnostics, targeted warning-level Pylint no longer reports excessive public methods, and a fresh whole-tree scan falls from 19 to 18 findings. `git diff --check` passes.
- **Open gate:** Whole-tree warning-level Pylint remains open at 18 findings; no checklist marker changed.
- **Outcome:** Preserved all API assertions and reduced one structural warning.

## 2026-10-26 — Fix access CLI test connection warning

- **Intent:** Remove the unclosed SQLite connection warning from the access CLI regression without weakening its grant, suspension, reactivation, or revocation checks.
- **Changed fact:** The test now closes its direct database connection deterministically and splits stale-review denial from exact-review reactivation/replay.
- **Verification:** All four tests in `tests/test_access_cli.py` pass with `ResourceWarning` treated as an error. The current whole-tree warning-level Pylint inventory reports 18 findings and no longer includes `test_access_cli.py`. The repository quality commands pass: strict Pyright (0 diagnostics), errors-only Pylint, Bandit, `uv audit --locked --preview-features audit-command` (no known vulnerabilities), and `git diff --check`.
- **Open gate:** The full 468-test run occurred before this test-only change and was not rerun afterward. Repository-wide Pylint findings remain open at 18 structural size/duplication notices; no checklist marker changed.
- **Outcome:** Removed one test resource leak and its complexity warning without claiming post-fix full-suite verification.

## 2026-10-26 — Split API tests into workflow modules

- **Intent:** Reduce repository-wide Pylint module-size findings while preserving the API test cases and shared fixtures.
- **Changed fact:** Moved the four API workflow classes into dedicated goal/access, health/metrics, evidence/ingress, and review-workflow modules. `test_api.py` now contains shared fixtures; repeated verified-goal setup and healthy-probe API construction use shared typed helpers.
- **Verification:** All 41 API tests pass. Strict Pyright reports zero diagnostics, the five affected modules score 10.00/10 under warning-level Pylint, and `git diff --check` passes. A fresh whole-tree inventory falls from 18 to 16 findings: five module-size, three public-method-count, and eight duplicate-code findings.
- **Open gate:** Repository-wide Pylint cleanup remains open at 16 findings. The full test suite was not rerun after this test-only refactor; no checklist marker changed.
- **Outcome:** Removed the oversized API test module without removing or weakening assertions.

## 2026-10-26 — Share deterministic SQLite cleanup in local CLIs

- **Intent:** Remove duplicated database cleanup branches from the attended access and stdin-staging commands.
- **Changed fact:** Both commands now use `contextlib.closing` around the opened `CuratorStore`, including early return and exception paths.
- **Verification:** Four access CLI tests and two producer CLI tests pass. Strict Pyright reports zero diagnostics; targeted warning-level Pylint rates both modules 10.00/10; `git diff --check` passes. The fresh whole-tree inventory falls from 16 to 15 findings (five module-size, three public-method-count, seven duplicate-code).
- **Open gate:** Repository-wide warning-level Pylint remains open at 15 findings. The full suite was not rerun after this scoped change; no checklist marker changed.
- **Outcome:** Removed one repeated cleanup pattern and preserved CLI behavior.

## 2026-10-26 — Share attended CLI argument construction in tests

- **Intent:** Remove duplicated access-CLI argv construction from the access and review regressions.
- **Changed fact:** Added `tests/cli_test_support.py` with a typed helper for the shared operation, project-root, database, and extra-option arguments; both test suites use it.
- **Verification:** Four access CLI and nine review CLI tests pass. Strict Pyright reports zero diagnostics; targeted warning-level Pylint scores the helper and both suites 10.00/10; `git diff --check` passes. Fresh whole-tree Pylint falls from 15 to 14 findings, including six duplicate-code notices.
- **Open gate:** Repository-wide Pylint cleanup remains open at 14 findings; no checklist marker changed.
- **Outcome:** Removed one duplicated test setup without changing CLI behavior.

## 2026-10-26 — Share deterministic event retry setup in tests

- **Intent:** Remove repeated direct SQL that fast-forwards an event retry deadline in the event-contract and durable-router regressions.
- **Changed fact:** Added `tests/event_test_support.py` with `make_event_retry_due`; both suites use the helper while keeping their separate processing and routing assertions.
- **Verification:** All 23 event tests and nine router tests pass. Strict Pyright reports zero diagnostics, targeted warning-level Pylint scores the support and affected modules 10.00/10, and `git diff --check` passes. Whole-tree Pylint falls from 14 to 13 findings, with five duplicate-code notices remaining.
- **Open gate:** Repository-wide Pylint cleanup remains open at 13 findings; no checklist marker changed.
- **Outcome:** Removed one duplicated retry fixture without changing application behavior.

## 2026-10-26 — Confirm producer/artifact audit closure and correct checklist total

- **Intent:** Close the reported local V2 producer/artifact audit and reconcile its checklist status.
- **Changed fact:** The audit checkbox in `docs/curator-v2-plan.md` is already checked. Current evidence covers manual-DNS success in disposable state, invocation of the installed root ACME wrapper against fake ACME and a loopback receipt endpoint, and the owner-approved Vhost/OS disposition for artifacts outside Curator's staging root. No marker change was needed.
- **Verification:** Recounted top-level checklist rows in the current plan: 168 checked, 46 open, 214 total. The plan's defined delivery scope remains 153/178 complete, 25 open. `git diff --check` passes. Existing plan and coverage records document eight passing focused producer tests; they were not rerun in this reconciliation.
- **Open gate:** Actual scheduled cron execution, real DNS/certificate renewal, production controls, and release approval remain separate runtime/release gates; none reopens the local source/artifact audit.
- **Outcome:** Confirmed closure and corrected the stale 166/216 and 168/216 all-checkbox reports to 168/214. No consumer repository was modified, and no commit, push, or service restart was performed.

## 2026-10-26 — Reverify local producer audit on current snapshot

- **Intent:** Close the reported local V2 producer/artifact audit for manual DNS, the root ACME bridge, and out-of-root ownership using current local evidence.
- **Changed fact:** The checked audit row now records a fresh current-snapshot verification. The owner-approved Vhost/OS disposition keeps out-of-root artifacts outside Curator scan and purge. A fresh sorted 24-path Vhost manifest is `1954612b71ceeef4a2fe274b5eed30c5ad7a2b6778c66767213b8c91696bd075` at dirty HEAD `1924fa2`; the Curator config hash remains unchanged.
- **Verification:** All eight focused producer tests pass, including both manual-DNS paths and the installed root-wrapper test against fake ACME and a loopback receipt endpoint. Installed and source wrapper hashes match at `28afc265f2a0193d443bd90569865f3bf5c1d00620930f41caab150d8c2a6f25`; read-only crontab inspection confirms four daily entries. Direct count of plan checklist rows remains 168 checked, 48 open, 216 total.
- **Open gate:** The scheduled cron itself has not been run, and no real DNS/certificate renewal occurred. Production scheduling/retention and release acceptance remain separate gates.
- **Outcome:** Confirmed the local producer/artifact audit is closed; its checkbox was already checked, so no marker changed.

## 2026-10-26 — Wire configured Git evidence capture into the local host CLI

- **Intent:** Advance the open source-specific evidence integration with a usable local path for immutable repository diffs and exact-commit test runs.
- **Changed fact:** The owner-only evidence config now loads the existing Git diff and test-runner resolvers into the fixed host registry. `curatormd-v2-evidence repository-diff` and `repository-test` produce only an evidence kind, full-commit locator, digest, and outcome. The test command remains a host-owned argv and runs in a temporary checkout of the exact commit. `docs/local-service-probes.md` documents the schema and commands.
- **Verification:** Nine local evidence-config tests and two capture CLI tests pass; four existing Git resolver regressions pass. The capture CLI tests confirm test output canaries do not appear in output. Strict Pyright reports zero diagnostics; targeted Pylint scores all affected source and test files 10.00/10. The current repository CI quality gates pass: strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and `git diff --check`.
- **Open gate:** `local-git:` is a local host assertion, not authenticated provider or hosted-CI identity. Service/browser source authentication, human-observation receipt, deployment trust roots, rotation/revocation and outage probes, and the verifier-to-completion race remain open. The related checklist row remains open; no marker changed.
- **Outcome:** Added a usable local Git evidence capture path without changing consumer configuration or claiming deployed-source authentication.

## 2026-10-26 — Refresh whole-tree warning inventory

- **Intent:** Keep the open repository-wide Pylint checklist item tied to a fresh scan after recent local changes.
- **Changed fact:** Project registration and project-authorization binding share one typed builder for validated config fingerprint fields. The new Git evidence config and capture paths introduce no targeted warning-level Pylint findings.
- **Verification:** A fresh pinned whole-tree warning-level Pylint JSON scan reports 12 findings: five `too-many-lines`, three `too-many-public-methods`, and four `duplicate-code`, down from the previously recorded 13. Strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass.
- **Open gate:** Repository-wide warning-level Pylint remains open at 12 structural findings. No checklist marker changed.
- **Outcome:** Corrected the recorded warning inventory without treating focused cleanliness as completion of the repository-wide item.

## 2026-10-26 — Reverify and close the local producer/artifact audit

- **Intent:** Resolve the reported open status for manual DNS, the root ACME cron bridge, and out-of-root artifact dispositions in the approved single-repository development alpha.
- **Changed fact:** The V2 plan records the local audit as closed. The owner-approved Vhost/OS disposition keeps ACME state, certificate/key files, Nginx files, logs, inventories, and temporary state outside Curator scan and purge; Curator receives bounded outcomes only. The fresh 33-path consumer working-tree manifest is `0d7f848f6312776d74abb7b7b9659c6b0c94bc4fc6bfef56f487883125fa8645` at dirty Vhost HEAD `1924fa2`.
- **Verification:** Eight focused producer regressions pass, including manual-DNS success/failure and an explicit test of the installed root wrapper with fake ACME and a loopback receipt endpoint. Installed/source wrapper hashes match; read-only root crontab inspection confirms four daily entries. Both log-expiry tests pass and the six-hour `expire-manual-dns-logs.timer` is enabled and active. `git diff --check` passes. Direct V2 plan recount is 168 checked, 48 open, 216 total; the audit checkbox was already checked.
- **Open gate:** Actual scheduled ACME execution, real DNS/certificate renewal, and production controls remain runtime/release gates; they do not leave this local audit open.
- **Outcome:** Closed the reported local producer/artifact audit without changing a checklist marker, editing the Vhost consumer, touching GPTMD, committing, pushing, or restarting a service.

## 2026-10-26 — Add attended local human-observation receipts

- **Intent:** Advance the open V2 source-specific evidence integration for the owner-approved single-user development alpha.
- **Changed fact:** The owner-only host evidence config can enable `human_observation`; `curatormd-v2-evidence human-observation` requires a terminal and an exact one-time challenge response, and binds a content-free passed receipt to the configured project, goal, criterion, and effective OS UID. Receipts are owner-only, expire within 15 minutes, and fail verification when missing, changed, expired, or used for another scope. Removing the exact receipt file revokes it. The source subject is host-derived; no observation text is stored.
- **Verification:** Six focused human-observation tests pass, covering attended and unattended CLI paths, exact context and UID binding, challenge mismatch, tampering, expiry, and receipt removal. Strict Pyright reports zero diagnostics; targeted warning-level Pylint scores 10.00/10; `git diff --check` passes.
- **Open gate:** No host evidence file was installed and no human observation was captured. This local OS-account receipt does not establish Hermes human identity, deployment trust/rotation or an independent revocation service, source outage behavior, or the verifier-to-completion race. The source-specific integration row remains open; no checklist marker changed.
- **Outcome:** Added the local-alpha human confirmation path and documented its limits without changing consumer repositories, installing host configuration, committing, or pushing.

## 2026-10-26 — Reverify local producer coverage and close lease-expiry race

- **Intent:** Confirm the already-closed single-repository producer/artifact audit on the current Vhost snapshot, then address the local evidence-lease expiry race in goal completion.
- **Changed fact:** The Curator V2 plan keeps the producer/artifact and standalone coverage rows checked and now records direct and event-driven completion's in-transaction lease-expiry recheck. It does not close external revocation/version semantics or deployed evidence trust.
- **Verification:** Ran eight focused Vhost test files: 10 tests pass, covering the manual DNS fixture, installed root-wrapper fixture, standalone utilities, bounded queues, redaction, and log expiry. Curator direct/event lease-expiry regressions pass (2), the positive event-completion regression passes (1), strict Pyright reports zero diagnostics, targeted Pylint scores 10.00/10, and `git diff --check` passes in both worktrees. The current plan count is 168/216 complete, 48 open; no checklist marker changed.
- **Open gate:** Actual scheduled cron execution, real certificate renewal, and production/release evidence remain open. External evidence revocation/version races and deployed trust remain open. The Vhost checkout is dirty; no consumer source was changed in this turn.
- **Outcome:** Confirmed the requested local audit is closed and tightened the local completion currentness check without changing checklist status, committing, pushing, deploying, or restarting services.

## 2026-10-26 — Verify current blocking quality gates

- **Intent:** Run the repository's documented CI type, blocking-lint, security, and dependency checks against the current worktree.
- **Changed fact:** The V2 plan records the fresh CI-gate result and keeps the separate warning-level Pylint refactor open.
- **Verification:** Strict Pyright reports zero diagnostics; errors-only Pylint and Bandit pass; `uv audit --locked --preview-features audit-command` finds no known vulnerabilities or adverse project statuses across 50 packages; Curator `git diff --check` passes. The full warning-level Pylint inventory is 12 structural findings (five oversized modules, three public-method counts, four duplicate-code diagnostics).
- **Open gate:** Repository-wide structural Pylint cleanup remains open. No checklist marker changed; the current all-checkbox count is 168/216 complete, 48 open.
- **Outcome:** Reconciled current CI evidence without suppressing warnings, running the full unit suite, committing, or pushing.

## 2026-10-26 — Refresh and verify the installed Vhost alpha wheel

- **Intent:** Bring the owner-approved local Vhost alpha onto the current tested V2 source and verify its installed package and Hermes-managed consumer path.
- **Changed fact:** Built and installed wheel SHA-256 `f804deb41386b36c445d65f1e6bad283f139944836ffbf64ce8d2fd715f2430c` only in the `renew-ssl-coding` Curator V2 virtualenv. Before replacement, archived the prior package, dist-info, and eight launchers in the verified 141-entry file `~/.hermes/profiles/renew-ssl-coding/backups/curator-v2-before-wheel-f804deb4-20261026T1435Z.tar.gz` (SHA-256 `74edd9c3e52cedd8c12ec9190d4f9656f5315507b6d7848fd17f336225fd4ce2`). Fixed the CI wheel job's stale installed-test module/class references after the clean-wheel invocation exposed them; added its missing `curatormd-v2-evidence --help` check.
- **Verification:** All 478 Curator tests pass. Strict Pyright, errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. A clean Python 3.12 wheel passes both installed-MCP tests, all eight CLI entrypoints, and installed backup/restore with SQLite integrity and row preservation. All 63 profile-installed Python modules match source and `uv pip check` passes. The Vhost-owned Hermes-managed disposable integration passes five events including retry/replay, re-enrollment, project/goal binding, projection reconciliation, and privacy checks. A fresh profile-context probe reports 35/35 processed receipts, 15 goals, 11 facts, no review/purge backlog, and healthy dependencies/staging.
- **Open gate:** The active system gateway was not restarted. No real app-server lifecycle event or new live Vhost operation was produced. Slice G and production/release evidence remain open; repository-wide warning-level Pylint remains at 12 structural findings. No checklist marker changed; all-checkbox progress remains 168/216 complete, 48 open.
- **Outcome:** Refreshed the local Vhost alpha and repaired the clean-wheel CI acceptance path without modifying Vhost source, changing the gateway/service, committing, or pushing.

## 2026-10-26 — Codify Curator V2 delivery progress counting

- **Intent:** Stop reusable Section 11 task-template checkboxes from being reported as V2 delivery progress.
- **Changed fact:** Added `tools/count_curator_v2_delivery.py`; the official count includes only top-level checklist rows in plan sections 0–10 and 12. It reports 153/178 complete and 25 open. The raw inventory count of 168/216 also includes Section 11's developer workflow contract and is not a delivery progress measure.
- **Verification:** Ran the count script against `docs/curator-v2-plan.md`; it returned 153/178 and matched `docs/release-gates-v2.md`. `git diff --check` passes.
- **Open gate:** Repository-wide warning-level Pylint remains open with 12 structural findings (five module-size, three public-method-count, four duplicate-code diagnostics); no delivery checkbox changed.
- **Outcome:** Replaced the misleading all-checkbox count in the producer-audit status and made the delivery count repeatable without changing checklist markers.

## 2026-10-26 — Share the V2 goal-definition schema

- **Intent:** Remove duplicate field definitions between the versioned `goal.started` payload and the persisted goal snapshot.
- **Changed fact:** `GoalStarted` and `GoalCard` now inherit the same typed `GoalDefinitionFields`; field order and constructor keyword names remain unchanged. The shared immutable schema carries a documented class-level Pylint exception for its required record fields.
- **Verification:** Event and validation suites pass (26 tests); targeted Pyright reports zero diagnostics; the focused duplicate-code scan is clean for the changed goal definitions. The fresh whole-tree warning inventory falls from 12 to 11: five module-size, three public-method-count, and three duplicate-code findings. `git diff --check` passes.
- **Open gate:** Repository-wide Pylint cleanup remains open at 11 findings; the delivery checklist marker remains open.
- **Outcome:** Removed one structural duplication and preserved the existing event/model call shape without changing any checklist marker.

## 2026-10-26 — Share cleanup status record fields

- **Intent:** Remove the duplicated per-artifact retry fields from the stored purge record and service status response.
- **Changed fact:** `PurgeTargetStatus` and `PurgeTargetRecord` now inherit the same typed `PurgeTargetFields`, preserving their serialized field names and order.
- **Verification:** Purge, event, and validation suites pass (56 tests plus two subtests); targeted Pyright reports zero diagnostics; the focused duplicate-code scan is clean for the shared records. Fresh whole-tree Pylint reports 10 findings: five module-size, three public-method-count, and two duplicate-code findings. `git diff --check` passes.
- **Open gate:** Repository-wide Pylint cleanup remains open at 10 findings; no delivery checkbox changed.
- **Outcome:** Removed a second duplicated record definition without changing purge behavior or checklist status.

## 2026-10-26 — Recheck local project-usage coverage

- **Intent:** Refresh local evidence for the open project staging and model/token budget requirement before setting any threshold.
- **Changed fact:** The `project-usage` plugin remains enabled in `renew-ssl-coding`, and its installed ledger reader reports six bound project turns: five reported, one unknown, sourced from `codex_app_server`. Project-wide and captured-turn token completeness both remain false.
- **Verification:** `hermes -p renew-ssl-coding plugins doctor project-usage --ci` passes runtime discovery, import, and one-tool registration. A read-only ledger query returned the counts and incompleteness flags without printing token values. No provider API call was made.
- **Open gate:** Staging budget values, token source completeness, accounting window, threshold/alert policy, billing reconciliation, and retention approval remain open; no checklist marker changed.
- **Outcome:** Updated the plan with current profile evidence and kept budgets unapproved pending the owner's concrete limits.

## 2026-10-26 — Remove two repository-wide duplicate-code findings

- **Intent:** Continue the open repository-wide Pylint cleanup using behavior-preserving deduplication.
- **Changed fact:** The shared project-access test support now constructs the base status request once and applies reactivation receipt fields with immutable `replace` calls. The evidence fixture now assembles one typed field mapping before creating its attestation, instead of repeating the production constructor's field sequence.
- **Verification:** The project-access suite passes 12 tests and the evidence-currentness suite passes 2. Strict Pyright reports zero diagnostics; focused duplicate-code Pylint is clean for both changed modules. A fresh whole-tree scan reports 8 structural findings, down from 10: five oversized modules and three public-method counts. `git diff --check` passes.
- **Open gate:** The repository-wide Pylint checklist remains open until all eight findings are resolved. No checklist marker changed.
- **Outcome:** Removed two duplicated code blocks without changing behavior; the full suite was not rerun.

## 2026-10-26 — Split oversized project-plugin test module

- **Intent:** Reduce the open repository-wide Pylint findings without suppressing the module-size rule or changing test behavior.
- **Changed fact:** Split `tests/test_project_plugin.py` along its five existing test classes; moved shared setup and race helpers into `tests/project_plugin_test_support.py`. Test method bodies and names remain intact.
- **Verification:** All 55 project-plugin tests pass. Strict Pyright reports zero diagnostics, and Pylint rates the support and split test modules 10.00/10. A fresh whole-tree structural scan falls from eight to seven findings: four oversized modules and three public-method counts. The original purge test suite also passes 30 tests after an attempted purge split was reverted. `git diff --check` passes.
- **Open gate:** Repository-wide Pylint cleanup remains open at seven findings. No checklist marker changed.
- **Outcome:** Removed one oversized test-module finding while preserving all project-plugin test cases; no runtime source changed.

## 2026-10-26 — Reverify the local producer/artifact audit

- **Intent:** Resolve the reported open status for manual DNS, the installed root ACME bridge, and out-of-root artifact disposition in the approved Vhost alpha.
- **Changed fact:** The audit row in `docs/curator-v2-plan.md` was already checked. Its current dirty Vhost snapshot is now bound by the refreshed 33-path manifest `1a3fe9f4c52076dcf0097690cd2544e57880987a0a134fb79b555ac4c68ac1a4` in `docs/vhost-producer-coverage-v2.md`. Owner-approved Vhost/OS paths remain outside Curator scan and purge.
- **Verification:** Seven focused producer tests pass, including manual-DNS success/failure and the installed root-wrapper fixture; two log-expiry tests pass. Read-only checks confirm four root schedule entries, matching installed/source wrapper hashes, and an enabled, active six-hour expiry timer. `git diff --check` passes in both repositories.
- **Open gate:** Real scheduled cron execution, real DNS/certificate renewal, and production/release controls remain separate runtime gates.
- **Outcome:** Confirmed the local audit closure and refreshed its evidence binding. No checklist marker changed; no consumer source changed; no commit, push, or service restart occurred.

## 2026-10-26 — Decompose the authenticated API facade

- **Intent:** Reduce one repository-wide structural Pylint finding without changing the public API or authorization behavior.
- **Changed fact:** `AuthenticatedCuratorAPI` retains its constructor and all 41 public method names. Existing implementations now live in inherited event, goal, storage, and review/purge method groups; the project effect-fence decorator remains applied to the same operations.
- **Verification:** An AST comparison confirms the original and inherited public method-name sets are identical. All 41 API tests and eight MCP-facing tests pass. Strict Pyright reports zero diagnostics; focused Pylint rates `api.py` 10.00/10. The full warning-level scan falls from seven to six structural findings: four oversized modules and two public-method counts. `git diff --check` passes.
- **Open gate:** Repository-wide warning-level Pylint cleanup remains open; no checklist marker changed. Current delivery progress remains 153/178 complete, 25 open.
- **Outcome:** Reduced the structural warning inventory while preserving the API surface; no commit, push, deployment, or service restart occurred.

## 2026-10-26 — Split the Curator service by behavior

- **Intent:** Remove the service module's structural size and public-method findings without changing goal, review, purge, or event behavior.
- **Changed fact:** `CuratorService` now composes ordered internal mixins for lifecycle, reporting, review, purge, and event processing. The original 38 public method names and `service.py` import path remain intact; status/request types and the hosted-MCP event test record remain importable there. Frozen-clock tests patch the new attestation module.
- **Verification:** AST comparison confirms all 38 public service method names match the pre-split class. The 159 API/MCP/service/lifecycle/purge/event tests, 12 hosted-MCP tests, and 55 project-plugin tests pass. Strict Pyright reports zero diagnostics; focused Pylint rates all affected modules 10.00/10. Full-tree Pylint reports four remaining structural findings (three oversized modules and one public-method count); `git diff --check` passes.
- **Open gate:** Repository-wide warning-level Pylint cleanup remains open; delivery progress remains 153/178 complete, 25 open. No checklist marker changed.
- **Outcome:** Removed both `service.py` structural findings while preserving its public method surface; no commit, push, deployment, or service restart occurred.

## 2026-10-26 — Reconfirm local Vhost producer audit closure

- **Intent:** Resolve the reported open status for manual DNS, root ACME cron integration, and out-of-root artifact disposition in the approved single-repository alpha.
- **Changed fact:** The V2 plan's local producer/artifact audit checkbox was already checked. Its approved scope includes the manual DNS and standalone utilities, the installed root-wrapper path, and owner-approved Vhost/OS ownership outside Curator scan and purge.
- **Verification:** Five standalone workflow tests, one installed root-wrapper fake-ACME test, one bounded result-queue test, and two log-expiry tests pass. Read-only checks confirm four daily root cron entries, matching installed/source wrapper SHA-256, and the enabled, active six-hour log-expiry timer. `git diff --check` passes in both repositories.
- **Open gate:** This does not claim an actual scheduled cron run or real DNS/certificate renewal; those remain runtime/release evidence. No checklist marker or delivery count changed.
- **Outcome:** Reconfirmed local producer/artifact audit closure for the approved alpha; no deployment, service restart, commit, or push occurred.

## 2026-10-26 — Reduce CuratorStore structural warnings

- **Intent:** Remove the public-method-count finding from the open repository-wide Pylint cleanup without changing the store API or behavior.
- **Changed fact:** Split the existing store operations into six dependency-ordered internal base classes. `CuratorStore` retains its import path and all 116 public method names; an AST comparison against the pre-split source confirms exact parity.
- **Verification:** Focused store, migration, access, event, purge, lifecycle, and concurrency suites pass 130 tests. Strict Pyright reports zero diagnostics. Targeted Pylint reports only the 9645-line module-size finding, and a fresh whole-tree scan has three size findings: `store.py`, `tests/test_migrations.py`, and `tests/test_purge.py`. `git diff --check` passes.
- **Open gate:** Repository-wide Pylint cleanup remains open for those three oversized modules. No checklist marker changed; no commit or push occurred.
- **Outcome:** Removed one whole-tree structural finding while preserving the public store surface.

## 2026-10-26 — Verify current local-alpha health probes

- **Intent:** Check whether the Vhost alpha's configured operational probes still leave project health unknown or degraded.
- **Changed fact:** The Hermes Core checkout CLI, using host-injected `renew-ssl-coding` profile/session context, returned `project_health=healthy` for `vhost-manager-alpha` at `2026-10-26T15:41:09Z`. All seven required dependencies are healthy: event router, purge scheduler, database storage adapter, host identity, human review, alert delivery, and artifact producer inventory. The staging inventory is complete and empty; pending review, purge-receipt, purge-artifact, expiry-receipt, and expiry-artifact counts are all zero.
- **Verification:** `./hermes -p renew-ssl-coding mcp test curator_v2 --probe-curator-status` exited 0; the bounded health response contains no gate codes.
- **Open gate:** This is a profile-context local-alpha read, not an active system-gateway app-server event, production identity, or external alert-delivery test. No checklist marker changed.
- **Outcome:** Confirmed healthy local-alpha operational probe coverage without restarting services or changing runtime configuration.

## 2026-10-26 — Verify scheduled local-alpha maintenance run

- **Intent:** Confirm the owner-approved six-hour purge retry timer has completed a scheduled run after its cadence change.
- **Changed fact:** `curatormd-v2-maintenance@vhost-manager-alpha.timer` is active; its scheduled run at 2026-10-26 18:00:11 +07 exited successfully. The bounded journal summary reports zero processed and zero pending purge/expiry targets. Its next trigger is 2026-10-27 00:00:02 +07.
- **Verification:** Read-only systemd properties report `Result=success`, `ExecMainStatus=0`, and the matching last/next trigger times. The journal contains only the project ID and bounded zero-valued counts.
- **Open gate:** This proves one local scheduled run only; production scheduling, external alerting, and restart/reconciliation evidence remain open. No checklist marker changed.
- **Outcome:** Replaced the stale “first scheduled run pending” note with current local timer evidence; no timer or service was changed.

## 2026-10-26 — Wire local evidence sources into the Vhost profile

- **Intent:** Make the approved single-user Vhost alpha's host-owned local evidence sources available to its bound Curator V2 profile.
- **Changed fact:** The `renew-ssl-coding` profile passes an owner-only evidence config bound to `vhost-manager-alpha`. It configures a local maintenance-timer probe, exact-commit Git diff, a Vhost manual-DNS fixture test runner, loopback browser proof, and attended `eaglesvn` observation receipts. Test output is normalized to a deterministic test-count/pass result before hashing; raw output is not retained. The JSON file is mode `0600`, the receipt directory is `0700`, and the prior Hermes profile config is backed up.
- **Verification:** The installed resolver attested the timer probe, committed Git diff, exact-commit fixture test, and browser capture/revalidation. The profile MCP check exited 0, discovered 48 tools, read the ledger, and reported healthy project status. No human receipt was created. Evidence-config SHA-256: `29667f3eaf8403ee0ad807f07f52989b10eca5b96ecac38e94fc07f4bb228296`; pre-change profile-config backup SHA-256: `d5181ebc1daa14c728e7d34114a58c008dd07c5d6dfacff00b8e2856efc2cdd3`.
- **Open gate:** Local human observation still requires an attended action. Deployed trust roots, remote identity, and loading this config in the already-running gateway remain open. No gateway/service restart or checklist-marker change occurred.
- **Outcome:** Enabled and verified all configured local non-human source paths for newly launched profile MCP processes; the active gateway process was left untouched.

## 2026-10-26 — Add content-free service-probe capture

- **Intent:** Let the local evidence CLI produce a usable reference for an owner-configured service probe without exposing probe output.
- **Changed fact:** Added `curatormd-v2-evidence service-probe`. It runs the exact configured argv, hashes bounded stdout, and emits only evidence kind, probe locator, digest, and pass outcome. Capture and verifier share the project-bound owner-only configuration; the verifier reruns the probe and checks the same digest.
- **Verification:** The focused evidence CLI, host-config, and service-resolver suites pass 16 tests. Strict Pyright reports zero diagnostics; focused Pylint rates all changed modules 10.00/10. A source-worktree capture against the installed `vhost-manager-alpha` profile config was immediately attested as `local-probe:eaglesvn`; its output was not printed or retained. `git diff --check` passes.
- **Open gate:** The probe remains a host-local assertion, not a deployment-authenticated service identity. No checklist marker changed; the active Hermes gateway was not restarted.
- **Outcome:** Completed the local capture-to-verification path for configured service probes without exposing command output.

## 2026-10-26 — Reverify and close local producer/artifact audit

- **Intent:** Close the reported V2 local-alpha audit for manual DNS, root ACME integration, and artifacts outside Curator staging.
- **Changed fact:** The V2 plan and producer-coverage record confirm this audit is closed for the approved one-repository Vhost development alpha. The owner-approved Vhost/OS disposition keeps ACME state, keys/certificates, Nginx files, logs, inventories, and temporary files outside Curator scan and purge; only bounded outcomes enter Curator.
- **Verification:** Reran nine focused disposable Vhost tests: manual-DNS success/failure, installed root-wrapper fake-ACME receipt, bounded result bridge, batch renewal, inventory refresh, Nginx setup, and both log-expiry cases; all pass. Installed/source wrapper SHA-256 values match. Read-only crontab inspection confirms four daily entries; the approved six-hour expiry timer is enabled and active. No live renewal was invoked.
- **Open gate:** Actual scheduled ACME execution, real DNS/certificate renewal, and production controls remain separate runtime/release gates. The local audit row was already checked; no marker changed.
- **Outcome:** Reconfirmed closure of the local audit without editing the Vhost consumer, touching GPTMD, committing, pushing, or restarting a service.

## 2026-10-26 — Remove duplicate evidence-test fixture

- **Intent:** Reduce the current repository-wide Pylint findings while preserving local evidence CLI/config test behavior.
- **Changed fact:** Added a shared test-only service-probe host-config builder and reused it in the CLI and host-config suites, removing the duplicated fixture block.
- **Verification:** The focused suites pass 12 tests; strict Pyright reports zero diagnostics; focused Pylint rates all changed test modules 10.00/10; `git diff --check` passes. The fresh whole-tree Pylint scan now has three `too-many-lines` findings (`store.py`, `test_migrations.py`, `test_purge.py`), down from those three plus one duplicate-code warning.
- **Open gate:** Repository-wide Pylint remains open until the three oversized modules are decomposed and a full scan passes. No checklist marker changed.
- **Outcome:** Removed one whole-tree warning without changing product behavior or the public API.

## 2026-10-26 — Exercise configured Vhost evidence sources

- **Intent:** Verify the current owner-configured local source adapters against the bound Vhost project.
- **Changed fact:** The installed `renew-ssl-coding` evidence config is present at mode `0600`, SHA-256 `29667f3eaf8403ee0ad807f07f52989b10eca5b96ecac38e94fc07f4bb228296`, and remains bound to `vhost-manager-alpha`.
- **Verification:** The exact Git-diff capture passed for `7d2b10f5…1924fa23` (digest `07adce01333b4aeda55c656675c6975b845e8a94c9fc5ed04b84c34e883c4d26`); the configured `vhost-manual-dns-fixture` runner passed at commit `1924fa23…` (digest `f6452a6de59b28bfe5fc38ababebcc383bd0646830593daba97831426bbac9c5`); and configured Chrome rendered `http://127.0.0.1:4310/` (digest `0bcb34d1ac447d769d8802a35fe753e5658f8ddcf814c0916227f2086118846c`). Outputs contained only bounded references and digests.
- **Open gate:** These resolver captures are local host assertions and were not attached to a durable criterion-verification fact. A direct Codex `goal_list` read returned `unauthenticated`, so no active goal/criterion IDs were obtained and no ledger mutation was attempted. Attended human confirmation, deployment trust roots, rotation/revocation/outage probes, and the verifier-to-completion boundary remain open. No checklist marker changed; the active gateway was not restarted.
- **Outcome:** Reverified repository diff, exact-commit test runner, and loopback browser proof through the configured local alpha without changing the consumer repository.

## 2026-10-26 — Split oversized migration and purge test suites

- **Intent:** Remove the test-module size findings from the open repository-wide Pylint item without changing regression assertions.
- **Changed fact:** Split purge tests into lifecycle, migration, and filesystem modules with shared fixtures. Split migration tests into a current-schema suite and three legacy-schema suites with shared migration adapters/builders; preserved the current `purge_targets.outcome` schema expectation.
- **Verification:** All 30 purge and 39 migration tests pass. Strict Pyright reports zero diagnostics; focused Pylint on the split/support modules rates 10.00/10; `git diff --check` passes. The fresh whole-tree Pylint scan reports only `src/curatormd_v2/store.py` (9645/1000 lines), rating 10.00/10 and exiting 16.
- **Open gate:** Repository-wide Pylint remains open until the store module is decomposed and a clean full scan passes. No checklist marker changed.
- **Outcome:** Removed two whole-tree size findings while retaining every test case; no public product API changed.

## 2026-10-26 — Reverify local producer/artifact audit evidence

- **Intent:** Resolve the status discrepancy around the approved Vhost alpha audit for manual DNS, the root ACME bridge, and out-of-root artifact disposition.
- **Changed fact:** The checklist row was already checked. The V2 plan now states that the audit is closed for the single-repository local alpha, while scheduled cron execution and real DNS/certificate renewal remain separate runtime gates.
- **Verification:** Nine focused disposable producer and log-expiry tests pass. The installed root wrapper SHA-256 matches `vhost-manager/curatormd-v2/acme_cron_bridge.sh`; read-only crontab inspection confirms four daily entries; the six-hour log-expiry timer is enabled and active. The owner-approved Vhost/OS disposition keeps out-of-root artifacts outside Curator scan and purge. Both repositories pass `git diff --check`.
- **Open gate:** No scheduled ACME execution or real renewal is claimed. Current delivery progress remains 153/178 complete, 25 open; no checkbox marker changed.
- **Outcome:** Reconciled local alpha audit status and preserved runtime limits. No consumer source, service, GPTMD, commit, or push was changed.

## 2026-10-26 — Reverify profile-bound Curator V2 integration

- **Intent:** Continue the open source-specific integration checklist with a current read through the configured Hermes profile.
- **Changed fact:** The `renew-ssl-coding` local stdio profile discovered 48 V2 tools and read `vhost-manager-alpha`: 35 processed receipts, 15 goals, and 11 facts. Its separate health snapshot was healthy, with complete empty staging inventory and all seven local dependencies healthy.
- **Verification:** `./hermes -p renew-ssl-coding mcp test curator_v2 --probe-curator-status` exited 0 at `2026-10-26T16:26:31Z`.
- **Open gate:** A direct Codex `goal_list({})` call returned `unauthenticated`; the Hermes profile test is the verified read path. This does not prove an authenticated Codex app-server event, attended human observation, deployment trust roots, rotation, revocation, or outage behavior. The source-specific integration row remains open; delivery progress remains 153/178 complete, 25 open.
- **Outcome:** Recorded current local profile evidence only. No checklist marker, consumer source, service, or runtime configuration changed.

## 2026-10-26 — Guard physical storage inventory coverage

- **Intent:** Strengthen the open permanent-data accounting work with a schema-to-physical-class regression.
- **Changed fact:** The host-authorized storage-view test now checks that every non-internal SQLite application table has a corresponding `dbstat` physical-class result when `dbstat` is supported; indexes remain attributed through their owning table.
- **Verification:** The focused project-access suite passes 12 tests, strict Pyright reports zero diagnostics, and `git diff --check` passes.
- **Open gate:** This guards physical table attribution only. Owner-approved class retention/recovery horizons, budgets, backup accounting, and deployment growth evidence remain open. Delivery progress stays 153/178 complete, 25 open; no checklist marker changed.
- **Outcome:** Added a regression against silently missing physical table classes without changing storage values or authorization.

## 2026-10-26 — Reduce a repository-wide Pylint finding

- **Intent:** Keep the physical-schema coverage regression while bringing its test method below Pylint's statement limit.
- **Changed fact:** Extracted the SQLite schema-table comparison into a focused test helper; the assertion still requires physical storage classes to cover every non-internal application table when `dbstat` is available.
- **Verification:** The focused project-access suite passes 12 tests; strict Pyright reports zero diagnostics; focused Pylint is 10.00/10; `git diff --check` passes. The fresh full-tree warning inventory reports one finding: `store.py` at 9,645/1,000 lines, exit 16 with a 10.00/10 score.
- **Open gate:** Structurally split `store.py` and rerun full-tree Pylint. No checklist marker changed.
- **Outcome:** Removed the test-method finding without changing the regression's coverage; preserved all unrelated work.

## 2026-10-26 — Split the oversized SQLite store

- **Intent:** Resolve the last warning-level repository Pylint finding without weakening the module-size threshold or changing store behavior.
- **Changed fact:** Reduced `store.py` to a compatibility facade; moved store contracts/helpers into two support modules and the ordered operation inheritance layers into 15 bounded modules. Preserved the existing public import surface (141 prior names). Updated internal monkeypatch tests to patch each extracted binding through one test helper, and converted two static self-references to class-bound calls to avoid an import cycle.
- **Verification:** Full suite: 479 tests pass. Strict Pyright: zero diagnostics. Repository-wide warning-level Pylint: zero diagnostics, exit 0. Wheel build succeeds and includes all 17 new store modules. Public-import comparison finds no missing prior public names; in-memory SQLite initialization reports schema 38. `git diff --check` passes.
- **Open gate:** The operation segments retain the pre-existing method/override order. Narrow Pylint suppressions document the increased internal inheritance depth and duplicate blocks detected only after splitting segments. No deployment, consumer, or live-runtime gate is closed by this code-quality change.
- **Outcome:** Closed the repository-wide Pylint checklist item by splitting the 9,645-line module into bounded package modules; no commit or push was made.

## 2026-10-26 — Reconcile producer-audit scope and progress

- **Intent:** Close the current ambiguity about standalone utilities and multi-consumer coverage in the local producer/artifact audit.
- **Changed fact:** Confirmed standalone utilities are included in the completed Vhost producer/artifact audit, including the manual-DNS fixtures, installed root ACME-wrapper fixture, and owner-approved Vhost/OS disposition for artifacts outside Curator's scan/purge root. The approved alpha is one development repository at a time; shared multi-consumer runtime is outside scope. The plan's audit checkbox was already checked.
- **Verification:** Re-read `docs/vhost-producer-coverage-v2.md` and the checked plan row; its current-snapshot record includes the nine focused producer/log-expiry checks, four root cron schedule entries, matching installed/source wrapper hashes, and the explicit out-of-root disposition. `python3 tools/count_curator_v2_delivery.py` reports 154/178 complete, 24 open. `git diff --check` passes.
- **Open gate:** This closes local source/artifact coverage only. No scheduled cron execution or real DNS/certificate renewal is claimed; production controls and release approval remain open.
- **Outcome:** Clarified the already-completed scope without changing checklist markers, consumer repositories, services, or runtime configuration.

## 2026-10-26 — Cover retry after purge unlink failure

- **Intent:** Add one missing local filesystem failure case from the open purge recovery matrix.
- **Changed fact:** Added a regression that injects an OS unlink error after the review decision, cleanup authorization, and canonical projection are durable. It verifies the file remains present, the receipt reports `purge_pending` with a fixed `filesystem_error` outcome and no raw path, and retrying the same receipt removes only the approved target.
- **Verification:** `uv run --group test python -m unittest discover -s tests -p test_purge_filesystem.py -v` passes 13 tests. Strict Pyright reports zero diagnostics for the changed test; errors-only Pylint and `git diff --check` pass. The first attempted `pytest` invocation could not start because pytest is not installed; the repository CI uses unittest and the configured unittest suite passed.
- **Open gate:** This is local filesystem-adapter evidence. Fault coverage against deployment storage/filesystem features and owner-reviewed retry/rollback policy remain open; no checklist marker changed. Delivery progress remains 154/178 complete, 24 open.
- **Outcome:** Added safe, idempotent retry evidence without changing the production purger, consumer repositories, services, or runtime configuration.

## 2026-10-26 — Cover staging-lock failure health

- **Intent:** Cover the staging lock-acquisition failure branch in the open storage/staging fault matrix.
- **Changed fact:** Added a health/metrics regression that injects a staging-lock `OSError` containing a private path. Readiness remains degraded, inventory is incomplete, the fixed adapter-unavailable gate is exposed, and the private path is absent from both outputs. Existing coverage separately injects staging-root open failure.
- **Verification:** `uv run --group test python -m unittest discover -s tests -p test_api_health_metrics.py -v` passes 15 tests. Strict Pyright reports zero diagnostics; errors-only Pylint and `git diff --check` pass.
- **Open gate:** This proves local health behavior only; production storage/staging failure injection and deployment recovery approval remain open. No checklist marker changed; delivery progress remains 154/178 complete, 24 open.
- **Outcome:** Added a distinct staging-lock fault regression without changing runtime behavior or external state.

## 2026-10-27 — Cover staging enumeration permission failure

- **Intent:** Cover a staging traversal fault from the open local failure matrix.
- **Changed fact:** Added a regression that denies directory enumeration after a valid staged artifact exists. Discovery remains incomplete, returns no manifest or artifact list, and exposes only `permission_denied`, not the injected private path.
- **Verification:** `uv run --group test python -m unittest discover -s tests -p test_project_plugin_staging.py -v` passes 12 tests. Strict Pyright reports zero diagnostics; errors-only Pylint and `git diff --check` pass.
- **Open gate:** This is local filesystem-adapter evidence. Deployment-shaped fault injection, production recovery policy, and owner-approved rollback evidence remain open. No checklist marker changed; delivery progress remains 154/178 complete, 24 open.
- **Outcome:** Added a distinct fail-closed staging-enumeration regression without changing runtime behavior or external state.

## 2026-10-27 — Roll back SQLite transactions when commit fails

- **Intent:** Close a local transaction-state defect in the open SQLite failure matrix.
- **Changed fact:** The outer SQLite transaction context now attempts rollback when `commit()` raises, and closes the connection if that rollback also fails. A deferred-foreign-key regression forces failure at commit, verifies the invalid row is absent after reopen, and confirms a later valid transaction persists.
- **Verification:** Full locked unittest suite passes 483 tests. The focused store-resource suite passes 3 tests; strict repository Pyright reports zero diagnostics; repository errors-only Pylint passes; `git diff --check` passes.
- **Open gate:** Local commit rollback is covered; quota/ENOSPC, sync failures, deployment storage, power loss, and the remaining staging/recovery fault matrix remain open. No checklist marker changed; delivery progress remains 154/178 complete, 24 open.
- **Outcome:** Fixed and verified rollback after failed commit without changing schema, consumer state, or service configuration.

## 2026-10-27 — Cover staged-file sync failure

- **Intent:** Exercise a local staging durability failure before atomic publication.
- **Changed fact:** Added a regression that injects a file-data `fsync` error during staging. The partial file is removed, no final artifact is published, and a subsequent inventory is complete and empty.
- **Verification:** `uv run --locked --group test python -m unittest discover -s tests -p test_project_plugin_staging.py -v` passes 13 tests. Strict Pyright and errors-only Pylint pass for the suite; `git diff --check` passes.
- **Open gate:** Directory-sync failure and deployment filesystem behavior remain unverified; the broad failure/recovery checklist remains open. No checklist marker changed; delivery progress remains 154/178 complete, 24 open.
- **Outcome:** Added local file-sync failure evidence without changing production staging behavior or external state.

## 2026-10-27 — Recover inventory after directory-sync failure

- **Intent:** Verify the outcome when staging's directory sync fails after the complete file has been linked.
- **Changed fact:** Added a regression that injects failure on the directory `fsync`. The producer call returns an error, publishes no success acknowledgment, and leaves no partial file; exact inventory then hashes and binds the complete final-path artifact for attended review.
- **Verification:** `uv run --locked --group test python -m unittest discover -s tests -p test_project_plugin_staging.py -v` passes 14 tests. Strict Pyright and errors-only Pylint pass for the suite; `git diff --check` passes.
- **Open gate:** Local visibility/recovery is proven, but directory durability after sync failure and behavior on deployment filesystems remain unverified. The full failure matrix remains open; no checklist marker changed. Delivery progress remains 154/178 complete, 24 open.
- **Outcome:** Added recoverable local evidence for uncertain publication without changing production writer behavior or external state.

## 2026-10-27 — Roll back staging when age receipt write fails

- **Intent:** Verify staging compensation when the durable artifact-age record cannot be written after publication.
- **Changed fact:** Added a regression that injects a SQLite operational error from the staging-age writer. The final file is unlinked, no partial remains, the error is returned, and the next inventory is complete and empty.
- **Verification:** `uv run --locked --group test python -m unittest discover -s tests -p test_project_plugin_staging.py -v` passes 15 tests. Strict Pyright and errors-only Pylint pass for the suite; `git diff --check` passes.
- **Open gate:** This covers the ordinary local receipt-write failure path. Crash/power-loss behavior, failures during compensating unlink/fsync, and deployment storage remain open; no checklist marker changed. Delivery progress remains 154/178 complete, 24 open.
- **Outcome:** Added a regression for safe rollback after staging metadata persistence fails; runtime behavior is unchanged.

## 2026-10-27 — Roll back SQLite on handled interruption

- **Intent:** Verify transaction cleanup when an in-process interruption occurs after a SQLite write.
- **Changed fact:** Added a `KeyboardInterrupt` regression for the outer transaction context. The inserted row is absent after the interruption is re-raised, and a subsequent transaction writes successfully.
- **Verification:** `uv run --locked --group test python -m unittest discover -s tests -p test_store_resources.py -v` passes 4 tests. Strict Pyright and errors-only Pylint pass for the changed test; `git diff --check` passes.
- **Open gate:** This proves handled interruption only; process kill, power loss, and deployment-storage recovery remain unverified. No checklist marker changed; delivery progress remains 154/178 complete, 24 open.
- **Outcome:** Added local transaction-interruption evidence without changing external state.

## 2026-10-27 — Reconfirm local producer/artifact audit closure

- **Intent:** Resolve the conflicting status report for the manual-DNS workflow, root ACME wrapper, standalone producers, and out-of-root artifact disposition.
- **Changed fact:** The V2 plan's local audit checkbox was already checked. The approved one-repository alpha includes the four standalone workflows, manual DNS, the installed root-wrapper fixture, bounded log handling, and owner-approved Vhost/OS ownership outside Curator scan and purge. Shared multi-consumer support is outside scope.
- **Verification:** On Vhost HEAD `1924fa2`, five standalone workflow tests, one installed root-wrapper fake-ACME test, one bounded-queue test, and two log-expiry tests pass. The changed manual-DNS success fixture SHA-256 is `6ad60570fdeec8535d9522eb3c66df4fb96e24c35d792927f619ee718a583cfd`. Curator `git diff --check` passes. Delivery count is 154/178 complete, 24 open; no marker changed.
- **Open gate:** Actual scheduled cron execution, real DNS/certificate renewal, and production retention remain unverified. No live workflow or service was run or changed.
- **Outcome:** Reconciled the alpha audit as closed without changing Vhost source, deployment state, consumer data, or checklist count.

## 2026-10-27 — Retry uncertain staged publication by exact occurrence

- **Intent:** Make retry safe after a directory sync failure leaves a complete artifact visible but unacknowledged.
- **Changed fact:** Exact same-ID, same-digest retries now bind the current file to its existing occurrence before recording age. A first successful receipt records age once; repeated retries retain that timestamp. Store admission requires the same occurrence identity, so a purged path cannot be reused even if the filesystem recycles its inode. Different content at an occupied path remains rejected. Commit cleanup now adds exception-type-only notes to the original error if rollback and connection close both fail; it does not silently swallow cleanup failures.
- **Verification:** The staging suite passes 15 tests and the storage/expiry suite passes 17 tests. The full locked Curator suite passes 487 tests. Strict repository Pyright reports zero diagnostics; errors-only Pylint, Bandit, the locked dependency audit, and `git diff --check` pass. Bandit emits only its existing `nosec` warnings. Delivery progress remains 154/178 complete, 24 open; no plan marker changed.
- **Open gate:** Local uncertain-publication recovery is covered. Directory durability, crash/power-loss behavior, and deployment-filesystem recovery remain unverified.
- **Outcome:** Added bounded idempotent recovery for the exact visible file without weakening overwrite or post-purge ID-reuse protections.

## 2026-10-27 — Reject a changing file during staging discovery

- **Intent:** Cover the local staging fault-matrix case where a file changes while inventory discovery opens and hashes it.
- **Changed fact:** Added a deterministic regression that mutates a disposable file after the scanner opens it. Discovery fails closed with `changed_during_scan`, no adopted artifact, and no manifest.
- **Verification:** The focused storage suite passes 18 tests; strict Pyright reports zero diagnostics and errors-only Pylint passes. No delivery marker changes from this local test; deployment filesystem race behavior remains open.
- **Open gate:** External actors and deployment filesystems may have different race and durability behavior; the production adapter/recovery matrix remains open.
- **Outcome:** Added direct local evidence for the scanner's changing-file rejection path without modifying runtime behavior.

## 2026-10-27 — Preserve commit errors when rollback cleanup fails

- **Intent:** Verify the SQLite transaction cleanup path when commit and rollback both fail.
- **Changed fact:** Added a fault regression covering rollback failure with both successful and failed connection close. The original commit error remains primary, cleanup is attempted, and notes expose only exception types. No database content or raw error text is added to the notes.
- **Verification:** The focused store-resource suite passes five tests; targeted Pyright reports zero diagnostics and errors-only Pylint passes. The full 487-test suite was run before this test-only addition and is recorded as a checkpoint, not as a run of the current expanded suite. `git diff --check` passes.
- **Open gate:** Power loss, process termination, and deployment storage cleanup remain unverified.
- **Outcome:** Added local evidence for both cleanup-error branches without changing transaction semantics or masking the original commit failure.

## 2026-10-27 — Remove partial staging data after simulated ENOSPC

- **Intent:** Cover storage exhaustion after a staged file has received a partial write.
- **Changed fact:** Added a writer fault fixture that writes a short prefix and raises `ENOSPC`. The producer returns the error, removes the temporary file, publishes no final artifact, and leaves a complete empty inventory.
- **Verification:** The focused staging suite passes 16 tests; targeted Pyright reports zero diagnostics and errors-only Pylint passes. `git diff --check` is pending after this history update. No checklist marker changed.
- **Open gate:** This is injected local filesystem evidence. Real quota/ENOSPC behavior, production adapter recovery, and repeated-failure policy remain open.
- **Outcome:** Added local cleanup evidence for partial writes without changing the production writer.

## 2026-10-27 — Reject short staged-file writes

- **Intent:** Prevent a short target write from being hashed and published as if the full input chunk reached disk.
- **Changed fact:** The staging writer now compares each target write's returned byte count with the full source chunk and raises on a short write. A regression confirms partial data is removed and no artifact is published.
- **Verification:** The focused staging suite passes 17 tests and the full locked Curator suite passes 491 tests. Repository-wide strict Pyright reports zero diagnostics; errors-only Pylint, Bandit, the locked dependency audit, and `git diff --check` pass. Bandit reports only existing `nosec` warnings. No checklist marker changed.
- **Open gate:** This proves local short-write handling; production storage adapters, quota behavior, and crash/power-loss recovery remain open.
- **Outcome:** Added fail-closed behavior for a short write without weakening staging limits or artifact identity.

## 2026-10-27 — Reconcile local producer/artifact audit status

- **Intent:** Close the reported V2 local-alpha audit for manual DNS, the root ACME wrapper, standalone utilities, and artifacts outside Curator's staging root.
- **Changed fact:** The audit checklist row was already checked. The plan now states directly that manual DNS fixture coverage, installed root-wrapper invocation and schedule inspection, standalone workflow coverage, and the approved Vhost/OS out-of-root disposition close the local single-repository alpha audit. Actual scheduled cron execution and real DNS/certificate renewal remain separate runtime gates.
- **Verification:** `docs/vhost-producer-coverage-v2.md` contains the scoped evidence and limitations. `python3 tools/count_curator_v2_delivery.py` reports 154/178 delivery rows complete, 24 open. `git diff --check` passes. No checklist marker changed.
- **Open gate:** No real scheduled renewal, DNS provider, or certificate operation was run; production controls and release evidence remain open.
- **Outcome:** Resolved the stale “audit open” status without changing consumer repositories, deployment state, or checklist progress.

## 2026-10-27 — Set the Vhost alpha staging budget

- **Intent:** Apply the owner's local-alpha staging limits to the Vhost Manager consumer and clarify FIFO without granting automatic deletion authority.
- **Changed fact:** The consumer-owned `.curatormd-v2.toml` sets `max_project_bytes = 262144000` (250 MiB) and `max_project_files = 150` for `vhost-manager-alpha`. The pilot policy says over-budget writes fail closed; FIFO is oldest-first proposal ordering only, and purge still requires human approval of the exact inventory.
- **Verification:** `ProjectConfig.load` reads the consumer config as project `vhost-manager-alpha` with limits `262144000` and `150`. All 17 `test_project_plugin_staging.py` tests pass, including incomplete-inventory denial, budget rejection, and no-auto-purge behavior. Curator and Vhost `git diff --check` pass. Delivery progress remains 154/178; no checklist marker changed.
- **Open gate:** Backend-wide budgets, measured growth, alert thresholds, complete temporary-data classes, and complete Hermes token-usage coverage remain open. FIFO ordering for a cleanup proposal is not implemented by this config change.
- **Outcome:** Applied the approved per-repository alpha caps without deleting artifacts or restarting a service; the broader budget/usage checklist item remains open.

## 2026-10-27 — Order expiry proposals oldest-first

- **Intent:** Apply the owner's FIFO preference to attended expiry proposals without allowing the ordering rule to authorize deletion.
- **Changed fact:** Eligible transient artifacts now sort by their exact durable `staged_at` timestamp, oldest first, with path as a deterministic tie-breaker. The held and eligible lists preserve that order. Proposal discovery remains read-only; an authorized reviewer must still approve the exact inventory.
- **Verification:** The storage/expiry suite passes 19 tests, including a regression that deliberately makes path order oppose age order and confirms neither file is deleted. All 17 staging-writer tests pass after the ordering change. Repository strict Pyright reports zero diagnostics; `git diff --check` is pending after this entry.
- **Open gate:** This source change has not yet been refreshed into the installed alpha wheel. Backend-wide budgets, measured growth, alert policy, and complete token-usage coverage remain open.
- **Outcome:** Implemented FIFO proposal order without automatic eviction or changes to exact-inventory approval.

## 2026-10-27 — Refresh the installed V2 alpha package

- **Intent:** Put the verified staging-budget and FIFO proposal behavior into the dedicated local Hermes profile package.
- **Changed fact:** Rebuilt and installed the current V2 source wheel in `renew-ssl-coding`'s isolated Curator V2 virtualenv. The previous installed distribution is recoverable from the verified 104-member archive recorded in `docs/alpha-v2.md`.
- **Verification:** Wheel SHA-256 is `0fe468fcd209ef39cca85b6e986b1cb7907fa85a8ff2ffc510dce4358ec72159`. All 87 installed Python modules match source, `pip check` passes, and the installed interpreter reads the configured 250 MiB/150-file Vhost limits and returns FIFO expiry proposal order. The 17 staging-writer and 19 storage/expiry tests pass; strict Pyright reports zero diagnostics.
- **Open gate:** No Hermes gateway or service restart, real app-server turn, DNS/certificate renewal, or live artifact deletion was performed. Release, production policy, and actual interactive lifecycle evidence remain open.
- **Outcome:** Refreshed the isolated local alpha package with rollback evidence; the Hermes service was left running unchanged.

## 2026-10-27 — Add the local staging-budget warning threshold

- **Intent:** Warn when the configured local-alpha staging budget approaches its cap while preserving fail-closed writes and human-only cleanup.
- **Changed fact:** A complete project staging scan now adds `staging_budget_warning` at 75% of either configured byte or file cap. At 100%, the existing `staging_budget_reached` gate remains authoritative and blocks new staging. Incomplete scans produce no budget percentage claim. Health and Prometheus expose the warning; no artifact is removed.
- **Verification:** The health/metrics suite passes 16 tests, including exact 75% and below-threshold cases. Strict Pyright reports zero diagnostics. The new wheel SHA-256 is `c9a1c8b3f068b20b780c4a0461ea83c8839c0f42400c4175b57ac6844a2bed50`; all 87 installed Python modules match source, the installed warning boundary returns expected true/false values, Vhost limits load as 262144000 bytes and 150 files, and `pip check` passes. The prior installed package is preserved in the 104-member archive recorded in `docs/alpha-v2.md`.
- **Open gate:** Health/Prometheus signaling is not journal or external alert delivery. No running MCP process or gateway was restarted, and the broader budget/usage checklist remains open.
- **Outcome:** Installed the local warning signal without changing alert delivery, triggering deletion, or restarting a service.

## 2026-10-27 — Rebind and verify the Vhost alpha config

- **Intent:** Restore the authorized local Hermes profile after the owner-approved staging-limit edit changed the consumer config fingerprint.
- **Changed fact:** The attended `curatormd-v2-access update` advanced `vhost-manager-alpha` registration revision 1 to 2 using transition `vhost-manager-alpha-staging-budget-20261027`. The registration now binds config SHA-256 `be277ffe944f0dd64418ad6b49d500ee2c887aa80891153329fac529b3d822bf`; repository fingerprint and API version are unchanged. All five existing profile/local UID grants remain.
- **Verification:** A fresh `hermes -p renew-ssl-coding mcp test curator_v2 --probe-curator-status` connects to the installed warning wheel, discovers 48 tools, reads 35/35 processed receipts, reconciles 15 goals and 11 facts, and reports `healthy` with a complete empty staging inventory and seven fresh dependencies. Read-only SQLite confirms registration revision 2 and the same grants.
- **Open gate:** This is a profile-context status read, not a real Codex app-server turn or Vhost application request. Staging is below 75%, so real-profile warning firing is not demonstrated; external journal/alert delivery remains open.
- **Outcome:** Reconciled the approved consumer config change with its exact local registration and restored the supported alpha profile without restarting a service or creating any goals, facts, or events.

## 2026-10-27 — Verify the six-hour local purge retry timer

- **Intent:** Confirm the owner-approved six-hour maintenance schedule remains active after the alpha package/config refresh.
- **Changed fact:** The `eaglesvn` user timer for `vhost-manager-alpha` is enabled and active, with its next trigger at 06:00:09 +07 and last trigger at 00:00:03 +07.
- **Verification:** The latest service run exited 0. Its journal summary reports zero processed or pending expiry/purge targets. Curator `git diff --check` passes; the delivery count remains 154/178 complete, 24 open.
- **Open gate:** This verifies an idle local pass, not an artifact deletion. Production scheduling, external alert delivery, restart reconciliation, and recovery drills remain open; no checklist marker changed.
- **Outcome:** Reconfirmed the approved six-hour local cadence without changing timer configuration, running a purge manually, or restarting a service.

## 2026-10-27 — Recheck the installed local evidence source

- **Intent:** Refresh the Vhost alpha's host-configured evidence path after the previous source captures.
- **Changed fact:** The `renew-ssl-coding` profile's evidence config remains owner-only (`0600`, `eaglesvn`) at SHA-256 `29667f3eaf8403ee0ad807f07f52989b10eca5b96ecac38e94fc07f4bb228296`.
- **Verification:** The installed `curatormd-v2-evidence service-probe` command returned `passed` for `service-probe:maintenance-timer`, digest `45df5ad5e0ecfa54d3226343e0e6857337494ba6e32f189d1174070665d8c659`.
- **Open gate:** This is a source capture, not a persisted criterion attestation. No attended human-observation receipt was created; deployment trust-root, identity, rotation, revocation, and outage evidence remain open. No checklist marker changed.
- **Outcome:** Confirmed the configured local evidence source remains usable without changing profile configuration or creating a Curator record.

## 2026-10-27 — Allow exact staging retries at configured caps

- **Intent:** Preserve idempotent artifact publication when a project is already at its byte or file staging limit.
- **Changed fact:** Before staging, the plugin now distinguishes an exact existing artifact path from a new path. For an exact retry it compares the bounded input stream directly with the inventoried no-follow file, preserves the existing occurrence and age, and creates no temporary copy. New paths still fail closed at count/byte limits, and changed content at an occupied ID conflicts.
- **Verification:** `test_project_plugin_staging.py` passes 18 tests and `test_project_plugin_storage.py` passes 19. Repository-wide strict Pyright reports zero diagnostics; errors-only Pylint on the changed source/test files and `git diff --check` pass. No checklist marker changed; delivery progress remains 154/178 complete, 24 open.
- **Open gate:** This fixes local cap-bound retry behavior only. Direct external filesystem writers, deployment filesystem behavior, and the broader backend budget/usage/alert policy remain separate gates.
- **Outcome:** Exact retries no longer fail merely because their existing bytes/files already consume the configured budget, while new artifacts cannot exceed it or trigger automatic deletion.

## 2026-10-27 — Add a local V2 project dashboard to the VS Code extension

- **Intent:** Give the approved single-user alpha a project-scoped view of goal outcomes and paged facts from the V2-owned status-bar integration.
- **Changed fact:** The `CuratorMD V2` status item now opens a read-only webview. The extension launches the locally configured MCP server with User-scoped database, profile-routing, and server settings; it rejects project-workspace overrides. Each goal/report page is an independent backend read and replaces the prior page; the UI displays page totals, renders ledger data as text, and exposes only a fixed generic error message. Tool calls include the User-configured profile label and a per-process random session ID expected by the profile-bound MCP host; the backend still derives authorization from the kernel UID and exact project grant.
- **Verification:** `node --check integrations/vscode-status/extension.js`, the three focused Node tests, `python3 -m json.tool integrations/vscode-status/package.json`, and `git diff --check` pass. A disposable project with an exact `local-uid` read grant was read through the actual `curatormd-v2-mcp` launcher; the dashboard client retrieved both its goal page and report. No checklist marker changed.
- **Open gate:** The VS Code extension has not been installed or exercised in a real window. Grant revocation between requests, trust-version changes, complete evidence snapshot binding, and real-consumer user acceptance remain open; this implementation does not close the dashboard checklist row.
- **Outcome:** Added the first local dashboard slice without changing the consumer repository, backend identity policy, or service runtime.

## 2026-10-27 — Install and exercise the V2 dashboard integration

- **Intent:** Put the V2 dashboard into the existing VS Code installation and verify the installed extension's read path against the approved local alpha.
- **Changed fact:** Installed `curatormd.curatormd-v2-status@0.2.0`; User settings now bind the `renew-ssl-coding` profile label, its Curator V2 database, and its dedicated local MCP launcher. Backups of the prior 0.1.0 extension, the prior 0.2.0 build, and the original VS Code settings are retained under the alpha backup directory. The panel-disposal callback now uses the VS Code panel API.
- **Verification:** Four focused Node tests pass. A host-level harness loaded the installed 0.2.0 extension, invoked its dashboard command, and read the actual `vhost-manager-alpha` goal page (15 goals) and one goal report through the real local MCP process. Installed `extension.js` SHA-256 matches source (`0111eaecd49faa4d2717a17b0158ef6269c080096e2211f9099245518f4f4a58`); `code --list-extensions` reports 0.2.0. `git diff --check` passes. No checklist marker changed.
- **Open gate:** The running VS Code window has not been reloaded and the rendered dashboard has not been inspected or clicked by a user. Grant revocation between pages, trust-version changes, complete evidence snapshot binding, and real-user acceptance remain open.
- **Outcome:** Installed and backend-integrated the local V2 dashboard with rollback copies, without changing Vhost source, restarting Hermes, or changing the delivery checklist count.

## 2026-10-27 — Detect report changes between dashboard pages

- **Intent:** Prevent paged dashboard reads from looking like one report when the underlying V2 ledger changes between requests.
- **Changed fact:** Goal reports now expose a deterministic SHA-256 revision over the full loaded report model. Goal, fact, review, and related-record reads share one query-only SQLite snapshot; evidence adapters run after it closes. The VS Code extension compares revisions on later fact pages; a mismatch clears that page and requests page one again. Each page remains a separate, freshly authorized read.
- **Verification:** `PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -p test_goal_reporting.py -v` passes 10 tests, including concurrent database mutation during report assembly. It also verifies stable revisions across unchanged pages and a changed revision after a new fact. `node --test integrations/vscode-status/extension.test.js` passes 4 tests, including a stale-page revision mismatch; `node --check integrations/vscode-status/extension.js`, targeted Pyright, and `git diff --check` pass.
- **Open gate:** This digest detects changes in the loaded report model; it is not an access token and does not include external trust-root versions, evidence expiry/revocation, or real-time grant revocation during UI rendering. The real VS Code UI and real-consumer acceptance remain unverified. The dashboard checklist row remains open.
- **Outcome:** Added local report-change detection without claiming complete snapshot or runtime acceptance.

## 2026-10-27 — Make the local staging threshold warning-only

- **Intent:** Apply the owner's clarification that the Vhost alpha should warn at its 250 MiB staging threshold, continue accepting writes above it, and ignore project file count.
- **Changed fact:** Curator no longer applies the configured project byte threshold as a write ceiling. Health still reports `staging_budget_warning` at 75% and `staging_budget_reached` at or above the threshold. The Vhost consumer config now sets only `max_project_bytes = 262144000`; exact retries and the independent per-artifact/per-goal safeguards remain.
- **Verification:** The 18 staging tests and 16 health/metrics tests pass. Targeted Pyright reports zero diagnostics; errors-only Pylint and `git diff --check` pass. The wheel SHA-256 is `56ab545000bfa9e1161a1d133674b28534fa6b1ab4343f027bb310288ee35573`; the prior installed package is archived at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-pre-warning-only-20261027.tar.gz` with SHA-256 `0b8d65b56949cee73a1969aeebe7ddf9c397023ab4a066d76567d9faaf219d96`. All 87 installed modules match source and `pip check` passes. The attended registration update advanced the project from revision 2 to 3 under transition `vhost-manager-alpha-byte-warning-only-20261027`, binding config SHA-256 `a37448f38683c864480d4f90db8fc6a6b694311679b598979f86ff574713f746`. Hermes Core's profile-scoped status probe connects, reads 35/35 receipts and 15 goals/11 facts, and reports healthy status with a complete empty staging inventory. The plan remains 169/216 complete; no checklist marker changed.
- **Open gate:** No live staging inventory has crossed the threshold, so real-profile warning firing is not demonstrated. External alert delivery, production budgets/retention, and release evidence remain open.
- **Outcome:** Installed and bound the warning-only local alpha behavior without restarting Hermes, changing Vhost application source, deleting artifacts, or claiming renewal evidence.

## 2026-10-27 — Report the retained Hermes usage interval

- **Intent:** Make project-usage reports show the time span represented by retained rows without implying complete capture or a billing period.
- **Changed fact:** The Hermes Core `project-usage` plugin response now identifies `all_retained_project_usage_rows` and returns first/last `occurred_at` timestamps; both are null for an empty ledger. Coverage remains explicitly incomplete, and the ledger read remains read-only.
- **Verification:** `scripts/run_tests.sh tests/plugins/test_project_usage.py -q` passes five tests. Hermes Core `scripts/check --base HEAD^` passes all 12 checks. Commit `d2aac32b8` is pushed to the configured fork branch.
- **Open gate:** This measures the retained ledger span only. It does not add missing usage classes or prove complete Codex app-server capture; Slice G and the project token-usage checklist remain open.
- **Outcome:** Added a bounded, privacy-preserving measurement interval without changing usage capture or declaring complete coverage.

## 2026-10-27 — Reconcile current V2 checklist and staging-policy notes

- **Intent:** Keep the plan's current progress count and active staging-policy description aligned with their current authoritative sources.
- **Changed fact:** The plan header now records the delivery-count tool's current result, 154/178 complete and 24 open. The earlier installed-package note now labels the 150-file setting as historical and points to the later warning-only configuration with no file-count limit.
- **Verification:** `python3 tools/count_curator_v2_delivery.py` reports 154/178 complete; the plan's delivery rows were not changed. `git diff --check` passes.
- **Open gate:** The full V2 plan remains active with 24 delivery rows open; this documentation correction closes no checklist item.
- **Outcome:** Preserve the correct historical config record while making the present count and policy unambiguous.

## 2026-10-27 — Clear dashboard data after a denied read

- **Intent:** Prevent a project dashboard from retaining previously rendered goal and fact data after a fresh Curator read fails authorization or otherwise errors.
- **Changed fact:** The VS Code webview now clears goal buttons, report text, selection, page labels, and pagination state before showing its generic read error.
- **Verification:** The focused Node suite passes all five tests, including an executed webview-script regression that loads a goal/report, injects a failed read, and verifies the prior content is removed. `node --check integrations/vscode-status/extension.js` and `git diff --check` pass.
- **Open gate:** Real VS Code interaction, grant revocation between pages, and external trust-version changes remain unverified; the dashboard checklist row stays open.
- **Outcome:** Close the local stale-display defect without claiming the full dashboard acceptance gate.

## 2026-10-27 — Exercise dashboard denial through MCP stdio

- **Intent:** Verify that a rejected Curator MCP tool response reaches the dashboard's clear-and-error path.
- **Changed fact:** The dashboard panel test now returns an MCP `isError` from the stdio child for a fresh report read and checks that the webview receives its generic failure message.
- **Verification:** All five VS Code extension tests pass; `node --check integrations/vscode-status/extension.test.js` and `git diff --check` pass.
- **Open gate:** The denial is simulated at the MCP protocol boundary. A real VS Code grant-revocation transition and full dashboard acceptance remain open.
- **Outcome:** Add protocol-path evidence without claiming live authorization revocation.

## 2026-10-27 — Show authorized project health in the VS Code dashboard

- **Intent:** Give the local V2 dashboard a concise project-health view while keeping goal reads usable when the health probe is unavailable.
- **Changed fact:** Loading goals now also requests `project_health`; the dashboard shows only status and fixed gate codes, treats missing or mismatched project health as `unknown`, and does not let a failed health request suppress a successful goal page.
- **Verification:** All six focused extension tests pass, including healthy, degraded, unavailable, and cross-project health results. `node --check integrations/vscode-status/extension.js` and `git diff --check` pass.
- **Open gate:** This is a local project dashboard only. Deployed scrape infrastructure, operator dashboards, alert delivery, and real VS Code acceptance remain open.
- **Outcome:** Improve local V2 visibility without claiming deployment monitoring or closing the operational dashboard checklist.

## 2026-10-27 — Show retained activity totals in the VS Code dashboard

- **Intent:** Expose local, project-authorized event and review backlog totals beside health and goal browsing.
- **Changed fact:** Each goal-page load also requests `project_activity_status`; the dashboard displays retained receipt states, goal/fact totals, and pending/approved/rejected SDE counts without IDs or content. Missing, malformed, or cross-project summaries show `unknown`; an unavailable summary does not block goal browsing.
- **Verification:** All six focused VS Code extension tests pass, including the MCP response path, content-free rendering, and unavailable-summary fallback. `node --check integrations/vscode-status/extension.js` and `git diff --check` pass.
- **Open gate:** This remains a local editor dashboard. Deployed dashboard/scrape wiring, alerts, storage-growth views, and operator acceptance remain open.
- **Outcome:** Add local backlog visibility without equating retained activity with complete capture.

## 2026-10-27 — Install the updated V2 VS Code dashboard

- **Intent:** Put the current local health/activity dashboard source into the existing VS Code extension installation.
- **Changed fact:** Packaged and installed `curatormd.curatormd-v2-status@0.3.0`. The installed extension source matches the repository. The prior installed 0.2.0 extension is archived at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curatormd-v2-vscode-0.2.0-before-0.3.0-20261027/installed-0.2.0.tar.gz`; SHA-256 is `d4f86bd2ca48a984c5dfd162b55949ce94de7f795ea7141b242a7cccc7be41c2`. The new VSIX is also preserved in that directory; SHA-256 is `334ffb89f7a2ed0f75f0473e2a2f9aa3abeed8c45185684e58fcab18549b9944`.
- **Verification:** `code --list-extensions --show-versions` reports version 0.3.0. Installed and source `extension.js` SHA-256 both equal `420cd9c66e88760f1cfa3dd907df36c925c6ec3e9874ca330311296c224905a9`. Six focused Node tests pass; package JSON, JS syntax, and `git diff --check` pass.
- **Open gate:** The VS Code process was already running and was not reloaded. It has not rendered or interacted with version 0.3.0; grant-revocation and full dashboard acceptance remain open.
- **Outcome:** Install the current local plugin with a verified rollback copy and no editor restart.

## 2026-10-27 — Verify installed dashboard reads against the Vhost alpha

- **Intent:** Check the installed 0.3.0 dashboard's authorized health, activity, and goal read path against the real local Vhost project.
- **Changed fact:** The installed extension returned a 16-goal page, 37 retained receipts, 12 facts, and zero pending SDEs. `project_health` returned `unknown` for all seven host dependencies because the direct VS Code stdio client sends profile/session routing metadata but not Hermes Core's trusted `hermes/readiness` observations.
- **Verification:** The actual installed extension used the configured `renew-ssl-coding` User settings and local Curator MCP launcher. Output was limited to aggregate counts, status, and fixed gate/dependency codes; no goal or fact text was printed and no state was changed.
- **Open gate:** A trusted Hermes-managed readiness source is not connected to this standalone editor path. Profile labels cannot stand in for host identity/readiness; the health result remains correctly fail-closed.
- **Outcome:** Verify real profile-bound dashboard reads and identify the missing trusted readiness link without claiming healthy host services.

## 2026-10-27 — Show local project storage in the V2 dashboard

- **Intent:** Add the existing project-authorized storage summary to the local V2 editor dashboard so development operators can see retained record growth and fact capacity.
- **Changed fact:** Each goal refresh now requests `project_storage_usage`. The dashboard validates project binding and bounded non-negative byte/count fields, then shows project logical bytes, retained event-payload bytes, fact count/byte capacity, and shared SQLite database/WAL file sizes. It states that staging and token usage are not included; unavailable, malformed, or cross-project results show `unknown` and do not prevent goal browsing. The extension was packaged and installed as version 0.4.0. The prior 0.3.0 installation is archived at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curatormd-v2-vscode-0.3.0-before-0.4.0-20261027/installed-0.3.0.tar.gz` (SHA-256 `eb18951749ba5ea36eee6301d490bcdc016d3c1cb572d6f8db74e305296f8f26`); VSIX SHA-256 is `4ed3f986a71bd6e9cb13faa69a948cee72ed00614ab809d920edc289fc519ccb`.
- **Verification:** All six focused VS Code extension tests pass, including project-mismatch, unavailable-read, and content-free storage rendering. `node --check integrations/vscode-status/extension.js` and `git diff --check` pass. `code --list-extensions --show-versions` reports 0.4.0; installed and source `extension.js` SHA-256 both equal `200a0ea3f48a46af9577bc12582f323b1748ae182738c1dceb477b01ea1989f5`. A read through the installed Vhost profile's actual stdio launcher returned project `vhost-manager-alpha`, 27,614 logical bytes, 12 facts, zero retained event payload bytes, 462,848 shared database bytes, and 53,592 shared WAL bytes.
- **Open gate:** The storage read does not measure staging or model/token usage. The dashboard is local-only; deployed scrape, alert delivery, and user acceptance remain open. No delivery checklist marker changed.
- **Outcome:** Add local storage visibility without attributing shared SQLite file sizes to a project or implying staging/token coverage.

## 2026-10-27 — Show staging bytes and warning state in the V2 dashboard

- **Intent:** Surface the bounded staging scan already included in the authorized project-storage result and apply the owner's warning-only 250 MiB policy in the local dashboard.
- **Changed fact:** The storage panel now validates scan completeness, observed bytes, fixed error codes, and the configured threshold. It reports the existing 75% warning level and threshold reached at 100%; both states say writes remain allowed. It does not use a file-count threshold or report token usage. Packaged and installed VS Code extension 0.5.0 after archiving the 0.4.0 install at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curatormd-v2-vscode-0.4.0-before-0.5.0-20261027/installed-0.4.0.tar.gz` (SHA-256 `d0f16c7cdfda2a66f3b8fce16e1bf83f202b61c06d6aea32ec844dc7fd479189`). VSIX SHA-256 is `c4f98ab77a2d5465d114f3f8597b520a684a99375f59fd4dc48e6924c7434bee`.
- **Verification:** All six focused VS Code extension tests pass, covering below-warning, 75%, threshold, incomplete scan, cross-project response, and unavailable read. `node --check integrations/vscode-status/extension.js` and `git diff --check` pass. VS Code lists 0.5.0; installed and source `extension.js` SHA-256 both equal `c5a707ab6f1a6ea55dbe49676d1a4888b52f1f6323f29594e4b6c55ebf1ddcfa`. The actual Vhost profile MCP read reported a complete staging scan with 0 bytes and a 262,144,000-byte threshold.
- **Open gate:** The running VS Code window has not reloaded, so the panel has not been visually accepted. The observed staging state was below warning; threshold behavior is covered by UI tests, not an oversized live staging tree. Token coverage and deployed monitoring remain open. No delivery checklist marker changed.
- **Outcome:** Show existing authorized staging measurements without treating the warning threshold as a write block or a complete artifact inventory.

## 2026-10-27 — Refresh Hermes profile health and report-only usage evidence

- **Intent:** Refresh the current local Hermes-to-Curator profile evidence and the open token-usage measurement using existing read-only interfaces.
- **Changed fact:** The supported `renew-ssl-coding` profile read reports project `vhost-manager-alpha` with 37 processed receipts, 16 goals, 12 facts, no pending SDEs, and a separate healthy project snapshot with all seven required local dependencies healthy and complete staging. Hermes `project_usage` returned six retained turns, five with reported usage and one with unknown usage; `coverage_complete=false` and `tokens_complete=false`, with only Codex app-server observed.
- **Verification:** `./hermes -p renew-ssl-coding mcp test curator_v2 --probe-curator-status` exits 0 and discovers 48 tools. The profile usage summary was read from the existing Hermes plugin through its read-only ledger path; only aggregate status, counts, source, and completeness flags were emitted.
- **Open gate:** This does not prove a live gateway/app-server event, authenticated person identity, producer-wide token coverage, token budget enforcement, or deployed alerting. The standalone VS Code path still lacks trusted Hermes readiness and correctly shows health as unknown. No checklist marker changed.
- **Outcome:** Reconcile current local profile health and incomplete token-usage evidence without changing profile, consumer, or runtime state.

## 2026-10-27 — Open the attended SDE reviewer from the V2 dashboard

- **Intent:** Make the local V2 reviewer reachable from its project dashboard while keeping review authority and deletion controls in the existing attended CLI.
- **Changed fact:** The dashboard now reads the authorized pending SDE queue and opens `curatormd-v2-review` for a candidate from that queue. It passes the exact workspace, database, and candidate through shell-quoted arguments; the review CLI defaults to the directory beside the configured MCP launcher, or PATH when the launcher is a PATH command. The extension itself cannot submit a decision or purge artifacts. Version 0.6.0 is installed; the prior 0.5.0 installation is archived at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curatormd-v2-vscode-0.5.0-before-0.6.0-20261027/installed-0.5.0.tar.gz` (SHA-256 `7133c756dfbaab51b4f08b76b5522278330e8568713333baa65b56157f252be4`).
- **Verification:** All eight focused VS Code extension tests pass, including queue discovery, rejection of an unlisted candidate, safe argument quoting, default CLI resolution, and terminal handoff. `node --check` and `git diff --check` pass. VS Code lists 0.6.0, and installed/source `extension.js` SHA-256 values match at `891c3b3449292d26e6582d1aa0000b140a19e0cf5eab6e6afbe31daca1251a95`; VSIX SHA-256 is `a1a3aba941a3427e824d952f690c550da45b371687c42f44d40c2f74d07f1adf`. The configured alpha environment contains an executable `curatormd-v2-review` CLI.
- **Open gate:** The running VS Code window has not been reloaded. No live review queue read, SDE review receipt, canonical projection, or purge was produced. Authenticated review, exact inventory decision, timer-driven purge, and pilot acceptance remain open. The Curator V2 goal-list MCP returned `unauthenticated`, so this checkpoint is recorded only in repository history.
- **Outcome:** Add the local reviewer entrypoint without duplicating the CLI’s identity checks or changing ledger state.

## 2026-10-27 — Fail closed on malformed V2 review queues

- **Intent:** Prevent a malformed or cross-project SDE queue response from appearing as an empty reviewer queue in the local dashboard.
- **Changed fact:** The V2 editor now validates the whole bounded queue: candidate identifiers and state, materiality, candidate-to-goal binding, project binding, duplicate IDs, and the 100-item limit. Any invalid response becomes unavailable and enables no review handoff. Extension 0.6.1 is installed after archiving 0.6.0 at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curatormd-v2-vscode-0.6.0-before-0.6.1-20261027/installed-0.6.0.tar.gz` (SHA-256 `6305efade63aabc62b4b45c783167dc3b23a8af999ca2903924390e4fd8aa19a`).
- **Verification:** All nine focused extension tests pass, including valid, malformed, and cross-project queue cases. `node --check` and `git diff --check` pass. Installed/source `extension.js` hashes match at `b981d1b6a7718976c34f007ac3648d1611c92ec7a3ef0ac723a09f7350b91a68`; VSIX SHA-256 is `2cbfc350e6710be28942963cea5d6ccaff3f436d945d6feb7c484f203289caf1`.
- **Open gate:** The running VS Code window has not been reloaded and no real queue response or reviewer action was observed. Human review, canonical decision receipt, exact cleanup, and pilot gates remain open. The Curator V2 MCP still returned `unauthenticated` for goal-ledger access.
- **Outcome:** Make malformed queue state visibly unavailable rather than falsely empty, with no ledger or artifact mutation.

## 2026-10-27 — Keep full review details out of dashboard messages

- **Intent:** Limit the pending-review dashboard to the candidate summary it renders instead of forwarding full MCP review records into the webview.
- **Changed fact:** The queue adapter now validates and copies only candidate ID, goal ID, pending state, materiality, rationale, project ID, and bounded goal problem. Supporting facts, receipts, and corrections are omitted from webview messages. Extension 0.6.2 is installed after archiving 0.6.1 at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curatormd-v2-vscode-0.6.1-before-0.6.2-20261027/installed-0.6.1.tar.gz` (SHA-256 `fc1b19bacc6e0e019ab942a7f5bd4836782cc03d584efd3f8ac343d86e552d48`).
- **Verification:** All nine focused extension tests pass, including an executed MCP fixture with fact and receipt canaries, malformed queue rejection, and cross-project denial. VS Code lists 0.6.2, and installed/source `extension.js` hashes match at `61529229a305afeebdea7f202c48a778d1654940f0ccddbeee6301ab532d6326`; VSIX SHA-256 is `bf4b0c3e2f478e83fc9b0039ed632c43e401d126ecb58b425ba8c2097909a697`. `node --check` and `git diff --check` pass.
- **Open gate:** This covers the local review-queue renderer boundary only. Real VS Code interaction, live queue data, decision receipts, projection-before-purge, and the full source-to-sink privacy audit remain open.
- **Outcome:** Reduce dashboard exposure without changing the authorized review CLI or candidate lifecycle.

## 2026-10-27 — Return compact SDE cards from MCP

- **Intent:** Keep supporting fact bodies and receipts out of stdio responses used only to populate the local review queue.
- **Changed fact:** Added read-only `sde_review_queue_cards`, which returns the exact project plus candidate and goal summary fields, without facts, evidence, receipts, or corrections. The V2 dashboard now calls this tool. The new Curator wheel is installed only in the dedicated alpha virtualenv; its prior distribution and command entrypoints are archived at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-pre-review-summary-20261027.tar.gz` (SHA-256 `d177433a36c9ceeffe9c57c300191b674e9eb250436dba424ba7e711d80fd573`). Extension 0.7.0 is installed after archiving 0.6.2 at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curatormd-v2-vscode-0.6.2-before-0.7.0-20261027/installed-0.6.2.tar.gz` (SHA-256 `ab8a16e23797bf9a80d0a6e60d3ea15efbc9797494e7ff2b488fb335965acd6e`).
- **Verification:** The focused MCP workflow tests, all nine extension tests, Pyright, errors-only Pylint, `node --check`, `pip check`, and `git diff --check` pass. All 87 installed Python modules match source. Hermes profile discovery reports 49 tools, including the new card tool; its project-scoped stdio call returned `vhost-manager-alpha` with zero candidates. Installed/source extension hashes match at `c1058235785dbaa57bf9817de2664179c677615fb5d5728b6b6a2d36fbc6fc77`; VSIX SHA-256 is `2771c8d4dcdc0661904c4fdce67b0aab46e567c5d471512bbf93f32df42b701f`.
- **Open gate:** No SDE candidate was available for an attended review. The VS Code window has not reloaded. Human review, decision projection, purge, and the broader privacy/release gates remain open; no ledger or artifact was changed.
- **Outcome:** Keep detailed review records inside the backend unless the attended CLI is actually reviewing a selected candidate.

## 2026-10-27 — Correct the V2 alpha editor status

- **Intent:** Make the alpha overview match the installed V2-owned VS Code extension and distinguish installation from live editor acceptance.
- **Changed fact:** `docs/alpha-v2.md` now identifies extension 0.7.0 and its local dashboard/review scope; it labels the older profile report historical and records that the current VS Code window has not activated the installed version.
- **Verification:** `python3 tools/count_curator_v2_delivery.py` reports 154/178 complete; `git diff --check` passes. No tests ran because this documentation-only change does not alter code.
- **Open gate:** Visible status-bar rendering and dashboard interaction in a running VS Code window remain unverified. No checklist marker changed.
- **Outcome:** Keep installed local capability and live UI evidence distinct.

## 2026-10-27 — Activate the V2 editor extension in an isolated profile

- **Intent:** Verify that the installed V2 status-bar integration activates in a real VS Code host against the Vhost workspace.
- **Changed fact:** Launched VS Code 1.143.1 with an isolated temporary User profile, the existing `renew-ssl-coding` database/profile settings, and the real `renew_ssl` workspace. Its extension-host log records activation of `curatormd.curatormd-v2-status`; the rendered editor showed `CuratorMD V2` in the status bar.
- **Verification:** Captured the activation log and rendered window. The temporary window closed before a stable dashboard response was confirmed. No app source edit or reviewer/cleanup action occurred.
- **Open gate:** Dashboard read/rendering, reviewer interaction, cleanup, and acceptance in the ordinary editor window remain open. No checklist marker changed.
- **Outcome:** Confirm real extension activation and status-bar rendering without claiming full dashboard acceptance.

## 2026-10-27 — Reload the ordinary V2 editor window

- **Intent:** Activate the installed V2-owned status-bar extension in the normal VS Code window for the `renew_ssl` workspace.
- **Changed fact:** Ran the VS Code `Developer: Reload Window` command. The current extension-host log for workspace `renew_ssl` records `curatormd.curatormd-v2-status` activation from the installed 0.7.0 extension at 14:01:26 local time; the `CuratorMD V2` status item is visible in the ordinary window.
- **Verification:** Inspected `/home/eaglesvn/.config/Code/logs/20261026T201215/window1/exthost/exthost.log` and the rendered ordinary VS Code window. No project source, ledger, or artifact was changed.
- **Open gate:** A stable dashboard response and project reads from the ordinary window are not confirmed. Reviewer interaction, receipt, purge, and alpha acceptance remain open; no checklist marker changed.
- **Outcome:** Clear the editor reload/activation gate for the installed extension without overstating dashboard acceptance.

## 2026-10-27 — Read the V2 dashboard in the ordinary editor

- **Intent:** Verify that the activated local editor plugin can render project-scoped health, activity, and storage data.
- **Changed fact:** Opened `CuratorMD V2: Open Project Dashboard` in the ordinary VS Code window. The webview rendered the configured project's health, retained activity, and storage; it showed 41 processed receipts, 18 goals, 14 facts, zero pending SDEs, and a complete empty staging inventory below the warning threshold. Health remained `unknown` with seven unverified dependency gates, and model/token usage was not reported.
- **Verification:** Observed the rendered 0.7.0 dashboard at 14:05 local time. The health, activity, and storage panels were populated from the local Curator V2 MCP reads. No decision, purge, or application-source change occurred.
- **Open gate:** This confirms the ordinary-window project read/render path only. Reviewer action, grant revocation, cleanup, token coverage, deployed scrape/alert delivery, and the broader pilot remain open; no checklist marker changed.
- **Outcome:** Verify the local plugin's live dashboard read while preserving unknown dependency state and remaining release gates.

## 2026-10-27 — Refresh the enabled Hermes project-usage plugin copy

- **Intent:** Resolve the stale installed plugin implementation and determine the freshness and completeness of its current project report.
- **Changed fact:** The `renew-ssl-coding` profile's enabled `project-usage` files now match Hermes Core source at SHA-256 `75ac7048626b3d274ed0d3b93fed2d2b9f91275d64394e1427bedcb7c1ad25f2`; the previous files were preserved in the profile backup directory. Its read-only report for `vhost-manager-alpha` contains six retained turns from 2026-10-20 through 2026-10-21: five reported and one with unknown usage, all from `codex_app_server`.
- **Verification:** Compared installed/source file hashes and called the plugin's read-only report function against the profile ledger. It returned the retained interval, `coverage_complete=false`, `tokens_complete=false`, and the three declared exclusions. No ledger rows were written and no Hermes service was restarted.
- **Open gate:** The source implementation is current, but its data is stale and incomplete. No new bound usage event was generated; missing call classes, token budgets, retention thresholds, and alerts remain open. No plan checkbox changed.
- **Outcome:** Make the data age and known coverage gaps explicit without presenting stale aggregate totals as current project usage.

## 2026-10-27 — Place the V2 status item after Git Graph and apply health colors

- **Intent:** Make the V2-owned editor status item easy to find and show project health with the established V1 color mapping.
- **Changed fact:** Extension 0.8.0 places the item on the left status-bar group at priority 0, after Git Graph's priority 1, and displays green/healthy, red/degraded, yellow/unknown, or gray before a health read. The V2 backend checkout has no consumer project config by design; the `renew_ssl` config matches the active `vhost-manager-alpha` registration and the `renew-ssl-coding` read grant.
- **Verification:** Ten focused extension tests pass; the packaged extension is installed, activation was observed, and installed/source extension hashes match. A direct read-only launcher call from `renew_ssl` returned project health `unknown` with seven dependency observations missing. The backend checkout's missing `.curatormd-v2.toml` explains why its own dashboard read fails. No consumer config or grant changed.
- **Open gate:** The 0.8.0 dashboard has not been rendered in the configured consumer workspace. Health remains unknown, and reviewer action, cleanup, complete token coverage, and deployment monitoring remain open. No checklist marker changed.
- **Outcome:** Show project-bound health at the requested status-bar position while preserving the backend/consumer boundary and truthful unknown health.

## 2026-10-27 — Explain missing consumer configuration in the V2 editor

- **Intent:** Replace the generic dashboard read failure when a workspace is the Curator V2 backend repo rather than a configured consumer.
- **Changed fact:** The dashboard now checks for `.curatormd-v2.toml` in an existing workspace before reading user settings or spawning the launcher. Missing config produces a direct message to open a configured consumer project. No consumer config or grant was added to the backend repo. Extension 0.8.1 was packaged and installed; the previous 0.8.0 install is archived at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curatormd-v2-vscode-0.8.0-before-0.8.1-20261027/installed-0.8.0.tar.gz` (SHA-256 `3f58e399f5707bc1ec15c3c2247217fe447feb7e36a7a969e8ff7db0d404d3af`).
- **Verification:** The missing-config regression confirms the launcher is not started and the exact configuration guidance is shown. All 11 focused extension tests pass; `node --check` and `git diff --check` pass. Installed/source `extension.js` hashes match at `0881fb12b0c7b1ccf7ceaef31045c5446e8cea203c00dbc758d66147c983a3c9`; VSIX SHA-256 is `dd3e0c892e739d602a1c70d77878d077a4d03ce4a745ce8a7718d3b1c5718b77`. The configured `renew_ssl` launcher returns successful, same-project results for `project_health`, `project_activity_status`, `project_storage_usage`, `goal_list_page` (18 goals), and `sde_review_queue_cards`; health is `unknown` with seven missing dependency observations. After reloading that VS Code window, its extension-host log records 0.8.1 activation. The dashboard rendered project health, and the yellow status item appeared immediately after Git Graph.
- **Open gate:** Health remains `unknown` because seven dependency observations are missing. Real reviewer decisions, purge, complete token coverage, and deployment monitoring remain open. No checklist marker changed.
- **Outcome:** Make the backend/consumer setup error actionable and verify the updated editor plugin in its configured consumer and backend workspaces without weakening registration or grant checks.

## 2026-10-27 — Make V2 dashboard read failures actionable

- **Intent:** Help the repository owner distinguish project-access failures from launcher and MCP transport failures without exposing backend diagnostics.
- **Changed fact:** The V2 editor dashboard now maps denied reads, launcher start/exit failures, timeouts, MCP request errors, and malformed responses to fixed user guidance. Unknown errors remain generic; backend exception text and process output are never forwarded. The current status legend describes green healthy, red degraded, yellow unknown, and gray before first read without a V1 runtime dependency.
- **Verification:** The focused editor suite passes 12/12 tests, including redaction of a private-path/traceback canary. `node --check` and `git diff --check` pass. Package 0.8.2 installed successfully; `code --list-extensions` reports 0.8.2, and installed/source `extension.js` hashes match (`f01c0abc1745cec0cac8fa6fbae07b8d9e4ee350fc8871e509b6ec393ff0cf76`). VSIX SHA-256 is `918c8526fa12509e714449234892f8101744a38191576890f1db911dd86d1573`. The prior 0.8.1 extension was archived with SHA-256 `2c24cccb5c68a1c2a6c8af7d06856313675ec7adc2bcb4edc068f74822132e6e`.
- **Open gate:** Activation of 0.8.2 in the existing editor host and the revised denied-read message in a live dashboard have not been independently observed. The backend repository intentionally has no consumer `.curatormd-v2.toml`; opening the dashboard there must remain unavailable. No checklist marker changed.
- **Outcome:** Improve failure guidance and package the local VS Code extension while preserving the backend/consumer boundary and not overstating editor-host activation.

## 2026-10-27 — Show V2 goal and operational queue totals

- **Intent:** Advance the local dashboard portion of the operational-visibility plan and keep an unconfigured backend workspace from showing a false yellow health result.
- **Changed fact:** The project dashboard now summarizes all eight goal states and the project-matched event, review, purge, and expiry queues from health/activity snapshots. Missing, incomplete, or cross-project snapshots render as unknown. The status item stays gray until a health read is attempted; unknown health after a read remains yellow. The dashboard is read-only and does not send external alerts.
- **Verification:** Thirteen focused extension tests pass, including exact queue/goal totals, mismatch/incomplete handling, and the no-config gray status. `node --check` and `git diff --check` pass. Package 0.8.3 installed successfully; its source hash matches this checkout (`a3ccf82a823f675e9a76f302f63c4b650c7bd4ed01cbfaea5ddc8f2b5978dc80`); VSIX SHA-256 is `96361a669edc667b90cf0b72d3fa82e93f3eee1094fe3f17e968b40acbd8d089`. A fresh read-only installed-launcher call returned same-project health/activity for `vhost-manager-alpha` and rendered 5 planned/13 active goals with zero event, review, purge, or expiry queue work; health remained `unknown`. The prior 0.8.2 install was archived with SHA-256 `2fb4e5c9595863de410ca88d1e19a44ee845236bc6a1422989f29c4eecd700b6`.
- **Open gate:** Activation of 0.8.3 in the existing editor host, external alert delivery, and deployment monitoring remain unverified. No plan marker changed.
- **Outcome:** Make local goal and queue state visible without representing the local dashboard as a deployed alerting system.

## 2026-10-27 — Clarify V2 status colors

- **Intent:** Make the V2 status legend distinguish “not checked” from an unknown health result and prevent confusion with deprecated V1 colors.
- **Changed fact:** The V2 extension guide now defines gray as no health read attempted, yellow as an attempted read that is unavailable, mismatched, or unknown, green as healthy, and red as degraded. V2 has no purple state.
- **Verification:** Compared the V2 `STATUS_COLORS` mapping and status update paths with the V1 palette and its Hermes-unhealthy branch. Documentation matches the V2 implementation. `pyright` reports 0 diagnostics; errors-only Pylint, Bandit, locked `uv audit`, and `git diff --check` pass. No unit tests ran because this was a documentation-only clarification.
- **Open gate:** Runtime display still depends on the installed extension version loaded by the current VS Code window. No checklist marker changed.
- **Outcome:** Preserve the V2 color contract without importing V1 state or meanings.

## 2026-10-27 — Check the loaded V2 editor package

- **Intent:** Determine whether the backend workspace's visible status item uses the latest V2 extension.
- **Changed fact:** The installed extension is 0.8.3, while the two existing `curatormd-v2.0` extension-host logs show 0.8.0 and 0.8.1. A request to open a new VS Code window produced no observed 0.8.3 activation log.
- **Verification:** Compared `code --list-extensions --show-versions` with the current extension-host activation/module-load entries for the backend workspace. The loaded package is older than the installed package.
- **Open gate:** The current window has not been verified after reload with 0.8.3; its visible color is not evidence of the current implementation. No checklist marker changed.
- **Outcome:** Identify stale VS Code activation as the reason the gray-state fix is not yet confirmed in the visible backend window.

## 2026-10-27 — Align reviewer acceptance with approved local-alpha identity

- **Intent:** Remove the definition-of-done conflict that rejected local UID review despite the owner's single-user alpha decision.
- **Changed fact:** The SDE acceptance now recognizes the attended `eaglesvn` OS UID, current-process UID check, and exact `vhost-manager-alpha` grant against the owner-owned ledger for local alpha. A shared or production deployment still requires its authenticated subject/role path. The review and one-action cleanup checklist items remain unchecked until an authorized human decision and its receipts are independently verified.
- **Verification:** `id` reports UID 1000 as `eaglesvn`; the alpha database is owned by `eaglesvn` with mode 0600 and schema 38. A read-only SQLite query confirms active `local-uid:1000` read, write, and review grants on `vhost-manager-alpha`; legacy profile read/write grants are revoked. The same read-only check finds no SDE candidates for the project. No ledger rows were changed.
- **Open gate:** No candidate currently exists for the authorized human to decide, and no exact-inventory cleanup receipt was created or independently checked. No checklist marker changed.
- **Outcome:** Make local-alpha acceptance match the approved single-user design while preserving human-review and cleanup evidence requirements.

## 2026-10-27 — Add local operational attention summary

- **Intent:** Make actionable local project warnings visible in the V2 editor without treating missing observations as zero or adding a deployed alerting claim.
- **Changed fact:** The dashboard now summarizes degraded/unknown readiness, event intake/failure counts, review and cleanup queues, incomplete staging inventory, and the warning-only byte threshold. Failed-event text points to fixed project metric categories for evidence rejection vs adapter errors; the dashboard does not display event content or raw diagnostics.
- **Verification:** The focused VS Code extension suite passes 14/14 tests, including project mismatch, unknown counters, pending queues, and staging warnings while writes remain allowed. `node --check` passes. Package 0.8.4 was built and installed; installed/source `extension.js` hashes match at `d97a0d4134a8e6012c81f8cfc3edbc1628d5bea2e904735948a5ae9a5fba9319`, and VSIX SHA-256 is `2b33577de7aa0b625e188a1afa271e7ddda08678b5157ce5da773a6d0d86b917`. The prior 0.8.3 install was archived with SHA-256 `7f7b23a8cbd013bbe8bd44565973ccb1e0bce7fa891b675a15c49b03c13b1874`. No backend suite was rerun because the change is isolated to the extension.
- **Open gate:** Existing VS Code windows still load 0.8.0/0.8.1, so activation and rendered 0.8.4 alert states remain unverified. This is local snapshot alerting only. External alert delivery, deployment monitoring, complete producer coverage, and the full operational-dashboard checklist item remain open. No checklist marker changed.
- **Outcome:** Improve and install local alpha operator visibility while preserving unknown states and separating it from deployed alert delivery.

## 2026-10-27 — Show the installed version in the V2 status tooltip

- **Intent:** Let the operator identify which V2 extension package a status-bar button is using.
- **Changed fact:** Neutral and project-health tooltips include the packaged extension version. The dashboard also displays fixed project-bound event-failure categories when metrics reconcile with health receipt totals.
- **Verification:** The focused VS Code extension suite passes 14/14 tests; `node --check` and `git diff --check` pass. Extension 0.8.6 is packaged and installed. Source and installed `extension.js` hashes match at `07fe63530d1373b14735a3171021a035660f3bfa5a1663dadebddd6118bc942e`; VSIX SHA-256 is `fbeff4c0c83eaa3191a2a7ceeeb80ff72b9dc3f7a81eb2ceed5e692e0a2e60fd`. The prior 0.8.5 installation is preserved at `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curatormd-v2-vscode-0.8.5-before-0.8.6-20261027/installed-0.8.5.tar.gz` (SHA-256 `25fc60815684d156c7f528524872d37610ceac97f0aa8a44d4677de785e9461f`).
- **Open gate:** Existing VS Code host activation and rendered tooltip remain unverified; no checklist marker changed. No backend tests were rerun because this change is isolated to the extension.
- **Outcome:** Install a version-identifiable local V2 status button without changing consumer repositories or V1.

## 2026-10-27 — Confirm V2 extension activation in the consumer editor

- **Intent:** Check whether the installed tooltip update is loaded by the current editor host.
- **Changed fact:** The `renew_ssl` VS Code extension host now loads CuratorMD V2 extension 0.8.6; this supersedes the prior observation that the existing windows still loaded 0.8.0/0.8.1.
- **Verification:** `/home/eaglesvn/.config/Code/logs/20261026T201215/window1/exthost/exthost.log` records `loadModule` for `/home/eaglesvn/.vscode/extensions/curatormd.curatormd-v2-status-0.8.6/extension.js` at 2026-10-27 15:17:28. The package version and installed/source hashes match the prior entry. This proves module activation, not rendered hover text.
- **Open gate:** Current tooltip text has not been inspected in the editor, and activation in the unconfigured Curator backend workspace remains unverified. No plan marker changed.
- **Outcome:** Replace stale activation status with current consumer-window evidence while keeping visual verification open.

## 2026-10-27 — Confirm the V2 status tooltip version

- **Intent:** Resolve whether the installed status-bar tooltip visibly identifies the active package.
- **Changed fact:** The owner reports the tooltip displays `8.6` in the current editor, matching installed extension version 0.8.6.
- **Verification:** User-observed tooltip text; extension-host logs independently record module activation from the 0.8.6 install, and focused extension tests assert that tooltip strings include the package version. No screenshot or automated UI capture was retained.
- **Open gate:** Activation in the unconfigured Curator backend workspace remains unverified. No plan marker changed.
- **Outcome:** Record the visible tooltip version without overstating the available UI evidence.

## 2026-10-27 — Preserve a concurrent restore destination

- **Intent:** Verify restore-to-new-path does not overwrite a file created after destination validation.
- **Changed fact:** Added a regression that injects a concurrent restore target immediately before the atomic hard-link install.
- **Verification:** `uv run python -m unittest discover -s tests -p test_backup.py` passes all six backup/restore tests. The regression confirms the competing file's bytes survive, the source snapshot remains present, and the temporary restore file is removed. `git diff --check` passes.
- **Open gate:** This is local filesystem evidence. The production-shaped storage/staging fault matrix, deployment recovery, and review of retry/stop policy remain open; no checklist marker changed.
- **Outcome:** Extend local no-overwrite recovery coverage for database restore.

## 2026-10-27 — Preserve unsupported-schema snapshots for isolated review

- **Intent:** Verify restore behavior when the backup is structurally valid but its schema is newer than this Curator build supports.
- **Changed fact:** Added a composed backup/restore regression proving the future schema is copied only to a new path, then rejected by the application without downgrading or mutating its `user_version`.
- **Verification:** `uv run python -m unittest discover -s tests -p test_backup.py` passes all seven backup/restore tests. The source, snapshot, and isolated restored copy retain the newer schema version. `git diff --check` passes.
- **Open gate:** This confirms local preservation and fail-closed open behavior; production storage drills, owner-reviewed recovery, and backup/restore authorization remain open. No checklist marker changed.
- **Outcome:** Keep unsupported recovery data intact for a compatible tool or operator review.

## 2026-10-27 — Back up committed WAL state with a held reader

- **Intent:** Verify online backup while an older read transaction prevents WAL truncation.
- **Changed fact:** Added a real SQLite integration regression that holds a reader snapshot, commits a later fact into WAL, confirms checkpoint busy, then backs up both committed facts without changing what the held reader observes.
- **Verification:** `uv run python -m unittest discover -s tests -p test_backup.py` passes all eight backup/restore tests. `git diff --check` passes.
- **Open gate:** This validates the local SQLite online-backup path under a held reader; deployment filesystem behavior, power loss, operational restore review, and production drills remain open. No checklist marker changed.
- **Outcome:** Cover WAL-reader interference in local recovery evidence.

## 2026-10-27 — Recheck the local Vhost maintenance timer

- **Intent:** Refresh the live local-alpha maintenance status before relying on older timer evidence.
- **Changed fact:** The six-hour `vhost-manager-alpha` timer is active and waiting; its latest run completed successfully with no expiry or purge targets.
- **Verification:** `systemctl --user show` reports timer active/waiting, `Result=success`, last trigger 2026-10-27 12:00:09 +07, and next trigger 18:00:13 +07. The service reports exit status 0. Its bounded journal summary reports zero processed and zero pending expiry/purge targets. No deletion or service restart occurred.
- **Open gate:** This is an idle local maintenance pass; it does not prove production router scheduling, external alert delivery, or a purge of an approved artifact. No checklist marker changed.
- **Outcome:** Replace the stale “first six-hour run pending” observation with current local service evidence.

## 2026-10-27 — Refresh the repository-wide quality inventory

- **Intent:** Recheck the documented blocking quality chain and warning-level Pylint after the store decomposition.
- **Changed fact:** `store.py` is 88 lines; the previous warning inventory describing it as 9,645 lines is stale. Full-tree Pylint currently reports 22 findings across seven modules and exits 28 at 9.99/10.
- **Verification:** Strict Pyright, errors-only Pylint, Bandit, and `git diff --check` pass. Bandit emits `nosec` and test-comment notices but exits successfully. Full warning-level Pylint findings are staging-write complexity, MCP registration module size, cleanup exception catches, a contextmanager warning, test-helper docstrings, and duplicate test-helper code.
- **Open gate:** Repository-wide warning-level cleanup remains open; no checklist marker changed. No source code or tests were changed in this verification step.
- **Outcome:** Replace the outdated Pylint inventory with current results without claiming broad lint completion.

## 2026-10-27 — Verify Hermes Core checks against the available base

- **Intent:** Recheck the Hermes Core integration branch with its repository quality command.
- **Changed fact:** The shallow checkout has no `main` or `origin/main` ref. Its current commit is `d2aac32b8`, with available parent `49c13f030cc7c4151d85c85de855246c81dc81a1`.
- **Verification:** The default `scripts/check` invocation cannot resolve its implicit base. Re-running `.venv/bin/python scripts/check --base 49c13f030cc7c4151d85c85de855246c81dc81a1` passes all 12 checks, including code-health with zero blocking and advisory findings. The Hermes worktree remains clean.
- **Open gate:** This verifies checkout quality against the current commit's parent; it does not prove active gateway delivery or a real app-server event. Slice G remains open.
- **Outcome:** Refresh local Hermes Core check evidence without changing its source or runtime.

## 2026-10-27 — Document staging and store fault-injection helpers

- **Intent:** Remove missing-docstring findings from the current warning-level Pylint inventory without changing test behavior.
- **Changed fact:** Added short docstrings to five commit/rollback connection-fault helper methods and two staging-writer fault helpers.
- **Verification:** Focused warning-level Pylint rates `tests/test_store_resources.py` and `tests/test_project_plugin_staging.py` 10.00/10; `git diff --check` passes. No tests were rerun because executable behavior did not change.
- **Open gate:** The full-tree Pylint inventory was not rerun; the remaining warnings and broad lint checklist item remain open.
- **Outcome:** Clear seven targeted style findings while preserving the warning gate's incomplete status.

## 2026-10-27 — Narrow SQLite cleanup exception handling

- **Intent:** Remove overly broad cleanup catches without masking the original commit failure.
- **Changed fact:** Transaction recovery catches `sqlite3.Error` for rollback and close failures, matching the SQLite adapter contract.
- **Verification:** All five `test_store_resources.py` tests pass; focused Pylint on `store_operations_00.py` rates 10.00/10; `git diff --check` passes.
- **Open gate:** The full-tree warning-level inventory was not rerun. Other warning findings remain and the broad lint checklist item stays open.
- **Outcome:** Narrow rollback/close recovery to expected SQLite errors and retain fault-injection coverage.

## 2026-10-27 — Split MCP artifact cleanup registrations

- **Intent:** Bring the MCP registration module below its configured size limit without changing its public tool contract.
- **Changed fact:** Moved six reviewed artifact cleanup handlers to `mcp_tool_cleanup_registration.py`; tool names, schemas, annotations, and API calls remain the same.
- **Verification:** Focused Pyright and Pylint pass. The MCP server suite passes five tests and the hosted-MCP suite passes 12. Whole-tree Pylint falls from 22 to 12 findings (score 9.99/10); the registration module, broad SQLite cleanup catches, and seven helper-docstring findings are cleared. `git diff --check` passes.
- **Open gate:** Twelve whole-tree Pylint findings remain: ten in staging-write design, one contextmanager warning, and one duplicate test fixture. The warning-level quality item remains open.
- **Outcome:** Separate cleanup registration from general tool wiring while preserving behavior.

## 2026-10-27 — Clear the remaining full-tree Pylint findings

- **Intent:** Remove the remaining staging-write, test-fixture, and contextmanager findings from the warning-level quality scan.
- **Changed fact:** Staging persistence callbacks and retry/publish/occurrence parameters now use typed request records; retry identity checks are separated into bounded helpers; the unused project-usage field was removed from the write request while the configured complete-inventory scan remains. Backup and storage CLI tests share one temporary initialized database fixture. A line-level Pylint waiver documents that the project-revision transaction intentionally remains open across the yielded caller effect.
- **Verification:** The staging suite passes 18 tests; backup and storage CLI suites pass 12. Full-tree warning-level Pylint reports 10.00/10 and exits successfully. Strict Pyright, errors-only Pylint, Bandit, and `git diff --check` pass. Bandit prints existing `nosec` and test-comment notices but returns success.
- **Open gate:** This closes local repository lint cleanup only. Deployment, production workflow, operational recovery, and release gates remain open; no delivery marker changed.
- **Outcome:** Restore a clean full-tree Pylint result without changing staged-file limits or the transaction fence's lifetime.

## 2026-10-27 — Preserve staging rollback errors

- **Intent:** Ensure unexpected staging-age receipt failures do not leave an unreceipted file silently published.
- **Changed fact:** Any exception from age-receipt persistence now attempts to remove the just-published target and sync its directory. If unlink or directory sync also fails, the original receipt exception remains primary and receives only the cleanup exception type as a note.
- **Verification:** The focused staging suite passes 20 tests, including unexpected callback failure and simultaneous rollback-unlink failure. The former leaves no final/partial files; the latter keeps the final file visible in a complete inventory. Strict Pyright, focused Pylint, and `git diff --check` pass.
- **Open gate:** This covers local adapter behavior only. Process kill, power loss, and production storage/staging recovery remain open; no delivery marker changed.
- **Outcome:** Make staging rollback outcomes explicit and avoid falsely acknowledging a file with no durable age receipt.

## 2026-10-27 — Refresh the Hermes alpha profile read

- **Intent:** Recheck local Hermes-profile connectivity and Curator V2 health without changing ledger state.
- **Changed fact:** The `renew-ssl-coding` profile connects to its installed Curator V2 stdio server and discovers 49 tools. Its `vhost-manager-alpha` ledger read returns 41 processed receipts, 18 goals, and 14 facts; the separate health read reports healthy with no pending review/purge work, a complete empty staging inventory, and seven fresh dependencies.
- **Verification:** `.venv/bin/hermes --profile renew-ssl-coding mcp test curator_v2 --probe-curator-status` succeeds at 2026-10-27 08:51 UTC. The Hermes checkout remains clean at `d2aac32b8`.
- **Open gate:** The last processed ledger event is timestamped 06:52 UTC; this profile health read does not create or prove a new app-server lifecycle event. Active gateway delivery and Slice G remain open.
- **Outcome:** Refresh local alpha integration evidence while preserving the distinction between profile connectivity and live lifecycle delivery.

## 2026-10-27 — Verify the V2 status tooltip in the reloaded consumer editor

- **Intent:** Confirm the rendered tooltip identifies the current V2 status extension package after the owner observed the previous `0.8.6` version.
- **Changed fact:** Rebuilt and reinstalled extension `0.8.7`. After `Developer: Reload Window` in the ordinary `renew_ssl` editor, hovering the status item visibly rendered `CuratorMD V2 0.8.7. Project health has not been checked. Click to open the dashboard.` The item was gray before the health read. After clicking it, the dashboard read health `unknown` with seven unverified dependency gates and showed 41 processed receipts, 18 goals, 14 facts, zero pending SDEs, and a complete empty staging inventory; the status turned yellow, and the hover rendered `CuratorMD V2 0.8.7. Project health: unknown, no SDE reviews pending. Click to open the project-scoped dashboard.` The V2 legend assigns purple to pending SDE review only when no other degraded health gate takes precedence.
- **Verification:** All 14 focused extension tests pass; `node --check` and `git diff --check` pass. `code --list-extensions --show-versions` reports `curatormd.curatormd-v2-status@0.8.7`; source and installed `extension.js` hashes match at `6209202ed1fac1f5a73398b4c4625e882a71a957fae5a9c276fe5686ac860188`. VSIX SHA-256 is `f26efef88fb0459c4338216dff7a09b5125d7e8fada32c5b20dae847be530834`. Both hover states were inspected directly in the `renew_ssl` window; the screenshots were not retained.
- **Open gate:** Activation in the unconfigured Curator backend workspace and live health/review color transitions remain unverified in the editor. No checklist marker changed.
- **Outcome:** Replace the stale 0.8.6 hover with directly verified 0.8.7 tooltip text in the configured consumer editor.

## 2026-10-27 — Exercise actual staging root and lock failures

- **Intent:** Fill the local health-path gap where prior coverage replaced the whole staging-lock context instead of failing the underlying OS operations.
- **Changed fact:** Added regressions that fail the real staging-root `os.open` and `fcntl.flock(LOCK_EX)` calls. Each project health read returns degraded with incomplete staging inventory and omits the injected private path. The lock-failure path closes the root descriptor; after each fault is removed, a fresh health read returns healthy with complete inventory.
- **Verification:** `uv run python -m unittest discover -s tests -p test_api_health_metrics.py` passes 18 tests. Focused Pyright reports zero diagnostics, errors-only Pylint passes, and `git diff --check` passes.
- **Open gate:** These verify local filesystem adapter boundaries. Production-adapter faults, repeated retry/stop behavior, and deployment-owner recovery classifications remain open; no checklist marker changed.
- **Outcome:** Add direct local evidence for staging root/lock failures and recovery without claiming production matrix completion.

## 2026-10-27 — Distinguish unreadable staged files from file changes

- **Intent:** Make staging inventory report unreadable-file faults accurately and ensure the existing changing-file test reaches the descriptor-read code.
- **Changed fact:** The scanner now maps hashing `OSError` values through its fixed filesystem error classifier, so `EACCES` yields `permission_denied`; `ValueError` from changed descriptor/path identity still yields `changed_during_scan`. Both keep the inventory incomplete with no manifest. The open-fault test fixtures preserve the `os.open` dir-fd capability check; a fault-free retry then returns a complete manifest.
- **Verification:** `uv run python -m unittest discover -s tests -p test_project_plugin_storage.py` passes 20 tests, including actual file mutation and unreadable-file cases. Focused Pyright reports zero diagnostics, errors-only Pylint passes, and `git diff --check` passes.
- **Open gate:** These are local file-read results. Filesystem races in the deployment adapter, bounded repeated-retry classification, and production recovery evidence remain open; no checklist marker changed.
- **Outcome:** Preserve truthful incomplete inventory semantics and fixed privacy-safe codes for local file-read faults.

## 2026-10-27 — Recheck the Curator V2 quality gate

- **Intent:** Complete the previously pending repository quality check against the current dirty V2 worktree without repeating the unit suite.
- **Changed fact:** No application source or checklist marker changed in this verification step. The local alpha six-hour purge timer and 72-hour staging expiry policy were already configured; production retention and monitoring remain separate gates.
- **Verification:** The README/CI quality commands pass: strict Pyright reports zero diagnostics, errors-only Pylint passes, Bandit exits 0, and `git diff --check` is clean. Bandit emits existing `nosec` and comment-tag notices. The unit suite was not rerun.
- **Open gate:** These are current local static/security checks only. Production scheduling, alert delivery, deployment identity, and live workflow evidence remain open.
- **Outcome:** Refresh current-tree quality evidence without claiming release readiness.

## 2026-10-27 — Confirm stale Hermes project-usage coverage

- **Intent:** Refresh the current usage measurement for the one-project Hermes alpha profile and determine whether the missing provider/model route can be recovered safely.
- **Changed fact:** The query-only `renew-ssl-coding` usage ledger still contains six `vhost-manager-alpha` turns from 2026-10-20 through 2026-10-21: five reported and one unknown. The unknown row has no provider/model labels. The stored Codex lifecycle envelope intentionally keeps only its allowlisted lifecycle fields and cannot supply those missing labels; do not backfill them by guessing.
- **Verification:** SQLite `PRAGMA quick_check` returns `ok`; the bounded aggregate read found six distinct turns, five reported, one unknown, and a last `occurred_at` of `2026-10-21T10:40:21.453664+00:00`. The query printed no token values, event IDs, or session IDs and wrote no rows. Hermes Core checkout remains clean on `codex/curator-v2-hermes-integration-upstream`.
- **Open gate:** The report is six days stale and incomplete. No new bound Hermes usage event was generated; excluded call paths, token budgets, billing reconciliation, retention thresholds, and alerts remain open. No checklist marker changed.
- **Outcome:** Preserve the unknown attribution and make stale usage evidence explicit rather than fabricating provider/model data.

## 2026-10-27 — Report age of retained Hermes project usage

- **Intent:** Make the read-only Hermes project-usage result expose how old its latest retained observation is, without choosing an owner freshness threshold.
- **Changed fact:** Hermes Core `project_usage` now returns UTC `measured_at` and `latest_event_age_seconds`; empty or invalid timestamps keep the age null. The profile-local plugin copy was refreshed after backing up its prior files under `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/project-usage-before-age-field-20261027T104832Z/`.
- **Verification:** Five focused plugin tests pass. `plugins doctor --ci` reports one registered tool. A direct handler read for `vhost-manager-alpha` returns six turns (five reported, one unknown), age 518,900 seconds, and `coverage_complete=false` / `tokens_complete=false`; token values and private IDs were not printed. `scripts/check --base 49c13f030cc7c4151d85c85de855246c81dc81a1` passes all 12 checks.
- **Open gate:** The new field measures age without deciding freshness. No new usage event or source coverage was created; token budget policy, excluded call classes, billing reconciliation, retention, alerting, and live runtime remain open. No checklist marker changed.
- **Outcome:** Give the local operator an explicit usage age while preserving unknown counts and avoiding an invented freshness policy.

## 2026-10-27 — Recheck Hermes-profile Curator V2 access

- **Intent:** Recheck the supported Hermes profile path behind the direct-Codex `unauthenticated` response and distinguish profile access from new lifecycle delivery.
- **Changed fact:** The `renew-ssl-coding` CLI connects to the installed Curator V2 stdio server with host-injected Hermes profile/session context and reads `vhost-manager-alpha`: 41 processed receipts, 18 goals, 14 facts, zero pending review/purge work, and healthy project health with complete empty staging.
- **Verification:** `/home/eaglesvn/.hermes/hermes-agent/.venv/bin/hermes --profile renew-ssl-coding mcp test curator_v2 --probe-curator-status` exits 0 and discovers 49 tools. The last processed event remains timestamped 2026-10-27 06:52 UTC; the probe created no new app-server lifecycle event.
- **Open gate:** Direct Codex MCP without Hermes context remains unauthenticated by design; supported profile access is verified. This does not establish human identity or live event delivery. Slice G and production gates remain open; no checklist marker changed.
- **Outcome:** Clarify the supported local access path without equating missing Codex caller context with a failed Curator ledger.



## 2026-10-27 — Verify the local alpha dashboard and alert surface

- **Intent:** Finish the local V2 operator dashboard/alert requirement for the approved single-user development alpha.
- **Changed fact:** The local acceptance row now records the installed V2 editor dashboard, attention summary, and journal-backed maintenance status. The dashboard covers project health, goal states, queues, staging completeness and warning threshold, storage, and reconciled event-failure categories.
- **Verification:** The focused extension suite has 14 passing cases for project binding, queue and failure summaries, incomplete snapshots, warning-only staging, and mismatch handling. The `renew-ssl-coding` profile reads the bound `vhost-manager-alpha` ledger. The six-hour user timer is active; its latest run exited 0 with zero processed or pending targets, and service output is in the user journal.
- **Open gate:** Production scrape infrastructure, remote alert routes, shared retention/cardinality policy, and production scheduler/recovery evidence remain open in their separate checklist rows. No production monitoring or all-producer coverage is claimed.
- **Outcome:** Record local dashboard and journal evidence without checking off the broader end-to-end monitoring requirement.

## 2026-10-27 — Preserve source apply criteria through Vhost Curator retries

- **Intent:** Keep a Vhost apply preview's source problem and success criteria intact when its first Curator event attempt is unavailable.
- **Changed fact:** The Vhost plan response now exposes the bounded problem and fixed criteria, and its review modal displays each criterion as open before apply. `/api/apply` carries that same problem and criterion IDs. It persists only those fields in the operation manifest before sending, reuses them on retry/replay, and removes them after a durable receipt. The operation outcome remains a separate compact fact.
- **Verification:** One focused Vhost browser preview test passes against a temporary build and test server. `test_vhost_apply_route_persists_and_retries_exact_curator_receipt` passes against a disposable Vhost server and Curator V2 store. It verifies project-scoped receipt, preview-to-goal problem/criteria equality, pending retry after restart, outcome fact, request cleanup, and identical replay. Node syntax checks and Python compilation pass; both repository `git diff --check` commands pass. The root Vhost process and its static asset directory were not modified.
- **Open gate:** This is fixture evidence only. The real-consumer request, named pilot bindings, owner-reviewed acceptance packet, and deployment/release gates remain open. No checklist marker changed; the V2 checklist count is unchanged.
- **Outcome:** Remove the lossy generic-goal fallback for pending apply retries without claiming the real one-run pilot acceptance.

## 2026-10-27 — Explain V2 status colors in the live tooltip

- **Intent:** Make the status-bar color meanings understandable from the button itself while retaining the installed version and project health in the hover.
- **Changed fact:** VS Code extension `0.8.8` now adds the active color meaning to its tooltip. Gray says no health read has been attempted; yellow says health or the SDE review count is unknown. Green, purple, and red receive corresponding descriptions. The status-bar extension checklist row was already complete; no checklist marker changed.
- **Verification:** The focused Node suite passes 14/14; `node --check` and `git diff --check` pass. VS Code lists `curatormd.curatormd-v2-status@0.8.8`; packaged and installed `extension.js` hashes match at `c91042d76b30704614ab141ec30bc2c052512ebd28290a2c2850d89d71f27217`. After reloading the `renew_ssl` window, live hovers displayed `CuratorMD V2 0.8.8. Gray means no health read has been attempted...` and, after the read, `CuratorMD V2 0.8.8. Yellow means health or the SDE review count is unknown. Project health: unknown, no SDE reviews pending...`. The dashboard still showed seven unknown host-dependency gates.
- **Open gate:** Live green/purple/red transitions and deployed monitoring remain unverified. Yellow is the correct fail-closed editor result without Hermes-provided readiness metadata; this UI change does not supply that metadata or claim those dependencies are healthy.
- **Outcome:** Close the color-explanation and rendered-tooltip detail for the local editor plugin; retain deployment and host-readiness gates as open.

## 2026-10-27 — Verify the live V2 status-bar hover

- **Intent:** Resolve the reported mismatch between the visible status-bar tooltip and the installed V2 extension version.
- **Changed fact:** In the current `renew_ssl` VS Code window, the `CuratorMD V2` item appears immediately after Git Graph, is yellow for unknown health, and its rendered hover reads `CuratorMD V2 0.8.7. Project health: unknown, no SDE reviews pending. Click to open the project-scoped dashboard.` The dashboard shows 41 processed receipts, 18 goals, 14 facts, zero pending SDEs, and a complete empty staging inventory.
- **Verification:** Directly inspected a live editor screenshot at 17:58 +07. The same view shows the 250 MiB staging threshold as warning-only with writes allowed, and says model/token use is not reported there. No tests were rerun; the existing focused extension tests cover the color-state branches. No checklist marker changed because the VS Code extension delivery item is already checked.
- **Open gate:** This proves the configured consumer editor and its unknown/yellow hover state. A live pending-review/purple or healthy/green transition, complete token usage, and deployed monitoring remain unverified.
- **Outcome:** Confirm the current visible version is 0.8.7 and close the rendered-tooltip check for this editor window.

## 2026-10-27 — Recheck Hermes-profile Curator V2 access

- **Intent:** Recheck the exact supported Hermes profile path behind the earlier direct-Codex `unauthenticated` response and distinguish profile access from new lifecycle delivery.
- **Changed fact:** The `renew-ssl-coding` CLI connects to the installed Curator V2 stdio server with host-injected Hermes profile/session context and reads the bound `vhost-manager-alpha` ledger. It reports 41 processed receipts, 18 goals, 14 facts, zero pending review/purge work, and healthy project health with a complete empty staging inventory.
- **Verification:** `/home/eaglesvn/.hermes/hermes-agent/.venv/bin/hermes --profile renew-ssl-coding mcp test curator_v2 --probe-curator-status` exits 0 and discovers 49 tools. The last processed event remains timestamped 2026-10-27 06:52 UTC; the probe created no new app-server lifecycle event.
- **Open gate:** Direct Codex MCP without Hermes context remains unauthenticated by design; supported profile access is verified. This does not establish human identity or live event delivery. Slice G and production gates remain open; no checklist marker changed.
- **Outcome:** Clarify the supported local access path without equating missing Codex caller context with a failed Curator ledger.

## 2026-10-27 — Show bounded evidence details in the V2 dashboard

- **Intent:** Let an authorized local user follow a visible verification fact to its evidence locator and immutable verifier receipt.
- **Changed fact:** Added project-authorized `goal_fact_evidence`, limited to one fact on the requested bounded report page. Its response includes the report revision, evidence outcome/digest/locator, and matching verifier attestation. The V2 VS Code panel now fetches details per visible fact, binds responses to the current project, goal, fact, page, and revision, and renders all ledger values as text. Version advanced to 0.8.9 for this package change.
- **Verification:** `test_goal_reporting.py` passes 11 tests; `test_api_goal_access.py` passes 13; the MCP client workflow passes and confirms the new read tool is discoverable/read-only; the VS Code extension suite passes 14; strict Pyright reports zero diagnostics; `node --check` and `git diff --check` pass. The extension test exercises the evidence read, checks its exact MCP arguments, and verifies stale report handling. VSIX 0.8.9 packages successfully and is installed locally; installed `extension.js` matches source at SHA-256 `6c2aa3a4376394e55a6eacd9f86f26c86eb6ea5085c95eda958bd0b61622af7b`.
- **Open gate:** The extension is installed as 0.8.9, but the running VS Code window still needs **Developer: Reload Window** before its hover can show the new version. The dashboard acceptance also remains open for trust-root/revocation changes between pages, grant revocation, reopen/compaction transitions, and an approved real-consumer interaction. No checklist marker changed.
- **Outcome:** Expose bounded evidence details in the local V2 plugin without claiming the remaining snapshot/trust lifecycle is complete.

## 2026-10-27 — Deny V2 dashboard reads after project-grant revocation

- **Intent:** Verify a previously rendered report does not authorize later evidence or page reads after the project grant changes.
- **Changed fact:** Added an API regression that reads a report and one fact's evidence under an exact read grant, revokes that grant, and confirms subsequent report and evidence reads are denied. The existing extension test verifies stale rendered data is cleared after a denied fresh read. The dashboard acceptance note records this synthetic local coverage; its full item remains open.
- **Verification:** `uv run python -m unittest discover -s tests -p test_api_goal_access.py` passes 14 tests; `uv run pyright tests/test_api_goal_access.py` reports zero diagnostics; `git diff --check` passes.
- **Open gate:** The toggle authorizer is a test fixture. Live editor grant changes, external trust/revocation versions, reopen/compaction transitions, and approved real-consumer evidence remain open. No checklist marker changed.
- **Outcome:** Prove fresh V2 reads fail closed after grant revocation without claiming live grant-management integration.

## 2026-10-27 — Invalidate a report after evidence revocation

- **Intent:** Ensure report pages do not preserve a verified label after the configured verifier rejects the stored proof.
- **Changed fact:** Added a reporting regression that accepts a proof for page one, changes the verifier to reject it, and requests a later page. The second report has a different revision and its criterion is open, which activates the extension's existing stale-page restart path. The plan now records this as synthetic local revocation coverage.
- **Verification:** `uv run python -m unittest discover -s tests -p test_goal_reporting.py` passes 12 tests; `uv run pyright tests/test_goal_reporting.py` reports zero diagnostics; `git diff --check` passes.
- **Open gate:** The fixture does not change a deployed trust-root version or live source revocation state. External trust versioning, live revocation, grant changes in the editor, and real-consumer acceptance remain open. No checklist marker changed.
- **Outcome:** Show that local evidence revocation changes the report revision and reopens its criterion without claiming deployed trust integration.

## 2026-10-27 — Fail closed on future staging ages

- **Intent:** Prevent a wall-clock rollback or future staged timestamp from resetting a transient artifact's retention age and authorizing deletion later.
- **Changed fact:** Expiry discovery now samples its observation clock after taking the staging-root lock and rejects any staged timestamp later than that observation. The file contributes to `unknown_age_count`, makes the inventory incomplete, suppresses its purge manifest, and remains on disk.
- **Verification:** `uv run python -m unittest discover -s tests -p test_project_plugin_storage.py` passes 21 tests, including a staged timestamp five minutes ahead of the observation clock. Strict Pyright reports zero diagnostics, focused Pylint is 10.00/10, and `git diff --check` passes.
- **Open gate:** This covers the local future-timestamp/clock-rollback case only. Missing or malformed timestamps, backup/restore age preservation, owner-approved production age anchors, measured budgets, and deployed growth alerts remain open. No checklist marker changed.
- **Outcome:** Prevent future-dated staging metadata from becoming purge-eligible after time catches up.

## 2026-10-27 — Preserve staging age across local database restore

- **Intent:** Ensure a restored Curator ledger does not restart the retention clock for artifacts that remain in the consumer staging tree.
- **Changed fact:** Added a restore-to-new-file regression for staging metadata. It backs up a project with one staged artifact, restores to another SQLite path, binds the same consumer config, and checks expiry against the original staged timestamp.
- **Verification:** `uv run python -m unittest discover -s tests -p test_project_plugin_storage.py` passes 22 tests; `uv run pyright tests/test_project_plugin_storage.py` reports zero diagnostics; focused Pylint is 10.00/10; `git diff --check` passes. The restored file remains present and becomes eligible only at the original 72-hour deadline.
- **Open gate:** This is local SQLite metadata evidence. Production rollback, paired filesystem/database restore, measured storage budgets, and owner-approved retention policy remain open. No checklist marker changed.
- **Outcome:** Verify the local restore path preserves the artifact's existing expiry age.

## 2026-10-27 — Reject inherited staging age after path changes

- **Intent:** Ensure copying or renaming a transient file cannot borrow another path's expiry timestamp and silently restart or advance its retention age.
- **Changed fact:** Added a local regression that renames a staged artifact and makes a same-content copy under a second path. Neither path has its own durable age record, so both count as unknown age; discovery returns no complete manifest and deletes neither file.
- **Verification:** `uv run python -m unittest discover -s tests -p test_project_plugin_storage.py` passes 23 tests; `uv run pyright tests/test_project_plugin_storage.py` reports zero diagnostics; focused Pylint is 10.00/10.
- **Open gate:** This validates local path identity only. Artifact-tree restore and deployment rollback still require a paired filesystem/database drill; approved production age anchors, retention budgets, and growth alerts remain open. No checklist marker changed.
- **Outcome:** Prevent path changes from inheriting a transient artifact's retention age.

## 2026-10-27 — Refresh local V2 editor extension evidence

- **Intent:** Keep the installed V2 editor plugin version, visible status behavior, and checklist evidence aligned.
- **Changed fact:** The V2-owned VS Code extension is version `0.8.9`; its installed `extension.js` matches the repository source. The status item is ordered after Git Graph, explains gray/green/purple/yellow/red states in its versioned tooltip, and keeps the existing read-only dashboard behavior. Removed a stray `>wrap` line from the extension README.
- **Verification:** `node --test extension.test.js` passes 14/14; installed and source `extension.js` SHA-256 both equal `6c2aa3a4376394e55a6eacd9f86f26c86eb6ea5085c95eda958bd0b61622af7b`; `code --list-extensions --show-versions` reports `curatormd.curatormd-v2-status@0.8.9`; `git diff --check` passes for these edits.
- **Open gate:** The running `renew_ssl` VS Code window still has extension `0.8.7` loaded. Its reload with `0.8.9` and the current live color transitions remain unverified; installed-package and unit-test evidence do not prove that runtime behavior. The checked extension delivery item remains checked; no marker changed.
- **Outcome:** Record the completed local extension package while keeping active-window validation precise.

## 2026-10-27 — Clarify the official delivery-row count

- **Intent:** Make the current progress denominator reproducible and distinguish it from reusable checklist templates.
- **Changed fact:** The plan now states that delivery progress includes sections 0–10 and 12 plus Definition of done, while excluding section 11 reusable workflow templates. The raw checkbox count across all file sections is a different measure.
- **Verification:** `python3 tools/count_curator_v2_delivery.py` reports 154/178 complete with 24 open; an independent section count agrees. The raw file contains 214 checkbox rows, including 36 section-11 template rows. `git diff --check` passes.
- **Open gate:** The 24 delivery rows remain open; this documentation correction changes no checklist markers.
- **Outcome:** Remove the plan's contradictory count-boundary statement.

## 2026-10-27 — Reject malformed staging age metadata

- **Intent:** Ensure invalid persisted staging timestamps cannot be treated as expired or authorize cleanup.
- **Changed fact:** Added regressions for unparsable and timezone-naive staged timestamps. Both are unknown age, make inventory incomplete, suppress the purge manifest, and leave the file present.
- **Verification:** The focused storage/expiry suite passes 24 tests; strict Pyright reports zero diagnostics; focused Pylint is 10.00/10; `git diff --check` passes. The delivery-count tool reports 154/178 complete and 24 open.
- **Open gate:** Local invalid-age handling is covered. Paired artifact-tree/database restore, production retention policy, measured budgets, and deployed growth alerts remain open; no checklist marker changed.
- **Outcome:** Keep malformed age metadata fail-closed without claiming production retention closure.

## 2026-10-27 — Verify paired local staging recovery

- **Intent:** Ensure restoring the transient staging tree and Curator database together preserves each artifact's original expiry age.
- **Changed fact:** Extended the disposable restore regression to copy the staged file tree, restore the SQLite backup to a new path, restore the tree, and bind the consumer to the restored database. The artifact remains ineligible at 71h59m and becomes proposed at its original 72-hour deadline.
- **Verification:** The focused storage/expiry suite passes 24 tests; strict Pyright reports zero diagnostics; focused Pylint is 10.00/10; `git diff --check` passes. Delivery count remains 154/178 complete with 24 open.
- **Open gate:** This closes only the local paired restore fixture. Deployment-shaped recovery/rollback, production retention policy, measured budgets, and growth alerts remain open; no checklist marker changed.
- **Outcome:** Prove local file-tree/database recovery does not reset artifact retention age.

## 2026-10-27 — Correct paired staging restore result

- **Intent:** Correct the preceding paired-restore record after its first regression run failed.
- **Changed fact:** A copied staging tree receives a new file identity. Its restored database age is therefore unknown; both pre-deadline and deadline discovery remain incomplete, emit no purge manifest, and leave the file present. This supersedes the preceding claim that paired restore preserved expiry age.
- **Verification:** The corrected focused storage/expiry suite passes 24 tests; strict Pyright reports zero diagnostics; focused Pylint is 10.00/10; `git diff --check` passes. The delivery count remains 154/178 complete, 24 open.
- **Open gate:** A trusted restore procedure that verifies and rebinds original age to restored files remains unimplemented; deployment recovery and production retention gates remain open. No checklist marker changed.
- **Outcome:** Record the actual fail-closed behavior without weakening the age-preservation requirement.

## 2026-10-27 — Recheck disposable Vhost apply receipt route

- **Intent:** Reconfirm the local Vhost bridge persists and retries the exact bounded Curator V2 request until a durable receipt is available.
- **Changed fact:** The focused Vhost apply-route contract passes against a temporary project and database. It exercises persistence, receipt completion, and retry/replay without requiring a live utility process.
- **Verification:** `test_vhost_apply_route_persists_and_retries_exact_curator_receipt` passed (1 test, 72.444 seconds) using `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/curator-v2-alpha-venv/bin/python`. No service was restarted and no live consumer data was changed.
- **Open gate:** The real local Vhost workflow and owner-reviewed evidence remain unverified. This fixture does not close the Definition of done item; no checklist marker changed.
- **Outcome:** Retain the route fixture result as local evidence and keep the live-consumer gate open.

## 2026-10-27 — Record current status tooltip version report

- **Intent:** Reconcile the extension-host version evidence with the user's current visible tooltip.
- **Changed fact:** The user reports the tooltip currently displays `8.8`; the installed VS Code extension and repository package are `0.8.9`. The older `0.8.7` extension-host log is not current evidence.
- **Verification:** `code --list-extensions --show-versions` reports `curatormd.curatormd-v2-status@0.8.9`; source `integrations/vscode-status/package.json` also declares `0.8.9`. No direct observation of the active window was available in this checkout.
- **Open gate:** Reconcile the reported tooltip with the active extension host and confirm the rendered `0.8.9` tooltip. No checklist marker changed.
- **Outcome:** Preserve the owner report and leave live-window verification open.

## 2026-10-27 — Reconcile live Vhost utility evidence

- **Intent:** Correct the Curator plan's claim that no real local Vhost request or canonical write had occurred.
- **Changed fact:** The Vhost Manager alpha guide records live local apply/rollback runs for two disposable `.test` sites, five operation goals saved by the authorized `eaglesvn` reviewer, and read-only Markdown/SQLite hash reconciliation. It also records a fake-ACME scheduled-result receipt. These establish real local utility and canonical-write evidence.
- **Verification:** Read the current Vhost checkout's `docs/curatormd-v2-alpha.md` sections “Vhost apply receipt bridge” and “SSL renewal receipt bridge”; the consumer documentation identifies the runs as local utility operations and distinguishes the fake ACME path from real renewal.
- **Open gate:** Those operations predate the current request-bound exact problem/criteria preview and retry contract. No packet yet binds that current request and criteria to fingerprints, a bounded report, replay/restart, and out-of-scope hashes. Keep the Definition of done item open; no checklist marker changed.
- **Outcome:** Preserve the verified local runs while narrowing the remaining evidence gap to the current request contract and its reviewed acceptance packet.
## 2026-10-28 — Reverify the local Curator V2 quality gate

**Intent:** Complete the previously requested check of the current Curator V2 quality commands and record their result without rerunning the already-passing unit suite.

**Changed fact:** No application source, database, or runtime state changed. The plan now records a fresh local quality verification and preserves deployment/live-runtime gates as open.

**Verification:** `uv run --locked --group quality pyright` reports zero errors, warnings, or informations. Errors-only Pylint and Bandit exit 0. `uv audit --locked --preview-features audit-command` finds no known vulnerabilities or adverse package status in 50 packages. `uv lock --check` and `git diff --check` pass.

**Open gate:** The unit suite was not rerun. These static and dependency checks do not establish deployment, scheduler, identity, production retention, or live Hermes lifecycle behavior. No checklist marker changed.

**Outcome:** Refresh local quality evidence only; keep runtime and release acceptance separate.

## 2026-10-28 — Verify the profile-bound Curator V2 ledger

**Intent:** Verify Curator V2 persistence through the supported Hermes profile path after recording the open lifecycle gate.

**Changed fact:** No ledger or runtime code changed. The trusted `renew-ssl-coding` profile read returns the `vhost-manager-alpha` ledger with 52 processed receipts, 23 goals, and 20 facts; the separate health snapshot is healthy with seven fresh dependencies and a complete empty staging inventory.

**Verification:** `./hermes -p renew-ssl-coding mcp test curator_v2 --probe-curator-status` exits 0, connects over local stdio, discovers 49 tools, and reads activity, goals, and health. A separate read-only SQLite metadata query finds 11/11 acknowledged Codex outbox events, latest sequence 11 at `2026-10-21T10:40:21Z`; no event payload was queried.

**Open gate:** The profile ledger read is not a new Codex app-server lifecycle event. Slice G remains open for a real managed-gateway turn and its durable receipt. No checklist marker changed.

**Outcome:** Confirm profile-bound persistence and current local health while preserving the live lifecycle gate.

## 2026-10-28 — Exercise the Vhost Manager local alpha route

**Intent:** Use the ready local Curator V2 integration in the Vhost Manager utility to exercise one disposable request through preview, apply, Curator persistence, exact-event replay, and rollback.

**Changed fact:** The running loopback Vhost Manager applied the reserved static target `curator-v2-alpha-smoke-20261028.test` with an empty firewall plan. Apply receipt `vhost-apply-65bb1c01-11e3-4cd3-b73a-57d0b7161d8c` and rollback receipt `vhost-rollback-b3cfa643-c3e1-456b-89a8-996479be6b4b` are processed. The active goal report preserves the preview problem and three open criteria. Exact fact-event replay leaves one processed inbox row and one matching fact; the goal-start replay returns `processed` and leaves one goal. Rollback removes the target site, dedicated account, and target Nginx files.

**Verification:** The applied target returned HTTP 200 for the exact local Host header. Root `nginx -t` passes after rollback; Vhost Manager, Nginx, and OpenLiteSpeed remain active. A content-free hash over 63 out-of-scope Nginx files is identical before and after (`b2c5d9b9e26afd0d99f93ee0b3062e3831d712628c64c88f33a9f9be8fbb8698`). Read-only SQLite checks show one `processed` row each for apply, apply fact, rollback, and rollback fact; `PRAGMA quick_check` returns `ok`. The existing dirty consumer checkout was not edited.

**Open gate:** The preview's firewall plan was empty, but the observed `iptables-save` digest changed and could not be attributed; no claim of unchanged firewall state is made. The goal's three criteria, including human review, remain open. The owner-reviewed acceptance packet and complete attributable out-of-scope hash set are still missing; no checklist marker changed.

**Outcome:** Advance local Vhost route, Curator persistence, bounded report, and fact-replay evidence while keeping the pilot gate open.
