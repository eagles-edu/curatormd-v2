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

## Runtime and verification scope

The package declares Python `>=3.12,<4`. The CI workflow exercises Linux with
Python 3.12, 3.13, and 3.14, runs the locked unit suite and quality/security
checks, and installs a freshly built wheel into a clean environment for an MCP
launcher acceptance test. A passing run proves those source/package checks for
the exact commit only.

## Known limitations

- Hermes profile and project values are operator assertions; authenticated
  human and Hermes identity binding is not implemented.
- Trusted repository, service, browser, and human evidence adapters remain
  reject-all/reference implementations until their trust roots are approved.
- No production router, scheduler, monitoring/alert delivery, or real
  interactive capture event is established by this alpha. The local Vhost
  Manager pilot has only the bounded lifecycle hook described below.
- Local-alpha retention defaults and hold semantics are owner-approved: the
  listed transient artifact classes become eligible promptly after recording
  and SDE disposition, with a 72-hour maximum-age fallback. Pending SDE review
  pauses expiry until disposition; explicit legal/operational holds require a
  separate release. Production retention policy, external hold discovery,
  backup/restore drills, and deployment rollback remain open.
- The Vhost Manager local alpha pilot is installed and its seven consumer
  contracts pass, including a synthetic bounded event through the profile hook,
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
72-hour maximum-age fallback, but purge still requires the attended local UID
review and an exact durable receipt. Do not broaden capture or enable an
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
