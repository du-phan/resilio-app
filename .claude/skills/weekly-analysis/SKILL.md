---
name: weekly-analysis
description: Comprehensive weekly training review including adherence analysis, intensity distribution validation (80/20), multi-sport load breakdown, and pattern detection. Use when athlete asks "how was my week?", "weekly review", "analyze training", or "did I follow the plan?".
allowed-tools: Bash, Read, Write
---

# Weekly Analysis: Comprehensive Training Review

## Overview

This skill provides complete weekly training analysis by:
1. Comparing planned vs. actual training (adherence)
2. Validating intensity distribution (80/20 rule)
3. Analyzing multi-sport load breakdown
4. Detecting patterns and suggesting adaptations

**Key principle**: Use computational tools to calculate metrics; apply coaching judgment to interpret patterns.

---

## Workflow

### Step 1: Get Weekly Summary

```bash
sce week
```

**Parse key data**:
- Total planned vs. completed workouts
- Running volume vs. other activities
- CTL/ATL/TSB/ACWR/readiness changes

### Step 2: Adherence Analysis

```bash
sce analysis adherence --week [WEEK_NUMBER] --planned [PLAN_FILE] --completed [ACTIVITIES_FILE]
```

**Returns**:
- `completion_rate`: 0-100%
- `workout_type_adherence`: Breakdown by type (easy, tempo, long, intervals)
- `missed_workouts`: List with reasons
- `patterns`: Detected trends

**Interpretation zones**:
- ≥90%: Excellent adherence
- 70-89%: Good, minor adjustments needed
- 50-69%: Fair, discuss barriers
- <50%: Poor, major replanning needed

### Step 3: Intensity Distribution Analysis

```bash
sce analysis intensity --activities [ACTIVITIES_FILE] --days 7
```

**Returns**:
- `distribution`: % breakdown (low vs. moderate+high intensity)
- `compliance`: Meets 80/20 guideline?
- `polarization_score`: 0-100 (separation of easy from hard)
- `violations`: Specific issues

**Quick interpretation**:
- ≥75% low intensity: Compliant ✅
- 60-74% low intensity: Moderate-intensity rut ⚠️
- <60% low intensity: Severe imbalance ❌

**For detailed 80/20 philosophy and violation handling**: See [references/intensity_guidelines.md](references/intensity_guidelines.md)

### Step 4: Multi-Sport Load Breakdown

```bash
sce analysis load --activities [ACTIVITIES_FILE] --days 7 --priority [PRIORITY]
```

**Returns**:
- `systemic_load_by_sport`: Cardio/whole-body load by activity
- `lower_body_load_by_sport`: Leg strain breakdown
- `priority_adherence`: How well schedule respected running priority
- `fatigue_flags`: Warning signals

**Quick zones** (for running PRIMARY):
- 60-70% running load: Good
- 50-60%: Fair
- <50%: Concerning

**For complete multi-sport load model and conflict handling**: See [references/multi_sport_balance.md](references/multi_sport_balance.md)

### Step 5: Pattern Detection

**Review activity notes for qualitative signals**:
```bash
# List activities with notes
sce activity list --since 7d --has-notes

# Search for wellness signals
sce activity search --query "tired fatigue flat heavy" --since 7d

# Search for pain/discomfort
sce activity search --query "pain sore tight discomfort" --since 7d
```

**Patterns to identify**:
1. **Consistency**: Completed all weekday runs, skipped weekend (schedule conflict?)
2. **Intensity**: Easy runs too fast (RPE 6 instead of 4)
3. **Multi-sport**: Climbing sessions preceded by rest days (good planning)
4. **Volume**: Weekly volume increased 59% (too aggressive)
5. **Adaptation**: ACWR trended from 1.1 → 1.4 (approaching caution)

### Step 5.5: Capture Significant Patterns as Memories

**When a pattern appears 3+ times or is highly significant**, persist as memory:

```bash
# Consistency pattern
sce memory add --type TRAINING_RESPONSE \
  --content "Consistently skips Tuesday runs due to work schedule" \
  --tags "schedule:tuesday,pattern:skip" \
  --confidence high

# Intensity pattern
sce memory add --type TRAINING_RESPONSE \
  --content "Easy runs consistently 0.5 min/km too fast (RPE 6 instead of 4)" \
  --tags "intensity:easy,violation:pace" \
  --confidence high
```

**Guidelines**:
- Capture patterns with 3+ occurrences or high significance
- Use HIGH confidence for 3+, MEDIUM for 2 occurrences
- Tag for future retrieval

### Step 6: Synthesize and Communicate

**Structure**:
1. **Opening**: Overall summary + key achievement (positive first)
2. **Adherence**: Planned vs. completed
3. **Intensity**: 80/20 compliance, violations if any
4. **Load**: Multi-sport breakdown, concerns
5. **Patterns**: Notable trends (positive and concerning)
6. **Metrics**: CTL/ATL/TSB/ACWR week-over-week changes
7. **Next Week**: Specific recommendations with concrete numbers

**Example opening**:
```
Great week! You completed 7/8 planned workouts (88% adherence) and your CTL increased from 42 → 44.
```

**See complete worked examples**:
- [Balanced week with excellent execution](examples/example_week_balanced.md)
- [80/20 intensity violation](examples/example_week_80_20_violation.md)
- [Multi-sport conflict](examples/example_week_multi_sport.md)

### Step 7: Log Weekly Summary to Training Log

**After presenting analysis**, append summary to training log:

Create JSON with week summary:
```json
{
  "week_number": 1,
  "week_dates": "Jan 20-26",
  "planned_volume_km": 22.0,
  "actual_volume_km": 20.0,
  "adherence_pct": 91.0,
  "completed_workouts": [...],
  "key_metrics": {
    "ctl_start": 28,
    "ctl_end": 30,
    "tsb_start": 3,
    "tsb_end": 1,
    "acwr": 1.1
  },
  "coach_observations": "...",
  "milestones": [...]
}
```

**Append to log**:
```bash
sce plan append-week --week 1 --from-json /tmp/week_1_summary.json
```

**Confirm with athlete**:
"Week summary logged. View anytime with: `sce plan show-log`"

---

## Quick Decision Trees

### Q: Adherence <50%
1. Don't criticize - investigate barriers
2. Assess cause: External (life stress), plan mismatch, motivation, physical
3. Adapt: Adjust current week OR replan → Use `plan-adaptation` skill

### Q: Intensity violates 80/20 (moderate-intensity rut)
1. Show distribution (e.g., 65/35 instead of 80/20)
2. Explain gray zone problem (RPE 5-6 = too hard to recover, not hard enough to adapt)
3. Provide specific pace targets from VDOT
4. Next week: Verify compliance

**For detailed intensity violation handling**: See [references/intensity_guidelines.md](references/intensity_guidelines.md)

### Q: Multi-sport conflict (e.g., climbing comp → next-day long run)
1. Analyze systemic vs. lower-body load
2. Explain impact (systemic fatigue even though legs okay)
3. Present options: Move long run, adjust expectations, or skip/replace
4. Capture pattern as memory

**For complete multi-sport scenarios**: See [references/multi_sport_balance.md](references/multi_sport_balance.md)

### Q: Volume increased too quickly (e.g., +60%)
1. Show violation of 10% rule
2. Connect to ACWR spike
3. Recommend pull-back for next week
4. Validate with: `sce guardrails progression --previous [X] --current [Y]`

### Q: Athlete wants to increase despite concerns (ACWR 1.35)
1. Explain leading indicator (predicts injury before symptoms)
2. Offer compromise: Maintain this week, reassess next week
3. Balance motivation with objective risk

---

## Quick Pitfalls Checklist

Before sending weekly review, verify:

1. ✅ **Started with positive** - Not leading with criticism
2. ✅ **Contextualized adherence** - Investigated why low (if applicable)
3. ✅ **Flagged 80/20 violations** - Checked intensity distribution
4. ✅ **Connected multi-sport dots** - Showed total load across activities
5. ✅ **Specific recommendations** - Concrete numbers, not vague advice

**For detailed pitfall explanations with examples**: See [references/pitfalls.md](references/pitfalls.md)

---

## Output Template

```markdown
# Weekly Review: Week [N] ([DATE_RANGE])

## Summary
[One sentence: overall + key achievement]

## Adherence
**Completion rate**: [X]% ([Y]/[Z] workouts)

Completed: [list]
Missed: [list with reasons]
Extra: [list]

## Intensity Distribution (80/20)
**Distribution**: [X]% easy, [Y]% moderate+hard
**Compliance**: [✓/✗]

[If violations: specific issue + recommendation]

## Multi-Sport Load
**Total systemic**: [X] AU
- Running: [X] AU ([Y]%)
- [Sport]: [X] AU ([Y]%)

**Total lower-body**: [X] AU
[If concerns: flag interactions]

## Patterns
**Positive**: [reinforce]
**Concerning**: [flag proactively]

## Metrics (Week-over-week)
- **CTL**: [prev] → [current] ([change])
- **ATL**: [prev] → [current] ([change])
- **TSB**: [prev] → [current] ([change])
- **ACWR**: [prev] → [current] ([change])

**Interpretation**: [1-2 sentences]

## Next Week Recommendations
1. [Primary with concrete numbers]
2. [Secondary]
3. [Tertiary]

**Focus**: [One key theme]

## Overall Assessment
[2-3 sentences: big picture, progress, encouragement]
```

---

## Additional Resources

- **80/20 Philosophy**: [Matt Fitzgerald's 80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md)
- **Intensity Guidelines (detailed)**: [references/intensity_guidelines.md](references/intensity_guidelines.md)
- **Multi-Sport Balance (detailed)**: [references/multi_sport_balance.md](references/multi_sport_balance.md)
- **Common Pitfalls (detailed)**: [references/pitfalls.md](references/pitfalls.md)
- **Worked Examples**: [examples/](examples/)
- **Adherence Patterns**: [Coaching Scenarios - Weekly Review](../../../docs/coaching/scenarios.md#scenario-5-weekly-review)
- **CLI Reference**: [Analysis Commands](../../../docs/coaching/cli/cli_analysis.md)
- **Methodology**: [ACWR Interpretation](../../../docs/coaching/methodology.md#acwr-acutechronic-workload-ratio)
