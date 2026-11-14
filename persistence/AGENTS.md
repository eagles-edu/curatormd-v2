# Curator V2 durable knowledge rules

- This repository owns the proposed CuratorMD global backend. Consumer source,
  project-local plugin configuration, runtime state, and private evidence stay
  in their respective repositories and ignored runtime directories.
- Canonical durable knowledge is limited to `AGENTS.md`, `SOP.md`,
  `HISTORY.md`, and `LESSONS-LEARNED.md` in this directory. Keep records as
  short, deduplicated bullets with dates where chronology matters.
- Keep dated history newest first; put the newest approved SDE entry at
  the top of each owner-approved destination and preserve the exact approved
  facts and destination list.
- Record verified facts and explicit decisions only. Label proposals, local
  test results, and runtime observations so none imply deployment or end-to-end
  operation. Preserve unresolved criteria as open gates.
- Human-facing timestamps use `Asia/Ho_Chi_Minh` with an explicit `+07:00`
  offset. Preserve UTC-normalized machine timestamps internally, convert them
  when rendering, and use the local calendar date for daily backup names.
- Never store raw chats, transcripts, imports, cues, scratch artifacts,
  credentials, personal data, or unreviewed native projections here.
- CuratorMD owns its global backend; consuming projects own their plugins,
  config, and canonical project records. Hermes runtime, profiles, gateway,
  and Host Steward belong to Hermes Core. Host cleanup is never a CuratorMD
  action; CuratorMD may retain only an approved compact outcome/reference.
- Do not commit, publish, deploy, purge user data, or close a release gate
  without explicit authorization and evidence.

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

<!-- curatormd-v2:sde:f38fd1247954741dee3ed6becc02a37896d22b1abbf49e634e14272258f97b9e:start -->
### Support untracked repository\-unrelated aside requests and an editor command to join wrapped Markdown prose\.

- SDE: `7be226eba18c417c9e9d1f4de8c87700`
- Significance: 4 / 5
- Significance use: guides future compression, summarization, archiving, and culling decisions.
- Decision: approved
- Reviewed: `2026-11-12T01:17:00+07:00`
- Reviewer: `local-uid:1000`
- Review rationale: Owner approved the SDE entry for persistence/HISTORY\.md, persistence/AGENTS\.md\.
- Decision receipt: `a7fea8673e3e420b8bb2005f65de0a23`
- Project ID: `curatormd-v2-dev-alpha`
- Receipt binding SHA-256: `fc4a9a80f8d81ab444556371e327d6be7208da1384877229c08ea069702d50fa`
- Project config SHA-256: `46c099c7182a553a53ce112e1612ae0f425b24def9361538a885a86958f0b86c`
- Draft SHA-256: `326f370ce702408163e4982dbafaaa6bf39226717b8d599d88b0eba93e12bce2`
- Supporting facts SHA-256: `2c102a25266ffae6a58e525227377d312c0245e39a1290832dd32911f0a007bb`
- Evidence state SHA-256: `093e2f61b6176752d99ef1e1b04379485ad266402709b88864e0c2772ea5bee7`
- Destination baseline SHA-256: `d4226e790cfab845f8c22660a3970b39363aa758773322e3e0a8ef3de213bbc8`
- Artifact inventory SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Dependency map SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Task started: `2026-11-11T16:18:10+07:00`
- Successfully completed: `2026-11-11T16:22:06+07:00`
- Problem / plan task: Support untracked repository\-unrelated aside requests and an editor command to join wrapped Markdown prose\.
- Cleanup authorization reviewer: `local-uid:1000`
- Cleanup authorization time: `2026-11-12T01:17:00+07:00`
- Cleanup manifest SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`

#### Completed successfully

- Focused aatask hook and Markdown join tests passed; complete hook suite passed 35 tests and VS Code suite passed 70 tests\.

- Future utility: aatask aside scope and Markdown paragraph joining\.

#### Approved persistence destinations

- `persistence/AGENTS.md`
- `persistence/HISTORY.md`
<!-- curatormd-v2:block-sha256:8c5cafc20ff06a3beecea1215bb1450af6c5a1b4e6aca2e514968add8bff6fb6 -->
<!-- curatormd-v2:sde:f38fd1247954741dee3ed6becc02a37896d22b1abbf49e634e14272258f97b9e:end -->

<!-- curatormd-v2:sde:cfbf02e7f95c17a50785dccac1b09e73c068bf87924aff9cdafdd1fd24747cfe:start -->
### Allow Curator task completion and SDE proposals without requiring automated proof while keeping uncertain claims honest and persistence human\-reviewed\.

- SDE: `fd6e44278e394d34aec71a2206e434a6`
- Significance: 3 / 5
- Significance use: guides future compression, summarization, archiving, and culling decisions.
- Decision: approved
- Reviewed: `2026-11-12T01:41:03+07:00`
- Reviewer: `local-uid:1000`
- Review rationale: Owner approved the SDE entry for persistence/AGENTS\.md, persistence/HISTORY\.md\.
- Decision receipt: `e5cb3450c2444ac985254c0d105c3f3f`
- Project ID: `curatormd-v2-dev-alpha`
- Receipt binding SHA-256: `598ab0ee80e30e2bd12adaaf29518871b95dcd6e969899792ff8c989bd4c61a7`
- Project config SHA-256: `46c099c7182a553a53ce112e1612ae0f425b24def9361538a885a86958f0b86c`
- Draft SHA-256: `01a565cb16afb23b71f24a7450427e0d30c26e98f8d22b16de0984ef7a1ce0ad`
- Supporting facts SHA-256: `0a126061d5c7f11bb908038ed955217dd182613b7f87bdeabde3a56f02bd7db0`
- Evidence state SHA-256: `11801e14928e7c24f7115db1200c9d2395bd4fc10c948e23f8c0e6f90a1ab67d`
- Destination baseline SHA-256: `fb870b669a149b04228497ab6fdb0f4bc552804e8c31d59abadf0661fa8b0642`
- Artifact inventory SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Dependency map SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Task started: `2026-11-11T16:37:21+07:00`
- Successfully completed: `2026-11-11T16:52:05+07:00`
- Problem / plan task: Allow Curator task completion and SDE proposals without requiring automated proof while keeping uncertain claims honest and persistence human\-reviewed\.
- Cleanup authorization reviewer: `local-uid:1000`
- Cleanup authorization time: `2026-11-12T01:41:03+07:00`
- Cleanup manifest SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`

- Future utility: Nonblocking Curator completion and owner\-reviewed SDE recording\.

#### Approved persistence destinations

- `persistence/AGENTS.md`
- `persistence/HISTORY.md`
<!-- curatormd-v2:block-sha256:ecd246e8b17fc2f2f9cd38d48c75a73f459706b6b696e7ae8e120a53d98c2a64 -->
<!-- curatormd-v2:sde:cfbf02e7f95c17a50785dccac1b09e73c068bf87924aff9cdafdd1fd24747cfe:end -->

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
