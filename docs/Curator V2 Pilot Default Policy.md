# Curator V2 Pilot Default Policy

## Approved for local alpha

- **Local reviewer/admin:** `eaglesvn` is the sole local project admin and SDE reviewer through the attended CLI bound to the current Linux UID. The CLI also requires the active account to own the ledger database before opening it, so another local account cannot review the shared alpha ledger by invoking the CLI under its own UID. This does not establish a Hermes-authenticated subject. The `renew-ssl-coding` profile reports `auth=none` and cannot approve, reject, release holds, or purge through a trusted Hermes identity until Hermes supplies an authenticated human identity.
- **Review and purge:** One explicit human review action records the SDE disposition and authorizes purge of the complete exact inventory displayed with that decision. Curator stores a distinct cleanup-authorization receipt for audit and projects both receipts canonically before deletion. The same action cannot authorize a changed or incomplete inventory. Retries may repeat only the previously approved inventory; they cannot create a new approval.
- **Retention:** Raw chat/transcript, cue, import, scratch, generated intermediate, and duplicate artifacts become eligible promptly after compact facts are recorded and any related SDE is approved or rejected. **72 hours is the hard maximum age**, even if an SDE is still pending; at that point the transient source can be purged while the SDE remains reviewable from canonical facts. Pending SDE review delays prompt expiry but does not extend the 72-hour limit. Explicit legal or operational artifact holds require a separate release and are the only local-alpha exception.
- **Privacy:** Canonical knowledge consists of compact deduplicated fact bullets and auditable decisions. Raw chats/transcripts, cues, imports, and scratch files stay temporary and are not copied into canonical facts. Missing trusted identity, incomplete inventory, or stale approval fails closed. The profile's `auth=none` state is not treated as a person or permission.
- **Hold handling:** Hold placement and release are attached to the exact artifact inventory and recorded with reviewer, time, and rationale. Held artifacts stay visible and excluded from purge/retry until a separate authorized release.
- **Host Steward:** Host Steward administration and host cleanup remain under the Hermes Core root account; CuratorMD does not execute host cleanup.

The approved values apply to local alpha only. They do not approve production
identity mapping, production retention periods, external hold discovery,
deployment recovery, or live runtime behavior.

## Still open

- Hermes-authenticated user/project identity and production role provisioning. Missing identity or `auth=none` is denied for trusted Hermes review actions. Hermes keeps authenticated subjects separate from profile IDs in [session_identity.py](/home/eaglesvn/.hermes/hermes-agent/gateway/session_identity.py).
- Production retention policy, hold discovery from deployment-owned sources, scheduled purge operations, alerting, and live-runtime evidence.
- Exact project/profile grant provisioning for a production deployment; no wildcard grants or self-registration are proposed.

The approved values above apply to local alpha only and do not close production release gates. The Curator V2 goal remains active.
