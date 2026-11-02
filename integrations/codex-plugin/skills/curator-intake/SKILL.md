---
name: curator-intake
description: Use Curator V2 to track normal Codex work requests, plan-item lifecycle, evidence, and human-reviewed SDE proposals.
---

# Curator V2 intake

Curator task tracking is the default workflow for non-trivial development,
inspection, debugging, and research. It is not an optional capture mode. Before
analysis, commands, or edits, state the problem and observable success checks,
read existing goals, and create or reuse the matching active task. For a plan,
create a planned parent and bounded planned child goals; activate each child
when work moves to it. Do not create goals for simple factual or formatting
questions.

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
  project goals have been checked. Match the saved problem and success checks,
  not just a similar title. Reuse one clear active match; for a resume, also
  consider deferred, planned, or blocked matches. If multiple goals could be
  the same task, ask which one. Create only when no clear match exists. Do not
  attach unrelated work to the most recent goal. For a new task the user has
  asked you to do now, set `initial_status="active"` when calling `goal_start`.
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
  Verify each success check against evidence, record the result, call
  `goal_finish` only when all checks pass, then activate the next planned child
  with `goal_activate`. Before lifecycle calls, read `goal_status` and pass its
  current lifecycle revision. If a check is missing, keep the item open and say
  what remains; do not silently skip to the next item.
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
  does not claim the task is already complete. At a reported endpoint, record
  the result, read `goal_status`, and, if its success checks pass, aggregate
  the task history and save/read back the `Task summary:` fact before calling
  `goal_finish` with its current lifecycle revision.
  Never close unrelated goals or claim a criterion passed without evidence. A
  one-off task ends at its own endpoint; activate another child only when the
  task belongs to a plan and the user is continuing to that next item.

Apply the same lifecycle to each plan child and each one-off task, whether it is
inside or outside a plan. Record compact,
typed facts at task start, after changes, after checks, on hold, and before the
outcome: intent, changed components, verification and result, open checks, hold
reason/next action, and outcome. `goal_report` accepts 1–16 facts per page; use
`fact_offset` to continue. Never save raw prompts, transcripts, imports, or
scratch content. Claim facts saved only after the MCP write succeeds. If Curator
is unavailable, report that and do not claim the work was recorded.

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
for retrying one start event; never use it as the task ID. Do not start a
replacement goal just because work was interrupted. For a plan item, retain
its child `goal_id`; its saved
`parent_goal_id` groups it under the plan. At a successful plan endpoint, page
through the parent’s child list and each child’s `goal_report` so the summary
uses the whole plan history, not only the latest turn. Summarize one-off and
child histories from all `goal_report` pages before calling `goal_finish`.
Since SDE facts must belong to the assessed goal, add a compact
parent-level `change` summary that points to supporting child goal/fact IDs
before assessing the parent; start its bullet with `Task summary:` so the
completion hook can require a readback. For a one-off or child, summarize all
pages under that same goal ID; never submit child fact IDs in the parent’s SDE proposal.
Keep summaries concise and factual.

After the summary and the user's SDE decision, show the exact cleanup
inventory. Delete only transient artifacts the user approves; keep the
`Task summary:` fact and audit receipts. Routine ledger facts leave active
history only through
`fact_compaction_propose` followed by exact owner approval with
`fact_compaction_approve`. Purge transient artifacts only through the
owner-approved exact-inventory purge flow. Preserve the compact outcome summary
and audit receipts; a task endpoint alone does not approve cleanup. After
approval, remove only the exact listed transient artifacts and verify the
purge receipt; do not describe archived facts as deleted because their reviewed
archive remains recoverable.

For an evidence reference, include `evidence_kind`, `locator`, `sha256` (64
lowercase hexadecimal characters), and `outcome` exactly `passed`, `failed`, or
`observed`. `occurrence_id` is optional. Never send a partial evidence object.
For configured host sources, use `evidence_capture` with the exact goal,
criterion, evidence kind, and configured locator, then pass its returned fields
unchanged to `fact_record`. It can use only sources configured by the owner; it
does not accept caller-supplied commands, executables, or arbitrary paths. A
missing capture leaves the evidence check open.
If an observation has no stable, independently checkable source, record it as
research without evidence and leave the success check unverified.

For a repository test, capture a receipt with the owner-configured
`curatormd-v2-evidence repository-test` command and pass its returned evidence
fields unchanged to `fact_record`. Pin it to the exact commit being checked. A
raw test log, command result, or hash by itself is not a verification
attestation. Never construct an evidence reference from command output or a
local hash. Use only the exact reference returned by `evidence_capture` or the
configured repository-test receipt. If capture returns no reference, or the
checked code is only in an uncommitted worktree with no configured runner,
record a compact open gate or research fact without evidence and leave
verification open.

## Curate historical SDEs separately from development

Task evidence and lifecycle tracking are part of each tracked task; do not ask
the user to enable capture. A hold records a checkpoint and pauses work; it does
not discard facts. Resuming continues from that point.

Curator tracks development while the goal is active. If any required check is
open or lacks current passing evidence, record the gap and next action, keep the
goal active, and continue development. Do not call `sde_assess` or create an
SDE review candidate for active, deferred, blocked, or otherwise incomplete
work. SDE curation is a separate task over historical work, not a step in
development or goal completion. Do not create an SDE proposal automatically
when `goal_finish` succeeds. When historical curation is requested, select a
goal whose `goal_status` is `complete`, summarize its supported facts and
current passing evidence, then call `sde_assess` for the user's review. Never
assess an active, reopened, deferred, blocked, or otherwise incomplete goal.
Present facts and any suggested category or
importance as recommendations only. The user decides what is memorialized,
its importance, and whether it is approved or rejected. `sde_assess` creates a
pending proposal only; it never approves or codifies knowledge. Do not invent
evidence or mark an unsupported fact as verified.

Use concise cues that report actual transitions:

- Beginning work: “Beginning task tracking.”
- Holding work: “Pausing task tracking.”
- Resuming work: “Resuming task tracking.”
- After `goal_finish` is confirmed: report task completion and end the
  development workflow. Do not automatically start historical SDE curation.
- When the user requests historical curation for a completed goal, prepare and
  present its pending proposal for review.
- When checks remain open: state the specific gap and next development action;
  keep the goal active and do not create an SDE candidate.

Never imply a tool write succeeded until the corresponding Curator tool
returns success. After an accepted goal or fact write, read the same goal with
`goal_status` or `goal_report` and confirm the saved criteria/facts before
ending the turn. Task completion is not SDE approval.
