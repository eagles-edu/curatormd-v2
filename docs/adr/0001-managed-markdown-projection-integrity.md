# ADR 0001: Guard managed Markdown projections against accidental edits

- Status: accepted for the local Curator V2 development utility
- Date: 2026-10-19; system-of-record decision confirmed 2026-10-28
- Scope: per-project plugin projection of one goal into a configured Markdown
  target, with SQLite as the authoritative structured ledger
- Conflict recovery: preserve both copies and require explicit review by the
  local owner before rebuilding the Markdown projection

## Context

Curator V2 stores structured goal state in its local SQLite ledger and projects
compact bullets into a consumer-owned Markdown file. An explicit projection may
update an older generated goal block after new facts arrive. The previous block
markers identified the goal but did not indicate whether a person had edited
the block; a later projection could replace those edits.

The owner selected SQLite as the authoritative structured record and Markdown
as its readable projection. A mismatch still requires review: the system must
preserve both copies and stop automatic projection or recovery until the owner
reviews the difference.

## Decision

- Add an unkeyed SHA-256 content checksum to every newly generated goal block.
- Permit a stale block to be updated only when its existing checksum validates.
- Permit an unchecksummed legacy block to be upgraded only when its full content
  exactly matches the current SQLite projection.
- Refuse to replace a checksum-mismatched block or a stale unchecksummed legacy
  block. Reconciliation reports checksum mismatch as `malformed`; operators
  preserve both copies and resolve the conflict explicitly before rebuilding
  Markdown from SQLite.
- Keep unrelated Markdown untouched. Continue to re-read and hash the full
  target before recording canonical-persistence proof for purge.

The checksum detects accidental or ordinary edits that do not update the
marker. It is not a signature: a writer with access to the file can recompute
it. It does not authenticate a producer or authorize conflict repair.

## Consequences

- Routine ledger updates remain idempotently projectable while the generated
  block and its checksum are intact.
- Manual edits inside a generated block no longer disappear silently; the
  affected projection fails closed and the purge gate cannot rely on that
  failed write. Curator preserves the mismatch for local owner review and does
  not rebuild Markdown automatically.
- Old exact projections are upgraded without a SQLite migration. Stale legacy
  blocks may require owner-reviewed manual reconciliation before future
  projection. SQLite remains authoritative; no automatic recovery writes into
  SQLite from Markdown.

## Verification

`tests/test_markdown_persistence.py` covers manual-edit preservation, exact
legacy upgrade, stale-legacy refusal, ledger-first updates, idempotent retry,
and canonical-persistence/purge ordering. API reconciliation tests cover the
read-only status and authorization boundary. These tests verify the local
projection and conflict behavior.
