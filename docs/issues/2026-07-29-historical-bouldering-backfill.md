# Historical bouldering backfill

- Status: corrected canary verified; athlete visual acceptance pending
- Plan:
  [historical bouldering backfill](../plans/2026-07-29-historical-bouldering-backfill.md)
- Parent:
  [Intervals.icu migration](../plans/2026-07-28-intervals-icu-migration.md)

## Live result

- The live deterministic dry run reproduced 433 selected, 29 hidden
  exclusions, 404 publishable, 28 noon-adjusted, and zero conflicts.
- The athlete approved the deterministic canary.
- The manual endpoint returned HTTP 422, and a non-creating validation probe
  confirmed `Invalid type [Bouldering]`.
- An ownership lookup found zero remote canaries. The ledger contains zero
  pending or verified publications, and no local facts or metrics changed.
- The application stage was not approved or started, so the original
  no-fallback rule was honored.
- The athlete subsequently approved an explicit replacement plan using
  `RockClimbing`, which matches the preserved original source label.
  Earlier approvals are invalid and cannot authorize the amended canary.
- The amended dry run passed with exact 433/29/404 accounting, 28
  noon-adjusted records, zero conflicts, an empty ownership ledger, and a
  verified restricted backup.
- The athlete approved the amended digest. The exact canary was created, but
  strict factual read-back found a mismatch. Ownership-safe cleanup deleted
  it, verified `404` and namespace absence, and left the ledger and local
  archive unchanged.
- Field-name-only diagnostics now identify future normalization without
  retaining values. All 951 tests pass, and a repeated read-only inventory
  check remains exact with the same immutable plan digest.
- The authorized diagnostic retry matched every field except
  `perceived_exertion` and was again deleted exactly. Intervals.icu manual
  activities require athlete RPE in `icu_rpe`; the strict DTO, read-back,
  inventory fingerprint, and inbound precedence now reflect that contract.
- The corrected fresh dry run passed with a new digest, exact 433/29/404
  accounting, 396 RPE values, zero conflicts, a verified `0700` backup, and
  an empty ledger. All 952 tests pass.
- The athlete approved the corrected digest. Exact read-back, repeated
  submission, stable identity, unique ownership, and final GET all passed.
  The ledger contains one verified canary and zero pending entries.

## Remaining work

- Obtain the athlete's visual acceptance of the verified `RockClimbing`
  canary.
- Record the athlete's separate application approval.
- Apply/resume all remaining batches and execute the acceptance checklist.
- Record the acceptance date and 90-day rollback deadline in repository and
  vault continuity artifacts.

No live mutation is authorized merely by this issue. Every mutation remains
bound to the immutable plan/canary digests and the recorded approval stage.
