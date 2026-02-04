# Adaptive Running Coach for Multi-Sport Athletes

## v0 Product Requirements Document (Simplified)

**Version:** 0.3.0  
**Last Updated:** March 2026  
**Status:** Draft for Implementation

---

## Executive Summary

This document defines a lean v0 for an AI-powered adaptive running coach. The product runs entirely within **Claude Code terminal**—no web interface, no database server. All data is stored in **local files** within the repository.

**v0 Core Promise:** Generate a personalized running plan based on user-defined constraints (available days, other sports, priorities) and continuously adapt it in response to actual training load across all tracked activities.

**Interaction Model:** User chats with Claude Code in terminal. Claude reads/writes local files (YAML, JSON, Markdown) to persist state, plans, and history.

---

## Core Design Principles

### 1. Minimize User Effort (Adoption-First Design)

**Principle:** User effort is inversely proportional to product adoption. Every required input is a friction point that increases abandonment risk.

**Application in v0:**

- **Automatic data ingestion:** Strava sync pulls activities automatically; no manual logging required for synced activities
- **Extraction over forms:** Wellness data extracted opportunistically from activity notes; no mandatory daily check-ins
- **Natural conversation:** No structured commands or rigid workflows; conversational interface adapts to user intent
- **Smart defaults:** Profile setup infers values from race PRs and existing training patterns when possible
- **Fail gracefully:** Missing data triggers conservative defaults, not errors or blockers

**What we explicitly avoid:**

- Daily wellness forms or morning check-ins (unrealistic expectation)
- Manual RPE entry when we can estimate from HR/text/Strava data
- Requiring complete profile data before generating first plan
- Forcing users to categorize every activity type manually

**Rationale:** Users are busy multi-sport athletes. While they may interact frequently (syncing Strava, checking today's workout), we cannot expect daily structured data entry. The product must fit seamlessly into their existing routines, not demand new ones.

### 2. Transparent Adaptability

All plan changes show clear reasoning linked to actual metrics. Users should understand _why_ the system recommends something, not just _what_ to do.

### 3. Multi-Sport Respect

Never suggest abandoning other sports. Work within the athlete's full training context and priorities.

### 4. Plan Stability (Suggest, Don't Auto-Modify)

**Principle:** The training plan is a stable reference that changes only with user consent.

**Application in v0:**

- Adaptation engine generates **suggestions**, not automatic changes
- User sees: "Based on your training load, I suggest [X]. Would you like to apply this?"
- User can accept, decline, or ask for alternatives
- Declined suggestions are logged but plan remains unchanged

**Why this matters:**

- Avoids "plan churn" (confusing constant changes that erode trust)
- Respects athlete autonomy (they decide, not the algorithm)
- Mirrors real coaching: coach suggests, athlete decides

**Safety exceptions (auto-apply with notification):**

- Injury flag detected → auto-rest with notification
- ACWR > 1.5 + readiness < 35 → auto-downgrade with warning
- Illness symptoms → forced rest (cannot override)

---

## Definition of Done (v0 Acceptance)

- **Profile & constraints captured:** Athlete profile file exists with goal, run-day availability, conflict policy, and at least one recent race or pace proxy.
- **Activity ingestion works:** Either (a) Strava sync pulls ≥1 activity into `activities/YYYY-MM/*.yaml` without duplication, or (b) user can log a manual activity that passes schema validation.
- **Metrics compute end-to-end:** CTL/ATL/TSB, ACWR, readiness, and weekly intensity distribution are written to `metrics/` after ingesting activities.
- **Plan generation respects constraints:** Running plan is created that matches run-day availability, caps long-run/time limits, and honors the conflict policy.
- **Adaptation triggers fire:** When ACWR/readiness/injury flags breach thresholds, at least one scheduled workout is automatically moved/downgraded with a logged reason.
- **Conversation loop usable:** “What should I do today?” returns a concrete workout or rest recommendation that references the athlete’s current metrics and context.
- **Local-only safety:** No secrets are committed; the app runs offline except for intentional Strava calls.

## Architecture Overview

### No Web UI, No Database

Everything happens through:

1. **Terminal conversation** with Claude Code
2. **Local files** in the repository for persistence
3. **Strava API calls** triggered manually by user request

### Explicitly Out of Scope (v0)

- Background daemons, push notifications, or any UI beyond the terminal conversation.
- Real-time re-planning on every message; adaptations happen after ingesting activities or on explicit request.
- Complex physiology modeling (HRV-based readiness, terrain-aware pacing, heat/altitude models beyond RPE/HR guidance).
- Multi-athlete handling in one repo; v0 assumes a single athlete context.
- Rich dashboards; outputs are YAML/Markdown plus textual summaries in the terminal.

### Cold Start / New User Handling

When an athlete first connects with no training history:

1. **Initial Plan Generation (Zero History)**

   - Generate plan assuming CTL = 0, ATL = 0, TSB = 0
   - Use conservative defaults: lower volume, no high-intensity sessions in first week
   - Set `baseline_established: false` in `athlete/training_history.yaml`

   **Cold Start Calibration (v0):**

   v0 requires Strava connection, so we calibrate to actual training data when available:

   ```
   If Strava history exists (≥14 days):
   - Weekly volume: matches recent 4-week average from Strava
   - First 1-2 weeks: emphasize easy runs, limit quality sessions
   - "Conservative" = don't ADD stress, not slash existing workload
   - Progression: 5-10% increase per week as baseline establishes

   If Strava history is minimal (<14 days):
   - CTL = 0, ATL = 0, TSB = 0
   - Weekly volume: 80% of user-reported current_weekly_run_km
   - First week: 100% easy runs, no quality sessions
   - Long run cap: 60 minutes until more data available
   ```

   **Key principle:** An athlete averaging 30km/week in Strava should get a plan starting
   at ~28-32km/week, NOT an arbitrary reduction like 15km. "Conservative" means avoiding
   sudden load increases, not underestimating their current capacity.

2. **Baseline Calibration (After 14+ Days)**

   - Once 14+ days of activity data exist, recompute CTL/ATL/TSB with actual history
   - Set `baseline_established: true`
   - Notify user: "I now have enough training data to calibrate your plan more accurately."

3. **ACWR Safeguard**

   - If 28-day average systemic load = 0: ACWR is undefined (do not divide by zero)
   - Skip ACWR-based adaptations until at least 28 days of data exist
   - Rely on readiness score and conservative defaults during this period

   **ACWR Display (when < 28 days data):**

   ```
   Show: "ACWR: -- (insufficient history)"
   Explanation: "I need 4 weeks of training data to calculate your injury risk ratio.
                 Until then, I'm using conservative defaults."

   In readiness calculation: Skip ACWR contribution; redistribute weight to TSB (30%) and trend (35%).
   ```

### File Structure

```
running-coach/
├── config/
│   ├── settings.yaml              # App settings (non-secret), paths, defaults
│   └── secrets.local.yaml         # Strava tokens/credentials (DO NOT COMMIT)
│
├── athlete/
│   ├── profile.yaml               # Athlete info, constraints, goals
│   ├── training_history.yaml      # Historical summary stats
│   └── memories.yaml              # AI-extracted facts from interactions
│
├── activities/
│   ├── 2025-11/                   # Organized by month
│   │   ├── 2025-11-05_run_lunch.yaml
│   │   ├── 2025-11-11_climb_evening.yaml
│   │   └── ...
│   └── 2025-12/
│       └── ...
│
├── metrics/
│   ├── daily/
│   │   ├── 2025-11-05.yaml        # Daily CTL/ATL/TSB/readiness
│   │   └── ...
│   └── weekly_summary.yaml        # Rolling weekly summaries
│
├── plans/
│   ├── current_plan.yaml          # Active training plan
│   ├── archive/                   # Previous plan versions
│   │   └── plan_2025-11-01_v1.yaml
│   └── workouts/
│       ├── week_01/
│       │   ├── mon_easy.yaml
│       │   ├── wed_tempo.yaml
│       │   └── sat_long.yaml
│       └── week_02/
│           └── ...
│
└── README.md                      # Usage instructions
```

---

## User Interaction Flow

### How User Interacts

User opens Claude Code in their terminal and has natural conversations:

```
User: "Hey, I just finished a run. Can you sync my latest Strava activities?"

Claude: [Calls Strava API, saves activities to files]
        "Synced 3 new activities since Monday, January 6th:

        Running:
        - Tue Jan 7: Easy Run (45min)
          → Systemic: 270 AU | Lower-body: 270 AU

        Other sports:
        - Wed Jan 8: Bouldering (2h30) — solid session, upper-body focus
          → Systemic: 630 AU | Lower-body: 105 AU
        - Mon Jan 6: Cycling (1h15) — easy spin
          → Systemic: 318 AU | Lower-body: 111 AU

        Week load so far: 1,218 AU systemic | 486 AU lower-body

        Current status:
        - Fitness (CTL): 44 (+2 this week) — solid recreational level
        - Form (TSB): -8 (productive training zone)
        - ACWR: 1.10 (safe)
        - Lower-body: Moderate (climbing was upper-body dominant)

        Tomorrow's tempo run looks good to go. Your legs should be fresh
        since Wednesday's climbing was mostly upper-body work."

User: "Actually I'm feeling a bit tired from climbing. Can we swap
       tomorrow's tempo for an easy run?"

Claude: [Updates workout file, recalculates week]
        "Done. I've moved the tempo run to Friday (swap with rest day) and
        tomorrow is now an easy 30-minute recovery run. Updated the plan."
```

### Key Commands User Can Request

| Request                            | What Claude Does                                                 |
| ---------------------------------- | ---------------------------------------------------------------- |
| "Sync my Strava"                   | Calls API, saves new activities, generates suggestions if needed |
| "Show me my week"                  | Shows current week status vs plan (completed, upcoming, skipped) |
| "How's my training load?"          | Calculates CTL/ATL/TSB, explains status                          |
| "Plan next week"                   | Refines next week based on current metrics                       |
| "I need to skip tomorrow's run"    | Updates workout status, adjusts plan                             |
| "I'm feeling tired"                | Generates suggestion to adjust upcoming workouts                 |
| "Change my goal to a 10K in March" | Updates profile, regenerates full plan                           |
| "Reset my plan"                    | Initiates soft reset (new training block)                        |
| "Start completely fresh"           | Initiates hard reset (archives all data)                         |

Freshness guard: if metrics/plan cache are older than 24 hours or missing, Claude re-runs metric aggregation before answering plan-related questions.

### Plan Structure: Master Plan + Weekly Refinement

**Master Plan (created at setup):**

- Full training arc from start to goal date
- Shows all phases: base → build → peak → taper
- Gives athlete visibility into the entire journey
- Generated once at onboarding or on goal change

**Weekly Refinement (at week boundary):**

- At Sunday sync or explicit "plan next week" request
- Coach analyzes the completed week: what was done? how did it feel?
- Refines next week's specific details based on current fitness
- Structure stays consistent with master plan; details adapt

**User experience:**

```
Sunday sync:
→ "Good week! You completed 4 of 5 sessions. CTL up 2 points."
→ "Ready to plan next week? I'll adjust based on how things went."

User: "Yes, plan next week"

→ "Here's your refined week 5:
   - Monday: Rest
   - Tuesday: Easy 40min (pace adjusted slightly up)
   - Wednesday: Tempo 35min (kept same intensity, you handled it well)
   - Friday: Easy 35min
   - Sunday: Long run 80min (increased 10min from last week)"
```

---

## Data Specifications

### Athlete Profile (`athlete/profile.yaml`)

```yaml
# Athlete Profile
name: "Du Phan"
email: "du@example.com"
created_at: "2025-11-01"
age: 32 # Optional; used for recovery guidance

# Strava Connection
strava:
  athlete_id: "12345678"
  # Tokens live in `config/secrets.local.yaml` (or env vars). Keep them out of VCS.

# Running Background
running_experience_years: 5
injury_history: "Hip flexor tightness, especially left side. Flares up with high intensity."

# Recent Fitness Snapshot (used for pacing)
recent_race:
  distance: "10k"
  time: "47:00"
  date: "2025-04-20"
current_weekly_run_km: 28
current_run_days_per_week: 3

# Personal Records (from Strava or self-reported)
personal_records:
  five_k:
    time: "22:30"
    date: "2025-06-15"
    source: "strava" # or "self_reported"
  ten_k:
    time: "47:00"
    date: "2025-04-20"
    source: "self_reported"
  half_marathon:
    time: "1:48:00"
    date: "2024-10-15"
    source: "strava"

# Vital Signs (optional but recommended)
vital_signs:
  max_hr: 185 # From test or 220-age estimate
  resting_hr: 52 # Baseline resting HR (self-reported or from wearable)
  resting_hr_updated_at: "2025-11-10"
  lthr: 172 # Lactate threshold HR
  lthr_method: "race_derived" # field_test | race_derived | estimated
  lthr_updated_at: "2025-06-15"

# Estimated VDOT (calculated from PRs)
estimated_vdot: 45
vdot_last_updated: "2025-06-15"

# Derived Training Paces (computed from VDOT, cached for reference)
derived_paces:
  vdot: 45
  calculated_from: "10k PR 47:00"
  calculated_at: "2025-06-15"
  easy_pace_min_km: "5:45-6:15"
  marathon_pace_min_km: "5:10-5:20"
  threshold_pace_min_km: "4:50-5:00"
  interval_pace_min_km: "4:25-4:35"
  repetition_pace_min_km: "4:05-4:15"

# Training Constraints
constraints:
  available_run_days: [tuesday, wednesday, saturday, sunday] # Days user CAN run
  preferred_run_days: [tuesday, saturday] # Ideal days if flexible
  min_run_days_per_week: 2
  max_run_days_per_week: 4
  max_time_per_session_minutes: 75
  time_preference: "morning" # morning, evening, flexible

# Other Sport Commitments
other_sports:
  - sport: "bouldering"
    days: [monday, thursday]
    typical_duration_minutes: 120
    typical_intensity: "moderate_to_hard" # easy, moderate, hard, moderate_to_hard
    is_flexible: false # Fixed commitment - won't move these
    notes: "Indoor gym, Arkose Montmartre"

  - sport: "cycling"
    days: [sunday]
    typical_duration_minutes: 90
    typical_intensity: "easy_to_moderate"
    is_flexible: true # Can reschedule based on weather
    notes: "Weather dependent, outdoor"

# Priority Setting
running_priority: "secondary" # primary, secondary, equal
primary_sport: "bouldering"

# Conflict Resolution Policy (User-Defined)
# When running and primary sport collide (time, soreness, schedule), what wins?
conflict_policy: "ask_each_time" # primary_sport_wins, running_goal_wins, ask_each_time

# Current Goal
goal:
  type: "half_marathon" # 5k, 10k, half_marathon, marathon, general_fitness
  race_name: "Paris Half Marathon"
  target_date: "2026-03-01"
  target_time: "1:45:00" # Optional
  effort_level: "pr_attempt" # pr_attempt, comfortable, just_finish

# Communication Preferences
preferences:
  detail_level: "moderate" # brief, moderate, detailed
  coaching_style: "supportive" # supportive, direct, analytical
  intensity_metric: "pace" # pace, hr, rpe
```

### Activity File (`activities/2025-11/2025-11-05_run_lunch.yaml`)

```yaml
# Activity: Lunch Run
id: "strava_12345678"
source: "strava"
sport_type: "running"
sub_type: "intervals" # easy, tempo, intervals, long, race
surface_type: "road" # road | track | trail | grass | treadmill | mixed (optional)
surface_type_confidence: "high" # high | low (low = auto-detected from GPS absence)

# Data Quality (for treadmill/indoor runs where pace/distance may be unreliable)
data_quality:
  pace_confidence: "high" # high | medium | low
  distance_confidence: "high" # high | medium | low
  pace_source: "gps" # gps | accelerometer | manual | unknown
  quality_notes: null # Optional explanation (e.g., "Treadmill - pace may vary 5-15%")

# Basic Info
name: "Lunch Run"
date: "2025-11-05"
start_time: "12:39"
location: "Paris"

# Metrics
duration_minutes: 52
distance_km: 10.2
elevation_gain_m: 45
average_pace_min_km: "5:05"

# Heart Rate (if available - Strava returns floats)
average_hr: 158.1
max_hr: 175.5
has_hr_data: true

# Strava Metrics
strava_relative_effort: 89 # suffer_score
strava_perceived_exertion: null # 1-10 if user set it

# User Feedback (from Strava description/private_note)
description: "6 x 1000m @10k pace 75s rest"
private_note: |
  My 10 pace is around 4:55-5:00 min/km.
  In the first lap (the first 1000m), the gps was not working so I feel like I was 
  running much faster than the goal pace.
  Not an easy session evidently but manageable, not very hard. At the end I felt 
  some tension and slight tightness in the front of my hip, right where the thigh 
  connects to the pelvis — around the hip flexor area, especially in the left side.
  It's more noticeable when I lift my leg or stretch the front of the hip. I notice 
  that yesterday and this morning too (but with less intensity) so it is not 100% 
  because of the running but it can be attribute to my bouldering stretching/training too.
  Overall, ok session, especially after the drinks last night (750ml of beer). I went 
  to bed a bit late (I got home at around 11pm but then geeked around a bit and slept 
  around 1:00 am) and woke up at 9am, feeling ok but the garmin watch gave a quite 
  bad sleep score.

# Calculated Training Load
calculated:
  estimated_rpe: 7 # Derived from relative_effort, HR, or user feedback
  base_effort_au: 364 # RPE × duration_minutes

  # v0 uses a simple 2-channel load model:
  # - systemic_load_au: drives aerobic fatigue/fitness (CTL/ATL/TSB)
  # - lower_body_load_au: drives run-compatibility (leg soreness/impact)
  systemic_multiplier: 1.0
  lower_body_multiplier: 1.0
  systemic_load_au: 364
  lower_body_load_au: 364
  session_type: "quality" # easy, moderate, quality, race

# AI Analysis (filled after processing)
ai_analysis:
  key_observations:
    - "Hip flexor tightness noted - consistent with profile injury history"
    - "Sleep was suboptimal (late night, ~8h but poor quality)"
    - "Session executed well despite suboptimal conditions"
  wellness_indicators:
    sleep_quality: 2 # 1-5, extracted from notes
    energy: 3
    soreness: 3 # Hip flexor mentioned
  recommendations:
    - "Monitor hip flexor before next quality session"
    - "Consider hip mobility work before Thursday climb"

# Link to Planned Workout (bidirectional reference)
planned_workout_ref:
  workout_id: "w02_tue_intervals" # Links to plans/workouts/week_02/tue_intervals.yaml
  plan_id: "plan_2025-11-01_v2"
  compliance: "executed" # executed | modified | skipped
```

### Activity File - Non-Running (`activities/2025-11/2025-11-11_climb_evening.yaml`)

```yaml
# Activity: Evening Rock Climb
id: "strava_12345679"
source: "strava"
sport_type: "climbing"
sub_type: "bouldering"

name: "Evening Rock Climb"
date: "2025-11-11"
start_time: "18:30"
location: "Arkose Montmartre"

duration_minutes: 150
has_hr_data: false

# Strava Metrics
strava_relative_effort: null # Often not available for climbing
strava_perceived_exertion: null

# User Feedback
description: |
  At home gym Arkose Montmartre.
  I flashed a black-level boulder (grade black 1/5): in slight overhang with some 
  powerful move. It is my style but objectively it is still a very easy, I'd rather 
  grade it red 3/5.
  Then I work on another black-level boulder (grade black 2/5): I spent at least 1h 
  on it to work on the crux, which, imo, is a bit morphological: it is harder for 
  shorter climber like me. I should be able to do it in the next sessions though.
  Finally I work on a red 4/5 traversal style: I did not succeed as I'm already 
  quite tired and this boulder is quite physical, especially for shorter climber (again).
  In general, I feel quite good, quite physical (and a bit longer than usual) session.

private_note: null

# Calculated Training Load
calculated:
  estimated_rpe: 7 # Derived from description analysis ("quite physical", "longer than usual")
  base_effort_au: 1050 # 7 × 150
  systemic_multiplier: 0.6 # Climbing = less systemic than running
  lower_body_multiplier: 0.1 # Mostly upper body; small leg carryover to running
  systemic_load_au: 630
  lower_body_load_au: 105
  session_type: "quality"

# AI Analysis
ai_analysis:
  key_observations:
    - "Physical session, longer than usual (2h30 vs typical 2h)"
    - "High effort on projecting (1h on single boulder)"
    - "Noted fatigue by end of session"
  intensity_assessment: "moderate_to_hard"
  recovery_impact: "local" # local (upper body) vs systemic
  estimated_recovery_hours: 48
```

### Daily Metrics (`metrics/daily/2025-11-11.yaml`)

```yaml
date: "2025-11-11"
calculated_at: "2025-11-11T22:00:00Z"

# Activities This Day
activities:
  - id: "strava_12345679"
    sport: "climbing"
    systemic_load_au: 630
    lower_body_load_au: 105

systemic_daily_load_au: 630
lower_body_daily_load_au: 105

# Cumulative Metrics
ctl: 42.5 # Chronic Training Load (fitness)
atl: 58.2 # Acute Training Load (fatigue)
tsb: -15.7 # Training Stress Balance (form)
acwr: 1.15 # Systemic ACWR (Acute:Chronic Workload Ratio)

# Interpretations
interpretations:
  ctl_trend: "building" # building, maintaining, declining
  tsb_status: "productive_training" # overreaching, productive_training, optimal, fresh, detrained
  acwr_status: "safe" # safe, caution, high_risk, undertraining

# Readiness Score (if wellness data available)
readiness:
  score: 62 # 0-100
  confidence: "medium" # low (no subjective data), medium, high
  components:
    tsb_contribution: 55
    sleep_contribution: 50 # From previous day's notes
    wellness_contribution: null # No explicit input
    trend_contribution: 68
  recommendation: "moderate_effort_ok" # rest, easy_only, moderate_effort_ok, full_send

# Wellness (extracted from activity notes or explicit input)
wellness:
  source: "extracted_from_activity" # explicit_input, extracted_from_activity, none
  sleep_hours: 8
  sleep_quality: 2 # 1-5, from Nov 5 run notes about sleep
  energy: 3
  soreness: 3
  mood: null
```

### Training Plan (`plans/current_plan.yaml`)

```yaml
# Training Plan
plan_id: "plan_2025-11-01_v2"
created_at: "2025-11-01"
last_modified: "2025-11-12"
version: 2
status: "active"

# Goal Reference
goal:
  type: "half_marathon"
  target_date: "2026-03-01"
  target_time: "1:45:00"

# Plan Structure
start_date: "2025-11-04" # Monday of first week
end_date: "2026-03-01"
total_weeks: 17

# Periodization
phases:
  - name: "base"
    weeks: [1, 2, 3, 4, 5, 6]
    focus: "Aerobic foundation, easy volume, establish consistency"
  - name: "build"
    weeks: [7, 8, 9, 10, 11, 12]
    focus: "Introduce intensity, tempo work, longer long runs"
  - name: "peak"
    weeks: [13, 14, 15]
    focus: "Race-specific work, peak long run, sharpen"
  - name: "taper"
    weeks: [16, 17]
    focus: "Reduce volume 40-60%, maintain intensity, stay fresh"

# Current Status
current_week: 2
current_phase: "base"

# Weekly Template (based on constraints)
weekly_template:
  tuesday: "quality" # tempo, intervals, or progression
  wednesday: null # Rest or optional easy (buffer after quality run)
  saturday: "long_run"
  sunday: null # Often cycling, or easy run if no cycling

# Target Progression
weekly_targets:
  week_1: { total_km: 25, long_run_km: 12, quality_sessions: 1 }
  week_2: { total_km: 28, long_run_km: 13, quality_sessions: 1 }
  week_3: { total_km: 30, long_run_km: 14, quality_sessions: 1 }
  # ... etc

# Adaptation Log (Enhanced for Auditability)
adaptations:
  - date: "2025-11-12"
    original: "Tuesday tempo run"
    adapted_to: "Thursday tempo run"
    reason: "High systemic load from recent climbing session; athlete requested extra recovery"
    triggered_by:
      metric: "lower_body_load_au"
      value: 420
      threshold: 270
      source_activity: "strava_12345679" # Link to activity that caused trigger
    conflict_policy_applied: "ask_each_time"
    user_choice: "move_workout" # If ask_each_time was used
    timestamp: "2025-11-12T08:30:00Z"

# Notes
coach_notes: |
  Du is balancing serious bouldering (Mon/Thu) with half marathon training.
  Key consideration: Tuesday quality run comes after Monday climbing - 
  monitor fatigue. Saturday long run should be primary running focus.
  Hip flexor is a watch item - reduce intensity if it flares.
```

### Individual Workout (`plans/workouts/week_02/tue_tempo.yaml`)

```yaml
# Workout: Tuesday Tempo
workout_id: "w02_tue_tempo"
plan_id: "plan_2025-11-01_v2"
week: 2
scheduled_date: "2025-11-12"

# Prescription
type: "tempo"
duration_minutes: 50
distance_km: 9
intensity: "moderate_hard"

structure:
  warmup:
    duration_minutes: 10
    distance_km: 1.5
    pace_guidance: "Easy, 5:45-6:00/km"
  main:
    type: "continuous_tempo"
    duration_minutes: 25
    distance_km: 5
    pace_guidance: "Tempo pace, 4:50-5:00/km (comfortably hard)"
    notes: "Should feel like you could hold this for an hour, but not easy"
  cooldown:
    duration_minutes: 10
    distance_km: 1.5
    pace_guidance: "Easy jog, 6:00+/km"
  optional_strides:
    count: 4
    duration_seconds: 20
    rest_seconds: 60

# Purpose & Context
purpose: |
  Tempo runs train your lactate threshold—the pace you can sustain for about 
  an hour. This directly translates to half marathon performance. At your 
  current fitness (VDOT ~45), tempo pace is around 4:50-5:00/km.

context: |
  Week 2 of base phase. This is your first tempo session of the block. 
  Yesterday was a rest day after Monday's climbing session, so legs should 
  be relatively fresh.

tips:
  - "Start conservative. First km of tempo should feel almost too easy."
  - "Monitor hip flexor—if tightness appears, drop pace by 10-15 sec/km."
  - "Given your climbing schedule, don't chase pace. Consistent effort matters more."

# Status & Execution
status: "scheduled" # scheduled, completed, skipped, adapted
adaptation_applied: null

# Execution (filled after completion)
execution:
  actual_activity_id: null
  actual_duration_minutes: null
  actual_distance_km: null
  average_hr: null
  average_pace_min_km: null
  session_rpe: null # Optional (1-10)
  pain_flag: "none" # Optional (none, monitor, stop)
  execution_notes: null # Athlete feedback

# Coach Review (short debrief)
coach_review: null
```

### Planned vs Actual (Coach Model)

v0 treats **planned** and **executed** as distinct layers:

- The plan/workout file preserves the original prescription.
- Execution fields are filled after the session, linked to the actual activity.
- Adaptations are logged rather than rewriting history, so coaches can review intent vs outcome.

### Coach Memories (`athlete/memories.yaml`)

```yaml
# AI-Extracted Facts About Athlete
# These persist across sessions to provide continuity

memories:
  - id: "mem_001"
    type: "injury_history"
    content: "Hip flexor tightness, especially left side. Flares up with high intensity running and bouldering stretching."
    source: "profile + activity notes 2025-11-05"
    created_at: "2025-11-05"
    confidence: "high"

  - id: "mem_002"
    type: "preference"
    content: "Prefers morning runs when possible"
    source: "profile"
    created_at: "2025-11-01"
    confidence: "high"

  - id: "mem_003"
    type: "context"
    content: "Bouldering is primary sport. Training at Arkose Montmartre. Working on black-level problems, projects red 4/5."
    source: "activity notes 2025-11-11"
    created_at: "2025-11-11"
    confidence: "high"

  - id: "mem_004"
    type: "insight"
    content: "Sleep quality affects perceived session difficulty. Has tendency to stay up late on weeknights."
    source: "activity notes 2025-11-05"
    created_at: "2025-11-05"
    confidence: "medium"

  - id: "mem_005"
    type: "training_response"
    content: "Handles interval work well even after suboptimal sleep. 6x1000m session was 'manageable, not very hard' despite beer and late night."
    source: "activity notes 2025-11-05"
    created_at: "2025-11-05"
    confidence: "medium"

# Superseded memories (kept for reference)
archived:
  - id: "mem_000"
    content: "Previous goal was 10K"
    superseded_by: "Current goal is half marathon"
    archived_at: "2025-11-01"
```

### Training History Summary (`athlete/training_history.yaml`)

```yaml
# Training History (lightweight v0 state)
last_strava_sync_at: "2025-11-12T08:30:00Z"
last_strava_activity_id: "strava_12345679"

# Baseline snapshot for context (optional)
baseline:
  ctl: 42.5
  atl: 58.2
  tsb: -15.7
  period_days: 84 # ~12 weeks of history
```

---

## Core Logic & Algorithms

### 0. Training Principles & Safety Guardrails (v0)

These guardrails are derived from Daniels, Pfitzinger, 80/20, and FIRST, and are
used by the plan generator and adaptation engine:

- Train at current fitness, not goal pace. Derive paces from a race in the last 4-6 weeks.
- Update VDOT no more than every 3-4 weeks, or after a new race.
- Consistency beats hero workouts. Prefer sustainable progress over spikes.
- Intensity distribution: if running >= 3 days/week, target ~80% low intensity and <= 20% moderate+high.
- If running <= 2 days/week: allow only 1 quality run; long run stays easy.
- Hard/easy separation: no back-to-back high-intensity sessions across all sports (see definition below).
- Avoid leg-heavy strength within 24-36 hours of a quality run.

#### Hard/Easy Separation (Concrete Definition)

**"Back-to-back" = within 24 hours (same or next calendar day)**

Rules:

- No high-intensity running the day after high-intensity anything (running or other sport)
- Minimum 1 easy/rest day between quality sessions
- "High-intensity" = session_type ∈ {quality, race} OR estimated_rpe ≥ 7

Cross-sport application:

- Monday hard climb + Tuesday hard run = VIOLATION → trigger adaptation
- Monday hard climb + Wednesday hard run = OK (1 day gap)

#### High-Intensity Session Definition

A session counts as "high-intensity" if ANY of:

- `session_type` = "quality" OR "race"
- `estimated_rpe` ≥ 7
- `sub_type` indicates intensity (intervals, tempo, race-pace, threshold)

**Scope: All sports, not just running.**

Weekly caps (all sports combined):

- ≤3 run days/week: max 2 high-intensity sessions per 7 days
- ≥4 run days/week AND running_priority = "primary": max 3 high-intensity sessions per 7 days

**High-Intensity Session Count Window:**

- Always use ROLLING 7-day window (not calendar week)
- Window: today minus 6 days through today (inclusive)
- Count includes ALL sports, not just running
- Example: If checking Wednesday Nov 13, count sessions from Nov 7-13 inclusive
- Long run caps: <= 25-30% of weekly run volume and <= 2.5 hours.

**Long Run Percentage Calculation:**

```
Base for percentage: RUNNING-ONLY weekly volume (not total activity)

Formula: long_run_km ≤ 0.30 × planned_weekly_run_km

Example:
- Planned weekly run km: 40 km
- Long run cap: 0.30 × 40 = 12 km
- Additional cap: ≤ 2.5 hours duration (whichever is reached first)

Cross-training (cycling, swimming) does NOT count toward the weekly run km base.
```

- T/I/R volume caps (Daniels-style):
  - T-pace total <= 10% of weekly mileage
  - I-pace total <= 8% of weekly mileage or 10 km (whichever is lower)
  - R-pace total <= 5% of weekly mileage or 8 km (whichever is lower)
- Use RPE/HR over pace in heat, hills, or altitude.
- If sick (below the chest), feverish, or pain alters gait: replace with rest or low-impact cross-training
  and flag for medical advice if persistent.

Note: T = threshold/tempo, I = interval/VO2max, R = repetition/speed.

### 1. Training Load Calculation

#### v0 Load Model (Simple, Multi-Sport Friendly)

v0 intentionally keeps the model simple, but avoids a common failure mode for multi-sport athletes:
one single load number can cause a hard strength/climbing day to “nuke” the running plan even when the
stress is mostly non-running-specific.

So v0 uses **two derived loads** per activity:

- **Systemic load** (`systemic_load_au`): “cardio + whole-body fatigue” → feeds CTL/ATL/TSB/ACWR.
- **Lower-body load** (`lower_body_load_au`): “leg strain + impact carryover” → gates quality/long runs.

**Base effort:** `base_effort_au = RPE × Duration (minutes)`

**Systemic load:** `systemic_load_au = base_effort_au × systemic_multiplier`

**Lower-body load:** `lower_body_load_au = base_effort_au × lower_body_multiplier`

Multipliers are simple defaults by sport (and optionally adjusted by sub_type / notes when obvious).

**RPE Estimation factors:**

1. Heart rate data (if available)
2. User's explicit perceived exertion (Strava field, if set)
3. Analysis of description/private_note for effort feedback and workout specs.
4. Strava's relative_effort (suffer_score), normalized
5. Sport type + duration heuristic

#### Default Multipliers (v0)

| Sport / Category         | systemic_multiplier | lower_body_multiplier | Notes                                          |
| ------------------------ | ------------------- | --------------------- | ---------------------------------------------- |
| Running                  | 1.00                | 1.00                  | Reference (outdoor road/track)                 |
| Running (treadmill)      | 1.00                | 0.90                  | Belt absorbs ~10% impact; pace data unreliable |
| Trail running            | 1.05                | 1.10                  | More eccentric/impact                          |
| Cycling                  | 0.85                | 0.35                  | Legs work but low impact; moderate carryover   |
| Swimming                 | 0.70                | 0.10                  | Little run-specific leg strain                 |
| Hiking                   | 0.60                | 0.50                  | Can be leggy on descents; moderate carryover   |
| Climbing / bouldering    | 0.60                | 0.10                  | Mostly upper-body / grip fatigue               |
| Strength / gym (general) | 0.55                | 0.40                  | Depends on lower-body emphasis                 |
| CrossFit / metcon        | 0.75                | 0.55                  | Variable; often leg+systemic                   |
| Yoga (vinyasa/flow)      | 0.35                | 0.10                  | Mostly recovery-supportive                     |
| Yoga (restorative / yin) | 0.00                | 0.00                  | Counts as recovery                             |
| Walking                  | 0.20                | 0.10                  | Minimal stress                                 |

**Workout-type adjustment (v0, minimal):**

- If strength/CrossFit notes mention clear lower-body emphasis (e.g., “squats”, “deadlifts”, “lunges”, “thrusters”, “wall balls”, “box jumps”), bump `lower_body_multiplier` by +0.20 (cap at 1.0).
- If notes mention upper-body emphasis (e.g., “bench”, “pull-ups”, “press”), reduce `lower_body_multiplier` by -0.15 (floor at 0.0).
- If unclear and it matters for tomorrow’s run, ask the user: “Was yesterday’s session leg-heavy?”

**Analyzing User Notes for RPE:**

Claude should parse description/private_note for intensity indicators:

| Indicators                                    | Estimated RPE |
| --------------------------------------------- | ------------- |
| "very easy", "recovery", "chill"              | 2-3           |
| "easy", "relaxed", "comfortable"              | 4-5           |
| "moderate", "steady", "ok session"            | 5-6           |
| "hard", "tough", "challenging", "tired after" | 7-8           |
| "very hard", "all out", "exhausted", "brutal" | 9-10          |
| "manageable but not easy"                     | 6-7           |
| "quite physical", "longer than usual"         | 7-8           |

Also look for:

- Sleep quality mentions → affects readiness
- Soreness/pain mentions → flag for injury tracking
- Fatigue mentions → factor into recovery estimates

**Treadmill/Indoor Run Detection:**

Strava does not distinguish treadmill runs from outdoor runs (both are `sport_type: "Run"`). The system must detect treadmill sessions to flag pace/distance data as unreliable.

**Tier 1 - Auto-classify (high confidence):**

Any of these signals → set `surface_type: "treadmill"` with `surface_type_confidence: "high"`:

| Signal Type          | Keywords/Indicators                                                                            |
| -------------------- | ---------------------------------------------------------------------------------------------- |
| Title keywords       | "treadmill", "indoor run", "dreadmill", "tm run", "hotel gym", "gym run"                       |
| Description keywords | "treadmill", "gym treadmill", "on the mill", "belt speed", "incline setting", "fitness center" |
| Device hints         | `sport_type: "virtual_run"` OR device metadata indicates indoor mode                           |

**Tier 2 - Auto-classify (low confidence):**

When BOTH conditions are true:

1. No GPS polyline (`map.summary_polyline` is null/empty)
2. No outdoor keywords in title/notes ("trail", "road", "track", "park", "outside", "route", "weather")

→ Set `surface_type: "treadmill"` with `surface_type_confidence: "low"`
→ Apply treadmill data quality flags (`pace_confidence: "low"`)
→ Coach acknowledges the classification in response; user can correct via conversation if wrong

**Data quality implications for treadmill:**

- Set `data_quality.pace_confidence: "low"` and `distance_confidence: "low"`
- Set `data_quality.pace_source: "accelerometer"`
- Prioritize HR over pace for RPE estimation (see RPE rules below)
- Exclude from VDOT recalculation and personal records

**Strava Relative Effort (suffer_score) Normalization:**

Strava's `suffer_score` is a 0-300+ scale (higher = harder). Normalize to RPE 1-10:

```
Basic normalization:
  rpe = 1 + (suffer_score / 25)
  rpe = min(rpe, 10)  # Cap at 10

Calibrated approach (after 20+ activities with suffer_score):
  Use athlete's personal distribution:
  - <25th percentile → RPE 2-4 (easy)
  - 25-75th percentile → RPE 5-7 (moderate)
  - >75th percentile → RPE 8-10 (hard)
```

**Notes:**

- Basic formula works for initial estimate
- Calibrated approach accounts for individual variability in HR response
- If suffer_score > 250, flag for review (unusually high)

**Intensity band classification (for 80/20 tracking):**

- low: easy/recovery sessions or RPE <= 4
- moderate: steady/tempo sessions or RPE 5-6
- high: interval/repetition/race sessions or RPE >= 7

This maps to `session_type` and is used to compute weekly intensity distribution.
High-intensity session count is tracked across all sports for recovery gating.

### 2. CTL/ATL/TSB Calculation

**Chronic Training Load (CTL)** - "Fitness"

- 42-day exponentially weighted moving average
- Higher = more fit, but takes time to build

**Acute Training Load (ATL)** - "Fatigue"

- 7-day exponentially weighted moving average
- Higher = more fatigued, changes quickly

**Training Stress Balance (TSB)** - "Form"

- TSB = CTL - ATL
- Negative = fatigued, positive = fresh

**Calculation:**

```
CTL_today = CTL_yesterday × 0.976 + systemic_daily_load × 0.024
ATL_today = ATL_yesterday × 0.867 + systemic_daily_load × 0.133
TSB = CTL - ATL
```

**TSB Interpretation:**

| TSB Range  | Status              | Guidance                 |
| ---------- | ------------------- | ------------------------ |
| Below -25  | Overreaching        | High fatigue—reduce load |
| -25 to -10 | Productive Training | Building fitness         |
| -10 to +5  | Optimal             | Ready for quality work   |
| +5 to +15  | Fresh               | Good for racing          |
| Above +15  | Possibly Detrained  | Consider increasing      |

### 3. ACWR (Acute:Chronic Workload Ratio)

**Formula:** `ACWR = (7-day total systemic load) / (28-day average systemic load)`

**Interpretation:**

| ACWR      | Status        | Action                        |
| --------- | ------------- | ----------------------------- |
| < 0.8     | Undertraining | Can increase load             |
| 0.8 - 1.3 | Safe Zone     | Continue as planned           |
| 1.3 - 1.5 | Caution       | Consider reducing intensity   |
| > 1.5     | High Risk     | Reduce load to prevent injury |

**Key Insight:** ACWR > 1.5 correlates with 2-4x increased injury risk in following 7 days.

### 4. Readiness Score

**Inputs & Weights:**

| Input               | Weight | Source                           |
| ------------------- | ------ | -------------------------------- |
| TSB (form)          | 20%    | Calculated                       |
| Recent load trend   | 25%    | 3-day vs 7-day comparison        |
| Sleep quality       | 25%    | Extracted from notes or explicit |
| Subjective wellness | 30%    | Extracted from notes or explicit |

**If subjective data missing:** Calculate from available data with "low confidence" flag.

**Score Interpretation:**

| Score  | Recommendation                      |
| ------ | ----------------------------------- |
| 80-100 | Full send—great day for hard effort |
| 65-79  | Execute as planned                  |
| 50-64  | Consider reducing intensity         |
| 35-49  | Easy effort only                    |
| < 35   | Rest recommended                    |

#### Readiness Confidence (v0 Simplified)

```
confidence = "high" if ≥14 days of activity history
confidence = "low" if <14 days of activity history
```

**When confidence = "low":**

- Add caveat to recommendation: "Based on limited data; consider how you feel today."
- Use conservative defaults (avoid high-intensity until baseline established)

**Note:** v0 does NOT compute detailed wellness scores. Readiness is primarily TSB-driven with safety overrides for explicit flags (injury, illness mentioned in notes).

#### Wellness Data Handling (v0)

v0 does NOT compute detailed wellness scores. Instead:

1. Extract obvious flags from recent activity notes (injury, illness, "bad sleep")
2. Apply safety overrides when flags present (see Safety Overrides table below)
3. Otherwise, rely on TSB-based readiness

**Rationale:** While users may interact frequently (daily syncs, workout queries), we cannot expect daily structured wellness input. Wellness extraction is opportunistic from activity notes, not mandatory daily forms.

#### Safety Overrides (Applied After Standard Calculation)

These overrides apply AFTER computing readiness from standard inputs (TSB, sleep, wellness, trend).
They ensure that safety-critical flags always result in rest/easy recommendations, regardless of computed score.

| Condition                                        | Override Action                  |
| ------------------------------------------------ | -------------------------------- |
| Illness flag (fever, chest congestion, "sick")   | readiness → 20 (force rest)      |
| Injury flag (sharp pain, gait-altering soreness) | readiness → 25 (force rest/easy) |
| ACWR > 1.5                                       | readiness -= 15 points           |

**Example:**

- Standard readiness computed as 68 ("execute as planned")
- Athlete notes mention "slight fever (99.5°F)"
- Override applied: readiness → 20
- Recommendation: "Rest is recommended today due to fever symptoms."

This prevents contradictory guidance like "Readiness 65, execute as planned" alongside "fever noted."

### 4.5 Metrics Accessibility Guidelines

Training metrics must be presented in ways athletes can intuitively understand. **Never show raw numbers without context.**

#### Presentation Principles

1. **Always include status labels:**

   - ❌ BAD: "CTL: 42"
   - ✅ GOOD: "Fitness (CTL): 42 — solid recreational level"

2. **Use relative language:**

   - ❌ BAD: "TSB: -12"
   - ✅ GOOD: "Form (TSB): -12 — you're in the productive training zone, building fitness"

3. **Show trends, not just snapshots:**

   - "Fitness up 3 points this week" not just "CTL: 45"
   - "ACWR trending toward caution zone" not just "ACWR: 1.28"

4. **Connect to decisions:**
   - "ACWR is 1.15 (safe), so today's tempo run is good to go"
   - "Lower-body load is elevated from climbing, so I'd recommend easy running today"

#### Metric Explainer Templates

| Metric    | What It Means                                      | Good/Caution/Bad                                                              |
| --------- | -------------------------------------------------- | ----------------------------------------------------------------------------- |
| CTL       | Your sustained training capacity (fitness level)   | Higher = more fit; 20-40 recreational, 40-60 serious amateur, 60+ competitive |
| ATL       | How much stress you've absorbed recently (fatigue) | Higher = more tired; context-dependent                                        |
| TSB       | How fresh you are (form = fitness minus fatigue)   | -25 to -10: building, -10 to +5: ready for quality, +5 to +15: race-ready     |
| ACWR      | Injury risk based on load spike                    | 0.8-1.3: safe, 1.3-1.5: caution, >1.5: high risk                              |
| VDOT      | Running efficiency score from race times           | Higher = faster; 40 ≈ 50min 10K, 50 ≈ 40min 10K                               |
| Readiness | Overall readiness score (0-100)                    | 80+: full send, 65-79: execute plan, 50-64: reduce intensity, <50: easy/rest  |

#### Multi-Metric Conflict Resolution

When metrics give conflicting signals, present them transparently with clear reasoning:

```
Your readiness is mixed today:
- ACWR: 1.42 (caution zone — recent load spike)
- TSB: -8 (optimal for quality work)
- Lower-body: Elevated from yesterday's climbing

My recommendation: Downgrade today's tempo to an easy run. The ACWR concern
outweighs the good TSB reading—injury prevention comes first.
```

**Resolution Priority:**

1. Safety flags (illness, injury) → always override all other metrics
2. ACWR > 1.5 → strong caution signal
3. Readiness < 50 → reduce intensity
4. TSB context-dependent (building vs maintaining vs fresh)

#### Progressive Disclosure Strategy

Don't overwhelm new athletes with all metrics at once:

**Week 1-2 (First 2 syncs):**

- Focus on weekly volume and easy/hard distribution
- "You completed 3 runs this week for 25km total—good start!"

**Week 3-4 (After 14+ days of data):**

- Introduce CTL/ATL/TSB
- "Your fitness (CTL) has increased from 35 to 38—you're building aerobic capacity!"

**Week 5+ (After 28+ days of data):**

- Add ACWR once 28-day baseline exists
- "Your ACWR is 1.18 (safe)—this tracks how quickly you're ramping up training"

This gradual approach prevents metric overload while building athlete literacy over time.

### 5. Plan Generation Logic

**Phase Distribution for Half Marathon:**

- Base (40%): Weeks 1-7 of 17
- Build (35%): Weeks 8-12
- Peak (15%): Weeks 13-15
- Taper (10%): Weeks 16-17

**Weekly Structure Based on Available Days:**

| Run Days | Distribution                          |
| -------- | ------------------------------------- |
| 1 day    | 1 Long Run (combine quality elements) |
| 2 days   | 1 Long + 1 Quality                    |
| 3 days   | 1 Long + 1 Quality + 1 Easy           |
| 4 days   | 1 Long + 1-2 Quality + 1-2 Easy       |
| 5+ days  | 1 Long + 2 Quality + 2-3 Easy         |

#### 2 Run Days/Week: Coaching Philosophy (v0)

When an athlete only runs **2 days/week**, the running plan cannot be “pure 80/20” inside running itself.
Instead, v0 prioritizes **specificity + durability**:

- **One long/aerobic run** per week (or every 7–10 days if schedule forces it).
- **One quality run** per week (or every 7–10 days), chosen based on the goal distance.
- Other sports provide most of the low-intensity aerobic volume; we keep the overall week sustainable by adapting around **systemic** and **lower-body** load.

This is broadly compatible with FIRST-style low-frequency running, but v0 adapts it to multi-sport reality
(leg-heavy strength and high-impact running are not treated as interchangeable).

#### Intensity Distribution & Quality Session Limits (v0)

- If running >= 3 days/week: target ~80% low intensity and <= 20% moderate+high within running time.
- Across all sports: cap high-intensity sessions at 2 per 7 days unless running is the primary sport.
- Never schedule back-to-back quality sessions (any sport). Keep at least 1 easy day in between.
- If a key run follows a leg-heavy day, move it 24-48 hours or downgrade to easy.

#### Multi-Sport Adaptation of Running Methodologies (v0)

The reference methodologies (Daniels, Pfitzinger, 80/20, FIRST) assume a running-only focus.
v0 adapts them for multi-sport athletes:

- Apply pace/zone prescriptions to running sessions only; other sports are guided by RPE/HR/time.
- Preserve a minimum running-specific stimulus (see table below); cross-training builds aerobic fitness
  but does not replace running economy or impact tolerance.
- Count hard sessions across all sports together; cap at 2 per 7 days (3 only if running is primary).
- Gate key runs by lower-body load from non-running sessions (strength, trail, CrossFit, ski).
- If running <= 2 days/week: only 1 quality run; long run stays easy and short of volume caps.

#### Double-Day Training Support (v0)

Some athletes can handle two training sessions in one day (e.g., morning run + evening climbing, or quality run + yoga). During onboarding, capture this preference:

**Profile fields:**

- `double_days_enabled: bool` (default: false)
- `double_day_preferences: list` (optional list of acceptable combinations)

**Valid double-day combinations (safe by default):**

| Morning     | Evening               | Load Consideration                          |
| ----------- | --------------------- | ------------------------------------------- |
| Quality run | Yoga/mobility         | Recovery-supportive, encouraged             |
| Easy run    | Climbing (upper-body) | Minimal interference                        |
| Easy run    | Easy cycling          | Aerobic stacking, watch total systemic load |
| Quality run | Easy swim             | Active recovery, good combo                 |

**Combinations requiring caution:**

| Morning     | Evening            | Warning                         |
| ----------- | ------------------ | ------------------------------- |
| Quality run | Hard climbing      | Both high-intensity; check ACWR |
| Quality run | Leg-heavy strength | Back-to-back leg stress         |
| Long run    | Any high-intensity | Too much systemic load          |

**Plan display for double-days:**

```
Thu Jan 30:
  AM: Easy run 30min
  PM: Bouldering 2h (fixed)
      ↳ Run first if possible; climbing won't affect leg recovery
```

**Adaptation rules for double-days:**

- If ACWR > 1.3: Block quality + hard combos on same day
- If lower-body load elevated: Don't stack run + leg-heavy session
- Always allow: Quality run + yoga/mobility (encouraged for recovery)

**When NOT to schedule double-days:**

- During taper weeks (prioritize rest)
- When readiness < 50 (athlete is fatigued)
- Back-to-back days with quality sessions (need recovery day)

#### Minimum Running Specificity (v0)

v0 defines a **minimum “specificity dose”** so progress happens even when running is secondary.

| Goal type         | Minimum weekly running specificity                          | Notes                                                                                           |
| ----------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `general_fitness` | 1 aerobic run (30–60 min)                                   | If 2 runs/wk: add strides or short tempo segments when fresh                                    |
| `5k`              | 1 speed/VO2 stimulus every 7–10 days                        | Examples: hills, short intervals; keep long run modest                                          |
| `10k`             | 1 threshold stimulus weekly                                 | Cruise intervals / tempo are the anchor                                                         |
| `half_marathon`   | 1 long run weekly + 1 threshold/HM-specific stimulus weekly | Long run is the non-negotiable anchor                                                           |
| `marathon`        | v0 supports, but warns if < 3 runs/wk                       | Minimum: long run + marathon-pace/threshold work; recommend more run days if goal is aggressive |

#### General Fitness Goal (v0)

When `goal.type = "general_fitness"`:

- **No end date:** Plan runs indefinitely with rolling 4-week windows
- **No periodization phases:** Maintain consistency without build/peak/taper cycles
- **Weekly structure:** 1 long run (up to 90 min) + 1-2 easy runs per week
- **Intensity:** ~80% easy; quality sessions only if explicitly requested by athlete
- **Progression:** +10% volume every 3 weeks, then 1 recovery week (repeat cycle)

**Key differences from race goals:**

- No target time or race date constraints
- Flexible weekly structure—athlete can skip a run without derailing a plan
- Emphasis on enjoyment and consistency over performance optimization
- No VDOT-based pace prescriptions unless athlete requests them

**When to recommend General Fitness:**

- Athlete has no specific race goal
- Off-season maintenance between race cycles
- Recovering from injury and rebuilding base
- Athlete explicitly wants low-pressure running alongside primary sport

**Constraint Application:**

1. Never schedule hard run day after user's hard other-sport day
2. Long run on user's preferred day (usually weekend)
3. Quality run NOT on day after high lower-body load (leg-heavy strength, hard trail, etc.)
4. Respect max_time_per_session constraint
5. If running is "secondary" priority, err on side of less volume

**Conflict resolution:** when running and primary-sport constraints conflict, use `conflict_policy` from the athlete profile:

- `primary_sport_wins`: protect the primary sport; adjust running first (shorten, swap, or move).
- `running_goal_wins`: keep key run sessions unless injury risk is high; adjust other training first.
- `ask_each_time`: present trade-off and ask the user which to prioritize today/this week.

**Progression Rules:**

- Increase weekly mileage max 10% per week
- Increase for 2-3 weeks, then hold or step back for 1 week
- Every 4th week: reduce volume 20-30% (recovery week)
- Long run progression: add 1-2km per week until peak (max ~21km for HM)
- Long run caps: <= 25-30% of weekly volume and <= 2.5 hours

### 6. Plan Adaptation Rules

**Automatic Adaptations:**

| Trigger                        | Scheduled Workout | Adaptation                              |
| ------------------------------ | ----------------- | --------------------------------------- |
| Systemic ACWR > 1.5            | Quality run       | → Easy run or rest                      |
| Systemic ACWR > 1.5            | Easy run          | → Rest                                  |
| Systemic ACWR 1.3-1.5          | Quality run       | → Reduce duration 20%                   |
| Readiness < 50                 | Quality run       | → Easy run                              |
| Readiness < 35                 | Any               | → Rest                                  |
| 2+ high-intensity sessions/7d  | Quality run       | → Move 24-48h or downgrade              |
| High lower-body load yesterday | Quality run       | → Swap to aerobic easy or move 24-48h   |
| High lower-body load yesterday | Long run          | → Reduce 15-25% or split into 2 runs    |
| Injury flag in notes           | Quality run       | → Easy run + monitoring                 |
| Pain alters gait / sharp pain  | Any               | → Stop run; rest or low-impact XT       |
| Illness below the chest/fever  | Any               | → Rest 48-72h; reassess before resuming |
| Missed 3-7 days                | Next week         | → Reduce volume 10-15%                  |
| Missed 1-2 weeks               | Plan              | → Reduce 20%, no intensity first 3 days |
| Missed 3+ weeks                | Plan              | → Regenerate from reassessment          |

#### Missed Workout Same-Week Handling

If a planned workout is skipped mid-week:

1. **DO NOT automatically shift remaining workouts** (avoid cascading changes)
2. Mark skipped workout as "skipped" with reason
3. **IF the skipped workout was the week's ONLY quality session:**
   - Offer to add quality elements to the long run (if safe: ACWR < 1.3, readiness > 65)
   - Or offer to move quality to a later day this week if available
4. **IF multiple workouts skipped (≥2 in one week):**
   - Reduce next week's volume by 10%
   - Log adaptation: "Volume reduced due to missed training this week"

#### Adaptation Rule Priority

When multiple adaptation rules trigger simultaneously, apply in this priority order:

1. **Safety flags** (illness, injury, sharp pain) → always override → rest or stop
2. **Systemic ACWR > 1.5** → downgrade quality run to easy or rest
3. **High lower-body load** → move workout 24-48h if possible, else reduce duration
4. **2+ high-intensity sessions in 7d** → move or downgrade next quality session

**Conflict resolution between systemic and lower-body triggers:**

- If both (ACWR > 1.5) and (high lower-body load) trigger: prefer **moving** over downgrading (preserves training stimulus while respecting recovery)
- Only downgrade to easy if moving is not possible (e.g., no available slot in next 48h)

**Example:**

- Systemic ACWR = 1.4 (caution zone, not override)
- Lower-body load yesterday = 420 AU (high)
- Tomorrow is scheduled: 30-min tempo run (quality)
- **Action:** Move tempo to Thursday (48h later) if Thursday is available and no conflicts
- **If Thursday is booked:** Reduce tempo to 20-min easy recovery run

**Cross-Training Credit:**

Aerobic credit ratios for replacing easy running (v0):

| Activity Type           | Credit Ratio  | Notes                        |
| ----------------------- | ------------- | ---------------------------- |
| Cycling (easy)          | 2.5h → 1h run | Low-impact, high cardio      |
| Swimming (easy)         | 2h → 1h run   | Zero impact                  |
| Hiking (moderate)       | 1.5h → 1h run | Some impact, lower intensity |
| Elliptical/pool running | 1:1           | Similar movement pattern     |
| Rowing                  | 2h → 1h run   | Upper-body dominant          |
| Cross-country skiing    | 1.5h → 1h run | Full-body, low impact        |

**Application rules:**

- Credit applies to aerobic/easy run replacement only
- Does NOT replace long run specificity (running economy, impact tolerance)
- For race goals: limit replacement to 25% of weekly run volume max
- For `general_fitness`: can replace any easy run 1:1 (time-based)
- If user does a long aerobic session (ride/hike/ski at low intensity), it can replace part of the _aerobic_ purpose of the long run that week, but not the full running-specific stimulus

**v0 substitution rule of thumb:**

- For `general_fitness`: can replace a planned aerobic run 1:1 (time-based) if lower-body load is high.
- For race goals (5k/10k/HM/marathon): allow reducing the long run by up to 25% if a long aerobic session occurred within the last 48h, unless the week is a planned "key long run".

### 7. Pace Estimation (from PRs)

Using Jack Daniels' VDOT system:

**From a 10K PR of 47:00 → VDOT ≈ 45**

| Training Zone     | Pace (min/km) | Purpose                |
| ----------------- | ------------- | ---------------------- |
| Easy              | 5:45 - 6:15   | Recovery, aerobic base |
| Marathon          | 5:10 - 5:20   | Goal marathon pace     |
| Threshold/Tempo   | 4:50 - 5:00   | Lactate threshold      |
| Interval (VO2max) | 4:25 - 4:35   | Aerobic capacity       |
| Repetition        | 4:05 - 4:15   | Speed, running economy |

#### VDOT Calculation Method (Jack Daniels)

Use the Jack Daniels published lookup tables or this approximation formula:

```
velocity_m_per_min = distance_m / time_seconds × 60
VDOT ≈ -4.6 + 0.182258 × velocity_m_per_min + 0.000104 × velocity_m_per_min²
```

**Supported race distances for input:**

- 5K, 10K, half marathon (21.0975 km), marathon (42.195 km)

**If multiple PRs available:**

- Use most recent within 6 weeks
- If all PRs are older: use highest VDOT, but flag "fitness estimate may be stale"

**Pace derivation:**

- Store Daniels Tables 5.1 and 5.2 as lookup JSON in `config/vdot_tables.json`
- Interpolate between table entries for non-integer VDOT values
- Cache derived paces in `athlete.derived_paces` (see profile schema)

**If no PR available:** Use recent training paces + perceived effort to estimate.

**VDOT update rule:** Use the most recent race (last 4-6 weeks) and do not update VDOT more than once every 3-4 weeks.
If only an older PR is available, downgrade paces conservatively or prompt for a new time trial.

---

## Strava API Integration

### Data Available from Strava

**Athlete Stats Endpoint** (`/athletes/{id}/stats`):

- All-time totals (runs, rides, swims)
- Recent totals (last 4 weeks)
- Year-to-date totals
- **Personal Records** (PRs) for various distances!

**Activity Endpoint** (`/activities/{id}`):

- name, type, sport_type
- start_date, elapsed_time, moving_time
- distance, total_elevation_gain
- average_speed, max_speed
- average_heartrate, max_heartrate (if available)
- **suffer_score** (Relative Effort)
- **perceived_exertion** (1-10, if user set it)
- **description** (public notes)
- **private_note** (requires `activity:read_all` scope)

### Sync Process (Manual Trigger)

When user says "sync my Strava":

1. **Check token validity** - refresh if expired
2. **Call activities list endpoint** - get activities since last sync
3. **For each new activity:**
   - Fetch full activity details (including private_note)
   - Create activity file in `activities/YYYY-MM/` folder
   - Calculate training load
   - Extract wellness indicators from notes
4. **Recalculate daily metrics** for affected days
5. **Check for plan adaptation triggers**
6. **Update training history** (`athlete/training_history.yaml`) with `last_strava_sync_at` and `last_strava_activity_id`
7. **Report summary** to user

### Initial Setup / Historical Import

On first setup:

1. **Get athlete stats** - extract PRs for pace estimation
2. **Import 8-12 weeks of history** (enough for CTL baseline)
3. **Build initial CTL/ATL/TSB**
4. **Ask clarifying questions** if data gaps exist

**Why 8-12 weeks?** CTL has 42-day time constant; 8-12 weeks provides stable baseline.

### Limitations & Workarounds

**Personal Records/Best Efforts:**

Strava tracks best efforts at standard distances (400m, 800m, 1K, 5K, 10K, half marathon, marathon), but accessing them has limitations:

- Available via `best_efforts` field in DetailedActivity, but requires fetching each activity individually
- No dedicated endpoint for all-time PRs
- Rate limits make bulk extraction inefficient (can't query all historical activities at once)
- Only available for running activities

**v0 Approach:**

1. **Primary:** Ask user for recent race PRs during onboarding (one-time question): "What's your recent 5K or 10K time?"
2. **Secondary:** Parse `best_efforts` from synced activities over time (builds automatically as activities sync)
3. **Fallback:** Estimate VDOT from training paces if no race data available

**Race Detection:**

The `workout_type` field can indicate race activities:

- `workout_type=1` indicates race (undocumented but functional for running)
- Values: 0 = None, 1 = Race, 2 = Long Run, 3 = Workout
- Many athletes don't tag races manually

**v0 Approach:**

- Check `workout_type=1` as a signal
- Also parse descriptions for race-related keywords: "race", "5K", "10K", "HM", "PB", "PR", "time trial"
- Ask user during onboarding if they have recent race results

---

## Claude's Coaching Prompts

### System Context (Always Provided)

```
You are an expert running coach helping a multi-sport athlete. You have deep
knowledge of training methodology (Daniels, Pfitzinger, 80/20, FIRST "Run Less
Run Faster"). Your athlete treats running as a secondary pursuit alongside
their primary sport or vice versa, depending on their current objective/race goal.

Key Principles:
1. Respect their multi-sport lifestyle—never suggest abandoning other activities
2. Use training load data (CTL/ATL/TSB/ACWR) to inform every recommendation
3. Prioritize injury prevention—ACWR > 1.3 is a warning, > 1.5 requires action
4. Keep easy runs easy; avoid the moderate-intensity rut
5. Quality over quantity—fewer, purposeful runs beat junk miles
6. Parse activity notes for wellness signals, injury flags, and illness cues
7. Be conversational, warm, and direct—avoid being preachy

Current Athlete Context:
[Insert athlete profile summary]
[Insert current metrics: CTL/ATL/TSB/ACWR/Readiness]
[Insert recent activity summary (last 7 days)]
[Insert relevant memories]
[Insert current plan status]

When making recommendations, always reference their actual data.
When suggesting workout modifications, explain why based on their load/readiness.
When you notice concerning patterns (injury, overtraining), flag them directly.
```

### Workout Description Generation

When creating workout files, Claude should write descriptions that:

1. **State the prescription clearly** (distance, pace, structure)
2. **Explain the purpose** (what physiological adaptation, why now)
3. **Connect to their context** (phase, goal, recent training)
4. **Add personalized tips** (based on their history, constraints, injury flags)

Example:

```yaml
purpose: |
  This tempo run builds your lactate threshold—the pace you can hold for about 
  an hour. At your current fitness (VDOT 45 from your 47:00 10K), tempo pace 
  is 4:50-5:00/km. This is the bread-and-butter workout for half marathon prep.

context: |
  Week 2 of base phase. You're coming off a solid climbing session Tuesday, 
  so I've scheduled this for Saturday when legs are fresher. Your ACWR is 1.1 
  (safe zone), so you're good to execute as planned.

tips:
  - Start conservative—first tempo km should feel almost too easy
  - Your hip flexor has been talking lately; if it tightens, drop pace 10-15 sec/km
  - Don't stress about pace. Consistent effort > perfect splits.
```

### Analyzing Activity Notes

When processing a new activity with description/private_note, Claude should:

1. **Extract structured data:**

   - Workout structure (intervals, tempo segments, etc.)
   - Perceived effort indicators
   - Sleep/wellness mentions
   - Injury/soreness flags
   - Contextual factors (weather, life stress, etc.)

2. **Update memories** if new persistent facts discovered:

   - New injury patterns
   - Preference revelations
   - Training response insights

3. **Flag concerns** for immediate discussion:
   - Pain that wasn't there before
   - Unusual fatigue patterns
   - Overtraining signals
   - Illness symptoms (below chest, fever) or heat stress cues

### Conversation Examples

**User asks about today's workout:**

```
User: "What's on the plan for today?"

Claude: [Reads scheduled workout, checks current metrics]

"Today you've got a tempo run scheduled—50 minutes with 25 minutes
at threshold pace (4:50-5:00/km).

Quick check on your status:
- ACWR: 1.15 (safe zone ✓)
- TSB: -12 (productive training zone)
- Last hard session: Tuesday's 6x1000m

Your climbing was Wednesday, so you've had good recovery time.
Should be good to go!

One thing to watch: you mentioned hip flexor tightness last week.
How's it feeling today? If it's acting up, we can dial back the
tempo pace or swap for an easy run."
```

**User reports unexpected session:**

```
User: "I ended up doing a spontaneous 2-hour hike with friends
yesterday instead of my scheduled easy run."

Claude: [Logs manual activity, recalculates load]

"Nice! That's actually a solid swap. I've logged the hike
(estimated ~420 AU with the 0.6 hiking multiplier).

Good news: this doesn't derail anything. The hike gave you
aerobic work similar to an easy run, just lower impact.

Your weekly load is now:
- Before hike: 890 AU
- After hike: 1,310 AU
- Target was: ~1,400 AU

You're right on track. Saturday's long run (14km) is still good
to go. No adjustments needed."
```

**Conflict policy: `ask_each_time` example:**

```
User: "What should I do tomorrow?"

Claude: [Checks plan, sees Tuesday tempo run conflicts with Tuesday climbing]

"Tomorrow's a bit tricky. You have:
  • Scheduled: 30-min tempo run (quality session, threshold pace)
  • Fixed: 2-hour bouldering at Arkose (your primary sport)

Your current status:
  • ACWR: 1.1 (safe zone)
  • Lower-body load: moderate (not elevated)
  • Last quality run: Saturday's long run

You could do both, but that's a lot for one day. Here are your options:

  A) Keep tempo in the morning, do lighter climbing or shorten climb
  B) Keep climbing, move tempo to Thursday (next available day)
  C) Keep climbing, convert tempo to easy 20-min recovery run

Which works best for your week?"

User: "Let's do B, move tempo to Thursday"

Claude: [Updates plan, logs adaptation]

"Done. Thursday is now your tempo day. I've updated the plan and noted:
  'Tempo moved from Tuesday → Thursday due to climbing conflict (user choice).'

Your week now looks like:
  • Monday: Rest
  • Tuesday: Climbing only (2h bouldering)
  • Wednesday: Easy run (30 min)
  • Thursday: Tempo run (30 min)
  • Friday: Rest
  • Saturday: Long run (14km)

Sound good?"
```

**Treadmill run sync (auto-detected):**

```
User: "Sync Strava"

Claude: [Fetches activities, detects treadmill run from no GPS + no outdoor keywords]

"Synced 1 new activity:

📍 Tuesday: 45-min run (treadmill detected)
   - Duration: 45 min
   - Distance: 7.2 km (displayed)
   - Avg HR: 142 bpm

I classified this as a treadmill run since there's no GPS route data.
Let me know if that's not right!

Since treadmill pace can vary 5-15% from actual effort due to calibration,
I'm using your heart rate (142 bpm = easy zone) as the primary indicator.
This looks like a solid easy run—good aerobic work.

Load added: 270 AU (systemic) / 243 AU (lower-body, 10% reduced for treadmill impact)"
```

**Treadmill pace vs HR mismatch:**

```
User: "My treadmill showed 5:00/km but that felt really easy"

Claude: "That mismatch is pretty common! Your HR data (avg 138 bpm)
suggests this was actually an easy effort, closer to your outdoor
5:30-5:45/km pace.

A few things that might explain it:
• Belt calibration: Many treadmills read 5-15% fast or slow
• Incline: Even 0% on some treadmills is slightly downhill
• Running form: Treadmill can feel easier (no wind, consistent surface)

I use HR as the primary metric for your treadmill runs, so the load
calculation reflects your actual effort, not the displayed pace.

For training purposes, you're running easy—which is exactly right
for today's prescribed recovery run. No need to speed up!"
```

---

## Open Questions - Resolved

### Q: Plan start date if user connects mid-week?

**Decision:** Ask user for preference, with recommendation based on context.

If they have a race date set, calculate backwards and recommend accordingly:

- If starting mid-week doesn't mess up week structure, start immediately
- If it would create awkward partial week, suggest starting next Monday
- Always ask: "Would you like to start this week or next Monday?"

### Q: Goal changes mid-plan?

**Decision:** Depends on severity of change.

| Change Type                          | Action                              |
| ------------------------------------ | ----------------------------------- |
| Same distance, different date        | Adjust timeline, keep structure     |
| Same distance, different target time | Adjust paces, keep structure        |
| Adjacent distance (10K → HM)         | Adapt existing plan, extend         |
| Major change (5K → Marathon)         | Regenerate from scratch             |
| Goal → "General Fitness"             | Simplify plan, maintain consistency |

### Q: Multiple goals?

**Decision:** v0 supports one running goal at a time.

"General Fitness" is a valid goal type that means:

- Maintain current fitness
- No race-specific periodization
- Flexible weekly structure
- Emphasis on consistency and enjoyment

If user wants to "run a 5K AND maintain climbing fitness," that's effectively a 5K goal with secondary running priority—we handle that via constraints.

### Q: Activities without HR data?

**Decision:** Analyze the below factos :

1. User's perceived_exertion field (if they set it in Strava)
2. Analysis of description/private_note that might contain information about the workout and/or the effort feedback.
3. Sport type + duration heuristic
4. Ask user directly if critical

For non-cardio activities (climbing, strength), HR data is less relevant anyway—we use notes-based analysis primarily.

### Q: Restorative vs. Vinyasa yoga?

**Decision:** Multiple signals:

1. Check activity name/description for keywords ("restorative," "yin," "gentle" vs. "flow," "vinyasa," "power")
2. Check duration (restorative often longer but lower intensity)
3. If unclear, ask user: "I see you did yoga on Tuesday. Was that a vigorous flow class or more restorative? This helps me count it correctly toward your load."

---

## Implementation Checklist

### Phase 1: Core Infrastructure

- [ ] Set up file structure
- [ ] Create all YAML templates
- [ ] Implement Strava OAuth flow
- [ ] Implement activity sync function
- [ ] Implement PR extraction from Strava stats

### Phase 2: Training Load Engine

- [ ] Implement RPE estimation logic (multi-source)
- [ ] Implement notes parsing for wellness/effort extraction
- [ ] Implement CTL/ATL/TSB calculation
- [ ] Implement ACWR calculation
- [ ] Implement readiness score calculation

### Phase 3: Planning

- [ ] Implement VDOT/pace calculation from PRs
- [ ] Implement intensity zones (pace/HR/RPE) and 80/20 tracking
- [ ] Implement plan generation with constraints
- [ ] Implement weekly structure templates
- [ ] Create workout description templates
- [ ] Implement periodization logic

### Phase 4: Adaptation

- [ ] Implement adaptation rule engine
- [ ] Implement missed workout handling
- [ ] Implement cross-training credit logic
- [ ] Implement red-flag detection (illness, injury, overtraining)
- [ ] Implement plan modification commands

### Phase 5: AI Coaching

- [ ] Create system prompts
- [ ] Implement notes analysis
- [ ] Implement memory extraction/storage
- [ ] Test conversational flows
