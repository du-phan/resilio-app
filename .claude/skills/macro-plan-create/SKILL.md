---
name: macro-plan-create
description: Create a methodology-explicit Monday-Sunday macro plan skeleton from an approved baseline VDOT, confirmed profile, and goal, then return it for separate athlete approval. Use after baseline VDOT approval and before exact weekly workout generation.
---

# Create a macro plan

Operate non-interactively. Do not ask the athlete questions, approve the plan,
or generate exact workouts.

## Preconditions

Require:

- an approved baseline VDOT bound in approval state;
- a confirmed goal and profile constraints;
- a complete enough synchronized history to establish recent run exposure;
- a target date that fits a contiguous Monday-Sunday plan horizon.

Return a blocking checklist if any item is absent.

## Methodology selection

Read `docs/coaching/methodology.md`. The controlled registry resolves the
matching source-only record and its exact SHA-256. Select one conceptual
methodology reference for the complete plan. The plan remains coach-designed
from athlete evidence and constraints:

- `daniels` for VDOT-anchored, purpose-specific running across race distances;
- `pfitzinger` for experienced marathon preparation with adequate running
  frequency and durable volume;
- `fitzgerald_80_20` when reliable intensity evidence and disciplined
  low-intensity volume are central;
- `first` is unavailable until edition-specific pace and schedule tables are
  verified and encoded.

Do not claim an edition-specific progression, pace, long-run share, recovery
cycle, or taper rule from these conceptual records. The draft records only the
identifier and an athlete-specific rationale; the registry binds the source
and labels the authority `coach_designed_conceptually_informed`.

## Workflow

1. Inspect:

   ```bash
   poetry run resilio approvals status
   poetry run resilio profile get
   poetry run resilio plan status
   ```

2. Use completed run distance, duration, frequency, and longest-run exposure as
   the starting-capacity evidence. Use Intervals.icu native aerobic load,
   fitness, fatigue, decoupling, polarization, TRIMP, and zone evidence only
   when supplied and with their coverage/provenance. Keep other-sport exposure
   separate. Never translate another sport through a multiplier into running
   distance. Never average activity polarization indices or infer meaning from
   raw decoupling with an unknown coupling basis.

3. Build contiguous Monday-Sunday weeks ending on a week that contains the goal
   date. For every week specify phase, `target_run_volume_meters`,
   recovery-week status, typed quality-session hints, and either typed long-run
   hints or explicit null when that week prescribes no long run. Leave
   `workouts` empty. For `fitzgerald_80_20`, every week must also contain
   `intensity_distribution.methodology: fitzgerald_80_20` and a
   `minimum_low_intensity_time_percent`; every other methodology must leave
   `intensity_distribution` null.

4. Progress only from demonstrated exposure and athlete constraints. A
   percentage rule is not proof of capacity. Explain every substantial
   increase, long-run extension, recovery week, and taper as a coach-designed
   choice; never attribute numeric authority to the conceptual source.

5. Create and validate the draft:

   ```bash
   poetry run resilio plan template-macro \
     --total-weeks <COUNT> \
     --out <DRAFT_JSON>
   poetry run resilio plan create-macro --from-json <DRAFT_JSON>
   poetry run resilio plan show
   ```

## Output

Return the complete macro review, including methodology and rationale, dates,
weekly run distance with units, phases, recovery weeks, quality and long-run
intent, the exact profile-derived constraint snapshot, evidence limitations,
and one approval prompt. The main coach records approval separately with
`poetry run resilio approvals approve-macro`. Approval binds the current plan
ID, macro revision, VDOT approval, planning-profile fingerprint, and macro
skeleton SHA-256.
