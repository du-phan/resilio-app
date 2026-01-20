# Planning Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Commands for setting race goals and managing training plans, including macro planning, weekly plan generation (primary workflow), and plan validation.

**Commands in this category:**
- `sce goal` - Set a race goal (automatically regenerates plan)
- `sce plan show` - Get current training plan with all weeks and workouts
- `sce plan regen` - Regenerate plan based on current goal
- `sce plan week` - Get specific week(s) from the training plan
- `sce plan create-macro` - Generate high-level training plan structure (16-week macro, mileage targets only)
- `sce plan generate-week` - **Generate detailed workouts for one week (primary workflow)**
- `sce plan validate-week` - **Validate single week's workout plan before saving**
- `sce plan revert-week` - **Revert week to macro plan targets (remove detailed workouts)**
- `sce plan generate-month` - Generate detailed monthly plan (batch scenarios, 2-6 weeks)
- `sce plan assess-month` - Assess completed month for adaptive planning
- `sce plan validate-month` - Validate monthly plan before saving

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

---

## sce plan regen

Regenerate plan based on current goal.

**Usage:**

```bash
sce plan regen
```

**When to use:**

- After significant training interruption
- After injury recovery (CTL dropped)
- Profile constraints changed significantly
- Want fresh plan with same goal

---

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
# Generate macro plan for 16-week half marathon
sce plan create-macro \
  --goal-type half_marathon \
  --race-date 2026-05-03 \
  --target-time 01:30:00 \
  --total-weeks 16 \
  --start-date 2026-01-20 \
  --current-ctl 44.0 \
  --starting-volume 25.0 \
  --peak-volume 55.0

# Generate macro plan without target time (fitness goal)
sce plan create-macro \
  --goal-type marathon \
  --race-date 2026-11-01 \
  --total-weeks 20 \
  --start-date 2026-06-08 \
  --current-ctl 38.5 \
  --starting-volume 20.0 \
  --peak-volume 65.0
```

**Parameters:**

- `--goal-type` (required) - Race distance: `5k`, `10k`, `half_marathon`, `marathon`
- `--race-date` (required) - Race date in YYYY-MM-DD format
- `--target-time` (optional) - Target finish time in HH:MM:SS format (e.g., 01:30:00)
- `--total-weeks` (required) - Total training weeks (typically 12-20)
- `--start-date` (required) - Plan start date (YYYY-MM-DD), must be Monday
- `--current-ctl` (required) - Current CTL value (use `sce status` to get)
- `--starting-volume` (required) - Starting weekly volume in km
- `--peak-volume` (required) - Peak weekly volume in km

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
    "volume_trajectory": [
      {"week": 1, "target_km": 25.0},
      {"week": 4, "target_km": 32.5},
      {"week": 7, "target_km": 42.0},
      {"week": 12, "target_km": 55.0},
      {"week": 16, "target_km": 18.0}
    ],
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
- **Volume trajectory** - Weekly volume targets using 10% rule, with recovery weeks at 70%
- **CTL projections** - Expected CTL at key milestones (+0.75/week in base/build)
- **Recovery week schedule** - Every 4th week for adaptation
- **Phase focus** - Training emphasis for each phase

**When to use:**

- First step of progressive disclosure planning (generate big picture before monthly details)
- Creating structural roadmap that athlete can see and approve
- Setting volume targets that guide subsequent monthly plan generation
- Establishing CTL progression goals for the training cycle

---

## sce plan generate-month

Generate detailed monthly plan (2-6 weeks) with workout prescriptions using macro plan targets and profile constraints.

> **Note**: This command is for **batch scenarios** (catching up multiple weeks, onboarding catch-up). For **primary workflow**, use `sce plan generate-week` (1 week at a time) integrated into the weekly-analysis skill for maximum adaptability.

**Usage:**

```bash
# Generate first month (4 weeks)
sce plan generate-month \
  --month-number 1 \
  --week-numbers "1,2,3,4" \
  --from-macro /tmp/macro_plan.json \
  --current-vdot 48.0 \
  --profile data/athlete/profile.yaml

# Generate 3-week cycle for 11-week plan
sce plan generate-month \
  --month-number 3 \
  --week-numbers "9,10,11" \
  --from-macro /tmp/macro_plan.json \
  --current-vdot 49.0 \
  --profile data/athlete/profile.yaml

# Generate with volume reduction (10% less due to injury signals)
sce plan generate-month \
  --month-number 2 \
  --week-numbers "5,6,7,8" \
  --from-macro /tmp/macro_plan.json \
  --current-vdot 48.5 \
  --profile data/athlete/profile.yaml \
  --volume-adjustment 0.9
```

**Parameters:**

- `--month-number` (required) - Month number (1-5 typically, may vary)
- `--week-numbers` (required) - Comma-separated week numbers (e.g., "1,2,3,4" or "9,10,11")
- `--from-macro` (required) - Path to macro plan JSON file
- `--current-vdot` (required) - Current VDOT (30-85, may be recalibrated from previous month)
- `--profile` (required) - Path to athlete profile file (YAML or JSON)
- `--volume-adjustment` (optional) - Volume multiplier (0.5-1.5, default 1.0)

**Returns:**

```json
{
  "ok": true,
  "message": "Monthly plan generated for month 1 (4-week cycle): weeks 1-4",
  "data": {
    "month_number": 1,
    "weeks_covered": [1, 2, 3, 4],
    "num_weeks": 4,
    "weeks": [
      {
        "week_number": 1,
        "phase": "base",
        "start_date": "2026-01-20",
        "end_date": "2026-01-26",
        "target_volume_km": 25.0,
        "is_recovery_week": false,
        "workouts": [
          {
            "id": "w_2026-01-20_easy_abc123",
            "workout_type": "easy",
            "date": "2026-01-20",
            "distance_km": 8.0,
            "duration_minutes": 48,
            "pace_zone": "E-pace",
            "purpose": "Aerobic foundation",
            "...": "..."
          }
        ],
        "notes": "Week 1 - Base phase: Aerobic foundation building"
      }
    ],
    "paces": {
      "vdot": 48.0,
      "e_pace": "6:15-6:45 /km",
      "m_pace": "5:25-5:40 /km",
      "t_pace": "4:55-5:10 /km",
      "i_pace": "4:35-4:50 /km",
      "r_pace": "4:15-4:30 /km"
    },
    "generation_context": {
      "volume_adjustment": 1.0,
      "generated_at": "2026-01-20",
      "cycle_length_weeks": 4,
      "phases_included": ["base"]
    }
  }
}
```

**What it generates:**

- **Detailed workout prescriptions** for each week in the cycle
- **Phase-appropriate distribution**: Base (long run + easy), Build (+ tempo/intervals), Peak (max load), Taper (reduced volume)
- **Multi-sport integration**: Workouts scheduled around other sports from profile
- **VDOT-based paces**: E/M/T/I/R pace zones for quality workouts
- **Volume allocation**: Uses `distribute_weekly_volume()` to ensure targets are met
- **Recovery week handling**: Every 4th week at 70% volume during base/build
- **Minimum duration compliance**: Easy 30min/5km, long 60min/8km

**Flexible cycle lengths:**

The system handles variable-length cycles (2-6 weeks) for plans that aren't evenly divisible by 4:
- **11-week plan**: Months might be 4+4+3 weeks
- **13-week plan**: Months might be 4+4+5 weeks
- **15-week plan**: Months might be 4+4+4+3 weeks

**Volume adjustment scenarios:**

- `1.0` (default) - Use macro plan targets as-is
- `0.9` - Reduce 10% if injury signals detected or athlete struggling
- `0.95` - Reduce 5% if CTL lagging but no injury signals
- `1.05` - Increase 5% if athlete handling load very well (use cautiously)

**When to use:**

- Initial plan creation: Generate first month (weeks 1-4) after macro plan approved
- Monthly transitions: Generate next month after assessing completed month
- Plan adaptation: Regenerate current month with adjusted volumes if needed

**Integration with other commands:**

```bash
# Typical monthly workflow:
# 1. Generate month
sce plan generate-month --month-number 2 --week-numbers "5,6,7,8" ...

# 2. Validate before presenting
sce plan validate-month --monthly-plan /tmp/monthly_plan_m2.json --macro-targets /tmp/targets.json

# 3. Save after approval
sce plan populate --from-json /tmp/monthly_plan_m2.json

# 4. At end of month, assess
sce plan assess-month --month-number 2 --week-numbers "5,6,7,8" ...

# 5. Generate next month with updated context
sce plan generate-month --month-number 3 --week-numbers "9,10,11,12" --current-vdot 49.5 ...
```

---

## sce plan assess-month

Assess completed month for adaptive planning - analyzes adherence, CTL progression, VDOT recalibration signals, and volume tolerance.

**Usage:**

```bash
# Assess month 1 (weeks 1-4) completion
sce plan assess-month \
  --month-number 1 \
  --week-numbers "1,2,3,4" \
  --planned-workouts /tmp/planned_workouts.json \
  --completed-activities /tmp/completed_activities.json \
  --starting-ctl 44.0 \
  --ending-ctl 50.5 \
  --target-ctl 52.0 \
  --current-vdot 48.0

# Assess month 2 (weeks 5-8)
sce plan assess-month \
  --month-number 2 \
  --week-numbers "5,6,7,8" \
  --planned-workouts /tmp/planned_m2.json \
  --completed-activities /tmp/completed_m2.json \
  --starting-ctl 50.5 \
  --ending-ctl 55.2 \
  --target-ctl 55.0 \
  --current-vdot 49.0
```

**Parameters:**

- `--month-number` (required) - Month number (1-4 for typical 16-week plan)
- `--week-numbers` (required) - Comma-separated week numbers (e.g., "1,2,3,4")
- `--planned-workouts` (required) - Path to JSON file with planned workouts
- `--completed-activities` (required) - Path to JSON file with completed activities from Strava
- `--starting-ctl` (required) - CTL at start of month
- `--ending-ctl` (required) - CTL at end of month
- `--target-ctl` (required) - Target CTL from macro plan
- `--current-vdot` (required) - Current VDOT value

**Input file formats:**

```json
// planned_workouts.json
[
  {
    "week_number": 1,
    "date": "2026-01-20",
    "workout_type": "easy",
    "distance_km": 8.0
  }
]

// completed_activities.json (from sce sync)
[
  {
    "date": "2026-01-20",
    "type": "Run",
    "distance_km": 8.2,
    "duration_minutes": 48,
    "description": "Easy morning run, felt good",
    "private_note": "Left knee slightly sore"
  }
]
```

**Returns:**

```json
{
  "ok": true,
  "message": "Month 1 assessment complete: 95% adherence, CTL on track",
  "data": {
    "month_number": 1,
    "weeks_covered": [1, 2, 3, 4],
    "adherence": {
      "completion_rate_pct": 95.0,
      "workouts_planned": 20,
      "workouts_completed": 19,
      "missed_workouts": [
        {"week": 2, "date": "2026-01-28", "type": "easy", "reason": "Detected 'tired' in notes"}
      ]
    },
    "ctl_progression": {
      "starting_ctl": 44.0,
      "ending_ctl": 50.5,
      "target_ctl": 52.0,
      "delta_from_target": -1.5,
      "status": "on_track",
      "interpretation": "Within 5% of target (97% achieved)"
    },
    "vdot_recalibration": {
      "needs_recalibration": false,
      "quality_completion_rate": 100.0,
      "rationale": "All tempo/interval sessions completed as prescribed"
    },
    "injury_illness_signals": {
      "detected": true,
      "keywords_found": ["tired", "sore"],
      "affected_workouts": [
        {"date": "2026-01-28", "note": "tired after work"},
        {"date": "2026-02-05", "note": "Left knee slightly sore"}
      ],
      "recommendation": "Monitor knee soreness - consider reducing volume if persists"
    },
    "volume_tolerance": {
      "assessment": "good",
      "rationale": "Completed 95% of planned volume, no systemic fatigue signals"
    },
    "recommendations": [
      "Continue with planned month 2 volume progression",
      "Monitor left knee - consider easy run reduction if soreness continues",
      "VDOT recalibration not needed (quality sessions completed well)"
    ]
  }
}
```

**What it analyzes:**

- **Adherence rates** - Planned vs. actual workout completion
- **CTL progression** - Whether athlete achieved target CTL (within 5% = on track)
- **VDOT recalibration signals** - Quality session completion <85% suggests pace adjustment needed
- **Injury/illness detection** - Keyword search in activity notes ("pain", "injury", "sick", "tired")
- **Volume tolerance** - Whether athlete handled the load well

**When to use:**

- End of each 4-week monthly cycle before generating next month
- Detecting need for VDOT recalibration (update paces if quality sessions struggled)
- Identifying injury/illness patterns requiring plan adjustments
- Informing next month's volume targets based on tolerance assessment

---

## sce plan validate-month

Validate 4-week monthly plan before saving - checks volume discrepancies, minimum workout durations, and guardrail compliance.

**Usage:**

```bash
# Validate monthly plan against macro targets
sce plan validate-month \
  --monthly-plan /tmp/monthly_plan_m2.json \
  --macro-targets /tmp/macro_targets_weeks_5_8.json
```

**Parameters:**

- `--monthly-plan` (required) - Path to JSON file with 4-week monthly plan
- `--macro-targets` (required) - Path to JSON file with macro plan volume targets for these weeks

**Input file formats:**

```json
// monthly_plan_m2.json
{
  "month_number": 2,
  "weeks": [
    {
      "week_number": 5,
      "target_volume_km": 45.0,
      "workouts": [
        {
          "date": "2026-02-17",
          "workout_type": "easy",
          "distance_km": 8.0,
          "duration_minutes": 48
        },
        {
          "date": "2026-02-19",
          "workout_type": "tempo",
          "distance_km": 10.0,
          "duration_minutes": 52
        }
      ]
    }
  ]
}

// macro_targets_weeks_5_8.json
[
  {"week": 5, "target_km": 45.0},
  {"week": 6, "target_km": 47.0},
  {"week": 7, "target_km": 50.0},
  {"week": 8, "target_km": 35.0}
]
```

**Returns:**

```json
{
  "ok": true,
  "message": "Monthly plan validated: 2 warnings, no critical violations",
  "data": {
    "overall_ok": true,
    "violations": [],
    "warnings": [
      {
        "severity": "warning",
        "week": 5,
        "issue": "Volume discrepancy: 46.5 km actual vs 45.0 km target (+3.3%)",
        "recommendation": "Acceptable (<5%), no action needed"
      },
      {
        "severity": "warning",
        "week": 7,
        "issue": "Easy run on 2026-03-03 is 4.5 km (below 5 km minimum)",
        "recommendation": "Consider merging with another easy run or increasing to 5 km"
      }
    ],
    "summary": {
      "weeks_checked": 4,
      "critical_issues": 0,
      "warnings": 2,
      "volume_accuracy": "98.2% average (all weeks <5% discrepancy)",
      "minimum_duration_compliance": "95% (1 violation)"
    }
  }
}
```

**What it validates:**

- **Volume discrepancies** - <5% acceptable, 5-10% warning, >10% critical error
- **Minimum workout durations**:
  - Easy runs: 30 min / 5 km
  - Long runs: 60 min / 8 km
  - Tempo runs: 40 min total
  - Intervals: 35 min total
- **Guardrail compliance** - Quality volume limits, long run caps, recovery week volumes
- **Recovery week verification** - Every 4th week at 70% volume

**Violation severities:**

- **`critical`** - Must fix before saving (>10% volume discrepancy, safety violations)
- **`warning`** - Review but may be acceptable (<5% discrepancy, minor duration issues)
- **`info`** - FYI only, no action needed

**When to use:**

- After generating monthly plan, before presenting to athlete
- Catches LLM arithmetic errors (volume distribution mistakes)
- Ensures minimum viable workout durations
- Prevents unsafe training loads (quality volume limits, long run caps)

---

## sce plan generate-week

Generate detailed workouts for a single week using macro plan targets and progressive disclosure workflow.

> **Primary Workflow**: This is the **recommended command** for weekly planning. Use this after weekly-analysis to generate the next week's workouts based on actual training response.

**Usage:**

```bash
# Generate week 1 (initial plan creation)
sce plan generate-week \
  --week-number 1 \
  --from-macro /tmp/macro_plan.json \
  --current-vdot 48.0 \
  > /tmp/weekly_plan_w1.json

# Generate week 2 (after completing week 1)
sce plan generate-week \
  --week-number 2 \
  --from-macro data/plans/current_plan_macro.json \
  --current-vdot 48.5 \
  > /tmp/weekly_plan_w2.json

# Generate with volume reduction (10% less due to fatigue)
sce plan generate-week \
  --week-number 3 \
  --from-macro data/plans/current_plan_macro.json \
  --current-vdot 48.5 \
  --volume-adjustment 0.9 \
  > /tmp/weekly_plan_w3.json
```

**Parameters:**

- `--week-number` (required) - Week number (1-16 typically)
- `--from-macro` (required) - Path to macro plan JSON file
- `--current-vdot` (required) - Current VDOT (30-85, may be recalibrated based on performance)
- `--volume-adjustment` (optional) - Volume multiplier (0.5-1.5, default 1.0)
- `--output` (optional) - Output file path (default: stdout)

**Returns:**

```json
{
  "ok": true,
  "message": "Week 2 plan generated: 26.0 km across 4 runs",
  "data": {
    "weeks": [
      {
        "week_number": 2,
        "phase": "base",
        "start_date": "2026-01-27",
        "end_date": "2026-02-02",
        "target_volume_km": 26.0,
        "is_recovery_week": false,
        "notes": "Week 2 - Base phase: Aerobic foundation",
        "workout_pattern": {
          "structure": "3 easy + 1 long",
          "run_days": [1, 3, 5, 6],
          "long_run_day": 6,
          "long_run_duration_min": 72,
          "long_run_pct": 46.0,
          "easy_runs": [
            {"run_number": 1, "distance_km": 4.5, "duration_min": 31, "day": 1},
            {"run_number": 2, "distance_km": 5.0, "duration_min": 34, "day": 3},
            {"run_number": 3, "distance_km": 4.5, "duration_min": 31, "day": 5}
          ],
          "long_run": {
            "distance_km": 12.0,
            "duration_min": 72,
            "pace_intention": "E-pace"
          },
          "paces": {
            "e_pace_min_km": "06:15",
            "e_pace_max_km": "06:45"
          }
        }
      }
    ]
  }
}
```

**What it generates:**

- **Intent-based format** - Coach specifies structure (3 easy + 1 long), system calculates exact distances
- **Single week only** - Progressive disclosure: plan 1 week at a time based on actual response
- **Phase-appropriate workouts** - Base (easy runs), Build (+ tempo/intervals), Peak (max load), Taper (reduced volume)
- **Multi-sport integration** - Workouts scheduled around other sports from profile
- **VDOT-based paces** - E/M/T/I/R pace zones for quality workouts
- **Volume allocation** - Uses `distribute_weekly_volume()` to ensure target is met
- **Minimum duration compliance** - Easy 30min/5km, long 60min/8km

**Progressive disclosure workflow:**

1. **Generate macro plan** - 16 weeks with mileage targets only (NO detailed workouts)
2. **Generate week 1** - Detailed workouts for first week
3. **Complete week 1** - Athlete trains, tracks activities
4. **Weekly analysis** - Analyze adherence, CTL, triggers, readiness
5. **Generate week 2** - Based on week 1 response (VDOT recalibration, volume adjustment)
6. **Repeat** - Each week adapts to actual training response

**Benefits over monthly planning:**

- **Maximum adaptability** - Respond immediately to illness, injury, schedule changes
- **Reduced LLM errors** - Smaller scope (7 days vs 28 days) = fewer date/calculation mistakes
- **Natural coaching rhythm** - Aligns with weekly-analysis skill (weekly check-ins)
- **Authentic coaching** - Real coaches plan week-by-week based on athlete response

**Volume adjustment scenarios:**

- `1.0` (default) - Use macro plan target as-is
- `0.9` - Reduce 10% if injury signals detected or elevated ACWR
- `0.95` - Reduce 5% if athlete struggling with fatigue
- `1.05` - Increase 5% if athlete handling load exceptionally well (use cautiously)

**When to use:**

- **Initial plan creation** - Generate week 1 after macro plan approved
- **Weekly transitions** - Generate next week after weekly-analysis completion (integrated workflow)
- **Plan adaptation** - Regenerate current week with adjusted volumes if needed

**Integration with weekly-analysis:**

The `weekly-analysis` skill automatically integrates weekly planning:

```bash
# After analyzing completed week:
# 1. Check macro plan for next week's target
# 2. Assess if volume adjustment needed
# 3. Recalibrate VDOT if significant performance change
# 4. Generate next week's workouts
sce plan generate-week --week-number $NEXT_WEEK ...
# 5. Validate plan
sce plan validate-week --weekly-plan /tmp/weekly_plan_w$NEXT_WEEK.json
# 6. Present to athlete
# 7. Save after approval
sce plan populate --from-json /tmp/weekly_plan_w$NEXT_WEEK.json
```

---

## sce plan validate-week

Validate a single week's workout plan before saving - checks JSON structure, volume discrepancy, minimum durations, and date alignment.

**Usage:**

```bash
# Validate week 1 plan
sce plan validate-week --weekly-plan /tmp/weekly_plan_w1.json

# Validate with verbose output (shows all checks)
sce plan validate-week --weekly-plan /tmp/weekly_plan_w1.json --verbose
```

**Parameters:**

- `--weekly-plan` (required) - Path to JSON file with single week's plan
- `--verbose` (optional) - Show detailed validation checks (default: false)

**Input file format:**

```json
{
  "weeks": [
    {
      "week_number": 1,
      "phase": "base",
      "start_date": "2026-01-20",
      "end_date": "2026-01-26",
      "target_volume_km": 23.0,
      "workout_pattern": {
        "structure": "3 easy + 1 long",
        "run_days": [1, 3, 5, 6],
        "easy_runs": [
          {"distance_km": 4.0, "duration_min": 28},
          {"distance_km": 4.5, "duration_min": 31},
          {"distance_km": 4.0, "duration_min": 28}
        ],
        "long_run": {"distance_km": 10.5, "duration_min": 72}
      }
    }
  ]
}
```

**Returns (success):**

```json
{
  "ok": true,
  "message": "Weekly plan validated: 0 errors, 1 warning",
  "data": {
    "overall_ok": true,
    "violations": [],
    "warnings": [
      {
        "severity": "warning",
        "week": 1,
        "issue": "Volume discrepancy: 23.0 km actual vs 23.0 km target (0.0%)",
        "recommendation": "Perfect match - no action needed"
      }
    ],
    "summary": {
      "weeks_checked": 1,
      "critical_issues": 0,
      "warnings": 0,
      "volume_accuracy": "100.0%",
      "minimum_duration_compliance": "100%"
    }
  }
}
```

**Returns (errors detected):**

```json
{
  "ok": false,
  "message": "Weekly plan validation failed: 2 errors, 1 warning",
  "data": {
    "overall_ok": false,
    "violations": [
      {
        "severity": "critical",
        "week": 2,
        "issue": "Easy run on 2026-01-28 is 3.5 km (below 5 km minimum)",
        "recommendation": "Increase to at least 5 km or merge with another easy run"
      },
      {
        "severity": "critical",
        "week": 2,
        "issue": "Start date 2026-01-28 is Tuesday, not Monday",
        "recommendation": "Training weeks must start on Monday"
      }
    ],
    "warnings": [
      {
        "severity": "warning",
        "week": 2,
        "issue": "Long run is 55% of weekly volume (recommended <50%)",
        "recommendation": "Consider adding another easy run to balance load"
      }
    ],
    "summary": {
      "weeks_checked": 1,
      "critical_issues": 2,
      "warnings": 1,
      "volume_accuracy": "98.5%",
      "minimum_duration_compliance": "75% (1 violation)"
    }
  }
}
```

**What it validates:**

- **JSON structure** - Required fields present (`week_number`, `phase`, `start_date`, `target_volume_km`, `workout_pattern`)
- **workout_pattern presence** - Intent-based format required (not empty workouts array)
- **Date alignment** - `start_date` must be Monday (weekday 0), `end_date` must be Sunday (weekday 6)
- **Volume accuracy** - Actual volume within 5% of target (<5% acceptable, >10% critical)
- **Minimum workout durations**:
  - Easy runs: 30 min / 5 km
  - Long runs: 60 min / 8 km
  - Tempo runs: 40 min total
  - Intervals: 35 min total
- **Long run percentage** - Should be <50% of weekly volume (warning if >50%)
- **ISO weekday validation** - `run_days` must be 1-7 (Monday=1, Sunday=7)

**Violation severities:**

- **`critical`** - Must fix before saving (date errors, volume >10% off, safety violations)
- **`warning`** - Review but may be acceptable (volume <5% off, minor duration issues)
- **`info`** - FYI only, no action needed

**When to use:**

- **After generating weekly plan** - Validate before presenting to athlete
- **Before saving plan** - Catches errors before committing to system
- **Catches LLM errors** - Date calculation mistakes, volume distribution errors
- **Ensures safety** - Minimum durations, reasonable long run percentages

**Integration with workflow:**

```bash
# Standard workflow:
# 1. Generate week
sce plan generate-week --week-number 2 ... > /tmp/weekly_plan_w2.json

# 2. Validate BEFORE presenting
sce plan validate-week --weekly-plan /tmp/weekly_plan_w2.json

# 3. If validation fails, regenerate with corrections
# 4. Once validated, present to athlete
# 5. After approval, save
sce plan populate --from-json /tmp/weekly_plan_w2.json
```

---

## sce plan revert-week

Revert a week's plan to macro plan targets (remove detailed workouts) - useful for rolling back if athlete disagrees with generated workouts.

**Usage:**

```bash
# Revert week 3 to macro plan targets only
sce plan revert-week --week-number 3

# After reverting, can regenerate with different parameters
sce plan generate-week --week-number 3 --volume-adjustment 0.9 ...
```

**Parameters:**

- `--week-number` (required) - Week number to revert (1-16 typically)

**Returns (success):**

```json
{
  "ok": true,
  "message": "Week 3 reverted to macro plan targets (detailed workouts removed)",
  "data": {
    "week_number": 3,
    "previous_state": {
      "had_workouts": true,
      "workout_count": 4,
      "total_volume_km": 30.0
    },
    "current_state": {
      "has_workouts": false,
      "target_volume_km": 30.0,
      "phase": "base",
      "notes": "Week 3 - Base phase (reverted to macro targets)"
    }
  }
}
```

**Returns (error - week not found):**

```json
{
  "ok": false,
  "error_type": "not_found",
  "message": "Week 5 not found in current plan"
}
```

**What it does:**

1. **Loads current plan** - Reads `data/plans/current_plan.yaml`
2. **Finds specified week** - Locates week by `week_number`
3. **Removes workout details** - Deletes `workout_pattern` and `workouts` fields
4. **Keeps macro data** - Preserves `target_volume_km`, `phase`, `start_date`, `end_date`, `notes`
5. **Saves updated plan** - Writes back to `current_plan.yaml`

**Use cases:**

- **Athlete disagrees with volume** - "That's too much for me this week"
- **Schedule changed** - "I can only run 3 days next week, not 4"
- **Volume adjustment needed** - Revert and regenerate with `--volume-adjustment 0.9`
- **Testing/experimentation** - Try different workout structures for the same week
- **Rollback after mistake** - Undo if wrong week was generated

**Workflow example:**

```bash
# Scenario: Week 4 generated with 4 runs, athlete wants 3 runs instead

# 1. Revert week 4 to macro targets
sce plan revert-week --week-number 4

# 2. Update profile constraint (if needed)
sce profile set --max-run-days 3

# 3. Regenerate week 4 with new constraint
sce plan generate-week --week-number 4 --from-macro data/plans/current_plan_macro.json ...

# 4. Validate new plan
sce plan validate-week --weekly-plan /tmp/weekly_plan_w4.json

# 5. Present and save after approval
sce plan populate --from-json /tmp/weekly_plan_w4.json
```

**Important notes:**

- **Does not affect future weeks** - Only reverts specified week
- **Does not delete macro plan** - Macro plan (`current_plan_macro.json`) remains intact
- **Safe operation** - Can always regenerate after reverting
- **No historical data loss** - Past weeks (already completed) remain unchanged

**When NOT to use:**

- **To skip a week** - Use plan adaptation workflow instead
- **To delete entire plan** - Use `sce plan regen` to regenerate from goal
- **To modify workouts** - Edit plan directly or regenerate with adjusted parameters

---

**Navigation**: [Back to Index](index.md) | [Previous: Metrics Commands](cli_metrics.md) | [Next: Profile Commands](cli_profile.md)
