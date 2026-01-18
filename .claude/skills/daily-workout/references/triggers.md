# Adaptation Trigger Reference

## Overview

Triggers are data signals that warrant coaching attention. This reference provides complete interpretation guidelines for all trigger types.

---

## Trigger Types and Thresholds

| Trigger                  | Threshold    | Severity | Typical Response                       |
|--------------------------|--------------|----------|----------------------------------------|
| `acwr_high_risk`         | ACWR > 1.5   | HIGH     | Downgrade or skip workout              |
| `acwr_elevated`          | ACWR > 1.3   | MODERATE | Consider downgrade, discuss options    |
| `readiness_very_low`     | Readiness<35 | HIGH     | Force rest or easy recovery            |
| `readiness_low`          | Readiness<50 | LOW      | Downgrade quality workouts             |
| `tsb_overreached`        | TSB < -25    | HIGH     | Reduce training load immediately       |
| `lower_body_load_high`   | Dynamic      | MODERATE | Delay running quality/long runs        |
| `session_density_high`   | 2+ hard/7d   | MODERATE | Space out quality sessions             |

---

## ACWR (Acute:Chronic Workload Ratio)

### Interpretation Zones

| ACWR Value | Zone    | Injury Risk        | Coaching Response                              |
|------------|---------|-------------------|------------------------------------------------|
| 0.8-1.3    | Safe    | Normal (baseline) | Proceed as planned                              |
| 1.3-1.5    | Caution | Elevated (1.5-2x) | Consider downgrade, discuss options             |
| > 1.5      | Danger  | High (2-4x)       | Strongly recommend downgrade or rest            |

### What Drives ACWR Up

**Common causes**:
- **Sudden volume increase**: e.g., 40 km → 55 km this week (+38%)
- **Back-to-back hard sessions**: Without adequate recovery between quality workouts
- **Multi-sport spike**: e.g., climbing comp + long run same week
- **Training break return**: Rapid volume increase after time off

**Example spike pattern**:
```
Week 1: 45 km (CTL 42) → ACWR 1.05
Week 2: 48 km (CTL 43) → ACWR 1.10
Week 3: 62 km (CTL 45) → ACWR 1.38 (⚠️ elevated)
```

### How to Bring ACWR Down

**Strategies** (in order of effectiveness):

1. **Rest day** (fastest reduction)
   - Acute load drops immediately
   - ACWR can drop 0.1-0.2 in a single day
   - Best for ACWR > 1.5

2. **Easy runs only for 3-5 days**
   - Maintain aerobic stimulus
   - Gradual ACWR reduction (~0.05-0.1 per day)
   - Best for ACWR 1.3-1.5

3. **Cross-training** (if lower-body load is the issue)
   - Cycling/swimming maintains cardio fitness
   - Reduces lower-body stress
   - Use when legs need break but systemic fitness is fine

**Timeline expectations**:
- ACWR 1.35 → 1.25: 2-3 days of easy running
- ACWR 1.52 → 1.25: 4-5 days of easy + 1 rest day
- ACWR 1.65 → 1.25: 7-10 days of easy + 2 rest days

---

## Readiness Score

### Interpretation Levels

| Readiness | Level     | Interpretation              | Coaching Response             |
|-----------|-----------|-----------------------------|-----------------------------|
| < 35      | Very Low  | Significant fatigue/illness | Force rest or very easy recovery |
| 35-50     | Low       | Moderate fatigue            | Downgrade quality workouts   |
| 50-70     | Moderate  | Normal training state       | Proceed as planned           |
| 70-85     | Good      | Fresh, ready for work       | Quality sessions encouraged  |
| > 85      | Excellent | Peak readiness              | Hard sessions, races         |

### Readiness Components

The readiness score (0-100) is calculated from four inputs:

1. **TSB (20%)**: Current training stress balance
   - TSB > 0 contributes positively
   - TSB < -20 reduces readiness significantly

2. **Recent trend (25%)**: Training trajectory (7-day window)
   - Declining TSB trend reduces readiness
   - Improving TSB trend increases readiness

3. **Sleep (25%)**: Sleep quality/duration from activity notes
   - Extracted from notes mentioning "sleep", "tired", "rested"
   - Poor sleep (<6h or "bad sleep") penalizes heavily
   - Good sleep (8h+ or "well rested") boosts readiness

4. **Wellness (30%)**: Subjective wellness signals
   - Extracted from notes: "felt great", "tired", "sore", "strong"
   - Positive signals boost readiness
   - Negative signals (pain, fatigue) reduce readiness

**Note**: If activity notes are sparse, readiness relies more on TSB and trend.

### Common Readiness Patterns

**Pattern 1: Low readiness after hard week**
```
Day 1 (intervals): Readiness 72 (good)
Day 2: Readiness 65 (moderate)
Day 3 (tempo): Readiness 58 (moderate)
Day 4: Readiness 42 (low) ← trigger
```
**Coaching**: "You've had 2 quality days this week. Low readiness is expected. Easy run or rest today."

**Pattern 2: Persistent low readiness (3+ days)**
```
Day 1: Readiness 38
Day 2: Readiness 35
Day 3: Readiness 41
```
**Coaching**: "Readiness has been low for 3 days. This suggests you need more recovery. Let's take a full rest day or very easy 20 minutes."

**Pattern 3: Very low readiness (<35)**
```
Readiness: 28
Contributing factors: TSB -24, poor sleep (noted), wellness "exhausted"
```
**Coaching**: "Very low readiness is a red flag. Rest day strongly recommended."

---

## TSB (Training Stress Balance)

### Interpretation Zones

| TSB Range  | State       | Interpretation              | Coaching Response            |
|------------|-------------|-----------------------------|-----------------------------|
| < -25      | Overreached | High fatigue, need recovery | Reduce load immediately      |
| -25 to -10 | Productive  | Optimal training zone       | Continue building            |
| -10 to +5  | Fresh       | Good for quality work       | Schedule quality sessions    |
| +5 to +15  | Race Ready  | Peaked, ready to race       | Race week                    |
| > +15      | Detraining  | Fitness declining           | Increase training            |

### Understanding TSB

**What is TSB?**
- TSB = CTL - ATL (Chronic Training Load - Acute Training Load)
- Negative TSB: Recent training is higher than chronic average → fatigue
- Positive TSB: Recent training is lower than chronic average → freshness

**How TSB changes**:
- Hard workout → TSB drops (fatigue increases)
- Easy day → TSB rises slightly (recovery)
- Rest day → TSB rises more (significant recovery)

**Example TSB progression**:
```
Monday: Easy run → TSB -12 (productive)
Tuesday: Intervals → TSB -18 (fatigued)
Wednesday: Rest → TSB -14 (recovering)
Thursday: Tempo → TSB -20 (fatigued)
Friday: Easy → TSB -17 (slight recovery)
Saturday: Long run → TSB -23 (approaching overreached)
Sunday: Rest → TSB -18 (recovering)
```

### TSB and Workout Type

**Optimal TSB ranges by workout type**:

| Workout Type | Optimal TSB | Why |
|--------------|-------------|-----|
| Easy run | Any TSB | Always safe |
| Tempo run | -15 to +5 | Need some freshness for quality |
| Intervals | -10 to +5 | Need good freshness for speed |
| Long run | -15 to +5 | Need leg freshness for distance |
| Race | +5 to +15 | Peak freshness required |

**Coaching decision based on TSB**:

- **TSB -24, tempo scheduled**: "You're approaching overreached (TSB -24). Let's either move tempo to tomorrow after rest, or downgrade to easy run today."

- **TSB +8, intervals scheduled**: "You're fresh (TSB +8) - perfect for intervals. Your legs should feel strong."

- **TSB -28, easy scheduled**: "TSB is -28 (overreached). Easy run is okay, but listen to your body. Consider rest if you feel worn out."

---

## Lower-Body Load (Multi-Sport Context)

### What is Lower-Body Load?

**Concept**: Running quality and long runs depend on leg freshness, not just systemic fitness.

**Sports that impact lower-body load**:
- **Running**: 1.00 multiplier (baseline)
- **Cycling**: 0.35 multiplier (moderate leg strain)
- **Climbing**: 0.10 multiplier (minimal leg strain)
- **Hiking**: 0.60 multiplier (moderate-high leg strain)

**Example scenario**:
```
Monday: Climbing session (340 AU systemic, 34 AU lower-body)
Tuesday: Long run scheduled (18 km)

Analysis:
- Systemic load: Moderate (climbing contributes)
- Lower-body load: Low (climbing had minimal leg impact)
- Coaching: "Your legs should be fresh despite yesterday's climbing. Long run is a go."
```

**Contrast with high lower-body sport**:
```
Monday: Hard cycling (280 AU systemic, 98 AU lower-body)
Tuesday: Long run scheduled (18 km)

Analysis:
- Systemic load: Moderate
- Lower-body load: High (cycling taxed legs)
- Coaching: "Your legs took a beating yesterday from cycling. Consider moving long run to Thursday."
```

### Trigger Threshold

**`lower_body_load_high` trigger**:
- Activates when 7-day lower-body load exceeds athlete's typical range by 30%+
- Example: Athlete averages 600 AU lower-body/week, current week is 820 AU (37% increase)

**Coaching response**:
- Downgrade running quality/long runs
- Easy runs are fine (low additional leg strain)
- Wait 2-3 days for leg recovery

---

## Session Density (Quality Spacing)

### What is Session Density?

**Concept**: Quality sessions (tempo, intervals, long runs) need adequate spacing for recovery and adaptation.

**Ideal spacing**:
- **2-3 days between quality sessions** for most athletes
- **1 day minimum** for competitive athletes in peak phase

**Example violation**:
```
Monday: Intervals (quality)
Tuesday: Easy
Wednesday: Tempo (quality) ← Only 2 days since intervals
Thursday: Easy
Friday: Long run (quality) ← Only 2 days since tempo, 3 quality in 5 days
```

### Trigger Threshold

**`session_density_high` trigger**:
- Activates when 2+ quality sessions within 3 days
- OR 3+ quality sessions within 5 days

**Coaching response**:
- "You've had intervals Monday and tempo Wednesday. Today's long run would be 3 quality sessions in 5 days. Consider moving long run to Saturday (adds 1 recovery day)."

**Why this matters**:
- Quality sessions cause muscular damage and CNS fatigue
- Adequate spacing allows adaptation
- Too frequent quality = accumulation without adaptation = injury risk

---

## Combining Triggers

### Multiple Triggers Detected

**When 2+ triggers fire simultaneously, prioritize by severity:**

1. **Very high severity** (address first):
   - `readiness_very_low` (<35)
   - `acwr_high_risk` (>1.5)
   - `tsb_overreached` (<-25)

2. **Moderate severity** (address if no high-severity triggers):
   - `acwr_elevated` (1.3-1.5)
   - `lower_body_load_high`
   - `session_density_high`
   - `readiness_low` (35-50)

**Example combination**:
```
Triggers:
- acwr_high_risk: 1.52
- readiness_very_low: 32
- tsb_overreached: -26

Coaching response:
"Three major red flags: ACWR 1.52 (danger), readiness 32 (very low), TSB -26 (overreached). This is a clear signal for rest. Your body needs recovery urgently."
```

**Example moderate combination**:
```
Triggers:
- acwr_elevated: 1.38
- lower_body_load_high: 820 AU (typical: 600 AU)

Coaching response:
"ACWR is slightly elevated (1.38) and your legs have taken more load than usual this week (820 AU vs typical 600 AU). Let's downgrade today's tempo to easy run, give legs another recovery day."
```

---

## Additional Resources

- **Complete ACWR research**: See [Coaching Methodology - ACWR](../../../docs/coaching/methodology.md#acwr-acute-chronic-workload-ratio)
- **Sport multipliers**: See [Coaching Methodology - Sport Multipliers](../../../docs/coaching/methodology.md#sport-multipliers)
- **Readiness calculation**: See `sports_coach_engine/models/readiness.py`
