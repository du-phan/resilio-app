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
