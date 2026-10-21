# Curator V2 release notes

## 0.1.0a1 — local alpha

Curator V2 `0.1.0a1` is a pre-release for local backend, package, and consumer
integration work. It is not a production release and does not authorize broader
capture, destructive cleanup, or deployment.

### Supported runtime

- Python `>=3.12,<4`; the current CI matrix exercises Python 3.12, 3.13, and
  3.14 on Linux.
- The package provides the local SQLite ledger, stdio MCP launcher, reference
  repository plugin, bounded staging and inventory, explicit one-shot router
  and purge commands, Markdown projection, and backup/restore-to-new-path CLI.
- Hermes Core lifecycle integration and Host Steward are separately owned and
  versioned in the Hermes Core repository. Consumer configuration and plugins
  belong in each consumer repository.

### Known limitations

- Hermes profile and project values do not authenticate a human or Hermes
  principal. Production identity and project authorization are open.
- Evidence sources use local reference contracts; deployment trust roots,
  revocation, service/browser integrations, and human confirmation are open.
- The router and purge worker are bounded one-shot commands. Production
  scheduling, dead-letter operations, monitoring, and alert delivery are open.
- Retention policy, legal and operational holds, production recovery drills,
  and deployment rollback require owner decisions and direct evidence.
- Local package acceptance and synthetic consumer tests do not establish a
  real application workflow, production persistence, or live service health.

### Operator guidance

Use the [alpha scope and current evidence](alpha-v2.md),
[consumer operations guide](consumer-operations-v1.md),
[CI verification policy](ci-v2.md), and
[release-gate ledger](release-gates-v2.md) together. The operations guide
covers local installation, access grants, bounded worker invocation, upgrades,
disablement, and recovery. Keep deployment, identity, retention, and live
runtime gates open until their listed evidence and owner approvals exist.

### Local verification

Reproduce the package's local checks with the commands in [CI policy](ci-v2.md).
Hosted CI applies to its exact source revision; it is not deployment evidence.
