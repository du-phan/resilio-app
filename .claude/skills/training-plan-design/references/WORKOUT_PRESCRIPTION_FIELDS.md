# WorkoutPrescription Field Reference

Complete field-by-field guide for creating WorkoutPrescription objects.

## Overview

A `WorkoutPrescription` object contains **20+ fields** across 7 categories:
1. Identity (4 fields)
2. Type & Phase (2 fields)
3. Duration/Distance (2 fields)
4. Intensity Guidance (2 fields)
5. Pace/HR Ranges (4 fields)
6. Structure (3 fields)
7. Purpose & Metadata (5 fields)

**All fields except those marked "Optional" are REQUIRED.**

---

## 1. Identity Fields

### `id` (string, required)
**Type**: Unique workout identifier
**Format**: `"w_YYYY-MM-DD_type_random"`
**Example**: `"w_2026-01-20_easy_a1b2c3"`
**Generation**: `f"w_{date.isoformat()}_{workout_type}_{uuid.uuid4().hex[:6]}"`

### `week_number` (int, required)
**Type**: Week number in plan (1-indexed)
**Range**: ≥ 1
**Example**: `1` (first week), `12` (week 12)
**Purpose**: Used for plan navigation and progress tracking

### `day_of_week` (int, required)
**Type**: Day of week (ISO weekday)
**Range**: 0-6 (0 = Monday, 6 = Sunday)
**Example**: `0` (Monday), `2` (Wednesday), `6` (Sunday)
**CRITICAL**: Must align with date's actual weekday

### `date` (string, required)
**Type**: Workout date in ISO format
**Format**: `"YYYY-MM-DD"`
**Example**: `"2026-01-20"`
**Validation**: Must be valid date, must match `day_of_week`

---

## 2. Type & Phase Fields

### `workout_type` (string, required)
**Type**: Workout classification
**Valid values**:
- `"easy"` - Easy aerobic run (conversational pace)
- `"long_run"` - Long endurance run (25-30% weekly volume)
- `"tempo"` - Threshold run (T-pace, 20-40 min sustained)
- `"intervals"` - VO2max intervals (I-pace, 800m-1600m reps)
- `"fartlek"` - Unstructured speed play
- `"strides"` - Neuromuscular training (6-8 × 100m)
- `"race"` - Race effort
- `"rest"` - Complete rest day

**Example**: `"tempo"`

### `phase` (string, required)
**Type**: Periodization phase
**Valid values**:
- `"base"` - Base building (aerobic foundation)
- `"build"` - Build phase (race-specific intensity)
- `"peak"` - Peak phase (maximum load)
- `"taper"` - Taper phase (recovery, maintain sharpness)

**Example**: `"build"`

---

## 3. Duration/Distance Fields

### `duration_minutes` (int, required)
**Type**: Target workout duration in minutes
**Range**: > 0 (typically 30-150 minutes)
**Example**: `45` (45-minute tempo run)
**Note**: Includes warmup + main set + cooldown

### `distance_km` (float, optional)
**Type**: Target distance in kilometers
**Range**: ≥ 0 (if provided)
**Example**: `8.0` (8 km)
**When to include**: For distance-based workouts (easy, long_run, tempo, intervals)
**When to omit**: For rest days or time-based workouts
**Note**: May be `null` for time-based workouts

---

## 4. Intensity Guidance Fields

### `intensity_zone` (string, required)
**Type**: Training intensity zone (Daniels system)
**Valid values**:
- `"zone_1"` - Recovery (50-65% max HR)
- `"zone_2"` - Easy aerobic (65-75% max HR) - **Most common**
- `"zone_3"` - Moderate (75-85% max HR)
- `"zone_4"` - Threshold (85-90% max HR) - Tempo pace
- `"zone_5"` - VO2max (90-95% max HR) - Interval pace

**Example**: `"zone_4"` (tempo run)
**80/20 rule**: 80% of runs should be zone_2, 20% should be zone_4/zone_5

### `target_rpe` (int, required)
**Type**: Target Rate of Perceived Exertion (1-10 scale)
**Range**: 1-10
**Examples**:
- `4` - Easy (conversational pace, can speak full sentences)
- `5` - Moderate (can speak phrases, not full sentences)
- `7` - Hard (can speak few words, "comfortably hard")
- `8-9` - Very hard (can barely speak, near max effort)

**Mapping to zones**:
- Zone 2 → RPE 3-5 (easy)
- Zone 4 → RPE 6-7 (tempo)
- Zone 5 → RPE 8-9 (intervals)

---

## 5. Pace/HR Range Fields

### `pace_range_min_km` (string, optional)
**Type**: Minimum pace per kilometer (slowest acceptable pace)
**Format**: `"M:SS"` (e.g., `"5:30"` = 5 minutes 30 seconds per km)
**Example**: `"6:20"` (easy run lower bound)
**Calculation**: From VDOT tables based on intensity zone
**Optional**: Omit if athlete doesn't have VDOT or for rest days

### `pace_range_max_km` (string, optional)
**Type**: Maximum pace per kilometer (fastest acceptable pace)
**Format**: `"M:SS"`
**Example**: `"6:30"` (easy run upper bound)
**Calculation**: From VDOT tables + small buffer (±5-10 sec)
**Range size**: Typically 10-30 sec/km range

### `hr_range_low` (int, optional)
**Type**: Lower heart rate bound in beats per minute
**Range**: 30-220 bpm (if provided)
**Example**: `129` (65% of max HR 199)
**Calculation**: `max_hr × zone_low_percentage`
**Optional**: Omit if max_hr not available

### `hr_range_high` (int, optional)
**Type**: Upper heart rate bound in beats per minute
**Range**: 30-220 bpm (if provided)
**Example**: `149` (75% of max HR 199)
**Calculation**: `max_hr × zone_high_percentage`
**Note**: Should be higher than `hr_range_low`

---

## 6. Structure Fields

### `intervals` (list[dict] or null, optional)
**Type**: Interval structure for structured workouts
**Format**: Array of interval definitions OR `null` for continuous workouts
**Examples**:

**Tempo run**:
```json
[
  {
    "type": "tempo_block",
    "duration_minutes": 20,
    "pace": "5:45",
    "description": "Steady threshold effort"
  }
]
```

**Intervals**:
```json
[
  {
    "type": "800m",
    "reps": 6,
    "recovery": "400m jog",
    "pace": "4:15"
  }
]
```

**Long run with progression**:
```json
[
  {
    "type": "progressive",
    "description": "Final 2 miles at M-pace (6:00/km)",
    "pace": "6:00"
  }
]
```

**When to use**: Tempo, intervals, structured long runs
**When null**: Easy runs, continuous workouts, rest days

### `warmup_minutes` (int, required)
**Type**: Warmup duration in minutes
**Range**: ≥ 0 (typically 10-15 minutes)
**Example**: `15` (15-minute warmup before tempo)
**Default**: `10` for most workouts
**Zero for**: Rest days

### `cooldown_minutes` (int, required)
**Type**: Cooldown duration in minutes
**Range**: ≥ 0 (typically 10-15 minutes)
**Example**: `10` (10-minute cooldown after tempo)
**Default**: `10` for most workouts
**Zero for**: Rest days

---

## 7. Purpose & Metadata Fields

### `purpose` (string, required)
**Type**: Training stimulus and workout rationale
**Length**: 1-2 sentences explaining "why"
**Examples**:
- `"Recovery and aerobic maintenance - build base without fatigue"`
- `"Build aerobic endurance and mental toughness for race distance"`
- `"Improve lactate threshold - the pace you can sustain for ~60 minutes"`
- `"Boost VO2max - maximum aerobic capacity"`

**Content focus**: WHY this workout, not what to do (that's in notes)

### `notes` (string, optional)
**Type**: Execution cues and specific instructions
**Length**: 1-3 sentences with actionable guidance
**Examples**:
- `"Keep conversation-pace easy. Should feel fully recovered by end."`
- `"15 min warmup, 20 min @ T-pace (comfortably hard), 10 min cooldown."`
- `"Final 2 miles at M-pace (6:00/km). This teaches running goal pace on tired legs."`

**Content focus**: HOW to execute, specific cues, pacing instructions
**Optional**: Can be `null` if purpose is sufficient

### `key_workout` (bool, required)
**Type**: Whether this is a key session for the week
**Values**: `true` or `false`
**True for**: Long runs, tempo runs, interval sessions, races
**False for**: Easy runs, recovery runs, rest days
**Purpose**: Helps athletes prioritize which workouts are non-negotiable

### `status` (string, required)
**Type**: Workout completion status
**Valid values**:
- `"scheduled"` - Not yet completed (default for all new workouts)
- `"completed"` - Successfully completed
- `"skipped"` - Intentionally skipped
- `"adapted"` - Modified from original prescription

**Default**: Always `"scheduled"` for new prescriptions

### `execution` (dict or null, optional)
**Type**: Actual execution data (filled post-workout)
**Default**: Always `null` for new prescriptions
**Filled after**: Athlete completes workout and syncs from Strava/Garmin
**Structure** (example after completion):
```json
{
  "actual_distance_km": 8.2,
  "actual_duration_minutes": 47,
  "average_pace_km": "5:43",
  "average_hr": 174,
  "completed_at": "2026-01-29T18:30:00",
  "notes": "Felt strong, could have held pace longer"
}
```

---

## Field Summary Table

| Field | Type | Required | Default | Example |
|-------|------|----------|---------|---------|
| `id` | string | ✓ | - | `"w_2026-01-20_easy_a1b2c3"` |
| `week_number` | int | ✓ | - | `1` |
| `day_of_week` | int | ✓ | - | `0` (Monday) |
| `date` | string | ✓ | - | `"2026-01-20"` |
| `workout_type` | string | ✓ | - | `"tempo"` |
| `phase` | string | ✓ | - | `"build"` |
| `duration_minutes` | int | ✓ | - | `45` |
| `distance_km` | float | Optional | `null` | `8.0` |
| `intensity_zone` | string | ✓ | - | `"zone_4"` |
| `target_rpe` | int | ✓ | - | `7` |
| `pace_range_min_km` | string | Optional | `null` | `"5:40"` |
| `pace_range_max_km` | string | Optional | `null` | `"5:50"` |
| `hr_range_low` | int | Optional | `null` | `169` |
| `hr_range_high` | int | Optional | `null` | `179` |
| `intervals` | list[dict] | Optional | `null` | `[{"type": "tempo_block", ...}]` |
| `warmup_minutes` | int | ✓ | `10` | `15` |
| `cooldown_minutes` | int | ✓ | `10` | `10` |
| `purpose` | string | ✓ | - | `"Improve lactate threshold..."` |
| `notes` | string | Optional | `null` | `"15 min warmup, 20 min @ T-pace..."` |
| `key_workout` | bool | ✓ | `false` | `true` |
| `status` | string | ✓ | `"scheduled"` | `"scheduled"` |
| `execution` | dict | Optional | `null` | `null` (filled post-workout) |

---

## Validation Rules

### Date Alignment
- `date` must match `day_of_week` (Monday = 0, Sunday = 6)
- Week's `start_date` must be Monday (weekday 0)
- Week's `end_date` must be Sunday (weekday 6)

### Volume Consistency
- Sum of workout `distance_km` ≈ week's `target_volume_km` (within 10%)
- Long run ≤ 30% of weekly volume
- Long run ≤ 150 minutes duration

### Intensity Consistency
- `intensity_zone` and `target_rpe` should align:
  - zone_2 → RPE 3-5
  - zone_4 → RPE 6-7
  - zone_5 → RPE 8-9
- `pace_range_min_km` < `pace_range_max_km`
- `hr_range_low` < `hr_range_high`

### Field Dependencies
- If `intervals` provided → must have `warmup_minutes` and `cooldown_minutes`
- If `pace_range_*` provided → requires VDOT
- If `hr_range_*` provided → requires max_hr

---

## Generation Tips

### Use Existing Functions
The `sports_coach_engine.core.plan.create_workout()` function handles most field generation automatically:
- Calculates `duration_minutes` and `distance_km` from weekly volume
- Looks up `intensity_zone` and `target_rpe` from WORKOUT_DEFAULTS
- Calculates pace/HR ranges from VDOT and max_hr
- Assigns appropriate `intervals`, `warmup_minutes`, `cooldown_minutes`
- Generates `purpose` text with phase context

### Manual JSON Creation
When creating JSON manually:
1. Start with COMPLETE_WORKOUT_EXAMPLE.json as template
2. Copy workout object, update identity fields (id, week_number, day_of_week, date)
3. Update type/phase (workout_type, phase)
4. Calculate or estimate duration/distance
5. Set intensity (intensity_zone, target_rpe)
6. Calculate paces from VDOT tables (if available)
7. Calculate HR zones from max_hr (if available)
8. Set intervals (if structured workout) or null
9. Write purpose (training stimulus) and notes (execution cues)
10. Set key_workout (true for quality, false for easy)
11. Leave status="scheduled" and execution=null

### Quick Reference for VDOT Paces
For athletes without VDOT tables:
- **Easy (zone_2)**: Add 60-90 sec/km to race pace
- **Marathon (zone_3)**: Race pace + 15-30 sec/km
- **Tempo (zone_4)**: Half marathon race pace (or 10K + 30 sec/km)
- **Intervals (zone_5)**: 5K race pace (or 10K - 15-30 sec/km)

---

## See Also

- **Complete example**: [COMPLETE_WORKOUT_EXAMPLE.json](COMPLETE_WORKOUT_EXAMPLE.json) - 2-week plan with all fields populated
- **Schema definition**: `sports_coach_engine/schemas/plan.py` lines 142-196
- **Generation function**: `sports_coach_engine/core/plan.py` lines 451-588 (`create_workout()`)
- **Test examples**: `tests/unit/test_plan.py` lines 84-120
