# CuratorMD V2 VS Code dashboard

The V2-owned extension places its `CuratorMD V2` status item immediately to
the right of Git Graph. Its colors are gray before a health read, green when
health is healthy with no pending SDE review, purple when a human SDE decision
is pending and health is healthy or review backlog is the only degraded gate,
red for other degraded health, and yellow when health or the review queue is
unknown.
The tooltip shows the installed extension version, health, the pending review
count or its unavailable state, and a short explanation of the active color.
For a same-project health result it also lists up to 12 valid gate codes, so a
yellow unknown state points to the reported reason without exposing arbitrary
server text.
Other degraded health gates take priority over
purple so a review queue cannot hide an operational problem. Gray means no
health read has been attempted; yellow means an attempted read was unavailable,
mismatched, incomplete, or returned `unknown`.
Cross-project or unavailable health is shown as unknown. If the workspace has
no `.curatormd-v2.toml`, the extension explains
that a configured consumer project is required before starting the launcher.
The button opens a
project-scoped dashboard for the first workspace folder. Goal, health, activity,
storage, and SDE queue reads are read-only. It shows project health, exact
goal-state totals, event/review/purge/expiry queue counts, storage estimates,
paged goal cards, and one
bounded goal report page at a time. Health, activity, storage, and goal
totals are separate authorized reads and may reflect different observation
times. Retained activity is not a capture-completeness measure. Project logical
record bytes and retained event payload bytes are separate from the shared
SQLite database/WAL file sizes. It also reports the staging byte scan,
completeness, and warning-only byte threshold; writes remain allowed above the
threshold. Model/token use is not reported. Refreshing or changing pages
replaces the old view, so pages from separate report reads are never combined.

Configure these **User** settings in VS Code:

- `curatormdV2.databasePath`: absolute path to the Curator V2 SQLite database.
- `curatormdV2.profileId`: host-selected profile routing label.
- `curatormdV2.serverCommand`: optional local `curatormd-v2-mcp` path or PATH
  command; defaults to `curatormd-v2-mcp`.
- `curatormdV2.reviewCommand`: attended local SDE review CLI path or PATH
  command; defaults beside an absolute `serverCommand`, otherwise
  `curatormd-v2-review` on PATH.

The extension rejects workspace-level overrides for the launcher, database,
profile, and review CLI. It starts a read-only stdio MCP process for each
request, pinned to the open repository's `.curatormd-v2.toml` project. The
Python host derives the
authorization subject from the kernel UID and checks the exact project read
grant on every request. The profile ID is routing context, not an identity or
credential. Missing settings, a missing grant, or an unavailable launcher leave
the dashboard in an explicit error state.

Goal pages show their offset and total. Fact pages show the goal report's
verified facts, recorded facts, unverified claims, open gates, and page total.
Each report shows a revision label. If the ledger changes between fact-page
requests, the extension clears the page and reloads from page one.
Reports missing a valid revision or fact total are rejected and the old view is
cleared.
Each page is a new authorized read; the prior page is cleared before requesting
the next one. The dashboard does not cache reports across requests.
Each visible fact has an **Evidence for ...** action. It fetches only that
fact's bounded evidence references and verifier receipt under a fresh project
read grant. The response must match the displayed project, goal, fact, page,
and report revision; stale responses are cleared and the report reloads from
page one. Evidence locators and attestation fields render as text, never HTML.
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

The editor launches Curator directly over local stdio and supplies profile and
session routing metadata. It does not supply Hermes Core's trusted host
readiness observations. Therefore host dependencies in `project_health` remain
`unknown` in this editor path until a trusted Hermes-managed readiness source is
connected. Do not treat the configured profile label as proof of host identity
or readiness.

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

The status item stays gray before a project health read, including when the
workspace lacks consumer configuration or required User settings. It turns
yellow only when an attempted health read is unavailable, mismatched, or
returns `unknown`.

The pending SDE section shows bounded candidate summaries from the authorized
review queue. **Review in terminal** opens the attended CLI for that exact
candidate, workspace, and database. The CLI rechecks the local OS identity and
project grant, displays the current evidence and complete artifact inventory,
requires a typed confirmation bound to candidate and inventory digests, records
the decision, and persists the canonical projection before cleanup becomes
eligible. The extension does not submit review decisions or cleanup commands.
The existing six-hour purge timer processes only already-approved cleanup
receipts.

Install locally by opening this directory in VS Code and selecting **Developer:
Install Extension from Location...**. Reload the window, set the User settings,
then click `CuratorMD V2` in the bottom status bar.
