# SDE qualification and review policy, version 1

This policy helps reviewers decide whether a verified goal outcome deserves a
durable Significant Development Event (SDE) record. Significance is about
lasting project value, not message count, diff size, emotional tone, or cue-word
matches. A candidate is only a proposal until an authorized human approves it.

## Qualification categories

| Category | Qualifies when | Does not qualify by itself |
| --- | --- | --- |
| Durable implementation | A user-visible or operational capability was implemented, its intended behavior is directly verified, and the compact facts will help a future maintainer understand or reuse it. | A code edit, refactor, dependency update, generated file, or passing test without evidence of a durable capability or useful project outcome. |
| Consequential decision | An authorized decision changes an enduring boundary, contract, workflow, data policy, ownership rule, or supported operating mode; record the decision and rationale. | A temporary preference, speculative proposal, routine task ordering, or an agent's inferred decision. |
| Verified recovery | A specific failure/root cause was established, the recovery was applied, and the relevant service or behavior was re-verified. Preserve the failure signal, causal finding, repair, and recovery proof as separate bullets. | An attempted fix, an unexplained green status, a transient restart, or a symptom without a verified cause/outcome. |
| Reusable verified lesson | A recurring failure mode or boundary was directly demonstrated, and a concrete prevention/recovery rule follows from that evidence. | Generic advice, an untested hypothesis, copied documentation, or a lesson that merely restates the task. |

Routine progress remains on the goal ledger. Examples include ordinary
maintenance, formatting, small fixes with no reusable outcome, repeated status
checks, work already captured by an existing SDE, and activity represented only
by transcript cues. A large diff or long session does not make routine work
significant.

## Evidence and claim language

- Link each SDE assertion to selected immutable goal facts and bounded evidence
  references. A passing check proves only the behavior covered by that check.
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
