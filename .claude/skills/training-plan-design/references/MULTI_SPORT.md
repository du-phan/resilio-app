# Multi-Sport Training Quick Reference

How to design running plans that respect and integrate other sports (climbing, cycling, swimming, etc.). Based on two-channel load model and sport-specific multipliers.

## Two-Channel Load Model

Traditional single-channel models treat all activities equally, causing problems. Sports Coach Engine uses **two channels**:

### 1. Systemic Load (Cardio + Whole-Body Fatigue)
**Feeds**: CTL/ATL/TSB/ACWR
**Represents**: Cardiovascular stress + overall fatigue
**Affects**: All activities equally

**Example**: Hard climbing session generates high systemic load → impacts running the next day (but see channel 2)

### 2. Lower-Body Load (Leg Strain + Impact)
**Gates**: Quality runs and long runs
**Represents**: Leg-specific fatigue and impact stress
**Affects**: Running intensity and duration capacity

**Example**: Hard climbing has LOW lower-body load → easy run next day is fine, but quality run may be compromised if systemic fatigue is high

### Why Two Channels?
- **Problem**: Single-channel treats "climbing 2 hours" = "running 2 hours"
- **Reality**: Climbing stresses upper body (systemic) but spares legs (lower-body)
- **Solution**: Climbing allows easy running next day, but quality running requires both channels to be recovered

---

## Sport Multipliers

Each sport has multipliers for systemic and lower-body load.

| Sport                | Systemic | Lower-Body | Notes                            |
|----------------------|----------|------------|----------------------------------|
| Running (road/track) | 1.00     | 1.00       | Baseline (highest leg impact)    |
| Running (treadmill)  | 1.00     | 0.90       | Reduced impact vs road           |
| Trail running        | 1.05     | 1.10       | Hills + technical terrain        |
| Cycling              | 0.85     | 0.35       | High cardio, low leg impact      |
| Swimming             | 0.70     | 0.10       | Minimal leg strain               |
| Climbing/bouldering  | 0.60     | 0.10       | Upper-body dominant              |
| Strength (general)   | 0.55     | 0.40       | Whole-body fatigue               |
| Hiking               | 0.60     | 0.50       | Moderate effort + impact         |
| CrossFit/metcon      | 0.75     | 0.55       | High intensity, varied movements |
| Yoga (flow)          | 0.35     | 0.10       | Low intensity, flexibility       |
| Yoga (restorative)   | 0.00     | 0.00       | Pure recovery (no load)          |

### Load Calculation
```
base_effort_au = RPE × duration_minutes
systemic_load_au = base_effort_au × systemic_multiplier
lower_body_load_au = base_effort_au × lower_body_multiplier
```

**Example (Climbing)**:
- Activity: Bouldering, 105 min, RPE 5
- Base effort: 5 × 105 = 525 AU
- Systemic load: 525 × 0.60 = 315 AU
- Lower-body load: 525 × 0.10 = 52 AU

**Interpretation**: High systemic fatigue (315 AU = equivalent to ~45 min hard run), but minimal leg impact (52 AU). Easy run next day is fine; quality run needs more recovery.

---

## Running Priority Levels

### PRIMARY (Race Goal Focus)
**Definition**: Running is the main sport, race goal takes precedence

**Plan structure**:
- Full periodization (base → build → peak → taper)
- Standard volume progression (50-80 km/week peak)
- Other sports supplement, don't replace key runs

**Multi-sport integration**:
- Climbing/cycling on non-run days or after easy runs
- Other sports for cross-training (low-intensity only)
- Quality running workouts protected

**Example**:
- Half marathon in 16 weeks
- Running: 4-5 days/week
- Climbing: 1-2 days/week (on rest days or after easy runs)
- Cycling: 1 day/week cross-training (easy spin)

**Load distribution**: 60-70% running, 30-40% other sports

---

### EQUAL (Balance Both Sports)
**Definition**: Running and other sport are equally important

**Plan structure**:
- Reduced running frequency (2-4 days/week)
- Lower peak volume (40-60 km/week)
- Coordinate phases with other sport's season
- Flexible conflict resolution

**Multi-sport integration**:
- Running 40-50% of systemic load
- Other sport 40-50% of load
- Negotiate conflicts case-by-case (see Conflict Policy)

**Example**:
- Half marathon + climbing season
- Running: 3 days/week (1 long, 1 tempo, 1 easy)
- Climbing: 2-3 days/week (comps, training, outdoor)

**Periodization coordination**:
- If climbing season peaks in spring: Running base phase in winter, taper running during climbing peak
- If off-season climbing: Run more, climb for cross-training

**Load distribution**: 40-50% running, 40-50% other sports, 10-20% recovery/yoga

---

### SECONDARY (Other Sport Primary)
**Definition**: Running supports overall fitness, other sport is focus

**Plan structure**:
- Minimal running frequency (2-3 days/week)
- No progressive buildup (maintain base)
- No peak phase (running is steady-state)
- No race-specific workouts (unless fun race)

**Multi-sport integration**:
- Running maintains cardio base for primary sport
- Easy runs only (RPE 3-4, conversational)
- Occasional tempo if athlete enjoys it

**Example**:
- Competitive climber, maintains running fitness
- Running: 2 days/week (both easy, 30-40 min)
- Climbing: 4-5 days/week (training, comps, projects)

**Load distribution**: 20-30% running, 70-80% other sports

---

## Conflict Policy

When running and other sports conflict (same day or consecutive days), policy determines resolution.

### 1. `ask_each_time` (Recommended for EQUAL priority)
**Approach**: Present trade-offs, athlete decides

**Example conflict**: Saturday long run vs. climbing comp

**Coach response** (using AskUserQuestion):
```
You have a long run (18 km) and a climbing comp on Saturday. What would you prefer?

Options:
1. Long run Saturday, skip comp (prioritize race training)
   - 20 weeks to half marathon, long run is key
   - Climbing comps happen more frequently

2. Climbing comp Saturday, long run Sunday (shift schedule)
   - You've been training for this comp
   - Sunday long run works if you're not too fatigued

3. Easy run + comp (compromise)
   - 30 min easy before comp (light stimulus)
   - Comp is main event

What sounds best based on your current priorities?
```

**Storage**: Remember preference for similar conflicts

### 2. `primary_sport_wins` (Protect Primary Sport)
**Approach**: Adjust running around other sport's schedule

**Example**: Climbing is primary
- Climbing comp Friday → automatically move Saturday long run to Sunday
- Don't ask, just adapt running plan

**Use when**: Other sport has fixed commitments (comps, team schedule)

### 3. `running_goal_wins` (Prioritize Race Prep)
**Approach**: Keep key runs unless injury risk

**Example**: Race in 6 weeks
- Saturday long run protected
- Move climbing to Sunday or skip if conflicts
- Exception: If ACWR >1.3, still allow flexibility

**Use when**: Race proximity high (8-12 weeks out), race is priority

---

## Planning with Multi-Sport Constraints

### Step 1: Identify Fixed Commitments
**Ask athlete**:
- "Which days are non-negotiable for [other sport]?"
- "Are [other sport] sessions fixed or flexible?"

**Example**:
- Climbing: Tuesday evenings (team night), Thursday (comp prep), Saturday (comp or outdoor)
- → Fixed: Tuesday, Thursday, Saturday for climbing

### Step 2: Map Running Around Fixed Days
**Running placement**:
- Wednesday: Easy run (24 hours after Tuesday climbing)
- Friday: Easy run (recovery before Saturday climbing)
- Sunday: Long run (48 hours after Thursday climbing)
- Monday: Tempo or intervals (48 hours since Saturday)

**Rationale**:
- Easy runs after climbing: Systemic fatigue moderate, lower-body fresh
- Quality runs after 48-hour gap: Both channels recovered

### Step 3: Consider Lower-Body Load Interactions
**Climbing (low lower-body) → Running (high lower-body)**:
- Easy run next day: ✓ Fine (systemic OK, legs fresh)
- Quality run next day: ⚠ Maybe (systemic fatigue may reduce quality)
- Long run next day: ⚠ Check readiness (systemic fatigue + long duration)

**Cycling (moderate lower-body) → Running (high lower-body)**:
- Easy run next day: ⚠ Possible (legs moderately tired)
- Quality run next day: ✗ Not recommended (legs need recovery)
- Long run next day: ✗ Avoid (compounding leg fatigue)

**Swimming (minimal lower-body) → Running (high lower-body)**:
- Easy run next day: ✓ Fine (minimal carryover)
- Quality run next day: ✓ Fine (legs fresh)
- Long run next day: ✓ Fine

### Step 4: Validate Multi-Sport Load
```bash
sce analysis load --activities activities.json --days 7 --priority equal
```

**Returns**:
- Systemic load by sport
- Lower-body load by sport
- Priority adherence: Good/fair/poor
- Fatigue flags (e.g., "High cycling load before quality run")

**Action**: Adjust plan if load imbalance detected

---

## Example Weekly Schedule (EQUAL Priority)

**Athlete**: Half marathon training + competitive climber
**Running**: 3 days/week (long, tempo, easy)
**Climbing**: 2-3 days/week (indoor training, outdoor)

### Sample Week
- **Monday**: Rest or yoga (recovery from weekend)
- **Tuesday**: Climbing (indoor, 90 min, technique)
- **Wednesday**: Easy run (6 km, 30 min, RPE 3-4)
- **Thursday**: Climbing (comp prep, 105 min, RPE 5-6)
- **Friday**: Rest or yoga
- **Saturday**: Long run (18 km, 110 min, RPE 4)
- **Sunday**: Climbing (outdoor, 4 hours, RPE 4-5)

**Load breakdown**:
- Running: 850 AU systemic, 850 AU lower-body (40% of load)
- Climbing: 900 AU systemic, 90 AU lower-body (42% of load)
- Yoga: 60 AU systemic, 10 AU lower-body (3% of load)
- **Total**: 1,810 AU systemic (balanced)

**Analysis**:
- Easy run Wednesday: 24 hours after Tuesday climbing (✓)
- Long run Saturday: 48 hours after Thursday climbing (✓)
- Sunday climbing: 24 hours after long run (✓ - lower-body load from climbing is low)

---

## Common Multi-Sport Mistakes

### 1. Treating all activities as equal
❌ **Bad**: "You trained 6 hours this week" (ignores sport differences)
✅ **Good**: "Your systemic load was 1,800 AU (running 850, climbing 900) with 950 AU lower-body load (mostly running)"

**Use load analysis** to understand true training stress.

### 2. Ignoring lower-body load accumulation
❌ **Bad**: "Climbing doesn't impact running" (oversimplification)
✅ **Good**: "Climbing has low lower-body load, so easy runs are fine next day. Quality runs need more systemic recovery."

**Two-channel model** prevents this error.

### 3. Not discussing conflict policy upfront
❌ **Bad**: Assuming athlete will prioritize running when conflicts arise
✅ **Good**: Set conflict policy during profile setup (`ask_each_time`, `primary_sport_wins`, or `running_goal_wins`)

**Prevent conflict surprises** by establishing policy early.

### 4. Planning running in isolation
❌ **Bad**: Designing 5-day/week running plan without checking climbing schedule
✅ **Good**: "I see you climb Tuesdays and Thursdays. Let's plan running around those fixed commitments."

**Integrate schedules** from the start.

### 5. Overloading a single day
❌ **Bad**: Long run + climbing comp on same day (compounding fatigue)
✅ **Good**: Separate high-load activities by 24-48 hours

**Recovery time** matters more than weekly volume.

---

## Multi-Sport Commands

```bash
# Analyze multi-sport load distribution
sce analysis load --activities activities.json --days 7 --priority equal

# Check if other sports impacting running readiness
sce today  # Returns adaptation triggers including lower-body load warnings

# Forecast multi-sport load across plan
sce risk forecast --weeks 4 --metrics metrics.json --plan plan.json
```

---

## Deep Dive Resources

For complete multi-sport methodology:
- [Run Less, Run Faster](../../../docs/training_books/run_less_run_faster_bill_pierce.md) - FIRST method for multi-sport athletes
- [Coaching Methodology - Sport Multipliers](../../../docs/coaching/methodology.md#sport-multipliers--load-model) - Two-channel load model
- [Coaching Methodology - Multi-Sport Awareness](../../../docs/coaching/methodology.md#multi-sport-awareness) - Conflict resolution strategies
