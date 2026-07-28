# M04 — athlete profile

Status: active
Last verified: 2026-07-28

## Purpose

The profile subsystem owns athlete-authored identity, goals, constraints,
preferences, personal bests, and multi-sport commitments. It also derives
profile observations from the canonical local activity archive.

Implementation:

- `resilio/schemas/profile.py`: persisted and API-facing profile contracts
- `resilio/core/profile.py`: deterministic profile calculations and validation
- `resilio/api/profile.py`: supported use-case surface
- `resilio/cli/commands/profile.py`: athlete-facing commands and envelopes

The only persisted profile file is `data/athlete/profile.yaml`.

## Boundaries

This subsystem does not own:

- completed activities (`CanonicalActivity` v2 owns them);
- completed-activity sync state (`data/state/activity_sync.json` owns it);
- daily load/readiness metrics (`data/metrics/` owns them);
- workout publication identity (`data/state/workout_publications.json` owns it);
- training-plan generation or mutation.

There is no separate training-history or provider-specific profile state.
Profile analysis reads active canonical activities and never transport DTOs or
raw external payloads.

## Domain contract

`AthleteProfile` contains:

- identity and optional physiology/vital signs;
- a current goal;
- run-day, session-time, and scheduling constraints;
- approved VDOT and derived training paces;
- personal-best entries;
- `other_sports`, including frequency and availability;
- running priority and conflict policy;
- communication preferences.

Important invariants:

- training weeks and unavailable-day values use Monday–Sunday semantics;
- min/max run-day and session-duration constraints must be internally valid;
- `other_sports` reflects actual activity distribution, while
  `running_priority` controls conflict resolution;
- profile-derived recommendations do not overwrite athlete-authored
  constraints or approvals silently;
- inactive external-deletion tombstones do not enter profile analysis.

## Supported API operations

Callers use `resilio.api.profile`, not `resilio.core.profile` directly:

- `create_profile`
- `get_profile`
- `update_profile`
- `set_personal_best`
- `set_goal`
- `analyze_profile_from_activities`
- `add_sport_to_profile`
- `remove_sport_from_profile`
- `pause_sport_in_profile`
- `resume_sport_in_profile`
- `validate_profile_completeness`

`analyze_profile_from_activities` reports the actual synchronized date range,
activity count, gaps, heart-rate coverage, recent running volume, workout
patterns, and sport distribution. It may update derived workout-pattern fields
but does not claim a fixed history span.

## Storage and failure behavior

Repository reads and writes validate `AthleteProfile` through Pydantic. Invalid
or missing data returns a typed profile error at the API boundary. Writes use
the repository transaction behavior and never modify sync state, metrics, or
calendar publication state.

The completed-activity integration is intentionally absent from this module:

```text
integrations -> canonical activity archive -> profile analysis
```

Transport DTOs must not cross directly into profile, coaching, load, metrics,
or planning code. The architecture guard suite enforces this dependency
boundary.
