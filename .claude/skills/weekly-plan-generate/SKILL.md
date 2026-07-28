---
name: weekly-plan-generate
description: Designs exact workouts for a single week using AI coaching judgment and writes a validated JSON file without applying it. Use for Week 1 and all subsequent weeks.
allowed-tools: Bash, Read, Write
---

# Weekly Plan Generate (Workout Designer)

Designs exact workouts using AI coaching judgment. Do not apply/save the plan.

## Preconditions (block if missing)

- Macro plan exists
- Target week identified (next unpopulated OR current week for update)
- Profile constraints present

If missing, return a blocking checklist and stop.

## Interactivity & Feedback

- Non-interactive: do not ask the athlete questions or call approval commands.
- Return an `athlete_prompt` for the main agent to ask and capture approval.
- If the athlete declines or requests changes, the main agent will re-run this skill with notes; treat notes as hard constraints and generate a new week JSON (do not edit the prior file in place).
- If new constraints are provided (injury, schedule limits), assume the main agent updated profile/memory before re-run.
- If any CLI command fails (exit code ≠ 0), include the error output in your response and return a blocking checklist.

## Philosophy

You are the weekly planning specialist. Use your AI coaching judgment to design exact workouts based on:

- Workout structure hints from macro plan (strategic guidance)
- Current athlete state (CTL, TSB, readiness, ACWR)
- Training methodology (Pfitzinger, Daniels, Fitzgerald)
- Athlete constraints and preferences

CLI tools provide computational support (metrics, guardrails, pace calculations).
You provide qualitative coaching decisions (exact distances, workout types, pacing).

**Metric explainer rule**: See CLAUDE.md "Metric one-liners" for first-mention definitions. Do not repeat unless the athlete asks.

## Workflow

1. Identify target week:

```bash
resilio plan next-unpopulated
resilio plan status
resilio plan week           # current week (use when updating current week)
resilio plan week --week <N>
```

If the parent agent requests a current-week update, use `resilio plan week` to set
`week_number`, `start_date`, `end_date`, and `phase`. Otherwise default to
the next unpopulated week.

**Extract `workout_structure_hints`** from the macro plan week - these are strategic
guidelines (e.g., "max 2 quality sessions", "long run 25-30%", "80% easy intensity").

**Long run target priority:**
1. If `workout_structure_hints.long_run.target_km` is set → use it as the long run distance directly
2. Otherwise → derive from `pct_range` against the week's `target_volume_km`

1.5. Volume context — AI coaching judgment within guardrail ceilings (skip for Week 1 or explicit volume override in notes):

```bash
# N-1: actual km and macro target
resilio plan week-execution --week <N-1> | \
  jq '[.data.executions[] | select(.matched == true) | .actual_distance_km] | add // 0'
resilio plan week --week <N-1> | jq '.data.weeks[0].target_volume_km'

# N-2: actual km, macro target, and whether it was a recovery week (omit if week doesn't exist)
resilio plan week-execution --week <N-2> | \
  jq '[.data.executions[] | select(.matched == true) | .actual_distance_km] | add // 0'
resilio plan week --week <N-2> | jq '.data.weeks[0].target_volume_km, .data.weeks[0].is_recovery_week'

# Get volume context (include --actual-prev2 and --macro-prev2 when N-2 exists and is not recovery)
resilio guardrails suggest-weekly-target \
  --actual-prev <actual_prev_km> \
  --actual-prev2 <actual_prev2_km> \
  --macro-prev <macro_prev_km> \
  --macro-prev2 <macro_prev2_km> \
  --macro-next <target_volume_km_from_step_1> \
  --run-days <max_run_days_per_week> \
  [--recovery-transition] \
  [--prev2-is-recovery]
```

The tool returns volume context. **You (the AI Coach) decide the target volume** using
this context alongside the CTL/TSB/ACWR metrics from Step 2:

| Field | Role |
|---|---|
| `hard_ceiling_km` | **Outer ceiling — never exceed.** `max(10%, Pfitzinger)` from N-1 actual. Always the more permissive of the two rules: below ~16×run_days km Pfitz wins; above that 10% wins. Both are marginal at high volume. |
| `actual_prev_km` | What the athlete actually ran last week — your primary baseline. |
| `macro_next_km` | Macro plan's intent for this week. |
| `suggested_target_km` | Conservative formula anchor: `min(10%, Pfitz)` from weighted average. Right starting point for normal and undershoot cases. |
| `overshoot_pattern` | True = N-1 AND N-2 both exceeded their respective macro targets by >10%. |

**Core rules:**
- Never exceed `hard_ceiling_km` (outer bound from Pfitzinger's rules).
- **Normal/undershoot/illness**: use `min(suggested_target_km, hard_ceiling_km)` as your anchor. In illness cases the hard ceiling (anchored to low raw N-1) can be tighter than the formula suggestion — it always wins.
- **When `overshoot_pattern: true`**: anchor target to `actual_prev_km` (not the formula's weighted-down average), then assess fatigue (TSB/ACWR/readiness) to pick the right scenario. See `references/volume_progression_weekly.md §Overshoot Scenarios`.
- Run Step 3 (`analyze-progression`) with your chosen target to validate against CTL capacity.

Set your chosen volume as `target_volume_km` for all downstream steps.

2. Load current metrics and recent response:

```bash
resilio status
resilio week
resilio dates week-boundaries --start <WEEK_START>
resilio profile get  # Load athlete profile including other_sports
```

2.5. Add weekly weather context:

```bash
resilio weather week --start <WEEK_START>
```

### Weather Context & Adjustments

- Weather data is coaching context for day selection — use it alongside training load,
  athlete state, and spacing rules when deciding which day gets which session.
- Example: a tempo on a rainy, windy day when a dry day is available is a poor coaching call.
- If weather lookup fails, continue planning and note the uncertainty.
- In environments with web access, the main coach may use internet search as fallback.

**Multi-sport athletes**: Check `other_sports` field in profile to identify:

- What other sports they do (climbing, cycling, surfing, etc.)
- Expected frequency/volume for each sport
- Running priority (PRIMARY/EQUAL/SECONDARY)
- **Day constraints**: Use `constraints.unavailable_run_days` for run-day blocking. Other sports inform load and intensity distribution, not day blocking, in v0.

Optionally export and analyze recent intensity distribution:

```bash
resilio activity export --since 28d --out /tmp/activities_28d.json
resilio analysis intensity --activities /tmp/activities_28d.json --days 28
```

2b. Load quality and long run history:

For week N, read the last 2 populated weeks:

```bash
resilio plan week --week <N-1>
resilio plan week --week <N-2>   # if it exists and was not a recovery week
resilio plan week-execution --week <N-1>  # execution classifications if activities synced
```

For any quality workout in the week-execution output where `classification` is `null`:
- If `has_laps: true` → call `resilio activity laps <activity_id>` and apply the lap
  classification methodology in `references/quality_progression_weekly.md §6b`
- If `has_laps: false` → use `actual_avg_pace` and `actual_avg_hr` as proxy; note
  the limitation (warmup/cooldown dilute the avg; EASY may be a false flag)

Synthesise a **Quality Progression Summary** before Step 6:

```
Last quality session (Week N-x): [type] | [structure: X min / N×Y] | [RPE X]
Execution: [CLEAN | STRUGGLED | EASY | MISSED | no execution data yet]
Execution detail: [actual pace avg vs target, HR trend, lap fade if known]
Last long run (Week N-x): [Ykm] / [approx Z min]
LR execution: [completed as prescribed / cut short / no data yet]
Recovery week since last quality: [yes/no]
```

If no prior quality exists (early base): note "no prior quality — first introduction"
and apply conservative introduction rules from `references/quality_progression_weekly.md`.

See `references/quality_progression_weekly.md` for the full decision framework:
execution states (CLEAN/STRUGGLED/EASY/MISSED), rotation rules, long run duration
progression (+10–15 min rule), cross-week boundary checks, and §6b lap methodology.

3. Analyze progression safety:

```bash
resilio guardrails analyze-progression \
  --previous <PREV_ACTUAL_KM> \
  --current <PROPOSED_KM> \
  --ctl <CTL> \
  --run-days <MAX_RUN_DAYS> \
  --age <AGE>
```

4. Calculate VDOT-based paces:

```bash
resilio vdot paces --vdot <VDOT>
```

Use these paces to set pace_range for each workout type (easy, tempo, intervals).

5. Determine run count (suggest-run-count):

**CRITICAL**: Before designing workouts, consult the system for optimal run count using:

```bash
resilio plan suggest-run-count \
  --volume <TARGET_VOLUME_KM> \
  --max-runs <ATHLETE_MAX_RUN_DAYS> \
  --phase <PHASE>
```

This step is strongly recommended - skipping it risks presentation-JSON mismatches. See `references/choosing_run_count.md` for complete workflow, decision heuristics, and integration guidance.

6. Design exact workouts using AI judgment:

**Day selection**: Reference weather signals from Step 2.5 when choosing days.
Prefer best-conditions days for quality sessions and long runs among structurally valid options.

**Before designing any quality session**, produce a Quality Progression Analysis
(expands the Step 2b summary — add the two fields below and complete the progression
decision; see `references/quality_progression_weekly.md` for the full decision framework):

```
QUALITY PROGRESSION ANALYSIS
─────────────────────────────
Last quality session (Week N-x): [type] | [structure: X min / N×Y] | [RPE X]
Execution: [CLEAN | STRUGGLED | EASY | MISSED | no data yet]
Execution detail: [actual pace avg vs target, HR trend, lap fade if known]
Last long run (Week N-x): [Ykm] / [approx Z min]
LR execution: [completed / cut short / no data yet]
Recovery week since last quality: [yes/no]
Volume last week vs this week: [±X km / ±Y%]
Stressor last week: [VOLUME increased / QUALITY progressed / NEITHER / BOTH]

Progression decision: [PROGRESS / MAINTAIN / DOWNGRADE / VARY TYPE]
Reasoning: [cite execution result + one-stressor rule + methodology source]

Planned quality this week: [type] | [structure: X min / N×Y] | [RPE X]
─────────────────────────────
```

Reflect the key progression reasoning in the workout's `notes` field.
Notes are athlete-facing: use pace/HR for any adjustment cues, not RPE. See `references/workout_generation.md` for the rule and examples.

**YOU design the workouts** using:

- Strategic hints from macro plan (workout_structure_hints)
- Current athlete state (CTL, TSB, readiness)
- Guardrail analysis (safe volume range, warnings)
- Training methodology principles (80/20, hard/easy separation, long run caps)
- VDOT-based pace zones
- Weekly weather conditions (from Step 2.5) — factor into day selection

Create explicit workout JSON manually with exact distances. Example structure:

```json
{
  "weeks": [
    {
      "week_number": 2,
      "phase": "base",
      "start_date": "2026-02-03",
      "end_date": "2026-02-09",
      "target_volume_km": 27.0,
      "target_systemic_load_au": 0.0,
      "workouts": [
        {
          "date": "2026-02-03",
          "sport": "run",
          "day_of_week": 0,
          "workout_type": "easy",
          "distance_km": 8.0,
          "pace_range": "6:00-6:30",
          "target_rpe": 4,
          "notes": "Pre-travel run, bank volume"
        },
        {
          "date": "2026-02-05",
          "sport": "run",
          "day_of_week": 2,
          "workout_type": "tempo",
          "distance_km": 10.0,
          "pace_range": "5:20-5:35",
          "target_rpe": 7,
          "structured_workout": {
            "sport": "run",
            "steps": [
              {
                "kind": "steady",
                "duration": {"unit": "meters", "value": 2500},
                "target": {
                  "mode": "pace",
                  "unit": "seconds_per_kilometer",
                  "minimum": 360,
                  "maximum": 390
                },
                "intensity": "warmup"
              },
              {
                "kind": "steady",
                "duration": {"unit": "meters", "value": 4000},
                "target": {
                  "mode": "pace",
                  "unit": "seconds_per_kilometer",
                  "minimum": 325,
                  "maximum": 330
                },
                "intensity": "interval"
              },
              {
                "kind": "steady",
                "duration": {"unit": "meters", "value": 2000},
                "target": {
                  "mode": "pace",
                  "unit": "seconds_per_kilometer",
                  "minimum": 360,
                  "maximum": 390
                },
                "intensity": "active"
              },
              {
                "kind": "steady",
                "duration": {"unit": "meters", "value": 1500},
                "target": {
                  "mode": "pace",
                  "unit": "seconds_per_kilometer",
                  "minimum": 370,
                  "maximum": 400
                },
                "intensity": "cooldown"
              }
            ]
          },
          "warmup_km": 2.5,
          "cooldown_km": 1.5,
          "key_workout": true,
          "notes": "First quality session of build phase"
        },
        {
          "date": "2026-02-09",
          "sport": "run",
          "day_of_week": 6,
          "workout_type": "long_run",
          "distance_km": 12.0,
          "pace_range": "6:20-6:40",
          "target_rpe": 5,
          "warmup_km": 0.5,
          "key_workout": true,
          "notes": "Priority aerobic session - key workout of the week"
        }
      ],
      "is_recovery_week": false
    }
  ]
}
```

**CRITICAL REQUIREMENTS**:

- Workouts MUST sum exactly to target_volume_km (±0.1km tolerance)
- **Required fields (all workouts)**: date, sport, day_of_week, workout_type, distance_km, pace_range, target_rpe
- **Device publication time**: every workout with `structured_workout` must include
  `start_time_local` (`HH:MM:SS`) so plan-wide publication is deterministic
- **Structure fields (YOU must design these - critical for athlete execution)**:
  - `structured_workout`: For tempo, interval, repetition, progression, and any other workout intended for device publishing, define exact typed steps. Use `steady`, `ramp`, and recursive `repeat` steps; unit-explicit durations and targets are mandatory. Omit only when the workout is intentionally coaching-only and will not be published.
  - The top-level `sport` and `structured_workout.sport` must match (`run` or `cycle`). Rest days cannot contain `structured_workout`.
  - Pace targets use integer seconds per kilometre, HR targets use bpm or an explicit percentage unit, and power targets use watts or `%FTP`. Never encode targets or recoveries as prose.
  - `warmup_km`: Design based on workout type (0 for easy/long, 1.5-2.5km for tempo, 2.0-3.0km for intervals)
  - `cooldown_km`: Design based on workout type (0 for easy/long, 1.0-2.0km for tempo, 1.5-2.0km for intervals)
  - `key_workout`: Mark 1-2 priority sessions per week that athlete shouldn't skip (typically long run + one quality session)
- Use day_of_week numbering: 0=Monday, 6=Sunday
- Follow workout_structure_hints constraints (max quality sessions, long run %, etc.)
- Apply 80/20 principle (80% easy, 20% quality)
- Respect guardrail warnings (ACWR, progression limits)

Write JSON to `/tmp/weekly_plan_w<week>.json`

7. Validate comprehensively:

```bash
resilio plan validate-week --file /tmp/weekly_plan_w<week>.json
```

This checks:

- Sum-to-target (workouts sum to target_volume_km)
- Required fields present
- Date alignment (within week boundaries)
- No duplicate days
- Guardrails (quality limits, volume progression, 80/20, etc.)

If validation fails, fix the issues and re-validate.

**Before proceeding**, verify your JSON:

```bash
# Count workouts (must match suggest-run-count recommendation)
jq '.weeks[0].workouts | length' /tmp/weekly_plan_w<week>.json

# Verify volume sum (must equal target_volume_km ±0.1km)
jq '[.weeks[0].workouts[].distance_km] | add' /tmp/weekly_plan_w<week>.json
```

**Consult the pre-return checklist** (`references/pre_presentation_checklist.md`) to confirm:
- Workout count matches suggest-run-count recommendation
- Volume sum equals target_volume_km (±0.1km)
- JSON is self-consistent and ready for main agent jq extraction

If any check fails, FIX THE JSON before returning.

8. Interval structure validation (conditional):
   Run **only if** your designed week includes a structured tempo/interval workout
   with explicit work + recovery bouts (Daniels-style). If not, skip.

Prepare two small JSON files from the planned session:

- `/tmp/work_bouts.json` (list of work bouts with durations)
- `/tmp/recovery_bouts.json` (list of recovery bouts)

Example formats:

```json
[
  { "duration_minutes": 4.0, "distance_km": 1.0, "pace_per_km_seconds": 240 },
  { "duration_minutes": 4.0, "distance_km": 1.0, "pace_per_km_seconds": 240 }
]
```

```json
[
  { "duration_minutes": 2.0, "type": "jog" },
  { "duration_minutes": 2.0, "type": "jog" }
]
```

Then run:

```bash
resilio plan validate-intervals \
  --type intervals \
  --intensity I-pace \
  --work-bouts /tmp/work_bouts.json \
  --recovery-bouts /tmp/recovery_bouts.json \
  --weekly-volume <WEEKLY_KM>
```

## References (load only if needed)

- **Pre-presentation checklist**: `references/pre_presentation_checklist.md` (consult before presenting)
- **Quality progression**: `references/quality_progression_weekly.md` (consult in Steps 2b and 6)
- Workout structure & session mechanics: `references/workout_structure.md`
- Weekly volume progression: `references/volume_progression_weekly.md`
- Workout generation: `references/workout_generation.md`
- **Choosing run count**: `references/choosing_run_count.md` (consult before workout design)
- Pace zones: `references/pace_zones.md`
- Guardrails: `references/guardrails_weekly.md`
- JSON workflow: `references/json_workflow.md`
- Multi-sport integration: `references/multi_sport_weekly.md`
- Common pitfalls: `references/common_pitfalls_weekly.md`
- Core methodology: `docs/coaching/methodology.md`

## Output

Return:

- `weekly_json_path`
- `week_number`
- `athlete_prompt` (single yes/no + adjustment question)
- If blocked: `blocking_checklist`
