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
| Manual DNS renewal | `acme_dns_manual_nginx_swap.sh`; the exit hook calls `script_result_bridge.py`. | Challenge output is shown to the operator but excluded from Curator. ACME account/certificate state stays under `ACME_HOME`; Nginx configuration and temporary swap paths stay under `/etc/nginx`; the lock stays under `/run/lock`; issue/renew and served-certificate temporary files use `mktemp`; a persistent status log is written under `/var/log`. | The bridge sends only producer ID, operation UUID, and exit code. The script removes tracked temporary files on exit. `redact_manual_dns_log.py` filters recognized TXT values, credentials, token-like values, and PEM private-key blocks from the persistent log. The Vhost/OS owner retains the log; this matrix does not set its retention period or claim universal secret detection. |
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

Consumer checkout HEAD: `7d2b10f5433cfe566fc560741bbc9401265176f4` (dirty
working tree). `.curatormd-v2.toml` SHA-256:
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
`7d2b10f5433cfe566fc560741bbc9401265176f4`; the Curator config SHA-256 remains
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

## Remaining boundaries

This closes the local producer/source-class and out-of-root disposition audit
for the approved Vhost development scope. It does not close the separate
retention-policy decision for persistent logs, human disposition of operation
goals, real certificate renewal, production scheduling/recovery, or release
approval. Those remain separate gates in `release-gates-v2.md`.
