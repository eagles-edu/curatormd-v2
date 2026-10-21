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
- Retention policy, legal/operational holds, production backup/restore and
  recovery drills, and deployment rollback have not received owner approval or
  deployment-like verification.
- The Vhost Manager local alpha pilot is installed and its seven consumer
  contracts pass, including a synthetic bounded event through the profile hook,
  installed MCP launcher, Curator V2 store, and Hermes outbox receipt path. On
  2026-10-21, the matching Hermes Core hook/outbox files and root-owned
  Host Steward plugin were installed into the local runtime with a recoverable
  file backup, and `hermes-gateway.service` restarted successfully. The
  `renew-ssl-coding` profile endpoint reports `state=ready`; MCP discovery
  connects and exposes 45 tools. Two real profile sessions created Hermes
  session-to-goal bindings and bounded Codex lifecycle outbox entries. The
  earliest unacknowledged event has eight delivery attempts; Curator still has
  only the two earlier processed receipts, so live event delivery is not
  verified. The first session exposed a JSON-text result parsing bug in the
  consumer hook; the handler now parses that bounded result and all seven
  consumer contracts pass. A focused Hermes suite passes 58 tests and
  `python3 scripts/check` passes 12 checks. The focused shell-hook suite has one
  known profile-isolation failure (52 passed, 2 skipped); its direct config
  compatibility probe passes. Curator's 336-test suite, strict Pyright,
  errors-only Pylint, Bandit, dependency audit, and diff check pass. This is a
  local alpha deployment with an open live-delivery and rollback gate, not an
  owner-approved release.
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
Do not broaden capture or enable destructive cleanup until the retention and
recovery policy is approved. Preserve existing canonical records and staged
evidence while evaluating this candidate. See the
[`release-gate ledger`](release-gates-v2.md) for the remaining V2 evidence
and approvals.
