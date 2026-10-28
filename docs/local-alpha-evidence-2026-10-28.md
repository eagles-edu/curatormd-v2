# Local Curator V2 alpha evidence snapshot

Updated 2026-10-28 05:30 UTC. Each row retains its observation time. This is
a content-free snapshot for the single-user, one-repository development alpha.
It does not authorize another capture, cleanup, or policy change.

## Binding

- Installed package source commit: `c1f15cb215c0c0d4a9fab703b988ac1830a2a825`.
- Alpha wheel: `curatormd_v2-0.1.0a1-py3-none-any.whl`, SHA-256
  `fbe39c5dc6ee0abe459e97fc7cc156527a110d1ca563d9036371e516ef3574b2`.
- Installed only in `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/curator-v2-alpha-venv`.
- Repository config: `vhost-manager-alpha`, SHA-256
  `a37448f38683c864480d4f90db8fc6a6b694311679b598979f86ff574713f746`.
- Local owner: `eaglesvn`, UID 1000. Alpha ledger:
  `/home/eaglesvn/.local/share/curatormd-v2-alpha/global.sqlite3`, mode `0600`;
  containing directory mode `0700`.

## Evidence

| Area | Observed result | State |
|---|---|---|
| Package | 88 installed Python modules match source; `pip check` and MCP launcher `--help` pass. Before replacement, 182 files were hash-verified in rollback archive `~/.hermes/profiles/renew-ssl-coding/backups/curator-v2-pre-mcp-privacy-20261028T041838Z.tar.gz` (SHA-256 `89133debfb12cb7a02cfc1476e019b0fd067d23752c95f7b8137757aeb75221b`). In a temporary site-packages copy, the active package tree was replaced by the verified archive; both package versions loaded and the launcher `--help` passed before and after rollback. The active profile install was not replaced. | Isolated package rollback passed; active profile and Hermes process were untouched. |
| V2 VS Code dashboard | Extension 0.9.1 is installed and the editor was reloaded at 2026-10-28 05:18 UTC. The status item renders immediately after Git Graph in yellow `unknown` state; the dashboard shows project health/open gates, retained activity, and a project-scoped goal report with its recorded-fact classification and evidence action. The focused Node suite passes 15/15 and rejects a goal report missing a valid revision or fact total. The tooltip source prefixes the package version; the root-screen hover capture did not show tooltip text. | Rendered status position/color and dashboard read verified. Hover wording, fresh grant revocation, trust-version changes, and full review/cleanup interactions remain open. |
| Quality | The focused backup suite passes 13 tests, including threshold status and keeping files above the warning level; `git diff --check` passes. The source change's targeted Pyright, errors-only Pylint, and Bandit checks passed when implemented. | Current focused backup behavior verified. The full Curator suite was not rerun for the backup warning change. |
| Vhost route and Markdown projection | The 2026-10-28 loopback smoke applied `curator-v2-alpha-smoke-20261028.test`, returned HTTP 200, replayed the same fact and goal-start idempotently, then rolled back. Apply receipt: `vhost-apply-65bb1c01-11e3-4cd3-b73a-57d0b7161d8c`; rollback operation: `b3cfa643-c3e1-456b-89a8-996479be6b4b`. The test site's account and Nginx files were absent afterward; the unrelated 63-entry Nginx tree retained hash `b2c5d9b9e26afd0d99f93ee0b3062e3831d712628c64c88f33a9f9be8fbb8698`. Using the owner-only local UID reviewer API, projected only goals `vhost-op-65bb1c01-11e3-4cd3-b73a-57d0b7161d8c` and `vhost-rollback-b3cfa643-c3e1-456b-89a8-996479be6b4b` to the configured `HISTORY.md`; read-only reconciliation returned `synced` for both. Their ledger block hashes are `112e427fad74cd5a451145ca796f96f101c081976dfedea2ebe7fdf27256862c` and `1a4360114240c1e1304ca46fd73b28caf6b9f619973183fb16e40ab4bcec2f7d`. | Local workflow and exact projections verified; owner review of the complete packet remains open. |
| Staging | The approved Vhost staging threshold is 262,144,000 bytes (250 MiB), warning only; writes remain allowed and there is no file-count limit. Boundary behavior has focused test coverage. | Policy and implementation verified; the live profile has not crossed the threshold. |
| Retention and backup | Live transient source files have a 72-hour maximum. The backup policy retains the newest seven verified daily SQLite copies; owner approval allows unresolved retry/quarantine payloads in those copies. Restore is manual to a new path. The per-user six-hour maintenance timer was active at 2026-10-28 12:30 +07; its 12:00 run exited 0 and emitted `backup_status=verified`, with zero due purge and expiry items or pending failures. | Policy, rotation/restore tests, and current timer/backup run verified. Restore-to-new-path has focused source tests but no live alpha restore; unresolved payloads can roll forward while pending. Retention of other backup-tree files is open. |
| Backup storage | The bounded metadata inventory (2026-10-28 04:52 UTC) counted 29 entries (27 files, 2 directories, 0 symlinks), 4,642,256 logical file bytes, and 4,681,728 allocated bytes without reading contents or following symlinks. The owner approved warning at 262,144,000 allocated bytes (250 MiB), keeping all files. Updated source reports `warning` at/above the threshold, `below_threshold` only after a complete supported scan, and `unknown` for an incomplete scan. The refreshed alpha package's scanner observed 21 entries, 4,636,672 allocated bytes, and `backup_status=incomplete`; its warning state is correctly `unknown`, so no below-threshold claim is made. | Policy and warning behavior are implemented and threshold regression-tested. The alpha runtime package is refreshed; its current incomplete scan does not establish whether the whole tree is below threshold. Retention of older recovery classes remains open. |
| Permanent storage measurement | The local Vhost project read reports 43,912 logical project bytes: 25 goals, 22 facts, 56 event receipts; 37,859 original event-payload bytes received and zero retained payload bytes. The inbox retains 18,885 logical row bytes of its 134,217,728-byte limit. The separate control-plane view reports 3,145 logical bytes across 11 classes, 524,288 database bytes, and a 383,192-byte WAL. Staging is empty and complete. | Current sizes measured; class retention/recovery horizons and permanent-storage warning rules remain open. |
| Token usage | At 2026-10-28 04:57:28 UTC, the read-only profile report still had six retained turns (five reported, one unknown), source `codex_app_server`, last event `2026-10-21T10:40:21Z`; both `coverage_complete` and `tokens_complete` are false. A real one-shot Hermes CLI query succeeded after correcting the profile's stale Codex binary path, but added no usage row because that CLI session had no durable project/goal binding and is excluded by design. | Stale and incomplete; a bound project/goal turn is still needed to refresh the report. Known source exclusions prevent a completeness claim. No synthetic usage event was written. |
| Process privacy | During a Hermes profile `--probe-curator-status` invocation, a syscall-only trace of the spawned Curator MCP server observed `prlimit64(... RLIMIT_CORE, {0, 0})` and `umask(077)` before serving. On 2026-10-28 05:13 UTC, Hermes Core's root-owned drop-in `/etc/systemd/system/hermes-gateway.service.d/90-local-privacy.conf` was applied, systemd reloaded, and `hermes-gateway.service` restarted. The active process (PID 3469938 at verification) reports `Umask: 0077` in `/proc/<pid>/status` and a zero `Max core file size` in `/proc/<pid>/limits`; systemd reports `ActiveState=active`, `SubState=running`, `LimitCORE=0`, and `UMask=0077`. | Hermes-launched MCP child and gateway process limits are verified on this host. Apport retention, journals, other data sinks, and crash-canary handling remain unverified; full source-to-sink audit stays open. |
| Hermes profile-to-ledger read | At 2026-10-28 04:58 UTC, `./.venv/bin/hermes --profile renew-ssl-coding mcp test curator_v2 --probe-curator-status` exited 0, identified host-injected profile/session context, connected to the installed stdio server, and discovered 50 tools. The read returned 56/56 processed receipts, 25 goals, 22 facts, zero SDE candidates, and a separate healthy project-health observation with complete database and staging observations and no gate codes. The profile's configured `codex_bin` was corrected from a missing VS Code extension path to installed Codex CLI `0.162.0-alpha.17.2`; a mode-0600 config backup was retained. | Current local profile and ledger read verified. It is not a new app-server lifecycle event and did not refresh token usage. The system Hermes CLI still displays `Auth: none`; that transport label is not the host-injected context result. |
| SDE review | The local review CLI's `queue` read returned `pending: []` for `vhost-manager-alpha`. | No candidate awaits disposition; alpha packet review is a separate owner decision. |

## Remaining local acceptance work

- Refresh the profile usage ledger through a real, durable project/goal-bound
  turn; a plain Hermes CLI turn is excluded. Then resolve or explicitly retain
  its known coverage gaps. No model/token budget is enforced.
- Assign retention and warning rules to the unclassified older backup files
  and complete permanent-data accounting.
- Finish the local source-to-sink privacy review beyond the Curator MCP child.
- Compare the other Vhost-owned target hashes for the reviewed workflow; only
  the configured `HISTORY.md` target was written during this projection check.
- Reconcile the package and all applicable local workflow evidence against this
  exact package/config binding.
- `eaglesvn` reviews and accepts or rejects this snapshot; no review decision is
  implied by its creation.

The active plan is [`curator-v2-plan.md`](curator-v2-plan.md); the alpha
implementation timeline is [`alpha-v2.md`](alpha-v2.md). This snapshot preserves
verified local facts and open work without introducing a production or
multi-user requirement.
