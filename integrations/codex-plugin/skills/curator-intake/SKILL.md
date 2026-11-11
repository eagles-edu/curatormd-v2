---
name: curator-intake
description: Use Curator V2 to track normal Codex work requests, plan-item lifecycle, evidence, and human-reviewed SDE proposals.
---

# Curator V2 intake

Codex uses its local account binding; it does not have a Hermes session. Do not
call `hermes_goal_bind` from Codex. A real Hermes host binds its own session
with host-injected metadata, never agent-supplied profile or session values.

For project planning and implementation sequencing, follow the repository's
[Codex Execution and Approval SOP](../../../../docs/codex-execution-and-approval-sop.md).
In particular, owner UX approval reviews working, repeatable behavior after
engineering checks; it is not a prerequisite to coding or closing passed
engineering criteria. Ask the owner about material product decisions, resolve
routine implementation choices within agreed scope, and continue work that
does not depend on an unanswered decision.

Curator task tracking is the default workflow for development, including quick
formatting work, and for non-trivial
inspection, debugging, and research. It is not an optional capture mode. Before
analysis, commands, or edits, state the problem and observable success checks,
read existing goals, and create or reuse the matching active task. For a plan,
create a planned parent and bounded planned child goals; activate each child
when work moves to it. Give each task one practical success check; split it
only when the request has independent outcomes. Do not create goals for simple
factual or formatting questions.

## Follow task language through each item

Treat ordinary wording as lifecycle controls. Follow both the user's words and
your own stated transitions; do not require a command, palette action, or
separate capture opt-in. Recognize the meaning of how the user says to start,
finish, move between items, or pause, including new wording that is not in the
hook's phrase examples. The hook's phrase match is a hint, not the authority:
use the full request and conversation to determine the transition. Keep only a
normalized transition category in hook state; never retain the user's exact
wording to build a phrase library. If meaning is genuinely ambiguous, ask a
short clarification while preserving task state.

- Beginning language (“start”, “begin”, “work on”, “fix”, “let's tackle”, or a
  direct request) starts the matching one-off task or activates the matching
  plan item. Before creating anything, page through `goal_list_page` until all
  project goals have been checked. Use `limit=10` and reduce each
  result to its `goal_id`, status, saved problem, success checks, and parent ID
  before comparing candidates; never create from a truncated or partially
  reviewed list. Match the saved problem and success checks, not just a similar
  title, repository, or topic. Reuse one clear same-task
  match; for a resume, also
  consider deferred, planned, or blocked matches. If multiple goals could be
  the same task, ask which one. Create only when no clear match exists. Do not
  attach unrelated work to the most recent goal. For a new task the user has
  asked you to do now, set `initial_status="active"` when calling `goal_start`.
  If the request is a distinct bounded task clearly within an active broader
  goal, create a separate active child with `parent_goal_id` set to that
  parent. Keep the child's criteria, facts, checks, and lifecycle separate;
  the parent link records scope and provenance. If the request is unrelated to
  the active item, create a top-level one-off with no parent. Reuse the active
  goal itself only when the request advances its saved criteria. Never append
  a distinct task's facts to a broader goal just because both concern the same
  repository. If the parent relationship is unclear, ask.
  The owner may prefix a request with `ootask` or `ootask:` to require a
  distinct one-off goal with its own criteria, facts, checks, and lifecycle.
  If it is unrelated to an active item, keep it top-level; if it is a distinct
  bounded task within a named parent or child, link the new goal with
  `parent_goal_id`. The owner
  may use `aotask <parent-or-child>:` to add progress to that existing goal's
  scope and saved criteria, keeping the same goal ID. The hook retains only the
  normalized prefix category and blocks `goal_start` for `aotask`.
  `aatask:` means an aside unrelated to this repository: handle it without
  creating or changing the current project's goals, facts, lifecycle, or SDEs.
  Leave any existing task as it is and return to it only when the user asks.
  Save intent and checks, and
  say “Beginning task tracking.” For each newly started
  goal, state the same compact kickoff in this exact form: `Problem: <what is
  wrong or needs doing>. Success: <observable checks that show it is done>.`
  A plan gets this statement for its parent and again for each child when that
  child starts. A one-off gets it once, whether it is inside or outside a plan.
  Derive the wording from the saved goal problem and criteria. On a retry or
  resume, reuse the same goal and wording; do not create a duplicate goal or
  repeat the kickoff unless the user asks or the saved statement needs correction.
- Progress language records changed facts and checks as work proceeds. Saying
  “moving to the next item”, “check this off”, “mark this complete”, “done with
  this item”, or similar means close out the current item before moving on.
  Record the observed result and available checks, call `goal_finish` when the
  task is done, then activate the next planned child
  with `goal_activate`. Every completed task must get its own pending SDE
  proposal before another plan item is activated. Call `sde_review_detail` for
  that candidate and confirm its goal ID and `pending_review` status. Present
  its facts as recommendations; the user decides importance and disposition.
  Before lifecycle calls, read
  `goal_status` and pass its
  current lifecycle revision. If the outcome is uncertain, ask for guidance
  and say what remains.
- Holding language (“pause”, “hold”, “put it aside”, “not now”, “park this”, or
  “shelve it”) records current facts, the reason, and the next action, then
  calls `goal_defer`. Read `goal_status` first and pass its current lifecycle
  revision. Say “Pausing task tracking.”
- Resuming language (“resume”, “continue”, “back to this”, “pick it back up”)
  finds the exact existing goal across every goal-list page and reads its
  checkpoint and `goal_status`;
  never call `goal_start` just because the turn or thread changed. Call
  `goal_activate` with its
  current lifecycle revision only when the goal is planned, deferred, or its
  blocker is resolved. If it is already active, continue without another
  transition and record an intent or progress fact before local work; do not
  call `goal_start` or `goal_activate` for the active goal. A terminal goal
  cannot be resumed. Announce the saved work, not
  just the transition: `Resuming problem/task: <saved problem or title>. Open
  checks: <checks still open>.` For a plan child, include the saved plan title
  and child label when present, such as `Resuming problem/task: <plan>, item
  3e — <child title>. Open checks:
  <checks still open>.` Use the exact problem/title and open criteria from
  `goal_status`; never invent a plan number. Say this once for the resume, not
  again on retries. Say “Resuming task tracking.”
- Ending language reports that the task has reached its endpoint (“this is
  done”, “we finished this item”, “check it off”, “mark it complete”, “close
  out this item”, or similar). A request to do the remaining work (“finish the
  plugin”, “complete this task”, “close the bug”) begins or continues work; it
  does not by itself claim the task is already complete. When the requested
  result is observed or the owner confirms it, record the result and finish
  without waiting for another instruction or automated evidence. A user moving
  on after seeing the result can indicate completion. Record available checks
  honestly; never label an unverified claim as verified. If unsure whether the
  result satisfies the request, ask the owner for guidance. Do not close
  unrelated goals. A
  one-off task ends at its own endpoint; activate another child only when the
  task belongs to a plan and the user is continuing to that next item.
  When an `ootask` interrupts a plan child, checkpoint and defer that exact
  child before starting the distinct one-off. On OOTASK completion, create a
  pending SDE proposal using only facts from the OOTASK, confirm the candidate
  with `sde_review_detail`, then reactivate the exact deferred child when the
  user says to continue. Do not skip to a later child or attach OOTASK facts to
  the resumed child.

Apply the same lifecycle to each plan child and each one-off task, whether it is
inside or outside a plan. Record compact typed facts at task start, after
changes, after checks, on hold, and at the outcome. A single fact can state
what changed and the test/lint result or the owner's confirmation. Never save
raw prompts, transcripts, imports, or scratch content. Claim facts saved only
after the MCP write succeeds. If Curator is unavailable, report that and do
not claim the work was recorded.

If Codex reports that the Curator MCP transport is closed, tell the user:
“Curator MCP transport closed. Save your work, then reload the VS Code window
(Codex host) or start a fresh Codex session. Do not re-enroll the project or
recreate its grants.”
This is a Codex host connection recovery; it does not indicate that the project
binding or grants need to change.

Keep interrupted work together: the existing `goal_id` is the continuity key
for all facts and checks about that task, even when records are separated by
other work, turns, pauses, or new threads. Append later facts to that same goal
so the full history is one retrievable group. The prompt-turn event ID is only
for retrying one `goal_start` event; never reuse it for a later operation or
use it as the task ID. Give every later `fact_record`, lifecycle transition,
and SDE operation its own fresh event ID. Reuse an operation's ID only when
retrying that same operation with the same payload. Do not start a replacement
goal just because work was interrupted. For a plan item, retain
its child `goal_id`; its saved `parent_goal_id` groups it under the plan. Build
the completed task's proposal summary from its supported facts. For a parent
plan, include concise references to completed child outcomes; never submit
child fact IDs as a parent's SDE facts. Do not create or read back a separate
`Task summary:` fact before finishing a task.

After the owner approves an SDE, transfer only the approved facts to the
pertinent persistence document and read it back to verify the saved content.
Then automatically clear eligible transient artifacts scoped to that candidate
after successful persistence readback and an internal comparison confirms the
saved SDE entry contains the same artifact-inventory and dependency-map
fingerprints as the rechecked transient set. The SDE decision is the single
owner approval; do not ask for a separate deletion approval. Build and recheck
the complete exact inventory internally, keep review and cleanup receipts, and
leave held, changed, incomplete, out-of-scope, or failed items pending. A task
endpoint or pending proposal alone does not authorize cleanup.

Record observed results and any actual passing local test/lint result or owner
confirmation. `evidence_capture` may be used
when a configured source is available, but it is not required for ordinary
repository completion. Never invent a result or store raw prompts, transcripts,
imports, or scratch content.

Use a configured evidence source when it is already available. Ordinary task
completion does not depend on an immutable-commit receipt or a test. Record
the result as a compact fact; do not invent evidence references or hashes.

## Prepare owner-reviewed SDE proposals at task endpoints

When the owner explicitly says to record a verbally relayed SDE, use
`sde_record_user_report` on the current active goal with a compact normalized
single-line summary and a fresh operation event ID. This route writes a
`user_report` fact and creates a pending SDE candidate without asking for an
artifact or evidence packet. Read the candidate back with
`sde_review_detail`; leave it pending for the owner's decision. Do not turn a
verbal report into task-completion evidence, infer a fact beyond what the
owner relayed, or save the raw chat.

Task evidence and lifecycle tracking are part of each tracked task; do not ask
the user to enable capture. A hold records a checkpoint and pauses work; it does
not discard facts. Resuming continues from that point.

Curator tracks development while the goal is active. When the result is
uncertain, ask for guidance and report what is known. Missing automated
evidence alone does not block recording a result or an SDE proposal. Propose
potentially useful facts for owner review, including during active work. After
`goal_finish` succeeds
and `goal_status` confirms complete, use only supported facts belonging to that
completed goal to prepare a pending proposal. For a child one-off, assess its
own facts even while its parent remains active. Never submit a parent's or
sibling's facts as the one-off's proposal. Present supporting facts and any
suggested category or importance as recommendations only. The user decides
what is memorialized, its importance, and whether it is approved or rejected.
`sde_assess` creates a pending proposal only; it never approves or codifies
knowledge. Do not invent evidence or mark an unsupported fact as verified. If
the proposal call fails, report the failure and keep that gate open.

Use concise cues that report actual transitions:

- Beginning work: “Beginning task tracking.”
- Holding work: “Pausing task tracking.”
- Resuming work: “Resuming task tracking.”
- After `goal_finish` is confirmed: prepare a pending proposal from supported
  facts attached to that completed goal. For an interrupting OOTASK, confirm
  the candidate with `sde_review_detail`, then resume the exact deferred plan
  item when the user says to continue. Leave the proposal pending for owner
  review.
- When the result is uncertain: state what is known and ask for guidance;
  missing automated evidence alone does not prevent a pending proposal.

Never imply a tool write succeeded until the corresponding Curator tool
returns success. After an accepted goal or fact write, read the same goal with
`goal_status` or `goal_report` and confirm the saved criteria/facts before
ending the turn. Task completion is not SDE approval.
