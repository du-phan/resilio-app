# JSON Workout Pattern Format

## Quick Start

```bash
# 1. Create plan skeleton (auto-persists to data/plans/current_plan.yaml)
poetry run sce plan create-macro --goal-type half_marathon --race-date 2026-06-01 \
  --start-date 2026-01-20 --total-weeks 16 --starting-volume-km 25 --peak-volume-km 55

# 2. Create week 1 JSON with workout_pattern
# (AI coach creates this manually using intent-based format below)

# 3. Validate JSON before presenting to athlete
poetry run sce plan validate --file /tmp/weekly_plan_w1.json

# 4. Populate week 1 into skeleton (after athlete approval)
poetry run sce plan populate --from-json /tmp/weekly_plan_w1.json

# 5. Verify
poetry run sce plan show
```

---

## Intent-Based Format (RECOMMENDED)

**Philosophy**: AI Coach specifies coaching intent (volume targets, workout structure), system handles arithmetic.

### Basic Structure

```json
{
  "weeks": [{
    "week_number": 1,
    "phase": "base",
    "start_date": "2026-01-20",
    "end_date": "2026-01-26",
    "target_volume_km": 23.0,
    "is_recovery_week": false,
    "notes": "Base Phase Week 1 - Establishing routine",
    "workout_pattern": {
      "structure": "3 easy + 1 long",
      "run_days": [1, 3, 6],
      "long_run_day": 6,
      "long_run_pct": 0.45,
      "quality_sessions": [],
      "easy_run_paces": "6:30-6:50",
      "long_run_pace": "6:30-6:50"
    }
  }]
}
```

### Field Explanations

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `week_number` | int | Week number (1-indexed) | `1` |
| `phase` | string | Training phase | `"base"`, `"build"`, `"peak"`, `"taper"` |
| `start_date` | string | Week start (MUST be Monday) | `"2026-01-20"` |
| `end_date` | string | Week end (MUST be Sunday) | `"2026-01-26"` |
| `target_volume_km` | float | Target weekly volume | `23.0` |
| `is_recovery_week` | bool | Is this a recovery week? | `false` |
| `notes` | string | Week-level notes | `"Base Phase Week 1"` |
| `workout_pattern` | object | Workout structure (see below) | See below |

### workout_pattern Object

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `structure` | string | Human-readable structure | `"3 easy + 1 long"` |
| `run_days` | array[int] | Days to run (ISO weekdays: 0=Mon, 6=Sun) | `[1, 3, 6]` = Tue, Thu, Sun |
| `long_run_day` | int | Which day is the long run | `6` (Sunday) |
| `long_run_pct` | float | Long run as % of weekly volume | `0.45` (45%) |
| `quality_sessions` | array | Quality workouts (tempo/intervals) | `[]` (base phase) or see below |
| `easy_run_paces` | string | Easy pace range (min/km) | `"6:30-6:50"` |
| `long_run_pace` | string | Long run pace range | `"6:30-6:50"` |

### Quality Sessions Format

For build/peak phases with tempo or interval workouts:

```json
"quality_sessions": [
  {
    "day": 2,
    "workout_type": "tempo",
    "volume_km": 6.0,
    "pace_range": "5:45-5:55",
    "structure": "10min WU + 4km tempo + 10min CD"
  }
]
```

**Quality session types**:
- `"tempo"`: Lactate threshold pace work
- `"intervals"`: VO2max intervals
- `"fartlek"`: Unstructured speed play

### How System Calculates Distances

**Example**: 23km target, 3 runs (run_days=[1,3,6]), 45% long run

1. **Long run**: 23 × 0.45 = 10.35 → **10.5km** (rounded to 0.5km)
2. **Remaining**: 23 - 10.5 = **12.5km** for easy runs
3. **Per easy run**: 12.5 ÷ 2 = 6.25km
4. **Distributed**: [**6.0km**, **6.5km**, **10.5km**]
5. **Validation**: 6.0 + 6.5 + 10.5 = **23.0km** ✓

**Result**: Zero arithmetic errors, guaranteed sum.

---

## AI Coach Decisions vs System Calculations

### AI Coach Decides (High-Level Intent)

Based on training methodology, athlete context, and guardrails:

- **target_volume_km**: Based on CTL, progression, capacity
- **structure**: Based on phase, run frequency (e.g., "3 easy + 1 long")
- **run_days**: Based on athlete schedule constraints
- **long_run_pct**: Base=0.40-0.45, Build/Peak=0.45-0.50, Recovery=0.50-0.55
- **paces**: Based on VDOT, athlete fitness

### System Calculates (Low-Level Mechanics)

System handles all arithmetic and object creation:

- Exact workout distances summing to target
- WorkoutPrescription objects with required fields
- Date calculations from week start + day of week
- HR zones based on workout type + athlete max HR
- Duration estimates from distance + pace
- Workout IDs, status, metadata

---

## Progressive Disclosure Workflow

### 1. Initial Plan Design (Week 1 Only)

```bash
# Step 1: Create skeleton (16 weeks, NO workout_pattern)
sce plan create-macro ...
# Creates: data/plans/current_plan.yaml with stub weeks

# Step 2: AI coach creates week 1 JSON (WITH workout_pattern)
# Saved to: /tmp/weekly_plan_w1.json

# Step 3: Validate week 1
sce plan validate --file /tmp/weekly_plan_w1.json

# Step 4: Populate week 1 into skeleton (after approval)
sce plan populate --from-json /tmp/weekly_plan_w1.json
```

**Result**: Plan skeleton with 16 stub weeks, week 1 has workouts, weeks 2-16 are empty.

### 2. Weekly Generation (Weeks 2-16)

Each week after completing previous week:

```bash
# Analyze completed week
sce week  # Review adherence, metrics

# AI coach creates next week JSON (e.g., week 2)
# Based on week 1 response, current CTL/ACWR, readiness

# Validate
sce plan validate --file /tmp/weekly_plan_w2.json

# Populate (merges into existing plan)
sce plan populate --from-json /tmp/weekly_plan_w2.json
```

**Key point**: `populate` merges weeks. Existing weeks are preserved, new weeks are added/updated.

---

## Date Alignment Rules

**CRITICAL**: Training plans MUST align to Monday-Sunday weeks.

### Week Dates

- `start_date` MUST be Monday (weekday() == 0)
- `end_date` MUST be Sunday (weekday() == 6)

**Validation**:
```bash
poetry run sce dates validate --date 2026-01-20 --must-be monday
# Returns: {"valid": true, "day_name": "Monday"}
```

### Run Days (ISO Weekdays)

**Python weekday() convention**:
- 0 = Monday
- 1 = Tuesday
- 2 = Wednesday
- 3 = Thursday
- 4 = Friday
- 5 = Saturday
- 6 = Sunday

**Examples**:
- `run_days: [1, 3, 6]` = Tuesday, Thursday, Sunday
- `run_days: [0, 2, 4, 6]` = Monday, Wednesday, Friday, Sunday

### Computing Dates

```bash
# Get today and next Monday
poetry run sce dates today
poetry run sce dates next-monday

# Get week boundaries
poetry run sce dates week-boundaries --start 2026-01-20
# Returns: {"start": "2026-01-20", "end": "2026-01-26"}
```

---

## Validation Rules

`sce plan validate --file <json>` checks:

1. **Volume discrepancy**: Sum of workout distances vs target_volume_km
   - <5%: Acceptable
   - 5-10%: Warning
   - >10%: Error

2. **Minimum durations**:
   - Easy runs: ≥5km (or 80% of athlete's typical_easy_distance_km)
   - Long runs: ≥8km (or 80% of athlete's typical_long_run_distance_km)

3. **Quality volume limits** (for build/peak phases):
   - Tempo: ≤10% of weekly volume
   - Intervals: ≤8% of weekly volume
   - Repetition: ≤5% of weekly volume

4. **Date alignment**:
   - start_date is Monday
   - end_date is Sunday
   - run_days are valid (0-6)

5. **Required fields**: All workout_pattern fields present

---

## Common Mistakes

### ❌ Wrong: Manual Arithmetic

```json
{
  "target_volume_km": 23.0,
  "workout_pattern": {
    "run_days": [1, 3, 6],
    "long_run_pct": 0.45,
    ...
  }
}
// AI manually calculates: 23 * 0.45 = 10.35, rounds to 10.5
// Remaining: 23 - 10.5 = 12.5, split: 6.25 each → 6.0 and 6.5
// Creates explicit workout distances
```

**Problem**: Prone to rounding errors, doesn't sum to 23.0 exactly.

### ✅ Right: Let System Calculate

```json
{
  "target_volume_km": 23.0,
  "workout_pattern": {
    "run_days": [1, 3, 6],
    "long_run_pct": 0.45,
    ...
  }
}
// System calculates distances automatically
// Guarantees sum = 23.0 exactly
```

### ❌ Wrong: Generating Weeks 2-16 Upfront

```json
{
  "weeks": [
    {"week_number": 1, "workout_pattern": {...}},
    {"week_number": 2, "workout_pattern": {...}},
    ...
    {"week_number": 16, "workout_pattern": {...}}
  ]
}
```

**Problem**: Violates progressive disclosure, creates rigid plan that can't adapt.

### ✅ Right: Generate Week 1 Only

```json
{
  "weeks": [
    {"week_number": 1, "workout_pattern": {...}}
  ]
}
// Weeks 2-16 remain as stub weeks in skeleton
// Generated weekly via weekly-analysis skill
```

### ❌ Wrong: Using MAX_RUN_DAYS Without Validation

```python
# AI coach logic
run_days = list(range(MAX_RUN_DAYS))  # e.g., [0,1,2,3] for 4 runs
```

**Problem**: At low volumes (e.g., 20km / 4 runs = 5km average), violates 5km easy minimum.

### ✅ Right: Use suggest-run-count

```bash
poetry run sce plan suggest-run-count --volume 20 --max-runs 4 --phase base
# Returns: recommended_runs=3 (warns 4 runs would create sub-5km runs)
```

---

## Architecture Notes

**ONE file system** (as of 2026-01-21):

- `create-macro` creates MasterPlan skeleton with stub weeks
- Stub weeks contain: week_number, phase, dates, target_volume_km, is_recovery_week, workouts=[]
- AI coach creates JSON with workout_pattern for specific weeks
- `populate` merges those weeks into the skeleton
- Single file: `data/plans/current_plan.yaml`

**Philosophy**: Package provides tools (distance calculation, validation), AI coach provides intelligence (workout structure, paces, progression).
