---
name: first-session
description: Onboard new athletes with complete setup workflow including authentication, activity sync, profile creation, goal setting, and constraints discussion. Use when athlete requests "let's get started", "set up my profile", "new athlete onboarding", or "first time using the system".
allowed-tools: Bash, Read, Write, AskUserQuestion
---

# First Session: Athlete Onboarding

## Overview

This skill guides you through complete athlete onboarding, from authentication to goal setting. The workflow ensures historical activity data is available before profile setup, enabling data-driven questions instead of generic prompts.

**Why historical data matters**: With 120 days of Strava history synced, you can ask "I see you average 35km/week - should we maintain this?" instead of "How much do you run?" (no context).

## Workflow

### Step 1: Check Authentication (CRITICAL - Always First)

Historical activity data from Strava is essential for intelligent coaching. Without it, you're coaching blind with CTL=0.

**Commands**:

```bash
sce auth status
```

**Handle exit codes**:

- **Exit code 0** (authenticated): Proceed to Step 2
- **Exit code 3** (expired/missing): Guide OAuth flow (see below)
- **Exit code 2** (config missing): Run `sce init` first

**If auth expired/missing** (exit code 3):

1. Explain why you need auth: "I need access to your Strava data to provide intelligent coaching based on your actual training patterns."
2. Generate OAuth URL: `sce auth url`
3. Instruct athlete: "Open this URL in your browser, authorize the app, and copy the code from the final page."
4. Wait for athlete to provide code
5. Exchange code for tokens: `sce auth exchange --code CODE_FROM_ATHLETE`
6. Confirm success: "Great! I can now access your training history."

### Step 2: Sync Activities

Import 120 days (4 months) of activity history to establish baseline metrics.

**Commands**:

```bash
sce sync
```

**What this provides**:

- Activities imported (running, climbing, cycling, etc.)
- CTL/ATL/TSB calculated from historical load
- Initial metrics baseline (not starting from zero)
- Activity patterns (training days, volume, sport distribution)

**Success message**: "Imported X activities from the last 120 days. Your CTL is Y (interpretation)."

### Step 3: Review Historical Data

Before asking profile questions, understand what the data shows.

**Commands**:

```bash
sce status    # Get baseline metrics (CTL/ATL/TSB/ACWR)
sce week      # See recent training patterns
sce profile analyze  # Get profile suggestions from synced data
```

**What to extract from analysis**:

- `max_hr_observed`: Suggests max HR value
- `avg_hr_mean`: Typical working HR
- `weekly_run_km_avg`: Average weekly running volume
- `training_days_distribution`: Which days athlete typically trains
- `sport_distribution`: Multi-sport breakdown (run %, climb %, etc.)
- `activity_gaps`: Potential injury/illness breaks

**Use this data to inform profile setup**: Instead of generic questions, reference actual numbers.

### Step 4: Profile Setup (Natural Conversation)

Use **natural conversation** for text/number inputs. Use **AskUserQuestion ONLY** for policy decisions with trade-offs.

#### 4a. Basic Info (Natural Conversation)

**Name**:

```
Coach: "What's your name?"
Athlete: "Alex"
Coach: [Store for later profile creation]
```

**Age**:

```
Coach: "How old are you?"
Athlete: "32"
Coach: [Store for later]
```

**Max HR** (reference analyzed data):

```
Coach: "Looking at your Strava data, your peak HR recorded is 199 bpm. Should we use that as your max HR?"
Athlete: "Yeah, that sounds right" OR "Actually, I think it's 190"
Coach: [Store actual value]
```

#### 4b. Injury History (Context-Aware with Memory System)

**Check for activity gaps first** (from `sce profile analyze` or `sce status`):

- CTL drops from 45 → 20 over 3 weeks
- 14+ day gaps between activities
- Activity notes mention pain/injury keywords

**If gap detected**:

```
Coach: "I noticed you had a break from running in November (2-week gap, CTL dropped from 44 to 28). Was that due to injury?"
Athlete: "Yeah, left knee tendonitis. It's healed now but I watch mileage."
```

**If no obvious gaps**:

```
Coach: "Any past injuries I should know about? Helps me watch for warning signs and adjust training load appropriately."
```

**IMPORTANT: Store each injury as a structured memory (NOT in profile.injury_history field)**

**Storage approach**: Create separate memory for each distinct injury with specific tags.

**Examples**:

1. **Past resolved injury**:
   ```bash
   sce memory add --type INJURY_HISTORY \
     --content "Left knee tendonitis Nov 2023, fully healed, watches mileage" \
     --tags "body:knee,year:2023,status:resolved,caution:mileage" \
     --confidence high
   ```

2. **Frequency-triggered issue**:
   ```bash
   sce memory add --type INJURY_HISTORY \
     --content "Right achilles tightness when running >3 consecutive days" \
     --tags "body:achilles,trigger:frequency,threshold:3-days,status:current" \
     --confidence high
   ```

3. **Volume-triggered issue**:
   ```bash
   sce memory add --type INJURY_HISTORY \
     --content "Left knee pain after long runs >18km, resolved with reduced volume in 2024" \
     --tags "body:knee,trigger:long-run,threshold:18km,year:2024,status:resolved" \
     --confidence high
   ```

4. **Past injury with resolution strategy**:
   ```bash
   sce memory add --type INJURY_HISTORY \
     --content "IT band syndrome 2023, resolved with hip strengthening and form adjustments" \
     --tags "body:it-band,year:2023,status:resolved,solution:strength,solution:form" \
     --confidence high
   ```

**Why use memory system instead of profile field**:
- Each injury is independently searchable
- Rich tagging (body part, trigger type, threshold, status, solution)
- Automatic deduplication if athlete mentions same injury again
- Confidence scoring for recurring patterns
- Can reference resolution strategies in future coaching

**Tag conventions**:
- `body:{part}` - knee, achilles, hamstring, it-band, etc.
- `trigger:{type}` - frequency, long-run, volume, speed, etc.
- `threshold:{value}` - 3-days, 18km, 50km-week, etc.
- `status:{state}` - current, resolved, monitoring, etc.
- `solution:{method}` - rest, strength, form, volume-cap, etc.
- `year:{YYYY}` - When injury occurred
- `caution:{area}` - Ongoing vigilance areas

#### 4c. Sport Priority (Natural Conversation)

Reference sport distribution from analysis:

```
Coach: "Your synced activities show running (28%) and climbing (42%). Which is your primary sport, or are they equally important?"
Athlete: "I'd say they're equal - I'm committed to both"
```

Options: `"running"` (PRIMARY), `"equal"` (EQUAL), `"climbing"` (or other sport name = SECONDARY)

#### 4d. Conflict Policy (AskUserQuestion - ONLY APPROPRIATE PLACE)

This is a **decision with trade-offs**, perfect for AskUserQuestion.

**Prompt**:

```
"When there's a conflict between running and climbing - like a long run and a climbing comp on the same day - how should I handle it?"
```

**Options**:

1. **Ask me each time** (most flexible)

   - I'll present options and trade-offs for each conflict
   - You decide based on current priorities and how you feel
   - Best for athletes with variable schedules

2. **Climbing wins by default** (protect primary sport)

   - Running workouts get adjusted around climbing schedule
   - Running plan adapts to accommodate climbing commitments
   - Best for competitive climbers in season

3. **Running goal wins** (prioritize race prep)
   - Keep key running workouts unless injury risk
   - Climbing scheduled around critical runs
   - Best when training for a specific race

**Store as**: `conflict_policy` = `"ask_each_time"` | `"primary_sport_wins"` | `"running_goal_wins"`

#### 4e. Create Profile

Once all data collected, create profile:

```bash
sce profile set --name "Alex" --age 32 --max-hr 190 --conflict-policy ask_each_time
```

**Note**: Injury history is stored separately in memory system (see Step 4b above), not in profile.

### Step 5: Goal Setting

Discuss race goals and training objectives.

**Questions** (natural conversation):

- "What are you training for?"
- "When is your race?" (date)
- "What's your goal time?" (optional - can be calculated from VDOT later)

**Command**:

```bash
sce goal --type half_marathon --date 2026-06-01
# Optional: --time "1:30:00" if athlete has specific time goal
```

**Goal types**: `5k`, `10k`, `half_marathon`, `marathon`

### Step 6: Constraints Discussion (Before Plan Generation)

**CRITICAL**: Before designing any training plan, discuss constraints.

**Questions to ask** (natural conversation):

1. **Run frequency**: "How many days per week can you realistically run?" (3-6 days typical)
2. **Available days**: "Any days of the week that work best? I see you typically train Tuesdays and weekends."
3. **Session duration**: "What's the longest time you can spend on a long run?" (90-180 minutes typical)
4. **Other sport commitments**: "Are your climbing days fixed or flexible?" (e.g., "Tuesdays are always climbing comp")
5. **Time of day preference**: "Morning or evening runs?" (optional, helps with scheduling)

**Store via profile**:

```bash
sce profile set --max-run-days 4 --available-days "tuesday,thursday,saturday,sunday" --preferred-days "saturday,sunday" --max-session-minutes 120
```

### Step 7: Suggest Next Steps

After onboarding complete, suggest plan generation:

```
"Great! Your profile is set up. I can see your CTL is 44 (solid recreational fitness) with a half marathon goal on June 1st.

That gives you 20 weeks. Based on your current fitness and constraints (4 run days/week, climbing Tuesdays), I recommend designing a training plan.

Would you like me to create a personalized plan now?"
```

If athlete agrees, activate the `training-plan-design` skill (transition to plan generation workflow).

---

## Decision Trees

### Q: Athlete has no recent Strava data

**Scenario**: Sync returns 0 activities or very few (<10 in 120 days).

**Response**:

```
"I see you don't have much recent activity on Strava (or this is a new account). No problem - we'll start from scratch.

Your CTL will start at 0, which means we'll build your training volume gradually from a conservative baseline."
```

**Profile setup adjustments**:

- Ask directly: "How much have you been running weekly?" (since no data to reference)
- Use stated volume to estimate starting CTL equivalent

### Q: Athlete refuses Strava auth

**Scenario**: Athlete declines OAuth authorization.

**Response**:

```
"No problem - you can still use the system, but I won't have access to historical activity data.

This means:
- Your CTL will start at 0
- I won't see your climbing/cycling activities automatically
- You'll need to manually log activities via `sce log` command

We can still create a great plan - I just won't have the historical context."
```

**Proceed with profile setup**, relying on stated values instead of synced data.

### Q: Multiple sports with complex schedule

**Scenario**: Athlete does running + climbing + cycling with fixed commitments.

**Approach**:

1. Identify fixed commitments: "Which days are non-negotiable for climbing/cycling?"
2. Map running around fixed days
3. Consider lower-body load: "Climbing doesn't impact legs much, so easy runs are fine the next day. Cycling does, so we'll avoid hard runs after long rides."
4. Set conflict policy carefully (likely `ask_each_time` for complex schedules)

**Store all constraints** in profile for plan generation to reference.

---

## Common Pitfalls

### 1. Asking for data that's already available

❌ **Bad**: "How much do you run per week?"
✅ **Good**: "I see you average 22.5 km/week - should we maintain this volume or adjust?"

**Always check `sce profile analyze` first** and reference actual numbers.

### 2. Using AskUserQuestion for free-form text

❌ **Bad**: AskUserQuestion with "What's your name?" options
✅ **Good**: Natural conversation → "What's your name?" → Store response

**AskUserQuestion is ONLY for conflict policy** (trade-off decision).

### 3. Skipping auth check

❌ **Bad**: Proceeding directly to profile setup without auth
✅ **Good**: Always check `sce auth status` first, guide OAuth if needed

**Auth must be first** - historical data enables intelligent profile setup.

### 4. Not discussing constraints before plan generation

❌ **Bad**: Creating plan without knowing athlete's schedule
✅ **Good**: Ask about run days, session duration, other sports BEFORE planning

**Constraints shape the entire plan structure** - must know upfront.

### 5. Generic injury questions

❌ **Bad**: "Any injuries?" (no context)
✅ **Good**: "I see a 2-week training gap in November with CTL drop - was that injury-related?"

**Use activity gaps as conversation starters** when asking about injury history.

---

## Example Session

**User**: "I want to start training for a half marathon"

**Coach**:

```
Great! Let's get you set up. First, I need to check your Strava authentication so I can access your training history.

[Runs: sce auth status]
[Exit code 3 - not authenticated]

Your Strava account isn't connected yet. Let me generate an authorization link for you.

[Runs: sce auth url]

Here's your authorization URL: https://strava.com/oauth/authorize?...

Please:
1. Open this URL in your browser
2. Click "Authorize" to grant access
3. Copy the code from the final page
4. Paste it here

Once you've authorized, I'll import your training history.
```

**Athlete**: [Provides code: ABC123]

**Coach**:

```
[Runs: sce auth exchange --code ABC123]

Perfect! I'm now connected to your Strava account. Let me sync your activities.

[Runs: sce sync]

Great! I've imported 93 activities from the last 120 days. Let me analyze your training patterns.

[Runs: sce status, sce profile analyze]

I can see:
- Your CTL is 44 (solid recreational fitness level)
- You average 22.5 km/week running
- You also do climbing (42% of activities) and yoga (14%)
- You typically train on Tuesdays, Thursdays, and weekends

Let's set up your profile. What's your name?
```

**Athlete**: "Alex"

**Coach**: "And how old are you?"

**Athlete**: "32"

**Coach**:

```
Looking at your Strava data, your peak heart rate recorded is 199 bpm. Should we use that as your max HR?
```

**Athlete**: "Yes, that sounds right"

**Coach**:

```
I noticed you had a 2-week gap in November where your CTL dropped from 44 to 28. Was that due to injury or just a break?
```

**Athlete**: "Yeah, left knee tendonitis. It's fully healed now but I watch my mileage."

**Coach**:

```
Good to know - I'll keep that in mind when designing your plan.

Your activities show running (28%) and climbing (42%). Which is your primary sport, or are they equally important?
```

**Athlete**: "They're equal - I'm committed to both"

**Coach**:

```
Perfect. One last question: When there's a conflict between running and climbing - like a long run and a climbing comp on the same day - how should I handle it?

[Uses AskUserQuestion with 3 options: ask each time, climbing wins, running wins]
```

**Athlete**: [Selects: "Ask me each time"]

**Coach**:

```
[Runs: sce profile set --name "Alex" --age 32 --max-hr 199 --conflict-policy ask_each_time]
[Runs: sce profile set --injury-history "Left knee tendonitis Nov 2025, fully healed"]

Great! Your profile is set up. Now, tell me about your half marathon goal. When is the race?
```

**Athlete**: "June 1st, 2026"

**Coach**:

```
[Runs: sce goal --type half_marathon --date 2026-06-01]

Perfect! That gives you 20 weeks. Based on your current fitness (CTL 44) and multi-sport commitments, I can design a personalized training plan.

Before I create the plan, a few quick questions about your schedule:
- How many days per week can you realistically run? (I see you typically do 3-4)
- Are your climbing days fixed or flexible?
- What's the longest time you can spend on a long run?

[Collects constraints via natural conversation]
[Stores via: sce profile set --max-run-days 4 --available-days "..." --time-preference morning]

Excellent! I have everything I need. Would you like me to design your training plan now?
```

[If yes → Activate `training-plan-design` skill]

---

## Success Criteria

**Onboarding is complete when**:

1. ✅ Authentication successful (sce auth status returns 0)
2. ✅ Activities synced (120 days of history)
3. ✅ Profile created with name, age, max HR, conflict policy
4. ✅ Injury history recorded (if applicable)
5. ✅ Goal set (race type, date)
6. ✅ Constraints discussed (run days, duration, other sports)
7. ✅ Athlete ready for plan generation

**Quality checks**:

- All data referenced from `sce profile analyze` (not generic questions)
- AskUserQuestion used ONLY for conflict policy
- Natural conversation for all text/number inputs
- Injury history captured in athlete's own words

**Handoff to next skill**: "Would you like me to design your training plan now?" → Activate `training-plan-design` skill

---

## Links to Additional Resources

- **Complete profile commands**: See [CLI Reference - Profile Commands](../../../docs/coaching/cli_reference.md#profile-commands)
- **OAuth troubleshooting**: See [CLI Reference - Authentication](../../../docs/coaching/cli_reference.md#authentication-commands)
- **Training methodology overview**: See [Coaching Methodology](../../../docs/coaching/methodology.md)
- **Detailed onboarding scenario**: See [Coaching Scenarios - First Session](../../../docs/coaching/scenarios.md#scenario-1-first-session)
