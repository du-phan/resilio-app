# JSON Plan Creation Workflow

## Quick Start

```bash
# 1. Create plan skeleton
poetry run sce plan regen

# 2. Create JSON using intent-based format (see below)

# 3. Validate JSON
poetry run sce plan validate-json --file /tmp/plan.json

# 4. Populate plan (system calculates exact distances)
poetry run sce plan populate --from-json /tmp/plan.json

# 5. Verify
poetry run sce plan show
poetry run sce today
```

---

## Intent-Based Format (RECOMMENDED)

**Philosophy**: AI Coach specifies coaching intent (volume targets, workout structure), system handles arithmetic.

### Format Structure

```json
{
  "weeks": [
    {
      "week_number": 1,
      "phase": "base",
      "start_date": "2026-01-19",
      "end_date": "2026-01-25",
      "target_volume_km": 23.0,
      "target_systemic_load_au": 161.0,
      "is_recovery_week": false,
      "notes": "Base Phase Week 1",
      "workout_pattern": {
        "structure": "3 easy + 1 long",
        "run_days": [1, 3, 5, 6],
        "long_run_day": 6,
        "long_run_pct": 0.45,
        "easy_run_paces": "6:30-6:50",
        "long_run_pace": "6:30-6:50"
      }
    }
  ]
}
```

### How System Calculates

**Example**: Week with 23km target, 4 runs (3 easy + 1 long), 45% long run

1. **Long run**: 23 × 0.45 = 10.35 → **10.5km** (rounded to 0.5km)
2. **Remaining**: 23 - 10.5 = **12.5km** for easy runs
3. **Per easy run**: 12.5 ÷ 3 = 4.17km
4. **Distributed**: [**4.0**, **4.5**, **4.0**, **10.5**]
5. **Validation**: 4.0 + 4.5 + 4.0 + 10.5 = **23.0km** ✓

**Result**: Zero arithmetic errors, guaranteed sum!

### AI Coach's Decisions (High-Level)

These are coaching decisions based on training methodology:

| Field | Decision | Rationale |
|-------|----------|-----------|
| `target_volume_km` | 23.0 | Based on CTL, progression, athlete capacity |
| `structure` | "3 easy + 1 long" | Based on run frequency, training phase |
| `run_days` | [1, 3, 5, 6] | Tue/Thu/Sat/Sun - athlete schedule constraints |
| `long_run_pct` | 0.45 | Base phase: 40-45%, Build phase: 45-50% |
| `paces` | "6:30-6:50" | Based on VDOT, athlete fitness level |

### System's Calculations (Low-Level)

System handles all mechanical tasks:

- Exact workout distances summing to target (no rounding errors)
- WorkoutPrescription objects with all required fields
- Date calculations from week start and day of week
- HR zones based on workout type and athlete max HR
- Duration estimates from distance and pace
- Workout IDs, status fields, metadata

---

## Macro Plan vs Weekly Plan

**Critical distinction**: Training plans use progressive disclosure with TWO formats:

### Macro Plan Format (16 Weeks, NO WORKOUTS)

Macro plans provide structure ONLY - phase boundaries, volume trajectory, no detailed workouts.

```json
{
  "weeks": [
    {
      "week_number": 1,
      "phase": "base",
      "start_date": "2026-01-20",
      "end_date": "2026-01-26",
      "target_volume_km": 23.0,
      "is_recovery_week": false,
      "notes": "Base Phase Week 1"
      // NO workout_pattern field - this will be generated when week arrives
    },
    {
      "week_number": 2,
      "phase": "base",
      "start_date": "2026-01-27",
      "end_date": "2026-02-02",
      "target_volume_km": 26.0,
      "is_recovery_week": false,
      "notes": "Base Phase Week 2"
      // NO workout_pattern field - future weeks remain as mileage targets
    }
  ]
}
```

**When to use**: `sce plan create-macro` generates this for the entire 16-week plan.

**Purpose**: Provides big-picture structure (phases, volume trajectory) without committing to specific workouts.

### Weekly Plan Format (1 Week, WITH WORKOUTS)

Weekly plans provide execution detail for the NEXT WEEK ONLY.

```json
{
  "weeks": [
    {
      "week_number": 1,
      "phase": "base",
      "start_date": "2026-01-20",
      "end_date": "2026-01-26",
      "target_volume_km": 23.0,
      "is_recovery_week": false,
      "notes": "Base Phase Week 1",
      "workout_pattern": {
        "structure": "3 easy + 1 long",
        "run_days": [1, 3, 5, 6],
        "long_run_day": 6,
        "long_run_pct": 0.45,
        "easy_run_paces": "6:30-6:50",
        "long_run_pace": "6:30-6:50"
      }
    }
  ]
}
```

**When to use**: `sce plan generate-week` generates this for the immediate week.

**Purpose**: Provides detailed workouts with paces, ready to execute.

### Key Differences

| Aspect | Macro Plan | Weekly Plan |
|--------|------------|-------------|
| **Weeks included** | All 16 weeks | 1 week only |
| **Detail level** | Mileage targets only | Complete workout prescriptions |
| **Has workout_pattern** | ❌ NO | ✅ YES |
| **Purpose** | Big-picture structure | Execution detail |
| **CLI command** | `sce plan create-macro` | `sce plan generate-week` |
| **When generated** | Once at plan start | Weekly, after completing previous week |

### Progressive Disclosure Workflow

1. **Initial plan design** (training-plan-design skill):
   - Generate macro plan (16 weeks, NO workouts)
   - Generate week 1 (WITH workouts)
   - Save both: macro remains constant, week 1 ready to execute

2. **After week 1 completes** (weekly-analysis skill):
   - Analyze week 1 adherence, adaptation
   - Generate week 2 (WITH workouts)
   - Weeks 3-16 remain as mileage targets

3. **Each week**:
   - Complete current week → analyze → generate next week
   - Macro plan provides context (phase, volume trajectory)
   - Weekly plan provides execution (paces, distances)

⚠️ **CRITICAL**: NEVER generate `workout_pattern` for weeks beyond the immediate week. This violates progressive disclosure and creates rigid plans that can't adapt.

---

## Explicit Format (OLD - Still Supported)

If you prefer to specify exact distances (not recommended due to arithmetic errors):

```json
{
  "weeks": [
    {
      "week_number": 1,
      "phase": "base",
      "start_date": "2026-01-19",
      "end_date": "2026-01-25",
      "target_volume_km": 23.0,
      "workouts": [
        {
          "day_of_week": 1,
          "date": "2026-01-20",
          "workout_type": "easy",
          "distance_km": 4.0,
          "phase": "base",
          "pace_range_min_km": "6:30",
          "pace_range_max_km": "6:50",
          ...
        },
        ...
      ]
    }
  ]
}
```

**Validation**: System checks 4.0+4.5+4.0+10.5 = 23.0 ✓

**Caution**: Manual distance entry is error-prone. Use intent-based format instead.

---

## Date Alignment Rules

**Critical**: Training plans must align to Monday-Sunday weeks.

### Week Dates
- `start_date` MUST be Monday (weekday 0)
- `end_date` MUST be Sunday (weekday 6)

### Run Days (ISO Weekdays)
- `run_days`: [0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun]
- Example: `[1, 3, 5, 6]` = Tue, Thu, Sat, Sun

### Computing Next Monday

```bash
# Get current date and next Monday
python3 -c "from datetime import date, timedelta; today = date.today(); print(f'Today: {today} ({today.strftime(\"%A\")}'); next_mon = today + timedelta(days=(7-today.weekday())%7 or 7); print(f'Next Monday: {next_mon}')"
```

Example output:
```
Today: 2026-01-19 (Monday)
Next Monday: 2026-01-26
```

---

## Validation Before Populate

Always validate before populating to catch errors early:

```bash
poetry run sce plan validate-json --file /tmp/plan.json
```

### What It Checks

- ✓ JSON syntax valid
- ✓ Required fields present (`week_number`, `phase`, `start_date`, `end_date`, `target_volume_km`)
- ✓ Dates aligned correctly (Monday-Sunday)
- ✓ Valid enum values (phase, intensity_zone, etc.)
- ✓ If intent-based: `workout_pattern` has required fields
- ✓ If explicit format: Distances sum to target

### Example Output

```json
{
  "success": true,
  "message": "JSON is valid and ready to populate!",
  "data": {
    "warnings": [
      "Week 2: long_run_pct is 55% (>50% of weekly volume, consider 0.45-0.50)"
    ],
    "warnings_count": 1
  }
}
```

---

## Example: 4-Week Training Plan (Batch Generation)

⚠️ **Note**: This example shows batch generation for multiple weeks. The **recommended workflow** is 1-week-at-a-time planning (via training-plan-design and weekly-analysis skills). Use batch generation only for catch-up scenarios (e.g., returning from vacation, backfilling multiple weeks).

**Scenario**: 4-week base phase plan
- Week 1: 23km, 4 runs (3 easy + 1 long)
- Week 2: 26km, 4 runs (3 easy + 1 long)
- Week 3: 30km, 4 runs (3 easy + 1 long)
- Week 4: 21km, 3 runs (2 easy + 1 long), recovery week

### Complete JSON

```json
{
  "weeks": [
    {
      "week_number": 1,
      "phase": "base",
      "start_date": "2026-01-19",
      "end_date": "2026-01-25",
      "target_volume_km": 23.0,
      "target_systemic_load_au": 161.0,
      "is_recovery_week": false,
      "notes": "Base Phase Week 1 - Establishing routine",
      "workout_pattern": {
        "structure": "3 easy + 1 long",
        "run_days": [1, 3, 5, 6],
        "long_run_day": 6,
        "long_run_pct": 0.45,
        "easy_run_paces": "6:30-6:50",
        "long_run_pace": "6:30-6:50"
      }
    },
    {
      "week_number": 2,
      "phase": "base",
      "start_date": "2026-01-26",
      "end_date": "2026-02-01",
      "target_volume_km": 26.0,
      "target_systemic_load_au": 182.0,
      "is_recovery_week": false,
      "notes": "Base Phase Week 2 - Progressive volume",
      "workout_pattern": {
        "structure": "3 easy + 1 long",
        "run_days": [1, 3, 5, 6],
        "long_run_day": 6,
        "long_run_pct": 0.46,
        "easy_run_paces": "6:30-6:50",
        "long_run_pace": "6:30-6:50"
      }
    },
    {
      "week_number": 3,
      "phase": "base",
      "start_date": "2026-02-02",
      "end_date": "2026-02-08",
      "target_volume_km": 30.0,
      "target_systemic_load_au": 210.0,
      "is_recovery_week": false,
      "notes": "Base Phase Week 3 - Peak base volume",
      "workout_pattern": {
        "structure": "3 easy + 1 long",
        "run_days": [1, 3, 5, 6],
        "long_run_day": 6,
        "long_run_pct": 0.45,
        "easy_run_paces": "6:30-6:50",
        "long_run_pace": "6:30-6:50"
      }
    },
    {
      "week_number": 4,
      "phase": "recovery",
      "start_date": "2026-02-09",
      "end_date": "2026-02-15",
      "target_volume_km": 21.0,
      "target_systemic_load_au": 147.0,
      "is_recovery_week": true,
      "notes": "Recovery Week - Absorb adaptations",
      "workout_pattern": {
        "structure": "2 easy + 1 long",
        "run_days": [1, 3, 6],
        "long_run_day": 6,
        "long_run_pct": 0.52,
        "easy_run_paces": "6:30-6:50",
        "long_run_pace": "6:30-6:50"
      }
    }
  ]
}
```

### System-Generated Distances

System automatically calculates exact distances:

- **Week 1**: [4.0, 4.5, 4.0, 10.5] = 23.0km ✓
- **Week 2**: [4.5, 5.0, 4.5, 12.0] = 26.0km ✓
- **Week 3**: [5.5, 5.5, 5.5, 13.5] = 30.0km ✓
- **Week 4**: [5.0, 5.0, 11.0] = 21.0km ✓

**Zero arithmetic errors!**

---

## Workflow Pattern Fields Reference

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `structure` | string | Human-readable description (e.g., "3 easy + 1 long") |
| `run_days` | int[] | ISO weekdays for runs [1-7] |
| `long_run_day` | int | ISO weekday for long run |
| `long_run_pct` | float | Long run as % of weekly volume (0.40-0.55) |
| `easy_run_paces` | string | Pace range for easy runs (e.g., "6:30-6:50") |
| `long_run_pace` | string | Pace range for long run |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `tempo_pace` | string | Pace for tempo workouts (if applicable) |
| `interval_pace` | string | Pace for interval workouts (if applicable) |

### Long Run Percentage Guidelines

| Phase | Long Run % | Rationale |
|-------|-----------|-----------|
| Base | 40-45% | Building aerobic foundation, moderate long runs |
| Build | 45-50% | Progressive endurance, longer sustained efforts |
| Peak | 45-50% | Race-specific endurance, near-race distances |
| Recovery | 50-55% | Fewer runs, maintain long run but reduce total volume |

---

## Benefits of Intent-Based Format

### Before (Explicit Format)
```
❌ AI calculates: 5+6+6+11 = 28km (target 23km)
❌ Validation fails
❌ AI recalculates: 4+5+5+11 = 25km (target 23km)
❌ Validation fails again
❌ AI recalculates: 4+4+5+10 = 23km ✓
❌ 3 iterations, frustrating errors
```

### After (Intent-Based Format)
```
✓ AI specifies: target=23km, pattern="3 easy + 1 long", long_run_pct=0.45
✓ System calculates: [4.0, 4.5, 4.0, 10.5] = 23.0km ✓
✓ Validation passes first try
✓ 1 iteration, zero errors
```

### Key Improvements

| Aspect | Before | After |
|--------|--------|-------|
| **Arithmetic errors** | Common (AI makes mistakes) | **Zero** (system guarantees correctness) |
| **Iterations needed** | 3-5 attempts typical | **1 attempt** (always correct) |
| **AI focus** | Mechanical calculation | **High-level coaching** |
| **Error detection** | After full JSON creation | **Before calculation** (validated pattern) |
| **Maintainability** | Brittle, error-prone | **Robust, reliable** |

---

## Common Validation Errors

### Error: "start_date must be Monday"

```json
{
  "start_date": "2026-01-20"  // Tuesday ❌
}
```

**Fix**: Use Monday:
```json
{
  "start_date": "2026-01-19"  // Monday ✓
}
```

### Error: "workout_pattern missing 'run_days'"

```json
{
  "workout_pattern": {
    "long_run_day": 6,
    "long_run_pct": 0.45
    // Missing run_days ❌
  }
}
```

**Fix**: Add run_days:
```json
{
  "workout_pattern": {
    "run_days": [1, 3, 5, 6],  // ✓
    "long_run_day": 6,
    "long_run_pct": 0.45
  }
}
```

### Warning: "long_run_pct is 55% (>50%)"

```json
{
  "workout_pattern": {
    "long_run_pct": 0.55  // ⚠️ High
  }
}
```

**Fix**: Reduce percentage:
```json
{
  "workout_pattern": {
    "long_run_pct": 0.48  // ✓ More balanced
  }
}
```

---

## Best Practices

1. **Always validate before populate**
   ```bash
   poetry run sce plan validate-json --file /tmp/plan.json
   poetry run sce plan populate --from-json /tmp/plan.json
   ```

2. **Use intent-based format** for new plans
   - Let system handle arithmetic
   - Focus on coaching decisions

3. **Align weeks to Monday-Sunday**
   - Compute next Monday before creating JSON
   - Validates automatically

4. **Keep long run percentage reasonable**
   - Base/Build: 40-50%
   - Recovery: 50-55% (fewer total runs)
   - Peak: 45-50%

5. **Review generated distances**
   ```bash
   poetry run sce plan show
   ```
   - Verify individual workout distances make sense
   - Check that minimum durations are met

---

## Troubleshooting

### Issue: "Arithmetic error in workout generation"

**Cause**: Pattern configuration produces invalid distances (e.g., negative values)

**Solution**: Check `long_run_pct` isn't too high for the number of runs

### Issue: "Invalid run_day, must be 1-7"

**Cause**: Using 0-indexed weekdays instead of ISO weekdays

**Solution**: Use ISO weekdays: 1=Mon, 2=Tue, ..., 7=Sun

### Issue: Workouts seem too short

**Cause**: Volume target too low for number of runs, or long run percentage too high

**Solution**:
- Increase `target_volume_km`, or
- Reduce number of runs, or
- Lower `long_run_pct`

---

## Summary

**Intent-Based Format** eliminates arithmetic errors by:
1. **Separating concerns**: AI Coach → coaching decisions, System → calculations
2. **Guaranteeing correctness**: Arithmetic validated internally, assertions enforce sums
3. **CLI-first design**: Uses `sce plan validate-json` and `sce plan populate` commands
4. **Maintaining AI intelligence**: Coach still makes all high-level decisions

**Result**: Zero arithmetic errors, first-try success, reliable training plan generation.
