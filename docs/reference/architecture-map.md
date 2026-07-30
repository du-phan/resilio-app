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
| Canonical completed activity v4 | Synchronized provider facts, native analysis, zone-setting identity, and retained historical provenance |
| Activity aerobic load, decoupling, polarization, TRIMP, heart-rate recovery, applicability flags, and zone time | Intervals.icu analysis; missing values remain missing |
| Wellness and training state | Intervals.icu daily wellness |
| Thresholds, zones, and priorities | Intervals.icu sport settings |
| Athlete profile v2 | Athlete-confirmed durable facts |
| Provider profile candidates | Read-only projections from settings and wellness |
| VDOT approval | Recomputable performance plus a verified canonical activity/fingerprint or exact profile personal best, or an explicit athlete-confirmed manual value; every approval also binds the proposal path and byte SHA-256 |
| Plan and all approvals | One atomic planning-state v3 aggregate with immutable revision identities |
| Weekly application | Exact proposal path, byte SHA-256, target-week hash, and prior applied-workout hash |
| Completed-workout adherence | Exact owned-event pairing manifest |
| External calendar ownership | Local manifest plus matching remote readback |
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

`resilio/core/coaching_context/` builds a typed weekly read model:

- `service.py` coordinates repositories and the as-of boundary;
- `exposure.py` separates run and other-sport exposure and preserves zone
  coverage;
- `recovery.py` creates individual baseline comparisons;
- `adherence.py` accepts only exact owned completion matches.

It deliberately does not compute a composite readiness score, injury
probability, local performance-management chart, or cross-sport multiplier.
Context durations and planned intensity exposure remain exact seconds.
Multi-week history explicitly separates the target week from the evidence
window, and sparse wellness signals retain observation date, age, temporary
status, personal median, sample count, and missingness.

Coaching evidence coverage is date-scoped and reads only strict sync-state v3
coverage windows. Complete source windows, unresolved source gaps, and
explicit exclusions are separate contracts; a partial sync never promotes its
requested range to complete and no obsolete checkpoint field can act as a
fallback. Historical adherence resolves
the exact immutable applied-week snapshot, schedule timezone, and approval
interval that was authoritative at each workout's scheduled instant,
including retired and replaced revisions. Competing authorities, invalid local
wall times, or changed approval-bound content make adherence unavailable
rather than guessed.

## Planning package

`resilio/core/planning/` separates approval evidence, content fingerprints,
methodology-independent policy, persistence, profile-driven invalidation,
historical adherence, publication evidence, and orchestration. The plan
mutation lock is shared by planning services and profile updates. A
planning-relevant profile update uses a durable profile/plan transaction
journal under that lock. Recovery rolls back a prepared or partially written
pair and rolls forward a committed pair, so readers never accept mismatched
profile and plan state after an abrupt process stop. Profile, planning, VDOT
file, and VDOT-source reads use that same coordinated boundary. Proposal,
VDOT approval, macro creation, macro approval, weekly approval, weekly
application, invalidation, and retirement timestamps must be chronological;
persisted-state validation rejects an impossible sequence even if a service
was bypassed.

## Mutation boundaries

- Completed sync uses one activity-mutation lock, staged archive, durable
  phase journal, coordinated wellness/settings/completion/state sidecars, and
  idempotent crash recovery.
- Ambiguous mappings and canonical mapping failures are sanitized and
  quarantined without raw payload persistence. A malformed external DTO
  collection rejects that sync boundary before canonical mutation.
- External-source fingerprints and canonical mapping versions are independent:
  source facts decide whether the provider record changed, while the mapping
  version forces deterministic remapping when canonical logic changes.
- Weekly plans apply only when the current file path and SHA-256 match the
  recorded approval, macro revision, week skeleton, and previous applied
  content.
- Publication resolves workouts by opaque ID from fresh, macro-approved,
  applied weekly content; callers cannot publish an arbitrary workout object.
- Calendar update or deletion requires deterministic local identity, manifest
  ownership, and exact remote proof.

See the [Intervals.icu integration reference](intervals-icu-integration.md) for
the external boundary and [agent workflow](../guides/development/agent-workflow.md)
for change discipline.
