# Weekly Planning: Generate Next Week's Workouts

## Overview

Generate detailed workouts for the next week of training using **progressive disclosure** workflow. Each week is tailored based on actual training response, enabling true adaptive planning.

**Core Philosophy**: Plan 1 week at a time (not 4 weeks in advance) to maximize adaptability and minimize LLM errors. AI coach designs weekly volumes using guardrails - NO algorithmic interpolation.

**This skill handles**:
- Loading macro plan context (phases, recovery weeks, volume goals)
- Analyzing previous week's training response
- **Designing next week's volume** (AI decision using guardrails)
- VDOT recalibration (race results, breakthrough workouts)
- Generating detailed workouts (intent-based format)
- Validation (volume, minimum durations, guardrails)
- Presentation to athlete
- Saving after approval

---

## When to Use This Skill

**Activate weekly-planning skill when**:
1. **After weekly-analysis completion** - Natural flow: analyze week → plan next week
2. **Initial plan creation** - Generate Week 1 after macro plan approved
3. **Mid-plan regeneration** - Athlete wants to adjust next week's plan

**Do NOT use this skill when**:
- Athlete asks "how was my week?" → Use `weekly-analysis` skill first
- Athlete wants to change entire plan → Use `plan-adaptation` skill instead
- Athlete asks for today's workout → Use `daily-workout` skill directly

---

## Prerequisites

Before activating this skill, ensure:
- ✅ **Macro plan exists** - 16-week structure with phases, recovery weeks, volume goals (`data/plans/current_plan_macro.json`)
- ✅ **Current week completed** (if generating week N+1) - Athlete has finished week N
- ✅ **Weekly analysis done** (optional but recommended) - Informs volume design decisions
- ✅ **Profile constraints current** - Run days, available days, max session duration

---

## Workflow

### Step 1: Load Context from Macro Plan

```bash
# Load macro plan structure
MACRO_PLAN=$(cat data/plans/current_plan_macro.json)
NEXT_WEEK_NUMBER=$((COMPLETED_WEEK + 1))

# Extract context
PHASE=$(echo "$MACRO_PLAN" | jq -r '.phases[] | select(.weeks[] == '$NEXT_WEEK_NUMBER') | .name')
RECOVERY_WEEKS=$(echo "$MACRO_PLAN" | jq -r '.recovery_weeks')
IS_RECOVERY_WEEK=$(echo "$RECOVERY_WEEKS" | jq 'contains(['$NEXT_WEEK_NUMBER'])')
PEAK_TARGET=$(echo "$MACRO_PLAN" | jq -r '.peak_volume_km')
```

**Context loaded**:
- `phase`: Current training phase (base/build/peak/taper)
- `is_recovery_week`: Whether next week is a recovery week
- `peak_target`: Peak volume goal (reference only)

**Note**: NO `volume_trajectory` field - volumes are designed by AI, not pre-computed.

### Step 2: Analyze Previous Week

**Gather training response data**:
```bash
# Get previous week's actual volume and metrics
PREV_ACTUAL=$(sce week | jq -r '.data.total_distance_km')
PREV_ADHERENCE=$(sce analysis adherence | jq -r '.data.adherence_rate')
CURRENT_ACWR=$(sce status | jq -r '.data.acwr.value')
CURRENT_TSB=$(sce status | jq -r '.data.tsb.value')
READINESS=$(sce status | jq -r '.data.readiness_score')
```

**Check for signals**:
- Illness/injury mentions in activity notes?
- Poor adherence (<70%)?
- Elevated ACWR (>1.3)?
- Negative TSB (<-20)?

**Output**: Understanding of athlete's current state and capacity

### Step 3: Propose Next Week Volume (AI Decision)

**Base calculation using phase progression**:
```bash
BASE_VOLUME=$PREV_ACTUAL

# Phase-based progression factors
if [ "$PHASE" == "base" ]; then
    PROGRESSION_FACTOR=1.10  # 10% increase (typical base phase)
elif [ "$PHASE" == "build" ]; then
    PROGRESSION_FACTOR=1.07  # 7% increase (build phase)
elif [ "$PHASE" == "peak" ]; then
    PROGRESSION_FACTOR=1.02  # 2% increase (hold volume)
elif [ "$PHASE" == "taper" ]; then
    PROGRESSION_FACTOR=0.80  # 20% reduction (taper)
fi

# Apply recovery week reduction
if [ "$IS_RECOVERY_WEEK" == "true" ]; then
    PROGRESSION_FACTOR=0.70  # 30% reduction
fi

# Calculate proposed volume
PROPOSED_VOLUME=$(echo "$BASE_VOLUME * $PROGRESSION_FACTOR" | bc -l)
```

**Apply context adjustments**:
```bash
# Illness/injury adjustment
if [ILLNESS_DETECTED]; then
    PROPOSED_VOLUME=$(echo "$PROPOSED_VOLUME * 0.75" | bc -l)  # 25% reduction
fi

# ACWR adjustment
if (( $(echo "$CURRENT_ACWR > 1.3" | bc -l) )); then
    PROPOSED_VOLUME=$(echo "$PROPOSED_VOLUME * 0.85" | bc -l)  # 15% reduction
fi

# Poor adherence adjustment
if (( $(echo "$PREV_ADHERENCE < 0.70" | bc -l) )); then
    PROPOSED_VOLUME=$(echo "$PROPOSED_VOLUME * 0.90" | bc -l)  # 10% reduction
fi

# Round to 1 decimal
PROPOSED_VOLUME=$(printf "%.1f" $PROPOSED_VOLUME)
```

**Output**: `PROPOSED_VOLUME` for next week (AI-designed based on response)

### Step 4: Validate Proposed Volume with Guardrails

**Run validation**:
```bash
MAX_RUN_DAYS=$(sce profile get | jq -r '.data.max_run_days')
AGE=$(sce profile get | jq -r '.data.age')

sce guardrails analyze-progression \
  --previous $PREV_ACTUAL \
  --current $PROPOSED_VOLUME \
  --ctl $CURRENT_CTL \
  --run-days $MAX_RUN_DAYS \
  --age $AGE
```

**Guardrails output provides**:
- `risk_factors`: List of concerns (e.g., "Weekly increase exceeds 15%")
- `protective_factors`: List of mitigations (e.g., "Low volume classification")
- `volume_classification`: low/medium/high volume context
- `pfitzinger_guideline`: Per-session analysis (1.6km rule)
- `coaching_considerations`: Methodology-based guidance

**Output**: Rich context for coaching decision (not a pass/fail)

### Step 5: Interpret Guardrails & Finalize Volume (AI Coaching Decision)

**Decision tree**:

1. **If risk_factors dominate** (e.g., "Weekly increase >15%", "ACWR spike"):
   - **MODIFY**: Reduce PROPOSED_VOLUME by 10-20%
   - Example: `FINAL_VOLUME=$(echo "$PROPOSED_VOLUME * 0.85" | bc -l)`

2. **If protective_factors dominate** (e.g., "Low volume", "Per-session within guideline"):
   - **ACCEPT**: Use PROPOSED_VOLUME as-is
   - Example: `FINAL_VOLUME=$PROPOSED_VOLUME`

3. **If mixed signals**:
   - Apply training methodology judgment
   - Prefer safety over progression
   - Example: Accept if athlete has good training history, modify if injury-prone

4. **If Pfitzinger per-session guideline violated** (e.g., 3.7km easy runs):
   - Reduce run frequency (4 runs → 3 runs)
   - Increase per-run distance to maintain minimum

**Output**: `FINAL_VOLUME` for next week (AI decision informed by guardrails)

### Step 6: VDOT Recalibration & Goal Re-Assessment

#### VDOT Recalibration

**Signals for VDOT adjustment**:

1. **Recent race result** (<7 days):
   ```bash
   sce vdot calculate --race-type [TYPE] --time [TIME]
   # If significantly different from current VDOT → update
   ```

2. **Breakthrough workout** (consistently faster paces):
   ```bash
   sce vdot estimate-current --lookback-days 14
   # If 2+ VDOT points higher → update
   ```

3. **Every 4 weeks** (default recalibration):
   ```bash
   sce vdot estimate-current --lookback-days 28
   # Update if confidence is high
   ```

**Decision**:
- If new VDOT differs by ≥2 points → use new VDOT
- If <2 points → keep current VDOT (avoid micro-adjustments)
- Communicate change to athlete: "Your fitness has improved - updating paces!"

**Output**: `CURRENT_VDOT` for next week's plan

#### Goal Re-Validation (Optional - Only When VDOT Changes Significantly)

**Trigger**: VDOT changes by ±2 points

**If VDOT improved significantly (e.g., 48 → 51)**:
- Celebrate: "Your VDOT jumped from 48 to 51! Goal now more achievable."
- Optional: Run `sce goal validate` to show updated feasibility

**If VDOT declined (e.g., 50 → 47)**:
- Check cause: Illness? Missed workouts? Overtraining?
- Discuss if goal adjustment needed

**Most cases**: Skip validation, let race-preparation skill handle final reality check (7-14 days out)

**Continue to Step 7 (Generate Next Week)**

### Step 7: Create Next Week's Workout Pattern (Manual JSON)

**IMPORTANT**: AI coach creates `workout_pattern` JSON manually (same workflow as Week 1). This is NOT an algorithmic generation - the AI coach applies training methodology and athlete context to design each week.

**Tools the AI coach uses**:

1. **Read macro plan context** (phase, recovery status):
   ```bash
   PHASE=$(jq -r '.phases[] | select(.weeks[] == '$NEXT_WEEK_NUMBER') | .name' data/plans/current_plan_macro.json)
   IS_RECOVERY=$(jq -r '.recovery_weeks | contains(['$NEXT_WEEK_NUMBER'])' data/plans/current_plan_macro.json)
   START_DATE=$(jq -r '.start_date' data/plans/current_plan_macro.json)
   # Calculate next week's start_date (add (NEXT_WEEK_NUMBER - 1) * 7 days to START_DATE)
   ```

2. **Get training paces** (using current or recalibrated VDOT):
   ```bash
   sce vdot paces --vdot $CURRENT_VDOT
   # Copy: easy_pace_range, tempo_pace_range, interval_pace_range, race_pace_range
   ```

3. **Pre-flight validation** (ensures run count won't violate minimum durations):
   ```bash
   sce plan suggest-run-count --volume $FINAL_VOLUME --max-runs $MAX_RUNS --phase $PHASE
   # Use: recommended_runs (e.g., 3, 4, or 5)
   ```

4. **Read composition guidance** (if macro plan has it - see plan document for details):
   ```bash
   SUGGESTED_QUALITY=$(jq -r '.weeks[] | select(.week_number == '$NEXT_WEEK_NUMBER') | .suggested_quality_count // 0' data/plans/current_plan_macro.json)
   SUGGESTED_TYPES=$(jq -r '.weeks[] | select(.week_number == '$NEXT_WEEK_NUMBER') | .suggested_quality_types // []' data/plans/current_plan_macro.json)
   # This guidance is REFERENCE ONLY - AI coach can override based on athlete state
   ```

**AI coach creates workout_pattern JSON manually**:

The AI coach applies training methodology to decide:
- **Workout composition**: How many easy, tempo, interval, race pace runs?
- **Run days**: Which days of the week (based on athlete constraints and recovery)?
- **Long run percentage**: 40-55% depending on phase and recovery status
- **Paces**: From VDOT calculation
- **Structure description**: Human-readable summary (e.g., "2 easy + 1 tempo + 1 long")

**Example - Base Phase Week 5 (First Tempo Introduction)**:
```json
{
  "weeks": [{
    "week_number": 5,
    "phase": "base",
    "start_date": "2026-02-17",
    "end_date": "2026-02-23",
    "target_volume_km": 31.0,
    "is_recovery_week": false,
    "notes": "Base Phase Week 5 - First tempo introduction",
    "workout_pattern": {
      "structure": "2 easy + 1 tempo + 1 long",
      "run_days": [1, 3, 5, 6],
      "long_run_day": 6,
      "long_run_pct": 0.45,
      "quality_sessions": [
        {
          "day": 3,
          "type": "tempo",
          "warmup_km": 2.0,
          "main_km": 4.0,
          "main_pace": "5:45-5:55",
          "cooldown_km": 2.0
        }
      ],
      "easy_run_paces": "6:30-6:50",
      "long_run_pace": "6:30-6:50"
    }
  }]
}
```

**Example - Build Phase Week 9 (Tempo + Intervals)**:
```json
{
  "weeks": [{
    "week_number": 9,
    "phase": "build",
    "start_date": "2026-03-31",
    "end_date": "2026-04-06",
    "target_volume_km": 45.0,
    "is_recovery_week": false,
    "notes": "Build Phase Week 9 - Progressive intensity",
    "workout_pattern": {
      "structure": "1 easy + 1 tempo + 1 intervals + 1 long",
      "run_days": [1, 3, 5, 6],
      "long_run_day": 6,
      "long_run_pct": 0.47,
      "quality_sessions": [
        {
          "day": 1,
          "type": "tempo",
          "warmup_km": 2.0,
          "main_km": 6.0,
          "main_pace": "5:45-5:55",
          "cooldown_km": 2.0
        },
        {
          "day": 5,
          "type": "intervals",
          "warmup_km": 2.0,
          "intervals": "6 x 1000m @ 5:15-5:25",
          "recovery": "400m jog",
          "cooldown_km": 2.0
        }
      ],
      "easy_run_paces": "6:30-6:50",
      "long_run_pace": "6:30-6:50"
    }
  }]
}
```

**Key decisions the AI coach makes**:
- **Quality work progression**: When to introduce tempo (week 5-6), intervals (week 8+), race pace (peak)
- **Override guidance when needed**: Remove quality if ACWR > 1.3, illness, or poor adherence
- **Run days optimization**: Balance recovery, athlete constraints, quality work placement
- **Long run percentage**: Base = 40-45%, Build/Peak = 45-50%, Recovery = 50-55%, Taper = 35-40%
- **Workout structure**: Appropriate for phase (base: easy+long, build: add tempo/intervals, peak: race pace emphasis)

**Decision Process**:
1. Read composition guidance from macro plan (reference, not constraint)
2. Check current athlete state (ACWR, TSB, readiness, recent notes)
3. **Decide**: Follow guidance, modify, or override completely
4. Apply training methodology (Pfitzinger periodization, 80/20 distribution)
5. Create complete `workout_pattern` structure manually

**Example Override - ACWR > 1.3**:
```
Macro guidance: 2 quality sessions (tempo + intervals)
AI coach checks: ACWR = 1.35, athlete noted "feeling fatigued"
AI coach decides: Override to 0 quality (all easy runs)
Rationale: "Reducing intensity this week - ACWR elevated (1.35) and fatigue noted"
```

**Save to file**:
```bash
# AI coach saves the manually created JSON to:
echo '<JSON_CONTENT>' > /tmp/weekly_plan_w${NEXT_WEEK_NUMBER}.json
```

**Success**: Next week's workout_pattern JSON created manually by AI coach, applying training methodology and athlete context.

### Step 8: Validate Next Week's Plan

```bash
sce plan validate-week --weekly-plan /tmp/weekly_plan_w${NEXT_WEEK_NUMBER}.json
```

**Validation checks**:
- Volume discrepancy <5% (target vs. sum of workouts)
- No minimum duration violations (easy ≥5km, long ≥8km)
- Quality volume within limits (T≤10%, I≤8%, R≤5%)
- Week-over-week progression acceptable (<10% increase)
- Dates aligned (start=Monday, end=Sunday)

**If validation fails**:
- Adjust run count: Use `sce plan suggest-run-count` to verify feasibility
- Regenerate with corrected parameters
- Re-validate until clean

**Critical**: Never present an unvalidated plan to the athlete.

### Step 9: Present Next Week's Plan to Athlete

**Format**:
```markdown
## Next Week Plan (Week [N])

Based on [previous week's performance / macro plan], here's your Week [N] plan:

**Volume**: [X] km ([+/-Y]% from Week [N-1])
**Phase**: [Base/Build/Peak/Taper]
**Start Date**: [YYYY-MM-DD] (Monday)

**Workouts**:
- **Tuesday**: [Workout type] ([X] km, [Y] min, [pace range])
- **Thursday**: [Workout type] ([X] km, [Y] min, [pace range])
- **Saturday**: [Workout type] ([X] km, [Y] min, [pace range])
- **Sunday**: [Workout type] ([X] km, [Y] min, [pace range])

**Why this plan**:
[1-2 sentences explaining rationale based on weekly analysis or macro plan]
- [e.g., "Volume increased 13% based on strong adaptation this week (ACWR 1.1)"]
- [e.g., "Maintaining easy paces after 80/20 violation last week"]
- [e.g., "Volume reduced 15% due to illness recovery"]

**Approve this plan, or request changes?**
```

**Key elements**:
- Clear connection to context (rationale is transparent)
- Concrete numbers (distances, paces, volume change)
- Explicit approval request (never save without consent)

### Step 10: Save Next Week's Plan (ONLY After Approval)

**After athlete explicitly approves**:

```bash
# Save weekly plan to system
sce plan populate --from-json /tmp/weekly_plan_w${NEXT_WEEK_NUMBER}.json

# Verify saved correctly
sce plan show --week $NEXT_WEEK_NUMBER
sce today  # Should show first workout of new week (if today is in that week)
```

**Confirm to athlete**:
```
Week [N] plan saved! You'll see daily workouts starting [START_DATE].

View anytime with:
- `sce today` - Today's workout
- `sce week` - Full week schedule
- `sce plan show` - All planned weeks
```

**If athlete requests changes**:
- "Change X" → Adjust parameters → Regenerate (Step 4) → Re-present (Step 6)
- "Question Y" → Answer → Re-confirm → Save when approved

**Critical**: NEVER save without explicit athlete approval.

---

## Volume Design Guidelines

Use these factors to propose next week volume in Step 3:

### Base Phase Progression
- **Standard**: +8-12% per week
- **Recovery week** (every 4th): 70% of previous week
- **Max single-week increase**: 15% (requires strong justification)

### Build Phase Progression
- **Standard**: +5-10% per week
- **Focus**: Quality over volume increases
- **Recovery week**: 75% of previous week

### Peak Phase
- **Standard**: Hold volume steady or minor increases (+0-5%)
- **Goal**: Maintain fitness without accumulating fatigue

### Taper Phase
- **Week 1 of taper**: -15-20%
- **Week 2 of taper**: -30-40%
- **Race week**: -50-60%

### Adjustment Factors
- **ACWR > 1.3**: Reduce by 15% (multiply by 0.85)
- **Illness recovery**: 70-85% depending on severity
- **Poor adherence**: Hold or reduce volume
- **Excellent adherence + low TSB**: Consider +5-10% bonus

### Example: Base Phase Week 3 → Week 4

**Context**: Week 3 actual = 28km, adherence = 92%, ACWR = 1.15, no illness

**Calculation**:
```bash
BASE_VOLUME=28
PROGRESSION_FACTOR=1.10  # Base phase standard
PROPOSED_VOLUME=$(echo "$BASE_VOLUME * $PROGRESSION_FACTOR" | bc)  # 30.8km

# No ACWR adjustment needed (1.15 < 1.3)
# No illness adjustment
# Strong adherence → no reduction

FINAL_VOLUME=30.8  # Round to 31km
```

**Rationale**: "Increasing 11% based on excellent adherence (92%) and safe ACWR (1.15). Base phase progression on track."

### Example: Build Phase Recovery Week

**Context**: Week 7 actual = 42km, adherence = 78%, ACWR = 1.28, Week 8 is recovery

**Calculation**:
```bash
BASE_VOLUME=42
PROGRESSION_FACTOR=0.75  # Recovery week (build phase)
PROPOSED_VOLUME=$(echo "$BASE_VOLUME * $PROGRESSION_FACTOR" | bc)  # 31.5km

# No additional adjustments needed (recovery already accounts for load)

FINAL_VOLUME=31.5  # Round to 32km
```

**Rationale**: "Recovery week reduces volume 25% to 32km. ACWR will drop from 1.28 → ~1.10."

---

## Quick Decision Trees

### Q: Should I reduce volume for next week?

**YES - Reduce volume by 10-20% if**:
- Previous week adherence <70% (missed multiple workouts)
- ACWR >1.3 (elevated injury risk)
- Illness/injury detected in previous week
- Athlete explicitly requests lower volume

**NO - Proceed with macro plan target if**:
- Previous week adherence >85%
- ACWR <1.2 (safe zone)
- No injury/illness signals
- Readiness score >65 (moderate to good)

### Q: Should I recalibrate VDOT?

**YES - Update VDOT if**:
- Recent race result (<7 days) differs by 2+ points
- Breakthrough workout (estimated VDOT 2+ points higher)
- 4+ weeks since last VDOT update AND consistent pace improvements

**NO - Keep current VDOT if**:
- <2 weeks since last update (too soon)
- New estimate differs by <2 points (avoid micro-adjustments)
- Low confidence in estimate (mixed workout quality)

### Q: Athlete disagrees with plan - what now?

1. **Listen to specific concerns**:
   - "Too much volume" → Regenerate with `--volume-adjustment 0.9`
   - "Wrong days" → Update profile `--available-days`, regenerate
   - "Can't do long run that long" → Update profile `--max-session-minutes`, regenerate

2. **Use revert-week if already saved**:
   ```bash
   sce plan revert-week --week-number [N]
   # Then regenerate with adjusted parameters
   ```

3. **Never override athlete's body awareness** - They know their capacity better than metrics

---

## Quick Pitfalls Checklist

Before presenting next week's plan:

- [ ] **Loaded macro plan context** - Extracted `phase`, `is_recovery_week`, `peak_target` (NO volume_trajectory)
- [ ] **Analyzed previous week** - Gathered actual volume, adherence, ACWR, TSB, readiness
- [ ] **Proposed next week volume** - Used phase progression factors + context adjustments (AI decision)
- [ ] **Validated with guardrails** - Ran `analyze-progression`, interpreted risk vs protective factors
- [ ] **Finalized volume** - Applied coaching judgment to guardrails output
- [ ] **Checked VDOT recalibration** - Updated if race result or breakthrough workout
- [ ] **Generated workouts** - Used `sce plan generate-week --target-volume-km $FINAL_VOLUME`
- [ ] **Validated plan** - Ran `sce plan validate-week`, resolved all critical violations
- [ ] **Presented clearly** - Included rationale, concrete numbers, approval request
- [ ] **Waited for approval** - Did NOT save until athlete explicitly approved

Critical boundaries:
- ⛔ **DO NOT save plan without athlete approval** - Always wait for explicit consent
- ⛔ **DO NOT skip validation** - Catches errors before presenting to athlete
- ⛔ **DO NOT ignore athlete feedback** - If they say "too much", believe them and adjust
- ⛔ **DO NOT use volume_trajectory** - Weekly volumes are AI-designed, not pre-computed

---

## Integration Notes

### Used After weekly-analysis Skill

Natural flow when athlete asks "How was my week?":

1. **weekly-analysis** skill runs Steps 1-7 (analyze completed week)
2. Coach asks: "Ready to plan next week?"
3. **weekly-planning** skill activates (this skill - generate next week)
4. Seamless coaching conversation from analysis → planning

### Used During Initial Plan Creation

When designing training plan for first time:

1. **training-plan-design** skill generates macro plan (16 weeks, mileage targets only)
2. Athlete approves macro structure
3. **weekly-planning** skill activates to generate Week 1 detailed workouts
4. Week 1 saved, plan is ready to start

### Used for Plan Adjustments

When athlete needs to adjust upcoming week:

1. Athlete: "Can we change next week's plan?"
2. **weekly-planning** skill activates
3. Generate with different parameters (volume adjustment, different run days, etc.)
4. Present and save after approval

---

## Additional Resources

- **CLI Reference**: [docs/coaching/cli/cli_planning.md](../../../docs/coaching/cli/cli_planning.md) - Commands for `generate-week`, `validate-week`, `revert-week`
- **Coaching Scenario**: [docs/coaching/scenarios.md - Scenario 12](../../../docs/coaching/scenarios.md#scenario-12-weekly-planning-transition-workflow) - Complete workflow example
- **Training Plan Design**: [training-plan-design/SKILL.md](../training-plan-design/SKILL.md) - Macro plan generation
- **Weekly Analysis**: [weekly-analysis/SKILL.md](../weekly-analysis/SKILL.md) - Analyze completed week before planning next week
