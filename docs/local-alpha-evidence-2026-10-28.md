# Local Curator V2 alpha evidence snapshot

Updated 2026-10-28 13:10 UTC. Each row retains its observation time. This is
a content-free snapshot for the single-user, one-repository development alpha.
It does not authorize another capture, cleanup, or policy change.

## Binding

- Installed package source commit: `851d12d5a7073cf236f6ba97a46ab95e9591d45c`.
- Alpha wheel: `curatormd_v2-0.1.0a1-py3-none-any.whl`, SHA-256
  `d3e81af77224f5cdaa7167a7c27c219284ea4acedb01b49a505041fa6131d219`.
- Installed only in `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/curator-v2-alpha-venv`.
- Repository config: `vhost-manager-alpha`, SHA-256
  `a37448f38683c864480d4f90db8fc6a6b694311679b598979f86ff574713f746`.
- Binding recheck (2026-10-28 05:44 UTC): `.curatormd-v2.toml` remains a regular
  file owned by UID 1000 with mode `0600`; its SHA-256 matches the bound value.
- Binding reconciliation (2026-10-28 12:08 UTC): the installed distribution
  is `0.1.0a1`; all 88 installed Python module hashes match the repository
  source at the recorded commit, `pip check` passes, and the project config
  remains a regular UID-1000 file with mode `0600` and the same SHA-256.
- Local owner: `eaglesvn`, UID 1000. Alpha ledger:
  `/home/eaglesvn/.local/share/curatormd-v2-alpha/global.sqlite3`, mode `0600`;
  containing directory mode `0700`.

## Evidence

| Area | Observed result | State |
|---|---|---|
| Package | 88 installed Python modules match source; `pip check` and MCP launcher `--help` pass. Before replacement, 182 files were hash-verified in rollback archive `~/.hermes/profiles/renew-ssl-coding/backups/curator-v2-pre-mcp-privacy-20261028T041838Z.tar.gz` (SHA-256 `89133debfb12cb7a02cfc1476e019b0fd067d23752c95f7b8137757aeb75221b`). In a temporary site-packages copy, the active package tree was replaced by the verified archive; both package versions loaded and the launcher `--help` passed before and after rollback. The active profile install was not replaced. | Isolated package rollback passed; active profile and Hermes process were untouched. |
| V2 VS Code dashboard and readiness | Extension 0.9.3 is installed. Its focused Node suite passes 17/17. The extension obtains project health from Hermes Core's bounded `--probe-curator-status --json` command, validates the exact configured project and all seven fresh probe observations, and keeps direct Curator MCP reads for dashboard data. The current User setting points `hermesCommand` at the Hermes Core source checkout. At 12:27:38 UTC, `showDashboard` ran with the actual Vhost workspace, User settings, Curator launcher, and Hermes CLI under a stubbed VS Code host; it loaded 26 goals, 23 facts, and 60 event receipts. Health was `healthy`, with zero gates and all seven dependencies healthy. Fresh invocations from the Vhost workspace at 12:39:03 UTC, 12:49 UTC, and 13:02 UTC returned `healthy`, seven healthy dependencies, and no gates. The 13:02 invocation exited 0, connected successfully, and reported `vhost-manager-alpha`. | Installed dashboard data path and fresh host observations verified. The host/webview was stubbed in the dashboard run, so desktop rendering and the visible status-bar color remain unverified. A direct Curator MCP call from this Codex session returned `unauthenticated`; it did not supply trusted Hermes context and does not establish the profile's readiness. |
| Quality | The focused backup suite passes 13 tests, including threshold status and keeping files above the warning level. The VS Code extension suite passes 16 tests; `git diff --check` passes. Targeted Pyright, errors-only Pylint, and Bandit passed when the backup scanner was implemented. | Focused checks verified; the full Curator suite was not rerun for the backup warning change. |
| Vhost route and Markdown projection | The 2026-10-28 loopback smoke applied `curator-v2-alpha-smoke-20261028.test`, returned HTTP 200, replayed the same fact and goal-start idempotently, then rolled back. Apply receipt: `vhost-apply-65bb1c01-11e3-4cd3-b73a-57d0b7161d8c`; rollback operation: `b3cfa643-c3e1-456b-89a8-996479be6b4b`. The test site's account and Nginx files were absent afterward; the unrelated 63-entry Nginx tree retained hash `b2c5d9b9e26afd0d99f93ee0b3062e3831d712628c64c88f33a9f9be8fbb8698`. Using the owner-only local UID reviewer API, projected only goals `vhost-op-65bb1c01-11e3-4cd3-b73a-57d0b7161d8c` and `vhost-rollback-b3cfa643-c3e1-456b-89a8-996479be6b4b` to the configured `HISTORY.md`; read-only reconciliation returned `synced` for both. Their ledger block hashes are `112e427fad74cd5a451145ca796f96f101c081976dfedea2ebe7fdf27256862c` and `1a4360114240c1e1304ca46fd73b28caf6b9f619973183fb16e40ab4bcec2f7d`. | Local workflow and exact projections verified; owner review of the complete packet remains open. |
| Staging | The approved Vhost staging threshold is 262,144,000 bytes (250 MiB), warning only; writes remain allowed and there is no file-count limit. Boundary behavior has focused test coverage. | Policy and implementation verified; the live profile has not crossed the threshold. |
| Retention and backup | Live transient source files have a 72-hour maximum. The backup policy retains the newest seven verified daily SQLite copies; owner approval allows unresolved retry/quarantine payloads in those copies. Restore is manual to a new path. On 2026-10-28, `eaglesvn` approved retaining goals, facts, SDE decisions, review/cleanup/recovery receipts, grants/audit rows, and processed receipts until approval of cleanup for an exact inventory, with no automatic pruning; existing hard caps are unchanged and the 250 MiB backup-tree threshold is warning-only. | Approved durable-record policy is documented. Pending retry/quarantine payload age, complete per-class accounting, and source enforcement remain open. The per-user six-hour timer and backup run are separately verified; restore-to-new-path has focused source tests but no live alpha restore. |
| Backup storage | The 04:52 UTC inventory counted 29 entries (27 files, 2 directories, 0 symlinks), 4,642,256 logical file bytes, and 4,681,728 allocated bytes without reading file contents. The refreshed installed scanner traverses all 29 entries using descriptor-relative no-follow opens, including the two group-writable directories. Its 12:03 UTC read measured 4,642,256 logical file bytes and 4,685,824 allocated bytes including the root directory; one daily snapshot is recognized and 28 legacy entries remain unclassified. Inventory `status=incomplete` describes class identification; the separate `warning_status=below_threshold` follows a complete bounded byte measurement under the 262,144,000-byte (250 MiB) warning threshold. The owner-approved warning never authorizes deletion, and no files were changed or removed. | The warning-only policy and complete bounded size measurement are verified. The approved durable-record retention default is recorded; pending payload age, other class-specific retention/recovery horizons, and complete permanent-data accounting remain open. |
| Permanent storage measurement | The 12:27:38 UTC dashboard read reports 46,338 logical project-record bytes across 26 goals, 23 facts, and 60 event receipts; retained event payload bytes are zero. The shared SQLite main file is 524,288 bytes and WAL 300,792 bytes. Staging inventory is complete and empty under the 262,144,000-byte warning-only threshold. The prior host-authorized control-plane read reported 3,145 logical bytes across 11 classes; the prior metadata-only `lstat` measured SHM at 32,768 bytes. No database contents were read. | Project totals and shared database/WAL sizes refreshed at 12:27 UTC. Per-class retention/recovery horizons, physical table/index attribution, and permanent-database warning rules remain open. |
| Token usage | Read-only report at 2026-10-28 13:10 UTC returned seven retained bound turns: six reported and one with unknown usage, all sourced from `codex_app_server`. The retained interval is 2026-10-20 09:08:37 UTC through 2026-10-28 05:50:47 UTC; latest-event age at measurement was 26,401 seconds. No token totals were copied into this evidence record. `coverage_complete=false` and `tokens_complete=false`; exclusions are auxiliary calls outside active-turn context, auxiliary attempts without a response, and unbound sessions. | The report has refreshed from a real profile-bound turn and remains report-only. No token budget is defined or enforced. Coverage gaps remain explicit; the report has no freshness threshold, so age is recorded without classifying it as stale or fresh. |
| Process privacy | During a Hermes profile `--probe-curator-status` invocation, a syscall-only trace of the spawned Curator MCP server observed `prlimit64(... RLIMIT_CORE, {0, 0})` and `umask(077)` before serving. On 2026-10-28 05:13 UTC, Hermes Core's root-owned drop-in `/etc/systemd/system/hermes-gateway.service.d/90-local-privacy.conf` was applied, systemd reloaded, and `hermes-gateway.service` restarted. Recheck at 05:40 UTC reports the gateway active/running with `LimitCORE=0` and `UMask=0077`; process UID is 1000, process umask is `0077`, and `/proc` reports zero core-file size. The Curator maintenance service reports `Result=success`, exit status 0, `LimitCORE=0`, and `UMask=0077`. | Hermes-launched MCP child, gateway, and maintenance-process limits are verified on this host. Apport retention, journals, other data sinks, and crash-canary handling remain unverified; full source-to-sink audit stays open. |
| Hermes profile-to-ledger and lifecycle | At 2026-10-28 05:50 UTC, a real Hermes Core app-server turn under the `renew-ssl-coding` profile emitted start/end outbox sequences 12 and 13 for `vhost-manager-alpha` and the existing active alpha goal. Both events were acknowledged; metadata-only binding checks matched their session to the same project and goal. Curator's supported profile probe then returned 58/58 processed receipts, zero failed or quarantined events, and healthy project status. The event contexts contain only bounded attempt/session/turn identifiers and outcome, without prompt/transcript text. A direct MCP call without injected Hermes context still returns `unauthenticated`; profile-context access succeeds. | Local app-server-to-managed-MCP lifecycle delivery and content boundary verified. No human-authentication or production claim. Token usage is now fresh but remains incomplete. |
| SDE review | The local review CLI's `queue` read returned `pending: []` for `vhost-manager-alpha`. | No candidate awaits disposition; alpha packet review is a separate owner decision. |

## Local-alpha privacy sink matrix

This matrix records tested boundaries and the approved retry-data exception. It
does not claim that every producer or operating-system sink has been audited.

| Sink | Current evidence | State |
|---|---|---|
| Exceptions, MCP errors, and CLI failures | Focused canary regressions cover MCP tool errors/logs, router configuration failures, producer failures, storage failures, and event/config decode errors. The handlers emit fixed public errors or bounded labels. See the privacy progress record in [`curator-v2-plan.md`](curator-v2-plan.md#8-security-privacy-token-and-disk-controls). | Covered for these tested paths; every producer/adapter path has not been inventoried. |
| Metrics | `tests/test_api_health_metrics.py::test_retry_payload_text_is_not_exposed_in_project_metrics` checks that retained retry text does not appear in Prometheus output. | Focused canary evidence recorded; no general trace exporter is configured in Curator V2. |
| Canonical ledger and SQLite | Sensitive-event ingress tests reject recognized credential-like input before durable writes. Processed payload scrub tests cover WAL removal. Retryable and quarantined event payloads remain in the inbox for recovery by design. | Processed/rejected paths have focused evidence; retry/quarantine retention is an explicit recovery exception, not canonical fact storage. |
| SQLite backups | Backup tests prove processed envelopes are not retained as source payloads and verify retry/quarantine restoration. Owner policy permits unresolved retry/quarantine payloads in the newest seven daily backups. | Approved exception; pending payload age can roll forward while the event remains unresolved. |
| Hermes diagnostics and trajectory | Hermes Core source/test progress records redaction of Curator V2 arguments, results, and failure details in the reviewed diagnostics and trajectory paths. | Source/test evidence only; other Hermes session and trajectory paths were not audited for this snapshot. |
| Core dumps | At 05:40 UTC, the active gateway and local maintenance service reported `LimitCORE=0`; the gateway process also reported a zero core limit and `UMask=0077`. No crash canary was generated. | Limits verified for these processes; other producers and crash-report handling were not exercised. |
| Host journals | The current maintenance run writes a bounded JSON summary with counts and status. The inspected service output contained no event payload. | Verified for this maintenance service run only; other journal producers were not scanned. |
| Command history | Curator event content is transported through MCP/stdin rather than command-line arguments in the reviewed producer path. | The account's command history was not scanned; this sink remains unverified. |

The full privacy checklist remains open for command-history coverage, other
local producer/log paths, broader Hermes and operating-system sinks, and owner
review of this matrix. The available focused evidence does not establish a
universal source-to-sink guarantee.

## Remaining local acceptance work

- Resolve the project-usage report's known coverage gaps or obtain an explicit
  owner decision to exclude those sources. The 2026-10-28 13:10 UTC read
  reflects a real bound app-server event through 05:50 UTC; coverage remains
  incomplete and report-only. No model/token budget is defined or enforced.
- Complete class-specific long-term retention/recovery horizons for the legacy
  backup entries and permanent database classes.
- Review the local-alpha privacy sink matrix and close its listed unverified
  producer and operating-system paths.
- Compare the other Vhost-owned target hashes before and after an approved
  workflow run; the recorded smoke verified the unrelated Nginx tree after
  rollback but did not record a before/after set for every configured target.
- `eaglesvn` reviews and accepts or rejects this snapshot; no review decision is
  implied by its creation.

The active plan is [`curator-v2-plan.md`](curator-v2-plan.md); the alpha
implementation timeline is [`alpha-v2.md`](alpha-v2.md). This snapshot preserves
verified local facts and open work without introducing a production or
multi-user requirement.
