# Proposed Curator V2 SDE review document

This document records the approved review format and behavior. The example is
fictional. Source code now generates an editable review document, binds the
decision to an immutable receipt, and journals writes to selected configured
destinations. Accepted canonical entries include recorded goal start and
successful-completion times in +07; absent legacy timestamps remain unknown.
The current worktree has not been proof-tested; projection, recovery, and
persistence behavior still need the owner's tests.

## Purpose

Each significant development event (SDE) describes a plan task, its outcome,
and knowledge the owner may choose to retain. The review document shows the
original proposed entry and a separate editable copy. The owner selects
**Accept** or **Reject** for each candidate.

## Example: `pending-review.md`

````markdown
# Pending SDE reviews

<!-- VS Code renders Accept and Reject CodeLens actions above this candidate. -->

## SDE #042 — Preserve project binding during task intake

**Started:** 2026-11-01 09:20 +07
**Successfully completed:** 2026-11-01 11:45 +07
**Plan task:** Bind each Codex task to the correct Curator V2 project.

### Proposed entry

**Suggested significance:** 4 / 5
**Suggested documents:**

- `persistence/HISTORY.md`
- `persistence/LESSONS-LEARNED.md`

**Problem / plan task**

- Tasks could be associated with the wrong project when the launcher started
  outside the active workspace.

**Completed successfully**

- The launcher resolves the active workspace before selecting a project.
- The project configuration and access grant are checked before task intake.

**Difficulties encountered**

- The editor started the launcher from a shared plugin directory.
- That directory did not identify the workspace containing the request.

**Plan changes required**

- Added a workspace-bound server registration to the integration plan.

**Lessons learned**

- A launcher's working directory is not always the active project directory.
- Check the project binding before creating or updating a task.

**Future utility**

- Use the same binding check when adding another editor or agent integration.

### Your editable copy

Edit the fields below, then choose **Accept** or **Reject**.

<!-- curatormd-actions:042 -->
<!-- curatormd-decision:042:start -->
```json
{
  "title": "Preserve project binding during task intake",
  "significance": 4,
  "documents": [
    "persistence/HISTORY.md",
    "persistence/LESSONS-LEARNED.md"
  ],
  "problem": "Tasks could be associated with the wrong project when the launcher started outside the active workspace.",
  "completed": [
    "Resolved the active workspace before selecting a project.",
    "Checked the project configuration and access grant before task intake."
  ],
  "difficulties": [
    "The editor started the launcher from a shared plugin directory."
  ],
  "plan_changes": [
    "Added a workspace-bound server registration."
  ],
  "lessons": [
    "Do not assume a launcher's working directory is the active project."
  ],
  "future_utility": "Apply the binding check to future editor and agent integrations."
}
```
<!-- curatormd-decision:042:end -->

The significance score helps inform later compression, summarization,
archiving, or culling. It does not itself authorize deletion or determine
the outcome of a future review.

---
````

## Requirements for the proposed flow

- Render the main document text in `#FBFFFF`; render headings and bold text in
  `#6DAAFF`.
- Show the SDE ID, proposed title, task start and successful completion times
  in UTC+07:00. Do not invent a time: show it as unknown when unsupported, and
  do not label a task successfully completed without current passing proof.
- Show a 0–5 significance rating for the SDE's contribution to the plan's
  successful completion. Show a starting recommendation based on the candidate
  type, clearly label it as a recommendation, and let the owner change it. A
  rating of 5 requires extra human confirmation.
- Let the owner select one or more approved persistence documents when
  appropriate. Preserve a clear purpose for each selected entry and avoid
  accidental duplicate writes when a decision is retried.
- Keep the original proposal available for comparison with the editable copy.
  Preserve saved edits on refresh and do not overwrite unsaved editor changes.
- Present the problem, successful work, difficulties, plan changes, and
  lessons in clear, concrete language. Include future utility when supported.
  Keep unsupported categories visible as not recorded; do not fill them with
  guesses. Mark proposed work as pending when current passing evidence has not
  been rechecked by the attended reviewer.
- Provide **Accept** and **Reject** actions immediately above each candidate
  in VS Code's Markdown editor. Each opens the attended review flow and never
  records a decision directly.
- Show evidence and the complete exact cleanup inventory before the owner
  confirms a decision. Approval requires current passing evidence. Record
  the decision and rationale in an auditable receipt; retain the existing
  exact-inventory authorization and cleanup safeguards.
- Use significance as information for a later human-reviewed decision about
  compression, summarization, archiving, or culling. A rating is not permission
  to delete or alter retained knowledge.
- Keep pending proposals separate from project health. A pending approval
  alone does not make the project degraded.
