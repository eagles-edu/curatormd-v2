# Durable knowledge procedure

1. State the problem and observable success criteria before implementation.
2. Inspect the current repository state and relevant instructions; preserve
   unrelated changes and private evidence.
3. Separate direct observations, test evidence, proposals, and live-runtime
   claims. A unit test does not prove deployment or end-to-end behavior.
4. After verification, append only the smallest useful fact or decision to
   `HISTORY.md`; record a repeatable prevention lesson in
   `LESSONS-LEARNED.md` only when a failure and remedy are verified.
5. Keep operating rules in `AGENTS.md` and repeatable procedures in this file.
   Avoid duplicate canonical statements; link to the implementation plan or
   contract where detailed requirements already live.
6. Leave incomplete requirements explicitly open. Never convert a proposal,
   local check, or operator assertion into a completed runtime claim.
7. Verify the resulting files, `git diff --check`, and Curator persistence
   status. Do not stage, commit, publish, or delete evidence automatically.
8. Show every human-facing Curator V2 date and time in `Asia/Ho_Chi_Minh`
   with an explicit `+07:00` offset. When converting an existing timestamp,
   convert the instant; never replace a UTC label without adjusting the clock
   and date. Keep UTC normalization for machine storage and calculations, and
   convert it at Markdown, report, and UI display boundaries. Use the local
   calendar date for daily backup names and other local-day policies.
9. When `eaglesvn` explicitly requests a commit and push of the entire
   worktree, inspect tracked and untracked changes, include the whole worktree,
   then commit and push it to the configured upstream. Do not silently stage
   only selected files or leave requested changes unsynced. This explicit
   instruction overrides the normal requirement to wait for publication
   authorization. After each item is completed, commit and push when this
   standing instruction applies.
10. Before a push, inspect the complete outgoing change set for server/host
    configuration, firewall rules, credentials, private runtime logs, or
    other operational details. Omit those files from publication and ask
    `eaglesvn` before including them. A request to push the whole worktree does
    not override this check. Never publish first and ask afterward.
