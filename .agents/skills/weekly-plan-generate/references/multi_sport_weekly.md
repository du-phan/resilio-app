# Multi-Sport Training - Weekly Planning

Workout placement and daily scheduling for multi-sport athletes. Uses two-channel load model to determine when running workouts can be placed relative to other sports.

---

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

## Sport Multipliers (For Workout Placement)

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

## Placing Running Workouts Around Other Sports

### Step 1: Identify Fixed Commitments
**Check athlete's profile or ask**:
- "Which days are non-negotiable for [other sport]?"
- "Are [other sport] sessions fixed or flexible?"

**Example**:
- Climbing: Tuesday evenings (team night), Thursday (comp prep), Saturday (comp or outdoor)
- → Fixed: Tuesday, Thursday, Saturday for climbing

### Step 2: Map Running Around Fixed Days
**Running placement principles**:
- Easy runs: Can be 24 hours after non-running activity (systemic load moderate, lower-body fresh)
- Quality runs: Need 48 hours after high-intensity non-running activity (both channels recovered)
- Long runs: Need 48+ hours after high lower-body load activity (cumulative leg fatigue risk)

**Example schedule (given fixed climbing days above)**:
- **Monday**: Rest or yoga
- **Tuesday**: Climbing (fixed)
- **Wednesday**: Easy run (24 hours after Tuesday climbing - systemic OK, legs fresh)
- **Thursday**: Climbing (fixed)
- **Friday**: Easy run (24 hours after Thursday climbing)
- **Saturday**: Climbing (fixed)
- **Sunday**: Long run (24 hours after Saturday climbing - low lower-body carryover)

**Quality workout placement**: Monday tempo/intervals (48 hours after Saturday climbing, fresh for week ahead)

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

**Strength training (moderate lower-body) → Running**:
- Easy run next day: ⚠ Possible (depends on leg work volume)
- Quality run next day: ✗ Avoid (DOMS risk)
- Long run next day: ✗ Avoid (compounding leg fatigue)

### Step 4: Validate Multi-Sport Load for the Week
```bash
sce analysis load --activities activities.json --days 7 --priority equal
```

**Returns**:
- Systemic load by sport
- Lower-body load by sport
- Priority adherence: Good/fair/poor
- Fatigue flags (e.g., "High cycling load before quality run")

**Action**: Adjust weekly workout placement if load imbalance detected

---

## Example Weekly Schedule (EQUAL Priority)

**Athlete**: Half marathon training + competitive climber
**Running**: 3 days/week (long, tempo, easy)
**Climbing**: 2-3 days/week (indoor training, outdoor)

### Sample Week
- **Monday**: Rest or yoga (recovery from weekend)
- **Tuesday**: Climbing (indoor, 90 min, technique)
  - Load: 450 AU systemic, 45 AU lower-body
- **Wednesday**: Easy run (6 km, 30 min, RPE 3-4)
  - Load: 120 AU systemic, 120 AU lower-body
- **Thursday**: Climbing (comp prep, 105 min, RPE 5-6)
  - Load: 550 AU systemic, 55 AU lower-body
- **Friday**: Rest or yoga
- **Saturday**: Long run (18 km, 110 min, RPE 4)
  - Load: 440 AU systemic, 440 AU lower-body
- **Sunday**: Climbing (outdoor, 4 hours, RPE 4-5)
  - Load: 750 AU systemic, 75 AU lower-body

**Load breakdown**:
- Running: 850 AU systemic, 850 AU lower-body (40% of load)
- Climbing: 900 AU systemic, 90 AU lower-body (42% of load)
- Yoga: 60 AU systemic, 10 AU lower-body (3% of load)
- **Total**: 1,810 AU systemic (balanced)

**Analysis**:
- Easy run Wednesday: 24 hours after Tuesday climbing (✓ - low lower-body carryover)
- Long run Saturday: 48 hours after Thursday climbing (✓ - full recovery)
- Sunday climbing: 24 hours after long run (✓ - climbing has low lower-body demand)

---

## Handling Workout Conflicts (Weekly Level)

### Scenario 1: Same-Day Conflict
**Problem**: Saturday long run (planned) + Saturday climbing comp (announced this week)

**Resolution options**:
1. **Shift long run to Sunday** - Does athlete have availability? Is Sunday climbing instead?
2. **Do both (sequential)** - Easy run AM + comp PM, or vice versa (check total load)
3. **Replace long run with easy run** - Compromise on running volume this week
4. **Skip climbing comp** - Depends on conflict policy and race proximity

**Check conflict policy** (from profile):
- `ask_each_time`: Present options using chat-based numbered options
- `running_goal_wins`: Keep long run, skip comp (or move comp)
- `primary_sport_wins`: Keep comp, adjust running

### Scenario 2: Back-to-Back High Intensity
**Problem**: Tuesday intervals (planned) + Wednesday climbing comp (fixed)

**Resolution**:
- **Option A**: Move intervals to Monday (give 48 hours before comp)
- **Option B**: Replace intervals with tempo (lower intensity, shorter recovery)
- **Option C**: Skip intervals this week (prioritize comp)

**Guideline**: Don't do back-to-back high-intensity days across sports

---

## Checking Daily Readiness with Multi-Sport Context

```bash
sce today
```

**Returns adaptation triggers including multi-sport warnings**:
- `lower_body_fatigue_high`: Recent cycling/strength → quality run compromised
- `session_density_high`: Too many hard sessions (running + other sport) in 7 days
- `multi_sport_conflict`: Today's planned workout conflicts with other sport session

**Response to triggers**:
- **Lower-body fatigue high**: Replace quality run with easy run
- **Session density high**: Skip today's quality session, insert rest day
- **Multi-sport conflict**: Apply conflict policy

---

## Common Multi-Sport Mistakes (Weekly Level)

### 1. Not checking other sport's schedule before generating workouts
❌ **Bad**: Generate week's running plan without knowing athlete has climbing comp Saturday
✅ **Good**: Check profile for fixed commitments, ask about upcoming events, then place workouts

### 2. Ignoring lower-body load accumulation
❌ **Bad**: Planning quality run Thursday after Wednesday cycling (moderate lower-body load)
✅ **Good**: Check lower-body load from previous day, adjust to easy run if needed

### 3. Same-day double sessions without load check
❌ **Bad**: Long run AM + climbing PM without calculating total load (may exceed safe systemic load)
✅ **Good**: Calculate combined load, ensure <120 load units/day

**Example check**:
- Long run: 18 km × 1.0 = 440 AU
- Climbing: 120 min × RPE 5 × 0.6 = 360 AU
- **Total**: 800 AU (acceptable if both are moderate intensity)

### 4. Not providing recovery after multi-sport overload
❌ **Bad**: Hard running Mon + climbing Tue + cycling Wed + hard running Thu
✅ **Good**: Hard running Mon + easy climbing Tue + rest/yoga Wed + hard running Thu

**48-72 hour rule** applies across ALL sports, not just running

---

## Weekly Multi-Sport Commands

```bash
# Check multi-sport load for current week
sce analysis load --activities activities.json --days 7 --priority equal

# Check today's readiness considering other sports
sce today

# View upcoming other sport commitments (from profile)
sce profile get | jq -r '.sports'

# Forecast multi-sport load for next week
sce risk forecast --weeks 1 --metrics metrics.json --plan plan.json
```

---

## Deep Dive Resources

- [Run Less, Run Faster](../../../docs/training_books/run_less_run_faster_bill_pierce.md) - FIRST method for multi-sport athletes

**Note**: For complete multi-sport methodology and sport multipliers, see SKILL.md Additional Resources section.
