---
name: monthly-transition
description: Adapt training plans mid-cycle by assessing completed monthly blocks (4 weeks) and generating next month based on actual response. Analyzes adherence, CTL progression, VDOT recalibration signals, and volume tolerance. Use when athlete completes a 4-week block, asks "how was my month?", "generate next month", or when approaching end of current monthly cycle.
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Monthly Transition

## Overview

This skill handles monthly training cycles for progressive disclosure planning:
- **Assess completed month** (4 weeks): Adherence, CTL progression, VDOT signals, injury/illness detection
- **Recalibrate training parameters**: Update VDOT if quality sessions struggled (<85% completion)
- **Generate next month**: 4 weeks of detailed workouts based on actual response
- **Enable adaptation**: Adjust volumes, paces, and structure based on athlete's tolerance

**Workflow**: Assess month → Review with athlete → Recalibrate if needed → Generate next month → Validate → Present → Save

**For initial plan creation**: Use the `training-plan-design` skill (generates macro plan + first month)

---

## Workflow

### Step 1: Assess Completed Month

Analyze how the athlete responded to the past 4 weeks of training.

**Gather completed activities**:
```bash
# Get activities from the past month
sce sync  # Ensure latest data from Strava

# Export completed activities for assessment
sce activity list --since 30d --has-notes > /tmp/completed_activities.json
```

**Retrieve planned workouts**:
```bash
# Get the planned workouts from current monthly plan
# These were saved when the monthly plan was generated
cp data/plans/current_monthly_plan.json /tmp/planned_workouts.json
```

**Get current metrics**:
```bash
# Get CTL progression
STARTING_CTL=44.0  # From beginning of the month (stored in macro plan)
CURRENT_CTL=$(sce status | jq -r '.data.ctl.value')
TARGET_CTL=52.0    # From macro plan for this milestone

# Get current VDOT
CURRENT_VDOT=$(sce profile get | jq -r '.data.vdot // 48')
```

**Run assessment**:
```bash
sce plan assess-month \
  --month-number 1 \
  --week-numbers "1,2,3,4" \
  --planned-workouts /tmp/planned_workouts.json \
  --completed-activities /tmp/completed_activities.json \
  --starting-ctl $STARTING_CTL \
  --ending-ctl $CURRENT_CTL \
  --target-ctl $TARGET_CTL \
  --current-vdot $CURRENT_VDOT \
  > /tmp/month_1_assessment.json
```

**Assessment analyzes**:
- **Adherence**: Planned vs. actual completion rate
- **CTL progression**: Whether athlete achieved target (within 5% = on track)
- **VDOT recalibration signals**: Quality session completion <85% suggests paces too fast
- **Injury/illness detection**: Keywords in notes ("pain", "injury", "sick", "tired")
- **Volume tolerance**: Whether athlete handled the load well

---

### Step 2: Review Assessment with Athlete

Present the assessment findings and discuss implications for next month.

**Extract key findings**:
```bash
# Parse assessment results
ADHERENCE=$(jq -r '.data.adherence.completion_rate_pct' /tmp/month_1_assessment.json)
CTL_STATUS=$(jq -r '.data.ctl_progression.status' /tmp/month_1_assessment.json)
NEEDS_VDOT=$(jq -r '.data.vdot_recalibration.needs_recalibration' /tmp/month_1_assessment.json)
INJURY_SIGNALS=$(jq -r '.data.injury_illness_signals.detected' /tmp/month_1_assessment.json)
RECOMMENDATIONS=$(jq -r '.data.recommendations[]' /tmp/month_1_assessment.json)
```

**Present to athlete**:
```
📊 Month 1 Assessment Complete

**Adherence**: ${ADHERENCE}% (${STATUS})
**CTL Progression**: ${CTL_STATUS} (target 52, achieved ${CURRENT_CTL})
**VDOT Recalibration**: ${NEEDS_VDOT ? "Needed" : "Not needed"}
**Injury/Illness Signals**: ${INJURY_SIGNALS ? "Detected" : "None"}

**Recommendations**:
${RECOMMENDATIONS}

Ready to generate month 2 (weeks 5-8)?
```

**Decision points**:
- If adherence <70%: Discuss barriers, adjust next month structure
- If CTL significantly off target (>10%): Adjust next month volumes
- If injury signals: Review injury history, consider reducing load
- If VDOT recalibration needed: Proceed to Step 3

---

### Step 3: Recalibrate Training Parameters (If Needed)

Update VDOT and training paces if quality sessions indicate paces were off.

**When to recalibrate**:
- Quality session completion <85% (struggled with prescribed paces)
- Athlete reports paces felt too hard/easy consistently
- Recent race result suggests fitness change

**Calculate new VDOT**:
```bash
# Option A: From recent tempo run
# If athlete completed a tempo run, calculate VDOT from actual pace
sce vdot calculate --race-type 10k --time 42:30

# Option B: From recent race
sce vdot calculate --race-type half_marathon --time 01:35:00

# Option C: Adjust current VDOT manually
# If paces felt too hard, reduce by 1-2 points
# If paces felt too easy, increase by 1-2 points
NEW_VDOT=49  # Example: upgraded from 48
```

**Update profile**:
```bash
sce profile set --vdot $NEW_VDOT
```

**Get new training paces**:
```bash
sce vdot paces --vdot $NEW_VDOT
# Returns: E-pace, M-pace, T-pace, I-pace, R-pace for next month
```

**Document recalibration**:
```bash
# Add memory for future reference
sce memory add --type TRAINING_RESPONSE \
  --content "VDOT recalibrated from 48 to 49 after month 1: tempo runs felt appropriate but long M-pace sections were completed faster than prescribed" \
  --tags "vdot:recalibration,phase:base,month:1" \
  --confidence high
```

---

### Step 4: Generate Next Monthly Plan

Generate detailed workouts for the next 4 weeks based on assessment and macro plan targets.

**Retrieve macro plan targets**:
```bash
# Get volume targets for next month from macro plan
MACRO_PLAN=/tmp/macro_plan.json  # Or data/plans/current_plan_macro.json
jq '.volume_trajectory[] | select(.week >= 5 and .week <= 8)' $MACRO_PLAN > /tmp/macro_targets_weeks_5_8.json
```

**Determine adjusted starting point**:
```bash
# Based on assessment, adjust volumes if needed
if [ "$CTL_STATUS" = "below_target" ]; then
  # If CTL is lagging, slightly reduce next month volumes (5-10%)
  VOLUME_ADJUSTMENT=0.95
elif [ "$INJURY_SIGNALS" = "true" ]; then
  # If injury signals, reduce volumes (10-15%)
  VOLUME_ADJUSTMENT=0.90
else
  # On track, continue as planned
  VOLUME_ADJUSTMENT=1.0
fi
```

**Generate monthly plan**:
```bash
# Get current VDOT (potentially recalibrated in Step 3)
CURRENT_VDOT=$(sce profile get | jq -r '.data.vdot')

# Generate month 2 (weeks 5-8)
sce plan generate-month \
  --month 2 \
  --weeks "5,6,7,8" \
  --from-macro $MACRO_PLAN \
  --current-vdot $CURRENT_VDOT \
  --profile data/athlete/profile.yaml \
  --volume-adjustment $VOLUME_ADJUSTMENT \
  > /tmp/monthly_plan_m2.json
```

**What it generates**:
- 4 weeks of detailed workouts (weeks 5-8)
- Updated paces from recalibrated VDOT
- Adjusted volumes based on tolerance assessment
- Continued multi-sport integration
- Phase-appropriate focus (if transitioning base → build)

**Date verification for generated weeks**:
```bash
# Verify all week start dates are Monday (see "Date Handling Rules" in CLAUDE.md)
sce dates validate --date <week_5_start> --must-be monday
sce dates validate --date <week_6_start> --must-be monday
sce dates validate --date <week_7_start> --must-be monday
sce dates validate --date <week_8_start> --must-be monday

# Get next month's week boundaries if needed
sce dates week-boundaries --start <week_5_monday>
```

---

### Step 5: Validate, Present, and Save

Validate the new monthly plan, present to athlete, and save after approval.

**Validate monthly plan**:
```bash
sce plan validate-month \
  --monthly-plan /tmp/monthly_plan_m2.json \
  --macro-targets /tmp/macro_targets_weeks_5_8.json \
  > /tmp/validation_m2.json

# Check for violations
OVERALL_OK=$(jq -r '.data.overall_ok' /tmp/validation_m2.json)
CRITICAL_ISSUES=$(jq -r '.data.summary.critical_issues' /tmp/validation_m2.json)

if [ "$OVERALL_OK" = "false" ] || [ "$CRITICAL_ISSUES" -gt 0 ]; then
  echo "❌ Validation failed with critical issues - regenerate required"
  # Review violations and return to Step 4
else
  echo "✓ Validation passed - ready to present"
fi
```

**Create review document**:
Use the template at `templates/monthly_review.md` to create a comprehensive review document.

```bash
# Copy template and fill in month 2 details
cp .claude/skills/monthly-transition/templates/monthly_review.md /tmp/training_plan_month_2_review.md

# Fill in the template with:
# - Assessment summary from month 1 (adherence, CTL, VDOT, signals)
# - Week-by-week performance data
# - Next month plan details (weeks 5-8 from monthly_plan_m2.json)
# - Changes from previous month
# - Coaching recommendations
```

**Template includes sections for**:
- Assessment summary (adherence, CTL progression, VDOT, injury/illness signals)
- Completed month performance (week-by-week breakdown, load analysis, multi-sport balance)
- Next month plan (weeks 5-8 structure, volume progression, workout details)
- Changes from previous month (volume, pace zones, phase, workout focus)
- Recommendations (training guidance, injury prevention, multi-sport balance)

**Present to athlete**:
```
📋 Month 2 Plan Ready (Weeks 5-8)

Based on your month 1 performance:
- Adherence ${ADHERENCE}%: ${STATUS}
- CTL progression: ${CTL_STATUS}
- VDOT: ${CURRENT_VDOT} ${NEEDS_VDOT ? "(recalibrated +1)" : ""}

Review: /tmp/training_plan_month_2_review.md

Key changes:
- [Volume adjustments if any]
- [Pace zone changes if VDOT recalibrated]
- [Phase transition if applicable: base → build]

Approve, request changes, or ask questions?
```

**Save after approval**:
```bash
# Update current monthly plan
cp /tmp/monthly_plan_m2.json data/plans/current_monthly_plan.json

# Populate workouts for weeks 5-8
sce plan populate --from-json /tmp/monthly_plan_m2.json

# Save review document
sce plan save-review --from-file /tmp/training_plan_month_2_review.md --approved

# Verify saved
sce plan week --week 5  # Check next week's plan
```

**Continue monthly cycles**:
- Repeat this workflow every 4 weeks
- Month 3 (weeks 9-12): Assess month 2 → Generate weeks 9-12
- Month 4 (weeks 13-16): Assess month 3 → Generate weeks 13-16 (peak + taper)

---

## Decision Trees

### Q: Adherence was low (<70%) - What to adjust?

**Analyze missed workouts**:
```bash
jq '.data.adherence.missed_workouts[]' /tmp/month_1_assessment.json
```

**Common patterns**:
1. **Missed easy runs**: Often life/schedule conflicts → No adjustment needed, continue
2. **Missed quality sessions**: Fatigue or scheduling → Reduce frequency next month (3 quality → 2 quality)
3. **Missed long runs**: Time constraints → Reduce long run duration next month

**Recommendation**: Address root cause, not just reduce volume blindly

### Q: CTL significantly below target (>10% gap)

**Scenario**: Target CTL 52, achieved 46 (-6 points, 11.5% below)

**Options**:
1. **Extend current phase** (+2-3 weeks): Stay in base longer, shift timeline
2. **Increase next month gradually** (+10% per week): Catch up slowly
3. **Accept lower peak**: Adjust macro plan expectations

**Recommendation**: Option 1 if >4 weeks to race, Option 3 if <4 weeks to race

### Q: Injury signals detected - How cautious to be?

**Severity assessment**:
```bash
# Check which activities mentioned injury keywords
jq '.data.injury_illness_signals.affected_workouts[]' /tmp/month_1_assessment.json
```

**Action based on severity**:
- **One-time mention** ("slight soreness"): Continue, monitor closely
- **Multiple mentions same area** ("knee pain" 3+ times): Reduce volume 15%, add memory
- **Escalating severity** ("pain" → "sharp pain"): Pause, consult plan-adaptation skill

**Always**:
- Add injury memory with trigger thresholds
- Reduce next month volume 10-15%
- Flag for monitoring in future monthly transitions

### Q: VDOT seems wrong - Trust assessment or athlete feel?

**Assessment says no recalibration needed, but athlete reports paces felt off**

**Trust athlete perception IF**:
- Consistent feedback across multiple quality sessions
- Not conflating effort with pace (E-pace should feel easy, T-pace hard)
- Environmental factors ruled out (heat, altitude, hills)

**Recommendation**:
- Small adjustment (±1 VDOT point) and monitor next month
- Larger adjustments (±2-3 points) only with race result validation

---

## Integration with Training-Plan-Design Skill

This skill handles **monthly cycles** for an existing macro plan. For **initial plan creation**, use `training-plan-design` which:
- Generates the macro plan (16-week structure)
- Creates the first month (weeks 1-4)
- Establishes baseline VDOT and paces

**Handoff point**: After training-plan-design saves first month → monthly-transition takes over for months 2-4

---

## Links to References

**CLI commands used**:
- `sce plan assess-month` - [Planning Commands](../../docs/coaching/cli/cli_planning.md#sce-plan-assess-month)
- `sce plan generate-month` - [Planning Commands](../../docs/coaching/cli/cli_planning.md#sce-plan-generate-month)
- `sce plan validate-month` - [Validation Commands](../../docs/coaching/cli/cli_validation.md#sce-plan-validate-month)

**Training methodology**:
- [VDOT Recalibration](../training-plan-design/references/pace_zones.md)
- [Volume Progression](../training-plan-design/references/volume_progression.md)
- [Injury History Management](../../docs/coaching/methodology.md)

**Related skills**:
- `training-plan-design` - Initial macro + first month creation
- `plan-adaptation` - Mid-cycle adjustments for illness/injury (not scheduled monthly transitions)
