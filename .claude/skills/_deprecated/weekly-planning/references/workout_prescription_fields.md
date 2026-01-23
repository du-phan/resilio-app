# WorkoutPrescription Field Reference

Complete field reference for creating WorkoutPrescription objects with all 20+ required fields.

---

## Field Categories

1. **Identity** (4 fields): id, week_number, day_of_week, date
2. **Type & Phase** (2 fields): workout_type, phase
3. **Duration/Distance** (2 fields): duration_minutes, distance_km
4. **Intensity** (2 fields): intensity_zone, target_rpe
5. **Pace/HR Ranges** (4 fields): pace_range_min_km, pace_range_max_km, hr_range_low, hr_range_high
6. **Structure** (3 fields): intervals, warmup_minutes, cooldown_minutes
7. **Purpose & Metadata** (5 fields): purpose, notes, key_workout, status, execution

---

## 1. Identity Fields (Required)

| Field | Type | Format | Example |
|-------|------|--------|---------|
| `id` | string | `"w_YYYY-MM-DD_type_random"` | `"w_2026-01-20_easy_a1b2c3"` |
| `week_number` | int | 1-indexed | `1`, `12` |
| `day_of_week` | int | 0-6 (0=Mon, 6=Sun) | `0` (Mon), `6` (Sun) |
| `date` | string | `"YYYY-MM-DD"` | `"2026-01-20"` |

**Critical**: `day_of_week` MUST match `date`'s actual weekday. Use computational tools, never mental math.

---

## 2. Type & Phase Fields (Required)

### `workout_type` (string)

**Valid values**:
- `"easy"` - Conversational pace
- `"long_run"` - 25-30% weekly volume
- `"tempo"` - Threshold (T-pace), 20-40 min sustained
- `"intervals"` - VO2max (I-pace), 800m-1600m reps
- `"fartlek"` - Unstructured speed play
- `"strides"` - 6-8 × 100m
- `"race"` - Race effort
- `"rest"` - Complete rest

### `phase` (string)

**Valid values**: `"base"`, `"build"`, `"peak"`, `"taper"`

---

## 3. Duration/Distance Fields

| Field | Type | Range | Required | Notes |
|-------|------|-------|----------|-------|
| `duration_minutes` | int | >0 | ✓ | Includes warmup + main + cooldown |
| `distance_km` | float | ≥0 | Optional | Null for rest days or time-based workouts |

---

## 4. Intensity Fields (Required)

### `intensity_zone` (string)

| Zone | HR% Max | Common Usage |
|------|---------|--------------|
| `"zone_1"` | 50-65% | Recovery |
| `"zone_2"` | 65-75% | **Easy aerobic (most common)** |
| `"zone_3"` | 75-85% | Moderate |
| `"zone_4"` | 85-90% | Threshold (T-pace) |
| `"zone_5"` | 90-95% | VO2max (I-pace) |

**80/20 rule**: 80% zone_2, 20% zone_4/zone_5.

### `target_rpe` (int, 1-10 scale)

| RPE | Effort | Zone Mapping |
|-----|--------|--------------|
| 3-5 | Easy, conversational | zone_2 |
| 6-7 | Comfortably hard | zone_4 (tempo) |
| 8-9 | Very hard, near max | zone_5 (intervals) |

---

## 5. Pace/HR Range Fields (Optional)

| Field | Type | Format | Example | Notes |
|-------|------|--------|---------|-------|
| `pace_range_min_km` | string | `"M:SS"` | `"6:20"` | From VDOT tables |
| `pace_range_max_km` | string | `"M:SS"` | `"6:30"` | From VDOT tables |
| `hr_range_low` | int | 30-220 bpm | `129` | max_hr × zone_low_% |
| `hr_range_high` | int | 30-220 bpm | `149` | max_hr × zone_high_% |

**Omit if**: No VDOT (paces) or no max_hr (HR zones) available.

**Quick VDOT approximation** (if no tables):
- **Easy**: Race pace + 60-90 sec/km
- **Tempo**: Half marathon pace (or 10K + 30 sec/km)
- **Intervals**: 5K pace (or 10K - 15-30 sec/km)

---

## 6. Structure Fields

### `intervals` (list[dict] or null, optional)

**Null for**: Easy runs, continuous workouts, rest days.

**Examples**:

**Tempo**:
```json
[{"type": "tempo_block", "duration_minutes": 20, "pace": "5:45"}]
```

**Intervals**:
```json
[{"type": "800m", "reps": 6, "recovery": "400m jog", "pace": "4:15"}]
```

**Progressive long run**:
```json
[{"type": "progressive", "description": "Final 2 miles at M-pace", "pace": "6:00"}]
```

### `warmup_minutes` & `cooldown_minutes` (int, required)

| Field | Range | Default | Example |
|-------|-------|---------|---------|
| `warmup_minutes` | ≥0 | 10 | 15 (before quality sessions) |
| `cooldown_minutes` | ≥0 | 10 | 10 (after quality sessions) |

**Zero for**: Rest days only.

---

## 7. Purpose & Metadata Fields

### `purpose` (string, required)

**Content**: WHY this workout (training stimulus), 1-2 sentences.

**Examples**:
- `"Recovery and aerobic maintenance - build base without fatigue"`
- `"Improve lactate threshold - the pace you can sustain for ~60 minutes"`
- `"Boost VO2max - maximum aerobic capacity"`

### `notes` (string, optional)

**Content**: HOW to execute (specific cues, pacing instructions), 1-3 sentences.

**Examples**:
- `"Keep conversation-pace easy. Should feel fully recovered by end."`
- `"15 min warmup, 20 min @ T-pace (comfortably hard), 10 min cooldown."`

### `key_workout` (bool, required)

- **True**: Long runs, tempo, intervals, races (non-negotiable sessions)
- **False**: Easy runs, recovery runs, rest days

### `status` (string, required)

**Valid values**: `"scheduled"` (default), `"completed"`, `"skipped"`, `"adapted"`

**Always use**: `"scheduled"` for new prescriptions.

### `execution` (dict or null, optional)

**Always null** for new prescriptions. Filled post-workout from Strava/Garmin sync.

**Post-workout structure** (for reference):
```json
{
  "actual_distance_km": 8.2,
  "actual_duration_minutes": 47,
  "average_pace_km": "5:43",
  "average_hr": 174,
  "completed_at": "2026-01-29T18:30:00",
  "notes": "Felt strong"
}
```

---

## Complete Field Summary

| Field | Type | Required | Default | Example |
|-------|------|----------|---------|---------|
| `id` | string | ✓ | - | `"w_2026-01-20_easy_a1b2c3"` |
| `week_number` | int | ✓ | - | `1` |
| `day_of_week` | int | ✓ | - | `0` |
| `date` | string | ✓ | - | `"2026-01-20"` |
| `workout_type` | string | ✓ | - | `"tempo"` |
| `phase` | string | ✓ | - | `"build"` |
| `duration_minutes` | int | ✓ | - | `45` |
| `distance_km` | float | Optional | null | `8.0` |
| `intensity_zone` | string | ✓ | - | `"zone_4"` |
| `target_rpe` | int | ✓ | - | `7` |
| `pace_range_min_km` | string | Optional | null | `"5:40"` |
| `pace_range_max_km` | string | Optional | null | `"5:50"` |
| `hr_range_low` | int | Optional | null | `169` |
| `hr_range_high` | int | Optional | null | `179` |
| `intervals` | list[dict] | Optional | null | See examples above |
| `warmup_minutes` | int | ✓ | 10 | `15` |
| `cooldown_minutes` | int | ✓ | 10 | `10` |
| `purpose` | string | ✓ | - | `"Improve lactate threshold..."` |
| `notes` | string | Optional | null | `"15 min warmup..."` |
| `key_workout` | bool | ✓ | false | `true` |
| `status` | string | ✓ | "scheduled" | `"scheduled"` |
| `execution` | dict | Optional | null | `null` |

---

## Validation Rules

### Date Alignment
- `date` must match `day_of_week` (Mon=0, Sun=6)
- Week `start_date` must be Monday
- Week `end_date` must be Sunday
- Use `sce dates validate --date <date> --must-be monday`

### Volume Consistency
- Sum of workout distances ≈ week's `target_volume_km` (<5% acceptable, see common_pitfalls.md)
- Long run ≤30% of weekly volume
- Long run ≤150 min duration

### Intensity Consistency
- `intensity_zone` and `target_rpe` must align (zone_2→RPE 3-5, zone_4→RPE 6-7, zone_5→RPE 8-9)
- `pace_range_min_km` < `pace_range_max_km`
- `hr_range_low` < `hr_range_high`

### Field Dependencies
- If `intervals` provided → must have `warmup_minutes` and `cooldown_minutes`
- If `pace_range_*` provided → requires VDOT
- If `hr_range_*` provided → requires max_hr

---

## Generation Tips

### Use CLI Commands (Recommended)

```bash
# Generate week with workout_pattern (system calculates all fields)
sce plan generate-week --week 1 --phase base --target-volume 25

# Validate before saving
sce plan validate --file /tmp/weekly_plan_w1.json
```

**Benefits**: Automatic field population, date calculation, validation.

### Use Python Helpers

When creating JSON programmatically:

```python
from sports_coach_engine.core.plan import distribute_weekly_volume, create_workout
from sports_coach_engine.schemas.plan import WorkoutType

# Calculate distances that sum to target
workout_types = [WorkoutType.EASY, WorkoutType.EASY, WorkoutType.LONG_RUN]
distances = distribute_weekly_volume(25.0, workout_types, profile=None)

# Create complete workout objects
workout = create_workout(
    date="2026-01-20",
    workout_type=WorkoutType.EASY,
    distance_km=distances[0],
    phase="base",
    vdot=39,
    max_hr=199
)
# Returns: Complete WorkoutPrescription with all 20+ fields
```

### Manual JSON Creation

1. Start with COMPLETE_WORKOUT_EXAMPLE.json template
2. Update identity fields (id, week_number, day_of_week, date)
3. Set type/phase (workout_type, phase)
4. Calculate duration/distance
5. Set intensity (intensity_zone, target_rpe)
6. Calculate paces from VDOT (if available)
7. Calculate HR zones from max_hr (if available)
8. Set intervals (if structured) or null
9. Write purpose (WHY) and notes (HOW)
10. Set key_workout (true for quality, false for easy)
11. Leave status="scheduled", execution=null

---

## See Also

- **Complete example**: [COMPLETE_WORKOUT_EXAMPLE.json](COMPLETE_WORKOUT_EXAMPLE.json)
- **Generation guide**: [workout_generation.md](workout_generation.md)
- **Schema definition**: `sports_coach_engine/schemas/plan.py` lines 142-196
- **Generation function**: `sports_coach_engine/core/plan.py` lines 451-588 (`create_workout()`)
