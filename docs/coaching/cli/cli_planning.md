# Planning Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Commands for setting race goals and managing training plans, including macro planning, weekly plan validation, and plan persistence.

**Commands in this category:**
- `sce goal set` - Set a race goal (validates feasibility if target time provided)
- `sce goal validate` - Validate existing goal feasibility
- `sce approvals status` - Show current approval state
- `sce approvals approve-vdot` - Record baseline VDOT approval
- `sce approvals approve-macro` - Record macro approval
- `sce approvals approve-week` - Record weekly approval (with file path)
- `sce plan show` - Get current training plan with all weeks and workouts
- `sce plan week` - Get specific week(s) from the training plan
- `sce plan populate` - Add/update weekly workouts in the plan
- `sce plan validate-week` - Validate single-week JSON before populate (unified validator)
- `sce plan validate-intervals` - Validate interval workout structure (Daniels)
- `sce plan validate-structure` - Validate plan structure inputs (phases, volumes, taper)
- `sce plan update-from` - Replace plan weeks from a specific week onwards
- `sce plan save-review` - Save plan review markdown
- `sce plan append-week` - Append weekly training summary to log
- `sce plan template-macro` - Generate a blank macro template JSON
- `sce plan create-macro` - Generate high-level plan structure (macro)
- `sce plan export-structure` - Export stored macro structure JSON for validation
- `sce plan assess-period` - Assess completed period for adaptive planning
- `sce plan suggest-run-count` - Suggest optimal run count for volume/phase

---

## sce goal set

Set a race goal (validates feasibility if target time provided).

**Usage:**

```bash
# Set 10K goal with target time
sce goal set --type 10k --date 2026-06-01 --time 00:45:00

# Set half marathon goal
sce goal set --type half_marathon --date 2026-09-15 --time 01:45:00

# Set marathon goal (no time = fitness goal)
sce goal set --type marathon --date 2026-11-01
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
2. If a target time is provided, feasibility is assessed and returned
3. Planning workflows use this goal as input (see `sce plan create-macro`)

---

## sce goal validate

Re-validate the current goal feasibility without setting a new goal.

**Usage:**

```bash
sce goal validate
```

**When to use:**

- Goal check-in mid-plan
- After illness/injury
- Before taper to confirm feasibility

---

## sce approvals status

Show current approval state (VDOT, macro, and weekly approval if present).

**Usage:**

```bash
sce approvals status
```

---

## sce approvals approve-vdot

Record baseline VDOT approval (required before macro creation).

**Usage:**

```bash
sce approvals approve-vdot --value 48.0
```

---

## sce approvals approve-macro

Record macro plan approval.

**Usage:**

```bash
sce approvals approve-macro
```

---

## sce approvals approve-week

Record weekly plan approval with the exact JSON file path.

**Usage:**

```bash
sce approvals approve-week --week 1 --file /tmp/weekly_plan_w1.json
```

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

## sce plan template-macro

Generate a blank macro template with required fields and null placeholders.

**Usage:**

```bash
sce plan template-macro --total-weeks 16 --out /tmp/macro_template.json
```

**Template Structure:**

The generated template includes:
- `weekly_volumes_km`: Weekly running volume targets (km)
- `target_systemic_load_au`: Total systemic load targets across ALL sports (optional)
- `workout_structure_hints`: Macro-level workout guidance per week

**Multi-Sport Planning:**

For **single-sport** athletes (running only):
- Set `target_systemic_load_au: [0.0, 0.0, ...]` (systemic load calculated later from running volume)

For **multi-sport** athletes (running + cross-training + other sports):
- Calculate total systemic load targets using `sce analysis load`
- Set `target_systemic_load_au: [95.0, 105.0, 110.0, ...]` (total aerobic load across all sports)
- Example: Week with 45 km running (45 AU) + climbing (48 AU) + yoga (12 AU) = 105 AU total systemic load

**Notes:**
- Replace all `null` values before calling `sce plan create-macro`
- Template is intentionally blank to keep planning decisions with the AI coach

---

## sce plan create-macro

Generate high-level training plan structure (macro plan) with phase boundaries, volume trajectory, CTL projections, and recovery week schedule.

**Template-first flow:** generate a blank template, fill it, then create the plan.

```bash
sce plan template-macro --total-weeks 16 --out /tmp/macro_template.json
# Fill /tmp/macro_template.json (replace nulls)
```

**Usage:**

```bash
# Requires approved baseline VDOT
sce approvals approve-vdot --value 48.0

# Generate macro plan for 16-week half marathon
sce plan template-macro --total-weeks 16 --out /tmp/macro_template.json
# Fill /tmp/macro_template.json with volumes + hints
sce plan create-macro \
  --goal-type half_marathon \
  --race-date 2026-05-03 \
  --target-time 01:30:00 \
  --total-weeks 16 \
  --start-date 2026-01-20 \
  --current-ctl 44.0 \
  --baseline-vdot 48.0 \
  --macro-template-json /tmp/macro_template.json

# Generate macro plan without target time (fitness goal)
sce plan template-macro --total-weeks 20 --out /tmp/macro_template.json
# Fill /tmp/macro_template.json with volumes + hints
sce plan create-macro \
  --goal-type marathon \
  --race-date 2026-11-01 \
  --total-weeks 20 \
  --start-date 2026-06-08 \
  --current-ctl 38.5 \
  --baseline-vdot 44.0 \
  --macro-template-json /tmp/macro_template.json
```

**Parameters:**

- `--goal-type` (required) - Race distance: `5k`, `10k`, `half_marathon`, `marathon`
- `--race-date` (required) - Race date in YYYY-MM-DD format
- `--target-time` (optional) - Target finish time in HH:MM:SS format (e.g., 01:30:00)
- `--total-weeks` (required) - Total training weeks (typically 12-20)
- `--start-date` (required) - Plan start date (YYYY-MM-DD), must be Monday
- `--current-ctl` (required) - Current CTL value (use `sce status` to get)
- `--baseline-vdot` (required) - Approved baseline VDOT for the macro plan
- `--macro-template-json` (required) - Macro template JSON generated by `sce plan template-macro` and filled by the AI coach (length of `workout_structure_hints` must equal `total_weeks`):
```json
{
  "template_version": "macro_template_v1",
  "total_weeks": 4,
  "volumes_km": [null, null, null, null],
  "workout_structure_hints": [
    {"quality": {"max_sessions": null, "types": null}, "long_run": {"emphasis": null, "pct_range": [null, null]}, "intensity_balance": {"low_intensity_pct": null}},
    {"quality": {"max_sessions": null, "types": null}, "long_run": {"emphasis": null, "pct_range": [null, null]}, "intensity_balance": {"low_intensity_pct": null}},
    {"quality": {"max_sessions": null, "types": null}, "long_run": {"emphasis": null, "pct_range": [null, null]}, "intensity_balance": {"low_intensity_pct": null}},
    {"quality": {"max_sessions": null, "types": null}, "long_run": {"emphasis": null, "pct_range": [null, null]}, "intensity_balance": {"low_intensity_pct": null}}
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
- **Starting/peak volume targets** - Derived outputs (NOT inputs): starting = weekly_volumes_km[0], peak = max(weekly_volumes_km)
- **CTL projections** - Expected CTL at key milestones (+0.75/week in base/build)
- **Recovery week schedule** - Every 4th week for adaptation
- **Phase focus** - Training emphasis for each phase

**Volume Derivation:**

`starting_volume_km` and `peak_volume_km` are **derived outputs** from the `weekly_volumes_km` array in the macro template:
- `starting_volume_km = weekly_volumes_km[0]`
- `peak_volume_km = max(weekly_volumes_km)`

These fields are **outputs**, not inputs. The AI coach fills `weekly_volumes_km` in the template using guardrails, and these summary values are automatically derived during plan creation.

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
sce plan validate-week --file /tmp/weekly_plan_wN.json

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

## sce plan validate-week

Validate weekly plan JSON before populating (unified validator).

**Usage:**

```bash
sce plan validate-week --file /tmp/weekly_plan_w1.json
sce plan validate-week --file /tmp/weekly_plan_w1.json --verbose
```

**What it checks:**
- JSON structure + required fields
- Date alignment (week start Monday, end Sunday)
- Volume accuracy + minimum workout durations
- Guardrails and safety constraints

---

## sce plan validate-intervals

Validate interval workout structure per Daniels methodology.

**Use when:** the week includes a structured tempo/interval session with explicit work + recovery bouts.

**Usage:**

```bash
sce plan validate-intervals \
    --type intervals \
    --intensity I-pace \
    --work-bouts work.json \
    --recovery-bouts recovery.json \
    --weekly-volume 50
```

**Input JSON Format (work.json):**

```json
[
  {
    "duration_minutes": 4.0,
    "pace_per_km_seconds": 270,
    "distance_km": 1.0
  },
  {
    "duration_minutes": 4.0,
    "pace_per_km_seconds": 270,
    "distance_km": 1.0
  }
]
```

**Input JSON Format (recovery.json):**

```json
[
  {
    "duration_minutes": 4.0,
    "type": "jog"
  },
  {
    "duration_minutes": 4.0,
    "type": "jog"
  }
]
```

**Daniels Rules Checked:**

- **I-pace**: 3-5min work bouts, equal recovery (jogging), total ≤10km or 8% weekly
- **T-pace**: 5-15min work bouts, 1min recovery per 5min work, total ≤10% weekly
- **R-pace**: 30-90sec work bouts, 2-3x recovery, total ≤8km or 5% weekly

**Returns:** Workout type, intensity, work/recovery bout analysis (ok/issue per bout), violations (type/severity/message/recommendation), total work volume (minutes/km), daniels_compliance (true/false), recommendations.

---

## sce plan validate-structure

Validate training plan structure for common errors.

**Use when:** creating or revising macro plan phases/volumes (not for single-week JSON).

**Usage:**

```bash
sce plan validate-structure \
    --total-weeks 20 \
    --goal-type half_marathon \
    --phases phases.json \
    --weekly-volumes volumes.json \
    --recovery-weeks recovery.json \
    --race-week 20
```

**Input JSON Format (phases.json):**

```json
{
  "base": 8,
  "build": 8,
  "peak": 2,
  "taper": 2
}
```

**Input JSON Format (volumes.json):**

```json
[25, 27, 29, 22, 31, 33, 35, 28, 37, 40, 43, 35, 46, 50, 54, 43, 60, 58, 35, 20]
```

**Input JSON Format (recovery.json):**

```json
[4, 8, 12, 16]
```

**Checks Performed:**

- **Phase duration**: Base/build/peak/taper weeks appropriate for goal type
- **Volume progression**: Average weekly increase ≤10% (10% rule)
- **Peak placement**: Peak week 2-3 weeks before race
- **Recovery frequency**: Recovery weeks every 3-4 weeks
- **Taper structure**: Gradual volume reduction (70%, 50%, 30% for 3-week taper)

**Returns:** Total weeks, goal type, phase duration checks, volume progression check, peak placement check, recovery week check, taper structure check, violations, overall_quality_score (0-100), recommendations.

---

## sce plan export-structure

Export stored macro plan structure into validation-ready JSON files.

**Usage:**

```bash
sce plan export-structure --out-dir /tmp
```

**Outputs:**
- `/tmp/plan_phases.json` (phase -> weeks)
- `/tmp/weekly_volumes_list.json` (list of weekly volumes in km)
- `/tmp/recovery_weeks.json` (list of recovery week numbers)

**Returns:** total_weeks, goal_type, race_week, phases, weekly_volumes_km, recovery_weeks, and file paths.

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
