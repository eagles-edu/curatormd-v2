# Durable knowledge procedure

1. State the problem and observable success criteria before implementation.
2. Inspect the current repository state and relevant instructions; preserve
   unrelated changes and private evidence.
3. Separate direct observations, test evidence, proposals, and live-runtime
   claims. A unit test does not prove deployment or end-to-end behavior.
4. After verification, put the newest fact or decision at the top of
   `HISTORY.md`; record a repeatable prevention lesson at the top of
   `LESSONS-LEARNED.md` only when a failure and remedy are verified.
5. Keep operating rules in `AGENTS.md` and repeatable procedures in this file.
   Avoid duplicate canonical statements; link to the implementation plan or
   contract where detailed requirements already live.
6. Leave incomplete requirements explicitly open. Never convert a proposal,
   local check, or operator assertion into a completed runtime claim.
7. Verify the resulting files, `git diff --check`, and Curator persistence
   status. Do not stage, commit, publish, or delete evidence automatically.
8. When the user reports a problem, keep working through diagnosis, repair, and
   an observable success check. A failed or forbidden path is evidence to find
   the supported route or repair the underlying authorization; it is not a
   reason to stop while useful authorized work remains. Do not abandon active
   work for an unrelated request; finish it first unless the new request
   changes its scope or provides information needed to proceed.
9. Show every human-facing Curator V2 date and time in `Asia/Ho_Chi_Minh`
   with an explicit `+07:00` offset. When converting an existing timestamp,
   convert the instant; never replace a UTC label without adjusting the clock
   and date. Keep UTC normalization for machine storage and calculations, and
   convert it at Markdown, report, and UI display boundaries. Use the local
   calendar date for daily backup names and other local-day policies.
10. When `eaglesvn` explicitly requests a commit and push of the entire
   worktree, inspect tracked and untracked changes, include the whole worktree,
   then commit and push it to the configured upstream. Do not silently stage
   only selected files or leave requested changes unsynced. This explicit
   instruction overrides the normal requirement to wait for publication
   authorization. After each item is completed, commit and push when this
   standing instruction applies.
11. Before a push, inspect the complete outgoing change set for server/host
    configuration, firewall rules, credentials, private runtime logs, or
    other operational details. Omit those files from publication and ask
    `eaglesvn` before including them. A request to push the whole worktree does
    not override this check. Never publish first and ask afterward.
12. Approved persistence destinations

    - `persistence/HISTORY.md`
    - `persistence/LESSONS-LEARNED.md`
    - `persistence/SOP.md`
    - `persistence/AGENTS.md`

<!-- curatormd-v2:sde:4e4b1a5f042091c20e6002ce8953b08505bc499e07f4a6fc16560e4a1e809ad7:start -->
### The current Curator V2 health read is unknown because all seven host dependencies are unobserved, despite a complete empty database queue snapshot\.

- SDE: `1ca610bc21984344b311a1706bd58679`
- Significance: 2 / 5
- Significance use: guides future compression, summarization, archiving, and culling decisions.
- Decision: approved
- Reviewed: `2026-11-11T14:54:52+07:00`
- Reviewer: `local-uid:1000`
- Review rationale: Owner approved the SDE entry for persistence/HISTORY\.md, persistence/LESSONS\-LEARNED\.md, persistence/SOP\.md, persistence/AGENTS\.md\.
- Decision receipt: `0cd607fe00e44ef7960d93a3b09ceec7`
- Project ID: `curatormd-v2-dev-alpha`
- Receipt binding SHA-256: `0ee2ff6bca0b00b4a4a0262995610d47f5c87815b85c5b2801c88fc06fb39b34`
- Project config SHA-256: `46c099c7182a553a53ce112e1612ae0f425b24def9361538a885a86958f0b86c`
- Draft SHA-256: `ee158597bf7b041f5b90edcec181ff06e745254511df2f3e5125f4cbeced60fb`
- Supporting facts SHA-256: `c91672c4ace42e7f386dde09df9b851d6d8f4c0112ebff85175a44e81ea5e047`
- Evidence state SHA-256: `7e8d3fc3a22e0d28f5b596e39c527df2de904606b3e54f38c8ee31009fad3088`
- Destination baseline SHA-256: `b67ff039c0396294ffed454f2acc85a47adb25f5d69928da14788805509fc69b`
- Artifact inventory SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Dependency map SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Task started: `2026-11-11T14:42:27+07:00`
- Successfully completed: `2026-11-11T14:49:12+07:00`
- Problem / plan task: The current Curator V2 health read is unknown because all seven host dependencies are unobserved, despite a complete empty database queue snapshot\.
- Cleanup authorization reviewer: `local-uid:1000`
- Cleanup authorization time: `2026-11-11T14:54:52+07:00`
- Cleanup manifest SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`

#### Completed successfully

- The host\-configured curator\-health\-dashboard proof passed for curatormd\-v2\-dev\-alpha: the profile\-bound Hermes snapshot was fresh and healthy with all seven dependencies healthy and no gates; the independent queue snapshot was complete with zero event and operational counts\. The earlier direct Codex project\_health result was unknown because that caller had no host dependency context\.

#### Lessons learned

- When Curator health appears unknown from a direct Codex call, use the project\-bound Hermes dashboard probe and separate queue snapshot before diagnosing degradation\.

- Future utility: When Curator health appears unknown from a direct Codex call, use the project\-bound Hermes dashboard probe and separate queue snapshot before diagnosing degradation\.

#### Approved persistence destinations

- `persistence/AGENTS.md`
- `persistence/HISTORY.md`
- `persistence/LESSONS-LEARNED.md`
- `persistence/SOP.md`
<!-- curatormd-v2:block-sha256:66d00dd9c140c47ffc7a66a58db158f9d78cd78c26c7003fc0b32b43fcfd38fb -->
<!-- curatormd-v2:sde:4e4b1a5f042091c20e6002ce8953b08505bc499e07f4a6fc16560e4a1e809ad7:end -->
