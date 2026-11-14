# CuratorMD V2 AI-Assisted Operations and Recovery

## Summary

Replace the scattered local-alpha checks and maintenance path with one project-bound `curatormd-v2-ops` system. A resident monitor checks every 60 seconds, targets under 1% average CPU, and is capped at 64 MiB. It runs scheduled maintenance on the existing six-hour cadence and invokes local Codex when it detects a fault.

I interpret “bu” as **backup**: every edited artifact must have a verified before-image and a documented restore path. AI may diagnose, build, and test fixes in an isolated worktree; installing code or changing identity, grants, or destructive data requires owner approval.

## Operational Inventory and Simplification

Create one runbook inventory for the exact `curatormd-v2-dev-alpha` local-alpha binding. For every dependency, record its owner, source of truth, check interval, success signal, failure state, automatic repair, escalation, and regression test:

- Project ID, OS UID, repository root, database path, and exact Hermes profile.
- Runtime version and schema compatibility; SQLite integrity and foreign-key checks.
- Before-images, daily backup freshness, permissions, rotation, and restore readiness.
- Monitor/service health, six-hour maintenance freshness, limits, and authorized purge receipts.
- All seven health dependencies, timestamps, queue completeness, and shared freshness policy.
- VS Code health display, journal reporting, resource use, installed/source parity, and recovery coverage.

Add one owner-only operations manifest as the approved binding authority. When it is intact, AI may diagnose drift and restore generated service/editor settings to match it. A missing, changed, or conflicting authority still triggers AI diagnosis, but identity changes stop for owner review.

Consolidate the current runtime selector, maintenance invocation, and repeated operational settings behind the wrapper. Keep one systemd resident service per project; it performs health checks every minute and maintenance every six hours.

## AI Diagnosis, Bug Fixing, and Recovery

On every missing, stale, malformed, failed, or mismatched observation—including binding mismatches—the monitor creates a sanitized incident and invokes the installed Codex CLI on demand. Deduplicate repeated incidents, allow only one AI run at a time, and bound each run by a timeout and token budget. Transient AI failures retry without blocking monitoring: start at five minutes and use exponential backoff capped at six hours. Diagnosis runs are isolated from the resident loop. The monitor itself stays within the selected CPU/RSS budget.

The wrapper exposes:

- `curatormd-v2-ops check --json` for read-only component status, evidence age, gates, incident ID, and next action.
- `curatormd-v2-ops maintain` for backup, allowed migration, integrity checks, and already-authorized due maintenance.
- `curatormd-v2-ops monitor` as the resident worker.

Codex may investigate source and produce a tested code fix in a managed worktree using the documented [Codex CLI `exec` worktree and sandbox controls](https://learn.chatgpt.com/docs/developer-commands#codex-exec). For each changed file or config, save a private before-image with hashes and a restore procedure. For database repairs, first create a consistent pre-change snapshot; if a known foreign-key mismatch prevents a fully healthy backup, record that failed check in the snapshot metadata, then require both SQLite checks to pass after the additive migration. Retain incident backups until closure plus 30 days.

The system may automatically retry bounded reversible operations and apply additive, idempotent migrations after a consistent snapshot. It never creates purge approvals, guesses a conflicting identity, changes grants, restores over the active database, or deploys AI code. Repeated or unclassified failure remains visible as degraded/unknown and hands the owner a tested patch and exact recovery steps.

## Tests and Acceptance

- Test every inventory row and assert each failure dispatches one deduplicated AI incident.
- Inject binding conflicts, stale/missing probes, schema mismatch, composite-FK mismatch, failed backup, locked/corrupt database, unavailable runtime, timer failure, repeated repair failure, and monitor restart.
- Verify snapshots restore edited files/configs and that migrations and safe repairs are idempotent.
- Run the full Python and VS Code suites, quality checks, packaging/install checks, and profile-bound health proof.
- Accept after a 24-hour local-alpha observation: monitor stays within budget; maintenance and backup succeed; both SQLite checks pass; all seven dependencies are healthy with no gates; AI incidents are deduplicated, auditable, and reversible.

## Assumptions

- Scope is Curator V2 local alpha plus read-only checks of its Hermes profile and VS Code integration; Hermes and consumer repositories remain unchanged.
- “bu” means keeping restorable backups of every AI-edited artifact.
- The selected repair policy is automated reversible recovery and additive migration, with owner approval required for identity/grant changes, destructive actions, and code deployment.
