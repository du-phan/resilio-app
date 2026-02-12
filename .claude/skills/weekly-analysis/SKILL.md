---
name: weekly-analysis
description: Comprehensive weekly training review including completion checks, intensity distribution validation (80/20), multi-sport load breakdown, and pattern detection. Use when athlete asks "how was my week?", "weekly review", "analyze training", or "did I follow the plan?".
allowed-tools: Bash, Read, Write, AskUserQuestion
argument-hint: ""
---

# Weekly Analysis: Comprehensive Training Review

## Overview

This skill provides complete weekly training analysis by:

1. Comparing planned vs. actual training (completion)
2. Validating intensity distribution (80/20 rule)
3. Analyzing multi-sport load breakdown
4. Detecting patterns and suggesting adaptations

**Key principle**: Use computational tools to calculate metrics; apply coaching judgment to interpret patterns.

**Communication guideline**: Present findings naturally. Say "Let me review your week" not "I'll use weekly-analysis." See CLAUDE.md "Athlete-Facing Communication Guidelines."

**Conversational flow**: See CLAUDE.md "Conversational Pacing" for guidance on when to wait for athlete responses vs. batching questions.

**Metric explainer rule**: See CLAUDE.md "Metric one-liners" for first-mention definitions. Do not repeat unless the athlete asks.

---

## Workflow

### Step 0: Optional Quick Sync (for faster weekly analysis)

For faster weekly analysis, optionally sync only last week's data:

```bash
resilio sync --since 7d  # Quick sync (5-10 seconds vs 20-30 seconds for full sync)
```

**Note**: Without `--since`, `resilio sync` uses smart detection (incremental sync from last activity).

### Step 0.5: Check for Active Training Plan (MANDATORY)

**Before analyzing the week, determine if the athlete has a structured plan:**

```bash
resilio plan week
```

This returns the current week's planned workouts (date, workout_type, distance_km, target_rpe, pace_range, intensity_zone) plus plan context (week number, phase, total weeks, goal).

**If plan exists** → the weekly analysis MUST compare actual vs planned (Step 2 Option A)
**If no plan / error** → proceed with freeform analysis (Step 2 Option B)

**Why this matters:** Without this step, the coach may analyze a week as freeform training when the athlete is actually on a structured plan — missing critical adherence insights.

### Step 1: Get Weekly Summary

```bash
resilio week
```

**Parse key data**:

- Total planned vs. completed workouts
- Running volume vs. other activities
- CTL/ATL/TSB/ACWR/readiness changes

### Step 2: Plan Adherence (if on plan) OR Activity Summary (if freeform)

#### Option A: Athlete on Structured Plan

Cross-reference planned workouts (from Step 0.5) with actual activities (from `resilio week`):

1. **Map planned → actual by date:**
   - **Match**: Correct workout type on planned date
   - **Day shift**: Correct type/volume but different day (e.g., Wed→Thu)
   - **Volume variance**: Right day but >15% over/under planned distance
   - **Missed**: Planned workout not completed
   - **Extra**: Activity not in the plan (including cross-training)

2. **Assess adherence:**
   - **Workout completion**: How many planned workouts were completed (count day-shifts as completed)
   - **Volume adherence**: Actual running km vs planned km — flag if >115% or <80%
   - **Quality session check**: Were tempo/interval/long run sessions completed as prescribed? (highest priority)

3. **Flag critical patterns:**
   - ⚠️ Quality sessions missed or downgraded (tempo→easy) — high priority
   - ⚠️ Long run >20% over/under planned distance
   - ⚠️ Easy runs at moderate pace (80/20 violation risk)
   - ⚠️ Unplanned high-load activities on rest days or before quality sessions

**Context matters:** A day shift (Wed→Thu) is usually fine. Volume variance needs coaching judgment — was it intentional, terrain-driven, or loss of discipline?

**Interpretation zones** (by completion rate):

- ≥90%: Excellent completion
- 70-89%: Good, minor adjustments needed
- 50-69%: Fair, discuss barriers
- <50%: Poor, major replanning needed

#### Option B: Freeform Training (No Structured Plan)

Focus on training quality without plan reference:

1. List all activities by date with sport/distance/duration
2. Compare volume to recent 4-week average
3. Assess frequency, sport distribution, consistency
4. Check if training supports stated goals

### Step 3: Verify Key Workouts with Lap Data (if structured workouts present)

**When reviewing structured workouts** (intervals, tempo, threshold), use lap data to verify execution quality:

```bash
resilio activity laps <activity-id>
```

**Quick checks** (see [lap_data_analysis.md](references/lap_data_analysis.md) for complete methodology):

1. **Warmup verification**: HR < 140, pace within easy range (avoid Fitzgerald's "moderate-intensity rut")
2. **Interval consistency**: Check pace variation across work intervals (CV < 3% = excellent)
3. **Tempo execution**: Pace within prescribed T-pace range, HR in threshold zone
4. **Pacing patterns**: Even pacing good, fade pattern = started too fast (FIRST's documented mistake)
5. **HR drift**: HR increasing at constant pace indicates heat stress or dehydration

**When lap data missing**: Fall back to aggregate metrics, note limitation in analysis.

**Common training mistakes detected via lap data** (Daniels, Pfitzinger, Fitzgerald, FIRST):
- Intervals too fast (defeats VO2max aerobic purpose)
- Easy runs at moderate intensity (compromises recovery)
- Tempo too fast (causes lactate accumulation vs. threshold stimulus)
- Starting long runs too fast (fade in later miles)

### Step 4: Intensity Distribution Analysis

First, export activities for analysis (if not already done):

```bash
resilio activity export --since 7d --out /tmp/week_activities.json
```

Then analyze intensity distribution:

```bash
resilio analysis intensity --activities /tmp/week_activities.json --days 7
```

**Returns**:

- `distribution`: % breakdown (low vs. moderate+high intensity)
- `compliance`: Meets 80/20 guideline?
- `polarization_score`: 0-100 (separation of easy from hard)
- `violations`: Specific issues

**Quick interpretation**:

- ≥80% low intensity: Compliant ✅ (80/20 target met)
- 75-79% low intensity: Acceptable but watch the trend ⚠️ (close — tighten easy pace)
- 60-74% low intensity: Moderate-intensity rut ❌ (gray zone problem — too hard to recover, not hard enough to adapt)
- <60% low intensity: Severe imbalance ❌❌ (injury/overtraining risk)

**For detailed 80/20 philosophy and violation handling**: See [references/intensity_guidelines.md](references/intensity_guidelines.md)

### Step 5: Multi-Sport Load Breakdown

```bash
resilio analysis load --activities /tmp/week_activities.json --days 7 --priority [PRIORITY]
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

### Step 6: Pattern Detection

**Review activity notes for qualitative signals**:

```bash
# List activities with notes
resilio activity list --since 7d --has-notes

# Search for wellness signals
resilio activity search --query "tired fatigue flat heavy" --since 7d

# Search for pain/discomfort
resilio activity search --query "pain sore tight discomfort" --since 7d
```

**Patterns to identify**:

1. **Consistency**: Completed all weekday runs, skipped weekend (schedule conflict?)
2. **Intensity**: Easy runs too fast (RPE 6 instead of 4)
3. **Multi-sport**: Climbing sessions preceded by rest days (good planning)
4. **Volume**: Weekly volume increased 59% (too aggressive)
5. **Adaptation**: ACWR trended from 1.1 → 1.4 (approaching caution)

### Step 6.5: Capture Significant Patterns as Memories

**When a pattern appears 3+ times or is highly significant**, persist as memory:

```bash
# Consistency pattern
resilio memory add --type TRAINING_RESPONSE \
  --content "Consistently skips Tuesday runs due to work schedule" \
  --tags "schedule:tuesday,pattern:skip" \
  --confidence high

# Intensity pattern
resilio memory add --type TRAINING_RESPONSE \
  --content "Easy runs consistently 0.5 min/km too fast (RPE 6 instead of 4)" \
  --tags "intensity:easy,violation:pace" \
  --confidence high
```

**Guidelines**:

- Capture patterns with 3+ occurrences or high significance
- Use HIGH confidence for 3+, MEDIUM for 2 occurrences
- Tag for future retrieval

### Step 7: Synthesize and Communicate

**Structure**:

1. **Opening**: Overall summary + key achievement (positive first)
2. **Completion**: Planned vs. completed
3. **Intensity**: 80/20 compliance, violations if any
4. **Load**: Multi-sport breakdown, concerns
5. **Patterns**: Notable trends (positive and concerning)
6. **Metrics**: CTL/ATL/TSB/ACWR week-over-week changes
7. **Next Week**: Specific recommendations with concrete numbers

**Example opening**:

```
Great week! You completed 7/8 planned workouts (88% completion) and your CTL increased from 42 → 44.
```

**See complete worked examples**:

- [Balanced week with excellent execution](examples/example_week_balanced.md)
- [80/20 intensity violation](examples/example_week_80_20_violation.md)
- [Multi-sport conflict](examples/example_week_multi_sport.md)
- [Plan adherence comparison](#example-plan-adherence-comparison-week-2-of-marathon-plan) (inline below)

### Step 8: Log Weekly Summary to Training Log

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
resilio plan append-week --week 1 --from-json /tmp/week_1_summary.json
```

**Confirm with athlete**:
"Week summary logged. View anytime with: `resilio plan show-log`"

---

### Step 9: Plan Next Week (Weekly Executor Flow)

**After completing weekly analysis**, transition to planning next week's workouts for adaptive training.

**Ask athlete**:

```
"Your weekly review is complete. Ready to plan next week's workouts?"
```

**If athlete says yes**:

Run the executor flow:

1. `weekly-plan-generate` → creates weekly JSON + presents review in chat
2. Athlete approval (main agent)
3. `weekly-plan-apply` → validates + persists approved week

**Context to pass to weekly-plan-generate** (as notes argument):

- Current week's completion rate
- ACWR and readiness scores
- Any illness/injury signals detected
- 80/20 intensity distribution compliance
- Notable patterns or concerns

**Example notes format**: `completion=88%, acwr=1.1, readiness=52, pattern: easy_runs_too_fast, no_injury_signals, intensity=82/18_compliant`

**If athlete says no** (wants to wait):

```
"No problem! When you're ready to plan next week, just let me know."
```

**Alternative**: If athlete only wants weekly analysis (not planning), you're done after Step 8.

---

## Integrated Workflow Example

**Natural coaching conversation**:

```
Athlete: "How was my week?"

Coach: [Runs Steps 1-8: Weekly Analysis]
  → 7/8 workouts completed (88% completion)
  → 82% easy, 18% hard (80/20 compliant ✓)
  → CTL increased 42 → 44 (healthy progression)
  → No concerning patterns

Coach: "Great week! You completed all runs except Saturday's easy run,
maintained excellent 80/20 intensity, and your CTL increased safely."

Coach: [Step 9] "Ready to plan next week's workouts?"

Athlete: "Yes"

Coach: [Runs weekly executor flow]
  → weekly-plan-generate creates Week 2 plan review + JSON
  → Presents plan with rationale based on this week's analysis
  → weekly-plan-apply saves after athlete approval

Coach: "Week 2 plan saved! You'll see workouts starting Monday."
```

---

### Example: Plan Adherence Comparison (Week 2 of Marathon Plan)

**From `resilio plan week`** (planned):
- Mon Feb 2: 8km easy (RPE 4, 6:19-6:49/km)
- Wed Feb 4: 7km easy (RPE 4, 6:19-6:49/km)
- Sun Feb 8: 12km long run (RPE 5, 6:20-6:49/km)

**From `resilio week`** (actual):
| Planned | Actual | Status |
|---------|--------|--------|
| Mon: 8km easy | Mon: 8.5km run, 53 min, HR 145.8 | ✅ Match |
| Wed: 7km easy | Thu: 6.6km run, 39 min, HR 145.4 | ⚠️ Day shift (Wed→Thu) |
| Sun: 12km long | Sun: 15.5km run, 96 min, HR 148.8 | ⚠️ Volume +29% |
| — | Mon: 80 min climb (RPE 4) | ➕ Extra (cross-training) |

**Coach summary**: "You completed all 3 planned runs — great consistency! Two things to discuss: Sunday's long run was 29% over target (15.5 vs 12km). Was that intentional? In base phase, I'd prefer staying closer to plan to build gradually. Also, the Wednesday→Thursday shift is totally fine — was that a schedule thing?"

---

## Quick Decision Trees

### Q: Adherence <50%

1. Don't criticize - investigate barriers
2. Assess cause: External (life stress), plan mismatch, motivation, physical
3. Adapt: Adjust current week using `weekly-plan-generate` + `weekly-plan-apply` (target current week)

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
4. Validate with: `resilio guardrails progression --previous [X] --current [Y]`

### Q: Athlete wants to increase despite concerns (ACWR 1.35)

1. Explain leading indicator (predicts injury before symptoms)
2. Offer compromise: Maintain this week, reassess next week
3. Balance motivation with objective risk

### Q: Athlete completed MORE workouts than planned

**Investigate:**
1. Extra activities: same sport or cross-training?
   - Same sport on rest day → recovery deficit risk, check ACWR
   - Cross-training → assess systemic load impact via multi-sport analysis
2. Did extra activities fall on rest days or before quality sessions?
   - Before quality session → may have compromised quality workout
   - On rest day → flag recovery importance
3. Were extra activities high-intensity or easy?
   - High-intensity → 80/20 violation risk
   - Easy → generally acceptable if ACWR safe

**Approach:** Celebrate enthusiasm, explain "more ≠ better" (adaptation during rest), suggest channeling energy into quality execution of planned sessions.

---

## Quick Pitfalls Checklist

Before sending weekly review, verify:

0. ✅ **Checked for active plan** - Ran `resilio plan week` before analyzing
1. ✅ **Started with positive** - Not leading with criticism
2. ✅ **Contextualized completion** - Investigated why low (if applicable)
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

## Plan Adherence (if on structured plan)

**Week [N] of [TOTAL] — [PHASE] phase**

| Planned | Actual | Status |
|---------|--------|--------|
| [date: workout] | [date: activity] | ✅/⚠️/❌ |

**Workout completion**: [X]/[Y] planned workouts
**Volume adherence**: [actual]km / [planned]km = [pct]%
**Quality sessions**: [completed/missed]

## Completion

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
