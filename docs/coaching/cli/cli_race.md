# Race Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Race performance tracking and personal best (PB) management for progression/regression analysis.

**Commands in this category:**
- `sce race add` - Add a race performance to your race history
- `sce race list` - List race history grouped by distance with VDOTs and PB flags
- `sce race import-from-strava` - Auto-detect potential race activities from Strava
- `sce vdot estimate-current` - Estimate current VDOT from workouts

---

## sce race add

Add a race performance to your race history with automatic VDOT calculation and PB tracking.

**Usage:**

```bash
sce race add --distance 10k --time 42:30 --date 2025-06-15 \
  --location "City 10K Championship" \
  --source official_race \
  --notes "Perfect conditions, felt strong"
```

**Parameters:**

- `--distance`: Race distance (5k, 10k, half_marathon, marathon, mile, 15k)
- `--time`: Race time in MM:SS or HH:MM:SS format (e.g., "42:30" or "1:30:00")
- `--date`: Race date in YYYY-MM-DD format
- `--location`: Race name or location (optional)
- `--source`: Race timing source (optional, default: gps_watch)
  - `official_race`: Chip-timed race (highest accuracy)
  - `gps_watch`: GPS-verified effort (good accuracy)
  - `estimated`: Calculated/estimated (lower accuracy)
- `--notes`: Additional notes about the race (optional)

**Returns:**

```json
{
  "ok": true,
  "message": "Added 10K race: 42:30 on 2025-06-15 (VDOT 44.0) [NEW PB]",
  "data": {
    "distance": "10k",
    "time": "42:30",
    "date": "2025-06-15",
    "location": "City 10K Championship",
    "source": "official_race",
    "vdot": 44.0,
    "notes": "Perfect conditions, felt strong",
    "is_pb": true
  }
}
```

**What happens:**

1. Calculates VDOT from race time
2. Updates PB flags (highest VDOT for each distance marked as PB)
3. Recalculates `peak_vdot` if this is your best performance
4. Stores in profile's `race_history` field

---

## sce race list

List race history grouped by distance with VDOTs and PB flags.

**Usage:**

```bash
# List all races
sce race list

# Filter by distance
sce race list --distance 10k

# Show only races after a date
sce race list --since 2024-01-01

# Combine filters
sce race list --distance half_marathon --since 2023-06-01
```

**Returns:**

```json
{
  "ok": true,
  "message": "Found 5 races across 3 distances",
  "data": {
    "5k": [
      {
        "distance": "5k",
        "time": "18:45",
        "date": "2024-05-10",
        "location": "Parkrun",
        "source": "gps_watch",
        "vdot": 51.0,
        "notes": null,
        "is_pb": true
      },
      {
        "distance": "5k",
        "time": "19:02",
        "date": "2024-03-15",
        "location": null,
        "source": "gps_watch",
        "vdot": 50.0,
        "notes": null,
        "is_pb": false
      }
    ],
    "10k": [
      {
        "distance": "10k",
        "time": "42:30",
        "date": "2025-06-15",
        "location": "City 10K",
        "source": "official_race",
        "vdot": 44.0,
        "notes": "Perfect conditions",
        "is_pb": true
      }
    ],
    "half_marathon": [
      {
        "distance": "half_marathon",
        "time": "1:30:45",
        "date": "2023-09-15",
        "location": "State Half",
        "source": "official_race",
        "vdot": 49.0,
        "notes": null,
        "is_pb": true
      }
    ]
  }
}
```

**Output structure:**

- Races grouped by distance (5k, 10k, half_marathon, marathon)
- Sorted by date (newest first) within each distance
- PB flag indicates fastest time for that distance

---

## sce race import-from-strava

Auto-detect potential race activities from synced Strava activities.

**Detection criteria:**

- Strava `workout_type == 1` (race flag)
- Keywords in title/description: "race", "5K", "10K", "HM", "PB", "PR"
- Distance matches standard race distances (±5%)

**Usage:**

```bash
# Detect all races in synced activities (last 120 days)
sce race import-from-strava

# Detect races since specific date
sce race import-from-strava --since 2025-01-01

# Non-interactive mode (no confirmation prompt)
sce race import-from-strava --no-interactive
```

**Returns:**

```json
{
  "ok": true,
  "message": "Detected 2 potential races from Strava",
  "data": [
    {
      "distance": "half_marathon",
      "time": "1:32:00",
      "date": "2025-11-15",
      "location": "State Half Marathon",
      "source": "gps_watch",
      "vdot": 48.5,
      "notes": "Auto-detected from Strava (activity_id: 12345678)",
      "is_pb": false
    },
    {
      "distance": "10k",
      "time": "43:00",
      "date": "2025-12-01",
      "location": "City 10K Race",
      "source": "gps_watch",
      "vdot": 43.5,
      "notes": "Auto-detected from Strava (activity_id: 87654321)",
      "is_pb": false
    }
  ]
}
```

**Important:**

- This command **detects** races but does **NOT** automatically add them to race history
- Review detected races, then use `sce race add` for each race you want to save
- Only detects races from synced activities (last 120 days by default)
- For historical PBs older than 120 days, use `sce race add` manually

**Typical workflow:**

```bash
# 1. Detect races
sce race import-from-strava

# 2. Review detected races
# Output shows 2 potential races

# 3. Add confirmed races
sce race add --distance half_marathon --time 1:32:00 --date 2025-11-15 \
  --source gps_watch --location "State Half Marathon"

sce race add --distance 10k --time 43:00 --date 2025-12-01 \
  --source gps_watch --location "City 10K Race"
```

---

## sce vdot estimate-current

Estimate current VDOT from recent tempo and interval workouts.

**Usage:**

```bash
# Estimate from last 28 days (default)
sce vdot estimate-current

# Estimate from last 14 days
sce vdot estimate-current --lookback-days 14
```

**Detection logic:**

- Searches for tempo/interval keywords in workout titles
- Extracts average pace from quality workouts
- Calculates implied VDOT from workout paces
- Returns median VDOT with confidence level

**Returns:**

```json
{
  "ok": true,
  "message": "Estimated current VDOT: 45 (confidence: high)",
  "data": {
    "estimated_vdot": 45,
    "confidence": "high",
    "source": "tempo_workouts",
    "supporting_data": [
      {
        "date": "2025-01-10",
        "workout_type": "tempo",
        "pace_sec_per_km": 270,
        "implied_vdot": 46
      },
      {
        "date": "2025-01-15",
        "workout_type": "tempo",
        "pace_sec_per_km": 275,
        "implied_vdot": 45
      },
      {
        "date": "2025-01-18",
        "workout_type": "interval",
        "pace_sec_per_km": 260,
        "implied_vdot": 44
      }
    ]
  }
}
```

**Confidence levels:**

- `high`: 3+ quality workouts found
- `medium`: 2 quality workouts found
- `low`: Only 1 quality workout found

**Use case - Progression/Regression Analysis:**

Compare current VDOT estimate to historical PB VDOTs:

```bash
# 1. Get race history
sce race list

# Output shows: 10K PB 42:30 (VDOT 48) from June 2023

# 2. Estimate current VDOT
sce vdot estimate-current

# Output shows: Current VDOT 45 (from recent workouts)

# 3. Interpret trend
# VDOT 48 → 45 = 3-point regression over 18 months
# Coach: "You've regressed 3 VDOT points since your PB. Normal after 18 months
# without racing. We'll rebuild gradually from VDOT 45 toward your peak of 48."
```

**Requirements:**

- Requires quality workouts with tempo/interval keywords in titles
- If no quality workouts found, run a tempo workout first
- Works best with 3+ quality workouts in lookback period

---

**Navigation**: [Back to Index](index.md) | [Previous: VDOT Commands](cli_vdot.md) | [Next: Guardrails Commands](cli_guardrails.md)
