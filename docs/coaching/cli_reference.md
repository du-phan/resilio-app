# CLI Reference

Complete reference for Sports Coach Engine command-line interface.

## Command Index

| Command                                 | Purpose                      | Key Data Returned                                                   |
| --------------------------------------- | ---------------------------- | ------------------------------------------------------------------- |
| **`sce init`**                          | Initialize data directories  | created/skipped paths, next_steps                                   |
| **`sce sync [--since 14d]`**            | Import from Strava           | activities_imported, total_load_au, metrics_updated                 |
| **`sce status`**                        | Get current training metrics | CTL, ATL, TSB, ACWR, readiness (all with interpretations)           |
| **`sce today [--date YYYY-MM-DD]`**     | Get workout recommendation   | workout details, current_metrics, adaptation_triggers, rationale    |
| **`sce week`**                          | Get weekly summary           | planned_workouts, completed_activities, metrics, week_changes       |
| **`sce goal --type --date [--time]`**   | Set race goal                | goal details, plan_regenerated confirmation                         |
| **`sce auth url`**                      | Get OAuth URL                | url, instructions for authorization                                 |
| **`sce auth exchange --code`**          | Exchange auth code           | status, expires_at, next_steps                                      |
| **`sce auth status`**                   | Check token validity         | authenticated, expires_at, expires_in_hours                         |
| **`sce profile get`**                   | Get athlete profile          | name, age, max_hr, goal, constraints, preferences                   |
| **`sce profile set --field value`**     | Update profile               | updated profile with all fields                                     |
| **`sce plan show`**                     | Get current plan             | goal, total_weeks, weeks array, phases, workouts                    |
| **`sce plan regen`**                    | Regenerate plan              | new plan based on current goal                                      |
| **`sce vdot calculate`**                | Calculate VDOT from race     | vdot, source_race, confidence, formatted_time                       |
| **`sce vdot paces`**                    | Get training pace zones      | easy/marathon/threshold/interval/repetition pace ranges             |
| **`sce vdot predict`**                  | Predict race times           | equivalent times for all distances                                  |
| **`sce vdot six-second`**               | Apply six-second rule        | R/I/T pace estimates for novices                                    |
| **`sce vdot adjust`**                   | Adjust for conditions        | pace adjustments for altitude/heat/humidity/hills                   |
| **`sce guardrails quality-volume`**     | Validate T/I/R pace volumes  | overall_ok, violations, pace_limits for T/I/R                       |
| **`sce guardrails progression`**        | Validate weekly progression  | ok, increase_pct, safe_max_km, violation if any                     |
| **`sce guardrails long-run`**           | Validate long run limits     | pct_ok, duration_ok, violations with recommendations                |
| **`sce guardrails safe-volume`**        | Calculate safe volume range  | ctl_zone, recommended_start/peak_km, masters_adjusted_range         |
| **`sce guardrails break-return`**       | Plan return after break      | load_phases, vdot_adjustment, return_schedule, red_flags            |
| **`sce guardrails masters-recovery`**   | Age-specific recovery        | age_bracket, adjustments by workout type, recommended_days          |
| **`sce guardrails race-recovery`**      | Post-race recovery protocol  | minimum/recommended_days, recovery_schedule, red_flags              |
| **`sce guardrails illness-recovery`**   | Return after illness         | severity, estimated_ctl_drop, return_protocol, red_flags            |
| **`sce analysis adherence`**            | Analyze week adherence       | completion_rate, load_variance, workout_type_adherence, patterns    |
| **`sce analysis intensity`**            | Validate 80/20 distribution  | distribution, compliance, polarization_score, violations            |
| **`sce analysis gaps`**                 | Detect training gaps         | gaps with CTL impact, potential causes, patterns                    |
| **`sce analysis load`**                 | Multi-sport load breakdown   | systemic/lower-body by sport, priority adherence, fatigue flags     |
| **`sce analysis capacity`**             | Check weekly capacity        | capacity_utilization, exceeds_proven_capacity, risk_assessment      |
| **`sce risk assess`**                   | Assess current injury risk   | overall_risk_level, injury_probability, contributing_factors        |
| **`sce risk recovery-window`**          | Estimate recovery timeline   | min/typical/max days, recovery_checklist, monitoring_metrics        |
| **`sce risk forecast`**                 | Forecast training stress     | week_forecasts, risk_windows, proactive_adjustments                 |
| **`sce risk taper-status`**             | Verify taper progression     | volume_reduction_check, tsb_trajectory, readiness_trend             |
| **`sce validation validate-intervals`** | Validate interval structure  | daniels_compliance, work/recovery bouts, violations                 |
| **`sce validation validate-plan`**      | Validate plan structure      | overall_quality_score, phase_checks, volume_progression, violations |
| **`sce validation assess-goal`**        | Assess goal feasibility      | feasibility_verdict, confidence_level, recommendations, warnings    |

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

| Code  | Meaning                | Error Type                    | Action                              |
| ----- | ---------------------- | ----------------------------- | ----------------------------------- |
| **0** | Success                | -                             | Parse JSON and proceed              |
| **2** | Config/Setup Missing   | `config_missing`              | Run `sce init` to initialize        |
| **3** | Authentication Failure | `auth_error`                  | Run `sce auth url` to refresh token |
| **4** | Network/Rate Limit     | `network_error`, `rate_limit` | Retry with exponential backoff      |
| **5** | Invalid Input          | `validation_error`            | Check parameters and retry          |
| **1** | Internal Error         | `internal_error`              | Report issue with traceback         |

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
- `validation_error`, `invalid_input`, `insufficient_data` → Exit code 5
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

#### `sce profile create`

Create a new athlete profile with sensible defaults.

**Required:**
- `--name` (string) - Athlete name

**Optional - Basic Info:**
- `--age` (integer, 0-120) - Age in years
- `--email` (string) - Contact email

**Optional - Vital Signs:**
- `--max-hr` (integer, 120-220) - Maximum heart rate
- `--resting-hr` (integer, 30-100) - Resting heart rate

**Optional - Running Background:**
- `--injury-history` (string) - Free-text injury description
- `--run-experience-years` (integer) - Years of running experience
- `--weekly-km` (float) - Current weekly volume baseline
- `--run-days-per-week` (integer, 0-7) - Current frequency
- `--vdot` (float, 30-85) - Jack Daniels VDOT

**Optional - Constraints:**
- `--min-run-days` (integer, 0-7) - Minimum run days per week (default: 2)
- `--max-run-days` (integer, 0-7) - Maximum run days per week (default: 4)
- `--available-days` (comma-separated) - Available run days (e.g., "monday,wednesday,friday")
- `--preferred-days` (comma-separated) - Preferred run days (subset of available)
- `--time-preference` (`morning`, `evening`, `flexible`) - Time of day preference
- `--max-session-minutes` (integer) - Maximum session duration (default: 90)

**Optional - Multi-Sport:**
- `--run-priority` (`primary`, `secondary`, `equal`) - Running priority (default: equal)
- `--primary-sport` (string) - Primary sport name if not running
- `--conflict-policy` (`primary_sport_wins`, `running_goal_wins`, `ask_each_time`) - Conflict resolution (default: ask_each_time)

**Optional - Preferences:**
- `--detail-level` (`brief`, `moderate`, `detailed`) - Coaching detail level (default: moderate)
- `--coaching-style` (`supportive`, `direct`, `analytical`) - Communication style (default: supportive)
- `--intensity-metric` (`pace`, `hr`, `rpe`) - Primary intensity metric (default: pace)

**Examples:**

```bash
# Minimal profile
sce profile create --name "Alex"

# Full profile with all fields
sce profile create \
  --name "Alex" --age 32 --email "alex@example.com" \
  --max-hr 199 --resting-hr 55 \
  --injury-history "IT band 2024, resolved" \
  --run-experience-years 3 --weekly-km 25 \
  --available-days "tuesday,thursday,saturday,sunday" \
  --preferred-days "saturday,sunday" \
  --time-preference morning \
  --run-priority equal --primary-sport climbing \
  --conflict-policy ask_each_time \
  --detail-level moderate
```

---

#### `sce profile get`

Get athlete profile with all settings.

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
    "email": "alex@example.com",
    "max_hr": 190,
    "injury_history": "IT band 2024, resolved",
    "goal": {
      "type": "half_marathon",
      "target_date": "2026-09-15"
    },
    "constraints": {
      "available_run_days": ["tuesday", "thursday", "saturday", "sunday"],
      "preferred_run_days": ["saturday", "sunday"],
      "min_run_days_per_week": 2,
      "max_run_days_per_week": 4,
      "max_time_per_session_minutes": 90,
      "time_preference": "morning"
    },
    "running_priority": "equal",
    "conflict_policy": "ask_each_time",
    "preferences": {
      "detail_level": "moderate",
      "coaching_style": "supportive",
      "intensity_metric": "pace"
    }
  }
}
```

---

#### `sce profile set`

Update profile fields. Only specified fields are updated; others remain unchanged.

**Available Fields:** (Same as `sce profile create` except `--name` is not required)

**Examples:**

```bash
# Update basic info
sce profile set --name "Alex" --age 33 --email "newemail@example.com"

# Update vital signs
sce profile set --max-hr 190 --resting-hr 55

# Update constraints
sce profile set --min-run-days 3 --max-run-days 4
sce profile set --available-days "tuesday,thursday,saturday,sunday"
sce profile set --time-preference morning

# Update priorities
sce profile set --run-priority primary
sce profile set --conflict-policy running_goal_wins

# Update preferences
sce profile set --detail-level detailed
sce profile set --coaching-style analytical
sce profile set --intensity-metric hr
```

---

#### `sce profile add-sport`

Add a sport commitment to track multi-sport training load.

**Required:**
- `--sport` (string) - Sport name (e.g., climbing, yoga, cycling)
- `--days` (comma-separated) - Days for this sport
- `--duration` (integer) - Typical session duration in minutes
- `--intensity` (string) - Intensity level: easy, moderate, hard, moderate_to_hard

**Optional:**
- `--fixed` / `--flexible` (boolean) - Fixed commitment or flexible (default: --fixed)
- `--notes` (string) - Optional notes about the commitment

**Examples:**

```bash
sce profile add-sport \
  --sport climbing \
  --days tuesday,thursday \
  --duration 120 \
  --intensity moderate_to_hard \
  --notes "Bouldering gym 6-7pm"

sce profile add-sport \
  --sport yoga \
  --days monday \
  --duration 60 \
  --intensity easy \
  --flexible
```

---

#### `sce profile remove-sport`

Remove a sport commitment (case-insensitive).

**Usage:**

```bash
sce profile remove-sport --sport climbing
```

---

#### `sce profile list-sports`

List all sport commitments.

**Usage:**

```bash
sce profile list-sports
```

**Returns:**

```json
{
  "ok": true,
  "message": "Found 2 sport commitment(s)",
  "data": {
    "sports": [
      {
        "sport": "climbing",
        "days": ["tuesday", "thursday"],
        "duration_minutes": 120,
        "intensity": "moderate_to_hard",
        "fixed": true,
        "notes": "Bouldering gym 6-7pm"
      },
      {
        "sport": "yoga",
        "days": ["monday"],
        "duration_minutes": 60,
        "intensity": "easy",
        "fixed": false,
        "notes": null
      }
    ]
  }
}
```

---

#### `sce profile edit`

Open profile YAML in $EDITOR for direct editing (power-user feature).

**Environment Variables:**
- `EDITOR` - Your preferred editor (default: nano). Supports: nano, vim, emacs, code, etc.

**Usage:**

```bash
sce profile edit                    # Uses $EDITOR (default: nano)
EDITOR=vim sce profile edit         # Use vim
EDITOR=code sce profile edit        # Use VS Code
```

After editing, the profile is validated. If validation fails, you'll see the error message and can re-edit.

---

#### `sce profile analyze`

Analyze synced activity history to suggest profile values.

**Usage:**

```bash
sce profile analyze
```

This analyzes your Strava activity history (last 120 days) to suggest:
- `max_hr` - Observed peak heart rate
- `weekly_km` - 4-week average volume
- `available_run_days` - Days you typically train
- `running_priority` - Based on sport distribution

---

### VDOT Commands

#### `sce vdot calculate --race-type TYPE --time TIME [--race-date DATE]`

Calculate VDOT from race performance.

**Usage:**

```bash
# Calculate from 10K race
sce vdot calculate --race-type 10k --time 42:30

# With race date for confidence adjustment
sce vdot calculate --race-type half_marathon --time 1:30:00 --race-date 2026-01-10

# Marathon performance
sce vdot calculate --race-type marathon --time 3:15:00
```

**Supported race types:**

- `mile`, `5k`, `10k`, `15k`, `half_marathon`, `marathon`

**Returns:**

```json
{
  "ok": true,
  "data": {
    "vdot": 48,
    "source_race": "10k",
    "source_time_seconds": 2550,
    "source_time_formatted": "42:30",
    "confidence": "high"
  }
}
```

**Confidence levels:**

- `high`: Race within last 2 weeks
- `medium`: Race 2-6 weeks ago
- `low`: Race >6 weeks ago (default if no date provided)

---

#### `sce vdot paces --vdot VDOT [--unit UNIT]`

Generate training pace zones from VDOT.

**Usage:**

```bash
# Get paces in min/km (default)
sce vdot paces --vdot 48

# Get paces in min/mile
sce vdot paces --vdot 55 --unit min_per_mile
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "vdot": 48,
    "unit": "min_per_km",
    "easy_pace_range": [306, 330],
    "marathon_pace_range": [258, 270],
    "threshold_pace_range": [240, 252],
    "interval_pace_range": [216, 228],
    "repetition_pace_range": [192, 204]
  }
}
```

**Pace zones explained:**

- **E (Easy)**: Recovery runs, aerobic base building (5:06-5:30/km for VDOT 48)
- **M (Marathon)**: Marathon race pace (4:18-4:30/km)
- **T (Threshold)**: Lactate threshold, "comfortably hard" (4:00-4:12/km)
- **I (Interval)**: VO2max intervals, hard repeats (3:36-3:48/km)
- **R (Repetition)**: Speed work, very hard repeats (3:12-3:24/km)

---

#### `sce vdot predict --race-type TYPE --time TIME`

Predict equivalent race times for other distances.

**Usage:**

```bash
# Predict from 10K performance
sce vdot predict --race-type 10k --time 42:30

# Predict from half marathon
sce vdot predict --race-type half_marathon --time 1:30:00
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "vdot": 48,
    "source_race": "10k",
    "source_time_formatted": "42:30",
    "confidence": "high",
    "predictions": {
      "mile": "6:00",
      "5k": "20:15",
      "10k": "42:30",
      "half_marathon": "1:32:45",
      "marathon": "3:14:20"
    }
  }
}
```

**Use cases:**

- Goal feasibility assessment
- Performance tracking
- Race time predictions for goal setting

---

#### `sce vdot six-second --mile-time TIME`

Apply six-second rule for novice runners without recent race times.

**Usage:**

```bash
# Estimate paces from mile time
sce vdot six-second --mile-time 6:00

# Slower runner
sce vdot six-second --mile-time 8:30
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "source_mile_time_seconds": 360,
    "source_mile_time_formatted": "6:00",
    "r_pace_400m": 90,
    "i_pace_400m": 97,
    "t_pace_400m": 104,
    "adjustment_seconds": 7,
    "estimated_vdot_range": [46, 50],
    "note": "For more accurate paces, use Daniels Table 5.3 or complete a recent 5K race"
  }
}
```

**Six-second rule:**

- R-pace = mile pace (per 400m)
- I-pace = R-pace + 6 seconds per 400m
- T-pace = I-pace + 6 seconds per 400m
- Note: Uses 7-8 seconds for VDOT 40-50 range

---

#### `sce vdot adjust --pace PACE --condition TYPE --severity VALUE`

Adjust pace for environmental conditions.

**Usage:**

```bash
# Altitude adjustment
sce vdot adjust --pace 5:00 --condition altitude --severity 7000

# Heat adjustment
sce vdot adjust --pace 4:30 --condition heat --severity 30

# Hill adjustment
sce vdot adjust --pace 5:15 --condition hills --severity 5
```

**Condition types:**

- `altitude`: Severity in feet (e.g., 7000 for 7000ft elevation)
- `heat`: Severity in °C (e.g., 30 for 30°C)
- `humidity`: Severity in % (e.g., 80 for 80% humidity)
- `hills`: Severity in grade % (e.g., 5 for 5% grade)

**Returns:**

```json
{
  "ok": true,
  "data": {
    "base_pace_sec_per_km": 300,
    "adjusted_pace_sec_per_km": 318,
    "adjustment_seconds": 18,
    "condition_type": "altitude",
    "severity": 7000.0,
    "reason": "Altitude (7,000ft): ~6.0% slower pacing",
    "recommendation": "Significant altitude effect. Strongly recommend effort-based (RPE/HR) pacing for all workouts except R-pace."
  }
}
```

**Guidelines:**

- **Altitude >7000ft**: Use effort-based pacing (RPE/HR), not pace targets
- **Heat >30°C**: Consider treadmill or cooler time of day
- **Hills >5%**: Focus on effort, not pace

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

---

## Guardrails Commands

Volume validation and recovery planning based on Daniels' Running Formula and Pfitzinger's guidelines.

### Volume Validation

#### `sce guardrails quality-volume --t-pace --i-pace --r-pace --weekly-volume`

Validate T/I/R pace volumes against Daniels' hard constraints.

**Daniels' Rules:**

- T-pace: ≤ 10% of weekly mileage
- I-pace: ≤ lesser of 10km OR 8% of weekly mileage
- R-pace: ≤ lesser of 8km OR 5% of weekly mileage

**Usage:**

```bash
sce guardrails quality-volume --t-pace 4.5 --i-pace 6.0 --r-pace 2.0 --weekly-volume 50.0
```

**Returns:** `overall_ok`, `violations[]`, pace limits and recommendations.

---

#### `sce guardrails progression --previous --current`

Validate weekly volume progression (10% rule).

**Usage:**

```bash
sce guardrails progression --previous 40.0 --current 50.0
```

**Returns:** `ok`, `increase_pct`, `safe_max_km`, violation if exceeds 10%.

---

#### `sce guardrails long-run --distance --duration --weekly-volume`

Validate long run against weekly volume (≤30%) and duration (≤150min) limits.

**Usage:**

```bash
sce guardrails long-run --distance 18.0 --duration 135 --weekly-volume 50.0
```

**Returns:** `pct_ok`, `duration_ok`, `violations[]` with recommendations.

---

#### `sce guardrails safe-volume --ctl --goal [--age]`

Calculate safe weekly volume range based on current fitness (CTL) and goals.

**Usage:**

```bash
sce guardrails safe-volume --ctl 44.0 --goal half_marathon --age 52
```

**Returns:** `ctl_zone`, `recommended_start/peak_km`, masters adjustments if age 50+.

---

### Recovery Planning

#### `sce guardrails break-return --days --ctl [--cross-training]`

Generate return-to-training protocol per Daniels Table 9.2.

**Usage:**

```bash
sce guardrails break-return --days 21 --ctl 44.0 --cross-training moderate
```

**Returns:** Load phases, VDOT adjustment, week-by-week schedule, red flags.

---

#### `sce guardrails masters-recovery --age --workout-type`

Calculate age-specific recovery adjustments (Pfitzinger).

**Usage:**

```bash
sce guardrails masters-recovery --age 52 --workout-type vo2max
```

**Returns:** Age bracket, additional recovery days by workout type.

---

#### `sce guardrails race-recovery --distance --age [--effort]`

Determine post-race recovery protocol by distance and age.

**Usage:**

```bash
sce guardrails race-recovery --distance half_marathon --age 52 --effort hard
```

**Returns:** Minimum/recommended recovery days, day-by-day schedule.

---

#### `sce guardrails illness-recovery --start-date --end-date [--severity]`

Generate structured return-to-training plan after illness.

**Usage:**

```bash
sce guardrails illness-recovery --start-date 2026-01-10 --end-date 2026-01-15 --severity moderate
```

**Returns:** CTL drop estimate, day-by-day return protocol, medical consultation triggers.

---

## Analysis Commands

Weekly insights and multi-sport load distribution analysis.

### Week Adherence Analysis

#### `sce analysis adherence --week --planned --completed`

Compare planned vs actual training to identify adherence patterns.

**Usage:**

```bash
sce analysis adherence --week 5 \
    --planned planned_week5.json \
    --completed completed_week5.json
```

**Input JSON Format (planned_week5.json):**

```json
[
  {
    "workout_type": "easy",
    "duration_minutes": 40,
    "distance_km": 6.0,
    "target_systemic_load_au": 160,
    "target_lower_body_load_au": 160
  },
  {
    "workout_type": "tempo",
    "duration_minutes": 45,
    "distance_km": 8.0,
    "target_systemic_load_au": 315,
    "target_lower_body_load_au": 315
  }
]
```

**Input JSON Format (completed_week5.json):**

```json
[
  {
    "sport": "running",
    "duration_minutes": 40,
    "distance_km": 6.0,
    "systemic_load_au": 160,
    "lower_body_load_au": 160,
    "workout_type": "easy"
  },
  {
    "sport": "climbing",
    "duration_minutes": 90,
    "systemic_load_au": 340,
    "lower_body_load_au": 52,
    "workout_type": null
  }
]
```

**Returns:** Completion rate, load variance (planned vs actual), workout type adherence breakdown, detected patterns, recommendations.

---

### Intensity Distribution

#### `sce analysis intensity --activities [--days]`

Validate 80/20 rule compliance (80% low-intensity, 20% high-intensity).

**Usage:**

```bash
sce analysis intensity --activities activities_28d.json --days 28
```

**Input JSON Format:**

```json
[
  { "intensity_zone": "z2", "duration_minutes": 40, "date": "2026-01-01" },
  { "intensity_zone": "z2", "duration_minutes": 30, "date": "2026-01-03" },
  { "intensity_zone": "z4", "duration_minutes": 45, "date": "2026-01-05" },
  { "intensity_zone": "z2", "duration_minutes": 60, "date": "2026-01-08" }
]
```

**Valid intensity zones:** z1, z2, z3, z4, z5

**Returns:** Distribution percentages (low/moderate/high), compliance level (excellent/good/fair/poor/moderate_intensity_rut), polarization score (0-100), violations, recommendations.

---

### Activity Gap Detection

#### `sce analysis gaps --activities [--min-days]`

Detect training breaks with CTL impact analysis and cause detection.

**Usage:**

```bash
sce analysis gaps --activities all_activities.json --min-days 7
```

**Input JSON Format:**

```json
[
  { "date": "2025-11-10", "ctl": 44.0, "notes": "Easy run" },
  { "date": "2025-11-12", "ctl": 44.5, "notes": "Tempo" },
  { "date": "2025-11-13", "ctl": 45.0, "notes": "Left ankle pain" },
  { "date": "2025-11-28", "ctl": 22.0, "notes": "Return from injury" },
  { "date": "2025-11-30", "ctl": 24.0, "notes": "Easy run" }
]
```

**Returns:** Detected gaps (start/end dates, duration, CTL impact), potential causes (injury/illness detected from notes), recovery status, patterns, recommendations.

---

### Multi-Sport Load Distribution

#### `sce analysis load --activities [--days] [--priority]`

Analyze systemic and lower-body load distribution across all sports.

**Usage:**

```bash
sce analysis load --activities week_activities.json \
    --days 7 --priority equal
```

**Valid priorities:** `running_primary`, `equal`, `other_primary`

**Input JSON Format:**

```json
[
  {
    "sport": "running",
    "systemic_load_au": 160,
    "lower_body_load_au": 160,
    "date": "2026-01-13"
  },
  {
    "sport": "climbing",
    "systemic_load_au": 340,
    "lower_body_load_au": 52,
    "date": "2026-01-14"
  },
  {
    "sport": "running",
    "systemic_load_au": 315,
    "lower_body_load_au": 315,
    "date": "2026-01-15"
  },
  {
    "sport": "yoga",
    "systemic_load_au": 70,
    "lower_body_load_au": 48,
    "date": "2026-01-16"
  }
]
```

**Returns:** Systemic/lower-body load by sport (AU + percentages), total loads, sport priority adherence, fatigue risk flags, recommendations.

---

### Weekly Capacity Check

#### `sce analysis capacity --week --volume --load --historical`

Validate planned volume against athlete's proven capacity.

**Usage:**

```bash
sce analysis capacity --week 15 --volume 60.0 --load 550.0 \
    --historical all_activities.json
```

**Input JSON Format (all_activities.json):**

```json
[
  { "distance_km": 25.0, "systemic_load_au": 350, "date": "2025-12-01" },
  { "distance_km": 30.0, "systemic_load_au": 400, "date": "2025-12-08" },
  { "distance_km": 50.0, "systemic_load_au": 500, "date": "2025-12-29" }
]
```

**Returns:** Historical max volume/load, capacity utilization percentages, exceeds_proven_capacity flag, risk assessment (low/moderate/high), risk factors, recommendations.

---

## Risk Assessment Commands

Holistic injury risk analysis and training stress forecasting.

### Current Risk Assessment

#### `sce risk assess --metrics --recent [--planned]`

Multi-factor injury risk assessment combining ACWR, readiness, TSB, recent load.

**Usage:**

```bash
sce risk assess --metrics current_metrics.json \
    --recent last_7d_activities.json \
    --planned today_workout.json
```

**Input JSON Format (current_metrics.json):**

```json
{
  "ctl": 44.0,
  "atl": 52.0,
  "tsb": -8.0,
  "acwr": 1.18,
  "readiness": 65,
  "date": "2026-01-15"
}
```

**Input JSON Format (last_7d_activities.json):**

```json
[
  {
    "sport": "climbing",
    "systemic_load_au": 340,
    "lower_body_load_au": 52,
    "date": "2026-01-14"
  },
  {
    "sport": "running",
    "systemic_load_au": 160,
    "lower_body_load_au": 160,
    "date": "2026-01-13"
  }
]
```

**Input JSON Format (today_workout.json, optional):**

```json
{
  "workout_type": "tempo",
  "expected_load_au": 315
}
```

**Returns:** Overall risk level (low/moderate/high/danger), injury probability (%), contributing factors with weights, recommended action, risk mitigation options (easy run, move workout, proceed), rationale.

---

### Recovery Window Estimation

#### `sce risk recovery-window --trigger --value --threshold`

Estimate recovery timeline to return to safe training zones.

**Usage:**

```bash
sce risk recovery-window --trigger ACWR_ELEVATED \
    --value 1.35 --threshold 1.3
```

**Valid triggers:** `ACWR_ELEVATED`, `TSB_OVERREACHED`, `READINESS_LOW`, `LOWER_BODY_SPIKE`

**Returns:** Min/typical/max recovery days, day-by-day recovery checklist with actions and checks, monitoring metrics.

---

### Training Stress Forecast

#### `sce risk forecast --weeks --metrics --plan`

Project CTL/ATL/TSB/ACWR 1-4 weeks ahead to identify risk windows.

**Usage:**

```bash
sce risk forecast --weeks 3 \
    --metrics current_metrics.json \
    --plan planned_weeks.json
```

**Input JSON Format (planned_weeks.json):**

```json
[
  {
    "week_number": 6,
    "target_systemic_load_au": 450,
    "end_date": "2026-01-22"
  },
  {
    "week_number": 7,
    "target_systemic_load_au": 480,
    "end_date": "2026-01-29"
  },
  { "week_number": 8, "target_systemic_load_au": 500, "end_date": "2026-02-05" }
]
```

**Returns:** Week-by-week forecast (projected CTL/ATL/TSB/ACWR, readiness estimate, risk level), risk windows with reasons and recommendations, proactive plan adjustments.

---

### Taper Status Assessment

#### `sce risk taper-status --race-date --metrics --recent-weeks`

Verify taper progression toward race day freshness.

**Usage:**

```bash
sce risk taper-status --race-date 2026-03-15 \
    --metrics current_metrics.json \
    --recent-weeks last_3_weeks.json
```

**Input JSON Format (last_3_weeks.json):**

```json
[
  { "week_number": 10, "actual_volume_km": 42.0, "end_date": "2026-03-01" },
  { "week_number": 11, "actual_volume_km": 30.0, "end_date": "2026-03-08" }
]
```

**Returns:** Weeks until race, taper phase (week_3_out/week_2_out/race_week), volume reduction check (target vs actual percentages), TSB trajectory (current/target/projected for race day), readiness trend (improving/stable/declining), overall status (on_track/adjust_needed/concern), recommendations, red flags.

---

## Validation Commands

Validate interval structure, plan structure, and goal feasibility.

### Interval Structure Validation

#### `sce validation validate-intervals --type --intensity --work-bouts --recovery-bouts [--weekly-volume]`

Validate interval workout structure per Daniels methodology.

**Usage:**

```bash
sce validation validate-intervals \
    --type intervals \
    --intensity I-pace \
    --work-bouts work.json \
    --recovery-bouts recovery.json \
    --weekly-volume 50
```

**Input JSON Format (work.json):**

```json
[
  {
    "duration_minutes": 4.0,
    "pace_per_km_seconds": 270,
    "distance_km": 1.0
  },
  {
    "duration_minutes": 4.0,
    "pace_per_km_seconds": 270,
    "distance_km": 1.0
  }
]
```

**Input JSON Format (recovery.json):**

```json
[
  {
    "duration_minutes": 4.0,
    "type": "jog"
  },
  {
    "duration_minutes": 4.0,
    "type": "jog"
  }
]
```

**Daniels Rules Checked:**

- **I-pace**: 3-5min work bouts, equal recovery (jogging), total ≤10km or 8% weekly
- **T-pace**: 5-15min work bouts, 1min recovery per 5min work, total ≤10% weekly
- **R-pace**: 30-90sec work bouts, 2-3x recovery, total ≤8km or 5% weekly

**Returns:** Workout type, intensity, work/recovery bout analysis (ok/issue per bout), violations (type/severity/message/recommendation), total work volume (minutes/km), daniels_compliance (true/false), recommendations.

**Example Response:**

```json
{
  "ok": true,
  "data": {
    "workout_type": "intervals",
    "intensity": "I-pace",
    "daniels_compliance": false,
    "violations": [
      {
        "type": "I_PACE_RECOVERY_TOO_SHORT",
        "severity": "MODERATE",
        "message": "Recovery 1 (2.0min) less than work bout (4.0min)",
        "recommendation": "Increase recovery to 4.0min (equal to work) for I-pace"
      }
    ],
    "total_work_volume_minutes": 12.0,
    "total_work_volume_km": 3.0,
    "total_volume_ok": true
  }
}
```

---

### Plan Structure Validation

#### `sce validation validate-plan --total-weeks --goal-type --phases --weekly-volumes --recovery-weeks --race-week`

Validate training plan structure for common errors.

**Usage:**

```bash
sce validation validate-plan \
    --total-weeks 20 \
    --goal-type half_marathon \
    --phases phases.json \
    --weekly-volumes volumes.json \
    --recovery-weeks recovery.json \
    --race-week 20
```

**Input JSON Format (phases.json):**

```json
{
  "base": 8,
  "build": 8,
  "peak": 2,
  "taper": 2
}
```

**Input JSON Format (volumes.json):**

```json
[25, 27, 29, 22, 31, 33, 35, 28, 37, 40, 43, 35, 46, 50, 54, 43, 60, 58, 35, 20]
```

**Input JSON Format (recovery.json):**

```json
[4, 8, 12, 16]
```

**Checks Performed:**

- **Phase duration**: Base/build/peak/taper weeks appropriate for goal type
- **Volume progression**: Average weekly increase ≤10% (10% rule)
- **Peak placement**: Peak week 2-3 weeks before race
- **Recovery frequency**: Recovery weeks every 3-4 weeks
- **Taper structure**: Gradual volume reduction (70%, 50%, 30% for 3-week taper)

**Returns:** Total weeks, goal type, phase duration checks (appropriate/issue per phase), volume progression check (safe/avg_increase_pct), peak placement check (appropriate/weeks_before_race), recovery week check (appropriate/frequency), taper structure check (appropriate/week_reductions), violations, overall_quality_score (0-100), recommendations.

**Example Response:**

```json
{
  "ok": true,
  "data": {
    "total_weeks": 20,
    "goal_type": "half_marathon",
    "overall_quality_score": 60,
    "violations": [
      {
        "type": "PEAK_PHASE_TOO_SHORT",
        "severity": "MODERATE",
        "message": "Peak phase (2 weeks) below recommended minimum (3 weeks)",
        "recommendation": "Extend peak phase to 3-5 weeks for half_marathon"
      }
    ],
    "volume_progression_check": {
      "safe": true,
      "avg_weekly_increase_pct": 7.2
    }
  }
}
```

---

### Goal Feasibility Assessment

#### `sce validation assess-goal --goal-type --goal-time --goal-date --current-ctl [--current-vdot] [--vdot-for-goal]`

Assess goal feasibility based on VDOT and CTL.

**Usage:**

```bash
sce validation assess-goal \
    --goal-type half_marathon \
    --goal-time "1:30:00" \
    --goal-date "2026-06-01" \
    --current-vdot 48 \
    --current-ctl 44.0 \
    --vdot-for-goal 52
```

**Goal Time Format:** `HH:MM:SS` or `MM:SS`

**Returns:** Goal description, current fitness (vdot/ctl/equivalent_race_time), goal fitness needed (vdot_for_goal/vdot_gap/ctl_recommended), time available (weeks_until_race/typical_duration/sufficient), feasibility_verdict (VERY_REALISTIC/REALISTIC/AMBITIOUS_BUT_REALISTIC/AMBITIOUS/UNREALISTIC), feasibility_analysis (vdot_improvement_pct/months_needed/buffer/limiting_factor), confidence_level (HIGH/MODERATE/LOW), recommendations, alternative_scenarios, warnings.

**Example Response:**

```json
{
  "ok": true,
  "data": {
    "goal": "Half Marathon 1:30:00 on 2026-06-01",
    "feasibility_verdict": "REALISTIC",
    "confidence_level": "MODERATE",
    "current_fitness": {
      "vdot": 48,
      "ctl": 44.0
    },
    "goal_fitness_needed": {
      "vdot_for_goal": 52,
      "vdot_gap": 4,
      "ctl_recommended": 50.0
    },
    "time_available": {
      "weeks_until_race": 20,
      "sufficient": true
    },
    "feasibility_analysis": {
      "vdot_improvement_pct": 8.3,
      "months_needed": 2.7,
      "months_available": 4.6,
      "buffer": 1.9
    },
    "recommendations": [
      "Current VDOT: 48 → Goal VDOT: 52 (requires 4 point gain)",
      "Build CTL from 44 to 50 over 20 weeks"
    ]
  }
}
```

---
