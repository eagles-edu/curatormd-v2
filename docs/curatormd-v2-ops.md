# CuratorMD V2 local-alpha operations

## Authority and scope

The owner-only manifest at `~/.config/curatormd-v2/ops-curatormd-v2-dev-alpha.json`
is the binding authority for project `curatormd-v2-dev-alpha`. It pins UID 1000,
this repository root, the global SQLite database, and the exact Hermes profile.
The monitor never rewrites a missing or conflicting manifest. Such conditions
raise an incident and require owner review before any identity change.

Runtime state and private incident/back-up records live under
`~/.local/state/curatormd-v2/curatormd-v2-dev-alpha/ops`. Each changed artifact
must have a mode-0600 before-image, SHA-256, and restore instruction recorded
before mutation. Retain incident snapshots until closure plus 30 days.

## Commands

Run these commands from the local-alpha checkout. The wrapper is installed in
that checkout's virtual environment and is not added to the user's shell
`PATH`.

```sh
OPS=/home/eaglesvn/dockerz/curatormd-v2.0/.venv/bin/curatormd-v2-ops
"$OPS" initialize-manifest
"$OPS" check --json
"$OPS" maintain
"$OPS" monitor
```

`check` is read-only except for deduplicated incident capture and AI dispatch.
One-shot checks do not reconcile abandoned diagnosis jobs or close recovered
incidents; only the resident monitor owns those transitions. `maintain` makes a
verified daily backup, runs the compatible maintenance
runtime, and retries only already-authorized due purges. `monitor` checks every
60 seconds and delegates six-hour maintenance. The systemd unit caps the
resident service at 5% CPU and 64 MiB RSS; the steady-state average CPU target
is under 1%.

## Failure and repair policy

Every missing, stale, malformed, failed, or mismatched observation produces a
sanitized, fingerprint-deduplicated incident. One Codex run may diagnose at a
time. Source fixes belong in a managed worktree and must include tests; they
are proposals only. Installation, grants, project identity, purge approvals,
destructive operations, and active-database replacement require owner action.
Each incident records every inspected node, a bounded failed-event inventory
without payloads, and the VS Code dashboard telemetry handoff. A changed event
ID or dashboard node state changes the incident fingerprint and starts a new
diagnosis. The diagnosis prompt requires an explicit node-state summary and
evidence gaps before proposing a repair. If the dashboard has not supplied a
fresh snapshot, its state remains unavailable, opens a gate, and is included
as a gap; the coordinator never reports healthy with missing dashboard state.
Codex diagnosis runs in a separate transient unit, so a slow or retried AI run
does not hold up the 60-second monitor. Each run has a five-minute process
deadline, an additional five-second systemd margin, multi-agent delegation
disabled, an 8,192-token context window, a 6,144-token compaction threshold, a
2,048-token tool-output budget, and low reasoning effort. The prompt limits
investigation to eight tool calls and one focused test. Reported usage counts
`input_tokens + output_tokens`; cached input is already included in
`input_tokens`. Usage is checked at each completed turn and stops the run at
24,000 cumulative tokens. Codex CLI does not expose a hard in-flight per-run
token cap, so wall/context/output limits bound a single turn while the token
counter provides a secondary stop. Transient failures retry after five minutes,
then with exponential backoff capped at one attempt every six hours. A completed
diagnosis remains a proposal; installation and deployment still require owner
action. Token-budget exhaustion or unobservable token usage ends that diagnosis
as a non-blocking warning, does not retry automatically, and does not change
component health or gates. The warning is included in check and journal output
for up to 24 hours; the incident still closes only after the monitored
components recover.
The Hermes
health probe runs separately from the resident
coordinator in a transient systemd unit with a 60-second timeout, 512 MiB cap,
and 50% CPU quota; the resident monitor has a 5% hard ceiling, 64 MiB cap, and
under-1% steady-state average CPU target.
The monitor reconciles expired queued or running diagnosis records against
their transient systemd unit. An inactive unit becomes a terminal timeout or
dispatch failure so a later healthy check can close the incident; unknown
unit state leaves the incident open for owner review. The resident monitor
closes recovered incidents only after its history sample and latest-check
record are written successfully. A failed write remains a gate, is reported
in the journal, and is retried on the next pass.
Additive migrations require a consistent pre-change snapshot and passing
SQLite integrity and foreign-key checks afterward. A failed foreign-key check
is recorded in snapshot metadata before an additive repair; it is never hidden.

## Operational inventory

| Observation | Owner / source of truth | Interval | Success signal | Failure and automatic action | Escalation / regression |
| --- | --- | ---: | --- | --- | --- |
| Project ID | Curator project config plus owner manifest | Every check | Both equal `curatormd-v2-dev-alpha` | Incident; no identity rewrite | Owner review; binding-conflict test |
| OS UID | Process credentials plus owner manifest | Every check | UID 1000 | Incident; no identity rewrite | Owner review; UID-mismatch test |
| Repository root | Installed source path plus manifest | Every check | Exact canonical root | Incident; no path rewrite | Owner review; root-mismatch test |
| Database path | Project binding plus manifest | Every check | Exact canonical DB path | Incident; no DB rebinding | Owner review; DB-mismatch test |
| Hermes profile | Pinned Hermes venv Python calls the profile-bound MCP test API directly; owner manifest binds exact profile and command | Every check | Exact `curatormd-v2-dev-alpha` profile; seven fresh dependencies and complete queue snapshot | Incident; no profile rewrite; bypasses ordinary Hermes CLI startup and its pending-update path | Owner review; profile-mismatch and CLI-update-bypass tests |
| Runtime and schema | Venv executable and SQLite `user_version` | Every check | Executable present; schema matches source | Degraded incident; no fallback to incompatible code | Tested worktree patch; schema/runtime tests |
| SQLite health | Active database, read-only `integrity_check` and `foreign_key_check` | Every check | Both pass | Incident; snapshot before any additive repair | Owner gets exact restore steps; integrity/FK tests |
| Daily backup | SQLite online backup under DB `backups/` | Daily and before migration | Fresh, mode-private, integrity-checked copy | Retry once; retain failed metadata | Incident; backup/restore tests |
| Backup retention | Hash-verified snapshot sidecar plus matching closed incident record | At monitor start when due, at least daily | Incident snapshots remain through closure + 30 days; private completion receipt is fresh | Delete only an owner-owned, mode-private snapshot with matching SHA-256 and closed incident older than retention; retain malformed, unlinked, open, and mismatched evidence and surface a gate | Expiration, idempotence, missing-link, malformed-record, permissions, and restore tests |
| Resident monitor | User systemd service and journal | 60 seconds | Active, bounded, last-check timestamp advances | systemd restart; incident on repeated failure | Owner journal steps; restart test |
| Maintenance timer | Exact project systemd timer | Every check; six-hour schedule | Timer active and successful wrapper receipt fresh | Incident; monitor uses bounded fallback only when timer is inactive | Timer failure/repeat test |
| Maintenance | Project timer invokes the ops wrapper | Six hours | Successful marker and authorized purge receipts | Bounded retry; no new approvals; repeated failure stays degraded and deduplicated | Incident; runtime, timer, and repeated-repair-failure tests |
| Shared freshness policy | Hermes health, database, staging, and dependency timestamps | Every check; max age 180 seconds | All observation timestamps are present, valid, and fresh | Stale/missing is degraded and dispatches one incident | Missing/stale timestamp tests |
| Event router | Profile-bound health dependency | Every check | Healthy and fresh | Incident; no data replay without existing receipt rules | Dependency failure test |
| Purge scheduler | Profile-bound health dependency and prior receipts | Every check | Healthy; only existing approvals processed | Incident; bounded maintenance retry | No invented approval; scheduler test |
| Database storage adapter | Profile-bound health dependency | Every check | Healthy and fresh | Incident; no active DB replacement | Dependency failure test |
| Host identity | Profile-bound health dependency | Every check | Healthy and matches manifest binding | Incident; freeze identity writes | Conflict test |
| Human review | Profile-bound health dependency | Every check | Healthy | Incident; review decisions remain human-owned | Dependency failure test |
| Alert delivery | Profile-bound health dependency | Every check | Healthy and fresh | Incident; journal remains available | Dependency failure test |
| Artifact producer inventory | Profile-bound health dependency | Every check | Healthy and inventory complete | Incident; no purge on incomplete inventory | Completeness test |
| Queue snapshot | Active DB event inbox and profile probe | Every check | All event and operational counts are present, nonnegative integers; oldest-event age is valid; DB and staging snapshots are complete and fresh | Incident; never infer empty from missing or malformed fields | Queue-missing/malformed test |
| Failed-event inventory | Project event inbox, read-only metadata query | Every check | No failed or quarantined event; inventory is complete and limited to 50 identifiers with status, source, digest, attempt count, and safe error class | Start a failure-node diagnosis; never read or send payload JSON | Late completed-goal fact fixture and payload-privacy regression |
| VS Code dashboard telemetry | Extension handoff under the project ops state directory | Every dashboard refresh; max age 180 seconds | Current project/profile snapshot contains refresh, Hermes, queue, event-processing, operational-log, and health-history node states | Missing, stale, invalid, or degraded state opens a gate and starts a failure-node diagnosis | Dashboard handoff shape, privacy, permissions, and stale-snapshot regression |
| VS Code health | Installed extension dashboard and configured profile | Every alpha acceptance run | Same project/profile and all seven dependencies shown | Incident and tested proposed patch | VS Code health-proof suite |
| Journal reporting | User journal, content-free incident records | Every minute and on recovery | One bounded record exposes status, gates, incident ID, component age, and next action | Keep degraded/unknown visible without logging payloads, paths, or exception details | Journal privacy regression and live journal entry |
| Acceptance history | Owner-private daily JSONL samples | Every minute; latest sample is no older than 180 seconds | Current-day file and each existing history file are regular, owner-owned, and mode-private; every current-day record is bounded, valid JSON with a timezone-aware ordered timestamp, status, gates, incident ID, and monitor sample | Missing, stale, malformed, unreadable, or non-private evidence creates one deduplicated incident; missing-file grace is limited to the first 120 seconds after monitor start | Missing/warm-up, stale, malformed, oversized-line, timestamp, permissions, and incident-deduplication tests |
| Resource use | systemd cgroup limits and sampled service stats | Continuous | CPUQuota 5%, MemoryMax 64 MiB, steady-state average under 1% | systemd enforces caps; restart and alert | Sustained monitor test |
| Source/install parity | Source package version, installed package metadata, source module path and runtime-critical ops/maintenance fingerprint, ops/maintenance entrypoints | Every check | Versions match, module resolves to this checkout, the running ops/maintenance fingerprint is unchanged, and both commands are executable | Mark parity degraded/unavailable; no silent deploy | Runtime parity and packaging/install tests |
| Recovery coverage | Tests plus private before-images | Every changed artifact | Hashes verify and restore steps are recorded | Stop mutation and retain snapshot | Restore/idempotence tests |

## Owner recovery

1. From the local-alpha checkout, run
   `./.venv/bin/curatormd-v2-ops check --json` and note the `incident_id` and
   component.
2. Inspect `journalctl --user -u curatormd-v2-ops@curatormd-v2-dev-alpha.service`.
3. Restore a changed file only from its incident's verified before-image, then
   verify SHA-256. Never overwrite the active database from a backup.
4. For database work, make a consistent SQLite snapshot first; require both
   integrity and foreign-key checks after an additive, idempotent migration.
5. Close an incident only after its cause is corrected and the next checks pass.
   The daily retention audit removes its snapshots only after 30 days from the
   recorded closure. Snapshots without a valid incident link remain in place and
   raise a retention evidence gate for owner review.
