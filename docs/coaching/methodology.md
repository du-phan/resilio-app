# Training Methodology Reference

Comprehensive guide to the training principles, metrics, and methodologies used in Sports Coach Engine.

## Table of Contents

- [Key Training Metrics](#key-training-metrics)
- [Sport Multipliers & Load Model](#sport-multipliers--load-model)
- [Adaptation Triggers](#adaptation-triggers)
- [Training Guardrails](#training-guardrails)
- [Evidence-Based Methodologies](#evidence-based-methodologies)
- [The Toolkit Paradigm](#the-toolkit-paradigm)

---

## Key Training Metrics

### CTL (Chronic Training Load)

**Definition**: 42-day exponentially weighted average of daily training load

**Represents**: "Fitness" - your aerobic base and training capacity

| CTL Value | Zone         | Interpretation                   | When to Use             |
| --------- | ------------ | -------------------------------- | ----------------------- |
| < 20      | Beginner     | New to training                  | Setting initial volumes |
| 20-35     | Recreational | Regular recreational athlete     | Moderate training loads |
| 35-50     | Competitive  | Serious recreational/competitive | Higher training volumes |
| 50-70     | Advanced     | Advanced competitive athlete     | Peak training periods   |
| > 70      | Elite        | Elite/professional level         | Elite training volumes  |

**Use for**:

- Assess overall fitness level
- Set volume baselines for training plans
- Understand training capacity
- Track long-term fitness trends

**Calculation**:

```
CTL_today = CTL_yesterday + (today_load - CTL_yesterday) / 42
```

---

### ATL (Acute Training Load)

**Definition**: 7-day exponentially weighted average of daily training load

**Represents**: "Fatigue" - your recent training stress

**Use for**:

- Gauge current fatigue state
- Understand recent training stress
- Determine if you've been pushing hard lately

**Calculation**:

```
ATL_today = ATL_yesterday + (today_load - ATL_yesterday) / 7
```

**Key insight**: ATL responds quickly to training changes, while CTL changes slowly. This creates the foundation for understanding form (TSB).

---

### TSB (Training Stress Balance)

**Definition**: CTL - ATL

**Represents**: "Form" - the balance between fitness and fatigue

| TSB Range  | State       | Interpretation              | When to Use               |
| ---------- | ----------- | --------------------------- | ------------------------- |
| < -25      | Overreached | High fatigue, need recovery | Consider rest week        |
| -25 to -10 | Productive  | Optimal training zone       | Continue building         |
| -10 to +5  | Fresh       | Good for quality work       | Schedule quality sessions |
| +5 to +15  | Race Ready  | Peaked, ready to race       | Race week                 |
| > +15      | Detraining  | Fitness declining           | Increase training         |

**Use for**:

- Determine readiness for quality work or racing
- Plan training intensity
- Decide when to rest vs push
- Time your peak for race day

**Key insight**: You can't be fit and fresh simultaneously. Training drives TSB negative (fatigue > fitness), rest brings it positive (fitness > fatigue).

---

### ACWR (Acute:Chronic Workload Ratio)

**Definition**: (7-day total load) / (28-day average daily load × 7)

**Represents**: Injury risk from training load changes

| ACWR Range | Zone    | Injury Risk       | When to Use               |
| ---------- | ------- | ----------------- | ------------------------- |
| 0.8-1.3    | Safe    | Normal (baseline) | Continue current training |
| 1.3-1.5    | Caution | Elevated (1.5-2x) | Consider modification     |
| > 1.5      | Danger  | High (2-4x)       | Reduce load immediately   |

**Use for**:

- Evaluate injury risk from load spikes
- Guide adaptation decisions
- Prevent overtraining injuries
- Manage training progressions safely

**Evidence**: Research shows ACWR > 1.5 increases injury risk 2-4x compared to baseline. This is the single most important metric for injury prevention.

**Calculation**:

```
acute_load = sum(last_7_days_load)
chronic_load = average(last_28_days_load) × 7
ACWR = acute_load / chronic_load
```

---

### Readiness Score (0-100)

**Definition**: Weighted combination of multiple factors

**Components**:

- TSB (20%): Current form
- Recent trend (25%): Training trajectory (building vs declining)
- Sleep (25%): Sleep quality/duration from activity notes
- Wellness (30%): Subjective wellness signals from notes

| Score | Level     | Interpretation              | When to Use          |
| ----- | --------- | --------------------------- | -------------------- |
| < 35  | Very Low  | Significant fatigue/illness | Force rest           |
| 35-50 | Low       | Moderate fatigue            | Downgrade quality    |
| 50-70 | Moderate  | Normal training state       | Proceed as planned   |
| 70-85 | Good      | Fresh, ready for work       | Quality sessions OK  |
| > 85  | Excellent | Peak readiness              | Hard sessions, races |

**Use for**:

- Daily go/no-go decision for hard workouts
- Overall training readiness assessment
- Balancing metrics with subjective feel

**Key insight**: Readiness synthesizes objective metrics (TSB) with subjective signals (sleep, wellness) to provide a holistic view of training state.

---

## Sport Multipliers & Load Model

### Two-Channel Load Model

Sports Coach Engine uses a **two-channel load model** to accurately account for multi-sport training:

1. **Systemic load** (`systemic_load_au`): Cardio + whole-body fatigue → feeds CTL/ATL/TSB/ACWR
2. **Lower-body load** (`lower_body_load_au`): Leg strain + impact → gates quality/long runs

**Why two channels?**

Traditional single-channel models treat all activities equally, causing problems like:

- Hard climbing session → system thinks legs are trashed → blocks tomorrow's easy run
- Reality: Upper-body fatigue doesn't prevent easy running

The two-channel model prevents this by separating:

- **Systemic fatigue** (affects everything)
- **Lower-body fatigue** (only affects running quality/long runs)

### Load Calculation

```
base_effort_au = RPE × duration_minutes
systemic_load_au = base_effort_au × systemic_multiplier
lower_body_load_au = base_effort_au × lower_body_multiplier
```

### Sport Multipliers Table

| Sport                | Systemic | Lower Body | Notes                         |
| -------------------- | -------- | ---------- | ----------------------------- |
| Running (road/track) | 1.00     | 1.00       | Baseline for all calculations |
| Running (treadmill)  | 1.00     | 0.90       | Reduced impact                |
| Trail running        | 1.05     | 1.10       | Increased effort + impact     |
| Cycling              | 0.85     | 0.35       | Low leg impact, high cardio   |
| Swimming             | 0.70     | 0.10       | Minimal leg strain            |
| Climbing/bouldering  | 0.60     | 0.10       | Upper-body dominant           |
| Strength (general)   | 0.55     | 0.40       | Whole-body fatigue            |
| Hiking               | 0.60     | 0.50       | Moderate impact               |
| CrossFit/metcon      | 0.75     | 0.55       | High intensity                |
| Yoga (flow)          | 0.35     | 0.10       | Low intensity recovery        |
| Yoga (restorative)   | 0.00     | 0.00       | Pure recovery                 |

### Validated Examples (Real Strava Data, Jan 2026)

| Activity | Details           | Systemic Load | Lower-Body Load |
| -------- | ----------------- | ------------- | --------------- |
| Running  | 7km, 43min, RPE 7 | 301 AU        | 301 AU          |
| Climbing | 105min, RPE 5     | 315 AU        | 52 AU           |
| Yoga     | 28min, RPE 2      | 20 AU         | 6 AU            |

**Key insight**: Climbing generates 315 AU systemic load (similar to running) but only 52 AU lower-body load. This allows easy running the next day without triggering lower-body fatigue warnings.

---

## Adaptation Triggers

M11 (Adaptation Engine) detects physiological triggers that warrant coaching attention. These are **data signals**, not decisions. Claude Code interprets triggers with athlete context and presents options.

| Trigger              | Threshold           | Severity    | Typical Response                    | Use Case                    |
| -------------------- | ------------------- | ----------- | ----------------------------------- | --------------------------- |
| ACWR_HIGH_RISK       | > 1.5               | 🔴 HIGH     | Downgrade or skip workout           | Injury prevention           |
| ACWR_ELEVATED        | > 1.3               | 🟡 MODERATE | Consider downgrade, discuss options | Cautionary signal           |
| READINESS_VERY_LOW   | < 35                | 🔴 HIGH     | Force rest or easy recovery         | Severe fatigue/illness      |
| READINESS_LOW        | < 50                | 🟡 LOW      | Downgrade quality workouts          | Moderate fatigue            |
| TSB_OVERREACHED      | < -25               | 🔴 HIGH     | Reduce training load immediately    | Overtraining prevention     |
| LOWER_BODY_LOAD_HIGH | Dynamic (CTL-based) | 🟡 MODERATE | Delay running quality/long runs     | Multi-sport load management |
| SESSION_DENSITY_HIGH | 2+ hard/7 days      | 🟡 MODERATE | Space out quality sessions          | Hard/easy discipline        |

### Toolkit Approach

**NOT**: "ACWR > 1.5 → auto-downgrade workout" (algorithm)

**YES**:

1. M11 returns trigger data + risk assessment
2. Claude Code interprets with athlete context (M13 memories, conversation history)
3. Presents options with reasoning
4. Athlete decides

### Example Trigger Handling

**Scenario**: ACWR 1.35 (elevated) + readiness 45 (low) + tempo run scheduled

**Claude Code Response**:

```
Your ACWR is 1.35 (slightly elevated - caution zone) and readiness is 45 (low).
Tempo run scheduled today. What would you prefer?

A) Easy 30min run (safest)
   - Lower injury risk, maintains aerobic base
   - ACWR stays manageable

B) Move tempo to Thursday
   - Gives you 2 extra recovery days
   - You climbed yesterday (elevated lower-body load)

C) Proceed with tempo as planned
   - Moderate risk (~15% injury probability)
   - Your form is good (TSB -8)

I'm leaning toward A or B given your readiness.
```

---

## Training Guardrails

Evidence-based training rules provided as **validation tools**. Claude Code decides enforcement based on athlete context.

| Guardrail                    | Rule                                          | Rationale                                       | Enforcement                  |
| ---------------------------- | --------------------------------------------- | ----------------------------------------------- | ---------------------------- |
| 80/20 intensity distribution | ~80% low intensity, ≤20% moderate+high        | Maximizes aerobic development, minimizes injury | ≥3 run days/week             |
| ACWR safety                  | ACWR > 1.5 = high injury risk                 | 2-4x increased injury probability               | M11 detects → Claude decides |
| Long run caps                | ≤25-30% of weekly run volume, ≤2.5 hours      | Prevents overuse injuries                       | Weekly validation            |
| Hard/easy separation         | No back-to-back high-intensity (RPE ≥7)       | Recovery between quality sessions               | Across all sports            |
| T/I/R volume limits          | Threshold ≤10%, Intervals ≤8%, Repetition ≤5% | Prevents excessive intensity                    | Of weekly mileage            |
| Recovery weeks               | Every 4th week at ~70% volume                 | Consolidates adaptations                        | During base/build phases     |

**Key Principle**: Guardrails are **validated** by modules, **enforced** by Claude Code. The system returns violations with context; Claude Code reasons about whether to enforce, override, or discuss with athlete.

### 80/20 Intensity Distribution

**Evidence**: Matt Fitzgerald's research shows elite endurance athletes spend ~80% of training at low intensity (Zones 1-2) and ≤20% at moderate/high intensity (Zones 3-5).

**Application**:

- Calculate weekly intensity distribution
- Flag violations: "Your training is 65/35 this week - too much intensity"
- Suggest adjustments: "Replace one tempo with easy run"

**Enforcement**: Only applies when running ≥3 days/week (need volume for distribution to matter)

---

## Evidence-Based Methodologies

Sports Coach Engine synthesizes principles from multiple proven training systems:

### 1. Jack Daniels' VDOT System

**Core Idea**: Pace zones calculated from recent race performances. VDOT represents current running fitness level.

**Application**: All pace prescriptions use VDOT-based zones:

- **E** (Easy): Aerobic base building, recovery runs
- **M** (Marathon): Race pace for marathon distance
- **T** (Threshold): Lactate threshold, "comfortably hard"
- **I** (Intervals): VO2max development, hard intervals
- **R** (Repetition): Speed/economy, very hard repeats

**Example**: VDOT 48 (competitive recreational)

- E: 6:00-6:30/km
- M: 5:15-5:30/km
- T: 4:50-5:10/km
- I: 4:20-4:40/km
- R: 3:50-4:10/km

**Reference**: _Daniels' Running Formula_ (2014)

---

### 2. Pfitzinger

**Core Ideas**:

- Periodization (base → build → peak → taper)
- Progressive long run development
- Recovery week cycles

**Application**:

**Periodization Structure**:

- **Base**: Build aerobic foundation, all easy/moderate
- **Build**: Add race-specific work (tempo, intervals)
- **Peak**: Highest volume + intensity
- **Taper**: Reduce volume, maintain intensity, peak for race

**Long Run Progression**:

- Start: 60-90 minutes
- Build gradually: +10-15 minutes every 2-3 weeks
- Cap: 25-30% of weekly volume, ≤2.5 hours

**Recovery Weeks**:

- Every 4th week during base/build
- ~70% of previous week's volume
- Maintains intensity but reduces volume
- Consolidates adaptations

**Reference**: _Advanced Marathoning_ (2009)

---

### 3. 80/20 (Matt Fitzgerald)

**Core Idea**: Intensity distribution - most training should be easy

**Evidence**:

- Study of elite endurance athletes across sports
- ~80% of training at low intensity (Zones 1-2)
- ≤20% at moderate/high intensity (Zones 3-5)

**Application**:

- Validate weekly intensity distribution
- Flag violations: "You're running 65/35 - too much moderate intensity"
- Enforce easy runs: "RPE 4-5, conversational pace"
- Limit quality: Only 1-2 hard sessions per week

**Common Mistake**: "Moderate-intensity rut" - everything at medium effort

- Easy runs too hard (RPE 6 instead of 4-5)
- Hard runs not hard enough (RPE 7 instead of 8-9)
- Result: Poor aerobic development, high injury risk, suboptimal performance

**Reference**: _80/20 Running_ (2014)

---

### 4. FIRST (Run Less, Run Faster)

**Core Idea**: Low-frequency, high-quality running (3 days/week)

**Target Athlete**: Multi-sport athletes, time-constrained runners

**Application**: When running ≤2-3 days/week:

- Focus on quality: each run has purpose
- Key workouts: long run, tempo, intervals
- Cross-training fills aerobic volume (cycling, swimming, etc.)

**Sports Coach Engine Adaptation**:

- Use FIRST structure for low-frequency running
- Account for systemic load from other sports (climbing, cycling, etc.)
- Account for lower-body load separately (gates quality/long runs)
- **Example**: 2 run days/week + 2 climbing days
  - Run 1: Long run (builds endurance)
  - Run 2: Tempo or intervals (builds speed)
  - Climbing: Adds systemic load without lower-body impact

**Reference**: _Run Less, Run Faster_ (2007)

---

## The Toolkit Paradigm

### Core Innovation: AI Reasoning + Computational Tools

**THE PARADIGM SHIFT**: Every other training app uses hardcoded algorithms to generate plans and suggestions. Sports Coach Engine uses **AI reasoning + computational tools** to enable truly personalized, context-aware, explainable coaching.

### Traditional Apps (Algorithm-Driven)

```
Algorithm: generate_plan(profile, goal, weeks) → TrainingPlan
Result: Rigid, one-size-fits-all plan
Problem: Can't handle "I climb Tuesdays, have knee history, prefer morning runs"
```

**Limitations**:

- Can't reason about athlete-specific context
- Can't explain "why" beyond pre-programmed messages
- Can't handle edge cases or multi-sport complexity
- Can't learn from conversation or memories

### Sports Coach Engine (Toolkit-Driven)

```
Toolkit: calculate_periodization(), validate_guardrails(), create_workout()
Claude Code: Uses tools + expertise + athlete context → designs plan
Result: Personalized, flexible, explainable
```

**Advantages**:

- Reasons about athlete context (knee history, climbing Tuesdays, etc.)
- Explains rationale: "ACWR 1.35 + yesterday's climbing → easy run safer"
- Handles edge cases: "You mentioned tight knee - let's skip tempo"
- Learns from memories: "You prefer morning runs - scheduling for 6 AM"

### Decision Framework

**Ask: "Is Claude Code better at this?"**

| Task Type                           | Who Handles It  | Why                                                        |
| ----------------------------------- | --------------- | ---------------------------------------------------------- |
| **Quantitative** (pure math)        | Package modules | Formulas, lookup tables, deterministic logic               |
| **Qualitative** (judgment, context) | Claude Code     | Natural language understanding, reasoning, personalization |

**Quantitative Examples** (Module handles):

- CTL/ATL/TSB calculation (formula)
- HR zone mapping (HR → zone lookup)
- ACWR computation (7-day / 28-day ratio)
- Load calculation (RPE × duration × multiplier)
- Pace conversions (VDOT tables)
- Guardrail validation (check 80/20, long run caps)

**Qualitative Examples** (Claude Code handles):

- RPE conflict resolution ("HR says 7, pace says 5, text says 4 → use which?")
- Injury assessment ("Is 'tight knee' pain or stiffness?")
- Training plan design ("Where to place quality runs around climbing schedule?")
- Adaptation decisions ("ACWR 1.5 → downgrade, move, or proceed?")
- Rationale generation ("Why this workout today for YOU?")

### Example: "What should I do today?" Flow

```
User: "what should I do today?"
    │
    ▼
Claude Code: understands intent, uses toolkit to coach
    │
    ▼ calls toolkit functions
1. get_current_metrics() → CTL/ATL/TSB/ACWR/readiness with interpretations
2. get_todays_workout() → planned workout from athlete's plan
3. detect_adaptation_triggers(workout, metrics) → trigger data
4. assess_override_risk(triggers) → risk assessment
5. load_memories() → athlete history, preferences, patterns
    │
    ▼
Claude Code: reasons with full context
    - Metrics show: CTL 44 (solid fitness), TSB -8 (productive zone), ACWR 1.3 (caution)
    - Triggers: ACWR elevated, lower-body load high yesterday (climbing)
    - Memories: "Athlete climbs Tuesdays", "Knee history: sensitive after 18km+"
    - Risk: Moderate (15% injury probability)
    │
    ▼
Claude Code: presents coaching decision with reasoning
    "Your tempo run is scheduled for today. However, I see:
     - ACWR at 1.3 (caution zone)
     - You climbed yesterday (elevated lower-body load: 340 AU)
     - Your knee history makes me cautious

     Options:
     A) Easy 30min run (RPE 4) - safest, maintains aerobic stimulus
     B) Move tempo to Thursday - gives legs 2 days recovery
     C) Proceed with tempo - moderate risk (~15%)

     What sounds best? I'm leaning toward A or B."
```

**The result**: Personalized coaching that feels like working with a human coach who knows you, not a rigid algorithm.

---

## Multi-Sport Awareness

### Running Priority

- **PRIMARY**: Running is the main sport, race goal takes precedence
- **SECONDARY**: Other sport is primary, running supports overall fitness
- **EQUAL**: Balance both sports, negotiate conflicts case-by-case

### Conflict Policy

When running and other sports conflict:

- **`primary_sport_wins`**: Protect primary sport, adjust running

  - Example: Climbing is primary → move Friday run if Wednesday climbing was hard

- **`running_goal_wins`**: Keep key runs unless injury risk

  - Example: Race in 6 weeks → protect Saturday long run, adjust climbing

- **`ask_each_time`**: Present trade-offs, let athlete decide (recommended)
  - Example: "Long run Saturday conflicts with climbing comp - move to Sunday?"

---

## Practical Application Tips

### For Daily Coaching

1. **Always check current metrics first**: `sce status`
2. **Reference actual data**: "Your ACWR is 1.35..." not "Maybe rest today"
3. **Use triggers as coaching cues**: ACWR elevated → discuss options
4. **Consider multi-sport context**: "You climbed yesterday (340 AU systemic, 52 AU lower-body)"

### For Plan Design

1. **Start with CTL**: Determines appropriate starting volume
2. **Apply periodization**: base → build → peak → taper structure
3. **Respect guardrails**: 80/20, long run caps, recovery weeks
4. **Validate with ACWR**: Ensure safe load progression

### For Adaptation Decisions

1. **Collect context**: metrics + triggers + memories + conversation
2. **Assess risk**: Use `assess_override_risk()` for injury probability
3. **Present options**: Give athlete choices with trade-offs
4. **Explain reasoning**: Link to CTL, ACWR, readiness, or phase

---

## See Also

- [CLI Command Index](cli/index.md) - Command documentation
- [Coaching Scenarios](scenarios.md) - Example workflows
- [API Layer Spec](../specs/api_layer.md) - Python API for scripting
- [PRD](../mvp/v0_product_requirements_document.md) - Product philosophy
- [Technical Spec](../mvp/v0_technical_specification.md) - System architecture
