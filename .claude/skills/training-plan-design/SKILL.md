---
name: training-plan-design
description: Design personalized training plans for 5K-Marathon races using Pfitzinger periodization, Daniels pace zones, and 80/20 principles. Accounts for multi-sport constraints, CTL-based volume progression, and injury history. Use when athlete requests "design my plan", "create training program", "how should I train for [race]", or after first-session onboarding.
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Training Plan Design

## Overview

This skill designs evidence-based training plans by combining:
- **Pfitzinger periodization** (base → build → peak → taper)
- **Daniels VDOT pace system** (E/M/T/I/R zones)
- **80/20 intensity distribution** (80% easy, 20% hard)
- **Multi-sport load awareness** (respecting climbing/cycling/etc.)
- **CTL-based volume progression** (safe starting points)
- **Guardrails validation** (injury prevention)

**Key principle**: Use computational tools to calculate periodization, volume, and paces; apply coaching judgment to integrate constraints and athlete context.

**Workflow pattern**: Gather context → Design phases → Prescribe workouts → Validate guardrails → Present for review → Save after approval.

---

## Workflow

### Step 1: Gather Athlete Context

Before designing any plan, understand current state, constraints, and preferences.

#### 1a. Get Current State
```bash
sce profile get     # Name, age, max HR, goal, injury history, constraints
sce status          # CTL/ATL/TSB/ACWR (current fitness baseline)
```

**Extract key data**:
- **Current CTL**: Determines safe starting volume (see [VOLUME_PROGRESSION.md](references/VOLUME_PROGRESSION.md))
- **Goal**: Race type (5K, 10K, half, marathon), date, target time (if known)
- **Constraints**: Run days/week, max long run duration, other sport commitments
- **Injury history**: Any limitations to consider (e.g., "left knee sensitive after 18km+")
- **Running priority**: PRIMARY, EQUAL, or SECONDARY (affects volume and structure)
- **Conflict policy**: `ask_each_time`, `primary_sport_wins`, or `running_goal_wins`

#### 1b. Calculate Weeks to Goal
```python
from datetime import datetime, date

goal_date = date.fromisoformat(profile['goal']['date'])
today = date.today()
weeks_available = (goal_date - today).days // 7
```

**Minimum weeks by distance**:
- 5K: 6 weeks (can be shorter for fitness maintenance)
- 10K: 8 weeks
- Half marathon: 12 weeks
- Marathon: 16 weeks

**If insufficient time**: Discuss with athlete - extend goal date or adjust expectations.

#### 1c. Verify Constraints (Natural Conversation)

**CRITICAL**: Constraints shape the entire plan. Verify before designing.

**Questions to ask** (if not already in profile):
1. **Run frequency**: "How many days per week can you realistically run?"
2. **Available days**: "Any days that work better? I see you typically train Tuesdays and weekends."
3. **Session duration**: "What's the longest time you can spend on a long run?" (90-180 min typical)
4. **Other sport commitments**: "Are your climbing days fixed or flexible?"
5. **Preference for long runs**: "Weekend mornings work best?"

**Store constraints** for reference during plan design.

---

### Step 2: Calculate Periodization

Divide training weeks into phases based on goal distance and weeks available.

**Use** [PERIODIZATION.md](references/PERIODIZATION.md) for phase allocation rules.

#### 2a. Allocate Phases

**Standard allocation**:
- Base: 45-50% of weeks
- Build: 30-35% of weeks
- Peak: 10-15% of weeks
- Taper: 8-12% of weeks (typically 2-3 weeks)

**Example (16-week half marathon plan)**:
- Base: 7 weeks (44%)
- Build: 5 weeks (31%)
- Peak: 2 weeks (12%)
- Taper: 2 weeks (12%)

**For marathon**: Extend base (+1-2 weeks), longer taper (3 weeks)
**For 10K**: Shorter base, no separate peak (peak integrated into build)

#### 2b. Place Recovery Weeks
- Every 4th week during **base** and **build** phases
- NOT during peak or taper

**Example (16-week plan)**:
- Base recovery: Week 4, Week 8
- Build recovery: Week 12
- No recovery during peak (Weeks 13-14) or taper (Weeks 15-16)

---

### Step 3: Design Volume Progression

Use CTL to determine safe starting volume and peak volume.

#### 3a. Determine Starting Volume

**Use** [VOLUME_PROGRESSION.md](references/VOLUME_PROGRESSION.md) for CTL-to-volume conversion.

```bash
sce guardrails safe-volume --ctl 44 --goal-type half_marathon
```

**Returns**:
- `recommended_start`: Safe starting volume (e.g., 40 km/week for CTL 44)
- `recommended_peak`: Race-appropriate peak (e.g., 60-65 km for half marathon)
- `progression_strategy`: Weekly increases to reach peak

**Adjustment for multi-sport**:
- If running priority = EQUAL: Reduce peak by 20-30% (compensate with other sports)
- If running priority = SECONDARY: Maintain base only (no peak)

#### 3b. Design Week-by-Week Volume

**Base phase**: +5-10% per week, recovery every 4th
**Build phase**: +0-5% per week (slower due to intensity)
**Peak phase**: Hold volume (no increase)
**Taper phase**: -20-30% per week

**Example progression (16-week half marathon, CTL 44)**:
```
Week 1 (Base): 40 km
Week 2: 44 km (+10%)
Week 3: 48 km (+9%)
Week 4: 34 km (Recovery, 70% of week 3)
Week 5: 52 km (+8% from week 3)
Week 6: 56 km (+8%)
Week 7: 60 km (+7%)
Week 8: 42 km (Recovery, 70% of week 7)
Week 9 (Build): 62 km (+3% from week 7)
Week 10: 64 km (+3%)
Week 11: 65 km (+2%)
Week 12: 46 km (Recovery, 70% of week 11)
Week 13 (Peak): 65 km (Hold)
Week 14 (Peak): 65 km (Hold)
Week 15 (Taper): 46 km (70% of peak)
Week 16 (Race week): 26 km (40% of peak, includes race)
```

**Validation**:
```bash
# Check each week-to-week progression
sce guardrails progression --previous 44 --current 48
```

---

### Step 4: Calculate VDOT & Training Paces

Determine personalized pace zones from recent race performance or estimated VDOT.

#### 4a. Calculate VDOT

**If recent race result**:
```bash
sce vdot calculate --race-type 10k --time 42:30
# Returns: VDOT 48
```

**If no recent race**:
- Ask: "Do you have a recent race time (5K, 10K, half, marathon)?"
- Alternative: Use mile time test (six-second rule)
- Conservative estimate: Start with moderate VDOT (45-50), adjust after first tempo run

#### 4b. Get Training Paces
```bash
sce vdot paces --vdot 48
```

**Returns** (example for VDOT 48):
- E-pace: 6:00-6:30/km (easy, conversational)
- M-pace: 5:15-5:30/km (marathon pace)
- T-pace: 4:50-5:10/km (threshold/tempo)
- I-pace: 4:20-4:40/km (intervals)
- R-pace: 3:50-4:10/km (repetition/speed)

**Use** [PACE_ZONES.md](references/PACE_ZONES.md) for workout type guidance.

**Store paces** for workout prescription.

---

### Step 5: Prescribe Workouts by Phase

Design weekly workout structure based on phase and constraints.

**Use** [PACE_ZONES.md](references/PACE_ZONES.md) for workout types by race distance.

#### 5a. Base Phase Workouts

**Focus**: Build aerobic foundation
**Intensity**: 80-90% easy (E-pace), 10-20% moderate
**Key sessions**: Long run, optional tempo (late base)

**Example week structure (4 run days/week)**:
- **Day 1**: Easy run (6 km, E-pace, 30-35 min)
- **Day 2**: Easy run (8 km, E-pace, 45-50 min)
- **Day 3**: Rest or cross-training
- **Day 4**: Easy run (6 km, E-pace, 30-35 min)
- **Day 5**: Rest
- **Day 6**: Long run (12-18 km, E-pace, 70-110 min)
- **Day 7**: Rest

**Long run progression**: +10-15 min every 2-3 weeks, cap at 30% of weekly volume

#### 5b. Build Phase Workouts

**Focus**: Add race-specific intensity
**Intensity**: 70-75% easy, 25-30% quality
**Key sessions**: Tempo run, long run, occasional intervals

**Example week structure (4 run days/week, half marathon)**:
- **Day 1**: Easy run (6 km, E-pace)
- **Day 2**: Tempo run (2 km warm-up + 6 km T-pace + 2 km cool-down = 10 km total)
- **Day 3**: Easy run (6 km, E-pace)
- **Day 4**: Rest
- **Day 5**: Easy run (8 km, E-pace)
- **Day 6**: Long run with M-pace (12 km E-pace + 6 km M-pace + 2 km E-pace = 20 km total)
- **Day 7**: Rest

**Tempo frequency**: Once per week
**Intervals**: Every 2-3 weeks (alternate with tempo)

#### 5c. Peak Phase Workouts

**Focus**: Maximum load, sharpening
**Intensity**: 65-70% easy, 30-35% quality
**Key sessions**: Race-pace work, maintain long run

**Example week structure (half marathon)**:
- **Day 1**: Easy run (8 km)
- **Day 2**: M-pace workout (3 km warm-up + 8 km M-pace + 2 km cool-down)
- **Day 3**: Easy run (6 km)
- **Day 4**: Tempo run (5 km T-pace)
- **Day 5**: Rest
- **Day 6**: Long run (18-20 km, mostly E-pace with M-pace segments)
- **Day 7**: Easy run (6 km) or rest

**Peak week 1**: Maximum volume + intensity
**Peak week 2**: Maintain volume, slightly reduce intensity (prepare for taper)

#### 5d. Taper Phase Workouts

**Focus**: Reduce fatigue, maintain fitness
**Intensity**: Maintain pace zones, reduce volume by 30-50%
**Key sessions**: Shorter quality work, race-pace strides

**Example week structure (Week 15 of 16, half marathon)**:
- **Day 1**: Easy run (6 km)
- **Day 2**: Short tempo (2 km warm-up + 3 km T-pace + 1 km cool-down = 6 km)
- **Day 3**: Rest
- **Day 4**: Easy run (6 km)
- **Day 5**: Rest
- **Day 6**: Long run (12 km E-pace)
- **Day 7**: Rest

**Race week** (Week 16):
- 2-3 easy runs (4-6 km each)
- 1 session with race-pace strides (4 × 200m at M-pace with 200m jog recovery)
- Rest 2 days before race
- **Race day**: Half marathon

---

### Step 6: Integrate Multi-Sport Constraints

Map running workouts around other sport commitments.

**Use** [MULTI_SPORT.md](references/MULTI_SPORT.md) for integration strategies.

#### 6a. Identify Fixed Days
Ask athlete: "Which days are non-negotiable for [other sport]?"

**Example**:
- Climbing: Tuesday evenings, Saturday (comp or outdoor)
- → Fixed: Tuesday, Saturday for climbing

#### 6b. Place Running Around Fixed Days

**Principle**:
- Easy runs 24 hours after climbing/other sports (systemic recovery, legs fresh)
- Quality runs 48 hours after hard sessions (both channels recovered)
- Long runs on days with good recovery window

**Example weekly schedule (EQUAL priority, climbing + running)**:
- **Monday**: Rest
- **Tuesday**: Climbing (fixed)
- **Wednesday**: Easy run (24 hours after climbing)
- **Thursday**: Climbing (fixed)
- **Friday**: Rest or yoga
- **Saturday**: Climbing (fixed)
- **Sunday**: Long run (24 hours after Saturday climbing, minimal lower-body carryover)
- **Monday** (following week): Tempo run (48 hours after Saturday climbing)

**Load analysis**:
```bash
sce analysis load --activities activities.json --days 7 --priority equal
```

Verify: Running ~40-50% of load, other sports ~40-50% of load

---

### Step 7: Validate Against Guardrails

Check plan compliance with evidence-based safety rules.

**Use** [GUARDRAILS.md](references/GUARDRAILS.md) for validation commands.

#### 7a. Quality Volume Limits (Daniels)
```bash
# For each week with quality work
sce guardrails quality-volume --t-pace 6.0 --i-pace 4.0 --r-pace 0 --weekly-volume 50.0
```

**Check**:
- T-pace ≤10% of weekly volume
- I-pace ≤8% of weekly volume
- R-pace ≤5% of weekly volume

**Action if violated**: Reduce quality distance or increase weekly volume

#### 7b. Long Run Caps
```bash
# For each week
sce guardrails long-run --duration 120 --weekly-volume 55 --pct-limit 30
```

**Check**:
- Duration ≤150 min (2.5 hours)
- Long run ≤30% of weekly volume

**Action if violated**: Reduce long run distance or increase weekly volume

#### 7c. Weekly Progression (10% Rule)
```bash
# Check week-to-week
sce guardrails progression --previous 44 --current 48
```

**Action if violated**: Adjust weekly volumes to comply

#### 7d. Overall Plan Structure
```bash
# Create temporary plan JSON (simplified structure for validation)
# See scripts/generate_plan.py for full implementation

sce validation validate-plan --total-weeks 16 --goal-type half_marathon \
  --phases phases.json --weekly-volumes volumes.json --recovery-weeks recovery.json --race-week 16
```

**Returns**:
- `overall_quality_score`: 0-100
- `phase_checks`: Duration, progression compliance
- `violations`: Specific issues
- `recommendations`: Suggested adjustments

**Action**: Fix violations before presenting to athlete

---

### Step 8: Present Plan for Review (CRITICAL)

**NEVER save plan directly**. Always present in markdown format for athlete review and approval.

#### 8a. Generate Markdown Presentation

**Template**: Use `/templates/plan_presentation.md` structure

Create `/tmp/training_plan_review_YYYY_MM_DD.md` with:

1. **Goal Overview**
   - Race: [Type], [Date]
   - Target time: [If specified]
   - Weeks: [Total]
   - Current fitness: CTL [Value] ([Interpretation])

2. **Plan Structure**
   - Phase breakdown (weeks, volume progression)
   - Recovery weeks placement
   - Peak volume: [X km]

3. **Constraints Respected**
   - Run days: [Days/week]
   - Other sports: [Schedule]
   - Long run cap: [Duration]

4. **Weekly Breakdown** (Weeks 1-4 detailed, then summary)
   - Week 1: [Volume], [Phase], [Key workouts]
   - Week 2: ...
   - [Summary of remaining weeks]

5. **Training Paces** (from VDOT)
   - Easy: [Range]
   - Tempo: [Range]
   - Marathon pace: [Range]
   - Intervals: [Range]

6. **Guardrails Check**
   - ✓ 80/20 compliance
   - ✓ Quality volume limits
   - ✓ Long run caps
   - ✓ Weekly progression safe

#### 8b. Present to Athlete

```
I've designed a training plan for your [race type] on [date].

📋 Plan proposal: /tmp/training_plan_review_2026_01_16.md

Key highlights:
- [X] weeks: Base ([Y]w) → Build ([Y]w) → Peak ([Y]w) → Taper ([Y]w)
- Volume: [Start] km → [Peak] km
- Respects your [constraints description]
- Week 1 starts [easy/moderate]: [Brief description]

Review the full plan and let me know:
- **Approve as-is** → I'll save it to your training plan
- **Request modifications** → I'll adjust and re-present
- **Ask questions** → Happy to explain any part

What do you think?
```

#### 8c. Handle Athlete Response

**If approve**: Proceed to Step 9 (save plan)
**If modify**: Use AskUserQuestion to clarify changes, regenerate, re-present
**If questions**: Answer with reference to methodology, then re-confirm approval

---

### Step 9: Save Plan to System

After athlete approval, convert markdown plan to JSON and populate via CLI.

**Option A: Use Python script** (recommended for complex plans)
```bash
python scripts/generate_plan.py --goal-type half_marathon --weeks 16 --output /tmp/plan.json
# Script reads profile, applies workflow steps 1-7, generates JSON

sce plan populate --from-json /tmp/plan.json
```

**Option B: Manual JSON creation** (for simple plans)
Create JSON structure manually, then:
```bash
sce plan populate --from-json /tmp/plan.json
```

**JSON structure** (see `examples/` directory for full examples):
```json
{
  "weeks": [
    {
      "week_number": 1,
      "phase": "base",
      "start_date": "2026-01-20",
      "end_date": "2026-01-26",
      "target_volume_km": 40.0,
      "target_systemic_load_au": 280.0,
      "is_recovery_week": false,
      "notes": "Base building week",
      "workouts": [
        {
          "id": "w1d2_easy",
          "week_number": 1,
          "day_of_week": 1,  // 0=Monday, 1=Tuesday, etc.
          "date": "2026-01-21",
          "workout_type": "easy",
          "phase": "base",
          "duration_minutes": 35,
          "distance_km": 6.0,
          "intensity_zone": "z2",
          "target_rpe": 3,
          "target_pace_per_km": "6:00-6:30",
          "target_hr_range": "120-140",
          "purpose": "Aerobic base",
          "surface": "road",
          "elevation_gain_m": 0
        }
        // More workouts...
      ]
    }
    // More weeks...
  ]
}
```

**Verification**:
```bash
sce plan show  # Confirm plan saved correctly
```

---

## Decision Trees

### Q: Athlete wants higher volume than CTL suggests

**Scenario**: CTL is 35 (suggests 35-40 km/week start), athlete wants 50 km/week

**Response**:
```
I understand you want to start at 50 km/week, but your current CTL is 35, which suggests 35-40 km is safer.

Here's the challenge:
- Starting above proven capacity increases ACWR immediately (spike risk)
- Injury probability rises when jumping >20% above current baseline
- Better to start conservatively and build safely

Two options:
1. Start at 40 km, reach 50 km by week 3 (gradual buildup, safer)
2. Start at 50 km, but extend base phase +2 weeks (more adaptation time)

Which sounds better? Remember: The goal is to reach race day healthy AND trained.
```

**Use**:
```bash
sce analysis capacity --activities activities.json --planned-volume 50
```

To show historical max vs. planned volume.

### Q: Insufficient weeks to goal

**Scenario**: Half marathon in 8 weeks (minimum 12 weeks recommended)

**Options via AskUserQuestion**:
1. **Extend goal date** (+4 weeks, safer)
   - Allows proper periodization
   - Reduces injury risk
   - Better race performance

2. **Compressed plan** (keep 8 weeks)
   - Skip base phase or shorten it
   - Higher risk (less adaptation time)
   - May not perform optimally

3. **Adjust expectations** ("Fun run" vs. race)
   - Participate without time goal
   - Less pressure, enjoy experience
   - Use as fitness check for future race

**Recommendation**: Extend goal date if possible

### Q: Multi-sport conflict during key workout

**Scenario**: Saturday long run conflicts with climbing comp

**If conflict policy = `ask_each_time`**:

Use AskUserQuestion:
```
Your 18 km long run is scheduled Saturday, but you have a climbing comp. What would you prefer?

Options:
1. Long run Saturday, skip comp (prioritize race training)
   - 14 weeks to half marathon, long run is key workout
   - Climbing comps happen more frequently

2. Climbing comp Saturday, long run Sunday (shift schedule)
   - Still gets long run in, 24-hour delay
   - Sunday works if not too fatigued from comp

3. Long run Friday, comp Saturday (advance schedule)
   - Gets long run done with fresh legs
   - Comp performance may suffer slightly from Friday run

What sounds best based on your priorities right now?
```

**Store preference** for similar future conflicts.

### Q: Athlete has injury history

**Scenario**: "Left knee tendonitis last year, sensitive after 18km+"

**Adjustments**:
1. **Cap long run**: Max 16-17 km (below sensitivity threshold)
2. **Increase frequency**: 5 runs/week instead of 4 (spread volume)
3. **More cross-training**: Cycling/swimming for volume without impact
4. **Monitor closely**: Flag any knee discomfort in training notes

**Communicate**:
```
Given your knee history (sensitive after 18km), I'm capping long runs at 16 km and spreading volume across 5 days instead of 4. This reduces single-session impact while maintaining weekly volume.

If you feel any knee discomfort, let me know immediately - we'll adjust.
```

### Q: No recent race time (unknown VDOT)

**Scenario**: Can't calculate VDOT from race result

**Options**:
1. **Mile test**: Run 1 mile at max effort, use six-second rule
   ```bash
   sce vdot six-second --mile-time 7:00
   ```

2. **Estimate from recent training**: "What pace feels 'comfortably hard' for 20-30 min?" (T-pace) → backsolve VDOT

3. **Conservative default**: Start with VDOT 45 (moderate), adjust after first tempo run

**After first quality session**: Recalculate VDOT from actual performance, update paces

---

## Common Pitfalls

### 1. Designing plan without discussing constraints

❌ **Bad**: Creating 6-day/week plan when athlete only has time for 4 days
✅ **Good**: "How many days per week can you realistically run?" → Design around answer

**Verify constraints BEFORE designing** (Step 1c).

### 2. Ignoring CTL when setting starting volume

❌ **Bad**: Starting all half marathon plans at 50 km/week
✅ **Good**: CTL 35 → start at 35 km; CTL 50 → start at 50 km

**Use CTL-based starting volume** (Step 3a).

### 3. Not presenting plan for review

❌ **Bad**: Generating JSON and populating directly
✅ **Good**: Create markdown presentation, get athlete approval, THEN save

**Always use markdown review workflow** (Step 8).

### 4. Forgetting recovery weeks

❌ **Bad**: 12 weeks of continuous building
✅ **Good**: Recovery week every 4th during base/build

**Place recovery weeks during periodization** (Step 2b).

### 5. Excessive quality volume

❌ **Bad**: 8 km T-pace + 6 km I-pace in a 40 km week (35% quality)
✅ **Good**: 4 km T-pace + 3 km I-pace (17.5% quality, compliant)

**Validate quality volume** (Step 7a).

### 6. Not accounting for multi-sport load

❌ **Bad**: Scheduling tempo run day after hard climbing
✅ **Good**: Easy run day after climbing, tempo 48 hours later

**Map workouts around other sports** (Step 6).

---

## Plan Update Strategies

After initial plan creation, athletes may need adjustments.

### Mid-Week Adjustment
**Use**: `sce plan update-week --week N --from-json week.json`
**Scenario**: Athlete got sick week 5, need to downgrade week 5 workouts
**JSON**: Single week object (not array)

### Partial Replan
**Use**: `sce plan update-from --week N --from-json weeks.json`
**Scenario**: After week 4, replan weeks 5-16 due to injury setback
**JSON**: Weeks array starting from week N
**Preserves**: Weeks 1 to N-1

### Full Regeneration
**Use**: `sce plan regen` or `sce plan populate --from-json`
**Scenario**: Goal changed (10K → half marathon), complete redesign needed

---

## Links to References

**Training methodology** (1-page summaries, load on-demand):
- [PERIODIZATION.md](references/PERIODIZATION.md) - Phase allocation, recovery weeks
- [PACE_ZONES.md](references/PACE_ZONES.md) - VDOT system, E/M/T/I/R zones
- [VOLUME_PROGRESSION.md](references/VOLUME_PROGRESSION.md) - 10% rule, CTL-based starting volumes
- [GUARDRAILS.md](references/GUARDRAILS.md) - 80/20, quality limits, long run caps
- [MULTI_SPORT.md](references/MULTI_SPORT.md) - Two-channel load model, conflict resolution

**Training books** (comprehensive methodology, deep dives):
- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md)
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md)
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md)
- [Faster Road Racing](../../../docs/training_books/faster_road_racing_pete_pfitzinger.md)
- [Run Less, Run Faster](../../../docs/training_books/run_less_run_faster_bill_pierce.md)

**Example plans** (see `examples/` directory):
- [10K plan example](examples/10k_plan_example.md)
- [Half marathon plan example](examples/half_marathon_plan_example.md)
- [Marathon plan example](examples/marathon_plan_example.md)

**Scripts**:
- [generate_plan.py](scripts/generate_plan.py) - Automated plan generation from profile + goal

**Template**:
- [plan_presentation.md](templates/plan_presentation.md) - Markdown template for athlete review
