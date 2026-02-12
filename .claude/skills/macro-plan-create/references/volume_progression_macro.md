# Volume Progression - Macro Planning

Strategic volume planning for 16-week training plans. Establishes starting point, peak volume, and phase progression rates.

---

## Starting Volume (CTL-Based)

| CTL Range | Zone        | Safe Starting Volume | Typical Weekly Mileage    |
|-----------|-------------|---------------------|---------------------------|
| < 20      | Beginner    | 15-25 km/week       | 3-4 runs, mostly easy     |
| 20-35     | Recreational| 25-40 km/week       | 4-5 runs, 1 quality       |
| 35-50     | Competitive | 40-60 km/week       | 5-6 runs, 2 quality       |
| 50-70     | Advanced    | 60-80 km/week       | 6-7 runs, 2-3 quality     |
| > 70      | Elite       | 80-120 km/week      | 7-14 runs, 3-4 quality    |

**Command**:
```bash
resilio guardrails safe-volume --ctl 44 --goal-type half_marathon
```

**Returns**: Recommended start (CTL-based), peak volume (race-specific), progression plan.

**Rule**: Start at current capacity (CTL equivalent), not aspirational volume.

---

## Minimum Weekly Volume by Run Frequency

**Problem**: Not all volume targets achievable with given run frequency due to minimum workout duration guardrails.

### Formula

For **N runs per week** (at least one long run):

```
Minimum Weekly Volume = (N - 1) × [Easy Run Min] + [Long Run Min]
```

**Standard minimums**:
- Easy run: 5 km (30 min)
- Long run: 8 km (60 min)

**Examples**:
- **3 runs/week**: (3-1) × 5 + 8 = **18 km minimum**
- **4 runs/week**: (4-1) × 5 + 8 = **23 km minimum**
- **5 runs/week**: (5-1) × 5 + 8 = **28 km minimum**
- **6 runs/week**: (6-1) × 5 + 8 = **33 km minimum**

### Profile-Aware Adjustments

If profile includes workout patterns (from `resilio profile analyze`):
- Easy run minimum = 80% of `typical_easy_distance_km`
- Long run minimum = 80% of `typical_long_run_distance_km`

**Example**: Athlete typically runs 7km easy, 12km long → Minimums: 5.6km easy, 9.6km long → 4 runs/week requires 26.4km (not generic 23km).

### Constraint Satisfaction

**Scenario 1: Target below minimum**
```
Problem: 22 km target with 4 runs/week
Minimum: 23 km for 4 runs
Options:
  A) Reduce to 3 runs/week (18 km min, 22 km achievable) ✓
  B) Increase target to 26 km
Recommendation: Option A
```

**Scenario 2: Target barely above minimum**
```
Problem: 24 km with 4 runs/week (23 km min)
Risk: No flexibility, all runs at absolute minimums (3×5 + 1×9 = 24)
Options:
  A) Reduce to 3 runs (more realistic: 2×6 + 1×12) ✓
  B) Increase to 28-30 km
Recommendation: Option A
```

**Scenario 3: Target well above minimum**
```
Problem: 35 km with 4 runs/week (23 km min)
Distribution: 3×8 + 1×11 = 35 km ✓
Result: All runs above minimums, realistic lengths
→ ACCEPTABLE
```

### Validation

```bash
resilio guardrails safe-volume --ctl 44 --recent-volume 22 --run-days-per-week 4
# Warns if 22 km < 23 km minimum for 4 runs
```

### Prevention

1. Calculate minimums before setting run frequency
2. Use profile-aware minimums when available: `resilio profile analyze`
3. Prefer frequency reduction over unrealistic run lengths (better: 3 runs with realistic lengths than 4 runs at minimums)

---

## Phase-Specific Volume Targets

### Base Phase
**Goal**: Build aerobic foundation
**Progression**: +5-10%/week
**Peak**: 80-90% of planned peak
**CTL gain**: +2-4 points/week

### Build Phase
**Goal**: Add intensity while maintaining volume
**Progression**: +0-5%/week (slower due to intensity)
**Peak**: 90-100% of planned peak
**CTL gain**: +1-2 points/week

### Peak Phase
**Goal**: Maximum training load
**Progression**: Hold volume (0% increase)
**Peak**: 100% of planned peak
**CTL gain**: 0-1 points/week

### Taper Phase
**Goal**: Reduce fatigue, maintain fitness
**Progression**: -20-30%/week
**Volume**: Progressive reduction to 40% of peak
**CTL drop**: -2 to -4 points total (acceptable)

**Example (half marathon, 16 weeks)**:
- Base (Weeks 1-7): 32 → 52 km
- Build (Weeks 8-12): 52 → 58 km
- Peak (Weeks 13-14): 58 km (hold)
- Taper (Weeks 15-16): 41 → 23 km

---

## Volume Limits by Distance

### 10K Training
- **Minimum**: 30 km/week (effective)
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

**Command**: `resilio guardrails safe-volume --ctl 44 --goal-type half_marathon`

---

## Multi-Sport Volume Adjustments

### Running PRIMARY
- Standard progression (10% rule)
- Other sports supplement (don't count toward running volume)

### Running EQUAL
- Reduce running volume 20-30%
- Account for systemic load from other sports
- Example: 50km running + 3 climbing sessions ≈ 70km running-equivalent

### Running SECONDARY
- Minimal volume (20-30 km/week maintenance)
- No progressive buildup

**Use systemic load** (not just running km) for macro planning with multi-sport athletes.

---

## Unproven Capacity Risk

**Definition**: Volume significantly exceeding historical maximum.

**Check**:
```bash
resilio analysis capacity --activities activities.json --planned-volume 70
```

**Returns**: `historical_max`, `capacity_utilization`, `exceeds_proven_capacity`, `risk_assessment`.

**Mitigation**: If planned >120% of historical max → high risk.
- Option 1: Cap peak at 120% of max
- Option 2: Extend base phase for gradual buildup

**Example**:
- Historical max: 50 km/week
- Planned peak: 75 km (150% of max) → HIGH RISK
- Solution: Cap at 60 km (120%) OR extend base +4 weeks

---

## Age-Adjusted Progression (Masters 45+)

### Slower Progression
- **Under 45**: +10%/week
- **45-54**: +7-8%/week
- **55-64**: +5-7%/week
- **65+**: +3-5%/week

**Rationale**: Recovery capacity decreases with age.

### More Frequent Recovery
- **Under 45**: Every 4th week
- **45-54**: Every 3rd week
- **55+**: Every 2-3rd week

**Command**: `resilio guardrails masters-recovery --age 52`

---

## Macro Planning Commands

```bash
# Safe starting volume
resilio guardrails safe-volume --ctl 44 --goal-type half_marathon

# Validate run frequency vs. volume
resilio guardrails safe-volume --ctl 44 --recent-volume 22 --run-days-per-week 4

# Check capacity risk
resilio analysis capacity --activities activities.json --planned-volume 70

# Age-adjusted recovery planning
resilio guardrails masters-recovery --age 52
```

---

## Deep Dive Resources

- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md) - Pfitzinger volume progressions
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md) - Quality volume limits
- [Guardrails Commands](../../../docs/coaching/cli/cli_guardrails.md) - Full CLI reference
