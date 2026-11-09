# Codex Execution and Approval SOP

## Purpose

This SOP keeps owner decisions meaningful without making them a queue that
blocks implementation. Codex is responsible for turning an agreed request and
its specification into working, tested code. The owner remains responsible
for decisions that belong to the owner, final UX acceptance, SDE disposition,
and any separately controlled production action.

The engineering item and the owner review are separate lifecycle records.
Owner review may follow engineering completion; it is not a prerequisite for
coding, local verification, or closing an engineering item whose criteria
pass.

## Plan work without an approval gate

At the start of a project or bounded task:

1. State the problem and the observable result that will count as done.
2. Give the task one practical success check. Add another only when the request
   has a genuinely independent outcome that cannot be covered by the first.
3. Identify decisions that actually require the owner's product or project
   judgment. Ask those questions early and narrowly.
4. Keep implementation tasks actionable from the agreed requirements. Do not
   add “owner approval” as a dependency of coding, tests, or engineering
   completion.
5. Track any owner UX review, SDE disposition, or separately controlled
   operational action as its own gate, with a clear reason and scope.

**A plan can and should include an explicit decision task when the project genuinely lacks a required but undetermined product choice.** That task covers the choice itself; _it does not make all other implementation wait_. Continue work that does not depend on the answer, then implement the decision after the owner resolves it.

## Decide what to ask

Ask the owner whenever an unresolved choice materially changes agreed product
behavior, user-visible workflow, scope, data handling, compatibility, or a
project constraint.

```md
State the decision and give:

- the realistic options;
- the practical effect of each option; and
- a recommendation when evidence supports one.

Keep the question limited to the affected behavior.
```

Resolve routine engineering choices within the agreed scope. Examples can include
internal names, code structure, test organization, a reversible library usage
choice, and implementation details already constrained by the specification.
Choose a conventional, reversible option, document material assumptions, and
continue. If the choice later changes user-visible behavior or a stated
constraint, bring that specific choice to the owner.

When a missing decision blocks only one part of a task, record a clearly labeled
TODO in the applicable consumer-owned pending-review document, such as
`.curatormd-v2/sde-proposals/pending-review.md`. Keep that part open and
continue independent work. Record the unresolved choice and the exact work it
blocks; do not mark the whole project blocked if useful work remains.

## Implement and verify

Codex owns implementation through a usable state. Work from the agreed
requirements, preserve existing work, and add focused regression coverage for
the behavior being changed. Run the relevant checks and test the behavior
against its stated purpose. Include performance checks when performance is a
stated requirement or an observable part of that purpose.

For behavior that must be safe to repeat, test retries and repeated user
actions. The same logical operation should reach the intended result without
creating duplicate records, repeating destructive effects, or losing accepted
user edits. Test both the successful path and the failure or recovery path that
the specification requires.

For code changes, a passing relevant test or lint check is enough evidence for
the task. If the owner says they ran the check or confirms the behavior works,
record that confirmation and use it as the evidence. Keep the check open only
when it failed, was not run, or the owner identified a concrete gap. Record the
check and result in one compact fact; do not require a host receipt, a separate
summary artifact, or report-page readbacks for ordinary task completion.

## Close engineering separately from UX review

Close the engineering item when its practical check passes. Record
any remaining UX review as a separate owner decision with its own status. Do
not leave finished implementation marked active solely because an owner has
not yet reviewed the interface.

Owner UX approval happens against a usable implementation that performs its
purpose repeatably. The review should exercise the real user path, including
relevant refresh, retry, reopening, or repeat-action cases. A failed UX review
creates a concrete change request or remediation item; it does not retroactively
turn the earlier coding work into an approval prerequisite.

Use distinct status language:

- **Engineering complete:** implementation criteria passed with recorded
  checks.
- **UX review pending:** the implementation is ready for owner review; this
  does not mean coding is incomplete.
- **UX changes requested:** the owner identified a specific behavior or
  usability gap; create or update the affected engineering task and test it.
- **Blocked:** a named dependency prevents the remaining work, and no
  independent work in scope can proceed.

## Keep other owner decisions in their own lane

An SDE proposal is a review artifact for the owner's memorialization decision;
it is not authorization to begin coding and is not a substitute for the task's
engineering criteria. Codex prepares the pending proposal at the specified
task endpoint from that task's supported facts. The owner decides its
importance and disposition.

Cleanup, publication, deployment, and other actions with their own explicit
authorization requirements retain those requirements. A review gate for one
such action does not become a general approval dependency for unrelated coding
or local tests. Work directly on a live production site follows that site's
operational controls and the user's stated authorization; do not apply those
controls as ambient gates to ordinary repository development.

## Complete the SDE lifecycle

For a completed tracked task, prepare a pending SDE proposal from that task's
supported outcome facts. Include the supporting facts and concise category,
importance, and retrieval summary as recommendations. Keep the proposal
pending for the owner. After the owner approves it, transfer only the approved
facts to the pertinent persistence document, then read back that document and
verify the transferred content. That SDE decision authorizes automatic cleanup
of eligible transient artifacts scoped to the candidate after successful
readback and an internal comparison confirming the persisted entry contains
the same artifact-inventory and dependency-map fingerprints as the rechecked
transient set; do not add a second artifact-by-artifact approval. Build and
recheck the complete exact inventory internally, retain the review and cleanup
receipts, and leave held, changed, incomplete, out-of-scope, or failed items
pending. A pending proposal alone authorizes neither persistence nor cleanup.

## Communicate progress and completion

Report current findings, concrete changes, check results, and actual blockers.
Do not send routine narration about what Codex will or will not do. For
ordinary repository work, act on the request and report the result. Use
forward-looking operational instructions only while directly working on a
live production site, where they are needed to coordinate the operation.

When an intra-project decision is needed, ask the bounded question and
continue independent work. At completion, report the engineering result,
checks and outcomes, separate UX status, and any remaining owner decision.
Keep factual status separate from assumptions and unverified claims.

## Completion checklist

- The problem, scope, and observable success criteria are recorded.
- Required owner decisions were asked directly; routine implementation choices
  did not wait on approval.
- Agreed behavior is implemented in a usable state.
- Relevant regression, runtime, repeat-action, and performance checks passed
  where specified; missing checks remain visibly open.
- The engineering item is closed independently of pending UX review.
- UX review, SDE disposition, and operational authorization are tracked only
  where relevant, each as a separate owner decision.
