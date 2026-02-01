---
name: weekly-plan-generate
description: Designs exact workouts for a single week using AI coaching judgment and presents the review directly in chat without applying it. Use for Week 1 and all subsequent weeks.
disable-model-invocation: false
context: fork
agent: weekly-planner
allowed-tools: Bash, Read, Write
argument-hint: "[optional-notes]"
---

# Weekly Plan Generate (Workout Designer)

Non-interactive. Designs exact workouts using AI coaching judgment. Do not apply/save the plan.

## Preconditions (block if missing)
- Macro plan exists
- Target week identified (next unpopulated OR current week for update)
- Profile constraints present

If missing, return a blocking checklist and stop.

## Philosophy

You are the weekly planning specialist. Use your AI coaching judgment to design exact workouts based on:
- Workout structure hints from macro plan (strategic guidance)
- Current athlete state (CTL, TSB, readiness, ACWR)
- Training methodology (Pfitzinger, Daniels, Fitzgerald)
- Athlete constraints and preferences

CLI tools provide computational support (metrics, guardrails, pace calculations).
You provide qualitative coaching decisions (exact distances, workout types, pacing).

## Workflow

1) Identify target week:
```bash
sce plan next-unpopulated
sce plan status
sce plan week           # current week (use when updating current week)
sce plan week --week <N>
```
If the parent agent requests a current-week update, use `sce plan week` to set
`week_number`, `start_date`, `end_date`, and `phase`. Otherwise default to
the next unpopulated week.

**Extract `workout_structure_hints`** from the macro plan week - these are strategic
guidelines (e.g., "max 2 quality sessions", "long run 25-30%", "80% easy intensity").

2) Load current metrics and recent response:
```bash
sce status
sce week
sce dates week-boundaries --start <WEEK_START>
sce profile get  # Load athlete profile including other_sports
```

**Multi-sport athletes**: Check `other_sports` field in profile to identify:
- What other sports they do (climbing, cycling, surfing, etc.)
- Expected frequency/volume for each sport
- Running priority (PRIMARY/EQUAL/SECONDARY)
- Use this to avoid scheduling conflicts (e.g., no quality runs on climbing days)

If you already have an activities JSON file for the last 28 days, you may run:
`sce analysis intensity --activities <FILE> --days 28`

3) Analyze progression safety:
```bash
sce guardrails analyze-progression \
  --previous <PREV_ACTUAL_KM> \
  --current <PROPOSED_KM> \
  --ctl <CTL> \
  --run-days <MAX_RUN_DAYS> \
  --age <AGE>
```

4) Calculate VDOT-based paces:
```bash
sce vdot calculate-paces --vdot <VDOT>
```
Use these paces to set pace_range for each workout type (easy, tempo, intervals).

5) Design exact workouts using AI judgment:

**YOU design the workouts** using:
- Strategic hints from macro plan (workout_structure_hints)
- Current athlete state (CTL, TSB, readiness)
- Guardrail analysis (safe volume range, warnings)
- Training methodology principles (80/20, hard/easy separation, long run caps)
- VDOT-based pace zones

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
          "day_of_week": 0,
          "workout_type": "easy",
          "distance_km": 8.0,
          "pace_range": "6:00-6:30",
          "target_rpe": 4,
          "notes": "Pre-travel run, bank volume"
        },
        {
          "date": "2026-02-05",
          "day_of_week": 2,
          "workout_type": "tempo",
          "distance_km": 10.0,
          "pace_range": "5:20-5:35",
          "target_rpe": 7,
          "intervals": [
            {"duration_minutes": 20, "pace": "5:25-5:30", "type": "threshold", "recovery": "0"}
          ],
          "warmup_minutes": 15,
          "cooldown_minutes": 10,
          "key_workout": true,
          "notes": "First quality session of build phase"
        },
        {
          "date": "2026-02-09",
          "day_of_week": 6,
          "workout_type": "long_run",
          "distance_km": 12.0,
          "pace_range": "6:20-6:40",
          "target_rpe": 5,
          "warmup_minutes": 5,
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
- **Required fields (all workouts)**: date, day_of_week, workout_type, distance_km, pace_range, target_rpe
- **Structure fields (YOU must design these - critical for athlete execution)**:
  - `intervals`: For tempo/interval workouts, define exact structure (e.g., `[{"duration_minutes": 20, "pace": "5:30-5:40", "type": "threshold", "recovery": "0"}]`). Omit for easy/long runs.
  - `warmup_minutes`: Design based on workout intensity (0-5min for easy, 10-20min for quality, 5-10min for long runs)
  - `cooldown_minutes`: Design based on workout intensity (0-5min for easy, 10-15min for quality, 0-5min for long runs)
  - `key_workout`: Mark 1-2 priority sessions per week that athlete shouldn't skip (typically long run + one quality session)
- Use day_of_week numbering: 0=Monday, 6=Sunday
- Follow workout_structure_hints constraints (max quality sessions, long run %, etc.)
- Apply 80/20 principle (80% easy, 20% quality)
- Respect guardrail warnings (ACWR, progression limits)

Write JSON to `/tmp/weekly_plan_w<week>.json`

6) Validate your design:
```bash
sce plan validate-week --file /tmp/weekly_plan_w<week>.json
```
This checks:
- Sum-to-target (workouts sum to target_volume_km)
- Required fields present
- Date alignment (within week boundaries)
- No duplicate days
- Guardrails (quality limits, volume progression, 80/20, etc.)

If validation fails, fix the issues and re-validate.

7) Interval structure validation (conditional):
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
sce plan validate-intervals \
  --type intervals \
  --intensity I-pace \
  --work-bouts /tmp/work_bouts.json \
  --recovery-bouts /tmp/recovery_bouts.json \
  --weekly-volume <WEEKLY_KM>
```

8) Present directly in chat:

**IMPORTANT**: Always show the complete weekly training plan with ALL activities (running + other sports).

Present in this structure:

**Weekly Training Plan - Week {N}**
**Phase**: {phase} | **Run Volume**: {target_km}km | **Dates**: {start} to {end}

**Multi-Sport Context** (if applicable):
- Athlete profile: {list other_sports from profile}
- Running priority: {running_priority} (PRIMARY/EQUAL/SECONDARY)
- Expected other sport activities: {e.g., "climbing 2x/week, cycling 1x/week"}
- Load integration: Running plan accounts for {systemic load from other sports}

**Coaching Rationale**:
- Why these exact workouts? (reference workout_structure_hints)
- How this follows macro plan strategic guidance
- Volume change vs previous week: {prev_km}km → {target_km}km ({change}%)
- Multi-sport considerations: {e.g., "Light week due to climbing comp", "No quality runs on climbing days"}
- Any guardrail overrides with justification

**Weekly Training Schedule**:

**Monday ({date})**:
- 🏃 Run: {workout_type} - {distance}km @ {pace}
  - Target RPE: {rpe}/10
  - Notes: {notes}
- 🧗 Climbing: {expected activity from profile or "None scheduled"}

**Tuesday ({date})**:
- 🏃 Run: Rest
- 🧗 Climbing: {expected activity}

**Wednesday ({date})**:
- 🏃 Run: {workout_type} - {distance}km @ {pace}
  - Target RPE: {rpe}/10
  - Notes: {notes}
- 🚴 Cycling: {expected activity}

... (continue for all 7 days, showing BOTH running AND other sports)

**Integration Notes**:
- Days with both activities: {e.g., "Mon: easy run + climbing (systemic load stacked)"}
- Recovery days (no activities): {e.g., "Tue, Thu"}
- Conflict avoidance: {e.g., "No quality runs on climbing days"}

**Week Summary**:

**Running**:
- Total volume: {sum_of_workouts}km (target: {target_km}km)
- Running days: {count} days
- Quality sessions: {count} (excluding long run)
- Long run: {distance}km ({percentage}% of volume)
- Easy volume: {percentage}% | Quality volume: {percentage}%

**Multi-Sport Load** (if applicable):
- Total systemic load: {running_load + other_sports_load}au
- Running contribution: {percentage}%
- Other sports contribution: {percentage}%
- ACWR: {value} ({safe/caution/danger})

**Approval Required**:
Does this plan work for you, considering both your running and {other sports}?
I'll record your approval with:
`sce approvals approve-week --week {N} --file /tmp/weekly_plan_w{N}.json`

**Handoff note**: main agent must record approval via the command above.

## References (load only if needed)
- Weekly volume progression: `references/volume_progression_weekly.md`
- Workout generation: `references/workout_generation.md`
- Choosing run count: `references/choosing_run_count.md`
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
