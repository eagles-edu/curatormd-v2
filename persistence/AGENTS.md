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
