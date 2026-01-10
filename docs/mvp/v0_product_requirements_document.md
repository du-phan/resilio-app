# Adaptive Running Coach for Multi-Sport Athletes

## v0 Product Requirements Document (Simplified)

**Version:** 0.2.0  
**Last Updated:** January 2026  
**Status:** Draft for Implementation

---

## Executive Summary

This document defines a lean v0 for an AI-powered adaptive running coach. The product runs entirely within **Claude Code terminal**—no web interface, no database server. All data is stored in **local files** within the repository.

**v0 Core Promise:** Generate a personalized running plan based on user-defined constraints (available days, other sports, priorities) and continuously adapt it in response to actual training load across all tracked activities.

**Interaction Model:** User chats with Claude Code in terminal. Claude reads/writes local files (YAML, JSON, Markdown) to persist state, plans, and history.

---

## Architecture Overview

### No Web UI, No Database

Everything happens through:

1. **Terminal conversation** with Claude Code
2. **Local files** in the repository for persistence
3. **Strava API calls** triggered manually by user request

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
│   └── memories.yaml              # AI-extracted facts from conversations
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
├── conversations/
│   ├── 2025-11-15_session.md      # Conversation logs
│   └── ...
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
        "Synced 3 new activities from the last week. I see you did:
        - Nov 11: Rock Climb (2h30) - looks like a solid session based on your notes
        - Nov 10: Easy Run (45min)
        - Nov 9: Cycling (1h15)

        Your training load is looking good. Systemic ACWR is 1.1 (safe zone).
        Ready for tomorrow's tempo run?"

User: "Actually I'm feeling a bit tired from climbing. Can we swap
       tomorrow's tempo for an easy run?"

Claude: [Updates workout file, recalculates week]
        "Done. I've moved the tempo run to Thursday and tomorrow is
        now an easy 30-minute recovery run. Updated the plan file."
```

### Key Commands User Can Request

| Request                            | What Claude Does                           |
| ---------------------------------- | ------------------------------------------ |
| "Sync my Strava"                   | Calls API, saves new activities to files   |
| "Show my plan for this week"       | Reads plan files, formats nicely           |
| "How's my training load?"          | Calculates CTL/ATL/TSB, explains status    |
| "I need to skip tomorrow's run"    | Updates workout status, adjusts plan       |
| "Change my goal to a 10K in March" | Updates profile, regenerates plan          |
| "What should I do today?"          | Checks scheduled workout, adapts if needed |
| "I did an extra yoga session"      | Logs manual activity                       |

---

## Data Specifications

### Athlete Profile (`athlete/profile.yaml`)

```yaml
# Athlete Profile
name: "Du Phan"
email: "du@example.com"
created_at: "2025-11-01"

# Strava Connection
strava:
  athlete_id: "12345678"
  # Tokens live in `config/secrets.local.yaml` (or env vars). Keep them out of VCS.

# Running Background
running_experience_years: 5
injury_history: "Hip flexor tightness, especially left side. Flares up with high intensity."

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

# Estimated fitness metrics (calculated from PRs)
estimated_vdot: 45
estimated_max_hr: 185 # or measured if known

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
    is_fixed: true # Won't move these
    notes: "Indoor gym, Arkose Montmartre"

  - sport: "cycling"
    days: [sunday]
    typical_duration_minutes: 90
    typical_intensity: "easy_to_moderate"
    is_fixed: false
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
```

### Activity File (`activities/2025-11/2025-11-05_run_lunch.yaml`)

```yaml
# Activity: Lunch Run
id: "strava_12345678"
source: "strava"
sport_type: "running"
sub_type: "intervals" # easy, tempo, intervals, long, race

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

# Link to plan (if matched)
linked_workout_id: "w02_tue_tempo" # Optional, set when matched to a planned workout

# Heart Rate (if available)
average_hr: 158
max_hr: 175
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

# Workout Index (quick view)
workout_index:
  - workout_id: "w02_tue_tempo"
    scheduled_date: "2025-11-12"
    type: "tempo"
    priority: "key"
    status: "scheduled"
    file: "plans/workouts/week_02/tue_tempo.yaml"
  - workout_id: "w02_sat_long"
    scheduled_date: "2025-11-16"
    type: "long_run"
    priority: "key"
    status: "scheduled"
    file: "plans/workouts/week_02/sat_long.yaml"

# Adaptation Log
adaptations:
  - date: "2025-11-12"
    original: "Tuesday tempo run"
    adapted_to: "Thursday tempo run"
    reason: "High systemic load from recent climbing session; athlete requested extra recovery"

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
priority: "key" # key, important, optional
locked: true # key workouts default to locked unless injury risk is high

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

# Planned Load (estimate)
planned_load:
  base_effort_au: 350
  systemic_load_au: 350
  lower_body_load_au: 350

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
  perceived_effort: null
  execution_notes: null

# Coach Review (short debrief)
coach_review: null

# Plan vs Actual (optional delta)
  delta:
    duration_minutes: null
    distance_km: null
    systemic_load_au: null
    lower_body_load_au: null
```

### Planned vs Actual (Coach Model)

v0 treats **planned** and **executed** as distinct layers:

- The plan/workout file preserves the original prescription.
- Execution fields are filled after the session, linked to the actual activity.
- Adaptations are logged rather than rewriting history, so coaches can review intent vs outcome.

### Coach Memories (`athlete/memories.yaml`)

```yaml
# AI-Extracted Facts About Athlete
# These persist across conversations to provide continuity

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

| Sport / Category         | systemic_multiplier | lower_body_multiplier | Notes                                        |
| ------------------------ | ------------------- | --------------------- | -------------------------------------------- |
| Running                  | 1.00                | 1.00                  | Reference                                    |
| Trail running            | 1.05                | 1.10                  | More eccentric/impact                        |
| Cycling                  | 0.85                | 0.35                  | Legs work but low impact; moderate carryover |
| Swimming                 | 0.70                | 0.10                  | Little run-specific leg strain               |
| Hiking                   | 0.60                | 0.50                  | Can be leggy on descents; moderate carryover |
| Climbing / bouldering    | 0.60                | 0.10                  | Mostly upper-body / grip fatigue             |
| Strength / gym (general) | 0.55                | 0.40                  | Depends on lower-body emphasis               |
| CrossFit / metcon        | 0.75                | 0.55                  | Variable; often leg+systemic                 |
| Yoga (vinyasa/flow)      | 0.35                | 0.10                  | Mostly recovery-supportive                   |
| Yoga (restorative / yin) | 0.00                | 0.00                  | Counts as recovery                           |
| Walking                  | 0.20                | 0.10                  | Minimal stress                               |

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

#### Minimum Running Specificity (v0)

v0 defines a **minimum “specificity dose”** so progress happens even when running is secondary.

| Goal type         | Minimum weekly running specificity                          | Notes                                                                                           |
| ----------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `general_fitness` | 1 aerobic run (30–60 min)                                   | If 2 runs/wk: add strides or short tempo segments when fresh                                    |
| `5k`              | 1 speed/VO2 stimulus every 7–10 days                        | Examples: hills, short intervals; keep long run modest                                          |
| `10k`             | 1 threshold stimulus weekly                                 | Cruise intervals / tempo are the anchor                                                         |
| `half_marathon`   | 1 long run weekly + 1 threshold/HM-specific stimulus weekly | Long run is the non-negotiable anchor                                                           |
| `marathon`        | v0 supports, but warns if < 3 runs/wk                       | Minimum: long run + marathon-pace/threshold work; recommend more run days if goal is aggressive |

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
- Every 4th week: reduce volume 20-30% (recovery week)
- Long run progression: add 1-2km per week until peak (max ~21km for HM)

### 6. Plan Adaptation Rules

**Automatic Adaptations:**

| Trigger                        | Scheduled Workout | Adaptation                              |
| ------------------------------ | ----------------- | --------------------------------------- |
| Systemic ACWR > 1.5            | Quality run       | → Easy run or rest                      |
| Systemic ACWR > 1.5            | Easy run          | → Rest                                  |
| Systemic ACWR 1.3-1.5          | Quality run       | → Reduce duration 20%                   |
| Readiness < 50                 | Quality run       | → Easy run                              |
| Readiness < 35                 | Any               | → Rest                                  |
| High lower-body load yesterday | Quality run       | → Swap to aerobic easy or move 24-48h   |
| High lower-body load yesterday | Long run          | → Reduce 15-25% or split into 2 runs    |
| Injury flag in notes           | Quality run       | → Easy run + monitoring                 |
| Missed 3-7 days                | Next week         | → Reduce volume 10-15%                  |
| Missed 1-2 weeks               | Plan              | → Reduce 20%, no intensity first 3 days |
| Missed 3+ weeks                | Plan              | → Regenerate from reassessment          |

**Cross-Training Credit:**

- 2-2.5 hours cycling ≈ 1 hour easy running (cardiovascular load)
- If user does a long aerobic session (ride/hike/ski at low intensity), it can replace part of the _aerobic_ purpose of the long run that week, but not the full running-specific stimulus.
- v0 substitution rule of thumb:
  - For `general_fitness`: can replace a planned aerobic run 1:1 (time-based) if lower-body load is high.
  - For race goals (5k/10k/HM/marathon): allow reducing the long run by up to 25% if a long aerobic session occurred within the last 48h, unless the week is a planned “key long run”.

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

**If no PR available:** Use recent training paces + perceived effort to estimate.

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
4. Quality over quantity—fewer, purposeful runs beat junk miles
5. Parse their activity notes carefully for wellness signals and injury flags
6. Be conversational, warm, and direct—avoid being preachy

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
- [ ] Implement plan generation with constraints
- [ ] Implement weekly structure templates
- [ ] Create workout description templates
- [ ] Implement periodization logic

### Phase 4: Adaptation

- [ ] Implement adaptation rule engine
- [ ] Implement missed workout handling
- [ ] Implement cross-training credit logic
- [ ] Implement plan modification commands

### Phase 5: AI Coaching

- [ ] Create system prompts
- [ ] Implement notes analysis
- [ ] Implement memory extraction/storage
- [ ] Test conversational flows
