# Example: Multi-Sport Conflict and Resolution

## Scenario

**Athlete**: Sam, 29F, training for half marathon (10 weeks out)
**Priority**: EQUAL (running + climbing)
**Week**: Week 6 of 12
**Issue**: Climbing comp Friday conflicted with Saturday long run

---

## Weekly Plan

**Running** (planned):
- Tuesday: 8 km easy
- Thursday: 12 km tempo @ LT pace
- Saturday: 18 km long run @ easy pace
- Sunday: Rest

**Climbing** (planned):
- Wednesday: 90-min bouldering
- Friday: 120-min lead climbing (moderate)

**Note**: Climbing competition added last-minute on Friday (not in original plan).

**Total planned**: 38 km running, 2 climbing sessions

---

## What Actually Happened

### Activities Completed

**Tuesday**: 8 km easy
- Pace: 6:52/km
- HR avg: 148 bpm
- RPE: 4
- Notes: "Felt great, good start to week"

**Wednesday**: 90-min bouldering
- Intensity: Moderate-hard
- Load: 210 AU systemic, 26 AU lower-body
- Notes: "Normal Wednesday session"

**Thursday**: 12 km tempo
- Pace: 5:38/km (prescribed: 5:30-5:45/km)
- HR avg: 172 bpm
- RPE: 8
- Notes: "Hit target pace, felt strong"

**Friday**: Climbing competition (added unplanned)
- Duration: 180 min (3 hours)
- Intensity: Hard
- Load: 600 AU systemic, 80 AU lower-body
- Notes: "Comp was intense, really pushed hard, felt exhausted after"

**Saturday**: 18 km long run
- Pace: 7:15/km (prescribed: 6:45-7:00/km)
- HR avg: 161 bpm (high for easy)
- RPE: 6-7 (should be 4)
- Notes: "Felt sluggish throughout, legs were okay but felt cardio fatigue, struggled more than usual"

**Sunday**: Rest (as planned)

**Total**: 38 km completed, 3 climbing sessions (1 unplanned comp)

---

## Analysis: Step by Step

### Step 1: Weekly Summary (`sce week`)

```json
{
  "planned_workouts": 5,
  "completed_activities": 5,
  "extra_activities": 1,
  "completion_rate": 100,
  "planned_volume_km": 38,
  "actual_volume_km": 38,
  "current_metrics": {
    "ctl": 46,
    "atl": 168,
    "tsb": -22,
    "acwr": 1.38,
    "readiness": 48
  }
}
```

**Initial observations**:
- ✅ Volume adherence (38 km)
- ⚠️ ACWR spiked to 1.38 (caution zone)
- ⚠️ TSB dropped to -22 (very productive/borderline overreached)
- ⚠️ Readiness at 48 (low)

### Step 2: Multi-Sport Load Breakdown (`sce analysis load`)

```json
{
  "systemic_load_by_sport": {
    "running": 880,
    "running_pct": 58,
    "climbing": 640,
    "climbing_pct": 42
  },
  "lower_body_load_by_sport": {
    "running": 880,
    "running_pct": 89,
    "climbing": 106,
    "climbing_pct": 11
  },
  "total_systemic": 1520,
  "total_lower_body": 986,
  "priority_adherence": "good",
  "fatigue_flags": [
    "Friday climbing comp (600 AU systemic) likely impacted Saturday long run quality"
  ]
}
```

**Key insight**: Friday comp added 320 AU systemic load beyond planned 280 AU → +40 AU unexpected load.

### Step 3: Analyze Saturday Long Run

**Planned expectation**:
- Pace: 6:45-7:00/km
- RPE: 4 (easy, conversational)
- HR: ~150 bpm

**Actual performance**:
- Pace: 7:15/km (30 sec/km slower)
- RPE: 6-7 (moderate-hard, not easy)
- HR: 161 bpm (11 bpm higher than expected)

**Athlete notes**: "Felt sluggish throughout, legs were okay but felt cardio fatigue"

**Diagnosis**: Systemic fatigue from Friday comp carried over.

### Step 4: Compare Lower-Body vs Systemic Load

**Friday climbing comp**:
- Systemic load: 600 AU (very high)
- Lower-body load: 80 AU (low)

**Impact on Saturday run**:
- Lower-body: Legs physically fresh (climbing doesn't stress legs much)
- Systemic: Cardiovascular system fatigued
- Result: Athlete's legs felt "okay" but cardiovascular system struggled

**This explains the RPE disconnect**: Legs not sore, but overall effort felt harder due to systemic fatigue.

### Step 5: Check ACWR Spike

**Week-over-week**:
- Previous week: 1100 AU total → ACWR 1.18
- This week: 1520 AU total → ACWR 1.38
- Change: +420 AU (+38%)

**Cause**: Friday comp added 320 AU unplanned systemic load.

---

## Step 6: Synthesis and Communication to Athlete

### Weekly Review: Week 6 (Feb 3-9)

Good week overall, Sam! You completed all 38 km as planned and added a climbing comp Friday. Let's talk about the Friday comp's impact on your Saturday long run and how to handle this better next time.

**Adherence**:
- ✅ Completed all planned running (38 km)
- ✅ Hit your tempo run Thursday (great effort)
- ✅ Added climbing comp Friday (3-hour competition)

**Multi-Sport Load**:
- Running: 880 AU systemic (58% of load)
- Climbing: 640 AU systemic (42% of load)
  - **Note**: Friday comp alone was 600 AU (intense!)
- Total: 1520 AU (38% increase from last week)

**What Happened on Saturday**:
Your long run felt harder than expected (RPE 6-7 instead of 4). Here's why:

Friday's climbing comp generated **600 AU systemic load** (very high). Even though your legs weren't sore (climbing doesn't stress legs much), your cardiovascular system was fatigued. This is called **systemic fatigue** - whole-body tiredness that affects endurance efforts.

Evidence from your Saturday run:
- Pace: 7:15/km (30 sec/km slower than usual 6:45/km)
- Heart rate: 161 bpm (higher than normal for easy pace)
- Your note: "Legs were okay but felt cardio fatigue"

**This is textbook systemic fatigue carryover.** Your legs were physically fresh, but your cardio system needed more recovery.

**Metrics**:
- CTL: 44 → 46 (+2, good progression)
- ACWR: 1.18 → 1.38 (+0.20, **jumped into caution zone**)
- TSB: -15 → -22 (-7, deeper into productive zone)
- Readiness: 68 → 48 (-20, significant drop)

**Interpretation**: The Friday comp spiked your load unexpectedly, pushing ACWR to 1.38 (caution zone = elevated injury risk). Combined with TSB at -22, you're in deep productive training but bordering on overreach.

**For Next Time: Handling Climbing Comps**

When you have a climbing comp followed by a long run, you have three options:

**Option 1: Move long run to Sunday** (Recommended)
- Gives you 48 hours recovery from Friday comp
- Saturday becomes rest/easy day
- Sunday long run will feel much better with systemic recovery

**Option 2: Keep Saturday long run but adjust expectations**
- Run at Saturday's actual pace (7:15/km) and accept RPE 6 instead of 4
- Don't try to hit normal easy pace - it will feel harder
- Total distance might need reduction (15 km instead of 18 km)

**Option 3: Skip/replace long run**
- If comp is priority and running is flexible that week
- Replace with 2 easy runs (Sun/Mon) totaling same volume

**Which option sounds best for your schedule and priorities?**

**Next Week Plan**:
1. **Recovery focus**: Let ACWR normalize
2. **Volume**: Reduce to 35 km (pull back from 38 km)
3. **Climbing**: Back to 2 normal sessions (no comps scheduled)
4. **Easy runs**: Keep truly easy (RPE 3-4) for full recovery
5. **Monitor**: Check readiness mid-week - if still low (<50), adjust quality session

**Focus for next week**: Recovery. Let your body absorb this week's big load spike.

**Overall**: You handled a tough week well - the long run was slower, but you completed it and stayed safe. The climbing comp was a big load spike that your body is telling us about (ACWR, readiness). Next week we'll dial back volume to stabilize metrics, then resume progression. This is smart training - push, recover, adapt.

---

## Step 7: Capture Pattern as Memory

Since this is the first occurrence, capture as insight for future reference:

```bash
sce memory add --type INSIGHT \
  --content "Climbing comps (3+ hours, high intensity) generate ~600 AU systemic load and impact next-day long runs due to cardiovascular fatigue, even though legs feel okay" \
  --tags "sport:climbing,conflict:schedule,impact:long-run,fatigue:systemic" \
  --confidence medium
```

**If this pattern recurs 2+ more times**, upgrade confidence to HIGH and adjust future planning proactively.

---

## Follow-Up Actions

### Immediate (Week 7 Planning)

1. **Reduce volume to 35 km**:
   ```bash
   sce plan update-week --week 7 --volume 35
   ```

2. **Monitor readiness mid-week**:
   ```bash
   # Wednesday check
   sce status
   # If readiness <50, adjust Friday quality session to easy
   ```

3. **Confirm climbing schedule**:
   Ask: "Any comps or hard climbing sessions planned for Week 7?"
   Adjust running schedule proactively if needed.

### Medium-Term (Future Comps)

4. **Update conflict policy if athlete prefers consistent approach**:
   If athlete consistently chooses Option 1 (move long run to Sunday), suggest:
   ```bash
   sce profile set --conflict-policy primary_sport_wins
   ```
   This will auto-adjust running when climbing comps conflict.

5. **Proactive planning**:
   When athlete mentions upcoming comp, ask:
   ```
   "Climbing comp on Friday Week X - want to move your long run to Sunday that week, or adjust differently?"
   ```

---

## Key Coaching Elements Demonstrated

1. **Data-driven diagnosis**: Used systemic vs lower-body load to explain why athlete felt sluggish
2. **Athlete's experience validated**: "Legs were okay but felt cardio fatigue" - confirmed by data
3. **Clear cause-effect**: Friday 600 AU → Saturday struggle
4. **Provided options**: 3 concrete approaches for future comps
5. **Respected priorities**: Asked athlete to choose based on their schedule/preferences
6. **Adjusted next week proactively**: Reduced volume to let ACWR normalize
7. **Pattern capture**: Stored insight for future coaching decisions

**Why this works**:
- Athlete understands *why* the run felt hard (not lack of fitness)
- Athlete has tools to handle this conflict next time
- Coach demonstrated understanding of multi-sport trade-offs
- Relationship strengthened through problem-solving (not blame)
