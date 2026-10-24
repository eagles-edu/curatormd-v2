# Curator V2 Local Maintenance Timer

The maintenance timer runs the existing one-shot due-purge command as the
owning user. Each pass is limited to one configured project and retries only
previously approved purge receipts whose deadlines have elapsed. The command
cannot create review decisions, release holds, or bypass backoff. A pending or
failed result exits nonzero and remains visible in the systemd journal.

## Configure a disposable or local-alpha instance

Create private instance directories at
`~/.local/state/curatormd-v2/<project-id>/` and
`~/.local/share/curatormd-v2/<project-id>/`, then copy
`deploy/systemd/user/maintenance-env.example` to
`~/.config/curatormd-v2/maintenance-<project-id>.env`. Fill every value from
the reviewed project deployment manifest, use absolute paths, and set mode
`0600`. The service template grants writes only to those instance directories.
If the configured database or project staging tree is elsewhere, add a
project-specific service drop-in with one exact `ReadWritePaths=` entry for
each required directory; do not grant write access to the whole repository.
The user manager runs the service as the same Unix account that owns the
config, database, and staging tree. Do not share one instance file across
projects.

Install the unit templates under `~/.config/systemd/user/`, reload the user
manager, then enable only the named project's timer:

```sh
systemctl --user daemon-reload
systemctl --user enable --now 'curatormd-v2-maintenance@<project-id>.timer'
```

The approved local-alpha cadence is every six hours at 00:00, 06:00, 12:00,
and 18:00, with a bounded 15-second spread and missed-run catch-up. The pass
has a five-minute execution timeout and a default batch limit of 100. Hermes
Core's readiness probe treats a timer as fresh only when a successful run
occurred within 18 hours, allowing three six-hour intervals. If the cadence
changes, update and review the health freshness window with it. Deployment
owners must review cadence, timeout,
batch size, instance paths, concurrency behavior, and account identity before
enabling it. systemd does not start a second copy while the oneshot service is
still active.

## Check and recover

```sh
systemctl --user list-timers 'curatormd-v2-maintenance@*'
systemctl --user status 'curatormd-v2-maintenance@<project-id>.service'
journalctl --user -u 'curatormd-v2-maintenance@<project-id>.service' --since today
```

The CLI emits only project identity and aggregate processed/complete/pending
counts. A nonzero exit leaves the service failed for operator inspection; it
does not authorize a new purge. Repair the cause, preserve pending receipts,
and allow a later timer pass to retry the same authorized work.

The service runs with an owner-only umask and core dumps disabled. These
settings reduce exposure from this maintenance process only; they do not
replace the wider Curator/Hermes log, trace, backup, and runtime data-flow
review.

## Vhost Manager local-alpha instance

The approved `vhost-manager-alpha` timer runs as OS account `eaglesvn` (UID
1000), every six hours at 00:00, 06:00, 12:00, and 18:00, with up to 15 seconds
of spread, a five-minute
service timeout, and a 100-receipt batch limit. Its dedicated alpha environment
points at the `renew-ssl-coding` Curator V2 CLI, the existing shared alpha
SQLite database, and `/home/eaglesvn/dockerz/renew_ssl` as the project root.
Because the database lives in
`/home/eaglesvn/.local/share/curatormd-v2-alpha/` and the project config puts
staging under `/home/eaglesvn/dockerz/renew_ssl/.curatormd-v2/staging/`, its
service drop-in grants write access to those two exact directories.

This host's unprivileged user manager cannot apply `PrivateDevices` or
`ProtectKernelModules`; those two directives are omitted from the user-unit
template. Other configured service restrictions remain active. The initial
one-shot run succeeded and found no due purge or expiry targets. The repeating
timer is enabled; its success is local scheduler evidence only. Journal-only
failures and missing alert delivery remain; production scheduling is outside
this development-only alpha scope.

This unit does not provide dead-letter delivery, an external alert recipient,
or a restart drill. For the local alpha, the Hermes source readiness probe
reports `purge_scheduler` ready after observing the enabled timer and a recent
successful run. Its journal-only `alert_delivery` probe checks that both unit
streams target journald and that the user journal can be queried. This does
not verify an alert recipient or external monitoring, and the changed Hermes
checkout is not the active `/usr/local/lib/hermes-agent` install. Production
use remains behind the owner decisions and failure-injection cases in
[the release gate](release-gates-v2.md).
