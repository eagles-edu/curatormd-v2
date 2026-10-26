# Vhost Manager producer and artifact coverage

## Scope and ownership

This review covers the approved single-repository Vhost Manager development
alpha and its current dirty source snapshot. The owner confirmed the standalone
workflow scope on 2026-10-25 and directed that manual DNS challenge values,
passwords, keys, and raw command output must not be recorded verbatim. The four
standalone producers below are the complete approved standalone set. Vhost and
OS artifacts remain owned by the consumer/host; Curator does not infer scan or
purge roots from them. Only bounded operation outcomes are sent to Curator.

## Producer and artifact matrix

| Producer | Source and publication point | Artifact classes and destinations | Curator record and disposition |
| --- | --- | --- | --- |
| Site apply, rollback, archive, and failed operations | Vhost routes in `server/index.cjs`, `server/core.cjs`, and `server/operations.cjs`; the operation snapshot is durable before the scoped bridge call. | Site/config files, site account/webroot, operation manifests and archive/backup data under configured Vhost paths; temporary route fixtures in disposable tests. | `apply_bridge.py` sends bounded operation ID, kind/title, domain, state, and exit code. Vhost owns these outputs. Existing disposable route evidence covers success, rollback, archive, failure, outage retry, replay, and interrupted operation recovery. |
| Scheduled ACME renewal | Root crontab invokes `/usr/local/sbin/renew-dev-ssl-acme-cron-curator`; its SHA-256 matches `vhost-manager/curatormd-v2/acme_cron_bridge.sh`. The bridge saves an operation before ACME execution and queues an outcome for Vhost receipt processing. | ACME account/certificate state under the configured ACME home; Vhost operation and pending-result state; system log/cron boundary. Provider-side DNS and CA state are outside the process boundary. | Curator receives a bounded outcome through the Vhost bridge. ACME state and logs stay Vhost/OS-owned. The schedule source is fingerprinted; this review did not run a scheduled renewal. |
| Manual DNS renewal | `acme_dns_manual_nginx_swap.sh`; the exit hook calls `script_result_bridge.py`. | Challenge output is shown to the operator but excluded from Curator. ACME account/certificate state stays under `ACME_HOME`; Nginx configuration and temporary swap paths stay under `/etc/nginx`; the lock stays under `/run/lock`; issue/renew and served-certificate temporary files use `mktemp`; a persistent status log is written under `/var/log`. | The bridge sends only producer ID, operation UUID, and exit code. The script removes tracked temporary files on exit. `redact_manual_dns_log.py` filters recognized TXT values, credentials, token-like values, and PEM private-key blocks from the persistent log. The Vhost/OS-owned log is subject to the approved 72-hour maximum-age cleanup; Curator never reads or deletes it. Redaction is not claimed to detect every possible secret. |
| Batch renewal | `renew_all_domains.sh`; after explicit batch confirmation, its exit hook sends one batch result. Each child renewal remains the manual renewal producer above. | Reads the generated inventory; progress state is stored under `/var/lib/acme-dns-manual-nginx-swap`; the batch lock is under `/run/lock`; child ACME state/log/temp files use the manual-renewal destinations. | One bounded batch outcome is sent; no domain list, progress file, child output, or challenge value is forwarded. Progress and locks remain Vhost/OS-owned. |
| Inventory refresh | `update_domain_inventory.sh`; its exit hook sends one refresh result. | Reads the source inventory and Nginx enabled-site entries; certificate classification files are temporary under `TMPDIR`; generated Markdown is written to the requested output path (the default is the consumer checkout). | Only producer ID, operation UUID, and exit code are sent. The inventory Markdown is Vhost-owned and remains outside Curator staging and purge. |
| Nginx vhost setup | `setup_nginx_vhost.sh`; its exit hook runs after apply or rollback. | Temporary config is created beside the target Nginx config and atomically installed; the enabled-site symlink, webroot challenge directory, and lock stay in their configured `/etc/nginx`, `/home`, and `/run/lock` locations. | Only producer ID, operation UUID, and exit code are sent. Config and webroot files remain Vhost/OS-owned. |
| Security counters and Hermes lifecycle hook | `server/security.cjs`; `hermes_hook/handler.py` and `HOOK.yaml`. | Security state remains Vhost-owned. Hook arguments are bounded lifecycle metadata; no transcript or raw tool output is a Curator artifact. | Security counters are not a Curator producer. The hook sends only the configured project event and waits for its exact receipt. |

No standalone artifact class is absent by inference. Vhost/OS ownership is the
approved disposition for all classes outside the configured Curator staging
root. Curator's scan and purge roots were not expanded. The active root cron
entry was checked read-only on 2026-10-25: it invokes the wrapper above at
01:52, 07:52, 13:52, and 19:52; the installed wrapper and repository bridge
hashes match. This establishes source identity and schedule configuration, not
a renewal run or host/provider filesystem coverage.

## Disposable workflow evidence

Six focused tests pass: the bounded result-queue limit; successful batch
renewal with a fixture child; successful inventory refresh with fake TLS tools;
successful Nginx setup in private mount namespaces; manual DNS issue failure
and operator restore after synthetic challenge output; and the streaming log
redaction canary test. The manual DNS fixture verifies that the challenge
canary is absent from its persistent log and result arguments, the tracked
temporary output is removed, and the staged link is restored. No real DNS,
certificate, host Nginx, or system service was changed.

`strace -f -yy` traced the six focused test process trees for file creation,
replacement, removal, and open-for-write operations. It reported 455 such
operations: 57 in the manual DNS fixture, 53 in the Nginx setup fixture, 39 in
the batch fixture, 23 in the inventory fixture, 8 through the fixture Nginx
mount, 5 through the fixture state mount, 3 through the lock mount, and 1
through the fixture log mount. Temporary roots were private fixtures; the trace
was removed after deriving these counts. Sixty operations were outside those
classified fixture paths and remain unclassified at the test/runtime boundary;
they are not claimed as Vhost workflow artifacts. The trace did not observe a live service,
host cron execution, external DNS provider, or certificate authority.

The disposable managed HTTP/MCP contract's standalone producer loop and
inventory-refresh assertions ran before that larger test was interrupted in a
later rollback-replay subprocess. That interrupted run is not reported as a
green full contract suite. Prior completed route and managed-hook evidence
remains documented in `release-gates-v2.md`.

## Freshness binding

Consumer checkout HEAD: `1924fa2` (the reviewed V2 files are committed; unrelated
working-tree changes remain). `.curatormd-v2.toml` SHA-256:
`4f3a34e84832b7e8ccfe4e91a68b0664c6aa603409318197f0b44e6454ece44a`.
The configured Curator adapter API version is `1`.
The 23-file sorted source/config/adapter/test manifest SHA-256 is
`79ce6b73d3a4d52a34b3931a1d74ce42221be4f604967756ed88529454d42128`.
The manifest covers the consumer config, four standalone utilities and log
filter, Vhost server/UI producers, Curator adapters and Hermes hook, plus the
focused producer tests. Any included file or config change invalidates this
review and requires a new source review. The dirty checkout is not a release
revision.

## 2026-10-26 standalone snapshot recheck

The owner directed closure of the standalone-script coverage item. The current
dirty checkout remains at HEAD
`1924fa2`; the Curator config SHA-256 remains
`4f3a34e84832b7e8ccfe4e91a68b0664c6aa603409318197f0b44e6454ece44a`. A fresh
24-file sorted source/config/adapter/test manifest SHA-256 is
`390823695cf388aa91dda1003ae3d5b18f131f42990f0a09bc38b4e31f7d51f2`.
It covers the configuration, the four standalone utilities and log filter,
Vhost server/UI producer files, Curator adapters and Hermes hook, and six
focused tests. The digest is computed by sorting repository-relative paths and
hashing each `path NUL content-SHA256 newline` record.

All six focused tests pass on this checkout: bounded result queue, batch
renewal, inventory refresh, Nginx setup, manual-DNS failure/restore cleanup,
and log redaction. `strace -f -yy` captured the three focused test groups in
disposable state. The evidence covers the local standalone development
workflows and content-free receipt path. It does not establish live certificate
renewal, host/provider behavior, universal secret detection, or log retention.
The prior owner-reviewed out-of-root dispositions remain bounded to this
approved Vhost development scope. The Curator standalone-coverage checkbox was
already checked; this refresh changes no checklist count.

## 2026-10-26 manual DNS and root cron closure refresh

The owner-directed local Vhost alpha audit now includes a successful disposable
manual-DNS issue/renew path and an invocation of the installed root cron
wrapper. No real DNS provider, ACME account, certificate, Nginx configuration,
or system service was used or changed.

The manual-DNS success fixture uses fake ACME, fake authoritative/public DNS,
fake TLS tools, and private filesystem mounts. It verifies both challenge
propagation checks, fixture certificate installation, staged-link retirement
and replacement by the enabled-site symlink, cleanup of tracked temporary
output, redaction of challenge values from the persistent fixture log, and a
result call containing only the producer ID, operation UUID, and exit code.
The challenge values stay in the disposable fixture and are not copied into
Curator documentation or records.

The root crontab still invokes
`/usr/local/sbin/renew-dev-ssl-acme-cron-curator` at 01:52, 07:52, 13:52, and
19:52. Its installed SHA-256 and repository bridge SHA-256 both equal
`28afc265f2a0193d443bd90569865f3bf5c1d00620930f41caab150d8c2a6f25`. A test
invoked that installed wrapper with fake ACME exit status 19, a temporary
pending directory, and a loopback-only mock receipt endpoint. It verified the
exact bounded `operationId`/`exitCode` receipt, acknowledged queue cleanup,
mode 0700 on the queue directory, and absence of the ACME output canary from
the wrapper's output and HTTP receipt. This is an invocation of the installed
wrapper, not proof that cron itself ran it or that real renewal succeeds.

The eight focused producer tests pass, including the new success and installed
wrapper cases. A refreshed 24-path source/config/adapter/test manifest for the
Vhost application sources, Curator bridges, standalone utilities, and focused
tests has SHA-256
`a5635ed8cbda33811a12603f6aa4453369a5c240c75c11d812db78c451cf8cfb`.
The Vhost checkout remains dirty at `1924fa2`; this digest binds the reviewed
working-tree paths, not a clean release revision.

The approved out-of-root disposition remains: Vhost/OS keeps ownership of its
ACME state, certificate/key outputs, Nginx files, operational logs, inventories,
and temporary state; Curator neither scans nor purges those paths and receives
only bounded outcome metadata. The approved local manual-DNS log expiry is
implemented by a root-owned Vhost/OS service; it does not route logs through
Curator. The local producer/artifact audit and local log-expiry policy are
closed for the approved single-repository development alpha. Real scheduled
ACME execution, provider/CA behavior, production retention controls, human
disposition of operation goals, and release approval remain separate gates.

## 2026-10-26 Vhost/OS-owned manual-DNS log expiry

The owner-approved six-hour timer runs a root service that removes only regular
direct-child files matching `acme-dns-manual-*.log` under `/var/log`. It never
opens or prints file contents and reports only a removal count to the journal.
The cleanup threshold is 65 hours 44 minutes 59 seconds, leaving a 15-minute
safety margin for the timer's maximum six-hour interval plus randomized spread
under normal operation. The source is in
[`deploy/acme-log-expiry`](</home/eaglesvn/dockerz/renew_ssl/deploy/acme-log-expiry>).

The installed timer and service are enabled and active. The first run removed
two matching logs older than 72 hours; a path-only count then found zero
matching regular log files. The two focused cleanup tests pass, including
symlink, filename, and age boundaries. This is Vhost/OS cleanup outside the
Curator staging root; Curator received no log contents. The schedule does not
prove real ACME execution, and a powered-off host cannot clean files while it
is stopped.

The sorted six-path cleanup implementation/test manifest is bound by SHA-256
`a3b07fadb8a08b50557b20f7008f86bcc0c90906d2991c2c7b2f46f65121da3f`. The
installed script, service unit, and timer unit each match their repository
source hash. This supplement does not change the existing 24-path Vhost
producer/source manifest.

## 2026-10-26 current-snapshot audit recheck

All eight focused producer tests pass on the current Vhost checkout, including
manual-DNS success and failure/restore, installed root-wrapper invocation,
batch renewal, inventory refresh, Nginx setup, queue limit, and log redaction.
The installed root wrapper was explicitly used for the cron-bridge test with
fake ACME and a loopback receipt endpoint. Its SHA-256 matches the repository
bridge (`28afc265f2a0193d443bd90569865f3bf5c1d00620930f41caab150d8c2a6f25`),
and read-only crontab inspection confirms the four daily schedule entries.

The current checkout remains dirty at HEAD `1924fa2`; the Curator config hash
remains `4f3a34e84832b7e8ccfe4e91a68b0664c6aa603409318197f0b44e6454ece44a`.
A fresh sorted 24-path source/config/adapter/test manifest uses the established
`path NUL content-SHA256 newline` record format and has SHA-256
`1954612b71ceeef4a2fe274b5eed30c5ad7a2b6778c66767213b8c91696bd075`. It binds
the reviewed working-tree snapshot, not a clean release revision. The approved
disposition remains Vhost/OS ownership for all out-of-root artifacts; Curator
does not scan or purge them and receives bounded outcomes only. These results
close the local producer/artifact audit for the approved single-repository
alpha. No scheduled cron run or real DNS/certificate renewal is claimed.

## 2026-10-26 current verification

The eight focused producer regressions pass on the current consumer snapshot:
manual-DNS success and failure/restore, the installed root-wrapper fake-ACME
receipt path, batch renewal, inventory refresh, Nginx setup, bounded result
queue, and log redaction. The cron test was explicitly run with
`CURATOR_V2_CRON_BRIDGE=/usr/local/sbin/renew-dev-ssl-acme-cron-curator`, so it
exercises the installed wrapper; the test uses fake ACME and a loopback receipt
endpoint. Read-only root crontab inspection shows entries at 01:52, 07:52,
13:52, and 19:52. Installed and source wrapper SHA-256 values match:
`28afc265f2a0193d443bd90569865f3bf5c1d00620930f41caab150d8c2a6f25`.

Both log-expiry regression tests pass. The root-owned
`expire-manual-dns-logs.timer` is enabled and active on the six-hour schedule;
it enforces the approved 72-hour maximum for matching Vhost/OS-owned logs.
Owner-approved disposition keeps ACME state, certificate/key outputs, Nginx
files, operational logs, inventories, and temporary state outside Curator
scan and purge; only bounded outcomes enter Curator. This is the approved
single-repository local alpha scope.

A fresh manifest covers 33 sorted paths: the consumer config, four standalone
producers and redactor, Vhost server/UI producer sources, Curator bridges and
Hermes hook, eight focused producer tests, and the log-expiry implementation,
units, installer, documentation, and tests. Its digest is
`0d7f848f6312776d74abb7b7b9659c6b0c94bc4fc6bfef56f487883125fa8645`, using
the `path NUL content-SHA256 newline` format. It binds the current dirty working
tree at HEAD `1924fa2`, not a clean release revision. Local producer/artifact
coverage and the owner disposition are closed for this alpha. Actual scheduled
ACME execution, real DNS/certificate renewal, and production controls remain
separate runtime/release gates.

## Remaining boundaries

This closes the local producer/source-class and out-of-root disposition audit
and the approved local 72-hour log-expiry control for the Vhost development
scope. Human disposition of operation goals, real certificate renewal,
production scheduling/recovery and retention controls, and release approval
remain separate gates in `release-gates-v2.md`.

## 2026-10-26 current-snapshot recheck

Re-ran the targeted producer tests on the current Vhost worktree. Seven tests
pass across the cron bridge, manual-DNS success and failure/restore, batch
renewal, inventory refresh, Nginx setup, and bounded script-result bridge. Two
manual-DNS log-expiry tests also pass. The cron test explicitly selects the
installed `/usr/local/sbin/renew-dev-ssl-acme-cron-curator` and uses fake ACME
plus a loopback receipt endpoint. Read-only checks confirm the four root cron
entries, matching installed/source bridge hashes, and the enabled, active
six-hour log-expiry timer. `git diff --check` passes in both repositories.

The refreshed sorted 33-path source/config/adapter/test/expiry manifest is
SHA-256 `1a3fe9f4c52076dcf0097690cd2544e57880987a0a134fb79b555ac4c68ac1a4`,
computed from `path NUL content-SHA256 newline` records. It includes the newly
added disposable manual-DNS success case and installed-cron-wrapper test. It
binds the current dirty Vhost worktree, not a clean release revision.

This recheck confirms the already-closed local source/artifact audit and the
owner-approved Vhost/OS disposition: out-of-root artifacts remain outside
Curator scan and purge, with only bounded outcomes sent to Curator. It does not
claim that cron ran on schedule or that real DNS/certificate renewal succeeded.

## 2026-10-27 alpha audit confirmation

The Vhost checkout remains at HEAD `1924fa2`. The manual-DNS success fixture
added to the dirty snapshot is bound by SHA-256
`6ad60570fdeec8535d9522eb3c66df4fb96e24c35d792927f619ee718a583cfd`. Five
standalone workflow tests pass on this snapshot, including manual-DNS success
and failure/restore; the installed root-wrapper fake-ACME receipt test and
bounded queue test pass; both log-expiry tests pass. The local audit remains
closed for the approved one-repository alpha. Shared multi-consumer use is out
of scope. Vhost Manager is a local utility; public hosting and a public
application endpoint are not alpha requirements. Real scheduled cron and
provider/CA behavior remain open only for validating the certificate-renewal
feature; production retention remains a deployment/release gate.

## 2026-10-27 local staging-warning configuration

The owner set the `vhost-manager-alpha` staging warning threshold to
262,144,000 bytes (250 MiB), warning-only, and clarified that project file count
is irrelevant. Its consumer-owned `.curatormd-v2.toml` now contains only the
byte threshold; the current config SHA-256 is
`a37448f38683c864480d4f90db8fc6a6b694311679b598979f86ff574713f746`. Project
ID, staging root, read scope, adapters, and persistence targets are unchanged.

The 18-test Curator staging suite passes, including regressions proving writes
continue above the project warning threshold and exact retries remain
idempotent; per-file/per-goal hard limits and incomplete-inventory checks remain
in force. The prior 33-path manifest predates this config change and is
historical. No real renewal, service restart, or artifact deletion was
performed.

The expiry-proposal path now returns eligible artifacts oldest-first by their
durable staging timestamps, using path as the stable tie-breaker. Held and
eligible partitions preserve that order. This is read-only proposal ordering;
deletion still requires the reviewer's exact-inventory approval. The 19-test
storage/expiry suite covers the FIFO order and confirms discovery leaves both
files present. The 17 staging-writer tests also pass against the updated code.
