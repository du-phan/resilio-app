# Volume Progression Quick Reference

Safe volume progression prevents injury while building fitness. Based on Pfitzinger's 10% rule and CTL-based starting volumes.

## Starting Volume (CTL-Based)

### CTL to Weekly Volume Conversion

| CTL Range | Zone        | Safe Starting Volume | Typical Weekly Mileage    |
|-----------|-------------|---------------------|---------------------------|
| < 20      | Beginner    | 15-25 km/week       | 3-4 runs, mostly easy     |
| 20-35     | Recreational| 25-40 km/week       | 4-5 runs, 1 quality       |
| 35-50     | Competitive | 40-60 km/week       | 5-6 runs, 2 quality       |
| 50-70     | Advanced    | 60-80 km/week       | 6-7 runs, 2-3 quality     |
| > 70      | Elite       | 80-120 km/week      | 7-14 runs, 3-4 quality    |

**Command**:
```bash
sce guardrails safe-volume --ctl 44 --goal-type half_marathon
```

**Returns**:
- Recommended start: CTL-based safe volume
- Peak volume: Race-specific target
- Progression plan: How to get from start to peak

**Rule**: Start at current capacity (CTL equivalent), not aspirational volume

---

## The 10% Rule

### Standard Progression
**Increase weekly volume by no more than 10% per week**

**Example**:
- Week 1: 40 km
- Week 2: 44 km (+10%)
- Week 3: 48 km (+10%)
- Week 4: 34 km (recovery week, 70% of week 3)
- Week 5: 52 km (+10% from week 3)

**Validation**:
```bash
sce guardrails progression --previous 40 --current 48
```

**Returns**: `ok: true/false`, safe maximum, violation warnings

### Recovery Week Exception
- Every 4th week: Reduce to 70% of previous week
- Next buildup week: Increase from week 3 baseline (not recovery week)

**Example**:
- Week 3: 48 km
- Week 4: 34 km (recovery, 70%)
- Week 5: 52 km (+10% from week 3's 48 km, NOT from week 4's 34 km)

---

## Phase-Specific Volume Targets

### Base Phase
**Goal**: Build aerobic foundation
**Progression**: +5-10% per week
**Peak**: 80-90% of planned peak volume
**CTL gain**: +2-4 points per week

**Example (half marathon, 20-week plan)**:
- Starting CTL: 40 (40 km/week equivalent)
- Base phase: Weeks 1-10
- Week 1: 40 km
- Week 5: 52 km (+30% over 5 weeks = +6%/week average)
- Week 10: 60 km (approaching peak volume)

### Build Phase
**Goal**: Add intensity while maintaining volume
**Progression**: +0-5% per week (slower due to intensity)
**Peak**: 90-100% of planned peak volume
**CTL gain**: +1-2 points per week

**Example (half marathon)**:
- Build phase: Weeks 11-16
- Week 11: 60 km
- Week 16: 65 km (holding steady, intensity increasing)

### Peak Phase
**Goal**: Maximum training load
**Progression**: Hold volume (no increase)
**Peak**: 100% of planned peak volume
**CTL gain**: 0-1 points per week

**Example (half marathon)**:
- Peak phase: Weeks 17-18
- Week 17: 65 km
- Week 18: 65 km (maintain load)

### Taper Phase
**Goal**: Reduce fatigue, maintain fitness
**Progression**: -20-30% per week
**Volume**: Progressive reduction to 40% of peak
**CTL drop**: -2 to -4 points total (acceptable)

**Example (half marathon)**:
- Taper phase: Weeks 19-20
- Week 19: 46 km (70% of peak)
- Week 20: 26 km (40% of peak, race week)

---

## Volume Limits by Distance

### 10K Training
- **Minimum**: 30 km/week (effective training)
- **Optimal**: 50-70 km/week (competitive)
- **Maximum**: 90 km/week (diminishing returns)

### Half Marathon Training
- **Minimum**: 40 km/week (finish comfortably)
- **Optimal**: 60-80 km/week (competitive)
- **Maximum**: 110 km/week (advanced/elite)

### Marathon Training
- **Minimum**: 55 km/week (survival)
- **Optimal**: 80-110 km/week (competitive)
- **Maximum**: 150+ km/week (elite only)

**Command**:
```bash
sce guardrails safe-volume --ctl 44 --goal-type half_marathon
```

---

## Long Run Progression

### Long Run Caps
- **Duration**: ≤2.5 hours (injury prevention)
- **% of weekly volume**: ≤25-30% (balance)
- **Frequency**: Once per week (7 days recovery)

**Validation**:
```bash
sce guardrails long-run --duration 150 --weekly-volume 60 --pct-limit 30
```

**Returns**: Violations if duration >150 min or >30% of volume

### Long Run Buildup
- Increase 10-15 minutes every 2-3 weeks
- Recovery week: Reduce 20-30%
- Peak: 2-2.5 hours (race-dependent)

**Example (half marathon)**:
- Week 1: 90 min
- Week 3: 105 min (+15 min)
- Week 4: 75 min (recovery)
- Week 5: 120 min (+15 min from week 3)
- Week 7: 135 min (+15 min)
- Week 10: 150 min (peak, hold here)

---

## Multi-Sport Volume Adjustments

### Running PRIMARY
- Standard volume progression (10% rule applies)
- Other sports supplement (don't count toward running volume)

### Running EQUAL
- Reduce running volume by 20-30%
- Account for systemic load from other sports
- Example: 50 km running + 3 climbing sessions = ~70 km running-equivalent

### Running SECONDARY
- Minimal volume (20-30 km/week maintenance)
- No progressive buildup (maintain base fitness)

**Use systemic load** (not just running km) for ACWR calculations:
```bash
sce analysis load --activities activities.json --days 7 --priority equal
```

---

## Unproven Capacity Risk

**Definition**: Training volume significantly exceeding historical maximum

**Risk**: Injury, overtraining when jumping to unfamiliar volume

**Check**:
```bash
sce analysis capacity --activities activities.json --planned-volume 70
```

**Returns**:
- `historical_max`: Highest sustained weekly volume in last 120 days
- `capacity_utilization`: Planned vs. historical (%)
- `exceeds_proven_capacity`: Boolean
- `risk_assessment`: Low/moderate/high

**Mitigation**:
- If planned volume >120% of historical max → high risk
- Either: Extend plan duration (more gradual buildup)
- Or: Reduce peak volume target

**Example**:
- Historical max: 50 km/week
- Planned peak: 75 km/week (150% of max)
- Risk: HIGH
- Solution: Cap peak at 60 km (120% of max) OR extend base phase +4 weeks

---

## Age-Adjusted Progression (Masters 45+)

### Slower Progression
- **Under 45**: +10% per week
- **45-54**: +7-8% per week
- **55-64**: +5-7% per week
- **65+**: +3-5% per week

**Rationale**: Recovery capacity decreases with age

### More Frequent Recovery Weeks
- **Under 45**: Every 4th week
- **45-54**: Every 3rd week
- **55+**: Every 2-3rd week

**Command**:
```bash
sce guardrails masters-recovery --age 52
```

**Returns**: Age-specific recovery recommendations

---

## Quality Volume Limits (Daniels)

**Hard running must be capped** to prevent injury:

| Intensity | Daniels Limit | Example (50 km/week) |
|-----------|---------------|---------------------|
| T-pace    | ≤10% of weekly volume | ≤5 km |
| I-pace    | ≤8% of weekly volume  | ≤4 km |
| R-pace    | ≤5% of weekly volume  | ≤2.5 km |

**Validation**:
```bash
sce guardrails quality-volume --t-pace 6.0 --i-pace 4.0 --r-pace 2.0 --weekly-volume 50.0
```

**Returns**: Violations if any intensity exceeds limits

**Why this matters**: Excessive quality work → injury, even if total volume is safe

---

## Common Progression Mistakes

1. **Jumping volume**: 30 km → 50 km in one week (+67%) → ACWR spike
2. **No recovery weeks**: 8+ weeks of continuous buildup → overtraining
3. **Long run too long**: 40% of weekly volume → disproportionate fatigue
4. **Ignoring historical max**: Planning 80 km peak when never exceeded 55 km
5. **Quality volume exceeded**: 12 km T-pace in a 40 km week (30%, should be ≤10%)

---

## Volume Progression Commands

```bash
# Check safe starting volume
sce guardrails safe-volume --ctl 44 --goal-type half_marathon

# Validate weekly progression
sce guardrails progression --previous 40 --current 48

# Validate long run
sce guardrails long-run --duration 135 --weekly-volume 55 --pct-limit 30

# Validate quality volume
sce guardrails quality-volume --t-pace 5.0 --i-pace 4.0 --r-pace 2.0 --weekly-volume 50.0

# Check capacity risk
sce analysis capacity --activities activities.json --planned-volume 70
```

---

## Deep Dive Resources

For complete volume progression methodology:
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md) - Pfitzinger's volume progressions
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md) - Quality volume limits
- [CLI Reference - Guardrails](../../../docs/coaching/cli_reference.md#guardrails-commands)
