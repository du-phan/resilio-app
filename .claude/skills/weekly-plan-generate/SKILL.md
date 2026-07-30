---
name: weekly-plan-generate
description: Design and validate exact workouts for one existing macro-plan week without applying them. Use for Week 1, a subsequent unpopulated week, or a revised weekly proposal that still requires athlete approval.
---

# Generate one training week

Operate non-interactively. Write a new proposal file; do not apply it, approve
it, or overwrite a previously presented proposal.

## Evidence acquisition

1. Resolve the target week:

   ```bash
   poetry run resilio plan status
   poetry run resilio plan week --week <WEEK_NUMBER>
   poetry run resilio profile get
   ```

2. Compute dates through the CLI, never mentally. Fetch the future-target
   planning context with an evidence date no later than today:

   ```bash
   poetry run resilio dates week-boundaries --start <WEEK_MONDAY>
   poetry run resilio coach planning-context \
     --week <WEEK_NUMBER> \
     --evidence-as-of <YYYY-MM-DD> \
     --history-weeks <COUNT>
   ```

   Keep `target_week` separate from `recent_history`. Never request a future
   weekly review or treat a future target week as completed evidence.

### Weather Context & Adjustments

3. Fetch local weather before choosing workout days:

   ```bash
   poetry run resilio weather week --start <WEEK_START>
   ```

   If the weather lookup fails or weather data unavailable is reported,
   continue with the training-logic decision and state the uncertainty. Do not
   use web weather. For a multi-sport week, consider the same day’s conditions
   for every outdoor sport rather than treating weather as run-only context.

## Coaching decisions

- Follow the macro plan’s single primary methodology and phase. Training-book
  records are source-only context, not workout constructors.
- Approved VDOT is performance evidence, not a training-pace table. Omit pace
  targets unless a separate verified source supplies exact bounds. Use
  athlete-approved RPE or Intervals.icu-native heart-rate guidance otherwise.
- Interpret native fitness, fatigue, form, ramp, aerobic load, relative
  intensity, decoupling, polarization, TRIMP, and zone time as provider
  observations, not automatic go/no-go rules. Never recreate a missing native
  metric. Do not average activity polarization indices or interpret raw
  decoupling with an unknown coupling basis.
- Inspect recovery signals individually against personal baselines. Missing
  signals remain unknown; zero is not missing.
- Keep aerobic load points, session-RPE arbitrary units, run exposure,
  other-sport exposure, and wellness separate.
- Respect exact run-day availability, maximum session duration in minutes,
  other-sport commitments, and the conflict policy.
- Progress one material stressor at a time when possible. Do not compensate for
  missed work by cramming sessions or making a single run absorb the deficit.
- Separate demanding sessions according to the primary methodology and the
  athlete’s actual recovery evidence.
- Prescribe every session with `planned_duration_seconds`, exact low-,
  moderate-, and high-intensity duration seconds that sum to it,
  `target_rpe_1_to_10`, and a purpose. Every run also requires positive
  `planned_distance_meters`; other sports may be duration-only. Include an
  exact `start_time_local` for every session. Use complete
  seconds-per-kilometer or beats-per-minute bounds when those targets are
  present. Include warm-up and cool-down in all totals.
- Represent publishable session steps under the typed `"structured_workout"`
  field; use recursive warm-up, work, recovery, repetition, and cool-down step
  contracts rather than an untyped interval list.
- Schedule rest as rest; do not create filler workouts to satisfy a count.

## Validation and output

Write a `WeekApplication` JSON containing only:

- `week_number`;
- `workouts`;
- a specific `adjustment_rationale` of at least 40 characters.

The sum of run `planned_distance_meters` must equal
the immutable target in `target_week.target_run_volume_meters`. Include every
active other-sport commitment exactly as captured by the planning context.
Do not emit a synthetic rest workout; an
unscheduled day is rest.

Then run:

```bash
poetry run resilio plan validate-week --file <NEW_PROPOSAL_JSON>
```

Return the exact proposal contents, the evidence and uncertainty summary, the
validation result, the new file path, and one athlete-facing approval prompt.
The main coach records approval with
`poetry run resilio approvals approve-week --file <NEW_PROPOSAL_JSON>`.
