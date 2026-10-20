# Curator V2 release-gate ledger

This is a snapshot of verified repository evidence, not a deployment health
claim. Statuses describe the strongest evidence currently present in this
checkout. A passing local unit test cannot close a deployment or owner-approval
gate.

Local alpha candidate (2026-10-20): package metadata is `0.1.0a1`. The wheel
and source archive build successfully. The wheel installs into the isolated
Vhost Manager profile environment; Hermes tool discovery, a config-bound read,
and a separate-database write/replay smoke pass. The locked V2 suite passes
324 tests. Strict Pyright reports 0 diagnostics;
errors-only Pylint, Bandit, dependency audit, lock check, and `git diff --check`
pass. These are local checks on the alpha candidate worktree, not a hosted
release or deployment. GitHub Actions run
[39389283097](https://github.com/eagles-edu/curatormd-v2/actions/runs/39389283097)
passed on alpha commit `8733875`, including the Python 3.12/3.13/3.14 matrix,
blocking quality/security checks, and clean installed-wheel launcher
acceptance. The current local wheel is
`dist/curatormd_v2-0.1.0a1-py3-none-any.whl`; SHA-256 is
`73205fffd9faab67c4f6b8b13011a46ccfde1e263c54108e46337ddbc9d7753b`.
GitHub Actions run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9`, including the three-version Python matrix, blocking quality/security jobs, and clean-wheel consumer launcher.
Repository-wide Pylint convention/refactor/warning findings remain open.

GitHub Actions run
[39388057201](https://github.com/eagles-edu/curatormd-v2/actions/runs/39388057201)
passed against commit `5c23c65`, including the 3.12/3.13/3.14 matrix,
quality/security checks, and clean-wheel launcher acceptance test. It does not
cover the current alpha candidate. Hosted CI, consumer installation, identity,
retention, deployment, and release approval remain open.
The
Hermes translator and local inbox/router acceptance test in
[`test_hermes_events.py`](../tests/test_hermes_events.py) are reference-adapter
evidence, not live Hermes identity, hook delivery, or deployment verification.
The reviewer-authorized `sde_review_packet` composes selected candidate
facts/evidence with a point-in-time hashed staging manifest; MCP acceptance
proves read-only callers are denied and the packet manifest matches the separate
inventory read. The latest full suite supersedes earlier per-slice counts in
this ledger.

| Slice | Status | Owner, probe, expected/actual | Evidence and remaining exit condition |
| --- | --- | --- | --- |
| A. Freeze contracts | in progress | Owner: Curator V2 core. Probe: locked unit suite, Pyright, and `git diff --check`. Expected: fixtures and runtime records validate, tests/type checks pass. Actual (2026-10-20): 324 tests pass locally on Python 3.12.3; strict Pyright reports 0 diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. Hosted CI run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9` across Python 3.12/3.13/3.14 and blocking quality/security jobs. The repository config pins `backend_api_version = 1` and its example validates against the machine-readable contract. MCP tool failures map through the sanitized version-1 error envelope, and subprocess tests prove denial messages omit exception details. | [Contract index](contracts-v1.md), [machine-readable v1 schemas](schemas/curator-v2-v1.schema.json), [schema tests](../tests/test_contract_schemas.py), [event types](../src/curatormd_v2/events.py), [error mapper](../src/curatormd_v2/errors.py), [MCP serializer](../src/curatormd_v2/mcp_server.py). Open: shared producer/backend compatibility tests, remote transport error integration, and owner policy approval. |
| B. Harden local domain | in progress | Owner: Curator V2 core. Probe: locked unit suite and Pyright. Expected: domain invariants and bounded/replay behavior pass. Actual: the current local suite has 324 passing tests on Python 3.12.3; Pyright reports 0 diagnostics. Deterministic property tests cover generated event encodings, incomplete completion claims, lifecycle revisions, parent/dependency gates, reopen orders, replay, and traversal rejection. API/MCP acceptance covers project authorization, both SDE dispositions, immutable receipts, inventory gating, canonical persistence, exact-artifact purge, truthful final status, and Hermes activity suppression/reopen ordering. Preliminary threat and evidence-trust contracts are documented, not substitutes for owner policy or real adapters. | [Domain records](../src/curatormd_v2/models.py), [service](../src/curatormd_v2/service.py), [store](../src/curatormd_v2/store.py), [lifecycle tests](../tests/test_lifecycle.py), [property/fuzz tests](../tests/test_property_fuzz.py), [concurrency tests](../tests/test_concurrency.py), [resource tests](../tests/test_resource_limits.py), [evidence trust contract](evidence-adapters-v1.md), [preliminary threat model](threat-model-v1.md), [migration tests](../tests/test_migrations.py). Open: deployment-owner privacy/threat review, real source integrations, deployment trust roots, and owner policy approval. |
| C. Storage and projection recovery | in progress | Owner: Curator V2 core. Probe: locked unit suite and migration fixtures. Expected: projection/purge retry invariants pass. Actual: migrations through v17 are covered, including v10-to-v11 registry/grant table creation, v11-to-v12 empty feedback-table creation without invented labels, v12-to-v13 shared rate-limit table creation, v13-to-v14 event disposition receipts, v14-to-v15 nullable fact source-event provenance, v15-to-v16 redaction of legacy purge exception details while preserving retry state, and v16-to-v17 semantic event-retry digests with retained-payload backfill. Existing backup/restore, purge retry, crash-after-delete, integrity, and Markdown reconciliation tests remain green. Read-authorized API/MCP reconciliation returns bounded paged goal statuses/hashes and project-wide orphan/malformed marker observations without changing either store; over-limit scans are explicit. Generated Markdown blocks now carry unkeyed SHA-256 checksums: accidental content edits are classified malformed and projection refuses replacement; an exact legacy block can be upgraded, but a stale unsealed block is preserved. This detects accidental edits, not malicious rewrites or which store is authoritative. | [Store](../src/curatormd_v2/store.py), [backup helpers](../src/curatormd_v2/backup.py), [migration tests](../tests/test_migrations.py), [Markdown tests](../tests/test_markdown_persistence.py), [API](../src/curatormd_v2/api.py), [MCP server](../src/curatormd_v2/mcp_server.py), [migration policy](schema-migrations-v1.md), [local recovery procedure](storage-recovery-v1.md). Open: authoritative-record policy, manual conflict resolution, production integrity/restore/migration drill, approved operator runbook. |
| D. Authenticated interfaces | in progress | Owner: Curator V2 core plus Hermes identity owner. Probe: durable access suite and MCP denial tests. Expected: default-deny API and exact project boundaries hold. Actual: persistent project registration, exact subject/project/action grants, revocations, suspension, audit, project-scoped pagination, content-free metrics, and SQLite request quotas are implemented and tested. The local launcher now enforces an active registration matching the loaded repository/config fingerprints and exact durable profile-subject grants on every request; the attended `curatormd-v2-access` CLI provisions this ledger outside MCP. CLI administrator attribution is only the local OS UID and is not human or Hermes authentication. The launcher still takes a profile assertion and Hermes context metadata is not cryptographic proof. | [API](../src/curatormd_v2/api.py), [project access](../src/curatormd_v2/project_access.py), [local access CLI](../src/curatormd_v2/access_cli.py), [store](../src/curatormd_v2/store.py), [access tests](../tests/test_project_access.py), [CLI tests](../tests/test_access_cli.py), [migration tests](../tests/test_migrations.py), [MCP tests](../tests/test_mcp_server.py), [rate limiter](../src/curatormd_v2/rate_limiter.py), [plugin config](project-plugin-v1.md), [plugin tests](../tests/test_project_plugin.py). Open: verified Hermes identity/role binding, deployment-grade admin identity and trusted fingerprint authority, remote/distributed rate limiting, deployment denial tests, owner-approved feedback retention/evaluation policy. |
| E. Durable routing and operations | in progress | Owner: Curator V2 core and future router operator. Probe: full Python 3.12/3.13/3.14 unit matrix plus API/MCP authorization tests. Expected: bounded local routing, retry/quarantine, source order, migration, queue visibility, and truthful local health pass; deployed operation remains separate. Actual: local event routing covers persisted retry backoff, quarantine, operator retry, ordering, cross-connection expiring claims and stale-owner fencing. Local purge cleanup has persisted per-target backoff, bounded due selection, immediate authorized retry override, and visible retry deadlines/countdowns. Authenticated API/MCP health returns healthy only with explicit fresh host probes (<=60 seconds), empty queues/review/purge/staging, complete staging inventory, and remaining capacity; known backlogs/failures are degraded, missing/stale/failed probes unknown. Its event/review/purge/storage database observations share one SQLite read transaction; the bounded no-follow staging scan is separately observed. Authorized project metrics include fixed, content-free evidence rejection, trusted adapter error, and other failure categories for current failed/quarantined receipts. This is a local exposition snapshot, not a deployed scrape endpoint/dashboard/alert system. | [Router](../src/curatormd_v2/router.py), [event/purge store](../src/curatormd_v2/store.py), [health and metrics API](../src/curatormd_v2/api.py), [metrics renderer](../src/curatormd_v2/observability.py), [router tests](../tests/test_router.py), [API tests](../tests/test_api.py), [concurrency tests](../tests/test_concurrency.py), [purge tests](../tests/test_purge.py), [migration tests](../tests/test_migrations.py), [MCP tests](../tests/test_mcp_server.py). Open: production event and purge schedulers, host probe adapters that supply fresh timestamped observations, scrape endpoint, dashboard/alert delivery, storage/lag budgets, restart/load/failure-injection/deployment probes. |
| F. Reusable consumer plugin | in progress | Owner: Curator V2 core plus each pilot-repository owner. Probe: locked suite plus owner-approved installation in a consumer. Expected: config/scope/projection tests pass. Actual: local config scope and secret policy, fixture consumers, goal-scoped staging, canonical projection/purge ordering, packaged MCP launcher, the Hermes project hook adapter, and the attended access CLI are covered. Current local delta: 324 tests on Python 3.12.3; strict Pyright, errors-only Pylint, Bandit, and dependency audit pass. The new regression stages all six supported temporary artifact classes through the reference producer API and confirms a complete inventory. The prior local `0.1.0a1` wheel passes its clean installed-launcher acceptance; GitHub Actions run [39389283097](https://github.com/eagles-edu/curatormd-v2/actions/runs/39389283097) passes the matrix on alpha commit `8733875`, and run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9`. The Vhost Manager checkout has a local alpha profile binding with five read-only tools and separate V2 staging, persistence, and database paths. The refreshed alpha wheel passes Hermes `mcp test` and a bound `goal_list` read; a separate V2 lifecycle smoke database verifies goal/fact writes, fresh-process retries, and conflict on changed content. Its activity survives reopening; a finish request without criterion evidence remains open and the report shows the open TODO. Health remains unknown for five unobserved operational dependencies. The application source and V1 persistence were untouched; authenticated identity and live gateway activation remain open. GPTMD-specific compatibility checks remain historical local-wheel/disposable-database evidence only. | [Plugin boundary](../src/curatormd_v2/project_plugin.py), [config loader](../src/curatormd_v2/project_config.py), [plugin contract](project-plugin-v1.md), [producer entrypoint](../src/curatormd_v2/producer_cli.py), [access CLI](../src/curatormd_v2/access_cli.py), [plugin tests](../tests/test_project_plugin.py), [producer tests](../tests/test_producer_cli.py), [MCP lifecycle test](../tests/test_mcp_server.py). Open: supported release package and install/upgrade/rollback path; pilot-owner approval; real producer adapters and out-of-root inventory coverage; retention policy/thresholds; network-filesystem lock semantics; authenticated Hermes identity/profile binding; trusted evidence adapters; canonical persistence through an approved consumer; live Hermes-bound cross-project runtime isolation. |
| G. Hermes Core integration | in progress | Owner: Hermes Core. Probe: inspect app-server/router wiring and exercise a real authorized lifecycle event. Expected: only typed, project-scoped events reach Curator. Actual: source on `codex/curator-v2-hermes-integration-upstream` commit `832b90fd31` includes the managed MCP hook adapter, durable profile-local outbox, exact acknowledgment handling, and root-account Host Steward. The 12-test gateway hook module previously exercised Hermes' production managed-MCP code path with an in-memory session and confirmed processed receipt, outbox acknowledgment, and host-derived metadata. The feature branch is pushed; no hosted Hermes CI run is listed. These are local source tests, not a live gateway event or authenticated identity. | [Ownership contract](../AGENTS.md), [event contract](event-contract-v1.md), [local MCP binding](mcp-tools-v1.md#local-hermes-profile-launcher), [reference translator](../src/curatormd_v2/hermes_events.py), [Hermes project adapter](../src/curatormd_v2/hermes_hook.py), [adapter acceptance test](../tests/test_hermes_hook.py). Hermes source/test evidence is in `/home/eaglesvn/.hermes/hermes-agent` and is not versioned here. Open: hosted CI/PR review; live hook installation; authenticated profile/project authorization; production router/scheduler; separate-process deployment replay; runtime privacy proof; deployment acceptance. |
| H. Host Steward validation | in progress | Owner: Hermes Core Host Steward. Probe: host-side inventory/approval/cleanup test suite plus deployment recovery probes. Expected: cleanup is separately approved, verified, receipted, and cannot write Curator knowledge. Actual: the opt-in root-account plugin provides bounded metadata inventory, exact configured-target proposals, fixed approval-gated cleanup, free-space/service checks, bounded receipts, and interrupted-cleanup reconciliation. The latest commit `832b90fd31` adds stable service-unit bindings to configured-target snapshots; it does not prove that a named service caused target writes. Twenty focused Host Steward tests pass, and Hermes `python3 scripts/check` passes all 12 checks. Tests use disposable paths and doubles; no live host cleanup is claimed. | [Ownership contract](../AGENTS.md). Hermes source is in `/home/eaglesvn/.hermes/hermes-agent` on `codex/curator-v2-hermes-integration-upstream`, pushed to the existing `eagles-edu/hermes-agent` fork. Open: measured service/host owner attribution; authenticated approver identity; live account installation; cross-process supervision; production recovery/deployment tests; explicit negative proof that Host Steward cannot write Curator project knowledge. |
| I. Pilot, cutover, release | not started | Owner: product owner plus V1/V2 operators. Probe: approved inventory, pilot acceptance suite, rollback drill, and sign-off record. Expected: every artifact and gate has a disposition and recovery path. Actual: deployment-level probes have not run. | [Cutover checklist](curator-v2-plan.md#10-v1-cutover-and-cleanup). Open: V1 inventory/disposition, pilot/rollback drills, runbooks/release notes, retention/cleanup sign-off, explicit capture approval. |
| CI quality/security | alpha candidate hosted checks passed | Owner: Curator V2 core. Probe: commands in [CI policy](ci-v2.md). Expected: Python matrix, strict typing, blocking Pylint errors, Bandit, lockfile audit, and clean-wheel launcher test pass. Actual: local `0.1.0a1` candidate passes 324 tests on Python 3.12.3, the isolated-profile installed-wheel MCP lifecycle check, strict Pyright, errors-only Pylint, Bandit, dependency audit, lock check, and `git diff --check`. GitHub Actions run [39389283097](https://github.com/eagles-edu/curatormd-v2/actions/runs/39389283097) passes on alpha commit `8733875`, with the Python 3.12/3.13/3.14 matrix and installed-wheel acceptance; GitHub Actions run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9` with the Python 3.12/3.13/3.14 matrix, quality/security checks, and installed-wheel acceptance. The new v16 processed-receipt fallback regression is local-only until hosted CI runs on its commit. | [Workflow](../.github/workflows/ci.yml), [tool pins and lock](../uv.lock), [CI policy](ci-v2.md). Open: hosted CI for the new migration regression; repository-wide Pylint convention/refactor/warning cleanup. |

The successful hosted runs on `8733875` and `3ce95b9` close hosted source/package CI for the
`0.1.0a1` alpha candidate. Deployment, identity, retention-policy, consumer
pilot, and owner-approval gates remain open.

The new local restart regression,
`DurableEventRouterTests.test_ordered_pending_events_resume_after_store_restart_and_replay`,
closes and reopens SQLite while a sequenced event waits behind its missing
predecessor, then verifies ordered processing and idempotent same-ID replay.
This is a store/router reconstruction test, not a process-kill, load, or
deployment recovery drill.

`DurableEventRouterTests.test_expired_claim_recovers_after_router_process_is_killed`
also kills a worker with `SIGKILL` after its claim transaction commits; after
lease expiry, a fresh router process recovers and applies the event once. The
test then snapshots/restores SQLite to a new file and verifies the receipt and
goal survived. The six-test router and four-test backup modules pass together.
This does not close production scheduler, load, filesystem/power-loss, or
multi-host locking gates.

The exact locked test command for the local slices is
`uv run --locked --group test python -m unittest discover -s tests -v`.

The current locked CI quality/security commands are documented in
[`ci-v2.md`](ci-v2.md). They have passed locally; hosted CI for the newest migration-test commit remains open until a run against
that exact commit succeeds.

## Entry, recovery, and approval register

| Slice | Entry condition | Recovery path if probe fails | Approval boundary |
| --- | --- | --- | --- |
| A | Existing typed records and v1 event/config parsers; external compatibility is not claimed. | Correct the fixture or its owning contract; preserve strict parser behavior and rerun the contract suite. | Product owner approves policy and any future stable external contract. |
| B | Slice A contract decisions are accepted for the local implementation. | Stop the failing transition; preserve SQLite state; repair with a tested migration/rollback instead of editing data ad hoc. | No retention-policy or destructive migration decision is inferred from tests. |
| C | SQLite and Markdown projection are present; read-only per-goal comparison reports missing/synced/divergent/malformed states through authenticated API/MCP reads. No conflict repair or authoritative-store decision is made. | Leave purge pending, preserve canonical files and receipts, then use an integrity-checked backup and owner-directed reconciliation procedure. | Any data restore or manual canonical rewrite requires the repository owner. |
| D | In-process API/MCP facade exists with reject-all default authorization. | Keep access fail-closed; remove/disable an untrusted binding and repair the host identity adapter before retry. | Host owner approves identity mapping and granted project/action scopes. |
| E | Local durable inbox is present; no router/operator deployment exists. | Pause producers, retain failed inbox receipts, repair the consumer, and replay stable event IDs; never discard backlog to restore green status. | Operator approval is required before quarantine release or any event disposition that drops data. |
| F | Repository config and adapters are locally testable; no consumer has installed this V2 package/config pair through an owner-approved rollout. | Disable the project binding, retain its canonical Markdown and staged evidence, then repair config/path bindings and rerun isolation checks. | Pilot repository owner approves installation and persistence targets. |
| G | Hermes Core has separate ownership; no Curator route is enabled. | Keep Curator disconnected and continue the existing Codex workflow; repair mapping/authorization in Hermes before replaying events. | Hermes profile owner approves event scope and project binding; raw transcript persistence remains prohibited. |
| H | Host Steward is a Hermes Core concern and is absent from this repository. | Use the existing managed host cleanup workflow or leave disk findings pending; do not substitute Curator purge for host cleanup. | A human approves each exact host cleanup proposal; the executor cannot self-approve. |
| I | No V1 inventory, pilot, or capture authorization is recorded here. | Roll back to read-only V1 canonical Markdown with V2 capture disabled; preserve all V2 receipts and migration manifests. | Product owner approves artifact disposition, retention policy, pilot, and capture enablement. |

The per-slice owner, concrete probe, expected result, observed result, and linked
code/test evidence are recorded in the status table above. Where no deployment
probe has run, the actual result explicitly says so; this ledger does not
authorize destructive changes.

## Slice A work record

- Problem: contract material existed across several documents and typed code,
  but consumers lacked one index and a checked-in example that the strict
  parser actually accepts.
- Success criteria: identify authoritative contract sources and actual
  compatibility limits; define machine-readable v1 event, goal, fact, SDE,
  receipt, error, and plugin data shapes; validate examples and representative
  runtime records; define a stable sanitized error envelope; leave production
  transport serializers and integrations open until implemented.
- Commands: `uv run --frozen --group test python -m unittest discover -s tests -v`,
  `pyright`, and `git diff --check`. Pyright must resolve dependencies from the
  repository `.venv`.
- Expected result: all tests and strict typing pass; fixtures and runtime
  records validate; whitespace check is clean. Pylint is also run as an open
  quality gate.
- Actual result: 158 unit tests passed; `pyright` passed with 0 errors after
  configuring its project virtual environment; `git diff --check` passed.
  Environment-adjusted repository-wide Pylint exited 28 from convention,
  refactor, and warning findings (no fatal/error findings); it remains an open
  quality gate and is not a passing gate. The repository-wide errors-only
  Pylint check for `src/curatormd_v2` and `tests` passed.
- Recovery: fix the fixture or contract mismatch in its owning test/doc; do not
  relax strict version/unknown-field validation to make an example pass.
- Approval: product-owner approval is still required before a production
  compatibility or retention commitment.
