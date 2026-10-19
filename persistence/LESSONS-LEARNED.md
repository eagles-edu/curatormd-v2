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
