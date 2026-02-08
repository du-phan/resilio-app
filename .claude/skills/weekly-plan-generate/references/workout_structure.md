# Workout Structure & Session Mechanics

**Context**: During Week 3 planning, the athlete asked whether a tempo session's structure (WU + work + CD) fits within the 8km distance target. This reference clarifies the critical convention.

---

## Section 1: Critical Convention

### Distance Accounting Rules

**`distance_km` = total session distance (WU + work + CD)**

This is a **mandatory convention**:
- `distance_km` includes warm-up, work portion, and cool-down
- `warmup_km` and `cooldown_km` specify WU/CD distances explicitly (at E-pace / E-pace+10-20s)
- Work km = `distance_km - warmup_km - cooldown_km`
- `target_volume_km` (weekly) = sum of all `distance_km` values

**Evidence**:
- `guardrails_weekly.md:68`: "Tempo run: 2 km warm-up + 5 km T-pace + 2 km cool-down = 9 km total"
- Plan validation: sums all `distance_km` to verify against `target_volume_km`

### Daniels Intensity Limits Apply to Work Portion Only

Daniels' quality volume limits (T≤10%, I≤8%, R≤5%) apply to **work km**, not total distance:
- **Tempo (T-pace)**: Work km ≤ 10% of weekly volume
- **Intervals (I-pace)**: Work km ≤ 8% of weekly volume
- **Repetitions (R-pace)**: Work km ≤ 5% of weekly volume

**Example**: 50 km/week plan
- Tempo session: `distance_km: 9.0`, `warmup_km: 2.0`, `cooldown_km: 1.5` → Work = 5.5 km (11% — slightly over, acceptable in build/peak)
- Intervals session: `distance_km: 10.0`, `warmup_km: 2.5`, `cooldown_km: 1.5` → Work = 6.0 km (12% — violation, reduce to 4.0 km work)

### Distance Math Verification

Always verify: `warmup_km + work_km + cooldown_km = distance_km`

If using `intervals` array with explicit distances, sum interval distances to get work km:
- Example: `intervals: [{"distance": "1000m", "reps": 4, "recovery": "400m jog"}]` → work = 4.0 km (recovery doesn't count)

---

## Section 2: WU/CD Design Rules

### Standard WU/CD by Workout Type

| Workout Type | WU (km) | CD (km) | Notes |
|--------------|---------|---------|-------|
| Easy | 0 | 0 | Entire run is E-pace; no separate WU/CD |
| Tempo | 1.5-2.5 | 1.0-2.0 | WU builds gradually to threshold pace |
| Intervals (I-pace) | 2.0-3.0 | 1.5-2.0 | Longer WU for VO2max; include 4-6 strides in last 500m of WU |
| Repetitions (R-pace) | 2.0-3.0 | 1.5 | Include 4-6 strides in final WU km |
| Long run | 0-1.0 | 0 | Optional very easy first km (E-pace +20-30s/km) |

### Key WU/CD Principles

1. **WU/CD pacing**: WU at E-pace, CD at E-pace + 10-20s/km (slightly slower recovery jog)
2. **No explicit pace needed**: The exact WU/CD pace doesn't need specifying in JSON — it's implied by convention (E-pace from VDOT table)
3. **Progressive activation**: WU for quality sessions should include gradual pace progression, ending with strides (4-6 × 100m at R-pace) in the final 500m
4. **Sources**:
   - Daniels: WU 10-15min E-pace ≈ 1.5-2.5km (at 6:00-6:30/km)
   - Pfitzinger: WU 2-3 miles ≈ 3-5km for intervals (we use shorter 2-3km to match Daniels)
   - FIRST: WU/CD = 1 mile each ≈ 1.6km (we use 1.5-2.5km as middle ground)

---

## Section 3: Worked Examples

### Example 1: Base-Phase Easy Run (8km)

**Session goal**: Aerobic endurance, no quality work

**Distance breakdown**:
- Total: 8.0 km (all at E-pace)
- WU: 0 km
- Work: 8.0 km @ E-pace
- CD: 0 km

**JSON snippet**:
```json
{
  "date": "2026-02-10",
  "day_of_week": 0,
  "workout_type": "easy",
  "distance_km": 8.0,
  "target_rpe": 4,
  "pace_range": "6:00-6:30",
  "warmup_km": 0.0,
  "cooldown_km": 0.0,
  "intervals": null,
  "notes": "Full session at easy aerobic pace"
}
```

**Volume accounting**: 8.0 km total → adds 8.0 km to weekly volume

---

### Example 2: Tempo with 15min Threshold Block (8km total)

**Session goal**: Lactate threshold development, constrained to 8km total distance

**Distance breakdown**:
- Total: 8.0 km
- WU: 2.5 km @ E-pace (≈15min)
- Work: 3.0 km @ T-pace (15min at 5:00/km)
- Remaining: 2.5 km split as 1.0 km E-pace buffer + 1.5 km CD

**JSON snippet**:
```json
{
  "date": "2026-02-12",
  "day_of_week": 2,
  "workout_type": "tempo",
  "distance_km": 8.0,
  "target_rpe": 7,
  "pace_range": "5:02-5:14",
  "warmup_km": 2.5,
  "cooldown_km": 1.5,
  "intervals": [
    {
      "duration_minutes": 15,
      "pace": "5:02-5:14",
      "type": "threshold"
    }
  ],
  "notes": "15min continuous threshold block. 1km E-pace transition before cooldown."
}
```

**Volume accounting**:
- Total: 8.0 km (adds to weekly volume)
- T-pace work: 3.0 km (check against 10% limit)
- For 50 km/week: 3.0 / 50 = 6% ✓ (well within limit)

---

### Example 3: Tempo with 20min Continuous Block (10km total)

**Session goal**: Extended lactate threshold work

**Distance breakdown**:
- Total: 10.0 km
- WU: 2.5 km @ E-pace
- Work: 4.0 km @ T-pace (20min at 5:00/km)
- Buffer: 2.0 km @ E-pace (transition)
- CD: 1.5 km @ E-pace +15s

**JSON snippet**:
```json
{
  "date": "2026-02-15",
  "day_of_week": 5,
  "workout_type": "tempo",
  "distance_km": 10.0,
  "target_rpe": 7,
  "pace_range": "5:00-5:12",
  "warmup_km": 2.5,
  "cooldown_km": 1.5,
  "intervals": [
    {
      "duration_minutes": 20,
      "pace": "5:00-5:12",
      "type": "threshold"
    }
  ],
  "key_workout": true,
  "notes": "Continuous 20min tempo block. 2km E-pace transition before CD."
}
```

**Volume accounting**:
- Total: 10.0 km
- T-pace work: 4.0 km
- For 50 km/week: 4.0 / 50 = 8% ✓

---

### Example 4: VO2max Intervals — 4×1000m @ I-pace (10km total)

**Session goal**: VO2max development with controlled volume

**Distance breakdown**:
- Total: 10.0 km
- WU: 2.5 km @ E-pace (include 4-6 strides in final 500m)
- Work intervals: 4 × 1.0 km @ I-pace = 4.0 km
- Recovery jogs: 3 × 0.6 km @ E-pace +20s = 1.8 km (between intervals)
- CD: 1.7 km @ E-pace +15s

**JSON snippet**:
```json
{
  "date": "2026-02-17",
  "day_of_week": 0,
  "workout_type": "intervals",
  "distance_km": 10.0,
  "target_rpe": 8,
  "pace_range": "4:45-4:55",
  "warmup_km": 2.5,
  "cooldown_km": 1.7,
  "intervals": [
    {
      "distance": "1000m",
      "reps": 4,
      "pace": "4:45-4:55",
      "recovery": "400m jog",
      "type": "vo2max"
    }
  ],
  "key_workout": true,
  "notes": "Include 4-6 strides in final 500m of WU. 400m jog recovery between reps."
}
```

**Volume accounting**:
- Total: 10.0 km
- I-pace work: 4.0 km (check against 8% limit)
- For 50 km/week: 4.0 / 50 = 8% ✓ (exactly at limit)

**Distance verification**: 2.5 (WU) + 4.0 (work) + 1.8 (recovery) + 1.7 (CD) = 9.0 km (note: recovery km often estimated, may be slightly under 10km total)

---

### Example 5: Long Run with M-pace Segments — Build Phase (14km)

**Session goal**: Race-specific endurance with marathon pace practice

**Distance breakdown**:
- Total: 14.0 km
- WU: 1.0 km @ E-pace
- Easy running: 5.0 km @ E-pace
- M-pace segment 1: 3.0 km @ M-pace
- Easy transition: 1.0 km @ E-pace
- M-pace segment 2: 3.0 km @ M-pace
- Final easy: 1.0 km @ E-pace
- CD: 0 km (finish at easy pace)

**JSON snippet**:
```json
{
  "date": "2026-02-16",
  "day_of_week": 6,
  "workout_type": "long_run",
  "distance_km": 14.0,
  "target_rpe": 6,
  "pace_range": "6:00-6:30",
  "warmup_km": 1.0,
  "cooldown_km": 0.0,
  "intervals": null,
  "key_workout": true,
  "notes": "5km E-pace, then 2×3km @ M-pace (5:30-5:45) with 1km E-pace between. Finish 1km easy."
}
```

**Why no intervals array?**
M-pace segments in long runs are described in `notes` rather than `intervals` array. The `intervals` array is reserved for threshold/VO2max/R-pace structured work.

**Volume accounting**: 14.0 km total → adds to weekly volume. M-pace segments (6.0 km) don't count against Daniels limits (M-pace is not T/I/R).

---

### Example 6: Recovery/Easy Long Run — Base Phase (12km)

**Session goal**: Endurance volume at pure easy pace

**Distance breakdown**:
- Total: 12.0 km (all at E-pace)
- WU: 0 km
- Work: 12.0 km @ E-pace
- CD: 0 km

**JSON snippet**:
```json
{
  "date": "2026-02-09",
  "day_of_week": 6,
  "workout_type": "long_run",
  "distance_km": 12.0,
  "target_rpe": 5,
  "pace_range": "6:15-6:45",
  "warmup_km": 0.0,
  "cooldown_km": 0.0,
  "intervals": null,
  "notes": "Entire run at easy aerobic pace. Build endurance foundation."
}
```

**Volume accounting**: 12.0 km total

---

## Section 4: Intervals Array Usage

### When to Use `intervals` Array

**Use for**:
- **Tempo blocks**: Continuous threshold efforts (cruise intervals, tempo runs)
- **VO2max intervals**: I-pace repetitions (800m-1600m)
- **Repetitions**: R-pace short intervals (200m-600m)

**Do NOT use for**:
- Easy runs (no quality work)
- Long runs with M-pace segments (describe in `notes` instead)
- Strides (describe in `notes` only)

### Intervals Array Fields

```json
"intervals": [
  {
    "duration_minutes": 15,          // For tempo: time-based block
    "distance": "1000m",              // For I/R-pace: distance-based reps
    "reps": 4,                        // Number of repetitions (for I/R-pace)
    "pace": "5:00-5:12",             // Work interval pace
    "recovery": "400m jog",          // Recovery between reps (for I/R-pace)
    "type": "threshold|vo2max|repetition"  // Intensity classification
  }
]
```

### Tempo vs Intervals vs Repetitions

| Type | Pace | Structure | Example |
|------|------|-----------|---------|
| Tempo | T-pace | Continuous or cruise intervals | 20min continuous, or 3×6min w/ 1min rest |
| Intervals | I-pace | Reps with jog recovery | 6×800m w/ 400m jog |
| Repetitions | R-pace | Short reps with full recovery | 8×400m w/ 400m jog |

---

## Section 5: Volume Accounting Connection

### How `distance_km` Connects to Weekly Volume

1. **Weekly volume target**: `target_volume_km` set in macro plan (e.g., 50.0 km)
2. **Sum of all sessions**: All `distance_km` values across the week must sum to `target_volume_km`
3. **Daniels quality limits**: Extract work km from each quality session, verify against limits:
   - Tempo work km ≤ 10% × `target_volume_km`
   - Intervals work km ≤ 8% × `target_volume_km`
   - R-pace work km ≤ 5% × `target_volume_km`

### 80/20 Intensity Balance

- **Easy volume**: WU + CD + easy runs + long run easy portions
- **Quality time**: Only the interval/tempo work portions (not WU/CD)
- **Target**: ≥80% easy time, ≤20% quality time

**Example**: 50 km week, 5:00-6:00/km average paces
- Tempo: 3.0 km @ 5:00/km = 15min quality | 6.0 km @ 6:00/km easy = 36min easy
- Intervals: 4.0 km @ 4:45/km = 19min quality | 6.0 km @ 6:00/km easy = 36min easy
- Easy runs: 37.0 km @ 6:00/km = 222min easy
- Total: ~34min quality (10%), ~294min easy (90%) ✓

### Long Run Cap (≤30% of Weekly Volume)

Use **total `distance_km`** of long run, not work-only:
- 50 km/week → long run ≤ 15 km
- 60 km/week → long run ≤ 18 km

---

## Section 6: Common Mistakes

### Mistake 1: Setting `distance_km` to Work-Only

❌ **Wrong**:
```json
{
  "workout_type": "tempo",
  "distance_km": 5.0,  // Only the T-pace work!
  "warmup_km": 2.0,
  "cooldown_km": 1.5
}
```
This would mean: 2.0 WU + 5.0 work + 1.5 CD = 8.5 km actual session, but `distance_km` says 5.0 → volume sum falls short by 3.5 km.

✅ **Correct**:
```json
{
  "workout_type": "tempo",
  "distance_km": 8.5,  // Total session distance
  "warmup_km": 2.0,
  "cooldown_km": 1.5
}
```
Work km = 8.5 - 2.0 - 1.5 = 5.0 km

---

### Mistake 2: Forgetting WU/CD When Computing Feasibility

❌ **Wrong thinking**: "8km session, need 15min tempo at 5:00/km = 3km work, leaving 5km for WU/CD — plenty of room!"
Reality: Need 2.5 km WU + 1.5 km CD = 4.0 km → only 8 - 4 = 4km available for work+buffer.

✅ **Correct approach**: Always account for WU/CD first:
- 8 km total - 2.5 km WU - 1.5 km CD = 4.0 km remaining
- 15min @ 5:00/km = 3.0 km work
- Buffer: 1.0 km (for transitions)
- Feasible ✓

---

### Mistake 3: Applying Daniels % to Total Distance

❌ **Wrong**: 50 km/week, tempo session `distance_km: 10.0`, check 10.0 / 50 = 20% → violation!
**Issue**: This applies the limit to total distance (including WU/CD), not work.

✅ **Correct**: Work km = 10.0 - 2.5 - 1.5 = 6.0 km. Check 6.0 / 50 = 12% → slightly over 10%, acceptable in build/peak phase.

---

### Mistake 4: Setting `warmup_km: 0` for Quality Sessions

❌ **Wrong**:
```json
{
  "workout_type": "intervals",
  "distance_km": 10.0,
  "warmup_km": 0.0,  // No warm-up!
  "cooldown_km": 1.5
}
```
**Issue**: Jumping into I-pace work without warm-up significantly increases injury risk.

✅ **Correct**: Always include 2.0-3.0 km WU for intervals, 1.5-2.5 km for tempo.

---

**End of Reference**

