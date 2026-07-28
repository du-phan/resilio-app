# Workout Generation Contract

Design every workout explicitly in the weekly JSON. `distance_km` remains the
total coaching volume; `structured_workout` is the deterministic device
prescription.

## Required workout fields

- `date` (`YYYY-MM-DD`)
- `start_time_local` (`HH:MM:SS`) for every device-published workout
- `sport` (`run` or `cycle`)
- `day_of_week` (`0` Monday through `6` Sunday)
- `workout_type`
- `distance_km` (warm-up + work + recovery + cool-down)
- `target_rpe`
- `warmup_km`
- `cooldown_km`

Use `pace_range`, `notes`, and `key_workout` for athlete-facing coaching. Use
`structured_workout` for machine-readable execution. Rest days must not have a
structured workout.

## Typed step tree

`structured_workout` contains `sport` and one or more steps:

- `steady`: one duration, optional target, intensity, cadence, and cue.
- `ramp`: one duration, start target, end target, intensity, cadence, and cue.
- `repeat`: `repetitions` plus nested `steps`.

Duration variants:

- `{"unit": "seconds", "value": 600}`
- `{"unit": "meters", "value": 1000}`
- `{"unit": "until_lap_press", "nominal_seconds": 600}`

Target variants:

- Pace: `seconds_per_kilometer`
- Heart rate: `beats_per_minute`, `percent_lthr`, or
  `percent_max_heart_rate`
- Power: `watts` or `percent_ftp`

Minimum and maximum are numeric and ordered. Do not put pace strings,
recoveries, or unit suffixes inside target values.

## Example quality workout

This 10 km session is 2.5 km warm-up, four repetitions of 1 km work and 400 m
recovery, then 1.9 km cool-down.

```json
{
  "date": "2026-02-12",
  "sport": "run",
  "day_of_week": 2,
  "workout_type": "intervals",
  "distance_km": 10.0,
  "target_rpe": 8,
  "pace_range": "4:45-4:55",
  "warmup_km": 2.5,
  "cooldown_km": 1.9,
  "structured_workout": {
    "sport": "run",
    "steps": [
      {
        "kind": "steady",
        "duration": {"unit": "meters", "value": 2500},
        "target": {
          "mode": "pace",
          "unit": "seconds_per_kilometer",
          "minimum": 360,
          "maximum": 390
        },
        "intensity": "warmup",
        "cue": "Finish with four relaxed strides"
      },
      {
        "kind": "repeat",
        "repetitions": 4,
        "steps": [
          {
            "kind": "steady",
            "duration": {"unit": "meters", "value": 1000},
            "target": {
              "mode": "pace",
              "unit": "seconds_per_kilometer",
              "minimum": 285,
              "maximum": 295
            },
            "intensity": "interval"
          },
          {
            "kind": "steady",
            "duration": {"unit": "meters", "value": 400},
            "target": {
              "mode": "pace",
              "unit": "seconds_per_kilometer",
              "minimum": 390,
              "maximum": 450
            },
            "intensity": "recovery"
          }
        ]
      },
      {
        "kind": "steady",
        "duration": {"unit": "meters", "value": 1900},
        "target": {
          "mode": "pace",
          "unit": "seconds_per_kilometer",
          "minimum": 370,
          "maximum": 420
        },
        "intensity": "cooldown"
      }
    ]
  },
  "key_workout": true,
  "notes": "Keep the first two repetitions controlled."
}
```

## Validation

- Sum all workout `distance_km` values exactly to `target_volume_km`.
- Confirm warm-up, work, recovery, and cool-down distances match the total.
- Apply Daniels quality limits to work distance only.
- Keep at least 80% of training time easy.
- Keep the long run within the configured guardrail.
- Ensure the workout and structured-workout sports match.
- Use a single target mode for Wahoo-bound workouts.
- Do not use `until_lap_press` for Wahoo until support is verified.
- Reject pace publishing without threshold pace or pace zones.
- Reject power publishing without FTP.

Cross-reference `workout_structure.md` for distance accounting and
`guardrails_weekly.md` for load limits.
