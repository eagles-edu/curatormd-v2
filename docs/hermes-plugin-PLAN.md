# Codex turn middleware for Curator workflows

## Summary

Use a profile-scoped Codex app-server proxy to observe one start/end pair per Codex turn. Record the pair as session telemetry and link it to the plan children or one-off tasks selected by Curator’s existing intake workflow. A turn may link to multiple tasks; a task may span multiple turns and sessions.

First verify the proxy path in an isolated profile. Use a minimal Hermes compatibility bridge only for capabilities the proxy cannot reliably obtain.

## Implementation

- Configure the affected Hermes profiles’ `model.codex_bin` to launch a transparent stdio proxy around the real Codex binary. Forward version checks, JSON-RPC, streaming, cancellation, and process exit behavior unchanged. Observe turn and task identifiers without persisting prompts, responses, or tool output.
- Pin each proxy to its profile and project using local account identity and profile-owned configuration. Use the inherited `HERMES_SESSION_ID` where present; verify it in live Hermes sessions. A static secret may authenticate a local producer if needed, but it does not select a goal. Preserve the existing project grants.
- Extend Curator with a session-level turn observation and separate links to task goal IDs. Capture links from successful Curator lifecycle or fact calls observed during that turn. Keep the existing goal-bound event API compatible while pending old outbox events drain.
- Store observations and links in a profile-local durable outbox with stable IDs, ordered retries, and matching receipt checks. Leave uncorrelated or failed delivery visibly pending; do not guess a task or treat a turn outcome as task-completion evidence.
- Follow the existing intake lifecycle unchanged: advance between plan children, keep one-off facts on their own goals, defer and later resume the exact interrupted child, and preserve owner-reviewed SDE decisions.
- If the proxy cannot reliably obtain session identity or successful task-call results, add only the missing host-provided context or observation seam in Hermes. Keep that bridge as a small, version-checked patch.

## Verification and rollout

- Test transparent proxy behavior, including long streams, version checks, interruption, subprocess failure, and concurrent sessions.
- Test a plan child, child-to-child transition within one turn, an interrupting one-off and subsequent resume, an unrelated one-off, and a turn with no selected task. Verify task links and existing lifecycle records remain distinct.
- Test profile isolation, authorization, duplicate receipts, retries, restart recovery, legacy pending events, and absence of prompt or response content in stored observations.
- Validate the Curator and Renew SSL profiles, restart through the attended password prompt, and verify a real turn and its task links in Curator. Report live readback separately from local test results.

## Assumptions

- GPTMD remains without V2; Feishu remains untouched.
- The proxy and profile configuration belong in the Hermes account or consuming project; Curator’s shared event contract belongs in the Curator backend.
- No commit, push, unrelated cleanup, or change to the reviewed diagnostic documents is included.
