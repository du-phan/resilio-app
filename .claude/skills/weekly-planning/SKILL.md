# Weekly Planning: Generate Next Week's Workouts

## Overview

Generate detailed workouts for the next week of training using **progressive disclosure** workflow. Each week is tailored based on actual training response, enabling true adaptive planning.

**Core Philosophy**: Plan 1 week at a time (not 4 weeks in advance) to maximize adaptability and minimize LLM errors.

**This skill handles**:
- Checking macro plan for next week's targets
- Assessing volume adjustments (illness, fatigue, ACWR)
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
- ✅ **Macro plan exists** - 16-week structure with phase/volume targets (`data/plans/current_plan_macro.json`)
- ✅ **Current week completed** (if generating week N+1) - Athlete has finished week N
- ✅ **Weekly analysis done** (optional but recommended) - Informs volume adjustment decisions
- ✅ **Profile constraints current** - Run days, available days, max session duration

---

## Workflow

### Step 1: Check Macro Plan for Next Week

```bash
# Get next week's macro plan targets
sce plan show --format json | jq '.weeks[] | select(.week_number == [NEXT_WEEK])'
```

**Extract**:
- `target_volume_km`: Next week's mileage target
- `phase`: Current training phase (base/build/peak/taper)
- `is_recovery_week`: Whether next week is a recovery week

**Context to consider**:
- Previous week's adherence, adaptation, patterns (from weekly-analysis if available)
- Current CTL/ACWR trajectory
- Any concerning triggers (fatigue, injury signals, illness)

### Step 2: Assess Volume Adjustment Needs

**Decision tree**:

1. **If previous week had illness or injury**:
   ```bash
   sce guardrails illness-recovery --severity [mild/moderate/severe] --days-since 7
   # Returns: recommended_volume_pct (e.g., 0.7 = 70% of planned)
   ```
   Apply adjustment: `ADJUSTED_VOLUME = target_volume_km * recommended_volume_pct`

2. **If ACWR >1.3 (elevated injury risk)**:
   - Recommend maintaining current volume (no increase)
   - Or reduce by 10-15% if ACWR >1.4
   - Use: `sce guardrails progression --previous [PREV_VOL] --current [NEXT_VOL]`

3. **If previous week adherence <70% (missed workouts)**:
   - Consider reducing next week's volume by 10-20%
   - OR maintain volume but reduce run frequency (e.g., 4 runs → 3 runs)
   - Rationale: Athlete needs more recovery or has schedule constraints

4. **If all green lights** (good adherence, ACWR <1.2, no issues):
   - Proceed with macro plan target as-is
   - No adjustment needed (volume_adjustment = 1.0)

**Output**: `FINAL_VOLUME` for next week (may differ from macro plan if adjustments needed)

### Step 3: Check for VDOT Recalibration

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

### Step 4: Generate Next Week's Workouts

**Run**:
```bash
NEXT_WEEK_NUMBER=$((COMPLETED_WEEK + 1))

sce plan generate-week \
  --week-number $NEXT_WEEK_NUMBER \
  --from-macro data/plans/current_plan_macro.json \
  --current-vdot $CURRENT_VDOT \
  --volume-adjustment $VOLUME_ADJUSTMENT_PCT \
  > /tmp/weekly_plan_w${NEXT_WEEK_NUMBER}.json
```

**Parameters**:
- `--week-number`: Next week to generate (e.g., 2, 3, 4)
- `--from-macro`: Path to macro plan with phase/volume targets
- `--current-vdot`: VDOT for pace calculations (potentially updated in Step 3)
- `--volume-adjustment`: Optional multiplier if reducing volume (e.g., 0.85 = 85%)

**System generates**:
- Intent-based JSON with `workout_pattern`
- Exact distances calculated to match `FINAL_VOLUME`
- Paces from `CURRENT_VDOT`
- Workout structure appropriate for phase (base: easy runs, build: + tempo/intervals)

### Step 5: Validate Next Week's Plan

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

### Step 6: Present Next Week's Plan to Athlete

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

### Step 7: Save Next Week's Plan (ONLY After Approval)

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

- [ ] **Checked macro plan** - Extracted `target_volume_km`, `phase`, `is_recovery_week`
- [ ] **Assessed volume adjustment** - Considered adherence, ACWR, illness/injury signals
- [ ] **Checked VDOT recalibration** - Updated if race result or breakthrough workout
- [ ] **Generated workouts** - Used `sce plan generate-week` with correct parameters
- [ ] **Validated plan** - Ran `sce plan validate-week`, resolved all critical violations
- [ ] **Presented clearly** - Included rationale, concrete numbers, approval request
- [ ] **Waited for approval** - Did NOT save until athlete explicitly approved

Critical boundaries:
- ⛔ **DO NOT save plan without athlete approval** - Always wait for explicit consent
- ⛔ **DO NOT skip validation** - Catches errors before presenting to athlete
- ⛔ **DO NOT ignore athlete feedback** - If they say "too much", believe them and adjust

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
