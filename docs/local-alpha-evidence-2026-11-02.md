# Curator V2 local alpha evidence checkpoint — 2026-11-02

Status: interim, content-free checkpoint, updated 2026-11-02 18:08 +07. This
is not an accepted alpha evidence packet and does not close any plan item. The
source is committed and pushed, the local quality and test suites pass, but the
active editor has no post-install activation evidence and owner acceptance is
absent.

## Scope and binding

- Approved scope: `eaglesvn` (UID 1000), this Curator V2 repository, one active
  repository. Vhost Manager application and utility workflows are excluded.
- Project: `curatormd-v2-dev-alpha`.
- Implementation commit used for the test runs:
  `832b6f9afd8b10e081751cf96dc45657fde8b293`. The checkpoint update itself
  was committed afterward as a documentation-only change.
- Worktree: clean at the time of this observation; this checkpoint update is
  content-free and source-pinned to the commit above.
- Project configuration SHA-256:
  `9af8812d008d753121489dd3c4e4a41768ddb6b56aa8b9fa27c95d06333c547e`.
- Host evidence configuration SHA-256:
  `cc62dace9c46b1d390be9f9389a9c93a8caf38fcfe54b262cd5094372529bda3`.
- Configuration owner/mode: `eaglesvn`, UID 1000, `0600`.
- Local alpha database: `/home/eaglesvn/.local/share/curatormd-v2-alpha/global.sqlite3`,
  owned by UID 1000, mode `0600`.
- VS Code source and installed extension: `curatormd-v2-status` 0.9.53. The
  active editor window has no post-install activation evidence, so current
  rendering remains unverified.
- Installed wheel/source identity: not established for this repository and
  worktree.

## Current observations

| Area | Observation at 2026-11-02 18:12 +07 | State |
|---|---|---|
| Maintenance timer | Project timer is active; last trigger was 18:00:06 +07, service result is success with exit status 0, and next trigger is scheduled for 00:00:11 +07. Configured service-probe receipt: `45df5ad5e0ecfa54d3226343e0e6857337494ba6e32f189d1174070665d8c659`. | Read-only observation; a single run does not establish the full operating gate. |
| Daily backups | Six recognized daily SQLite snapshots are present, dated 2026-10-28 through 2026-11-02; all six pass `quick_check` and have zero foreign-key violations. | Seven-copy rotation remains open. Unclassified files and sidecars were preserved. |
| Restore to a new path | The latest 2026-11-02 snapshot was restored with the Curator V2 storage CLI to a new temporary path; the CLI returned `verified`, SQLite `quick_check` returned `ok`, and foreign-key check found zero violations. The temporary copy was removed after validation. | This proves one snapshot restore. It does not prove seven-copy rotation, package upgrade rollback, or live expiry. |
| Source tests and quality | Python unittest passed 606/606, VS Code Node suite passed 38/38, Pyright reported 0 diagnostics, Bandit exited 0, and Pylint `--errors-only` passed. Full Pylint exited 24 with convention/refactor findings (9.93/10). | Local results; Python/quality output is not host-attested. The configured committed VS Code test receipt is `d4800e61e45102415e0acfd70e850f9af70d425813dc99207fe5833daf14b549`, for commit `832b6f9`. |
| Project health and review status | Current source excludes pending SDE review from health degradation and gives outstanding reviews a separate blue/action state. | Source review only; the active VS Code rendering was not inspected. |
| Review document | Editable draft, significance, multiple configured destinations, and receipt-binding paths are covered by the passing local suites. | No local attended review or receipt reconciliation was performed. |

## Follow-up observation — 2026-11-02 17:32 +07

- `code --list-extensions --show-versions` reports the installed extension as
  0.9.53, matching the workspace package version.
- The installed `extension.js` has filesystem modification time 17:25:36 +07.
- The active Curator V2 window's extension-host log shows the latest extension
  activation at 16:37:19 +07, before that install time. Reload is required
  before checking the rendered dashboard or pending-review document.
- This is package/version and activation-timing evidence only. No rendered UI,
  test suite, reviewer action, or plan criterion is verified by this update.

## Acceptance work still open

- **Privacy sinks:** no end-to-end canary proves the approved retry-payload
  exception and raw-content/credential absence across every log, trace,
  backup, crash, journal, and command-history sink.
- **Local alpha:** no reconciled, source-matched package and configuration
  packet or explicit owner accept/reject decision exists for this repository.
- **Real task intake:** this tracked task has Curator readback; the required
  real Hermes Core/Codex intake, replay comparison, and unchanged out-of-scope
  project snapshot have not been independently accepted.
- **Rendered facts:** source and installed extension are 0.9.53, but the active
  window has no post-install activation evidence. Current dashboard rendering,
  page/stale behavior, reauthorization, and reopen acceptance remain
  unverified.
- **SDE assessment:** candidate
  `84e98982094c41ac92c3d398be23e93a` remains pending human review. No human
  decision or independent receipt reconciliation was performed here.
- **Cleanup recovery:** no local attended decision, exact-inventory cleanup, or
  per-target recovery acceptance was exercised.
- **Operating recovery:** the current service receipt, six verified daily
  snapshots, and one restore to a new path do not prove the 250 MiB warning
  boundary, live due 72-hour expiry, seven-copy rotation, or package rollback
  for this alpha. The passing unit suite covers bounded implementations only;
  it does not replace the remaining current runtime and recovery evidence.

No project staging or backup artifact was deleted, no service was restarted,
and no SDE decision was made while preparing this checkpoint. The temporary
restore copy created for the check was removed after validation. The acceptance
scope and remaining work are defined by
[`curator-v2-plan.md`](curator-v2-plan.md).
