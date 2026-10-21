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

The local attended reviewer may combine disposition and cleanup approval in
one explicit action when it displays a complete, freshly hashed inventory.
The reviewer must type the decision, candidate ID, and inventory hash. The
plugin re-scans the exact inventory before storing the receipt, then persists
canonical facts and the receipt before attempting eligible purge. Any held
artifact remains held. Incomplete inventories cannot authorize cleanup through
this workflow. Other API callers may record a decision and complete an
inventory separately; they do not inherit the local reviewer's combined
confirmation.

This policy does not define legal holds, project-specific retention, or an
automatic compaction policy. Those remain explicit release gates.
