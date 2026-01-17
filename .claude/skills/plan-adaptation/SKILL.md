---
name: plan-adaptation
description: Adapt training plans mid-cycle due to illness, injury, missed workouts, or schedule changes. Use when athlete reports "I got sick", "adjust my plan", "missed workouts", "schedule changed", "need to modify training", or when significant disruptions require replanning.
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Plan Adaptation

## Overview

This skill handles mid-cycle training plan adjustments due to:
- Illness (common cold, flu, fever, etc.)
- Injury (acute or chronic pain, recovery periods)
- Missed workouts (life events, travel, fatigue)
- Schedule changes (work, family, other sports)
- Training break return (after time off)

**Philosophy**: Adaptation is coaching. The best plan is one that responds to reality while maintaining long-term progression toward the goal.

---

## Core Workflow

### Step 0: Load Adaptation History

**Retrieve past illness/injury recovery patterns and adaptation preferences:**

```bash
sce memory search --query "illness injury recovery"
sce memory list --type CONTEXT
sce memory list --type PREFERENCE
```

**Apply retrieved patterns**:
- Reference past recovery timelines (e.g., "Last flu took 10 days to return to full volume")
- Acknowledge known constraints (e.g., "Work travel typically disrupts 1 week/month")
- Respect preferences (e.g., "Prefers maintaining frequency over volume")

### Step 1: Assess Current State

**Check metrics and plan status**:
```bash
sce status        # Current CTL/ATL/TSB/ACWR/readiness
sce week          # Recent training pattern
sce plan show     # Current plan structure
```

**Gather context**:
- What happened? (illness severity, injury location, missed workout count)
- Current week number?
- How many weeks to goal/race?
- What phase are they in? (base, build, peak, taper)

**Parse JSON responses** to understand:
- CTL trend: Has fitness dropped significantly?
- ACWR: Is there elevated injury risk from returning too aggressively?
- TSB: Is athlete overtrained or fresh?
- Plan structure: What workouts were missed? What's coming up?

---

### Step 2: Determine Adaptation Type

Based on the disruption, choose the appropriate adaptation strategy:

| Disruption Type | Duration | Adaptation Strategy | CLI Command |
|-----------------|----------|---------------------|-------------|
| **Single missed workout** | 1 day | No plan change, just skip or reschedule | None (advise only) |
| **Illness (mild)** | 2-4 days | Update current week only | `sce plan update-week` |
| **Illness (severe)** | 5-14 days | Replan from current week onward | `sce plan update-from` |
| **Injury (acute)** | 1-3 weeks | Replan with reduced volume/intensity | `sce plan update-from` |
| **Training break** | >14 days | Return-to-training protocol + replan | `sce guardrails break-return` + `update-from` |
| **Schedule change** | Ongoing | Update affected weeks only | `sce plan update-week` (multiple) |

---

### Step 3: Use Guardrails for Recovery Protocols

**Before modifying plan**, consult guardrails to determine safe return parameters:

#### Illness Recovery
```bash
sce guardrails illness-recovery --severity moderate --days-missed 7
```

**Returns**:
- `can_resume_immediately`: Boolean
- `recommended_easy_days`: Number of easy-only days before quality
- `volume_reduction_pct`: How much to reduce first week back
- `notes`: Symptoms to monitor (fever, fatigue, chest tightness)

**Severity levels**:
- `minor`: Sniffles, minor cold (above neck)
- `moderate`: Full cold, body aches, fatigue (no fever)
- `severe`: Flu, fever, significant fatigue

#### Injury Recovery
```bash
sce guardrails break-return --days 21 --ctl 44 --cross-training moderate
```

**Returns**:
- `recommended_start_volume_km`: Safe starting weekly volume
- `buildup_weeks`: Weeks to return to pre-injury volume
- `progression_rate_pct`: Safe weekly increase (usually 5-10%)
- `notes`: Red flags to monitor

**Cross-training levels**:
- `none`: Complete rest (more aggressive return needed)
- `light`: Yoga, walking (some fitness maintained)
- `moderate`: Swimming, cycling (cardiovascular fitness maintained)
- `high`: Running-equivalent cross-training (minimal fitness loss)

#### Race Recovery
```bash
sce guardrails race-recovery --distance half_marathon --age 52 --effort hard
```

**Returns**:
- `minimum_days`: Absolute minimum before running again
- `recommended_days`: Conservative return-to-training
- `recovery_schedule`: Day-by-day protocol
- `red_flags`: Warning signs (pain, excessive fatigue)

---

### Step 4: Choose Update Strategy

#### Strategy A: Single Week Update (`sce plan update-week`)

**Use when**:
- Disruption affects 1-2 weeks only
- Rest of plan remains valid
- Minor adjustments (reschedule workouts, reduce volume)

**Workflow**:
1. Read current plan: `sce plan show > /tmp/current_plan.json`
2. Extract week to modify: `jq '.weeks[] | select(.week_number == 5)' /tmp/current_plan.json`
3. Modify week structure (reduce volume, reschedule workouts, etc.)
4. Save modified week: `/tmp/week_5_updated.json` (single week object, not array)
5. Update: `sce plan update-week --week 5 --from-json /tmp/week_5_updated.json`

**Example JSON structure** (single week update):
```json
{
  "week_number": 5,
  "phase": "base",
  "start_date": "2026-02-10",
  "end_date": "2026-02-16",
  "target_volume_km": 18.0,
  "target_systemic_load_au": 126.0,
  "is_recovery_week": false,
  "notes": "Reduced volume due to illness recovery - easy runs only",
  "workouts": [
    {
      "id": "w5_tue_easy",
      "week_number": 5,
      "day_of_week": 1,
      "date": "2026-02-11",
      "workout_type": "easy",
      "phase": "base",
      "duration_minutes": 30,
      "distance_km": 6.0,
      "intensity_zone": "z2",
      "target_rpe": 3,
      "target_pace_per_km": "6:45",
      "purpose": "Post-illness easy return",
      "surface": "road"
    }
  ]
}
```

**CRITICAL**: JSON must be a single week object, NOT an array of weeks.

#### Strategy B: Partial Replan (`sce plan update-from`)

**Use when**:
- Disruption affects 3+ weeks
- Major changes to volume/intensity needed
- Phase transitions required (e.g., extend base, skip peak)

**Workflow**:
1. Determine starting week for replan (usually current week)
2. Calculate new periodization based on:
   - Weeks remaining to goal
   - Current CTL (post-disruption)
   - Recovery protocol recommendations
3. Design new weekly progression (see training-plan-design skill)
4. Validate guardrails
5. Save replanned weeks: `/tmp/weeks_5_to_16.json` (array of weeks starting from week N)
6. Update: `sce plan update-from --week 5 --from-json /tmp/weeks_5_to_16.json`

**Example JSON structure** (partial replan):
```json
{
  "weeks": [
    {
      "week_number": 5,
      "phase": "base",
      ...
    },
    {
      "week_number": 6,
      "phase": "base",
      ...
    },
    ...
    {
      "week_number": 16,
      "phase": "taper",
      ...
    }
  ]
}
```

**CRITICAL**:
- JSON must contain `"weeks"` array
- Preserves weeks 1 to N-1 (before starting week)
- Replaces weeks N to end

---

### Step 5: Present Adaptation Plan

**IMPORTANT**: Use markdown presentation pattern (same as training-plan-design).

**Create adaptation summary** (`/tmp/plan_adaptation_YYYY_MM_DD.md`):

```markdown
# Plan Adaptation: [Reason]

## Situation
- **Disruption**: [Illness/Injury/Schedule change]
- **Duration**: [Days missed or affected]
- **Impact on fitness**: CTL [before] → [after] ([change])
- **Current week**: Week [N] of [Total]
- **Weeks to goal**: [X] weeks

## Recovery Protocol

**Guardrails recommendation**:
- [Output from sce guardrails illness-recovery or break-return]
- Safe return volume: [X] km/week
- Easy-only period: [Y] days
- Buildup rate: [Z]% per week

## Adaptation Strategy

**Approach**: [Single week update / Partial replan]

**Changes**:
- Week [N]: [Description of changes]
- Week [N+1]: [Description of changes]
- [etc.]

**Updated periodization** (if partial replan):
- Base: Weeks [X-Y] ([Z] weeks)
- Build: Weeks [A-B] ([C] weeks)
- Peak: Weeks [D-E] ([F] weeks)
- Taper: Weeks [G-H] ([I] weeks)

## Updated Weekly Breakdown

### Week [N]: [Phase] - [Description]
**Volume**: [X] km ([% change] from original plan)
**Focus**: [Recovery / Return to training / Rebuild base]

**Workouts**:
- [Day]: [Workout description]
- [Day]: [Workout description]

[Repeat for affected weeks]

## Guardrails Check

✓ **ACWR Safety**: [Current ACWR], [Projected ACWR after return]
✓ **Volume Progression**: [% increase week-to-week]
✓ **Recovery Period**: [Days of easy running before quality]
✓ **Goal Feasibility**: [Still achievable / Adjusted expectations]

---

## Approval

Review the adapted plan and let me know:
1. **Approve** → I'll save changes to your plan
2. **Modify** → Tell me what to adjust
3. **Questions** → I'll explain any part in detail
```

**Present to athlete**:
- Summarize key changes
- Explain rationale (reference metrics, guardrails)
- Highlight trade-offs (if goal timing affected)
- Wait for approval before saving

---

### Step 6: Save Adapted Plan

**After approval**:
```bash
# Strategy A: Single week update
sce plan update-week --week 5 --from-json /tmp/week_5_updated.json

# Strategy B: Partial replan
sce plan update-from --week 5 --from-json /tmp/weeks_5_to_16.json
```

**Verify save**:
```bash
sce plan show | jq '.weeks[] | select(.week_number == 5)'
```

**Confirm with athlete**:
- "Plan updated successfully"
- "Week 5 now shows [new volume] km with [workout changes]"
- "Next workout: [description]"

---

## Decision Trees

For guidance on common decisions during plan adaptation, see [DECISION_TREES.md](references/DECISION_TREES.md):

- How severe is the illness? (Minor/Moderate/Severe)
- Can the goal still be achieved?
- Should quality workouts be reduced or eliminated?
- What if they miss a long run?
- What if schedule change is permanent?

---

## Common Adaptation Scenarios

See [ADAPTATION_SCENARIOS.md](examples/ADAPTATION_SCENARIOS.md) for 5 complete examples with CLI commands and JSON structures:

1. **Mild Illness** (3 days) - Single week update
2. **Severe Illness** (10 days, flu) - Partial replan
3. **Injury** (2 weeks off, knee pain) - Conservative buildup
4. **Training Break** (3 weeks vacation) - Major replan
5. **Missed Long Run** (Travel) - Rescheduling options

---

## Validation Checklist

Before saving any adapted plan, verify all criteria in [VALIDATION_CHECKLIST.md](references/VALIDATION_CHECKLIST.md):

- ✓ ACWR Safety (<1.3)
- ✓ Volume Progression (≤+10% per week)
- ✓ Recovery Protocol (adequate easy-only period)
- ✓ Goal Feasibility (still realistic)
- ✓ 80/20 Distribution (maintained)
- ✓ Multi-Sport Conflicts (respected)

---

## Key Principles

1. **Err on the side of caution**: Better to return slowly than risk re-injury or relapse
2. **Preserve long-term fitness**: Short-term setbacks are normal; focus on sustainable return
3. **Communicate trade-offs**: If goal timing affected, present options clearly
4. **Trust the data**: Use CTL/ACWR to guide decisions, not arbitrary timelines
5. **Monitor closely**: First 2 weeks after return are critical - watch for warning signs

---

### Step 6: Capture Adaptation Patterns

**After implementing adaptation, capture patterns for future reference:**

**When to capture**:
- Illness/injury recovery took specific duration
- Athlete reveals schedule constraint or preference
- Adaptation strategy worked particularly well or poorly

**Patterns to capture**:

1. **Recovery timelines**:
   ```bash
   sce memory add --type TRAINING_RESPONSE \
     --content "Returned to full training volume 10 days after flu, needed 14 days for intensity work" \
     --tags "illness:flu,recovery-time:10-days,intensity-delay:14-days" \
     --confidence high
   ```

2. **Schedule constraints**:
   ```bash
   sce memory add --type CONTEXT \
     --content "Work travel disrupts training first week of each month, prefers easy runs during travel" \
     --tags "schedule:travel,frequency:monthly,adaptation:easy-runs" \
     --confidence high
   ```

3. **Adaptation preferences**:
   ```bash
   sce memory add --type PREFERENCE \
     --content "Prefers maintaining 4 runs/week over total volume when time-constrained" \
     --tags "adaptation:frequency,constraint:time,priority:frequency-over-volume" \
     --confidence medium
   ```

4. **Injury recovery protocols that worked**:
   ```bash
   sce memory add --type INJURY_HISTORY \
     --content "Achilles issue resolved with 5 days off + 2 weeks easy-only, gradual return successful" \
     --tags "body:achilles,recovery:5-days-off,protocol:2-weeks-easy,status:resolved" \
     --confidence high
   ```

---

## Training Methodology References

**Illness Recovery**:
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md#illness-and-injury) - Pfitzinger's return-to-training protocols

**Injury Recovery**:
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md) - Conservative volume buildup after injury

**Training Break Return**:
- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md) - Rebuilding base after time off

**Complete methodology**:
- [Coaching Methodology](../../../docs/coaching/methodology.md#adaptation-triggers) - Adaptation trigger thresholds and decision frameworks

---

## Edge Cases

For unusual adaptation situations, see [EDGE_CASES.md](references/EDGE_CASES.md):

1. **Illness During Taper** - Race proximity decisions
2. **Injury During Peak Phase** - Goal feasibility assessment
3. **Multiple Disruptions** - When to regenerate vs. adapt
4. **Schedule Change Affects Key Long Run Day** - Permanent restructure

---

## Related Skills

- **training-plan-design**: Use for full plan regeneration if disruption too severe
- **daily-workout**: Use for day-to-day adaptation decisions during return period
- **injury-risk-management**: Use for proactive risk assessment during return
- **weekly-analysis**: Use to monitor return progress and validate recovery

---

## Additional Resources

**Decision support**:
- [Decision Trees](references/DECISION_TREES.md) - Common scenario guidance
- [Edge Cases](references/EDGE_CASES.md) - Handling unusual situations

**Reference material**:
- [CLI Reference](references/CLI_REFERENCE.md) - Command quick reference
- [Validation Checklist](references/VALIDATION_CHECKLIST.md) - Pre-save verification

**Examples**:
- [Adaptation Scenarios](examples/ADAPTATION_SCENARIOS.md) - 5 complete examples

**Templates**:
- [Adaptation Plan Template](templates/adaptation_plan.md) - Structured output format

**Training methodology**:
- [Pfitzinger's Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md)
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md)
- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md)
- [Coaching Methodology](../../../docs/coaching/methodology.md#adaptation-triggers)
