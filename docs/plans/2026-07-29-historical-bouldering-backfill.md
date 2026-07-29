# Historical bouldering backfill to Intervals.icu

This is the living execution plan for the one-time publication of Resilio's
historical climbing archive. It is subordinate to the main
[Intervals.icu migration plan](2026-07-28-intervals-icu-migration.md) and uses
the same architecture and data-safety rules.

- Owner: Resilio
- Created: 2026-07-29
- Status: live dry run complete; publication blocked because the live
  Intervals.icu API rejects exact activity type `Bouldering`
- Acceptance record:
  [Intervals.icu acceptance](../acceptance/2026-07-28-intervals-icu.md)
- Repository issue:
  [historical backfill issue](../issues/2026-07-29-historical-bouldering-backfill.md)
- Vault issue:
  `projects/resilio-app/issues/issue-20260729-historical-bouldering-backfill.md`
- Rollback retention: keep the verified backup and executable for at least
  90 days after athlete acceptance

## Frozen scope

- Select all 433 active `historical_import` climb records.
- Correct 405 stored wall clocks by interpreting their clock components in
  `Europe/Paris`; all must be valid and unambiguous.
- Place 28 date-only screenshot records at local noon and disclose that the
  exact historical start time is unavailable.
- Exclude exactly 29 one-to-one hidden-row matches without linking, updating,
  or deleting those remote rows.
- Publish exactly 404 records: 376 exact-time records and 28 noon-adjusted
  records.
- Require exact remote `Bouldering`; there is no `RockClimbing` fallback.

The deterministic ownership key is:

```text
resilio:v1:historical-activity:<local_activity_id>
```

Contract references: [manual activity endpoint](https://forum.intervals.icu/t/manual-entry-via-api/24003)
and [bulk external-ID upsert announcement](https://forum.intervals.icu/t/api-access-to-intervals-icu/609?page=32).
Because the published bulk contract scopes upsert ownership to an OAuth
application, personal-key behavior remains an explicit live canary gate.

## Payload policy

The outbound payload contains only the ownership key, `Bouldering` type,
existing title, corrected local and UTC occurrence, timezone, elapsed/moving
duration, existing public description, athlete-sourced RPE, and strictly
positive distance/elevation.

Private notes, calculated Resilio load, raw provenance, server-managed
identity/source fields, device data, segments, and zero-valued measurements
remain local. Current coverage is 396 athlete RPE values, 39 source public
descriptions, one positive distance, and no positive elevation.

## Safety and ownership gates

1. A dry run re-fetches the complete external inventory, proves frozen
   433/29/404 accounting, hashes the archive/metrics/sync state/inventory, and
   creates an immutable report plus a restricted verified backup.
2. Future activity downloads must be disabled in the Intervals.icu UI and
   explicitly recorded in that dry run before approval can be stored.
3. A separate athlete approval binds the exact plan digest before the canary.
4. The deterministic canary is the newest collision-free exact-time record
   with both public description and athlete RPE.
5. The canary is submitted twice. Exact ownership, `Bouldering`, facts,
   stable remote identity, and a single remaining activity are mandatory.
6. A second athlete approval binds both the plan and canary-proof digests.
7. Remaining records are processed by occurrence/local ID in batches of 25.
   Every pending intent is durable before POST; POST/DELETE are never retried
   blindly.
8. Uncertain results recover by listing the affected dates and ownership IDs.
   Exact matches are adopted; only proven-absent records may be retried.
9. The canonical archive and completed-activity sync index switch atomically
   under the same mutation lock used by normal sync. Metrics and sync cursors
   do not change.
10. Rollback verifies each exact remote ID, namespace, type, date, and factual
    fingerprint before deletion, verifies absence, then restores only the
    hash-proven original local record and sync-index entry.

Any archive, metrics, sync-state, or non-owned external-inventory drift
invalidates the approvals. Ambiguous hidden timestamps, visible unowned
composite matches, multiple ownership matches, and payload conflicts stop the
run.

## Commands

```text
resilio activity-backfill dry-run --confirm-downloads-disabled
resilio activity-backfill status
resilio activity-backfill record-approval --stage canary --plan-digest <sha256>
resilio activity-backfill canary --plan-digest <sha256>
resilio activity-backfill record-approval --stage apply \
  --plan-digest <sha256> --canary-digest <sha256>
resilio activity-backfill apply \
  --plan-digest <sha256> --canary-digest <sha256>
resilio activity-backfill resume \
  --plan-digest <sha256> --canary-digest <sha256>
resilio activity-backfill rollback \
  --plan-digest <sha256> --canary-digest <sha256>
```

The coach owns both approval conversations. The live mutation commands are
not run as part of automated verification.

## Live acceptance result (2026-07-29)

The live dry run reproduced the frozen baseline exactly: 433 selected, 29
hidden exclusions, 404 publishable, 28 noon-adjusted, and zero unresolved
conflicts. The athlete approved the deterministic canary under the immutable
replacement plan digest
`913b126be39f92d6719a150ab326fb54c62d886e1847042fb46fdbe758887b8d`.

The manual bulk endpoint rejected the canary with HTTP 422. A non-creating
validation probe then returned `Invalid type [Bouldering]`, proving that the
live write contract does not accept the destination type required by this
plan. A date-and-ownership lookup verified that zero owned canaries exist,
and the ownership ledger has zero pending or verified publications.

The application stage was not approved or started. In accordance with the
frozen no-fallback rule, no activity was submitted as `RockClimbing`, no local
activity or metric was changed, and the historical backfill is blocked until
Intervals.icu accepts exact `Bouldering` or a separately approved plan changes
the destination-type requirement.

## Acceptance

- Dry run: 433 selected, 29 hidden exclusions, 404 publishable, 28
  noon-adjusted, zero conflicts.
- Canary: athlete visually approves type, time, duration, title, description,
  and RPE; repeated submission leaves one stable remote ID.
- Apply: 404 verified receipts, no pending/failed entry, repeat is a
  404-record no-op.
- Local: 1,125 active records remain; total external links rise from 110 to
  514; historical facts, load, metrics tree, profile counts, and screenshots
  are unchanged.
- Feedback: immediate full and incremental sync create/link zero additional
  records and retain historical provenance.
- Calendar: spot-check early/middle/recent exact records and several
  noon-adjusted records; the 29 hidden rows remain unchanged.
- Retention: record acceptance date and the computed 90-day rollback deadline
  in this plan, the acceptance record, vault issue/status, and weekly note.

## Implementation progress

- [x] Strict manual write DTO, bulk endpoint, exact delete, and no mutation
  retries.
- [x] Paris wall-time correction, noon disclosure, strict payload omission,
  deterministic source/payload/read-back fingerprints.
- [x] Frozen accounting, one-to-one hidden matching across all sports,
  visible/owned conflict classification, and sanitized deterministic reports.
- [x] Restricted verified backup, immutable run artifacts, approval records,
  durable pending intents, and provider-neutral ownership ledger.
- [x] Shared activity-mutation lock and extracted archive/state transaction;
  normal sync service reduced below 800 lines.
- [x] Canary identity/upsert proof and namespace-only failure cleanup.
- [x] Checkpointed batch apply/resume and exact rollback.
- [x] Feedback-loop guard preserving historical local facts and provenance.
- [x] Offline client/mapping/selection/interruption/recovery/rollback tests.
- [x] Current archive rendering probe confirms 433 strict payloads, 405 valid
  exact wall times, 28 noon adjustments, 396 athlete RPE values, 39 original
  public descriptions, one positive distance, and no positive elevation.
- [x] Full offline suite passes: 949 tests, focused Ruff, architecture/link
  guards, `git diff --check`, Poetry validation, and source/wheel builds.
- [x] Confirm future activity downloads are disabled and execute the live dry
  run.
- [x] Obtain athlete canary approval and execute the canary gate; the provider
  rejected exact `Bouldering`, zero owned canaries were created, and the run
  failed closed.
- [ ] Visually accept an exact `Bouldering` canary if provider support becomes
  available.
- [ ] Obtain athlete application approval and execute the remaining batches.
- [ ] Complete live no-op, sync, calendar, count/hash, and rollback-retention
  acceptance.
