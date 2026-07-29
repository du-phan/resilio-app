# Historical bouldering backfill

- Status: blocked by live Intervals.icu rejection of exact `Bouldering`
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
- The application stage was not approved or started. The required
  `RockClimbing` no-fallback rule remains in force.

## Remaining work

- Wait for exact `Bouldering` support in the live Intervals.icu manual
  activity API, or create and separately approve a replacement plan that
  changes the destination-type requirement.
- Re-run the drift-sensitive dry run and obtain a new canary approval.
- Publish and visually verify one exact canary.
- Record the athlete's separate application approval.
- Apply/resume all remaining batches and execute the acceptance checklist.
- Record the acceptance date and 90-day rollback deadline in repository and
  vault continuity artifacts.

No live mutation is authorized merely by this issue. Every mutation remains
bound to the immutable plan/canary digests and the recorded approval stage.
