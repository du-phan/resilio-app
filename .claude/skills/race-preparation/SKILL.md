---
name: race-preparation
description: Race week preparation and taper verification. Use when athlete asks "Race week", "am I ready to race?", "taper check", "what should I do this week?", "race day strategy", or when race date is within 14 days and you need to verify taper execution and readiness.
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Race Preparation

## Overview

This skill provides **comprehensive race readiness assessment** and **race week guidance** to ensure athletes arrive at the start line fresh, confident, and prepared.

**Philosophy**: The race is the culmination of months of training. The final 7-14 days are about arriving fresh (TSB positive), maintaining sharpness, and executing race day strategy with confidence.

**Core concept**: Taper is an art. Too much rest = loss of sharpness. Too little rest = arrive fatigued.

---

## Core Workflow

### Step 0: Retrieve Relevant Memories

```bash
# Retrieve past taper/race experiences
sce memory search --query "taper race"
sce memory list --type TRAINING_RESPONSE
sce memory search --query "pain injury body"
```

**Apply memories**: Reference past taper experiences, adjust pacing based on history, consider nutrition/strategy successes.

---

### Step 1: Verify Taper Status

```bash
sce risk taper-status --race-date 2026-03-15 --metrics metrics.json --recent-weeks recent_weeks.json
```

**Key fields returned**:
- `days_to_race`: Days until race
- `taper_phase`: early_taper (14-8d) / peak_taper (7-3d) / race_week (2-0d)
- `tsb_trajectory`: on_track / too_fatigued / too_fresh / uncertain
- `ctl_stability`: excellent / good / declining / unstable
- `taper_quality`: excellent / good / fair / poor
- `race_readiness`: excellent / good / moderate / poor / not_ready

---

### Step 2: Interpret Taper Metrics

#### TSB (Training Stress Balance) - Race Day Freshness

**Target**: +5 to +15 on race day

**Quick zones**:
- <-10: Still fatigued, not tapered enough
- 0 to +5: Fresh, good for most races
- **+5 to +15: Ideal race day range** ✅
- +15 to +25: Very fresh, risk over-taper
- >+25: Over-rested, lost fitness

**For detailed TSB progressions by distance**: See [references/taper_trajectories.md](references/taper_trajectories.md)

#### CTL (Chronic Training Load) - Fitness Stability

**Target**: CTL stable (±2-3 points) during taper

**Quick zones**:
- +3 or more: Still training hard (taper too aggressive)
- **-1 to +2: Stable (ideal)** ✅
- -3 to -5: Slight decline (acceptable for marathon)
- -6 or more: Over-tapered, losing fitness

#### Readiness Trend

**Target**: Readiness >70 consistently during taper

**Trends**:
- `improving`: 50s → 70s → 80s (good taper)
- `stable_high`: 70-85 consistently (excellent)
- `declining`: Fatigue accumulating, need more rest
- `erratic`: Stress/sleep issues, illness risk

---

### Step 3: Assess Race Readiness

**Synthesize taper status into overall readiness assessment.**

#### Race Readiness: EXCELLENT
- TSB on_track (+5 to +15), CTL stable, Readiness >70
- Message: "You're in excellent shape. Taper executing perfectly. Trust your training."

#### Race Readiness: GOOD
- TSB on_track or slightly off, CTL stable, minor warnings
- Message: "Good shape with minor adjustments needed. [Specific recommendation]."

#### Race Readiness: MODERATE
- TSB too_fatigued/too_fresh, CTL declining, Readiness 50-65
- Message: "Moderate readiness. [Specific intervention needed]. Adjust expectations."

#### Race Readiness: POOR / NOT READY
- TSB <+5 projected, CTL unstable, Readiness declining, red flags
- Message: "⚠️ Readiness concerning. Consider: DNS, adjust expectations, or last-ditch rest."
- **Use AskUserQuestion** to present options with trade-offs

**For complete readiness messaging templates**: See [references/decision_trees.md](references/decision_trees.md)

---

### Step 4: Race Week Schedule

**Generate schedule based on distance**:
- **5K/10K**: [templates/race_week_5k.md](templates/race_week_5k.md)
- **Half Marathon**: [templates/race_week_half.md](templates/race_week_half.md)
- **Marathon**: [templates/race_week_marathon.md](templates/race_week_marathon.md)

**Key principles**:
- Maintain routine, reduce volume
- Final hard workout: 5K (3 days out), Marathon (10 days out)
- Race-pace strides 2-3 days before race
- Complete rest 1-2 days before race

---

### Step 5: Race Day Strategy

**Develop race plan based on**: Goal, VDOT predictions, fitness (CTL), course, weather

#### Pacing Strategy

```bash
# Get VDOT predictions
sce vdot predict --race-type 10k --time 42:30 --goal-race half_marathon
```

**Three approaches**:
1. **Conservative** (recommended): Start 5-10s/km slower, settle → hold → push
2. **Aggressive** (experienced + excellent taper): Start at goal, hold, push final 1/4
3. **Negative split** (marathons): First half 2-5s/km slower, second half at/faster than goal

**Example pacing (Half, 1:30:00 = 4:16/km)**:
- Miles 1-4: 4:20-4:25/km (settle)
- Miles 5-10: 4:15-4:18/km (goal pace)
- Miles 11-13.1: 4:10-4:15/km (push)

#### Environmental Adjustments

```bash
# Adjust for heat
sce vdot adjust --pace 4:15 --condition heat --severity 28
```

**Quick adjustments**:
- **Heat**: +3-5s/km per 5°C above 15°C
- **Wind**: Headwind +5-10s/km, shelter behind runners
- **Rain**: Minimal pace impact, watch slippery surfaces

#### Mental Strategy

**Chunking**: 10K (2×5K), Half (3×7K), Marathon (4×10K)
**Mantras**: "Smooth and steady", "Trust the training"
**Pain cave** (final 20-25%): Focus on form, count to 100, landmark to landmark

---

### Step 6: Pre-Race Checklist

See [templates/pre_race_checklist.md](templates/pre_race_checklist.md) for complete 3-day countdown.

**Key items**:
- Carb load 3 days before (8-10g/kg body weight)
- Test all race gear 2 days before
- Sleep well 2 nights before (matters more than night before)
- Wake 3 hours before race
- **Nothing new on race day**

---

### Step 7: Present Race Preparation Plan

**Create comprehensive race prep document** using template at [templates/race_preparation.md](templates/race_preparation.md).

Write to `/tmp/race_preparation_YYYY_MM_DD.md` with:
- Taper status (readiness, metrics, assessment)
- Race week schedule (day-by-day workouts)
- Race day strategy (pacing, environmental, mental, course)
- Pre-race checklist (3-day countdown)
- Nutrition & hydration plan
- Mental preparation (goals, visualization, mantras)
- Post-race recovery protocol

**Present to athlete**:
- Highlight key readiness indicators
- Build confidence with concrete data
- Provide clear, actionable race day plan

---

### Step 8: Post-Race Memory Capture

**After race completion, capture significant experiences:**

```bash
# Taper response
sce memory add --type TRAINING_RESPONSE \
  --content "10-day taper felt optimal, felt strong at race start" \
  --tags "taper:10-days,race:10k,feeling:strong" \
  --confidence high

# Pacing strategy outcome
sce memory add --type TRAINING_RESPONSE \
  --content "Conservative start (5s/km slower) allowed strong finish" \
  --tags "race:pacing,strategy:conservative,outcome:success" \
  --confidence high

# Nutrition/gear
sce memory add --type PREFERENCE \
  --content "Pre-race oatmeal 3h before worked perfectly" \
  --tags "nutrition:pre-race,timing:3h,food:oatmeal" \
  --confidence high
```

**Patterns to capture**: Taper duration, pacing outcomes, nutrition/gear, mental strategies, body responses

---

## Quick Decision Trees

### Q: TSB projected +18 (very fresh) - Over-tapered?
1. Check CTL: Declining >5 points? If yes, add short quality session
2. If no, maintain current approach - some athletes perform well at +15-20
3. Athlete feeling sluggish? Add race-pace strides

### Q: Readiness declining during taper
1. Investigate: Sleep? Stress? Illness?
2. If illness: Use decision tree in [references/edge_cases.md](references/edge_cases.md)
3. If stress: Extra rest day, address anxiety
4. If unknown: Monitor 24-48h, add rest if continues declining

### Q: TSB still negative 3 days out, athlete feels great
1. Trust data over feelings - TSB is predictive
2. Add 1-2 extra rest days
3. Re-run taper-status after rest
4. If still negative: Consider adjusting race expectations

**For complete decision guidance**: See [references/decision_trees.md](references/decision_trees.md)

---

## Common Taper Mistakes

See [references/taper_mistakes.md](references/taper_mistakes.md) for detailed explanations:

1. **Training Through Taper** - Doesn't trust rest, keeps training hard
2. **Complete Rest (Couch Taper)** - No running, loses sharpness
3. **Pre-Race Jitters** - Adds extra workouts from anxiety
4. **Carb Depletion** - Outdated method, risky
5. **New Gear on Race Day** - Blister/chafing risk

**Golden rule**: "Nothing new on race day"

---

## Additional Resources

**Decision support**:
- [Decision Trees](references/decision_trees.md) - Common taper decisions with scenarios
- [Edge Cases](references/edge_cases.md) - Race canceled, illness, injury, over-taper

**Reference material**:
- [Taper Mistakes](references/taper_mistakes.md) - 5 mistakes with detailed coaching responses
- [VDOT Prediction](references/vdot_prediction.md) - Performance prediction guidance
- [Taper Trajectories](references/taper_trajectories.md) - Distance-specific TSB progressions
- [CLI Reference](references/cli_reference.md) - Command quick reference

**Templates**:
- [Race Week Schedules](templates/) - 5K, 10K, Half, Marathon day-by-day
- [Pre-Race Checklist](templates/pre_race_checklist.md) - 3-day countdown + gear
- [Race Preparation Template](templates/race_preparation.md) - Complete output format

**Training methodology**:
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md) - Pfitzinger taper protocols
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md) - VDOT predictions
- [Faster Road Racing](../../../docs/training_books/faster_road_racing_pete_pfitzinger.md) - 5K-Half tactics
- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md) - Pacing strategies
- [Coaching Methodology](../../../docs/coaching/methodology.md) - TSB interpretation

---

## Related Skills

- **training-plan-design**: Taper structure from original plan
- **injury-risk-management**: TSB/ACWR for readiness assessment
- **daily-workout**: Race week workout guidance
- **plan-adaptation**: Taper adjustment if needed
