# Decision Trees for Daily Workout Recommendations

## Overview

This reference provides detailed decision logic for common coaching scenarios that require judgment beyond simple trigger interpretation.

---

## Decision Tree 1: No Training Plan Exists

**Scenario**: Athlete asks "what should I do today?" but has no plan.

### Decision Logic

```
Check: Does athlete have a training plan?
├─ YES → Proceed with normal workflow (Step 1)
└─ NO → Follow below

  ├─ Check: Does athlete have a goal set? (sce goal show)
  │  ├─ YES → Offer plan generation
  │  │   "You have a [goal_type] goal on [date] but no plan yet. I can:
  │  │    A) Design a full training plan (recommended)
  │  │    B) Suggest a single workout for today
  │  │   Which would you prefer?"
  │  │
  │  └─ NO → Offer goal setting OR single workout
  │      "You don't have a goal or plan yet. I can:
  │       A) Help you set a goal and design a plan (recommended)
  │       B) Suggest a workout based on your current fitness
  │      Which would you prefer?"
  │
  └─ If option B chosen (single workout):
     ├─ Check CTL: sce status
     ├─ Suggest appropriate workout based on CTL:
     │   - CTL < 20: Easy 4-6 km at conversational pace (RPE 3-4)
     │   - CTL 20-35: Easy 6-8 km at conversational pace
     │   - CTL 35-50: Easy 8-10 km OR tempo 5 km if feeling good
     │   - CTL > 50: Easy 10-12 km OR tempo 8 km OR intervals 5x1000m
     │
     └─ Caveat: "This is a one-off workout. For consistent training, I recommend setting a goal and creating a plan."
```

### Example Response (No Plan, CTL 44)

```
You don't have a training plan yet. I can either:
A) Design a full training plan based on your goal (recommended)
B) Suggest a single workout based on your current fitness

Your CTL is 44 (solid recreational fitness). If you want option B, I'd suggest:
- Easy run: 8-10 km at conversational pace (RPE 3-4)

Which would you prefer?
```

---

## Decision Tree 2: Subjective Wellness Conflicts with Metrics

**Scenario**: Athlete reports subjective wellness ("I'm tired", "my legs are sore") that may or may not align with metrics.

### Decision Logic

```
Athlete reports wellness signal (tired, sore, feeling great, etc.)

├─ Step 1: Check metrics (sce status)
│  ├─ Get: CTL, TSB, ACWR, readiness
│  └─ Get: Recent activities and notes
│
├─ Step 2: Ask clarifying questions
│  "How tired? Normal post-workout fatigue or unusual exhaustion?"
│  "Where are you sore? Sharp pain or muscle soreness?"
│
├─ Step 3: Compare wellness with metrics
│
│  ├─ Case A: Wellness conflicts with metrics (e.g., feels tired but readiness 75)
│  │   → Trust subjective feel over metrics
│  │   "Metrics look okay, but you know your body best. Let's downgrade today."
│  │
│  │   Why: Metrics are lagging indicators. Subjective feel is real-time.
│  │
│  ├─ Case B: Wellness aligns with metrics (e.g., feels tired and readiness 38)
│  │   → Confirm with data
│  │   "That aligns with what I see - readiness is 38 (very low). Rest day makes sense."
│  │
│  └─ Case C: Positive wellness + good metrics (e.g., feels great, readiness 78)
│      → Encourage quality work
│      "Great! Your readiness is 78 (good) and you feel strong. Perfect day for [quality workout]."
│
└─ Key principle: Wellness signals override metrics when in conflict.
```

### Example Scenarios

**Scenario A: Conflict (Feels Tired, Metrics Good)**

```
Athlete: "I'm feeling really tired today"

Coach checks metrics:
- Readiness: 72 (good)
- TSB: -8 (productive zone)
- ACWR: 1.12 (safe)

Coach response:
"Your metrics look solid (readiness 72, ACWR safe), but you know your body best. Fatigue can be mental or physical stress that metrics don't fully capture. Let's downgrade to an easy 30-minute run instead of today's tempo. Better to underdose than push through."
```

**Scenario B: Alignment (Feels Tired, Metrics Poor)**

```
Athlete: "My legs feel heavy and I'm exhausted"

Coach checks metrics:
- Readiness: 38 (very low)
- TSB: -23 (approaching overreached)
- ACWR: 1.42 (elevated)

Coach response:
"That aligns perfectly with what I see: readiness 38 (very low), TSB -23 (approaching overreached), ACWR 1.42 (elevated). Your body is clearly telling you it needs recovery. Let's take a full rest day today."
```

**Scenario C: Positive Alignment**

```
Athlete: "Feeling great today, legs are fresh!"

Coach checks metrics:
- Readiness: 78 (good)
- TSB: -5 (fresh)
- ACWR: 1.08 (safe)

Coach response:
"Perfect! Your readiness is 78 (good), TSB is -5 (fresh), and ACWR is safe. This is exactly the kind of day for quality work. Let's proceed with today's interval session - you should be able to hit your target paces comfortably."
```

---

## Decision Tree 3: Multi-Sport Conflict

**Scenario**: Athlete has other sport commitment that conflicts with planned running workout.

### Decision Logic

```
Athlete reports conflict: "I have [other sport] today, but [running workout] is scheduled"

├─ Step 1: Check profile conflict policy (sce profile get)
│
│  ├─ conflict_policy: "primary_sport_wins"
│  │   → Automatically prioritize primary sport
│  │   "Since [primary sport] is your priority, let's move the [running workout] to [alternative day]."
│  │
│  ├─ conflict_policy: "running_goal_wins"
│  │   → Automatically prioritize running
│  │   "Your race is [X weeks away]. The [running workout] is key for race prep. Can you move [other sport] to [alternative day]?"
│  │
│  └─ conflict_policy: "ask_each_time"
│      → Present trade-offs (continue below)
│
├─ Step 2: If ask_each_time, gather context
│  ├─ Check: How critical is this running workout?
│  │   - Long run in peak phase → Very critical
│  │   - Easy run → Less critical
│  │
│  ├─ Check: How important is other sport commitment?
│  │   - Competition → High importance
│  │   - Regular training → Moderate importance
│  │
│  └─ Check: Can either be rescheduled?
│      - Running workout flexibility?
│      - Other sport flexibility?
│
└─ Step 3: Present options with trade-offs (AskUserQuestion)
```

### Example: Climbing Comp vs. Long Run

**Context**:
- Sport: Climbing comp (can't reschedule)
- Running: 18 km long run scheduled
- Goal: Half marathon in 8 weeks
- Conflict policy: ask_each_time

**Coach presents options**:

```
You have a climbing comp today and an 18 km long run scheduled. What would you prefer?

Options:

1. **Climbing comp today, long run tomorrow** (reschedule)
   - Prioritizes climbing commitment
   - Long run on Sunday instead of Saturday
   - Pro: Both workouts completed at full quality
   - Con: Back-to-back training days (climbing Sat + run Sun)

2. **Easy 30-minute run + climbing comp** (compromise)
   - Light aerobic stimulus before comp (morning)
   - Climbing is primary focus today
   - Pro: Maintains running frequency
   - Con: Misses long run stimulus this week

3. **Long run today, skip climbing comp** (prioritize running)
   - Prioritizes race training (8 weeks to half marathon)
   - Long runs are cornerstone of endurance
   - Pro: Stays on training plan
   - Con: Misses climbing comp

4. **Light climbing + shortened long run** (split)
   - Climbing comp with conservative effort
   - 12 km run (67% of planned distance)
   - Pro: Both activities completed
   - Con: Neither done at full quality, fatigue risk

Recommendation: Option 1. You'll be fresher for both climbing comp (Saturday) and long run (Sunday). Your CTL is 44, so back-to-back days are manageable.
```

---

## Decision Tree 4: "Feel It Out" Approach

**Scenario**: Athlete wants to start workout and assess mid-run.

### Decision Logic

```
Athlete says: "I'll start and see how I feel"

├─ Step 1: Check metrics
│  ├─ Metrics safe (ACWR <1.3, readiness >50) → Support approach
│  └─ Metrics concerning (ACWR >1.3 OR readiness <50) → Support with guardrails
│
├─ Step 2: Provide framework
│
│  ├─ For quality workout (tempo, intervals):
│  │   "Start with: Easy pace for 10 minutes (warm-up)
│  │   Then assess:
│  │   - If you feel great → proceed with planned [workout]
│  │   - If you feel okay → shorten [workout] by 50%
│  │   - If you feel off → keep it easy for 20-30 minutes total"
│  │
│  └─ For long run:
│      "Start with: Easy pace for 15 minutes
│      Then assess:
│      - If you feel great → proceed with planned [distance]
│      - If you feel okay → cap at [75% distance]
│      - If you feel off → cap at 30-40 minutes easy"
│
└─ Step 3: Add safety guardrails
   "Listen to your body. Better to underdose than overdose. If anything feels sharp or unusual, stop immediately."
```

### Example: Tempo Run with Elevated ACWR

**Context**:
- Scheduled: 8 km tempo at 5:10-5:30/km
- Metrics: ACWR 1.35 (elevated), readiness 58 (moderate)
- Athlete: "I want to start and see how I feel"

**Coach response**:

```
That's a good approach, especially with elevated ACWR (1.35). Here's a framework:

**Start with**: Easy pace for 10 minutes (warm-up)

**Then assess** how you feel:

- **If you feel great** (legs fresh, breathing easy):
  → Proceed with planned tempo: 8 km at 5:10-5:30/km
  → Monitor closely - if pace feels harder than RPE 7-8, dial back

- **If you feel okay** (legs decent, not terrible):
  → Shorten tempo to 5 km (50% volume reduction)
  → This still gives threshold stimulus while managing injury risk

- **If you feel off** (legs heavy, breathing labored):
  → Keep it easy for 20-30 minutes total
  → Save the tempo for Thursday when you're fresher

**Safety note**: Listen to your body. Better to underdose than overdose. At first sign of sharp pain or unusual discomfort, stop immediately.
```

---

## Decision Tree 5: Athlete Disagrees with Metrics

**Scenario**: Athlete feels fine despite concerning metrics, or feels bad despite good metrics.

### Decision Logic

```
Athlete disagrees with metric-based recommendation

├─ Case A: Athlete feels fine, metrics show high risk
│
│  ├─ Acknowledge tension
│  │   "I hear you - and I trust your subjective feel. Here's the tension:
│  │    - Your [metric] is [value] ([interpretation])
│  │    - But you feel good subjectively"
│  │
│  ├─ Explain leading vs lagging indicators
│  │   "This is common - athletes often feel fine before an injury strikes.
│  │    [Metric] is a leading indicator, not a lagging one."
│  │
│  ├─ Offer compromise with guardrails
│  │   "My recommendation: Proceed if you want, but with guardrails:
│  │    - Monitor closely for any discomfort
│  │    - At first sign of pain, downgrade immediately
│  │    - Consider it a 'test run' - if metrics and feel align next week, we're good"
│  │
│  └─ Respect athlete agency
│      "Sound fair? I won't stop you, but I want you to be aware of the risk."
│
└─ Case B: Athlete feels bad, metrics look fine

   ├─ Trust subjective feel
   │   "Metrics show [interpretation], but you know your body best.
   │    There may be factors metrics don't capture: stress, sleep, illness."
   │
   └─ Downgrade recommendation
       "Let's downgrade to [easy option]. Better safe than sorry."
```

### Example A: Feels Fine Despite High ACWR

**Context**:
- Metrics: ACWR 1.48 (high risk), readiness 62 (moderate)
- Scheduled: 18 km long run
- Athlete: "But I feel fine! I want to do the long run."

**Coach response**:

```
I hear you - and I trust your subjective feel. Here's the tension:

- Your ACWR is 1.48 (high risk zone - 2-4x injury risk)
- But you feel good subjectively

This is actually common - athletes often feel fine before an injury strikes. ACWR is a **leading indicator** (predicts future injury risk), not a lagging one (reacts to current pain).

My recommendation: Proceed if you want, but with guardrails:
- Start conservatively - aim for slower end of easy pace
- Monitor closely for any discomfort (especially [known injury area])
- At first sign of sharp or unusual pain, stop immediately
- Consider this a "test run" - if you complete it without issues and ACWR drops by next week, we're good

Sound fair? I won't stop you, but I want you to be aware of the risk (18-22% injury probability). Your call.
```

### Example B: Feels Bad Despite Good Metrics

**Context**:
- Metrics: ACWR 1.08 (safe), readiness 71 (good), TSB -6 (productive)
- Scheduled: Tempo run
- Athlete: "I feel exhausted today, don't think I can do the tempo"

**Coach response**:

```
Your metrics look solid (ACWR 1.08, readiness 71), but you know your body best. There may be factors metrics don't fully capture:
- Work stress or life stress
- Poor sleep quality last night
- Early stages of illness
- Mental fatigue (just as important as physical)

Let's downgrade to an easy 30-minute run instead of the tempo. Better to listen to your body and err on the side of caution. We can move the tempo to Thursday if you're feeling better.

The tempo will be more productive when you feel fresh anyway. No point forcing it through fatigue.
```

---

## Decision Tree 6: Rest Day vs. Active Recovery

**Scenario**: Triggers suggest rest, but athlete asks about "active recovery" option.

### Decision Logic

```
Athlete asks: "Can I do active recovery instead of full rest?"

├─ Check severity of triggers
│
│  ├─ Very high severity (readiness <35, ACWR >1.5, TSB <-25)
│  │   → Full rest strongly recommended
│  │   "Your body needs complete recovery. Active recovery still adds load (even if minimal).
│  │    Full rest is best today."
│  │
│  ├─ Moderate severity (readiness 35-50, ACWR 1.3-1.5)
│  │   → Active recovery acceptable with conditions
│  │   "Active recovery is fine if it's truly easy:
│  │    - 20-30 minutes max
│  │    - RPE 2-3 (conversation is effortless)
│  │    - Walk breaks encouraged
│  │    - Monitor closely - if anything feels off, stop"
│  │
│  └─ Low severity (readiness 50-65, minor trigger)
│      → Active recovery or easy run fine
│      "Active recovery or easy run both work. Keep it conversational (RPE 3-4)."
│
└─ Explain difference
   "Rest day = 0 training load (fastest recovery)
    Active recovery = ~15-30 AU (maintains movement, slower recovery)
    Easy run = ~40-60 AU (aerobic stimulus, minimal recovery)"
```

### Example: ACWR 1.52, Readiness 32

**Athlete**: "Can I just do 20 minutes easy instead of full rest?"

**Coach response**:

```
I understand the urge to move, but your metrics are concerning:
- ACWR 1.52 (danger zone - high injury risk)
- Readiness 32 (very low)
- TSB -24 (approaching overreached)

Active recovery still adds training load (even if minimal ~20-30 AU). Your body needs **complete recovery** today - that means 0 AU.

Think of it this way:
- Full rest = letting the battery fully recharge
- Active recovery = using the battery on low-power mode (still draining)

You'll get more from tomorrow's workout if you rest completely today. Trust the process.

If you feel restless, try:
- Stretching or yoga (no cardio load)
- Walk (leisure pace, not exercise pace)
- Foam rolling or massage

But no running today.
```

---

## Additional Resources

- **Coaching philosophy on athlete agency**: See [Coaching Methodology - Balancing Data and Feel](../../../docs/coaching/methodology.md#balancing-data-and-feel)
- **Multi-sport conflict resolution**: See [first-session skill - Conflict Policy](../first-session/SKILL.md#step-4-profile-setup)
- **Subjective wellness integration**: See [Coaching Scenarios - Daily Workout](../../../docs/coaching/scenarios.md#scenario-3-daily-workout-with-triggers)
