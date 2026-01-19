# Validation Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Validate interval structure, plan structure, and goal feasibility.

**Commands in this category:**
- `sce validation validate-intervals` - Validate interval workout structure per Daniels methodology
- `sce validation validate-plan` - Validate training plan structure
- `sce validation assess-goal` - Assess goal feasibility based on VDOT and CTL

---

## sce validation validate-intervals

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

---

## sce validation validate-plan

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

**Returns:** Total weeks, goal type, phase duration checks, volume progression check, peak placement check, recovery week check, taper structure check, violations, overall_quality_score (0-100), recommendations.

---

## sce validation assess-goal

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

**Navigation**: [Back to Index](index.md) | [Previous: Risk Commands](cli_risk.md)
