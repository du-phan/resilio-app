# Intervals.icu migration and agent-legible architecture

This is a living execution plan. It is self-contained enough for a new agent to
resume the work from repository state and the artifacts named here.

- Owner: Resilio
- Created: 2026-07-28
- Status: implementation and owned calendar lifecycle complete; no active
  training plan; device acceptance deferred
- Acceptance record: `docs/acceptance/2026-07-28-intervals-icu.md`
- Historical bouldering backfill:
  `docs/plans/2026-07-29-historical-bouldering-backfill.md`
- Vault issue: `projects/resilio-app/issues/issue-20260728-intervals-icu-migration.md`
- Vault status: `projects/resilio-app/status.md`
- Weekly continuity: `weekly/2026-W31.md`
- Approved vault brief: `projects/resilio-app/brief.md`
- Scope: replace every active legacy activity-provider path with Intervals.icu,
  migrate the local archive to canonical activity schema v2, add safe completed
  activity sync and owned workout publication, and remove obsolete code and
  terminology.

## Outcomes

The athlete can record activities from Garmin, Wahoo, climbing, bouldering,
yoga, strength, and other sources in Intervals.icu; import them into one local
archive idempotently; preserve history unavailable through the API; compute all
coaching metrics locally; and publish, update, reschedule, or delete only
Resilio-owned run and cycling workouts. RockClimbing and Bouldering both
aggregate as `climb`.

The final application has one external integration, no OAuth refresh flow, no
provider-specific domain fields, and no dependency from schemas/core into
presentation layers.

## Evidence legend

- `[CODE]` repository source or tests
- `[DATA]` ignored local athlete files
- `[SPEC]` `docs/api/intervals_icu_openapi_spec.json`
- `[LIVE]` secret-safe, read-only API request
- `[OFFICIAL]` first-party documentation
- `[INFERRED]` design derived from evidence
- `[UNKNOWN]` behavior requiring an explicit validation gate

## Baseline

- `[CODE]` `resilio/core/strava.py` is 1,181 lines and combines auth,
  transport, mapping, pagination, deduplication, and local manual creation.
- `[CODE]` `resilio/core/workflows.py` is 1,744 lines, imports the transport
  directly, and imports `resilio.api.coach` from core.
- `[CODE]` Activity file names use date, sport, and minute; same-minute
  activities can collide.
- `[CODE]` The v1 activity model persists derived units and provider fields.
- `[CODE]` `WorkoutPrescription.intervals` is an untyped `list[dict]`.
- `[CODE]` Configuration requires a provider-only YAML secret document.
- `[CODE]` On 2026-07-28 the baseline suite was 883 passed, 3 failed, 10
  skipped. One failure is skill mirror drift and two fixtures depend on the
  wall-clock date.
- `[DATA]` The ignored archive has 1,114 valid activity YAML files spanning
  2022-01-20 through 2026-07-15: 433 climb, 325 cycle, 196 run, 58 yoga,
  68 other, 14 hike, 13 walk, and 7 strength.
- `[DATA]` There are 56 screenshot imports: 28 climb, 22 cycle, and 6 run,
  spanning 2026-04-07 through 2026-07-15.
- `[DATA]` Pre-migration totals are 5,541,553 duration seconds,
  8,735,943.9 distance metres, 103,995.3 elevation metres, 67,604.3 systemic
  load AU, and 25,779.2 lower-body load AU.
- `[DATA]` Daily metrics contain 1,651 records through 2026-07-28.
- `[SPEC]` The vendored OpenAPI 3.0.1 contract contains 117 paths, 148
  operations, and 110 schemas.
- `[LIVE]` Planning probes found 97 rows: 30 complete Wahoo rides and 67
  inaccessible legacy-provider stubs. No personal raw response was retained.

## Target dependency direction

```text
.env.local
  -> runtime configuration (SecretStr)
  -> integrations/intervals_icu client and strict DTOs
  -> activity/workout mappers
  -> canonical domain schemas
  -> archive, sync-state, and publication repositories
  -> sync/publication services
  -> load, metrics, profile, coaching, planning
  -> API
  -> CLI
```

Rules:

1. Schemas import no repository, integration, API, or CLI code.
2. External DTOs never enter metrics, load, profile, coaching, or planning.
3. Core services depend on schemas and repository protocols, never CLI/API.
4. API depends on core; CLI depends on API.
5. No general provider-plugin or orchestration framework is introduced.

## Canonical activity v2

The only persisted activity is `CanonicalActivity`.

```yaml
_schema:
  name: resilio.activity
  version: 2
local_activity_id: act_h_0123456789abcdef01234567
status: active
sport: run
source_sport_type: Run
source_sport_subtype: null
name: Morning Run
occurrence:
  local_date: 2026-07-28
  start_time_utc: 2026-07-28T05:00:00Z
  start_time_local: 2026-07-28T07:00:00+02:00
  timezone: Europe/Paris
duration:
  elapsed_seconds: 3600
  moving_seconds: 3500
distance_meters: 10000
elevation_gain_meters: 50
heart_rate:
  average_beats_per_minute: 145
  maximum_beats_per_minute: 170
power: null
cadence: null
notes:
  description: null
  private_note: null
perceived_effort: null
device:
  name: null
  gear_external_id: null
classification:
  surface: road
  data_quality: high
  has_gps_data: true
segments: []
origin:
  kind: historical_import
  recording_provider: unknown
  intervals_icu_activity_id: null
  upstream_external_id: null
  original_file_sha256: null
audit:
  imported_at_utc: 2026-07-28T00:00:00Z
  external_created_at_utc: null
  external_sync_at_utc: null
  external_fingerprint_sha256: null
calculated_load: null
```

Invariants:

- Persist only SI base units; date, weekday, minutes, kilometres, and pace are
  computed views.
- Numeric values are finite and domain-bounded.
- `elapsed_seconds >= moving_seconds >= 0` and elapsed duration is positive.
- `_schema` serializes literally and round-trips.
- Local IDs are immutable and filename-safe.
- External IDs use the first 24 hex characters of
  `SHA-256("intervals-icu\0" + external_id)` with prefix `act_i_`.
- Historical IDs use the first 24 hex characters of
  `SHA-256("historical-import-v2\0" + legacy_id)` with prefix `act_h_`.
- A deduplicated external record preserves the historical local ID.
- Raw API payloads and obsolete provider IDs/names are not persisted.
- Old laps become `segments`; external intervals have origin kind
  `intervals_icu_interval`.

Sport mapping is strict. Run variants map to their canonical run variants;
ride variants map to `cycle`; RockClimbing and Bouldering map to `climb`;
Yoga maps to `yoga`; WeightTraining and StrengthTraining map to `strength`;
Hike, Walk, Swim/OpenWaterSwim, and Crossfit map directly; explicit
Other/Workout maps to `other`; unknown strings are quarantined.

## Configuration

`.env.local` is the sole production secret file. The required key is
`INTERVALS_ICU_API_KEY`, parsed with `python-dotenv` into a local mapping
without mutating process environment. Tests inject mappings and never read the
developer file. The credential is a Pydantic `SecretStr`.

The client uses personal-key Basic authentication, athlete alias `0`, and
`User-Agent: Resilio/<version>`. Errors distinguish missing credential, auth,
authorization, rate limit, transport, invalid payload, and unsupported sport.
No error or log may expose a credential, auth header, URL credential, or raw
personal response.

## Historical migration transaction

The one-time executable is restartable:

1. Acquire an exclusive migration lock and validate all source files.
2. Create a mode-restricted backup at
   `data/backups/activity-v2/<run-id>/` containing activities, metrics,
   profile, training history/sync state, plans, and publication state.
3. Write and verify a sorted SHA-256 manifest.
4. Transform under
   `data/migrations/activity-v2/<run-id>/candidate/`; never edit v1 in place.
5. Produce deterministic `report.json` and `report.md`; volatile timestamps
   live in a separate run envelope.
6. Reconcile count, date range, sport counts, numeric sums, null coverage,
   screenshot records, and per-record hashes.
7. Dry-run stops before switching directories.
8. Apply with same-filesystem atomic renames and switch dependent state only
   after candidate validation.
9. On any failure restore from verified backup and revalidate hashes.
10. Resume only immutable stages whose recorded input hashes still match.

Migration preserves occurrence, sport, durations, distance, elevation, HR,
notes, RPE, device, segments, classification, and calculated load. A single
legacy duration becomes both elapsed and moving duration with the unavailable
distinction recorded in the report. Legacy imports become
`historical_import`; screenshot records use recording provider `manual`.

## Completed-activity sync

Initial sync validates account/connections/sport settings, lists from
2022-01-20 through the computationally determined current date in 90-day
local-date windows, and bisects any window reaching `limit=1000`. Hidden rows
are reported and do not overwrite migrated history. Complete rows are fetched
in bounded detail batches with intervals.

Incremental sync always overlaps 30 days. A full reconciliation runs every 30
days or with `--full`. Canonical external fingerprints detect late edits. A
linked ID absent from a complete list window is verified by detail GET:
`404` creates a retained `external_deleted` tombstone; `200` records a partial
listing; auth/rate/transport failure leaves it active and marks the run partial.

Read retries cover connection errors, `429`, and `5xx`, at most four attempts,
with bounded jitter and `Retry-After`. Validation and `400/401/403/422` are not
blindly retried. Checkpoints advance only after archive and metrics commit.
Files are `YYYY-MM/<local_activity_id>.yaml`.

The final sync state records schema version, resolved athlete ID, successful
incremental timestamp, complete windows, full-reconciliation timestamp,
overlap policy, current checkpoint/run ID, and external-to-local index.

## Deduplication

For every validated external activity:

1. Update an already linked external activity after fingerprint comparison.
2. Otherwise block candidates by canonical sport and occurrence date.
3. Link a unique upstream external ID or temporary original-file SHA-256.
4. For recorded activities require start delta <=120 seconds, elapsed delta
   <= max(60 seconds, 2%), moving delta within the same tolerance when both
   exist, distance delta <= max(100 metres, 1%) when both exist, and compatible
   source/device evidence.
5. For distance-free manual activities require same local date/sport, exact
   rounded-minute duration, exact normalized title when present, and exactly
   one candidate.
6. Wider candidates (start <=30 minutes, duration <=max(300 seconds, 5%),
   distance <=max(250 metres, 2%)) become a deterministic ambiguity report.
7. With no review candidates, create a new canonical activity.

Athlete-authored notes/RPE are never overwritten. Valid sensors may fill
nulls. Material conflicts are quarantined. Load is always recomputed locally.
Every decision records sanitized rule inputs and tolerances.

## Structured workouts and ownership

`WorkoutPrescription` uses typed provider-neutral recursive steps: steady,
ramp, and repeat. Durations are seconds, metres, or `until_lap_press` with a
nominal load duration. Targets are pace, HR, or power with explicit units.
Steps carry intensity, optional cadence range, and athlete cue. Rest days are
not published.

```text
external_id = "resilio:v1:workout:" + local_workout_id
requested_uid = UUIDv5(URL_NAMESPACE, external_id)
```

Publication validates and deterministically renders native workout text,
fetches timezone/connections/sport settings, fails closed for missing pace or
power prerequisites and unsupported device semantics, preflights date-range
ownership, and uses single-event `POST .../events?upsertOnUid=true`. Read-back
must prove external ID, namespace, date, sport, and rendered fingerprint.
`[LIVE]` Personal-key creation preserves `external_id` but replaces the
submitted UUID. The manifest therefore retains both the deterministic
requested UID and the server UID; later upserts use the server UID.

A local manifest maps workout ID to event ID, requested UID, server UID,
external ID, fingerprint, and sport-settings version. Same fingerprint is a
no-op; edits and reschedules retain the external ID and server UID. Deletion
requires local manifest plus remote server-UID/external-ID proof, deletes one
exact event ID, and verifies absence. Unowned events and date-range deletion
are forbidden.

## Architectural guardrails

- Warn above 800 lines and fail above 1,500.
- The initial hard-limit inventory contained four pre-existing modules above
  1,500 lines. `core/workflows.py` left the list in this migration; the three
  remaining modules have linked architecture-debt issues and may not grow.
- AST tests enforce dependency direction and prohibit transport DTO imports in
  metrics/load/profile/coaching/planning.
- Automated tests cannot use live network or read the real `.env.local`.
- Secret-safety tests inspect fixtures, logs, and errors.
- `.agents/skills` is authoritative; `.claude/skills` remains a mechanically
  validated mirror during this migration.
- Documentation checks cover links, authority declarations, active-provider
  terminology, and skill parity.

## Phase plan

Each phase is red-green-refactor and ends with a findings-first review.
Confirmed high-severity findings block progression.

### Phase 0 — Continuity

Create this plan, the vault issue, update vault status and computed weekly
note, and record the reproducible baseline without touching athlete data.
`brief.md` is not edited without explicit approval.

### Phase 1 — Harness

Make the three baseline tests deterministic and green. Add module budget,
dependency, no-network, secret-safety, docs, and skill-parity checks. Record
separate debt for unrelated oversized modules.

### Phase 2 — Workflow decomposition

Move locking/transaction, metrics refresh, plan generation, adaptation, and
sync responsibilities into focused modules. Update call sites directly and
delete `core/workflows.py`; add no re-export facade.

### Phase 3 — Final schemas/config/workouts

Implement canonical activity v2, final sync/config models, dotenv loading,
and typed structured workouts. Update every downstream consumer and remove
provider-specific domain vocabulary before touching active data.

### Phase 4 — Migration proof

Implement pure transforms and filesystem transaction separately. Test invalid
source, duplicate IDs, corrupt YAML, interrupted checkpoints, backup collision,
rename failure, and rollback. A full real-data dry-run must account for all
1,114 records and a disposable copy must prove rollback.

### Phase 5 — Typed client

Implement the narrow Intervals.icu client/DTO/error package using
`httpx.MockTransport` tests. Cover account, connections, sport settings,
activity lists/details/files, and calendar events. Automated tests never use
the live API.

### Phase 6 — Mapping/reconciliation

Implement strict sport/activity mapping, fingerprints, candidate generation,
dedup decisions, merges, conflicts, and quarantine reports. Every fixture maps
or fails explicitly; no unknown sport silently becomes `other`.

### Phase 7 — Cutover/sync

After the real dry-run, take the verified backup, atomically apply v2, switch
readers, import completed activities, and regenerate dependent metrics. Prove
repeat sync, overlap, late edits, confirmed deletion, saturated windows, and
interrupted resume.

### Phase 8 — Workout publication

Implement deterministic rendering, ownership manifest, preflight, UID upsert,
read-back, update, reschedule, and exact delete behind narrow plan API/CLI
commands. Automated tests use a fake client only.

### Phase 9 — Athlete surfaces

Expose provider-neutral auth status, sync/full reconcile, migration status,
and workout publication. Remove direct local manual entry and OAuth commands.
Update setup/onboarding/coaching skills without exposing implementation details.

### Phase 10 — Removal/docs

Delete the old integration, tests, spec module, config/templates, imports,
fixtures, setup language, and active documentation. The case-insensitive audit
may retain occurrences only in the vendored third-party spec, this migration
record/vault issue, Git history, and rollback backup during retention.

### Phase 11 — Acceptance/finalization

Run controlled athlete/device acceptance. Convert every defect to a failing
regression first. Record final reconciliation, architecture/security/data/docs
reviews, outcomes, and rollback-window disposition.

## Verification matrix

Automated suites cover configuration isolation/redaction; HTTP error classes,
retry and User-Agent; window bisection and batch omissions; all sport and
provenance variants; finite measurements; deterministic migration/backup/
restart/rollback; every dedup tier; initial/incremental/full sync; metrics
determinism; recursive workout rendering; owned publication lifecycle;
timezone/DST; no-live-network; secret leakage; dependencies; module budgets;
skill parity; documentation; and obsolete-term cleanup.

Manual pure-function probes cover zero/negative/long duration, missing time,
NaN/infinity, DST transitions in Europe/Paris, same-minute activities,
duplicate identifiers, distance-free manual activities, RockClimbing/
Bouldering siblings, unknown types, source variants, late edits, sync window
boundaries, repeat upsert, cross-day rescheduling, mixed targets, lap press,
and unowned deletion.

## Acceptance checklist

- [x] Only `INTERVALS_ICU_API_KEY` is required in `.env.local`.
- [x] Auth status succeeds without key leakage.
- [x] First import succeeds and immediate repeat creates zero duplicates.
- [ ] Rock climbing and bouldering both appear as `climb`.
- [ ] Manual yoga, Wahoo sensor data, and a Garmin activity import correctly.
- [ ] Garmin attribution appears where required.
- [ ] Structured run and cycling workouts reach Garmin and Wahoo.
- [ ] Update/reschedule/delete affects only Resilio-owned events.
- [ ] Device forwarding filters/timezones are documented and verified.
- [x] Coaching, metrics, profile, weekly analysis, and planning run on v2.
- [x] Free-account dormancy behavior is explained during setup.

## Risks and defaults

- Critical history loss: verified restricted backup, staging, atomic switch,
  and hash-proven rollback.
- Critical false merge: strict evidence tiers and ambiguity quarantine.
- Critical secret exposure: SecretStr, injected test mappings, redacted errors,
  and no raw payload persistence.
- Hidden historical rows: migrated local archive remains authoritative.
- Missing update/deletion markers: fingerprints, overlap, monthly full
  reconciliation, and detail confirmation.
- `[AMENDED]` Bouldering payload: the manual endpoint returned HTTP 422 and a
  non-creating validation probe confirmed `Invalid type [Bouldering]`.
  The athlete explicitly approved `RockClimbing`, which the live validator
  accepts and which matches the preserved original Strava source label. This
  requires a fresh plan digest and approvals; it is not a silent fallback.
  The first amended canary was created but failed strict factual read-back;
  exact cleanup verified absence. A field-name-only diagnostic retry now
  requires explicit authorization. That authorized retry isolated the mismatch
  to `perceived_exertion`; the manual contract instead writes athlete RPE
  through `icu_rpe`. The corrected fresh dry run passes and invalidates every
  earlier approval.
- `[UNKNOWN]` Garmin/manual live fields: strict spec-derived fixtures plus
  controlled acceptance samples.
- `[UNKNOWN]` bulk personal-key event semantics: keep single-event upserts.
  Live creation proves the server replaces the requested UID, so later
  mutations use the manifest-bound server UID.
- Wellness/webhooks are out of scope; local metrics and polling remain
  authoritative.
- Unrelated large plan/profile modules are separate debt, not migration scope.

## Completion gate

Completion requires cross-linked plan/issue/status/weekly/approved brief;
preservation of user-owned changes; verified backup and rollback proof; exact
accounting for 1,114 source records and 56 screenshot records; v2-only archive
validation and deterministic metrics; idempotent sync with edit/deletion/resume
coverage; strict climb mapping; source/sensor sibling coverage; safe workout
publication lifecycle; fully green offline tests and all architecture/security/
docs guardrails; no unresolved high-severity review finding; removal of unused
`requests` if confirmed; and zero unclassified obsolete active-provider
occurrences.

## Progress

- [x] 2026-07-28: Reproduced baseline environment with Poetry.
- [x] 2026-07-28: Confirmed 1,114 activity files without modifying them.
- [x] 2026-07-28: Reproduced 883 passed, 3 failed, 10 skipped.
- [x] 2026-07-28: Materialized this living plan.
- [x] Phase 0 continuity links and the explicitly approved vault brief are
  complete.
- [x] Phase 1 harness green.
- [x] Phase 2 workflow decomposition complete.
- [x] Phase 3 final schemas/config/workouts complete.
- [x] Phase 4 dry-run and isolated rollback proof complete.
- [x] Phase 5 typed client complete.
- [x] Phase 6 reconciliation complete.
- [x] Phase 7 archive cutover and safe partial sync complete.
- [x] Phase 8 publication implementation complete with offline ownership tests.
- [x] Phase 9 athlete surfaces complete.
- [x] Phase 10 removal/docs complete.
- [x] Findings-first hardening closed interrupted sync/publication transactions,
  DST timestamp ambiguity, remote event drift, and active tombstone leakage.
- [x] Added a current-candidate-bound athlete review queue and hash-based,
  idempotent approval ledger for conservative historical matches.
- [x] Added atomic exact-event completed-workout matching and report-only
  date/sport/time fallback candidates.
- [x] Added plan-wide future-workout reconciliation with setting-sensitive
  upserts, per-workout partial reporting, and non-destructive stale detection.
- [x] Connected temporary original-file hashing to unresolved identity
  decisions without retaining raw file content.
- [x] Added exact-fingerprint acknowledgement for stable validation
  quarantines; unsupported sports and logical conflicts remain fail-closed.
- [x] Added a read-only external-deletion review queue before the existing
  explicit tombstone confirmation.
- [x] Hardened event deletion and local manifests against cascading deletes
  and cross-workout ownership identity collisions.
- [x] Resolved all 41 conservative review rows: 39 linked to historical
  records and two proven Wahoo/Garmin duplicate recordings excluded.
- [x] Acknowledged the four exact validation-quarantine fingerprints and
  completed full and incremental no-op syncs.
- [x] Created a nine-week macro plan and validated/applied Week 1 with two
  structured runs and one structured ride.
- [x] Published three owned events, recovered their server-assigned UIDs, and
  proved an immediate repeated publication is a three-event no-op.
- [x] Re-fetched all three exact remote events in a later read-only audit and
  re-proved server UID, external ID, category, sport, date, and rendered-text
  ownership; a fresh incremental activity sync remained a complete no-op.
- [ ] Phase 11 acceptance and outcomes complete.
- [x] 2026-07-29: Implemented the ownership-safe historical bouldering
  backfill offline; live dry run and separate canary/application approvals
  remain tracked in the dedicated plan.

## Discoveries

- 2026-07-28: The current ignored credential is expired. No legacy sync was
  attempted before backup.
- 2026-07-28: The worktree began with user-owned changes to `CLAUDE.md` and
  deleted `.claude/worktrees/*` entries. They must remain untouched unless an
  overlapping edit is explicitly reconciled.
- 2026-07-28: The legacy importer stored local wall time in its sole timestamp
  and moving time in its sole duration. Historical-only wall-clock and
  moving-duration comparison was required to avoid false duplicates.
- 2026-07-28: The first live reconciliation exposed an unsafe merge that
  replaced preserved historical duration/occurrence fields. A deterministic
  repair restored all 1,114 migrated records to the exact migration totals,
  retained 60 external links, and left all 11 new records intact.
- 2026-07-28: The account returned 46 hidden historical rows, 41 review-window
  ambiguities, and four invalid sensor payloads. Athlete-authorized review
  later linked 39 rows, excluded two cross-device duplicate recordings, and
  acknowledged the four exact failure fingerprints.
- 2026-07-28: Sanitized error-location inspection proved all four mapping
  quarantines are impossible interval maximum-speed spikes above the canonical
  safety bound. No personal payload or raw identifier was emitted or retained.
- 2026-07-28: A phase review found that a successful remote workout upsert
  followed by failed read-back could strand an owned event. A durable
  pre-mutation intent and recovery path now makes create/update/delete
  interruption-safe without blind mutation retries.
- 2026-07-28: The initial completion-link implementation would have mutated a
  separate ledger before activity/load staging succeeded. The completion
  ledger now participates in the archive/metrics/sync-state rollback
  transaction, and exact pairings are idempotent.
- 2026-07-28: Adding completion policy directly to the sync service pushed it
  above the 800-line warning threshold. Extracting the pure policy restored the
  service to 752 lines without changing behavior.
- 2026-07-28: `rollback_verified: false` on the applied real run means the
  active archive has not been rolled back. Disposable apply/rollback and
  failure-reversal tests prove recovery without undoing the accepted cutover.
- 2026-07-28: Completion audit found that original-file download and
  hash-based matching existed separately but were not connected. Ambiguous
  matches now trigger one temporary in-memory hash probe; all 41 live
  ambiguities were probed and none produced a unique file-hash match.
- 2026-07-28: Validation quarantines had no explicit athlete acceptance path.
  The review surface now exposes only hashed identity, validation location/type,
  and a failure fingerprint. An acknowledgement applies only to that exact
  current fingerprint and does not weaken or bypass canonical validation.
- 2026-07-28: Exact calendar deletion omitted the API's optional `others`
  query flag. It now sends `others=false` explicitly, preventing reliance on a
  server default that could cascade to related events.
- 2026-07-28: External activity deletion required explicit confirmation but
  had no athlete-legible preflight queue. The current `404` candidates can now
  be inspected from retained local facts before tombstoning.
- 2026-07-28: A broad lint audit found 618 pre-existing findings in legacy
  modules outside this migration. Correctness-first cleanup is tracked in
  `docs/issues/engineering-debt-full-ruff-baseline.md`; all changed migration
  modules remain Ruff-clean.
- 2026-07-28: Two review candidates were historical records already linked to
  another recording of the same physical ride, one Wahoo and one Garmin.
  Approving them would have overwritten external ownership. Hash-bound
  duplicate exclusions now close these rows without merging or deleting data.
- 2026-07-28: The live personal-key event endpoint accepted deterministic
  external IDs but replaced submitted UUIDv5 UIDs with server UUIDs. The
  manifest now audits the requested UUID separately and uses the exact
  server-assigned UID for update, reschedule, and deletion proof.
- 2026-07-28: The final ignored-state audit found a retired
  `data/athlete/training_history.yaml` containing only obsolete sync fields.
  Its verified rollback copy remains in the restricted backup; the active file
  and its unused path/schema entrypoints were removed.
- 2026-07-28: A later acceptance refresh found no new activity sample and no
  archive change. All three owned remote events still match their manifest,
  and API-side Garmin/Wahoo connections, forwarding toggles, sport settings,
  filters, and account timezone remain publication-ready.

## Decision log

- 2026-07-28: Use a single personal API key, athlete alias `0`, handwritten
  DTOs, canonical SI-unit schema, 90-day bisection-capable initial windows,
  30-day incremental overlap/monthly reconciliation, deterministic IDs and
  fingerprints, retained deletion tombstones, native workout text,
  deterministic external IDs plus audited UUIDv5 requests, and exact-event
  mutation through server-assigned UIDs.
- 2026-07-28: Keep readiness/load local; exclude webhooks, wellness import,
  provider plugins, generalized workbenches, schedulers, and broad monolith
  refactors.
- 2026-07-28: Treat migrated occurrence, duration, distance, elevation,
  athlete-authored facts, and existing calculated load as immutable during
  automatic linking. External data may attach identity/provenance and fill
  missing sensors/device facts. Current external records still accept
  fingerprinted late edits.
- 2026-07-28: Keep unresolved live rows in a sanitized partial checkpoint.
  Review is required before any manual match; completeness is never inferred
  from a partial run.
- 2026-07-28: Treat Intervals.icu's empty Garmin upload-filter list as
  unrestricted; when filters are present, publication requires a positive
  workout-sport match. Both Garmin and Wahoo forwarding toggles must be enabled
  for their connected devices.
- 2026-07-28: Resolve naive external wall times from the authoritative UTC
  instant and named timezone. Reject inconsistent/nonexistent wall times and
  ambiguous planned-workout times rather than guessing a DST fold.
- 2026-07-28: Retained external-deletion tombstones are archival only. Metrics,
  profile, VDOT, planning matches, and default activity surfaces exclude them.
- 2026-07-28: Manual match approvals store no external plaintext ID and never
  mutate the archive directly. A later sync applies an approval only while the
  exact local ID remains a candidate under current sport/date/rule evidence.
- 2026-07-28: Completed-workout state is provider-neutral and separate from
  canonical activity v2. Exact owned event IDs may create a durable match;
  unique date/sport/time candidates remain report-only.
- 2026-07-28: Plan-wide publication never deletes a stale manifest event.
  It reconciles only future structured workouts, uses the existing exact
  ownership path, and reports per-workout errors after retaining each verified
  earlier mutation.
- 2026-07-28: Raw original activity files remain transient. Only a SHA-256 may
  enter canonical provenance after a unique link or explicit reviewed match.
- 2026-07-28: A stable canonical validation exclusion may stop blocking a
  complete cursor only after exact-fingerprint acknowledgement. A payload or
  failure-shape change invalidates that acknowledgement automatically.
- 2026-07-28: Publication and completion manifests revalidate after in-memory
  mutation. Cross-workout event IDs, UIDs, external IDs, or duplicate
  completion ownership fail before persistence or remote deletion.
- 2026-07-28: For personal-key calendar events, deterministic external ID is
  the stable namespace. The requested UUIDv5 is retained for audit; the
  server-assigned UID becomes the exact remote mutation identity after
  read-back.

## Outcomes

Implementation evidence on 2026-07-28:

- The deterministic dry-run digest is
  `a800d7aa03e451cd73b8a836332ae7e9c73d659581ca44a3f2a32d8e488c8baa`.
  All 1,114 source records and all 56 screenshot imports reconciled exactly:
  5,541,553 duration seconds, 8,735,943.9 distance metres, 103,995.3
  elevation metres, 67,604.3 systemic-load AU, and 25,779.2 lower-body-load
  AU.
- The restricted backup at
  `data/backups/activity-v2/migration-a800d7aa03e4/` contains 2,775
  manifest-verified files. Isolated apply/rollback tests restore activities,
  metrics, athlete profile, plans, sync state, and publication state.
- The active archive contains 1,125 valid schema-v2 records: 1,114 preserved
  historical records plus 11 new external records. It has 110 external links,
  literal `_schema` serialization, no obsolete provider text, and the original
  historical aggregate totals.
- Daily metrics were regenerated deterministically for 1,651 days through
  2026-07-28. Profile analysis covers the actual 1,638-day data window.
- Secret-safe live account validation succeeds for athlete timezone
  `Europe/Paris`. The authorized full reconciliation linked 39 records,
  reported 71 unchanged, and excluded two duplicate recordings. Its immediate
  incremental rerun created/updated/linked zero records with empty review and
  quarantine queues.
- The authorized review resolved all 41 sanitized ambiguous matches: 39
  linked to their historical records and two proven Wahoo/Garmin duplicate
  recordings were excluded. All four exact invalid-speed fingerprints were
  acknowledged. The completed full reconciliation is non-partial; 46 hidden
  rows remain reported without overwriting preserved history.
- The closing offline suite passes with 922 tests (50 documented warnings).
  Focused Ruff, architecture/cleanup checks, `git diff --check`, and source/
  wheel builds pass. The direct `requests` dependency is removed.
- Live forwarding preflight reports the Europe/Paris athlete timezone, Garmin
  and Wahoo connections, both workout-upload toggles enabled, and an empty
  Garmin filter list (unrestricted). The approved Week 1 contains two
  structured HR-target runs and one structured power-target ride.
- A later read-only refresh re-fetched all three event IDs and proved that
  server UID, external ID, category, Run/Ride type, local date, and rendered
  workout text still match the manifest. Run HR settings and ride FTP remain
  present. The same refresh's incremental activity sync saw five unchanged
  rows and no create/update/link, review, quarantine, or deletion outcome.
- Sync commits now restore archive, metrics, and sync state together on
  failure, include the completed-workout ledger in the same transaction, and
  recover a process interruption before retry. Publication writes a durable
  intent before remote mutation, detects remote content drift, and recovers
  interrupted create/update/delete verification.
- Exact completed-workout pairing is covered offline, including idempotency,
  ownership sport mismatch, report-only fallback, and rollback. The latest
  live full reconciliation found no exact pairs or fallback candidates.
- Plan-wide publication created three future structured acceptance workouts
  with server-assigned UIDs, and an immediate repeat produced three no-ops.
  A live calendar review then found ambiguous renderer tokens: `m` was parsed
  as minutes rather than metres and `% max HR` as power rather than heart
  rate. The renderer now uses `mtr` and `% HR`; both run events were updated
  in place, read back as 5,000/8,000 metres with HR targets, and repeated as
  no-ops.
- The athlete confirmed that no training plan is currently active and
  explicitly requested removal of the acceptance fixtures. All three exact
  manifest-owned events were deleted, each returned `404`, no Resilio-owned
  event remained in the week, and the publication manifest is empty. The
  unstarted local plan and review were hash-preserved in the plan archive and
  removed from the active-plan paths.
- All 41 conservative historical overlaps were reviewed with explicit athlete
  authorization. Thirty-nine candidate-bound approvals linked successfully;
  two already-owned cross-device recordings were closed through exact
  review-fingerprint exclusions.
- The four validation quarantines resolve to the same sanitized failure
  fingerprint: `maximum_speed_meters_per_second` violates its upper bound.
  All four exact fingerprints were explicitly acknowledged.
- The required mapping matrix now has explicit regression coverage for every
  documented run, ride, climbing, strength, swim, and other variant;
  Garmin/Wahoo/manual/upload provenance; distance-free manual yoga; and
  power/cadence measurements.
- Exact event deletion sends `others=false`. Publication manifests reject
  cross-workout event/UID/external-ID collisions, and completion manifests
  reject one workout matching multiple activities.
- The live external-deletion review queue is empty.
- A direct ignored-state audit validated all 1,125 active files as literal
  activity v2, verified all 2,775 backup hashes and `0700` backup permissions,
  found one credential key (`INTERVALS_ICU_API_KEY`), and found zero obsolete
  provider occurrences across active activities, athlete state, sync state,
  and plans.

Remaining acceptance gates:

- The corrected historical `RockClimbing`/`icu_rpe` canary passed every
  automated gate and is awaiting athlete visual acceptance; manual yoga
  remains pending. A live
  Garmin/Wahoo sibling pair is now proven through the duplicate-recording
  review.
- When the athlete starts a real plan, publish an approved run and ride and
  observe physical Garmin/Wahoo delivery. No acceptance-only workout is left
  on the calendar.
- Live rescheduling remains optional acceptance evidence; ownership-safe
  in-place update and exact deletion are now live-proven.
