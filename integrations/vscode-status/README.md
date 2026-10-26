# CuratorMD V2 VS Code dashboard

The V2-owned extension keeps the `CuratorMD V2` status-bar label and opens a
read-only dashboard for the first workspace folder. It lists paged goal cards
and displays one bounded goal report page at a time. Refreshing or changing
pages replaces the old view, so pages from separate reads are never combined.

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

Install locally by opening this directory in VS Code and selecting **Developer:
Install Extension from Location...**. Reload the window, set the User settings,
then click `CuratorMD V2` in the bottom status bar.
