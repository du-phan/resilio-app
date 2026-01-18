---
name: first-session
description: Onboard new athletes with complete setup workflow including authentication, activity sync, profile creation, goal setting, and constraints discussion. Use when athlete requests "let's get started", "set up my profile", "new athlete onboarding", or "first time using the system".
allowed-tools: Bash, Read, Write, AskUserQuestion
---

# First Session: Athlete Onboarding

## Overview

This skill guides complete athlete onboarding from authentication to goal setting. The workflow ensures historical data is available before profile setup, enabling data-driven questions instead of generic prompts.

**Why historical data matters**: With 120 days synced, ask "I see you average 35km/week - should we maintain this?" instead of "How much do you run?" (no context).

---

## Workflow

### Step 1: Check Authentication (CRITICAL - Always First)

Historical activity data from Strava is essential for intelligent coaching. Without it, you're coaching blind with CTL=0.

```bash
sce auth status
```

**Handle exit codes**:
- **Exit code 0**: Authenticated → Proceed to Step 2
- **Exit code 3**: Expired/missing → Guide OAuth flow
- **Exit code 2**: Config missing → Run `sce init` first

**If auth expired/missing** (exit code 3):
1. Explain why: "I need Strava access to provide intelligent coaching based on actual training patterns."
2. Generate URL: `sce auth url`
3. Instruct: "Open URL, authorize, copy code from final page"
4. Wait for athlete to provide code
5. Exchange: `sce auth exchange --code CODE`
6. Confirm: "Great! I can now access your training history."

**For complete OAuth flow and troubleshooting**: See [references/authentication.md](references/authentication.md)

---

### Step 2: Sync Activities

```bash
sce sync
```

**What this provides**:
- 120 days of activity history
- CTL/ATL/TSB calculated from historical load
- Activity patterns (training days, volume, sport distribution)

**Success message**: "Imported X activities. Your CTL is Y (interpretation)."

---

### Step 3: Review Historical Data

**Before asking profile questions, understand what the data shows.**

```bash
sce status                # Baseline metrics (CTL/ATL/TSB/ACWR)
sce week                  # Recent training patterns
sce profile analyze       # Profile suggestions from synced data
```

**Extract from analysis**:
- `max_hr_observed`: Suggests max HR
- `weekly_run_km_avg`: Average weekly volume
- `training_days_distribution`: Which days athlete typically trains
- `sport_distribution`: Multi-sport breakdown
- `activity_gaps`: Potential injury/illness breaks

**Use data to inform profile setup** - reference actual numbers.

---

### Step 4: Profile Setup (Natural Conversation)

**Use natural conversation for text/number inputs. Use AskUserQuestion ONLY for conflict policy.**

#### 4a. Basic Info

**Name & Age** (natural conversation):
```
Coach: "What's your name?"
Athlete: "Alex"
Coach: [Store for later]

Coach: "How old are you?"
Athlete: "32"
Coach: [Store for later]
```

**Max HR** (reference analyzed data):
```
Coach: "Looking at your Strava data, peak HR is 199 bpm. Use that as your max HR?"
Athlete: "Yes" OR "Actually, I think it's 190"
Coach: [Store actual value]
```

#### 4b. Injury History (Context-Aware with Memory System)

**Gather injury signals**:
```bash
sce profile analyze                                      # Check activity gaps
sce activity search --query "pain injury sore" --since 120d  # Search notes
sce activity list --since 90d --has-notes --sport run      # Context
```

**If gap or pain mention detected**:
```
Coach: "I noticed a 2-week gap in November (CTL dropped 44→28). Was that injury-related?"
Athlete: "Yeah, left knee tendonitis. Healed now but I watch mileage."
```

**If no gaps**:
```
Coach: "Any past injuries I should know about? Helps me watch for warning signs."
```

**IMPORTANT: Store each injury as structured memory** (NOT in profile field):

```bash
sce memory add --type INJURY_HISTORY \
  --content "Left knee tendonitis Nov 2023, fully healed, watches mileage" \
  --tags "body:knee,year:2023,status:resolved,caution:mileage" \
  --confidence high
```

**Why memory system**: Independent searchability, rich tagging, deduplication, confidence scoring.

**Tag conventions**:
- `body:{part}`: knee, achilles, hamstring, it-band
- `trigger:{type}`: frequency, long-run, volume, speed
- `threshold:{value}`: 3-days, 18km, 50km-week
- `status:{state}`: current, resolved, monitoring
- `solution:{method}`: rest, strength, form, volume-cap

#### 4c. Sport Priority (Natural Conversation)

Reference sport distribution from analysis:
```
Coach: "Your activities show running (28%) and climbing (42%). Primary sport or equal?"
Athlete: "Equal - committed to both"
```

Options: `"running"` (PRIMARY), `"equal"` (EQUAL), other sport name (SECONDARY)

#### 4d. Conflict Policy (AskUserQuestion - ONLY USE HERE)

**This is a decision with trade-offs** - appropriate for AskUserQuestion.

**Prompt**:
"When there's a conflict between running and climbing - like long run + climbing comp same day - how should I handle it?"

**Options**:
1. **Ask me each time** - Present options/trade-offs per conflict (most flexible)
2. **Climbing wins by default** - Running adjusts around climbing (protect primary sport)
3. **Running goal wins** - Keep key runs unless injury risk (prioritize race prep)

**Store as**: `conflict_policy` = `"ask_each_time"` | `"primary_sport_wins"` | `"running_goal_wins"`

#### 4e. Create Profile

```bash
sce profile set --name "Alex" --age 32 --max-hr 190 --conflict-policy ask_each_time
```

**Note**: Injury history stored separately in memory system.

**For complete field reference (28 fields)**: See [references/profile_fields.md](references/profile_fields.md)

---

### Step 5: Goal Setting

**Questions** (natural conversation):
- "What are you training for?"
- "When is your race?" (date)
- "What's your goal time?" (optional)

```bash
sce goal --type half_marathon --date 2026-06-01
# Optional: --time "1:30:00" if specific goal
```

**Goal types**: `5k`, `10k`, `half_marathon`, `marathon`

---

### Step 6: Constraints Discussion (Before Plan Generation)

**CRITICAL: Discuss constraints before designing plan.**

**Questions** (natural conversation):
1. **Run frequency**: "How many days per week can you realistically run?" (3-6 typical)
2. **Available days**: "Which days work best? I see you typically train Tuesdays and weekends."
3. **Session duration**: "Longest time for a long run?" (90-180 min typical)
4. **Other sports**: "Are climbing days fixed or flexible?"
5. **Time preference**: "Morning or evening runs?" (optional)

**Store constraints**:
```bash
sce profile set --max-run-days 4 --available-days "tuesday,thursday,saturday,sunday" --max-session-minutes 120
```

---

### Step 7: Suggest Next Steps

**After onboarding complete**:
```
"Great! Your profile is set up. CTL is 44 (solid recreational fitness) with half marathon goal June 1st.

That's 20 weeks. Based on your fitness and constraints (4 run days/week, climbing Tuesdays), I recommend designing a training plan.

Would you like me to create a personalized plan now?"
```

**If yes**: Activate `training-plan-design` skill

---

## Quick Decision Trees

### Q: Athlete has no recent Strava data
**Scenario**: Sync returns <10 activities in 120 days

**Response**: "I see minimal recent Strava activity. No problem - we'll start from scratch. CTL starts at 0, building volume gradually from conservative baseline."

**Adjustments**: Ask directly "How much have you been running weekly?" (no data to reference)

### Q: Athlete refuses Strava auth
**Response**: "No problem - you can still use the system, but I won't have historical context. CTL starts at 0, you'll manually log via `sce log`. We can still create a great plan."

**Proceed**: Rely on stated values instead of synced data

### Q: Multiple sports with complex schedule
**Approach**:
1. Identify fixed commitments: "Which days non-negotiable for climbing/cycling?"
2. Map running around fixed days
3. Consider lower-body load: "Climbing doesn't impact legs, cycling does"
4. Set conflict policy carefully (likely `ask_each_time`)

---

## Common Pitfalls

### 1. Asking for data already available
❌ **Bad**: "How much do you run per week?"
✅ **Good**: "I see you average 22.5 km/week - maintain this or adjust?"

**Always check `sce profile analyze` first**

### 2. Using AskUserQuestion for free-form text
❌ **Bad**: AskUserQuestion for "What's your name?"
✅ **Good**: Natural conversation for all text/number inputs

**AskUserQuestion ONLY for conflict policy**

### 3. Skipping auth check
❌ **Bad**: Proceeding to profile without auth
✅ **Good**: Always `sce auth status` first

**Auth must be first** - historical data enables intelligent setup

### 4. Not discussing constraints before planning
❌ **Bad**: Creating plan without knowing schedule
✅ **Good**: Ask run days, duration, other sports BEFORE planning

**Constraints shape entire plan**

### 5. Generic injury questions
❌ **Bad**: "Any injuries?" (no context)
✅ **Good**: "I see 2-week gap in November with CTL drop - injury-related?"

**Use activity gaps as conversation starters**

---

## Success Criteria

**Onboarding complete when**:
1. ✅ Authentication successful (`sce auth status` returns 0)
2. ✅ Activities synced (120 days)
3. ✅ Profile created (name, age, max HR, conflict policy)
4. ✅ Injury history recorded in memory system (if applicable)
5. ✅ Goal set (race type, date)
6. ✅ Constraints discussed (run days, duration, other sports)
7. ✅ Ready for plan generation

**Quality checks**:
- All data referenced from `sce profile analyze`
- AskUserQuestion used ONLY for conflict policy
- Natural conversation for text/number inputs
- Injury history in memory system with proper tags

**Handoff**: "Would you like me to design your training plan now?" → Activate `training-plan-design`

---

## Additional Resources

**Reference material**:
- [Authentication Guide](references/authentication.md) - Complete OAuth flow and troubleshooting
- [Profile Fields Reference](references/profile_fields.md) - All 28 fields with examples

**Complete examples**:
- [Runner Primary Onboarding](examples/example_onboarding_runner_primary.md) - Race-focused athlete

**CLI documentation**:
- [Profile Commands](../../../docs/coaching/cli_reference.md#profile-commands) - Complete command reference
- [Authentication Commands](../../../docs/coaching/cli_reference.md#authentication-commands) - OAuth troubleshooting

**Training methodology**:
- [Coaching Scenarios - First Session](../../../docs/coaching/scenarios.md#scenario-1-first-session) - Detailed walkthrough
- [Coaching Methodology](../../../docs/coaching/methodology.md) - Overview
