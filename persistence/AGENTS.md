# Curator V2 durable knowledge rules

- This repository owns the proposed CuratorMD global backend. Consumer source,
  project-local plugin configuration, runtime state, and private evidence stay
  in their respective repositories and ignored runtime directories.
- Canonical durable knowledge is limited to `AGENTS.md`, `SOP.md`,
  `HISTORY.md`, and `LESSONS-LEARNED.md` in this directory. Keep records as
  short, deduplicated bullets with dates where chronology matters.
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
