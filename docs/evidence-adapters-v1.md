# Curator V2 trusted evidence adapter contract, version 1

This document defines the trust boundary that an evidence adapter must satisfy
before Curator V2 may accept a verification fact. The local library now
implements a host-injected receipt-verifier boundary, source-kind policy
wrappers, compact persisted attestations, and revalidation on every use. It
does not include trusted integrations with real repository runners, service
probes, browsers, or human identity systems, and it does not make the reference
plugin production-ready. Until a trusted verifier is injected,
`RejectUnverifiedEvidence` remains the required fail-closed default.

## Trust boundary

The host constructs and injects adapters from trusted configuration. Event,
MCP, checklist, and repository payloads may select an evidence reference, but
must never select or construct the verifier, its credentials, its allowed
project set, or its authentication principal. The Curator backend passes the
bound project, goal, criterion, and current verification time to the adapter;
an adapter must reject references outside that scope.

For every accepted reference, the adapter must independently establish all of
the following:

- **Authentication:** identify the source through host-owned credentials or an
  authenticated human principal. A source's self-asserted `outcome=passed`, a
  model statement, a repository file, or a caller-provided identity is not
  authentication. Missing, expired, or unverifiable credentials reject.
- **Integrity:** retrieve or validate the source and compare its independently
  computed SHA-256 with the reference. A matching hash proves byte identity,
  not source authenticity or correctness.
- **Scope:** bind the result to the configured project and the requested goal
  criterion. Repository adapters additionally bind to the configured worktree
  and revision; service adapters bind to the allowlisted service and probe;
  browser adapters bind to the allowed origin and capture/session; human
  observations bind to the authenticated actor and explicit confirmation.
- **Freshness:** enforce source-specific age and validity rules at every
  verification. Time values must be timezone-aware and checked against a
  trusted host clock. An immutable test result may remain valid only for its
  exact source revision; liveness probes require a short validity window.
  Reusing an expired result rejects.
- **Revocation:** re-check the source's current authorization and revocation
  state whenever Curator evaluates evidence. Revoked credentials, withdrawn
  source records, superseded revisions, and unavailable revocation checks fail
  closed. Deletion of a transient artifact during an authorized purge does not
  itself revoke proof if its immutable digest and decision remain in the
  canonical fact/receipt; without that retained commitment, the reference is
  unverifiable and fails closed. A cached result may not outlive the source
  adapter's declared validity window.
- **Boundedness:** return only a typed verdict and compact provenance
  identifiers, timestamps, and source revision/digest. Never persist raw
  command output, chat, transcript, page body, screenshot, or credential.

The service must invoke verification outside SQLite write transactions, then
re-check goal state and criterion revision at the write boundary. It must also
re-verify evidence when calculating criterion status and accepting completion;
an earlier successful check is not permanent authorization. Adapter exceptions,
timeouts, malformed attestations, and missing adapters are failures, never
passing evidence.

## Source-specific rules

| Adapter class | Minimum independent proof | Scope and freshness | Revocation / failure behavior |
| --- | --- | --- | --- |
| Repository diff or test | Host-controlled Git/worktree identity plus commit/tree hash; test results come from an allowlisted runner receipt, not prose or arbitrary command output | Exact configured repository and commit; code-review evidence is immutable to that commit, while a working-tree claim must hash the current selected files | Reject if the repository identity changes, the referenced commit/result is unavailable, or a signature/runner identity cannot be checked |
| Service probe | Authenticated host probe receipt with probe name, target identity, result, and observation time | Exact allowlisted project service and probe; liveness evidence must expire quickly (default ceiling: 60 seconds unless deployment policy tightens it) | Re-probe on use; timeout, stale result, target mismatch, or unavailable host identity is not healthy |
| Browser proof | Trusted browser/session receipt with authenticated capture source, origin, page/interaction identifier, observation time, and digest of the selected proof artifact | Exact allowed origin and project route; session evidence expires at session end or the configured short TTL | Revalidate session/origin and artifact digest before purge; afterward use the retained immutable digest/decision receipt. Reject cross-origin redirects, stale sessions, or missing/revoked receipts |
| Human-confirmed observation | Explicit confirmation action attributed to a verified host-authenticated human subject; include a bounded decision/receipt ID | Project, goal, criterion, actor, and confirmation time are bound; the confirmation is not inferred from agent text | Reject if actor authorization is missing/revoked, the receipt is absent, or the observation was withdrawn; retain its audit receipt without raw conversation |

The 60-second service-probe ceiling is a proposed maximum for freshness, not a
claim that any probe is currently configured or trusted. Product/deployment
owners must set source-specific identities, origins, service allowlists, runner
trust roots, and retention policy before enabling these adapters.

## Persisted attestation shape

An adapter result must be equivalent to this bounded record (field names are
illustrative until included in a versioned runtime contract):

```text
verified: true
evidence_kind: repository_test | service_probe | browser | human_observation
project_id: the exact bound project
goal_id: the exact bound goal
criterion_id: the exact criterion evaluated
evidence_sha256: the independently computed digest
source_revision: immutable commit, probe receipt, browser receipt, or decision ID
authenticated_subject: host-verified service or human identity
verified_at: timezone-aware host timestamp
valid_until: timezone-aware expiry for this source
revocation_checked_at: timezone-aware timestamp for the current source check
```

Every field is bounded and validated before the local adapter emits an
attestation. The fact store retains the typed record beside the immutable
verification fact, includes its bytes in capacity accounting and fact digests,
and exposes it only through authorized fact/report reads. Event payloads still
cannot supply an attestation. Existing schema-v7 verification facts migrate
with empty provenance and do not count as current proof.

## Required contract tests before enabling an adapter

- Reject absent, wrong, expired, or revoked credentials and any identity
  supplied only by an event or MCP argument.
- Reject cross-project, cross-goal, wrong-criterion, wrong-repository,
  wrong-origin, and wrong-service references.
- Reject digest mismatch, stale/future/naive timestamps, expired validity,
  superseded source revisions, and missing revocation checks.
- Revalidate on completion after a previously accepted fact, and prove that a
  later revocation removes current criterion verification without deleting the
  immutable historical fact.
- Prove adapter timeout/exception/unavailability fails closed and never writes
  a verification fact or changes a goal to complete.
- Prove no raw output or sensitive source contents enter SQLite, logs, error
  messages, metrics, traces, or canonical Markdown.
- Exercise each adapter against its real host identity and source, not only a
  mock or in-memory protocol implementation, before marking it production-ready.

## Current status

The local domain injects an `EvidenceVerifier` and defaults to
`RejectUnverifiedEvidence`. Typed receipt adapters cover the four evidence
kinds and enforce exact project/goal/criterion/hash/scope/subject binding,
fresh revocation checks, expiry, and source-specific age/validity ceilings.
Resolver receipts now reject unbounded or unsafe single-line fields, malformed
SHA-256 values, naive timestamps, and non-boolean revocation flags at object
construction; adapter tests cover these malformed-input cases. A local
`GitCommitDiffResolver` also hashes a bounded diff between full commit IDs in
one configured Git worktree and emits a path-free local receipt. Its checkout
and runner subject are host assertions; it does not authenticate a human or a
remote repository provider and it does not run tests. The integration test uses
a disposable Git repository and proves exact diff hashing, cross-project
rejection, immutable-range behavior, and the byte ceiling. These are local
source checks only. `LocalGitTestRunnerResolver` additionally runs a
host-configured argv in a disposable checkout of the exact commit, bounds its
runtime and combined output, rejects nonzero exits, and returns only a digest
bound to the runner ID and commit. Disposable-repository tests verify the exact
revision, failure handling, output limit, and absence of output/path data in
receipts. The local runner's command and subject remain operator assertions; it
does not authenticate CI, establish revocation, or provide deployment trust.
No deployment-owned repository runner, service probe, browser/session, or human
identity integration, deployment trust root, approved owner policy, or
end-to-end adapter test exists. Do not enable broad automatic capture or mark a
criterion verified from these local tests alone.
