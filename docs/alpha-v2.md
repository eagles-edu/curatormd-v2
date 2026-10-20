# Curator V2 alpha

## Candidate scope

The package version is `0.1.0a1`. This is a local alpha candidate for
integration and feedback. It is not a published distribution, production
deployment, or authorization to enable capture or destructive cleanup.

The candidate includes the typed goal/fact/event lifecycle, local SQLite
backend, stdio MCP server, reference repository plugin, bounded staging and
inventory APIs, canonical Markdown projection, review receipts, and guarded
purge/retry paths. Hermes Core integration and Host Steward are separate source
changes in the Hermes Core repository; they are not part of this wheel and are
not installed in the live Hermes account.

## Runtime and verification scope

The package declares Python `>=3.12,<4`. The CI workflow exercises Linux with
Python 3.12, 3.13, and 3.14, runs the locked unit suite and quality/security
checks, and installs a freshly built wheel into a clean environment for an MCP
launcher acceptance test. A passing run proves those source/package checks for
the exact commit only.

## Known limitations

- Hermes profile and project values are operator assertions; authenticated
  human and Hermes identity binding is not implemented.
- Trusted repository, service, browser, and human evidence adapters remain
  reject-all/reference implementations until their trust roots are approved.
- No production router, scheduler, monitoring/alert delivery, or live capture
  installation is established by this alpha.
- Retention policy, legal/operational holds, production backup/restore and
  recovery drills, and deployment rollback have not received owner approval or
  deployment-like verification.
- No V1 artifact inventory, approved disposition, migration, or cutover has
  been completed. The local Codex plugin and three Hermes profile entries
  inspected for this task are disabled; this does not claim every possible V1
  consumer is disabled. V1 data has not been imported or deleted.
- No consumer pilot or owner-approved production install is included.

Keep V2 capture disabled and preserve existing canonical records and staged
evidence while evaluating this candidate. See the
[`release-gate ledger`](release-gates-v2.md) and
[`cutover checklist`](curator-v2-plan.md#10-v1-cutover-rollout-and-rollback)
for the remaining evidence and approvals.
