# Volume Progression Quick Reference

Safe volume progression prevents injury while building fitness. Based on Pfitzinger's 10% rule and CTL-based starting volumes.

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
sce guardrails safe-volume --ctl 44 --goal-type half_marathon
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

If profile includes workout patterns (from `sce profile analyze`):
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
sce guardrails safe-volume --ctl 44 --recent-volume 22 --run-days-per-week 4
# Warns if 22 km < 23 km minimum for 4 runs
```

### Prevention

1. Calculate minimums before setting run frequency
2. Use profile-aware minimums when available: `sce profile analyze`
3. Prefer frequency reduction over unrealistic run lengths (better: 3 runs with realistic lengths than 4 runs at minimums)

---

## Interpreting Progression Context (AI Coaching Judgment)

### Philosophy: CLI Provides Context, AI Coach Decides

`sce guardrails analyze-progression` provides **rich context**, not pass/fail. You interpret using training methodology.

**Command**:
```bash
sce guardrails analyze-progression --previous 15 --current 20 --ctl 27 --run-days 4 --age 32
```

**Returns**:
- Volume classification (low/medium/high)
- Traditional 10% rule (reference only)
- Absolute load analysis (Pfitzinger per-session guideline)
- CTL capacity context
- Risk factors (injury, age, large % increase)
- Protective factors (small absolute load, adequate capacity)
- Coaching considerations

### Volume Classification

**Low Volume (<25km)**:
- **Primary risk**: Absolute load per session
- **Flexibility**: Higher % increases OK if absolute load manageable
- **Key metric**: Per-session increase (<1.6km per Pfitzinger)
- **Decision**: Accept if within Pfitzinger guideline, even if % high

**Example**: 15→20km (+33%) acceptable because:
- Per-session increase 1.25km (within 1.6km guideline)
- Small absolute increase (5km total)
- Low volume means small absolute loads manageable

**Medium Volume (25-50km)**:
- **Primary risk**: Both absolute and cumulative load
- **Flexibility**: Moderate - balance % and absolute increases
- **Decision**: Consider both Pfitzinger guideline AND 10% rule

**High Volume (≥50km)**:
- **Primary risk**: Cumulative load
- **Flexibility**: Limited - adhere to 10% rule
- **Key concern**: Large absolute increases (>10km) significantly increase injury risk

**Example**: 60→75km (+25%) should be rejected because:
- Per-session increase 3.75km (exceeds 1.6km guideline)
- Large absolute increase (15km)
- High volume amplifies cumulative stress
- Recommend: 66km (10% increase)

### Risk vs. Protective Factors

**Weigh factors**:
- **Risk**: Recent injury, masters age, large % increase
- **Protective**: Low volume, small absolute load, adequate CTL capacity, within Pfitzinger guideline

**Decision rule**: Accept when protective factors outweigh risk factors.

**Example - Accept despite high %**:
```json
{
  "increase_pct": 33.3,
  "risk_factors": ["Large percentage increase"],
  "protective_factors": [
    "Low volume with small absolute increase",
    "Within Pfitzinger per-session guideline (1.25km < 1.6km)",
    "Target within CTL capacity (20km in 25-40km range)"
  ]
}
```
→ **ACCEPT**: 3 strong protective factors outweigh 1 risk factor.

**Example - Reject despite moderate %**:
```json
{
  "increase_pct": 15.0,
  "risk_factors": [
    "Recent injury (<90 days)",
    "Masters athlete (age 55)"
  ],
  "protective_factors": []
}
```
→ **MODIFY**: 2 moderate risks with no protective factors → be conservative.

### CTL Capacity

**Within capacity** (`target_within_capacity: true`): Strong protective factor, fitness supports volume.

**Outside capacity** (`target_within_capacity: false`): Warning flag (not automatic rejection).
- **Below**: Acceptable (conservative start or detraining)
- **Above**: Requires strong justification

**Example - Above capacity**:
```json
{
  "current_volume_km": 50.0,
  "ctl": 27.0,
  "ctl_based_capacity_km": [25, 40]
}
```
→ 50km exceeds 40km capacity limit (needs strong protective factors or adjustment).

### Decision Framework

1. Check volume classification (low/medium/high)
2. Identify primary risk (absolute vs. cumulative load)
3. Count protective vs. risk factors
4. Apply volume-specific rule:
   - **Low**: Accept if within Pfitzinger guideline
   - **Medium**: Balance both metrics
   - **High**: Be conservative, prioritize 10% rule
5. Consider athlete context (CTL, injury, age)
6. Provide clear rationale

**Example Decision - Accept**:
"Your 15→20km progression is 33%, exceeding the traditional 10% rule. However, at low volumes, absolute load per session matters more. Your per-session increase is 1.25km (within Pfitzinger's 1.6km guideline), and your CTL of 27 supports this volume. I'm accepting this progression."

**Example Decision - Modify**:
"Your 60→75km progression is too aggressive. The 15km absolute increase and 3.75km per-session increase both exceed safe guidelines. At 60km weekly volume, cumulative load stress is the primary risk. Reduce to 66km (10% increase)."

---

## The 10% Rule

**Standard progression**: Increase weekly volume ≤10% per week.

**Example**:
- Week 1: 40 km
- Week 2: 44 km (+10%)
- Week 3: 48 km (+10%)
- Week 4: 34 km (recovery, 70%)
- Week 5: 52 km (+10% from week 3, NOT week 4)

**Command**:
```bash
sce guardrails progression --previous 40 --current 48
```

**Recovery exception**: Every 4th week at 70%. Next buildup increases from pre-recovery baseline.

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

**Example (half marathon, 20 weeks)**:
- Base (Weeks 1-10): 40 → 60 km
- Build (Weeks 11-16): 60 → 65 km
- Peak (Weeks 17-18): 65 km (hold)
- Taper (Weeks 19-20): 46 → 26 km

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

**Command**: `sce guardrails safe-volume --ctl 44 --goal-type half_marathon`

---

## Long Run Progression

### Caps
- **Duration**: ≤2.5 hours (injury prevention)
- **% of weekly volume**: ≤25-30%
- **Frequency**: Once per week (7 days recovery)

**Command**:
```bash
sce guardrails long-run --duration 150 --weekly-volume 60 --pct-limit 30
```

### Buildup
- Increase 10-15 minutes every 2-3 weeks
- Recovery week: Reduce 20-30%
- Peak: 2-2.5 hours (race-dependent)

**Example (half marathon)**:
- Week 1: 90 min
- Week 3: 105 min (+15)
- Week 4: 75 min (recovery)
- Week 5: 120 min (+15 from week 3)
- Week 7: 135 min (+15)
- Week 10: 150 min (peak, hold)

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

**Use systemic load** (not just running km) for ACWR:
```bash
sce analysis load --activities activities.json --days 7 --priority equal
```

---

## Unproven Capacity Risk

**Definition**: Volume significantly exceeding historical maximum.

**Check**:
```bash
sce analysis capacity --activities activities.json --planned-volume 70
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

**Command**: `sce guardrails masters-recovery --age 52`

---

## Quality Volume Limits (Daniels)

Hard running must be capped:

| Intensity | Daniels Limit | Example (50 km/week) |
|-----------|---------------|---------------------|
| T-pace    | ≤10% of weekly volume | ≤5 km |
| I-pace    | ≤8% of weekly volume  | ≤4 km |
| R-pace    | ≤5% of weekly volume  | ≤2.5 km |

**Command**:
```bash
sce guardrails quality-volume --t-pace 6.0 --i-pace 4.0 --r-pace 2.0 --weekly-volume 50.0
```

**Why**: Excessive quality work → injury, even if total volume safe.

---

## Common Progression Mistakes

1. **Jumping volume**: 30 → 50 km in one week (+67%) → ACWR spike
2. **No recovery weeks**: 8+ weeks continuous buildup → overtraining
3. **Long run too long**: 40% of weekly volume → disproportionate fatigue
4. **Ignoring historical max**: Planning 80 km peak when never exceeded 55 km
5. **Quality volume exceeded**: 12 km T-pace in 40 km week (30%, should be ≤10%)

---

## Volume Progression Commands

```bash
# Safe starting volume
sce guardrails safe-volume --ctl 44 --goal-type half_marathon

# Validate weekly progression
sce guardrails progression --previous 40 --current 48

# Context-aware progression analysis
sce guardrails analyze-progression --previous 15 --current 20 --ctl 27 --run-days 4

# Validate long run
sce guardrails long-run --duration 135 --weekly-volume 55 --pct-limit 30

# Validate quality volume
sce guardrails quality-volume --t-pace 5.0 --i-pace 4.0 --weekly-volume 50.0

# Check capacity risk
sce analysis capacity --activities activities.json --planned-volume 70

# Age-adjusted recovery
sce guardrails masters-recovery --age 52
```

---

## Deep Dive Resources

- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md) - Pfitzinger volume progressions
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md) - Quality volume limits
- [Guardrails Commands](../../../docs/coaching/cli/cli_guardrails.md) - Full CLI reference
