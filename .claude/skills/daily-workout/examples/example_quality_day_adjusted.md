# Example: Quality Day Adjusted (ACWR Elevated)

## Scenario

**Athlete**: Jordan, training for 10K (8 weeks out)
**Day**: Tuesday (week 6 of 12-week plan)
**Scheduled workout**: Intervals - 6x1000m at 4:15/km with 400m jog recovery
**Context**: Hard climbing session Monday (340 AU systemic, 34 AU lower-body), returned from 3-day conference last week (lower training volume)

---

## Complete Coaching Interaction

### Step 1: Athlete Initiates

**Athlete**: "What should I do today?"

### Step 2: Coach Checks Memory and Recent Notes

**Coach runs**:
```bash
sce memory search --query "climbing"
# Returns: "Prefers to train through moderate fatigue if legs feel good"

sce activity list --since 3d --has-notes
# Returns:
# - Monday climbing: "Hard session, crushed it! Upper body pumped."
# - Saturday easy run: "Felt sluggish after travel"
# - Friday: Travel day (no activity)
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
    "type": "intervals",
    "description": "6x1000m at 4:15/km with 400m jog recovery",
    "distance_km": 10,
    "duration_minutes": 52,
    "intensity": "hard (RPE 8-9)"
  },
  "current_metrics": {
    "ctl": { "value": 48, "interpretation": "competitive fitness level" },
    "tsb": { "value": -14, "zone": "productive training zone" },
    "acwr": { "value": 1.37, "risk_level": "slightly elevated - caution zone" },
    "readiness": { "value": 58, "level": "moderate" }
  },
  "adaptation_triggers": [
    {
      "type": "acwr_elevated",
      "severity": "MODERATE",
      "details": {
        "current_acwr": 1.37,
        "threshold": 1.30,
        "spike_cause": "Conference travel disrupted training last week, returning volume this week"
      }
    }
  ],
  "rationale": "Interval session develops VO2max and speed endurance"
}
```

### Step 4: Coach Assesses State

**Metrics review**:
- CTL: 48 (competitive fitness)
- TSB: -14 (productive zone, okay for quality)
- ACWR: 1.37 ⚠️ (elevated, caution zone)
- Readiness: 58 (moderate)
- **Trigger**: `acwr_elevated` (1.37 > 1.30)

**Contributing factors**:
- Travel disrupted training last week (lower volume)
- Returning to normal volume this week (acute load spike)
- Hard climbing Monday (340 AU systemic load)

**Recent notes**: Monday climbing "crushed it", Saturday run "felt sluggish after travel"

**Memory**: "Prefers to train through moderate fatigue if legs feel good"

**Decision**: ACWR elevated + moderate readiness → Present options with trade-offs

### Step 5: Coach Presents Options (AskUserQuestion)

**Coach**:
```
Your ACWR is **1.37 (slightly elevated - caution zone)** and readiness is **58 (moderate)**. You have intervals scheduled today.

Here's what's contributing to the elevated ACWR:
- Conference travel last week disrupted training (lower volume)
- This week you're returning to normal volume (acute load spike)
- You had a hard climbing session yesterday (340 AU systemic load)

I see you noted "crushed it" for yesterday's climbing - great session! But that adds to this week's load.

**What would you prefer?**

[Uses AskUserQuestion with 4 options]
```

**Options presented**:

1. **Easy 6 km run (safest)**
   - Maintains aerobic base without additional stress
   - ACWR stays manageable (~1.35 by tomorrow)
   - Lower injury risk (~8-10%)
   - **Pro**: Safest option given elevated ACWR
   - **Con**: Delays interval work

2. **Tempo 5 km at threshold (compromise)**
   - Still gets quality stimulus, but lower intensity than intervals
   - Moderate injury risk (~12-15%)
   - **Pro**: Quality work without max effort
   - **Con**: Not as specific to 10K goal as intervals

3. **Shorten intervals to 4x1000m (moderate risk)**
   - Still gets VO2max stimulus (67% volume reduction)
   - Moderate injury risk (~15-18%)
   - **Pro**: Specific to goal, manageable volume
   - **Con**: Still adds significant load with elevated ACWR

4. **Proceed with intervals as planned (highest risk)**
   - Full 6x1000m at 4:15/km
   - Higher injury risk (~18-22%)
   - **Pro**: Stays on plan, develops speed
   - **Con**: Injury risk with ACWR 1.37

**Coach recommendation**:
```
I'm leaning toward **option 2 or 3**.

- Option 2 (tempo) gives you quality work at lower risk
- Option 3 (shortened intervals) keeps specificity but reduces volume

Your memory suggests you prefer training through moderate fatigue "if legs feel good." How do your legs feel after yesterday's climbing?
```

### Step 6: Athlete Responds

**Athlete**: "Legs actually feel decent. Upper body is sore, but legs are fine. I'd like to do option 3 - shorten the intervals."

### Step 7: Coach Confirms and Explains Rationale

**Coach**:
```
Good call. Here's why this makes sense:

**Why shortened intervals work**:
- ACWR of 1.37 means your acute load is 37% higher than your chronic baseline
- Research shows ACWR > 1.5 increases injury risk 2-4x - you're at the edge
- Shortened intervals (4x1000m) still give VO2max stimulus but reduce total volume by 33%
- Your legs feel decent (you know your body best), so moderate risk is acceptable

**Adjusted workout**: 4x1000m at 4:15/km with 400m jog recovery

**Execution tips**:
- Warm up 15 minutes easy before starting
- Hit target pace (4:15/km ± 5 seconds)
- Monitor how you feel - if rep 3 feels way harder than rep 1-2, stop there
- Any sharp or unusual pain → stop immediately

**What to watch**:
- Your climbing yesterday (340 AU) contributes to systemic load - monitor overall fatigue
- If intervals feel exceptionally hard (RPE >9), you're confirming the ACWR spike

You'll get great stimulus from 4 reps. Better to nail 4 than struggle through 6 with elevated injury risk.

Sound good?
```

**Athlete**: "Perfect, thanks!"

### Step 8: Post-Workout Follow-Up

**Later that day...**

**Athlete**: "Done! 4x1000m - paces were 4:12, 4:14, 4:16, 4:18. Felt tough but manageable."

**Coach**:
```
Nice execution! Your paces were right on target (4:15/km ± 5 sec range).

**Observations**:
- Progressive slowdown (4:12 → 4:18) suggests you were working at true VO2max effort
- "Felt tough but manageable" = RPE 8-9, exactly right for intervals
- You executed smart adjustment (4 reps instead of 6) and avoided injury risk

**What this tells me**:
- ACWR 1.37 was indeed impacting performance (felt tougher than usual)
- Shortened volume was the right call - 6 reps would have pushed you into red zone
- Your VDOT is solid (hitting 4:15/km at VO2max confirms VDOT ~51-52)

**Next steps**:
- Tomorrow: Easy 6 km recovery
- Thursday: Rest or easy swim/cycle
- Saturday: Long run 14 km (by then ACWR should drop to ~1.25)

Let your ACWR normalize this week. Great decision-making today. 🎯
```

---

## Key Coaching Elements Demonstrated

1. **Trigger detection**: ACWR 1.37 (elevated) triggered adaptation logic
2. **Root cause analysis**: Identified travel disruption + climbing load as contributors
3. **Memory integration**: Referenced athlete preference ("train through moderate fatigue")
4. **Subjective assessment**: Asked how legs feel to inform decision
5. **Trade-off presentation**: 4 distinct options with pros/cons
6. **Athlete agency**: Let athlete choose, respected decision
7. **Rationale explanation**: Explained why shortened intervals make sense
8. **Execution guardrails**: Provided monitoring cues and stop signals
9. **Post-workout analysis**: Validated execution, explained what slowdown indicates

---

## Workflow Summary

```
1. Check memory → Found: "prefers to train through moderate fatigue"
2. Check recent notes → Climbing Monday "crushed it", Saturday "sluggish"
3. Get scheduled workout → Intervals 6x1000m
4. Check metrics → ACWR 1.37 (elevated), readiness 58 (moderate)
5. Detect trigger → acwr_elevated (severity: MODERATE)
6. Assess root cause → Travel disruption + climbing load
7. Present 4 options → Easy, tempo, shortened intervals, full intervals
8. Athlete chooses option 3 → Shortened intervals
9. Explain rationale → Why 4 reps works given ACWR
10. Provide execution tips → Monitor feel, stop signals
11. Post-workout validation → Confirm execution, explain performance
```

---

## Why This Worked

**Balance of factors**:
- ⚠️ ACWR elevated (1.37) BUT not danger zone (<1.5)
- ✅ Athlete legs feel decent (subjective)
- ✅ Athlete prefers training through moderate fatigue (memory)
- ✅ Shortened workout reduces risk while preserving stimulus

**Coaching approach**:
- Detected trigger, didn't ignore
- Presented options, explained trade-offs
- Respected athlete preference and subjective feel
- Provided compromise (shortened intervals)
- Monitored execution with guardrails

This demonstrates **adaptive coaching** - not binary (proceed vs. rest), but finding middle ground that balances risk and stimulus.
