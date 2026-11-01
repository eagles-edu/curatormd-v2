# SDE qualification and review policy, version 1

This policy helps the owner review proposed Significant Development Event
(SDE) records. Curator prepares a pending proposal from supported facts at each
completed tracked task or plan-item endpoint; it does not decide that a task is
too routine or unimportant to show for review. Materiality and retrieval value
are recommendations. The owner decides what is memorialized, its importance,
and its disposition. A candidate is only a proposal until the owner decides.

## Suggested materiality categories

The categories below help describe a pending proposal. They do not decide
whether a proposal is created or whether a task fact is worth keeping.

| Category | Suggested description | Evidence limits to show the owner |
| --- | --- | --- |
| Durable implementation | A user-visible or operational capability was implemented and its intended behavior was checked. | A code edit or passing test alone does not prove lasting impact. |
| Consequential decision | The owner made a decision that changes an enduring boundary, contract, workflow, data policy, ownership rule, or supported operating mode. | Do not present a temporary preference, speculation, or an agent-inferred choice as an owner decision. |
| Verified recovery | A failure/root cause was established, the recovery was applied, and the relevant behavior was checked again. | An attempted fix or unexplained healthy status does not establish the cause or recovery. |
| Reusable verified lesson | A recurring failure or boundary was demonstrated, with a concrete prevention or recovery rule. | Generic advice, an untested hypothesis, or copied documentation is not verification. |

Routine work may still have a pending proposal so the owner can approve,
reject, or otherwise dispose of it. Examples include ordinary maintenance,
formatting, small fixes, repeated status checks, or work already represented by
an existing SDE. A large diff or long session does not make work significant;
that judgment is offered to the owner rather than used to suppress the proposal.

## Evidence and claim language

- Link each SDE assertion to selected immutable goal facts and bounded evidence
  references. A proposal may be created before verification; label missing or
  stale proof clearly. Approval requires current passing evidence. A passing
  check proves only the behavior covered by that check.
- Include a compact impact statement and a separate retrieval-value statement
  in every new candidate. Label impact as observed or expected where needed;
  retrieval value describes what a future maintainer may need to find and is
  not evidence that the proposed impact occurred.
- Keep observed facts distinct from expected benefits, estimates, and open
  questions. Use wording such as `Observed:` for directly measured outcomes and
  `Expected:` for plausible but unmeasured benefits.
- Do not infer clinical, production, user, cost, reliability, or performance
  impact from local tests unless those tests directly measure that outcome.
- A completion claim, healthy service indicator, event count, cue, or SDE
  materiality label is not evidence on its own.
- Write the candidate as compact bullets: trigger/context, decision or change,
  verification, outcome/impact, and remaining gate. Keep the rationale to one
  concise line; never place a transcript, multi-paragraph recap, command output,
  or raw artifact in the review packet or canonical record.

## Reviewer decision

The reviewer checks source facts, evidence scope, materiality category,
observed-versus-expected wording, duplicate history, and retention/cleanup
manifest. Approval or rejection is attributable and immutable. A correction is
a separately authorized, append-only record linked to the decided candidate;
it never rewrites the candidate or its decision receipt. Pending decisions do
not authorize cleanup. Canonical project facts and the receipt must be durable
before purge of the exact unchanged transient manifest begins.

The local attended reviewer uses one explicit action for both the SDE
disposition and purge authorization. The confirmation phrase includes the
complete freshly hashed inventory manifest displayed in the review packet. The
plugin re-scans that exact inventory, records a distinct cleanup receipt,
persists both receipts canonically, and only then attempts deletion. Any held
artifact remains held. Incomplete or changed inventories cannot authorize
cleanup.

## Approved local-alpha artifact retention default

The owner approved this local-alpha default on 2026-10-22: raw chat/transcript,
cue, import, scratch, generated intermediate, and duplicate artifacts become
eligible for expiry as soon as their compact facts are recorded and any related
SDE is approved or rejected, with 72 hours as the absolute maximum age. The
explicit SDE decision clears only the pending-SDE review hold. Legal or
operational artifact holds remain in force until separately released by an
authorized reviewer. The same explicit review action authorizes purge only for
a complete, freshly hashed inventory displayed in the packet; a scheduler may
retry only a purge already approved in a durable receipt.

This is the approved policy for local alpha, not evidence that expiry is fully
operational in production. The explicit review action authorizes cleanup only
for its complete exact inventory; a separate durable cleanup-authorization
receipt binds that inventory and its canonical projection before the SDE
review path can purge unheld artifacts.
V2 records publication time for producer-staged files and exposes a read-only
72-hour candidate scan that fails closed on unknown age or incomplete
inventory. The local implementation now supports attended approval of an
expiry-only inventory, a durable receipt before unlink, hold integration, and a
one-shot retry command that can process only existing approvals. Production
retention policy, deployed scheduling/alerting, and deployment-owner policy
remain open release gates.
