# Multi-Sport Load Balance Guidelines

## Overview

Multi-sport athletes require **two-channel load tracking** to understand how different activities interact. Running, climbing, cycling, swimming, and other sports contribute to:

1. **Systemic load** (cardio + whole-body fatigue)
2. **Lower-body load** (leg strain + impact stress)

Understanding this dual-channel model is critical for intelligent load management and injury prevention.

---

## Two-Channel Load Model

### Channel 1: Systemic Load
**What it measures**: Cardiovascular stress and whole-body fatigue

**Feeds into**: CTL, ATL, TSB, ACWR (primary metrics)

**Examples**:
- Hard climbing session: High systemic load (cardio, upper-body, core fatigue)
- Cycling: Moderate systemic load (cardio effort)
- Swimming: Moderate systemic load (cardio, upper-body)

**Key insight**: Systemic load accumulates regardless of muscle groups used. A hard climbing session fatigues your cardiovascular system even though it doesn't stress your legs.

### Channel 2: Lower-Body Load
**What it measures**: Leg strain and impact stress

**Gates**: Quality runs, long runs, high-intensity running efforts

**Examples**:
- Running: High lower-body load (impact, leg muscle stress)
- Cycling: Low-moderate lower-body load (concentric only, no impact)
- Climbing: Very low lower-body load (upper-body dominant)

**Key insight**: Lower-body load determines whether you can execute quality running workouts. High climbing systemic load doesn't prevent easy running the next day, but high cycling lower-body load might.

---

## Sport Multipliers

Each sport has different systemic and lower-body multipliers relative to running (baseline 1.00/1.00).

| Sport | Systemic Multiplier | Lower-Body Multiplier | Notes |
|-------|--------------------|-----------------------|-------|
| **Running** | 1.00 | 1.00 | Baseline (full impact) |
| **Cycling** | 0.85 | 0.35 | Lower systemic than running, low impact |
| **Climbing** | 0.60 | 0.10 | Upper-body dominant, minimal leg strain |
| **Swimming** | 0.70 | 0.10 | Low impact, upper-body focus |
| **Hiking** | 0.75 | 0.70 | Moderate systemic, leg strain without impact |
| **Strength Training** | 0.50 | 0.40 | Depends on focus (legs vs upper-body) |
| **Yoga** | 0.30 | 0.15 | Low intensity, flexibility focus |

**Note**: This table shows common sports. For complete sport multipliers methodology, see SKILL.md Additional Resources section.

---

## Load Interpretation Zones

### Running Priority: PRIMARY (Race Goal)

**Target**: Running should constitute 60-70% of systemic load

- **>70%**: Excellent - running-focused training
- **60-70%**: Good - balanced with primary focus on running
- **50-60%**: Fair - borderline, other sports competing for energy
- **<50%**: Concerning - running not prioritized, may impact race goal

### Running Priority: EQUAL

**Target**: Running ~40-50% of systemic load

- **50-60%**: Good - balanced multi-sport
- **40-50%**: Excellent - equal priority maintained
- **<40%**: Running under-emphasized for equal priority
- **>60%**: Other sports under-emphasized

### Running Priority: SECONDARY (Fitness Support)

**Target**: Running ~25-35% of systemic load

- **<25%**: Running appropriately de-emphasized
- **25-35%**: Good balance for secondary focus
- **>35%**: Running taking too much energy from primary sport

---

## Example Multi-Sport Breakdown

### Scenario: Equal Priority (Running + Climbing)

**Week's activities**:
- 3 runs: 6 km easy, 10 km tempo, 14 km long (30 km total)
- 2 climbing sessions: 90-min bouldering, 120-min lead (moderate-hard intensity)
- 1 yoga session: 60 min gentle flow

**Load calculation** (from `sce analysis load`):
```json
{
  "systemic_load_by_sport": {
    "running": 850 AU (62%),
    "climbing": 420 AU (31%),
    "yoga": 90 AU (7%)
  },
  "lower_body_load_by_sport": {
    "running": 850 AU (85%),
    "climbing": 52 AU (5%),
    "cycling": 0 AU (0%),
    "yoga": 13 AU (1%)
  },
  "total_systemic": 1360 AU,
  "total_lower_body": 915 AU,
  "priority_adherence": "fair"
}
```

**Interpretation**:
- **Systemic load**: Running at 62% is slightly high for EQUAL priority (target 40-50%)
  - This week leaned more toward running focus
  - Climbing at 31% is reasonable but could be higher for equal balance
- **Lower-body load**: Running dominates (85%), which is expected
  - Climbing contributes minimal leg strain (5%)
  - Allows easy running day after climbing without lower-body fatigue concern
- **Priority adherence**: Fair (not excellent)
  - To better balance, either reduce running volume slightly or add climbing session

**Coaching message**:
```
Your running volume (850 AU, 62% of load) was a bit high for EQUAL priority this week - we're leaning toward running-focused. If you want to maintain equal balance with climbing:

Option 1: Reduce running to 25 km next week (keep climbing at 2 sessions)
Option 2: Add a 3rd climbing session next week (keep running at 30 km)

Your lower-body load is well-managed - climbing doesn't interfere with running quality.
```

---

## Multi-Sport Interaction Patterns

### Pattern 1: High Systemic Load, Low Lower-Body Load
**Example**: Hard climbing session (Tuesday: 340 AU systemic, 42 AU lower-body)

**Effect on running**:
- ✅ Can run easy Wednesday (systemic load manageable for low-intensity)
- ⚠️ Quality/tempo Wednesday may feel harder (systemic fatigue reduces capacity)
- ❌ Intervals Wednesday likely compromised (need full systemic recovery)

**Recommendation**: Easy run day after hard climbing, quality 48+ hours later

### Pattern 2: Moderate Systemic, Moderate Lower-Body Load
**Example**: Long cycling ride (Saturday: 400 AU systemic, 140 AU lower-body)

**Effect on running**:
- ⚠️ Sunday long run may feel sluggish (leg fatigue without impact recovery)
- ❌ Sunday quality run likely compromised
- ✅ Monday easy run okay (48 hours recovery)

**Recommendation**: Avoid long/quality run day after cycling, easy run okay

### Pattern 3: Low Systemic, Very Low Lower-Body Load
**Example**: Yoga session (Friday: 90 AU systemic, 13 AU lower-body)

**Effect on running**:
- ✅ No interference with any running session
- ✅ May enhance recovery (flexibility, stress relief)

**Recommendation**: No running restrictions, can run quality same day or next

---

## Decision Trees

### Q: Climbing comp Friday (600 AU systemic, 80 AU lower-body), Long run scheduled Saturday

**Step 1: Assess systemic vs lower-body impact**
- Systemic: Very high (600 AU)
- Lower-body: Low (80 AU)

**Step 2: Evaluate Saturday long run risk**
- Lower-body: Legs are fresh enough (low climbing leg strain)
- Systemic: Cardiovascular system fatigued
- Predicted feeling: RPE will be 1-2 points higher than usual

**Step 3: Present options to athlete (based on conflict policy)**

If policy is **ASK_EACH_TIME**:
```
Your climbing comp Friday was intense (600 AU systemic). Your Saturday long run is planned, but you'll likely feel the systemic fatigue even though your legs are fine.

Two options:
1. Move long run to Sunday (24-hour recovery, will feel better)
2. Keep Saturday but adjust expectations (same pace will feel RPE 6 instead of 4)

Which do you prefer?
```

If policy is **RUNNING_GOAL_WINS**:
```
Your climbing comp Friday was intense (600 AU systemic). To protect your Saturday long run quality, let's move it to Sunday. This gives you 48 hours to recover from the systemic fatigue.
```

If policy is **PRIMARY_SPORT_WINS**:
```
Great comp Friday! Your long run is scheduled Saturday, but systemic fatigue will make it feel harder. Two options:
1. Move to Sunday (better quality)
2. Run Saturday but treat as "maintenance" (lower quality is okay)

Since climbing is your primary sport, protecting Friday comp performance matters more than perfect long run execution. Which option works better?
```

**Step 4: Capture pattern if recurring**
If this conflict happens 3+ times, store as memory:
```bash
sce memory add --type INSIGHT \
  --content "Climbing comps on Friday consistently impact Saturday long run quality due to systemic fatigue" \
  --tags "sport:climbing,conflict:schedule,impact:long-run" \
  --confidence high
```

### Q: Athlete wants to add cycling but maintain running volume

**Step 1: Check current load distribution**
```bash
sce analysis load --activities [FILE] --days 7 --priority [PRIORITY]
```

**Step 2: Model the addition**
- Current running: 850 AU systemic (70% of load)
- Proposed cycling: 2 rides @ 60 min each = ~240 AU systemic
- New total: 1090 AU systemic
- New running %: 850 / 1090 = 78% (still running-dominant)

**Step 3: Assess lower-body impact**
- Cycling lower-body: ~85 AU
- Total lower-body: 850 (running) + 85 (cycling) = 935 AU
- Increase: +10% lower-body load

**Step 4: Make recommendation**
```
Adding 2 cycling sessions (60 min each) will:
- Increase systemic load by 22% (850 → 1090 AU)
- Increase lower-body load by 10% (850 → 935 AU)
- Push ACWR from 1.15 → ~1.35 (caution zone)

Recommendation: Add cycling gradually
- Week 1: 1 ride (30 min easy) - monitor ACWR
- Week 2: If ACWR <1.3, increase to 45 min
- Week 3: Add 2nd ride if ACWR stable
- Keep running volume flat during cycling ramp-up

This staged approach lets your body adapt to the new load pattern safely.
```

---

## Common Scenarios

### Scenario 1: Volume increased across all sports simultaneously

**Red flag**: ACWR spike

**Example**:
- Running: 30 km → 40 km (+33%)
- Climbing: 2 sessions → 3 sessions (+50%)
- Total load: 900 AU → 1350 AU (+50%)
- ACWR: 1.1 → 1.52 (danger zone)

**Response**:
```
Your total load jumped 50% this week (900 → 1350 AU), driven by increases in both running and climbing. This spiked ACWR to 1.52 (danger zone - 2-4x injury risk).

For next week, we need to reduce total load:
- Running: Drop to 35 km (10% reduction)
- Climbing: Revert to 2 sessions
- Target: ~1000 AU total (let ACWR normalize)

Once ACWR drops below 1.3, we can resume progression - but one sport at a time.
```

### Scenario 2: Consistent multi-sport balance maintained

**Green flag**: Stable metrics, good adherence

**Example**:
- Running: 40 km/week for 4 weeks (850 AU)
- Climbing: 2 sessions/week for 4 weeks (350 AU)
- Total: ~1200 AU systemic (consistent)
- ACWR: 1.05 → 1.08 → 1.10 → 1.09 (stable)

**Response**:
```
Excellent load consistency! You've maintained 40 km running + 2 climbing sessions for 4 weeks straight. Your ACWR is stable around 1.08 (safe zone), and metrics show steady adaptation.

This is exactly what we want - sustainable training load that your body can adapt to. You're ready to progress volume if you want:
- Option 1: Increase running to 45 km (maintain 2 climbing)
- Option 2: Add 3rd climbing session (maintain 40 km running)

Either increase is safe given your stable ACWR trend.
```

---

## Additional Resources

- **Multi-sport case studies**: [docs/coaching/scenarios.md](../../../docs/coaching/scenarios.md)
- **Conflict policy settings**: See profile setup in first-session skill

**Note**: For complete sport multipliers table and methodology, see SKILL.md Additional Resources section.
