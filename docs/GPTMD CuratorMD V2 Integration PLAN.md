# GPTMD CuratorMD V2 Integration

## Summary

Connect GPTMD’s `gptmd-coding` Hermes profile to its existing CuratorMD V2
project registration. Retire only that profile’s legacy CuratorMD V1 plugin
and stale V1 workspace settings. Preserve GPTMD application code, all existing
worktree edits, and V1 data.

## Implementation Changes

- Reuse GPTMD’s existing `.curatormd-v2.toml`, matching project registration,
  database binding, and profile mapping. Keep the existing read/write grants
  and add a project-scoped review grant for `local-uid:1000`; do not
  re-register the project or grant access to another project.
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
  Normal Codex app-server tool use is still open: a real turn did not invoke
  `tool_search` or `project_health`, and the shared Codex config has no
  `curatormd_v2` entry. Its Hermes-managed `hermes-tools` bridge exposes a
  curated tool list that does not include Curator V2 MCP tools. The successful
  Hermes probes therefore do not prove that the configured Codex runtime can
  use Curator V2. Do not mark this integration complete until a normal profile
  turn calls an authorized Curator tool and the result is verified.

## Assumptions

- Owner authorization on 2026-11-25: update this plan and grant
  project-scoped review access to `local-uid:1000` so GPTMD’s `human_review`
  health dependency can pass. Keep the grant bound to project `gptmd`.
- The existing registration and `gptmd-coding` read/write grants remain
  authoritative because their fingerprints match the current GPTMD config.
  Review permission expands this profile’s project access only; it does not
  authorize V1 data deletion.
