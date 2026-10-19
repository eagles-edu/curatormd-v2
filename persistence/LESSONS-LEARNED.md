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
