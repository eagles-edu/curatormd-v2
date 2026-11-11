# Curator V2 Codex integration

The Codex plugin turns ordinary requests into Curator V2 task intake. In a
workspace with `.curatormd-v2.toml`, type the request normally. Codex states the
problem and checkable success criteria, saves an active one-off goal, then
starts implementation. Route each request by its relationship to the active
plan and configured repository, using the full conversation and saved goal
criteria rather than requiring special wording:

- **Plan work:** When a request advances a plan shepherded by an existing goal,
  continue with the current plan item; the plan workflow already advances
  through its items. `AOTASK` means “add-on to current item.” Use `aotask:` to
  add a sub-item under the current goal/plan item, or to correct or change that
  item. Keep its existing goal ID; the ID is implicit in current task context.
  Do not create another goal or switch to another plan item for an AOTASK.
- **One-off work:** A normal work request with no matching plan starts or
  resumes its own top-level one-off goal. Use `ootask` or `ootask:` to
  explicitly force a distinct one-off. Keep its facts and SDE proposal on
  that goal; do not merge them into a plan item.
- **Unrelated repository work:** If the request is clearly outside the
  configured repository's scope, treat it as an aside whether the user says so
  naturally or prefixes it with `aatask:`. Do not create or update this
  project's goals, facts, lifecycle, or SDEs, and do not interrupt unrelated
  work in progress. Ask only when the target repository or relationship to the
  active plan is genuinely unclear.

Do not infer a plan match from repository or topic similarity alone. Do not
make the user learn these prefixes: natural language is sufficient, and the
prefixes are explicit routing controls when desired. Resume a deferred task
only when the user asks to continue it. The plugin does not add a
command-palette action or save raw prompt text.

The Codex plugin supplies the intake skill and its own local MCP connection.
The connection uses the active Codex workspace to select the configured V2
project. Read and lifecycle tool approval depends on the effective server's
Codex configuration; review and cleanup decisions remain unavailable to the
task tracker. It tracks compact task facts and prepares a pending owner-review
proposal from supported facts after each goal completes. Reviewing historical
completed goals is a separate workflow.
Use the read-only `evidence_capture` tool for owner-configured host checks, then
pass its returned reference unchanged to `fact_record`. It cannot accept
arbitrary commands or paths; no separate capture mode is required.
Normal wording drives the lifecycle: beginning/work starts or activates a
goal, hold/pause saves a checkpoint and defers it, resume/continue reactivates
it, and a clear completion statement or check-off records the endpoint and
calls `goal_finish` against the saved checks. Requests such as “finish the
plugin” or “complete this task” ask Codex to do work; they do not claim the
task is already complete. Each lifecycle call uses the current revision from
`goal_status`. Plan items and one-off tasks use the same flow. Missing evidence
keeps the task open.
The plugin bundle contains its prompt hook, tool guards, and stop hook. In the
Codex CLI, native user hooks must be installed separately because CLI hook
commands do not receive the plugin's `PLUGIN_ROOT` or `PLUGIN_DATA` variables.
The installer below registers all four V2 hooks and gives them a private state
directory under the Codex home. The prompt hook
recognizes common begin, hold, resume, next-item, and end wording for the
current turn, keeps only that normalized cue in private turn state, and injects
the matching action cue. Phrase matches are hints: Codex must follow the
meaning of the full request and conversation even when wording is new. Users
do not need to learn a command vocabulary. The stop hook uses the saved user cue
even when Codex's final message omits the transition. A pre-tool guard requires
a Curator-confirmed active goal and a saved intent/progress fact before shell commands
or edits in a configured project. It also requires a saved checkpoint fact
before `goal_finish` or `goal_defer`. After a finish request, Codex must read
`goal_status`; only a confirmed `complete` state closes the development task.
A post-tool hook tracks only accepted goal and fact IDs for the current turn.
After an accepted goal, fact, lifecycle, or SDE write, the Stop hook requires a
matching `goal_status` or `goal_report` readback before allowing the turn to
end. It confirms only that the report names the same goal; it stores no report
text.
The stop hook checks Codex's last response for a stated lifecycle transition.
When Codex
says it is starting, pausing, resuming, moving to the next plan item, or
finishing a task, the hook gives it one continuation for each missing lifecycle
step before ending the turn: confirm finish/hold status, or record the matching
start/progress/hold transition.
It ignores explicitly negated cues. The hooks inspect bounded text in memory
only; they do not save or repeat prompts or responses. They do nothing in
workspaces without `.curatormd-v2.toml`.
If any success check remains open or lacks current passing evidence, Codex keeps
the goal active and records the gap and next action. When `goal_finish` succeeds
and `goal_status` confirms `complete`, Codex calls `sde_assess` with supported
facts attached to that completed goal and leaves the proposal pending for your
review. It never assesses an active or reopened goal. It presents the facts and
any suggested category or importance as recommendations. You decide what is
memorialized, its importance, and its disposition. Curator does not approve,
reject, or codify for you. A standalone task ends at its own endpoint; activate
the next child only when the active task is a plan item and work is continuing.

When you explicitly ask Curator to record a verbally relayed SDE, Codex uses
`sde_record_user_report` on the current active goal with a concise normalized
report. Curator stores a `user_report` fact and creates a pending candidate
without requiring an artifact or evidence packet. Codex reads it back with
`sde_review_detail`; this does not complete the task or approve the candidate.
Tracking is
the default task workflow; no separate opt-in capture action is required.
When an `ootask` interrupts a plan child, Codex defers that child, completes the
one-off as a separate goal, creates its pending SDE proposal from that goal's
facts, confirms the candidate's goal ID and `pending_review` status with
`sde_review_detail`, presents its facts for your decision, then resumes the same
deferred child when you say to continue. It does not skip to a later child.
Beginning, pausing, and resuming work also get short cues that report the
matching lifecycle action.

On resume, Codex searches every goal-list page and compares the saved problem
and success checks before reusing a goal. If multiple goals could match, it
asks which task to resume; unrelated work is never attached to the latest goal.
It says `Resuming problem/task: <saved problem or title>. Open checks: <saved
checks>.` For a plan child, it includes the saved plan and child label or
number; it never invents an item number. It reuses the same `goal_id` across
turns and threads, while a plan item's child `goal_id` remains linked through
`parent_goal_id`. Facts from separated work periods stay in one task history.
At success, it reads all pages of the task report; for a plan, it also reads
each child's report and records one compact parent summary using the supporting
child IDs. This groups interrupted progress for aggregation and summarizing.
Before `goal_finish`, the completion hook requires a `change` fact beginning
`Task summary:` and a matching report readback that contains it. SDE preparation
then follows the confirmed finish.
This groups separated turns under the same goal and makes the full history
available for aggregation before cleanup.

Cleanup follows that summary and your SDE decision. Codex shows the exact
inventory before cleanup. It deletes only transient artifacts you approve and
keeps the summary and audit receipts. Routine facts leave active history only
after you approve the exact `fact_compaction_propose` inventory; the reviewed
archive remains recoverable. Finishing a task alone does not approve cleanup.

Desktop plugin installation uses the bundled hooks; Codex CLI uses the native
user-hook installer below.

The plugin's `mcp.json` declares `codex-intake` and uses an owner-managed host
map to select a database by exact project ID. The user-level registration below
uses the same server name without a fixed working directory; Codex gives it
precedence and starts it in the thread's working directory. The server finds
that workspace's `.curatormd-v2.toml`, selects only its exact database entry,
then enforces its repository/config fingerprints and project grants. A missing
map entry fails closed; it never falls back to another project's database.

The Codex route enables the separate `--allow-purge-retry` ceiling so its
attended recovery action can retry cleanup. This flag does not grant access:
the active local UID must also hold the exact project's durable `purge_retry`
grant, and Curator still retries only already-reviewed, canonically persisted
cleanup manifests. The grant is separate from `read`, `write`, and `review`.

Create `~/.config/curatormd-v2/database-bindings.json` outside the consumer
repositories and restrict it to the owner (`chmod 600`). Its exact schema is:

```json
{
  "schema_version": 1,
  "projects": {
    "curatormd-v2-dev-alpha": "/absolute/path/to/curator/global.sqlite3",
    "example-project": "/absolute/path/to/example/global.sqlite3"
  }
}
```

Use the same exact project-to-database mappings as the host's other Curator
integrations. The map and every database must be owner-controlled and private.
The installer refuses to register the per-project route when the map file is
missing or not private. The legacy `--database` option remains available for an
explicit single-project server.

Use the host map as the source of truth for VS Code User settings. From this
checkout, run the coordinator with the project's Python environment:

```sh
.venv/bin/python -m curatormd_v2.bindings_coordinator
.venv/bin/python -m curatormd_v2.bindings_coordinator --apply
```

The first command only checks for drift and exits with status 1 when the two
maps differ. The second adds missing entries to `curatormdV2.databaseBindings`.
The default settings path is for Linux and must already exist. Save the VS Code
User settings buffer first and avoid editing settings until the command finishes.
The coordinator preserves other settings and their comments and rejects a file
changed before its final replacement check or an invalid map. Its replacement
is not atomic with respect to other writers, so an edit made after that check
can be overwritten. It does not touch project registrations or grants. If an
existing VS Code entry differs or has no map entry, review it before allowing
replacement and removal with `--apply --replace-conflicts`. Comments inside
the binding object require a manual edit. Use `--map` and `--settings` for
other host paths. The coordinator exits with status 2 on an error.

The server selects `~/.config/curatormd-v2/<project-id>-evidence.json` for the
active project when that owner-managed file exists. An explicit
`--evidence-config` overrides discovery. A missing file leaves evidence capture
unconfigured; an invalid or mismatched file prevents the server from starting.

Before trusting a work-blocking hook, check `codex mcp list` and confirm that a
fresh session can call `codex-intake` for the intended project. If its tools are
unavailable in that session, disable the Curator V2 PreToolUse hook with
`/hooks`, repair the connection, and reload before trusting it again.

If the Curator MCP transport closes, save your work, then reload the VS Code
window (Codex host) or start a fresh Codex session. Do not re-enroll the project
or recreate its grants; transport recovery is handled by the Codex host.

The prompt hook hashes Codex's prompt-turn ID and gives the model that stable
`goal_start.event_id`; retries of that same turn can therefore replay the same
goal event without storing the prompt or raw turn ID. The MCP server displays
its server-verified repository and config fingerprints as audit metadata.
These displayed values do not grant access.

## Local installation

The plugin is listed in `../.agents/plugins/marketplace.json`. Add the local
marketplace and install `curator-v2` with the Codex plugin manager. Install the
`curatormd-v2-codex-mcp` entry point on Codex's `PATH`, or set the absolute
`CURATOR_V2_CODEX_MCP` executable path in the Codex process environment. The
checkout's `.venv` is also used when the launcher itself runs from that
checkout. A cached plugin cannot infer the checkout from its own location.
Install the owner-level server registration from this checkout:

```bash
python3 integrations/codex-plugin/bin/install_user_mcp.py
```

It refuses to replace a different user registration named `codex-intake`.
By default, it registers the per-project database map described above; set
`CURATOR_V2_DATABASE` only when intentionally installing an explicit
single-database server.
The user-level registration has its own tool approval settings: plugin-scoped
settings do not automatically configure that registration. Review the effective
`mcp_servers.codex-intake` settings and copy any intended individual tool rules
there. Keep the default at `prompt` if other tools require individual approval;
do not grant task tracking tools authority to make review or cleanup decisions.
Confirm the server can connect for the intended project before installing or
trusting work-blocking hooks. For Codex CLI, install the native hooks with:

```bash
python3 integrations/codex-plugin/bin/install_user_hook.py
```

This adds or updates only Curator V2's four hook handlers in
`~/.codex/hooks.json`, preserves unrelated handlers, and stores bounded turn
markers in the private `~/.codex/curator-v2-data` directory. It does not store
submitted prompts or responses.

## Activate Codex CLI hooks

After installation or a hook update, activate the current definitions in the
Codex CLI:

1. From the intended workspace, confirm that the `codex-intake` MCP server is
   available with `codex mcp list`.
2. Start `codex` in that workspace and enter `/hooks`.
3. Review and trust the four Curator V2 handlers: `UserPromptSubmit`,
   `PreToolUse`, `PostToolUse`, and `Stop`. If Codex marks a handler as
   modified, it skips that definition until you review and trust the current
   version. Plugin installation does not trust native CLI hooks for you.
4. Start a fresh thread in the same workspace. Send an ordinary nontrivial
   request and confirm Curator records an active goal and intent before local
   commands or edits are allowed.

Use the packaged Codex CLI for hook review. Install it with
`npm install --global @openai/codex@latest` if `codex` is unavailable; the VS
Code extension's bundled executable may not be a complete standalone CLI.

Each workspace must have its own `.curatormd-v2.toml` and matching exact
project grant in the ledger. The server binds only the active workspace's
config; it does not create a project or grant access. Keep the marketplace and
Codex user config separate from consumer repositories.
