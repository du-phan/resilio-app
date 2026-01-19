# VDOT & Training Pace Zones Quick Reference

Based on Jack Daniels' _Running Formula_. VDOT represents current running fitness - all training paces derive from it.

## VDOT System Overview

**VDOT**: A measure of running fitness derived from recent race performance
**Range**: 30 (beginner) to 85+ (world-class)
**Use**: Calculates personalized training pace zones (E/M/T/I/R)

### Calculating VDOT
```bash
sce vdot calculate --race-type 10k --time 42:30
# Returns: VDOT 48
```

**Input**: Recent race time (5K, 10K, half, marathon)
**Output**: VDOT value + equivalent race times for other distances

**Recalculate**: After significant progress (every 4-6 weeks) or race performance

---

## Five Training Pace Zones

### E-Pace (Easy)
**Purpose**: Aerobic base building, recovery
**Effort**: Conversational, comfortable
**RPE**: 3-4 (out of 10)
**Heart rate**: 65-79% max HR
**% of training**: 70-80% (most common workout type)

**Use for**:
- Daily easy runs
- Recovery runs (day after hard workout)
- Long run base (most of distance at E-pace)
- Warm-up and cool-down

**Example (VDOT 48)**:
- Pace: 6:00-6:30/km (conversational)
- Should feel "too slow" initially - that's correct

**Common mistake**: Running too fast on easy days → chronic fatigue

---

### M-Pace (Marathon)
**Purpose**: Race pace for marathon distance
**Effort**: "Comfortably hard", sustainable for 2-4 hours
**RPE**: 6-7
**Heart rate**: 80-90% max HR
**% of training**: 5-15% (marathon-specific training only)

**Use for**:
- Marathon race pace workouts
- Long runs with M-pace segments
- Tempo runs for marathon training

**Example (VDOT 48)**:
- Pace: 5:15-5:30/km
- Should feel sustainable for hours (not sprinting)

**Not used for**: 10K or shorter race training (use T-pace and I-pace instead)

---

### T-Pace (Threshold / Tempo)
**Purpose**: Build lactate threshold - the pace you can hold "comfortably hard" for 20-60 minutes
**Effort**: Hard but controlled, can say a few words
**RPE**: 7-8
**Heart rate**: 88-92% max HR
**% of training**: ≤10% of weekly mileage

**Use for**:
- Tempo runs (20-40 min continuous)
- Cruise intervals (3-5 × 5-8 min with 1 min rest)
- Long runs with T-pace segments

**Example (VDOT 48)**:
- Pace: 4:50-5:10/km
- Should feel "comfortably hard" (not maximal)

**Daniels limit**: No more than 10% of weekly volume at T-pace (injury prevention)

---

### I-Pace (Interval / VO2max)
**Purpose**: Develop VO2max (maximal aerobic capacity)
**Effort**: Hard, breathing heavily, short phrases only
**RPE**: 8-9
**Heart rate**: 95-100% max HR
**% of training**: ≤8% of weekly mileage

**Use for**:
- Intervals: 3-5 min work bouts (e.g., 4 × 1000m)
- Total interval time: 10-15 min per session (not including recovery)
- 10K race-specific training

**Example (VDOT 48)**:
- Pace: 4:20-4:40/km
- Should feel very hard but repeatable

**Recovery**: Equal or slightly longer than work time (e.g., 3 min work → 3 min recovery jog)

**Daniels limit**: No more than 8% of weekly volume at I-pace

---

### R-Pace (Repetition / Speed)
**Purpose**: Improve running economy and speed
**Effort**: Very hard, near-maximal, gasping for air
**RPE**: 9-10
**Heart rate**: Not useful (intervals too short to reach target HR)
**% of training**: ≤5% of weekly mileage

**Use for**:
- Short repeats: 200m, 400m, 800m
- Speed work for 5K racing
- Total repeat time: 5-8 min per session
- Strides (20-30 sec accelerations)

**Example (VDOT 48)**:
- Pace: 3:50-4:10/km (800m repeats)
- Should feel near-maximal effort

**Recovery**: Much longer than work time (e.g., 2 min work → 4 min recovery jog)

**Daniels limit**: No more than 5% of weekly volume at R-pace

---

## Getting Training Paces

### From VDOT
```bash
sce vdot paces --vdot 48
```

**Returns**:
```
E-pace: 6:00-6:30/km
M-pace: 5:15-5:30/km
T-pace: 4:50-5:10/km
I-pace: 4:20-4:40/km
R-pace: 3:50-4:10/km (800m repeats)
```

### Adjusting for Conditions
```bash
sce vdot adjust --pace 5:00 --condition altitude --severity 7000
# Returns adjusted pace for 7,000 ft elevation
```

**Conditions**: altitude, heat, humidity, hills
**Use**: When training environment differs from race conditions

---

## Workout Prescription by Training Phase

### Base Phase (Aerobic Foundation)
**Intensity distribution**: 80-90% easy (E-pace), 10-20% moderate (long runs + optional late-base tempo)

**Workout structure**:
- Most runs: E-pace easy runs (all conversational)
- Long run: E-pace with progressive buildup (+10-15 min every 2-3 weeks)
- Optional late-base tempo: 1 × 20 min T-pace (final 2 weeks of base)
- No intervals yet (VO2max work comes later)

**Weekly pattern**: 3-4 easy runs + 1 long run (+ optional 1 tempo in late base)

**Purpose**: Build aerobic foundation, increase volume gradually, prepare body for intensity

---

### Build Phase (Race-Specific Intensity)
**Intensity distribution**: 70-75% easy (E-pace), 25-30% quality (tempo + M-pace + intervals)

**Workout structure**:
- Easy runs: E-pace for recovery and volume
- Tempo runs: T-pace 20-40 min continuous, or cruise intervals (3-5 × 5-8 min @ T-pace)
- M-pace long runs: E-pace with M-pace segments (e.g., 2 × 20 min @ M-pace)
- Intervals: I-pace for 10K and shorter (4-5 × 1000m @ I-pace)
- Recovery week: Every 4th week at 70% volume

**Weekly pattern**: 2-3 easy runs + 1 tempo + 1 long run (with quality) + optional 1 interval session

**Purpose**: Add race-specific intensity, maintain volume, build lactate threshold

---

### Peak Phase (Maximum Load)
**Intensity distribution**: 65-70% easy (E-pace), 30-35% quality (maximum load + race-pace focus)

**Workout structure**:
- Peak week(s) with maximum volume + intensity
- Race-pace workouts frequent (M-pace for marathon, T-pace for 10K)
- Tempo + intervals in same week (highest load)
- Long runs: E-pace with quality segments at race pace
- No recovery weeks (maintain peak load)

**Weekly pattern**: 2-3 easy runs + 1 tempo + 1 interval + 1 long run with quality

**Purpose**: Maximum training load, sharpening for race, build confidence at race pace

---

### Taper Phase (Peak Fitness)
**Intensity distribution**: Maintain pace zones, reduce volume 30-50%

**Workout structure**:
- Week 1 taper: 70% volume, maintain intensity (shorter tempo, shorter intervals)
- Week 2 taper: 50% volume, maintain intensity (very short quality sessions)
- Race week: 40% volume, easy runs + race-pace strides (20-30 sec accelerations)
- Keep intensity: Quality sessions at race pace, just shorter duration
- No hard workouts 3-5 days before race

**Weekly pattern**: 2-3 easy runs + 1 short quality session + 1 short long run

**Purpose**: Reduce fatigue, maintain fitness, peak for race day (TSB target: +5 to +15)

---

### Long Run Progression

**Progression rate**: +10-15 minutes every 2-3 weeks (NOT every week)

**Weekly volume cap**: Long run ≤ 30% of weekly volume (injury prevention)

**Example progression** (half marathon plan, 50 km/week peak):
- Week 1: 90 min (18 km)
- Week 3: 100 min (20 km)
- Week 5: 110 min (22 km)
- Week 7: 120 min (24 km) — cap at 30% of 50 km = 15 km, but duration matters more
- Taper: 90 min → 75 min → 60 min

**Quality long runs** (build/peak phases only):
- Base phase: All E-pace (build aerobic base first)
- Build phase: E-pace with M-pace or T-pace segments (e.g., 10 km E + 2 × 3 km @ M + 5 km E)
- Peak phase: E-pace with race-pace segments (simulate race conditions)

---

### Quality Session Spacing

**Minimum spacing**: 48 hours between quality sessions (lower-body recovery)

**Safe patterns**:
- ✅ Mon: Tempo → Tue: Easy → Wed: Easy → Thu: Intervals
- ✅ Tue: Intervals → Wed: Easy → Thu: Easy → Sat: Long run with quality
- ❌ Mon: Tempo → Tue: Intervals (insufficient recovery)

**Multi-sport consideration**: Easy runs allowed 24 hours after hard climbing/cycling (systemic recovery ok), but quality runs need 48 hours after any hard session.

---

## Workout Type by Race Distance

### 5K Training
- **Primary**: I-pace intervals (develops VO2max)
- **Secondary**: T-pace tempo (lactate threshold)
- **Tertiary**: R-pace repeats (speed)
- **Volume**: E-pace easy runs

**Example week**: 3 easy, 1 tempo, 1 intervals, 1 long run

### 10K Training
- **Primary**: T-pace tempo + I-pace intervals (balanced)
- **Secondary**: M-pace segments (if building to longer distances)
- **Volume**: E-pace easy runs

**Example week**: 3 easy, 1 tempo, 1 intervals, 1 long run

### Half Marathon Training
- **Primary**: T-pace tempo (lactate threshold)
- **Secondary**: M-pace segments (race pace)
- **Tertiary**: I-pace intervals (maintain VO2max)
- **Volume**: E-pace easy runs + long run

**Example week**: 3 easy, 1 tempo, 1 M-pace long run, 1 intervals (every 2-3 weeks)

### Marathon Training
- **Primary**: M-pace segments (race pace specificity)
- **Secondary**: T-pace tempo (lactate threshold)
- **Volume**: E-pace easy runs + long run (very important)

**Example week**: 3 easy, 1 tempo, 1 M-pace long run, occasional intervals

---

## Six-Second Rule (Daniels)

**For novice runners** without recent race data:

1. Run 1 mile at maximal effort
2. VDOT = Mile time
3. Training paces = Mile pace + 6 sec per 400m

**Example**:
- Mile time: 7:00 (=7:00/mile = 4:21/km)
- E-pace: ~6:30/km (+6 sec/400m)
- T-pace: ~5:00/km
- I-pace: ~4:30/km

**Limitations**: Less accurate than race-based VDOT; recalculate after 4-6 weeks

---

## Common Mistakes

1. **E-pace too fast**: RPE 5-6 instead of 3-4 → chronic fatigue
2. **Ignoring pace ranges**: Running at single pace (middle of range) → lack of polarization
3. **Exceeding intensity limits**: >10% T-pace, >8% I-pace → injury risk
4. **Not updating VDOT**: Using outdated paces → training at wrong intensity
5. **Pace obsession on easy runs**: Focusing on pace instead of effort → defeats purpose of easy runs

---

## Training Pace Commands

```bash
# Calculate VDOT from race
sce vdot calculate --race-type 10k --time 42:30

# Get training paces
sce vdot paces --vdot 48

# Predict equivalent race times
sce vdot predict --race-type 10k --time 42:30

# Apply six-second rule (novice runners)
sce vdot six-second --mile-time 7:00

# Adjust pace for conditions
sce vdot adjust --pace 5:00 --condition altitude --severity 7000
```

---

## Deep Dive Resources

For complete VDOT tables, workout prescriptions, and methodology:
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md) - Complete VDOT system
- [CLI Reference - VDOT Commands](../../../docs/coaching/cli_reference.md#vdot-commands) - All VDOT CLI commands
