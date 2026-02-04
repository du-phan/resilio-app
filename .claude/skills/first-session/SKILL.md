---
name: first-session
description: Onboard new athletes with complete setup workflow including authentication, activity sync, profile creation, goal setting, and constraints discussion. Use when athlete requests "let's get started", "set up my profile", "new athlete onboarding", or "first time using the system".
allowed-tools: Bash, Read, Write, AskUserQuestion
argument-hint: "[athlete-name]"
---

# First Session: Athlete Onboarding

## Overview

This skill guides complete athlete onboarding from authentication to goal setting. The workflow ensures historical data is available before profile setup, enabling data-driven questions instead of generic prompts.

**Prerequisites**: This skill assumes your environment is ready (Python 3.11+, `sce` CLI available). If you haven't set up your environment yet, use the `complete-setup` skill first to install Python and the package.

**Communication guideline**: When talking to athletes, never mention skills, slash commands, or internal tools. Say "Let me help you get started" not "I'll run the first-session skill." See CLAUDE.md "Athlete-Facing Communication Guidelines."

**Why historical data matters**: ask "I see you average 35km/week over the last X weeks/months - should we maintain this?" instead of "How much do you run?" (no context).

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

**If config is missing or credentials are empty**:

1. Run `sce init` to create `config/secrets.local.yaml` (if missing).
2. Read `config/secrets.local.yaml` and verify `strava.client_id` and `strava.client_secret` are present.
3. If either is missing or still the placeholder, ask the athlete to paste the **Client ID** and **Client Secret** from the Strava API settings page (`https://www.strava.com/settings/api`).
4. Write the values into `config/secrets.local.yaml` under:
   ```yaml
   strava:
     client_id: "..."
     client_secret: "..."
   ```
5. Confirm: "Saved locally. I’ll use these for authentication going forward."

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
sce sync  # First-time: fetches 365 days automatically
```

**Post-sync overview (MANDATORY)**
After every `sce sync`, give the athlete a brief overview. Use the sync command output (JSON envelope or success message); optionally run `sce profile analyze` to get exact date range.

Include:

1. **Number of activities synced** (from sync result: `activities_imported` or success message).
2. **Time span covered** (weeks or months). From sync result if evident; otherwise from `sce profile analyze` → `data_window_days`, `synced_data_start`, `synced_data_end`.
3. **Rate limit status** (if hit): Explain that the athlete has imported sufficient data for baseline metrics.

Keep the overview to 2–4 sentences. Do not skip this step.

**Note**: Activities are stored in monthly folders (`data/activities/YYYY-MM/*.yaml`). See [cli_data_structure.md](../../../docs/coaching/cli/cli_data_structure.md) for details on data organization.

**What this provides**:

- Up to 365 days (52 weeks) of activity history (Greedy Sync)
- CTL/ATL/TSB calculated from historical load
- Activity patterns (training days, volume, sport distribution)

**Handling Greedy Sync & Rate Limits (IMPORTANT)**:
The sync process is "greedy"—it fetches the most recent activities first and proceeds backwards until it hits the 52-week limit OR the Strava API rate limit (100 requests / 15 min).

**EXPECTED**: The initial sync WILL hit rate limits for most athletes with regular training. This is normal, designed behavior.

**Why**: Fetching 365 days typically requires 200-400 API requests. Strava limits apps to 100 requests per 15 minutes. The system handles this gracefully by pausing and resuming.

**Reference**: See [Strava Rate Limits](https://developers.strava.com/docs/rate-limits/) - 100 requests/15min, 1000 requests/day.

**If rate limit hit (~100 activities):**

Present this choice with coaching expertise:

"I've imported your last [X] activities (about [Y] months). The sync paused due to Strava's rate limit (100 requests per 15 minutes) - this is expected for initial syncs.

Your current data is sufficient to establish baseline metrics (CTL, fitness level), so you have two options:

**Options:**
1. **Continue with current data (recommended for getting started)** - Enough for reliable baseline
2. **Wait 15 minutes and sync more** - To get complete year of history

We can always sync more history later. What would you prefer?"

**If athlete chooses option 2:**
- Wait 15 minutes for rate limit reset
- Run `sce sync` again (will automatically resume from where it left off)
- Repeat until athlete is satisfied or full year is synced

**For very active athletes** (7+ activities/week):
- Multiple 15-minute waits expected (3-5 pauses typical)
- Total sync time: 45-60 minutes including waits
- Rare edge case: May approach daily limit (1,000 requests) - if so, continue next day

**Coaching tip**: For very active athletes, set expectation upfront: "Your training volume means the initial sync will take 45-60 minutes with several 15-minute pauses. Totally normal - Strava limits how fast we can fetch data."

**Success message**: "Imported X activities (covering approximately Y weeks). Your CTL is Z."

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

**For complete field-by-field guidance**: See [references/profile_setup_workflow.md](references/profile_setup_workflow.md)

#### Quick Overview

**Step 4a - Basic Info**: Name, age, max HR (reference Strava peak), resting HR, running experience (years)

**Step 4b - Injury History**: Search activities for gaps/pain mentions → Store in memory system with tags

- Use `sce activity search --query "pain injury sore"` to detect signals
- Store each injury: `sce memory add --type INJURY_HISTORY --content "..." --tags "body:knee,status:resolved"`

**Step 4c - Sport Priority**: Reference `sce profile analyze` sport distribution

- Options: `"running"` (PRIMARY), `"equal"` (EQUAL), other sport name (SECONDARY)

**Step 4d - Conflict Policy**: Use AskUserQuestion (ONLY use here - trade-offs exist)

- Options: Ask each time | Primary sport wins | Running goal wins

**Step 4e - Create Profile**:

```bash
sce profile set --name "Alex" --age 32 --max-hr 190 --conflict-policy ask_each_time
```

**Step 4.5 - Personal Bests (Race History)**:

- CRITICAL: Manual entry FIRST (Sync defaults to 365 days, but old PBs may still be missing)
- Ask directly: "What are your PBs for 5K, 10K, half, marathon?"
- Enter each: `sce race add --distance 10k --time 42:30 --date 2023-06-15 --source official_race`
- Auto-import supplement: `sce race import-from-strava --since 120d`
- Verify: `sce race list`

**Step 4f - Other Sports Collection**:

- Check distribution: `sce profile analyze` → sport_percentages
- Collect ALL sports >15%: `sce profile add-sport --sport climbing --days tue,thu --duration 120`
- running_priority determines CONFLICT RESOLUTION, not whether to track sports

**Step 4f-validation - Data Alignment**:

- Verify: `sce profile validate`
- Check: All sports >15% from analyze are in other_sports
- Only proceed when alignment confirmed

**Step 4g - Communication Preferences** (optional):

- Offer customization: "Tailor coaching style or use defaults?"
- If yes: Detail level, coaching style, intensity metric
- If no: "I'll use moderate detail, supportive tone, pace-based workouts"

See [profile_setup_workflow.md](references/profile_setup_workflow.md) for detailed workflows, decision trees, validation steps, and common scenarios.

---

### Step 5: Goal Setting

**Questions** (natural conversation):

- "What are you training for?"
- "When is your race?" (date)
- "What's your goal time?" (optional)

```bash
sce goal set --type half_marathon --date 2026-06-01
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

**Scenario**: Sync returns <10 activities in 365 days / 52 weeks

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

### 4. Asking the athlete to edit YAML manually

❌ **Bad**: "Open config/secrets.local.yaml and edit it."
✅ **Good**: Ask for Client ID/Secret in chat and write them locally.

### 5. Not discussing constraints before planning

❌ **Bad**: Creating plan without knowing schedule
✅ **Good**: Ask run days, duration, other sports BEFORE planning

**Constraints shape entire plan**

### 6. Generic injury questions

❌ **Bad**: "Any injuries?" (no context)
✅ **Good**: "I see 2-week gap in November with CTL drop - injury-related?"

**Use activity gaps as conversation starters**

### 7. Only relying on Strava auto-import for PBs

❌ **Bad**: Only running `sce race import-from-strava` (misses old PBs)
✅ **Good**: Ask directly for PBs first, then auto-import as supplement

**Manual entry is primary** - Automatic sync targets 365 days, but doesn't replace historical context for old PBs.

---

## Success Criteria

**Onboarding complete when**:

1. ✅ Authentication successful (`sce auth status` returns 0)
2. ✅ Activities synced (max 365 days / 52 weeks target)
3. ✅ Profile created (name, age, max HR, conflict policy)
   3.5. ✅ Running experience collected (years, or marked as unknown)
4. ✅ Injury history recorded in memory system (if applicable)
5. ✅ Race history captured (PBs added via `sce race add`, auto-import run)
6. ✅ Goal set (race type, date)
7. ✅ Constraints discussed (run days, duration, other sports)
8. ✅ Other sports data collected (all sports >15% from sce profile analyze)
9. ✅ Data validation passed (other_sports matches Strava distribution)
10. ✅ Ready for plan generation

**Quality checks**:

- All data referenced from `sce profile analyze`
- AskUserQuestion used ONLY for conflict policy
- Natural conversation for text/number inputs
- Injury history in memory system with proper tags
- Multi-sport athletes have other_sports populated based on actual Strava data
- Validation checkpoint prevents progression until data is complete
- Coach explains WHY other_sports matters (load calc, not just priority)

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
