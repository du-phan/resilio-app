# Intervals.icu integration

Intervals.icu is Resilio's sole external activity and workout-calendar
integration. External transport models stop at the integration boundary;
coaching, load, metrics, profile analysis, and planning operate on
provider-neutral local schemas.

## Runtime boundary

```text
INTERVALS_ICU_API_KEY
        |
        v
integrations/intervals_icu
  client -> strict DTOs -> activity mapper
        |
        v
canonical local activity archive
        |
        +-> local load, metrics, profile, and coaching
        |
        +-> ownership-safe workout publication
```

The only production credential is `INTERVALS_ICU_API_KEY` in `.env.local`.
Non-secret settings live under `intervals_icu` in `config/settings.yaml`.
Transport errors are typed and redacted. Automated tests inject fake
credentials and transports; they must not read `.env.local` or contact the
live service.

## Completed activities

`resilio sync` imports completed activities through strict DTO validation,
maps them to canonical activity v2 records, quarantines invalid or ambiguous
rows, and atomically commits the archive, metrics, and sync state. The local
archive remains authoritative for coaching calculations.

Normal sync uses an overlap window so late external edits can be detected.
`resilio sync --full` performs complete reconciliation. External deletion is
never inferred from a missing list row: an exact detail request must confirm
absence, and deletion candidates require explicit review before a local
tombstone is committed.

Both external `Bouldering` and `RockClimbing` map to canonical sport `climb`.
Intervals.icu athlete RPE is read from `icu_rpe`, with
`perceived_exertion` retained only as an inbound fallback when athlete RPE is
absent.

## Workout publication

Resilio publishes structured run and cycling workouts under deterministic
external IDs. The local publication manifest and exact remote read-back form
the ownership proof. Update, reschedule, and delete operations refuse
unowned, ambiguous, or remotely drifted events. Exact deletion disables
related-event cascading.

Garmin and Wahoo forwarding is configured in Intervals.icu. Resilio does not
connect to those device services directly.

## Historical climbing publication

The one-time historical climbing publication is complete:

- 404 activities have exact verified ownership receipts;
- 29 pre-existing external matches remain unowned and untouched;
- 35 missing remote RPE values were separately approved and set to 5;
- 369 existing RPE values were preserved;
- repeat application and repeat RPE repair are verified no-ops.

The provider accepts manual `RockClimbing` and displays it as `Climbing` in
the calendar. The publication never changes local activity facts, historical
provenance, calculated load, metrics, profile data, or private notes.

The verified backup, ownership ledger, and rollback executable must remain
available through 2026-10-27. Until then:

- use `resilio activity-backfill status` for read-only inspection;
- use `resume` only to recover a durable pending intent;
- use `rollback` only with the exact approved plan and canary digests;
- never delete an external activity without exact ledger and remote ownership
  proof.

After 2026-10-27, removing the one-time executable and verified backup
requires explicit athlete approval. The provider-neutral ownership receipts
and canonical external links remain durable state.

## Operational references

- [Completed-activity sync](../coaching/cli/cli_sync.md)
- [Historical activity backfill](../coaching/cli/cli_activity_backfill.md)
- [Authentication](../coaching/cli/cli_auth.md)
- [API boundary](../specs/api_layer.md)
- [Architecture map](architecture-map.md)
