# Intervals.icu integration

Intervals.icu is Resilio’s sole external source for completed activity
analysis, wellness/training state, sport settings, and planned-workout
calendar readback.

## Credential and transport boundary

The only production secret is `INTERVALS_ICU_API_KEY` in `.env.local`.
Non-secret transport settings live under `intervals_icu` in
`config/settings.yaml`. The client:

- uses strict request and response DTOs;
- distinguishes configuration, authentication, authorization, rate limit,
  not-found, transport, unsupported-sport, and invalid-payload failures;
- applies bounded retries only to safe reads;
- redacts credentials and never persists raw provider payloads;
- supports injected transports and sleepers for deterministic tests.

## Completed-state sync

`resilio sync` reads activity summaries and details, daily wellness, and sport
settings into a staged coordinated transaction.

```text
activity DTO -> canonical activity v4
wellness DTO -> WellnessDay
sport settings DTO -> SportSettingsSnapshot
                  |
                  v
validated staging -> atomic activity switch + coordinated state writes
                  -> completion-manifest reconciliation -> checkpoint
```

The sync:

- splits date ranges so provider result caps cannot silently truncate history;
- validates strict DTOs before mapping;
- quarantines unknown sports as explicitly acknowledgeable mapping gaps while
  invalid DTO or canonical records remain blocking;
- uses conservative overlap reconciliation;
- never infers deletion from an absent list row;
- records complete date windows, partial-attempt gaps, and explicit source
  exclusions only after their applicable durable transition;
- records bounded progress for diagnosis; an interrupted run discards
  incomplete staging and restarts its requested range on the next invocation.

Sync state is strict schema v3. Coverage authority is only
`complete_activity_windows`, `source_coverage_gaps`, and explicit exclusions;
obsolete single-window compatibility fields are neither read nor written.

An exclusion is evidence, not an inferred deletion. Hidden provider records,
athlete-acknowledged unsupported mappings, and reviewed duplicate
representations have distinct reasons. A reviewed duplicate is bound to both
the local canonical activity identity and the exact sanitized review
fingerprint. A later provider or candidate change invalidates that decision.

The external fingerprint hashes mapped provider facts only. Canonical mapping
version 7 is stored separately, so a mapper release remaps unchanged provider
records without pretending their source facts changed.

Both provider `Bouldering` and `RockClimbing` map to canonical `climb`.
Athlete RPE is read with explicit provenance. A provider RPE without confirmed
duration-based session-RPE remains distinct from athlete-confirmed subjective
effort.

## Native analyzed values

Canonical activity v4 may preserve:

- aerobic load points and calculation method;
- relative intensity, aerobic decoupling, polarization index, and TRIMP when
  the provider supplies them;
- native heart-rate recovery with sample indices, offsets in seconds, heart
  rates in beats per minute, average power in watts, and recovery in beats per
  minute;
- native applicability flags that state whether time, power, heart rate,
  velocity, or pace analysis was ignored;
- heart rate, power, cadence, pace, elevation, device, and source fields with
  explicit units;
- provider intervals as typed activity segments;
- native power-zone time as provider-ID/duration-second objects; provider IDs
  are preserved and linked to captured names and bounds only by an exact,
  unambiguous name match; fingerprinting is independent of provider response
  order and canonical zones are ordered by resolved zone index followed by
  provider ID;
- native heart-rate, pace, or grade-adjusted-pace zone time as
  duration-second arrays whose ordinal positions are bound to captured upper
  bounds, optional native names, units, coverage percentage, and matching
  analysis-settings SHA-256.

The list operation validates only its required summary identity and ordering
fields; full analyzed facts are accepted only from the detail operation.
Polarization is preserved as a signed, finite provider value. Provider sensor
spikes such as extreme maximum speed remain source evidence rather than
causing the entire activity to disappear.

Wellness preserves provider fitness, fatigue, ramp, contribution values,
recovery observations, provider readiness, VO2 max, and the upstream
hydration-volume value without asserting an undocumented physical unit. Sport
settings
preserve sport-scoped FTP, LTHR, maximum heart rate, threshold speed in meters
per second, the separate pace display preference, named zones,
load/time-in-zone/workout priorities, and a source fingerprint.

Resilio does not recompute a missing native analyzed value. Missingness is a
first-class state.

Native applicability is retained alongside the analysis so absence and
provider-declared inapplicability are not conflated. Polarization is not
reinterpreted as zone-distribution evidence because the provider response does
not prove the zone basis used for that scalar.

Activity detail does not claim activity-time fitness, fatigue, form, or
temperature when those facts are absent from the validated provider contract.
Fitness and fatigue history come from dated wellness records. A provider
session-RPE load retains its provider-defined duration basis; athlete-entered
session-RPE uses an explicit elapsed-time basis.

## Athlete-profile candidates

Sport-setting thresholds and the latest wellness resting heart rate or VO2 max
are exposed through `resilio profile candidates`. Every candidate includes its
unit, sport scope, settings identity or observation date, provider update time,
and temporary flag. This surface is read-only; athlete confirmation is
required before changing athlete-owned profile facts.

## VDOT evidence provenance

A VDOT race proposal may reference synchronized evidence only through the
canonical local activity ID and the exact Intervals.icu source fingerprint.
Approval and every later use reverify that the activity remains active,
running, and identical in local date, elapsed seconds, timezone, and source
fingerprint. Personal-best proposals instead reverify exact distance, date,
and elapsed seconds against the athlete-confirmed profile. Proposal and
approval dates are evaluated in the declared performance or athlete training
timezone, never the host machine’s date.

## Planned running-workout synchronization

Resilio publishes only typed running workouts with deterministic external
identities. Every approved run has a provider-neutral structured prescription;
bouldering and all other sports stay local. Date-only runs remain date-only in
coaching state and use local midnight only as the Intervals calendar
representation. An exact athlete-approved time takes precedence.

The bounded workflow reads athlete-confirmed synchronization preferences,
reports Intervals/Garmin capabilities, inspects one exact applied week without
mutation, then reconciles only that week's running-workout desired state.
Applying an approved week triggers reconciliation immediately when automation
is enabled and returns local-commit and provider outcomes separately. The
active applied week remains the durable retry obligation; no background daemon
or redundant outbox is required. A later explicit reconcile is idempotent.
Pace targets require Run threshold pace and pace zones. Percent-LTHR and
percent-max-heart-rate targets require their corresponding Run setting;
absolute-heart-rate and targetless workouts require none of those metrics.
The capability projection reports these target styles independently and lists
missing settings as limitations, not as blockers for unrelated target styles.
Wahoo configuration never blocks this workflow.

Provider names are deterministic, date-independent, derived from executable
content, and limited to 15 characters for small watch lists. Examples include
`Easy4K`, `Tempo2x7m`, `Interval6x800m`, and `5KTest`; opaque abbreviations are
not used. Moving a workout to another calendar day does not rename it.
Identical structures reuse the same name; only genuinely different structures
with the same summary receive a compact variant suffix. The full purpose
remains in the description. Workout text puts prompts before step termination
tokens and emits explicit `intensity=...` metadata. One run uses at most one
target mode.

After create or update, Resilio reads the event back and requires exact owned
fields plus semantic equivalence of the typed provider-parsed workout document.
It compares ordered expanded steps, termination, explicit intensity, prompts,
cadence, and targets. Provider-estimated time is ignored when distance
terminates a step. A nonempty but incomplete workout document fails with
`provider_semantics_mismatch`. Resilio persists provider-computed planned
aerobic load, relative intensity, fitness, fatigue, and downstream push errors
when supplied. Intervals synchronization and Garmin forwarding are distinct
results. `eligible_unverified` proves only the observed Intervals
connection/settings/filter and absence of a reported Garmin push error; it
never proves Garmin Connect or the watch received the workout.
Garmin Connect can present third-party workouts as read-only; edits remain
local-plan changes followed by reconciliation. The Garmin workout-list preview
is target-oriented, not a step-count proof. A targetless run can therefore show
`--` instead of a colored target skyline while still containing valid
distance/time steps, intensities, and prompts.

The publication manifest plus exact remote UID/external ID and the last
verified owned-field fingerprint is the ownership proof. Update, reschedule,
and delete refuse ambiguous, unowned, or drifted events. One canonical lock
order holds publication authority before plan authority for reconciliation and
plan closure. A replacement week updates retained identities and deletes only
removed future, uncompleted events after exact ownership proof. Past and
completed events remain for pairing. Explicit restore-local drift resolution
records athlete confirmation before overwriting exact owned content; ordinary
reconciliation never overwrites drift. Completed-workout adherence accepts
only the provider’s exact paired event identity; date/sport/duration resemblance
remains a report-only candidate.

Only a qualified plan/revision/week/workout identity resolved from the active
planning-state aggregate may be published. The aggregate must have a fresh
planning-profile fingerprint, an approved plan skeleton, an active
applied-week approval, and an unchanged applied-workout SHA-256. Publication
and completion manifests retain that full lineage.

Historical adherence is revision-aware: content-addressed closed-plan archives
retain their plan approval, closure facts, lifecycle-review evidence, and
immutable applied-week snapshots. The resolver compares approval,
invalidation, and closure instants with each workout's scheduled UTC instant
using the recorded IANA timezone. It refuses competing revisions, missing
approvals, invalid or ambiguous local wall times, changed approval-bound
content, or an archive whose bytes no longer match its planning-state
reference. The effective closure date is the final workout-authority boundary;
a later administrative closure timestamp cannot extend the training cycle.

Completed and did-not-finish target events can retain one athlete-confirmed
canonical activity with distance, elapsed and moving duration, elevation,
aerobic load, subjective effort, thresholds, and native analysis when those
measurements exist. Macro planning receives that immutable goal-performance
summary instead of trying to rediscover a historical race heuristically.

## Crash consistency

Completed sync writes a durable journal before switching state. Its phases
record preparation, previous-archive displacement, staged-archive activation,
sidecar application, and commit. Startup rolls back any pre-commit phase and
rolls forward a durable commit. File contents and directory entries are
flushed before the next phase is recorded.

Planning-relevant profile changes use a separate durable transaction journal
for the athlete profile and dependent planning aggregate. Recovery rolls back
incomplete phases and rolls forward the committed pair.

## Operational commands

- `poetry run resilio auth status`
- `poetry run resilio sync`
- `poetry run resilio sync --full`
- `poetry run resilio sync --status`
- `poetry run resilio activity-review ...`
- `poetry run resilio profile candidates`
- `poetry run resilio coach history --as-of <DATE> --weeks <COUNT>`
- `poetry run resilio workout ...`

See the [CLI index](../coaching/cli/index.md) and
[architecture map](architecture-map.md).
