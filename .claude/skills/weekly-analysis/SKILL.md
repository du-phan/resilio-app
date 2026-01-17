---
name: weekly-analysis
description: Comprehensive weekly training review including adherence analysis, intensity distribution validation (80/20), multi-sport load breakdown, and pattern detection. Use when athlete asks "how was my week?", "weekly review", "analyze training", or "did I follow the plan?".
allowed-tools: Bash, Read, Write
---

# Weekly Analysis: Comprehensive Training Review

## Overview

This skill provides a complete weekly training analysis by:
1. Comparing planned vs. actual training (adherence)
2. Validating intensity distribution (80/20 rule)
3. Analyzing multi-sport load breakdown
4. Detecting patterns and suggesting adaptations for next week

**Key principle**: Use computational tools to calculate adherence, intensity, and load; apply coaching judgment to interpret patterns and suggest improvements.

## Workflow

### Step 1: Get Weekly Summary

Retrieve the current week's activities and planned workouts.

**Command**:
```bash
sce week
```

**What this returns**:
- `planned_workouts`: What was scheduled this week
- `completed_activities`: What athlete actually did (all sports)
- `current_metrics`: CTL/ATL/TSB/ACWR/readiness
- `week_changes`: Metric changes from last week
- `week_number`: Current training week (if in plan)

**Parse key data**:
- Total planned workouts: X
- Completed running workouts: Y
- Other activities (climbing, cycling, etc.): Z
- Planned volume vs. actual volume

### Step 2: Adherence Analysis

Compare planned workouts to completed activities.

**Command**:
```bash
sce analysis adherence --week [WEEK_NUMBER] --planned [PLAN_FILE] --completed [ACTIVITIES_FILE]
```

**What this returns**:
- `completion_rate`: Percentage of planned workouts completed (0-100%)
- `load_variance`: Actual load vs. planned load (systemic AU)
- `workout_type_adherence`: Breakdown by type (easy, tempo, long, intervals)
- `missed_workouts`: List of skipped workouts with types
- `extra_activities`: Unplanned activities athlete added
- `patterns`: Detected patterns (e.g., "consistently skips Tuesday runs")

**Interpretation zones**:
- **≥90%**: Excellent adherence - on track
- **70-89%**: Good adherence - minor adjustments needed
- **50-69%**: Fair adherence - discuss barriers
- **<50%**: Poor adherence - major replanning needed

### Step 3: Intensity Distribution Analysis

Validate 80/20 intensity distribution (80% easy, 20% moderate+hard).

**Command**:
```bash
sce analysis intensity --activities [ACTIVITIES_FILE] --days 7
```

**What this returns**:
- `distribution`: Percentage breakdown by intensity zone
  - Low intensity (Z1-Z2): Should be ~80%
  - Moderate+high (Z3-Z5): Should be ~20%
- `compliance`: Boolean - meets 80/20 guideline?
- `polarization_score`: How well training separates easy from hard (0-100)
- `violations`: Specific issues (e.g., "too much moderate intensity", "gray zone training")
- `recommendations`: Suggested adjustments

**Common violations**:
1. **Moderate-intensity rut**: 65/35 distribution (everything at medium effort)
2. **Too much hard**: 75/25 distribution (easy runs too hard)
3. **Poor polarization**: Lots of RPE 6 (not easy, not hard)

**Why 80/20 matters**: Elite endurance athletes spend ~80% of training at low intensity. This maximizes aerobic development while minimizing injury risk and allowing recovery for quality sessions.

### Step 4: Multi-Sport Load Breakdown

Analyze load distribution across all sports (running, climbing, cycling, etc.).

**Command**:
```bash
sce analysis load --activities [ACTIVITIES_FILE] --days 7 --priority [PRIORITY]
```

**What this returns**:
- `systemic_load_by_sport`: Breakdown of cardio/whole-body load by activity
- `lower_body_load_by_sport`: Leg strain breakdown
- `priority_adherence`: How well schedule respected running priority
- `fatigue_flags`: Warning signals (e.g., "high lower-body load from cycling before long run")

**Example output**:
```json
{
  "systemic_load_by_sport": {
    "running": 850 AU (60%),
    "climbing": 420 AU (30%),
    "yoga": 140 AU (10%)
  },
  "lower_body_load_by_sport": {
    "running": 850 AU (85%),
    "climbing": 52 AU (5%),
    "cycling": 100 AU (10%)
  },
  "priority_adherence": "good",
  "fatigue_flags": [
    "Tuesday climbing (340 AU systemic, 52 AU lower-body) may have impacted Wednesday tempo quality"
  ]
}
```

**Interpretation**:
- If running is PRIMARY: Should be 60-70% of systemic load
- If EQUAL priority: Running ~40-50% of load
- Lower-body load: Watch for spikes that gate quality runs

### Step 5: Pattern Detection

Identify trends and recurring issues from the week's data.

**First, review activity notes for qualitative signals**:
```bash
# List this week's activities with notes
sce activity list --since 7d --has-notes

# Search for wellness signals
sce activity search --query "tired fatigue flat heavy" --since 7d

# Search for pain/discomfort signals
sce activity search --query "pain sore tight discomfort" --since 7d
```

**Activity notes provide qualitative context** that metrics miss:
- "Felt flat on the long run" → fatigue accumulating despite OK metrics
- "Legs heavy from climbing yesterday" → multi-sport interaction signal
- "Best tempo in months" → positive adaptation signal

**Patterns to look for**:

1. **Consistency patterns**:
   - "Completed all weekday runs, skipped weekend long run" (schedule conflict?)
   - "Ran 4/4 planned workouts" (excellent)
   - "Missed Tuesday runs 3 weeks in a row" (systemic barrier)

2. **Intensity patterns**:
   - "Easy runs too fast (RPE 6 instead of 4)" (moderate-intensity rut)
   - "Tempo pace slower than prescribed" (fatigue? or VDOT outdated?)
   - "All runs within prescribed zones" (excellent discipline)

3. **Multi-sport patterns**:
   - "Climbing sessions consistently preceded by rest days" (good planning)
   - "Long run scheduled day after climbing comp" (conflict)
   - "Cycling volume increased 40% this week" (contributing to ACWR spike)

4. **Volume patterns**:
   - "Weekly volume: 22 km → 35 km (+59%)" (progression too aggressive)
   - "Consistent 40-45 km/week for 4 weeks" (stable, safe)
   - "Volume dropped 50% without planned recovery week" (illness? life stress?)

5. **Adaptation patterns**:
   - "ACWR trended from 1.1 → 1.4 this week" (approaching caution zone)
   - "Readiness declined from 68 → 45" (accumulating fatigue)
   - "TSB dropped from -8 → -18" (productive but monitor closely)

### Step 5.5: Capture Significant Patterns as Memories

**When a pattern appears 3+ times or is highly significant, persist it as a memory for future coaching context.**

**Patterns to capture**:

1. **Consistency patterns** (3+ occurrences):
   ```bash
   sce memory add --type TRAINING_RESPONSE \
     --content "Consistently skips Tuesday runs due to work schedule" \
     --tags "schedule:tuesday,pattern:skip" \
     --confidence high
   ```

2. **Intensity patterns** (recurring):
   ```bash
   sce memory add --type TRAINING_RESPONSE \
     --content "Easy runs consistently 0.5 min/km too fast (RPE 6 instead of 4)" \
     --tags "intensity:easy,violation:pace" \
     --confidence high
   ```

3. **Multi-sport conflicts** (if detected):
   ```bash
   sce memory add --type INSIGHT \
     --content "Long run scheduled day after climbing comp consistently impacts quality" \
     --tags "sport:climbing,conflict:schedule" \
     --confidence high
   ```

4. **Volume tolerance** (if observed):
   ```bash
   sce memory add --type TRAINING_RESPONSE \
     --content "Volume increases >15% per week consistently trigger ACWR spikes above 1.4" \
     --tags "volume:progression,acwr:spike,injury-risk:high" \
     --confidence high
   ```

5. **Recovery patterns** (if significant):
   ```bash
   sce memory add --type CONTEXT \
     --content "Reports feeling flat after hard climbing sessions" \
     --tags "recovery:poor,sport:climbing,readiness:low" \
     --confidence medium
   ```

**Guidelines**:
- Only capture patterns with 3+ occurrences or high coaching significance
- Use HIGH confidence for 3+ occurrences, MEDIUM for 2 occurrences
- Tag appropriately for future retrieval (e.g., `schedule:tuesday`, `body:knee`, `sport:climbing`)
- Deduplication is automatic - if similar memory exists, occurrences will increment

### Step 6: Synthesize and Communicate

Combine all analyses into a coherent weekly review.

**Structure**:
1. **Opening**: Overall summary (positive reinforcement + key stat)
2. **Adherence**: What was planned vs. completed
3. **Intensity**: 80/20 compliance, violations if any
4. **Load**: Multi-sport breakdown, any concerns
5. **Patterns**: Notable trends (positive and concerning)
6. **Metrics**: CTL/ATL/TSB/ACWR changes from last week
7. **Next Week**: Recommendations and focus areas

**Example synthesis**:
```
Great week! You completed 7/8 planned workouts (88% adherence) and your CTL increased from 42 → 44.

Adherence:
- Completed all quality sessions (tempo, intervals)
- Skipped Thursday easy run (noted you were traveling)
- Added 2 climbing sessions (60-minute lead session, 90-minute bouldering)

Intensity (80/20):
- Distribution: 78% easy, 22% hard (excellent compliance)
- Your easy runs stayed at RPE 3-4 (conversational)
- Tempo and intervals hit prescribed paces

Multi-Sport Load:
- Running: 850 AU systemic, 850 AU lower-body (62% of total load)
- Climbing: 420 AU systemic, 52 AU lower-body (30% of load)
- Good balance for EQUAL priority setting

Patterns:
+ Consistent Tuesday climbing doesn't impact Wednesday tempo quality
+ Long run completed as planned (18 km at 6:15/km)
⚠ ACWR increased from 1.1 → 1.28 (safe range but trending up)
⚠ Readiness dropped from 72 → 58 (moderate, monitor)

Metrics changes (from last week):
- CTL: 42 → 44 (+2, steady progression)
- ATL: 118 → 132 (+14, load spike this week)
- TSB: -10 → -15 (-5, moving into productive zone)
- ACWR: 1.1 → 1.28 (+0.18, watch next week)

Next Week Recommendations:
1. Maintain current volume (40-45 km) - don't increase
2. Monitor ACWR - if it reaches 1.3+, reduce intensity
3. Consider recovery week after next (4th week = recovery cycle)
4. Keep easy runs truly easy (RPE 3-4, no drift)

Overall: Solid training week with good adherence and intensity discipline. Watch ACWR trend - if it continues rising, we'll dial back next week.
```

---

## Decision Trees

### Q: Adherence is poor (<50%)

**Scenario**: Athlete completed 3/8 planned workouts.

**Approach**:
1. **Don't criticize**: "Life happens - let's understand what got in the way."
2. **Investigate barriers**:
   - Ask: "What made it hard to stick to the plan this week?"
   - Common barriers: Work stress, family commitments, illness, injury, motivation
3. **Assess cause**:
   - **External (life stress)**: "Understandable - work deadline or family event?"
   - **Plan mismatch**: "Is the plan too ambitious for your current schedule?"
   - **Motivation**: "Feeling burnt out or questioning the goal?"
   - **Physical**: "Any injury or illness signals?"
4. **Adapt plan**:
   - If external: "No problem - let's adjust this week's plan"
   - If plan mismatch: "Let's replan with more realistic constraints" → Activate `plan-adaptation` skill
   - If motivation: "Let's revisit your goal and why you're training"
   - If physical: Check metrics, consider injury/illness protocol

**Key**: Treat low adherence as **information**, not failure.

### Q: Intensity distribution violates 80/20

**Scenario**: Distribution is 65% easy, 35% moderate+hard (moderate-intensity rut).

**Response**:
```
Your intensity distribution this week was 65/35 (should be ~80/20). This means too much moderate-intensity work (RPE 5-6) - the "gray zone".

Why this matters:
- Moderate intensity doesn't provide enough stimulus for adaptation (not hard enough)
- But it's too hard to recover from (not easy enough)
- Result: Fatigue accumulates without performance gains

Looking at your runs:
- Tuesday easy: 6:00/km pace → RPE 6 (should be RPE 3-4 at 6:45-7:15/km)
- Thursday easy: 5:45/km pace → RPE 6 (should be RPE 3-4)
- Your "easy" runs are actually tempo pace

Next week:
- Slow down easy runs to conversational pace (you should be able to talk in full sentences)
- Target: 6:45-7:15/km for easy (based on your VDOT 48)
- Check: If you can't talk easily, slow down

This will feel "too slow" at first - that's normal. Easy runs build aerobic base without fatigue.
```

**Action**: Provide specific pace zones from VDOT for next week's easy runs.

### Q: Multi-sport conflict impacting running

**Scenario**: Climbing comp on Friday (600 AU systemic, 80 AU lower-body) followed by long run Saturday (athlete felt sluggish).

**Analysis**:
```
I see the pattern: Your climbing comp Friday generated high systemic load (600 AU), and your long run Saturday felt harder than expected.

Here's what happened:
- Systemic load (600 AU) accumulated from upper-body work
- Even though lower-body load was low (80 AU), cardio fatigue carried over
- Result: Long run felt RPE 6-7 instead of RPE 4

Two options for next time:
1. Move long run to Sunday (24-hour recovery from Friday comp)
2. Keep Saturday long run but reduce intensity expectation (it will feel harder, and that's okay)

Based on your conflict policy (ask each time), which sounds better for future comps?
```

**Store preference** for future planning.

### Q: Volume increased too quickly

**Scenario**: 30 km → 48 km in one week (+60%, violates 10% rule).

**Response**:
```
Your volume jumped from 30 km → 48 km this week (+60%). The 10% progression guideline recommends ≤33 km for this week.

I see why it happened:
- You added an unplanned 12 km long run Saturday
- You felt good, so you ran 8 km Tuesday instead of 6 km

This contributed to your ACWR spike (1.15 → 1.42).

For next week:
- Pull back to 35-40 km (don't compound the spike)
- Let your body adapt to the increased load
- ACWR should drop back to <1.3 with this adjustment

Remember: Training is about *consistency* over time, not weekly heroics. Better to undershoot and stay healthy than overshoot and get injured.
```

**Command for validation**:
```bash
sce guardrails progression --previous 30 --current 48
```

### Q: Athlete wants to increase volume despite concerns

**Scenario**: ACWR is 1.35 (caution zone), athlete says "But I feel fine, I want to do more."

**Response**:
```
I hear you - you feel good, and that's great. Here's the challenge:

ACWR is a *leading* indicator (predicts injury before it happens), not a lagging one. Athletes often feel fine right before an injury strikes.

Your current ACWR of 1.35 means you're at 1.5-2x baseline injury risk. Not guaranteed, but elevated.

Here's a compromise:
- This week: Maintain current volume (don't increase)
- Next week: If ACWR drops to <1.3, we can increase volume by 10%
- If ACWR stays elevated: Hold steady for another week

This way, we let your body adapt to the current load before adding more. Sound fair?

Remember: The goal is to get to race day healthy and trained, not just trained.
```

**Balance athlete motivation with objective risk**.

---

## Patterns Library

### Positive Patterns (Reinforce)

1. **Consistent adherence**: "You've completed 90%+ of planned workouts for 3 weeks straight - excellent discipline!"
2. **Good intensity discipline**: "Your easy runs stayed truly easy (RPE 3-4) - this is rare and impressive."
3. **Smart multi-sport planning**: "You scheduled climbing on rest days from running - great load management."
4. **Progressive volume**: "You've increased from 30 → 40 km over 6 weeks (~5% per week) - textbook progression."

### Concerning Patterns (Flag Proactively)

1. **ACWR trending up**: "ACWR has climbed from 1.0 → 1.25 → 1.35 over 3 weeks - let's cap volume next week."
2. **Consistent skipped workouts**: "You've skipped Tuesday runs 4 weeks in a row - is Tuesday a tough day for you?"
3. **Declining readiness**: "Readiness dropped from 75 → 68 → 58 over 3 weeks - accumulating fatigue?"
4. **Moderate-intensity rut**: "Your easy runs have averaged RPE 5-6 for 3 weeks - need to slow down."
5. **Volume spikes**: "You increased volume 25% last week, 30% this week - compounding ACWR risk."

### Neutral Patterns (Acknowledge)

1. **Weekend warrior**: "You do 70% of weekly volume on weekends - works for your schedule."
2. **Variable week-to-week**: "Your volume varies 30-50 km depending on climbing schedule - flexibility is fine."
3. **Cross-training heavy**: "Running is 40% of systemic load, climbing 50% - aligns with EQUAL priority."

---

## Output Template

Use this structure for consistent weekly reviews:

```markdown
# Weekly Review: Week [N] ([DATE_RANGE])

## Summary
[One sentence: overall assessment + key achievement]

## Adherence
**Completion rate**: [X]% ([Y]/[Z] workouts)

Completed:
- [List completed workouts]

Missed:
- [List missed workouts with brief reason if known]

Extra activities:
- [List unplanned activities]

## Intensity Distribution (80/20)
**Distribution**: [X]% easy, [Y]% moderate+hard
**Compliance**: [✓ Yes / ✗ No]

[If violations:]
- [Specific issue, e.g., "Easy runs too fast (RPE 6 instead of 4)"]
- [Recommendation for next week]

## Multi-Sport Load
**Total systemic load**: [X] AU
- Running: [X] AU ([Y]%)
- [Other sport]: [X] AU ([Y]%)

**Total lower-body load**: [X] AU
- Running: [X] AU ([Y]%)
- [Other sport]: [X] AU ([Y]%)

**Priority adherence**: [good/fair/poor]

[If concerns:]
- [Flag, e.g., "High climbing load Tuesday may have impacted Wednesday tempo"]

## Patterns
**Positive**:
- [Reinforce good habits]

**Concerning** (if any):
- [Flag proactively]

## Metrics (Week-over-week changes)
- **CTL**: [prev] → [current] ([change])
- **ATL**: [prev] → [current] ([change])
- **TSB**: [prev] → [current] ([change])
- **ACWR**: [prev] → [current] ([change])

**Interpretation**: [Brief 1-2 sentence summary]

## Next Week Recommendations
1. [Primary recommendation]
2. [Secondary recommendation]
3. [Tertiary recommendation]

**Focus for next week**: [One key theme, e.g., "Maintain intensity discipline, cap volume"]

## Overall Assessment
[2-3 sentences: big picture, progress toward goal, encouragement]
```

---

## Common Pitfalls

### 1. Focusing only on negatives

❌ **Bad**: "You missed 2 workouts, your ACWR is elevated, intensity is off"
✅ **Good**: "Solid week! You nailed all quality sessions. Let's fine-tune easy run pace and watch ACWR next week."

**Start with positive reinforcement**, then address concerns.

### 2. Not contextualizing adherence

❌ **Bad**: "You only completed 60% of workouts"
✅ **Good**: "You completed 60% due to work travel - understandable. When you did train, quality was excellent."

**Understand *why* adherence was low** before interpreting.

### 3. Ignoring 80/20 violations

❌ **Bad**: "Your training looks good this week"
✅ **Good**: "Training looks good, but I notice easy runs are RPE 5-6 (should be 3-4). This can lead to chronic fatigue."

**Proactively flag moderate-intensity rut** - it's the #1 mistake recreational athletes make.

### 4. Not synthesizing multi-sport data

❌ **Bad**: "You ran 40 km this week, climbed 3 times" (separate silos)
✅ **Good**: "Your 40 km running + 3 climbing sessions totaled 1,200 AU systemic load - higher than planned. This drove ACWR to 1.32."

**Connect the dots** between sports to explain load spikes.

### 5. Generic recommendations

❌ **Bad**: "Try to stick to the plan next week"
✅ **Good**: "Next week: (1) Slow easy runs to 6:45-7:15/km, (2) Cap volume at 40 km, (3) Monitor ACWR - if >1.3, reduce intensity"

**Specific, actionable recommendations** with concrete numbers.

---

## Links to Additional Resources

- **80/20 philosophy**: See [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md)
- **Adherence patterns**: See [Coaching Scenarios - Weekly Review](../../../docs/coaching/scenarios.md#scenario-5-weekly-review)
- **Analysis commands**: See [CLI Reference - Analysis Commands](../../../docs/coaching/cli_reference.md#analysis-commands)
- **Multi-sport load model**: See [Coaching Methodology - Sport Multipliers](../../../docs/coaching/methodology.md#sport-multipliers--load-model)
- **ACWR interpretation**: See [Coaching Methodology - ACWR](../../../docs/coaching/methodology.md#acwr-acutechronic-workload-ratio)
