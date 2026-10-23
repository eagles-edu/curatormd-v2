# Curator V2 release-gate ledger

This is a snapshot of verified repository evidence, not a deployment health
claim. Statuses describe the strongest evidence currently present in this
checkout. A passing local unit test cannot close a deployment or owner-approval
gate.

Current delivery checklist snapshot (2026-10-23): 139/178 complete, 39 open,
using the counting rule in [`curator-v2-plan.md`](curator-v2-plan.md).

Historical source snapshot (2026-10-21): Curator commit `3a4314b` is pushed to
`main`; GitHub Actions run
[39638397374](https://github.com/eagles-edu/curatormd-v2/actions/runs/39638397374)
passes the Python 3.12/3.13/3.14 matrix, strict typing, blocking Pylint,
Bandit, dependency audit, and clean-wheel acceptance. The Curator **Delivery
checklist** is 126/153 complete (27 open), using the progress definition in
[`curator-v2-plan.md`](curator-v2-plan.md); reusable work-cycle and acceptance
templates are excluded. The isolated `renew-ssl-coding` V2 database was read
with SQLite read-only mode: schema 18, `quick_check=ok`, one active registered
project, one active goal, two facts, 12 processed event receipts, zero retained
event payload JSON bytes, and no SDE or purge rows. This is local persistence
evidence, not a health probe. The current Hermes Core checkout's
`hermes mcp test curator_v2 --probe-curator-status` connects through the
configured local stdio server using host-injected profile/session context,
discovers 48 tools, and returns activity, paginated goal total, and aggregate
health. Its latest read reports 12 processed receipts, one goal, two facts,
goal-list total 1, and health `unknown` with gates for the router, purge
scheduler, host identity, human review, and artifact-producer inventory. A
read-only SQLite check reports schema 22, `quick_check=ok`, one project, one
goal, two facts, 12 inbox receipts, and zero pending payload scrubs. The
attended alpha reviewer has exact
`local-uid:1000` project `read` and `review` grants; the installed reviewer
queue command succeeds and returns no pending candidates. This verifies the
selected local `eaglesvn` UID path only. The direct Codex `goal_list` call
without Hermes context still returns
`unauthenticated: Trusted Hermes profile context is required`; the Hermes
profile transport still has `Auth: none`, so the successful profile-context
read does not authenticate a human. Full Hermes identity, live healthy status,
and application-workflow persistence remain unverified. Production retention
policy, production scheduling/recovery, and live application workflow gates
remain open.

The source wheel recorded at the isolated-profile checkpoint (SHA-256
`e268f1eddce61c44b1f132f93c6afad842a5ddd39e9e791cabd7091c25fdc2d0`) is
installed in the isolated `renew-ssl-coding` alpha environment. At that
checkpoint, all 38 Python module hashes matched the Curator V2 source tree, and
seven disposable Vhost consumer contracts passed against the wheel using the
typed project-registration request. This is checkpoint-specific package and
consumer-contract evidence; current profile installation has not been
reverified here. No Vhost application request or canonical application-target
write was exercised.

The system-installed Hermes CLI connects to the alpha server and discovers
48 tools. `Auth: none` indicates there are no conventional MCP credentials;
that display does not show Hermes' separate host-context path. The configured
`renew-ssl-coding` profile opts into `hermes_context`, and the installed
managed-MCP call path attaches host-derived profile and session metadata to
tool requests. The focused Hermes trust-gating tests pass (2 tests), and the
checkout CLI status probe reads V2 activity through the same configured
profile. `mcp test` itself only connected and discovered tools; it did not
exercise a protected tool call. An actual gateway tool call, live Vhost event
delivery, and Hermes-authenticated person identity remain open.

Hermes Core source head `9b8fc71e30` is clean; the focused lifecycle-hook,
profile-usage, and Codex-app-server integration files pass 61 tests, and
`python3 scripts/check` passes all 12 checks. These source checks do not close
the Curator identity, retention, deployment, or live-runtime gates.

The clean-wheel acceptance now also starts the installed MCP launcher and
asserts `sde_assess` exposes optional `impact` and `retrieval_value` fields
without exposing `project_id`. The local Python 3.12 wheel install and both
installed-launcher checks pass, and the hosted wheel-install job passes this
new assertion.

The same wheel (`b141087b8f9359097d5246195d8c9a09cc60a8fae37dfb128539956c267f94b3`)
is now installed in the isolated `renew-ssl-coding` alpha virtualenv. All 34
package module hashes match source; seven Vhost consumer contracts and the
Hermes-managed disposable lifecycle harness pass. Profile MCP discovery
connects with `auth=none` and lists 46 tools. A read-only profile-store check
reports schema 18, `quick_check=ok`, one goal, two facts, 12 processed receipts,
and zero retained event payload JSON bytes. This is local alpha package and
storage evidence; interactive identity/approval and the Vhost application
workflow remain unverified.

Local alpha candidate (2026-10-21): package metadata is `0.1.0a1`. The wheel
and source archive build successfully. The wheel installs into the isolated
Vhost Manager profile environment; Hermes tool discovery, a config-bound read,
and a separate-database write/replay smoke pass. At that alpha-candidate checkpoint, the locked V2 suite passed 340 tests. Strict Pyright reports 0 diagnostics;
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
A subsequent unhosted worktree revision extended clean-wheel acceptance to
all five operational CLI entrypoints and a backup/restore-to-new-path round trip. The
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
At the 2026-10-21 profile check, the repository wheel was reinstalled into
the isolated Vhost profile after three stale installed modules were detected.
Its 32 Python module hashes matched the source tree at that checkpoint; MCP
discovery saw 45 tools and all seven Vhost consumer contracts passed against
that wheel. This is local alpha
deployment evidence, not authenticated identity or production readiness.
Repository-wide Pylint convention/refactor/warning findings remain open.

Latest local source/package recheck (2026-10-21): the rebuilt profile wheel
SHA-256 is `ad6ee0e214757e007765dafa806539be3fcea6fdfb2134a48484ad08dcfa1192`.
The full locked Curator suite passes 340 tests; strict Pyright, errors-only
Pylint, Bandit, locked dependency audit, and lock check pass. All seven
installed Vhost consumer contracts passed against that profile package,
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
| B. Harden local domain | verified locally; broader gates open | Owner: Curator V2 core. Probe: locked unit suite and Pyright. Expected: domain invariants and bounded/replay behavior pass. Actual at the 2026-10-20 validation checkpoint: the local suite had 335 passing tests on Python 3.12.3; Pyright reported 0 diagnostics. Deterministic property tests cover generated event encodings, incomplete completion claims, lifecycle revisions, parent/dependency gates, reopen orders, replay, and traversal rejection. API/MCP acceptance covers project authorization, both SDE dispositions, immutable receipts, inventory gating, canonical persistence, exact-artifact purge, truthful final status, and Hermes activity suppression/reopen ordering. Preliminary threat and evidence-trust contracts are documented, not substitutes for owner policy or real adapters. The plan records local Slice B closure with a 377-test run and a later 397-test full-suite quality checkpoint; neither closes the remaining source-to-sink privacy, production migration, deployment trust, or owner-policy gates. | [Domain records](../src/curatormd_v2/models.py), [service](../src/curatormd_v2/service.py), [store](../src/curatormd_v2/store.py), [lifecycle tests](../tests/test_lifecycle.py), [property/fuzz tests](../tests/test_property_fuzz.py), [concurrency tests](../tests/test_concurrency.py), [resource tests](../tests/test_resource_limits.py), [evidence trust contract](evidence-adapters-v1.md), [preliminary threat model](threat-model-v1.md), [migration tests](../tests/test_migrations.py). Open: deployment-owner privacy/threat review, real source integrations, deployment trust roots, and owner policy approval. |
| C. Storage and projection recovery | in progress | Owner: Curator V2 core. Probe: locked unit suite and migration fixtures. Expected: projection/purge retry invariants pass. Actual: migrations through v18 cover v10-to-v11 registry/grant tables, v11-to-v12 empty feedback tables without invented labels, v12-to-v13 shared rate limits, v13-to-v14 event disposition receipts, v14-to-v15 fact source-event provenance, v15-to-v16 purge-error redaction, v16-to-v17 semantic event-retry digests, and v17-to-v18 SDE proposal context. The source checkpoint recorded on 2026-10-22 was schema v22: v19 adds staging artifact age, v20 adds expiry purge receipts, v21 adds separate cleanup authorizations, and v22 adds a content-free WAL-scrub queue and one database-wide checkpoint receipt for a nonempty legacy inbox without copying or deleting payload rows. Follow-up local source now reaches schema v32: v23-v30 add purge-target identity, stale-approval, dependency-map, and reacquisition-action safeguards; v31 adds project-registration compare-and-set revisions and ordered audit revisions; v32 adds stable transition IDs for exact retry recovery. Local tests cover busy-reader retry, restart retry, payload absence from the WAL after successful truncation, and preservation of the legacy payload row during migration. Existing backup/restore, purge retry, crash-after-delete, integrity, and Markdown reconciliation tests remain documented local coverage. Read-authorized API/MCP reconciliation returns bounded paged goal statuses/hashes and project-wide orphan/malformed marker observations without changing either store; over-limit scans are explicit. Generated Markdown blocks use unkeyed SHA-256 checksums: accidental edits are classified malformed and projection refuses replacement; exact legacy blocks can be upgraded, while stale unsealed blocks are preserved. This detects accidental edits, not malicious rewrites. A proposed record-authority/conflict policy is documented but not approved. | [Store](../src/curatormd_v2/store.py), [backup helpers](../src/curatormd_v2/backup.py), [migration tests](../tests/test_migrations.py), [WAL scrub tests](../tests/test_event_payload_scrub.py), [Markdown tests](../tests/test_markdown_persistence.py), [API](../src/curatormd_v2/api.py), [MCP server](../src/curatormd_v2/mcp_server.py), [migration policy](schema-migrations-v1.md), [local recovery procedure](storage-recovery-v1.md). Open: product/repository-owner decision on the authority model and recovery-record fields; trusted approver and durable conflict-resolution receipts; owner-reviewed disposable-data exercise of every recovery decision-table row; production integrity/restore/migration/rollback drill; owner-approved staging byte/file and age policy with alert thresholds, human-approved cleanup receipts, and `PROJECT-STAGING-BUDGET`; owner-approved permanent-data inventory and budgets for project registry/access, rate-limit buckets, event cursors, staging-age metadata, expiry/cleanup/scrub records, and shared database/WAL/backup overhead under `PERMANENT-DATA-BUDGET`; owner-reviewed inbox archive/compaction and restore case `EVENT-RETENTION-RECOVERY`; approved operator runbook. |
| D. Authenticated interfaces | in progress | Owner: Curator V2 core plus Hermes identity owner. Probe: durable access suite and MCP denial tests. Expected: default-deny API and exact project boundaries hold. Actual: persistent project registration, exact subject/project/action grants, revocations, suspension, audit, project-scoped pagination, content-free metrics, and SQLite request quotas are implemented and tested. Local follow-up (2026-10-23): project config updates, suspension, and reactivation compare the reviewed registry revision, increment it atomically, and record that revision in the audit history; stale revisions leave state and audit unchanged. Schema v32 adds stable transition IDs; exact config/status retries recover the original audit receipt without another revision, while conflicting ID reuse is rejected. Schemas v33-v36 add separate consumer binding state, source-epoch re-enrollment, exact inventory-bound drain, retirement tombstones, and terminal event disposition. Finalization waits for all source events to reach durable receipts or authorized terminal disposition. This reference-store behavior remains a local slice of the full lifecycle. The local launcher enforces active registration/config fingerprints and exact grants; the attended CLI provisions this ledger outside MCP. CLI administrator attribution is only the local OS UID and is not human or Hermes authentication. Open: verified Hermes identity/role binding, trusted fingerprint authority, external staging-inventory authority, production reactivation review, remote/distributed rate limiting, deployment denial tests, and owner-approved feedback retention/evaluation policy. Schema v37 locally binds reactivation to a fresh packet covering registry/config, binding/source epoch, grants, cursors, backlog, purge work, and a complete staging scan; the CLI rejects stale review and persists the packet in the audit receipt. The 74 focused tests and local quality checks pass, but this does not prove deployed identity or a production workflow. | [API](../src/curatormd_v2/api.py), [project access](../src/curatormd_v2/project_access.py), [local access CLI](../src/curatormd_v2/access_cli.py), [store](../src/curatormd_v2/store.py), [access tests](../tests/test_project_access.py), [CLI tests](../tests/test_access_cli.py), [migration tests](../tests/test_migrations.py), [MCP tests](../tests/test_mcp_server.py), [rate limiter](../src/curatormd_v2/rate_limiter.py), [plugin config](project-plugin-v1.md), [plugin tests](../tests/test_project_plugin.py). |
| E. Durable routing and operations | in progress | Owner: Curator V2 core and future router operator. Probe: full Python 3.12/3.13/3.14 unit matrix plus API/MCP authorization tests. Expected: bounded local routing, retry/quarantine, source order, migration, queue visibility, and truthful local health pass; deployed operation remains separate. Actual: local event routing covers persisted retry backoff, quarantine, operator retry, ordering, cross-connection expiring claims and stale-owner fencing. The `curatormd-v2-router` CLI runs one explicit bounded pass for a fixed list of validated repository configs; claims are restricted to those project IDs, leaving other projects untouched. Local project retirement tombstones and attended exact terminal disposition are implemented. The bounded lifecycle view reports project/binding/tombstone state, event counts, leases, unresolved digest, and terminal candidates from one SQLite snapshot. This remains a local one-shot operation, not a resident worker or production monitoring service. At the recorded local routing checkpoint, nine focused routing/CLI tests
and the 336-test suite passed. This is a local one-shot operation, not an installed worker or scheduler. Local purge cleanup has persisted per-target backoff, bounded due selection, immediate authorized retry override, and visible retry deadlines/countdowns. Authenticated API/MCP health returns healthy only with explicit fresh host probes (<=60 seconds), empty queues/review/purge/staging, complete staging inventory, and remaining capacity; known backlogs/failures are degraded, missing/stale/failed probes unknown. Its event/review/purge/storage database observations share one SQLite read transaction; the bounded no-follow staging scan is separately observed. Authorized project metrics include fixed, content-free evidence rejection, trusted adapter error, and other failure categories for current failed/quarantined receipts. This is a local exposition snapshot, not a deployed scrape endpoint/dashboard/alert system. | [Router](../src/curatormd_v2/router.py), [event/purge store](../src/curatormd_v2/store.py), [health and metrics API](../src/curatormd_v2/api.py), [metrics renderer](../src/curatormd_v2/observability.py), [router tests](../tests/test_router.py), [API tests](../tests/test_api.py), [concurrency tests](../tests/test_concurrency.py), [purge tests](../tests/test_purge.py), [migration tests](../tests/test_migrations.py), [MCP tests](../tests/test_mcp_server.py). Open: production event and purge schedulers, host probe adapters that supply fresh timestamped observations, scrape endpoint, dashboard/alert delivery, storage/lag budgets, restart/load/failure-injection/deployment probes; `EVENT-CAP-ALLOCATION` and `EVENT-RETENTION-RECOVERY` deployment scenarios. |
| F. Reusable consumer plugin | local consumer integration verified; pilot/release gates open | Owner: Curator V2 core plus each pilot-repository owner. Probe: locked suite plus consumer integration. Actual: Vhost Manager has the installed alpha package, isolated V2 staging/persistence/database paths, a consumer-owned hook, and a bounded writable Hermes profile grant. Disposable acceptance covers configured persistence, isolation, bounded hook delivery, exact retry, durable receipts, projection, and content-canary exclusion. Curator-local tests additionally cover inventory-bound drain, terminal disposition, retirement, and source-epoch re-enrollment. The Vhost application producer, live canonical workflow, and rollback remain unverified; other dirty Vhost application changes are outside this alpha evidence. | [Plugin boundary](../src/curatormd_v2/project_plugin.py), [config loader](../src/curatormd_v2/project_config.py), [plugin contract](project-plugin-v1.md), [lifecycle tests](../tests/test_project_access.py), [consumer tests](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_contract.py). Open: separate two-real-consumer generalization gate; real app producer plus owner-reviewed producer/source-to-class coverage for each pilot, with every source, class, and destination accounted for and each out-of-root artifact given an explicit owner disposition; production retention policy; [producer coverage sequence](curator-v2-plan.md#6-per-project-plugin-and-repository-boundary); network-filesystem lock semantics; authenticated Hermes identity/profile binding; trusted evidence adapters; live canonical Vhost persistence; real interactive cross-project isolation; rollback and release approval. |
| G. Hermes Core integration | local alpha route verified; production gates open | Owner: Hermes Core. Actual: Hermes Core source includes the managed MCP hook adapter, durable profile-local outbox, exact acknowledgment handling, and root-account Host Steward. The isolated `renew-ssl-coding` profile connects to the installed Curator V2 server (45 tools). After correcting the Vhost hook to match the durable event envelope, a real profile session replayed sequences 1-9; all are acknowledged, the current project/goal binding is persisted, and Curator's Vhost inbox cursor is 9 with 10 processed receipts. All nine source events have `applied` disposition; two compact intent/change facts are linked to the active Vhost goal. SQLite `quick_check=ok`; source-event inbox rows retain no payload JSON. The earlier integration checkpoint records seven Vhost contracts, Hermes `scripts/check` (12 checks), and a 58-test focused Hermes integration suite passing; the row does not record the source revision for the 58-test result. A later one-shot profile CLI session delivered sequences 10-11, both acknowledged once and processed/applied; read-only V2 SQLite now shows cursor 11, 12 processed/applied receipts, one goal, two facts, and no payload JSON for the new receipts. A Vhost-owned disposable harness additionally loads actual Hermes Core HookRegistry/HookContext, calls the installed Curator stdio server through Hermes managed MCP, acknowledges and replays two lifecycle events, and reconciles the configured consumer projection; see [harness](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_hermes_managed_integration.py). Hermes Core source-head verification at `9b8fc71e30` passed 61 focused gateway-hook, profile-usage, and Codex app-server tests plus all 12 `scripts/check` checks; this is historical evidence for the verified commit. This composes the local managed-MCP path but does not launch the gateway service or exercise the application workflow, cryptographic identity, or production authorization. | [Ownership contract](../AGENTS.md), [event contract](event-contract-v1.md), [Hermes project adapter](../src/curatormd_v2/hermes_hook.py), [consumer hook test](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_contract.py). The latest profile-bound status probe (2026-10-22) validates all three activity, paginated-goal, and health responses against the configured `hermes_project_id`; it returns 12 processed receipts, goal total 1, and project health `unknown` with required probes unknown for event router, purge scheduler, host identity, human review, and artifact-producer inventory. Direct Codex MCP reads without Hermes context remain `unauthenticated`; the profile's `Auth: none` is not human authentication. This is local profile/project-bound evidence, not a live Vhost workflow or green readiness. Open: authenticated profile/project identity; production event/purge router and scheduler; live canonical Vhost Markdown write; production recovery and retention approval; owner-approved project-usage source/window/budget/alert policy with incomplete-coverage handling and `PROJECT-USAGE-BUDGET`; provider capture and billing reconciliation evidence; hosted Hermes CI. |
| H. Host Steward validation | local validation complete; deployment gates open | Owner: Hermes Core Host Steward. Probe: host-side inventory/approval/cleanup suite and Hermes source checks. Expected: cleanup is separately approved, verified, receipted, and cannot write Curator knowledge. Actual: the opt-in root-account plugin provides bounded metadata inventory, exact configured-target proposals, fixed approval-gated cleanup, free-space/service checks, bounded receipts, and interrupted-cleanup reconciliation. The recorded focused Host Steward suite passed 15 tests, including interrupted-receipt reconciliation; Hermes `python3 scripts/check` passed all 12 checks at that verification checkpoint. This row does not pin that 15-test result to a source revision; see the Hermes source-check freshness note below before using it as current-head evidence. Earlier regressions verify exact-target approval, managed cleanup, post-cleanup checks, receipts, declared-tool-only registration, and an unchanged consumer history sentinel after approved disposable cleanup. Tests use disposable paths and doubles; no live host cleanup is claimed. | [Ownership contract](../AGENTS.md). Hermes source remains owned by `/home/eaglesvn/.hermes/hermes-agent` on `codex/curator-v2-hermes-integration-upstream`. Open: measured live service/host attribution; authenticated approver identity; root-account activation; cross-process supervision; production recovery/deployment tests. See the [proposed Hermes-owner deployment sequence](curator-v2-plan.md#ordered-implementation-slices-and-exit-evidence). |
| I. V2 pilot and release | local alpha route exercised; release gates open | Owner: Curator V2 core, Vhost Manager pilot owner, and product/deployment/release owners for their respective approvals. Actual: the isolated profile, consumer hook, bounded write grant, and installed V2 package are active. A real `renew-ssl-coding` profile session produced acknowledged Hermes outbox events and processed Curator receipts through the managed gateway; the profile binding and bounded payload disposal were checked in persisted state. The 7-test consumer contract covers configured persistence and isolation in disposable repositories. This does not exercise a user workflow inside the Vhost Manager application, write its canonical Markdown target, or prove rollback. | [Alpha scope](alpha-v2.md), [consumer operations](consumer-operations-v1.md), [failure recovery](component-failure-recovery-v2.md). Open: Vhost application workflow; deployment rollback; production runbooks/release approval; production retention/cleanup policy; explicit owner authorization for a named Vhost application request; authenticated identity. V1 is outside V2. |
| CI quality/security | alpha candidate hosted checks passed | Owner: Curator V2 core. Probe: commands in [CI policy](ci-v2.md). Expected: Python matrix, strict typing, blocking Pylint errors, Bandit, lockfile audit, and clean-wheel launcher test pass. Actual at the alpha-candidate checkpoint: the local `0.1.0a1` candidate passed 340 tests on Python 3.12.3, isolated-profile installed-wheel consumer contracts, strict Pyright, errors-only Pylint, Bandit, dependency audit, lock check, and `git diff --check`. The later 2026-10-22 source verification recorded in [`curator-v2-plan.md`](curator-v2-plan.md) reports a 397-test full-suite run; this ledger does not claim that result was rerun or covered by the hosted runs listed here. GitHub Actions run [39389283097](https://github.com/eagles-edu/curatormd-v2/actions/runs/39389283097) passes on alpha commit `8733875`, with the Python 3.12/3.13/3.14 matrix and installed-wheel acceptance; GitHub Actions run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9`, and run [39392957765](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392957765) passes on `0e98bf0` with the processed-v16-receipt regression included. | [Workflow](../.github/workflows/ci.yml), [tool pins and lock](../uv.lock), [CI policy](ci-v2.md). Open: repository-wide Pylint convention/refactor/warning cleanup. |

Hermes source-check freshness (2026-10-23): a read-only recheck confirms the Hermes checkout is still clean at `cbf36955a2a0dab40224efa49af692300194f9df`, ten commits after verified source head `9b8fc71e30`. The recorded 61-test and 39-test lifecycle/integration suites are for `9b8fc71e30`. The separate 58-test Hermes integration result in row G has no source revision recorded, so it cannot establish current-head coverage. The plan records separate current-head trace-export coverage: seven tests in the trace-export file (one optional-upload test skipped) and all 12 `scripts/check` checks. That evidence covers trace rendering only; the broader gateway-hook, profile-usage, and Codex app-server suites have not been verified at current `HEAD`. Current-head integration verification remains open.

Consumer evidence freshness (2026-10-22): the Vhost Manager checkout currently has a modified [consumer contract test](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_contract.py) and an untracked [managed-integration harness](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_hermes_managed_integration.py). This ledger does not establish whether those exact working-tree versions were included in the last recorded run, and they were not rerun for this update. The seven-test result is historical evidence, not verification of the current dirty consumer test tree.

The successful hosted runs on `8733875`, `3ce95b9`, and `0e98bf0` close hosted source/package CI for the
`0.1.0a1` alpha candidate. The Vhost Manager alpha package and bounded profile
binding are installed locally. The local Hermes-to-Curator route has processed
12 receipts, while the Vhost application workflow and live canonical target
write remain unverified. Production deployment, authenticated identity,
production retention policy, recovery, and owner-approval gates remain open.

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
| C | SQLite and Markdown projection are present; read-only per-goal comparison reports missing/synced/divergent/malformed states through authenticated API/MCP reads. No conflict repair or authoritative-store decision is made. | Leave purge pending, preserve canonical files and receipts, then use an integrity-checked backup and owner-directed reconciliation procedure. | Product/repository owners approve the field-level authority model, recovery-record fields, incident owner, pause/switch roles, and any live-store switch. The repository owner separately approves each restore or per-record conflict repair; integrity checks and tests confer no authority. Track the lifecycle v22 migration, failure, restore, and rollback case as `LC-V22-MIGRATION`. |
| D | In-process API/MCP facade exists with reject-all default authorization. | Keep access fail-closed; remove/disable an untrusted binding and repair the host identity adapter before retry. | Hermes identity owner approves the authenticated identity source and trusted role claims; product/repository owners approve repository/config fingerprint authority and administrator scope; owners set revocation/freshness rules and exact project/action grants. Track authenticated transition CAS and review-bound suspension/reactivation as `LC-TRANSITION-CAS` and `LC-SUSPEND-REACTIVATE`. Distributed quota and feedback-retention decisions remain separate open gates. |
| E | Local durable inbox, one-shot router, tombstone, terminal-disposition, and bounded lifecycle-snapshot implementations exist; no router/operator deployment exists. | Pause producers, retain failed inbox receipts, repair the consumer, and replay stable event IDs; never discard backlog to restore green status. | Router and purge-scheduler owners plus the host operator approve the supervised host, exact project roots, bounded pass limits, restart/stop and overlap policy, required probes, metric/alert routing, and measured thresholds before deployment. Operator approval is separately required before quarantine release or any event disposition that drops data; local tests grant no deployment authority. Track remaining effect fencing, authenticated content-free operator status, and cross-project inbox-capacity allocation as `LC-EFFECT-BOUNDARY`, `LC-OPERATOR-STATUS`, and `EVENT-CAP-ALLOCATION`. |
| F | Local Vhost Manager alpha binding is active with a bounded write grant and installed consumer hook; local drain authorization and source-epoch re-enrollment are implemented in Curator V2, while real app producer, canonical persistence, and rollback remain unverified. | Disable only the V2 project binding, retaining V2 receipts, staged evidence, and consumer records; then repair and repeat the alpha checks. | Pilot owner explicitly authorizes the named one-run request under the approved local-alpha policy and approves its producer/source-to-class inventory, exact profile/project/repository/config fingerprints, and persistence/staging targets. Hermes identity owner approves trusted identity and grants; production retention/cleanup/capture-policy changes, rollback, and release require their respective owners' approval. Track `LC-DEREG-DRAIN`, `LC-REENROLL-EPOCH`, and `CONSUMER-SOURCE-COVERAGE` as separate evidence cases under this gate. |
| G | Vhost Manager local alpha route passes synthetic hook-to-managed-MCP delivery and terminal outbox acknowledgment; real interactive identity and production routing remain open. | Keep the bounded V2 binding disabled if its exact project/profile route cannot be verified; preserve pending events for replay after repair. | Hermes profile owner approves the exact event classes, bounded fields, profile/project/session/goal binding, and named one-run capture. The identity owner approves trusted human identity and grants under Slice D; the router operator approves production route/scheduler scope under Slice E. Raw transcript persistence remains prohibited; production retention or broader capture requires separate owner approval. |
| H | Host Steward is a Hermes Core concern and is absent from this repository. | Use the existing managed host cleanup workflow or leave disk findings pending; do not substitute Curator purge for host cleanup. | Hermes Core account owner approves account-home placement, the bounded target manifest, service bindings, host-authenticated approver identity, cross-process supervision, recovery, and receipt retention before deployment. A human separately approves each exact cleanup proposal; the executor cannot self-approve. Local tests authorize no live cleanup. |
| I | Vhost Manager's alpha package and bounded project write grant are installed in its local profile; synthetic delivery passes, while live profile delivery, real application workflow, and release gates remain open. V1 is outside V2 scope. | Disable only the V2 project binding; retain V2 receipts, staged evidence, and consumer canonical records for owner-directed recovery. | Pilot owner authorizes the named one-run request under the approved local-alpha policy and signs off the workflow, source inventory, exact profile/project/repository/config bindings, and persistence/staging targets. Product owner signs off the pilot and residual risks; production retention/cleanup/capture-policy changes require separate owner approval. Deployment owner approves rollback, and release owner approves runbooks/release before broader use. |

The per-slice owner, concrete probe, expected result, observed result, and linked
code/test evidence are recorded in the status table above. Where no deployment
probe has run, the actual result explicitly says so; this ledger does not
authorize destructive changes.

## Lifecycle deployment evidence catalog

Each lifecycle case is an independent deployment gate. Run cases only against
disposable project data with the intended service and administrator identity
paths. Each packet binds the package/config fingerprints, project and consumer
binding revisions, source epoch, transition ID, approval reference, and
before/after state digests. Do not merge dispositions across cases.

| Case ID | Gate | Owner | Preconditions | Expected result | Current disposition |
| --- | --- | --- | --- | --- | --- |
| `LC-V22-MIGRATION` | C | Curator storage/recovery owner and repository owner | Isolated v22 database, reviewed backup, migration fault points, approved rollback boundary | Preserve registry/grant/audit state; represent legacy epoch/sequence baselines as unknown; injected failure is atomic; restore/rollback follows the approved boundary | Open; local migrations through schema v37 and disposable upgrade checks pass, but deployment restore/rollback approval is absent |
| `LC-TRANSITION-CAS` | D | Hermes identity owner and Curator access-policy owner | Authenticated admin and project principals; active binding with recorded revisions | Exact retry after lost response returns the same receipt; stale revision or changed-input reuse makes no mutation | Open; local project/binding CAS and idempotency are implemented; verified deployed identity remains absent |
| `LC-SUSPEND-REACTIVATE` | D | Hermes identity owner, project owner, and retention/review owner | Active project/binding, approved review packet and baseline grant/cursor/inventory observations | Suspension fences old sessions; stale review is rejected; reactivation requires a fresh review bound to unchanged complete inputs | Open; schema-v37 local packet and CLI bind reactivation to grants, cursors, event backlog, purge work, and a complete fresh staging scan; 74 focused tests and quality checks pass. Hermes-authenticated reviewer identity, external staging-inventory authority, and deployed workflow evidence remain absent |
| `LC-DEREG-DRAIN` | F | Consumer owner and router operator | Complete pre-cutover event inventory and exact envelope digests; bounded drain window | Only inventoried exact retries are admitted; new IDs are denied; unresolved or ambiguous acknowledgements keep deregistration pending | Open for deployment; local schema-v35 drain authorization binds an expiring transition and exact event inventory/envelope, source/profile/config/binding revision; effect-boundary approval is rechecked. Store ingress now rejects new event IDs during deregistration while retaining exact lookup for an event recorded before cutover. Focused `test_project_access` passes 18 tests; expiry, lost-ack, in-flight consumer-binding fence, and deployed identity evidence remain open |
| `LC-REENROLL-EPOCH` | F | Consumer owner, Hermes identity owner, and router operator | Deregistered binding; reconciled old events; newly reviewed repository/config/grant/cursor/backlog/purge observations | New enrollment increments the source epoch; old-epoch events, grants, sessions, and configs cannot cross the binding; no old envelope is copied, resequenced, replayed, or used to resume purge | Open for deployment; local schema-v34 enrollment rotates the sequence generation, blocks unresolved old events, and does not restore grants; the focused refresh passed |
| `LC-RETIRE-FENCE` | E | Router operator and project/repository owner | Disposable project with retained cursor and explicit terminal-disposition approval | Irreversible tombstone fences replay; cursor is unchanged; dropping backlog requires separate contiguous disposition approval | Open for deployment; local schema-v35 tombstone and schema-v36 exact terminal disposition preserve unresolved records and fence replay. Store ingress now rejects new IDs for the retired project while an exact retry returns its preserved receipt. Focused `test_project_access` passes 18 tests; deployed authenticated approval and replay-horizon evidence remain open |
| `LC-EFFECT-BOUNDARY` | E | Router, persistence, and purge operators | Concurrent write, source acknowledgement, projection, and unlink attempts around a lifecycle transition | No stale-revision effect crosses cutover; crash/retry state is recoverable and attributable | Open; local tests prove suspension waits for an in-flight expiry unlink and receipt, post-cutover retry is denied, and Hermes refuses mismatched receipts. The real MCP hook recovers an exact processed event after suspension under unchanged config/binding and an active write grant; changed envelopes and unprocessed IDs are denied. Focused lifecycle/adapter suites pass 124 tests with quality checks. Deregistered/retired-source reconciliation, other purge interruption points, consumer-binding revision races, and deployed coverage remain incomplete |
| `LC-OPERATOR-STATUS` | E | Operations owner and authenticated dashboard owner | Authenticated project status view with bounded complete-state queries and timestamped host observations | Reconciled counts expose completeness and observation times; unknown/failure states never appear as zero or healthy; no event IDs or payloads leak | Open; local attended snapshot reports observation time/completeness and bounded event state; authenticated deployment view remains absent |

Scenario procedures and required packet fields are specified in
[`curator-v2-plan.md`](curator-v2-plan.md), Section 9. The corresponding
Section 6 lifecycle item and deployment-level integration-test item remain
open until the owner-reviewed probes and rollback drill have passed.

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
