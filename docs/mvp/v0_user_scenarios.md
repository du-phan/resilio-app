# Resilio v0 - User Scenarios Specification

## 1. Introduction

### 1.1 Purpose

This document specifies the three core usage scenarios for the Resilio v0:

1. **Scenario 1: New User Setup** - First-time athlete onboarding
2. **Scenario 2: Existing User Weekly Cycle** - Ongoing training management
3. **Scenario 3: Reset / Archive / Fresh Start** - Plan changes and data management

Each scenario is broken down into precise steps, mapped to technical modules (M1-M13), and identifies gaps requiring resolution before implementation.

### 1.2 Relationship to Other Documents

| Document                              | Scope                                                           |
| ------------------------------------- | --------------------------------------------------------------- |
| `v0_product_requirements_document.md` | **What** the system does (features, metrics, guardrails)        |
| `v0_technical_specification.md`       | **How** the system is built (modules, schemas, data flows)      |
| **This document**                     | **When** and **in what sequence** things happen (user journeys) |

### 1.3 Core Assumptions

- **Single-user**: v0 assumes one athlete per repository. Multi-user support deferred to future versions.
- **Strava required**: Activity data comes exclusively from Strava. Manual logging not supported in v0.
- **Plan stability**: Adaptations are suggested, not auto-applied. The plan is a stable reference that changes only with user consent.
- **Claude Code as Interface**: Claude Code (the AI) runs in the repository as the coach. It handles all natural language understanding, conversation management, and response formatting. The `resilio` package provides callable Python functions that return structured data. Claude Code naturally understands user intent—no keyword matching or intent parsing logic is needed in the package.

### 1.4 Formatting Conventions

#### Date Formatting

All activity references and schedules should include full dates for clarity:
- **Activity references**: "Day Month Date" (e.g., "Tuesday January 7th")
- **Week displays**: Include date range (e.g., "Week of January 6-12")
- **Sync summaries**: "Synced 2 activities since Monday, January 13th"

#### Multi-Sport Display

The system serves **multi-sport athletes**. All weekly status displays and sync responses must:
- Show ALL activities (running, climbing, cycling, yoga, etc.), not just running
- Include load breakdown (systemic + lower-body) for each activity
- Explain how non-running activities affect running readiness
- Respect the athlete's conflict policy when presenting options

---

## 2. Scenario 1: New User Setup (Cold Start)

### 2.1 User Perspective

The athlete installs the Resilio and wants to get started with personalized training. They expect:

1. Quick setup (< 10 minutes)
2. Connection to their existing Strava data
3. A training plan that reflects their current fitness, not arbitrary defaults
4. Clear explanation of what to do next

### 2.2 System Perspective

The system must:

1. Detect first-time setup (no profile exists)
2. Authenticate with Strava and import historical data
3. Ask minimal questions to fill gaps Strava can't provide
4. Generate a full training plan calibrated to actual fitness
5. Hand off to regular operation with clear next steps

### 2.3 Step-by-Step Flow

#### Phase A: Initial Contact

| Step | User Action              | System Response                                             | Module(s) |
| ---- | ------------------------ | ----------------------------------------------------------- | --------- |
| A1   | Runs Claude Code in repo | Detects missing `athlete/profile.yaml`                      | M1, M3    |
| A2   | —                        | "Welcome! I'm your AI running coach. Let's get you set up." | M12       |
| A3   | —                        | Initiates onboarding dialogue                               | M1        |

#### Phase B: Strava Connection (Required)

| Step | User Action             | System Response                                                               | Module(s) |
| ---- | ----------------------- | ----------------------------------------------------------------------------- | --------- |
| B1   | —                       | "First, let's connect your Strava account to import your training history."   | M12       |
| B2   | Authorizes Strava OAuth | Receives access token, stores in `config/secrets.local.yaml`                  | M2, M5    |
| B3   | —                       | Fetches 8-12 weeks of activity history                                        | M5        |
| B4   | —                       | Extracts athlete stats (PRs, recent races)                                    | M5        |
| B5   | —                       | "Found 47 activities over the past 10 weeks. Let me analyze your training..." | M12       |

**Edge Cases:**

- Strava authorization fails → Retry with clear error message
- No activity history → Proceed with cold-start defaults (CTL=0)
- < 14 days of history → Set `baseline_established: false`

#### Phase C: Essential Data Collection

The system asks only what Strava cannot provide:

| Step | Question                                                                                                                            | Purpose                                            | Module(s)   |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ----------- |
| C1   | "What's your running goal? (e.g., 'Half marathon on March 15' or 'General fitness')"                                                | Determines plan structure and periodization        | M1, M4      |
| C2   | "How many days per week can you realistically run?"                                                                                 | Constrains weekly structure                        | M1, M4      |
| C3   | "I see you also do [cycling/climbing/...]. Which sport takes priority when schedules conflict?"                                     | Sets conflict policy                               | M1, M4      |
| C4   | "How does [other sport] feel for your legs? Mostly upper-body, or do you feel it in your legs too?"                                 | Determines lower-body load multiplier adjustments  | M1, M4, M8  |
| C5   | "Can you handle two training sessions in one day? (e.g., morning run + evening climbing, or quality run + yoga)"                    | Enables double-day scheduling when safe            | M1, M4, M10 |
| C6   | "Any current injuries or recurring issues I should know about?"                                                                     | Safety baseline                                    | M1, M4, M13 |

**What we DON'T ask:**

- Recent race time (we'll ask directly: "What's your recent 5K/10K time?" during onboarding if not in Strava)
- Current weekly volume (calculated from Strava)
- Daily wellness scores (never required)

#### Phase D: Profile & Baseline Creation

| Step | Action                            | Output                                                         | Module(s) |
| ---- | --------------------------------- | -------------------------------------------------------------- | --------- |
| D1   | Create athlete profile            | `athlete/profile.yaml` with goal, constraints, conflict_policy | M4, M3    |
| D2   | Normalize imported activities     | `activities/YYYY-MM/*.yaml` files                              | M6        |
| D3   | Analyze notes for RPE/wellness    | RPE estimates, wellness flags extracted                        | M7        |
| D4   | Calculate loads for each activity | `systemic_load_au`, `lower_body_load_au` computed              | M8        |
| D5   | Compute baseline metrics          | CTL/ATL/TSB from actual history                                | M9        |
| D6   | Extract initial memories          | Injury mentions, preferences noted                             | M13       |
| D7   | Set baseline flag                 | `baseline_established: true` if ≥14 days                       | M4        |

**Example output:**

```
Based on your Strava data:
- Current fitness (CTL): 42
- Recent fatigue (ATL): 38
- Form (TSB): +4 (fresh)
- Average weekly volume: 32 km over 4 runs
- Recent 10K: 48:32 (from Nov 12) → VDOT 42 → Easy pace: 5:50-6:10/km
```

#### Phase E: Initial Plan Generation (Master Plan - Tier 1)

| Step | Action                              | Output                                        | Module(s) |
| ---- | ----------------------------------- | --------------------------------------------- | --------- |
| E1   | Determine periodization structure   | Phases: base → build → peak → taper           | M10       |
| E2   | Calculate weekly volume progression | Week-by-week km targets based on current CTL  | M10       |
| E3   | Assign workout types per week       | Long run, tempo, intervals, easy runs         | M10       |
| E4   | Schedule recovery weeks             | Every 4th week: reduce volume 20-30%          | M10       |
| E5   | Apply guardrails                    | 80/20 intensity, long-run caps, T/I/R limits  | M10       |
| E6   | Generate workout files              | `plans/workouts/week_##/*.yaml` for all weeks | M10, M3   |
| E7   | Create master plan file             | `plans/current_plan.yaml`                     | M10, M3   |

**Calibration principle:**

- Weekly volume matches recent average (not arbitrary reduction)
- First 1-2 weeks: emphasize easy runs, limit quality sessions (let system learn)
- "Conservative" = don't ADD stress, not slash existing workload

**Example:**

```
Athlete averaging 32km/week → Plan starts at ~30-32km/week with easy emphasis
NOT: "Start with a conservative 15km week" (ignores actual fitness)
```

#### Phase F: Handoff to Regular Operation

| Step | Action                      | Output                                                        | Module(s) |
| ---- | --------------------------- | ------------------------------------------------------------- | --------- |
| F1   | Present plan summary        | "Here's your 14-week plan to your March 15 half marathon..."  | M12       |
| F2   | Show current week           | This week's Mon-Sun workout schedule                          | M12       |
| F3   | Explain next steps          | "Sync your Strava 2-3x per week. Say 'show my week' anytime." | M12       |

### 2.4 Module Mapping Summary

| Phase                 | Primary Modules         | Supporting Modules |
| --------------------- | ----------------------- | ------------------ |
| A: Initial Contact    | M1, M3                  | M12                |
| B: Strava Connection  | M5, M2                  | M12                |
| C: Data Collection    | M1, M4                  | M12                |
| D: Profile & Baseline | M4, M6, M7, M8, M9, M13 | M3                 |
| E: Plan Generation    | M10                     | M3                 |
| F: Handoff            | M12                     | —                  |

---

## 3. Scenario 2: Existing User Weekly Cycle

### 3.1 User Perspective

The athlete has a training plan and is actively training. During a typical week, they:

1. Complete workouts and sync Strava
2. Check their weekly status ("Where am I vs the plan?")
3. Make adjustments when life happens (schedule changes, fatigue, missed workouts)
4. Review the week and prepare for next week

**Key insight:** The user already HAS the plan. They don't ask "what should I do today?" They need status visibility and adjustment capability.

### 3.2 Interaction Patterns

**Claude Code's Role in Patterns:**

In all interaction patterns below, Claude Code (the AI running in the terminal) serves as the coach:

1. **User speaks naturally** - No rigid command syntax required (e.g., "sync my Strava" or "update activities" both work)
2. **Claude Code understands intent** - Uses natural language understanding to determine what the user wants
3. **Claude Code calls package functions** - Invokes appropriate functions from `resilio.api` (e.g., `sync_strava()`, `get_weekly_status()`)
4. **Package returns structured data** - Functions return Pydantic models with enriched data (e.g., `SyncResult`, `EnrichedMetrics`, `WorkoutRecommendation`)
5. **Claude Code formats response** - Crafts conversational response using the returned data, adapting to context and conversation history

The package does NOT parse intent, match keywords, or generate formatted text responses—that's all Claude Code. The package focuses on training science, calculations, and data management.

#### Pattern A: Sync Strava (2-3x per week)

**Trigger:** User says "Sync my Strava" or similar

**Flow:**

```
M1 (parse intent) → M5 (fetch since last_sync) → M6 (normalize) → M7 (analyze notes)
→ M8 (calculate loads) → M13 (extract memories) → M9 (recompute metrics)
→ M11 (check adaptation triggers, generate suggestions) → M12 (render)
```

**Response includes:**

- Activities synced (count, types)
- Current metrics (CTL/ATL/TSB/ACWR)
- Week progress: "3/5 workouts completed"
- Pending suggestions if any triggers fired (NOT auto-applied)

**Example response:**

```
Synced 3 activities since Monday, January 13th:
Quick defs (first mention only): RPE is your perceived effort from 1–10. CTL is your long-term training load—think of it as your 6-week fitness trend. TSB is freshness (long-term fitness minus short-term fatigue). ACWR compares this week to your recent average; high values mean a sudden spike. For multi-sport athletes, these reflect total work across running + other sports.

Running:
- Tue Jan 14: Tempo run 48min, RPE 7
  → Systemic: 336 AU | Lower-body: 336 AU
- Wed Jan 15: Easy run 35min, RPE 4
  → Systemic: 140 AU | Lower-body: 140 AU

Other sports:
- Mon Jan 13: Bouldering 2h, RPE 6 (upper-body session)
  → Systemic: 432 AU | Lower-body: 72 AU

Week load so far: 908 AU systemic | 548 AU lower-body

Current status:
- Fitness (CTL): 44 (+2 this week) — solid recreational level
- Form (TSB): -8 (productive training zone)
- ACWR: 1.18 (safe)
- Lower-body: Moderate (Monday climbing was upper-body focused)

Running progress: 2/4 workouts complete
Remaining: Thu Jan 16 easy run, Sat Jan 18 long run

Note: I factored Monday's bouldering into your load calculations.
Since it was upper-body dominant, your legs should be relatively fresh.
```

#### Pattern B: Weekly Status Check (PRIMARY daily pattern)

**Trigger:** User says "Show me my week" / "Where am I at?" / "Weekly status"

**Flow:**

```
M1 (parse intent) → M3/M10 (read plan) → M9 (current metrics) → M12 (render)
```

**Response includes:**

- This week's plan overview (Mon-Sun grid)
- Completed workouts marked with actual vs planned
- Remaining workouts with dates
- Pending suggestions (if any)
- Current readiness/form status

**Example response:**

```
Week 3 of 14 (Build Phase) — January 13-19

Mon Jan 13: Bouldering (2h) ✓ — load: 630 AU systemic | 105 AU lower-body
Tue Jan 14: Tempo 45min → Done (48min @ 5:08/km, felt strong!)
            → Systemic: 336 AU | Lower-body: 336 AU
Wed Jan 15: Easy 35min → Done (35min)
            → Systemic: 140 AU | Lower-body: 140 AU
Thu Jan 16: Bouldering (2h) + Easy 30min → TODAY
            ↳ Run in morning if legs feel fresh; skip if fatigued after climbing
Fri Jan 17: Rest
Sat Jan 18: Long run 14km → Scheduled
Sun Jan 19: Cycling 90min (planned, weather dependent)

Running Progress: 2/4 complete
Total Week Load: 1,106 AU systemic | 581 AU lower-body (so far)

Current Status:
Quick defs (first mention only): CTL is your long-term training load—think of it as your 6-week fitness trend. TSB is freshness (long-term fitness minus short-term fatigue). ACWR compares this week to your recent average; high values mean a sudden spike. For multi-sport athletes, these reflect total work across running + other sports.
- Fitness (CTL): 44 (+2 this week) — solid recreational level
- Form (TSB): -8 (productive training zone)
- ACWR: 1.15 (safe)
- Lower-body: Moderate (Monday climbing was upper-body focused)

Note: Thursday has both bouldering and running scheduled. Your legs should
be relatively fresh since Monday's climbing was mostly upper-body work.
```

#### Pattern C: Plan Adjustment (when life happens)

**Trigger:** User reports schedule change, missed workout, or fatigue

**Examples:**

- "I need to move Wednesday's run"
- "I missed yesterday's tempo"
- "I'm feeling really tired"
- "I have a dinner Thursday, can't run"
- "I went climbing yesterday instead of the running session"
- "My yoga class ran long, should I still do my easy run?"

**Flow:**

```
M1 (parse intent) → M11 (evaluate options based on metrics/plan)
→ M12 (present alternatives) → User chooses → M3 (update plan)
```

**Response pattern:**

```
User: "I missed yesterday's tempo"

Coach: [Auto-detected during sync — coach doesn't need user to report this]
       "I noticed your tempo run from Tuesday isn't in Strava. No problem—
        here are your options:

        1. Move it to Thursday (swap with easy run)
        2. Add tempo segments to Saturday's long run (ACWR is safe at 1.18)
        3. Skip it and continue as planned

        Given your Thursday bouldering session is fixed, option 1 would mean
        doing quality running the same day as climbing.

        My recommendation: Option 3 (skip). You've had a good week already
        and consistency matters more than any single workout.

        Which do you prefer?"
```

**Multi-sport conflict example:**

```
User: "I went climbing yesterday instead of my scheduled easy run"

Coach: "Got it—I see the 2-hour bouldering session from yesterday in Strava.

        Impact on your week:
        - Systemic load: Added 630 AU (vs ~180 AU from easy run)
        - Lower-body load: Only 105 AU (climbing was upper-body dominant)

        Good news: Your legs are actually fresher than if you'd run.
        Tomorrow's tempo run is still good to go.

        Want me to mark Tuesday's easy run as 'swapped for climbing'?"
```

**Key principle:** Coach suggests options with rationale; user decides.

**Auto-detection note:** When syncing Strava, the system automatically compares
synced activities against the planned schedule. If a planned workout has no
matching activity, it flags as potentially missed and proactively presents
options—the athlete doesn't need to remember to report missed workouts.

#### Pattern D: Next Week Preview (anytime)

**Trigger:** User says "What's next week?" / "Show next week's plan"

**Flow:**

```
M1 (parse intent) → M10 (read next week's workouts) → M12 (render with context)
```

**Response includes:**

- Next week's workout schedule
- Focus/theme for the week
- Key sessions highlighted
- Pre-emptive notes (travel, events from profile)

#### Pattern E: Weekly Summary (end of week)

**Trigger:** User says "How did my week go?" or implicit after Sunday sync

**Flow:**

```
M9 (compute weekly summary) → M12 (render analysis)
```

**Response includes:**

- Execution rate (4/5 workouts completed)
- Total volume vs planned
- Intensity distribution (80/20 check)
- Key observations
- Metrics trend (CTL up, form improving)
- Segue to next week

#### Pattern F: Next Week Plan Generation (CRITICAL WEEKLY WORKFLOW)

**Trigger:** Week boundary (Sunday sync) or explicit request ("Plan next week")

**Flow:**

```
M9 (weekly summary) → M10 (refine next week's workouts) → M12 (present)
```

**Process:**

1. **Analyze current week execution:**

   - What was completed vs skipped?
   - How did actual effort compare to prescribed?
   - Any injury/fatigue flags emerged?

2. **Review current metrics:**

   - CTL trend (fitness building?)
   - ATL (current fatigue level)
   - TSB (form status)
   - ACWR (injury risk)

3. **Consider periodization phase:**

   - Where are we in the training cycle?
   - Is it a build week, recovery week, peak week?

4. **Refine next week's workouts:**

   - Take the pre-planned structure from master plan
   - Adjust specific details based on current state
   - Example: If fitness improved, slightly increase tempo duration

5. **Present to user with rationale:**

   ```
   Based on Week 3 (January 13-19):
   - Running: 4/5 workouts complete (tempo skipped due to travel)
   - All activities: Running (38km) + Bouldering (4h) + Cycling (90min)
   - CTL increased from 42 to 44
   - ACWR at 1.18 (safe)
   - Lower-body load managed well (climbing was upper-body focused)

   Week 4 Focus: Build (adding interval work) — January 20-26

   Mon Jan 20: Bouldering (2h, fixed) — your regular session
   Tue Jan 21: Intervals 6x800m @ I-pace
               ↳ Legs should be fresh after upper-body climbing
   Wed Jan 22: Easy 35min
   Thu Jan 23: Bouldering (2h, fixed) + Easy 30min (optional)
               ↳ Run in morning if feeling good
   Fri Jan 24: Rest
   Sat Jan 25: Long run 16km
   Sun Jan 26: Cycling 90min (planned, weather dependent)

   Running volume: 40km | Total load: ~2,400 AU systemic

   Shall I confirm this plan or would you like adjustments?
   ```

### 3.3 Two-Tier Plan Architecture

**Tier 1: Master Plan (from Scenario 1)**

- Covers all weeks from now to goal date
- Contains periodization phases, weekly volume progression, workout types
- Gives athlete visibility into the full journey
- Stored in `plans/current_plan.yaml`

**Tier 2: Weekly Refinement (Scenario 2, Pattern F)**

- At week boundary, coach takes the pre-planned structure
- Refines specific details based on current state
- STRUCTURE stays consistent with master plan
- DETAILS adapt to current reality

**Example:**

```
Master plan (week 5): Long run 16km, Tempo 45min, Easy 30min x2

After week 4 analysis:
  - Athlete executed well, CTL up 3 points
  - ACWR at 1.25 (safe but building)

Refined week 5:
  - Long run 16km (unchanged)
  - Tempo 48min (slightly longer, fitness supports it)
  - Easy 35min x2 (maintain base)
```

### 3.4 Adaptation Trigger Timing

**When suggestions are generated:**

- After sync → M11 checks all triggers
- Suggestions are presented, NOT auto-applied
- User can accept, decline, or ask for alternatives

**Trigger types:**

| Trigger                | Threshold                          | Suggested Action                       |
| ---------------------- | ---------------------------------- | -------------------------------------- |
| ACWR elevated          | > 1.3                              | Reduce next quality session intensity  |
| ACWR high              | > 1.5                              | Convert quality to easy, consider rest |
| Readiness low          | < 50                               | Downgrade intensity                    |
| Readiness very low     | < 35                               | Rest day                               |
| High lower-body load   | > threshold (relative or absolute) | Gate quality/long runs                 |
| Injury flag in notes   | Keywords detected                  | Force rest with notification           |
| 2+ hard sessions in 7d | Count exceeded                     | Move or downgrade next quality         |

**Safety-critical exceptions (auto-apply with notification):**

- Injury flag detected → Force rest, notify user
- ACWR > 1.5 AND readiness < 35 → Auto-downgrade with strong warning

### 3.5 Module Mapping Summary

| Pattern                 | Primary Modules         | Supporting Modules |
| ----------------------- | ----------------------- | ------------------ |
| A: Sync Strava          | M5, M6, M7, M8, M9, M11 | M13, M12           |
| B: Weekly Status        | M3, M10, M9             | M12                |
| C: Plan Adjustment      | M1, M11                 | M3, M12            |
| D: Next Week Preview    | M10                     | M12                |
| E: Weekly Summary       | M9                      | M12                |
| F: Next Week Generation | M9, M10                 | M12                |

---

## 4. Scenario 3: Reset / Archive / Fresh Start

### 4.1 Use Cases

| Sub-Scenario        | Description                      | Data Preserved               | Data Archived/Removed                      |
| ------------------- | -------------------------------- | ---------------------------- | ----------------------------------------- |
| **3A: Goal Change** | Same athlete, new goal           | Profile, activities, metrics | Current plan archived                      |
| **3B: Soft Reset**  | Same athlete, new training block | Profile, memories, activities, metrics | Plan archived |
| **3C: Hard Reset**  | New athlete or clean slate       | Nothing                      | Everything removed                         |

### 4.2 Sub-Scenario 3A: Goal Change

**Trigger:** User says "Change my goal to 10K in April" or similar

**Flow:**

```
M1 (parse intent) → M4 (update goal) → M10 (archive old plan, generate new)
→ M3 (write) → M12 (present new plan)
```

**Process:**

1. **Archive current plan:**

   - Move to `plans/archive/plan_<old_goal>_<timestamp>.yaml`
   - Keep workout files for reference

2. **Update profile:**

   - Set new goal type, target date
   - Preserve all other profile data

3. **Generate new plan:**

   - Use existing CTL/ATL/TSB (fitness doesn't reset)
   - Calculate new periodization for new goal
   - If goal date < 4 weeks → warn about insufficient prep time

4. **Handle partial week:**
   - Mon-Wed goal change: Update remaining days of current week
   - Thu-Sun goal change: Complete current week, start new plan Monday

**Response:**

```
Goal changed: Half Marathon (March 15) → 10K (April 20)

I've archived your previous plan and created a fresh one.
- Your fitness (CTL 44) carries forward
- New plan: 8 weeks, building to peak at 10K goal pace
- This week: Continue as easy week while I finalize the new structure

Week 1 starts Monday. Want to see the overview?
```

### 4.3 Sub-Scenario 3B: Soft Reset

**Trigger:** User says "Start a new training block" or "Reset my plan"

**Flow:**

```
M1 (parse intent) → M3 (archive plan) → M4 (keep profile)
→ M10 (generate fresh plan) → M12 (present)
```

**What happens:**

- Profile and memories preserved (same athlete)
- Activities and metrics preserved
- Current plan archived to `plans/archive/`
- New plan generated using recent history (favoring latest weeks)

**Use case:** Athlete returning after long break, wants fresh baseline

### 4.4 Sub-Scenario 3C: Hard Reset

**Trigger:** User says "Start completely fresh" or "New athlete"

**Flow:**

```
M1 (parse intent) → M12 (confirm with warning) → M3 (delete everything)
→ Return to Scenario 1
```

**What happens:**

- ALL data deleted (no backup)
- System returns to new user state
- User goes through Scenario 1 again

**Confirmation required:**

```
This will delete ALL your data and start fresh:
- Training history: 47 activities over 10 weeks
- Current plan: Week 3 of 14-week HM plan
- Memories: 5 stored insights

Your data will be removed with no backup.

Type "confirm reset" to proceed, or anything else to cancel.
```

### 4.5 Module Mapping Summary

| Sub-Scenario    | Primary Modules | Supporting Modules |
| --------------- | --------------- | ------------------ |
| 3A: Goal Change | M4, M10         | M3, M12            |
| 3B: Soft Reset  | M3, M10         | M4, M12            |
| 3C: Hard Reset  | M3              | M12                |

---

## 5. Technical Gaps & Recommendations

### 5.1 Gaps Requiring Resolution Before Implementation

**Note:** The "M1 intent parsing" gap identified in earlier drafts has been **resolved** by the "Claude Code as Interface" architecture. Claude Code (the AI) handles all natural language understanding and intent recognition. The package provides callable Python functions—no keyword matching or intent parsing logic is needed.

| Gap                                    | Severity | Module(s) | Description                                                                                              |
| -------------------------------------- | -------- | --------- | -------------------------------------------------------------------------------------------------------- |
| **Pending suggestions data structure** | BLOCKING | M11       | New concept not in tech spec. Need: schema for suggestions queue, status transitions                     |
| **Onboarding dialogue flow**           | HIGH     | M1        | Sequence of questions undefined. Need: state machine for onboarding                                      |
| **Memory deduplication**               | HIGH     | M13       | "Semantic similarity" undefined. Need: concrete matching algorithm                                       |
| **Weekly refinement trigger**          | HIGH     | M10       | When/how does Tier 2 refinement happen? Need: explicit trigger and flow                                  |
| **Conflict policy + safety override**  | MEDIUM   | M11       | Which takes precedence? Need: priority matrix                                                            |
| **Lock file retry logic**              | MEDIUM   | M3        | Risk of deadlock. Need: timeout and retry strategy                                                       |
| **Injury flag duration**               | MEDIUM   | M11       | How long does override persist? Need: expiration rules                                                   |

### 5.2 Proposed Solutions

#### M1 Intent Parsing (RESOLVED)

**Status:** ✅ Resolved by Claude Code architecture.

Claude Code (the AI) handles all intent understanding through natural language processing. No keyword matching or pattern rules are needed in the package.

**How it works:**

1. User speaks naturally: "sync my Strava", "update activities", or "pull new workouts"
2. Claude Code understands the intent (no keyword matching required)
3. Claude Code calls the appropriate API function: `api.sync.sync_strava()`
4. Package returns structured data: `SyncResult` with enriched metrics
5. Claude Code formats conversational response based on context

**API Functions for Common Intents:**

| User Intent      | Claude Code Calls                    | Returns                   |
| ---------------- | ------------------------------------ | ------------------------- |
| Sync activities  | `api.sync.sync_strava()`             | `SyncResult`              |
| Show week status | `api.coach.get_weekly_status()`      | `WeeklyStatus`            |
| Get today's plan | `api.coach.get_todays_workout()`     | `WorkoutRecommendation`   |
| Check metrics    | `api.metrics.get_current_metrics()`  | `EnrichedMetrics`         |
| View plan        | `api.plan.get_current_plan()`        | `TrainingPlan`            |
| Accept change    | `api.plan.accept_suggestion(id)`     | `AcceptResult`            |
| Change goal      | `api.profile.set_goal(...)`          | `Goal`                    |

All functions are documented in `CLAUDE.md` for Claude Code's reference.

#### Pending Suggestions Schema

```yaml
# plans/pending_suggestions.yaml
pending_suggestions:
  - id: "sugg_2024-01-15_001"
    created_at: "2024-01-15T18:30:00Z"
    trigger: "acwr_elevated"
    trigger_value: 1.42
    affected_workout:
      file: "week_03/tuesday_tempo.yaml"
      date: "2024-01-16"
    suggestion_type: "downgrade" # downgrade | skip | move | substitute
    original:
      type: "tempo"
      duration_minutes: 50
      intensity: "threshold"
    proposed:
      type: "easy"
      duration_minutes: 45
      intensity: "easy"
    rationale: "ACWR at 1.42 (caution zone). Reducing intensity protects against injury risk."
    status: "pending" # pending | accepted | declined | expired
    expires_at: "2024-01-16T23:59:59Z"
    user_response: null # filled when user responds
    response_at: null
```

#### Weekly Refinement Trigger

Add to M10 specification:

```
refine_next_week(current_week_summary, master_plan, current_metrics):
  1. Get next week's structure from master_plan
  2. Evaluate adjustments based on:
     - current_week_summary.execution_rate
     - current_metrics.ctl_delta
     - current_metrics.acwr
     - current_metrics.readiness
  3. Apply refinement rules:
     - If execution_rate < 80%: reduce next week volume by 10%
     - If ctl_delta > 3: can increase intensity slightly
     - If acwr > 1.3: cap intensity at moderate
  4. Return refined workouts with change annotations
```

### 5.3 New Module Extensions Needed

#### M11 Extension: Suggestion Generation

```
generate_adaptation_suggestions(metrics, plan, activities):
  suggestions = []

  # Check each trigger
  if metrics.acwr > 1.3:
    suggestions.append(create_suggestion("acwr_elevated", ...))

  if metrics.readiness < 50:
    suggestions.append(create_suggestion("low_readiness", ...))

  # ... other triggers

  return suggestions

apply_suggestion(suggestion_id):
  suggestion = load_suggestion(suggestion_id)
  workout = load_workout(suggestion.affected_workout)
  workout.apply_changes(suggestion.proposed)
  save_workout(workout)
  suggestion.status = "accepted"
  suggestion.response_at = now()
  save_suggestion(suggestion)
```

#### M12 Extension: Suggestion Rendering

```
render_sync_response(sync_result, suggestions):
  output = format_sync_summary(sync_result)

  if suggestions:
    output += "\n\n**Suggestions:**\n"
    for s in suggestions:
      output += format_suggestion(s)
      output += "\nAccept? (y/n) or 'explain' for more detail\n"

  return output
```

---

## 6. Appendix: Dialogue Templates

### 6.1 Onboarding Dialogue

```markdown
**Coach:** Welcome! I'm your AI running coach. Let's get you set up.

**Coach:** First, let's connect your Strava account to import your training history.
[Strava OAuth flow]

**Coach:** Found 47 activities over the past 10 weeks. Let me analyze your training...

**Coach:** Based on your Strava data:

- Current fitness (CTL): 42
- Average weekly volume: 32 km over 4 runs
- Recent 10K: 48:32 → Easy pace: 5:50-6:10/km

**Coach:** Now I need a few things Strava can't tell me.

**Coach:** What's your running goal? For example:

- "Half marathon on March 15"
- "Sub-50 10K this spring"
- "General fitness, no specific race"

**User:** Half marathon on March 15

**Coach:** How many days per week can you realistically run?

**User:** 4

**Coach:** I see you also do cycling and climbing. When running and another sport conflict, what's your priority?

1. Running takes priority (I'll adjust other sports)
2. Other sport takes priority (adjust running)
3. Ask me each time

**User:** 3 - Ask me each time

**Coach:** Any current injuries or recurring issues I should know about?

**User:** Occasional knee pain after long runs

**Coach:** Got it—I'll monitor that and adjust if needed.

**Coach:** Creating your 14-week plan...

**Coach:** Here's your path to March 15:

- Weeks 1-4: Base building (maintaining ~32km/week)
- Weeks 5-10: Build phase (progressing to 45km/week)
- Weeks 11-13: Peak (maintaining fitness, race-specific work)
- Week 14: Taper (rest up for race day)

This week's schedule:
[Shows Mon-Sun grid]

Sync your Strava 2-3x per week. Say "show my week" anytime to check your status.

Let's crush this!
```

### 6.2 Weekly Check-in Patterns

```markdown
**User:** Show me my week

**Coach:** Week 5 of 14 (Build Phase)

Mon: Rest ✓
Tue: Tempo 45min @ 5:10/km → Done (47min @ 5:08, strong!)
Wed: Easy 35min → Done (38min)
Thu: Easy 30min → TODAY (scheduled)
Fri: Rest
Sat: Long run 16km → Scheduled
Sun: Rest

Progress: 3/5 complete
Form: TSB -6 (productive training zone)
ACWR: 1.15 (safe)

Looking good! Thursday easy run, then build toward Saturday's long run.
```

### 6.3 Plan Adjustment Dialogue

```markdown
**User:** I need to skip Thursday, have a work dinner

**Coach:** No problem. Here are your options:

1. **Skip Thursday easy** - You've already hit 3 runs this week. Missing one easy run won't affect your fitness.

2. **Move to Friday** - Swap rest day to Thursday, run Friday morning.

3. **Add 10min to Saturday's long run** - Compensate slightly on the long run.

My recommendation: Option 1. You're on track, and consistency matters more than any single easy run.

Which works for you?

**User:** Option 1

**Coach:** Done. Thursday is now rest. Enjoy your dinner!

Updated week:
Thu: Rest (moved from easy)
Sat: Long run 16km (unchanged)
```

### 6.4 Next Week Generation Dialogue

```markdown
**User:** [Sunday sync completes]

**Coach:** Week 5 complete! Here's your summary:

Execution: 4/5 workouts (Thursday skipped - work dinner)
Volume: 38km (planned: 40km) - 95%
Intensity: 78% easy, 22% moderate - on target

Highlights:

- Tuesday tempo was your best this cycle (5:08/km avg)
- Long run executed well, pacing disciplined

Metrics:

- CTL: 46 (+3 this week)
- TSB: -4 (fresh for next week)
- ACWR: 1.18 (safe)

**Coach:** Ready for Week 6?

Based on your progress, here's the plan:

**Week 6 Focus: Build (introducing intervals)**

Mon: Rest
Tue: Intervals 5x1000m @ 4:35/km (I-pace)
Wed: Easy 40min
Thu: Easy 30min
Fri: Rest
Sat: Long run 18km (adding 2km)
Sun: Rest

Volume: 45km (+5km progression)

The interval session is new—I'll explain the workout when you're ready for it.

Confirm this plan, or let me know if you need adjustments.
```

### 6.5 Reset Confirmation Dialogue

```markdown
**User:** I want to start completely fresh

**Coach:** I understand. Just to be clear, there are two options:

1. **Soft reset** - Archive your plan, delete activities/metrics, and keep your profile. Good if you're the same athlete starting a new training block.

2. **Hard reset** - Delete EVERYTHING and start as a new user. Good if you're a different person or want a completely clean slate.

Which would you prefer?

**User:** Hard reset

**Coach:** This will delete ALL your data with no backup:

- Training history: 47 activities over 10 weeks
- Current plan: Week 5 of 14-week HM plan
- Memories: 5 stored insights

Your data will be removed permanently.

Type "confirm reset" to proceed, or anything else to cancel.

**User:** confirm reset

**Coach:** Done. All data deleted.

Welcome! I'm your AI running coach. Let's get you set up...
[Returns to Scenario 1]
```

---

## 7. Document History

| Version | Date       | Author        | Changes               |
| ------- | ---------- | ------------- | --------------------- |
| 1.0     | 2024-01-15 | AI Coach Team | Initial specification |

---

_This document bridges the PRD and Technical Spec by specifying when and in what sequence the system behaviors occur. Implementation should follow this document for user-facing flows._
