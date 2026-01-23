# Coaching Scenarios Reference

Detailed examples of common coaching workflows using the Sports Coach Engine CLI.

## Scenario 1: First Session with New Athlete (AUTH-FIRST PATTERN)

```bash
# STEP 0: Check auth status FIRST (mandatory)
sce auth status

# If not authenticated or token expired:
if [ $? -eq 3 ]; then
  # Guide user through OAuth flow
  echo "Let's connect your Strava account so I can access your training history."
  sce auth url
  # User opens browser, authorizes, copies code
  sce auth exchange --code CODE_FROM_URL
fi

# STEP 1: Now sync activities (this is why auth was required first)
sce sync  # Imports 12+ weeks of history → provides CTL/ATL/TSB baseline

# STEP 2: Review historical data to inform profile setup
sce week    # See recent training patterns and activities
sce status  # Get baseline metrics (CTL will be non-zero with history)

# STEP 3: Set up profile with context from historical data
sce profile get  # Check if profile exists

# Now you can ask refined questions based on actual data:
# "I see you average 35km/week - should we maintain this volume?"
# "Your recent activities show climbing Tuesdays - is this consistent?"
# vs generic "How much do you run?" without any context

# STEP 4: Set goal and generate plan
sce goal --type 10k --date 2026-06-01
```

### Detailed Profile Setup Conversation Example

After auth + sync, here's how to collect profile data using natural conversation:

```
# STEP 3a: Collect basic info via natural conversation
# (NOT AskUserQuestion - these are free-form text/number inputs)

Coach: "I can see your training history now. Let's set up your profile. What's your name?"
Athlete: "Alex"

Coach: "Nice to meet you, Alex! How old are you?"
Athlete: "32"

Coach: "Perfect. Looking at your Strava data, your resting HR averages around 55. Do you know your max heart rate?"
Athlete: "Yeah, I tested it last month - it's about 190"

Coach: "Great, that helps with zone calculations. I notice you do climbing and running. Which is your primary sport?"
Athlete: "I'd say they're equal - I'm equally committed to both"

# STEP 3b: Now use AskUserQuestion for policy decision
# (This IS appropriate - distinct options with trade-offs)

Coach: "When there's a conflict between running and climbing - like a long run and a climbing comp on the same day - how should I handle it?"

[Use AskUserQuestion with options]
A) Ask me each time (most flexible)
   - I'll present options and trade-offs for each conflict
   - You decide based on current priorities and how you feel
   - Best for athletes with variable schedules

B) Climbing wins by default (protect primary sport)
   - Running workouts get adjusted around climbing schedule
   - Running plan adapts to accommodate climbing commitments
   - Best for competitive climbers in season

C) Running goal wins (prioritize race prep)
   - Keep key running workouts unless injury risk
   - Climbing scheduled around critical runs
   - Best when training for a specific race

Athlete: "Ask me each time - my priorities shift depending on the week"

# STEP 3c: Save profile
sce profile set --name "Alex" --age 32 --max-hr 190 --conflict-policy ask_each_time

Coach: "Perfect! Your profile is set up. Now let's talk about your running goal..."
```

**Key Takeaways**:
- ✅ Names, ages, HR values → Natural conversation (text/number input)
- ✅ Sport priority → Natural conversation works here too ("equal")
- ✅ Conflict policy → AskUserQuestion is PERFECT (decision with trade-offs)
- ❌ NEVER: "AskUserQuestion: What's your name? Options: A) Tell me B) Skip"

### Injury History - Context-Aware Questioning

The AI coach should adapt the injury question based on observed activity patterns from the computational tools.

#### Detection Methods

**1. Activity Gap Detection**:
- Via `sce status`: CTL drop from 45→20 over 3 weeks
- Via `sce week`: 14+ day gap between activities
- Via activity dates: Compare timestamps for gaps

**2. Injury Keywords in Notes**:
- The `flags` field in daily metrics automatically extracts injury/illness keywords
- Keywords: pain, sore, injury, hurt, ache, strain, etc.
- Example: flags = ["run activity: pain, sore"]

**3. CTL/ATL Anomalies**:
- Sudden CTL drops not explained by planned rest
- ATL spike followed by extended low-load period

#### Adaptive Question Patterns

**If activity gap detected**:
```
"I noticed you had a break from running in November. Was that due to injury?"
```

**If activity notes mention pain**:
```
"I see some notes about knee discomfort in your recent activities.
Can you tell me about that injury history?"
```

**If no signals detected**:
```
"Any past injuries I should know about? Helps me watch for warning signs
and adjust training load appropriately."
```

#### Follow-Up Questions

Always ask if recent/ongoing:
```
"Is that fully healed or something to monitor during training?"
```

#### Storage Format

Store exactly as athlete describes - don't sanitize or categorize:

✅ **Good**:
- "Left knee tendonitis 2023, fully healed"
- "Right Achilles tightness if I run 3 days in a row"
- "Took break Nov 2025 - knee pain, better now but watch mileage"

❌ **Bad**:
- "Knee injury" (too vague)
- "Healed tendonitis" (lost context)
- Categorizing into "major" vs "minor" (subjective)

#### Example Workflow

```bash
# 1. Check for activity gaps
sce status  # Look for CTL drops
sce week    # Review recent activity density

# 2. If gap detected, ask context-aware question
Coach: "I noticed your CTL dropped from 44 to 22 in mid-November.
       Was that a planned break or due to injury?"

Athlete: "Actually, I had some left knee pain. Took a few weeks off."

# 3. Follow up on current status
Coach: "Thanks for letting me know. Is that fully healed now,
       or something I should watch for?"

Athlete: "It's better, but it can flare up if I increase mileage too quickly."

# 4. Store detailed history
sce profile set --injury-history "Left knee pain Nov 2025, healed but watch mileage progression"
```

**📊 WHY AUTH FIRST:**

- Provides 12+ weeks of activity history for baseline CTL/ATL/TSB calculations
- Enables intelligent profile setup questions based on actual training patterns
- Reveals multi-sport activities for accurate load management
- Without auth: coaching starts blind with CTL=0 and generic defaults
- With auth: "I see your CTL is 44 (solid recreational level)" vs "Let's start from zero"

## Scenario 2: Daily Coaching Check-in

```bash
# Get today's workout with full context
sce today
# Returns: workout, current_metrics, adaptation_triggers, rationale

# Claude Code can now coach based on:
# - Workout details (type, duration, pace zones)
# - Current metrics (CTL, TSB, ACWR, readiness)
# - Any triggers (ACWR elevated, readiness low, etc.)
```

**Coaching Approach:**

- Reference actual metrics when explaining recommendations
- If triggers detected, use AskUserQuestion to present options
- Explain trade-offs: "ACWR 1.35 (caution) + yesterday's climbing (340 AU) → easy run, move tempo, or proceed?"

## Scenario 3: Weekly Review

```bash
# Get full week summary
sce week
# Returns: planned vs completed, total load, metrics, changes

# Sync latest if needed
sce sync --since 7d

# Check current state
sce status
```

**Analysis Points:**

- Compare planned vs completed workouts
- Review total training load (systemic + lower-body)
- Check metric trends (CTL/ATL/TSB progression)
- Identify patterns: consistency, intensity distribution, recovery

## Scenario 4: Goal Change

```bash
# Set new goal (automatically regenerates plan)
sce goal --type half_marathon --date 2026-09-15 --time 01:45:00

# View new plan
sce plan show
# Returns: All weeks with phases, workouts, volume progression
```

**Interactive Plan Presentation:**

1. Use toolkit to design plan based on new goal
2. Create markdown file with full plan structure
3. Present for review: phases, volume progression, constraints
4. Save to YAML only after athlete approves

## Scenario 5: Profile Updates

```bash
# Update basic info
sce profile set --name "Alex" --age 32 --max-hr 190

# Update training preferences
sce profile set --run-priority primary --conflict-policy ask_each_time
```

**When to Update Profile:**

- After race performance (update VDOT from PR)
- Changed training availability (work schedule, life events)
- New multi-sport priorities (e.g., climbing season starting)
- Discovered preferences through coaching conversation

## Scenario 6: Handling Adaptation Triggers

```bash
# Get today's workout and check for triggers
result=$(sce today)

# Parse triggers
triggers=$(echo "$result" | jq -r '.data.adaptation_triggers')

# If triggers exist, present options using AskUserQuestion
# Example: ACWR elevated + low readiness
```

**Response Pattern:**

```
Your ACWR is 1.35 (slightly elevated) and readiness is 45 (low).
Tempo run scheduled today. What would you prefer?

A) Easy 30min run (safest) - maintains aerobic base, ACWR stays manageable
B) Move tempo to Thursday - 2 extra recovery days
C) Proceed as planned - moderate risk (~15% injury probability)
```

## Scenario 7: Plan Regeneration After Injury

```bash
# After injury recovery, assess current fitness
sce status  # Check CTL drop during recovery

# Sync recent activities to understand training interruption
sce sync --since 30d

# Regenerate plan with conservative restart
sce goal --type [same_goal] --date [adjusted_date]

# Present updated plan for review
# Adjust phases: longer base rebuild, shorter peak
```

**Coaching Considerations:**

- CTL will have dropped during recovery - use new CTL as baseline
- Volume restart: 50-70% of pre-injury volume
- Gradual ramp: slower progression than initial plan
- Monitor triggers closely: ACWR, readiness, wellness signals

## Scenario 8: Multi-Sport Conflict Resolution

```bash
# Check upcoming week's plan
sce week

# Athlete mentions: "I have a climbing competition Saturday"
# Review lower-body load implications

# Use AskUserQuestion to resolve conflict
```

**Conflict Resolution Pattern:**

```
I see you have a long run Saturday (18km, 90min).
You mentioned a climbing competition that day.

Options:
A) Move long run to Sunday - fresh legs for competition
B) Downgrade Saturday to easy 30min - light stimulus, legs ready
C) Skip Saturday run - prioritize competition (equal priority policy)

Based on your "equal priority" policy, I'm leaning toward A or B.
```

## Scenario 9: Race Week Preparation

```bash
# 1 week before race
sce today --date [race_date - 7 days]

# Check taper plan
sce week

# Verify readiness trends
sce status
```

**Race Week Coaching:**

- Confirm TSB is moving toward +5 to +15 (race ready zone)
- Verify taper is reducing volume (typically 70% → 50% → 30%)
- Check readiness score (should be trending up to 70-85+)
- Remind about rest, nutrition, logistics

## Scenario 10: Post-Race Recovery

```bash
# Day after race - check status
sce status  # TSB will be very negative

# Recommend recovery period based on race distance:
# - 5K: 3-5 days easy
# - 10K: 5-7 days easy
# - Half: 7-10 days easy
# - Marathon: 14-21 days easy + full recovery week

# Monitor readiness and wellness signals
sce week  # Track recovery progression
```

**Recovery Coaching:**

- Force easy pace regardless of how athlete feels
- Watch for readiness to return to >60 before resuming quality work
- Use multi-sport activities wisely: yoga, easy cycling OK; climbing/HIIT not OK
- New goal setting: wait until readiness stabilizes

## Scenario 11: Pre-Plan Constraints Discussion (BEFORE Plan Generation)

**Context**: After profile setup and goal setting, BEFORE calling `sce plan regen`

**Why This Matters**:
- Generic defaults (2-4 runs/week, all 7 days available, 90min sessions) don't reflect reality
- Plan design requires knowing actual schedule constraints
- Long runs >90min essential for marathon training - must confirm athlete can do them
- Other sport commitments must be locked in before workout placement

**What Happens if Skipped**:
- Plan assigns runs to days athlete can't train
- Long runs capped at 90min when athlete could do 3 hours
- Conflicts with other sports not managed → athlete manually moves workouts weekly (bad UX)

### Conversation Pattern

**Constraints to Discuss**:

1. **Run frequency**: "How many runs per week are realistic for you?"
2. **Available days**: "Which days can you typically run? Work commitments, family, other sports?"
3. **Session duration**: "What's the longest run you can do? Marathon training means 2-3hr long runs."
4. **Other sport commitments**: "I see you climb. Which days/times? Fixed or flexible?"
5. **Time of day**: "Morning or evening runs? Any preference?"

### Example Dialogue

```
Coach: "Before I design your marathon plan, let me understand your schedule.
       How many runs per week are realistic?"

Athlete: "I can do 3-4 runs consistently. Maybe 5 on a good week, but let's plan for 4."

Coach: "Perfect, 4 runs/week is solid for marathon training. Which days work best?
       I know you climb - when are those sessions?"

Athlete: "I climb Friday evenings at the gym. Weekends usually open.
       Weekdays I can run Tuesday and Thursday mornings before work."

Coach: "Got it. Tentatively: Tuesday, Thursday, Saturday, Sunday for runs,
       Friday reserved for climbing. Does that work?"

Athlete: "Yes, that's ideal."

Coach: "One more thing - what's the longest run you can do? Marathon training
       means long runs of 2-3 hours eventually."

Athlete: "Weekends I can do 2-3 hours no problem. Weekdays max 90 minutes."

Coach: "Excellent! Let me update your profile with these constraints."
```

### Update Profile with Constraints

```bash
sce profile set \
  --min-run-days 4 \
  --max-run-days 4 \
  --available-days "tuesday,thursday,saturday,sunday" \
  --max-session-minutes 120
```

### Common Constraint Patterns

| Athlete Type | Run Days/Week | Available Days | Max Session | Notes |
|--------------|---------------|----------------|-------------|-------|
| Full-time worker, climbing Fridays | 4 | Tue, Thu, Sat, Sun | 180min weekend | Protect Friday climbing |
| Parent, evenings only | 3 | Mon, Wed, Sat | 120min | Early morning long run Saturday |
| Multi-sport (cycling Sat) | 3-4 | Mon, Wed, Thu, Sun | 90min weekday, 150min Sun | Sunday long run only |
| Flexible schedule | 4-5 | Any 5 days | 180min | Optimize for recovery |

### Integration with Conflict Policy

Constraints + conflict policy = complete scheduling system:

- **Constraints**: Define WHEN athlete CAN train
- **Conflict policy**: Define WHAT HAPPENS when conflicts arise within available days

Example:
- Constraint: "Can run Tue/Thu/Sat/Sun, Friday climbing"
- Conflict policy: "ask_each_time"
- Result: Coach proposes runs on available days, asks when conflicts occur within those days

### Workflow Position

**Correct Flow**:
1. Profile setup (basic info, sport priorities, conflict policy)
2. **→ THIS SCENARIO: Constraints discussion** ←
3. Goal setting
4. Plan skeleton generation (`sce plan regen`)
5. Plan design (weekly structure)
6. Plan presentation and approval

---

## Scenario 12: Weekly Planning Transition Workflow

**Context**: Athlete has completed Week 1 of their training plan. Time to analyze the week and generate Week 2 workouts using the progressive disclosure workflow.

**Why This Matters**:
- **Adaptive planning**: Each week is tailored based on actual training response, not rigid advance planning
- **Reduced errors**: Smaller scope (1 week vs 4 weeks) = fewer date/calculation mistakes
- **Natural coaching rhythm**: Weekly check-ins + weekly planning = seamless coaching experience
- **Authentic coaching**: Real coaches plan week-by-week based on athlete response

**Progressive Disclosure Principle**:
- Macro plan (16 weeks) provides structure: phases, volume targets, CTL projections
- Weekly plan (1 week) provides execution: detailed workouts with exact distances, paces, purposes
- Each week generated AFTER previous week completes → informed by actual adherence, fatigue, adaptation

### Workflow: Weekly Analysis → Weekly Planning

```bash
# ========================================
# PART 1: Analyze Completed Week (Week 1)
# ========================================

# Check what week we just completed
sce dates today
# Returns: {"date": "2026-01-26", "day_name": "Sunday", "week_boundary": "end"}

# Get weekly summary
sce week
# Shows: Week 1 (Jan 20-26), 4 workouts, 23 km total

# Analyze adherence
sce analysis adherence --start 2026-01-20 --end 2026-01-26
# Returns: 100% completion (4/4 runs completed)

# Analyze intensity distribution
sce analysis intensity --start 2026-01-20 --end 2026-01-26
# Returns: 82% easy, 18% hard (good 80/20 compliance)

# Check current metrics (post-week-1)
sce status
# Returns: CTL 46.2 (+2.2 from 44.0), ACWR 1.05 (safe), readiness 72 (good)

# ========================================
# PART 2: Weekly Analysis Interpretation
# ========================================

# Coach analyzes results:
# ✓ Adherence: 4/4 runs completed - excellent
# ✓ Intensity: 82% easy, 18% hard - good 80/20 discipline
# ✓ CTL progression: +2.2 points (target was +2.0) - on track
# ✓ ACWR: 1.05 (safe zone) - no injury risk spike
# ✓ Readiness: 72 (good) - ready for next week's progression
# ✓ Activity notes: No pain/injury keywords detected

# Conclusion: Athlete handled Week 1 well → proceed with Week 2 as planned

# ========================================
# PART 3: Check Macro Plan for Week 2
# ========================================

# Load macro plan to see Week 2 target
sce plan show --format json | jq '.weeks[] | select(.week_number == 2)'
# Returns:
# {
#   "week_number": 2,
#   "phase": "base",
#   "start_date": "2026-01-27",
#   "end_date": "2026-02-02",
#   "target_volume_km": 26.0,
#   "workout_structure_hints": {
#     "quality": {"max_sessions": 1, "types": ["strides_only"]},
#     "long_run": {"emphasis": "steady", "pct_range": [24, 30]},
#     "intensity_balance": {"low_intensity_pct": 0.90}
#   },
#   "is_recovery_week": false
#   // NO workout_pattern - this is macro plan (structure only + hints)
# }

# ========================================
# PART 4: Assess if Volume Adjustment Needed
# ========================================

# Decision logic:
# - Adherence 100% → no downgrade needed
# - ACWR 1.05 (safe) → no injury risk
# - Readiness 72 (good) → can handle progression
# - No illness/injury signals → proceed as planned
# → Use volume_adjustment = 1.0 (no change from macro target)

# If athlete had struggled:
# - Adherence <80% → consider 0.95 adjustment
# - ACWR >1.3 → consider 0.9 adjustment
# - Readiness <50 → consider skipping week or 0.85 adjustment

# ========================================
# PART 5: Recalibrate VDOT if Needed
# ========================================

# Check if VDOT recalibration needed:
# - Recent race result? No
# - Breakthrough workout? No (Week 1 was all easy runs)
# - Consistent pace improvements? Too early (only 1 week)
# → Keep VDOT at 48.0 (no recalibration)

# If there WAS a signal:
# sce vdot calculate --race-type 10k --time 42:00
# sce vdot paces --vdot 49

# ========================================
# PART 6: Generate Week 2 Workouts
# ========================================

# Generate detailed workouts for Week 2
sce plan generate-week \
  --week 2 \
  --run-days "0,2,4,5" \
  --long-run-day 5 \
  --long-run-pct 0.45 \
  --easy-run-paces "6:15-6:45" \
  --long-run-pace "6:15-6:45" \
  --out /tmp/weekly_plan_w2.json

# Returns:
# {
#   "ok": true,
#   "message": "Weekly plan JSON generated for week 2",
#   "data": {
#     "week_number": 2,
#     "file": "/tmp/weekly_plan_w2.json",
#     "phase": "base",
#     "target_volume_km": 26.0
#   }
# }

# ========================================
# PART 7: Validate Week 2 Plan
# ========================================

# Validate BEFORE presenting to athlete
sce plan validate --file /tmp/weekly_plan_w2.json

# Returns:
# {
#   "ok": true,
#   "message": "Weekly plan validated: 0 errors, 0 warnings",
#   "data": {
#     "overall_ok": true,
#     "violations": [],
#     "warnings": [],
#     "summary": {
#       "weeks_checked": 1,
#       "critical_issues": 0,
#       "warnings": 0,
#       "volume_accuracy": "100.0%",
#       "minimum_duration_compliance": "100%"
#     }
#   }
# }

# ✓ Validation passed - safe to present

# ========================================
# PART 8: Present Week 2 to Athlete
# ========================================
```

**Coach presents to athlete**:

```
"Great week! You completed all 4 runs and maintained excellent 80/20 intensity
distribution. Your CTL increased by 2.2 points to 46.2 - right on target.
ACWR is 1.05 (safe zone) and your readiness score is 72 (good), so you're
ready for Week 2's progression.

Here's your Week 2 plan (Jan 27 - Feb 2):

**Volume**: 26 km (+13% from Week 1)
**Structure**: 3 easy runs + 1 long run
**Phase**: Base (aerobic foundation)

**Workouts**:
- Monday: Easy run (4.5 km, 31 min, 6:15-6:45 pace) - Recovery from long run
- Wednesday: Easy run (5.0 km, 34 min, 6:15-6:45 pace) - Midweek maintenance
- Friday: Easy run (4.5 km, 31 min, 6:15-6:45 pace) - Pre-long run freshness
- Saturday: Long run (12.0 km, 72 min, 6:15-6:45 pace) - Build endurance

**Key Points**:
- Volume increases 13% (within safe 10-15% range)
- All runs at E-pace (conversational) - continue building aerobic base
- Long run increases from 10.5 km → 12.0 km (progressive overload)
- Rest days: Tuesday, Thursday, Sunday (recovery + climbing schedule)

Does this look good to you? Any adjustments needed?"
```

**Athlete**: "Looks perfect! Let's do it."

```bash
# ========================================
# PART 9: Save Week 2 Plan
# ========================================

# After athlete approval, save to system
sce approvals approve-week --week 2 --file /tmp/weekly_plan_w2.json
sce plan populate --from-json /tmp/weekly_plan_w2.json --validate

# Returns:
# {
#   "ok": true,
#   "message": "Training plan populated with 1 week",
#   "data": {
#     "weeks_added": 1,
#     "workouts_added": 4,
#     "date_range": "2026-01-27 to 2026-02-02"
#   }
# }

# Week 2 now available for daily coaching
sce today  # Will show Monday's workout (4.5 km easy run)

# ========================================
# PART 10: Repeat Next Week
# ========================================

# After Week 2 completes (Feb 2), repeat this workflow:
# 1. Analyze Week 2 adherence, intensity, CTL progression
# 2. Check macro plan for Week 3 target
# 3. Assess volume adjustment (did athlete struggle? Need downgrade?)
# 4. Recalibrate VDOT if performance breakthrough
# 5. Generate Week 3 workouts
# 6. Validate
# 7. Present
# 8. Approve + save after approval
```

### Alternative Scenarios Within Workflow

#### Scenario A: Volume Adjustment Needed (Athlete Struggled)

```bash
# After Week 2 analysis:
# - Adherence: 75% (3/4 runs completed)
# - ACWR: 1.42 (elevated risk)
# - Readiness: 48 (low)
# - Activity notes: "felt tired all week"

# Decision: Reduce Week 3 volume by 10%
sce plan generate-week \
  --week 3 \
  --run-days "0,2,4,6" \
  --long-run-day 6 \
  --long-run-pct 0.45 \
  --easy-run-paces "6:20-6:50" \
  --long-run-pace "6:20-6:50" \
  --out /tmp/weekly_plan_w3.json

# Macro target: 30 km → Adjusted target: 27 km
```

**Coach explains**:
```
"I noticed Week 2 was tough - you missed one run and noted feeling tired.
Your ACWR jumped to 1.42 (elevated injury risk) and readiness is 48 (low).

Let's reduce Week 3 volume by 10% to let your body catch up. Instead of
30 km, we'll do 27 km - still progressing, but more conservatively.

This is exactly what adaptive planning is for!"
```

#### Scenario B: VDOT Recalibration (Breakthrough Performance)

```bash
# During Week 4, athlete runs a 10K race: 42:00 (previous estimate was 45:00)

# Recalibrate VDOT
sce vdot calculate --race-type 10k --time 42:00
# Returns: VDOT 49.0 (was 48.0)

sce vdot paces --vdot 49
# Get new training paces (all ~5 sec/km faster)

# Generate Week 5 with updated VDOT
sce plan generate-week \
  --week 5 \
  --run-days "0,2,4,6" \
  --long-run-day 6 \
  --long-run-pct 0.45 \
  --easy-run-paces "6:10-6:40" \
  --long-run-pace "6:10-6:40" \
  --out /tmp/weekly_plan_w5.json
```

**Coach explains**:
```
"Congratulations on that 10K! 42:00 is a significant breakthrough - your
VDOT is now 49 (up from 48). This means your training paces will be about
5 seconds per km faster going forward.

New E-pace: 6:10-6:40 (was 6:15-6:45)
New T-pace: 4:50-5:05 (was 4:55-5:10)

Week 5 workouts will reflect these updated paces. Your fitness is improving!"
```

#### Scenario C: Schedule Conflict (Need to Adjust Run Days)

```bash
# Athlete: "I have a work trip Thursday-Friday next week, can we shift workouts?"

# Option 1: Regenerate with profile update
sce profile set --available-days "monday,tuesday,saturday,sunday"  # Remove Thu/Fri

sce plan generate-week \
  --week 5 \
  --run-days "0,1,5,6" \
  --long-run-day 6 \
  --long-run-pct 0.45 \
  --easy-run-paces "6:10-6:40" \
  --long-run-pace "6:10-6:40" \
  --out /tmp/weekly_plan_w5.json

# System generates workouts only on Mon, Tue, Sat, Sun

# Option 2: Manually move workouts (for one-time change)
# Coach: "Let's move Thursday's easy run to Wednesday instead"
```

### Key Benefits of Weekly Planning

1. **Maximum adaptability**: Respond immediately to illness, injury, schedule changes
2. **Reduced errors**: 7 days vs 28 days = 75% fewer dates to calculate
3. **Natural coaching rhythm**: Weekly check-ins already happen → seamless integration
4. **Authentic coaching**: Real coaches don't plan 4 weeks in advance rigidly
5. **Data-informed decisions**: Each week uses most recent CTL, ACWR, readiness, adherence

### Macro Plan Still Provides Structure

The 16-week macro plan remains critical:
- **Phase boundaries**: When to introduce tempo runs, intervals, peak volume, taper
- **Volume trajectory**: Where we're headed (23 km → 55 km → 18 km)
- **CTL projections**: Expected fitness at key milestones
- **Recovery week schedule**: Every 4th week at 70% volume

**Weekly planning executes the macro structure with real-time adaptation.**

### Integration with weekly-analysis Skill

The `weekly-analysis` skill includes Steps 8-14 for seamless weekly planning:
- Step 8: Check macro plan for next week
- Step 9: Assess volume adjustment
- Step 10: Recalibrate VDOT if needed
- Step 11: Generate next week's workouts
- Step 12: Validate plan
- Step 13: Present to athlete
- Step 14: Save after approval

**Result**: Athlete experiences weekly check-ins as a single continuous conversation,
not separate "analysis" and "planning" sessions.

---

## Tips for Effective Scenario-Based Coaching

1. **Always start with data**: Run `sce status` or `sce today` before giving advice
2. **Reference actual metrics**: Don't say "rest today" - say "Your ACWR is 1.5 (danger) and readiness is 35 (very low) - let's rest"
3. **Use AskUserQuestion for choices**: Present options with trade-offs, let athlete decide
4. **Explain the why**: Link recommendations to CTL, ACWR, readiness, or training phase
5. **Track patterns**: Use M13 memories to store recurring issues or preferences

## See Also

- [CLI Command Index](cli/index.md) - Complete CLI command documentation
- [Training Methodology](methodology.md) - Understanding metrics and training principles
- [API Layer Spec](../specs/api_layer.md) - Python API for scripting
