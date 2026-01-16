# VDOT-Based Performance Prediction

Using VDOT to predict race performance and set realistic goals.

---

## How to Use VDOT Predictions

**CLI command**:
```bash
# Athlete ran 42:30 (10K), predict half marathon
sce vdot predict --race-type 10k --time 42:30 --goal-race half_marathon
```

**Returns**:
```json
{
  "vdot": 48,
  "equivalent_times": {
    "5k": "20:45",
    "10k": "42:30",
    "half_marathon": "1:32:30",
    "marathon": "3:12:00"
  }
}
```

---

## Use Cases

**1. Set realistic race goals**:
Compare predicted time to athlete's goal. If goal is significantly faster than prediction, it's a stretch goal.

**2. Validate goal times**:
Is 1:30:00 half marathon realistic with VDOT 48? → Prediction is 1:32:30, so 1:30:00 is ambitious (2:30 faster).

**3. Adjust pacing if fitness changed**:
If CTL improved since last race, predictions may be conservative. If CTL dropped, predictions may be optimistic.

---

## Important Assumptions

VDOT predictions assume:
- **Proper taper** (TSB +5 to +15)
- **Good race day conditions** (mild weather, flat course)
- **Athlete trained for target distance** (adequate long run preparation)

---

## When to Adjust Expectations

**Adjust predictions if**:
- Taper execution poor (TSB <+5) → Add 10-30 seconds/km
- Extreme conditions (heat, wind, hilly course) → Use `sce vdot adjust`
- Athlete under-trained for distance (e.g., VDOT from 10K but limited long run experience for marathon) → Be conservative
