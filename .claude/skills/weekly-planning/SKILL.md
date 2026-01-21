# Weekly Planning: Generate Next Week's Workouts

## Overview

Generate detailed workouts for the next week using **progressive disclosure**. Each week is tailored based on actual training response.

**Core Philosophy**: Plan 1 week at a time to maximize adaptability. AI coach designs weekly volumes using guardrails - NO algorithmic interpolation.

**This skill handles**:
- Determining week type (Week 1 initial vs Week 2+ progression)
- Loading macro plan context (phases, recovery weeks, volume goals)
- Analyzing training history (previous weeks for Week 2+, CTL baseline for Week 1)
- Designing volume (AI decision using guardrails)
- VDOT determination (estimate for Week 1, recalibration for Week 2+)
- Generating detailed workouts (intent-based format)
- Validation & presentation
- Saving after approval

---

## When to Use This Skill

**Activate when**:
1. After weekly-analysis completion → Natural flow
2. Initial plan creation → Generate Week 1 after macro plan approved
3. Mid-plan regeneration → Athlete wants to adjust next week

**Do NOT use when**:
- Athlete asks "how was my week?" → Use `weekly-analysis` first
- Wants to change entire plan → Use `plan-adaptation`
- Asks for today's workout → Use `daily-workout`

---

## Prerequisites

Before activating:
- ✅ **Macro plan exists** - MasterPlan skeleton with phases, recovery weeks, volume goals (`data/plans/current_plan.yaml`)
- ✅ **Current week completed** (if generating week N+1) OR Week 1 (initial plan)
- ✅ **Profile constraints current** - Run days, available days, max session duration
- ✅ **Weekly analysis done** (optional but recommended for Week 2+)

---

## Workflow

### Step 0: Determine Week Type

**Check what week we're generating**:

```bash
# Check current plan state
LAST_WEEK=$(jq -r '.weeks[-1].week_number // 0' data/plans/current_plan.yaml)
NEXT_WEEK=$((LAST_WEEK + 1))
```

**Branch logic**:

**If NEXT_WEEK == 1** (Initial week generation):
- No previous week to analyze
- Baseline: `sce status` (CTL, TSB, ACWR, readiness)
- Volume source: Macro plan's week 1 `target_volume_km` (reference, AI can adjust)
- VDOT: Load `baseline_vdot` from macro plan (already determined during macro planning)

**If NEXT_WEEK > 1** (Weekly progression):
- Previous week: `sce week` (actual volume, adherence)
- Recent weeks: `sce week --offset 1,2,3` (trend analysis)
- Adherence patterns: `sce analysis adherence --days 28` (last 4 weeks)
- Intensity distribution: `sce analysis intensity --days 28` (80/20 compliance)
- Volume progression: Based on recent trend, not just last week
- VDOT: Check for recalibration signals (race, breakthrough workout)

**Proceed to appropriate steps based on week type.**

---

### Step 1: Load Context from Master Plan

```bash
# Load master plan structure
MASTER_PLAN=$(cat data/plans/current_plan.yaml)
NEXT_WEEK_NUMBER=$((COMPLETED_WEEK + 1))

# Extract context for next week
sce plan show --week $NEXT_WEEK_NUMBER  # Shows phase, recovery status, target volume
```

**Context loaded**:
- `phase`: Current training phase (base/build/peak/taper)
- `is_recovery_week`: Whether next week is recovery week
- `target_volume_km`: Volume target from macro plan (REFERENCE only, not fixed)

**Note**: AI coach can adjust target_volume_km based on athlete response (it's a starting point, not a constraint).

---

### Step 2: Analyze Previous Week

```bash
# Get actual performance
PREV_ACTUAL=$(sce week | jq -r '.data.total_distance_km')
PREV_ADHERENCE=$(sce analysis adherence | jq -r '.data.adherence_rate')

# Get current metrics
CURRENT_ACWR=$(sce status | jq -r '.data.acwr.value')
CURRENT_TSB=$(sce status | jq -r '.data.tsb.value')
READINESS=$(sce status | jq -r '.data.readiness_score')
```

**Check for signals**:
- Illness/injury in activity notes?
- Poor adherence (<70%)?
- Elevated ACWR (>1.3)?
- Negative TSB (<-20)?

---

### Step 3: Propose Next Week Volume (AI Decision)

**Base calculation**:
```python
base_volume = prev_actual

# Phase progression
if phase == "base":
    progression_factor = 1.10  # 10% increase
elif phase == "build":
    progression_factor = 1.07  # 7% increase
elif phase == "peak":
    progression_factor = 1.02  # Hold volume
elif phase == "taper":
    progression_factor = 0.80  # 20% reduction

# Recovery week override
if is_recovery_week:
    progression_factor = 0.70  # 30% reduction

proposed_volume = base_volume * progression_factor
```

**Apply context adjustments**:
- **Illness/injury**: × 0.75 (25% reduction)
- **ACWR > 1.3**: × 0.85 (15% reduction)
- **Poor adherence (<70%)**: × 0.90 (10% reduction)

**Output**: `PROPOSED_VOLUME` for next week (AI-designed based on response).

---

### Step 4: Validate with Guardrails

```bash
sce guardrails analyze-progression \
  --previous $PREV_ACTUAL \
  --current $PROPOSED_VOLUME \
  --ctl $CURRENT_CTL \
  --run-days $MAX_RUN_DAYS \
  --age $AGE
```

**Returns**:
- `risk_factors`: Concerns (e.g., "Weekly increase >15%")
- `protective_factors`: Mitigations (e.g., "Low volume classification")
- `volume_classification`: low/medium/high context
- `pfitzinger_guideline`: Per-session analysis (1.6km rule)
- `coaching_considerations`: Methodology guidance

**Output**: Rich context for coaching decision (not pass/fail).

---

### Step 5: Interpret Guardrails & Finalize Volume

**Decision tree**:

1. **Risk factors dominate** → MODIFY: Reduce by 10-20%
2. **Protective factors dominate** → ACCEPT: Use as-is
3. **Mixed signals** → Apply methodology judgment (prefer safety)
4. **Pfitzinger guideline violated** → Reduce run frequency (4→3 runs)

**See**: [volume_progression_weekly.md](references/volume_progression_weekly.md) for detailed interpretation framework.

**Output**: `FINAL_VOLUME` for next week (AI decision informed by guardrails).

---

### Step 6: VDOT Determination/Recalibration

**For Week 1** (initial generation):
- Load `baseline_vdot` from macro plan (already determined during macro planning)
- Use baseline paces (no recalibration needed)
- Skip this step entirely for Week 1

**For Week 2+** (optional recalibration):

**Signals for VDOT adjustment**:

1. **Recent race (<7 days)**: `sce vdot calculate --race-type [TYPE] --time [TIME]`
2. **Breakthrough workout**: `sce vdot estimate-current --lookback-days 14`
3. **Every 4 weeks**: `sce vdot estimate-current --lookback-days 28`

**Decision**:
- New VDOT differs by ≥2 points → Update `current_vdot`
- <2 points → Keep current (avoid micro-adjustments)
- Communicate change: "Your fitness improved - updating paces!"
- Store in VDOT history: `{week: N, vdot: X, source: "race"/"estimate"}`

**Goal re-validation**: Only if VDOT changes significantly (±2 points). Most cases: skip, let race-preparation skill handle final check.

---

### Step 7: Create Workout Pattern JSON

**AI coach creates `workout_pattern` JSON manually** (same as Week 1 in training-plan-design).

**Tools to use**:

```bash
# Get training paces
sce vdot paces --vdot $CURRENT_VDOT

# Suggest run count (avoids minimum duration violations)
sce plan suggest-run-count --volume $FINAL_VOLUME --max-runs $MAX_RUNS --phase $PHASE

# Verify dates
sce dates week-boundaries --start <week_start_date>
```

**AI coach decides** (using training methodology):
- Workout composition: How many easy, tempo, interval runs?
- Run days: Which days (based on constraints, recovery)?
- Long run percentage: 40-55% depending on phase
- Paces: From VDOT calculation
- Structure: "2 easy + 1 tempo + 1 long"

**Example - Base Phase Week 5 (First Tempo)**:
```json
{
  "weeks": [{
    "week_number": 5,
    "phase": "base",
    "start_date": "2026-02-17",
    "end_date": "2026-02-23",
    "target_volume_km": 31.0,
    "is_recovery_week": false,
    "notes": "First tempo introduction",
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

**Key decisions**:
- Quality work progression: Tempo (week 5-6), intervals (week 8+), race pace (peak)
- Override guidance when needed: Remove quality if ACWR >1.3, illness, poor adherence
- Run days: Balance recovery, constraints, quality placement
- Long run %: Base=40-45%, Build/Peak=45-50%, Recovery=50-55%, Taper=35-40%

**Save to file**: `/tmp/weekly_plan_w${NEXT_WEEK_NUMBER}.json`

**See**: [json_workflow.md](references/json_workflow.md) for complete workout_pattern format.

---

### Step 8: Validate Plan

```bash
sce plan validate --file /tmp/weekly_plan_w${NEXT_WEEK_NUMBER}.json
```

**Checks**:
- Volume discrepancy <5%
- No minimum duration violations (easy ≥5km, long ≥8km)
- Quality volume within limits (T≤10%, I≤8%, R≤5%)
- Week-over-week progression acceptable
- Dates aligned (start=Monday, end=Sunday)

**If fails**: Adjust run count or regenerate. Never present unvalidated plan.

---

### Step 9: Present to Athlete

```markdown
## Next Week Plan (Week [N])

Based on [context], here's your Week [N] plan:

**Volume**: [X] km ([+/-Y]% from Week [N-1])
**Phase**: [Phase name]
**Start Date**: [YYYY-MM-DD] (Monday)

**Workouts**:
- **Tuesday**: [Type] ([X] km, pace: [range])
- **Thursday**: [Type] ([X] km, pace: [range])
- **Saturday**: [Type] ([X] km, pace: [range])
- **Sunday**: [Type] ([X] km, pace: [range])

**Why this plan**:
[1-2 sentences explaining rationale]
- [e.g., "Volume increased 13% based on strong adaptation (ACWR 1.1)"]
- [e.g., "Maintaining easy paces after 80/20 violation last week"]

**Approve this plan, or request changes?**
```

**Key elements**: Clear rationale, concrete numbers, explicit approval request.

---

### Step 10: Save Plan (ONLY After Approval)

**After athlete explicitly approves**:

```bash
sce plan populate --from-json /tmp/weekly_plan_w${NEXT_WEEK_NUMBER}.json

# Verify
sce plan show --week $NEXT_WEEK_NUMBER
sce today  # Should show first workout if today is in that week
```

**Confirm to athlete**:
```
Week [N] plan saved! View with:
- `sce today` - Today's workout
- `sce week` - Full week schedule
- `sce plan show` - All planned weeks
```

**If athlete requests changes**: Adjust → Regenerate (Step 7) → Re-present (Step 9) → Save when approved.

⛔ **NEVER save without explicit athlete approval**.

---

## Volume Design Guidelines

### Base Phase
- **Standard**: +8-12%/week
- **Recovery** (every 4th): 70%
- **Max increase**: 15% (strong justification needed)

### Build Phase
- **Standard**: +5-10%/week
- **Focus**: Quality over volume
- **Recovery**: 75%

### Peak Phase
- **Standard**: Hold volume (+0-5%)
- **Goal**: Maintain fitness without fatigue

### Taper Phase
- **Week 1**: -15-20%
- **Week 2**: -30-40%
- **Race week**: -50-60%

### Adjustment Factors
- **ACWR >1.3**: × 0.85 (-15%)
- **Illness recovery**: × 0.70-0.85 (severity-dependent)
- **Poor adherence**: Hold or reduce
- **Excellent adherence + low TSB**: Consider +5-10% bonus

---

## Quick Decision Trees

### Q: Should I reduce volume?

**YES (reduce 10-20%) if**:
- Adherence <70%
- ACWR >1.3
- Illness/injury detected
- Athlete explicitly requests

**NO (proceed with target) if**:
- Adherence >85%
- ACWR <1.2
- No injury/illness signals
- Readiness score >65

### Q: Should I recalibrate VDOT?

**YES if**:
- Recent race differs by 2+ points
- Breakthrough workout (2+ points higher)
- 4+ weeks since last update AND consistent improvements

**NO if**:
- <2 weeks since last update
- New estimate differs by <2 points
- Low confidence in estimate

### Q: Athlete disagrees - what now?

1. **Listen to concerns**:
   - "Too much volume" → Regenerate with × 0.9 adjustment
   - "Wrong days" → Update profile, regenerate
   - "Long run too long" → Update profile max_session_minutes, regenerate

2. **Use revert if saved**:
   ```bash
   sce plan revert-week --week $N
   # Regenerate with adjusted parameters
   ```

3. **Trust athlete's body awareness** - They know their capacity better than metrics.

---

## Quick Checklist

Before presenting:

- [ ] Loaded master plan context (phase, recovery status, target volume)
- [ ] Analyzed previous week (actual volume, adherence, ACWR, TSB, readiness)
- [ ] Proposed volume using phase progression + context adjustments
- [ ] Validated with guardrails (ran analyze-progression, interpreted output)
- [ ] Finalized volume (applied coaching judgment)
- [ ] Checked VDOT recalibration (if race result or breakthrough)
- [ ] Generated workouts (created workout_pattern JSON manually)
- [ ] Validated plan (ran `sce plan validate`, resolved violations)
- [ ] Presented clearly (rationale, numbers, approval request)
- [ ] Waited for approval

**Critical boundaries**:
- ⛔ DO NOT save without athlete approval
- ⛔ DO NOT skip validation
- ⛔ DO NOT ignore athlete feedback (if they say "too much", believe them)
- ⛔ DO NOT use pre-computed volumes (weekly volumes are AI-designed)

---

## Integration Notes

### Used After weekly-analysis Skill

Natural flow when athlete asks "How was my week?":
1. **weekly-analysis** runs (analyze completed week)
2. Coach asks: "Ready to plan next week?"
3. **weekly-planning** activates (this skill)
4. Seamless: analysis → planning

### Used During Initial Plan Creation

When designing training plan:
1. **training-plan-design** generates macro plan (16 weeks, volume targets)
2. Athlete approves macro structure
3. **weekly-planning** generates Week 1 detailed workouts
4. Week 1 saved, plan ready to start

### Used for Plan Adjustments

When athlete needs to adjust upcoming week:
1. Athlete: "Can we change next week's plan?"
2. **weekly-planning** activates
3. Generate with different parameters
4. Present and save after approval

---

## Additional Resources

- **Volume Progression Guide**: [volume_progression_weekly.md](references/volume_progression_weekly.md)
- **Workout Pattern Format**: [json_workflow.md](references/json_workflow.md)
- **Common Pitfalls**: [common_pitfalls_weekly.md](references/common_pitfalls_weekly.md)
- **Workout Generation**: [workout_generation.md](references/workout_generation.md)
- **Pace Zones**: [pace_zones.md](references/pace_zones.md)
- **Choosing Run Count**: [choosing_run_count.md](references/choosing_run_count.md)
- **Guardrails**: [guardrails_weekly.md](references/guardrails_weekly.md)
- **Multi-Sport Integration**: [multi_sport_weekly.md](references/multi_sport_weekly.md)
- **CLI Reference**: [docs/coaching/cli/cli_planning.md](../../../docs/coaching/cli/cli_planning.md)
- **Training Plan Design**: [training-plan-design/SKILL.md](../training-plan-design/SKILL.md)
- **Weekly Analysis**: [weekly-analysis/SKILL.md](../weekly-analysis/SKILL.md)
