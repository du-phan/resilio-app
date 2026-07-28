# Workout Structure and Distance Accounting

## Core convention

`distance_km` is the total session distance:

```text
warm-up + work + recoveries + transitions + cool-down = distance_km
```

Weekly `target_volume_km` is the sum of each workout's `distance_km`.
Daniels quality limits apply only to quality work, not to the complete
session.

| Workout | Typical warm-up | Typical cool-down |
|---|---:|---:|
| Easy | 0 km | 0 km |
| Tempo | 1.5–2.5 km | 1.0–2.0 km |
| VO2max intervals | 2.0–3.0 km | 1.5–2.0 km |
| Repetitions | 2.0–3.0 km | 1.5 km |
| Long run | 0–1.0 km | 0 km |

## Typed structure rules

Use `structured_workout` when a workout should be publishable. The nested
`sport` must match the workout's required top-level `sport`.

Use:

- `steady` for warm-ups, cool-downs, work, recoveries, and active running.
- `ramp` for progressive targets over one duration.
- `repeat` for repeated groups of nested steps.

Every fixed step duration uses seconds or metres. A lap-button step uses
`until_lap_press` plus `nominal_seconds` so local load remains calculable.
Every target has a mode, an explicit unit, and numeric minimum/maximum.

For pace, convert `MM:SS/km` to seconds per kilometre. For example,
`5:00–5:12/km` becomes `300–312 seconds_per_kilometer`.

## Worked tempo example

The structure below accounts for all 8 km: 2 km warm-up, 3 km threshold,
1.5 km active easy running, and 1.5 km cool-down.

```json
{
  "date": "2026-02-12",
  "sport": "run",
  "day_of_week": 2,
  "workout_type": "tempo",
  "distance_km": 8.0,
  "target_rpe": 7,
  "pace_range": "5:00-5:12",
  "warmup_km": 2.0,
  "cooldown_km": 1.5,
  "structured_workout": {
    "sport": "run",
    "steps": [
      {
        "kind": "steady",
        "duration": {"unit": "meters", "value": 2000},
        "target": {
          "mode": "pace",
          "unit": "seconds_per_kilometer",
          "minimum": 360,
          "maximum": 390
        },
        "intensity": "warmup"
      },
      {
        "kind": "steady",
        "duration": {"unit": "meters", "value": 3000},
        "target": {
          "mode": "pace",
          "unit": "seconds_per_kilometer",
          "minimum": 300,
          "maximum": 312
        },
        "intensity": "interval"
      },
      {
        "kind": "steady",
        "duration": {"unit": "meters", "value": 1500},
        "target": {
          "mode": "pace",
          "unit": "seconds_per_kilometer",
          "minimum": 360,
          "maximum": 400
        },
        "intensity": "active"
      },
      {
        "kind": "steady",
        "duration": {"unit": "meters", "value": 1500},
        "target": {
          "mode": "pace",
          "unit": "seconds_per_kilometer",
          "minimum": 375,
          "maximum": 420
        },
        "intensity": "cooldown"
      }
    ]
  },
  "key_workout": true,
  "notes": "Run the threshold block evenly; avoid accelerating early."
}
```

## Worked cycling ramp example

```json
{
  "date": "2026-02-14",
  "sport": "cycle",
  "day_of_week": 4,
  "workout_type": "tempo",
  "distance_km": 0,
  "target_rpe": 7,
  "warmup_km": 0,
  "cooldown_km": 0,
  "structured_workout": {
    "sport": "cycle",
    "steps": [
      {
        "kind": "steady",
        "duration": {"unit": "seconds", "value": 900},
        "target": {
          "mode": "power",
          "unit": "percent_ftp",
          "minimum": 55,
          "maximum": 65
        },
        "intensity": "warmup"
      },
      {
        "kind": "ramp",
        "duration": {"unit": "seconds", "value": 1200},
        "start_target": {
          "mode": "power",
          "unit": "percent_ftp",
          "minimum": 75,
          "maximum": 80
        },
        "end_target": {
          "mode": "power",
          "unit": "percent_ftp",
          "minimum": 90,
          "maximum": 95
        },
        "intensity": "interval"
      },
      {
        "kind": "steady",
        "duration": {"unit": "seconds", "value": 600},
        "target": {
          "mode": "power",
          "unit": "percent_ftp",
          "minimum": 45,
          "maximum": 55
        },
        "intensity": "cooldown"
      }
    ]
  },
  "key_workout": true
}
```

## Accounting checks

- Tempo work: no more than 10% of weekly running volume by default.
- VO2max work: no more than 8%.
- Repetition work: no more than 5%.
- Easy time: at least 80% across warm-ups, recoveries, cool-downs, easy runs,
  and easy portions of long runs.
- Long run: no more than the configured percentage cap, normally 30%.

Do not hide structured segments in prose. Notes are for cues; the typed step
tree is the execution contract.
