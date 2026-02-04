# Workout Generation (Intent-Based)

This skill uses **intent-based** weekly JSON. You do NOT manually build `WorkoutPrescription` objects.

## Key Rule
- Provide `workout_pattern` only.
- The system generates full `workouts` when you run:
  ```bash
  sce plan populate --from-json /tmp/weekly_plan_wX.json --validate
  ```

## Required Fields (Weekly JSON)
- `week_number`, `phase`, `start_date`, `end_date`, `target_volume_km`
- `workout_pattern` with `run_days`, `long_run_day`, `long_run_pct`

## Why this matters
- Avoids manual arithmetic
- Guarantees workouts sum to target volume
- Ensures consistent IDs, pacing, HR zones, and durations
