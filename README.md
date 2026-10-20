# Curator V2

Goal-ledger CuratorMD V2 core. The existing CuratorMD repository remains
separate; this repository does not copy its runtime state, inbox, transcripts,
or project records.

## Proposed ownership

- This repository: global event/goal/fact backend and reusable contracts.
- Each consumer repository: its own CuratorMD plugin and repository-specific
  configuration. GPTMD is one such consumer only; its application source,
  plugin binding, runtime state, and canonical records are not part of this
  Curator V2 repository.
- Hermes Core: runtime, global event routing, and Host Steward. Host Steward
  is outside CuratorMD's ownership boundary.

## Implemented core

- SQLite-backed goal cards, success criteria, compact deduplicated facts, SDE
  candidates, and audit receipts.
- Atomic goal completion/open/defer/block transitions. A goal cannot complete
  until each criterion has independently verified passing evidence.
- Completed goals can be reopened as a new evidence epoch; criteria can be
  amended explicitly with optimistic revision checks. Original criteria and
  every amendment remain queryable, while prior verification facts are retained
  for audit but cannot satisfy the new contract. Criteria history is bounded
  to 16 versions per goal.
- Fact capture is capped at 512 facts/512 KiB per goal and 10,000 facts/16 MiB
  per project. When a ceiling is reached, new facts are rejected without
  pruning; goal status and project usage expose the open capacity gate. Approved
  compaction and event-receipt retention are not implemented, so broad capture
  remains gated. Capacity-failed event receipts discard their payload and retain
  only a digest/error code; the producer must replay the same event after an
  approved capacity remedy.
- Routine facts stay ordinary progress. SDE candidates require a materiality
  category and selected passing verification evidence; approve/reject
  decisions are explicit and immutable. The review-authorizer boundary fails
  closed by default, and receipts retain its authenticated reviewer identity;
  the in-process review queue exposes selected evidence by project. A
  project-scoped review API/MCP surface exists, but its reviewer authorizer
  is deliberately fail-closed until Hermes Core supplies verified identity;
  a reviewer UI and production identity binding remain unimplemented.
- Post-review purge records its decision and artifact hashes before deletion.
  Purge is restricted to exact regular files under a configured staging root;
  hash mismatches, symlinks, directories, and outside paths are retained and
  reported as `purge_pending` for retry. Deletion stays blocked until the
  project adapter marks the full artifact inventory complete.
- `curatormd-v2-maintenance` provides an explicit one-shot retry of due,
  already-reviewed and canonically persisted purge targets. It respects target
  backoff and retention holds, acquires the project's staging lock, emits only
  aggregate results, and returns an alertable nonzero result for pending work.
  It is not itself a production scheduler or approval surface.
- SQLite transitions are transactional and database files are created private
  (`0600`); database files are runtime state and are ignored by Git.
- A fail-closed transport-neutral API facade centralizes host-supplied
  identity, project/action authorization, bounded event ingress, and request
  limits. It is not itself an HTTP/MCP server or an authentication provider.
- A real MCP SDK v2 stdio server factory exposes project-bound lifecycle,
  review, canonical-persistence, and purge tools. It still requires a trusted
  Hermes bootstrap for identity and project policy.
- A repository plugin can explicitly project one scoped goal into a configured
  Markdown target using an atomic, idempotent bullet block. Projection is not
  automatically invoked for every event and never approves an SDE. A reviewed
  receipt cannot purge artifacts until the plugin has written its goal/fact/
  receipt block and recorded the target and SHA-256 in SQLite. Projection and
  SQLite are not one cross-system atomic transaction; retries are idempotent,
  while broader reconciliation/backup recovery remains open.
- A project-scoped `goal_report` read tool renders bounded Markdown bullets for
  the problem, criteria, verified/recorded/unverified facts, TODOs, dependencies,
  SDE decisions, and canonical-write/purge status. Facts are paged; full evidence
  locators and hashes remain available only through `goal_status`.
- `project_activity_status` exposes retained event receipt/processing counts and
  recency, project goal/fact totals, and pending/approved/rejected SDE counts.
  It is deliberately separate from `project_health`: healthy readiness does
  not mean capture occurred, and zero SDEs does not imply a health failure.
- At active fact limits, a reviewer can preview and approve archival of routine
  research/advice facts only. Exact source records are compressed and SHA-256
  verified before active rows are removed; archived facts remain retrievable in
  goal status. Project usage reports archive bytes separately under a 64 MiB
  cap. This reuses SQLite pages but does not promise immediate shrinkage of the
  physical database file.

This is a Python global-backend/library implementation with a local MCP stdio
host and reusable repository-plugin adapter. The evidence verifier defaults to
reject-all until a trusted consumer/runtime adapter is configured. Bounded
versioned event ingress, a durable SQLite router, project registration and
scoped authorization, and read-only Markdown/SQLite reconciliation exist in
the local implementation; deployment-wide system-of-record and recovery policy
remain open.

Each consuming repository owns its `.curatormd-v2.toml`, read/checklist scope,
staging directory, and canonical Markdown targets. GPTMD is one consumer, not
part of this backend repository. The current local V2 wheel is installed in
GPTMD's ignored `.curatormd-v2/venv`; a disposable MCP stdio probe against its
real config and exact checklist line exercised planned, active, factual, and
honestly open states. GPTMD source and canonical records were not changed by
that probe. This was an uncommitted local wheel, not a released package or an
active Hermes integration.

The local profile launcher binds one operator-supplied profile ID and access
grant to one configured project; these are assertions, not authenticated
Hermes identity. Live app-server event mapping/delivery, Hermes permission
binding, trusted repository/service/browser/human evidence, authenticated SDE
review, production schedulers/alerts, retention policy, and deployment recovery
remain open. Checklist-backed goals pin the exact selected line and source-file
SHA-256 revision; parent/child tasks remain same-project and block parent
completion until linked work is resolved.

## Architecture sources

- [`docs/curator-v2-plan.md`](docs/curator-v2-plan.md) — lifecycle, behavior,
  tests, and cutover constraints.
- [`docs/event-contract-v1.md`](docs/event-contract-v1.md) — bounded version-1
  goal/fact event envelope and the requirements still open for a real ingress.
- [`docs/evidence-adapters-v1.md`](docs/evidence-adapters-v1.md) — fail-closed
  trust requirements for future repository, service, browser, and human proof
  adapters; it does not claim those adapters are deployed.
- [`docs/api-v1.md`](docs/api-v1.md) — in-process API/authz boundary and the
  remaining MCP/host integration contract.
- [`docs/mcp-tools-v1.md`](docs/mcp-tools-v1.md) — registered tools, trust
  binding, source sequencing, and transport verification boundaries.
- [`docs/project-plugin-v1.md`](docs/project-plugin-v1.md) — repository-owned
  config contract and reference plugin limits.
- [`docs/project-plugin-contract-testing-v1.md`](docs/project-plugin-contract-testing-v1.md)
  — reusable producer/backend assertions for consumer plugin test suites.
- [`docs/consumer-operations-v1.md`](docs/consumer-operations-v1.md) — bounded
  local profile install, upgrade, disablement, and recovery guidance; not a
  production deployment runbook.
- [`docs/examples/curatormd-v2.toml`](docs/examples/curatormd-v2.toml) — sample
  config to copy and adapt inside a consuming repository.
- [`docs/diagrams/inkscape-curator-v2-hermes-core.svg`](docs/diagrams/inkscape-curator-v2-hermes-core.svg)
  — detailed bounded-system landscape.

## Development

Python 3.12+ is the initial implementation language. Install the locked
project dependencies and run the test suite from the repository root with:

```sh
uv sync --locked --group test
uv run --locked --group test python -m unittest discover -s tests -v
```

Run the pinned local quality and security checks with:

```sh
uv sync --locked --group test --group quality
uv run --locked --group quality pyright
uv run --locked --group quality pylint --errors-only src/curatormd_v2 tests
uv run --locked --group quality bandit -q -r src/curatormd_v2
uv audit --locked --preview-features audit-command
```

The CI matrix tests Python 3.12, 3.13, and 3.14; static analysis and security
checks run once on Python 3.12. See [`docs/ci-v2.md`](docs/ci-v2.md) for the
blocking policy and the handling of newly disclosed vulnerabilities.
