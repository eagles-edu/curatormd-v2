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
