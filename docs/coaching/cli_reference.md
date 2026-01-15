# CLI Reference

Complete reference for Sports Coach Engine command-line interface.

## Command Index

| Command                               | Purpose                      | Key Data Returned                                                |
| ------------------------------------- | ---------------------------- | ---------------------------------------------------------------- |
| **`sce init`**                        | Initialize data directories  | created/skipped paths, next_steps                                |
| **`sce sync [--since 14d]`**          | Import from Strava           | activities_imported, total_load_au, metrics_updated              |
| **`sce status`**                      | Get current training metrics | CTL, ATL, TSB, ACWR, readiness (all with interpretations)        |
| **`sce today [--date YYYY-MM-DD]`**   | Get workout recommendation   | workout details, current_metrics, adaptation_triggers, rationale |
| **`sce week`**                        | Get weekly summary           | planned_workouts, completed_activities, metrics, week_changes    |
| **`sce goal --type --date [--time]`** | Set race goal                | goal details, plan_regenerated confirmation                      |
| **`sce auth url`**                    | Get OAuth URL                | url, instructions for authorization                              |
| **`sce auth exchange --code`**        | Exchange auth code           | status, expires_at, next_steps                                   |
| **`sce auth status`**                 | Check token validity         | authenticated, expires_at, expires_in_hours                      |
| **`sce profile get`**                 | Get athlete profile          | name, age, max_hr, goal, constraints, preferences                |
| **`sce profile set --field value`**   | Update profile               | updated profile with all fields                                  |
| **`sce plan show`**                   | Get current plan             | goal, total_weeks, weeks array, phases, workouts                 |
| **`sce plan regen`**                  | Regenerate plan              | new plan based on current goal                                   |

## JSON Response Structure

All `sce` commands return JSON with this consistent structure:

```json
{
  "schema_version": "1.0",
  "ok": true,
  "error_type": null,
  "message": "Human-readable summary",
  "data": {
    /* command-specific payload with rich interpretations */
  }
}
```

### Field Definitions

- **schema_version**: Response format version (currently "1.0")
- **ok**: Boolean success indicator
  - `true`: Operation succeeded, parse `data`
  - `false`: Operation failed, check `error_type` and `message`
- **error_type**: Error category (see Exit Codes below)
- **message**: Human-readable description of result or error
- **data**: Command-specific payload
  - Contains rich interpretations (e.g., "CTL 44 = solid recreational fitness")
  - Includes zone classifications, trend indicators, recommendations

### Using Rich Interpretations

Don't just read raw values - use the interpretations:

```bash
# ❌ Bad: Generic coaching
"Your CTL is 44"

# ✅ Good: Use interpretations
result=$(sce status)
ctl=$(echo "$result" | jq -r '.data.ctl.value')
interpretation=$(echo "$result" | jq -r '.data.ctl.interpretation')
echo "Your CTL is $ctl ($interpretation)"
# Output: "Your CTL is 44 (solid recreational fitness level)"
```

---

## Exit Codes Reference

Always check exit codes after command execution:

```bash
sce status
exit_code=$?
```

### Exit Code Table

| Code | Meaning | Error Type | Action |
|------|---------|------------|--------|
| **0** | Success | - | Parse JSON and proceed |
| **2** | Config/Setup Missing | `config_missing` | Run `sce init` to initialize |
| **3** | Authentication Failure | `auth_error` | Run `sce auth url` to refresh token |
| **4** | Network/Rate Limit | `network_error`, `rate_limit` | Retry with exponential backoff |
| **5** | Invalid Input | `validation_error` | Check parameters and retry |
| **1** | Internal Error | `internal_error` | Report issue with traceback |

### Error Handling Pattern

```bash
sce sync
case $? in
  0)
    echo "Sync successful"
    ;;
  2)
    echo "Config missing - run: sce init"
    sce init
    ;;
  3)
    echo "Auth expired - refreshing token"
    sce auth url
    # Wait for user to authorize...
    ;;
  4)
    echo "Network issue - retrying in 30s"
    sleep 30
    sce sync
    ;;
  5)
    echo "Invalid parameters - check command syntax"
    sce sync --help
    ;;
  *)
    echo "Internal error - check logs"
    ;;
esac
```

### Error Type to Exit Code Mapping

- `config_missing` → Exit code 2
- `auth_error` → Exit code 3
- `network_error`, `rate_limit` → Exit code 4
- `validation_error`, `insufficient_data` → Exit code 5
- All other errors → Exit code 1

## Detailed Command Reference

### Authentication Commands

#### `sce auth url`

Get Strava OAuth authorization URL.

**Usage:**

```bash
sce auth url
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "url": "https://www.strava.com/oauth/authorize?...",
    "instructions": "Open this URL in your browser and authorize..."
  }
}
```

**Next steps:**

1. Open URL in browser
2. Authorize application
3. Copy authorization code from redirect URL
4. Run `sce auth exchange --code YOUR_CODE`

---

#### `sce auth exchange --code CODE`

Exchange authorization code for access token.

**Usage:**

```bash
sce auth exchange --code 1234567890abcdef
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "status": "authenticated",
    "expires_at": "2026-02-14T10:30:00Z",
    "next_steps": "Run 'sce sync' to import activities"
  }
}
```

**Token Storage:**

- Saved to `config/secrets.local.yaml`
- Automatically refreshed when expired
- Never committed to git (in .gitignore)

---

#### `sce auth status`

Check current authentication status.

**Usage:**

```bash
sce auth status
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "authenticated": true,
    "expires_at": "2026-02-14T10:30:00Z",
    "expires_in_hours": 720
  }
}
```

**Exit codes:**

- `0`: Token valid
- `3`: Token expired or missing - refresh required

---

### Data Management Commands

#### `sce init`

Initialize data directories and configuration.

**Usage:**

```bash
sce init
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "created_paths": ["data/athlete", "data/activities", ...],
    "skipped_paths": ["config/"],
    "next_steps": "Run 'sce auth url' to connect Strava"
  }
}
```

**What it does:**

- Creates `data/` directory structure
- Validates `config/settings.yaml` exists
- Checks for `config/secrets.local.yaml` (warns if missing)

---

#### `sce sync [--since PERIOD]`

Import activities from Strava.

**Usage:**

```bash
# Sync all activities (12+ weeks recommended for CTL baseline)
sce sync

# Sync last 14 days only
sce sync --since 14d

# Sync specific date range
sce sync --since 2026-01-01
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "activities_imported": 45,
    "date_range": { "start": "2025-10-15", "end": "2026-01-14" },
    "total_load_au": 12450,
    "metrics_updated": true,
    "ctl_baseline": 44.2
  }
}
```

**What it does:**

1. Fetches activities from Strava API
2. Normalizes sport types and units (M6)
3. Computes RPE from HR/pace/notes (M7)
4. Calculates systemic + lower-body loads (M8)
5. Recalculates daily/weekly metrics (M9)
6. Updates athlete profile with discovered data

**Rate limits:**

- Strava: 100 requests / 15 minutes, 1000 requests / day
- If hit, exit code 4, retry after indicated time

---

### Metrics & Status Commands

#### `sce status`

Get current training metrics with interpretations.

**Usage:**

```bash
sce status
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "ctl": {
      "value": 44.2,
      "formatted_value": "44",
      "zone": "recreational",
      "interpretation": "solid recreational fitness level",
      "trend": "+2 from last week",
      "explanation": "Your fitness has been building steadily..."
    },
    "atl": {
      "value": 52.1,
      "formatted_value": "52"
    },
    "tsb": {
      "value": -7.9,
      "formatted_value": "-8",
      "zone": "productive",
      "interpretation": "optimal training zone"
    },
    "acwr": {
      "value": 1.18,
      "formatted_value": "1.18",
      "zone": "safe",
      "interpretation": "normal injury risk"
    },
    "readiness": {
      "score": 68,
      "level": "moderate",
      "breakdown": {
        "tsb_contribution": 15,
        "recent_trend_contribution": 20,
        "sleep_contribution": 17,
        "wellness_contribution": 16
      }
    }
  }
}
```

**Key Metrics:**

- **CTL** (Chronic Training Load): 42-day fitness
- **ATL** (Acute Training Load): 7-day fatigue
- **TSB** (Training Stress Balance): CTL - ATL, represents form
- **ACWR** (Acute:Chronic Workload Ratio): Injury risk indicator
- **Readiness**: 0-100 composite score

---

#### `sce week`

Get weekly summary with planned vs completed activities.

**Usage:**

```bash
sce week
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "week_number": 2,
    "week_start": "2026-01-13",
    "week_end": "2026-01-19",
    "planned_workouts": [
      {
        "date": "2026-01-13",
        "workout_type": "easy",
        "duration_minutes": 30,
        "status": "completed"
      },
      {
        "date": "2026-01-15",
        "workout_type": "tempo",
        "duration_minutes": 45,
        "status": "pending"
      }
    ],
    "completed_activities": [
      {
        "date": "2026-01-13",
        "sport_type": "run",
        "duration_minutes": 32,
        "systemic_load_au": 224
      },
      {
        "date": "2026-01-14",
        "sport_type": "climbing",
        "duration_minutes": 105,
        "systemic_load_au": 315,
        "lower_body_load_au": 52
      }
    ],
    "weekly_metrics": {
      "total_load_au": 539,
      "ctl_change": 2.1,
      "completion_rate": 0.5
    }
  }
}
```

---

#### `sce today [--date YYYY-MM-DD]`

Get today's workout recommendation with full context.

**Usage:**

```bash
# Today's workout
sce today

# Specific date
sce today --date 2026-01-20
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "workout": {
      "workout_type": "tempo",
      "duration_minutes": 45,
      "target_rpe": 7,
      "pace_zones": {
        "easy": "6:00-6:30/km",
        "moderate": "5:30-5:50/km",
        "threshold": "4:50-5:10/km"
      },
      "hr_zones": {
        "zone_2": "130-145 bpm",
        "zone_3": "145-160 bpm",
        "zone_4": "160-175 bpm"
      },
      "workout_type_display": "Tempo Run",
      "intensity_description": "Comfortably Hard",
      "purpose": "Develop aerobic threshold"
    },
    "current_metrics": {
      "ctl": 44.2,
      "tsb": -7.9,
      "acwr": 1.18,
      "readiness": 68
    },
    "adaptation_triggers": [
      {
        "type": "lower_body_load_high",
        "severity": "moderate",
        "message": "Elevated lower-body load from yesterday's climbing"
      }
    ],
    "rationale": "Your form is good (TSB -8), fitness building (CTL +2). Consider easy warm-up given yesterday's climbing."
  }
}
```

---

### Planning Commands

#### `sce goal --type TYPE --date DATE [--time TIME]`

Set a race goal (automatically regenerates plan).

**Usage:**

```bash
# Set 10K goal with target time
sce goal --type 10k --date 2026-06-01 --time 00:45:00

# Set half marathon goal
sce goal --type half_marathon --date 2026-09-15 --time 01:45:00

# Set marathon goal (no time = fitness goal)
sce goal --type marathon --date 2026-11-01
```

**Supported race types:**

- `5k`, `10k`, `half_marathon`, `marathon`

**Returns:**

```json
{
  "ok": true,
  "data": {
    "goal": {
      "type": "10k",
      "target_date": "2026-06-01",
      "target_time": "00:45:00",
      "target_pace_per_km": "4:30",
      "vdot": 48,
      "effort_level": "competitive"
    },
    "plan_regenerated": true,
    "total_weeks": 20
  }
}
```

**What happens:**

1. Goal saved to profile
2. M10 generates new training plan
3. Plan saved to `data/plans/current_plan.yaml`
4. Periodization calculated based on weeks available
5. Volume progression set based on current CTL

---

#### `sce plan show`

Get current training plan with all weeks and workouts.

**Usage:**

```bash
sce plan show
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "goal": {
      "type": "half_marathon",
      "target_date": "2026-09-15",
      "target_time": "01:45:00"
    },
    "total_weeks": 32,
    "plan_start": "2026-01-20",
    "plan_end": "2026-09-15",
    "phases": {
      "base": {"weeks": 12, "start_week": 1},
      "build": {"weeks": 12, "start_week": 13},
      "peak": {"weeks": 6, "start_week": 25},
      "taper": {"weeks": 2, "start_week": 31}
    },
    "weeks": [
      {
        "week_number": 1,
        "phase": "base",
        "weekly_volume_km": 25,
        "workouts": [...]
      }
    ]
  }
}
```

---

#### `sce plan regen`

Regenerate plan based on current goal.

**Usage:**

```bash
sce plan regen
```

**When to use:**

- After significant training interruption
- After injury recovery (CTL dropped)
- Profile constraints changed significantly
- Want fresh plan with same goal

---

### Profile Commands

#### `sce profile get`

Get athlete profile.

**Usage:**

```bash
sce profile get
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "name": "Alex",
    "age": 32,
    "max_hr": 190,
    "goal": {
      "type": "half_marathon",
      "target_date": "2026-09-15"
    },
    "constraints": {
      "available_run_days": [
        "monday",
        "wednesday",
        "friday",
        "saturday",
        "sunday"
      ],
      "min_run_days_per_week": 3,
      "max_run_days_per_week": 4,
      "max_time_per_session_minutes": 90
    },
    "running_priority": "equal",
    "conflict_policy": "ask_each_time"
  }
}
```

---

#### `sce profile set --field VALUE`

Update profile fields.

**Usage:**

```bash
# Update basic info
sce profile set --name "Alex" --age 32 --max-hr 190

# Update constraints
sce profile set --min-run-days 3 --max-run-days 4

# Update priorities
sce profile set --run-priority primary
sce profile set --conflict-policy running_goal_wins
```

**Available fields:**

- `--name` (string)
- `--age` (integer)
- `--max-hr` (integer)
- `--min-run-days` (integer, 1-7)
- `--max-run-days` (integer, 1-7)
- `--max-session-time` (integer, minutes)
- `--run-priority` (`primary`, `secondary`, `equal`)
- `--conflict-policy` (`primary_sport_wins`, `running_goal_wins`, `ask_each_time`)

---

## Parsing CLI Output

### Using `jq`

```bash
# Extract specific field
result=$(sce status)
ctl=$(echo "$result" | jq -r '.data.ctl.value')
echo "CTL: $ctl"

# Check if command succeeded
ok=$(echo "$result" | jq -r '.ok')
if [ "$ok" = "true" ]; then
  echo "Success"
fi

# Extract error message
if [ "$ok" = "false" ]; then
  error=$(echo "$result" | jq -r '.message')
  echo "Error: $error"
fi
```

### Error Handling Pattern

```bash
sce status
exit_code=$?

case $exit_code in
  0)
    echo "Success"
    ;;
  2)
    echo "Run 'sce init' first"
    ;;
  3)
    echo "Auth expired - run 'sce auth url'"
    ;;
  4)
    echo "Network/rate limit - retry later"
    ;;
  5)
    echo "Invalid input - check parameters"
    ;;
  *)
    echo "Internal error"
    ;;
esac
```

## See Also

- [Coaching Scenarios](scenarios.md) - Example workflows
- [Training Methodology](methodology.md) - Understanding metrics
- [API Layer Spec](../specs/api_layer.md) - Python API documentation
