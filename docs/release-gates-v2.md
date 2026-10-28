# Curator V2 release-gate ledger

This is a snapshot of verified repository evidence, not a deployment health
claim. Statuses describe the strongest evidence currently present in this
checkout. A passing local unit test cannot close a deployment or owner-approval
gate.

Current delivery checklist snapshot (2026-10-28 direct delivery-row recount):
167/178 complete, 11 open, using the counting rule in
[`curator-v2-plan.md`](curator-v2-plan.md). This counts top-level checklist
rows in sections 0–10, 12, and Definition of done; reusable templates and
acceptance examples are excluded. The prior embedded `154/188` value did not
match that scope and has been corrected. The Vhost source/artifact audit for
the approved dirty development snapshot is complete; release gates below remain
separate.

Latest local-alpha package refresh (2026-10-26): wheel SHA-256
`c1c3eb614e0dc85f5c9ebe28842316c6db8c59a748b14f05eb720ebb3bf3cee9` was
installed only in the dedicated `renew-ssl-coding` V2 virtualenv after a
verified rollback archive at
`/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-package-before-alpha-refresh-20261026-d1cjyoeq/`;
archive SHA-256 is
`a865a4ff3ae737bdee5a9df538b9cba330bf6fd6c8aab0c28e7c49a6360b3452`, with
117 manifest entries. All 61 installed Python module hashes match source and
`pip check` passes. The source suite passes 465 tests; strict Pyright,
errors-only Pylint, Bandit, and locked dependency audit pass. Clean-wheel
acceptance passes two installed MCP tests, seven CLI entrypoints, and SQLite
backup/restore. The Vhost consumer contract passes eight tests against
disposable state, and the Hermes-managed harness passes five bounded events,
exact replay/retry/re-enrollment, projection reconciliation, and privacy checks.
A fresh Hermes profile read discovers 48 tools and reports 29 processed
receipts, 12 goals, eight facts, a complete zero-file inventory, and healthy
local dependencies. Existing long-lived gateway/web/editor MCP processes were
not restarted; this does not claim they reloaded the installed wheel or prove
the live gateway route. Production identity, retention, deployment recovery,
and release gates remain separate.

Earlier local-alpha package refresh checkpoint (2026-10-25): the Curator source
was built and installed only in the dedicated `renew-ssl-coding` V2
virtualenv. Wheel SHA-256:
`38a5d943be64971872ed69a15913ee78d16b81b91e2aa0f41b31968665117531`.
Before installation, the prior package, dist-info, and command entrypoints
were archived under
`/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-package-before-alpha-refresh-20261025T105038Z/`;
the verified archive SHA-256 is
`6e4079ff5be37d43972e4b7a6bb4b29f5d0289b3745fd4055e1391b33de3e703` with
117 manifest entries. All 51 installed Python modules match source byte for
byte, `pip check` passes, and the installed module rejects a synthetic labeled
DNS challenge without echoing its value. The supported Hermes profile probe
connects, discovers 48 tools, and at package-refresh time read 17/17 processed
receipts, six goals, and two facts with healthy local-alpha status. This updates
local package evidence only; it does not exercise a new Vhost application
request or establish production readiness. After installation, the Vhost-owned
Hermes-managed disposable harness also passed against this wheel: five events,
exact replay, delivery retry, re-enrollment recovery, projection reconciliation,
privacy canaries, and reviewer-write denial. All harness state was temporary;
this is not a live application workflow.

Earlier local-alpha recheck (2026-10-25T06:24Z): the `eaglesvn` user timer for
`vhost-manager-alpha` is enabled and active on the approved six-hour schedule
at 00:00, 06:00, 12:00, and 18:00, with journal-only failures. Scheduled
passes at 00:00, 06:00, and 12:00 exited successfully; no purge or expiry work
was due. At 06:24 UTC, the Hermes development checkout's
`renew-ssl-coding` profile probe connected to the installed Curator stdio
package, discovered 48 tools, read 12 processed receipts, one goal, and two
facts, and reported `project_health=healthy` with no gates. The global Hermes
CLI remains `0.22.2+1558` and does not support this probe flag; the read used
development checkout `0.22.2+2263`. `/usr/local/lib/hermes-agent` was not
modified. This is current local-profile evidence only; it does not verify a
Vhost application request or its Curator record. Curator is development-only,
one repository at a time; multi-user identity and production controls are
deferred, not alpha blockers.

Previous local-alpha package verification (2026-10-24): built from Curator
commit `1e10df2` and installed the `0.1.0a1` wheel only in the dedicated
`renew-ssl-coding` profile environment. Wheel SHA-256:
`4118c2cd1aeaf323bd88c8c0bdcd5d11173ac50769d0bceb4b1b747b82b660d2`. Before
installation, archived the previous package, distribution metadata, and CLI
entry points at
`/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-package-before-alpha-refresh-20261024T2255/`;
the archive SHA-256 is
`f471d4e7c6dd43ac295c3c0e925d0dca678e2e4ac2291d2bfabe9e14ead5e0f8`, and its
sidecar file manifest was verified. All 51 installed Python modules match the
wheel and source byte for byte; `pip check` reports no broken requirements.
The seven Vhost consumer contracts and Hermes-managed disposable recovery
harness pass against this package. The harness processes five events and checks
exact replay, retry, re-enrollment, projection reconciliation, and privacy
canaries. A read-only Hermes profile probe at 15:56 UTC discovers 48 tools and
reads 12/12 processed receipts, one goal, two facts, and `healthy` project
health with no gates. This is profile and disposable-consumer evidence, not a live Vhost
application request. The first scheduled pass after the six-hour cadence change
is still pending; no Vhost application source or project data was changed.
At that historical checkpoint the checklist was 145/178, with 33 open; no row
was closed by that package refresh.

Historical Hermes profile recheck (2026-10-24 12:04 UTC): the older installed
package returned `degraded` health because the local timer had not yet been
enabled. This was superseded by the 15:48 UTC healthy profile probe above. A
direct Codex MCP call without host-injected Hermes profile context remains
`unauthenticated`; the approved single-user alpha uses the local `eaglesvn` OS
UID grant and does not require multi-user person authentication.

Vhost consumer bridge follow-up (2026-10-25): the disposable HTTP/MCP
integration now persists a deterministic, path-free `change` fact after each
completed operation's exact goal receipt. The goal remains active for human
review. The focused test covers apply, rollback, renewal, cron, archive,
interrupted, and failed outcomes and passes against the installed alpha
launcher; duplicate retries remain idempotent. The Vhost-owned source changes
are uncommitted for consumer-owner review. This advances local workflow
evidence but closes no checklist row: standalone-script coverage, complete
artifact inventory, reviewed canonical output, human disposition, and the
broader Gate F/Slice I criteria remain open.

## Open gates in plain language

These labels refer to different missing evidence; they are not a request for
more generic approval. Local-alpha policy decisions are already approved in
[`Curator V2 Pilot Default Policy.md`](Curator%20V2%20Pilot%20Default%20Policy.md):
`eaglesvn` is the sole attended local reviewer/admin, one explicit SDE decision
authorizes purge of that decision's exact displayed inventory, and transient
artifacts have a 72-hour maximum age. Legal/operational holds need a separate
release. These decisions do not authorize production policy or deployment.
The current Curator V2 scope is development-only, one repository at a time,
under the `eaglesvn` OS account. Hermes-authenticated multi-user identity and
production controls are deferred; `Auth: none` is not a blocker for this local
alpha. Reopen those gates only if the owner expands the deployment scope.

Current installed-plugin read (2026-10-25 19:21 +07): the local root service is
active. The supported `renew-ssl-coding` Hermes profile connects to `curator_v2`,
discovers 48 tools, and reads 25/25 processed event receipts, 10 goals, and six
facts. The separate project-health snapshot reports `healthy`, a complete
zero-file staging inventory, and no operational gate codes. This verifies the
supported local profile route. Direct calls without Hermes profile context
remain unauthenticated; active-goal human disposition, production log-retention controls,
and release evidence remain open. The local dirty-snapshot producer/artifact
matrix is complete in
[`vhost-producer-coverage-v2.md`](vhost-producer-coverage-v2.md).

Latest read-only profile probe (2026-10-25T18:36:52Z): the supported
`renew-ssl-coding` CLI connects with host-injected profile/session context,
discovers 48 Curator V2 tools, and reads `vhost-manager-alpha`. The ledger has
27/27 processed receipts, 11 goals (five planned and six active), and seven
facts; lifecycle counts reconcile with the paginated goal total. Review and
purge queues are empty, staging inventory is complete and empty, and the
separate health observation is `healthy` with all seven dependencies healthy.
This is a dated local-alpha profile read; it does not represent human
disposition of the six active goals or production/release readiness.

| Gate | What is already done | What is still needed to close it |
| --- | --- | --- |
| Hermes-authenticated identity for shared use (deferred) | Local alpha is provisioned for the approved `eaglesvn` Linux account (`local-uid:1000`) with exact `vhost-manager-alpha` read/write/review grants. One repository is active at a time. | No additional identity work is required for the current single-user development scope. If the owner later enables shared or multi-user use, authenticate Hermes people and bind exact subject/project/action grants before widening access. |
| Local purge scheduler and journal reporting | The `eaglesvn` user timer is enabled and active for `vhost-manager-alpha` every six hours at 00:00, 06:00, 12:00, and 18:00, with 15-second spread, five-minute timeout, 100-item limit, and journal-only failures. The timer and service were rechecked on 2026-10-26: the 00:00 pass exited successfully with zero pending or processed targets, and the next timer trigger is 06:00. This verifies the approved local timer schedule. | No further local-cadence check is pending. External alerting, dead-letter delivery, production scheduling, and restart/reconciliation remain deferred production controls. The zero-work pass does not demonstrate a live deletion. |
| Live Vhost workflow | Disposable acceptance runs the consumer-owned hook through Hermes Core managed MCP into the installed Curator stdio server; exact receipts, retry/replay, readable goal-history reconciliation, and privacy canaries are checked. Three reserved local `.test` sites have been applied and rolled back through the root service with exact processed receipts. The first five apply/rollback and fake-ACME goals were written by the authorized local reviewer to Vhost `HISTORY.md` and reconciled to ledger hashes. The newest apply and rollback each produced one active review goal and one compact path-free fact; both records are projected and reconcile as `synced`. The test site is absent from Vhost inventory. The root ACME bridge preserves its four daily times and has disposable outage-queue recovery coverage. A 2026-10-26 read-only browser capture rendered the Vhost home page through system Chrome and revalidated its content-free digest for the bound local project. The owner-reviewed source/artifact matrix and four standalone utility workflows are covered for the current dirty development snapshot in [the coverage record](vhost-producer-coverage-v2.md). The approved local 72-hour manual-DNS log-expiry timer is enabled and active; its first pass removed two expired logs and retained no matching expired files. | Vhost Manager is a local utility; public hosting and a public application endpoint are not alpha requirements. The browser check covered only the home-page render, not an authenticated session or Vhost operation. The five earlier projected goals remain planned; the two newest goals await human disposition. No SDE review/purge flow was exercised. Fake ACME does not prove real certificate-renewal behavior; that is a separate feature-validation gate. Production log-retention controls and release approval remain open. |
| Other owner decisions | Local-alpha reviewer, exact-inventory cleanup, and 72-hour retention decisions are recorded above. | Production still needs explicit owners and values for record authority/recovery, event and artifact retention/replay horizons, permanent and staging storage budgets, external hold discovery, production role provisioning, and release/rollback acceptance. These are separate scoped decisions, not covered by the local-alpha approval. |

Current local-alpha recheck (2026-10-25): through the running root Vhost
Manager HTTP service, a disposable `.test` site was applied and rolled back.
The app manifest recorded matching `received` receipts for the exact apply and
rollback event IDs; a read-only query of the installed global V2 SQLite ledger
confirmed both receipts as `processed` under `vhost-manager-alpha`. The site
account and webroot were removed, the Vhost inventory no longer lists the
target, and the root service reports active Nginx/OpenLiteSpeed with valid
configuration. This supersedes earlier statements that no root-service apply,
Vhost application receipt, or rollback had been checked. The `eaglesvn`
reviewer has also projected five exact local Vhost operation goals into
`.curatormd-v2/persistence/HISTORY.md`; read-only reconciliation matched each
stored document hash to SQLite, and the records exclude temporary paths,
database paths, and the ACME output canary. This verifies canonical Markdown
records for those five operations. The separate user-facing status/dashboard,
full source/artifact coverage, production retention, and release/rollback
approvals remain open. The local identity and purge timer described above are
verified for the current development scope; they do not imply a production or
multi-user deployment.

Current-source route follow-up (2026-10-25 19:15 +07): restarted the local root
Vhost Manager service, applied and rolled back the previously absent
`curator-v2-smoke-20261025.test`, and queried the configured V2 SQLite ledger.
The exact apply and rollback receipts are `processed`; the site is absent from
Vhost inventory and Nginx/OpenLiteSpeed report active, valid configurations.
No certificate was changed. The service now runs from the dirty Vhost checkout;
this is a local disposable workflow, not release-revision evidence. Source
coverage, standalone utilities, human disposition, and release approval remain
open.

Hermes profile probe (2026-10-25, before the latest root-service route test): the supported
`renew-ssl-coding` profile-context command connected to the installed Curator
V2 MCP, discovered 48 tools, and read project `vhost-manager-alpha`: 17 of 17
event receipts processed, zero received/failed/quarantined, six goals, two
facts, and project health `healthy` with no gates. This is a current local
alpha probe. A direct connector call without Hermes context remains
`unauthenticated` by design; that denial does not contradict the supported
profile read. No human identity or production readiness is inferred.

Current local-alpha profile probe (2026-10-25T11:53:27Z): the installed
profile reads 21/21 processed receipts, zero received/failed/quarantined
events, eight goals, and four facts. All lifecycle counts reconcile to the
paginated total (five planned, three active, zero in the other six states),
with zero SDE candidates, pending review, or purge backlog. The separately
timestamped health snapshot reports complete database and staging observations,
a complete zero-file staging inventory, seven healthy local dependencies, and
no gates. This closes the one-project local status-view criterion. The earlier
root-service apply/rollback evidence remains current; standalone producers,
complete artifact coverage, and broader release gates remain open.

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
Repository-wide Pylint recheck (2026-10-25): the latest full warning-level run
exits 24 at 9.96/10 with structural findings across backend and test modules.
Two subsequent focused test refactors remove the `too-many-locals` warning in
`test_purge.py` and local/statement-complexity warnings in
`test_markdown_persistence.py`; the full inventory was not rerun after those
deltas. Broad repository structure and interfaces remain open.

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
inventory read. The attended local review CLI now prints that packet, including
candidate facts, verification evidence, exact staged paths and manifest hash,
before soliciting approve/reject. Its second confirmation binds the dependency
map and inventory hashes; the local-UID/database-owner and full review/purge
flow pass in the focused nine-test suite. Local single-user reviewer UX is
verified; Hermes-person identity and production review UX remain outside alpha
scope. The latest full suite supersedes earlier per-slice counts in this ledger.

| Slice | Status | Owner, probe, expected/actual | Evidence and remaining exit condition |
| --- | --- | --- | --- |
| A. Freeze contracts | in progress | Owner: Curator V2 core. Probe: locked unit suite, Pyright, and `git diff --check`. Expected: fixtures and runtime records validate, tests/type checks pass. Actual (2026-10-20): 335 tests pass locally on Python 3.12.3; strict Pyright reports 0 diagnostics; errors-only Pylint, Bandit, locked dependency audit, and `git diff --check` pass. Hosted CI run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9` across Python 3.12/3.13/3.14 and blocking quality/security jobs; run [39392957765](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392957765) also passes on `0e98bf0` with the processed-v16-receipt migration regression. The repository config pins `backend_api_version = 1` and its example validates against the machine-readable contract. MCP tool failures map through the sanitized version-1 error envelope, and subprocess tests prove denial messages omit exception details. | [Contract index](contracts-v1.md), [machine-readable v1 schemas](schemas/curator-v2-v1.schema.json), [schema tests](../tests/test_contract_schemas.py), [event types](../src/curatormd_v2/events.py), [error mapper](../src/curatormd_v2/errors.py), [MCP serializer](../src/curatormd_v2/mcp_server.py). Open: shared producer/backend compatibility tests, remote transport error integration, and owner policy approval. |
| B. Harden local domain | verified locally; broader gates open | Owner: Curator V2 core. Probe: locked unit suite and Pyright. Expected: domain invariants and bounded/replay behavior pass. Actual at the 2026-10-20 validation checkpoint: the local suite had 335 passing tests on Python 3.12.3; Pyright reported 0 diagnostics. Deterministic property tests cover generated event encodings, incomplete completion claims, lifecycle revisions, parent/dependency gates, reopen orders, replay, and traversal rejection. API/MCP acceptance covers project authorization, both SDE dispositions, immutable receipts, inventory gating, canonical persistence, exact-artifact purge, truthful final status, and Hermes activity suppression/reopen ordering. Preliminary threat and evidence-trust contracts are documented, not substitutes for owner policy or real adapters. The plan records local Slice B closure with a 377-test run and a later 397-test full-suite quality checkpoint; neither closes the remaining source-to-sink privacy, production migration, deployment trust, or owner-policy gates. | [Domain records](../src/curatormd_v2/models.py), [service](../src/curatormd_v2/service.py), [store](../src/curatormd_v2/store.py), [lifecycle tests](../tests/test_lifecycle.py), [property/fuzz tests](../tests/test_property_fuzz.py), [concurrency tests](../tests/test_concurrency.py), [resource tests](../tests/test_resource_limits.py), [evidence trust contract](evidence-adapters-v1.md), [preliminary threat model](threat-model-v1.md), [migration tests](../tests/test_migrations.py). Open: deployment-owner privacy/threat review, real source integrations, deployment trust roots, and owner policy approval. |
| C. Storage and projection recovery | complete for local alpha | Owner: Curator V2 core. Probe: locked unit suite and migration fixtures. Expected: projection/purge retry invariants pass. Actual: migrations through v18 cover v10-to-v11 registry/grant tables, v11-to-v12 empty feedback tables without invented labels, v12-to-v13 shared rate limits, v13-to-v14 event disposition receipts, v14-to-v15 fact source-event provenance, v15-to-v16 purge-error redaction, v16-to-v17 semantic event-retry digests, and v17-to-v18 SDE proposal context. The source checkpoint recorded on 2026-10-22 was schema v22: v19 adds staging artifact age, v20 adds expiry purge receipts, v21 adds separate cleanup authorizations, and v22 adds a content-free WAL-scrub queue and one database-wide checkpoint receipt for a nonempty legacy inbox without copying or deleting payload rows. Follow-up local source now reaches schema v32: v23-v30 add purge-target identity, stale-approval, dependency-map, and reacquisition-action safeguards; v31 adds project-registration compare-and-set revisions and ordered audit revisions; v32 adds stable transition IDs for exact retry recovery. Local tests cover busy-reader retry, restart retry, payload absence from the WAL after successful truncation, and preservation of the legacy payload row during migration. Existing backup/restore, purge retry, crash-after-delete, integrity, and Markdown reconciliation tests remain documented local coverage. Read-authorized API/MCP reconciliation returns bounded paged goal statuses/hashes and project-wide orphan/malformed marker observations without changing either store; over-limit scans are explicit. Generated Markdown blocks use unkeyed SHA-256 checksums: accidental edits are classified malformed and projection refuses replacement; exact legacy blocks can be upgraded, while stale unsealed blocks are preserved. This detects accidental edits, not malicious rewrites. The owner-approved local policy makes SQLite authoritative for structured records and requires manual review before rebuilding Markdown on mismatch. | [Store](../src/curatormd_v2/store.py), [backup helpers](../src/curatormd_v2/backup.py), [migration tests](../tests/test_migrations.py), [WAL scrub tests](../tests/test_event_payload_scrub.py), [Markdown tests](../tests/test_markdown_persistence.py), [API](../src/curatormd_v2/api.py), [MCP server](../src/curatormd_v2/mcp_server.py), [migration policy](schema-migrations-v1.md), [local recovery procedure](storage-recovery-v2.md). Open: `PERMANENT-DATA-BUDGET` and `EVENT-RETENTION-RECOVERY` remain separate local storage-policy decisions |
| D. Authenticated interfaces | local alpha complete; production controls deferred | Owner: Curator V2 core. Probe: focused access/API/MCP/rate-limit suites, strict Pyright, and a read-only installed-profile ledger check. Expected: fail-closed interfaces, exact project/action grants, durable local identity/audit, and bounded quotas. Actual (2026-10-24): 94 tests pass across access, attended provisioning, API, hosted MCP, MCP server, and rate limiter; Pyright reports 0 diagnostics. The enabled `renew-ssl-coding` profile uses Hermes host context for `vhost-manager-alpha`. Its read-only SQLite ledger is schema 37 with `quick_check=ok`, active project and binding revision 1/source epoch 1, and active read/write/review grants only for `local-uid:1000`; earlier profile-name grants are revoked. The host maps UID 1000 to the owner-approved `eaglesvn` account. This closes the one-developer, one-repository development interface. | [API](../src/curatormd_v2/api.py), [project access](../src/curatormd_v2/project_access.py), [local access CLI](../src/curatormd_v2/access_cli.py), [store](../src/curatormd_v2/store.py), [access tests](../tests/test_project_access.py), [CLI tests](../tests/test_access_cli.py), [MCP tests](../tests/test_mcp_server.py), [hosted MCP tests](../tests/test_hosted_mcp.py), [rate limiter](../src/curatormd_v2/rate_limiter.py). Open only if scope expands: Hermes-human identity/role binding, distributed quotas, production denial/provisioning probes, trusted fingerprint authority, and feedback-retention policy.
| E. Durable routing and operations | local alpha complete; production controls open | Owner: Curator V2 core and future router operator. Probe: full Python 3.12/3.13/3.14 unit matrix plus API/MCP authorization tests. Expected: bounded local routing, retry/quarantine, source order, migration, queue visibility, and truthful local health pass; deployed operation remains separate. Actual: local event routing covers persisted retry backoff, quarantine, operator retry, ordering, cross-connection expiring claims and stale-owner fencing. The `curatormd-v2-router` CLI runs one explicit bounded pass for a fixed list of validated repository configs; claims are restricted to those project IDs, leaving other projects untouched. Local project retirement tombstones and attended exact terminal disposition are implemented. The bounded lifecycle view reports project/binding/tombstone state, event counts, leases, unresolved digest, and terminal candidates from one SQLite snapshot. This remains a local one-shot operation, not a resident worker or production monitoring service. A separate local `eaglesvn` systemd user timer now runs the approved Vhost Manager purge-retry command every six hours at 00:00, 06:00, 12:00, and 18:00 with 15-second spread; it does not schedule router event processing or provide production alerting. At the recorded local routing checkpoint, nine focused routing/CLI tests and the 336-test suite passed. This is a local one-shot operation, not an installed worker or scheduler. Local purge cleanup has persisted per-target backoff, bounded due selection, immediate authorized retry override, and visible retry deadlines/countdowns. Authenticated API/MCP health returns healthy only with explicit fresh host probes (<=60 seconds), empty queues/review/purge/staging, complete staging inventory, and remaining capacity; known backlogs/failures are degraded, missing/stale/failed probes unknown. Its event/review/purge/storage database observations share one SQLite read transaction; the bounded no-follow staging scan is separately observed. Authorized project metrics include fixed, content-free evidence rejection, trusted adapter error, and other failure categories for current failed/quarantined receipts. This is a local exposition snapshot, not a deployed scrape endpoint/dashboard/alert system. | [Router](../src/curatormd_v2/router.py), [event/purge store](../src/curatormd_v2/store.py), [health and metrics API](../src/curatormd_v2/api.py), [metrics renderer](../src/curatormd_v2/observability.py), [router tests](../tests/test_router.py), [API tests](../tests/test_api.py), [concurrency tests](../tests/test_concurrency.py), [purge tests](../tests/test_purge.py), [migration tests](../tests/test_migrations.py), [MCP tests](../tests/test_mcp_server.py). Fresh local-alpha verification (2026-10-24): the focused operations suite passes 154 tests on each of Python 3.12, 3.13, and 3.14, and the approved six-hour purge timer is active. Production scheduler/worker operation, external alerting, deployment storage budgets, and production drills remain open. Open: production event and purge schedulers, host probe adapters that supply fresh timestamped observations, scrape endpoint, dashboard/alert delivery, storage/lag budgets, restart/load/failure-injection/deployment probes; `EVENT-CAP-ALLOCATION` and `EVENT-RETENTION-RECOVERY` deployment scenarios. |
| F. Reusable consumer plugin | local consumer integration verified; pilot/release gates open | Owner: Curator V2 core plus each pilot-repository owner. Probe: locked suite plus consumer integration. Actual: Vhost Manager has the installed alpha package, isolated V2 staging/persistence/database paths, a consumer-owned hook, and a bounded writable Hermes profile grant. Disposable acceptance covers configured persistence, isolation, bounded hook delivery, explicit goal binding, failed-delivery retry, exact replay acknowledgement, readable goal history reconciliation, content-canary exclusion, and recovery of a persisted running SSL operation to an interrupted receipt after app restart. The 2026-10-24 managed Hermes stdio harness passes; its nested `source_epoch` parser fix is pushed to the Hermes fork. Curator-local tests cover inbox cutover, exact drain, terminal disposition, retirement, and source-epoch re-enrollment. Vhost apply/rollback receipts were verified through the running local service; disposable tests also verify that failed rollback attempts and rollback-restored failed applies are recorded and sent to Curator with exact receipts and path-free summaries. This does not verify repair/recovery from a damaged backup. The 2026-10-25 focused Vhost HTTP route contract also passes apply/archive/rollback and SSL/cron receipt retry/recovery against temporary server, database, and filesystem state; no live site or certificate was changed. The current managed integration recheck passes Hermes HookRegistry/HookContext through managed stdio MCP into the installed Curator server with five processed synthetic events. The source-to-class matrix, out-of-root owner disposition, and four standalone utility workflows are covered for the current dirty development snapshot in [the coverage record](vhost-producer-coverage-v2.md). This does not prove a real Codex app-server event, real certificate renewal, or production artifact behavior. | [Plugin boundary](../src/curatormd_v2/project_plugin.py), [config loader](../src/curatormd_v2/project_config.py), [plugin contract](project-plugin-v1.md), [lifecycle tests](../tests/test_project_access.py), [consumer tests](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_contract.py). Scope: the approved alpha uses one repository at a time; two-real-consumer generalization is deferred unless the owner expands scope. The local isolation criterion is complete for one real Vhost config plus a synthetic adversarial project. Open: production log-retention controls beyond the approved local 72-hour expiry timer; network-filesystem lock semantics; Hermes person authentication beyond the local eaglesvn UID (deferred unless shared use is approved); trusted evidence adapters; human disposition of persisted operation goals; damage recovery and release approval. Closed for the approved alpha scope: standalone producer/source-to-artifact coverage, including the four reviewed utility workflows, queue, and no-verbatim log handling, is bound to the current dirty checkout in the coverage record. Shared multi-consumer runtime is outside scope because alpha uses one repository at a time; it is not an alpha gate and reopens only if the owner expands scope. |
| G. Hermes Core integration | local alpha route verified; production gates open | Owner: Hermes Core. Actual: Hermes Core source includes the managed MCP hook adapter, durable profile-local outbox, exact acknowledgment handling, and root-account Host Steward. The isolated `renew-ssl-coding` profile connects to the installed Curator V2 server (45 tools). After correcting the Vhost hook to match the durable event envelope, a real profile session replayed sequences 1-9; all are acknowledged, the current project/goal binding is persisted, and Curator's Vhost inbox cursor is 9 with 10 processed receipts. All nine source events have `applied` disposition; two compact intent/change facts are linked to the active Vhost goal. SQLite `quick_check=ok`; source-event inbox rows retain no payload JSON. The earlier integration checkpoint records seven Vhost contracts, Hermes `scripts/check` (12 checks), and a 58-test focused Hermes integration suite passing; the row does not record the source revision for the 58-test result. A later one-shot profile CLI session delivered sequences 10-11, both acknowledged once and processed/applied; read-only V2 SQLite now shows cursor 11, 12 processed/applied receipts, one goal, two facts, and no payload JSON for the new receipts. A Vhost-owned disposable harness additionally loads actual Hermes Core HookRegistry/HookContext, calls the installed Curator stdio server through Hermes managed MCP, acknowledges and replays two lifecycle events, and reconciles the configured consumer projection; see [harness](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_hermes_managed_integration.py). Hermes Core source-head verification at `9b8fc71e30` passed 61 focused gateway-hook, profile-usage, and Codex app-server tests plus all 12 `scripts/check` checks; this is historical evidence for the verified commit. A fresh read-only profile status probe (2026-10-24) using the Hermes development checkout discovers 48 Curator tools and returns 12 processed receipts, goal total 1, and `project_health=degraded` with only `purge_scheduler` and `alert_delivery` unavailable. The Hermes probe initially failed because the bridge imported PyYAML, which is absent from the Hermes runtime; it now uses Hermes Core's `hermes_yaml`, and its focused three-test suite passes. A later read-only profile probe (2026-10-24T13:25:05Z), after enabling the local timer, still reports health `degraded` only for `alert_delivery`; the scheduler observation is ready. The local timer ran successfully with zero due targets. This does not launch production schedulers or alert delivery, update the active `/usr/local` Hermes install, or establish production authorization. A later 2026-10-25 local HTTP-route check exercised Vhost apply/rollback and canonical projection; see the current local-alpha recheck above. | [Ownership contract](../AGENTS.md), [event contract](event-contract-v1.md), [Hermes project adapter](../src/curatormd_v2/hermes_hook.py), [consumer hook test](/home/eaglesvn/dockerz/renew_ssl/tests/vhost-manager/test_curatormd_v2_contract.py). A prior profile-bound status probe (2026-10-22) returned unknown for five host observations; direct Codex MCP reads without Hermes context remain `unauthenticated`, and the profile's `Auth: none` is not human authentication. Post-restart check (2026-10-24): the active system gateway now serves all five configured profiles; the installed renew-ssl V2 wheel matches all 49 source modules, and the installed-wheel managed-MCP Vhost harness passes with five processed events. The MCP test still reports `Auth: none`; this is not human authentication or a live application request. This is local profile/project-bound evidence, not a live Vhost workflow or green readiness. Open: authenticated profile/project identity; production event/purge router and scheduler; live canonical Vhost Markdown write; production recovery and retention approval; owner-approved project-usage source/window/budget/alert policy with incomplete-coverage handling and `PROJECT-USAGE-BUDGET`; provider capture and billing reconciliation evidence; hosted Hermes CI. |
| H. Host Steward validation | local validation complete; deployment gates open | Owner: Hermes Core Host Steward. Probe: host-side inventory/approval/cleanup suite and Hermes source checks. Expected: cleanup is separately approved, verified, receipted, and cannot write Curator knowledge. Actual: the opt-in root-account plugin provides bounded metadata inventory, exact configured-target proposals, fixed approval-gated cleanup, free-space/service checks, bounded receipts, and interrupted-cleanup reconciliation. The recorded focused Host Steward suite passed 15 tests, including interrupted-receipt reconciliation; Hermes `python3 scripts/check` passed all 12 checks at that verification checkpoint. This row does not pin that 15-test result to a source revision; see the Hermes source-check freshness note below before using it as current-head evidence. Earlier regressions verify exact-target approval, managed cleanup, post-cleanup checks, receipts, declared-tool-only registration, and an unchanged consumer history sentinel after approved disposable cleanup. Tests use disposable paths and doubles; no live host cleanup is claimed. | [Ownership contract](../AGENTS.md). Hermes source remains owned by `/home/eaglesvn/.hermes/hermes-agent` on `codex/curator-v2-hermes-integration-upstream`. Open: measured live service/host attribution; authenticated approver identity; root-account activation; cross-process supervision; production recovery/deployment tests. See the [proposed Hermes-owner deployment sequence](curator-v2-plan.md#ordered-implementation-slices-and-exit-evidence). |
| I. V2 pilot and release | local alpha route exercised; release gates open | Owner: Curator V2 core, Vhost Manager pilot owner, and product/deployment/release owners for their respective approvals. Actual: the isolated profile, consumer hook, bounded write grant, and installed V2 package are active. A real `renew-ssl-coding` profile session produced acknowledged Hermes outbox events and processed Curator receipts through the managed gateway; the profile binding and bounded payload disposal were checked in persisted state. The 7-test consumer contract covers configured persistence and isolation in disposable repositories. On 2026-10-25, reserved local `.test` sites were applied and rolled back through real Vhost HTTP routes; exact Curator receipts were processed and the latest compact facts reconcile to configured Vhost Markdown. The current dirty-snapshot producer matrix, out-of-root disposition, and standalone utility fixture coverage are recorded in [the coverage record](vhost-producer-coverage-v2.md). | [Alpha scope](alpha-v2.md), [consumer operations](consumer-operations-v1.md), [failure recovery](component-failure-recovery-v2.md). Open: human disposition of persisted operation goals; recovery snapshot and recovery-receipt packet; independent local pilot and release sign-off; production retention, cleanup, identity, and scheduling controls. V1 is outside V2. Real certificate renewal and production artifact behavior remain unverified. |
| CI quality/security | current main hosted checks passed | Owner: Curator V2 core. Probe: commands in [CI policy](ci-v2.md). Expected: Python matrix, strict typing, blocking Pylint errors, Bandit, lockfile audit, and clean-wheel launcher test pass. Actual at the alpha-candidate checkpoint: the local `0.1.0a1` candidate passed 340 tests on Python 3.12.3, isolated-profile installed-wheel consumer contracts, strict Pyright, errors-only Pylint, Bandit, dependency audit, lock check, and `git diff --check`. The later 2026-10-22 source verification recorded in [`curator-v2-plan.md`](curator-v2-plan.md) reports a 397-test full-suite run; this ledger does not claim that result was rerun or covered by the hosted runs listed here. GitHub Actions run [39389283097](https://github.com/eagles-edu/curatormd-v2/actions/runs/39389283097) passes on alpha commit `8733875`, with the Python 3.12/3.13/3.14 matrix and installed-wheel acceptance; GitHub Actions run [39392148597](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392148597) passes on source commit `3ce95b9`, and run [39392957765](https://github.com/eagles-edu/curatormd-v2/actions/runs/39392957765) passes on `0e98bf0` with the processed-v16-receipt regression included. GitHub Actions run [40105937812](https://github.com/eagles-edu/curatormd-v2/actions/runs/40105937812) passes on source commit `c653257e50df8472f921002512111f6cf0f8dda1`; the subsequent docs-only commit `4ebca4d406b7a12eb3a1c535d1d49edf5dbf6c58` also passes all jobs in run [40106053196](https://github.com/eagles-edu/curatormd-v2/actions/runs/40106053196). | [Workflow](../.github/workflows/ci.yml), [tool pins and lock](../uv.lock), [CI policy](ci-v2.md). Open: repository-wide Pylint convention/refactor/warning cleanup. |

Hermes source-check freshness (2026-10-23): a read-only recheck confirms the Hermes checkout is still clean at `cbf36955a2a0dab40224efa49af692300194f9df`, ten commits after verified source head `9b8fc71e30`. The recorded 61-test and 39-test lifecycle/integration suites are for `9b8fc71e30`. The separate 58-test Hermes integration result in row G has no source revision recorded, so it cannot establish current-head coverage. The plan records separate current-head trace-export coverage: seven tests in the trace-export file (one optional-upload test skipped) and all 12 `scripts/check` checks. That evidence covers trace rendering only; the broader gateway-hook, profile-usage, and Codex app-server suites have not been verified at current `HEAD`. Current-head integration verification remains open.

Consumer evidence freshness (2026-10-24): the current dirty Vhost consumer tree was exercised with `tests/vhost-manager/test_curatormd_v2_hermes_managed_integration.py` using Hermes Core's current checkout and the current Curator V2 source interpreter. It passed five bounded lifecycle events through Hermes `HookRegistry`/`HookContext`, managed stdio MCP, and the consumer-owned Vhost hook. The run includes a committed event whose response is lost, consumer deregistration/re-enrollment, explicit read/write grant restoration, a fingerprint-bound Curator MCP process restart, exact old-receipt recovery, and a fresh epoch-2 event at sequence 1. Retry/replay, Vhost projection reconciliation, and private model/cwd canaries also pass. `git diff --check` passes in both worktrees. This is disposable integration evidence; it still does not exercise a person acting in the Vhost application or a deployed service.

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
| F | Local Vhost Manager alpha binding is active with a bounded write grant and installed consumer hook; local drain authorization and source-epoch re-enrollment are implemented in Curator V2. The root service has applied and rolled back two reserved disposable `.test` sites through its actual local HTTP routes; all four exact receipts are `processed`, and rollback removed the test accounts/webroots. Interactive SSL outcomes have retryable receipts. The installed root ACME bridge preserves the existing four-times-daily schedule, records compact exit outcomes, and has a fake-ACME live receipt plus disposable outage-queue recovery coverage. The focused manual-DNS success fixture verifies challenge propagation, fixture install, temp cleanup, log redaction, and a content-free receipt; a disposable invocation of the installed cron wrapper verifies bounded receipt delivery and queue cleanup. The four apply/rollback goals and fake-ACME goal are projected and reconciled at the configured Vhost Markdown target. The owner-reviewed source/artifact matrix and out-of-root disposition are complete for the approved single-repository development alpha, bound to the dirty checkout in [the coverage record](vhost-producer-coverage-v2.md). The Vhost/OS-owned manual-DNS log-expiry timer enforces the approved local 72-hour cap. Actual scheduled ACME execution, provider/CA behavior, production log-retention controls, human disposition of operation goals, and release evidence remain open. | Disable only the V2 project binding, retaining V2 receipts, staged evidence, and consumer records; then repair and repeat the alpha checks. | Pilot owner explicitly authorizes the named one-run request under the approved local-alpha policy and approves its producer/source-to-class inventory, exact profile/project/repository/config fingerprints, and persistence/staging targets. Hermes identity owner approves trusted identity and grants; production retention/cleanup/capture-policy changes, rollback, and release require their respective owners' approval. Track `LC-DEREG-DRAIN`, `LC-REENROLL-EPOCH`, and `CONSUMER-SOURCE-COVERAGE` as separate evidence cases under this gate. |
| G | Vhost Manager local alpha route passes synthetic hook-to-managed-MCP delivery and terminal outbox acknowledgment; real interactive identity and production routing remain open. | Keep the bounded V2 binding disabled if its exact project/profile route cannot be verified; preserve pending events for replay after repair. | Hermes profile owner approves the exact event classes, bounded fields, profile/project/session/goal binding, and named one-run capture. The identity owner approves trusted human identity and grants under Slice D; the router operator approves production route/scheduler scope under Slice E. Raw transcript persistence remains prohibited; production retention or broader capture requires separate owner approval. |
| H | Host Steward is a Hermes Core concern and is absent from this repository. | Use the existing managed host cleanup workflow or leave disk findings pending; do not substitute Curator purge for host cleanup. | Hermes Core account owner approves account-home placement, the bounded target manifest, service bindings, host-authenticated approver identity, cross-process supervision, recovery, and receipt retention before deployment. A human separately approves each exact cleanup proposal; the executor cannot self-approve. Local tests authorize no live cleanup. |
| I | The one-user, one-repository Vhost alpha has local apply/rollback receipts, exact event replay, canonical Vhost records for prior operations, and owner-approved source/artifact coverage. The current content-free evidence snapshot binds the package/config/project and lists open recovery, usage, and privacy checks. The 2026-10-28 route smoke is locally verified; final packet reconciliation and `eaglesvn` sign-off remain open. | Keep only the configured local project binding; preserve pending receipts for exact replay and retain the known-good rollback archive. | `eaglesvn` reviews the named local evidence snapshot and accepts or rejects only the reviewed alpha package, project, and config. No separate release, deployment, or policy role is required. A changed target, unapproved retention rule, or cleanup inventory still needs its existing explicit owner decision. |

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

| Case ID | Gate | Owner | Preconditions | Expected result | Evidence binding | Current disposition |
| --- | --- | --- | --- | --- | --- | --- |
| `LC-V22-MIGRATION` | C | Curator storage/recovery owner and repository owner | Isolated v22 database, reviewed backup, migration fault points, approved rollback boundary | Preserve registry/grant/audit state; represent legacy epoch/sequence baselines as unknown; injected failure is atomic; restore/rollback follows the approved boundary | Backup SHA-256; source/target schema versions; registry/grant/audit digests; injected fault ID; restore/rollback receipt | Open; local migrations through schema v37 and disposable upgrade checks pass, but deployment restore/rollback approval is absent |
| `LC-TRANSITION-CAS` | D | Hermes identity owner and Curator access-policy owner | Authenticated admin and project principals; active binding with recorded revisions | Exact retry after lost response returns the same receipt; stale revision or changed-input reuse makes no mutation | Actor/action-grant digest; project/binding revisions; transition ID and request digest; exact retry receipt digest | Open; local project/binding CAS and idempotency are implemented. Read-only deployed Vhost-alpha check confirms the profile stdio process runs as OS UID 1000 (`eaglesvn`) and the active ledger grants that exact subject read/write/review; the Hermes MCP probe connects and discovers 48 tools. Hermes transport auth is `none`, so person-level identity and production identity remain unverified |
| `LC-SUSPEND-REACTIVATE` | D | Hermes identity owner, project owner, and retention/review owner | Active project/binding, approved review packet and baseline grant/cursor/inventory observations | Suspension fences old sessions; stale review is rejected; reactivation requires a fresh review bound to unchanged complete inputs | Review-packet digest; registration/config/grant/cursor/backlog/purge/staging digests; suspension ID; activation receipt | Open; schema-v37 local packet and CLI bind reactivation to grants, cursors, event backlog, purge work, and a complete fresh staging scan; 74 focused tests and quality checks pass. Hermes-authenticated reviewer identity, external staging-inventory authority, and deployed workflow evidence remain absent |
| `LC-DEREG-DRAIN` | F | Consumer owner and router operator | Complete pre-cutover event inventory and exact envelope digests; bounded drain window | Only inventoried exact retries are admitted; new IDs are denied; unresolved or ambiguous acknowledgements keep deregistration pending | Cutover revision/source epoch; complete event-inventory digest; exact envelope digests; drain transition/expiry; per-event receipt outcomes | Open for deployment; local schema-v35 drain authorization binds an expiring transition and exact event inventory/envelope, source/profile/config/binding revision; effect-boundary approval is rechecked. Store ingress now rejects new event IDs during deregistration while retaining exact lookup for an event recorded before cutover. Focused `test_project_access` passes 18 tests; expiry, lost-ack, in-flight consumer-binding fence, and deployed identity evidence remain open |
| `LC-REENROLL-EPOCH` | F | Consumer owner, Hermes identity owner, and router operator | Deregistered binding; reconciled old events; newly reviewed repository/config/grant/cursor/backlog/purge observations | New enrollment increments the source epoch; old-epoch events, grants, sessions, and configs cannot cross the binding; no old envelope is copied, resequenced, replayed, or used to resume purge | Old/new source epochs; unresolved-event digest/count; reviewed repository/config/grant/cursor/purge digests; old/new receipt IDs | Open for deployment; local schema-v34 enrollment rotates the sequence generation, blocks unresolved old events, and does not restore grants. The disposable managed Hermes/Vhost harness now loses an acknowledgement after commit, re-enrolls, restores exact read/write grants, restarts the fingerprint-bound MCP process, acknowledges the exact old receipt, and sends a fresh epoch-2 sequence-1 event. Authenticated deployment identity and migration/recovery evidence remain open |
| `LC-RETIRE-FENCE` | E | Router operator and project/repository owner | Disposable project with retained cursor and explicit terminal-disposition approval | Irreversible tombstone fences new writes/replay; an exact pre-retirement processed receipt may be returned for lost-ack recovery; cursor is unchanged; dropping backlog requires separate contiguous disposition approval | Tombstone transition/receipt; pre-retirement cursor digest; exact receipt replay result; terminal-disposition approval/digest | Open for deployment; local schema-v35 tombstone and schema-v36 exact terminal disposition preserve unresolved records and fence new writes. A fresh API regression allows only a pre-retirement processed receipt bound to the tombstoned source epoch/profile/config and denies changed content, new IDs, and another profile. Deployed authenticated approval and replay-horizon evidence remain open |
| `LC-EFFECT-BOUNDARY` | E | Router, persistence, and purge operators | Concurrent write, source acknowledgement, projection, and unlink attempts around a lifecycle transition | No stale-revision effect crosses cutover; crash/retry state is recoverable and attributable | Run ID; effect/transition order; project/binding revisions; receipt/projection/unlink outcomes; injected restart point | Open; local tests prove suspension waits for an in-flight expiry unlink and receipt, post-cutover retry is denied, and Hermes refuses mismatched receipts. A new API-level regression recovers only an exact processed pre-retirement receipt and denies changed content, new events, and another profile. The real MCP hook also recovers an exact processed event after suspension; focused API/project-access suites pass 62 tests, targeted Pyright reports zero diagnostics, and errors-only Pylint is clean. Other purge interruption points, consumer-binding revision races, managed-MCP post-retirement coverage, and deployed coverage remain incomplete |
| `LC-OPERATOR-STATUS` | E | Operations owner and authenticated dashboard owner | Authenticated project status view with bounded complete-state queries and timestamped host observations | Reconciled counts expose completeness and observation times; unknown/failure states never appear as zero or healthy; no event IDs or payloads leak | Authorized query scope; observation times/completeness; reconciled page totals/count digests; privacy-canary results | Open; local attended snapshot reports observation time/completeness and bounded event state; authenticated deployment view remains absent |

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
