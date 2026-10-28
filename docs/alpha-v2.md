# Curator V2 alpha

## Candidate scope

The package version is `0.1.0a1`. This is a local alpha candidate for
integration and feedback. It is not a published distribution, production
deployment, or authorization to broaden capture or enable destructive cleanup.

The candidate includes the typed goal/fact/event lifecycle, local SQLite
backend, stdio MCP server, reference repository plugin, bounded staging and
inventory APIs, a manually invoked bounded event-router command, canonical
Markdown projection, review receipts, guarded purge/retry paths, and a
non-overwriting SQLite backup/restore-to-new-path command. Hermes
Core integration and Host Steward are separate source
changes in the Hermes Core repository; they are not part of this wheel. The
Vhost Manager consumer plugin and hook are installed in its isolated local
Hermes profile for alpha testing.
The separate V2-owned VS Code extension
`curatormd.curatormd-v2-status@0.9.0` is installed. It provides the project
dashboard, a bounded operational attention summary, review-queue display, and
attended review handoff. Its status item appears immediately to the right of
Git Graph. Gray means health has not been read, green means healthy, yellow
means unknown, red means degraded, and purple means review is pending when no
other degraded gate takes precedence. Purple is covered by focused UI tests;
the live project has no pending review to display it.

The last direct hover-level observation in the reloaded `renew_ssl` editor was
from 0.8.8: the item was yellow and reported unknown health with no SDE reviews
pending. Version 0.9.0 adds same-project health gate codes to the tooltip, but
the active editor must be reloaded before that detail is visible. Gray means
health has not been read; green means healthy; purple means an SDE review is
pending without another degraded gate; yellow means health or the review count
is unknown; red means another health gate is degraded.
The dashboard reads the bound `vhost-manager-alpha` project: 41 processed
receipts, 18 goals, 14 facts, no pending SDEs, and a complete empty staging
inventory. Storage reports `0 B / 250.0 MiB` at a warning-only threshold and
states writes remain allowed; model/token use is not reported in this view.
The last observed seven unknown dependency gates explain the yellow state.
This verifies the configured consumer editor and tooltip, not review/purge,
complete token coverage, or deployed monitoring. The Curator V2 backend
checkout remains a global backend, not a consumer project; it does not need a
consumer config or status-bar activation.

## Historical local-alpha snapshot (2026-10-26T14:38:13Z)

The supported `renew-ssl-coding` Hermes profile connects to the installed
Curator V2 stdio server, discovers 48 tools, and reads `vhost-manager-alpha`:
35 of 35 event receipts are processed, with zero received, failed, or
quarantined events. The ledger has 15 goals and 11 facts; lifecycle counts
(five planned, ten active, zero in the other six states) reconcile to the
paginated total. There are no SDE candidates or pending review/purge targets,
and the staging inventory is complete with zero files. The separately
timestamped project-health snapshot is `healthy`; the database observation and
all seven dependencies are healthy, with zero pending review, purge, or expiry
work. This verifies the bound local-profile read, not a real app-server event,
production identity, or general source coverage.

Prior package verification (2026-10-26): wheel SHA-256
`c1c3eb614e0dc85f5c9ebe28842316c6db8c59a748b14f05eb720ebb3bf3cee9` was
installed only in the dedicated `renew-ssl-coding` Curator V2 virtualenv after
the previous package, dist-info, and seven entrypoints were archived and
verified. The rollback archive SHA-256 is
`a865a4ff3ae737bdee5a9df538b9cba330bf6fd6c8aab0c28e7c49a6360b3452` with 117
manifest entries. All 61 installed Python module hashes match the source, and
`pip check` passes. The full local suite passes 465 tests; strict Pyright,
errors-only Pylint, Bandit, and the locked dependency audit pass. In a clean
Python 3.12 environment, both installed-wheel MCP tests pass, all seven CLI
entrypoints load, and storage backup/restore verifies the restored database.
The installed package then passed eight Vhost consumer contract tests and the
five-event Hermes-managed disposable integration. These checks use temporary
workflow state; they do not prove an authenticated person or a real certificate
renewal. The profile probe starts a fresh stdio process; existing long-lived
gateway, web, and editor MCP processes were not restarted, so their in-memory
imports are not claimed to have reloaded this wheel.

Current-source package refresh (2026-10-26): rebuilt from this checkout as
wheel SHA-256
`96ff9a085c0a8a7a80ee685a61b5986bcc58e9f102c185b169d1a004147f5a57` and
installed only in the dedicated profile virtualenv. Before replacement, the
prior package, metadata, and eight launchers were copied to a verified
130-file rollback archive at
`~/.hermes/profiles/renew-ssl-coding/backups/curator-v2-before-source-refresh-5e7wgdz5.tar.gz`
with SHA-256
`34222eaec1ed2d8e4080f85c5e2d686d4a3f3cfb922987b61d70a1b30d72568a`.
All 61 installed Python modules match this source tree byte for byte; `pip
check` passes. Pyright, errors-only Pylint, and Bandit pass on the current
source. A fresh Hermes-profile MCP probe still reads 29/29 processed receipts,
12 goals, eight facts, zero review/purge backlog, an empty complete staging
inventory, and healthy local-alpha dependencies. No service was restarted;
long-lived processes are not claimed to have reloaded the package. This
refresh does not prove a new app-server event, a real certificate renewal, or
human disposition of active goals. The disposable Hermes-managed Vhost
integration was rerun against this installed interpreter and passed five
events, exact replay and retry, lost-ack recovery after re-enrollment, source
epoch advancement, project/goal binding, Vhost projection reconciliation,
privacy-canary exclusion, and reviewer-write denial. It remains synthetic
app-server event evidence. The last full 465-test run applies to the prior
wheel above; the current source changes have focused test evidence recorded in
`persistence/HISTORY.md`.

Latest source refresh (2026-10-26): built wheel SHA-256
`f804deb41386b36c445d65f1e6bad283f139944836ffbf64ce8d2fd715f2430c` and
installed it only into the dedicated Vhost Curator V2 virtualenv. Before
replacement, archived the package, dist-info, and eight launchers in the
verified 141-entry archive
`~/.hermes/profiles/renew-ssl-coding/backups/curator-v2-before-wheel-f804deb4-20261026T1435Z.tar.gz`
(SHA-256 `74edd9c3e52cedd8c12ec9190d4f9656f5315507b6d7848fd17f336225fd4ce2`).
All 63 installed Python modules match source and `uv pip check` passes. The
current 478-test suite, strict Pyright, errors-only Pylint, Bandit, locked
dependency audit, and `git diff --check` pass. Both installed-wheel MCP tests,
all eight command entrypoints, and installed storage backup/restore pass. The
Hermes-managed disposable Vhost integration passes five bounded events,
including retry/replay, re-enrollment, goal binding, projection reconciliation,
and privacy checks. The fresh profile read remains healthy at 35 processed
receipts. No gateway or Vhost service was restarted; a real active-gateway
app-server event and a new live Vhost operation are still unverified.

The local Vhost Manager HTTP service has applied and rolled back reserved
`.test` sites through its real routes. Exact receipts were processed, compact
operation facts were projected and reconciled for the latest apply/rollback,
and the disposable site/account were removed. The route test does not cover
every producer or out-of-root artifact. Five earlier operation goals remain
planned; the two latest apply/rollback review goals remain active pending human
disposition. The 2026-10-26 read-only browser capture also rendered the local
Vhost home page and revalidated its content-free digest; this did not exercise
an authenticated browser session or application operation. No SDE decision or
artifact purge is claimed.

The approved alpha remains one local OS reviewer (`eaglesvn`), one repository
at a time, with a six-hour local purge schedule and a 72-hour maximum transient
artifact age. The Vhost standalone utility source/artifact coverage is closed
for the owner-reviewed dirty development snapshot; see
[`vhost-producer-coverage-v2.md`](vhost-producer-coverage-v2.md). Production
scheduling, identity, alerting, retention policy, recovery drills, and release
sign-off remain outside this local-alpha evidence.

## Runtime and verification scope

The package declares Python `>=3.12,<4`. The CI workflow exercises Linux with
Python 3.12, 3.13, and 3.14, runs the locked unit suite and quality/security
checks, and installs a freshly built wheel into a clean environment for an MCP
launcher acceptance test. A passing run proves those source/package checks for
the exact commit only.

## Known limitations

- Local alpha project access uses the kernel-reported real/effective OS UID as
  the authorization subject, while Hermes profile/session values stay separate
  routing context. The approved `eaglesvn` UID is the local alpha reviewer and
  has exact project read/write/review grants. Hermes still reports MCP transport
  auth as `none`; a Hermes-authenticated human subject and production identity
  binding are not established.
- Trusted repository, service, browser, and human evidence adapters remain
  reject-all/reference implementations until their trust roots are approved.
- No production router, scheduler, or monitoring/alert delivery is established
  by this alpha. Real local Vhost operation events are captured as bounded
  operation summaries; prompt/response content and manual DNS values are not
  included. This does not establish coverage for every standalone producer.
- Local-alpha retention defaults and hold semantics are owner-approved: the
  listed transient artifact classes become eligible promptly after recording
  and SDE disposition, with a hard 72-hour maximum age. Pending SDE review
  delays prompt expiry but does not extend that ceiling; the SDE remains
  reviewable from canonical facts after its transient source expires. Explicit
  legal/operational holds require a separate release and are the only local
  alpha exception. Production retention policy, external hold discovery,
  backup/restore drills, and deployment rollback remain open.
- Historical Vhost deployment checkpoints are listed below. The current
  workflow and ledger status are summarized at the top of this document; those
  dated checkpoints must not be read as the latest state. The Vhost Manager
  local alpha pilot is installed and its seven consumer contracts pass,
  including a synthetic bounded event through the profile hook,
  installed MCP launcher, Curator V2 store, and Hermes outbox receipt path. On
  2026-10-21, the matching Hermes Core lifecycle-hook/outbox files and
  root-owned Host Steward plugin were installed into the local runtime with a
  recoverable file backup, and `hermes-gateway.service` restarted successfully.
  The `renew-ssl-coding` profile MCP test connects and discovers 45 tools. The
  Vhost hook was corrected to gate on the bound project ID because Hermes'
  durable outbox intentionally omits `cwd`; the installed source/profile hook
  hashes match. A fresh profile session replayed Hermes source sequences 1-9,
  including the previously stuck sequence 2, and all were acknowledged. The
  current session's persisted project/goal binding matches; Curator's Vhost
  inbox cursor is 9 with 10 processed receipts, and its SQLite store passes
  `PRAGMA quick_check=ok`. The Curator payload rows for those source events do
  not retain raw payload JSON. This verifies live event delivery for the local
  alpha profile, not cryptographic identity or production authorization. A
  natural-language CLI response claimed the bind failed, but persisted Hermes
  binding and Curator receipt records confirm it completed. The consumer test
  suite passes seven contracts; its composed disposable-checkout case writes
  and reconciles Hermes-derived facts through the configured Markdown adapter,
  while canaries and an out-of-scope target remain absent/unchanged. This is
  local consumer-adapter evidence, not a production target write. A focused
  Hermes suite passes 58 tests and
  `python3 scripts/check` passes 12 checks. A fresh focused Hermes
  gateway/outbox/MCP run passes 38 tests. The current repository wheel was
  installed into the isolated Vhost profile on 2026-10-21; its SHA-256 is
  `fcce3c0e343c79a7e800153131e0dd4b43a02087055dd6a6a257f9cbe01e688f`, and all
  32 installed Python modules match the current Curator source. The focused
  shell-hook suite has one
  known profile-isolation failure (52 passed, 2 skipped); its direct config
  compatibility probe passes. Curator's 336-test suite, strict Pyright,
  errors-only Pylint, Bandit, dependency audit, and diff check pass. This is a
  local alpha deployment; identity, retention, backup/recovery, and release
  approval remain open. The current profile-bound V2 `project_health` read is
  `unknown`, with zero pending/failed/quarantined events and unknown required
  probes for the event router, purge scheduler, host identity, human review,
  and artifact-producer inventory. Processed receipts do not make the overall
  service healthy.

Latest profile-session evidence (2026-10-21): a one-shot Hermes Codex
app-server turn was run from the Vhost Manager checkout. The CLI's natural-
language response claimed that the bind failed, but authoritative read-only
Hermes and Curator state confirms source sequences 10 and 11 were acknowledged
once and processed/applied against the persisted profile/project/goal binding.
The V2 store now has 12 processed receipts; both new receipt payloads were
cleared after processing, and `PRAGMA quick_check=ok`. This verifies that
one-shot profile route. `hermes --profile renew-ssl-coding gateway status`
reports only the default-profile PID, so this does not establish that the
isolated profile is served by the running gateway. No Vhost Manager UI/request
workflow or canonical application-target write was exercised, and
`project_health` remains `unknown`.

Vhost alpha lifecycle deployment (2026-10-23): rebuilt and installed wheel
`curatormd_v2-0.1.0a1-py3-none-any.whl` (SHA-256
`d14df4b3e01fea66363fd98dcb409b42bb3170014702dd4c93ab718610a719d5`) into the
isolated `renew-ssl-coding` profile. The profile is configured for local-alpha
review and write. The active SQLite ledger was backed up while at schema v35
before migration to schema v36; both the live DB and a disposable migrated copy
pass `PRAGMA quick_check=ok` and retain the active Vhost project/binding, with
exactly three active grants for `local-uid:1000` (read, write, review). Obsolete
`renew-ssl-coding` subject grants were revoked.
Hermes MCP connects and discovers 48 tools. Its profile outbox currently has
11 acknowledged events, no pending events, and 22 attempts; the Curator ledger
has 12 processed receipts. These counts are independent reads, not a claim that
all events correspond one-to-one. The 0600 DB, package, and profile-config
recovery copies are under `/home/eaglesvn/.local/share/curatormd-v2-alpha/
backups/`. Terminal event disposition now requires an exact failed-event digest,
fenced binding revision and source epoch, attended exact confirmation, and
contiguous source order; it preserves an immutable decision receipt and lets
the Hermes outbox acknowledge that processed receipt. The full Curator suite
passes 438 tests; strict Pyright, errors-only Pylint, Bandit, and
`git diff --check` pass. This verifies only local alpha identity and lifecycle behavior;
the deployed attended `view` returns a complete, time-stamped snapshot with 12
processed events and no unresolved events. Production identity, production
acceptance, and rollback drills remain open. The active Vhost project was not
retired.

Vhost alpha endpoint check (2026-10-21): `hermes -p renew-ssl-coding gateway
ensure --json --timeout 45` returned `state=ready` with a profile-scoped
systemd endpoint. `hermes --profile renew-ssl-coding mcp test curator_v2`
connected and discovered the 45-tool server surface; Hermes reports transport
auth as `none`. This verifies the isolated profile deployment and tool
discovery. It does not establish authenticated identity, make `project_health`
healthy, or exercise a Vhost application request or canonical target write.

Local alpha readiness recheck (2026-10-21): the full Curator V2 suite passes
338 tests on Python 3.12, including a partial-child regression that preserves
completed child history without completing its parent. Strict Pyright reports
zero diagnostics; errors-only Pylint, Bandit, locked dependency audit, lock
check, and `git diff --check` pass. The installed Vhost consumer contract passes all seven tests against the
isolated alpha wheel. Hermes Core's focused gateway/outbox/MCP suite passes 38
tests and `python3 scripts/check` passes all 12 checks. This meets the local
backend, repository-plugin, and Hermes-route acceptance bar for the Vhost
application smoke test. The profile already has the matching wheel installed;
no Vhost application UI/request or canonical target write was exercised by
these checks. The smoke test must continue to keep production identity,
retention, recovery, and release gates open.

Alpha deployment recheck (2026-10-21): the isolated `renew-ssl-coding` gateway
ensure again returned `state=ready`; `hermes --profile renew-ssl-coding mcp test
curator_v2` connected and discovered 45 tools. The installed Vhost consumer
contracts pass 7/7. Hermes Core's focused lifecycle-hook, durable-outbox, and
trusted-MCP suites pass 42 tests, and `python3 scripts/check` passes all 12
checks. A profile-mediated `curator-v2 bind` interaction did not return a
binding result; read-only Curator state remains one active alpha goal, 12/12
processed receipts, source cursor 11, zero stored inbox payload JSON, and
`PRAGMA quick_check=ok`. The live goal operation and Vhost application request
workflow therefore remain open. `project_health` is still `unknown`; these
checks do not establish authenticated identity, retention approval, or
production readiness.

Latest local package verification (2026-10-21): the shared bounded CLI limit
parser is present in the installed profile environment and its SHA-256 matches
the source module (`b0492667c355411951430c031f8d2dedafa5cda9f3fd2110cc93b655400b23c0`).
The rebuilt wheel SHA-256 is
`ad6ee0e214757e007765dafa806539be3fcea6fdfb2134a48484ad08dcfa1192`. The full
Curator suite passes 340 tests; strict Pyright, errors-only Pylint, Bandit,
dependency audit, and lock check pass. All seven installed Vhost consumer
contracts pass; Hermes MCP discovery connects and exposes 45 tools, and Hermes
Core `python3 scripts/check` passes 12 checks. This is local alpha package and
consumer evidence. The Vhost application request workflow, canonical
application-target write, `project_health` (still `unknown`), authenticated
identity, retention, recovery, and release approval remain open.

Latest profile call probe (2026-10-21): an unattended Hermes session started
from the Vhost Manager checkout reached the `renew-ssl-coding` profile, but
the initial Curator V2 `goal_list` call was rejected with `user rejected MCP
tool call`. No goal, binding, or receipt was created by this attempt. The
profile's interactive MCP approval path remains unresolved; tool discovery and
the installed consumer contract do not prove a successful profile-mediated
request. The Vhost application workflow and canonical target write remain
unverified.

Latest alpha wheel retest (2026-10-21): wheel SHA-256
`b141087b8f9359097d5246195d8c9a09cc60a8fae37dfb128539956c267f94b3` is
installed in the dedicated `renew-ssl-coding` virtualenv, with all 34 package
module hashes matching source. The seven Vhost consumer contracts and the
Hermes-managed disposable integration harness pass; profile MCP discovery
connects with `auth=none` and exposes 46 tools. A read-only profile database
check after the v18 migration reports `quick_check=ok`, one goal, two facts, 12
processed receipts, zero retained inbox payload JSON bytes, and both new SDE
context columns. No Vhost repository source or application data changed. This
does not resolve the separate interactive MCP approval rejection, establish
authenticated identity, or exercise the Vhost application workflow.

Current source package recheck (2026-10-21): rebuilt wheel SHA-256 is
`2773a8e05fc28dc8e45c236b75e208428c276cfa201a98de96891c616cc2bb0e` and is
installed in the isolated Vhost alpha profile. All seven installed consumer
contracts pass, MCP discovery exposes 45 tools, and the installed
`markdown_persistence.py` and `project_plugin.py` hashes match Curator source.
The full Curator suite passes 342 tests, strict Pyright reports zero
diagnostics, errors-only Pylint and Bandit pass, and dependency audit and lock
check pass. The profile-mediated `goal_list` call remains approval-rejected;
the Vhost application workflow and canonical target write remain unverified.

Latest Curator source package (2026-10-21): after the purge exception-path
fix, wheel SHA-256
`ed728e38b88ef208e47d6a48ae6ee2982531703cd6eedf51ceb82aca5f695d77` is
installed in the isolated Vhost profile. The full Curator suite passes 343
tests; the 22-test purge suite passes; strict Pyright, errors-only Pylint,
Bandit, dependency audit, and lock check pass. All seven installed Vhost
consumer contracts pass, MCP discovery exposes 45 tools, and installed purge,
Markdown persistence, and project-plugin modules match source hashes. The
profile-mediated goal call remains rejected; the Vhost application workflow,
identity, retention, recovery, and release gates remain open.

Latest Curator source package (2026-10-21): wheel SHA-256
`f2c4ffa40bf33bb35d5925436911eabc9c93dcbeed149aa6212ef2bd275a5383` is
installed in the isolated Vhost alpha profile. The full Curator suite passes
344 tests; all seven installed Vhost consumer contracts pass, MCP discovery
exposes 45 tools, and installed store, purge, Markdown persistence, and
project-plugin modules match source hashes. The profile-mediated goal call
remains approval-rejected; no Vhost application request or canonical target
write is verified.

- V1 is outside this V2 alpha and is not an import source or rollback target.
  In the Vhost Manager Hermes profile, the legacy Curator MCP entry is disabled
  and the `curatormd-observer` hook now declares no events; the profile hook
  loader skips it. On 2026-10-21, the scheduled V1 `curatormd.py` jobs in the
  `renew-ssl-coding` and `curatormd-coding` Hermes profiles were paused; their
  historical data was retained. These profile checks do not establish shutdown
  of every possible V1 runtime elsewhere. Host checks found no V1-named
  systemd unit, Docker container, or matching process; these name-based checks
  are not an exhaustive audit of every possible runtime.

Keep alpha capture limited to the installed local Vhost Manager lifecycle hook.
It records bounded session/goal metadata and excludes prompt/response content.
The approved local retention policy allows prompt expiry eligibility and a
hard 72-hour maximum age even with pending SDE review. Explicit legal or
operational holds remain exceptions until separately released; purge still
requires the attended local UID review and an exact durable receipt. Do not broaden capture or enable an
unattended production cleanup path until production retention and recovery
policies are approved. Preserve existing canonical records and staged evidence
while evaluating this candidate. See the
[`release-gate ledger`](release-gates-v2.md) for the remaining V2 evidence
and approvals.

Vhost profile endpoint recheck (2026-10-22):
`hermes -p renew-ssl-coding gateway ensure --json --timeout 45` returned
`state=ready` under the systemd supervisor with a profile-scoped endpoint and
durable-admission, event-replay, and session-authority capabilities. The
profile's Curator MCP stdio test connects and discovers 46 tools, with transport
auth reported as `none`. A subsequent gateway status lists only the default
gateway PID; the endpoint handshake and stdio discovery do not prove an
interactive profile tool call, authenticated identity, Vhost application
workflow, or canonical application-target write.

Local alpha wheel deployment (2026-10-22): installed the wheel built from
Curator commit `060b325` into the dedicated `renew-ssl-coding` Curator V2
environment. The seven Vhost consumer contracts pass (7/7), as does the
Hermes Core managed-MCP disposable harness with three processed lifecycle
events, retry/replay, binding checks, and projection reconciliation. Installed
`project_plugin.py`, `store.py`, and `mcp_server.py` hashes match source.
`hermes -p renew-ssl-coding mcp test curator_v2` discovers 47 tools but reports
`auth=none`; gateway status lists only the default-profile PID. The install and
disposable tests do not establish interactive profile authorization or a live
Vhost application request.

Current source package recheck (2026-10-22): built from Curator commit
`24cae4c`, wheel SHA-256
`3f552edf5edafa9f509a491e385dfc6286751e99ebf1cf5dd7dddead5d62ca1a`, and
installed in the dedicated `renew-ssl-coding` Curator V2 environment. Hashes
match all 35 installed Python modules. All seven Vhost consumer contracts pass,
and the Hermes Core managed-MCP disposable harness passes with three processed
events, exact replay, failed-delivery retry, explicit binding checks, denied
reviewer persistence, reconciled projection, and absent private/out-of-scope
canaries. MCP discovery exposes 47 tools with `auth=none`. Read-only SQLite
reports schema 20, `quick_check=ok`, one goal, two facts, 12 inbox receipts,
and two project grants. Gateway status lists only the default-profile PID.
These checks verify the current package and local plugin composition. They do
not verify an interactive profile tool call or live Vhost application request;
authenticated identity, production policy/recovery, and live runtime gates
remain open.

## 2026-10-27 installed alpha staging-budget refresh

The current Curator source wheel was rebuilt as
`curatormd_v2-0.1.0a1-py3-none-any.whl` (SHA-256
`0fe468fcd209ef39cca85b6e986b1cb7907fa85a8ff2ffc510dce4358ec72159`) and
installed in the dedicated `renew-ssl-coding` Curator V2 virtualenv. Before
replacement, the installed distribution files were archived at
`/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-pre-fifo-20261026T173915Z.tar.gz`
(104 members; SHA-256
`da915d01d53f459f4c91ef4356677931083368da62979797e649468d4bbf8c2d`). All 87
installed Python modules match the source byte for byte and `pip check` passes.

The installed package loads the Vhost consumer config as
`vhost-manager-alpha` with a 262,144,000-byte (250 MiB) staging warning
threshold and no project file-count limit.
An installed-module check confirms expired cleanup candidates are ordered by
staged age, oldest first. The 17 staging-writer tests, 19 storage/expiry tests,
strict Pyright, and `git diff --check` pass. This refresh used only disposable
data; no gateway/service was restarted, no real renewal was run, and no artifact
was deleted. Real interactive app-server delivery, user identity, and release
gates remain open.

## 2026-10-27 staging-warning refresh

The warning-gate update was rebuilt as wheel SHA-256
`c9a1c8b3f068b20b780c4a0461ea83c8839c0f42400c4175b57ac6844a2bed50` and
installed in the same isolated alpha virtualenv. Before replacement, the
previous package was archived to
`/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-pre-budget-warning-20261026T174403Z.tar.gz`
(104 members; SHA-256
`130447b3722854ebbf4e09c0478225c9c5401952069bf97bbcf1d56f16eaa802`). All 87
installed Python modules match source, and `pip check` passes.

Project health and Prometheus emit `staging_budget_warning` at 75% of the
configured byte threshold and `staging_budget_reached` at or above the
threshold. Both are warnings only; staging writes continue, subject to the
independent per-artifact and per-goal hard limits. The health/metrics regression
suite passes 16 tests and checks
the 75% boundary and a below-threshold case. The installed helper and Vhost
config were read back successfully. No gateway process was restarted, so this
documents the installed package contents, not a reload by an already-running
MCP process. External journal/alert delivery remains open.

The owner-approved consumer config is now registered in the local alpha ledger
at revision 2 with its current config fingerprint. The attended update receipt
uses transition `vhost-manager-alpha-staging-budget-20261027`; read-only SQLite
inspection confirms the exact config hash and all five existing read/write/
review grants remain. A fresh Hermes Core `renew-ssl-coding` profile probe now
connects to the installed MCP package and reads the project: 35/35 receipts are
processed, 15 goals and 11 facts reconcile, the staging inventory is complete
and empty, and health is `healthy` with no gates. This is a profile-context
read, not a real interactive app-server turn or a live Vhost operation.

## 2026-10-27 warning-only threshold correction

The owner clarified that 262,144,000 bytes (250 MiB) is a warning threshold,
not a staging write limit, and that project file count is irrelevant. The Vhost
consumer config now sets only `max_project_bytes`; registration revision 3
binds its SHA-256 `a37448f38683c864480d4f90db8fc6a6b694311679b598979f86ff574713f746`
under transition `vhost-manager-alpha-byte-warning-only-20261027`. Curator
health warns at 75% and reports `staging_budget_reached` at or above the
threshold while accepting new writes. Per-artifact/per-goal safety limits and
complete-inventory checks remain active.

The updated wheel SHA-256 is
`56ab545000bfa9e1161a1d133674b28534fa6b1ab4343f027bb310288ee35573`. Before
installation the previous package was archived at
`/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-pre-warning-only-20261027.tar.gz`
with SHA-256
`0b8d65b56949cee73a1969aeebe7ddf9c397023ab4a066d76567d9faaf219d96`. All 87
installed Python modules match source, `pip check` passes, and the profile
status probe reads 35/35 receipts, 15 goals, 11 facts, and healthy status with
a complete empty staging inventory. Focused tests verify warnings and writes
above the threshold; the real profile has not crossed 250 MiB. No service was
restarted, and no real certificate renewal or artifact deletion was performed.

At this historical snapshot, the local VS Code integration was packaged as
extension 0.8.4. Its dashboard shows project goal-state totals and
event/review/purge/expiry queue counts from authorized project snapshots, plus
concise warnings for current event, review, cleanup, readiness, and staging
conditions. The current installed extension is 0.8.8 and its `extension.js`
hash matches this checkout. After reloading the ordinary `renew_ssl` editor,
the gray hover rendered `CuratorMD V2 0.8.8. Gray means no health read has been
attempted. Click to open the project dashboard.` Clicking the item in that
configured consumer then read project health as `unknown` with seven
unverified dependency gates; the status changed to yellow, and the hover read
`CuratorMD V2 0.8.8. Yellow means health or the SDE review count is unknown.
Project health: unknown, no SDE reviews pending. Click to open the
project-scoped dashboard.` The dashboard showed 41 processed
receipts, 18 goals, 14 facts, zero pending SDEs, and a complete empty staging
inventory. Green means healthy with no pending reviews; purple means pending
SDE review when no other degraded health gate takes precedence; red means
another degraded health gate; yellow means unknown, unavailable, or incomplete
status. Activation in the unconfigured backend workspace remains unverified.
This package install does not change the Vhost application or backend project
configuration.

## 2026-10-28 local storage-view package refresh

The current source wheel
`curatormd_v2-0.1.0a1-py3-none-any.whl` (SHA-256
`3dcd2e577b8cf6c9f068720dd49035e0203f6ca96c6726c65a48c2947accc149`)
was installed only in the dedicated `renew-ssl-coding` Curator V2 virtualenv.
Before replacement, 188 installed package, metadata, and launcher files were
archived at
`/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-before-storage-metrics-20261028.tar.gz`
(SHA-256
`dadd754c36b5005ef852d848604ee0e588290315e1805715572c4f181b959b13`);
its sidecar manifest was verified against every archived file. All 88
installed Python modules now match source, the backup measurement import
succeeds, and `uv pip check` passes. No service was restarted.

The attended, read-only Vhost access view reports a 524,288-byte SQLite main
file, a 168,952-byte WAL, and 3,145 logical control-plane bytes across 11
classes. The backup-directory scan remains incomplete: it recognizes one
524,288-byte daily snapshot but reports 20 unclassified entries. The full
directory has 21 entries and measures 4,618,625 logical / 4,636,672 allocated
bytes; no files were changed or deleted. Retention and local warning thresholds
for those unclassified recovery files remain open.

## 2026-10-28 local backup-tree accounting

Curator's bounded backup-directory reader now includes observed counts and
logical/allocated bytes for regular files across nested directories. It does
not open file contents or follow symlinks, and retains separate totals for
recognized daily SQLite snapshots. The refreshed wheel SHA-256 is
`c4c4d265c7cb82dd6cd4ba100a95746ca3fd612c48615c0ccba68914fbef1543`.
Before installation, 183 package, metadata, and launcher files were archived
and hash-verified at
`/home/eaglesvn/.hermes/profiles/renew-ssl-coding/backups/curator-v2-pre-backup-tree-metrics-20261028.tar.gz`
(SHA-256
`afc393c1eca11d00dee8ca091651d55b1b717be84ffcae224d4bf1d7281f6af9`).
All 88 installed Python modules match source, and `uv pip check` passes.

The attended read-only Vhost view reports 21 observed entries, 19 regular
files, 4,618,625 observed file bytes, and 4,636,672 allocated bytes. One
524,288-byte daily snapshot is recognized; 20 other entries remain
unclassified, so status remains incomplete. The scanner traversed the bounded
tree without reading file contents or following symlinks. No service was
restarted and no backup entry was moved, changed, or deleted. Retention and
warning levels for the unclassified recovery material remain open.
