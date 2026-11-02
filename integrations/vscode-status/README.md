# CuratorMD V2 VS Code dashboard

The V2-owned extension places its `CuratorMD V2` status item immediately to
the right of Git Graph. It is blue when SDE reviews are waiting; clicking it
opens `.curatormd-v2/sde-proposals/pending-review.md`. With no pending reviews,
it shows health in blue before a read, yellow when health is unknown, green
when project health is healthy, and red when project health is degraded.
Pending SDE approvals do not degrade project health. Each
candidate has Accept and Reject actions directly in the document that open
the attended reviewer in a terminal. The selected action is
only a hint: the reviewer still sees the full packet and exact inventory,
re-enters the decision, supplies a rationale, and types the bound confirmation
before any decision or cleanup is recorded.
Purple marks other review work in dashboard panels.
The tooltip shows the installed extension version, health, the pending review
count or its unavailable state, and a short explanation of the active color.
When a health read fails, it gives a fixed next step for the known failure
instead of showing exception text or file paths.
If the Curator MCP process exits before replying, VS Code shows a modal:
save your work, then reload the VS Code window or start a fresh Codex session.
The `Reload Window` action reloads VS Code; the message explicitly says not
to re-enroll the project or recreate its grants.
The dashboard's Open gates and Operational alerts rows show that same plain
language reason, rather than an internal code such as
`health_read_unavailable`.
For a same-project health result it also lists up to 12 plain-language gate
descriptions, so yellow and red states point to the reported cause without
exposing arbitrary server text. Pending SDE approvals appear in the review
action and operational queue. Unknown or
unavailable health is yellow; blue means a health read has not been attempted.
Cross-project or unavailable health is shown as unknown. If the workspace has
no `.curatormd-v2.toml`, the extension explains
that a configured consumer project is required before starting the launcher.
For configured consumer workspaces, health and the review queue are read when
the extension activates and when the workspace folder changes, so the status
bar does not wait for the dashboard to be opened.
The dashboard reads Hermes readiness and Curator queue counts independently.
It gets readiness from Hermes and uses Curator's read-only
`project_queue_snapshot` MCP tool for queue counts. Queue counts are accepted
only from a fresh, complete SQLite observation for the configured project;
host dependency warnings do not hide those counts.
Each panel shows its own read time and a plain-language error when unavailable.
Overlapping feed refreshes share one read. After three identical failures for
one feed, its automatic checks pause until the dashboard is opened, a manual
refresh is requested, or a workspace or Curator setting changes. Opening the
dashboard performs one fresh attempt. The paused panel keeps showing that feed's
last source-specific failure and check time. Generated inbox and proposal views are
replaced only when their saved data changes; their check time remains in the
dashboard.
The extension also creates `.curatormd-v2/` with three working areas:
`inbox/status.json` is a count-only view of SQLite event receipts;
`sde-proposals/pending.json` contains pending proposal summaries and
`sde-proposals/pending-review.md` presents them with review actions;
`side-buffer/` is the configured
temporary artifact staging root. The two JSON files are rewritten from an
authorized database read. They are views, not canonical records or approval
receipts. SQLite remains authoritative. The extension refuses symlinked state
directories and writes these local views with owner-only permissions.
Each candidate includes a readable proposed SDE entry and a separate editable
copy. The copy starts with a materiality-based significance recommendation;
the owner may set any score from 0 to 5 for future compression, summarization,
archiving, and culling decisions, and select multiple configured destinations.
A score of 5 requires extra confirmation. The proposal separates the plan task,
evidence-checked work, difficulties, plan changes, lessons, and future utility;
unsupported details are marked as not recorded.
Accept and Reject open the attended reviewer with the saved copy. The reviewer
displays the draft and exact inventory and requires typed confirmation; the
edited review and projection path still needs proof.
Review-document refresh pauses while the document has unsaved edits. Saved
editable blocks for still-pending candidates are carried forward; changes to
generated text, missing markers, and drafts for candidates no longer in the
queue pause refresh for manual reconciliation. Existing documents without a
recognized checksum are also preserved. Saving edits alone does not submit a
decision. Review actions refuse a stale document or changes outside its editable
blocks. Cleanup remains pending for edited reviews.
The button opens a project-scoped dashboard for the first workspace folder.
Task intake happens through the normal Codex request; there is no VS Code
palette command for starting a task. The V2-owned Codex plugin's prompt hook
supplies the intake workflow, and its local-UID MCP server saves the problem
and checkable success criteria as a one-off goal before implementation. A plan
request creates a planned parent with child tasks. The dashboard remains for
reviewing project state and SDE decisions. Task text is stored as problem and
criteria, not as a chat transcript.
Goal, health, activity,
storage, and SDE queue reads are read-only. It shows project health, exact
goal-state totals, event/review/purge/expiry queue counts, storage estimates,
paged goal cards, and one
bounded goal report page at a time. Health, activity, storage, and goal
totals are separate authorized reads and may reflect different observation
times. Retained activity is not a capture-completeness measure. Project logical
record bytes and retained event payload bytes are separate from the shared
SQLite database/WAL file sizes. It also reports the staging byte scan,
completeness, and warning-only byte threshold; writes remain allowed above the
threshold. The status item and dashboard warn when the shared SQLite main file
and WAL together exceed 250 MiB; the warning does not block writes or control
SQLite checkpointing. Model/token use is not reported. Refreshing or changing pages
replaces the old view, so pages from separate report reads are never combined.

Configure these **User** settings in VS Code:

- `curatormdV2.databasePath`: absolute path to the Curator V2 SQLite database.
- `curatormdV2.databaseBindings`: optional owner-managed object mapping exact
  Curator project IDs to absolute SQLite paths. A matching project entry takes
  priority over `databasePath`, so different workspaces can use separate
  ledgers. For example,
  `{"curatormd-v2-dev-alpha":"/home/eaglesvn/.local/share/curatormd-v2-alpha/global.sqlite3"}`.
  The extension reads the project ID from the workspace's `.curatormd-v2.toml`
  before starting Curator and rejects a database response bound to another ID.
- `curatormdV2.evidenceConfigBindings`: optional owner-managed map from exact
  project IDs to their host evidence files. An exact empty string deliberately
  disables the shared `evidenceConfig` fallback for that project, for example
  when another workspace uses a host file bound to a different project.
- `curatormdV2.profileId`: host-selected profile routing label.
- `curatormdV2.hermesProfileBindings`: owner-managed object mapping each exact
  Curator project ID to the Hermes profile that serves that project. For this
  machine, use `{"curatormd-v2-dev-alpha":"curatormd-v2-dev-alpha","vhost-manager-alpha":"renew-ssl-coding"}`.
  Missing mappings leave Hermes health unknown while Curator queue counts remain
  available. Keep this application-scoped in User settings.
- `curatormdV2.hermesCommand`: absolute path or PATH command for a Hermes CLI
  that supports the machine-readable Curator health probe; defaults to `hermes`.
- `curatormdV2.serverCommand`: optional local `curatormd-v2-mcp` path or PATH
  command; defaults to `curatormd-v2-mcp`.
- `curatormdV2.reviewCommand`: attended local SDE review CLI path or PATH
  command; defaults beside an absolute `serverCommand`, otherwise
  `curatormd-v2-review` on PATH.
- `curatormdV2.evidenceConfig`: optional absolute path to the owner-only host
  evidence JSON file. The extension passes this path to each local Curator
  launcher. Keep the file outside the repository with mode `0600`; the backend
  validates its owner, permissions, project binding, and location. Workspace
  settings cannot override this path. If unset, evidence verification remains
  reject-all unless the host launcher supplies its own verifier.

The extension rejects workspace-level overrides for the Hermes command and
profile bindings, Curator launcher, database path and database bindings,
profile, review CLI, host evidence config, and evidence config bindings. It starts a local stdio MCP process
for each request, pinned to the open repository's `.curatormd-v2.toml` project.
Read requests stay read-only; only the attended, confirmed reopen action asks
for write scope. The
Python host derives the
authorization subject from the kernel UID and checks the exact project read
grant on every request. The profile ID is routing context, not an identity or
credential. Missing settings, a missing grant, or an unavailable launcher leave
the dashboard in an explicit error state.

The dashboard puts pending SDE review before the goal refresh and paging
controls. Health, retained activity, operational queues, and storage appear in
four compact panels with color-coded metric tables, bold column headers, and
clear state labels. Tables use readable 1rem text, consistent header/body
column widths, and keep state labels intact while long values wrap. Narrow
editor panels reduce outer padding and retain a usable state column. Neutral states use
the editor theme's blue link color. Goal cards show the disposition, last-updated
date and time in +07, and next action; generated operation IDs are omitted.

Goal pages show their offset and total. Fact pages show the goal report's
verified facts, recorded facts, unverified claims, open gates, and page total.
Each report shows a revision label. If the ledger changes between fact-page
requests, the extension clears the page and reloads from page one.
Reports missing a valid revision or fact total are rejected and the old view is
cleared. If any authorized project read fails or is denied, the panel clears
reports, evidence, goal and review cards, and project summaries; the extension
also discards its cached project, candidate, and report identifiers before
accepting another request.
Each page is a new authorized read; the prior page is cleared before requesting
the next one. The dashboard does not cache reports across requests.
Each visible fact has an **Evidence for ...** action. It fetches only that
fact's bounded evidence references and verifier receipt under a fresh project
read grant. The response must match the displayed project, goal, fact, page,
and report revision; stale responses are cleared and the report reloads from
page one. Evidence locators and attestation fields render as text, never HTML.
Selecting a completed goal also offers **Reopen completed task**. Reopening
requires a one-line reason, a concrete next action, and a final confirmation.
The extension sends the goal's displayed lifecycle revision with that single
write request; a changed or no-longer-completed goal is rejected. Write access
is requested only for the confirmed reopen action. Curator starts a new
evidence epoch while retaining earlier facts and proof as history; current
criteria return to open and need fresh evidence.
Health displays only the project status and fixed gate codes. Activity displays
retained receipt states, goal/fact totals, and pending/approved/rejected SDE
counts; it includes no record IDs or fact text. Missing, malformed, or
cross-project summary results display as `unknown`. If a fresh read fails, the
dashboard clears previously rendered goal and report data before displaying a
fixed, actionable error. It distinguishes a denied project read, a launcher
that cannot start or exits, a timeout, and an invalid MCP response. It never
displays backend exception text or process output.

Storage displays only project logical byte/count totals, fact-capacity values,
shared database/WAL file sizes, and the bounded staging scan. SQLite file sizes
are global to the shared database and must not be attributed to this project.
The staging warning begins at 75% of the configured byte threshold; reaching or
exceeding the threshold warns but does not block writes. Incomplete scans show
their fixed error code and observed lower bound. Missing, malformed, or
cross-project results display as unknown. Token usage remains outside this read
and is not inferred from zero values.

Health comes from Hermes Core's trusted, profile-bound
`mcp test curator_v2 --probe-curator-status --json` read. The result must be
bounded, include all seven timestamped dependency probes, and match the project
returned by Curator. This lets the editor display the same local host evidence
as the Hermes profile while keeping health `unknown` if the Hermes CLI is old,
unavailable, stale, malformed, or bound to another project. The editor never
creates readiness values itself. The `profileId` setting remains routing
context, not an identity or credential.

The probe selects the profile mapped to Curator's returned project ID by setting
`HERMES_HOME` to `~/.hermes/profiles/<mapped-profile-id>` and runs `mcp test`
without treating the profile ID as Hermes' model option. Point `hermesCommand` at a Hermes Core
checkout or installation that includes `--probe-curator-status`; older CLI
builds return unknown because they do not support that read.

The operational queue summary shows event age and counts, pending review,
purge, and expiry queues from a project-matched health snapshot. The **Attention**
line calls out degraded/unknown readiness, pending event failures or claims,
review and cleanup work, incomplete staging inventories, and the warning-only
staging byte threshold. For failed event receipts it reads the project's fixed
`project_metrics` categories and displays evidence rejection, adapter errors,
and other failures separately. Category totals are shown only when the
project-bound metrics reconcile to the health receipt totals. Missing,
incomplete, or cross-project snapshots show `unknown`; the editor does not infer
zero work from a failed read. These are local snapshot alerts, not external
alert delivery or capture-completeness proof.

The status item stays blue before a project health read, including when the
workspace lacks consumer configuration or required User settings. It turns
yellow when an attempted health or review-count read is unknown or unavailable.

The pending SDE section shows bounded candidate summaries from the authorized
review queue. **Review in terminal** opens the attended CLI for that exact
candidate, workspace, and database. The CLI rechecks the local OS identity and
project grant, displays the current evidence and complete artifact inventory,
rechecks selected verification evidence at approval time using the same
owner-only evidence config as the dashboard,
requires a typed confirmation bound to candidate and inventory digests, records
the decision, and persists the canonical projection before cleanup becomes
eligible. The extension does not submit review decisions or cleanup commands.
The existing six-hour purge timer processes only already-approved cleanup
receipts.

Install locally by opening this directory in VS Code and selecting **Developer:
Install Extension from Location...**. Reload the window, set the User settings,
then click `CuratorMD V2` in the bottom status bar.

Reload once after installing or updating the extension so VS Code activates the
new files. After activation, the single status item reads health at startup and
refreshes
every 60 seconds, when Curator settings change, when the workspace folder
changes, and when the VS Code window regains focus. Clicking the item opens the
pending review document when approvals are waiting; otherwise it opens the
dashboard and performs a fresh health read. Reopening the repository is not
needed for later health changes.
