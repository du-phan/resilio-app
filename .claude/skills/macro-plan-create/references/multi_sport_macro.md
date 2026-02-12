# Multi-Sport Training - Macro Planning

Strategic volume planning for multi-sport athletes. Establishes running priority, load distribution targets, and conflict resolution policy for the 16-week plan.

---

## Running Priority Levels

### PRIMARY (Race Goal Focus)
**Definition**: Running is the main sport, race goal takes precedence

**Macro plan structure**:
- Full periodization (base → build → peak → taper)
- Standard volume progression (50-80 km/week peak)
- Other sports supplement, don't replace key runs

**Volume planning**:
- Peak running volume: 60-70% of total load
- Other sports: 30-40% of total load
- Plan assumes running availability 4-5 days/week

**Example goal**: Half marathon PR in 16 weeks
- Running: 4-5 days/week
- Climbing: 1-2 days/week (on rest days or after easy runs)
- Cycling: 1 day/week cross-training (easy spin)

**Conflict default**: Running goal wins (key workouts protected)

---

### EQUAL (Balance Both Sports)
**Definition**: Running and other sport are equally important

**Macro plan structure**:
- Reduced running frequency (2-4 days/week)
- Lower peak volume (40-60 km/week)
- Coordinate phases with other sport's season
- Flexible conflict resolution

**Volume planning**:
- Peak running volume: 40-50% of total load
- Other sport: 40-50% of load
- Recovery/yoga: 10-20% of load
- Plan assumes running availability 3-4 days/week

**Periodization coordination**:
- If other sport peaks in spring: Running base phase in winter, reduce running during other sport's peak
- If other sport off-season: Increase running volume, other sport for cross-training

**Example goal**: Half marathon + climbing season
- Running: 3 days/week (1 long, 1 tempo, 1 easy)
- Climbing: 2-3 days/week (comps, training, outdoor)

**Conflict default**: Ask each time (negotiate based on context)

---

### SECONDARY (Other Sport Primary)
**Definition**: Running supports overall fitness, other sport is focus

**Macro plan structure**:
- Minimal running frequency (2-3 days/week)
- No progressive buildup (maintain base)
- No peak phase (running is steady-state)
- No race-specific workouts (unless fun race)

**Volume planning**:
- Running volume: 20-30% of total load (maintenance only)
- Other sport: 70-80% of load
- No volume progression for running

**Example**: Competitive climber maintaining running fitness
- Running: 2 days/week (both easy, 30-40 min)
- Climbing: 4-5 days/week (training, comps, projects)

**Conflict default**: Primary sport wins (running is flexible)

---

## Volume Reduction Based on Priority

### EQUAL Priority Volume Adjustment

**Standard PRIMARY peak** (running-only): 60 km/week

**With EQUAL priority**:
- Reduce running 20-30%: 42-48 km/week peak
- Account for systemic load from other sports
- Example: 45 km running + 3 climbing sessions ≈ 70 km running-equivalent

**Rationale**: Other sport contributes systemic load but minimal lower-body load. Running volume reduced to prevent total load overreach while maintaining running-specific stimulus.

### Load Distribution Planning

**Calculate total systemic load target**:
- PRIMARY: ~80-100 load units/week peak (mostly running)
- EQUAL: ~100-120 load units/week peak (balanced)
- SECONDARY: ~80-100 load units/week peak (mostly other sport)

**Example (EQUAL priority, week 12)**:
- Running: 45 km × 1.0 = 45 AU systemic (40% of load)
- Climbing: 3 sessions × 105 min × RPE 5 × 0.6 = 48 AU systemic (42% of load)
- Yoga: 2 sessions × 60 min × RPE 3 × 0.35 = 12 AU systemic (11% of load)
- **Total**: 105 AU systemic load (safe total aerobic load)

**In macro template**, this becomes:
```json
{
  "weekly_volumes_km": [..., 45.0, ...],          // Week 12 running volume
  "target_systemic_load_au": [..., 105.0, ...],   // Week 12 total systemic load
  ...
}
```

The weekly planner then distributes the 105 AU systemic budget across running (45 AU) + climbing (48 AU) + yoga (12 AU) based on actual training response.

---

## Conflict Policy (Strategic Level)

When running and other sports conflict (same day or consecutive days), policy determines resolution **across the entire plan**.

### 1. `ask_each_time` (Recommended for EQUAL priority)
**Approach**: Present trade-offs, athlete decides

**Macro planning**: Don't pre-commit to conflict resolution. Allow flexibility week-by-week.

**Use when**: Both sports are equally important, conflicts are infrequent, athlete wants autonomy

### 2. `primary_sport_wins` (Protect Primary Sport)
**Approach**: Automatically adjust running around other sport's schedule

**Macro planning**: Identify fixed commitments for primary sport, plan running flexibility around those dates.

**Use when**: Other sport has fixed commitments (comps, team schedule), running is secondary or equal

**Example**: Climbing comps on weeks 4, 8, 12 → Plan reduced running those weeks automatically

### 3. `running_goal_wins` (Prioritize Race Prep)
**Approach**: Keep key runs unless injury risk

**Macro planning**: Protect long runs and quality workouts in plan. Other sports are flexible or adjusted.

**Use when**: Race proximity high (8-12 weeks out), running is primary focus

**Example**: Weeks 13-16 (final taper) → Running workouts protected, other sports reduced or skipped

---

## Planning Multi-Sport Volume Progression

### Step 1: Determine Running Priority
**During profile setup**:
- PRIMARY: Race goal focus
- EQUAL: Balance running + other sport
- SECONDARY: Running is cross-training

### Step 2: Set Volume Targets Based on Priority

**PRIMARY**:
- Starting volume: Based on CTL (standard `resilio guardrails safe-volume`)
- Peak volume: Goal-specific (half marathon: 60-70 km)
- Progression: Standard 10% rule

**EQUAL**:
- Starting volume: 70-80% of PRIMARY equivalent
- Peak volume: 40-50 km (regardless of goal distance)
- Progression: Conservative 7-8% per week

**SECONDARY**:
- Starting volume: Current maintenance level
- Peak volume: Same as starting (no buildup)
- Progression: None (steady-state)

### Step 3: Account for Other Sports in Load

**Don't just count running kilometers** - calculate total systemic load:

```bash
resilio analysis load --activities activities.json --days 7 --priority equal
```

**Use output** to verify total load stays within 100-120 load units/week during peak weeks.

### Step 4: Schedule Recovery Weeks Considering Multi-Sport Load

**EQUAL priority**: Recovery weeks protect against cumulative multi-sport fatigue
- If other sport has competition weeks: Plan running recovery week that same week
- If other sport is off-season: Normal running recovery schedule (every 4th week)

**Example**: Climbing comp week 8 → Plan running recovery week 8 (both sports reduced = true recovery)

---

## Macro Planning Commands

```bash
# Set running priority in profile
resilio profile set --run-priority equal  # or primary, secondary

# Set conflict policy
resilio profile set --conflict-policy ask_each_time  # or running_goal_wins, primary_sport_wins

# Analyze historical multi-sport distribution
resilio analysis load --activities activities.json --days 90

# Safe volume with multi-sport context
resilio guardrails safe-volume --ctl 44 --goal-type half_marathon --priority equal
```

---

## Deep Dive Resources

- [Run Less, Run Faster](../../../docs/training_books/run_less_run_faster_bill_pierce.md) - FIRST method for multi-sport athletes

**Note**: For complete multi-sport methodology, see SKILL.md Additional Resources section.
