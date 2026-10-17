# Curator V2 repository contract

This repository owns the proposed CuratorMD global backend. A repository-
specific plugin and its configuration belong in each consuming project; do
not mix consumer source, state, or persistence into this repository. Host
Steward belongs to the Hermes Core account, not CuratorMD.

## Development contract

- Start each task with the problem and observable success criteria.
- Record typed goal events: intent, changed fact, verification, open gate, and
  outcome. A completion claim is not evidence.
- Persist compact, deduplicated bullet facts. Do not retain raw chats,
  transcripts, imports, cues, or scratch artifacts as canonical knowledge.
- Keep proposed SDEs reviewable and separate from ordinary goal progress.
- Commit durable facts and an auditable receipt before purging transient
  artifacts. Make purge retries idempotent and expose failures as
  `purge_pending`; never report a false healthy/green state.
- Human approval is required for SDE disposition and destructive cleanup.
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
