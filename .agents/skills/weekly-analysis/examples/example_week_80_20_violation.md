# Example: Week with 80/20 Intensity Violation

## Scenario

**Athlete**: Jordan, 28M, training for 10K (8 weeks out)
**Priority**: PRIMARY (running focus)
**Week**: Week 3 of 12
**Issue**: Moderate-intensity rut (easy runs too fast)

---

## Weekly Plan

**Running** (planned):
- Tuesday: 8 km easy @ 6:45-7:15/km
- Thursday: 6 x 800m intervals @ 4:30/km, 400m recovery
- Saturday: 8 km easy @ 6:45-7:15/km
- Sunday: 16 km long run @ 6:45-7:15/km

**Total planned**: 42 km

---

## What Actually Happened

### Activities Completed

**Tuesday**: 8 km
- **Planned**: Easy @ 6:45-7:15/km (RPE 3-4)
- **Actual**: 6:05/km average
- HR avg: 162 bpm (high for easy)
- RPE: 6 (moderate)
- Notes: "Felt good, legs had energy"

**Thursday**: Intervals
- **Planned**: 6 x 800m @ 4:30/km
- **Actual**: 6 x 800m @ 4:35/km average (slightly slower)
- HR avg: 178 bpm
- RPE: 9 (very hard)
- Notes: "Struggled more than expected, legs heavy"

**Saturday**: 8 km
- **Planned**: Easy @ 6:45-7:15/km (RPE 3-4)
- **Actual**: 5:50/km average
- HR avg: 165 bpm (high for easy)
- RPE: 6 (moderate)
- Notes: "Wanted to test pace, felt okay"

**Sunday**: 16 km long run
- **Planned**: Easy @ 6:45-7:15/km (RPE 4)
- **Actual**: 6:20/km average (too fast for long run)
- HR avg: 158 bpm
- RPE: 5-6 (moderate, drifted higher at end)
- Notes: "Started easy but picked up pace, last 3km felt harder"

**Total**: 42 km completed (100% adherence by volume)

---

## Analysis: Step by Step

### Step 1: Weekly Summary (`sce week`)

```json
{
  "planned_workouts": 4,
  "completed_activities": 4,
  "completion_rate": 100,
  "planned_volume_km": 42,
  "actual_volume_km": 42,
  "current_metrics": {
    "ctl": 38,
    "atl": 145,
    "tsb": -18,
    "acwr": 1.25,
    "readiness": 52
  }
}
```

**Initial observations**:
- ✅ Perfect volume adherence (42 km)
- ⚠️ Readiness dropped to 52 (moderate)
- ⚠️ ACWR at 1.25 (approaching caution zone)

### Step 2: Adherence Analysis

```json
{
  "completion_rate": 100,
  "load_variance": +15,
  "workout_type_adherence": {
    "easy": "3/3 completed",
    "intervals": "1/1 completed"
  },
  "missed_workouts": [],
  "extra_activities": []
}
```

**Load variance +15 AU**: Actual load slightly higher than planned (easy runs run too hard).

### Step 3: Intensity Distribution (`sce analysis intensity`)

```json
{
  "distribution": {
    "low_intensity_z1_z2": 62,
    "moderate_high_z3_z5": 38
  },
  "compliance": false,
  "polarization_score": 58,
  "violations": [
    "Moderate-intensity rut detected",
    "Easy runs averaging RPE 5-6 (should be 3-4)",
    "Poor separation between easy and hard efforts"
  ],
  "recommendations": [
    "Slow down easy runs by 40-70 seconds per km",
    "Target conversational pace (can talk in full sentences)",
    "Check: If HR >155 bpm on easy runs, slow down"
  ]
}
```

**Interpretation**:
- ❌ 62/38 distribution (should be ~80/20)
- ❌ Low polarization score (58/100)
- ❌ Easy runs at moderate intensity (RPE 5-6, not 3-4)

### Step 4: Detailed Pace Analysis

Compare prescribed vs actual paces:

| Run | Prescribed | Actual | Difference | Issue |
|-----|------------|--------|------------|-------|
| Tuesday easy | 6:45-7:15/km | 6:05/km | -50 sec/km | Too fast |
| Thursday intervals | 4:30/km | 4:35/km | +5 sec/km | Slightly slow |
| Saturday easy | 6:45-7:15/km | 5:50/km | -65 sec/km | Too fast |
| Sunday long | 6:45-7:15/km | 6:20/km | -35 sec/km | Too fast |

**Pattern**: Easy runs 35-65 sec/km too fast consistently.

### Step 5: Connect Dots - Why Intervals Felt Hard

**Hypothesis**: Tuesday's too-fast easy run (6:05/km at RPE 6) prevented full recovery before Thursday intervals.

**Evidence**:
- Tuesday: RPE 6 (should be 3-4) → accumulated fatigue
- 48 hours later (Thursday): Intervals felt "very hard" (RPE 9), slower than target
- Athlete notes: "legs heavy" on Thursday

**Cause-effect**: Insufficient recovery between hard efforts due to easy runs run at moderate intensity.

---

## Step 6: Synthesis and Communication to Athlete

### Weekly Review: Week 3 (Jan 13-19)

Solid week, Jordan! You completed all 42 km as planned (100% adherence) and hit your interval workout. Let's talk about one important adjustment for next week.
Quick defs (first mention only): RPE is your perceived effort from 1–10.

**Adherence**:
- ✅ Completed all 4 workouts (42 km total)
- ✅ Hit your interval session
- ✅ Volume is on track

**Intensity (80/20) - Needs Adjustment**:
- **Distribution**: 62% easy, 38% hard (should be ~80/20)
- **The issue**: Your easy runs are too fast - you're running them at moderate intensity (RPE 5-6) instead of easy (RPE 3-4)

Here's what happened:
- **Tuesday easy**: 6:05/km pace → RPE 6 (prescribed: 6:45-7:15/km, RPE 3-4)
- **Saturday easy**: 5:50/km pace → RPE 6 (prescribed: 6:45-7:15/km, RPE 3-4)
- **Sunday long**: 6:20/km pace → RPE 5-6 (prescribed: 6:45-7:15/km, RPE 4)

**Why this matters**:
- **Moderate intensity** (RPE 5-6) is the "gray zone" - it's too hard to recover from but not hard enough for quality adaptations
- Result: You accumulate fatigue without fitness gains
- Evidence: Thursday intervals felt "very hard" and you struggled to hit target pace - likely because Tuesday's too-fast easy run prevented full recovery

**Your easy runs are actually tempo pace.** This is super common - most runners make this mistake. The fix is simple but will feel uncomfortable at first.

**VDOT Pace Zones** (based on your VDOT 48):
VDOT is a running fitness score based on your recent race or hard-effort times. I use it to set your training paces so your running stays matched to your current fitness alongside your other sports.
- **Easy**: 6:45-7:15/km ← Target this
- **Tempo/LT**: 5:15-5:30/km
- **Intervals**: 4:25-4:35/km

You're running easy at 5:50-6:05/km - that's between easy and tempo (the gray zone).

**Metrics**:
Quick defs (first mention only): CTL is your long-term training load—think of it as your 6-week fitness trend. ACWR compares this week to your recent average; high values mean a sudden spike. Readiness is a recovery score—higher usually means you can handle harder work. For multi-sport athletes, these reflect total work across running + other sports.
- CTL: 36 → 38 (+2, steady)
- ACWR: 1.18 → 1.25 (+0.07, approaching caution zone)
- Readiness: 68 → 52 (-16, concerning drop)

**Interpretation**: The too-fast easy pace is contributing to fatigue accumulation (readiness dropped 16 points). ACWR is climbing toward 1.3 (caution zone).

**Next Week - Primary Goal: Nail Easy Pace**:
1. **Slow down easy runs to 6:45-7:15/km** (will feel "too slow" - that's normal)
2. **Check**: You should be able to talk in full sentences. If you can't, slow down more.
3. **Heart rate cap**: Keep HR <155 bpm on easy days (yours averaged 160-165)
4. **Volume**: Maintain 42 km (don't increase while fixing intensity)
5. **Intervals**: Same workout as this week - but you'll nail the pace with proper recovery

**Focus for next week**: Discipline on easy runs. Slow down and trust the process.

**Why slowing down will help**:
- ✅ Better recovery between quality sessions → intervals will feel easier
- ✅ Lower injury risk (ACWR will stabilize)
- ✅ Build aerobic base without fatigue
- ✅ Higher total volume capacity over time

**Overall**: You're training hard and showing great commitment. Now we need to channel that effort more strategically - easy runs truly easy, hard runs truly hard. This one adjustment will unlock your next level of performance.

---

## Follow-Up Actions

### Recommended Next Steps

1. **Send VDOT pace table**:
   ```bash
   sce vdot paces --vdot 48
   ```
   Share with athlete so they have reference.

2. **Consider heart rate caps**:
   If athlete continues to struggle with pacing by feel, prescribe HR caps for easy runs.
   ```
   Easy runs: Keep HR <155 bpm (not pace-based)
   This removes the temptation to "chase pace"
   ```

3. **Check compliance next week**:
   In Week 4 review, specifically verify:
   - Easy run paces: Were they 6:45-7:15/km?
   - Heart rate: Did HR stay <155 bpm?
   - Interval quality: Did they feel more manageable?

4. **Capture pattern if persists**:
   If athlete runs easy too fast again in Week 4, store as memory:
   ```bash
   sce memory add --type TRAINING_RESPONSE \
     --content "Tendency to run easy runs 40-60 sec/km too fast (RPE 6 instead of 4), requires frequent reminders and HR caps" \
     --tags "intensity:easy,violation:pace,pattern:consistent" \
     --confidence high
   ```

---

## Key Coaching Elements Demonstrated

1. **Positive opening**: Acknowledged adherence and volume completion
2. **Data-driven**: Specific pace comparisons (6:05 vs 6:45-7:15)
3. **Explained cause-effect**: Connected Tuesday's pace to Thursday's struggle
4. **Normalized the mistake**: "Super common - most runners make this"
5. **Provided VDOT reference**: Showed athlete their prescribed zones
6. **Specific next-week goal**: "Nail easy pace" with concrete targets
7. **Explained the "why"**: Benefits of slowing down (recovery, injury prevention)
8. **Encouraging close**: "Unlock your next level of performance"

**Why this works**:
- Athlete understands the problem (not just "run slower")
- Athlete sees the consequence (interval struggle)
- Athlete has concrete actions (6:45-7:15/km, HR <155)
- Athlete feels supported (not criticized for enthusiasm)
