# Proposed SDE review and knowledge improvements

Status: design for review. This document does not claim that the proposed
behavior is implemented or authorize a change to an SDE decision.

## Problem and outcome

An owner should be able to see what an SDE actually proposes to remember,
why each destination fits, and what happened after approval. Retained knowledge
should remain useful as it grows. The intended result is a review experience
that supports informed edits, honest evidence labels, reliable persistence, and
focused retrieval without losing approved material.

## Build on the existing workflow

The current VS Code generator recommends configured destinations and gives a
reason for each. The editable decision is bounded and the backend binds the
review action to the candidate, facts, evidence state, and draft. The review
workflow prepares and journals destination projections. These are source-level
observations; this document does not establish live-host acceptance.

## Proposed improvements

1. Show a concise candidate outcome, supporting fact labels, open gaps, and
   recommended destinations. Explain why each destination is included or
   omitted. Treat recommendation heuristics as advice, not proof.
2. Let the owner review and edit the exact content proposed for each configured
   destination. Distinguish a historical outcome, a supported reusable lesson,
   an agent instruction, and a repeatable procedure. Avoid requiring a change
   to every destination. Preserve dirty editor content and owner edits across
   refresh and reopen.
3. Keep candidate identity, fact provenance, and evidence state authoritative
   in Curator. Bind the approved destination-specific text and configuration to
   the reviewed action. An observed outcome may be proposed without automated
   evidence; do not infer verification from a default or editable field.
4. Show an actionable durable result for each destination: saved and read
   back, already applied, conflicting, or failed. Show cleanup separately,
   including `purge_pending` where the candidate inventory or fingerprint
   checks cannot be completed. Retain receipts and make retries idempotent.
5. Measure actual document and retrieval usage before choosing limits. If a
   size indicator is useful, label estimates and make thresholds project
   policy. Prefer selecting relevant knowledge for a task over loading entire
   documents. Surface stale or unavailable retrieval honestly.
6. Design any archive or consolidation operation separately: show the exact
   affected content, preserve its meaning and discoverability, verify readback,
   detect concurrent changes, and provide a recoverable retry. An SDE approval
   does not by itself authorize moving unrelated previously approved entries.

## Decisions and implementation boundaries

- Decide whether destination-specific content belongs directly in the editable
  decision or in a separate review view, and how much detail is shown by
  default. The owner should be able to inspect the final exact text.
- Define project-configured destinations and their purposes without hard-coding
  a consumer's persistence files into the global backend. Version any new draft
  schema and preserve a migration path for existing pending drafts.
- Decide whether and when budget warnings matter to a specific host. Do not
  call a character-based estimate a hard model token limit.
- Keep retrieval triggers as recommendations until a host implements and
  verifies their behavior. A metadata label alone does not enforce a trigger.
- Define any future archive authorization and active-instruction retrieval
  policy before implementing automatic movement of retained knowledge.

## Practical acceptance checks

- Review a candidate with multiple destinations and different proposed text;
  edit it, refresh and reopen, and confirm the exact edits survive. Verify the
  real VS Code action binds that decision to the current candidate and facts.
- Exercise missing and stale evidence, changed facts, changed destinations,
  duplicate submissions, a partial write, and retry. Confirm that the result
  reflects each destination and cleanup remains pending where appropriate.
- Exercise a configured consumer with different destination names. Confirm
  that unconfigured paths and unrelated projects cannot be written.
- If retrieval or budget indicators are added, measure them on representative
  documents and verify their labels, source coverage, and unavailable states.

These checks describe proposed acceptance, not results already obtained.
