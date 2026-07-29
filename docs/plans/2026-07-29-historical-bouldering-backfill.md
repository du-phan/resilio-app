# Historical bouldering backfill to Intervals.icu

This is the living execution plan for the one-time publication of Resilio's
historical climbing archive. It is subordinate to the main
[Intervals.icu migration plan](2026-07-28-intervals-icu-migration.md) and uses
the same architecture and data-safety rules.

- Owner: Resilio
- Created: 2026-07-29
- Status: 404 activities applied and ownership-verified; repeat apply and
  feedback sync are idempotent; visual calendar sampling beyond the accepted
  canary remains
- Acceptance record:
  [Intervals.icu acceptance](../acceptance/2026-07-28-intervals-icu.md)
- Repository issue:
  [historical backfill issue](../issues/2026-07-29-historical-bouldering-backfill.md)
- Vault issue:
  `projects/resilio-app/issues/issue-20260729-historical-bouldering-backfill.md`
- Rollback retention: keep the verified backup and executable through
  2026-10-27, 90 days after athlete acceptance on 2026-07-29

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
- Publish explicitly as remote `RockClimbing`, the live-supported
  Intervals.icu type and the preserved original source label.

The deterministic ownership key is:

```text
resilio:v1:historical-activity:<local_activity_id>
```

Contract references: [manual activity endpoint](https://forum.intervals.icu/t/manual-entry-via-api/24003)
and [bulk external-ID upsert announcement](https://forum.intervals.icu/t/api-access-to-intervals-icu/609?page=32).
Because the published bulk contract scopes upsert ownership to an OAuth
application, personal-key behavior remains an explicit live canary gate.

## Payload policy

The outbound payload contains only the ownership key, `RockClimbing` type,
existing title, corrected local and UTC occurrence, timezone, elapsed/moving
duration, existing public description, athlete-sourced Intervals.icu
`icu_rpe`, and strictly positive distance/elevation.

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
5. The canary is submitted twice. Exact ownership, `RockClimbing`, facts,
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
plan's original frozen baseline. A date-and-ownership lookup verified that
zero owned canaries exist, and the ownership ledger has zero pending or
verified publications.

The application stage was not approved or started. In accordance with the
frozen no-fallback rule, no activity was submitted as `RockClimbing`, no local
activity or metric was changed.

On 2026-07-29 the athlete explicitly approved a replacement destination-type
plan using `RockClimbing`. This is a deliberate amendment, not a silent
fallback: `RockClimbing` is accepted by the live validator and matches the
historical records' preserved original source label. The amendment
invalidates every earlier approval. A fresh dry run and a new exact
digest-bound canary approval are mandatory before another live POST.

The amended dry run then passed under run
`backfill-415d95d8bbb84545` and plan digest
`9748597443bbd12895c0e26368533007a694c137713568e42d984c0ffe9283e5`.
It reproduced 433 selected, 29 hidden exclusions, 404 publishable, 405
exact-time, 28 noon-adjusted, zero owned recoveries, and zero conflicts. The
archive remains at 1,125 records with 110 initial external links. Its verified
backup is restricted to `0700`; the ownership ledger remains empty.

The athlete approved that exact amended digest and the canary POST created an
owned activity, but strict factual read-back rejected at least one
server-normalized field. Namespace-only cleanup immediately deleted the exact
canary and verified `404` plus namespace absence. The run is failed, the
ledger has zero pending or verified entries, and local activity facts, links,
metrics, and sync state remain unchanged.

The original failure message intentionally retained no remote values but was
too coarse to identify the normalized field. Read-back failures now report
only deterministic mismatched field names, never actual or approved values.
All 951 offline tests pass. A repeated read-only inventory check reproduced
the same 433/29/404 accounting, zero conflicts, empty namespace, and unchanged
plan digest. Another POST requires an explicit athlete-authorized diagnostic
canary attempt; it is never retried automatically.

The athlete authorized that diagnostic retry. All approved fields except
`perceived_exertion` matched, after which exact cleanup again verified
deletion and namespace absence. The result exposed a contract error:
Intervals.icu manual activities write athlete RPE through `icu_rpe`;
`perceived_exertion` is a distinct source/read field. The strict write DTO,
read-back fingerprint, external inventory fingerprint, and inbound mapper now
use `icu_rpe`, with inbound fallback to `perceived_exertion` only when no
Intervals.icu athlete RPE exists.

A new dry run passed under run `backfill-96741af2889c3160` and plan digest
`897930642711a1753d2e75642b31641a2bb179abf0f484ea4d68ef2088c9e04d`.
It again proves 433 selected, 29 hidden exclusions, 404 publishable, 405
exact-time, 28 noon-adjusted, 396 athlete RPE, zero owned recoveries, and zero
conflicts. The new backup is restricted to `0700`, the ownership ledger is
empty, and all 952 offline tests pass. Every earlier approval is invalid for
this corrected payload digest.

The athlete approved the corrected plan digest. The canary passed exact
creation read-back, identical second submission, stable destination identity,
single-owned-row inventory, and final exact GET. The immutable canary-proof
digest is
`3a794aeba04b5e5c74f7d5156cf9749118ce703e6099ae914c3f8d004492f527`.
The run has one verified receipt, zero pending intents, and no error. The
athlete must visually accept the calendar representation before a separate
application approval can be recorded for the remaining 403 activities.

The athlete then supplied a full activity-page screenshot and accepted the
calendar representation. Intervals.icu displays API type `RockClimbing` as
`Climbing`; exact API read-back still proves `RockClimbing`. The screenshot
shows 2026-04-02 at 12:30, 1h10 duration, title `Lunch Activity`, public
description `Back to climbing! Hang board session`, and RPE 5. Uploaded load
is absent as required; Intervals.icu's own S-RPE remains provider-calculated.

The athlete separately approved application under plan digest
`897930642711a1753d2e75642b31641a2bb179abf0f484ea4d68ef2088c9e04d`
and canary-proof digest
`3a794aeba04b5e5c74f7d5156cf9749118ce703e6099ae914c3f8d004492f527`.
The application processed the remaining 403 activities in checkpointed
batches and finished with 404 verified ownership receipts, zero pending or
failed entries, and no rollback entries. Immediate identical application
processed zero records and proved the required 404-record no-op.

The acceptance full sync examined 566 external rows and created, linked, or
made ambiguous zero local records. It refreshed external audit data on 514
existing links, retained the two established duplicate exclusions, and
recognized all four acknowledged quarantines. The immediate incremental sync
examined ten recent rows; all ten were unchanged, with zero create, update,
link, ambiguity, duplicate, quarantine, tombstone, or partial result. The
live reconciliation, quarantine, and deletion review queues are empty.

Final local verification finds 1,125 canonical records, 514 external links,
404 backfill links, 404 verified ledger receipts, and zero pending intents.
All 433 historical climbing source projections and calculated loads, all 56
screenshot imports, and the athlete profile remain unchanged against the
verified snapshot. The full sync rewrote only metric `calculated_at` metadata
and added an empty current-day metric; after semantic equality was proved,
the verified snapshot bytes were restored. The exact frozen metrics-tree hash
therefore remains unchanged. All 2,787 backfill-backup files reverify and the
backup root remains restricted to `0700`.

The accepted canary provides live calendar/UI evidence, while exact API
read-back verified all 404 publications. Early, middle, recent, and multiple
noon-adjusted calendar UI spot checks remain athlete-visible acceptance
sampling and do not affect ownership or rollback readiness.

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
- [x] Full offline suite passes: 953 tests, focused Ruff, architecture/link
  guards, `git diff --check`, Poetry validation, and source/wheel builds.
- [x] Confirm future activity downloads are disabled and execute the live dry
  run.
- [x] Obtain athlete canary approval and execute the canary gate; the provider
  rejected exact `Bouldering`, zero owned canaries were created, and the run
  failed closed.
- [x] Obtain explicit athlete approval to amend the destination type to
  `RockClimbing`.
- [x] Execute a fresh amended dry run with exact 433/29/404 accounting and zero
  conflicts.
- [x] Obtain an exact digest-bound amended canary approval; its first POST
  failed closed on a factual read-back mismatch and was deleted exactly.
- [x] Add secret-safe field-name-only mismatch diagnostics and revalidate the
  unchanged external inventory and plan digest.
- [x] Obtain explicit approval for one diagnostic canary retry; it isolated
  the mismatch to the incorrect `perceived_exertion` write field and cleaned
  up exactly.
- [x] Correct manual athlete RPE to `icu_rpe`, preserve inbound source-field
  fallback, and execute a fresh 433/29/404 dry run with zero conflicts.
- [x] Obtain approval for the new exact corrected-payload digest and pass the
  complete automated canary gate with one stable owned remote activity.
- [x] Visually accept the exact `RockClimbing` canary; the Intervals.icu UI
  renders its sport label as `Climbing`.
- [x] Obtain athlete application approval and execute the remaining batches.
- [x] Complete live no-op, sync, count/hash, and rollback-retention
  acceptance.
- [ ] Visually sample early, middle, recent, and multiple noon-adjusted
  calendar entries beyond the already accepted canary.
