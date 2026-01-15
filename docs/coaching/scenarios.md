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

## Tips for Effective Scenario-Based Coaching

1. **Always start with data**: Run `sce status` or `sce today` before giving advice
2. **Reference actual metrics**: Don't say "rest today" - say "Your ACWR is 1.5 (danger) and readiness is 35 (very low) - let's rest"
3. **Use AskUserQuestion for choices**: Present options with trade-offs, let athlete decide
4. **Explain the why**: Link recommendations to CTL, ACWR, readiness, or training phase
5. **Track patterns**: Use M13 memories to store recurring issues or preferences

## See Also

- [CLI Reference](cli_reference.md) - Complete CLI command documentation
- [Training Methodology](methodology.md) - Understanding metrics and training principles
- [API Layer Spec](../specs/api_layer.md) - Python API for scripting
