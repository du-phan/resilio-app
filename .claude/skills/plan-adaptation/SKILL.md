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

### Q: How severe is the illness?

**Decision factors**:
- Above neck (sniffles, sore throat) → Minor
- Body aches, fatigue, full cold → Moderate
- Fever, chest congestion, flu → Severe

**Actions**:
- Minor: 1-2 days rest, return with easy runs
- Moderate: 3-7 days rest, use `sce guardrails illness-recovery --severity moderate`
- Severe: 7-14 days rest, use `sce guardrails illness-recovery --severity severe` + partial replan

### Q: Can the goal still be achieved?

**Factors to consider**:
- Weeks remaining to goal
- CTL drop from disruption
- Training phase (base is flexible, peak/taper less so)
- Goal difficulty (time goal vs finish comfortably)

**Decision**:
1. Calculate CTL projection with adapted plan
2. Use `sce vdot predict` to estimate race performance at projected CTL
3. Compare to goal time
4. Present options using **AskUserQuestion**:
   - Option A: Keep goal, accept higher training load
   - Option B: Adjust goal (more realistic time)
   - Option C: Move race date (if possible)

### Q: Should quality workouts be reduced or eliminated?

**During illness recovery**:
- Week 1 back: Easy runs only (no quality)
- Week 2 back: Light tempo if feeling good (reduced duration)
- Week 3+ back: Resume quality gradually

**During injury recovery**:
- Until pain-free: No quality workouts
- First week pain-free: Short tempo test (if successful, continue)
- Rebuild intensity over 2-4 weeks

**Check readiness**:
```bash
sce status | jq '.data.readiness'
```

If readiness < 50 after return, delay quality workouts.

### Q: What if they miss a long run?

**Options**:
1. **Move to next available day** (if within same week)
2. **Skip and continue** (if recent long run was adequate)
3. **Reduce and reschedule** (shorter version later in week)
4. **Extend next week's long run** (add 10-15 min)

**Use AskUserQuestion** to present options with context:
- Current CTL
- Previous long run date/duration
- Upcoming schedule constraints
- Goal proximity

### Q: What if schedule change is permanent?

**Example**: "I can no longer run on Thursdays"

**Workflow**:
1. Identify affected workouts (quality sessions, long runs)
2. Map to new available days
3. Validate with multi-sport constraints (see training-plan-design/references/MULTI_SPORT.md)
4. Update affected weeks using `sce plan update-week` (multiple calls)

**Considerations**:
- Quality sessions need 48 hours separation
- Long runs need recovery day after
- Other sports: avoid quality run + hard climbing on consecutive days

---

## Common Adaptation Scenarios

### Scenario 1: Mild Illness (3 days missed)

**Situation**: Athlete caught cold, missed Tuesday tempo and Thursday easy run. Feeling better Friday.

**Assessment**:
```bash
sce guardrails illness-recovery --severity minor --days-missed 3
```

**Returns**: "2 days easy running before resuming quality"

**Action**: Update current week only
- Skip missed workouts (don't reschedule)
- Replace Saturday long run with moderate easy run (70% duration)
- Next week: Resume normal plan with volume -10%

**JSON**: Single week update (`sce plan update-week`)

### Scenario 2: Severe Illness (10 days missed, flu)

**Situation**: Athlete had flu with fever, missed entire week + 3 days of next week.

**Assessment**:
```bash
sce guardrails illness-recovery --severity severe --days-missed 10
```

**Returns**: "7 days easy running before quality, reduce volume 30% first week"

**Action**: Partial replan from current week
- Week N: 3 easy runs, 60% of planned volume
- Week N+1: 4 easy runs, 75% of planned volume
- Week N+2: Resume quality (short tempo), 85% volume
- Week N+3: Normal progression resumes

**JSON**: Partial replan (`sce plan update-from`)

### Scenario 3: Injury (2 weeks off, knee pain)

**Situation**: Athlete rested 14 days for knee tendonitis, did swimming 3x/week.

**Assessment**:
```bash
sce guardrails break-return --days 14 --ctl 44 --cross-training moderate
```

**Returns**: "Start at 18 km/week, +5% weekly increase, 4 weeks to pre-injury volume"

**Action**: Partial replan with conservative buildup
- Extend base phase by 2 weeks
- Reduce peak volume by 10%
- Monitor knee pain signals (check notes in activities)

**JSON**: Partial replan with modified phases

### Scenario 4: Training Break (3 weeks vacation)

**Situation**: Athlete took 21 days off for travel, no training.

**Assessment**:
```bash
sce guardrails break-return --days 21 --ctl 44 --cross-training none
```

**Returns**: "CTL dropped to ~30. Start at 15 km/week, rebuild over 6 weeks"

**Action**: Major replan
- Restart base phase (or extend existing base)
- Adjust goal if timeline compromised
- Use conservative progression (+5% per week)

**JSON**: Partial replan, possibly full plan regeneration if goal date affected

### Scenario 5: Missed Long Run (Travel)

**Situation**: Athlete traveling for work, can't do Saturday 18km long run.

**Assessment**: No guardrails needed, simple rescheduling.

**Action**: Use AskUserQuestion to present options
- Option A: Run Sunday instead (move long run 1 day)
- Option B: Run Friday before travel (earlier in week)
- Option C: Skip this week, extend next week's long run to 20km

**JSON**: Single week update if rescheduling, or skip + adjust next week

---

## Validation Checklist

**Before saving adapted plan**, verify:

1. **ACWR Safety**: Projected ACWR stays <1.3 after return
   ```bash
   sce risk forecast --weeks 3 --metrics metrics.json --plan adapted_plan.json
   ```

2. **Volume Progression**: No week exceeds +10% increase
   ```bash
   sce guardrails progression --previous [X] --current [Y]
   ```

3. **Recovery Protocol**: Adequate easy-only period per guardrails

4. **Goal Feasibility**: Still realistic given new CTL trajectory
   ```bash
   sce validation assess-goal --goal-type [type] --goal-time [time] --goal-date [date] --current-vdot [vdot] --current-ctl [ctl]
   ```

5. **80/20 Distribution**: Plan maintains intensity balance
   - Use `sce analysis intensity` after 2-3 weeks back

6. **Multi-Sport Conflicts**: Adjusted schedule respects other sports
   - Review with athlete if climbing/cycling days affected

---

## Key Principles

1. **Err on the side of caution**: Better to return slowly than risk re-injury or relapse
2. **Preserve long-term fitness**: Short-term setbacks are normal; focus on sustainable return
3. **Communicate trade-offs**: If goal timing affected, present options clearly
4. **Trust the data**: Use CTL/ACWR to guide decisions, not arbitrary timelines
5. **Monitor closely**: First 2 weeks after return are critical - watch for warning signs

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

### Edge Case 1: Illness During Taper

**Problem**: Athlete gets sick 10 days before race.

**Decision**:
- If fever/severe: Consider skipping race (no safe adaptation)
- If mild: Maintain taper volume reduction, skip quality sessions
- Race day: Start conservatively, adjust goals to "finish comfortably"

**No plan update needed** - focus on recovery and race readiness.

### Edge Case 2: Injury During Peak Phase

**Problem**: Acute injury 4 weeks before race, peak phase training.

**Decision**:
- 1-2 weeks off: Possible to salvage race with reduced goals
- 3+ weeks off: Recommend moving race date or DNS (do not start)

**Use AskUserQuestion** to discuss options:
- Option A: Race with adjusted goals (finish, not time)
- Option B: Move to later race
- Option C: DNS, replan for different goal

### Edge Case 3: Multiple Disruptions in Short Period

**Problem**: Illness → recovered → injury → recovered (4 weeks total disruption).

**Decision**: Full plan regeneration likely needed.

**Action**:
1. Assess current CTL
2. Calculate weeks to goal
3. Use training-plan-design skill to regenerate plan
4. Present new plan (not adaptation, but fresh start)

### Edge Case 4: Schedule Change Affects Key Long Run Day

**Problem**: Athlete can no longer run on Sundays (traditional long run day).

**Decision**: Permanent schedule restructure.

**Action**:
1. Identify new long run day (Saturday? Friday?)
2. Validate with multi-sport constraints
3. Update all future weeks with new schedule pattern
4. Use `sce plan update-from` with restructured weekly pattern

---

## Related Skills

- **training-plan-design**: Use for full plan regeneration if disruption too severe
- **daily-workout**: Use for day-to-day adaptation decisions during return period
- **injury-risk-management**: Use for proactive risk assessment during return
- **weekly-analysis**: Use to monitor return progress and validate recovery

---

## CLI Command Reference

**Guardrails**:
```bash
sce guardrails illness-recovery --severity [minor|moderate|severe] --days-missed [N]
sce guardrails break-return --days [N] --ctl [X] --cross-training [none|light|moderate|high]
sce guardrails race-recovery --distance [type] --age [N] --effort [easy|moderate|hard]
sce guardrails progression --previous [X] --current [Y]
```

**Plan Updates**:
```bash
sce plan update-week --week [N] --from-json [file.json]      # Single week object
sce plan update-from --week [N] --from-json [file.json]      # Weeks array from N onward
sce plan show                                                 # View current plan
```

**Validation**:
```bash
sce risk forecast --weeks [N] --metrics metrics.json --plan plan.json
sce validation assess-goal --goal-type [type] --goal-time [time] --goal-date [date] --current-vdot [vdot] --current-ctl [ctl]
```

**Status**:
```bash
sce status        # Current metrics (CTL/ATL/TSB/ACWR/readiness)
sce week          # Recent training pattern
```

---

## Output Template

After completing adaptation, provide structured output:

```
# Plan Adaptation Complete

**Situation**: [Brief description]
**Action taken**: [Single week update / Partial replan / Full replan]
**Affected weeks**: [Week range]

**Key changes**:
- Week [N]: [Summary of changes]
- [Additional weeks as needed]

**Updated metrics**:
- Volume: [Old] → [New] km/week
- Projected CTL: [Value] by Week [N]
- ACWR: [Value] (safe range)

**Next steps**:
- [Immediate action, e.g., "Easy 30min run tomorrow"]
- [Monitoring, e.g., "Watch for knee pain signals"]
- [Timeline, e.g., "Resume quality workouts Week 7"]

**Goal status**: [On track / Adjusted expectations / Timeline extended]
```

---

## Testing Plan Adaptation

**Manual test scenarios**:

1. Mild illness (3 days) → Single week update
2. Severe illness (10 days) → Partial replan
3. Injury (2 weeks) → Partial replan with conservative return
4. Training break (3 weeks) → Major replan
5. Missed long run → Rescheduling decision
6. Permanent schedule change → Multi-week update

**Success criteria**:
- Guardrails consulted before plan changes
- ACWR stays <1.3 after return
- Volume progression respects 10% rule
- Athlete approves adapted plan before save
- JSON structure correct (week object vs weeks array)
