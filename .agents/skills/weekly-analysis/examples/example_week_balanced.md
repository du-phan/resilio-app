# Example: Balanced Week with Excellent Execution

## Scenario

**Athlete**: Alex, 32F, training for half marathon (12 weeks out)
**Priority**: EQUAL (running + climbing)
**Week**: Week 5 of 12
**Goal**: Maintain 80/20 intensity, balance running/climbing load

---

## Weekly Plan

**Running** (planned):
- Tuesday: 6 km easy
- Thursday: 10 km tempo @ LT pace
- Saturday: 6 km easy
- Sunday: 14 km long run @ easy pace

**Climbing** (planned):
- Wednesday: 90-min bouldering
- Friday: 120-min lead climbing

**Total planned**: 36 km running, 2 climbing sessions

---

## What Actually Happened

### Activities Completed

**Tuesday, Week 5 Day 2**: 6 km easy
- Pace: 6:48/km (prescribed: 6:30-7:00/km)
- HR avg: 145 bpm
- RPE: 4 (conversational)
- Notes: "Felt great, legs fresh"

**Wednesday, Week 5 Day 3**: 90-min bouldering
- Intensity: Moderate-hard
- Load: 210 AU systemic, 26 AU lower-body
- Notes: "Good session, sent V4 project"

**Thursday, Week 5 Day 4**: 10 km tempo
- Pace: 5:32/km (prescribed: 5:30-5:45/km)
- HR avg: 168 bpm
- RPE: 8 (comfortably hard)
- Notes: "Hit target pace, felt controlled"

**Friday, Week 5 Day 5**: 120-min lead climbing
- Intensity: Moderate-hard
- Load: 280 AU systemic, 35 AU lower-body
- Notes: "Endurance climbing, long routes"

**Saturday, Week 5 Day 6**: 6 km easy
- Pace: 6:55/km (prescribed: 6:30-7:00/km)
- HR avg: 142 bpm
- RPE: 3 (very easy)
- Notes: "Legs a bit tired from yesterday, kept it easy"

**Sunday, Week 5 Day 7**: 14 km long run
- Pace: 6:42/km (prescribed: 6:30-7:00/km)
- HR avg: 149 bpm
- RPE: 4 (conversational)
- Notes: "Best long run yet, felt strong throughout"

---

## Analysis: Step by Step

### Step 1: Weekly Summary (`sce week`)

```json
{
  "planned_workouts": 6,
  "completed_activities": 6,
  "completion_rate": 100,
  "planned_volume_km": 36,
  "actual_volume_km": 36,
  "current_metrics": {
    "ctl": 44,
    "atl": 132,
    "tsb": -15,
    "acwr": 1.12,
    "readiness": 68
  },
  "week_changes": {
    "ctl_change": +2,
    "atl_change": +8,
    "tsb_change": -3,
    "acwr_change": +0.05
  }
}
```

**Initial observations**:
- ✅ Perfect completion (100%)
- ✅ Volume exactly as planned (36 km)
- ✅ Metrics stable and healthy

### Step 2: Completion Summary (`sce week`)

```json
{
  "week_start": "2026-01-06",
  "week_end": "2026-01-12",
  "planned_workouts": 5,
  "completed_workouts": 5,
  "completion_rate": 1.0,
  "total_duration_minutes": 220,
  "total_load_au": 460,
  "current_ctl": 44,
  "current_tsb": -15,
  "current_readiness": 68,
  "ctl_change": 2,
  "tsb_change": -3
}
```

**Interpretation**: Excellent completion - athlete is highly consistent.

### Step 3: Intensity Distribution (`sce analysis intensity`)

```json
{
  "distribution": {
    "low_intensity_z1_z2": 78,
    "moderate_high_z3_z5": 22
  },
  "compliance": true,
  "polarization_score": 87,
  "violations": [],
  "recommendations": [
    "Excellent intensity discipline - maintain current approach"
  ]
}
```

**Interpretation**:
- ✅ 78/22 distribution (target: ~80/20)
- ✅ High polarization score (87/100)
- ✅ Easy runs truly easy (RPE 3-4)
- ✅ Tempo run appropriately hard (RPE 8)

### Step 4: Multi-Sport Load Breakdown (`sce analysis load`)

```json
{
  "systemic_load_by_sport": {
    "running": 850,
    "running_pct": 63,
    "climbing": 490,
    "climbing_pct": 36,
    "other": 10,
    "other_pct": 1
  },
  "lower_body_load_by_sport": {
    "running": 850,
    "running_pct": 93,
    "climbing": 61,
    "climbing_pct": 7
  },
  "total_systemic": 1350,
  "total_lower_body": 911,
  "priority_adherence": "good",
  "fatigue_flags": []
}
```

**Interpretation**:
- Running: 63% of systemic load (good for EQUAL priority)
- Climbing: 36% of systemic load (healthy contribution)
- No multi-sport conflicts detected
- Lower-body load well-managed (climbing doesn't interfere)

### Step 5: Pattern Detection

**Activity notes review**:
```bash
sce activity list --since 7d --has-notes
# All 6 activities have notes - athlete is engaged
```

**Patterns identified**:
1. **Consistency**: 3rd consecutive week with 100% adherence
2. **Intensity discipline**: Easy runs at RPE 3-4, tempo at RPE 8 (good polarization)
3. **Multi-sport planning**: Climbing on rest days from quality running (smart scheduling)
4. **Volume stability**: 36 km for 2nd consecutive week (safe progression)
5. **Positive signals**: "Best long run yet" suggests good adaptation

**Check for concerning signals**:
```bash
sce activity search --query "tired fatigue flat heavy" --since 7d
# Result: No matches

sce activity search --query "pain sore tight discomfort" --since 7d
# Result: No matches (Saturday "legs a bit tired" is normal post-climbing)
```

**No red flags detected**.

### Step 5.5: Capture Significant Pattern as Memory

**Pattern observed**: 3rd consecutive week with 100% adherence - worth storing.

```bash
sce memory add --type TRAINING_RESPONSE \
  --content "Consistently completes 100% of planned workouts, excellent discipline and schedule management" \
  --tags "adherence:excellent,pattern:consistent,discipline:high" \
  --confidence high
```

---

## Step 6: Synthesis and Communication to Athlete

### Weekly Review: Week 5 (Jan 27 - Feb 2)

Great week, Alex! You completed all 6 planned workouts (100% adherence) and hit 36 km exactly. Your CTL increased from 42 → 44, showing steady fitness gains.
Quick defs (first mention only): CTL is your long-term training load—think of it as your 6-week fitness trend. RPE is your perceived effort from 1–10. For multi-sport athletes, these reflect total work across running + other sports.

**Adherence**:
- ✅ Completed all running workouts (easy, tempo, long)
- ✅ Completed both climbing sessions as planned
- ✅ 3rd consecutive week with perfect adherence - impressive consistency!

**Intensity (80/20)**:
- Distribution: 78% easy, 22% hard (excellent compliance)
- Your easy runs stayed at RPE 3-4 (conversational) - great discipline
- Tempo run hit prescribed pace (5:32/km, RPE 8) with good control
- High polarization score (87/100) - you're separating easy from hard effectively

**Multi-Sport Load**:
- Running: 850 AU systemic (63% of total load)
- Climbing: 490 AU systemic (36% of load)
- Good balance for EQUAL priority setting
- Lower-body load well-managed - climbing doesn't interfere with running quality

**Patterns**:
- ✅ Your scheduling is smart: climbing on Wednesday/Friday gives legs recovery before tempo and long run
- ✅ Best long run yet (14 km) - fitness is improving
- ✅ Saturday legs felt "a bit tired" from Friday climbing, but you smartly kept it easy (6:55/km pace)
- ✅ No pain/discomfort signals - body adapting well

**Metrics (Week-over-week changes)**:
Quick defs (first mention only): TSB is freshness (long-term fitness minus short-term fatigue). ACWR compares this week to your recent average; high values mean a sudden spike. For multi-sport athletes, these reflect total work across running + other sports.
- CTL: 42 → 44 (+2, steady progression)
- ATL: 124 → 132 (+8, load absorbed well)
- TSB: -12 → -15 (-3, productive training zone)
- ACWR: 1.07 → 1.12 (+0.05, safe zone)

**Interpretation**: Your body is adapting well to the training load. CTL rising steadily, ACWR in safe zone, and TSB in productive range. All green lights.

**Next Week Recommendations**:
1. **Maintain current volume** (36 km) for one more week - let your body consolidate gains
2. **Keep intensity discipline** - easy runs at 6:30-7:00/km, tempo at 5:30-5:45/km
3. **Continue current climbing schedule** (Wed/Fri) - it's working well with running
4. **Week after next**: We can increase to 40 km if metrics stay stable

**Focus for next week**: Consistency. You've hit 3 perfect weeks in a row - let's make it 4.

**Overall**: This is textbook training execution. You're demonstrating excellent discipline with intensity, smart multi-sport scheduling, and perfect adherence. Your fitness is building steadily without red flags. Keep doing exactly what you're doing.

---

## Key Coaching Elements Demonstrated

1. **Positive opening**: "Great week" + key stat (100% adherence, 36 km)
2. **Data-driven**: Referenced specific numbers (CTL, ACWR, pace, RPE)
3. **Balanced feedback**: Highlighted strengths, no criticisms needed (rare!)
4. **Multi-sport synthesis**: Connected climbing schedule to running quality
5. **Specific recommendations**: Concrete volume and pace targets for next week
6. **Encouragement**: "Textbook execution", "Keep doing what you're doing"

**Why this works**:
- Athlete feels seen (all their notes acknowledged)
- Athlete understands *why* training is working (data + explanation)
- Athlete knows exactly what to do next week (clear guidance)
- Athlete feels motivated (positive reinforcement)
