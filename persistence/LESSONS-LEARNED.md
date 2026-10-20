# Verified lessons

- A single disk-size observation establishes a baseline, not growth. Emit a
  growth proposal only after a later complete observation shows a positive
  allocated-byte delta; suppress proposals when a scan is incomplete or has
  metadata errors. This keeps bounded Host Steward output from presenting
  unknown change as measured growth.
# Verification timeouts under contention

Tests with short subprocess deadlines can time out when the full suite runs
alongside CPU-intensive type/lint jobs. Reproduce the failing test alone, then
rerun the suite without competing jobs before changing product code; a passing
isolated and sequential rerun distinguishes host contention from a deterministic
plugin regression.

## Verified fix: A staged file could be replaced at its path after its opened descriptor was hashed, allowing a later path-based unlink t

**Date:** 2026-10-20

**Lesson:** Before unlink, perform a descriptor-relative no-follow stat of the leaf and require matching device and inode; reject mismatches so the receipt stays purge-pending.

**Evidence:** The failure was reproduced or observed, and the fix was verified.

**Trigger / root cause:** A staged file could be replaced at its path after its opened descriptor was hashed, allowing a later path-based unlink to target the replacement.

The purge implementation verified descriptor metadata and content hash but did not confirm that the directory entry still referenced that descriptor immediately before unlink.

**Preventative rule:** Keep symlink-safe descriptor traversal and hash checks, compare the leaf directory entry to the verified descriptor, and retain the explicit residual that stat and unlink are not atomic and same-privilege directory moves need deployment-specific controls.

<!-- curatormd:record_id=a664e0063598c921b7d25f3d9f28d278;content_sha256=a664e0063598c921b7d25f3d9f28d278269f619a2ec0d71e29b6b18ef40598cb -->

## Keep attended prompts off machine-readable CLI output

**Date:** 2026-10-20

**Lesson:** When a local CLI requires an interactive confirmation but emits JSON for automation, write the prompt and refusal messages to stderr and reserve stdout for the structured result. Regression-test both stream separation and that rejected/noninteractive confirmations create no database or access mutation.

**Trigger / root cause:** The access CLI's initial test exposed that a confirmation prompt prefixed stdout and made an otherwise successful JSON result unparsable; stream separation resolved it and the expanded attended/noninteractive regressions pass.

**Preventative rule:** Preserves human confirmation while keeping CLI output safely machine-readable.

<!-- curatormd:record_id=6cd24fdac891a8220fe247b03f6f22ad;content_sha256=6cd24fdac891a8220fe247b03f6f22ada17701c06944eaa0c58cda886539d470 -->

## Do not persist filesystem exception text in purge receipts

**Date:** 2026-10-20

**Lesson:** Operational receipts may surface through status APIs and future database backups, so store a bounded allowlisted failure code—not `str(exception)`—when filesystem or cleanup operations fail. Preserve retry state independently from diagnostics, and include a migration that redacts previously persisted free-form failures with rollback/retry coverage.

**Trigger / root cause:** A purge failure was being stored and exposed verbatim; injected marker tests now prove safe status output while retry remains available.

**Preventative rule:** Prevents arbitrary exception details and path fragments from propagating through persistent operational state.

<!-- curatormd:record_id=f550318549abd0aeeddc808e9308fef4;content_sha256=f550318549abd0aeeddc808e9308fef411fbd4fc4cf63b4333fbb1e416de6d50 -->
