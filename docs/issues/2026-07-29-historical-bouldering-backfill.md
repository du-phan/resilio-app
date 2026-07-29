# Historical bouldering backfill

- Status: amended dry run passed; canary approval pending
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

## Remaining work

- Obtain a new canary approval bound to the amended plan digest.
- Publish and visually verify one exact `RockClimbing` canary.
- Record the athlete's separate application approval.
- Apply/resume all remaining batches and execute the acceptance checklist.
- Record the acceptance date and 90-day rollback deadline in repository and
  vault continuity artifacts.

No live mutation is authorized merely by this issue. Every mutation remains
bound to the immutable plan/canary digests and the recorded approval stage.
