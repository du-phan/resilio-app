# Risk Assessment Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Holistic injury risk analysis and training stress forecasting.

**Commands in this category:**
- `sce risk assess` - Multi-factor injury risk assessment
- `sce risk recovery-window` - Estimate recovery timeline
- `sce risk forecast` - Project CTL/ATL/TSB 1-4 weeks ahead
- `sce risk taper-status` - Verify taper progression

---

## sce risk assess

Multi-factor injury risk assessment combining ACWR, readiness, TSB, and recent load.

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

**Returns:** Overall risk level (low/moderate/high/danger), injury probability (%), contributing factors with weights, recommended action, risk mitigation options, rationale.

---

## sce risk recovery-window

Estimate recovery timeline to return to safe training zones.

**Usage:**

```bash
sce risk recovery-window --trigger ACWR_ELEVATED \
    --value 1.35 --threshold 1.3
```

**Valid triggers:** `ACWR_ELEVATED`, `TSB_OVERREACHED`, `READINESS_LOW`, `LOWER_BODY_SPIKE`

**Returns:** Min/typical/max recovery days, day-by-day recovery checklist with actions and checks, monitoring metrics.

---

## sce risk forecast

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

## sce risk taper-status

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

**Navigation**: [Back to Index](index.md) | [Previous: Analysis Commands](cli_analysis.md) | [Next: Validation Commands](cli_validation.md)
