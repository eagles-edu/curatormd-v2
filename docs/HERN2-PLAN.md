# Hermes Host and Profile Review

## Summary

The document records an incomplete audit, not a completed optimization. Its reported updater side effect, live runtime leases, and unfinished repository scan need fresh verification before maintenance. The observable goal is a stable Hermes installation, a focused default host-maintenance profile, and appropriately scoped CuratorMD profiles, supported by current health checks and an exact cleanup inventory.

A current read-only snapshot confirms the root filesystem is still 92% full, with 5.1 GiB available, and swap is nearly full. The installed Hermes checkout still has 14 modified or untracked paths; their significance has not yet been established. The document’s other operational findings are historical and require rechecking.

## Implementation

- Inspect updater logs, installed and source checkout revisions, service processes, runtime paths, and leases without invoking a launcher that may resume an update. Determine what remains pending and prepare a recovery sequence that preserves local changes and identifies any necessary service interruption.
- Inventory current disk usage, memory pressure, scheduled jobs, profiles, skills, plugins, MCPs, and configuration. Research current Hermes documentation and host-maintenance practices; distinguish measured problems from possible optimizations.
- Review the default profile for host-maintenance responsibilities and the CuratorMD profiles for their respective project functions. Preserve all five profiles and project-specific database bindings. Propose specific, evidence-backed configuration changes and removal candidates rather than treating low usage or repeated definitions as proof of waste.
- Produce an exact cleanup preview with paths, ownership, size, active references, dependencies, and recovery implications. Hold garbage collection, runtime removal, cache pruning, and other deletion until the pending update and live references are understood and the applicable cleanup boundary is authorized.
- Recover the interrupted nine-repository language scan if its output is available; otherwise run a bounded replacement and report the actual results. Review the recorded skill modification separately instead of assuming it was correct.
- Diagnose the recorded MCP, hook, adapter, and scheduler errors against current logs and profile context. Apply targeted fixes within the appropriate owning project or Hermes environment, preserving unrelated working-tree changes.

## Verification

- Compare disk space, memory pressure, service health, scheduled-job state, and profile configuration before and after any authorized changes.
- Verify each changed profile through its configured runtime and relevant live health probe; distinguish configuration discovery from a successful connection and working behavior.
- Check repeated maintenance runs for safe, idempotent behavior. Report remaining update, cleanup, and operational gaps explicitly, including any action requiring a maintenance window.

## Assumptions

- The document’s stated authorization permits updater inspection only and defers cleanup until an exact preview; it does not authorize running the updater or deleting candidates.
- Host Steward belongs to Hermes Core. Consumer-specific source, state, and persistence stay outside this CuratorMD backend repository.
- Existing uncommitted changes and editable review documents are preserved. No commit, push, deployment, or external publication is included.
