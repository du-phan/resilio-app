# Lap Data Analysis Reference Guide

This guide explains how to use lap data to verify workout execution and detect common training mistakes.

## Overview

Lap data provides lap-by-lap granularity (distance, pace, HR, elevation) enabling the AI coach to:
- Verify workout execution against prescribed intensities
- Detect pacing errors (starting too fast, fading)
- Analyze effort distribution (HR drift, decoupling)
- Assess interval consistency

## CLI Command

```bash
resilio activity laps <activity-id>
```

**Output**: Table showing lap breakdown with distance, time, pace, HR, elevation per lap.

**Example output**:
```
Laps: Tempo Run (2026-02-11)
┏━━━━━┳━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━┓
┃ Lap ┃ Distance ┃   Time ┃   Pace ┃ Avg HR ┃ Max HR ┃ Elev+ ┃
┡━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━┩
│   1 │  2.50 km │  17:18 │   6:55 │    136 │    144 │    5m │
│   2 │  2.94 km │  15:00 │   5:06 │    178 │    191 │   -4m │
│   3 │  2.00 km │  14:16 │   7:08 │    158 │    165 │    3m │
└─────┴──────────┴────────┴────────┴────────┴────────┴───────┘
```

## Common Training Mistakes (Evidence-Based)

Principles adapted from Daniels, Pfitzinger, Fitzgerald, and FIRST training methodologies. Lap data enables detection.

### 1. Intervals Too Fast (Daniels)

**Mistake**: Running VO2max intervals significantly faster than prescribed I-pace.

**Impact**: Introduces anaerobic stress without providing additional aerobic (VO2max) benefit (Daniels' Running Formula principle)

**Detection**: Compare actual interval paces to prescribed I-pace:
- Prescribed: 5 x 1km @ 5:10/km (I-pace from VDOT 52)
- Actual lap data: 5:00, 4:58, 5:02, 5:05, 5:08
- Diagnosis: First 3 intervals too fast (defeats aerobic stimulus)

**Coaching response**: "Your intervals averaged 5:02/km instead of the prescribed 5:10/km I-pace. This pushed you into anaerobic territory, defeating the VO2max aerobic purpose of the workout."

### 2. Easy Runs Too Fast (Fitzgerald's "Moderate-Intensity Rut")

**Mistake**: Running easy/recovery runs at moderate intensity instead of true easy pace.

**Impact**: Compromises recovery, accumulates fatigue, prevents adaptation.

**Detection**: Check warmup lap HR and pace:
- Prescribed: Warmup @ E-pace (6:19-6:49/km), HR < 140
- Actual lap 1: 6:10/km, HR 149
- Diagnosis: Warmup too fast (moderate intensity, not easy)

**Coaching response**: "Your warmup pace (6:10/km) and HR (149) indicate moderate intensity. For proper recovery, warmups should be truly easy: 6:30+/km, HR < 140."

### 3. Tempo/Threshold Too Fast (Pfitzinger)

**Mistake**: Running tempo portion at race effort instead of threshold pace.

**Impact**: Causes rapid lactate accumulation and changes the workout's stimulus (Advanced Marathoning principle)

**Detection**: Compare threshold lap pace to T-pace range:
- Prescribed: 15min @ T-pace (5:02-5:14/km)
- Actual lap 2: 4:58/km, HR 185
- Diagnosis: Tempo too fast (race effort, not threshold)

**Coaching response**: "Your threshold block was at 4:58/km (HR 185), faster than the target 5:02-5:14 T-pace. This shifted you into anaerobic territory rather than maintaining threshold stimulus."

### 4. Starting Long Runs Too Fast (Training Principle)

**Mistake**: Starting out too fast instead of easing into first few miles.

**Impact**: Excessive fatigue, fade in later miles, poor race-day pacing practice.

**Detection**: Check lap progression for fade pattern:
- Laps 1-10: 5:30 → 5:35 → 5:40 → 5:45 → 5:50 → 5:55 → 6:00 → 6:05 → 6:10 → 6:15
- Pattern: Continuous fade (30 seconds/km slower by end)
- Diagnosis: Started too fast, couldn't maintain pace

**Coaching response**: "Your long run showed a classic fade pattern: starting at 5:30/km and fading to 6:15/km. This suggests overpacing early miles. For long runs, aim for even pacing or negative splits."

### 5. HR Drift (Cardiovascular Decoupling)

**Mistake**: Not recognizing signs of heat stress, dehydration, or accumulated fatigue.

**Impact**: Suboptimal training stimulus, increased injury risk, poor recovery.

**Detection**: HR increasing while pace stays constant:
- Lap 1: 6:30/km @ HR 145
- Lap 5: 6:30/km @ HR 158
- Drift: +13 BPM at same pace
- Diagnosis: Heat stress or dehydration

**Coaching response**: "Your HR increased 13 BPM across the run while maintaining the same pace. This HR drift suggests heat stress or dehydration. Consider: hydration strategy, time of day, temperature conditions."

## Analysis Workflow

When reviewing a structured workout:

1. **Load lap data**: `resilio activity laps <activity-id>`

2. **Identify workout structure**:
   - Warmup phase (easy pace/HR)
   - Work phase (intervals, tempo, threshold)
   - Cooldown phase (easy pace/HR)

3. **Verify each phase**:
   - **Warmup**: Did HR stay < 140? Was pace easy?
   - **Work intervals**: Were paces consistent? Hit target range?
   - **Tempo/threshold**: Was pace in prescribed range? HR appropriate?
   - **Cooldown**: Did athlete cool down properly?

4. **Check pacing patterns**:
   - Even pacing: Good
   - Negative split: Good (building confidence)
   - Fade: Red flag (started too fast)
   - Surge: Red flag (poor pacing discipline)

5. **Calculate consistency** (for intervals):
   - Coefficient of Variation (CV) = StdDev / Mean
   - CV < 3%: Excellent pacing discipline
   - CV 3-5%: Acceptable
   - CV > 5%: Poor pacing (coaching issue)

6. **Flag issues**:
   - Starting too fast → Coaching feedback needed
   - Incorrect intensity → Pacing education required
   - HR drift → Hydration/environmental factors
   - Inconsistent intervals → Pacing discipline work

## When Lap Data Is Not Available

Not all activities have lap markers:
- Manual entry (no GPS data)
- GPS issues during activity
- Athlete didn't use lap function on watch
- Non-running activities (climbing, strength)
- Historical activities >60 days old (adaptive sync strategy)

**Fallback approach**:
- Use aggregate metrics (total distance, average pace/HR)
- Note limitation in analysis
- Can still assess overall intensity, but can't verify execution quality

**Note on sync strategy**: During first-time sync (>90 days), lap data is only fetched for activities from the last 60 days (rate limit optimization). Regular incremental syncs fetch all laps. This means:
- Weekly analysis: Always has lap data (activities are recent)
- Historical analysis: May lack lap data for older activities (limited coaching value anyway)

**Example response**: "This tempo run shows good aggregate pace (5:08/km avg), but I can't verify lap-by-lap execution without lap data. In future workouts, ensure your watch is set to record laps so we can analyze pacing consistency."

## Integration with Coaching Workflow

**During weekly reviews**:
1. Check completion rates (all activities)
2. Verify plan adherence (planned vs. actual)
3. **Dive into key workouts using lap data** ← NEW STEP
4. Verify intensity distribution (80/20 principle)
5. Assess load balance (multi-sport)
6. Detect patterns (gaps, injuries, adaptation triggers)
7. Provide coaching insights

**Key workouts to verify with lap data**:
- Interval sessions (VO2max, repetition)
- Tempo runs (threshold pace)
- Long runs (pacing discipline)
- Race simulations (negative split execution)

**Skip lap analysis for**:
- Easy recovery runs (unless checking "easy enough")
- Climbing sessions (no lap data)
- Strength/cross-training (no lap data)
- Manual entries (no lap data)
