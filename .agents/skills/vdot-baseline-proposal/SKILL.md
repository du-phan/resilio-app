---
name: vdot-baseline-proposal
description: Propose an evidence-backed baseline VDOT from exact race, personal-best, manual, or closed owned-assessment evidence without mutating approval state. Use when a race macro needs baseline evidence or the athlete asks to reassess race-performance equivalence.
---

# Baseline VDOT proposal

This is a proposal-only procedure. Write a new reviewable proposal file, but
do not approve it or mutate the profile or planning state.

## Evidence rules

- Prefer an athlete-confirmed, recent race or personal best with an exact
  distance, elapsed time, and date.
- An active exact-file VDOT approval in planning state is valid evidence and
  must be labeled as such.
- A new VDOT approval cannot replace the dependency of an active plan. For a
  successor plan, complete the plan-renewal review and closure first.
- Do not infer VDOT from easy pace, average activity pace, provider VO2 max,
  heart rate, native aerobic load, fitness/fatigue, or an arbitrary decay
  formula.
- Do not use future performances or evidence outside the requested lookback.
- If no qualifying evidence exists, return `not_found` and request an explicit
  manual athlete-approved value or route a non-injured athlete to the
  baseline-assessment-plan procedure.

## Workflow

1. Read the confirmed profile and approval state:

   ```bash
   poetry run resilio dates today
   poetry run resilio profile get
   poetry run resilio approvals status
   ```

2. Evaluate current evidence:

   ```bash
   poetry run resilio vdot estimate-current --lookback-days <DAYS>
   ```

3. For a newly confirmed race, calculate its value independently:

   ```bash
   poetry run resilio vdot calculate \
     --race-type <DISTANCE> \
     --time <ELAPSED_TIME> \
     --race-date <YYYY-MM-DD> \
     --as-of-date <ATHLETE_LOCAL_TODAY>
   ```

4. For synchronized race evidence, retrieve the exact canonical source:

   ```bash
   poetry run resilio activity list \
     --since <PERFORMANCE_DATE> \
     --sport run
   ```

   Use only the matching record’s `local_activity_id`,
   `elapsed_duration_seconds`, `distance_meters`, `activity_timezone`, and
   `source_external_fingerprint_sha256`. Require a precise athlete confirmation
   that this result represents the complete official race distance. If those
   facts do not identify the confirmed race exactly, use an athlete-confirmed
   profile personal best or request clarification; do not invent a source
   binding or treat GPS distance as official distance.

5. For a completed owned baseline assessment, create the proposal only from
   the immutable closed review:

   ```bash
   poetry run resilio vdot create-proposal-from-assessment \
     --review-sha256 <ASSESSMENT_REVIEW_SHA256> \
     --out <NEW_PROPOSAL_JSON>
   ```

   This path re-verifies the plan, review, publication, fulfillment, canonical
   activity fingerprint, and whole-activity or exact-segment result. Never
   copy assessment values into a hand-written race-performance proposal.

6. If two valid performances materially disagree, explain the dates, race
   distances, and computed values. Prefer the more recent representative
   performance only when its context supports using it; otherwise present the
   uncertainty and ask the athlete.

## Output

Write a new JSON file with exactly:

- `schema_version: 2`;
- integer `proposed_vdot`;
- discriminated `evidence`:
  - race evidence requires its `evidence_type`, exact `race_distance`,
    `elapsed_time_seconds`, `performance_date`, `performance_timezone`,
    `source_local_activity_id`, `source_external_fingerprint_sha256`,
    `measured_distance_meters`, and
    `official_distance_confirmation_reference`;
  - personal-best evidence requires its `evidence_type`, exact
    `race_distance`, `elapsed_time_seconds`, `performance_date`, and
    `performance_timezone`; those facts must exactly match the confirmed
    profile record;
  - manual evidence requires `evidence_type: manual_athlete_value`, the
    `athlete_confirmed_vdot`, and an exact `confirmation_reference`;
  - owned assessment evidence requires
    `evidence_type: owned_baseline_assessment`, the immutable
    `assessment_review_sha256`, exact performance facts, and the copied typed
    whole-activity or exact-segment `result`;
- an evidence-specific `evidence_summary` of at least 20 characters;
- timezone-aware `generated_at_utc`.

Do not clamp an out-of-range performance, decay an old result, or add a
temperature, altitude, or arbitrary time adjustment. Then return:

- `proposed_vdot`;
- evidence type, distance, elapsed time, and date, or the existing approval;
- evidence date, age in days, and the explicit applicability window;
- excluded evidence and the factual reason for exclusion;
- the new proposal file path and exact contents;
- one athlete-facing approval prompt.

VDOT approval does not authorize Resilio to manufacture training paces.

After explicit athlete approval, and only when no active plan depends on the
previous approval, the main coach records:

```bash
poetry run resilio approvals approve-vdot --file <PROPOSAL_JSON>
```

Approval binds the exact absolute path and file SHA-256. Any revision requires
a new file and a new approval.
