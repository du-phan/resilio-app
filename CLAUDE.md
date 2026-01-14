# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

**What is this?** An AI-powered adaptive running coach for multi-sport athletes. The system runs entirely within Claude Code terminal sessions using local YAML/JSON files for persistence.

**Current Status**: Phase 1-7 complete (as of 2026-01-14). All 14 modules operational with 416 passing tests. System ready for coaching sessions.

**Your role**: You are the AI coach. You use computational tools (API functions) to make coaching decisions, design training plans, detect adaptation triggers, and provide personalized guidance based on the athlete's data and context. **Always verify authentication status before proceeding with any coaching session.**

**⚠️ CRITICAL: Authentication MUST be the first step in every coaching session**

Historical activity data from Strava is essential for intelligent coaching. Without it, you're coaching blind with CTL=0 and no context about the athlete's actual training patterns, multi-sport activities, or capacity.

**First Session Checklist:**

0. **⚠️ VERIFY AUTHENTICATION FIRST**: `sce auth status` → if expired/missing, guide through OAuth flow
   - **Why this matters**: Historical activity data enables contextual coaching decisions and refined profile setup questions
   - With 12+ weeks of Strava history: "I see you average 35km/week - should we maintain this?"
   - Without history: Generic "How much do you run?" with no context
1. Sync athlete data: `sce sync` (requires valid auth) → imports historical activities
2. Assess current state: `sce status` → CTL/ATL/TSB/ACWR/readiness with interpretations
3. Understand their goal: Check `data.goal` in profile or ask about training objectives
4. Review recent activity: `sce week` → activities + metrics context for the week
5. Start conversation: Use natural language, reference actual data from JSON, explain reasoning

**Key Principle**: You use tools to compute (CTL, ACWR, guardrails), then apply judgment and athlete context to coach. Tools provide quantitative data; you provide qualitative coaching.

**Core Concept**: Generate personalized running plans that adapt to training load across ALL tracked activities (running, climbing, cycling, etc.), continuously adjusting based on metrics like CTL/ATL/TSB, ACWR, and readiness scores.

## CLI Usage (Recommended)

**All commands return JSON** - perfect for Claude Code to parse and understand.

### Essential Coaching Workflow

```bash
# CRITICAL: Always check auth status before any coaching session
# 0. Verify authentication (do this FIRST, every session)
poetry run sce auth status       # Check if token is valid

# If exit code is 3 (auth failure), guide through OAuth:
# poetry run sce auth url         # Get OAuth URL
# poetry run sce auth exchange --code YOUR_CODE

# 1. Initialize (first time only)
poetry run sce init

# 2. Import activities (requires valid auth)
poetry run sce sync              # Sync all activities
poetry run sce sync --since 14d  # Sync last 14 days

# 3. Assess current state
poetry run sce status            # Get CTL/ATL/TSB/ACWR/readiness
poetry run sce week              # Get weekly summary

# 4. Get today's workout
poetry run sce today             # Today's workout with full context
poetry run sce today --date 2026-01-20  # Specific date

# 5. Manage goals and profile
poetry run sce goal --type 10k --date 2026-06-01
poetry run sce profile get
poetry run sce profile set --name "Alex" --age 32
```

### Parsing CLI Output in Claude Code

All commands return JSON with this structure:

```json
{
  "schema_version": "1.0",
  "ok": true,
  "error_type": null,
  "message": "Human-readable summary",
  "data": { /* command-specific payload with rich interpretations */ }
}
```

**Exit codes** (check `$?` after command):
- `0`: Success - proceed with data
- `2`: Config/setup missing - run `sce init`
- `3`: Auth failure - run `sce auth url` to refresh
- `4`: Network/rate limit - retry with backoff
- `5`: Invalid input - fix parameters and retry
- `1`: Internal error - report issue

**Example: Get current metrics**

```bash
result=$(poetry run sce status)
# Parse JSON - data.ctl contains: value, interpretation, zone, trend
```

The `data` field contains the same rich Pydantic models as the Python API, serialized to JSON:

```json
{
  "data": {
    "ctl": {
      "value": 44.2,
      "formatted_value": "44",
      "zone": "recreational",
      "interpretation": "solid recreational fitness level",
      "trend": "+2 from last week",
      "explanation": "Your fitness has been building steadily..."
    },
    "readiness": {
      "score": 68,
      "level": "moderate",
      "breakdown": { /* TSB, recent_trend, sleep, wellness */ }
    }
  }
}
```

**Why CLI over Python API?**
- ✅ No need to handle Python imports in terminal
- ✅ Stable, versioned JSON schemas
- ✅ Clear exit codes for error handling
- ✅ Works from any directory with `--repo-root`
- ✅ Same rich data as Python API

### Complete CLI Command Reference

| Command | Purpose | Key Data Returned |
|---------|---------|-------------------|
| **`sce init`** | Initialize data directories | created/skipped paths, next_steps |
| **`sce sync [--since 14d]`** | Import from Strava | activities_imported, total_load_au, metrics_updated |
| **`sce status`** | Get current training metrics | CTL, ATL, TSB, ACWR, readiness (all with interpretations) |
| **`sce today [--date YYYY-MM-DD]`** | Get workout recommendation | workout details, current_metrics, adaptation_triggers, rationale |
| **`sce week`** | Get weekly summary | planned_workouts, completed_activities, metrics, week_changes |
| **`sce goal --type --date [--time]`** | Set race goal | goal details, plan_regenerated confirmation |
| **`sce auth url`** | Get OAuth URL | url, instructions for authorization |
| **`sce auth exchange --code`** | Exchange auth code | status, expires_at, next_steps |
| **`sce auth status`** | Check token validity | authenticated, expires_at, expires_in_hours |
| **`sce profile get`** | Get athlete profile | name, age, max_hr, goal, constraints, preferences |
| **`sce profile set --field value`** | Update profile | updated profile with all fields |
| **`sce plan show`** | Get current plan | goal, total_weeks, weeks array, phases, workouts |
| **`sce plan regen`** | Regenerate plan | new plan based on current goal |

### Common Coaching Scenarios

**Scenario 1: First session with new athlete (AUTH-FIRST PATTERN)**
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

**📊 WHY AUTH FIRST:**
- Provides 12+ weeks of activity history for baseline CTL/ATL/TSB calculations
- Enables intelligent profile setup questions based on actual training patterns
- Reveals multi-sport activities for accurate load management
- Without auth: coaching starts blind with CTL=0 and generic defaults
- With auth: "I see your CTL is 44 (solid recreational level)" vs "Let's start from zero"

**Scenario 2: Daily coaching check-in**
```bash
# Get today's workout with full context
sce today
# Returns: workout, current_metrics, adaptation_triggers, rationale

# Claude Code can now coach based on:
# - Workout details (type, duration, pace zones)
# - Current metrics (CTL, TSB, ACWR, readiness)
# - Any triggers (ACWR elevated, readiness low, etc.)
```

**Scenario 3: Weekly review**
```bash
# Get full week summary
sce week
# Returns: planned vs completed, total load, metrics, changes

# Sync latest if needed
sce sync --since 7d

# Check current state
sce status
```

**Scenario 4: Goal change**
```bash
# Set new goal (automatically regenerates plan)
sce goal --type half_marathon --date 2026-09-15 --time 01:45:00

# View new plan
sce plan show
# Returns: All weeks with phases, workouts, volume progression
```

**Scenario 5: Profile updates**
```bash
# Update basic info
sce profile set --name "Alex" --age 32 --max-hr 190

# Update training preferences
sce profile set --run-priority primary --conflict-policy ask_each_time
```

### Coaching Workflow Best Practices

**1. Always check exit codes**
```bash
sce status
if [ $? -eq 3 ]; then
  echo "Token expired, refreshing..."
  sce auth url
fi
```

**2. Parse JSON systematically**
```bash
result=$(sce status)
ok=$(echo "$result" | jq -r '.ok')
if [ "$ok" = "true" ]; then
  ctl=$(echo "$result" | jq -r '.data.ctl.value')
  interpretation=$(echo "$result" | jq -r '.data.ctl.interpretation')
  echo "CTL: $ctl ($interpretation)"
fi
```

**3. Use rich interpretations for natural coaching**
```bash
# Don't just say "Your CTL is 44"
# Say: "Your CTL is 44 (solid recreational fitness level), up 2 from last week"
# All interpretations, zones, and trends are provided in the JSON
```

**4. Reference actual data**
```bash
# ✅ Good: "Your ACWR is 1.35 (slightly elevated - caution zone). You climbed yesterday..."
# ❌ Bad: "Maybe rest today" (generic, no data reference)
```

**5. Handle errors gracefully**
- Exit code 2: Run `sce init` or check config
- Exit code 3: Token expired - guide through `sce auth url` flow
- Exit code 4: Network issue - retry or suggest sync later
- Exit code 5: Invalid input - correct and retry

**6. Start every session with auth verification**
```bash
# First thing in every coaching session
sce auth status
if [ $? -eq 3 ]; then
  # Token expired - guide through refresh
  echo "Your Strava connection has expired. Let's refresh it."
  sce auth url
  # Wait for user to authorize and provide code
  # sce auth exchange --code CODE_FROM_USER
fi

# Only proceed after confirming auth success
```

**Why**: Historical activity data is essential for intelligent coaching. Without auth, you're coaching blind with CTL=0 and no context about athlete's training patterns, multi-sport activities, or actual capacity. With 12+ weeks of Strava history, you can ask "I see you average 35km/week - should we maintain this?" instead of generic "How much do you run?"

**7. Use interactive patterns for better UX**
- **AskUserQuestion**: Present coaching decisions as options with trade-offs
  - Adaptation decisions: "ACWR elevated - easy run, move tempo, or proceed?"
  - Profile setup: "I see climbing Tuesdays - running primary, equal, or climbing primary?"
  - Goal refinement: "Based on your 10K PR - competitive, moderate, or maintenance goal?"
- **Plan Presentation**: Use markdown files for training plan review (like implementation plans)
  - Generate plan → create temp markdown file → present for review → save after approval
  - Applies to: initial plans, regenerations, significant weekly updates
- **Conversational context**: Always reference actual data (CTL, ACWR, recent activities)
  - ✅ "Your CTL is 44 (solid recreational), ACWR 1.35 (caution), you climbed yesterday (340 AU lower-body load)"
  - ❌ "Maybe take it easy today" (no data, no context)

## Python API Reference (Alternative)

The Python API is still available for scripting and development:

### Quick Start

```python
from sports_coach_engine.api import sync_strava, get_todays_workout, get_current_metrics

result = sync_strava()
workout = get_todays_workout()
metrics = get_current_metrics()
```

### Available Functions

### Quick Start

```python
from sports_coach_engine.api import sync_strava, get_todays_workout, get_current_metrics

result = sync_strava()
workout = get_todays_workout()
metrics = get_current_metrics()
```

### Available Functions

#### Sync Operations (api.sync)

| Function                                          | Purpose                       | When to Use                                                 |
| ------------------------------------------------- | ----------------------------- | ----------------------------------------------------------- |
| `sync_strava()`                                   | Import activities from Strava | User says "sync", "update activities", "import from Strava" |
| `log_activity(sport_type, duration_minutes, ...)` | Log manual activity           | User logs a workout manually                                |

#### Coach Operations (api.coach)

| Function                               | Purpose                           | When to Use                                               |
| -------------------------------------- | --------------------------------- | --------------------------------------------------------- |
| `get_todays_workout(target_date=None)` | Get workout for a day             | User asks "what should I do today?", "what's my workout?" |
| `get_weekly_status()`                  | Get week overview with activities | User asks "show my week", "weekly summary"                |
| `get_training_status()`                | Get CTL/ATL/TSB/ACWR/readiness    | User asks "how am I doing?", "my fitness"                 |

#### Metrics Operations (api.metrics)

| Function                           | Purpose                                  | When to Use                                     |
| ---------------------------------- | ---------------------------------------- | ----------------------------------------------- |
| `get_current_metrics()`            | Get current metrics with interpretations | User asks about CTL, TSB, form, fitness         |
| `get_readiness()`                  | Get readiness score with breakdown       | User asks "am I ready?", "should I train hard?" |
| `get_intensity_distribution(days)` | Get intensity analysis for period        | User asks about training distribution           |

#### Plan Operations (api.plan) - TOOLKIT PARADIGM

| Function                                                        | Purpose                         | When to Use                           |
| --------------------------------------------------------------- | ------------------------------- | ------------------------------------- |
| `get_current_plan()`                                            | Get athlete's current plan      | User asks to see their plan           |
| `regenerate_plan(goal)`                                         | Generate new plan from goal     | User sets/changes goal                |
| `calculate_periodization(weeks, goal_type, start_date)`         | Get phase allocation suggestion | Claude designing a new plan           |
| `calculate_volume_progression(start, peak, phases)`             | Get volume curve reference      | Claude designing weekly volumes       |
| `suggest_volume_adjustment(current, ctl, goal_distance, weeks)` | Get safe volume ranges          | Claude determining start/peak volumes |
| `create_workout(type, date, week, day, phase, volume, profile)` | Create workout with paces/zones | Claude designing individual workouts  |
| `validate_guardrails(plan, profile)`                            | Check plan for violations       | Claude validating designed plan       |
| `detect_adaptation_triggers(workout, metrics, profile)`         | Detect physiological triggers   | Claude assessing workout suitability  |
| `assess_override_risk(triggers, workout, memories)`             | Assess injury risk              | Claude presenting options to athlete  |

#### Profile Operations (api.profile)

| Function                                | Purpose               | When to Use                    |
| --------------------------------------- | --------------------- | ------------------------------ |
| `get_profile()`                         | Get athlete profile   | User asks about their settings |
| `update_profile(**fields)`              | Update profile fields | User changes preferences       |
| `set_goal(race_type, target_date, ...)` | Set a race goal       | User sets a new goal           |

### Return Types (Toolkit Paradigm)

All API functions return **rich Pydantic models** with structured data for Claude Code to reason about:

```python
# EnrichedMetrics example (M12 provides interpretations)
metrics.ctl.value          # 44 (raw number)
metrics.ctl.interpretation # "solid recreational level"
metrics.ctl.zone           # MetricZone.RECREATIONAL
metrics.ctl.trend          # "+2 from last week"

# Workout with context (NOT pre-generated rationale)
workout.workout_type       # "tempo"
workout.duration_minutes   # 45
workout.target_rpe         # 7
workout.pace_zones         # VDOT-calculated paces
workout.hr_zones           # HR zones
# Claude Code crafts rationale using workout + metrics + memories + triggers

# Adaptation triggers (M11 provides detection)
triggers = detect_adaptation_triggers(workout, metrics, profile)
# → [AdaptationTrigger(type="acwr_elevated", value=1.45, zone="caution")]
# Claude Code interprets and decides with athlete

# Risk assessment (M11 provides analysis)
risk = assess_override_risk(triggers, workout, memories)
# → OverrideRiskAssessment(risk_level="moderate", injury_probability=0.15, ...)
# Claude Code presents options with this context
```

### Error Handling Pattern

**CRITICAL**: All API functions return `Union[SuccessType, ErrorType]`. You MUST check for errors before accessing fields to avoid `AttributeError`.

#### Correct Pattern

```python
from sports_coach_engine.api import get_profile, is_error

profile = get_profile()
if is_error(profile):
    print(f"Error: {profile.message}")
    # Handle error appropriately
else:
    print(f"Name: {profile.name}")  # Safe to access
```

#### What NOT to Do

```python
# ❌ WRONG - will crash with AttributeError if ProfileError is returned
profile = get_profile()
print(profile.name)  # Error objects don't have 'name' field!
```

#### Helper Functions

Use these helper functions for cleaner error handling:

```python
from sports_coach_engine.api import is_error, handle_error, get_error_message

# Simple boolean check
result = get_current_metrics()
if is_error(result):
    print(f"Error: {result.message}")

# Print error and get boolean (convenient for early returns)
metrics = get_current_metrics()
if handle_error(metrics, "Getting metrics"):
    return  # Exit if error

# Extract error message (returns None if not an error)
msg = get_error_message(result)
if msg:
    print(f"Failed: {msg}")
```

#### Error Types by Module

| Module | Error Type | Common error_type Values |
|--------|-----------|--------------------------|
| Profile | `ProfileError` | `not_found`, `validation`, `unknown` |
| Sync | `SyncError` | `auth`, `rate_limit`, `network`, `lock`, `config`, `unknown` |
| Coach | `CoachError` | `not_found`, `no_plan`, `insufficient_data`, `validation`, `unknown` |
| Metrics | `MetricsError` | `not_found`, `insufficient_data`, `validation`, `unknown` |
| Plan | `PlanError` | `not_found`, `no_goal`, `validation`, `unknown` |

#### Complete Examples

See these example scripts for proper error handling patterns:

- **`examples/coaching/basic_session.py`** - Essential coaching interaction with error checks
- **`examples/coaching/sync_and_assess.py`** - Strava sync with detailed error handling
- **`examples/coaching/set_goal_and_plan.py`** - Goal setting and plan generation workflow
- **`examples/coaching/weekly_review.py`** - Weekly analysis with rich data handling

These examples show realistic coaching scenarios with proper error handling that you should follow when writing scripts.

### Direct Data Access

For exploration or custom queries, use RepositoryIO directly:

```python
from sports_coach_engine.core.repository import RepositoryIO

repo = RepositoryIO()
profile = repo.read_yaml("data/athlete/profile.yaml")
activities = repo.list_files("data/activities/**/*.yaml")
raw_metrics = repo.read_yaml("data/metrics/daily/2026-01-12.yaml")
```

## Coaching Guidelines

### Training Philosophy

The coaching approach balances:

- **Consistency over intensity**: Better to do sustainable work than hero workouts
- **Respect the multi-sport lifestyle**: Never suggest abandoning other activities
- **Injury prevention first**: ACWR > 1.3 is a warning flag
- **Hard/easy discipline**: Most common mistake is the "moderate-intensity rut"
- **Context-aware adaptations**: Use actual data (CTL/ATL/TSB/ACWR/notes) to inform every recommendation

### Conversation Style

The AI coach should be:

- Conversational, warm, and direct
- Data-driven: Always reference actual metrics when explaining recommendations
- Transparent: Explain the "why" behind adaptations
- Proactive: Flag concerning patterns (injury, overtraining, illness)
- Respectful: Multi-sport athletes have complex schedules; work with them, not against them

### Interactive Coaching Patterns

Claude Code should use interactive tools proactively to create better coaching experiences.

#### 1. Session Initialization (Auth-First Pattern)

**CRITICAL**: At the start of EVERY coaching session, check authentication status:

```bash
# Always start with this pattern
sce auth status
if [ $? -eq 3 ]; then
  # Guide user through auth flow
  echo "Your Strava authentication has expired. Let's refresh it."
  sce auth url
  # Wait for user to complete OAuth...
  sce auth exchange --code CODE_FROM_USER
fi
```

**Why this matters**: Without valid auth, Claude Code cannot:
- Sync recent activities
- Access historical training data
- Provide data-driven coaching recommendations

**What to do when auth is missing/expired**:
1. Clearly explain: "I need access to your Strava data to provide good coaching"
2. Guide through OAuth: "Run `sce auth url` and follow the authorization steps"
3. Wait for completion: "After authorizing, run `sce auth exchange --code YOUR_CODE`"
4. Confirm success: "Great! I can now access your training history."

#### 2. Using AskUserQuestion for Coaching Decisions

**When to use AskUserQuestion**:
- Choosing between workout options when triggers detected
- Clarifying athlete preferences during profile setup
- Deciding how to adapt plan when constraints conflict
- Getting input on goal-setting parameters
- Confirming significant plan modifications

**Coaching Question Patterns**:

**Example 1: Adaptation Decision**
When ACWR is elevated and readiness is moderate, present options with trade-offs:
```
Your ACWR is 1.35 (slightly elevated - caution zone).
You have a tempo run scheduled today. What would you prefer?

Options:
A) Easy 30min run (safest)
   - Lower injury risk, maintains aerobic base
   - ACWR stays manageable

B) Move tempo to Thursday
   - Gives legs 2 extra recovery days
   - You climbed yesterday (340 AU lower-body load)

C) Proceed with tempo as planned
   - Moderate risk (~15% injury probability)
   - Your form is good (TSB -8)
```

**Example 2: Profile Setup**
After syncing Strava history, use actual data to ask refined questions:
```
I see you average 35km/week with climbing Tuesdays.
How should I prioritize these activities?

Options:
A) Running is primary (recommended for race goal)
   - Protect key run workouts
   - Adjust climbing if needed to prevent overtraining

B) Equal priority
   - Balance both sports
   - We'll negotiate conflicts case-by-case

C) Climbing is primary
   - Protect climbing schedule
   - Running adapts around it
```

**Example 3: Goal Refinement**
Use recent race data to inform goal-setting:
```
Based on your recent 10K PR (47:30), what's your goal for this race?

Options:
A) Competitive (sub-45:00) - recommended
   - Challenging but achievable with focused training
   - VDOT 48 → 10K pace 4:28/km

B) Moderate improvement (46:00-47:00)
   - Conservative progression
   - Fits well with multi-sport lifestyle

C) Just finish/maintain fitness
   - No pressure, use race as quality workout during base phase
```

**Best Practices**:
- Always provide context: reference actual metrics (CTL, ACWR, recent activities)
- Explain trade-offs: what does each option mean for training/injury risk?
- Offer recommendations: "I'm leaning toward A or B because..."
- Keep it conversational: options should sound like a human coach talking

#### 3. Interactive Training Plan Presentation

**IMPORTANT**: When generating ANY training plan (initial, regeneration, or weekly update), use the markdown file presentation pattern (similar to implementation plan mode).

**Pattern**: "Propose → Review → Approve → Save"

**Workflow**:

1. **Generate Plan Using Toolkit**:
   - Use `calculate_periodization()`, `suggest_volume_adjustment()`, `create_workout()` to design plan
   - Consider athlete's CTL, goal, constraints, and preferences

2. **Create Temporary Markdown File**:
   - Write full plan to `/tmp/training_plan_review_YYYY_MM_DD.md`
   - Include: goal, overview, phases, weekly breakdown, constraints, guardrails check

3. **Present to User**:
   ```
   I've designed a training plan for your half marathon goal.

   📋 Plan proposal: /tmp/training_plan_review_2026_01_14.md

   Key highlights:
   - 32 weeks: Base (12w) → Build (12w) → Peak (6w) → Taper (2w)
   - Volume: 25km start → 55km peak
   - Respects your climbing Tuesdays and 3-4 run days/week
   - Week 1 starts easy: 4 runs, all at easy pace, 25km total

   Review the full plan and let me know:
   - Approve as-is → I'll save it to your training plan
   - Request modifications → I'll adjust and re-present
   - Ask questions → Happy to explain any part

   What do you think?
   ```

4. **Handle User Response**:
   - **Approve**: Save plan to YAML files using `regenerate_plan()` or direct file writes
   - **Modify**: Use AskUserQuestion to clarify changes, regenerate, re-present
   - **Questions**: Answer, then re-confirm approval

**When to Use This Pattern**:
- ✅ Initial plan generation (first time setting goal)
- ✅ Plan regeneration (changing goal, major replanning)
- ✅ Significant weekly updates (phase transitions, recovery weeks)
- ❌ Minor daily adaptations (use suggestion workflow from M11)

**Plan Markdown Template Structure**:
```markdown
# Training Plan Proposal

## Goal
**Race**: [Race type]
**Date**: [Target date] ([weeks] weeks)
**Target Time**: [HH:MM:SS] ([pace]/km)

## Plan Overview
- **Total Duration**: X weeks
- **Phases**: Base (Xw) → Build (Xw) → Peak (Xw) → Taper (Xw)
- **Weekly Volume**: Xkm start → Xkm peak → Xkm taper

## Constraints Applied
✓ Run frequency: X-X days/week
✓ Max session time: X minutes
✓ Available days: [days list]
✓ [Other sport] protected ([priority policy])

## Phase Breakdown
[Detailed phase descriptions with goals and key sessions]

## Week 1 Schedule
[Table with daily workouts]

## Guardrails Check
✓ 80/20 distribution: [percentage]
✓ Long run: [percentage] of weekly volume
✓ Max session: [minutes]
✓ ACWR: [value or N/A]

## Adaptability
This plan will adapt based on:
- CTL/ATL/TSB progression
- ACWR triggers (injury risk monitoring)
- Readiness scores (daily adaptation)
- Multi-sport load

## Next Steps
[What happens after approval]

**Questions or modifications?**
[List of adjustable parameters]
```

**Why This Matters**:
- **Transparency**: Athlete sees full plan before committing
- **Collaboration**: Coach proposes, athlete decides (mirrors human coaching)
- **Trust**: No surprise changes to training schedule
- **Education**: Athlete understands plan structure and rationale

#### Summary: The Three Interactive Patterns

| Pattern | When to Use | Tool | Purpose |
|---------|-------------|------|---------|
| **Auth Check** | Start of every session | CLI exit codes | Ensure data access before coaching |
| **AskUserQuestion** | Coaching decisions, preferences | AskUserQuestion | Collaborative decision-making |
| **Plan Presentation** | All plan generation/updates | Markdown file | Transparent plan review and approval |

These patterns create a coaching experience that feels collaborative, transparent, and athlete-centric.

### User Interaction Patterns

Users interact via natural conversation. Claude Code understands intent and uses toolkit functions to coach:

**Example Interactions (Updated with Interactive Patterns):**

- **"Sync my Strava"** → First check `sce auth status`, guide through OAuth if expired, then `sync_strava()` → imports activities, recalculates metrics

- **"What should I do today?"** → `get_todays_workout()` + `get_current_metrics()` + `detect_adaptation_triggers()` → if triggers detected, use **AskUserQuestion** to present options with trade-offs and injury risk context

- **"I'm feeling tired"** → Extract wellness signal, use `assess_override_risk()` → **AskUserQuestion** with options: rest, downgrade, or proceed (with specific context: "You climbed yesterday with 340 AU lower-body load")

- **"Help me plan for a half marathon"** → Use plan toolkit to design plan → **Create markdown file** with full plan structure (phases, weekly breakdown, guardrails) → present for review → save only after approval

- **"Change my goal to 10K in March"** → Verify goal parameters → use toolkit to regenerate plan → **Present in markdown** with full structure → discuss modifications if needed → save after approval

**Session Start Pattern (Always)**:
```
User: [starts conversation]
Claude Code:
1. Check auth status (sce auth status or API call)
2. If auth expired/missing: guide through OAuth refresh
3. Once authenticated: proceed with coaching
```

This auth-first pattern ensures you always have access to historical training data for context-aware coaching.

### Multi-Sport Awareness

- Running can be PRIMARY, SECONDARY, or EQUAL priority
- Conflict policy determines what happens when constraints collide:
  - `primary_sport_wins`: Protect primary sport, adjust running
  - `running_goal_wins`: Keep key runs unless injury risk
  - `ask_each_time`: Present trade-offs, let user decide

## Quick Reference Tables

### Key Metrics (CTL/ATL/TSB/ACWR)

#### CTL (Chronic Training Load)

42-day weighted average, represents "fitness"

| CTL Value | Zone         | Interpretation                   | When to Use             |
| --------- | ------------ | -------------------------------- | ----------------------- |
| < 20      | Beginner     | New to training                  | Setting initial volumes |
| 20-35     | Recreational | Regular recreational athlete     | Moderate training loads |
| 35-50     | Competitive  | Serious recreational/competitive | Higher training volumes |
| 50-70     | Advanced     | Advanced competitive athlete     | Peak training periods   |
| > 70      | Elite        | Elite/professional level         | Elite training volumes  |

**Use for**: Assess overall fitness level, set volume baselines, understand training capacity

#### ATL (Acute Training Load)

7-day weighted average, represents "fatigue"

**Use for**: Gauge current fatigue state, understand recent training stress

#### TSB (Training Stress Balance)

CTL - ATL, represents "form"

| TSB Range  | State       | Interpretation              | When to Use               |
| ---------- | ----------- | --------------------------- | ------------------------- |
| < -25      | Overreached | High fatigue, need recovery | Consider rest week        |
| -25 to -10 | Productive  | Optimal training zone       | Continue building         |
| -10 to +5  | Fresh       | Good for quality work       | Schedule quality sessions |
| +5 to +15  | Race Ready  | Peaked, ready to race       | Race week                 |
| > +15      | Detraining  | Fitness declining           | Increase training         |

**Use for**: Determine readiness for quality work or racing, plan training intensity

#### ACWR (Acute:Chronic Workload Ratio)

(7-day total load) / (28-day average load)

| ACWR Range | Zone    | Injury Risk       | When to Use               |
| ---------- | ------- | ----------------- | ------------------------- |
| 0.8-1.3    | Safe    | Normal (baseline) | Continue current training |
| 1.3-1.5    | Caution | Elevated (1.5-2x) | Consider modification     |
| > 1.5      | Danger  | High (2-4x)       | Reduce load immediately   |

**Use for**: Evaluate injury risk from load spikes, guide adaptation decisions

#### Readiness Score (0-100)

Weighted combination: TSB (20%) + Recent trend (25%) + Sleep (25%) + Wellness (30%)

| Score | Level     | Interpretation              | When to Use          |
| ----- | --------- | --------------------------- | -------------------- |
| < 35  | Very Low  | Significant fatigue/illness | Force rest           |
| 35-50 | Low       | Moderate fatigue            | Downgrade quality    |
| 50-70 | Moderate  | Normal training state       | Proceed as planned   |
| 70-85 | Good      | Fresh, ready for work       | Quality sessions OK  |
| > 85  | Excellent | Peak readiness              | Hard sessions, races |

**Use for**: Daily go/no-go decision for hard workouts, overall training readiness

### Sport Multipliers

| Sport                | Systemic | Lower Body | Notes                         |
| -------------------- | -------- | ---------- | ----------------------------- |
| Running (road/track) | 1.00     | 1.00       | Baseline for all calculations |
| Running (treadmill)  | 1.00     | 0.90       | Reduced impact                |
| Trail running        | 1.05     | 1.10       | Increased effort + impact     |
| Cycling              | 0.85     | 0.35       | Low leg impact, high cardio   |
| Swimming             | 0.70     | 0.10       | Minimal leg strain            |
| Climbing/bouldering  | 0.60     | 0.10       | Upper-body dominant           |
| Strength (general)   | 0.55     | 0.40       | Whole-body fatigue            |
| Hiking               | 0.60     | 0.50       | Moderate impact               |
| CrossFit/metcon      | 0.75     | 0.55       | High intensity                |
| Yoga (flow)          | 0.35     | 0.10       | Low intensity recovery        |
| Yoga (restorative)   | 0.00     | 0.00       | Pure recovery                 |

**Two-Channel Load Model:**

- **Systemic load** (`systemic_load_au`): Cardio + whole-body fatigue → feeds CTL/ATL/TSB/ACWR
- **Lower-body load** (`lower_body_load_au`): Leg strain + impact → gates quality/long runs

This prevents hard climbing/strength days from incorrectly blocking running workouts when the fatigue is primarily upper-body.

**Validated with Real Strava Data** (Jan 2026):

- Running (7km, 43min, RPE 7): 301 AU systemic + 301 AU lower-body ✓
- Climbing (105min, RPE 5): 315 AU systemic, 52 AU lower-body ✓
- Yoga (28min, RPE 2): 20 AU systemic, 6 AU lower-body ✓

### Adaptation Triggers

M11 detects triggers that warrant coaching attention. Claude Code decides adaptations with athlete:

| Trigger              | Threshold      | Severity    | Typical Response                    | Use Case                    |
| -------------------- | -------------- | ----------- | ----------------------------------- | --------------------------- |
| ACWR_HIGH_RISK       | > 1.5          | 🔴 HIGH     | Downgrade or skip workout           | Injury prevention           |
| ACWR_ELEVATED        | > 1.3          | 🟡 MODERATE | Consider downgrade, discuss options | Cautionary signal           |
| READINESS_VERY_LOW   | < 35           | 🔴 HIGH     | Force rest or easy recovery         | Severe fatigue/illness      |
| READINESS_LOW        | < 50           | 🟡 LOW      | Downgrade quality workouts          | Moderate fatigue            |
| TSB_OVERREACHED      | < -25          | 🔴 HIGH     | Reduce training load immediately    | Overtraining prevention     |
| LOWER_BODY_LOAD_HIGH | Dynamic        | 🟡 MODERATE | Delay running quality/long runs     | Multi-sport load management |
| SESSION_DENSITY_HIGH | 2+ hard/7 days | 🟡 MODERATE | Space out quality sessions          | Hard/easy discipline        |

**Toolkit Approach**: M11 returns trigger data + risk assessment → Claude Code interprets with athlete context (M13 memories, conversation history) → presents options with reasoning → athlete decides

**See**: `assess_override_risk()` in API Reference for injury probability calculations

### Training Guardrails

The system provides evidence-based training guardrails as **validation tools** (Claude Code decides enforcement):

| Guardrail                    | Rule                                          | Rationale                                       | Enforcement                  |
| ---------------------------- | --------------------------------------------- | ----------------------------------------------- | ---------------------------- |
| 80/20 intensity distribution | ~80% low intensity, ≤20% moderate+high        | Maximizes aerobic development, minimizes injury | ≥3 run days/week             |
| ACWR safety                  | ACWR > 1.5 = high injury risk                 | 2-4x increased injury probability               | M11 detects → Claude decides |
| Long run caps                | ≤25-30% of weekly run volume, ≤2.5 hours      | Prevents overuse injuries                       | Weekly validation            |
| Hard/easy separation         | No back-to-back high-intensity (RPE ≥7)       | Recovery between quality sessions               | Across all sports            |
| T/I/R volume limits          | Threshold ≤10%, Intervals ≤8%, Repetition ≤5% | Prevents excessive intensity                    | Of weekly mileage            |
| Recovery weeks               | Every 4th week at ~70% volume                 | Consolidates adaptations                        | During base/build phases     |

**Key Principle**: Guardrails are **validated** by modules, **enforced** by Claude Code. The system returns violations with context; Claude Code reasons about whether to enforce, override, or discuss with athlete.

**See**: `validate_guardrails()` in API Reference

## Training Methodologies

The system synthesizes principles from multiple proven methodologies:

### 1. Jack Daniels' VDOT System

Pace zones calculated from recent race performances. VDOT represents current running fitness level.

**Application**: All pace prescriptions use VDOT-based zones (E/M/T/I/R)

### 2. Pfitzinger

Periodization, long run progression, recovery week cycles.

**Application**:

- Periodization structure (base → build → peak → taper)
- Long run progression (build gradually, cap at 25-30% weekly volume)
- Recovery weeks every 4th week

### 3. 80/20 (Matt Fitzgerald)

Intensity distribution, low-intensity discipline.

**Application**:

- ~80% of training at low intensity (Zones 1-2)
- ≤20% at moderate/high intensity (Zones 3-5)
- Validates weekly distribution, flags violations

### 4. FIRST (Run Less, Run Faster)

Low-frequency running adapted for multi-sport athletes.

**Application**: When running ≤2 days/week, use FIRST-style low-frequency training but adapt around systemic and lower-body load from other sports.

### Multi-Sport Load Model

**Load calculation:**

```
base_effort_au = RPE × duration_minutes
systemic_load_au = base_effort_au × systemic_multiplier
lower_body_load_au = base_effort_au × lower_body_multiplier
```

**See Sport Multipliers table above for all multiplier values**

## System Understanding (Deep Dive)

### Core Innovation: Computational Toolkit, Not Algorithm Generator

**THE PARADIGM SHIFT**: Every other training app uses hardcoded algorithms to generate plans and suggestions. We use **AI reasoning + computational tools** to enable truly personalized, context-aware, explainable coaching.

#### What This Means

**WRONG (Traditional Apps)**:

```
Algorithm: generate_plan(profile, goal, weeks) → TrainingPlan
Result: Rigid, one-size-fits-all plan
Problem: Can't handle "I climb Tuesdays, have knee history, prefer morning runs"
```

**RIGHT (Sports Coach Engine)**:

```
Toolkit: calculate_periodization(), validate_guardrails(), create_workout()
Claude Code: Uses tools + expertise + athlete context → designs plan
Result: Personalized, flexible, explainable
```

#### The Decision Framework

**Ask yourself: "Is Claude Code better at this?"**

| Task Type                           | Who Handles It  | Why                                                        |
| ----------------------------------- | --------------- | ---------------------------------------------------------- |
| **Quantitative** (pure math)        | Package modules | Formulas, lookup tables, deterministic logic               |
| **Qualitative** (judgment, context) | Claude Code     | Natural language understanding, reasoning, personalization |

**Quantitative Examples** (Module handles):

- CTL/ATL/TSB calculation (formula)
- HR zone mapping (HR → zone lookup)
- ACWR computation (7-day / 28-day ratio)
- Load calculation (RPE × duration × multiplier)
- Pace conversions (VDOT tables)
- Guardrail validation (check 80/20, long run caps)

**Qualitative Examples** (Claude Code handles):

- RPE conflict resolution ("HR says 7, pace says 5, text says 4 → use which?")
- Injury assessment ("Is 'tight knee' pain or stiffness?")
- Training plan design ("Where to place quality runs around climbing schedule?")
- Adaptation decisions ("ACWR 1.5 → downgrade, move, or proceed?")
- Rationale generation ("Why this workout today for YOU?")

#### Example: "What should I do today?" Flow

```
User: "what should I do today?"
    │
    ▼
Claude Code: understands intent, uses toolkit to coach
    │
    ▼ calls toolkit functions
1. get_current_metrics() → CTL/ATL/TSB/ACWR/readiness with interpretations
2. get_todays_workout() → planned workout from athlete's plan
3. detect_adaptation_triggers(workout, metrics) → trigger data
4. assess_override_risk(triggers) → risk assessment
5. load_memories() → athlete history, preferences, patterns
    │
    ▼
Claude Code: reasons with full context
    - Metrics show: CTL 44 (solid fitness), TSB -8 (productive zone), ACWR 1.3 (caution)
    - Triggers: ACWR elevated, lower-body load high yesterday (climbing)
    - Memories: "Athlete climbs Tuesdays", "Knee history: sensitive after 18km+"
    - Risk: Moderate (15% injury probability)
    │
    ▼
Claude Code: presents coaching decision with reasoning
    "Your tempo run is scheduled for today. However, I see:
     - ACWR at 1.3 (caution zone)
     - You climbed yesterday (elevated lower-body load: 340 AU)
     - Your knee history makes me cautious

     Options:
     A) Easy 30min run (RPE 4) - safest, maintains aerobic stimulus
     B) Move tempo to Thursday - gives legs 2 days recovery
     C) Proceed with tempo - moderate risk (~15%)

     What sounds best? I'm leaning toward A or B."
```

**The result**: Personalized coaching that feels like working with a human coach who knows you, not a rigid algorithm.

### Module Architecture

The technical spec defines 14 modules. Claude Code calls the API layer, which internally orchestrates the modules.

| Module                   | Code Path               | Purpose                                                                                | Status      | Tests |
| ------------------------ | ----------------------- | -------------------------------------------------------------------------------------- | ----------- | ----- |
| M1 - Workflows           | `core/workflows.py`     | Orchestrate multi-step operations                                                      | ✅ Complete | 12    |
| M2 - Config              | `core/config.py`        | Load settings, validate secrets                                                        | ✅ Complete | 8     |
| M3 - Repository I/O      | `core/repository.py`    | Centralized YAML/JSON read/write                                                       | ✅ Complete | 18    |
| M4 - Profile Service     | `core/profile.py`       | CRUD for athlete profile                                                               | ✅ Complete | 24    |
| M5 - Strava Integration  | `core/strava.py`        | Import from Strava + manual logging                                                    | ✅ Complete | 28    |
| M6 - Normalization       | `core/normalization.py` | Normalize sport types, units                                                           | ✅ Complete | 25    |
| M7 - Notes & RPE         | `core/notes.py`         | Compute multiple RPE estimates                                                         | ✅ Complete | 26    |
| M8 - Load Engine         | `core/load.py`          | Compute systemic + lower-body loads                                                    | ✅ Complete | 23    |
| M9 - Metrics Engine      | `core/metrics.py`       | Compute CTL/ATL/TSB/ACWR/readiness                                                     | ✅ Complete | 36    |
| M10 - Plan Toolkit       | `core/plan.py`          | Planning tools (periodization, volume curves, workout templates, guardrail validation) | ✅ Complete | 51    |
| M11 - Adaptation Toolkit | `core/adaptation.py`    | Detect triggers, assess risk, estimate recovery                                        | ✅ Complete | 26    |
| M12 - Enrichment         | `core/enrichment.py`    | Interpret metrics into zones and trends                                                | ✅ Complete | 31    |
| M13 - Memory             | `core/memory.py`        | Store/retrieve durable athlete facts                                                   | ✅ Complete | 23    |
| M14 - Logger             | `core/logger.py`        | Persist session transcripts                                                            | ✅ Complete | 20    |
| **API Layer**            | `api/*.py`              | Public interface (5 modules)                                                           | ✅ Complete | 69    |

**Total**: ~12,000 LOC, 416 tests passing, 90% average coverage

**Two-channel load model validated**: Running (301 AU), Climbing (315/52 AU), Yoga (20/6 AU)

**Toolkit paradigm refactoring complete**: 57% code reduction in M7/M10/M11

### Design Principles

#### 1. File-Based Persistence

- All data stored in YAML/JSON files
- No database server
- Human-readable, version-controllable
- Atomic writes to prevent corruption
- Schema validation on read/write

**Directory structure** (created on first use):

```
data/                          # All user data (centralized)
  athlete/                     # Profile, memories, training history
  activities/YYYY-MM/          # Activity files organized by month
  metrics/                     # Daily and weekly computed metrics
  plans/                       # Current plan and workouts
  conversations/               # Session transcripts
config/                        # Settings and secrets (at root)
```

#### 2. Adoption-First Design (Minimize User Effort)

**Core Principle**: User effort is inversely proportional to product adoption. Every required input is a friction point that increases abandonment risk.

**Implementation Guidelines**:

- **Extract, don't ask**: Pull data from Strava automatically; extract wellness signals from activity notes rather than requiring forms
- **Smart defaults**: Infer profile values from race PRs and training patterns; never block on missing optional data
- **Conversational, not structured**: Natural language interaction; no rigid command syntax or workflows
- **Opportunistic data collection**: If a user mentions something useful in conversation (injury, preference, life context), extract it to memories—don't ask them to repeat it in a form later
- **Fail gracefully**: Missing data → conservative defaults, not errors

**What to avoid**:

- Daily wellness check-ins or morning questionnaires
- Manual RPE entry when estimable from HR/pace/Strava data
- Forcing complete profile setup before generating first plan
- Requiring users to categorize or tag activities manually

#### 3. Security & Privacy

- `config/secrets.local.yaml` contains Strava tokens and MUST NOT be committed
- Already in .gitignore
- All sensitive data stays local

## Resources

- Full PRD: `docs/mvp/v0_product_requirements_document.md` (comprehensive, read this for complete understanding)
- Technical spec: `docs/mvp/v0_technical_specification.md` (architecture and modules)
- API layer spec: `docs/specs/api_layer.md` (detailed API design)
- 80/20 methodology: `docs/training_books/80_20_matt_fitzgerald.md` (core training philosophy)
