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
- Illness (cold, flu, fever)
- Injury (acute or chronic pain, recovery periods)
- Missed workouts (life events, travel, fatigue)
- Schedule changes (work, family, other sports)
- Training break return (after time off)

**Philosophy**: Adaptation is coaching. The best plan responds to reality while maintaining long-term progression toward the goal.

**Date Handling**: All weeks must follow Monday-Sunday structure. The core system enforces this constraint.

---

## Core Workflow

### Step 0: Load Adaptation History

```bash
sce memory search --query "illness injury recovery"
sce memory list --type CONTEXT
sce memory list --type PREFERENCE
```

**Apply retrieved patterns**:
- Reference past recovery timelines
- Acknowledge known constraints
- Respect preferences

### Step 1: Assess Current State

```bash
sce status        # Current CTL/ATL/TSB/ACWR/readiness
sce week          # Recent training pattern
sce plan show     # Current plan structure
```

**Gather context**:
- What happened? (severity, duration, impact)
- Current week number?
- Weeks to goal/race?
- Training phase? (base, build, peak, taper)

---

### Step 2: Determine Adaptation Type

| Disruption | Duration | Strategy | CLI Command |
|-----------|----------|----------|-------------|
| **Single missed workout** | 1 day | No plan change, advise only | None |
| **Illness (mild)** | 2-4 days | Update current week | `sce plan update-week` |
| **Illness (severe)** | 5-14 days | Replan from current week | `sce plan update-from` |
| **Injury (acute)** | 1-3 weeks | Replan with reduced load | `sce plan update-from` |
| **Training break** | >14 days | Return protocol + replan | `sce guardrails break-return` + `update-from` |
| **Schedule change** | Ongoing | Update affected weeks | `sce plan update-week` (multiple) |

---

### Step 3: Use Guardrails for Recovery Protocols

**Before modifying plan**, consult guardrails:

#### Illness Recovery
```bash
sce guardrails illness-recovery --severity moderate --days-missed 7
```

**Returns**: `can_resume_immediately`, `recommended_easy_days`, `volume_reduction_pct`, `notes`

**Severity levels**: `minor` (above neck), `moderate` (full cold, no fever), `severe` (flu, fever)

#### Injury Recovery
```bash
sce guardrails break-return --days 21 --ctl 44 --cross-training moderate
```

**Returns**: `recommended_start_volume_km`, `buildup_weeks`, `progression_rate_pct`, `notes`

**Cross-training levels**: `none`, `light`, `moderate`, `high`

#### Race Recovery
```bash
sce guardrails race-recovery --distance half_marathon --age 52 --effort hard
```

**Returns**: `minimum_days`, `recommended_days`, `recovery_schedule`, `red_flags`

**For complete guardrails reference**: See [references/cli_reference.md](references/cli_reference.md)

---

### Date Validation (CRITICAL)

**See "Date Handling Rules" section in CLAUDE.md for complete guidance.**

**Before modifying any week**, verify Monday-Sunday alignment using CLI commands:

```bash
# Check plan week dates
sce plan show | jq '.data.weeks[] | {week: .week_number, start: .start_date, end: .end_date}'

# Verify each week start is Monday
sce dates validate --date 2026-01-20 --must-be monday  # Returns: {"valid": true/false}
sce dates validate --date 2026-01-27 --must-be monday
# ... for each week

# Verify each week end is Sunday
sce dates validate --date 2026-01-26 --must-be sunday
sce dates validate --date 2026-02-01 --must-be sunday
# ... for each week
```

**When creating modified week JSON**:
- `start_date` MUST be Monday (weekday() == 0)
- `end_date` MUST be Sunday (weekday() == 6)
- **Current/past weeks**: Keep existing dates unchanged
- **Future weeks**: Use `sce dates next-monday` or `sce dates week-boundaries` for alignment
- **Always validate** before saving: `sce dates validate --date <date> --must-be monday`

---

### Step 4: Choose Update Strategy

#### Strategy A: Single Week Update (`sce plan update-week`)

**Use when**: Disruption affects 1-2 weeks only

**Workflow**:
1. Read plan: `sce plan show > /tmp/current_plan.json`
2. Extract week: `jq '.weeks[] | select(.week_number == 5)' /tmp/current_plan.json`
3. Modify workouts (reduce volume, reschedule, etc.)
4. Save: `/tmp/week_5_updated.json` (single week object, NOT array)
5. Update: `sce plan update-week --week 5 --from-json /tmp/week_5_updated.json`

**JSON must be single week object**, not array.

#### Strategy B: Partial Replan (`sce plan update-from`)

**Use when**: Disruption affects 3+ weeks, major changes needed

**Workflow**:
1. Determine starting week for replan
2. Calculate new periodization (weeks remaining, current CTL, recovery protocol)
3. Design new weekly progression
4. Validate guardrails
5. Save: `/tmp/weeks_5_to_16.json` (array of weeks)
6. Update: `sce plan update-from --week 5 --from-json /tmp/weeks_5_to_16.json`

**For complete JSON schemas and examples**: See [references/cli_reference.md](references/cli_reference.md)

---

### Step 5: Validate Adapted Plan

```bash
sce validation validate-plan --plan-file /tmp/adapted_plan.json
```

**Checks**:
- Date alignment (Monday-Sunday)
- Volume progression (10% rule)
- Quality volume limits (Daniels' T/I/R)
- Recovery week placement
- Load progression (CTL increase rate)

**For complete validation checklist**: See [references/validation_checklist.md](references/validation_checklist.md)

---

### Step 6: Present Adaptation Plan

**Create adaptation document** using template at [templates/adaptation_plan.md](templates/adaptation_plan.md).

**Structure**:
1. **Disruption Summary**: What happened, duration, impact
2. **Adaptation Strategy**: Which approach (update-week vs update-from)
3. **Modified Weeks**: Table showing old vs new structure
4. **Rationale**: Why these changes (guardrails, recovery protocol)
5. **Next Steps**: Monitoring, warnings, adjustment triggers

**Present to athlete**:
- Explain "why" behind changes
- Show trade-offs made (e.g., extend base phase to preserve fitness)
- Provide clear return-to-training protocol
- Build confidence that goal is still achievable (or adjust goal if needed)

---

### Step 7: Capture Adaptation as Memory

**After implementing adaptation, store pattern for future reference:**

```bash
# Illness recovery pattern
sce memory add --type CONTEXT \
  --content "Moderate flu took 10 days to return to full volume - 3 easy days, then gradual buildup" \
  --tags "illness:flu,recovery:10-days,protocol:gradual" \
  --confidence high

# Preference
sce memory add --type PREFERENCE \
  --content "Prefers maintaining frequency over volume during recovery" \
  --tags "recovery:preference,frequency:maintain,volume:flex" \
  --confidence high
```

---

## Quick Decision Trees

### Q: Single missed workout - reschedule or skip?
- **Quality workout** (tempo, intervals): Reschedule to next available day if <3 days to next quality
- **Easy run**: Skip, not worth disrupting rest of week
- **Long run**: Reschedule to weekend if possible, otherwise shorten next long run

### Q: Illness severity - minor vs moderate vs severe?
- **Minor** (above neck): Can run easy if feeling up to it, resume quality after 2-3 days
- **Moderate** (full cold, no fever): 3-5 days off, return with easy runs only for 2-3 days
- **Severe** (fever, flu): 7-14 days off, guardrails protocol for return, replan from current week

**Use "neck check" rule**: Symptoms above neck (runny nose, sore throat) = can run easy. Below neck (chest congestion, body aches, fever) = rest.

### Q: How many weeks to replan?
- **<3 weeks to goal**: Adjust remaining weeks, focus on maintaining fitness
- **3-8 weeks to goal**: Replan from current week, compress peak phase if needed
- **>8 weeks to goal**: Replan with adjusted periodization, goal likely still achievable

### Q: Should goal be adjusted?
- **Fitness loss <10%** (CTL drop <5 points): Goal likely still achievable
- **Fitness loss 10-20%** (CTL drop 5-10 points): Adjust goal time by 2-5%
- **Fitness loss >20%** (CTL drop >10 points): Consider postponing race or adjusting to "finish comfortably"

**For complete decision trees**: See [references/decision_trees.md](references/decision_trees.md)

---

## Common Adaptation Scenarios

See [examples/ADAPTATION_SCENARIOS.md](examples/ADAPTATION_SCENARIOS.md) for complete worked examples:

1. **Mild Cold (Week 5)** - 3 days off, single week update
2. **Moderate Flu (Week 7)** - 10 days off, partial replan
3. **Work Travel (Weeks 8-10)** - Schedule change, multi-week update
4. **Minor Injury (Week 9)** - 2 weeks reduced volume, partial replan
5. **Training Break (21 days)** - Return-to-training protocol + full replan

---

## Edge Cases

See [references/edge_cases.md](references/edge_cases.md) for guidance on:

1. **Multiple disruptions** - Compounding issues (illness + injury + schedule)
2. **Taper disruption** - Illness/injury during taper (7-14 days before race)
3. **Race-week illness** - DNS decision tree (fever rule, gut check)
4. **Chronic injury** - Persistent pain requiring ongoing accommodation
5. **Goal no longer achievable** - Honest conversation about alternatives

---

## Additional Resources

**Decision support**:
- [Decision Trees](references/decision_trees.md) - Common adaptation decisions
- [Edge Cases](references/edge_cases.md) - Unusual situations

**Reference material**:
- [CLI Reference](references/cli_reference.md) - Complete command documentation
- [Validation Checklist](references/validation_checklist.md) - Pre-update verification

**Templates**:
- [Adaptation Plan Template](templates/adaptation_plan.md) - Structured output format

**Examples**:
- [Adaptation Scenarios](examples/ADAPTATION_SCENARIOS.md) - 5 complete worked examples

**Training methodology**:
- [Pfitzinger Adaptation Principles](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md) - Illness/injury guidance
- [Coaching Methodology - Guardrails](../../../docs/coaching/methodology.md#guardrails) - Complete guardrails system

---

## Related Skills

- **training-plan-design**: Referenced for periodization logic
- **injury-risk-management**: Consulted for injury-related adaptations
- **weekly-analysis**: Used to understand adaptation effectiveness
- **race-preparation**: Handles taper-specific adaptations
