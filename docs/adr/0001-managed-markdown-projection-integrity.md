# ADR 0001: Guard managed Markdown projections against accidental edits

- Status: accepted for the local Curator V2 reference implementation
- Date: 2026-10-19
- Scope: per-project plugin projection of one goal into a configured Markdown
  target
- Approval boundary: this does not choose a deployment-wide system of record or
  replace repository-owner authorization for conflict recovery

## Context

Curator V2 stores structured goal state in its shared SQLite backend and
projects compact bullets into a consumer-owned Markdown file. An explicit
projection may update an older generated goal block after new facts arrive. The
previous block markers identified the goal but did not indicate whether a
person had edited the block; a later projection could replace those edits.

SQLite-versus-Markdown authority and production recovery remain unresolved.
The reference plugin therefore needs to avoid silently discarding recognizable
manual edits without inventing an automatic merge or restore policy.

## Decision

- Add an unkeyed SHA-256 content checksum to every newly generated goal block.
- Permit a stale block to be updated only when its existing checksum validates.
- Permit an unchecksummed legacy block to be upgraded only when its full content
  exactly matches the current SQLite projection.
- Refuse to replace a checksum-mismatched block or a stale unchecksummed legacy
  block. Reconciliation reports checksum mismatch as `malformed`; operators
  preserve both stores and resolve the conflict explicitly.
- Keep unrelated Markdown untouched. Continue to re-read and hash the full
  target before recording canonical-persistence proof for purge.

The checksum detects accidental or ordinary edits that do not update the
marker. It is not a signature: a writer with access to the file can recompute
it. It does not authenticate a producer, prove SQLite is authoritative, or
authorize conflict repair.

## Consequences

- Routine ledger updates remain idempotently projectable while the generated
  block and its checksum are intact.
- Manual edits inside a generated block no longer disappear silently; the
  affected projection fails closed and the purge gate cannot rely on that
  failed write.
- Old exact projections are upgraded without a SQLite migration. Stale legacy
  blocks may require owner-reviewed manual reconciliation before future
  projection.
- Production still needs a system-of-record decision, backup/restore drills,
  authenticated recovery operators, and deployment evidence.

## Verification

`tests/test_markdown_persistence.py` covers manual-edit preservation, exact
legacy upgrade, stale-legacy refusal, ledger-first updates, idempotent retry,
and canonical-persistence/purge ordering. API reconciliation tests cover the
read-only status and authorization boundary. These are local test results, not
production recovery evidence.
