# CuratorMD V2 VS Code dashboard

The V2-owned extension keeps the `CuratorMD V2` status-bar label and opens a
read-only dashboard for the first workspace folder. It shows a project health
summary, retained event/review totals, paged goal cards, and one bounded goal
report page at a time. Health, activity, and goal totals are separate authorized
reads and may reflect different observation times. Retained activity is not a
capture-completeness measure. Refreshing or changing pages replaces the old
view, so pages from separate report reads are never combined.

Configure these **User** settings in VS Code:

- `curatormdV2.databasePath`: absolute path to the Curator V2 SQLite database.
- `curatormdV2.profileId`: host-selected profile routing label.
- `curatormdV2.serverCommand`: optional local `curatormd-v2-mcp` path or PATH
  command; defaults to `curatormd-v2-mcp`.

The extension rejects workspace-level overrides for the launcher, database,
and profile. It starts a read-only stdio MCP process for each request, pinned to
the open repository's `.curatormd-v2.toml` project. The Python host derives the
authorization subject from the kernel UID and checks the exact project read
grant on every request. The profile ID is routing context, not an identity or
credential. Missing settings, a missing grant, or an unavailable launcher leave
the dashboard in an explicit error state.

Goal pages show their offset and total. Fact pages show the goal report's
verified facts, recorded facts, unverified claims, open gates, and page total.
Each report shows a revision label. If the ledger changes between fact-page
requests, the extension clears the page and reloads from page one.
Each page is a new authorized read; the prior page is cleared before requesting
the next one. The dashboard does not cache reports across requests.
Health displays only the project status and fixed gate codes. Activity displays
retained receipt states, goal/fact totals, and pending/approved/rejected SDE
counts; it includes no record IDs or fact text. Missing, malformed, or
cross-project summary results display as `unknown`. If a fresh read fails, the
dashboard clears previously rendered goal and report data before displaying a
generic error.

The editor launches Curator directly over local stdio and supplies profile and
session routing metadata. It does not supply Hermes Core's trusted host
readiness observations. Therefore host dependencies in `project_health` remain
`unknown` in this editor path until a trusted Hermes-managed readiness source is
connected. Do not treat the configured profile label as proof of host identity
or readiness.

Install locally by opening this directory in VS Code and selecting **Developer:
Install Extension from Location...**. Reload the window, set the User settings,
then click `CuratorMD V2` in the bottom status bar.
