# Curator V2 local alpha evidence checkpoint — 2026-11-02

Status: interim, content-free checkpoint, updated 2026-11-02 18:27 +07. This
is not an accepted alpha evidence packet and does not close any plan item. The
schema repair and dashboard retry fix are committed and pushed. Local tests
pass, but the active editor has no post-install activation evidence and owner
acceptance is absent.

## Scope and binding

- Approved scope: `eaglesvn` (UID 1000), this Curator V2 repository, one active
  repository. Vhost Manager application and utility workflows are excluded.
- Project: `curatormd-v2-dev-alpha`.
- Current implementation commit: `3a47e95ace97c26219dee7c3ce82e9b5f05c33a7`.
  The full Python suite ran at `cc2dec67be476b46a551b97832534b769e0196dc`;
  the later commit changes only the VS Code extension and package.
- Worktree: clean at the time of this observation; this checkpoint update is
  content-free and source-pinned to the commit above.
- Project configuration SHA-256:
  `9af8812d008d753121489dd3c4e4a41768ddb6b56aa8b9fa27c95d06333c547e`.
- Host evidence configuration SHA-256:
  `cc62dace9c46b1d390be9f9389a9c93a8caf38fcfe54b262cd5094372529bda3`.
- Configuration owner/mode: `eaglesvn`, UID 1000, `0600`.
- Local alpha database: `/home/eaglesvn/.local/share/curatormd-v2-alpha/global.sqlite3`,
  owned by UID 1000, mode `0600`.
- VS Code source and installed extension: `curatormd-v2-status` 0.9.54. The
  installed JavaScript hash matches source. The active editor window has no
  post-install activation evidence, so current rendering remains unverified.
- Installed wheel/source identity: not established for this repository and
  worktree.

## Current observations

| Area | Observation at 2026-11-02 18:12 +07 | State |
|---|---|---|
| Maintenance timer | Project timer is active; last trigger was 18:00:06 +07, service result is success with exit status 0, and next trigger is scheduled for 00:00:11 +07. Configured service-probe receipt: `45df5ad5e0ecfa54d3226343e0e6857337494ba6e32f189d1174070665d8c659`. | Read-only observation; a single run does not establish the full operating gate. |
| Daily backups | Six recognized daily SQLite snapshots are present, dated 2026-10-28 through 2026-11-02; all six pass `quick_check` and have zero foreign-key violations. | Seven-copy rotation remains open. Unclassified files and sidecars were preserved. |
| Restore to a new path | The latest 2026-11-02 snapshot was restored with the Curator V2 storage CLI to a new temporary path; the CLI returned `verified`, SQLite `quick_check` returned `ok`, and foreign-key check found zero violations. The temporary copy was removed after validation. | This proves one snapshot restore. It does not prove seven-copy rotation, package upgrade rollback, or live expiry. |
| Source tests and quality | Python unittest passed 607/607 at `cc2dec6`; the VS Code Node suite passed 38/38 at `3a47e95`; Pyright reported 0 diagnostics and Pylint `--errors-only` passed at the Python change. Full Pylint exited 24 with convention/refactor findings (9.93/10). | Python/quality output is local and not host-attested. The configured current VS Code repository-test receipt is `310e3748d2aeff5326a4dfb211335dab15a3f24986a12a9c071b97a81f78dc80`; it proves the extension suite only. |
| Project health and review status | Fresh Hermes probe matches the project, reports all seven dependencies healthy, and is degraded only for `event_failures`. The independent queue snapshot is complete: 3 failed events, 4 pending reviews, and no purge/expiry work. Pending review is not a health gate. | Read-only source observations; three failed event receipts still explain degraded health. The active editor rendering was not inspected. |
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

## Follow-up observation — 2026-11-02 18:27 +07

- The live database now reports schema version 46, includes
  `sde_review_targets`, passes SQLite `quick_check`, and has zero foreign-key
  violations. The missing table that caused the earlier incomplete health and
  queue snapshots is repaired.
- Commit `3a47e95ace97c26219dee7c3ce82e9b5f05c33a7` changes the dashboard's
  initial read to a manual retry, so clicking the red `CuratorMD V2` status
  item can clear a three-identical-failure pause. The separate pending-review
  item remains blue and opens `pending-review.md`. The host-configured VS Code
  suite passed 38/38 at this commit.
- The installed extension is 0.9.54 and its `extension.js` hash matches source.
  Extension-host logs show the latest activation before 0.9.54 was installed;
  the active window still needs a reload and rendered check.
- Fresh Hermes and Curator queue reads are project-matched and complete. Hermes
  health is degraded only for three failed event receipts; the queue separately
  reports four pending human reviews. No review decision or failed-event
  disposition was made.
- The Python suite passed 607/607 at `cc2dec6`; a `ResourceWarning` appeared
  during a legacy schema migration test, but the suite completed successfully.
  The new schema migration regression is included in that run. The seven
  acceptance items remain open pending their broader runtime, privacy, reviewer,
  cleanup, and recovery evidence.

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

## Documentation consistency — 2026-11-02 18:35 +07

- Updated the dashboard retry contract: opening the dashboard is a manual
  retry after the three-failure pause; page navigation remains automatic.
- The VS Code window still has no post-install activation record. Reload and
  rendered status/queue confirmation remain open.
