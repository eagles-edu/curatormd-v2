# Curator V2 preliminary threat model, version 1

**Status: proposed engineering analysis; not owner-approved and not a release
or privacy certification.** This document covers the local Curator V2 library
slice in this repository. It does not claim that Hermes Core, a consumer
plugin, a production database, or a deployed network path is integrated or
secure.

## Scope and security objectives

Curator V2 should retain only bounded, useful project facts and review receipts;
keep raw source material temporary; preserve project isolation; require
independent evidence for verification; require an authorized human for SDE
decisions and destructive cleanup; and report incomplete processing or purge
truthfully. Host inventory and cleanup belong to Hermes Core's Host Steward,
not this Curator backend.

The security boundary begins at any caller or project-plugin input and ends at
the backend's temporary inbox, goal/fact store, review records, project-owned
canonical Markdown target, and configured temporary staging root. External
authentication, production transport, real evidence adapters, backup systems,
and Hermes lifecycle routing are outside the verified local boundary.

## Assets and trust boundaries

| Asset or boundary | Security concern | Local implementation evidence |
| --- | --- | --- |
| Goal problems, criteria, fact bullets, evidence locators, review decisions | Untrusted input could persist secrets, personal data, misleading claims, or oversized content. | Typed bounded models, versioned event schemas, reject-only sensitive-pattern checks, and byte/count ceilings. |
| Event inbox payloads and source cursors | Duplicate, reordered, oversized, or unprocessed events could corrupt state or exhaust storage. | Event IDs/source sequences, idempotent processing, payload limits, per-project sequence checks, global receipt caps, and processed-payload discard behavior. |
| Evidence references | A caller could assert a passing check without authentic proof, or reuse stale proof. | The default verifier rejects all evidence; only a configured verifier can accept it. Production identity, provenance, freshness, and revocation remain open. |
| Project-scoped API operations | A caller could read or mutate another project's records or approve its reviews. | Authorizer protocol, fail-closed default, project/action checks, reviewer binding, and in-process per-subject/project rate limits. Host identity and role binding are not deployed. |
| SQLite state and canonical Markdown | A process failure could leave records inconsistent, or filesystem access could expose them. | Transactional local writes, private database-file permissions, bounded writes, and canonical-write proofs before purge. Cross-store crash reconciliation, encryption, backups, and restore are unverified. |
| Temporary staging artifacts | A malicious path, symlink, changed file, incomplete inventory, or crash could delete the wrong item or lose evidence. | Configured-root confinement, exact regular-file manifests, hashes, symlink/directory rejection, complete-inventory gate, immutable receipt, and retryable purge-pending state. Race-resistant deletion and production-storage failure injection remain open. |
| Hermes Core and Host Steward boundary | Curator events or cleanup authority could be confused with host ownership. | Repository ownership contract keeps Hermes Core and Host Steward external; no Host Steward component exists in this repository. Integration and negative authorization tests remain open. |

## Threat register

| Threat | Current mitigation | Residual risk / required evidence |
| --- | --- | --- |
| Malicious prompt or repository content injects instructions, secrets, or false success claims into durable facts. | Treat producer text as untrusted; bound and validate fields; reject recognized secret/PII patterns; completion claims do not satisfy criteria. | Pattern checks can miss or falsely flag content. Add owner-approved data rules, broader format/jurisdiction analysis, and adversarial corpus tests. |
| Forged, stale, or mis-scoped evidence claims a criterion passed. | Evidence is accepted only through a configured verifier; default rejects all. Verification facts link to bounded references and criteria. | No real repository/test/browser/service adapter is installed. Define adapter identity, source authorization, hash semantics, freshness, replay, and revocation before accepting production evidence. |
| Cross-project read/write, review, or purge through a confused-deputy plugin. | Project IDs are checked at API/service boundaries; authorizer defaults to deny; configured project roots and targets are scoped. | No production identity provider, tenant binding, or installed consumer plugin has been tested. Require negative cross-project and wrong-role integration tests. |
| Replayed, reordered, or conflicting lifecycle events alter state or create duplicate facts. | Stable event IDs, source sequence fences, transactional cursor updates, deduplication, lifecycle revisions, and concurrency tests. | Router retry/quarantine and restart/load behavior are not deployed. Add production-router contract, lag, quarantine, and replay tests. |
| Oversized event or fact streams exhaust memory or disk. | Event and model size ceilings, bounded lists, per-goal/project fact budgets, global inbox caps, and bounded report pages. | Limits are not yet tied to measured deployment budgets; inbox/failed-event retention and alert thresholds require an operator policy and load/disk-growth evidence. |
| Secret or personal data leaks through logs, exceptions, metrics, traces, backups, or upstream transport. | Sensitive-content errors identify only field/category; the detector rejects instead of redacting; public errors use bounded stable codes. Hosted startup now suppresses exception text, and a local backup test proves a processed event's serialized envelope is absent while its digest receipt restores. | Failed/quarantined event payloads intentionally remain in SQLite for retry and therefore can enter backups. This does not prove WAL-page scrubbing, every logging/trace path, upstream transport, or deployed behavior. Define retry-payload backup policy and perform data-flow/leakage tests across the deployed stack before capture is enabled. |
| Purge traversal, symlink substitution, file replacement, or partial failure deletes unintended data or hides retained artifacts. | Resolve paths below a configured staging root; require exact manifest/hash and complete inventory; refuse symlinks/directories; persist receipt before deletion; retain retryable pending state. | Path validation tests do not prove race freedom. Test adversarial concurrent replacement and failure injection on the production filesystem; define holds, retry/backoff, alert, and operator override policy. |
| A staged leaf is replaced after its descriptor is opened and hashed but before the path-based unlink. | Open without following symlinks, hash through the pinned descriptor, compare descriptor metadata before/after reading, then compare the leaf name's device/inode to the verified descriptor immediately before unlink. A deterministic regression proves a replacement inserted after hashing is retained and leaves the receipt pending. | The name comparison and unlink are separate filesystem operations; an adversary can still race that final interval. An opened ancestor directory can also be moved by a process with write access. This is not a sandbox against another process with the same filesystem privileges; controlled staging ownership/locking and adversarial deployment-filesystem tests remain required. |
| SQLite or Markdown interruption creates false completion or false-clean status. | Atomic SQLite lifecycle writes, criterion-derived completion, canonical-write proof, explicit purge state, and integrity/hash checks in the local slice. | Authoritative-store choice, SQLite/Markdown crash reconciliation, corruption recovery, backup/restore, and operator repair runbook are open. |
| Compromised or buggy plugin fabricates facts, broadens paths, or claims an incomplete inventory is complete. | Plugin configuration is project-scoped and bounded; backend checks project IDs, configured paths, and inventory completeness; evidence defaults to reject. | The plugin is not a security sandbox. Define plugin installation/signing, version pinning, least privilege, review, update/revocation, and real-consumer isolation tests. |
| Host Steward cleanup authority is used to mutate Curator project knowledge, or Curator purge is mistaken for host cleanup. | Ownership is explicitly separated; Host Steward is not implemented in this repository. | Hermes Core must prove distinct identities, approval gates, managed executors, receipts, and negative tests showing no project-knowledge write path. |

## Minimum deployment decisions before enabling capture

The product and deployment owners must decide and record:

- Which data classes and jurisdictions are in scope, including prohibited
  identifiers and approved retention periods for each artifact class.
- Which identity provider supplies project, reviewer, and operator roles, and
  how credentials are rotated, revoked, audited, and least-privileged.
- Which source adapters may verify evidence, how their hashes and freshness
  windows are established, and how compromised or revoked sources fail closed.
- Whether SQLite, canonical Markdown, backups, transport, and logs require
  encryption, and how keys and access audits are managed.
- How long pending/failed inbox payloads, review material, artifacts, receipts,
  and backups remain; who can place a legal/operational hold; and who can release
  a hold or authorize deletion.
- Storage budgets, queue/purge retry policy, dead-letter handling, alert owners,
  and stop conditions for unexplained growth or incomplete cleanup.
- Recovery authority and tested procedures for database corruption, partial
  cross-store writes, restore, migration rollback, and artifact-receipt mismatch.

Until those decisions and deployment tests exist, automatic capture, broad
retention, production evidence acceptance, and unattended destructive cleanup
must remain disabled. A passing local test suite does not close these gates.

## Verification boundary

The current repository tests establish selected library invariants only. They
do not prove confidentiality of a deployed stack, completeness of PII
detection, secure transport, production authentication, filesystem race
resistance, operational retention, or Host Steward behavior. Track the open
items in [`release-gates-v2.md`](release-gates-v2.md) and the implementation
checklist; do not label this analysis approved until deployment owners review
and accept its assumptions and residual risks.
