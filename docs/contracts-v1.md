# Curator V2 contract index, version 1

Status: proposed local-library contract. It is not a production compatibility
promise or evidence that a Hermes host, authenticated transport, or consumer
plugin is deployed. Contract owners must approve the retention and security
policies before a production stability commitment.

This v1 contract family is still pre-release. Its schemas and plugin surface may
change together before an approved consumer rollout; no compatibility is
promised for draft wheel/config pairs. At the first pilot release, freeze the
schema and plugin API versions, pin the wheel, and provide an explicit migration
for any consumer config or tool-shape change. After that freeze, required-field
or meaning changes need a new contract version.

## Canonical contract sources

| Contract | Versioned source | Runtime authority | Current verification boundary |
| --- | --- | --- | --- |
| Goal lifecycle events, envelope, and processed receipts | [`event-contract-v1.md`](event-contract-v1.md), [`schemas/curator-v2-v1.schema.json`](schemas/curator-v2-v1.schema.json) (`eventEnvelope`, payloads, and `eventInboxReceipt`) | `curatormd_v2.events.EventEnvelope`, payload types, and `EventInboxReceipt` | Runtime parser/encoder, all eleven event payloads, and both durable receipt dispositions validate locally; no external producer is connected. |
| Goal, criterion, evidence, and fact records | [`schemas/curator-v2-v1.schema.json`](schemas/curator-v2-v1.schema.json) (`goalCard`, `successCriterion`, `evidenceRef`, `fact`) | Frozen typed records; lifecycle invariants also enforced by `CuratorStore` | Runtime record shapes validate against Draft 2020-12 schema; no production wire serializer exists. |
| Evidence trust requirements and provenance | [`evidence-adapters-v1.md`](evidence-adapters-v1.md), [`schemas/curator-v2-v1.schema.json`](schemas/curator-v2-v1.schema.json) (`evidenceAttestation`) | Host-injected `EvidenceVerifier`, source-kind receipt adapters, persisted `EvidenceAttestation`, and fail-closed default | Local synthetic-receipt tests cover binding, freshness, revocation, and fail-closed behavior; real source resolvers, deployment trust roots, and owner policy remain open. |
| SDE candidate, review packet, decision, and quality feedback | [`sde-review-policy-v1.md`](sde-review-policy-v1.md), [`api-v1.md`](api-v1.md), [`schemas/curator-v2-v1.schema.json`](schemas/curator-v2-v1.schema.json) (`sdeCandidate`, `sdeReviewPacket`, `sdeCorrection`, `sdeQualityFeedback`, `sdeQualityFeedbackSummary`) | `SDECandidate`, `SDEReviewPacket`, `SDECorrection`, `SDEQualityFeedback`, `AuditReceipt`, review authorization protocols | Local review, persistence, metric privacy, and schema tests; feedback labels are human QA only, and default authorization rejects callers until a trusted host adapter is supplied. |
| Receipt, artifact inventory, retention holds, and purge state | [`api-v1.md`](api-v1.md), [`content-safety-v1.md`](content-safety-v1.md), [`schemas/curator-v2-v1.schema.json`](schemas/curator-v2-v1.schema.json) (`artifactRef`, `auditReceipt`, `purgeTargetStatus`) | `AuditReceipt`, `ArtifactRef`, `PurgeTargetStatus`, `ArtifactPurger`, and `CuratorStore` | Local schema, migration, hold-exclusion, authorized release/audit, hash/root-confinement, and retry tests; no real producer staging adapter or host reviewer binding is connected. |
| Repository plugin configuration | [`project-plugin-v1.md`](project-plugin-v1.md), [`schemas/curator-v2-v1.schema.json`](schemas/curator-v2-v1.schema.json) (`projectConfig`) | `ProjectConfig.load` | Strict TOML parsing, schema, and path-confinement tests; installation into a real consumer is open. |
| Authenticated operations and MCP tool surface | [`api-v1.md`](api-v1.md), [`mcp-tools-v1.md`](mcp-tools-v1.md) | `AuthenticatedCuratorAPI` and MCP factory | In-process authorization tests and local stdio subprocess tests; production identity binding is open. |
| Markdown projection reconciliation | [`api-v1.md`](api-v1.md), [`mcp-tools-v1.md`](mcp-tools-v1.md) | `MarkdownPersistenceAdapter.reconcile_goal` and `reconcile_project` | Bounded, read-only goal pages and orphan-marker inventory are covered locally; conflict repair and authoritative-store policy remain open. |
| Transport-neutral error envelope | `curatormd_v2.errors.APIError` | `APIErrorCode`, `to_api_error` | Unit tests verify stable codes and that internal exception details are not exposed; no remote transport currently emits this envelope. |

The schema bundle defines versioned JSON-compatible data shapes and validates
the runtime dataclasses, event encoder, error value, and repository TOML sample.
It does not create a production wire serializer: the record definitions are
local contract shapes, not an implemented network transport. Transport code
must use a deliberate serializer and add producer/consumer compatibility tests
before claiming interoperability.

## Versioning and compatibility policy

- Version `1` is exact for the event envelope, project-config schema, and
  project-plugin/backend API contract. Config declares both
  `schema_version = 1` and `backend_api_version = 1`; an
  unknown version, unknown field, duplicate JSON key, invalid enum, or missing
  required field is rejected; readers must not guess or silently discard data.
- Version-1 events may omit the historical optional `source_id` and
  `source_sequence` fields. The decoder supplies the documented legacy
  defaults. Optional lifecycle revision fields default to revision `1` only
  for older event payloads; the store then applies its current revision fence.
- A compatible v1 change may add an optional field only when old readers can
  reject it safely and new readers preserve the documented legacy defaults.
  Because the current parsers reject unknown fields, adding a field requires a
  coordinated producer/consumer rollout or a new schema version; it is not
  backward compatible with deployed v1 readers.
- Any change to required fields, field meaning, enum values, lifecycle
  semantics, privacy boundaries, or receipt/purge ordering requires a new
  contract version and an explicit migration. Never rewrite stored v1 events
  or receipts in place. A migration must be bounded, idempotent, retain the
  original digest/provenance, and have a tested rollback or restore path.
- Project configuration version `1` is repository-owned and fail-closed. Its
  backend API version must exactly match the runtime's published supported
  contract version. A
  plugin must not execute config content, infer a different project root, or
  migrate a file automatically. Unsupported versions require a reviewed
  migration tool and a backup of the original file.
- Error envelope version `1` is `{schema_version, code, message}`. Codes are
  `invalid_request`, `forbidden`, `not_found`, `conflict`, `capacity_exceeded`,
  `rate_limited`, and `internal_error`. `to_api_error` maps internal exception
  classes to these categories and emits fixed public messages; exception text
  must never be copied into a client response. An external transport must use
  this mapper and add transport-level contract tests before claiming the error
  contract is integrated.

## V1 executable examples

- [`examples/event-v1-goal-started.json`](examples/event-v1-goal-started.json)
  has a checklist digest matching its exact sample checklist bytes, is parsed
  and round-tripped by `test_published_event_v1_fixture_is_accepted_by_the_runtime_parser`
  in `tests/test_events.py`, and is replayed through an authenticated local
  backend by `test_published_producer_fixture_runs_through_authenticated_backend`
  in `tests/test_api.py`.
- [`examples/curatormd-v2.toml`](examples/curatormd-v2.toml) is loaded by the
  `test_published_project_config_fixture_loads` in `tests/test_project_plugin.py`
  after creating its declared repository paths in an isolated Git fixture.
- Existing event, lifecycle, review, receipt, purge, API, and plugin tests
  exercise record invariants beyond these two examples. They remain local
  verification and do not establish cross-version interoperability.

## Open contract gates

- Share the producer/backend compatibility fixture with actual producer
  plugins and verify it against a real consumer plugin before claiming
  interoperability. The local authenticated API fixture test is not that
  cross-repository integration.
- Integrate the stable error envelope into each external transport and test
  its encoded response.
- Approve privacy, retention, legal-hold, and archive/migration policies.
- Define production serializers and transport behavior separately from these
  local JSON-compatible schema shapes.
