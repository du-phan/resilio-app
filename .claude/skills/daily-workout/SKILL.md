---
name: daily-workout
description: Provide daily workout recommendations with adaptation logic based on current metrics, triggers, and risk assessment. Use when athlete asks "what should I do today?", "today's workout", "run recommendation", or "should I train today?".
allowed-tools: Bash, Read, AskUserQuestion
---

# Daily Workout: Adaptive Recommendation

## Overview

This skill provides intelligent daily workout recommendations by:
1. Checking scheduled workout from training plan
2. Assessing current state (CTL/ATL/TSB/ACWR/readiness)
3. Detecting adaptation triggers (injury risk, fatigue, overtraining)
4. Presenting options with trade-offs when triggers detected

**Key principle**: Tools detect triggers; you interpret with athlete context and present options.

---

## Workflow

### Step 0: Retrieve Relevant Context

**Before making recommendations, load athlete's training response patterns, preferences, AND recent activity notes.**

```bash
sce memory list --type TRAINING_RESPONSE          # Training response patterns
sce memory search --query "readiness recovery"    # Recovery patterns
sce activity list --since 3d --has-notes          # Recent wellness signals
sce activity search --query "pain sore" --since 7d  # Pain mentions
```

**Recent activity notes reveal real-time wellness**:
- Yesterday's note "ankle felt tight at end" → monitor today
- Last 3 days "felt great, strong legs" → green light for quality
- 2 days ago "stopped early, knee pain" → downgrade today

**Use retrieved memories**: Reference patterns when presenting options ("I know you typically push through low readiness, but...")

---

### Step 1: Get Scheduled Workout

```bash
sce today
```

**Returns**:
- `workout`: Today's scheduled workout (type, distance, pace, duration)
- `current_metrics`: CTL/ATL/TSB/ACWR/readiness with interpretations
- `adaptation_triggers`: List of detected triggers (if any)
- `rationale`: Why this workout was prescribed

**If no plan exists**: "You don't have a training plan yet. Would you like me to design one based on your goal? Or I can suggest a workout based on your current fitness (CTL X)."

---

### Step 2: Assess Current State

**From `sce today` response, extract**:
- **CTL**: Current fitness level (e.g., 44 = "solid recreational fitness")
- **TSB**: Form/freshness (e.g., -8 = "productive training zone")
- **ACWR**: Injury risk (e.g., 1.35 = "slightly elevated - caution zone")
- **Readiness**: Daily go/no-go score (e.g., 55 = "moderate readiness")

---

### Step 3: Detect Adaptation Triggers

**Common triggers** (from `sce today` response):

| Trigger                  | Threshold    | Severity | Typical Response                       |
|--------------------------|--------------|----------|----------------------------------------|
| `acwr_high_risk`         | ACWR > 1.5   | HIGH     | Downgrade or skip workout              |
| `acwr_elevated`          | ACWR > 1.3   | MODERATE | Consider downgrade, discuss options    |
| `readiness_very_low`     | Readiness<35 | HIGH     | Force rest or easy recovery            |
| `readiness_low`          | Readiness<50 | LOW      | Downgrade quality workouts             |
| `tsb_overreached`        | TSB < -25    | HIGH     | Reduce training load immediately       |
| `lower_body_load_high`   | Dynamic      | MODERATE | Delay running quality/long runs        |
| `session_density_high`   | 2+ hard/7d   | MODERATE | Space out quality sessions             |

**For detailed trigger interpretations**: See [references/triggers.md](references/triggers.md)

**If NO triggers**: Proceed with planned workout (Step 4)
**If triggers detected**: Present options (Step 5)

---

### Step 4: Proceed with Planned Workout (No Triggers)

When metrics are within safe ranges, recommend the planned workout with context.

**Template**:
```
Your [workout_type] is scheduled for today: [distance] at [pace] ([duration]).

Current state:
- CTL: [value] ([interpretation])
- TSB: [value] ([zone])
- ACWR: [value] (safe range)
- Readiness: [value] ([level])

This workout is designed to [purpose]. Your metrics look good - proceed as planned.

[Optional: Tips based on workout type]
```

**Example**: Tempo run with good metrics - provide warm-up tips, pace guidance, effort level (RPE 7-8).

**For complete examples**: See [examples/example_quality_day_ready.md](examples/example_quality_day_ready.md)

---

### Step 5: Adaptation Decision (Triggers Detected)

When triggers are detected, interpret with athlete context and present options with trade-offs.

#### 5a. Assess Risk (if not in `sce today` response)

```bash
sce risk assess --metrics metrics.json --recent activities.json
```

**Returns**:
- `overall_risk_level`: low, moderate, high, very_high
- `injury_probability`: percentage (0-100%)
- `contributing_factors`: List of risk contributors

#### 5b. Present Options with Context (AskUserQuestion)

**Pattern**:
1. State current metrics with interpretations
2. Explain what's scheduled
3. Present 3-4 options with specific trade-offs
4. Include your recommendation

**Example options for ACWR elevated (1.35) + moderate readiness (55)**:

1. **Easy 30-minute run (safest)** - Maintains aerobic base, reduces ACWR, ~8-10% injury risk
2. **Move workout to Thursday** - Gives 2 extra recovery days, fresh legs for quality
3. **Shorten workout by 50%** - Still gets stimulus, ~12-15% injury risk
4. **Proceed as planned** - ~15-18% injury risk, only if feeling strong

**For complete decision scenarios**: See [references/decision_trees.md](references/decision_trees.md)

**For worked examples**: See:
- [examples/example_quality_day_adjusted.md](examples/example_quality_day_adjusted.md) - ACWR elevated, shortened intervals
- [examples/example_rest_day_triggered.md](examples/example_rest_day_triggered.md) - Very low readiness + high ACWR
- [examples/example_multi_sport_conflict.md](examples/example_multi_sport_conflict.md) - Climbing comp vs long run

---

### Step 6: Log Decision and Rationale

After athlete decides, explain the reasoning behind the recommendation.

**If athlete chose downgrade**:
```
Smart decision. Here's why this makes sense:
- [Explain metric implications]
- [Reference research/risk levels]
- [Describe benefits of downgrade]

Your adjusted workout: [details]
```

**If athlete chose to proceed despite triggers**:
```
I understand you want to stick with the plan. Here's what to watch for:
- Any sharp or sudden pain → stop immediately
- Monitor [known injury area] closely
- If it feels harder than [expected RPE], dial back

Your workout: [details]

If you feel off during the run, it's okay to downgrade mid-workout. Better to adjust than risk injury.
```

---

### Step 7: Capture Significant Patterns as Memories

**After athlete makes decisions (especially when overriding recommendations), capture recurring patterns.**

**When to capture**: Pattern appears 3+ times

**Example patterns**:

**Override pattern** (athlete overrides rest 3+ times):
```bash
sce memory add --type TRAINING_RESPONSE \
  --content "Prefers to train through low readiness (<40), proceeds with planned workout despite elevated ACWR" \
  --tags "readiness:override,acwr:elevated,preference:train-through" \
  --confidence high
```

**Recovery pattern** (observed 2+ times):
```bash
sce memory add --type TRAINING_RESPONSE \
  --content "Reports feeling flat after back-to-back quality days (intervals + tempo)" \
  --tags "recovery:poor,quality:consecutive,pattern:fatigue" \
  --confidence medium
```

**Guidelines**:
- HIGH confidence for 3+ occurrences
- MEDIUM for 2 occurrences
- Include specific thresholds (e.g., "readiness <40", "ACWR >1.3")

---

## Quick Reference: Metric Interpretation

### ACWR (Acute:Chronic Workload Ratio)

| ACWR Value | Zone    | Injury Risk        | Response                              |
|------------|---------|-------------------|---------------------------------------|
| 0.8-1.3    | Safe    | Normal (baseline) | Proceed as planned                    |
| 1.3-1.5    | Caution | Elevated (1.5-2x) | Consider downgrade, discuss options   |
| > 1.5      | Danger  | High (2-4x)       | Strongly recommend downgrade or rest  |

**How to bring ACWR down**: Rest day (fastest), easy runs 3-5 days, cross-training if lower-body issue.

**For complete ACWR guide**: See [references/triggers.md#acwr](references/triggers.md)

### Readiness Score

| Readiness | Level     | Interpretation              | Response                           |
|-----------|-----------|-----------------------------|------------------------------------|
| < 35      | Very Low  | Significant fatigue/illness | Force rest or very easy recovery   |
| 35-50     | Low       | Moderate fatigue            | Downgrade quality workouts         |
| 50-70     | Moderate  | Normal training state       | Proceed as planned                 |
| 70-85     | Good      | Fresh, ready for work       | Quality sessions encouraged        |
| > 85      | Excellent | Peak readiness              | Hard sessions, races               |

**Components**: TSB (20%), recent trend (25%), sleep (25%), wellness (30%)

### TSB (Training Stress Balance)

| TSB Range  | State       | Response                     |
|------------|-------------|------------------------------|
| < -25      | Overreached | Reduce load immediately      |
| -25 to -10 | Productive  | Continue building            |
| -10 to +5  | Fresh       | Schedule quality sessions    |
| +5 to +15  | Race Ready  | Race week                    |
| > +15      | Detraining  | Increase training            |

**For complete trigger interpretations**: See [references/triggers.md](references/triggers.md)

---

## Quick Decision Trees

### Q: No training plan exists

**Response**:
```
You don't have a training plan yet. I can either:
A) Design a full training plan based on your goal (recommended)
B) Suggest a single workout based on your current fitness (CTL X)

If option B: Easy 6-8 km at conversational pace (RPE 3-4)
```

### Q: Athlete mentions subjective wellness

**Approach**:
1. Check metrics: `sce status`
2. Ask clarifying questions: "How tired? Normal fatigue or unusual?"
3. **If wellness conflicts with metrics**: Trust subjective feel over metrics
4. **If wellness aligns with metrics**: Confirm with data

**Key**: Wellness signals override metrics when in conflict.

### Q: Multi-sport conflict

**Check conflict_policy** first:
- `primary_sport_wins`: Protect primary sport, adjust running
- `running_goal_wins`: Keep key runs unless injury risk
- `ask_each_time`: Present trade-offs with AskUserQuestion

**If `ask_each_time`**: Present 3-4 options showing pros/cons for each choice, include recommendation based on goal proximity and athlete priority.

### Q: Athlete wants to "feel it out"

**Response**:
```
Good approach. Start with: Easy pace for 10 minutes (warm-up)
Then assess:
- If you feel great → proceed with planned workout
- If you feel okay → shorten workout by 50%
- If you feel off → keep it easy for 20-30 minutes total

Listen to your body. Better to underdose than overdose.
```

### Q: Athlete disagrees with metrics

**Balance objective data with subjective feel** - don't dismiss either.

**If feels fine but metrics show risk**:
```
I trust your subjective feel. Here's the tension: [metric] is [value] ([risk]).

ACWR is a leading indicator (predicts future), not lagging (reacts to current pain).

Proceed if you want, but with guardrails:
- Monitor closely for any discomfort
- At first sign of pain, downgrade immediately
```

**If feels bad but metrics look fine**:
```
Metrics show [interpretation], but you know your body best. There may be factors metrics don't capture: stress, sleep, illness.

Let's downgrade to [easy option]. Better safe than sorry.
```

**For complete decision trees**: See [references/decision_trees.md](references/decision_trees.md)

---

## Common Pitfalls

1. **Ignoring subjective wellness**
   - ❌ "Your metrics look fine, do the tempo" (athlete says exhausted)
   - ✅ "Metrics show readiness 72, but you know your body best. Let's downgrade."

2. **Not providing specific trade-offs**
   - ❌ "You could rest, or run easy, or do the tempo"
   - ✅ "Easy run maintains aerobic base (pro) but delays threshold work (con). Tempo gives stimulus (pro) but 15% injury risk (con)."

3. **Over-relying on ACWR alone**
   - ❌ "ACWR is 1.28, you're fine" (ignoring readiness 35, TSB -23)
   - ✅ "ACWR is safe, but readiness and TSB suggest fatigue. Let's downgrade."

4. **Not explaining rationale**
   - ❌ "Do easy run instead"
   - ✅ "Easy run reduces ACWR (currently 1.35) while maintaining aerobic stimulus."

5. **Forcing downgrade without athlete input**
   - ❌ "You must rest today" (no options)
   - ✅ "I strongly recommend rest (ACWR 1.52, readiness 32). But if you want to run, here's the safest option: easy 20 minutes."

---

## Additional Resources

**Reference material**:
- [Trigger Interpretations](references/triggers.md) - Complete ACWR, readiness, TSB guides with thresholds
- [Decision Trees](references/decision_trees.md) - Detailed decision logic for common scenarios

**Complete examples**:
- [Quality Day Ready](examples/example_quality_day_ready.md) - No triggers, proceed with tempo
- [Quality Day Adjusted](examples/example_quality_day_adjusted.md) - ACWR elevated, shortened intervals
- [Rest Day Triggered](examples/example_rest_day_triggered.md) - Very low readiness + high ACWR
- [Multi-Sport Conflict](examples/example_multi_sport_conflict.md) - Climbing comp vs long run

**Training methodology**:
- [Adaptation Triggers](../../../docs/coaching/methodology.md#adaptation-triggers) - Complete trigger system
- [ACWR Research](../../../docs/coaching/methodology.md#acwr-acute-chronic-workload-ratio) - Evidence base
- [Sport Multipliers](../../../docs/coaching/methodology.md#sport-multipliers) - Multi-sport load model

**CLI commands**:
- [Risk Assessment Commands](../../../docs/coaching/cli_reference.md#risk-assessment) - Complete command reference
