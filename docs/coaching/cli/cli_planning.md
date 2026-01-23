# Planning Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Commands for setting race goals and managing training plans, including macro planning, weekly plan validation, and plan persistence.

**Commands in this category:**
- `sce goal` - Set a race goal (automatically regenerates plan)
- `sce plan show` - Get current training plan with all weeks and workouts
- `sce plan week` - Get specific week(s) from the training plan
- `sce plan populate` - Add/update weekly workouts in the plan
- `sce plan validate` - Validate weekly plan JSON before populate (unified validator)
- `sce plan update-from` - Replace plan weeks from a specific week onwards
- `sce plan save-review` - Save plan review markdown
- `sce plan append-week` - Append weekly training summary to log
- `sce plan create-macro` - Generate high-level plan structure (macro)
- `sce plan assess-period` - Assess completed period for adaptive planning
- `sce plan suggest-run-count` - Suggest optimal run count for volume/phase

---

## sce goal

Set a race goal (automatically regenerates plan).

**Usage:**

```bash
# Set 10K goal with target time
sce goal --type 10k --date 2026-06-01 --time 00:45:00

# Set half marathon goal
sce goal --type half_marathon --date 2026-09-15 --time 01:45:00

# Set marathon goal (no time = fitness goal)
sce goal --type marathon --date 2026-11-01
```

**Supported race types:**

- `5k`, `10k`, `half_marathon`, `marathon`

**Returns:**

```json
{
  "ok": true,
  "data": {
    "goal": {
      "type": "10k",
      "target_date": "2026-06-01",
      "target_time": "00:45:00",
      "target_pace_per_km": "4:30",
      "vdot": 48,
      "effort_level": "competitive"
    },
    "plan_regenerated": true,
    "total_weeks": 20
  }
}
```

**What happens:**

1. Goal saved to profile
2. M10 generates new training plan
3. Plan saved to `data/plans/current_plan.yaml`
4. Periodization calculated based on weeks available
5. Volume progression set based on current CTL

---

## sce plan show

Get current training plan with all weeks and workouts.

**Usage:**

```bash
sce plan show
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "goal": {
      "type": "half_marathon",
      "target_date": "2026-09-15",
      "target_time": "01:45:00"
    },
    "total_weeks": 32,
    "plan_start": "2026-01-20",
    "plan_end": "2026-09-15",
    "phases": {
      "base": {"weeks": 12, "start_week": 1},
      "build": {"weeks": 12, "start_week": 13},
      "peak": {"weeks": 6, "start_week": 25},
      "taper": {"weeks": 2, "start_week": 31}
    },
    "weeks": [
      {
        "week_number": 1,
        "phase": "base",
        "weekly_volume_km": 25,
        "workouts": [...]
      }
    ]
  }
}
```

## sce plan week

Get specific week(s) from the training plan without loading the entire plan.

**Usage:**

```bash
# Current week (default)
sce plan week

# Next week
sce plan week --next

# Specific week by number
sce plan week --week 5

# Week containing a specific date
sce plan week --date 2026-02-15

# Multiple consecutive weeks
sce plan week --week 5 --count 2
```

**Parameters:**

- `--week N` - Week number (1-indexed). Takes priority over other flags.
- `--next` - Get next week instead of current week
- `--date YYYY-MM-DD` - Get week containing this date
- `--count N` - Number of consecutive weeks to return (default: 1)

**Returns:**

```json
{
  "ok": true,
  "message": "Week 5 of 9: build phase (2026-02-16 to 2026-02-22)",
  "data": {
    "weeks": [
      {
        "week_number": 5,
        "phase": "build",
        "start_date": "2026-02-16",
        "end_date": "2026-02-22",
        "target_volume_km": 35.0,
        "target_systemic_load_au": 245.0,
        "is_recovery_week": false,
        "notes": "Week 5 - Build phase: Introducing tempo work",
        "workouts": [
          {
            "id": "w_2026-02-16_easy_754e59",
            "date": "2026-02-16",
            "workout_type": "easy",
            "duration_minutes": 31,
            "distance_km": 5.25,
            "purpose": "Recovery",
            "pace_range_min_km": "15:59",
            "pace_range_max_km": "16:09"
          }
        ]
      }
    ],
    "goal": {
      "type": "marathon",
      "target_date": "2026-03-28",
      "target_time": "4:34:00"
    },
    "current_week_number": 4,
    "total_weeks": 9,
    "week_range": "Week 5 of 9",
    "plan_context": {
      "starting_volume_km": 20.0,
      "peak_volume_km": 45.19,
      "conflict_policy": "running_goal_wins"
    }
  }
}
```

**When to use:**

- "What's my training plan for next week?" - Use `--next` flag
- "What does week 8 look like?" - Use `--week 8`
- "What training do I have mid-February?" - Use `--date 2026-02-15`
- Previewing upcoming weeks without loading entire plan
- More efficient than `sce plan show` when you only need specific weeks

**Benefits:**

- **92% smaller output** - Returns only requested week(s), not entire plan
- **Single tool call** - No secondary file read required
- **No file I/O** - Direct data retrieval without persistence
- **Faster coaching context** - Quickly check next week during coaching sessions

---

## sce plan create-macro

Generate high-level training plan structure (macro plan) with phase boundaries, volume trajectory, CTL projections, and recovery week schedule.

**Usage:**

```bash
# Requires approved baseline VDOT
sce approvals approve-vdot --value 48.0

# Generate macro plan for 16-week half marathon
sce plan create-macro \
  --goal-type half_marathon \
  --race-date 2026-05-03 \
  --target-time 01:30:00 \
  --total-weeks 16 \
  --start-date 2026-01-20 \
  --current-ctl 44.0 \
  --starting-volume-km 25.0 \
  --peak-volume-km 55.0 \
  --baseline-vdot 48.0 \
  --weekly-volumes-json /tmp/weekly_volumes.json

# Generate macro plan without target time (fitness goal)
sce plan create-macro \
  --goal-type marathon \
  --race-date 2026-11-01 \
  --total-weeks 20 \
  --start-date 2026-06-08 \
  --current-ctl 38.5 \
  --starting-volume-km 20.0 \
  --peak-volume-km 65.0 \
  --baseline-vdot 44.0 \
  --weekly-volumes-json /tmp/weekly_volumes.json
```

**Parameters:**

- `--goal-type` (required) - Race distance: `5k`, `10k`, `half_marathon`, `marathon`
- `--race-date` (required) - Race date in YYYY-MM-DD format
- `--target-time` (optional) - Target finish time in HH:MM:SS format (e.g., 01:30:00)
- `--total-weeks` (required) - Total training weeks (typically 12-20)
- `--start-date` (required) - Plan start date (YYYY-MM-DD), must be Monday
- `--current-ctl` (required) - Current CTL value (use `sce status` to get)
- `--starting-volume-km` (required) - Starting weekly volume in km
- `--peak-volume-km` (required) - Peak weekly volume in km
- `--baseline-vdot` (required) - Approved baseline VDOT for the macro plan
- `--weekly-volumes-json` (required) - JSON file with weekly volume targets and workout structure hints in this exact format:
```json
{
  "volumes_km": [32.0, 35.0, 38.0, 28.0],
  "workout_structure_hints": [
    {
      "quality": {"max_sessions": 1, "types": ["strides_only"]},
      "long_run": {"emphasis": "steady", "pct_range": [24, 30]},
      "intensity_balance": {"low_intensity_pct": 0.90}
    },
    {
      "quality": {"max_sessions": 2, "types": ["tempo", "intervals"]},
      "long_run": {"emphasis": "progression", "pct_range": [24, 30]},
      "intensity_balance": {"low_intensity_pct": 0.85}
    }
  ]
}
```

**Returns:**

```json
{
  "ok": true,
  "message": "Macro plan generated for 16 weeks",
  "data": {
    "race": {
      "type": "half_marathon",
      "date": "2026-05-03",
      "target_time": "01:30:00"
    },
    "structure": {
      "total_weeks": 16,
      "phases": [
        {
          "name": "base",
          "weeks": [1, 2, 3, 4, 5, 6, 7],
          "focus": "Aerobic foundation + multi-sport integration"
        },
        {
          "name": "build",
          "weeks": [8, 9, 10, 11, 12],
          "focus": "Half marathon-specific intensity"
        },
        {
          "name": "peak",
          "weeks": [13, 14],
          "focus": "Maximum load, race-pace emphasis"
        },
        {
          "name": "taper",
          "weeks": [15, 16],
          "focus": "Reduce fatigue, peak fitness"
        }
      ]
    },
    "starting_volume_km": 25.0,
    "peak_volume_km": 55.0,
    "ctl_projections": [
      {"week": 0, "ctl": 44.0},
      {"week": 7, "ctl": 52.0},
      {"week": 12, "ctl": 58.0},
      {"week": 16, "ctl": 56.0}
    ],
    "recovery_weeks": [4, 8, 12]
  }
}
```

**What it generates:**

- **Periodization phases** - Divides plan into base/build/peak/taper with appropriate durations
- **Starting/peak volume targets** - Reference values for AI coach to design weekly volumes
- **CTL projections** - Expected CTL at key milestones (+0.75/week in base/build)
- **Recovery week schedule** - Every 4th week for adaptation
- **Phase focus** - Training emphasis for each phase

**Note**: Weekly volumes are NOT pre-computed. AI coach designs each week's volume using guardrails based on athlete's actual training response.

**When to use:**

- First step of progressive disclosure planning (generate big picture before weekly details)
- Creating structural roadmap that athlete can see and approve
- Providing starting/peak volume goals as reference for AI coach
- Establishing CTL progression goals and phase boundaries for the training cycle

---

## Weekly planning workflow (CLI)

The CLI can now scaffold a weekly JSON via `sce plan generate-week` (it does not choose the pattern; the AI coach still decides run days, long run %, and paces).

**Typical flow:**

```bash
# 1) AI coach decides the pattern (run days, long run %, paces) and generates JSON
sce plan generate-week \
  --week N \
  --run-days "0,2,6" \
  --long-run-day 6 \
  --long-run-pct 0.45 \
  --easy-run-paces "6:30-6:50" \
  --long-run-pace "6:30-6:50" \
  --out /tmp/weekly_plan_wN.json

# 2) Validate before presenting
sce plan validate --file /tmp/weekly_plan_wN.json

# 3) Present to athlete and get approval
sce approvals approve-week --week N --file /tmp/weekly_plan_wN.json

# 4) Persist after approval
sce plan populate --from-json /tmp/weekly_plan_wN.json --validate
```

---

## sce plan populate

Add or update weekly workouts in the training plan.

**Usage:**

```bash
sce plan populate --from-json /tmp/weekly_plan_w1.json --validate
```

**Notes:**
- Safe to call repeatedly; existing weeks are preserved and updated by week_number.
- Requires weekly approval in `data/state/approvals.json` (set via `sce approvals approve-week`).

---

## sce plan validate

Validate weekly plan JSON before populating (unified validator).

**Usage:**

```bash
sce plan validate --file /tmp/weekly_plan_w1.json
sce plan validate --file /tmp/weekly_plan_w1.json --verbose
```

**What it checks:**
- JSON structure + required fields
- Date alignment (week start Monday, end Sunday)
- Volume accuracy + minimum workout durations
- Guardrails and safety constraints

---

## sce plan update-from

Replace plan weeks from a specific week onward.

**Usage:**

```bash
sce plan update-from --week 5 --from-json /tmp/weeks_5_to_10.json
```

---

## sce plan save-review

Save plan review markdown to the repository after athlete approval.

**Usage:**

```bash
sce plan save-review --from-file /tmp/training_plan_review_2026_01_20.md --approved
```

---

## sce plan append-week

Append weekly training summary to the training log (used by weekly analysis).

**Usage:**

```bash
sce plan append-week --week 1 --from-json /tmp/week_1_summary.json
```

---

## sce plan assess-period

Assess a completed training period (2–6 weeks) for adaptive planning.

**Usage:**

```bash
sce plan assess-period   --period-number 1   --week-numbers "1,2,3,4"   --planned-workouts /tmp/planned.json   --completed-activities /tmp/completed.json   --starting-ctl 44.0   --ending-ctl 50.5   --target-ctl 52.0   --current-vdot 48.0
```

---

## sce plan suggest-run-count

Suggest optimal run count for a weekly volume and phase.

**Usage:**

```bash
sce plan suggest-run-count --volume 35 --max-runs 5 --phase build
```

---

**Navigation**: [Back to Index](index.md) | [Previous: Metrics Commands](cli_metrics.md) | [Next: Profile Commands](cli_profile.md)
