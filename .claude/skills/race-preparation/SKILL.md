---
name: race-preparation
description: Race week preparation and taper verification. Use when athlete asks "Race week", "am I ready to race?", "taper check", "what should I do this week?", "race day strategy", or when race date is within 14 days and you need to verify taper execution and readiness.
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Race Preparation

## Overview

This skill provides **comprehensive race readiness assessment** and **race week guidance** to ensure athletes arrive at the start line fresh, confident, and prepared to perform.

**Philosophy**: The race is the culmination of months of training. The final 7-14 days are about arriving fresh (TSB positive), maintaining sharpness (short quality), and executing race day strategy with confidence.

**Core concept**: Taper is an art. Too much rest = loss of sharpness. Too little rest = arrive fatigued. This skill validates taper execution using TSB trajectory, CTL stability, and readiness trends.

---

## Core Workflow

### Step 0: Retrieve Relevant Memories

**Before assessing taper, load athlete's past race/taper experiences to inform strategy.**

```bash
# Retrieve past taper responses
sce memory search --query "taper race"

# Retrieve training response patterns
sce memory list --type TRAINING_RESPONSE

# Check for body concerns
sce memory search --query "pain injury body"
```

**Apply retrieved memories**:
- Reference past taper experiences (e.g., "felt flat with 2-week taper, better with 10-day")
- Account for known sensitivities (e.g., "right achilles tight after >3 consecutive days")
- Adjust race-day pacing based on training responses
- Consider past race-day nutrition/strategy successes

---

### Step 1: Verify Taper Status

**Run taper verification**:
```bash
sce risk taper-status --race-date 2026-03-15 --metrics metrics.json --recent-weeks recent_weeks.json
```

**Returns**:
```json
{
  "ok": true,
  "data": {
    "race_date": "2026-03-15",
    "days_to_race": 7,
    "taper_phase": "peak_taper",
    "tsb_current": -8.2,
    "tsb_projected_race_day": 12.5,
    "tsb_target_range": [5, 15],
    "tsb_trajectory": "on_track",
    "ctl_current": 52.3,
    "ctl_race_day_projected": 51.8,
    "ctl_stability": "excellent",
    "taper_quality": "good",
    "readiness_trend": "improving",
    "warnings": [],
    "recommendations": [
      "TSB trajectory is ideal for race day",
      "Continue current taper approach",
      "Include race-pace strides 2-3 days before race"
    ],
    "race_readiness": "excellent"
  }
}
```

**Key fields**:
- `days_to_race`: Days until race (determines taper phase)
- `taper_phase`: early_taper (14-8 days) / peak_taper (7-3 days) / race_week (2-0 days)
- `tsb_trajectory`: on_track / too_fatigued / too_fresh / uncertain
- `ctl_stability`: excellent / good / declining / unstable
- `taper_quality`: excellent / good / fair / poor
- `race_readiness`: excellent / good / moderate / poor / not_ready

---

### Step 2: Interpret Taper Metrics

#### TSB (Training Stress Balance) - Race Day Freshness

**Target TSB range**: +5 to +15 on race day

| TSB Range | Interpretation | Race Day Impact |
|-----------|----------------|-----------------|
| <-10 | Still fatigued | Risk underperformance, not tapered enough |
| -10 to 0 | Slightly fatigued | May be OK for shorter races, risky for marathon |
| 0 to +5 | Fresh | Good for most races |
| +5 to +15 | Peak freshness | **Ideal race day range** |
| +15 to +25 | Very fresh | Risk losing sharpness (over-tapered) |
| >+25 | Over-rested | Likely lost fitness, too much taper |

**TSB Trajectory**:
- `on_track`: Current TSB trends toward +5 to +15 on race day
- `too_fatigued`: Projected TSB <+5, need more rest
- `too_fresh`: Projected TSB >+15, risk over-taper
- `uncertain`: Erratic recent training, hard to predict

**Common taper trajectories** (by race distance): See [TAPER_TRAJECTORIES.md](references/TAPER_TRAJECTORIES.md) for detailed progressions.

#### CTL (Chronic Training Load) - Fitness Stability

**Target**: CTL should remain stable (±2-3 points) during taper

| CTL Change | Interpretation | Action |
|------------|----------------|--------|
| +3 or more | Gaining fitness during taper | Taper too aggressive (still training hard) |
| -1 to +2 | Stable | **Ideal - maintaining fitness** |
| -3 to -5 | Slight decline | Acceptable for longer tapers (marathon) |
| -6 or more | Significant decline | Over-tapered, losing fitness |

**Why CTL stability matters**:
- Taper reduces volume, not fitness
- CTL should hold steady (you're rested, not detrained)
- Rapid CTL drop = losing aerobic capacity

#### Readiness Trend - Daily Form

**Target**: Readiness >70 consistently during taper

**Readiness trend patterns**:
- `improving`: Readiness climbing from 50s → 70s → 80s (good taper)
- `stable_high`: Readiness 70-85 consistently (excellent taper)
- `declining`: Readiness dropping (fatigue accumulating, not enough rest)
- `erratic`: Readiness fluctuating wildly (stress, poor sleep, illness risk)

**Red flags**:
- Readiness <50 within 5 days of race → Investigate (illness, stress, overtraining)
- Readiness declining during taper → Need more rest

---

### Step 3: Assess Race Readiness

**Synthesize taper status into overall readiness**:

#### Race Readiness: EXCELLENT

**Criteria**:
- TSB trajectory: on_track (+5 to +15 projected)
- CTL stability: excellent (stable ±2)
- Readiness trend: improving or stable_high (>70)
- No warnings or red flags

**Messaging**:
> "You're in excellent shape for race day. Your taper is executing perfectly:
> - TSB will be +12 on race day (ideal freshness)
> - CTL is stable at 52 (fitness maintained)
> - Readiness trending up (currently 78, was 62 at start of taper)
>
> You're ready to race. Trust your training and execute your race plan with confidence."

#### Race Readiness: GOOD

**Criteria**:
- TSB trajectory: on_track or slightly off
- CTL stability: good (stable ±3-4)
- Readiness trend: stable or improving
- Minor warnings (e.g., "TSB slightly lower than ideal")

**Messaging**:
> "You're in good shape for race day. Your taper is on track with minor adjustments needed:
> - TSB will be +8 on race day (target +10-12, but still fresh)
> - CTL stable at 51 (fitness maintained)
> - Readiness 72 (good)
>
> Recommendation: [Specific adjustment, e.g., 'Take an extra rest day Thursday']
>
> You'll be ready to race. Slight adjustment will optimize freshness."

#### Race Readiness: MODERATE

**Criteria**:
- TSB trajectory: too_fatigued or too_fresh
- CTL stability: declining (losing fitness)
- Readiness trend: stable but low (50-65 range)
- Multiple warnings

**Messaging**:
> "Your race readiness is moderate. Taper execution has some issues:
> - TSB projected +3 on race day (target +8-12, you may arrive slightly fatigued)
> - CTL declining from 52 → 48 (losing some fitness)
> - Readiness 58 (low-moderate)
>
> Recommendation: [Specific intervention, e.g., 'Extra rest this week + short race-pace run Thursday']
>
> You can still race, but expectations should be adjusted. Focus on executing well within your current state."

#### Race Readiness: POOR / NOT READY

**Criteria**:
- TSB trajectory: too_fatigued (<+5 projected)
- CTL stability: unstable or significantly declining
- Readiness trend: declining or erratic
- Red flags (illness, injury, severe fatigue)

**Messaging**:
> "⚠️ Your race readiness is concerning. Current state:
> - TSB projected -2 on race day (still fatigued, not tapered enough)
> - CTL dropped from 52 → 45 (significant fitness loss)
> - Readiness 42 (low)
> - Red flag: [Specific issue, e.g., 'Readiness declining for 5 consecutive days']
>
> **Recommendation**: Consider these options:
> 1. **DNS (Do Not Start)**: Skip race, recover fully, target next race
> 2. **Adjust expectations**: Race as training run, no time goal
> 3. **Last-ditch rest**: Complete rest next 3-4 days, reassess
>
> Racing in this state risks poor performance or injury. Let's discuss your priorities."

**Use AskUserQuestion** to present options with honest trade-offs.

---

### Step 4: Race Week Schedule

**Generate race week schedule based on race distance**:

- **5K/10K**: See [race_week_5k.md](templates/race_week_5k.md)
- **Half Marathon**: See [race_week_half.md](templates/race_week_half.md)
- **Marathon**: See [race_week_marathon.md](templates/race_week_marathon.md)

**Key principles**:
- Maintain routine, reduce volume
- Final hard workout: 5K (3 days out), Marathon (10 days out)
- Race-pace strides 2-3 days before race
- Complete rest 1 day before (5K/10K) or 2 days before (half/marathon)

---

### Step 5: Race Day Strategy

**Develop race plan based on**:
1. Goal (time vs finish comfortably)
2. VDOT-based pace predictions
3. Current fitness (CTL, recent workouts)
4. Course profile (flat, hilly, technical)
5. Weather forecast (heat, wind, rain)

#### Pacing Strategy

**Use VDOT predictions**:
```bash
sce vdot predict --race-type 10k --time 42:30 --goal-race half_marathon
```

**Returns**: Equivalent half marathon time based on 10k performance.

**Conservative approach** (recommended for most athletes):
- Start 5-10 seconds/km **slower** than goal pace
- First 1/3: Settle in, conserve energy
- Middle 1/3: Hold steady at goal pace
- Final 1/3: Increase if feeling strong

**Example (Half Marathon, 1:30:00 goal = 4:16/km pace)**:
- Miles 1-4: 4:20-4:25/km (settle)
- Miles 5-10: 4:15-4:18/km (goal pace)
- Miles 11-13.1: 4:10-4:15/km (push)

**Aggressive approach** (experienced athletes with excellent taper):
- Start at goal pace
- Hold through middle
- Push final 1/4

**Negative split approach** (safest for marathons):
- First half: 2-5 seconds/km slower than goal
- Second half: At or slightly faster than goal

#### Environmental Adjustments

**Heat**:
```bash
sce vdot adjust --pace 4:15 --condition heat --severity 28
```

**Returns**: Adjusted pace accounting for temperature impact.

**Rule of thumb**: +3-5 seconds/km for every 5°C above 15°C optimal.

**Wind**:
- Headwind: +5-10 seconds/km effort (pace will drop)
- Tailwind: Resist urge to go too fast early
- Strategy: Shelter behind other runners in headwind sections

**Rain**:
- Minimal impact on pace
- Watch for slippery surfaces (corners, painted lines)
- Pre-apply anti-chafe (wet clothes = more friction)

#### Mental Strategy

**Chunking**: Break race into segments
- 10K: 2 × 5K chunks
- Half Marathon: 3 × 7K chunks
- Marathon: 4 × 10K chunks

**Mantras**:
- "Smooth and steady"
- "Trust the training"
- "Relax and flow"

**Pain cave management** (final 20-25%):
- Expected: Legs heavy, breathing hard
- Strategy: Focus on form, count to 100, landmark to landmark

---

### Step 6: Pre-Race Checklist

See [pre_race_checklist.md](templates/pre_race_checklist.md) for complete timeline (3 days, 2 days, 1 day, race morning) and gear checklist.

**Key items**:
- Carb load begins 3 days before (8-10g/kg body weight)
- Lay out and test all race gear 2 days before
- Early to bed 1 day before (sleep 2 nights before matters most)
- Wake 3 hours before race (digestion time)
- Nothing new on race day (gear, nutrition, routine)

---

### Step 7: Present Race Preparation Plan

**Create race prep document** (`/tmp/race_preparation_YYYY_MM_DD.md`):

```markdown
# Race Preparation Plan

**Race**: [Race Name] - [Distance]
**Date**: [YYYY-MM-DD]
**Goal**: [Time goal or "Finish comfortably"]
**Days to race**: [N]

---

## Taper Status

**Overall Readiness**: [EXCELLENT/GOOD/MODERATE/POOR]

**Key Metrics**:
- **TSB**: [Current] → [Projected race day] (Target: +5 to +15)
- **CTL**: [Current] → [Projected race day] (Stability: [excellent/good/fair])
- **Readiness**: [Current value] ([Trend]: [improving/stable/declining])

**Taper Quality**: [excellent/good/fair/poor]

**Assessment**: [Brief interpretation of taper execution]

---

## Race Week Schedule

### [Day] - [Date]
**Workout**: [Description]
**Purpose**: [Why this workout]
**Intensity**: [Easy/Moderate/Strides]
**Duration**: [Minutes]

[Repeat for each day of race week]

### Race Day - [Date]
**Warm-up**: [Protocol]
**Start time**: [Time]
**Expected finish**: [Time estimate]

---

## Race Day Strategy

### Pacing Plan

**Goal pace**: [X:XX/km] ([Total time])

**Race splits** (conservative approach):
- **Start** (first [distance]): [Pace] - [Purpose: Settle in]
- **Middle** ([distance]): [Pace] - [Purpose: Hold steady]
- **Finish** (final [distance]): [Pace] - [Purpose: Push if feeling strong]

**Effort guideline**:
- First half: RPE 6-7 (comfortably hard)
- Second half: RPE 7-8 (hard but sustainable)
- Final mile/km: RPE 8-9 (give everything)

### Environmental Considerations

**Weather forecast**: [Temperature, conditions]
**Adjustments**: [Pace adjustments for heat/wind if applicable]
**Gear**: [Weather-specific gear recommendations]

### Course Strategy

**Profile**: [Flat/Rolling/Hilly]
**Key sections**:
- [Mile/km X-Y]: [Description, e.g., "Steady climb, maintain effort not pace"]
- [Mile/km X-Y]: [Description, e.g., "Downhill, resist surging too hard"]

---

## Pre-Race Checklist

**3 Days Before**: [Items]
**2 Days Before**: [Items]
**1 Day Before**: [Items]
**Race Morning**: [Items]

**Gear**: [Checklist of race day gear]

---

## Nutrition & Hydration

**Carb loading** (3 days before):
- Target: 8-10g carbs per kg body weight
- Example meals: [Pasta, rice, bread, etc.]

**Race morning**:
- Meal: [Specific breakfast, 300-500 calories]
- Timing: 3 hours before start
- Hydration: 400-600ml water

**During race**:
- [5K/10K: Water only at aid stations]
- [Half: Optional gel at 10K + water]
- [Marathon: Gel every 45min + water every aid station]

---

## Mental Preparation

**Visualization**: [2-3 key moments to visualize success]
**Mantras**: [Personal mantras to use during race]
**Race goals**:
1. A-goal: [Stretch goal]
2. B-goal: [Realistic goal]
3. C-goal: [Minimum acceptable]

**Remember**: Trust your training. Months of work have prepared you for this. Execute the plan, stay patient, and finish strong.

---

## Post-Race

**Immediate** (first 30min):
- Walk 5-10min (don't stop moving immediately)
- Hydrate and eat (recovery drink/snack)
- Change into dry clothes

**First 24 hours**:
- Easy walk or swim (active recovery)
- Compression socks (optional)
- Sleep well

**Recovery protocol**: [Based on race distance]
- [5K: 3-5 days easy running]
- [10K: 5-7 days easy running]
- [Half: 10-14 days (see sce guardrails race-recovery)]
- [Marathon: 14-21 days (see sce guardrails race-recovery)]

---

## Questions?

Review this plan and let me know:
- Adjustments to pacing strategy?
- Concerns about taper status?
- Race day logistics questions?

You've done the work. Now it's time to execute. Good luck!
```

**Present to athlete**:
- Highlight key readiness indicators
- Emphasize taper execution quality
- Build confidence with concrete data
- Provide clear race day plan

---

### Step 8: Post-Race Memory Capture

**After race completion, capture significant experiences as memories for future reference:**

```bash
# Capture taper response
sce memory add --type TRAINING_RESPONSE \
  --content "10-day taper felt optimal, felt strong at race start" \
  --tags "taper:10-days,race:10k,feeling:strong" \
  --confidence high

# Capture pacing strategy outcome
sce memory add --type TRAINING_RESPONSE \
  --content "Conservative start (5s/km slower) allowed strong finish" \
  --tags "race:pacing,strategy:conservative,outcome:success" \
  --confidence high

# Capture nutrition/gear successes or issues
sce memory add --type PREFERENCE \
  --content "Pre-race oatmeal 3h before worked perfectly" \
  --tags "nutrition:pre-race,timing:3h,food:oatmeal" \
  --confidence high
```

**Patterns to capture**:
- Taper duration effectiveness
- Race-day pacing strategy outcomes
- Nutrition/hydration successes or failures
- Gear issues (blisters, chafing)
- Mental strategy effectiveness
- Body responses during race

---

## Decision Trees

For guidance on common race preparation decisions, see [DECISION_TREES.md](references/DECISION_TREES.md):

- TSB is projected +18 (very fresh) - Over-tapered?
- Readiness declining during taper - Why?
- Athlete feels great but TSB still negative 3 days out - Proceed?
- Should race-pace strides be included in taper?

---

## Common Taper Mistakes

See [TAPER_MISTAKES.md](references/TAPER_MISTAKES.md) for 5 common mistakes:

1. **Training Through Taper** - Athlete doesn't trust taper, keeps training hard
2. **Complete Rest (Couch Taper)** - Rests completely, loses sharpness
3. **Pre-Race Jitters** - Adds extra workouts from lack of confidence
4. **Carb Depletion Before Carb Load** - Outdated method, risky
5. **New Gear on Race Day** - Blister/chafing risk

**Golden rule**: "Nothing new on race day"

---

## VDOT-Based Performance Prediction

See [VDOT_PREDICTION.md](references/VDOT_PREDICTION.md) for complete guidance on using VDOT predictions to set realistic race goals.

**Key use**: Compare predicted times to athlete's goals to validate expectations.

**Important**: Predictions assume proper taper (TSB +5 to +15), good conditions, and distance-appropriate training.

---

## Training Methodology References

**Taper Science**:
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md) - Pfitzinger's taper protocols
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md) - VDOT predictions and race pace guidance

**Race Strategy**:
- [Faster Road Racing](../../../docs/training_books/faster_road_racing_pete_pfitzinger.md) - 5K-Half marathon racing tactics
- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md) - Pacing strategies

**Complete methodology**:
- [Coaching Methodology](../../../docs/coaching/methodology.md) - TSB interpretation, race readiness assessment

---

## Edge Cases

For unusual race preparation situations, see [EDGE_CASES.md](references/EDGE_CASES.md):

1. **Race Canceled or Postponed** - Replacement race or reverse taper options
2. **Illness in Final Week** - DNS decision tree (fever vs above/below neck)
3. **Injury Flare-Up in Taper** - Race vs long-term health priorities
4. **Over-Tapered** - Lost sharpness, how to recover

---

## Related Skills

- **training-plan-design**: References taper structure from original plan
- **injury-risk-management**: Uses TSB/ACWR for readiness assessment
- **daily-workout**: Guides race week workouts
- **plan-adaptation**: Use if taper needs adjustment mid-execution

---

## Additional Resources

**Decision support**:
- [Decision Trees](references/DECISION_TREES.md) - Common taper decisions
- [Edge Cases](references/EDGE_CASES.md) - Unusual situations

**Reference material**:
- [Taper Mistakes](references/TAPER_MISTAKES.md) - 5 common mistakes to avoid
- [VDOT Prediction](references/VDOT_PREDICTION.md) - Performance prediction guidance
- [Taper Trajectories](references/TAPER_TRAJECTORIES.md) - Distance-specific TSB progressions
- [CLI Reference](references/CLI_REFERENCE.md) - Command quick reference

**Templates**:
- [Race Week Schedules](templates/) - 5K, 10K, Half, Marathon week-by-week
- [Pre-Race Checklist](templates/pre_race_checklist.md) - 3-day countdown + gear
- [Race Preparation Template](templates/race_preparation.md) - Structured output format

**Training methodology**:
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md)
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md)
- [Faster Road Racing](../../../docs/training_books/faster_road_racing_pete_pfitzinger.md)
- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md)
- [Coaching Methodology](../../../docs/coaching/methodology.md)
