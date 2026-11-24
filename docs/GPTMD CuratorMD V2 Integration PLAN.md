# GPTMD CuratorMD V2 Integration

## Summary

Connect GPTMD’s `gptmd-coding` Hermes profile to its existing CuratorMD V2 project registration. Retire only that profile’s legacy CuratorMD V1 plugin and stale V1 workspace settings. Preserve GPTMD application code, all existing worktree edits, and V1 data.

## Implementation Changes

- Reuse GPTMD’s existing `.curatormd-v2.toml`, matching project registration, `gptmd-coding` read/write grants, database binding, and profile mapping. Do not re-register or grant review access.
- Add the `curatormd_v2` local stdio server to the `gptmd-coding` profile, bound to the GPTMD root, shared V2 database, and project ID `gptmd`. Enable `--allow-write` to match the existing grant; omit review flags.
- Install the documented profile-local V2 lifecycle hook and exact MCP allowlist. Make the V2 package importable to Hermes by adding the existing V2 source path in the hook before importing its adapter.
- After V2 is configured, remove only the V1 skill, wrapper, frozen observer files, and V1-specific VS Code settings/Python path. Preserve `.curatormd` inbox records, plugin data, logs, backups, canonical persistence, and unrelated dirty changes.

## Acceptance Checks

- Validate the profile configuration and confirm Hermes lists and handshakes with the V2 server using the GPTMD project context.
- Read GPTMD project details, goal list, event queue status, and health; report each result with its verification boundary.
- Exercise lifecycle delivery against the active integration goal and confirm a durable event receipt.
- Confirm the V1 plugin binding is gone, V2 is active, and no out-of-scope GPTMD files or preserved V1 data changed.

## Assumptions

- The existing registration and `gptmd-coding` read/write grants remain authoritative because their fingerprints match the current GPTMD config.
- V2 lifecycle capture is in scope; review-gated operations and V1 data deletion are not.
