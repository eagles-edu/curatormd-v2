# GPTMD CuratorMD V2 Integration

## Summary

Connect GPTMD’s `gptmd-coding` Hermes profile to its existing CuratorMD V2
project registration. Retire only that profile’s legacy CuratorMD V1 plugin
and stale V1 workspace settings. Preserve GPTMD application code, all existing
worktree edits, and V1 data.

## Implementation Changes

- Reuse GPTMD’s existing `.curatormd-v2.toml`, matching project registration,
  database binding, and profile mapping. Keep the existing project-scoped
  `read`, `write`, and `review` grants for `local-uid:1000`; do not re-register
  the project or grant access to another project.
- Add the `curatormd_v2` local stdio server to the `gptmd-coding` profile,
  bound to the GPTMD root, shared V2 database, and project ID `gptmd`. Enable
  `--allow-write` and `--allow-review` to match the project-scoped grants.
- Install the documented profile-local V2 lifecycle hook and exact MCP
  allowlist. Make the V2 package importable to Hermes by adding the existing
  V2 source path in the hook before importing its adapter.
- After V2 is configured, remove only the V1 skill, wrapper, frozen observer
  files, and V1-specific VS Code settings/Python path. Preserve `.curatormd`
  inbox records, plugin data, logs, backups, canonical persistence, and
  unrelated dirty changes.

## Acceptance Checks

- Validate the profile configuration and confirm Hermes lists and handshakes
  with the V2 server using the GPTMD project context.
- Read GPTMD project details, goal list, event queue status, and health; report
  each result with its verification boundary.
- Exercise lifecycle delivery against the active integration goal and confirm
  a durable event receipt.
- Confirm all seven configured health dependencies are healthy across
  repeated profile-bound probes, including `human_review`.
- Confirm a normal `gptmd-coding` Codex app-server turn can discover and call
  an authorized Curator V2 tool, then verify the result and health again.
- Confirm the V1 plugin binding is gone, V2 is active, and no out-of-scope
  GPTMD files or preserved V1 data changed.

## Current Verification

- 2026-11-25: The attended access flow granted project-scoped `review` to
  `local-uid:1000` on project `gptmd` (grant
  `6ac0b3c0762a4b5a8df5c4f6d4353117`). A read-only ledger check confirms the
  existing exact `read` and `write` grants remain active. The GPTMD profile has
  matching `--allow-write` and `--allow-review` flags, and its MCP server
  connects with Hermes profile context.
- The two previously stuck lifecycle events were retried by the live Hermes
  profile hook through its managed Curator MCP connection. Both exact event
  IDs now have acknowledged outbox receipts (start sequence 1 and end sequence
  2), and read-only backend ledger checks show both inbox rows `processed` with
  no error. The source cursor remains at sequence 2. The narrow replay rule
  accepts these newer `GoalActivityObserved` facts without rewinding that
  cursor; retries reuse the exact event IDs and remain idempotent.
- Repeated profile-bound `hermes mcp test --probe-curator-status --json
  curatormd_v2` probes at 2026-11-25 13:08:34 UTC, 13:08:44 UTC, 13:35:37
  UTC, and 13:35:51 UTC all report overall `healthy` with all seven
  dependencies healthy, empty `gate_codes`, zero failed or quarantined
  events, and zero pending purge or expiry work. The review queue still
  contains one pending item; this does not degrade health.
- A further profile-bound read at 13:18:19 UTC returned project activity,
  the sole active goal and its saved acceptance criterion, event queue status,
  project queue snapshot, and health. It reports 18 processed receipts, zero
  received, failed, or quarantined events, and all seven dependencies healthy.
  The queue snapshot is complete, with one pending human-review item and no
  pending purge or expiry work.
- The active GPTMD profile has the `curator-v2` hook and configured V2 server;
  no active V1 Curator hook, script, plugin, or workspace setting was found.
  Legacy V1 scripts and observer files remain only in the dated retirement
  backup. The project `.curatormd` directory still contains 10 preserved
  files, and GPTMD's Git worktree is clean.
- The profile-bound Hermes MCP connection, reads, exact lifecycle receipts,
  repeated healthy gates, retired V1 entrypoints, and preservation checks pass.
- 2026-11-25: Hermes Core commit `10495e8a17` adds an explicit, profile-scoped
  Codex app-server context bridge on top of live Core baseline
  `79f808a6eac69b2f91ce1bc25493fa9440a241c4`. The GPTMD profile opts in only
  its local stdio `curatormd_v2` server. Host context is supplied per active
  profile and session; the model request cannot author that context. Durable
  Hermes lifecycle dispatch remains denied to app-server calls and continues
  through the existing Hermes hook.
- The GPTMD Codex migration generated a Curator server entry with the context
  marker and `--allow-codex-app-server-context`, preserving the existing
  `--allow-write` and `--allow-review` flags. Two migration runs produced the
  same config SHA-256 (`6405f3c6d92389967f6ce9e8f41a231ddbc8c1524fcb93c42ed6cb4436e30dd6`)
  with no migration errors. Optional Codex `plugin/list` discovery timed out;
  it did not affect Curator migration or the app-server MCP route.
- After restarting `hermes-gateway.service`, two real GPTMD Codex app-server
  turns called `project_health` at 2026-11-25 14:07:35 UTC and 14:08:54 UTC.
  Both returned overall `healthy`, all seven dependencies healthy, and an
  empty gate list. These calls were read-only and made no project-state
  changes. This verifies the normal app-server tool route and repeatable
  profile/session context after gateway reload.
- Four additional consecutive profile-bound probes at 2026-11-25 14:35:40
  UTC, 14:36:00 UTC, 14:36:11 UTC, and 14:36:23 UTC all report overall
  `healthy`; all seven dependencies, including `human_review`, are healthy,
  `gate_codes` is empty, and failed/quarantined events and pending purge or
  expiry work remain zero. `pending_review_count=1` remains an expected review
  queue item and does not degrade health. The review grant readback confirms
  grant `6ac0b3c0762a4b5a8df5c4f6d4353117` is project-scoped to `gptmd`,
  subject `local-uid:1000`, action `review`.
- A fresh profile-bound health probe at 2026-11-25 15:07:29 UTC again reports
  overall `healthy`, with complete database and staging observations, all seven
  dependencies healthy, empty `gate_codes`, zero failed or quarantined events,
  and zero pending purge or expiry work. The one pending human-review item
  remains unchanged.
- Hermes Core commit `3529c6c92d1d3d3adf7d189721385d68ae28e067` was pushed to
  `origin/fix/gptmd-curator-readiness`, fast-forwarded into the installed
  `/usr/local/lib/hermes-agent` checkout, and activated by restarting
  `hermes-gateway.service`. The installed checkout is clean and matches the
  remote feature branch. Two post-restart profile-bound probes at 2026-11-25
  15:43:09 UTC and 15:43:58 UTC report overall `healthy`, complete database and
  staging observations, all seven dependencies healthy, empty `gate_codes`, and
  zero failed, quarantined, or purge/expiry work. The pending review count
  remains one. No GitHub Actions runs were listed for the Hermes Core branch at
  verification time.
- The GPTMD integration goal remains active. A completion fact write through
  the configured profile was rejected by the Codex app-server route; no
  completion fact or replacement SDE proposal was saved. The existing pending
  proposal still describes degraded health and must not be treated as the
  stable-installation SDE. Retry through a supported, owner-authorized Curator
  write route, then verify the goal and pending proposal by readback.
- A follow-up through the Hermes host profile returned `not_found` for both
  `goal_status` and `goal_report` on that goal ID, even though a preceding
  `goal_list_page` response identified it as active. No lifecycle or SDE writes
  were made. Resolve this Curator read inconsistency before recording the
  verified installation outcome.
- The complete Curator V2 test suite passes: 718 tests and 563 subtests. The
  health-probe fixture grants access to the runtime’s actual local host
  identity. Strict Pyright reports zero errors; blocking Pylint, Bandit, and
  the locked dependency audit also pass.
- The Hermes Core readiness branch is pushed and installed at
  `/usr/local/lib/hermes-agent` on `fix/gptmd-curator-readiness`, at
  `3529c6c92d1d3d3adf7d189721385d68ae28e067`. Its source checks passed before
  publication; the installed gateway is active and the repeated GPTMD health
  probes pass. GitHub Actions listed no runs for this feature branch at the
  time of verification.

## Assumptions

- Owner authorization on 2026-11-25: update this plan and grant
  project-scoped review access to `local-uid:1000` so GPTMD’s `human_review`
  health dependency can pass. The grant is active only on project `gptmd`.
- The existing registration and `gptmd-coding` read/write/review grants remain
  authoritative because their fingerprints match the current GPTMD config.
  Review permission expands this profile’s project access only; it does not
  authorize V1 data deletion.
