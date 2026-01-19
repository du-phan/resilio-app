# Analysis Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Weekly insights and multi-sport load distribution analysis.

**Commands in this category:**
- `sce analysis adherence` - Compare planned vs actual training
- `sce analysis intensity` - Validate 80/20 rule compliance
- `sce analysis gaps` - Detect training breaks with CTL impact
- `sce analysis load` - Analyze systemic and lower-body load distribution
- `sce analysis capacity` - Validate planned volume against proven capacity

---

## sce analysis adherence

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

**Returns:** Completion rate, load variance (planned vs actual), workout type adherence breakdown, detected patterns, recommendations.

---

## sce analysis intensity

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

**Returns:** Distribution percentages (low/moderate/high), compliance level, polarization score (0-100), violations, recommendations.

---

## sce analysis gaps

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
  { "date": "2025-11-28", "ctl": 22.0, "notes": "Return from injury" }
]
```

**Returns:** Detected gaps (start/end dates, duration, CTL impact), potential causes (injury/illness detected from notes), recovery status, patterns, recommendations.

---

## sce analysis load

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
  }
]
```

**Returns:** Systemic/lower-body load by sport (AU + percentages), total loads, sport priority adherence, fatigue risk flags, recommendations.

---

## sce analysis capacity

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

**Navigation**: [Back to Index](index.md) | [Previous: Guardrails Commands](cli_guardrails.md) | [Next: Risk Commands](cli_risk.md)
