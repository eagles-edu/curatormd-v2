# Curator V2 release-gate ledger

This is a snapshot of verified repository evidence, not a deployment health
claim. Statuses describe the strongest evidence currently present in this
checkout. A passing local unit test cannot close a deployment or owner-approval
gate.

Local alpha candidate (2026-10-21): package metadata is `0.1.0a1`. The wheel
and source archive build successfully. The wheel installs into the isolated
Vhost Manager profile environment; Hermes tool discovery, a config-bound read,
and a separate-database write/replay smoke pass. The current locked V2 suite
passes 336 tests. Strict Pyright reports 0 diagnostics;
errors-only Pylint, Bandit, dependency audit, lock check, and `git diff --check`
pass. These are local checks on the alpha candidate worktree, not a hosted
release or deployment. GitHub Actions run
[39389283097](https://github.com/eagles-edu/curatormd-v2/actions/runs/39389283097)
passed on alpha commit `8733875`, including the Python 3.12/3.13/3.14 matrix,
blocking quality/security checks, and clean installed-wheel launcher
acceptance. The current local wheel is
`dist/curatormd_v2-0.1.0a1-py3-none-any.whl`; SHA-256 is
`cf06d826406bdd59e9390a196ac72f931345c499059ec9c56601516ca37db3af`.
The current unhosted worktree extends clean-wheel acceptance to all five
operational CLI entrypoints and a backup/restore-to-new-path round trip. The
YAML parses and the matching clean Python 3.12.3 smoke passes locally; no hosted
run covers this workflow edit yet.
GitHub Actions run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9`, including the three-version Python matrix, blocking quality/security jobs, and clean-wheel consumer launcher. Run [39392957765](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392957765) also passes on `0e98bf0` with the processed-v16-receipt regression included.
The docs-only follow-up run [39393130048](https://github.com/eagles-edu/curator-v2/actions/runs/39393130048) also passed. The isolated Vhost Manager profile has the installed alpha package, consumer-owned project hook, bounded MCP allowlist, and exact project write grant. The current wheel was reinstalled into that profile; Hermes MCP config lists 10 selected tools and a fresh stdio discovery connects and sees the server's 45-tool surface. Seven consumer tests pass against the refreshed package, including two-config cross-project denial and independent configured persistence in disposable repositories, an installed-wheel router invocation that processes only the configured Vhost project, and synthetic bounded hook delivery with receipt acknowledgment and content-canary exclusion. The isolated profile's installed `curatormd-v2-storage` command also passes its four focused backup/restore tests. On 2026-10-21, the profile-scoped gateway endpoint returned `state=ready`; the Hermes Core system service is active after the local integration update. Two profile sessions created Hermes session-to-goal bindings and bounded lifecycle outbox events, but Curator has no new live-session receipt and the earliest unacknowledged event has eight delivery attempts. These are local alpha checks, not a production runtime.
The installed V2 profile's configured SQLite store was checked read-only on
2026-10-20: schema version 17, `PRAGMA quick_check=ok`, one registered
`vhost-manager-alpha` project, one active goal, one fact, and two processed
event receipts with zero retained event-payload bytes. V2 `project_health`
returns `unknown` because the router, purge scheduler, host identity, human
review, and artifact-producer inventory probes have no observations. This is
V2 database and tool evidence; it does not establish live capture or a healthy
runtime.
Repository-wide Pylint convention/refactor/warning findings remain open.

Current live-route probe (2026-10-21): the Vhost hook now accepts the actual
JSON-text result shape from Hermes managed MCP; its seven installed-consumer
contracts pass. The installed Hermes runtime and profile hook are recoverable
from `/home/eaglesvn/.hermes/curator-v2-alpha-runtime-backup.0KzV1U`. The
profile endpoint is ready and tool discovery succeeds, but event acknowledgment
is not verified: Hermes outbox sequence 2 remains unacknowledged with eight
attempts, later sequence entries remain pending, and Curator retains only its
two earlier processed receipts. One focused Hermes shell-hook test fails in the
real-home profile-isolation case (52 passed, 2 skipped); the targeted
`hooks.entries` compatibility probe passes. Retention, identity, recovery, and
release approval remain open.

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
| A. Freeze contracts | in progress | Owner: Curator V2 core. Probe: locked unit suite, Pyright, and `git diff --check`. Expected: fixtures and runtime records validate, tests/type checks pass. Actual (2026-10-20): 335 tests pass locally on Python 3.12.3; strict Pyright reports 0 diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. Hosted CI run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9` across Python 3.12/3.13/3.14 and blocking quality/security jobs; run [39392957765](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392957765) also passes on `0e98bf0` with the processed-v16-receipt migration regression. The repository config pins `backend_api_version = 1` and its example validates against the machine-readable contract. MCP tool failures map through the sanitized version-1 error envelope, and subprocess tests prove denial messages omit exception details. | [Contract index](contracts-v1.md), [machine-readable v1 schemas](schemas/curator-v2-v1.schema.json), [schema tests](../tests/test_contract_schemas.py), [event types](../src/curatormd_v2/events.py), [error mapper](../src/curatormd_v2/errors.py), [MCP serializer](../src/curatormd_v2/mcp_server.py). Open: shared producer/backend compatibility tests, remote transport error integration, and owner policy approval. |
| B. Harden local domain | in progress | Owner: Curator V2 core. Probe: locked unit suite and Pyright. Expected: domain invariants and bounded/replay behavior pass. Actual: the current local suite has 335 passing tests on Python 3.12.3; Pyright reports 0 diagnostics. Deterministic property tests cover generated event encodings, incomplete completion claims, lifecycle revisions, parent/dependency gates, reopen orders, replay, and traversal rejection. API/MCP acceptance covers project authorization, both SDE dispositions, immutable receipts, inventory gating, canonical persistence, exact-artifact purge, truthful final status, and Hermes activity suppression/reopen ordering. Preliminary threat and evidence-trust contracts are documented, not substitutes for owner policy or real adapters. | [Domain records](../src/curatormd_v2/models.py), [service](../src/curatormd_v2/service.py), [store](../src/curatormd_v2/store.py), [lifecycle tests](../tests/test_lifecycle.py), [property/fuzz tests](../tests/test_property_fuzz.py), [concurrency tests](../tests/test_concurrency.py), [resource tests](../tests/test_resource_limits.py), [evidence trust contract](evidence-adapters-v1.md), [preliminary threat model](threat-model-v1.md), [migration tests](../tests/test_migrations.py). Open: deployment-owner privacy/threat review, real source integrations, deployment trust roots, and owner policy approval. |
| C. Storage and projection recovery | in progress | Owner: Curator V2 core. Probe: locked unit suite and migration fixtures. Expected: projection/purge retry invariants pass. Actual: migrations through v17 are covered, including v10-to-v11 registry/grant table creation, v11-to-v12 empty feedback-table creation without invented labels, v12-to-v13 shared rate-limit table creation, v13-to-v14 event disposition receipts, v14-to-v15 nullable fact source-event provenance, v15-to-v16 redaction of legacy purge exception details while preserving retry state, and v16-to-v17 semantic event-retry digests with retained-payload backfill. Existing backup/restore, purge retry, crash-after-delete, integrity, and Markdown reconciliation tests remain green. Read-authorized API/MCP reconciliation returns bounded paged goal statuses/hashes and project-wide orphan/malformed marker observations without changing either store; over-limit scans are explicit. Generated Markdown blocks now carry unkeyed SHA-256 checksums: accidental content edits are classified malformed and projection refuses replacement; an exact legacy block can be upgraded, but a stale unsealed block is preserved. This detects accidental edits, not malicious rewrites or which store is authoritative. | [Store](../src/curatormd_v2/store.py), [backup helpers](../src/curatormd_v2/backup.py), [migration tests](../tests/test_migrations.py), [Markdown tests](../tests/test_markdown_persistence.py), [API](../src/curatormd_v2/api.py), [MCP server](../src/curatormd_v2/mcp_server.py), [migration policy](schema-migrations-v1.md), [local recovery procedure](storage-recovery-v1.md). Open: authoritative-record policy, manual conflict resolution, production integrity/restore/migration drill, approved operator runbook. |
| D. Authenticated interfaces | in progress | Owner: Curator V2 core plus Hermes identity owner. Probe: durable access suite and MCP denial tests. Expected: default-deny API and exact project boundaries hold. Actual: persistent project registration, exact subject/project/action grants, revocations, suspension, audit, project-scoped pagination, content-free metrics, and SQLite request quotas are implemented and tested. The local launcher now enforces an active registration matching the loaded repository/config fingerprints and exact durable profile-subject grants on every request; the attended `curatormd-v2-access` CLI provisions this ledger outside MCP. CLI administrator attribution is only the local OS UID and is not human or Hermes authentication. The launcher still takes a profile assertion and Hermes context metadata is not cryptographic proof. | [API](../src/curatormd_v2/api.py), [project access](../src/curatormd_v2/project_access.py), [local access CLI](../src/curatormd_v2/access_cli.py), [store](../src/curatormd_v2/store.py), [access tests](../tests/test_project_access.py), [CLI tests](../tests/test_access_cli.py), [migration tests](../tests/test_migrations.py), [MCP tests](../tests/test_mcp_server.py), [rate limiter](../src/curatormd_v2/rate_limiter.py), [plugin config](project-plugin-v1.md), [plugin tests](../tests/test_project_plugin.py). Open: verified Hermes identity/role binding, deployment-grade admin identity and trusted fingerprint authority, remote/distributed rate limiting, deployment denial tests, owner-approved feedback retention/evaluation policy. |
| E. Durable routing and operations | in progress | Owner: Curator V2 core and future router operator. Probe: full Python 3.12/3.13/3.14 unit matrix plus API/MCP authorization tests. Expected: bounded local routing, retry/quarantine, source order, migration, queue visibility, and truthful local health pass; deployed operation remains separate. Actual: local event routing covers persisted retry backoff, quarantine, operator retry, ordering, cross-connection expiring claims and stale-owner fencing. The new `curatormd-v2-router` CLI runs one explicit bounded pass for a fixed list of validated repository configs; claims are restricted to those project IDs, leaving other projects untouched. Nine focused routing/CLI tests and the 335-test suite pass. This is a local one-shot operation, not an installed worker or scheduler. Local purge cleanup has persisted per-target backoff, bounded due selection, immediate authorized retry override, and visible retry deadlines/countdowns. Authenticated API/MCP health returns healthy only with explicit fresh host probes (<=60 seconds), empty queues/review/purge/staging, complete staging inventory, and remaining capacity; known backlogs/failures are degraded, missing/stale/failed probes unknown. Its event/review/purge/storage database observations share one SQLite read transaction; the bounded no-follow staging scan is separately observed. Authorized project metrics include fixed, content-free evidence rejection, trusted adapter error, and other failure categories for current failed/quarantined receipts. This is a local exposition snapshot, not a deployed scrape endpoint/dashboard/alert system. | [Router](../src/curatormd_v2/router.py), [event/purge store](../src/curatormd_v2/store.py), [health and metrics API](../src/curatormd_v2/api.py), [metrics renderer](../src/curatormd_v2/observability.py), [router tests](../tests/test_router.py), [API tests](../tests/test_api.py), [concurrency tests](../tests/test_concurrency.py), [purge tests](../tests/test_purge.py), [migration tests](../tests/test_migrations.py), [MCP tests](../tests/test_mcp_server.py). Open: production event and purge schedulers, host probe adapters that supply fresh timestamped observations, scrape endpoint, dashboard/alert delivery, storage/lag budgets, restart/load/failure-injection/deployment probes. |
| F. Reusable consumer plugin | local consumer integration verified; pilot/release gates open | Owner: Curator V2 core plus each pilot-repository owner. Probe: locked suite plus consumer integration. Actual: Vhost Manager has the installed alpha package, isolated V2 staging/persistence/database paths, a consumer-owned hook, and a bounded writable Hermes profile grant. Its seven consumer tests pass, including two-config cross-project denial and independent configured-target persistence, installed bounded router delivery, and synthetic bounded hook delivery with terminal receipt acknowledgment and turn-start/turn-end ordering/replay; content canaries are excluded from SQLite and sidecars. Earlier hosted alpha CI runs and local quality checks are recorded above; the current full Curator suite has 335 tests. No application-code change was needed for the V2 plugin acceptance; other dirty Vhost application changes are outside this alpha evidence. | [Plugin boundary](../src/curatormd_v2/project_plugin.py), [config loader](../src/curatormd_v2/project_config.py), [plugin contract](project-plugin-v1.md), [consumer tests](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_contract.py). Open: second real consumer; real app producer; out-of-root inventory coverage; retention policy; network-filesystem lock semantics; authenticated Hermes identity/profile binding; trusted evidence adapters; canonical consumer persistence; real interactive cross-project isolation; rollback and release approval. |
| G. Hermes Core integration | local alpha wired; production gates open | Owner: Hermes Core. Actual: Hermes Core source includes the managed MCP hook adapter, durable profile-local outbox, exact acknowledgment handling, and root-account Host Steward. Vhost Manager's isolated profile has the consumer hook, bounded `curator_v2` MCP allowlist, and exact project write grant; MCP config validation, fresh stdio discovery, and all seven consumer tests pass. Synthetic tests exercise managed-MCP delivery and duplicate-receipt acknowledgment using disposable state. On 2026-10-21, 57 focused gateway-hook, MCP trust-gating, and Host Steward tests passed together; Hermes `scripts/check` passed all 12 checks with zero blocking/advisory findings. The gateway runs manually; no real Vhost event was delivered through it. | [Ownership contract](../AGENTS.md), [event contract](event-contract-v1.md), [Hermes project adapter](../src/curatormd_v2/hermes_hook.py), [consumer hook test](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_contract.py). Open: real Vhost session; authenticated profile/project authorization; production router/scheduler; canonical consumer persistence; runtime privacy proof; deployment recovery and retention approval; hosted Hermes CI. |
| H. Host Steward validation | in progress | Owner: Hermes Core Host Steward. Probe: host-side inventory/approval/cleanup test suite plus deployment recovery probes. Expected: cleanup is separately approved, verified, receipted, and cannot write Curator knowledge. Actual: the opt-in root-account plugin provides bounded metadata inventory, exact configured-target proposals, fixed approval-gated cleanup, free-space/service checks, bounded receipts, and interrupted-cleanup reconciliation. The latest commit `832b90fd31` adds stable service-unit bindings to configured-target snapshots; it does not prove that a named service caused target writes. Twenty-one focused Host Steward tests pass, and Hermes `python3 scripts/check` passes all 12 checks. A new regression verifies the plugin exposes only its declared host tools and that read paths plus an approval-authorized disposable-cache cleanup leave a consumer history sentinel unchanged. Tests use disposable paths and doubles; no live host cleanup is claimed. | [Ownership contract](../AGENTS.md). Hermes source is in `/home/eaglesvn/.hermes/hermes-agent` on `codex/curator-v2-hermes-integration-upstream`, pushed to the existing `eagles-edu/hermes-agent` fork. Open: measured service/host owner attribution; authenticated approver identity; live account installation; cross-process supervision; production recovery/deployment tests. |
| I. V2 pilot and release | local alpha package installed; live gates open | Owner: Curator V2 core plus Vhost Manager pilot owner. Actual: isolated package/profile, consumer hook, bounded write grant, and synthetic managed-MCP/outbox receipt smoke pass; the shared gateway is running manually, but no live Vhost event has traversed it; seven consumer tests pass. No real Vhost Manager application session, canonical consumer Markdown write, rollback drill, or release sign-off is evidenced. | [Alpha scope](alpha-v2.md), [consumer operations](consumer-operations-v1.md), [failure recovery](component-failure-recovery-v2.md). Open: real app producer workflow; deployment rollback; runbooks/release approval; retention/cleanup policy; authenticated identity; explicit V2 capture authorization. V1 is outside V2. |
| CI quality/security | alpha candidate hosted checks passed | Owner: Curator V2 core. Probe: commands in [CI policy](ci-v2.md). Expected: Python matrix, strict typing, blocking Pylint errors, Bandit, lockfile audit, and clean-wheel launcher test pass. Actual: local `0.1.0a1` candidate passes 335 tests on Python 3.12.3, the isolated-profile installed-wheel MCP lifecycle check, strict Pyright, errors-only Pylint, Bandit, dependency audit, lock check, and `git diff --check`. GitHub Actions run [39389283097](https://github.com/eagles-edu/curatormd-v2/actions/runs/39389283097) passes on alpha commit `8733875`, with the Python 3.12/3.13/3.14 matrix and installed-wheel acceptance; GitHub Actions run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9`, and run [39392957765](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392957765) passes on `0e98bf0` with the processed-v16-receipt regression included. | [Workflow](../.github/workflows/ci.yml), [tool pins and lock](../uv.lock), [CI policy](ci-v2.md). Open: repository-wide Pylint convention/refactor/warning cleanup. |

The successful hosted runs on `8733875`, `3ce95b9`, and `0e98bf0` close hosted source/package CI for the
`0.1.0a1` alpha candidate. The Vhost Manager alpha package and bounded profile
binding are installed locally; its profile-scoped endpoint is ready, but live event delivery is unverified.
Production deployment, identity, retention-policy, real-session verification,
and owner-approval gates remain open.

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
[`ci-v2.md`](ci-v2.md). They pass locally and hosted run [39392957765](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392957765) covers the newest migration-test commit `0e98bf0`.

## Entry, recovery, and approval register

| Slice | Entry condition | Recovery path if probe fails | Approval boundary |
| --- | --- | --- | --- |
| A | Existing typed records and v1 event/config parsers; external compatibility is not claimed. | Correct the fixture or its owning contract; preserve strict parser behavior and rerun the contract suite. | Product owner approves policy and any future stable external contract. |
| B | Slice A contract decisions are accepted for the local implementation. | Stop the failing transition; preserve SQLite state; repair with a tested migration/rollback instead of editing data ad hoc. | No retention-policy or destructive migration decision is inferred from tests. |
| C | SQLite and Markdown projection are present; read-only per-goal comparison reports missing/synced/divergent/malformed states through authenticated API/MCP reads. No conflict repair or authoritative-store decision is made. | Leave purge pending, preserve canonical files and receipts, then use an integrity-checked backup and owner-directed reconciliation procedure. | Any data restore or manual canonical rewrite requires the repository owner. |
| D | In-process API/MCP facade exists with reject-all default authorization. | Keep access fail-closed; remove/disable an untrusted binding and repair the host identity adapter before retry. | Host owner approves identity mapping and granted project/action scopes. |
| E | Local durable inbox is present; no router/operator deployment exists. | Pause producers, retain failed inbox receipts, repair the consumer, and replay stable event IDs; never discard backlog to restore green status. | Operator approval is required before quarantine release or any event disposition that drops data. |
| F | Local Vhost Manager alpha binding is active with a bounded write grant and installed consumer hook; real app producer, canonical persistence, and rollback remain unverified. | Disable only the V2 project binding, retaining V2 receipts, staged evidence, and consumer records; then repair and repeat the alpha checks. | Pilot owner confirms the live workflow, persistence targets, retention policy, and rollback path. |
| G | Vhost Manager local alpha route passes synthetic hook-to-managed-MCP delivery and terminal outbox acknowledgment; real interactive identity and production routing remain open. | Keep the bounded V2 binding disabled if its exact project/profile route cannot be verified; preserve pending events for replay after repair. | Hermes profile owner approves event scope and project binding; raw transcript persistence remains prohibited. |
| H | Host Steward is a Hermes Core concern and is absent from this repository. | Use the existing managed host cleanup workflow or leave disk findings pending; do not substitute Curator purge for host cleanup. | A human approves each exact host cleanup proposal; the executor cannot self-approve. |
| I | Vhost Manager's alpha package and bounded project write grant are installed in its local profile; synthetic delivery passes, while live profile delivery, real application workflow, and release gates remain open. V1 is outside V2 scope. | Disable only the V2 project binding; retain V2 receipts, staged evidence, and consumer canonical records for owner-directed recovery. | Pilot owner confirms real-session workflow, exact persistence targets, retention policy, and rollback path before broader use. |

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
