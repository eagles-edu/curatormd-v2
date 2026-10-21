# Curator V2 Pilot Default Policy

## Approved for local alpha

- **Local reviewer/admin:** `eaglesvn` is the sole local project admin and SDE reviewer through the attended CLI bound to the current Linux UID. This does not establish a Hermes-authenticated subject. The `renew-ssl-coding` profile reports `auth=none` and cannot approve, reject, release holds, or purge through a trusted Hermes identity until Hermes supplies an authenticated human identity.
- **Review and purge:** The same explicit human review action approves disposition and purge of only the exact displayed artifact inventory, after canonical facts/decision receipts are durable. Retries may repeat only that previously approved inventory; they cannot create a new approval.
- **Retention:** Raw chat/transcript, cue, import, scratch, generated intermediate, and duplicate artifacts become eligible promptly after compact facts are recorded and any related SDE is approved or rejected, with a 72-hour maximum-age fallback. Pending SDE review pauses expiry until an authorized reviewer decides. The SDE decision clears only that review hold; explicit legal or operational artifact holds require a separate release. A maximum-age threshold does not override those holds.
- **Hold handling:** Hold placement and release are attached to the exact artifact inventory and recorded with reviewer, time, and rationale. Held artifacts stay visible and excluded from purge/retry until a separate authorized release.
- **Host Steward:** Host Steward administration and host cleanup remain under the Hermes Core root account; CuratorMD does not execute host cleanup.

## Still open

- Hermes-authenticated user/project identity and production role provisioning. Missing identity or `auth=none` is denied for trusted Hermes review actions. Hermes keeps authenticated subjects separate from profile IDs in [session_identity.py](/home/eaglesvn/.hermes/hermes-agent/gateway/session_identity.py).
- Production retention policy, hold discovery from deployment-owned sources, scheduled purge operations, alerting, and live-runtime evidence.
- Exact project/profile grant provisioning for a production deployment; no wildcard grants or self-registration are proposed.

The approved values above apply to local alpha only and do not close production release gates. The Curator V2 goal remains active.
