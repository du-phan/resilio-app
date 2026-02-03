# Metrics & Status Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Commands to get current training metrics, weekly summaries, and daily workout recommendations.

**Commands in this category:**
- `sce status` - Get current training metrics with interpretations
- `sce week` - Get weekly summary with planned vs completed activities
- `sce today` - Get today's workout recommendation with full context

---

## sce status

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
      "interpretation": "stable training load"
    },
    "readiness": {
      "score": 68,
      "level": "moderate",
      "breakdown": {
        "tsb_contribution": 15,
        "load_trend_contribution": 20
      }
    }
  }
}
```

**Key Metrics:**

- **CTL** (Chronic Training Load): 42-day fitness
- **ATL** (Acute Training Load): 7-day fatigue
- **TSB** (Training Stress Balance): CTL - ATL, represents form
- **ACWR** (Acute:Chronic Workload Ratio): Load spike indicator
- **Readiness**: 0-100 composite score

---

## sce week

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

## sce today

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

**Navigation**: [Back to Index](index.md) | [Previous: Activity Commands](cli_activity.md) | [Next: Planning Commands](cli_planning.md)
