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

**Resting HR** (natural conversation):
```
Coach: "What's your morning resting heart rate? (Measure first thing when you wake up)"
Athlete: "Around 52 bpm"
Coach: [Store value]
```

**If athlete doesn't know**: "No problem - you can measure it tomorrow and add later with `sce profile set --resting-hr XX`"

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

### Step 4.5: Personal Bests (PBs) - Race History Capture

**Why this matters**: PBs provide accurate fitness baseline + motivational context. Even old PBs reveal progression/regression.

**CRITICAL**: Strava sync only captures last 120 days. PBs older than 4 months won't be auto-detected. **Manual entry is PRIMARY workflow.**

#### Workflow: Manual Entry FIRST, Then Auto-Import

**Step 1: Ask directly for PBs** (natural conversation):
```
Coach: "What are your personal bests for 5K, 10K, half marathon, and marathon?"
Coach: "When did you run these? Were they official races or GPS efforts?"
```

**Step 2: Manual entry for each PB mentioned**:
```bash
sce race add --distance 10k --time 42:30 --date 2023-06-15 \
  --source official_race --location "City 10K Championship"

sce race add --distance 5k --time 18:45 --date 2022-05-10 \
  --source gps_watch --notes "Parkrun effort"
```

**Race sources**:
- `official_race`: Chip-timed race (highest accuracy)
- `gps_watch`: GPS-verified effort (good accuracy)
- `estimated`: Calculated/estimated (lower accuracy)

**Step 3: Auto-import recent races** (after manual entry):
```bash
sce race import-from-strava --since 120d
```

**What this detects**:
- Strava activities with `workout_type == 1` (race flag)
- Keywords in title/description: "race", "5K", "10K", "HM", "PB", "PR"
- Distance matching standard race distances (±5%)

**Present detected races for confirmation**:
```
Coach: "Found 2 potential races in last 120 days:
- Half Marathon 1:32:00 (Nov 2025) - not yet in race_history
- 10K 43:00 (Dec 2025) - not yet in race_history

Should I add these to your race history?"
```

**If athlete confirms**, add each race:
```bash
sce race add --distance half_marathon --time 1:32:00 --date 2025-11-15 \
  --source gps_watch --location "State Half Marathon"
```

**Step 4: Verify race history**:
```bash
sce race list
```

**Review with athlete**:
```
Coach: "I have your 10K PB at 42:30 (Jun 2023, VDOT 48), 5K at 18:45 (May 2022, VDOT 51). Anything missing?"
```

**Step 5: Store key PBs in memory system** (for long-term context):
```bash
sce memory add --type RACE_HISTORY \
  --content "10K PB: 42:30 (Jun 2023, City 10K, VDOT 48)" \
  --tags "distance:10k,vdot:48,year:2023,pb:true" \
  --confidence high
```

**Why memory + profile**: Profile stores structured race data, memory enables natural language search and long-term pattern detection.

#### Benefits of Race History

1. **Accurate VDOT baseline**: Use historical PBs (even if >120 days old) for training pace calculation
2. **Goal validation**: "Your 10K PB (VDOT 48) predicts 1:25 half, is 1:20 realistic?"
3. **Motivational context**: "Let's rebuild to your 42:30 fitness"
4. **Progression tracking**: Compare current VDOT estimate to peak PB VDOT over time

#### Common Scenarios

**Q: Athlete says "I don't remember exact times"**
- **Response**: "No problem - we can estimate. What's your rough 5K or 10K time?"
- Use `--source estimated` and add note: `--notes "Athlete estimate, not official"`

**Q: Athlete has no race history**
- **Response**: "No PBs yet? We'll establish baseline from tempo workouts. First quality run will give us VDOT estimate."
- Skip race entry, use `sce vdot estimate-current` after first tempo workout

**Q: Old PBs from years ago**
- **Response**: "That 42:30 10K from 2018 is still useful! Gives baseline even if fitness has changed."
- Enter with accurate date, system tracks progression/regression from peak

---

### Step 4f: Other Sports Collection (If Multi-Sport Athlete)

**CRITICAL: Only for athletes with `running_priority = "equal"` or `"secondary"`**

If sport distribution from `sce profile analyze` shows significant other sports (>20% of total load):

**Ask about regular sports** (natural conversation):
```
Coach: "I see climbing makes up 42% of your training. What days do you typically climb?"
Athlete: "Tuesdays and Thursdays, usually 2-hour sessions"
```

**For each sport, collect**:
- Sport name (climbing, cycling, swimming, etc.)
- Days per week (fixed schedule or flexible)
- Typical duration (minutes)
- Intensity level (easy, moderate, moderate_to_hard, hard)

**Add each sport**:
```bash
sce profile add-sport --sport climbing --days tue,thu --duration 120 --intensity moderate_to_hard
sce profile add-sport --sport cycling --days flexible --duration 90 --intensity moderate
```

**Verify**:
```bash
sce profile list-sports
```

**Review with athlete**:
```
Coach: "I have climbing (Tue/Thu, 120 min, moderate-hard) and cycling (flexible, 90 min, moderate).
This helps me design run days around your fixed climbing schedule."
```

**Why this matters**: Multi-sport load affects CTL/ATL calculations, lower-body fatigue gates, and workout scheduling.

---

### Step 4g: Communication Preferences (Optional - Can Skip)

**Offer customization without creating decision fatigue**:

```
Coach: "I can tailor my coaching style to your preferences, or use defaults if you'd like to get started quickly.
Would you like to customize how I communicate?"
```

**If athlete says YES** (natural conversation):

**Detail level**:
```
Coach: "Do you prefer brief updates, moderate detail, or comprehensive analysis after each workout?"
Athlete: "Moderate detail works for me"
# Store: detail_level = "moderate"
```

**Coaching style**:
```
Coach: "What coaching tone works best for you: supportive, direct, or analytical?"
Athlete: "Direct - just tell me what to do"
# Store: coaching_style = "direct"
```

**Intensity metric**:
```
Coach: "For workouts, do you prefer pace targets, heart rate zones, or RPE (perceived effort)?"
Athlete: "Pace - I like tangible numbers"
# Store: intensity_metric = "pace"
```

**Update profile**:
```bash
sce profile set --detail-level moderate --coaching-style direct --intensity-metric pace
```

**If athlete says NO or "use defaults"**:
```
Coach: "No problem! I'll use moderate detail, supportive tone, and pace-based workouts.
You can adjust anytime with 'sce profile set'."
```

**Skip to Step 5**

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

### Step 5.5: Validate Goal Feasibility

**CRITICAL: Always validate goal against current fitness before committing to plan.**

#### Get Performance Baseline

```bash
sce performance baseline
```

**Present context to athlete**:
- Current VDOT estimate: XX (from recent workouts)
- Peak VDOT: YY (from ZZ race on [date])
- Goal requires VDOT: ZZ
- Gap: +/- N VDOT points

#### Set Goal (Automatic Validation)

The `sce goal set` command automatically validates feasibility:

```bash
sce goal set --type half_marathon --date 2026-06-01 --time "1:30:00"
# Automatically returns: goal saved + feasibility verdict + recommendations
```

**Output includes**:
- Feasibility verdict: VERY_REALISTIC / REALISTIC / AMBITIOUS_BUT_REALISTIC / AMBITIOUS / UNREALISTIC
- VDOT gap (current vs. required)
- Weeks available for training
- Recommendations for achieving goal

#### Coaching Response Based on Verdict

**VERY_REALISTIC / REALISTIC:**
- Build confidence: "Your goal is well within reach based on your current fitness (VDOT 48) and training history."
- Set expectations: "We'll design a plan that maintains fitness and sharpens your speed."

**AMBITIOUS_BUT_REALISTIC:**
- Acknowledge challenge: "This is a stretch goal requiring VDOT improvement from 48 → 52 (+8.3%) over 20 weeks."
- Build commitment: "It's achievable with strong adherence. Are you ready to commit to 4 quality runs/week?"

**AMBITIOUS:**
- Use AskUserQuestion to present options:
  - **Option 1**: Keep ambitious goal, design aggressive plan, acknowledge 40-50% success probability
  - **Option 2**: Adjust goal to realistic range (suggest alternative: 1:35:00 = VDOT 49)
  - **Option 3**: Target a later race (suggest +8 weeks for better preparation)

**UNREALISTIC:**
- Present reality: "Your goal requires VDOT 52, but current fitness is VDOT 45. That's a 15.6% improvement in 12 weeks."
- Show math: "Typical VDOT gains are 1.5 points/month. You'd need 7 points in 3 months = 2.3 points/month (50% faster than typical)."
- Recommend alternatives:
  - Alternative time: "Based on current fitness, 1:38:00 is realistic (VDOT 48)"
  - Alternative timeline: "For your 1:30:00 goal, I recommend targeting a race 5 months out"

**Decision point**: Wait for athlete confirmation before proceeding to Step 6 (Constraints Discussion).

#### Edge Case: No Current VDOT Estimate

If `sce performance baseline` returns no VDOT estimate (no recent quality workouts):

```
Coach: "I don't have enough recent quality workout data to estimate your current fitness.
Your goal is half marathon 1:30:00 (VDOT 52 required).

Let's take a conservative approach initially and reassess after your first tempo run gives us a VDOT estimate."
```

**Proceed with goal set**, but flag that validation will improve after first quality workout.

---

### Step 6: Constraints Discussion (Before Plan Generation)

**CRITICAL: Discuss constraints before designing plan.**

**Questions** (natural conversation):

1. **Run frequency (minimum)**: "What's the minimum days per week you can commit to running?" (2-3 typical)
   - Store as: `--min-run-days N`

2. **Run frequency (maximum)**: "How many days per week can you realistically run?" (3-6 typical)
   - Store as: `--max-run-days N`

3. **Available days (reverse logic)**: "Are there any days you absolutely CANNOT run?"
   - **If athlete says "No" or "All days work"**: Keep default (all 7 days available)
   - **If athlete says "Tuesdays and Thursdays"**: Remove those from available_run_days
   - **Example**: If "cannot run Tue/Thu" → `--available-days "monday,wednesday,friday,saturday,sunday"`
   - **Default assumes all 7 days available** - ask only for exceptions

4. **Session duration**: "What's the longest time for a long run?" (90-180 min typical)
   - Store as: `--max-session-minutes N`

5. **Other sports schedule**: "Are climbing days fixed or flexible?" (if applicable)
   - Context for workout scheduling around other sports

**Store constraints**:
```bash
# Example: Cannot run Tue/Thu, 3-4 days/week, max 120 min sessions
sce profile set --min-run-days 3 --max-run-days 4 \
  --available-days "monday,wednesday,friday,saturday,sunday" \
  --max-session-minutes 120
```

**If athlete says "all days work"**:
```bash
# No need to specify --available-days (defaults to all 7 days)
sce profile set --min-run-days 3 --max-run-days 4 --max-session-minutes 120
```

---

### Step 7: Suggest Next Steps

**After onboarding complete**:
```
"Great! Your profile is set up. CTL is 44 (solid recreational fitness) with half marathon goal June 1st.

That's 20 weeks. Based on your fitness and constraints (4 run days/week, climbing Tuesdays), I recommend designing a training plan.

Would you like me to create a personalized plan now?"
```

**If yes**: Run `vdot-baseline-proposal`, then `macro-plan-create`

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

### 6. Only relying on Strava auto-import for PBs
❌ **Bad**: Only running `sce race import-from-strava` (misses old PBs)
✅ **Good**: Ask directly for PBs first, then auto-import as supplement

**Manual entry is primary** - Strava only has 120 days

---

## Success Criteria

**Onboarding complete when**:
1. ✅ Authentication successful (`sce auth status` returns 0)
2. ✅ Activities synced (120 days)
3. ✅ Profile created (name, age, max HR, conflict policy)
4. ✅ Injury history recorded in memory system (if applicable)
5. ✅ Race history captured (PBs added via `sce race add`, auto-import run)
6. ✅ Goal set (race type, date)
7. ✅ Constraints discussed (run days, duration, other sports)
8. ✅ Ready for plan generation

**Quality checks**:
- All data referenced from `sce profile analyze`
- AskUserQuestion used ONLY for conflict policy
- Natural conversation for text/number inputs
- Injury history in memory system with proper tags

**Handoff**: "Would you like me to design your training plan now?" → Run `vdot-baseline-proposal` → `macro-plan-create`

---

## Additional Resources

**Reference material**:
- [Authentication Guide](references/authentication.md) - Complete OAuth flow and troubleshooting
- [Profile Fields Reference](references/profile_fields.md) - All 28 fields with examples

**Complete examples**:
- [Runner Primary Onboarding](examples/example_onboarding_runner_primary.md) - Race-focused athlete

**CLI documentation**:
- [Profile Commands](../../../docs/coaching/cli/cli_profile.md) - Complete command reference
- [Authentication Commands](../../../docs/coaching/cli/cli_auth.md) - OAuth troubleshooting

**Training methodology**:
- [Coaching Scenarios - First Session](../../../docs/coaching/scenarios.md#scenario-1-first-session) - Detailed walkthrough
- [Coaching Methodology](../../../docs/coaching/methodology.md) - Overview
