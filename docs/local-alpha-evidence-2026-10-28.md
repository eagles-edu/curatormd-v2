# Local Curator V2 alpha evidence snapshot

Measured 2026-10-28 04:35:27 UTC. This is a content-free snapshot for the
single-user, one-repository development alpha. It does not authorize another
capture, cleanup, or policy change.

## Binding

- Installed package source commit: `584b7693c46122f069c7fb4c5f5e4c191e512a27`;
  package source files are unchanged in the current checkout.
- Alpha wheel: `curatormd_v2-0.1.0a1-py3-none-any.whl`, SHA-256
  `f422a3f11749a6b519c39da8de60e22018cb7b9c3b6cdeedad2babd7ec7e7b55`.
- Installed only in `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/curator-v2-alpha-venv`.
- Repository config: `vhost-manager-alpha`, SHA-256
  `a37448f38683c864480d4f90db8fc6a6b694311679b598979f86ff574713f746`.
- Local owner: `eaglesvn`, UID 1000. Alpha ledger:
  `/home/eaglesvn/.local/share/curatormd-v2-alpha/global.sqlite3`, mode `0600`;
  containing directory mode `0700`.

## Evidence

| Area | Observed result | State |
|---|---|---|
| Package | 88 installed Python modules match source; `pip check` and MCP launcher `--help` pass. Before replacement, 182 files were hash-verified in rollback archive `~/.hermes/profiles/renew-ssl-coding/backups/curator-v2-pre-mcp-privacy-20261028T041838Z.tar.gz` (SHA-256 `89133debfb12cb7a02cfc1476e019b0fd067d23752c95f7b8137757aeb75221b`). The archive was extracted to a temporary isolated package path; its `0.1.0a1` metadata loaded and the restored MCP launcher `--help` passed. The active profile install was not replaced. | Archive restore/launch is verified in isolation; replacing and rolling back a disposable installed environment remains open. |
| Quality | Focused hosted-MCP tests pass (13 plus one CLI evidence test); full Pyright, errors-only Pylint on the changed files, Bandit, and `git diff --check` passed for the source change. | Verified for the changed launcher; the full Curator test suite was not rerun for this change. |
| Vhost route and Markdown projection | The 2026-10-28 loopback smoke applied `curator-v2-alpha-smoke-20261028.test`, returned HTTP 200, replayed the same fact and goal-start idempotently, then rolled back. Apply receipt: `vhost-apply-65bb1c01-11e3-4cd3-b73a-57d0b7161d8c`; rollback operation: `b3cfa643-c3e1-456b-89a8-996479be6b4b`. The test site's account and Nginx files were absent afterward; the unrelated 63-entry Nginx tree retained hash `b2c5d9b9e26afd0d99f93ee0b3062e3831d712628c64c88f33a9f9be8fbb8698`. Using the owner-only local UID reviewer API, projected only goals `vhost-op-65bb1c01-11e3-4cd3-b73a-57d0b7161d8c` and `vhost-rollback-b3cfa643-c3e1-456b-89a8-996479be6b4b` to the configured `HISTORY.md`; read-only reconciliation returned `synced` for both. Their ledger block hashes are `112e427fad74cd5a451145ca796f96f101c081976dfedea2ebe7fdf27256862c` and `1a4360114240c1e1304ca46fd73b28caf6b9f619973183fb16e40ab4bcec2f7d`. | Local workflow and exact projections verified; owner review of the complete packet remains open. |
| Staging | The approved Vhost staging threshold is 262,144,000 bytes (250 MiB), warning only; writes remain allowed and there is no file-count limit. Boundary behavior has focused test coverage. | Policy and implementation verified; the live profile has not crossed the threshold. |
| Retention and backup | Live transient source files have a 72-hour maximum. The backup policy retains the newest seven verified daily SQLite copies; owner approval allows unresolved retry/quarantine payloads in those copies. Restore is manual to a new path. | Policy and rotation/restore tests verified; unresolved payloads can roll forward while still pending. Retention of other backup-tree files is open. |
| Backup storage | The last content-free inventory found 21 entries, 19 regular files, 4,618,625 logical bytes, and 4,636,672 allocated bytes. Twenty entries remain unclassified; four entries were not owner-only, so the scan reported incomplete. | Open: no retention or warning policy for the older recovery files. |
| Token usage | The profile ledger has six retained turns, five with reported usage and one unknown; its only source is `codex_app_server`. Latest event: `2026-10-21T10:40:21Z`; age at measurement: 582,351 seconds. The installed profile plugin matches Hermes source and reports `coverage_complete=false` and `tokens_complete=false`. | Open: current usage needs a real profile turn; known source exclusions prevent a completeness claim. No synthetic event was written. |
| Process privacy | Curator's installed MCP launcher sets its own core limit to zero and umask to `0077`; an installed-interpreter child observed both settings. | Partial: no active Hermes-launched session was checked; Hermes, Apport, journals, and other sinks remain unverified. |
| SDE review | The local review CLI's `queue` read returned `pending: []` for `vhost-manager-alpha`. | No candidate awaits disposition; alpha packet review is a separate owner decision. |

## Remaining local acceptance work

- Refresh the profile usage ledger with a real turn and resolve or explicitly
  retain its known coverage gaps. No model/token budget is enforced.
- Assign retention and warning rules to the unclassified older backup files
  and complete permanent-data accounting.
- Finish the local source-to-sink privacy review beyond the Curator MCP child.
- Compare the other Vhost-owned target hashes for the reviewed workflow; only
  the configured `HISTORY.md` target was written during this projection check.
- Exercise replacement and rollback in a disposable installed environment, then
  reconcile all applicable local workflow evidence against this exact
  package/config binding.
- `eaglesvn` reviews and accepts or rejects this snapshot; no review decision is
  implied by its creation.

The active plan is [`curator-v2-plan.md`](curator-v2-plan.md); the alpha
implementation timeline is [`alpha-v2.md`](alpha-v2.md). This snapshot preserves
verified local facts and open work without introducing a production or
multi-user requirement.
