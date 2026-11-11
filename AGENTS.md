# Curator V2 repository contract

This repository owns the proposed CuratorMD global backend. A repository-
specific plugin and its configuration belong in each consuming project; do
not mix consumer source, state, or persistence into this repository. Host
Steward belongs to the Hermes Core account, not CuratorMD.

## Development contract

- Start each task with the problem and observable success criteria.
- Follow the [Codex Execution and Approval SOP](docs/codex-execution-and-approval-sop.md).
  Owner UX approval reviews usable, repeatable behavior; it is not a prerequisite
  for coding, local checks, or closing passed engineering criteria. Ask the owner
  about material project decisions, resolve routine engineering choices, and
  keep independent work moving.
- Record compact typed goal facts for intent, changes, checks, open gaps, and
  outcome. Complete a task when its result is observed; missing automated
  evidence does not block completion or an SDE proposal. Label claims and
  verification honestly, ask the owner when unsure, and leave SDE disposition
  and persistence to human review.
- Persist compact, deduplicated bullet facts. Do not retain raw chats,
  transcripts, imports, cues, or scratch artifacts as canonical knowledge.
- Keep proposed SDEs reviewable and separate from ordinary goal progress.
- After the owner's SDE approval, transfer approved facts to pertinent
  persistence docs and verify the saved content. That single decision
  authorizes automatic cleanup of eligible, candidate-scoped transient
  artifacts after successful readback and an internal comparison confirms the
  saved entry contains the same artifact-inventory and dependency-map
  fingerprints as the rechecked transient set; do not ask for another deletion
  approval.
- Build and recheck the complete exact cleanup inventory internally. Keep held,
  changed, incomplete, out-of-scope, or failed artifacts pending.
- Commit durable facts and an auditable receipt before purging transient
  artifacts. Make purge retries idempotent and expose failures as
  `purge_pending`; never report a false healthy/green state.
- Human approval is required for SDE disposition. The approved SDE decision
  also authorizes only its verified, candidate-scoped transient cleanup.
- Keep event payloads bounded; stream large inputs rather than reading them
  fully into memory.
- Mark unimplemented architecture and interfaces as proposed. Do not describe
  a scaffold or passing unit test as working end-to-end behavior.

## Repository workflow

- Python 3.12+ with strict typing at domain and adapter boundaries.
- Add focused regression tests for lifecycle and deletion behavior.
- Do not import V1 runtime state or raw artifacts into this repository.
- No deployment, external publication, commit, or push without an explicit
  request.
- For an explicitly requested full push, inventory staged, unstaged, and
  untracked changes before publishing. Include all authorized pending work,
  integrate the latest remote tip, resolve overlaps without duplicating
  behavior, and verify the pushed commit contains the full requested scope.
  After publishing from another worktree, reconcile the original checkout
  when its changes are represented in the published tree, then verify the
  branch is clean and up to date with its remote. Preserve changes that are
  outside the authorized scope and report any state that cannot be safely
  reconciled.
- Work reported problems through diagnosis, repair, and an observable success
  check. A failed or forbidden path is evidence for finding the supported
  recovery route, not a reason to stop while authorized work remains. Finish
  active work before switching to an unrelated request unless the new request
  changes its scope or supplies information needed to proceed.

## Markdown documents

- Treat lint findings as signs that the source may be difficult to scan. Fix
  the heading structure, spacing, and line wrapping so the document reads
  clearly in source and preview.
- Do not suppress, bypass, or reconfigure lint rules just to obtain a passing
  result. Use the repository's actual lint configuration and address the
  underlying formatting issue.
- Use real hierarchical headings instead of bold text as headings. Keep
  editable fenced JSON readable and preserve owner edits when regenerating a
  review document.
