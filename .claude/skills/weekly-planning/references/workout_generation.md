# Workout Generation and Volume Distribution

This reference provides detailed guidance for generating complete workout prescriptions and using volume distribution helpers.

---

## Step 5b: Generate Workout Prescriptions (CRITICAL)

**IMPORTANT**: The markdown plan is for humans. The YAML needs actual `WorkoutPrescription` objects with all 20+ fields populated.

**DO NOT skip this step!** Without populated workouts, the YAML is useless and CLI tools (`sce today`, `sce week`) will fail.

### Use the Workout Generator Script (Recommended)

```bash
# Option 1: Generate complete plan from outline JSON
python .claude/skills/training-plan-design/scripts/generate_workouts.py plan \
  --plan-outline /tmp/plan_outline.json \
  --vdot 39 \
  --max-hr 199 \
  --output /tmp/complete_plan.json

# Option 2: Generate single week
python .claude/skills/training-plan-design/scripts/generate_workouts.py week \
  --week-file /tmp/week1_outline.json \
  --vdot 39 \
  --max-hr 199 \
  --output /tmp/week1_complete.json

# Option 3: Validate existing plan/week structure
python .claude/skills/training-plan-design/scripts/generate_workouts.py validate \
  --file /tmp/plan.json \
  --type plan
```

### Required Fields for Each Workout

Each workout needs **20+ fields total**:

- **Identity**: `id`, `week_number`, `day_of_week` (0=Mon, 6=Sun), `date` (ISO format)
- **Type**: `workout_type` (easy|long_run|tempo|intervals|rest), `phase`
- **Duration**: `duration_minutes`, `distance_km` (optional)
- **Intensity**: `intensity_zone` (zone_2|zone_4|zone_5), `target_rpe` (1-10)
- **Pacing**: `pace_range_min_km`, `pace_range_max_km` (from VDOT tables, e.g., "5:30")
- **HR**: `hr_range_low`, `hr_range_high` (from %HRmax)
- **Structure**: `intervals` (null or structure), `warmup_minutes`, `cooldown_minutes`
- **Purpose**: `purpose` (training stimulus), `notes` (execution cues)
- **Metadata**: `key_workout` (bool), `status` ("scheduled"), `execution` (null initially)

**Full field reference**: See [workout_prescription_fields.md](workout_prescription_fields.md)

**Complete example**: See [COMPLETE_WORKOUT_EXAMPLE.json](COMPLETE_WORKOUT_EXAMPLE.json)

### Week Outline JSON Structure

Input format for `generate_workouts.py`:

```json
{
  "week_number": 1,
  "phase": "base",
  "start_date": "2026-01-19",
  "end_date": "2026-01-25",
  "target_volume_km": 22.0,
  "workout_schedule": [
    {"day": "monday", "type": "easy", "purpose": "Recovery"},
    {"day": "wednesday", "type": "easy", "purpose": "Base building"},
    {"day": "friday", "type": "easy", "purpose": "Pre-long run"},
    {"day": "sunday", "type": "long_run", "purpose": "Endurance foundation"}
  ]
}
```

### Validation Checklist

The script checks automatically:

- ✓ `start_date` is Monday (weekday 0)
- ✓ `end_date` is Sunday (weekday 6)
- ✓ All workouts have required fields
- ✓ Total workout volume ≈ target volume (±5%)
- ✓ Pace ranges match VDOT
- ✓ HR zones within 50-100% max_hr
- ✓ No back-to-back hard days
- ✓ Long run ≤30% weekly volume, ≤2.5h duration
- ✓ Quality volume within Daniels limits (T≤10%, I≤8%, R≤5%)

**IF VALIDATION FAILS**: Review error messages, adjust workouts, and regenerate. DO NOT save plans with validation errors!

---

## Step 5c: Use Volume Distribution Helper (RECOMMENDED)

**Problem**: Fixed percentage allocations (28% long run, 15% easy) don't account for number of workouts, causing volume mismatches.

**Solution**: Use `distribute_weekly_volume()` toolkit function to calculate distances that sum to target.

### Python Helper Code

Use this when designing workouts:

```python
import sys
sys.path.insert(0, '/Users/duphan/Projects/sports-coach-engine')

from sports_coach_engine.core.plan import distribute_weekly_volume, suggest_long_run_progression
from sports_coach_engine.schemas.plan import WorkoutType, PlanPhase

# Example: Week 1 with 25km target
workout_types = [WorkoutType.LONG_RUN, WorkoutType.EASY, WorkoutType.EASY, WorkoutType.EASY]
allocation = distribute_weekly_volume(
    weekly_volume_km=25.0,
    workout_types=workout_types,
    profile=None  # Or pass profile dict with typical_easy_distance_km, etc.
)

# Result: {0: 7.0, 1: 6.0, 2: 6.0, 3: 6.0} → sums to 25km!
# Use these distances when building workout_schedule
```

### Long Run Progression Helper

Consult athlete's historical capacity:

```python
# Get athlete's recent long run distance
# Example: recent activities show 8km long runs

suggestion = suggest_long_run_progression(
    current_long_run_km=8.0,
    weeks_to_peak=10,
    target_peak_long_run_km=22.0,
    phase=PlanPhase.BASE
)

# Returns: {"suggested_distance_km": 9.0, "rationale": "...", "min_safe_km": 7.2, "max_safe_km": 9.2}
# Use this as REFERENCE - adjust based on athlete context
```

### ⚠️ CRITICAL: Respect Minimum Workout Durations

When using `distribute_weekly_volume()`:

- **Always pass the `profile` parameter** with athlete's typical patterns (from `sce profile get`)
- Verify allocated distances meet minimums (especially easy runs)
- Generic minimums: Easy runs ≥5km, Long runs ≥8km
- Profile-aware minimums: 80% of athlete's typical (e.g., if typical easy run is 7km, minimum is 5.6km)

**If target volume is low**, consider:

- **Reducing run frequency** (3 runs instead of 4) to maintain longer individual runs
- **Increasing target volume** if athlete's CTL and ACWR allow
- **Accepting shorter runs with clear justification** (e.g., injury recovery, specific taper phase)

### Common Mistake

**Problem**: 22km target with 4 runs (3 easy + 1 long) creates 3.7km easy runs - too short for most athletes!

**Better approach**: 22km with 3 runs (2 easy + 1 long) creates 6.5km easy runs - more realistic.

### Auto-Compute Patterns

Run `poetry run sce profile analyze` to automatically compute athlete's typical workout patterns from recent history (last 60 days).

### Key Principle

Tools SUGGEST, you DECIDE based on:

- Athlete's recent activity patterns (`sce activity list --since 30d`)
- Injury history and constraints (`sce memory list --type INJURY_HISTORY`)
- Multi-sport schedule conflicts
- Recovery state (TSB, readiness)
