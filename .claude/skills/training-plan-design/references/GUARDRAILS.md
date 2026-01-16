# Training Guardrails Quick Reference

Evidence-based safety rules that protect against injury and overtraining. Based on Daniels, Pfitzinger, and 80/20 Running research.

## 80/20 Intensity Distribution

**Rule**: ~80% of training at low intensity (Z1-Z2), ≤20% at moderate+high intensity (Z3-Z5)

### Why It Matters
- Elite endurance athletes across sports follow 80/20 distribution
- Maximizes aerobic development (mitochondria, capillary density)
- Minimizes injury risk (excessive intensity → chronic stress)
- Allows quality work to be truly quality (fresh for hard sessions)

### Validation
```bash
sce analysis intensity --activities activities.json --days 28
```

**Returns**:
- Distribution: X% easy, Y% moderate+hard
- Compliance: true/false
- Violations: "Too much moderate intensity" (gray zone)
- Polarization score: 0-100 (how well easy/hard are separated)

### Common Violations
1. **Moderate-intensity rut**: 65/35 or 70/30 (easy runs too hard)
2. **Everything hard**: 60/40 (no true easy days)
3. **Gray zone training**: Lots of RPE 5-6 (neither easy nor hard)

### Enforcement
- **Applies when**: Running ≥3 days/week (need volume for distribution to matter)
- **Check frequency**: Weekly or bi-weekly
- **Action if violated**: Slow down easy runs, reduce frequency of quality sessions

**Matt Fitzgerald quote**: "The most common mistake recreational runners make is running their easy runs too hard and their hard runs not hard enough."

---

## Quality Volume Limits (Daniels)

**Rule**: Cap intensity volume to prevent overuse injuries

| Intensity | Limit             | Rationale                     |
|-----------|-------------------|-------------------------------|
| T-pace    | ≤10% weekly volume| Lactate threshold work is stressful |
| I-pace    | ≤8% weekly volume | VO2max intervals very demanding |
| R-pace    | ≤5% weekly volume | Speed work highest injury risk |

### Validation
```bash
sce guardrails quality-volume --t-pace 6.0 --i-pace 4.0 --r-pace 2.0 --weekly-volume 50.0
```

**Returns**:
- `overall_ok`: Boolean
- `violations`: List of exceeded limits
- `pace_limits`: Recommended maximums for each intensity

### Example (50 km/week plan)
- T-pace: ≤5 km (10% of 50 km)
- I-pace: ≤4 km (8% of 50 km)
- R-pace: ≤2.5 km (5% of 50 km)

**Typical workout**:
- Tempo run: 2 km warm-up + 5 km T-pace + 2 km cool-down = 9 km total, 5 km quality
- Intervals: 2 km warm-up + 3 × 1 km I-pace (3 km quality) + 2 km cool-down = 7 km total

### Enforcement
- Check during plan design (weekly validation)
- Adjust workout volumes to comply
- Exception: Recovery weeks can proportionally reduce limits

---

## Long Run Caps

**Rule**: Long runs capped by duration AND percentage of weekly volume

### Duration Limit
**≤2.5 hours** (150 minutes)

**Rationale**:
- Beyond 2.5 hours: Diminishing aerobic returns
- Increased injury risk (fatigue-related form breakdown)
- Excessive recovery time (impacts next week's training)

**Exception**: Marathon-specific training may approach 3 hours, but with caution

### Percentage Limit
**≤25-30% of weekly volume**

**Rationale**:
- Prevents one run from dominating the week
- Ensures balanced load distribution
- Reduces injury risk from single excessive session

**Example**:
- 50 km/week → long run ≤12.5-15 km (25-30%)
- 70 km/week → long run ≤17.5-21 km (25-30%)

### Validation
```bash
sce guardrails long-run --duration 150 --weekly-volume 60 --pct-limit 30
```

**Returns**:
- `pct_ok`: Boolean (within percentage limit)
- `duration_ok`: Boolean (within time limit)
- `violations`: Specific issues + recommendations

### Enforcement
- Weekly check during plan design
- Adjust long run duration or increase weekly volume
- Taper: Long run can be higher % (40-50%) as volume drops

---

## Weekly Progression (10% Rule)

**Rule**: Increase weekly volume by ≤10% per week

### Rationale
- Gradual adaptation prevents overuse injuries
- ACWR stays <1.3 (safe injury risk zone)
- Body adapts to new load before adding more

### Validation
```bash
sce guardrails progression --previous 40 --current 48
```

**Returns**:
- `ok`: Boolean
- `increase_pct`: Actual increase percentage
- `safe_max_km`: Recommended maximum
- `violation`: Details if exceeded

### Recovery Week Exception
- Every 4th week: Drop to 70% of previous week
- Next buildup: Increase from pre-recovery baseline (NOT from recovery week)

**Example**:
- Week 3: 48 km
- Week 4: 34 km (recovery, -30%)
- Week 5: 52 km (+10% from week 3's 48 km, NOT +53% from week 4)

### Enforcement
- Check during plan design (week-to-week validation)
- Flag violations, suggest safer progression
- Exception: First week after injury/illness (use return-to-training protocol)

---

## Recovery Week Frequency

**Rule**: Every 4th week during base/build phases

### Purpose
- Consolidate adaptations from previous 3 weeks
- Prevent overtraining accumulation
- Allow body to supercompensate

### Structure
- **Volume**: 70% of previous week
- **Intensity**: Maintain (keep quality, reduce duration)
- **Frequency**: Reduce number of runs if needed

**Example**:
- Week 3: 50 km (3 easy, 1 tempo, 1 intervals, 1 long)
- Week 4: 35 km (2 easy, 1 short tempo, 1 short long) = 70% volume, maintains intensity

### When NOT to Schedule
- Peak phase (maintaining high load)
- Taper (already reducing volume)
- First 2 weeks of plan (building from base)

### Masters Adjustment (45+)
- Every 3rd week instead of 4th
- See `sce guardrails masters-recovery --age 52`

---

## Hard/Easy Separation

**Rule**: No back-to-back high-intensity sessions (RPE ≥7)

### Applies Across All Sports
- Running tempo + climbing comp on consecutive days → violation
- Intervals Tuesday + hard cycling Wednesday → violation

### Rationale
- Recovery time: 48-72 hours needed between high-intensity efforts
- Prevents overtraining and injury
- Maintains quality (hard sessions done fresh)

### Validation
Check session density:
```bash
sce today  # Returns adaptation triggers including "session_density_high"
```

**Trigger**: `session_density_high` if 2+ hard sessions in 7 days without adequate spacing

### Enforcement
- Plan quality sessions 2-3 days apart
- Easy runs (RPE 3-4) between hard days
- Consider multi-sport schedule (climbing intensity impacts running)

---

## ACWR Safety

**Rule**: ACWR > 1.5 = high injury risk (2-4x baseline)

### ACWR Zones
- **0.8-1.3**: Safe (normal injury risk)
- **1.3-1.5**: Caution (elevated risk, 1.5-2x)
- **>1.5**: Danger (high risk, 2-4x)

### Causes of ACWR Spikes
1. Sudden volume increase (violates 10% rule)
2. Back-to-back hard sessions
3. Multi-sport load accumulation
4. Insufficient recovery weeks

### Prevention During Plan Design
- Validate weekly progression (10% rule)
- Schedule recovery weeks
- Forecast ACWR across plan:
  ```bash
  sce risk forecast --weeks 4 --metrics metrics.json --plan plan.json
  ```

### Action if ACWR Elevated
- Hold volume steady (don't increase)
- Add recovery days
- Reduce intensity temporarily
- See `daily-workout` skill for adaptation decisions

---

## Race Recovery Protocol

**Rule**: Recovery days = f(distance, age, effort)

### Pfitzinger Formula
**Recovery days = Race distance (km) ÷ 1.6 + age adjustment**

**Example**:
- Half marathon (21 km): 21 ÷ 1.6 = 13 days
- Age 52: +1-2 days → 14-15 days total

### Validation
```bash
sce guardrails race-recovery --distance half_marathon --age 52 --effort hard
```

**Returns**:
- `minimum_days`: Absolute minimum before running again
- `recommended_days`: Conservative return-to-training
- `recovery_schedule`: Day-by-day protocol
- `red_flags`: Warning signs (pain, excessive fatigue)

### Recovery Schedule Structure
- Days 1-3: Complete rest or cross-training (swimming, yoga)
- Days 4-7: Easy short runs (20-30 min)
- Days 8-14: Build volume gradually (50% → 75% → 100% of pre-race)
- Day 15+: Resume normal training

### Enforcement
- Flag if plan schedules race + hard workout within recovery window
- Suggest easy runs during recovery period
- Check for "back-to-back race" violations (races <2 weeks apart)

---

## Guardrail Validation Commands

```bash
# 80/20 intensity distribution
sce analysis intensity --activities activities.json --days 28

# Quality volume limits
sce guardrails quality-volume --t-pace 5.0 --i-pace 4.0 --r-pace 2.0 --weekly-volume 50.0

# Long run caps
sce guardrails long-run --duration 135 --weekly-volume 55 --pct-limit 30

# Weekly progression (10% rule)
sce guardrails progression --previous 40 --current 48

# Race recovery
sce guardrails race-recovery --distance half_marathon --age 52 --effort hard

# Return after training break
sce guardrails break-return --days 21 --ctl 44 --cross-training moderate

# Illness recovery
sce guardrails illness-recovery --severity moderate --days-missed 7

# Masters recovery adjustments
sce guardrails masters-recovery --age 52
```

---

## Guardrail Enforcement Philosophy

**Important**: Guardrails are **validated** by modules, **enforced** by coach (you).

### Toolkit Approach
1. **Modules return violations**: "T-pace volume is 12% (exceeds 10% limit)"
2. **You interpret with context**: "Athlete is experienced, CTL is high, no injury history"
3. **You decide enforcement**: "Acceptable violation" OR "Adjust plan"

### When to Enforce Strictly
- New athletes (limited injury history)
- Recent injury recovery
- ACWR already elevated
- Masters athletes (45+)
- Multi-sport athletes (complex load)

### When to Allow Flexibility
- Experienced athletes with good history
- CTL is well-established
- Athlete knows their body well
- Violation is minor (e.g., 11% T-pace vs 10%)

**Key**: Use guardrails as **guidance**, not absolute rules. Coach with context.

---

## Deep Dive Resources

For complete guardrails methodology:
- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md) - Intensity distribution research
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md) - Quality volume limits
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md) - Recovery protocols
- [Coaching Methodology](../../../docs/coaching/methodology.md#training-guardrails) - Complete guardrails system
