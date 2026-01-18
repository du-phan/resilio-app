# Example: Rest Day Triggered (Very Low Readiness + High ACWR)

## Scenario

**Athlete**: Sam, training for marathon (12 weeks out)
**Day**: Wednesday (week 10 of 18-week plan)
**Scheduled workout**: Easy run - 10 km at 6:00-6:20/km
**Context**: Long run Saturday (28 km), tempo Tuesday (12 km), intervals Sunday, poor sleep noted Monday/Tuesday

---

## Complete Coaching Interaction

### Step 1: Athlete Initiates

**Athlete**: "What's today's workout? Honestly feeling pretty tired."

### Step 2: Coach Checks Memory and Recent Notes

**Coach runs**:
```bash
sce memory search --query "readiness recovery fatigue"
# Returns: "Low readiness (<40) persists 3+ days after hard training weeks"

sce activity list --since 5d --has-notes
# Returns:
# - Tuesday tempo: "Tough, legs felt heavy"
# - Monday easy: "Very tired, poor sleep last night"
# - Sunday intervals: "Solid session, HR a bit high"
# - Saturday long run: "28 km done, felt it in last 5 km"
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
    "type": "easy",
    "distance_km": 10,
    "pace_range": "6:00-6:20/km",
    "duration_minutes": 62,
    "description": "Recovery run at conversational pace (RPE 3-4)"
  },
  "current_metrics": {
    "ctl": { "value": 54, "interpretation": "advanced fitness level" },
    "tsb": { "value": -24, "zone": "approaching overreached" },
    "acwr": { "value": 1.53, "risk_level": "danger zone - high injury risk" },
    "readiness": { "value": 31, "level": "very low" }
  },
  "adaptation_triggers": [
    {
      "type": "readiness_very_low",
      "severity": "HIGH",
      "details": {
        "current_readiness": 31,
        "threshold": 35,
        "contributing_factors": ["poor_sleep", "tsb_approaching_overreached", "consecutive_quality_sessions"]
      }
    },
    {
      "type": "acwr_high_risk",
      "severity": "HIGH",
      "details": {
        "current_acwr": 1.53,
        "threshold": 1.50,
        "spike_cause": "Back-to-back quality sessions (long run Sat, intervals Sun, tempo Tue) without adequate recovery"
      }
    },
    {
      "type": "tsb_overreached",
      "severity": "HIGH",
      "details": {
        "current_tsb": -24,
        "threshold": -25,
        "trend": "declining rapidly"
      }
    }
  },
  "rationale": "Easy run maintains aerobic base during recovery period"
}
```

### Step 4: Coach Assesses State

**Metrics review**:
- CTL: 54 (advanced fitness)
- TSB: -24 ⚠️ (approaching overreached, threshold -25)
- ACWR: 1.53 🚨 (danger zone, >1.5)
- Readiness: 31 🚨 (very low, <35)
- **Triggers**: THREE high-severity triggers 🚨🚨🚨

**Contributing factors**:
- Back-to-back quality sessions (long run Sat → intervals Sun → tempo Tue)
- Poor sleep Monday and Tuesday (noted)
- TSB declining rapidly (-15 → -20 → -24 over 3 days)
- Tuesday tempo noted "tough, legs felt heavy"

**Recent notes show clear distress signals**:
- Saturday: "felt it in last 5 km" (fatigue)
- Monday: "Very tired, poor sleep"
- Tuesday: "Tough, legs felt heavy"

**Memory**: "Low readiness (<40) persists 3+ days after hard training weeks"

**Athlete subjective**: "Honestly feeling pretty tired"

**Decision**: Multiple high-severity triggers + athlete reports fatigue → STRONGLY recommend rest

### Step 5: Coach Presents Recommendation (Clear Red Flags)

**Coach**:
```
I'm glad you mentioned feeling tired - your metrics are showing **three major red flags**:

🚨 **ACWR: 1.53** (danger zone - high injury risk)
🚨 **Readiness: 31** (very low)
🚨 **TSB: -24** (approaching overreached, threshold -25)

**What's happening**:
You've had an intense training block:
- Saturday: 28 km long run
- Sunday: Intervals (no recovery between long run and quality)
- Tuesday: 12 km tempo (legs noted "heavy")
- Poor sleep Monday and Tuesday (you noted this)

Your body is telling you clearly it needs recovery:
- ACWR 1.53 means 2-4x higher injury risk than baseline
- Readiness 31 is very low (scale 0-100)
- TSB -24 means you're on the edge of overreaching

I see you noted "very tired" Monday, "tough, legs felt heavy" Tuesday. This aligns perfectly with your metrics.

**My strong recommendation: Rest day today.**

I know you have an easy run scheduled, but even easy running adds load (~60-80 AU). Your body needs **complete recovery** (0 AU) to avoid injury and overtraining.

**However, if you absolutely want to move**, here's the only option I'd support:

**Option: Very easy 20-minute recovery jog** (with conditions)
- RPE 2-3 (conversation is effortless)
- Walk breaks every 5 minutes
- Stop immediately if anything feels off
- **This is a compromise** - still adds ~25-30 AU load

**My recommendation remains: Full rest day.**

What would you prefer?
```

### Step 6: Athlete Considers Options

**Athlete**: "I hear you. I do feel pretty beaten up. What happens if I rest today?"

### Step 7: Coach Explains Benefits of Rest

**Coach**:
```
Great question. Here's what rest accomplishes:

**Immediate benefits**:
- ACWR drops naturally (from 1.53 → ~1.40 by tomorrow)
- Readiness will climb (31 → likely 40-45 tomorrow)
- TSB improves (-24 → ~-20 tomorrow)
- Reduced injury risk (22% today → ~12-15% tomorrow)

**Biological recovery**:
- Muscle glycogen fully restores (takes 24-48h after hard training)
- Muscle microtrauma heals (from long run + intervals + tempo)
- CNS fatigue reduces (nervous system needs recovery too)
- Sleep debt improves (noted poor sleep Mon/Tue)

**Training impact**:
- **Zero fitness loss** from one rest day (CTL drops 0.5 points max)
- **Better quality** in Friday's workout (you'll have fresher legs)
- **Lower injury risk** for Saturday's next long run

**What happens if you don't rest**:
- ACWR stays elevated (1.53 → 1.48, still danger zone)
- Accumulating fatigue continues (TSB → -27, overreached)
- Higher injury probability (22% today, stays ~20% tomorrow)
- Friday's workout will suffer (tired legs, poor quality)

**Think of it this way**: One rest day now prevents being forced to take 7-14 days off for an injury later.

Your marathon is 12 weeks away. Missing one easy run today has ZERO impact on race day fitness. But getting injured from ignoring red flags would derail your entire plan.

Sound reasonable?
```

### Step 8: Athlete Decides

**Athlete**: "That makes sense. I'll rest today. What should I do instead?"

### Step 9: Coach Provides Rest Day Guidance

**Coach**:
```
Smart decision. Here's how to make today productive:

**Rest day activities** (no cardio load):
- **Stretching or yoga** (20-30 min) - helps muscle recovery
- **Foam rolling** - targets IT band, hamstrings, calves
- **Leisure walk** (not exercise pace) - light movement without training stress
- **Nap** - if you can, catch up on sleep debt

**Nutrition focus**:
- Maintain normal eating (your body needs fuel for recovery)
- Hydrate well (helps glycogen restoration)
- Protein with meals (muscle repair)

**Mental reframing**:
- Rest is training too - it's when adaptation happens
- You're not "falling behind" - you're building resilience
- Recovery now = stronger workouts Friday and Saturday

**Tomorrow (Thursday)**:
- Check metrics: `sce status`
- If readiness >40 and ACWR <1.45: Easy 8 km recovery run
- If still low: Another rest day or very easy 20 min

**Friday**:
- Target: Easy 10 km (if metrics improve)
- This sets you up for Saturday's quality long run

**Saturday**:
- Long run 24 km (reduced from typical 28 km to manage load)
- By then, ACWR should be ~1.30-1.35 (caution zone, acceptable)

I'll check in tomorrow. Your body gave you clear signals - you listened. That's smart training.

Enjoy the rest day!
```

### Step 10: Next Day Check-In

**Thursday...**

**Coach** (proactively):
```
Morning! How are you feeling after yesterday's rest day?

Let me check your metrics:

[Runs: sce status]

Result:
- Readiness: 42 (low, improved from 31)
- ACWR: 1.42 (elevated, down from 1.53)
- TSB: -20 (productive zone, improved from -24)

Good news: Metrics are improving. Readiness up 11 points, ACWR down 0.11, TSB back in productive zone.

How do you feel subjectively? If you feel decent, an easy 6-8 km recovery run is fine today. If you still feel tired, another rest day is totally acceptable.

What's your sense?
```

**Athlete**: "I actually feel a bit better. I'll do an easy 6 km today."

**Coach**:
```
Perfect. Easy 6 km at 6:00-6:20/km (RPE 3-4, conversational). Monitor how you feel - if legs still feel heavy, no shame in cutting it to 4 km or walking.

You're rebuilding capacity after a tough training block. Patience now pays off in better quality workouts later.

Friday: Another easy 8 km if today goes well
Saturday: Long run 24 km (watch ACWR, may adjust)

You made the right call yesterday. 💪
```

---

## Key Coaching Elements Demonstrated

1. **Multiple trigger detection**: Three HIGH-severity triggers (ACWR, readiness, TSB)
2. **Activity note integration**: Referenced poor sleep, heavy legs from recent workouts
3. **Athlete subjective alignment**: "Feeling tired" matched metrics perfectly
4. **Memory pattern recognition**: "Low readiness persists after hard weeks"
5. **Clear warning communication**: Used red flag emojis, explicit risk numbers
6. **Strong recommendation**: "Rest day" presented as primary recommendation
7. **Compromise option**: Offered very easy jog with conditions (athlete agency)
8. **Rationale explanation**: Detailed benefits of rest vs. consequences of ignoring
9. **Rest day guidance**: Specific non-cardio activities to remain productive
10. **Follow-up check-in**: Proactive next-day assessment to confirm recovery
11. **Progressive return**: Easy volume rebuild (6 km → 8 km → 24 km over 3 days)

---

## Workflow Summary

```
1. Athlete reports fatigue → "honestly feeling pretty tired"
2. Check memory → "Low readiness persists after hard weeks"
3. Check recent notes → Poor sleep, heavy legs, tough workouts
4. Get scheduled workout → Easy 10 km
5. Check metrics → ACWR 1.53, readiness 31, TSB -24 (🚨🚨🚨)
6. Detect triggers → THREE high-severity triggers
7. Strong recommendation → REST DAY (with compromise option if needed)
8. Explain rationale → Benefits of rest vs. consequences
9. Athlete decides rest → Confirms decision
10. Provide rest day guidance → Activities, nutrition, mental reframing
11. Next-day check-in → Metrics improving, suggest easy 6 km
12. Progressive rebuild → 6 km → 8 km → 24 km long run
```

---

## Why This Worked

**Alignment of factors**:
- 🚨 THREE high-severity triggers (ACWR, readiness, TSB)
- 🚨 Recent notes confirm distress (poor sleep, heavy legs)
- 🚨 Athlete subjective matches metrics ("feeling tired")
- 🚨 Memory shows pattern (low readiness after hard weeks)

**Coaching approach**:
- **Clear communication**: Red flags, explicit risk percentages
- **Strong stance**: Rest recommended, not "maybe consider"
- **Athlete agency**: Compromise option offered, but framed as suboptimal
- **Education**: Explained WHY rest matters and consequences of ignoring
- **Support**: Provided rest day activities to remain productive
- **Follow-through**: Checked in next day to confirm recovery trajectory

This demonstrates **protective coaching** - when data, subjective feel, and recent patterns ALL point to overtraining risk, coach intervenes firmly while respecting athlete agency.

---

## What This Prevents

**Without intervention**:
- Day 4: ACWR 1.56, readiness 28, TSB -28 (full overreach)
- Day 5: Injury probability 25-30% (2-4x normal)
- Week 2: Forced rest 7-14 days (injury)
- Marathon goal: At risk due to lost training time

**With intervention**:
- Day 2: Metrics improving (ACWR 1.42, readiness 42, TSB -20)
- Day 3: Easy 6 km successful
- Day 4: Easy 8 km successful
- Day 5: Long run 24 km with manageable risk
- Marathon goal: On track, avoided injury spiral

**One rest day today = Prevented 7-14 days off later**. This is smart coaching.
