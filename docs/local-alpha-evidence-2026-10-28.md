# Local Curator V2 alpha evidence snapshot

Updated 2026-10-28 05:44 UTC. Each row retains its observation time. This is
a content-free snapshot for the single-user, one-repository development alpha.
It does not authorize another capture, cleanup, or policy change.

## Binding

- Installed package source commit: `c1f15cb215c0c0d4a9fab703b988ac1830a2a825`.
- Alpha wheel: `curatormd_v2-0.1.0a1-py3-none-any.whl`, SHA-256
  `fbe39c5dc6ee0abe459e97fc7cc156527a110d1ca563d9036371e516ef3574b2`.
- Installed only in `/home/eaglesvn/.hermes/profiles/renew-ssl-coding/curator-v2-alpha-venv`.
- Repository config: `vhost-manager-alpha`, SHA-256
  `a37448f38683c864480d4f90db8fc6a6b694311679b598979f86ff574713f746`.
- Binding recheck (2026-10-28 05:44 UTC): `.curatormd-v2.toml` remains a regular
  file owned by UID 1000 with mode `0600`; its SHA-256 matches the bound value.
- Local owner: `eaglesvn`, UID 1000. Alpha ledger:
  `/home/eaglesvn/.local/share/curatormd-v2-alpha/global.sqlite3`, mode `0600`;
  containing directory mode `0700`.

## Evidence

| Area | Observed result | State |
|---|---|---|
| Package | 88 installed Python modules match source; `pip check` and MCP launcher `--help` pass. Before replacement, 182 files were hash-verified in rollback archive `~/.hermes/profiles/renew-ssl-coding/backups/curator-v2-pre-mcp-privacy-20261028T041838Z.tar.gz` (SHA-256 `89133debfb12cb7a02cfc1476e019b0fd067d23752c95f7b8137757aeb75221b`). In a temporary site-packages copy, the active package tree was replaced by the verified archive; both package versions loaded and the launcher `--help` passed before and after rollback. The active profile install was not replaced. | Isolated package rollback passed; active profile and Hermes process were untouched. |
| V2 VS Code dashboard | Extension 0.9.2 is installed and its `extension.js` hash matches source (`1f863844c655c0ddd9bb76ecbb8f609fb61f4b9ade920896065def34525551bf`). The focused Node suite passes 16/16, including revision mismatch, fresh-read denial, and rejection of a later page without a first-page snapshot. The reloaded `renew_ssl` window's extension-host log records 0.9.2 activation; the status item is immediately after Git Graph. Hover visibly renders `CuratorMD V2 0.9.2` and says gray means no health read has been attempted. | Package/source match, active-window version, placement, and rendered version tooltip verified. The current gray state accurately reflects that no project health read has run in this window. Grant/trust changes and full review/cleanup interactions remain open. |
| Quality | The focused backup suite passes 13 tests, including threshold status and keeping files above the warning level; `git diff --check` passes. The source change's targeted Pyright, errors-only Pylint, and Bandit checks passed when implemented. | Current focused backup behavior verified. The full Curator suite was not rerun for the backup warning change. |
| Vhost route and Markdown projection | The 2026-10-28 loopback smoke applied `curator-v2-alpha-smoke-20261028.test`, returned HTTP 200, replayed the same fact and goal-start idempotently, then rolled back. Apply receipt: `vhost-apply-65bb1c01-11e3-4cd3-b73a-57d0b7161d8c`; rollback operation: `b3cfa643-c3e1-456b-89a8-996479be6b4b`. The test site's account and Nginx files were absent afterward; the unrelated 63-entry Nginx tree retained hash `b2c5d9b9e26afd0d99f93ee0b3062e3831d712628c64c88f33a9f9be8fbb8698`. Using the owner-only local UID reviewer API, projected only goals `vhost-op-65bb1c01-11e3-4cd3-b73a-57d0b7161d8c` and `vhost-rollback-b3cfa643-c3e1-456b-89a8-996479be6b4b` to the configured `HISTORY.md`; read-only reconciliation returned `synced` for both. Their ledger block hashes are `112e427fad74cd5a451145ca796f96f101c081976dfedea2ebe7fdf27256862c` and `1a4360114240c1e1304ca46fd73b28caf6b9f619973183fb16e40ab4bcec2f7d`. | Local workflow and exact projections verified; owner review of the complete packet remains open. |
| Staging | The approved Vhost staging threshold is 262,144,000 bytes (250 MiB), warning only; writes remain allowed and there is no file-count limit. Boundary behavior has focused test coverage. | Policy and implementation verified; the live profile has not crossed the threshold. |
| Retention and backup | Live transient source files have a 72-hour maximum. The backup policy retains the newest seven verified daily SQLite copies; owner approval allows unresolved retry/quarantine payloads in those copies. Restore is manual to a new path. The per-user six-hour maintenance timer was active at 2026-10-28 12:30 +07; its 12:00 run exited 0 and emitted `backup_status=verified`, with zero due purge and expiry items or pending failures. | Policy, rotation/restore tests, and current timer/backup run verified. Restore-to-new-path has focused source tests but no live alpha restore; unresolved payloads can roll forward while pending. Retention of other backup-tree files is open. |
| Backup storage | The bounded metadata inventory (2026-10-28 04:52 UTC) counted 29 entries (27 files, 2 directories, 0 symlinks), 4,642,256 logical file bytes, and 4,681,728 allocated bytes without reading contents or following symlinks. The owner approved warning at 262,144,000 allocated bytes (250 MiB), keeping all files. Existing legacy entries remain untouched until `eaglesvn` approves deletion of an exact inventory; seven-copy rotation is limited to verified routine-generated daily SQLite snapshots. Updated source reports `warning` at/above the threshold, `below_threshold` only after a complete supported scan, and `unknown` for an incomplete scan. The refreshed alpha package's scanner observed 21 entries, 4,636,672 allocated bytes, and `backup_status=incomplete`; its warning state is correctly `unknown`, so no below-threshold claim is made. | The warning and no-budget-deletion rules are recorded and threshold regression-tested. The current incomplete scan does not establish whether the whole tree is below threshold. Class-specific long-term retention/recovery horizons remain open. |
| Permanent storage measurement | The local Vhost project read at 04:49 UTC reported 43,912 logical project bytes: 25 goals, 22 facts, 56 event receipts; 37,859 original event-payload bytes received and zero retained payload bytes. The inbox retains 18,885 logical row bytes of its 134,217,728-byte limit. Its separate control-plane view reported 3,145 logical bytes across 11 classes, 524,288 database bytes, and a 383,192-byte WAL. At 05:34 UTC, metadata-only `lstat` measured the current database at 524,288 bytes, WAL at 457,352 bytes, and SHM at 32,768 bytes; all are regular files owned by UID 1000 with mode `0600`, and the backup directory is owned by UID 1000 with mode `0700`. No contents were read. Staging was empty and complete in the earlier project read. | Logical class values remain the 04:49 observation; physical WAL/SHM values are dynamic and were remeasured at 05:34. Per-class retention/recovery horizons and permanent-database warning rules remain open. |
| Token usage | At 2026-10-28 05:57 UTC, the read-only installed `project-usage` handler (SHA-256 matches Hermes source) reports seven retained turns, six reported and one unknown, with the latest event at 05:50:47 UTC and age 380 seconds. `coverage_complete` and `tokens_complete` remain false; excluded sources are auxiliary calls outside active-turn context, auxiliary attempts without responses, and unbound sessions. No token totals were displayed. | Freshness refreshed by the local app-server turn; coverage remains incomplete and report-only. No token budget is defined or enforced. |
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

- Refresh the profile usage ledger through a real, durable project/goal-bound
  turn; a plain Hermes CLI turn is excluded. Then resolve or explicitly retain
  its known coverage gaps. No model/token budget is enforced.
- Complete class-specific long-term retention/recovery horizons for the legacy
  backup entries and permanent database classes.
- Review the local-alpha privacy sink matrix and close its listed unverified
  producer and operating-system paths.
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
