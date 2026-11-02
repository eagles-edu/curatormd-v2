# Curator V2 local alpha evidence checkpoint — 2026-11-02

Status: interim, content-free checkpoint, updated 2026-11-02 17:32 +07. This
is not an accepted alpha evidence packet and does not close any plan item. The
worktree is dirty, the proof suites have not been run, the installed extension
matches source but the active editor has no post-install activation evidence,
and owner acceptance is absent.

## Scope and binding

- Approved scope: `eaglesvn` (UID 1000), this Curator V2 repository, one active
  repository. Vhost Manager application and utility workflows are excluded.
- Project: `curatormd-v2-dev-alpha`.
- Repository `HEAD`: `1e25d84db3d36df11685828e7cb12bff2c984131`.
- Worktree: 37 modified or untracked paths at observation time; this checkpoint
  is not pinned to a clean commit.
- Project configuration SHA-256:
  `9af8812d008d753121489dd3c4e4a41768ddb6b56aa8b9fa27c95d06333c547e`.
- Configuration owner/mode: `eaglesvn`, UID 1000, `0600`.
- Local alpha database: `/home/eaglesvn/.local/share/curatormd-v2-alpha/global.sqlite3`,
  owned by UID 1000, mode `0600`.
- VS Code source and installed extension: `curatormd-v2-status` 0.9.53. The
  active editor window has no post-install activation evidence, so current
  rendering remains unverified.
- Installed wheel/source identity: not established for this repository and
  worktree.

## Current observations

| Area | Observation at 2026-11-02 17:17 +07 | State |
|---|---|---|
| Maintenance timer | Project timer is active; last trigger was 12:00 +07, service exit status was 0, and next trigger is scheduled for 18:00 +07. | Read-only observation; a single run does not establish the full operating gate. |
| Daily backups | Six recognized daily SQLite snapshots are present, dated 2026-10-28 through 2026-11-02. | Seven-copy rotation remains open. Unclassified files and sidecars were preserved. |
| Source syntax | Python compilation, JavaScript syntax checks, and `git diff --check` passed for the reviewed source/test files. | Local checks only; no Python or Node test suite was run and no commit-pinned repository-test receipt was captured. |
| Project health and review status | Current source excludes pending SDE review from health degradation and gives outstanding reviews a separate blue/action state. | Source review only; the active VS Code rendering was not inspected. |
| Review document | Editable draft, significance, multiple configured destinations, and receipt-binding paths have focused regression coverage. | Tests are unrun; no local attended review or receipt reconciliation was performed. |

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
- **Operating recovery:** the current observation does not prove the 250 MiB
  warning boundary, live due 72-hour expiry, seven-copy rotation, restore to a
  new path, or package rollback for this alpha.

No artifact was deleted, no service was restarted, and no SDE decision was
made while preparing this checkpoint. The acceptance scope and remaining work
are defined by [`curator-v2-plan.md`](curator-v2-plan.md).
