# GPTMD CuratorMD V2 Integration

## Summary

Connect GPTMD’s `gptmd-coding` Hermes profile to its existing CuratorMD V2 project registration. Retire only that profile’s legacy CuratorMD V1 plugin and stale V1 workspace settings. Preserve GPTMD application code, all existing worktree edits, and V1 data.

## Implementation Changes

- Reuse GPTMD’s existing `.curatormd-v2.toml`, matching project registration,
  database binding, and profile mapping. Keep the existing read/write grants
  and add a project-scoped review grant for `local-uid:1000`; do not
  re-register the project or grant access to another project.
- Add the `curatormd_v2` local stdio server to the `gptmd-coding` profile,
  bound to the GPTMD root, shared V2 database, and project ID `gptmd`. Enable
  `--allow-write` and `--allow-review` to match the project-scoped grants.
- Install the documented profile-local V2 lifecycle hook and exact MCP allowlist. Make the V2 package importable to Hermes by adding the existing V2 source path in the hook before importing its adapter.
- After V2 is configured, remove only the V1 skill, wrapper, frozen observer files, and V1-specific VS Code settings/Python path. Preserve `.curatormd` inbox records, plugin data, logs, backups, canonical persistence, and unrelated dirty changes.

## Acceptance Checks

- Validate the profile configuration and confirm Hermes lists and handshakes with the V2 server using the GPTMD project context.
- Read GPTMD project details, goal list, event queue status, and health; report each result with its verification boundary.
- Exercise lifecycle delivery against the active integration goal and confirm a durable event receipt.
- Confirm all seven configured health dependencies are healthy across
  repeated profile-bound probes, including `human_review`.
- Confirm the V1 plugin binding is gone, V2 is active, and no out-of-scope GPTMD files or preserved V1 data changed.

## Current Verification

- 2026-11-25: The owner authorized project-scoped review access. The attended
  access flow granted `review` to `local-uid:1000` on project `gptmd`
  (grant `6ac0b3c0762a4b5a8df5c4f6d4353117`). The GPTMD profile has the
  matching `--allow-review` flag; a timestamped copy of its previous config
  is saved in the GPTMD profile's `backups/config/` directory.
- The GPTMD profile MCP handshake succeeds and discovers 64 tools. Two
  repeated readiness probes report six healthy dependencies and a stable
  `event_router` failure. The backend cursor is already at sequence 2, while
  the profile outbox has unacknowledged lifecycle events at sequences 1 and 2;
  sequence 1 is recorded as failed with `EventOrderError`.
- The stale outbox events have not been retried, disposed, or rewritten in
  this continuation. Current attended operations cannot resolve this exact
  cursor mismatch. Keep lifecycle acceptance open until the sequence gap has
  an audited recovery and repeated profile-bound health checks pass. The Hermes
  Core source fix is committed locally but is not installed in the active
  system checkout.

## Assumptions

- Owner authorization on 2026-11-25: update this plan and grant
  project-scoped review access to `local-uid:1000` so GPTMD’s `human_review`
  health dependency can pass. Keep the grant bound to project `gptmd`.
- The existing registration and `gptmd-coding` read/write grants remain
  authoritative because their fingerprints match the current GPTMD config.
  Review permission expands this profile’s project access only; it does not
  authorize V1 data deletion.
