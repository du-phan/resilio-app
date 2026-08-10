# Architecture map

Resilio is a local, provider-neutral coaching application. Intervals.icu is the
only external activity-analysis and workout-calendar boundary. Resilio owns
canonical archival state, athlete-confirmed facts, planning methodology,
coaching judgment, approvals, and publication ownership.

```text
.env.local + config/settings.yaml
              |
              v
resilio/integrations/intervals_icu
  strict DTOs -> HTTP client -> pure mappers
              |
              v
resilio/schemas <-> focused repositories
              |
              v
resilio/core
  activity_sync | coaching_context | profile | planning
  workout_publication | vdot | weather | memory
              |
              v
resilio/api -> resilio/cli -> JSON envelopes
```

## Dependency rules

| Package | Owns | Must not own |
| --- | --- | --- |
| `resilio/schemas` | Provider-neutral persisted and domain contracts | I/O, HTTP, API, or CLI dependencies |
| `resilio/integrations` | External DTOs, transport, and boundary mapping | Profile mutation or coaching decisions |
| `resilio/core` | Deterministic calculations, repositories, and application services | CLI output or API imports |
| `resilio/api` | Presentation-neutral callable use cases and typed errors | External DTO leakage or domain calculations |
| `resilio/cli` | Argument parsing, JSON envelopes, and exit codes | Transport or coaching logic |

Architecture tests mechanically enforce dependency direction, module-size
budgets, current documentation links, active-state vocabulary, and the skill
mirror.

## State ownership

| State | Authority |
| --- | --- |
| Canonical completed activity v5 | Synchronized provider facts, interval measurements, provider feedback, native analysis, zone-setting identity, and retained historical provenance |
| Activity aerobic load, decoupling, polarization, TRIMP, heart-rate recovery, applicability flags, and zone time | Intervals.icu analysis; missing values remain missing |
| Wellness and training state | Intervals.icu daily wellness |
| Thresholds, zones, and priorities | Intervals.icu sport settings |
| Athlete profile v3 | Athlete-confirmed durable facts, run constraints, flexible or recurring athlete-managed sport expectations, and one training priority |
| Provider profile candidates | Read-only projections from settings and wellness |
| VDOT approval | Recomputable performance plus a verified canonical activity/fingerprint, exact profile personal best, owned closed assessment review, or explicit athlete-confirmed manual value; every approval also binds the proposal path and byte SHA-256 |
| Plan lifecycle and approvals | Compact planning-state v6 with a discriminated race-macro or baseline-assessment active plan, generic plan revision/approval identity, and immutable content-addressed archives and evidence artifacts |
| Race-plan renewal evidence | Coverage-aware cycle review, athlete-confirmed goal outcome and performance, all closed race summaries and assessment results, 52 compact historical weeks, 12 detailed recent weeks, and source-state freshness fingerprints |
| Baseline-assessment evidence | Immutable assessment context, one owned timed-distance workout, exact publication/completion pairing, athlete-selected whole activity or exact canonical segment, and separately confirmed closure |
| Weekly application | Exact run-only proposal path, byte SHA-256, target-week hash, prior applied-running-workouts hash, immutable weekly context, and complete configured/observed other-sport considerations |
| Completed-workout adherence | Exact owned-event pairing manifest |
| Run synchronization preferences | Athlete-confirmed automation mode, calendar-day policy, and requested Garmin destination |
| External calendar ownership | Local manifest plus matching remote UID/external ID, owned-field fingerprint, semantic parsed-workout readback, drift-resolution audit, and push-error evidence |
| Raw external response | Ephemeral only |

## Coordinated state boundary

Activity archive, wellness, sport settings, sync state, profile, planning
aggregate, and publication/completion manifests are one migration state set.
Migrations validate and stage candidates, preserve a recoverable backup, switch
same-filesystem paths atomically where applicable, verify identities and
digests, and demonstrate rollback before touching athlete state. The `data/`
tree is private state: writers maintain mode `0700` on directories and `0600`
on files, and permission hardening rejects symlinks rather than following
them.

## Coaching-context boundary

`resilio/core/coaching_context/` builds typed weekly and exact-activity read
models:

- `service.py` coordinates repositories and the as-of boundary;
- `exposure.py` separates run and other-sport exposure and preserves zone
  coverage;
- `recovery.py` creates individual baseline comparisons;
- `exact_activity.py` binds one complete canonical activity to its completion,
  as-of recovery, training-state, and optional provider curve evidence;
- `adherence.py` accepts only exact owned completion matches.

It deliberately does not compute a composite readiness score, injury
probability, local performance-management chart, or cross-sport multiplier.
Context durations and planned intensity exposure remain exact seconds.
Multi-week history explicitly separates the target week from the evidence
window, and sparse wellness signals retain observation date, age, temporary
status, scale direction, seven-day observations and coverage, personal median
from up to 28 prior days, sample count, freshness, and missingness. A baseline
requires at least seven prior observations. Calendar-day wellness never proves
that an observation preceded an activity on the same date.

Coaching evidence coverage is date-scoped and reads only strict sync-state v3
coverage windows. Complete source windows, unresolved source gaps, and
explicit exclusions are separate contracts; a partial sync never promotes its
requested range to complete and no obsolete checkpoint field can act as a
fallback. Historical adherence resolves the full
plan/revision/week/workout identity and the exact immutable applied-week snapshot,
schedule timezone, and approval interval that was authoritative at each
workout's scheduled instant, including closed and replaced revisions. A closed
revision's workout authority ends on its effective closure date even when the
athlete records the closure later.
Competing authorities, invalid local
wall times, or changed approval-bound content make adherence unavailable
rather than guessed.

## Planning package

`resilio/core/planning/` separates approval evidence, content fingerprints,
methodology-independent policy, active-state persistence, immutable archives,
race-cycle review, baseline-assessment context/review/VDOT evidence, bounded
macro context, profile-driven invalidation, historical adherence, publication
evidence, exact unapproved-proposal discard, and orchestration. The plan
mutation lock is shared by planning services and profile updates. A
planning-relevant profile update uses a durable profile/plan transaction
journal under that lock. Recovery rolls back a prepared or partially written
pair and rolls forward a committed pair, so readers never accept mismatched
profile and plan state after an abrupt process stop. Profile, planning, VDOT
file, and VDOT-source reads use that same coordinated boundary. Proposal,
VDOT approval, macro- or assessment-context creation, plan creation, plan
approval, weekly-context creation, weekly approval, weekly application,
invalidation, and closure timestamps must be
chronological. Persisted-state validation rejects an impossible sequence even
if a service was bypassed. Cycle closure also re-verifies the exact active-plan
snapshot and the date-bounded activity, wellness, coverage, completion, and
publication inputs used by the review. Assessment review additionally
re-verifies the owned publication/completion chain and exact canonical result.
Race-macro creation performs the analogous freshness check for its 12-week
context and must cite the latest assessment result when one exists.

## Mutation boundaries

- Completed sync uses one activity-mutation lock, staged archive, durable
  phase journal, coordinated wellness/settings/completion/state sidecars, and
  idempotent crash recovery.
- Ambiguous mappings and canonical mapping failures are sanitized and
  quarantined without raw payload persistence. A malformed external DTO
  collection rejects that sync boundary before canonical mutation.
- Provider-snapshot hashes, performance-evidence hashes, and canonical mapping
  versions have separate authority. The provider snapshot detects any mapped
  provider change, including feedback. Performance evidence binds immutable
  planning and assessment decisions only to measured execution facts. Mapping
  version changes force deterministic remapping without pretending that the
  provider changed.
- Weekly plans apply only when the current file path and SHA-256 match the
  recorded approval, plan revision, week skeleton, previous applied running
  content, immutable week-planning context, and unchanged synchronized
  evidence. The proposal must consider every configured athlete-managed sport
  and every non-running sport observed in that context by exact activity ID.
  The API returns local commit and automatic run-synchronization
  outcomes separately; provider failure never rolls back the local commit.
- Unapproved proposal discard requires the exact current revision ID, empty
  plan/weekly approval state, no applied revisions, and no matching publication
  or completion ownership. Approved plan removal remains impossible here.
- Weekly application policy accepts only running workouts and requires a typed
  structured prescription for each one. Publication resolves a qualified
  plan/revision/week/workout identity from fresh, plan-approved, applied weekly
  content; non-running prescriptions cannot enter this lifecycle. A date-only
  run projects to provider local midnight while retaining
  an absent approved start time locally. Callers cannot publish an arbitrary
  workout or reuse an ID across plan lineages.
- Calendar reconciliation holds the publication lock before the plan lock,
  derives desired state from the exact active applied week, and requires
  deterministic identity, manifest ownership, unchanged remote fingerprint,
  and semantic readback. Explicit restore-local drift resolution is separately
  athlete-confirmed and audited. Garmin-forwarding eligibility remains
  unverified delivery until the athlete confirms receipt.

See the [Intervals.icu integration reference](intervals-icu-integration.md) for
the external boundary and [agent workflow](../guides/development/agent-workflow.md)
for change discipline.
