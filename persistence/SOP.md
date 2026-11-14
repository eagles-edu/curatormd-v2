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
13. Never publish an SDE proposal with an empty `completed` field. Build that
    field from supported task facts: changes, research, verification, or an
    explicitly owner-reported outcome. Label owner reports as unverified and
    historical verification as not current proof; do not turn either into a
    passing-evidence claim. If the candidate's matching outline or a grounded
    completion fact is unavailable, withhold the review document update and
    surface the projection failure instead of writing an empty proposal.
14. For periodic health reads, keep the bounded freshness window at least
    three refresh intervals and align the backend, UI parser, and dashboard
    proof. Test a delayed refresh inside the window and an expired probe beyond
    it. Missing, malformed, unavailable, and expired probes remain unknown;
    the margin prevents ordinary scheduling jitter from flapping healthy state
    without extending it indefinitely.
15. For SQLite-backed scheduled work, verify both `integrity_check` and
    `foreign_key_check`. A clean page-integrity result does not prove that a
    composite foreign key has a valid unique parent key. Reproduce failures
    with the exact relation shape, make the migration idempotent, test scoped
    references, then rerun the configured service and profile-bound health
    probe.

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

<!-- curatormd-v2:sde:bad69059631a32e63e2b2963977d64a26ac0c56f63935bdf3a1a6850e14be841:start -->
### Complete remaining open requirements in Curator V2 at docs/curator\-v2\-plan\.md and docs/Repair V2 dashboard health and queue feeds PLAN\.md\.

- SDE: `10cb433892ef4c059c0801ffd5f279bb`
- Significance: 4 / 5
- Significance use: guides future compression, summarization, archiving, and culling decisions.
- Decision: approved
- Reviewed: `2026-11-12T23:15:52+07:00`
- Reviewer: `local-uid:1000`
- Review rationale: Owner approved the SDE entry for persistence/HISTORY\.md, persistence/SOP\.md\.
- Decision receipt: `9b9beaaefce842a8bfe1b81c71ec2cc1`
- Project ID: `curatormd-v2-dev-alpha`
- Receipt binding SHA-256: `05780cb7309c733d525fecc3bbf18deb770fe263a3e3c2130def48397012c5b1`
- Project config SHA-256: `46c099c7182a553a53ce112e1612ae0f425b24def9361538a885a86958f0b86c`
- Draft SHA-256: `acdce70361f7e05ec030c4dd8e1db050198790d470a31cf70f05282413171071`
- Supporting facts SHA-256: `0ac076ac2414afc0ae24629c70489f84092bcb73e9b81dff958a33eb5efa8d26`
- Evidence state SHA-256: `74d01a2dbd6e9c11651bbc2cdeeaf883258f627382deb1463312772a88e3f35d`
- Destination baseline SHA-256: `9df68dc2f227a4ba64c0db4ee90b4933f40e6004d27ca24acbca5688724c976a`
- Artifact inventory SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Dependency map SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Task started: `2026-11-02T18:20:57+07:00`
- Successfully completed: `unknown`
- Problem / plan task: Complete remaining open requirements in Curator V2 at docs/curator\-v2\-plan\.md and docs/Repair V2 dashboard health and queue feeds PLAN\.md\.
- Cleanup authorization reviewer: `local-uid:1000`
- Cleanup authorization time: `2026-11-12T23:15:52+07:00`
- Cleanup manifest SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`

#### Completed successfully

- Added and installed \`curatormd\-v2\-ops\` for \`curatormd\-v2\-dev\-alpha\`: an owner\-private exact\-binding manifest, 60\-second resident monitor, six\-hour maintenance path, seven\-dependency and complete\-queue freshness checks, resource limits, and one runbook inventory\. Incident diagnosis is deduplicated and bounded; identity, grant, deployment, and destructive changes remain owner\-gated\.

- Future utility: Useful for future Curator V2 local\-alpha maintenance and operations\.

#### Approved persistence destinations

- `persistence/HISTORY.md`
- `persistence/SOP.md`
<!-- curatormd-v2:block-sha256:19e5ab1d7814d54f480c1cd2e66c4089ea88249d06cd03e44d4ed3677fec3d56 -->
<!-- curatormd-v2:sde:bad69059631a32e63e2b2963977d64a26ac0c56f63935bdf3a1a6850e14be841:end -->

<!-- curatormd-v2:sde:0614ccb97486af75b45c0d0e685e5778e262184d72143565081fd7153c8c8b20:start -->
### Complete remaining open requirements in Curator V2 at docs/curator\-v2\-plan\.md and docs/Repair V2 dashboard health and queue feeds PLAN\.md\.

- SDE: `7633fb2d6d974cc2a8cfaa453adad9fc`
- Significance: 3 / 5
- Significance use: guides future compression, summarization, archiving, and culling decisions.
- Decision: approved
- Reviewed: `2026-11-12T23:16:52+07:00`
- Reviewer: `local-uid:1000`
- Review rationale: Owner approved the SDE entry for persistence/HISTORY\.md, persistence/SOP\.md, persistence/AGENTS\.md\.
- Decision receipt: `12e66e23f9f94e0f96120239e254baf1`
- Project ID: `curatormd-v2-dev-alpha`
- Receipt binding SHA-256: `5cc1f140a6126c44736a4b660ac65a8429eb850a556dcb80ba20b94b28d8a6bc`
- Project config SHA-256: `46c099c7182a553a53ce112e1612ae0f425b24def9361538a885a86958f0b86c`
- Draft SHA-256: `c7c3f9b8ba80e64af613e18de4acb77fa2dd2a8696015e408e5d290a2f38f8bf`
- Supporting facts SHA-256: `5bdea14d3e2171e0d6678d3a89e7e06b18b8aadc53dffe3ee8f22bd82a313eed`
- Evidence state SHA-256: `ee310bb0a64e1f83062483c4a5edd14a183b87561004166e2a406588bcd1d2f3`
- Destination baseline SHA-256: `52046bea21df66950cf632cd71f86d35676ea633e2cad8adbc1d8b3878836f92`
- Artifact inventory SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Dependency map SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Task started: `2026-11-02T18:20:57+07:00`
- Successfully completed: `unknown`
- Problem / plan task: Complete remaining open requirements in Curator V2 at docs/curator\-v2\-plan\.md and docs/Repair V2 dashboard health and queue feeds PLAN\.md\.
- Cleanup authorization reviewer: `local-uid:1000`
- Cleanup authorization time: `2026-11-12T23:16:52+07:00`
- Cleanup manifest SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`

#### Completed successfully

- Added reversible recovery safeguards: verified before\-images and restore steps for changed files, consistent snapshots before migration, post\-migration SQLite integrity and foreign\-key checks, bounded idempotent retry, and reconciliation of expired Codex diagnosis units\. \`tests/test\_ops\_cli\.py\` covers binding conflicts, corrupt/locked databases, snapshot/FK failures, stale or incomplete health, deduplication, diagnosis dispatch, CPU/RSS limits, timer, and restart behavior\.

- Future utility: Useful when diagnosing or safely recovering Curator V2 local\-alpha incidents\.

#### Approved persistence destinations

- `persistence/AGENTS.md`
- `persistence/HISTORY.md`
- `persistence/SOP.md`
<!-- curatormd-v2:block-sha256:5a9dbfcce6f636bb58dfec469172e4023c371de673c06ae21518b925c0841c52 -->
<!-- curatormd-v2:sde:0614ccb97486af75b45c0d0e685e5778e262184d72143565081fd7153c8c8b20:end -->

<!-- curatormd-v2:sde:85a2dd86412aae8093e542f64ca8f03b220d6e0b5daa177c926dac85591f5551:start -->
### Four\-level JSON proposals with editable pending SDE approval copies

- SDE: `8b825a5ee25244d9a83977383af38231`
- Significance: 4 / 5
- Significance use: guides future compression, summarization, archiving, and culling decisions.
- Decision: approved
- Reviewed: `2026-11-13T16:17:54+07:00`
- Reviewer: `local-uid:1000`
- Review rationale: Owner approved the SDE entry for persistence/HISTORY\.md, persistence/SOP\.md\.
- Decision receipt: `b38a7682825b4aad95d5d8b2cffafde4`
- Project ID: `curatormd-v2-dev-alpha`
- Receipt binding SHA-256: `d2819ade4d063c8e1d851c6dc60427978379c5f97cddd2d092baf1e675f01175`
- Project config SHA-256: `46c099c7182a553a53ce112e1612ae0f425b24def9361538a885a86958f0b86c`
- Draft SHA-256: `4741171c9fb512455ba5e6994770f1a612c739165ce4d68a4c61956b2a653fa4`
- Supporting facts SHA-256: `c28aeea4d84e09ddbae624c70625a8d2faf0184d0bab7ac57faeaf1bb9654122`
- Evidence state SHA-256: `3b0e24e742ad660ec434e783682d4cd6f147e379967338db0f095f83c0906a76`
- Destination baseline SHA-256: `0ae545c7c4f2ff65d42b82fe58a785ccfa7bc511390bb55ad1db4fe90c907ae7`
- Artifact inventory SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Dependency map SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Task started: `2026-11-13T00:14:07+07:00`
- Successfully completed: `2026-11-13T00:14:47+07:00`
- Problem / plan task: Pending SDE reviews lacked a structured four\-level proposal, a separately editable owner approval copy, and nonempty\-completion validation\.
- Cleanup authorization reviewer: `local-uid:1000`
- Cleanup authorization time: `2026-11-13T16:17:54+07:00`
- Cleanup manifest SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`

#### Completed successfully

- The working\-tree VS Code generator builds a four\-level sdeProposal object, renders a source proposal and a separate editable approval copy, maps edits back for review, and refuses empty completion\.

- Future utility: Useful for future SDE proposal generation and review\.

#### Approved persistence destinations

- `persistence/HISTORY.md`
- `persistence/SOP.md`
<!-- curatormd-v2:block-sha256:b0dc7d3ca78991e669a6a0be5dca55caead579f696b149cf1bb51aad7388183f -->
<!-- curatormd-v2:sde:85a2dd86412aae8093e542f64ca8f03b220d6e0b5daa177c926dac85591f5551:end -->
