# VDOT Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Commands for VDOT calculation, training pace zones, race predictions, and pace adjustments for environmental conditions.

**Commands in this category:**
- `sce vdot calculate` - Calculate VDOT from race performance
- `sce vdot paces` - Generate training pace zones from VDOT
- `sce vdot predict` - Predict equivalent race times for other distances
- `sce vdot six-second` - Apply six-second rule for novice runners
- `sce vdot adjust` - Adjust pace for environmental conditions
- `sce vdot estimate-current` - Estimate current VDOT from workouts

---

## sce vdot calculate

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

## sce vdot paces

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

## sce vdot predict

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

## sce vdot six-second

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

## sce vdot adjust

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

## sce vdot estimate-current

Estimate current VDOT from recent tempo and interval workouts.

---

**Navigation**: [Back to Index](index.md) | [Previous: Profile Commands](cli_profile.md) | [Next: Guardrails Commands](cli_guardrails.md)
