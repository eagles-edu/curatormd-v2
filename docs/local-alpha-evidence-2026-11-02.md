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

## Readiness source recheck — 2026-11-02 18:38 +07

- The V2 dashboard's configured Hermes command is the Hermes development
  checkout wrapper. Running that exact command for profile
  `curatormd-v2-dev-alpha` returned a project-matched, complete health snapshot
  with all seven dependencies healthy and only the `event_failures` gate.
  The separate complete Curator queue snapshot reports 3 failed events, 4
  pending reviews, and no purge or expiry work. Pending review does not cause
  the degraded health state.
- The default `hermes` command on `PATH` is a separate older installation and
  does not accept the health-probe flags. Its result is not the dashboard's
  readiness source. No failed-event disposition, SDE decision, test run,
  runtime update, or restart was performed.
- Active VS Code rendering remains unverified; the window still needs a
  reload and visual check of the red health and separate blue review actions.

## Proof-run artifact checkpoint — 2026-11-02 18:47 +07

- Curator V2 repository `HEAD` and `origin/main` match at
  `0930be95fb5df02066ccdfc23766e512f63fd1fb`.
- The proof-run package is
  `integrations/vscode-status/curatormd-v2-status-0.9.55.vsix`, SHA-256
  `af771732d8fa80a2d8052776a2cd7ed95a0a4c3f587766c9b47eb049665d6be5`.
  The installed VS Code extension still reports 0.9.54; 0.9.55 has not been
  installed and the active editor has not been reloaded.
- The owner-configured maintenance service probe returned `passed` for
  `service-probe:curator-maintenance-timer`. This is service-readiness evidence
  only; it does not prove the 250 MiB warning boundary, 72-hour expiry,
  seven-copy rotation, restore, or rollback.
- No unit/proof tests, editor reload, Hermes runtime update, SDE decision, or
  cleanup action was performed. All seven acceptance items remain open.

## Live dashboard feed recheck — 2026-11-02 18:49 +07

- The exact Hermes command and project profile configured for the dashboard
  returned a complete, matching snapshot with all seven dependencies healthy.
  Health is degraded only for `event_failures`; there are 3 failed events and
  4 pending reviews. The pending reviews are not the cause of degradation.
- The independent Curator queue snapshot is complete for the same project and
  reports 3 failed events, 4 pending reviews, and zero purge/expiry work.
- Curator's separate `project_health` read reports unknown dependencies and
  `sqlite_payload_scrub_pending`; it is not the dashboard's Hermes readiness
  feed. Keep these sources distinct.
- No event disposition, payload cleanup, human review, editor reload, or proof
  test was performed. Rendered status and the separate blue review action
  remain unverified in the active editor.

## Recovery follow-up — 2026-11-04

- The configured local maintenance service probe returned `passed` for
  `service-probe:curator-maintenance-timer`. This proves that configured
  service probe only.
- Seven daily backups dated 2026-10-29 through 2026-11-04 passed SQLite
  `quick_check`, foreign-key checks, and owner-only permission checks. The
  newest restored through `curatormd-v2-storage` to a disposable new path. This
  is a command-level observation, not a host-accepted recovery attestation.
- The configured dashboard Hermes probe at 2026-11-04 14:39 +07 returned a
  connected, project-matched snapshot with all seven dependencies healthy and
  no gates. The complete Curator queue snapshot at 14:38 +07 reports zero
  received, failed, quarantined, or pending-review items. The separate direct
  `project_health` call is `unknown` because that request contained no current
  observations for the seven Hermes-supplied dependencies; it is not the
  dashboard's Hermes readiness feed.
- The review document now has a **Refresh evidence** action. A blocked Accept
  points to it before loading the artifact inventory. With an explicit
  reason, next action, and confirmation, it reopens the completed source goal
  and withdraws the stale proposal. The owner must add fresh passing evidence
  for every criterion, finish the goal, and assess a new proposal. Existing
  facts and receipts remain; no decision is accepted and no terminal opens.
- VS Code extension 0.9.65 is installed and its JavaScript matches the current
  source. Local checks passed: extension suite 44/44, hosted MCP review test
  1/1, and `git diff --check`. The active window still needs reload and the
  action needs rendered verification against a pending proposal; the live
  review queue is empty.
- A read-only expiry-inventory request was denied for this caller. The live
  due 72-hour expiry, warning-only 250 MiB boundary, package rollback, privacy
  sink audit, owner review, and full local-alpha acceptance remain open.
