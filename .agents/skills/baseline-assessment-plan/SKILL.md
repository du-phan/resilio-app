---
name: baseline-assessment-plan
description: Create a short, evidence-bound return-to-running plan ending in one owned timed-distance benchmark, without requiring an approved VDOT or race methodology. Use when baseline fitness is missing, disputed, conflicting, or stale after inactivity and the athlete is not seeking injury rehabilitation.
---

# Plan a baseline assessment

Keep the conversation in athlete language. The coach owns every health check,
distance choice, scheduling choice, and approval. This procedure may create an
unapproved plan, but it must not approve the plan or any exact week.

## Safety boundary

- This workflow is for non-injury return to running. If pain, an active injury,
  post-operative rehabilitation, systemic illness, pregnancy-related medical
  restrictions, or clinician-directed return-to-sport constraints are present,
  stop and route the athlete to appropriate professional guidance.
- Default to a 5K benchmark. Mile, 10K, half-marathon, and marathon are
  representable, but a test longer than 5K requires explicit athlete
  confirmation and an evidence-backed rationale. Never choose a longer test
  merely because the target race is longer.
- Do not invent VDOT, target time, pace, heart-rate, readiness, or injury-risk
  values. The benchmark establishes evidence; it does not depend on them.

## Preconditions

Require a confirmed profile, goal, training timezone, run availability,
athlete-managed sport expectations, and training priority. Require no approved
active plan.
An obsolete unapproved proposal may be discarded only by its exact revision ID;
never use proposal discard to bypass evidence-backed closure. Refresh completed
activities and coverage before using inactivity or recent exposure as facts:

```bash
poetry run resilio dates today
poetry run resilio sync
poetry run resilio sync --status
poetry run resilio profile get
poetry run resilio approvals status
poetry run resilio plan status
```

If `plan status` identifies an obsolete proposal that was never approved or
populated, first inspect it and use its exact revision ID. Do not discard merely
because a new proposal would be more convenient:

```bash
poetry run resilio plan show
poetry run resilio plan discard-unapproved --plan-revision <EXACT_REVISION_ID>
```

Classify at least one exact reason: `missing_baseline`, `disputed_baseline`,
`conflicting_evidence`, or `post_inactivity_baseline`.

## Evidence and dates

1. Resolve every Monday-Sunday boundary through `resilio dates`; never calculate
   dates mentally. Choose a short contiguous return block that starts strictly
   after the evidence date.

2. Create its immutable evidence context:

   First write every temporary athlete-confirmed unavailable date range to a
   new JSON array. Each item requires `unavailable_start_date`,
   `unavailable_end_date`, a precise `reason`, and
   `athlete_confirmation_reference`. Keep these cycle-specific constraints out
   of the durable profile.

   ```bash
   poetry run resilio plan create-assessment-context \
     --evidence-as-of <DATE> \
     --start <MONDAY> \
     --reason <ASSESSMENT_REASON> \
     --constraints-file <CONSTRAINTS_JSON>
   ```

3. Select one preferred benchmark date and a bounded fallback window contained
   in one plan week. Before day-specific advice, use:

   ```bash
   poetry run resilio weather week --start <WEEK_MONDAY>
   ```

   Do not use web weather. If the forecast horizon does not yet cover the week,
   preserve the preferred date and fallback window, keep exact workouts
   date-only, and state that weather/recovery will decide the final day or time
   at the weekly approval boundary.

4. Respect holidays and every other confirmed unavailable date. Account for
   athlete-managed sport expectations when selecting running volume and
   recovery spacing, but never create, date, reduce, or approve their sessions.
   Do not cram running into the days before a benchmark or holiday.

## Build the assessment skeleton

Create contiguous Monday-Sunday weeks with empty `running_workouts`. Each week requires
an evidence-backed `target_run_volume_meters`, run-frequency-compatible
structure hints, and recovery intent. The benchmark week must allow exactly one
`benchmark` quality role. Record:

- the assessment context reference and exact reasons;
- every temporary athlete-confirmed unavailable date range from the context;
- the exact athlete-managed sport expectations and training priority captured
  by the context, without turning them into plan sessions;
- a 5K default or the explicitly confirmed alternative distance;
- preferred date and fallback window;
- `medical_rehabilitation_excluded: true`;
- evidence-cited `starting_volume` and `benchmark_scheduling` decisions;
- athlete-specific rationale and limitations.

Cite only evidence IDs returned by the context, including the latest recent
week. Progress from demonstrated run exposure, not a generic percentage rule.

```bash
poetry run resilio plan template-assessment \
  --total-weeks <COUNT> \
  --out <DRAFT_JSON>
poetry run resilio plan create-assessment --from-json <DRAFT_JSON>
poetry run resilio plan show
```

## Approval boundary

Present the reasons, dates, weekly run volumes in meters/kilometers, maximum
three-run constraint when applicable, treatment of athlete-managed sport
expectations, benchmark distance, preferred date, fallback window,
uncertainties, and the fact that exact weeks remain separately approvable. Ask
for one explicit plan approval.

Only after that approval may the main coach run:

```bash
poetry run resilio approvals approve-plan
```

Then use the weekly-plan-generate and weekly-plan-apply procedures for each
week. Creating or approving this skeleton does not publish workouts and does
not approve a VDOT.
