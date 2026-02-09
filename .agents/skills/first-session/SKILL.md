---
name: first-session
description: Onboard new athletes with complete setup workflow including authentication, activity sync, profile creation, goal setting, and constraints discussion. Use when athlete requests "let's get started", "set up my profile", "new athlete onboarding", or "first time using the system".
compatibility: Codex CLI/IDE; requires local sce CLI and repo context
---

# First Session: Athlete Onboarding

## Overview

This skill guides complete athlete onboarding from authentication to goal setting. The workflow ensures historical data is available before profile setup, enabling data-driven questions instead of generic prompts.

**Prerequisites**: This skill assumes your environment is ready (Python 3.11+, `sce` CLI available). If you haven't set up your environment yet, use the `complete-setup` skill first to install Python and the package.

**Communication guideline**: When talking to athletes, never mention skills, slash commands, or internal tools. Say "Let me help you get started" not "I'll run the first-session skill." See AGENTS.md / CLAUDE.md "Athlete-Facing Communication Guidelines."

**Why historical data matters**: ask "I see you average 35km/week over the last X weeks/months - should we maintain this?" instead of "How much do you run?" (no context).

**Metric explainer rule (athlete-facing)**:
On first mention of any metric (VDOT/CTL/ATL/TSB/ACWR/Readiness/RPE), add a short, plain-language definition. If multiple metrics appear together, use a single "Quick defs" line. Do not repeat unless the athlete asks or seems confused. For multi-sport athletes, add a brief clause tying the metric to total work across running + other sports (e.g., climbing/cycling). Optionally add: "Want more detail, or is that enough for now?"

Use this exact VDOT explainer on first mention:
"VDOT is a running fitness score based on your recent race or hard-effort times. I use it to set your training paces so your running stays matched to your current fitness alongside your other sports."

One-line definitions for other metrics:
- CTL: "CTL is your long-term training load—think of it as your 6-week fitness trend."
- ATL: "ATL is your short-term load—basically how much you've trained in the past week."
- TSB: "TSB is freshness (long-term fitness minus short-term fatigue)."
- ACWR: "ACWR compares this week to your recent average; high values mean a sudden spike."
- Readiness: "Readiness is a recovery score—higher usually means you can handle harder work."
- RPE: "RPE is your perceived effort from 1–10."

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
sce sync  # First-time: targets up to 365 days automatically
```

**Post-sync overview (MANDATORY)**
After every `sce sync`, give the athlete a brief overview. Use the sync command output (JSON envelope or success message); run `sce profile analyze` to get the exact date range.

Include:

1. **Number of activities synced** (from sync result: `activities_imported` or success message).
2. **Time span covered** (weeks or months). Always compute from `sce profile analyze` → `data_window_days`, `synced_data_start`, `synced_data_end`.
3. **Rate limit status** (if hit): Explain that the athlete has imported sufficient data for baseline metrics.

Keep the overview to 2–4 sentences. Do not skip this step.

**Never claim** "last 365 days" unless `data_window_days >= 360` and no rate-limit error occurred.
If a rate limit was hit, the summary must explicitly say the history is partial and can be resumed later.

**Required summary pattern** (adapt wording, keep facts):
"Imported X activities spanning N days (YYYY-MM-DD to YYYY-MM-DD). If rate limited: 'Sync paused due to Strava rate limits, so this is a partial year. We can resume in ~15 minutes.'"

**Note**: Activities are stored in monthly folders (`data/activities/YYYY-MM/*.yaml`). See [cli_data_structure.md](../../../docs/coaching/cli/cli_data_structure.md) for details on data organization.

**What this provides**:

- Up to 365 days (52 weeks) of activity history (Greedy Sync)
- CTL/ATL/TSB calculated from historical load
- Activity patterns (training days, volume, sport distribution)

**Handling Greedy Sync & Rate Limits (IMPORTANT)**:
The sync process is "greedy"—it fetches the most recent activities first and proceeds backwards until it hits the 52-week limit OR the Strava API rate limit (100 requests / 15 min).

**EXPECTED**: The initial sync may hit rate limits for many athletes with regular training. This is normal, designed behavior.

**Why**: Fetching 365 days typically requires 200-400 API requests. Strava limits apps to 100 requests per 15 minutes. The system handles this gracefully by pausing and resuming.

**Reference**: See [Strava Rate Limits](https://developers.strava.com/docs/rate-limits/) - 100 requests/15min, 1000 requests/day.

**If rate limit hit (~100 requests):**

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

**Use natural conversation for text/number inputs. Use chat-based numbered options for decisions with distinct trade-offs (conflict policy, goal feasibility).**

**For complete field-by-field guidance**: See [references/profile_setup_workflow.md](references/profile_setup_workflow.md)

#### Multi-Sport Branching Logic

**Check sport distribution** from `sce profile analyze` → `sport_percentages`:

- **If >1 sport at >15%**: Use full sequence (steps 4a-4d-4e-4f)
- **If mostly running (>80%)**: Use standard sequence (steps 4a-4d-4e), add 4f only if athlete reports regular non-running commitments

This ensures we understand the athlete's complete training picture before asking about constraints.

#### Quick Overview (Multi-Sport Sequence)

**Step 4a - Basic Info**: Name, age, max HR (reference Strava peak), resting HR, running experience (years)

**Why this matters**: "I need your complete training picture. Climbing loads your cardiovascular system even though it doesn't stress your legs the same way. If I ignore it, I'll over-prescribe running and you'll burn out."

**Step 4b - Injury History**: Search activities for gaps/pain mentions → Store in memory system with tags

- Use `sce activity search --query "pain injury sore"` to detect signals
- Store each injury: `sce memory add --type INJURY_HISTORY --content "..." --tags "body:knee,status:resolved"`

**Step 4c - Sport Priority**: Reference `sce profile analyze` sport distribution

- Options: `"running"` (PRIMARY), `"equal"` (EQUAL), other sport name (SECONDARY)

**Step 4d - Conflict Policy** (from sport picture): Use chat-based numbered options (trade-offs with distinct options)

- Options: Ask each time | Primary sport wins | Running goal wins
- Context: "Your week has climbing 3x/week and yoga 2x/week. When training conflicts arise..."

**Step 4e - Create Profile**:

```bash
sce profile create --name "Alex" --age 32 --max-hr 190 --run-priority equal --conflict-policy ask_each_time
```

**Step 4f - Other Sports Collection** (AFTER profile creation):

- Check distribution: `sce profile analyze` → sport_percentages
- Collect ALL sports >15%
- **Frequency + unavailable days model**:
  - **Option 1**: Frequency only → `sce profile add-sport --sport climbing --frequency 3 --duration 120`
  - **Option 2**: Frequency + unavailable days → `sce profile add-sport --sport climbing --frequency 3 --unavailable-days tue,thu --duration 120`

**Temporary break handling**:
- If athlete pauses a sport to focus on running or due to injury/illness:
  - Pause: `sce profile pause-sport --sport climbing --reason focus_running`
  - Resume later: `sce profile resume-sport --sport climbing`

**Coaching conversation**:
- "How many times per week do you climb? Any days you can’t do it?"
- If athlete says "3 times a week, days vary" → Use `--frequency 3`
- If athlete says "I can’t climb Sundays" → Add `--unavailable-days sunday`

**Step 4f-validation - Data Alignment**:

- Verify: `sce profile validate`
- Check: All sports >15% from analyze are in other_sports
- Only proceed when alignment confirmed

**Step 4.5 - Personal Bests**:

- Ask directly: "What are your PBs for 5K, 10K, half, marathon?"
- Enter each: `sce profile set-pb --distance 10k --time 42:30 --date 2023-06-15`
- After sync, cross-check standout activities conversationally: "I see a strong 43:15 10K on Dec 15 — was that a race?" If yes, update PB if faster.
- Verify: `sce profile get` (PBs section)

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

Run `sce performance baseline` and `sce goal set` (which includes automatic feasibility validation). Respond based on the verdict (VERY_REALISTIC → UNREALISTIC).

**For complete verdict handling, coaching responses, and edge cases**: See [references/goal_validation.md](references/goal_validation.md)

**Decision point**: Wait for athlete confirmation before proceeding to Step 6.

---

### Step 6: Running Constraints (Subtractive Model)

**CRITICAL: Discuss constraints AFTER other sports are configured. This step is now informed by the athlete's complete training picture.**

**Context-aware conversation**: For multi-sport athletes, reference their other sports when discussing constraints.

Example: "Your week has climbing 3x/week and yoga 2x/week. Given your half marathon goal, 3 quality run days fits well alongside everything else. Does that sound manageable?"

**Questions** (natural conversation):

1. **Run frequency (minimum)**: "What's the minimum days per week you can commit to running?" (2-3 typical)

   - Store as: `--min-run-days N`

2. **Run frequency (maximum)**: "How many days per week can you realistically run?" (3-6 typical)

   - Store as: `--max-run-days N`

3. **Unavailable days (subtractive model)**: "Are there any days you absolutely CANNOT run?"

   - **NEW APPROACH**: Ask for exceptions, not exhaustive lists
   - **If athlete says "No" or "All days work"**: No unavailable days (default)
   - **If athlete says "Tuesdays and Thursdays - that's climbing night"**: Mark those as unavailable
   - **Example**: "Cannot run Tue/Thu" → `--unavailable-days "tuesday,thursday"`
   - **Default is empty** - only specify days that are UNAVAILABLE

4. **Session duration**: "What's the longest time for a long run?" (90-180 min typical)

   - Store as: `--max-session-minutes N`

**Store constraints**:

```bash
# Example: Cannot run Tue/Thu (climbing nights), 3-4 days/week, max 120 min sessions
sce profile set --min-run-days 3 --max-run-days 4 \
  --unavailable-days "tuesday,thursday" \
  --max-session-minutes 120
```

**If athlete says "all days work"** (no unavailable days):

```bash
# No need to specify --unavailable-days (defaults to empty - no unavailable days)
sce profile set --min-run-days 3 --max-run-days 4 --max-session-minutes 120
```

**Auto-derive suggestion**: If the athlete says they cannot run on certain days because of other sports, set those as `--unavailable-days` for running. But don’t assume - some athletes can do both on the same day.

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

### Q: Athlete doesn't have a Strava account

**Response**: Strava authentication is required. Guide the athlete to create a free account at strava.com before proceeding. They'll need to record at least a few activities before we can provide data-driven coaching.

### Q: Multiple sports with complex schedule

**Approach**:

1. Identify sport frequency and hard no-go days
2. Map running around unavailable days
3. Consider lower-body load: "Climbing doesn't impact legs, cycling does"
4. Set conflict policy carefully (likely `ask_each_time`)

---

## Common Pitfalls

### 1. Asking for data already available

❌ **Bad**: "How much do you run per week?"
✅ **Good**: "I see you average 22.5 km/week - maintain this or adjust?"

**Always check `sce profile analyze` first**

### 2. Using chat-based numbered options for free-form text

❌ **Bad**: chat-based numbered options for "What's your name?"
✅ **Good**: Natural conversation for all text/number inputs

**chat-based numbered options ONLY for decisions with distinct trade-offs (conflict policy, goal feasibility)**

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

### 7. Not asking for PBs directly

❌ **Bad**: Only looking at synced data for PBs (misses pre-Strava performances)
✅ **Good**: Ask directly for PBs first, then cross-check synced data conversationally

**Ask first, verify second** - Most runners know their PBs. Sync data is supplementary, not primary.

---

## Success Criteria

**Onboarding complete when**:

1. ✅ Authentication successful (`sce auth status` returns 0)
2. ✅ Activities synced (max 365 days / 52 weeks target)
3. ✅ Profile created (name, age, max HR, conflict policy)
   3.5. ✅ Running experience collected (years, or marked as unknown)
4. ✅ Injury history recorded in memory system (if applicable)
5. ✅ Personal bests captured (PBs added via `sce profile set-pb`)
6. ✅ Goal set (race type, date)
7. ✅ Constraints discussed (run days, duration, other sports)
8. ✅ Other sports data collected (all sports >15% from sce profile analyze)
9. ✅ Data validation passed (other_sports matches Strava distribution)
10. ✅ Ready for plan generation

**Quality checks**:

- All data referenced from `sce profile analyze`
- chat-based numbered options used ONLY for decisions with distinct trade-offs (conflict policy, goal feasibility)
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
