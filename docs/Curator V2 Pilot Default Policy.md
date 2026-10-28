# Curator V2 Pilot Default Policy

## Approved for local alpha

- **Local reviewer/admin:** `eaglesvn` is the sole local project admin and SDE reviewer through the attended CLI bound to the current Linux UID. The CLI requires the active account to own the ledger database. This is the complete identity requirement for the local, single-user utility; no separate Hermes person identity is required.
- **Review and purge:** One explicit human review action records the SDE disposition and authorizes purge of the complete exact inventory displayed with that decision. Curator stores a distinct cleanup-authorization receipt for audit and projects both receipts canonically before deletion. The same action cannot authorize a changed or incomplete inventory. Retries may repeat only the previously approved inventory; they cannot create a new approval.
- **Retention:** Raw chat/transcript, cue, import, scratch, generated intermediate, and duplicate artifacts become eligible promptly after compact facts are recorded and any related SDE is approved or rejected. **72 hours is the hard maximum age** for those live transient source files, even if an SDE is still pending; at that point the transient source can be purged while the SDE remains reviewable from canonical facts. Pending SDE review delays prompt expiry but does not extend the 72-hour limit. Explicit legal or operational artifact holds require a separate release. The owner-approved seven daily SQLite backups may contain raw event payloads still pending retry or quarantine. Each snapshot is retained only as one of the newest seven daily copies, but a still-pending payload can be copied into each new snapshot; no maximum age for unresolved event payloads has been approved. This recovery exception does not make payloads canonical facts.
- **Privacy:** Canonical knowledge consists of compact deduplicated fact bullets and auditable decisions. Raw chats/transcripts, cues, imports, and scratch files stay temporary and are not copied into canonical facts. Missing trusted identity, incomplete inventory, or stale approval fails closed. The profile's `auth=none` state is not treated as a person or permission.
- **Hold handling:** Hold placement and release are attached to the exact artifact inventory and recorded with reviewer, time, and rationale. Held artifacts stay visible and excluded from purge/retry until a separate authorized release.
- **Staging budget:** For `vhost-manager-alpha`, monitor Curator's configured temporary staging area at 262,144,000 bytes (250 MiB); this is a warning threshold, not a write limit, and there is no project file-count limit. This does not limit Vhost's normal application writes or renewal operations. At 75% of the byte threshold, project health emits `staging_budget_warning`; at or above the threshold it emits `staging_budget_reached` as a critical warning. Curator continues accepting staged files above the threshold, subject to independent per-artifact and per-goal hard limits. A complete inventory is still required to report threshold status. Warnings do not delete or overwrite artifacts. FIFO means oldest-first ordering for a cleanup proposal only; it never authorizes deletion. Purge still requires approval of the exact complete inventory and honors artifact holds. External alert delivery is not configured by this policy.
- **Database backup:** The six-hour local maintenance run creates one verified SQLite snapshot per UTC day in the private Curator state directory and retains the newest seven daily copies. Those snapshots may contain event payloads still pending retry or quarantine. If the event remains pending, each new daily snapshot can carry the payload forward; after it is scrubbed from the live ledger, snapshots that still contain it roll out within seven days. It prunes older copies only after the new snapshot passes integrity checks. Restore is manual: `eaglesvn` selects the exact backup and approves restoring it to a new path. Curator never replaces the active database or switches to a restored copy automatically. **Local verification (2026-10-28 09:20 +07):** the enabled timer's latest run exited successfully with `backup_status=verified`; the installed daily-backup function and maintenance entrypoint match the current source, and the service points to the dedicated V2 virtualenv.
- **System of record:** SQLite is authoritative for structured goals, facts, and receipts. Consumer `persistence/HISTORY.md` is a readable projection. On mismatch, preserve both and wait for `eaglesvn` to review; only then may Markdown be regenerated from SQLite. Never restore SQLite from Markdown automatically.
- **Host Steward:** Host Steward administration and host cleanup remain under the Hermes Core root account; CuratorMD does not execute host cleanup.

## Still open

- Remaining local SQLite/staging failure cases.
- Complete permanent-data policy and local warning levels beyond the approved staging threshold. The installed bounded V2 scanner measures the current backup tree without reading contents or following symlinks: 21 observed entries, 19 regular files, 4,618,625 observed logical bytes, and 4,636,672 observed allocated bytes. It recognizes one 524,288-byte daily snapshot and reports 20 unclassified entries; two regular files and both directories are not owner-only, so inventory status remains incomplete. By name/type only, the other entries are three older SQLite snapshots, eight SQLite WAL/SHM sidecars, five package rollback archives, one YAML profile-config snapshot, one VS Code settings snapshot, and two prior VS Code extension-backup directories. Archive and settings contents were not opened. No entries were moved, changed, or deleted. Retention and warning thresholds for this recovery material still need owner review.

The following breakdown uses entry type and filename suffix only. File contents
were not read; directory entries have no regular files beneath them in this
bounded scan.

| Class | Entries | Logical file bytes | Allocated bytes | Entries not owner-only |
| --- | ---: | ---: | ---: | ---: |
| Daily SQLite snapshot | 1 | 524,288 | 524,288 | 0 |
| Other SQLite snapshots | 3 | 1,060,864 | 1,060,864 | 0 |
| SQLite WAL/SHM sidecars | 8 | 131,072 | 131,072 | 0 |
| Package rollback archives | 5 | 2,893,904 | 2,908,160 | 1 |
| YAML configuration snapshot | 1 | 3,264 | 4,096 | 0 |
| VS Code settings snapshot | 1 | 5,233 | 8,192 | 1 |
| Prior extension-backup directories | 2 | 0 | 0 | 2 |
| **Total** | **21** | **4,618,625** | **4,636,672** | **4** |

The approved values above define the supported local development utility. No multi-user or public-service behavior is required.
