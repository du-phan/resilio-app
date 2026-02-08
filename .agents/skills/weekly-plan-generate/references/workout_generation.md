# Workout Generation — Explicit Specification

You design each workout explicitly in the `workouts` array. This leverages your coaching intelligence.

---

## Required Fields Per Workout

- `date` (YYYY-MM-DD)
- `day_of_week` (0=Monday, 6=Sunday)
- `workout_type` (easy | long_run | tempo | intervals | rest)
- `distance_km` (total session distance: WU + work + CD)
- `target_rpe` (1-10)
- `warmup_km` (WU distance in km, 0 for easy/long runs)
- `cooldown_km` (CD distance in km, 0 for easy/long runs)

---

## Optional But Recommended

- `pace_range` (e.g., "5:00-5:12" for T-pace)
- `intervals` (for tempo/intervals/reps — see `workout_structure.md`)
- `notes` (coaching cues, M-pace segments for long runs, strides, etc.)
- `key_workout` (true for week's critical sessions)

---

## Critical Volume Rule

**All `distance_km` values must sum exactly to `target_volume_km`.**

Verification: Before finalizing JSON, sum all `distance_km` → must equal `target_volume_km`.

---

## Workout Structure Convention

**See `references/workout_structure.md` for complete details.**

Key points:
- `distance_km` = total session distance (WU + work + CD)
- `warmup_km` / `cooldown_km` = explicit WU/CD distances (at E-pace)
- Work km = `distance_km - warmup_km - cooldown_km`
- Daniels limits (T≤10%, I≤8%, R≤5%) apply to work km only

---

## Example Weekly JSON

```json
{
  "week_number": 3,
  "phase": "build",
  "start_date": "2026-02-10",
  "end_date": "2026-02-16",
  "target_volume_km": 50.0,
  "workout_structure_hints": {
    "quality": {"max_sessions": 2, "types": ["tempo", "intervals"]},
    "long_run": {"emphasis": "steady", "pct_range": [25, 30]},
    "intensity_balance": {"low_intensity_pct": 0.82}
  },
  "workouts": [
    {
      "date": "2026-02-10",
      "day_of_week": 0,
      "workout_type": "easy",
      "distance_km": 8.0,
      "target_rpe": 4,
      "pace_range": "6:00-6:30",
      "warmup_km": 0.0,
      "cooldown_km": 0.0,
      "notes": "Recovery from weekend long run"
    },
    {
      "date": "2026-02-12",
      "day_of_week": 2,
      "workout_type": "tempo",
      "distance_km": 10.0,
      "target_rpe": 7,
      "pace_range": "5:00-5:12",
      "warmup_km": 2.5,
      "cooldown_km": 1.5,
      "intervals": [
        {
          "duration_minutes": 20,
          "pace": "5:00-5:12",
          "type": "threshold"
        }
      ],
      "key_workout": true,
      "notes": "Continuous 20min tempo. 2km E-pace transition before CD."
    },
    {
      "date": "2026-02-14",
      "day_of_week": 4,
      "workout_type": "easy",
      "distance_km": 7.0,
      "target_rpe": 4,
      "pace_range": "6:00-6:30",
      "warmup_km": 0.0,
      "cooldown_km": 0.0,
      "notes": "Easy aerobic run"
    },
    {
      "date": "2026-02-15",
      "day_of_week": 5,
      "workout_type": "intervals",
      "distance_km": 10.0,
      "target_rpe": 8,
      "pace_range": "4:45-4:55",
      "warmup_km": 2.5,
      "cooldown_km": 1.5,
      "intervals": [
        {
          "distance": "1000m",
          "reps": 5,
          "pace": "4:45-4:55",
          "recovery": "400m jog",
          "type": "vo2max"
        }
      ],
      "key_workout": true,
      "notes": "Include 4-6 strides in final 500m of WU"
    },
    {
      "date": "2026-02-16",
      "day_of_week": 6,
      "workout_type": "long_run",
      "distance_km": 15.0,
      "target_rpe": 5,
      "pace_range": "6:00-6:30",
      "warmup_km": 0.0,
      "cooldown_km": 0.0,
      "notes": "Pure aerobic endurance. 30% of weekly volume."
    }
  ]
}
```

**Volume verification**: 8.0 + 10.0 + 7.0 + 10.0 + 15.0 = 50.0 km ✓

---

**Cross-references**:
- Workout structure & distance accounting: `workout_structure.md`
- Guardrails (80/20, Daniels limits, long run cap): `guardrails_weekly.md`
- JSON workflow & approval: `json_workflow.md`
