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

**Common taper trajectories** (by race distance):

**5K/10K** (7-10 day taper):
- Start: TSB -5 to -10
- Race day: TSB +5 to +10
- Strategy: Maintain intensity, reduce volume 40-50%

**Half Marathon** (10-14 day taper):
- Start: TSB -10 to -15
- Race day: TSB +8 to +12
- Strategy: Reduce volume 50-60%, maintain some intensity

**Marathon** (14-21 day taper):
- Start: TSB -15 to -20
- Race day: TSB +10 to +15
- Strategy: Gradual volume reduction, minimal intensity

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

#### 5K/10K Race Week (Example: Saturday race)

**Monday**: Easy 30min + 6 × 100m strides
- Purpose: Maintain leg turnover, keep sharp
- Intensity: Easy run (RPE 3), strides at race pace

**Tuesday**: Rest or easy 20min
- Purpose: Recovery

**Wednesday**: Easy 30min + 4 × 200m race-pace strides
- Purpose: Final sharpening, race-pace feel
- Intensity: Easy run (RPE 3), strides at race pace (RPE 8)

**Thursday**: Rest
- Purpose: Maximum recovery before race

**Friday**: Easy 15min jog + dynamic stretching
- Purpose: Loosen up, stay mobile
- Intensity: Very easy (RPE 2)

**Saturday**: RACE DAY
- Warm-up: 15min easy jog + drills + 4 × 100m strides

**Sunday**: Rest or easy 20min recovery jog

#### Half Marathon Race Week (Example: Sunday race)

**Monday**: Easy 40min
- Purpose: Light recovery, start taper
- Intensity: Easy (RPE 3)

**Tuesday**: Easy 30min + 5 × 200m race-pace strides
- Purpose: Maintain sharpness
- Intensity: Easy run, strides at M-pace (half marathon pace)

**Wednesday**: Rest or easy 20min
- Purpose: Recovery

**Thursday**: Easy 30min + 4 × 200m race-pace strides
- Purpose: Final race-pace feel
- Intensity: Easy run, strides at M-pace

**Friday**: Rest
- Purpose: Maximum recovery

**Saturday**: Easy 15min jog + dynamic stretching
- Purpose: Loosen up, stay mobile

**Sunday**: RACE DAY
- Warm-up: 10-15min easy jog + dynamic stretching + 3 × 100m strides

**Monday**: Rest or easy 20min recovery jog

#### Marathon Race Week (Example: Sunday race)

**Monday**: Easy 40min
- Purpose: Very light maintenance
- Intensity: Easy (RPE 3)

**Tuesday**: Easy 30min
- Purpose: Maintain routine, minimal load

**Wednesday**: Rest or easy 20min
- Purpose: Deep recovery

**Thursday**: Easy 20min + 3 × 200m M-pace strides (optional)
- Purpose: Final race-pace reminder (optional - some skip this)

**Friday**: Rest (recommended) or easy 15min if feeling stiff
- Purpose: Maximum recovery

**Saturday**: Easy 10min jog + dynamic stretching (optional)
- Purpose: Shake out stiffness, stay mobile
- Many marathoners rest completely

**Sunday**: RACE DAY
- Warm-up: 5-10min easy jog + dynamic stretching

**Monday**: Rest (complete)

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

**3 Days Before Race**:
- ✓ Carb load begins (55-60% carbs in diet)
- ✓ Hydration increase (urine pale yellow)
- ✓ Review course map and elevation profile
- ✓ Plan race day logistics (start time, parking, gear)

**2 Days Before Race**:
- ✓ Easy short run + strides (if scheduled)
- ✓ Lay out race day gear (test everything)
- ✓ Check weather forecast
- ✓ Finalize pace plan

**1 Day Before Race**:
- ✓ Rest or very easy jog (10-15min max)
- ✓ Pre-race meal (familiar foods, 60-70% carbs)
- ✓ Hydrate (but don't overdo - clear urine = over-hydrated)
- ✓ Early to bed (sleep 2 nights before matters more than night before)
- ✓ Pack race day bag

**Race Morning**:
- ✓ Wake 3 hours before start (allow digestion time)
- ✓ Pre-race meal (familiar breakfast, 300-500 calories)
- ✓ Arrive 45-60min before start
- ✓ Warm-up routine (15min jog + strides for 5K/10K, 10min for half, 5min for marathon)
- ✓ Final bathroom stop (15-20min before start)
- ✓ Line up in appropriate pace corral

**Gear checklist**:
- Race bib (pinned or race belt)
- Running shoes (broken in, not new)
- Race outfit (tested in training)
- Watch (charged, pace alerts set)
- Anti-chafe (apply to hot spots)
- Sunscreen (if sunny)
- Sunglasses (optional)
- Hat/visor (optional, helps in heat)

**Nutrition (race day)**:
- 5K/10K: No fueling needed (hydration only)
- Half Marathon: Optional gel at 10K mark
- Marathon: Gel/chew every 45min starting at 60min + water every aid station

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

## Decision Trees

### Q: TSB is projected +18 (very fresh). Over-tapered?

**Factors to consider**:
1. **How many days to race?**
   - 7+ days: Add short tempo or race-pace strides (increase TSB load slightly)
   - 3-5 days: Add easy run with strides
   - 1-2 days: Too late to adjust, trust fitness

2. **Is CTL stable?**
   - If CTL stable: Over-rested but fitness intact, should be fine
   - If CTL declining: Lost fitness, race expectations should adjust

3. **How does athlete feel?**
   - Feeling sluggish: Over-rested, add short sharp run
   - Feeling bouncy: Good sign, likely OK

**Decision**: If >5 days to race and CTL stable, add 1 short quality session (20min tempo or race-pace strides). If <5 days, proceed with current plan.

### Q: Readiness is declining during taper (was 72, now 58). Why?

**Common causes**:
1. **Illness brewing**: Check for cold symptoms, elevated resting HR
2. **Poor sleep**: Stress, travel, pre-race nerves
3. **Under-fueling**: Athlete cut calories during taper (bad idea)
4. **Over-taper**: Boredom, loss of routine

**Action**:
- Illness: Extra rest, consider DNS if severe
- Sleep: Sleep hygiene coaching, relaxation techniques
- Under-fueling: Increase carbs, ensure adequate calories
- Over-taper: Add short easy run to maintain routine

### Q: Athlete feels great but TSB is still negative (-3) with 3 days to race. Proceed?

**Risk assessment**:
- **5K/10K**: Acceptable (short races tolerate slight fatigue)
- **Half Marathon**: Borderline (may struggle in final 5K)
- **Marathon**: Risky (likely to hit wall earlier)

**Decision**:
- If feeling great + readiness >75: Proceed (subjective trumps metric for short races)
- If any doubt: Extra rest day, aim for TSB 0-+5 minimum
- Adjust race expectations slightly (B-goal instead of A-goal)

### Q: Should race-pace strides be included in taper?

**Yes** - for sharpness and race-pace feel:
- 5K/10K: 4-6 × 200m at race pace, 2-3 days before race
- Half Marathon: 4-5 × 200m at M-pace (race pace), 3-4 days before race
- Marathon: Optional - some athletes skip, others do 3-4 × 200m M-pace 4-5 days before

**Purpose**: Maintain leg turnover, remind body of race pace, build confidence

**Caution**: Don't overdo volume - strides are <5% of weekly volume during taper

---

## Common Taper Mistakes

### Mistake 1: Training Through Taper

**Symptom**: CTL rising during taper, TSB staying negative

**Cause**: Athlete doesn't trust taper, keeps training hard

**Fix**: Explain taper science - fitness maintains for 2-3 weeks, rest allows expression of fitness

**Messaging**: "You can't gain fitness in the final 2 weeks, but you CAN arrive too tired to perform. Trust the taper."

### Mistake 2: Complete Rest (Couch Taper)

**Symptom**: CTL dropping >5 points, TSB >+20

**Cause**: Athlete rests completely (no running at all)

**Fix**: Easy short runs maintain routine, prevent staleness

**Messaging**: "Taper is reduced volume, not elimination. Short easy runs keep you sharp."

### Mistake 3: Pre-Race Jitters (Unnecessary Workouts)

**Symptom**: Athlete adds extra tempo or long run 5 days before race

**Cause**: Lack of confidence, fear of "losing fitness"

**Fix**: Reassure with data (CTL stable, TSB trending positive)

**Messaging**: "Your CTL is 52, same as 2 weeks ago. Your fitness is intact. Extra work now only adds fatigue."

### Mistake 4: Carb Depletion Before Carb Load

**Some athletes**: Deplete glycogen (low-carb 2-3 days) before carb loading

**Problem**: Outdated method, leaves athlete depleted if done incorrectly

**Recommendation**: Skip depletion, just increase carbs 3 days before race (8-10g/kg)

### Mistake 5: New Gear on Race Day

**Problem**: New shoes, new shorts, new anything = blister/chafing risk

**Rule**: "Nothing new on race day"

**Fix**: Test all gear in training (including race outfit, nutrition, watch settings)

---

## VDOT-Based Performance Prediction

**Use VDOT to predict race performance**:

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

**Use predictions to**:
- Set realistic race goals
- Validate goal times (is 1:30:00 half marathon realistic with VDOT 48? → Stretch goal)
- Adjust pacing if fitness changed since last race

**Important**: Predictions assume:
- Proper taper (TSB +5 to +15)
- Good race day conditions
- Athlete trained for target distance

**Adjust expectations if**:
- Taper execution poor (TSB <+5)
- Extreme conditions (heat, wind, hilly course)
- Athlete under-trained for distance (e.g., VDOT from 10K but limited long run experience for marathon)

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

### Edge Case 1: Race Canceled or Postponed

**Problem**: Race canceled 1 week before due to weather/COVID/etc.

**Action**:
1. Assess athlete's options:
   - Option A: Find replacement race within 2-3 weeks
   - Option B: Time trial (solo race effort on measured course)
   - Option C: Return to training (reverse taper, rebuild CTL)

2. If no replacement race:
   - Week 1: Easy running (maintain taper volume)
   - Week 2: Gradual return to pre-taper volume
   - Week 3+: Resume normal training

**Key**: Don't let peak fitness go to waste - time trial or replacement race preferred

### Edge Case 2: Illness in Final Week

**Problem**: Athlete gets cold 5 days before race.

**Decision tree**:
- **Fever**: DNS (do not start) - racing with fever risks serious illness
- **Above neck** (sniffles, sore throat): Possible to race, expectations adjusted
- **Below neck** (chest congestion, body aches): DNS recommended

**If racing with minor illness**:
- Adjust goals (B-goal or C-goal)
- Conservative pacing (no A-goal attempts)
- Monitor during race (stop if feeling worse)

### Edge Case 3: Injury Flare-Up in Taper

**Problem**: Old injury (e.g., IT band) flares 10 days before race.

**Action**:
1. Rest completely until pain-free (may sacrifice some fitness for health)
2. Cross-train if possible (pool running, cycling)
3. Race day decision:
   - Pain-free with running: Proceed (adjusted goals)
   - Pain persists: DNS (long-term health > single race)

**Use AskUserQuestion** to discuss priorities (race vs long-term health)

### Edge Case 4: Over-Tapered (TSB +22, CTL dropped 6 points)

**Problem**: Athlete rested too much, lost sharpness.

**Action** (if >5 days to race):
- Add 1-2 short tempo runs (20-30min at T-pace)
- Include race-pace strides
- Increase easy run volume slightly

**Action** (if <5 days to race):
- Too late to fix, adjust expectations
- Focus on executing race plan within current fitness
- Post-race: Learn lesson for next taper

---

## Related Skills

- **training-plan-design**: References taper structure from original plan
- **injury-risk-management**: Uses TSB/ACWR for readiness assessment
- **daily-workout**: Guides race week workouts
- **plan-adaptation**: Use if taper needs adjustment mid-execution

---

## CLI Command Reference

**Taper Verification**:
```bash
sce risk taper-status --race-date [YYYY-MM-DD] --metrics metrics.json --recent-weeks recent_weeks.json
```

**Performance Prediction**:
```bash
sce vdot predict --race-type [5k|10k|half_marathon|marathon] --time [HH:MM:SS] --goal-race [race_type]
sce vdot calculate --race-type [type] --time [HH:MM:SS]  # Get VDOT from race result
```

**Environmental Adjustments**:
```bash
sce vdot adjust --pace [M:SS] --condition [heat|altitude|wind] --severity [value]
```

**Recovery Protocol**:
```bash
sce guardrails race-recovery --distance [5k|10k|half_marathon|marathon] --age [N] --effort [easy|moderate|hard]
```

**Status**:
```bash
sce status        # Current metrics (CTL/ATL/TSB/readiness)
sce week          # Recent training summary
```

---

## Output Template

After completing race preparation assessment, provide structured output:

```
# Race Preparation Summary

**Race**: [Name] - [Distance]
**Date**: [YYYY-MM-DD] ([N] days away)
**Goal**: [Time or finish comfortably]

---

## Race Readiness: [EXCELLENT/GOOD/MODERATE/POOR]

**Taper Status**:
- TSB: [Current] → [Projected] (Target: +5 to +15) - [on_track/too_fatigued/too_fresh]
- CTL: [Current] → [Projected] ([Stability level])
- Readiness: [Current] ([Trend])

**Assessment**: [Brief interpretation]

---

## Race Week Schedule

[Day-by-day schedule with purpose for each workout]

---

## Race Day Strategy

**Pacing**: [Goal pace with conservative/aggressive/negative split approach]
**Conditions**: [Weather adjustments if needed]
**Mental approach**: [Key mantras/strategies]

---

## Pre-Race Checklist

[Key items for 3 days, 2 days, 1 day, race morning]

---

## Confidence Builder

[Data-driven confidence statement referencing training quality, taper execution, VDOT predictions]

You've done the work. The hay is in the barn. Now it's time to trust your training and race with confidence. Good luck!
```

---

## Testing Race Preparation

**Manual test scenarios**:

1. Perfect taper (TSB on track, CTL stable) → "Excellent readiness"
2. Under-tapered (TSB still negative 3 days out) → "Moderate readiness, extra rest recommended"
3. Over-tapered (TSB >+20, CTL dropped) → "Fair readiness, lost some sharpness"
4. Illness during taper → "DNS recommended" or "Adjusted expectations"
5. 5K vs Half vs Marathon → Different taper schedules and warm-up protocols

**Success criteria**:
- Taper status correctly interpreted
- TSB trajectory validated against targets
- Race week schedule appropriate for distance
- Pacing strategy aligns with VDOT predictions
- Athlete feels prepared and confident
