# Training Guardrails - Macro Planning

Strategic guardrails for 16-week training plan design. Ensures safe volume progression, appropriate phase allocation, and recovery week timing.

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

### When to Schedule
- **Base/Build phases**: Every 4th week (weeks 4, 8, 12)
- **Peak phase**: No recovery weeks (maintaining high load)
- **Taper**: No recovery weeks (already reducing volume)
- **First 2 weeks**: No recovery (building from base)

**Example 16-week plan**:
- Weeks 1-3: Build
- Week 4: Recovery (70%)
- Weeks 5-7: Build
- Week 8: Recovery (70%)
- Weeks 9-11: Build
- Week 12: Recovery (70%)
- Weeks 13-14: Peak (hold volume)
- Weeks 15-16: Taper

### Masters Adjustment (45+)
- **45-54**: Every 3rd week
- **55+**: Every 2-3rd week

**Command**:
```bash
sce guardrails masters-recovery --age 52
```

---

## Phase Allocation Guardrails

### Minimum Phase Lengths

**Base Phase**:
- **Minimum**: 4 weeks (8 weeks preferred)
- **Purpose**: Establish aerobic foundation
- **Volume progression**: +5-10%/week
- **Guardrail**: Don't rush base building

**Build Phase**:
- **Minimum**: 4 weeks (6 weeks preferred)
- **Purpose**: Add intensity while maintaining volume
- **Volume progression**: +0-5%/week
- **Guardrail**: Need time for intensity adaptation

**Peak Phase**:
- **Minimum**: 2 weeks (3 weeks preferred)
- **Purpose**: Absorb maximum training load
- **Volume progression**: Hold steady
- **Guardrail**: Don't peak too long (overtraining risk)

**Taper Phase**:
- **Minimum**: 2 weeks (required)
- **Purpose**: Reduce fatigue, maintain fitness
- **Volume progression**: -20-30%/week
- **Guardrail**: Insufficient taper = poor race performance

### Example Allocations

**16-week plan** (half marathon):
- Base: 7 weeks (good)
- Build: 5 weeks (good)
- Peak: 2 weeks (minimum)
- Taper: 2 weeks (minimum)

**12-week plan** (10K, compressed):
- Base: 4 weeks (minimum)
- Build: 4 weeks (minimum)
- Peak: 2 weeks (minimum)
- Taper: 2 weeks (minimum)

**20-week plan** (marathon, extended):
- Base: 10 weeks (excellent)
- Build: 6 weeks (good)
- Peak: 2 weeks (minimum)
- Taper: 2 weeks (minimum)

---

## Volume Trajectory Validation

### Overall Progression Rate

Across entire plan:
- **Too aggressive**: >15% average weekly increase → high injury risk
- **Safe**: 5-10% average weekly increase (accounting for recovery weeks)
- **Conservative**: <5% average weekly increase (beginners, returning from injury)

**Formula**:
```
Average increase = (Peak volume - Starting volume) / (Buildup weeks - Recovery weeks)
```

**Example**:
- Starting: 32 km
- Peak: 58 km
- Total weeks: 14 (excluding 2-week taper)
- Recovery weeks: 3
- Buildup weeks: 14 - 3 = 11
- Average increase: (58 - 32) / 11 = 2.4 km/week (~7%)
→ SAFE

### CTL Consistency Check

**Macro plan CTL trajectory should be smooth**:
- Base phase: +2-4 CTL points/week
- Build phase: +1-2 CTL points/week
- Peak phase: 0-1 CTL points/week
- Taper: -2 to -4 CTL points total

**Warning signs**:
- Sudden CTL jumps (>5 points in one week) → volume spike risk
- CTL plateau during base → insufficient stimulus
- CTL decline during build → volume not maintained

**Validation** (conceptual, not CLI command):
Plot planned weekly volumes, verify CTL would increase smoothly.

---

## Multi-Sport Load Planning

### Running Priority Adjustments

**Running PRIMARY**:
- Standard volume progression (10% rule)
- Other sports don't constrain running volume
- Guardrail: Watch for systemic load accumulation

**Running EQUAL**:
- Reduce running volume 20-30%
- Account for systemic load from other sports
- Guardrail: Peak running volume should be 70-80% of running-only equivalent

**Example**:
- Running-only peak: 60 km
- With climbing 2x/week: Peak 42-48 km (70-80%)

**Running SECONDARY**:
- Maintenance volume only (20-30 km/week)
- No progressive buildup
- Guardrail: Don't design periodized plan (maintain baseline)

### Multi-Sport Guardrails

1. **Systemic load cap**: Total weekly load ≈100-120 load units
   - Running: 1.0× multiplier
   - Cycling: 0.85× multiplier
   - Climbing: 0.60× multiplier

2. **Lower-body load cap**: Primary limiter for running progression
   - Running: 1.0× multiplier
   - Cycling: 0.35× multiplier
   - Climbing: 0.10× multiplier

**Example calculation**:
- 50 km running: 50 load units (systemic), 50 load units (lower-body)
- 3 climbing sessions (120 min each): 36 load units (systemic), 3.6 load units (lower-body)
- Total systemic: 86 (safe)
- Total lower-body: 53.6 (safe for running adaptation)

---

## Unproven Capacity Guardrail

**Rule**: Don't plan peak volume >120% of historical maximum

**Rationale**:
- Injury risk increases exponentially beyond proven capacity
- "Paper fitness" (never tested) is unreliable

**Check**:
```bash
sce analysis capacity --activities activities.json --planned-volume 70
```

**Returns**:
- `historical_max`: Highest 4-week rolling average
- `capacity_utilization`: Planned peak ÷ historical max
- `exceeds_proven_capacity`: Boolean
- `risk_assessment`: Low/Moderate/High

**Mitigation**:
- If planned >120% of max → Cap at 120% OR extend base phase
- If planned >150% of max → Reject (extremely high risk)

**Example**:
- Historical max: 50 km/week
- Planned peak: 75 km (150%) → REJECT or cap at 60 km (120%)
- Alternative: Extend base phase +4 weeks to build capacity gradually

---

## Guardrail Enforcement Philosophy

**Important**: Guardrails are **validated** by modules, **enforced** by coach (you).

### Toolkit Approach
1. **Modules return violations**: "T-pace volume is 12% (exceeds 10% limit)"
2. **You interpret with context**: "Athlete is experienced, CTL is high, no injury history"
3. **You decide enforcement**: "Acceptable violation" OR "Adjust plan"

### When to Enforce Strictly (Macro Level)
- New athletes (limited training history)
- Large gap in training (>8 weeks off)
- Previous injury during last training cycle
- Multi-sport athlete (complex load interactions)
- Masters athletes (45+, reduced recovery capacity)
- Ambitious goal (>120% of historical peak volume)

### When to Allow Flexibility
- Experienced athletes with strong training history
- Conservative goal (peak volume <100% of historical max)
- Good injury resilience (no injuries in past 2 years)
- Athlete has successfully completed similar volume before

**Key**: Use guardrails as **guidance**, not absolute rules. Coach with context.

---

## Macro Planning Guardrail Commands

```bash
# Safe starting and peak volumes
sce guardrails safe-volume --ctl 44 --goal-type half_marathon

# Masters recovery adjustments
sce guardrails masters-recovery --age 52

# Historical capacity check
sce analysis capacity --activities activities.json --planned-volume 70

# Return after training break
sce guardrails break-return --days 21 --ctl 44 --cross-training moderate
```

---

## Deep Dive Resources

- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md) - Intensity distribution research
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md) - Quality volume limits
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md) - Recovery protocols
- [Coaching Methodology](../../../docs/coaching/methodology.md#training-guardrails) - Complete guardrails system
