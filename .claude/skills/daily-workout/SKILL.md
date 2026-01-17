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

## Workflow

### Step 0: Retrieve Relevant Memories (Context Loading)

**Before making recommendations, load athlete's training response patterns and preferences.**

```bash
# Check training response patterns
sce memory list --type TRAINING_RESPONSE

# Check readiness/recovery patterns
sce memory search --query "readiness recovery fatigue"

# Check override preferences
sce memory search --query "override rest"
```

**Use retrieved memories to inform recommendations**:
- If memory shows "Prefers to train through low readiness", acknowledge this pattern when presenting options
- If memory shows "Low readiness persists 3+ days after hard weeks", anticipate this pattern
- If memory shows past override decisions, reference them: "I know you typically push through, but..."

**Example memory application**:
```
Memory: "Reports feeling flat after back-to-back quality days"
Today's context: Yesterday was interval session, today is tempo
Your response: "I see you had intervals yesterday. You've mentioned in past weeks that back-to-back quality leaves you flat. How are you feeling today?"
```

### Step 1: Get Scheduled Workout

Check what's planned for today from the athlete's training plan.

**Command**:
```bash
sce today
```

**What this returns**:
- `workout`: Today's scheduled workout (type, distance, pace, duration)
- `current_metrics`: CTL/ATL/TSB/ACWR/readiness with interpretations
- `adaptation_triggers`: List of detected triggers (if any)
- `rationale`: Why this workout was prescribed

**If no plan exists**:
```
"You don't have a training plan yet. Would you like me to design one based on your goal? Or I can suggest a workout based on your current fitness (CTL 44)."
```

### Step 2: Assess Current State

Review metrics to understand athlete's readiness.

**From `sce today` response, extract**:
- **CTL**: Current fitness level (e.g., 44 = "solid recreational fitness")
- **TSB**: Form/freshness (e.g., -8 = "productive training zone")
- **ACWR**: Injury risk (e.g., 1.35 = "slightly elevated - caution zone")
- **Readiness**: Daily go/no-go score (e.g., 55 = "moderate readiness")

**Also check**:
```bash
sce status  # If you need more detailed metrics breakdown
```

### Step 3: Detect Adaptation Triggers

Triggers are data signals that warrant coaching attention.

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

**If NO triggers detected**: Proceed with planned workout (Step 4).

**If triggers detected**: Assess risk and present options (Step 5).

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

**Example**:
```
Your tempo run is scheduled for today: 8 km at 5:10-5:30/km (threshold pace).

Current state:
- CTL: 44 (solid recreational fitness)
- TSB: -8 (productive training zone)
- ACWR: 1.15 (safe range)
- Readiness: 68 (good)

This workout builds lactate threshold - the pace you can hold "comfortably hard" for 20-60 minutes. Your metrics look good - proceed as planned.

Tips:
- Warm up 10 minutes easy before starting threshold pace
- Maintain conversational effort (RPE 7-8, not maximal)
- Cool down 10 minutes easy after
```

### Step 5: Adaptation Decision (Triggers Detected)

When triggers are detected, interpret with athlete context and present options with trade-offs.

#### 5a. Assess Risk

**Command** (if not already in `sce today` response):
```bash
sce risk assess --metrics metrics.json --recent activities.json
```

**What this returns**:
- `overall_risk_level`: low, moderate, high, very_high
- `injury_probability`: percentage (0-100%)
- `contributing_factors`: List of risk contributors (ACWR, readiness, TSB, etc.)

#### 5b. Present Options with Context

Use **AskUserQuestion** to present distinct options with trade-offs.

**Pattern**:
1. State current metrics with interpretations
2. Explain what's scheduled
3. Present 3-4 options with specific trade-offs
4. Include your recommendation

**Example 1: ACWR Elevated (1.35) + Moderate Readiness (55)**

**Scheduled**: Tempo run (8 km at 5:10-5:30/km)

**Your response**:
```
Your ACWR is 1.35 (slightly elevated - caution zone) and readiness is 55 (moderate). You have a tempo run scheduled today.

I see you climbed yesterday (340 AU lower-body load), which may be contributing to the elevated ACWR.

What would you prefer?

[Use AskUserQuestion with options:]
```

**Options**:
1. **Easy 30-minute run (safest)**
   - Maintains aerobic base without additional stress
   - ACWR stays manageable (reduces injury risk)
   - Lower-body load recovery from yesterday's climbing

2. **Move tempo to Thursday**
   - Gives legs 2 extra recovery days
   - You climbed yesterday - fresh legs help tempo quality
   - Reschedule around your climbing commitments

3. **Shorten tempo to 5 km (compromise)**
   - Still gets threshold stimulus (50% volume reduction)
   - Moderate injury risk (~10-12%)
   - Good if you're feeling strong despite metrics

4. **Proceed with tempo as planned**
   - Moderate risk (~15% injury probability)
   - Your form is decent (TSB -8 = productive zone)
   - Only if you're confident in how you feel

**Recommendation**: "I'm leaning toward option 1 or 2 given your ACWR and yesterday's climbing load."

**Example 2: Very Low Readiness (32) + High ACWR (1.52)**

**Scheduled**: Long run (18 km at easy pace)

**Your response**:
```
Your readiness is 32 (very low) and ACWR is 1.52 (danger zone - high injury risk). You have a long run scheduled today.

Contributing factors:
- Poor sleep noted in last 2 activities
- ACWR spike from 1.15 → 1.52 this week
- TSB is -22 (approaching overreached)

This is a clear red flag. What would you prefer?

[Use AskUserQuestion with options:]
```

**Options**:
1. **Rest day (strongly recommended)**
   - Your body is telling you it needs recovery
   - ACWR will drop naturally with rest
   - Protects against injury (current risk: 18-22%)

2. **Easy 20-minute recovery run**
   - Very light stimulus if you feel restless
   - Walk breaks encouraged
   - Monitor how you feel - stop if anything hurts

**Recommendation**: "I strongly recommend option 1 (rest). Your metrics indicate high fatigue and injury risk."

### Step 6: Log Decision and Rationale

After athlete decides, explain the reasoning behind the recommendation.

**If athlete chose downgrade**:
```
Smart decision. Here's why this makes sense:
- ACWR of 1.35 means your acute load is 35% higher than your body's adapted chronic load
- Research shows ACWR > 1.5 increases injury risk 2-4x - you're at the edge
- Easy run maintains aerobic stimulus while giving legs recovery

Your adjusted workout: 30 minutes easy (RPE 3-4, conversational pace)
```

**If athlete chose to proceed despite triggers**:
```
I understand you want to stick with the plan. Here's what to watch for:
- Any sharp or sudden pain → stop immediately
- Monitor knee (your injury history) closely
- If it feels harder than RPE 7-8, dial back pace

Your workout: Tempo run, 8 km at 5:10-5:30/km

If you feel off during the run, it's okay to downgrade mid-workout. Better to adjust than risk injury.
```

---

## Decision Trees

### Q: No training plan exists

**Scenario**: Athlete asks "what should I do today?" but has no plan.

**Response**:
```
You don't have a training plan yet. I can either:
A) Design a full training plan based on your goal (recommended)
B) Suggest a single workout based on your current fitness

Your CTL is 44 (solid recreational fitness). If you want option B, I'd suggest:
- Easy run: 6-8 km at conversational pace (RPE 3-4)

Which would you prefer?
```

### Q: Athlete mentions subjective wellness

**Scenario**: "I'm feeling tired" or "my legs are sore"

**Approach**:
1. Check metrics: `sce status`
2. Ask clarifying questions: "How tired? Normal training fatigue or unusual?"
3. If wellness conflicts with metrics (e.g., feels tired but readiness is 75):
   - Trust subjective feel over metrics
   - "Metrics look okay, but you know your body best. Let's downgrade today."
4. If wellness aligns with metrics (e.g., feels tired and readiness is 38):
   - Confirm with data: "That aligns with what I see - readiness is 38 (very low). Rest day makes sense."

**Key**: Wellness signals override metrics when in conflict.

### Q: Multi-sport conflict

**Scenario**: Athlete mentions other sport commitment conflicts with planned run.

**Example**: "I have a climbing comp today, but my long run is scheduled"

**Approach**:
1. Check `profile.conflict_policy`:
   - `ask_each_time`: Present trade-offs (below)
   - `primary_sport_wins`: "Let's move the long run to tomorrow"
   - `running_goal_wins`: "Can you do the comp another day? Long run is key for race prep"

**If `ask_each_time`**, use AskUserQuestion:
```
You have a climbing comp today and a long run scheduled. What would you prefer?

Options:
1. Climbing comp today, long run tomorrow (shift schedule)
   - Prioritizes climbing commitment
   - Long run on Sunday instead of Saturday

2. Easy 30-minute run + climbing comp (compromise)
   - Light aerobic stimulus before comp
   - Climbing is primary today

3. Long run today, skip climbing comp
   - Prioritizes race training (20 weeks to half marathon)
   - Climbing comps happen more frequently
```

**Recommendation**: Based on goal proximity and conflict policy.

### Q: Athlete wants to "feel it out" during run

**Scenario**: "I'll start and see how I feel"

**Response**:
```
That's a good approach, especially with elevated ACWR. Here's a framework:

Start with: Easy pace for 10 minutes (warm-up)
Then assess:
- If you feel great → proceed with planned tempo
- If you feel okay → shorten tempo to 5 km (50% volume)
- If you feel off → keep it easy for 20-30 minutes total

Listen to your body. Better to underdose than overdose.
```

### Q: Athlete disagrees with metrics

**Scenario**: "But I feel fine!" when metrics show high risk

**Response**:
```
I hear you - and I trust your subjective feel. Here's the tension:
- Your ACWR is 1.48 (high risk zone)
- But you feel good subjectively

This is common - athletes often feel fine before an injury strikes. ACWR is a leading indicator, not a lagging one.

My recommendation: Proceed if you want, but with guardrails:
- Monitor closely for any discomfort
- At first sign of pain, downgrade immediately
- Consider it a "test run" - if metrics and feel align by next week, we're good

Sound fair?
```

**Balance objective data with subjective feel** - don't dismiss either.

---

## Adaptation Trigger Reference

### ACWR Interpretation

| ACWR Value | Zone    | Injury Risk        | Coaching Response                              |
|------------|---------|-------------------|------------------------------------------------|
| 0.8-1.3    | Safe    | Normal (baseline) | Proceed as planned                              |
| 1.3-1.5    | Caution | Elevated (1.5-2x) | Consider downgrade, discuss options             |
| > 1.5      | Danger  | High (2-4x)       | Strongly recommend downgrade or rest            |

**What drives ACWR up**:
- Sudden volume increase (e.g., 40 km → 55 km this week)
- Back-to-back hard sessions without recovery
- Multi-sport spike (e.g., climbing comp + long run same week)

**How to bring it down**:
- Easy runs only for 3-5 days
- Rest day (fastest reduction)
- Cross-training (if lower-body load is the issue)

### Readiness Interpretation

| Readiness | Level     | Interpretation              | Coaching Response             |
|-----------|-----------|-----------------------------|-----------------------------|
| < 35      | Very Low  | Significant fatigue/illness | Force rest or very easy recovery |
| 35-50     | Low       | Moderate fatigue            | Downgrade quality workouts   |
| 50-70     | Moderate  | Normal training state       | Proceed as planned           |
| 70-85     | Good      | Fresh, ready for work       | Quality sessions encouraged  |
| > 85      | Excellent | Peak readiness              | Hard sessions, races         |

**Readiness components**:
- TSB (20%): Current form
- Recent trend (25%): Training trajectory
- Sleep (25%): Sleep quality/duration from notes
- Wellness (30%): Subjective wellness signals

### TSB Interpretation

| TSB Range  | State       | Interpretation              | Coaching Response            |
|------------|-------------|-----------------------------|-----------------------------|
| < -25      | Overreached | High fatigue, need recovery | Reduce load immediately      |
| -25 to -10 | Productive  | Optimal training zone       | Continue building            |
| -10 to +5  | Fresh       | Good for quality work       | Schedule quality sessions    |
| +5 to +15  | Race Ready  | Peaked, ready to race       | Race week                    |
| > +15      | Detraining  | Fitness declining           | Increase training            |

---

## Common Pitfalls

### 1. Ignoring subjective wellness

❌ **Bad**: "Your metrics look fine, do the tempo" (athlete says they're exhausted)
✅ **Good**: "Metrics show readiness 72, but you know your body best. Let's downgrade."

**Subjective feel trumps metrics** when in conflict.

### 2. Not providing specific trade-offs

❌ **Bad**: "You could rest, or run easy, or do the tempo"
✅ **Good**: "Easy run maintains aerobic base (pro) but delays threshold work (con). Tempo gives stimulus (pro) but 15% injury risk (con)."

**Always explain trade-offs** for each option.

### 3. Over-relying on ACWR alone

❌ **Bad**: "ACWR is 1.28, you're fine" (ignoring readiness 35, TSB -23)
✅ **Good**: "ACWR is safe, but readiness and TSB suggest fatigue. Let's downgrade."

**Check all metrics** - ACWR, readiness, TSB, athlete notes.

### 4. Not explaining rationale

❌ **Bad**: "Do easy run instead"
✅ **Good**: "Easy run reduces ACWR (currently 1.35) while maintaining aerobic stimulus. Your climbing yesterday (340 AU) contributed to the spike."

**Always explain WHY** the recommendation makes sense.

### 5. Forcing downgrade without athlete input

❌ **Bad**: "You must rest today" (no options)
✅ **Good**: "I strongly recommend rest (ACWR 1.52, readiness 32). But if you want to run, here's the safest option: easy 20 minutes."

**Present options** - even when recommendation is clear, give athlete agency.

---

### Step 7: Capture Significant Patterns as Memories

**After athlete makes decisions (especially when overriding recommendations), capture recurring patterns.**

**When to capture**:
- Pattern appears 3+ times
- Athlete reveals new preference or constraint
- Significant fatigue/recovery pattern observed

**Patterns to capture**:

1. **Override patterns** (if athlete overrides rest/downgrade 3+ times):
   ```bash
   sce memory add --type TRAINING_RESPONSE \
     --content "Prefers to train through low readiness (<40), typically proceeds with planned workout despite elevated ACWR" \
     --tags "readiness:override,acwr:elevated,preference:train-through" \
     --confidence high
   ```

2. **Recovery patterns** (if observed 2+ times):
   ```bash
   sce memory add --type TRAINING_RESPONSE \
     --content "Reports feeling flat after back-to-back quality days (intervals + tempo)" \
     --tags "recovery:poor,quality:consecutive,pattern:fatigue" \
     --confidence medium
   ```

3. **Fatigue signals** (if readiness <40 for 3+ consecutive days):
   ```bash
   sce memory add --type TRAINING_RESPONSE \
     --content "Low readiness (<40) persists for 3+ days after hard training weeks (ACWR >1.3)" \
     --tags "readiness:low,recovery:slow,acwr:spike" \
     --confidence high
   ```

4. **Wellness signals** (if athlete mentions subjective feel):
   ```bash
   sce memory add --type CONTEXT \
     --content "Reports knee tightness on days following climbing sessions with >300 AU lower-body load" \
     --tags "body:knee,sport:climbing,load:lower-body,threshold:300" \
     --confidence medium
   ```

5. **Schedule constraints** (if recurring conflict):
   ```bash
   sce memory add --type CONTEXT \
     --content "Morning runs preferred due to evening work commitments (5pm meetings)" \
     --tags "schedule:morning,constraint:work,time:evening" \
     --confidence high
   ```

**Guidelines**:
- Only capture patterns with sufficient evidence (2-3+ occurrences)
- HIGH confidence for 3+ occurrences, MEDIUM for 2 occurrences, LOW for single observation but high significance
- Tag appropriately for future retrieval
- Include specific thresholds/numbers when relevant (e.g., "readiness <40", "ACWR >1.3", "load >300 AU")

---

## Links to Additional Resources

- **Adaptation triggers**: See [Coaching Methodology - Adaptation Triggers](../../../docs/coaching/methodology.md#adaptation-triggers)
- **ACWR research**: See [Coaching Methodology - ACWR](../../../docs/coaching/methodology.md#acwr-acute-chronic-workload-ratio)
- **Training intensity**: See [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md)
- **Workout types**: See [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md)
- **Risk assessment commands**: See [CLI Reference - Risk Commands](../../../docs/coaching/cli_reference.md#risk-assessment)
