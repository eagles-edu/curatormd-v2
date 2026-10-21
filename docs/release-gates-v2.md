# Curator V2 release-gate ledger

This is a snapshot of verified repository evidence, not a deployment health
claim. Statuses describe the strongest evidence currently present in this
checkout. A passing local unit test cannot close a deployment or owner-approval
gate.

Current source snapshot (2026-10-21): Curator commit `94bb816` is pushed to
`main`; the locked local suite passes 354 tests and the GitHub Actions run
[39628941504](https://github.com/eagles-edu/curatormd-v2/actions/runs/39628941504)
passes the Python 3.12/3.13/3.14 matrix, strict typing, errors-only Pylint,
Bandit, dependency audit, and clean-wheel acceptance. Hermes Core source head
`9b8fc71e30` is clean; the focused lifecycle-hook, profile-usage, and
Codex-app-server integration files pass 61 tests, and `python3 scripts/check`
passes all 12 checks. The V2 checklist is 138/211 complete (73 open).
The authenticated Curator V2 goal-list call currently returns
`unauthenticated: Trusted Hermes profile context is required`; live tracker
persistence is unverified. These source checks do not close authenticated
identity, owner retention policy, production scheduling/recovery, or live
application workflow gates.

The clean-wheel acceptance now also starts the installed MCP launcher and
asserts `sde_assess` exposes optional `impact` and `retrieval_value` fields
without exposing `project_id`. The local Python 3.12 wheel install and both
installed-launcher checks pass. Hosted CI for this new assertion is pending.

Local alpha candidate (2026-10-21): package metadata is `0.1.0a1`. The wheel
and source archive build successfully. The wheel installs into the isolated
Vhost Manager profile environment; Hermes tool discovery, a config-bound read,
and a separate-database write/replay smoke pass. The current locked V2 suite
passes 340 tests. Strict Pyright reports 0 diagnostics;
errors-only Pylint, Bandit, dependency audit, lock check, and `git diff --check`
pass. These are local checks on the alpha candidate worktree, not a hosted
release or deployment. GitHub Actions run
[39389283097](https://github.com/eagles-edu/curatormd-v2/actions/runs/39389283097)
passed on alpha commit `8733875`, including the Python 3.12/3.13/3.14 matrix,
blocking quality/security checks, and clean installed-wheel launcher
acceptance. The earlier repository artifact at
`dist/curatormd_v2-0.1.0a1-py3-none-any.whl` has SHA-256
`fcce3c0e343c79a7e800153131e0dd4b43a02087055dd6a6a257f9cbe01e688f`; the
latest installed profile wheel is recorded below.
The current unhosted worktree extends clean-wheel acceptance to all five
operational CLI entrypoints and a backup/restore-to-new-path round trip. The
YAML parses and the matching clean Python 3.12.3 smoke passes locally; no hosted
run covers this workflow edit yet.
GitHub Actions run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9`, including the three-version Python matrix, blocking quality/security jobs, and clean-wheel consumer launcher. Run [39392957765](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392957765) also passes on `0e98bf0` with the processed-v16-receipt regression included.
The docs-only follow-up run [39393130048](https://github.com/eagles-edu/curator-v2/actions/runs/39393130048) also passed. The isolated Vhost Manager profile has the installed alpha package, consumer-owned project hook, bounded MCP allowlist, and exact project write grant. Hermes MCP config lists 11 selected tools and a fresh stdio discovery connects and sees the server's 45-tool surface; Hermes reports transport auth as `none`. Seven consumer tests pass against the installed package, including two-config cross-project denial and independent configured persistence in disposable repositories, an installed-wheel router invocation that processes only the configured Vhost project, and synthetic bounded hook delivery with receipt acknowledgment and content-canary exclusion. The isolated profile's installed `curatormd-v2-storage` command also passes its four focused backup/restore tests. These are local alpha checks, not a production runtime.
The installed V2 profile's configured SQLite store was checked read-only on
2026-10-21: schema version 17, `PRAGMA quick_check=ok`, one registered
`vhost-manager-alpha` project, one active goal, two facts, and ten processed
event receipts with zero received, failed, or quarantined events. Earlier live
route records show the nine Hermes source events acknowledged; the V2 activity
read confirms no received events pending processing. V2 `project_health`
remains `unknown` because the router, purge
scheduler, host identity, human review, and artifact-producer inventory probes
have no observations. This is V2 database and local route evidence; it does not
establish a Vhost application workflow or production health.
The current repository wheel was reinstalled into the isolated Vhost profile on
2026-10-21 after detecting three stale installed modules. Its 32 Python module
hashes now match the source tree; MCP discovery sees 45 tools and all seven
Vhost consumer contracts pass against that wheel. This is local alpha
deployment evidence, not authenticated identity or production readiness.
Repository-wide Pylint convention/refactor/warning findings remain open.

Latest local source/package recheck (2026-10-21): the rebuilt profile wheel
SHA-256 is `ad6ee0e214757e007765dafa806539be3fcea6fdfb2134a48484ad08dcfa1192`.
The full locked Curator suite passes 340 tests; strict Pyright, errors-only
Pylint, Bandit, locked dependency audit, and lock check pass. All seven
installed Vhost consumer contracts pass against the current profile package,
and MCP discovery exposes 45 tools. Hermes Core `python3 scripts/check` passes
all 12 checks. This does not exercise a Vhost application request or canonical
application-target write; `project_health` remains `unknown`, and identity,
retention, production recovery, and release approval remain open.

The isolated profile was reinstalled from the latest wheel after the router
and maintenance CLIs adopted the store context manager. The installed source
hashes for both CLIs and `cli_args.py` match the Curator V2 worktree. All seven
Vhost consumer contracts pass, and Hermes MCP discovery still exposes 45
tools. Wheel SHA-256:
`ad6ee0e214757e007765dafa806539be3fcea6fdfb2134a48484ad08dcfa1192`.

Current local alpha checks (2026-10-21): the installed `0.1.0a1` wheel passes
the clean Python 3.12 launcher and operational-command acceptance, including a
backup/restore round trip. The installed Vhost profile connects and discovers
45 tools; all seven Vhost consumer contracts pass. Hermes Core's focused
gateway-hook, durable-outbox, and MCP trust-gating tests pass 42 cases, and
`python3 scripts/check` passes all 12 checks. A fresh profile gateway ensure
returns `state=ready`; read-only V2 status reports 12 processed receipts, zero
received events pending processing, and
`project_health=unknown`. This verifies the local alpha route and consumer
adapter, not an interactive Vhost application workflow. Authenticated
identity, retention, production scheduling, recovery, and release approval
remain open.

Latest read-only profile status after a one-shot Hermes Codex app-server turn
(2026-10-21) reports 12 processed receipts, zero received/failed/quarantined
events, one goal, and two deduplicated facts. Hermes source sequences 10 and 11
were each acknowledged once; Curator processed/applied both and cleared their
payload JSON. The V2 database passes `PRAGMA quick_check=ok`. This session
verifies the profile CLI route, while Hermes gateway status reports only the
default-profile PID. The Vhost application workflow, live canonical target
write, authenticated identity, production health, retention, recovery, and
release approval remain open; `project_health` is `unknown`.

The Vhost profile allowlist now includes the read-only `goal_report` tool (12
selected Curator V2 tools total); the profile config is backed up at
`/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/config/config.yaml.before-goal-report-20261021T104917Z`.
Hermes MCP connection/discovery still succeeds, but the one-shot model request
to `goal_report` remains rejected after this change. This confirms the missing
selection was a configuration gap but not the complete cause; do not count
tool discovery as a working read call.

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
| C. Storage and projection recovery | in progress | Owner: Curator V2 core. Probe: locked unit suite and migration fixtures. Expected: projection/purge retry invariants pass. Actual: migrations through v18 are covered, including v10-to-v11 registry/grant table creation, v11-to-v12 empty feedback-table creation without invented labels, v12-to-v13 shared rate-limit table creation, v13-to-v14 event disposition receipts, v14-to-v15 nullable fact source-event provenance, v15-to-v16 redaction of legacy purge exception details while preserving retry state, v16-to-v17 semantic event-retry digests with retained-payload backfill, and v17-to-v18 nullable SDE proposal context. Existing backup/restore, purge retry, crash-after-delete, integrity, and Markdown reconciliation tests remain green. Read-authorized API/MCP reconciliation returns bounded paged goal statuses/hashes and project-wide orphan/malformed marker observations without changing either store; over-limit scans are explicit. Generated Markdown blocks now carry unkeyed SHA-256 checksums: accidental content edits are classified malformed and projection refuses replacement; an exact legacy block can be upgraded, but a stale unsealed block is preserved. This detects accidental edits, not malicious rewrites or which store is authoritative. | [Store](../src/curatormd_v2/store.py), [backup helpers](../src/curatormd_v2/backup.py), [migration tests](../tests/test_migrations.py), [Markdown tests](../tests/test_markdown_persistence.py), [API](../src/curatormd_v2/api.py), [MCP server](../src/curatormd_v2/mcp_server.py), [migration policy](schema-migrations-v1.md), [local recovery procedure](storage-recovery-v1.md). Open: authoritative-record policy, manual conflict resolution, production integrity/restore/migration drill, approved operator runbook. |
| D. Authenticated interfaces | in progress | Owner: Curator V2 core plus Hermes identity owner. Probe: durable access suite and MCP denial tests. Expected: default-deny API and exact project boundaries hold. Actual: persistent project registration, exact subject/project/action grants, revocations, suspension, audit, project-scoped pagination, content-free metrics, and SQLite request quotas are implemented and tested. The local launcher now enforces an active registration matching the loaded repository/config fingerprints and exact durable profile-subject grants on every request; the attended `curatormd-v2-access` CLI provisions this ledger outside MCP. CLI administrator attribution is only the local OS UID and is not human or Hermes authentication. The launcher still takes a profile assertion and Hermes context metadata is not cryptographic proof. | [API](../src/curatormd_v2/api.py), [project access](../src/curatormd_v2/project_access.py), [local access CLI](../src/curatormd_v2/access_cli.py), [store](../src/curatormd_v2/store.py), [access tests](../tests/test_project_access.py), [CLI tests](../tests/test_access_cli.py), [migration tests](../tests/test_migrations.py), [MCP tests](../tests/test_mcp_server.py), [rate limiter](../src/curatormd_v2/rate_limiter.py), [plugin config](project-plugin-v1.md), [plugin tests](../tests/test_project_plugin.py). Open: verified Hermes identity/role binding, deployment-grade admin identity and trusted fingerprint authority, remote/distributed rate limiting, deployment denial tests, owner-approved feedback retention/evaluation policy. |
| E. Durable routing and operations | in progress | Owner: Curator V2 core and future router operator. Probe: full Python 3.12/3.13/3.14 unit matrix plus API/MCP authorization tests. Expected: bounded local routing, retry/quarantine, source order, migration, queue visibility, and truthful local health pass; deployed operation remains separate. Actual: local event routing covers persisted retry backoff, quarantine, operator retry, ordering, cross-connection expiring claims and stale-owner fencing. The new `curatormd-v2-router` CLI runs one explicit bounded pass for a fixed list of validated repository configs; claims are restricted to those project IDs, leaving other projects untouched. Nine focused routing/CLI tests and the 336-test suite pass. This is a local one-shot operation, not an installed worker or scheduler. Local purge cleanup has persisted per-target backoff, bounded due selection, immediate authorized retry override, and visible retry deadlines/countdowns. Authenticated API/MCP health returns healthy only with explicit fresh host probes (<=60 seconds), empty queues/review/purge/staging, complete staging inventory, and remaining capacity; known backlogs/failures are degraded, missing/stale/failed probes unknown. Its event/review/purge/storage database observations share one SQLite read transaction; the bounded no-follow staging scan is separately observed. Authorized project metrics include fixed, content-free evidence rejection, trusted adapter error, and other failure categories for current failed/quarantined receipts. This is a local exposition snapshot, not a deployed scrape endpoint/dashboard/alert system. | [Router](../src/curatormd_v2/router.py), [event/purge store](../src/curatormd_v2/store.py), [health and metrics API](../src/curatormd_v2/api.py), [metrics renderer](../src/curatormd_v2/observability.py), [router tests](../tests/test_router.py), [API tests](../tests/test_api.py), [concurrency tests](../tests/test_concurrency.py), [purge tests](../tests/test_purge.py), [migration tests](../tests/test_migrations.py), [MCP tests](../tests/test_mcp_server.py). Open: production event and purge schedulers, host probe adapters that supply fresh timestamped observations, scrape endpoint, dashboard/alert delivery, storage/lag budgets, restart/load/failure-injection/deployment probes. |
| F. Reusable consumer plugin | local consumer integration verified; pilot/release gates open | Owner: Curator V2 core plus each pilot-repository owner. Probe: locked suite plus consumer integration. Actual: Vhost Manager has the installed alpha package, isolated V2 staging/persistence/database paths, a consumer-owned hook, and a bounded writable Hermes profile grant. Its seven consumer tests pass, including two-config cross-project denial, independent configured-target persistence, installed bounded router delivery, and a composed disposable checkout flow from bounded hook events through the installed MCP launcher and processed receipts to the configured Markdown projection; reconciliation passes, content canaries are excluded, and an out-of-scope target is unchanged. The current full Curator suite has 340 tests; strict Pyright, errors-only Pylint, Bandit, dependency audit, lock check, and `git diff --check` pass. No application-code change was needed for the V2 plugin acceptance; other dirty Vhost application changes are outside this alpha evidence. | [Plugin boundary](../src/curatormd_v2/project_plugin.py), [config loader](../src/curatormd_v2/project_config.py), [plugin contract](project-plugin-v1.md), [consumer tests](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_contract.py). Open: second real consumer; real app producer; out-of-root inventory coverage; retention policy; network-filesystem lock semantics; authenticated Hermes identity/profile binding; trusted evidence adapters; live canonical Vhost persistence; real interactive cross-project isolation; rollback and release approval. |
| G. Hermes Core integration | local alpha route verified; production gates open | Owner: Hermes Core. Actual: Hermes Core source includes the managed MCP hook adapter, durable profile-local outbox, exact acknowledgment handling, and root-account Host Steward. The isolated `renew-ssl-coding` profile connects to the installed Curator V2 server (45 tools). After correcting the Vhost hook to match the durable event envelope, a real profile session replayed sequences 1-9; all are acknowledged, the current project/goal binding is persisted, and Curator's Vhost inbox cursor is 9 with 10 processed receipts. All nine source events have `applied` disposition; two compact intent/change facts are linked to the active Vhost goal. SQLite `quick_check=ok`; source-event inbox rows retain no payload JSON. Seven Vhost contracts and Hermes `scripts/check` (12 checks) pass; the focused Hermes integration suite passes 58 tests. A later one-shot profile CLI session delivered sequences 10-11, both acknowledged once and processed/applied; read-only V2 SQLite now shows cursor 11, 12 processed/applied receipts, one goal, two facts, and no payload JSON for the new receipts. A Vhost-owned disposable harness additionally loads actual Hermes Core HookRegistry/HookContext, calls the installed Curator stdio server through Hermes managed MCP, acknowledges and replays two lifecycle events, and reconciles the configured consumer projection; see [harness](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_hermes_managed_integration.py). Current Hermes Core source-head verification (`9b8fc71e30`) passes 61 focused gateway-hook, profile-usage, and Codex app-server tests plus all 12 `scripts/check` checks. This composes the local managed-MCP path but does not launch the gateway service or exercise the application workflow, cryptographic identity, or production authorization. | [Ownership contract](../AGENTS.md), [event contract](event-contract-v1.md), [Hermes project adapter](../src/curatormd_v2/hermes_hook.py), [consumer hook test](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_contract.py). The latest evidenced profile-bound V2 `project_health` read (2026-10-21) is `unknown` with zero pending/failed/quarantined events and unknown required probes for event router, purge scheduler, host identity, human review, and artifact-producer inventory; this is not green readiness. Open: authenticated profile/project identity; production event/purge router and scheduler; live canonical Vhost Markdown write; production recovery and retention approval; hosted Hermes CI. |
| H. Host Steward validation | in progress | Owner: Hermes Core Host Steward. Probe: host-side inventory/approval/cleanup test suite plus deployment recovery probes. Expected: cleanup is separately approved, verified, receipted, and cannot write Curator knowledge. Actual: the opt-in root-account plugin provides bounded metadata inventory, exact configured-target proposals, fixed approval-gated cleanup, free-space/service checks, bounded receipts, and interrupted-cleanup reconciliation. The latest commit `832b90fd31` adds stable service-unit bindings to configured-target snapshots; it does not prove that a named service caused target writes. Twenty-one focused Host Steward tests pass, and Hermes `python3 scripts/check` passes all 12 checks. A new regression verifies the plugin exposes only its declared host tools and that read paths plus an approval-authorized disposable-cache cleanup leave a consumer history sentinel unchanged. Tests use disposable paths and doubles; no live host cleanup is claimed. | [Ownership contract](../AGENTS.md). Hermes source is in `/home/eaglesvn/.hermes/hermes-agent` on `codex/curator-v2-hermes-integration-upstream`, pushed to the existing `eagles-edu/hermes-agent` fork. Open: measured service/host owner attribution; authenticated approver identity; live account installation; cross-process supervision; production recovery/deployment tests. |
| I. V2 pilot and release | local alpha route exercised; release gates open | Owner: Curator V2 core plus Vhost Manager pilot owner. Actual: the isolated profile, consumer hook, bounded write grant, and installed V2 package are active. A real `renew-ssl-coding` profile session produced acknowledged Hermes outbox events and processed Curator receipts through the managed gateway; the profile binding and bounded payload disposal were checked in persisted state. The 7-test consumer contract covers configured persistence and isolation in disposable repositories. This does not exercise a user workflow inside the Vhost Manager application, write its canonical Markdown target, or prove rollback. | [Alpha scope](alpha-v2.md), [consumer operations](consumer-operations-v1.md), [failure recovery](component-failure-recovery-v2.md). Open: Vhost application workflow; deployment rollback; production runbooks/release approval; retention/cleanup policy; authenticated identity; explicit V2 capture authorization. V1 is outside V2. |
| CI quality/security | alpha candidate hosted checks passed | Owner: Curator V2 core. Probe: commands in [CI policy](ci-v2.md). Expected: Python matrix, strict typing, blocking Pylint errors, Bandit, lockfile audit, and clean-wheel launcher test pass. Actual: current local `0.1.0a1` candidate passes 340 tests on Python 3.12.3, the isolated-profile installed-wheel consumer contracts, strict Pyright, errors-only Pylint, Bandit, dependency audit, lock check, and `git diff --check`. GitHub Actions run [39389283097](https://github.com/eagles-edu/curatormd-v2/actions/runs/39389283097) passes on alpha commit `8733875`, with the Python 3.12/3.13/3.14 matrix and installed-wheel acceptance; GitHub Actions run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9`, and run [39392957765](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392957765) passes on `0e98bf0` with the processed-v16-receipt regression included. | [Workflow](../.github/workflows/ci.yml), [tool pins and lock](../uv.lock), [CI policy](ci-v2.md). Open: repository-wide Pylint convention/refactor/warning cleanup. |

The successful hosted runs on `8733875`, `3ce95b9`, and `0e98bf0` close hosted source/package CI for the
`0.1.0a1` alpha candidate. The Vhost Manager alpha package and bounded profile
binding are installed locally. The local Hermes-to-Curator route has processed
12 receipts, while the Vhost application workflow and live canonical target
write remain unverified. Production deployment, authenticated identity,
retention policy, recovery, and owner-approval gates remain open.

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
