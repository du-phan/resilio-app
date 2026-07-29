# Historical bouldering backfill

- Status: 404 applied and verified; technical acceptance complete; additional
  visual calendar sampling pending
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
- The athlete's full-page screenshot confirms the UI displays `Climbing`,
  2026-04-02 12:30, 1h10, `Lunch Activity`, the public description, and RPE 5.
  Exact API read-back remains `RockClimbing`; uploaded load is absent.
- The separately approved application processed the remaining 403 records.
  The ledger now contains 404 verified receipts, zero pending or failed
  entries, and zero rollback entries. Immediate repeated application processed
  zero records and proved a 404-record no-op.
- Full feedback sync examined 566 rows with zero create, link, or ambiguity;
  its immediate incremental successor found ten unchanged rows and zero
  mutation or review outcome. Reconciliation, quarantine, and deletion queues
  are empty.
- Final state contains 1,125 local records and 514 external links. Historical
  climbing facts/load, all 56 screenshot records, the profile, and the exact
  frozen metrics digest remain unchanged. All 2,787 restricted-backup files
  verify.
- Acceptance was recorded on 2026-07-29. Retain the rollback executable and
  verified backup through 2026-10-27.
- The closing 953-test suite, architecture guard, focused Ruff, and diff
  validation pass. Sync-derived retired transport labels cannot re-enter
  canonical device fields.

## Remaining work

- Visually sample early, middle, recent, and multiple noon-adjusted calendar
  entries beyond the already accepted canary.
- After 2026-10-27, remove the one-time executable and backup only with
  explicit approval while retaining the sanitized receipt and canonical links.

Any rollback remains an explicit, digest-bound operation and may delete only
the exact manifest-owned activities after remote ownership revalidation.
