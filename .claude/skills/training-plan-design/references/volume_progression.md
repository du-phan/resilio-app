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

## Minimum Weekly Volume by Run Frequency

**Problem**: Not all weekly volume targets are achievable with a given number of runs per week due to minimum workout duration guardrails.

### Minimum Volume Formula

For **N runs per week** (where at least one is a long run):

```
Minimum Weekly Volume = (N - 1) × [Easy Run Minimum] + [Long Run Minimum]
```

**Standard minimums**:
- Easy run: 5 km (30 minutes)
- Long run: 8 km (60 minutes)

**Examples**:
- **3 runs/week**: (3-1) × 5 + 8 = **18 km minimum**
- **4 runs/week**: (4-1) × 5 + 8 = **23 km minimum**
- **5 runs/week**: (5-1) × 5 + 8 = **28 km minimum**
- **6 runs/week**: (6-1) × 5 + 8 = **33 km minimum**

### Profile-Aware Adjustments

If athlete's profile includes workout pattern fields (from `sce profile analyze`):
- Use 80% of `typical_easy_distance_km` as easy run minimum
- Use 80% of `typical_long_run_distance_km` as long run minimum

**Example**:
```
Athlete typical patterns (from profile):
  - typical_easy_distance_km: 7.0 km
  - typical_long_run_distance_km: 12.0 km

Adjusted minimums:
  - Easy run: 7.0 × 0.80 = 5.6 km
  - Long run: 12.0 × 0.80 = 9.6 km

For 4 runs/week:
  Minimum = (4-1) × 5.6 + 9.6 = 26.4 km (not the generic 23 km)
```

### Constraint Satisfaction Scenarios

**Scenario 1: Target volume below minimum**
```
Problem: 22 km target with 4 runs/week
Minimum: 23 km for 4 runs
Discrepancy: -1 km (-4.3%)

Options:
  A) Reduce to 3 runs/week (18 km minimum, 22 km achievable)
  B) Increase target to 26 km (accommodate 4 runs comfortably)

Recommendation: Option A (frequency matters less than sustainable volume)
```

**Scenario 2: Target volume barely above minimum**
```
Problem: 24 km target with 4 runs/week
Minimum: 23 km for 4 runs
Margin: +1 km (+4.3%)

Risk: Very tight constraint, no flexibility for workout adjustments
Result: All runs at absolute minimums (3×5 km + 1×9 km = 24 km)
  → No room for progression within week
  → Unrealistic (no athlete runs exactly 5.0 km every time)

Options:
  A) Reduce to 3 runs/week (more realistic distribution: 2×6 km + 1×12 km)
  B) Increase target to 28-30 km (comfortable 4-run distribution)

Recommendation: Option A (better balance, realistic run lengths)
```

**Scenario 3: Target volume well above minimum**
```
Problem: 35 km target with 4 runs/week
Minimum: 23 km for 4 runs
Margin: +12 km (+52%)

Distribution example: 3×8 km + 1×11 km = 35 km ✓
  → All runs above minimums
  → Realistic individual run lengths
  → Room for adjustment if needed

Result: ACCEPTABLE, proceed with plan
```

### Validation Command

The `safe-volume` CLI command should warn when target volume conflicts with run frequency:

```bash
sce guardrails safe-volume \
  --ctl 44 \
  --goal-type half_marathon \
  --recent-volume 22 \
  --run-days-per-week 4

# Should return warning if 22 km < 23 km minimum for 4 runs:
{
  "recommended_start_km": 20,
  "recommended_peak_km": 55,
  "warning": "Target 22 km with 4 run days is below minimum (23 km). Suggest: 3 run days OR 26 km target."
}
```

### Common Mistakes

**Mistake 1: Ignoring minimum constraints**
```
Bad: Week 3, 21 km target, 4 runs prescribed
  → System cannot satisfy: (3×5 + 8) = 23 km > 21 km target
  → Validation failure, requires regeneration

Good: Week 3, 21 km target, 3 runs prescribed
  → Distribution: 2×6 km + 1×9 km = 21 km ✓
```

**Mistake 2: Using minimums as actual run lengths**
```
Bad: 4 runs at minimums (3×5 km + 1×8 km = 23 km)
  → Unrealistic (too short for most athletes)
  → No margin for natural variation

Good: 4 runs with comfortable lengths (3×7 km + 1×11 km = 32 km)
  → Realistic individual run durations
  → Natural distribution
```

**Mistake 3: Not accounting for athlete's typical patterns**
```
Bad: Using generic 5 km easy minimum for athlete who typically runs 8 km easy
  → Unrealistic downgrade from athlete's normal patterns
  → May cause confusion ("Why are all my runs so short?")

Good: Use athlete's typical patterns as baseline
  → Plans feel natural and achievable
  → Respects athlete's established training rhythm
```

### Prevention

1. **Calculate minimums before setting run frequency**:
   ```bash
   # If target is 22 km, check feasibility with N runs
   For 3 runs: 18 km min ✓ (22 km achievable)
   For 4 runs: 23 km min ✗ (22 km too low)
   For 5 runs: 28 km min ✗ (22 km too low)
   ```

2. **Use profile-aware minimums when available**:
   ```bash
   sce profile analyze  # Compute typical patterns
   # Then extract typical_easy_distance_km and typical_long_run_distance_km
   ```

3. **Validate before finalizing week structure**:
   ```bash
   python -c "
   target_km = 22
   num_runs = 4
   easy_min = 5  # or from profile
   long_min = 8  # or from profile
   min_weekly = (num_runs - 1) * easy_min + long_min
   if target_km < min_weekly:
       print(f'WARNING: {target_km} km with {num_runs} runs is below minimum ({min_weekly} km)')
   "
   ```

4. **Prefer frequency reduction over unrealistic run lengths**:
   - Better: 3 runs with realistic lengths (6-12 km each)
   - Worse: 4 runs with minimums (5-8 km each, too short for most athletes)

---

## Interpreting Progression Context with AI Coaching Judgment

### Philosophy: CLI Provides Context, AI Coach Decides

The `analyze-progression` command provides **rich context and insights**, not pass/fail decisions. As the AI coach, you interpret this data using training methodology knowledge to make intelligent, context-aware decisions.

**Key Principle**: The CLI computes metrics and classifies context → You (Claude Code) apply coaching judgment.

### Using the analyze-progression Command

```bash
sce guardrails analyze-progression \
  --previous 15 \
  --current 20 \
  --ctl 27 \
  --run-days 4 \
  --age 32
```

**Returns rich context including**:
- Volume classification (low/medium/high)
- Traditional 10% rule analysis (reference only)
- Absolute load analysis (Pfitzinger per-session guideline)
- CTL-based capacity context
- Risk factors (injury, age, large percentage increase)
- Protective factors (small absolute load, adequate capacity)
- Coaching considerations from training methodology

### Interpretation Framework

#### 1. Volume Context Classification

**Low Volume (<25km)**:
- **Primary risk**: Absolute load per session
- **Flexibility**: Higher percentage increases acceptable if absolute load is manageable
- **Key metric**: Per-session increase (<1.6km per Pfitzinger)

**Example - BG Scenario**:
```json
{
  "volume_context": {
    "category": "low",
    "injury_risk_factor": "absolute_load"
  },
  "absolute_load_analysis": {
    "per_session_increase_km": 1.25,
    "within_pfitzinger_guideline": true
  }
}
```

**Interpretation**: Despite 33% increase, accept this progression because:
- Low volume (20km) means small absolute increase (5km)
- Per-session increase (1.25km) well within Pfitzinger guideline (1.6km)
- Small absolute loads are physiologically manageable at low volumes

**Medium Volume (25-50km)**:
- **Primary risk**: Both absolute and cumulative load
- **Flexibility**: Moderate - balance percentage and absolute increases
- **Decision factors**: Consider both Pfitzinger guideline AND 10% rule

**High Volume (≥50km)**:
- **Primary risk**: Cumulative load
- **Flexibility**: Limited - adhere closely to 10% rule
- **Key concern**: Large absolute increases (>10km) significantly increase injury risk

**Example - High Volume Scenario**:
```bash
sce guardrails analyze-progression --previous 60 --current 75 --ctl 55 --run-days 4
```
```json
{
  "volume_context": {
    "category": "high",
    "injury_risk_factor": "cumulative_load"
  },
  "absolute_load_analysis": {
    "per_session_increase_km": 3.75,
    "within_pfitzinger_guideline": false
  },
  "traditional_10pct_rule": {
    "exceeds_by_pct": 15.0
  }
}
```

**Interpretation**: Be conservative - reject or modify this progression because:
- High volume (75km) means cumulative load stress
- Per-session increase (3.75km) exceeds Pfitzinger guideline (1.6km)
- Large absolute increase (15km) significantly elevates injury risk
- Recommend: Reduce to 66km (10% increase) or 68km (max acceptable with strong justification)

#### 2. Risk vs. Protective Factors

**Weighing Factors**:
- **Risk factors**: Recent injury, masters age, large percentage increase
- **Protective factors**: Low volume, small absolute load, adequate CTL capacity, within Pfitzinger guideline

**Decision Rule**: Accept progression when protective factors outweigh risk factors.

**Example - Low Risk Despite High Percentage**:
```json
{
  "increase_pct": 33.3,
  "risk_factors": [
    {
      "factor": "Large percentage increase (33%)",
      "severity": "high"
    }
  ],
  "protective_factors": [
    {
      "factor": "Low volume level with small absolute increase",
      "note": "Small absolute increases are physiologically manageable"
    },
    {
      "factor": "Within Pfitzinger per-session guideline",
      "note": "1.25km per session is below 1.6km limit"
    },
    {
      "factor": "Target volume within CTL capacity",
      "note": "20km within 25-40km capacity range"
    }
  ]
}
```

**Interpretation**: Accept - 3 strong protective factors outweigh 1 risk factor (high percentage).

**Example - High Risk Despite Acceptable Percentage**:
```json
{
  "increase_pct": 15.0,
  "risk_factors": [
    {
      "factor": "Recent injury (<90 days)",
      "severity": "moderate"
    },
    {
      "factor": "Masters athlete (age 55)",
      "severity": "moderate"
    }
  ],
  "protective_factors": []
}
```

**Interpretation**: Be conservative - 2 moderate risk factors with no protective factors warrant caution. Consider reducing progression or monitoring closely.

#### 3. CTL Capacity Analysis

**Within Capacity** (`target_within_capacity: true`):
- Strong protective factor
- Athlete's fitness supports target volume
- Example: CTL 27 (recreational) → 25-40km capacity range

**Outside Capacity** (`target_within_capacity: false`):
- Warning flag (not automatic rejection)
- Two scenarios:
  - **Below capacity**: May indicate detraining or conservative start (acceptable)
  - **Above capacity**: Requires strong justification (protective factors must clearly outweigh)

**Example - Below Capacity (Acceptable)**:
```json
{
  "current_volume_km": 20.0,
  "athlete_context": {
    "ctl": 27.0,
    "ctl_zone": "recreational",
    "ctl_based_capacity_km": [25, 40],
    "target_within_capacity": false
  }
}
```

**Interpretation**: 20km is below 25-40km range (acceptable - athlete is building conservatively).

**Example - Above Capacity (Requires Justification)**:
```json
{
  "current_volume_km": 50.0,
  "athlete_context": {
    "ctl": 27.0,
    "ctl_zone": "recreational",
    "ctl_based_capacity_km": [25, 40],
    "target_within_capacity": false
  }
}
```

**Interpretation**: 50km exceeds 40km capacity limit (needs strong protective factors or plan adjustment).

#### 4. Coaching Considerations

The `coaching_considerations` field provides methodology-based guidance:

**Low Volume Considerations**:
- "Low volume allows more flexible percentage increases when absolute load per session is small"
- "Pfitzinger principle: '1.6km per session' often more relevant than 10% rule at low volumes"

**Apply**: Prioritize Pfitzinger absolute load guideline over 10% rule.

**High Volume Considerations**:
- "High volume requires stricter adherence to 10% rule due to cumulative load stress"
- "Large absolute increases (>10km) significantly increase injury risk"

**Apply**: Be conservative with percentage increases, emphasize injury prevention.

**Injury/Masters Considerations**:
- "Recent injury history warrants conservative approach; monitor response carefully"
- "Masters athletes benefit from more conservative progressions (Pfitzinger: reduce volume 10% for age 50+)"

**Apply**: Reduce target progression or add monitoring guidance to plan.

#### 5. Traditional 10% Rule (Reference Only)

The `traditional_10pct_rule` field is provided **for reference**, not as a decision criterion.

**Use it to**:
- Explain context to athlete ("Traditional rule suggests 16.5km, but...")
- Provide perspective on progression magnitude
- Reference in coaching rationale

**Don't use it to**:
- Make pass/fail decisions
- Override context-aware analysis
- Ignore volume classification or protective factors

### Decision Examples

#### Example 1: Accept High Percentage (Low Volume)

**Scenario**: 15→20km, CTL 27, 4 run days, age 32

**Command**:
```bash
sce guardrails analyze-progression --previous 15 --current 20 --ctl 27 --run-days 4 --age 32
```

**Key Context**:
- Volume: Low (<25km)
- Per-session increase: 1.25km (within Pfitzinger guideline)
- Protective factors: Low volume + small absolute load + within guideline
- Risk factors: Large percentage (33%)

**Decision**: **ACCEPT**

**Rationale**:
"Your 15→20km progression represents a 33% increase, which exceeds the traditional 10% rule. However, at low volumes, absolute load per session is more important than percentage. Your per-session increase is 1.25km (well within Pfitzinger's 1.6km guideline), and your CTL of 27 supports this volume. The small absolute increase (5km total) is physiologically manageable despite the high percentage. I'm comfortable accepting this progression."

#### Example 2: Reject/Modify High Volume

**Scenario**: 60→75km, CTL 55, 4 run days

**Command**:
```bash
sce guardrails analyze-progression --previous 60 --current 75 --ctl 55 --run-days 4
```

**Key Context**:
- Volume: High (≥50km)
- Per-session increase: 3.75km (exceeds Pfitzinger guideline)
- Risk factors: Large absolute increase (15km) + exceeds guideline
- Protective factors: None identified

**Decision**: **MODIFY** to 66km (10% increase)

**Rationale**:
"Your planned 60→75km progression is too aggressive for high-volume training. The 15km absolute increase and 3.75km per-session increase both exceed safe guidelines. At 60km weekly volume, cumulative load stress is the primary injury risk. I recommend reducing to 66km (10% increase) to maintain safe progression. This still builds fitness while minimizing injury risk."

#### Example 3: Conservative Approach (Risk Factors Present)

**Scenario**: 40→46km, age 52, recent injury

**Command**:
```bash
sce guardrails analyze-progression --previous 40 --current 46 --age 52 --recent-injury
```

**Key Context**:
- Volume: Medium
- Percentage: 15% (exceeds 10%)
- Risk factors: Recent injury + masters athlete
- Protective factors: Moderate absolute increase

**Decision**: **MODIFY** with monitoring

**Rationale**:
"Your 15% increase would normally be acceptable in the medium-volume range, but your recent injury and masters status (age 52) warrant a more conservative approach. I recommend limiting to 44km (10% increase) and closely monitoring your ankle response during this week. If symptoms return, we'll adjust immediately."

### Summary: Context-Aware Decision Framework

1. **Check volume classification** (low/medium/high)
2. **Identify primary risk factor** (absolute load vs. cumulative load)
3. **Count protective factors vs. risk factors**
4. **Apply volume-specific decision rule**:
   - **Low volume**: Accept if within Pfitzinger guideline, even if percentage high
   - **Medium volume**: Balance both absolute and percentage
   - **High volume**: Be conservative, prioritize 10% rule
5. **Consider athlete context** (CTL capacity, injury history, age)
6. **Provide clear rationale** citing specific context from analysis

**Remember**: You are the coach. The CLI provides data - you make the intelligent, context-aware decision.

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
