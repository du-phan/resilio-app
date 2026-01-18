# Example: Quality Day Ready (No Triggers)

## Scenario

**Athlete**: Alex, training for half marathon (10 weeks out)
**Day**: Thursday (week 8 of 16-week plan)
**Scheduled workout**: Tempo run - 8 km at 5:10-5:30/km (threshold pace)
**Context**: Athlete completed easy runs Monday/Tuesday, rest day Wednesday

---

## Complete Coaching Interaction

### Step 1: Athlete Initiates

**Athlete**: "What's my workout today?"

### Step 2: Coach Checks Memory and Recent Notes

**Coach runs**:
```bash
sce memory list --type TRAINING_RESPONSE
# Returns: "Reports feeling strong on Thursdays after Wednesday rest"

sce activity list --since 3d --has-notes
# Returns:
# - Tuesday easy run: "Felt good, legs fresh"
# - Wednesday: Rest day (no activity)
```

### Step 3: Coach Gets Scheduled Workout

**Coach runs**:
```bash
sce today
```

**Response**:
```json
{
  "workout": {
    "type": "tempo",
    "distance_km": 8,
    "pace_range": "5:10-5:30/km",
    "duration_minutes": 42,
    "description": "Threshold run at comfortably hard pace (RPE 7-8)"
  },
  "current_metrics": {
    "ctl": { "value": 46, "interpretation": "solid recreational fitness level" },
    "tsb": { "value": -6, "zone": "fresh, good for quality work" },
    "acwr": { "value": 1.12, "risk_level": "safe range" },
    "readiness": { "value": 74, "level": "good" }
  },
  "adaptation_triggers": [],
  "rationale": "Tempo run builds lactate threshold - the pace you can sustain for 20-60 minutes at comfortably hard effort"
}
```

### Step 4: Coach Assesses State

**Metrics review**:
- CTL: 46 (solid fitness)
- TSB: -6 (fresh, ideal for quality)
- ACWR: 1.12 (safe range)
- Readiness: 74 (good)
- **Triggers**: None detected ✅

**Recent notes**: Tuesday noted "Felt good, legs fresh"

**Memory**: "Reports feeling strong on Thursdays after Wednesday rest" ✅

**Decision**: All systems go - proceed with planned tempo run

### Step 5: Coach Presents Recommendation

**Coach**:
```
Your tempo run is scheduled for today: **8 km at 5:10-5:30/km** (threshold pace).

**Current state**:
- CTL: 46 (solid recreational fitness)
- TSB: -6 (fresh, good for quality work)
- ACWR: 1.12 (safe range)
- Readiness: 74 (good)

This workout builds your **lactate threshold** - the pace you can hold "comfortably hard" for 20-60 minutes. Your metrics look excellent - proceed as planned.

I see you noted "felt good, legs fresh" after Tuesday's easy run, and you rested yesterday. Your body is ready for quality work.

**Tips for tempo run**:
- **Warm up**: 10 minutes easy before starting threshold pace
- **Effort**: RPE 7-8 (hard but controlled, not maximal)
- **Breathing**: Rhythmic but labored - you can speak 3-4 words at a time
- **Pace**: Start at slower end (5:25-5:30/km), settle in, don't sprint
- **Cool down**: 10 minutes easy after

You should feel strong today. Go get it!
```

### Step 6: Athlete Confirms

**Athlete**: "Sounds good, thanks!"

### Step 7: Post-Workout (Optional)

**Later that day...**

**Athlete**: "Done! 8 km at 5:22 avg pace. Felt strong."

**Coach**:
```
Nice work! 5:22/km is right in your target zone (5:10-5:30/km). That's a solid threshold effort.

A few observations:
- You hit the middle of your pace range - perfect execution
- "Felt strong" is exactly what we want for tempo runs (RPE 7-8)
- This confirms your VDOT is progressing (originally 48, trending toward 49-50)

Your next quality session is Saturday's long run (16 km). Friday will be easy recovery.

Enjoy the endorphins! 🎯
```

---

## Key Coaching Elements Demonstrated

1. **Proactive memory retrieval**: Checked training response pattern ("strong on Thursdays")
2. **Recent activity notes**: Referenced Tuesday's wellness ("felt good, legs fresh")
3. **Metrics alignment**: All metrics in healthy ranges, no triggers
4. **Context provision**: Explained what tempo run does (lactate threshold)
5. **Practical tips**: Warm-up, effort level, pacing strategy, cool down
6. **Positive reinforcement**: Acknowledged athlete's readiness based on data and notes
7. **Post-workout validation**: Confirmed execution was solid, tied to VDOT progression

---

## Workflow Summary

```
1. Check memory → Found: "strong on Thursdays after Wednesday rest"
2. Check recent notes → Found: "felt good, legs fresh" (Tuesday)
3. Get scheduled workout → Tempo 8 km
4. Check metrics → All good (CTL 46, TSB -6, ACWR 1.12, readiness 74)
5. Detect triggers → None
6. Proceed with planned workout → Present with tips and context
7. Post-workout feedback → Validate execution, tie to progression
```

---

## Why This Worked

**Alignment of factors**:
- ✅ Rest day yesterday (TSB -6, fresh)
- ✅ Good readiness (74)
- ✅ Safe ACWR (1.12)
- ✅ Athlete subjective feel positive ("felt good")
- ✅ Historical pattern positive ("strong on Thursdays")

**Coaching approach**:
- Trust the plan when metrics are green
- Provide context (why tempo, what it does)
- Give practical tips for execution
- Positive reinforcement based on data

This is the **ideal scenario** - data, subjective feel, and plan all aligned. Coach's role is to confirm readiness and provide execution tips.
