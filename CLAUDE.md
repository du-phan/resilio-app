# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Sports Coach Engine** is an AI-powered adaptive running coach for multi-sport athletes. The system runs entirely within Claude Code terminal sessions with no web interface or database server. All data is persisted in local YAML/JSON files within the repository.

**Current Status**: v0 planning phase. The repository contains comprehensive product requirements and technical specifications, but no implementation code yet.

**Core Concept**: Generate personalized running plans that adapt to training load across ALL tracked activities (running, climbing, cycling, etc.), continuously adjusting based on metrics like CTL/ATL/TSB, ACWR, and readiness scores.

## Repository Structure

```
docs/
  mvp/
    v0_product_requirements_document.md    # Complete PRD - read this first
    v0_technical_specification.md          # Modular architecture design
  training_books/                          # Training methodology references
    80_20_matt_fitzgerald.md               # Primary methodology reference
    advanced_marathoning_pete_pfitzinger.md
    faster_road_racing_pete_pfitzinger.md
    daniel_running_formula.md
    run_less_run_faster_bill_pierce.md
```

**Planned directory structure** (from PRD, not yet implemented):
```
athlete/                 # Profile, memories, training history
activities/YYYY-MM/      # Activity files organized by month
metrics/                 # Daily and weekly computed metrics
plans/                   # Current plan and workouts
conversations/           # Session transcripts
config/                  # Settings and secrets
```

## Key Architecture Principles

### 1. File-Based Persistence
- All data stored in YAML/JSON files
- No database server
- Human-readable, version-controllable
- Atomic writes to prevent corruption
- Schema validation on read/write

### 2. Adoption-First Design (Minimize User Effort)

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

This principle informed major v0 design decisions: extraction-only wellness data, no mandatory daily logging, automatic Strava sync, and conversational orchestration via M1.

### 3. Multi-Sport Load Model
The system uses a **two-channel load model** to handle multi-sport athletes correctly:

- **Systemic load** (`systemic_load_au`): Cardio + whole-body fatigue → feeds CTL/ATL/TSB/ACWR
- **Lower-body load** (`lower_body_load_au`): Leg strain + impact → gates quality/long runs

This prevents hard climbing/strength days from incorrectly blocking running workouts when the fatigue is primarily upper-body.

**Load calculation**:
```
base_effort_au = RPE × duration_minutes
systemic_load_au = base_effort_au × systemic_multiplier
lower_body_load_au = base_effort_au × lower_body_multiplier
```

**Validated with Real Strava Data** (Jan 2026):
- Running (7km, 43min, RPE 7): 301 AU systemic + 301 AU lower-body ✓
- Climbing (105min, RPE 5): 315 AU systemic, 52 AU lower-body ✓
- Yoga (28min, RPE 2): 20 AU systemic, 6 AU lower-body ✓

Two-channel model confirmed working correctly with real multi-sport activities.

### 4. Claude Code as Interface

**Claude Code (the AI) is the user interface.** The sports-coach-engine package provides an API layer designed for Claude Code to call. Claude Code handles:
- Understanding user intent (natural language)
- Managing conversation flow and context
- Formatting responses appropriately for the user

**The package provides:**
- `sports_coach_engine.api` — Public functions for all operations
- Rich return types with interpretations (CTL=44 → "solid recreational level")
- Direct file access via `RepositoryIO` for exploration

### 5. The Core Innovation: Computational Toolkit, Not Algorithm Generator

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

| Task Type | Who Handles It | Why |
|-----------|----------------|-----|
| **Quantitative** (pure math) | Package modules | Formulas, lookup tables, deterministic logic |
| **Qualitative** (judgment, context) | Claude Code | Natural language understanding, reasoning, personalization |

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

#### Module Responsibilities (Toolkit Paradigm)

| Module | OLD (Algorithm Generator) | NEW (Computational Toolkit) |
|--------|--------------------------|----------------------------|
| **M7 (Notes & RPE)** | Extracts injury/illness from text, resolves RPE conflicts | Returns multiple RPE estimates; Claude extracts wellness via conversation |
| **M8 (Load Engine)** | Classifies session type from keywords | Calculates load from RPE + duration only; Claude determines session purpose |
| **M9 (Metrics)** | ✅ Correct: Computes CTL/ATL/TSB/ACWR | ✅ No change: Pure quantitative formulas |
| **M10 (Plan Generator)** | Generates complete training plan algorithmically | Provides planning tools; Claude designs plan workout by workout |
| **M11 (Adaptation)** | Generates adaptation suggestions automatically | Detects triggers, assesses risk; Claude decides adaptations with athlete |
| **M12 (Enrichment)** | Generates workout rationales and summaries | Provides metric interpretations; Claude crafts coaching messages |
| **M13 (Memory)** | ✅ Correct: Storage + retrieval; Claude extracts | ✅ No change: Toolkit for durable athlete facts |

#### Example: Training Plan Generation

**OLD (Algorithmic)**:
```python
# Algorithm decides everything
plan = generate_plan(profile, goal="half_marathon", weeks=12)
# Returns rigid plan: quality on Tue/Thu, long run Sunday, etc.
# Cannot accommodate: "I climb Tuesdays"
```

**NEW (Toolkit)**:
```python
# Claude Code has conversation
User: "I want to train for a half marathon in 12 weeks. I climb Tuesdays and Thursdays."

Claude Code reasoning:
1. Calls: suggest_volume_adjustment(current=35, ctl=44, goal_distance=21.1)
   Gets: start_range=(30, 40), peak_range=(50, 60)

2. Calls: calculate_periodization(weeks=12, goal_type="half_marathon")
   Gets: PhaseAllocation(base=3, build=6, peak=2, taper=1)

3. Designs plan considering climbing schedule:
   - Quality runs: Wednesday (after Tue climb recovery)
   - Long runs: Saturday (fresh, no climbing conflict)
   - Easy runs: Monday, Thursday (light after/before climbing)

4. For each workout:
   workout = create_workout("tempo", duration_min=40, profile=profile)

5. Validates:
   violations = validate_guardrails(claude_designed_plan, profile)

6. Presents plan with rationale:
   "I've designed your plan with quality on Wednesdays and Saturdays
    to work around your climbing. Week 4 looked aggressive, so I adjusted..."
```

#### Example: Adaptation Decision

**OLD (Algorithmic)**:
```python
# Algorithm auto-generates suggestion
if acwr > 1.5:
    suggestion = Suggestion(type="downgrade", workout=easy_run())
    # Generic rationale: "ACWR at 1.52. Reducing intensity to prevent injury."
```

**NEW (Toolkit)**:
```python
# M11 detects triggers
triggers = detect_adaptation_triggers(workout, metrics, profile)
# → [AdaptationTrigger.ACWR_ELEVATED(1.45)]

# M11 assesses risk
risk = assess_override_risk(triggers, workout, athlete_memories)
# → OverrideRiskAssessment(risk_level="moderate", injury_probability=0.15)

# Claude Code reasons with full context
Claude: "ACWR is 1.45 (caution zone). You climbed yesterday, which explains
         the elevated lower-body load. Your knee history makes me cautious.
         Here are three options:

         A) Run easy tomorrow (30min RPE 4) - safest
         B) Move tempo to Thursday - gives legs 2 days recovery
         C) Do tempo as planned - moderate risk (~15% injury probability)

         What sounds best to you? I'm leaning toward A or B."

User: "Let's move to Thursday"

Claude: ✓ Updates plan
        ✓ Logs to M13: "Athlete prefers moving workouts over downgrading"
```

#### Why This Matters

**Traditional apps are limited by algorithms:**
- Can't understand: "I'm feeling tired but it's just work stress, not training fatigue"
- Can't reason: "Climbing Tuesday → elevated load Wednesday → easy run makes sense"
- Can't adapt: "That didn't work? Let me try a different approach"
- Can't explain: "Why did you put quality on Saturday?" → "The algorithm decided"

**Claude Code + Toolkit enables true coaching:**
- Understands context naturally
- Reasons about individual athletes
- Adapts based on feedback
- Explains every decision transparently

**The result**: Personalized coaching that feels like working with a human coach who knows you, not a rigid algorithm.

### 6. Modular Architecture (v0)

The technical spec defines 14 modules. Claude Code calls the API layer, which internally orchestrates the modules.

**API Layer (Public):**
| Module | Code Path | Purpose |
|--------|-----------|---------|
| api/coach.py | `api.coach` | Workouts, weekly status |
| api/sync.py | `api.sync` | Strava sync, manual logging |
| api/metrics.py | `api.metrics` | CTL/ATL/TSB/ACWR/readiness |
| api/plan.py | `api.plan` | Plans, suggestions |
| api/profile.py | `api.profile` | Athlete profile management |

**Internal Modules (Computational Toolkit):**
| Module | Code Path | Responsibility (Toolkit Functions) |
|--------|-----------|-----------------------------------|
| M1 - Internal Workflows | `core/workflows.py` | Orchestrate multi-step operations |
| M2 - Config & Secrets | `core/config.py` | Load settings, validate secrets |
| M3 - Repository I/O | `core/repository.py` | Centralized YAML/JSON read/write |
| M4 - Profile Service | `core/profile.py` | CRUD for athlete profile |
| M5 - Strava Integration | `core/strava.py` | Import from Strava + manual logging |
| M6 - Activity Normalization | `core/normalization.py` | Normalize sport types, units |
| M7 - Notes & RPE Analyzer | `core/notes.py` | Compute multiple RPE estimates from HR/pace/duration |
| M8 - Load Engine | `core/load.py` | Compute systemic + lower-body loads from RPE |
| M9 - Metrics Engine | `core/metrics.py` | Compute CTL/ATL/TSB/ACWR/readiness formulas |
| M10 - Plan Toolkit | `core/plan.py` | Planning tools: periodization, volume curves, workout templates, guardrail validation |
| M11 - Adaptation Toolkit | `core/adaptation.py` | Detect triggers, assess risk, estimate recovery time |
| M12 - Data Enrichment | `core/enrichment.py` | Interpret metrics into zones and trends |
| M13 - Memory & Insights | `core/memory.py` | Store/retrieve durable athlete facts (Claude Code extracts) |
| M14 - Conversation Logger | `core/logger.py` | Persist session transcripts |

### 7. Training Science Guardrails

The system provides evidence-based training guardrails as **validation tools** (Claude Code decides enforcement):

- **80/20 intensity distribution**: ~80% low intensity, ≤20% moderate+high (for ≥3 run days/week)
- **ACWR safety**: ACWR > 1.5 = high injury risk, M11 detects trigger → Claude Code decides adaptation
- **Long run caps**: ≤25-30% of weekly run volume, ≤2.5 hours
- **Hard/easy separation**: No back-to-back high-intensity sessions across all sports
- **T/I/R volume limits**: Threshold ≤10%, Intervals ≤8%, Repetition ≤5% of weekly mileage
- **Conflict policy**: User-defined rules for when running and primary sport collide

**Key Principle**: Guardrails are **validated** by modules, **enforced** by Claude Code. The system returns violations with context; Claude Code reasons about whether to enforce, override, or discuss with athlete.

### 8. User Interaction Model

Users interact via natural conversation. Claude Code understands intent and uses toolkit functions to coach:
- "Sync my Strava" → `sync_strava()` → imports activities, recalculates metrics
- "What should I do today?" → Claude uses `detect_adaptation_triggers()` + metrics context → coaches with reasoning
- "I'm feeling tired" → Claude extracts wellness signal, uses `assess_override_risk()` → presents options with trade-offs
- "Help me plan for a half marathon" → Claude uses `calculate_periodization()`, `suggest_volume_adjustment()`, `create_workout()` → designs personalized plan
- "Change my goal to 10K in March" → `set_goal()` → Claude uses toolkit to redesign plan

## Training Methodologies

The system synthesizes principles from multiple proven methodologies:

1. **Jack Daniels' VDOT System**: Pace zones calculated from recent race performances
2. **Pfitzinger**: Periodization, long run progression, recovery week cycles
3. **80/20 (Matt Fitzgerald)**: Intensity distribution, low-intensity discipline
4. **FIRST (Run Less, Run Faster)**: Low-frequency running adapted for multi-sport athletes

**Key adaptation for multi-sport**: When running ≤2 days/week, the system uses FIRST-style low-frequency training but adapts around systemic and lower-body load from other sports.

## Important Constraints

### Security & Privacy
- `config/secrets.local.yaml` contains Strava tokens and MUST NOT be committed
- Already in .gitignore
- All sensitive data stays local

### Multi-Sport Awareness
- Running can be PRIMARY, SECONDARY, or EQUAL priority
- Conflict policy determines what happens when constraints collide:
  - `primary_sport_wins`: Protect primary sport, adjust running
  - `running_goal_wins`: Keep key runs unless injury risk
  - `ask_each_time`: Present trade-offs, let user decide

### Adaptation Triggers
M11 detects triggers that warrant coaching attention. Claude Code decides adaptations with athlete:
- ACWR > 1.5 (high injury risk detected)
- Readiness score < 50 (fatigue signal detected)
- Readiness < 35 (severe fatigue detected)
- High lower-body load yesterday before quality/long run
- Injury/wellness signals extracted from conversation
- 2+ high-intensity sessions in 7 days

**Toolkit Approach**: M11 returns trigger data + risk assessment → Claude Code interprets with athlete context (M13 memories, conversation history) → presents options with reasoning → athlete decides

## Data Flow

### Typical "Sync Strava" Flow
```
User: "sync my Strava"
    │
    ▼
Claude Code: understands intent
    │
    ▼ calls
api.sync.sync_strava()
    │
    ▼ internally orchestrates
M1 (workflows) → M5 (Strava) → M6 (normalize) → M7 (notes)
    → M8 (loads) → M9 (metrics) → M11 (adaptations) → M13 (memories)
    │
    ▼ returns
SyncSummary (enriched by M12)
    │
    ▼
Claude Code: crafts natural response from structured data
```

### Typical "What should I do today?" Flow (Toolkit Paradigm)
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

## Key Metrics

### CTL/ATL/TSB (Training Stress Balance)
- **CTL** (Chronic Training Load): 42-day weighted average, represents "fitness"
- **ATL** (Acute Training Load): 7-day weighted average, represents "fatigue"
- **TSB** (Training Stress Balance): CTL - ATL, represents "form"
  - TSB -25 to -10: Productive training zone
  - TSB -10 to +5: Optimal for quality work
  - TSB +5 to +15: Fresh, good for racing

### ACWR (Acute:Chronic Workload Ratio)
```
ACWR = (7-day total load) / (28-day average load)
```
- 0.8-1.3: Safe zone
- 1.3-1.5: Caution
- >1.5: High injury risk (2-4x increased)

### Readiness Score (0-100)
Weighted combination of:
- TSB (20%)
- Recent load trend (25%)
- Sleep quality (25%)
- Subjective wellness (30%)

## Implementation Status

**Phase 1-5 Complete** (Infrastructure + Load Engine + Memory + Toolkit Refactoring):
- ✅ M2 - Config & Secrets
- ✅ M3 - Repository I/O
- ✅ M4 - Profile Service
- ✅ M5 - Strava Integration (with real Strava data validation)
- ✅ M6 - Activity Normalization
- ✅ M7 - Notes & RPE Analyzer (refactored to toolkit paradigm)
- ✅ M8 - Load Engine (two-channel model validated with real data)
- ✅ M9 - Metrics Engine (CTL/ATL/TSB/ACWR/readiness)
- ✅ M10 - Plan Toolkit (refactored from generator to toolkit)
- ✅ M11 - Adaptation Toolkit (refactored from suggestion generator to trigger detector)
- ✅ M12 - Data Enrichment (context tables, metric interpretation)
- ✅ M13 - Memory & Insights (AI-driven extraction, deduplication, pattern analysis)

**Pending** (Orchestration & Logging):
- ⏳ M1 - Internal Workflows (orchestration layer)
- ⏳ M14 - Conversation Logger (session transcript persistence)

**Complete**:
- Product requirements (v0_product_requirements_document.md)
- Technical specification (v0_technical_specification.md)
- Training methodology references
- Comprehensive test suites (315 tests passing across all modules)
- Real Strava data integration and validation

## When Implementing

1. **Start with infrastructure**: M2 (config), M3 (file I/O), M4 (profile service)
2. **Build load engine next**: M5→M6→M7→M8→M9 pipeline
3. **Then planning**: M10 (generator), M11 (adaptation)
4. **Finally UX**: M1 (orchestrator), M12 (formatter), M14 (logger)

**Critical design choices**:
- Use YAML for human readability (easy to debug/inspect)
- Atomic writes (temp file + rename)
- Schema validation on every read/write
- Fail fast with helpful errors
- Idempotent operations (especially activity ingestion)
- Separation of concerns (no module mutates another's data directly)

## Training Philosophy

The coaching approach balances:
- **Consistency over intensity**: Better to do sustainable work than hero workouts
- **Respect the multi-sport lifestyle**: Never suggest abandoning other activities
- **Injury prevention first**: ACWR > 1.3 is a warning flag
- **Hard/easy discipline**: Most common mistake is the "moderate-intensity rut"
- **Context-aware adaptations**: Use actual data (CTL/ATL/TSB/ACWR/notes) to inform every recommendation

## Conversation Style

The AI coach should be:
- Conversational, warm, and direct
- Data-driven: Always reference actual metrics when explaining recommendations
- Transparent: Explain the "why" behind adaptations
- Proactive: Flag concerning patterns (injury, overtraining, illness)
- Respectful: Multi-sport athletes have complex schedules; work with them, not against them

## Quick Reference: Sport Multipliers

| Sport | systemic | lower_body |
|-------|----------|------------|
| Running (road/track) | 1.00 | 1.00 |
| Running (treadmill) | 1.00 | 0.90 |
| Trail running | 1.05 | 1.10 |
| Cycling | 0.85 | 0.35 |
| Swimming | 0.70 | 0.10 |
| Climbing/bouldering | 0.60 | 0.10 |
| Strength (general) | 0.55 | 0.40 |
| Hiking | 0.60 | 0.50 |
| CrossFit/metcon | 0.75 | 0.55 |
| Yoga (flow) | 0.35 | 0.10 |
| Yoga (restorative) | 0.00 | 0.00 |

## API Reference for Claude Code

### Quick Start
```python
from sports_coach_engine.api import sync_strava, get_todays_workout, get_current_metrics

result = sync_strava()
workout = get_todays_workout()
metrics = get_current_metrics()
```

### Available Functions

#### Sync Operations (api.sync)
| Function | Purpose | When to Use |
|----------|---------|-------------|
| `sync_strava()` | Import activities from Strava | User says "sync", "update activities", "import from Strava" |
| `log_activity(sport_type, duration_minutes, ...)` | Log manual activity | User logs a workout manually |

#### Coach Operations (api.coach)
| Function | Purpose | When to Use |
|----------|---------|-------------|
| `get_todays_workout(target_date=None)` | Get workout for a day | User asks "what should I do today?", "what's my workout?" |
| `get_weekly_status()` | Get week overview with activities | User asks "show my week", "weekly summary" |
| `get_training_status()` | Get CTL/ATL/TSB/ACWR/readiness | User asks "how am I doing?", "my fitness" |

#### Metrics Operations (api.metrics)
| Function | Purpose | When to Use |
|----------|---------|-------------|
| `get_current_metrics()` | Get current metrics with interpretations | User asks about CTL, TSB, form, fitness |
| `get_readiness()` | Get readiness score with breakdown | User asks "am I ready?", "should I train hard?" |

#### Plan Operations (api.plan) - TOOLKIT PARADIGM
| Function | Purpose | When to Use |
|----------|---------|-------------|
| `get_current_plan()` | Get athlete's current plan | User asks to see their plan |
| `calculate_periodization(weeks, goal_type)` | Get phase allocation suggestion | Claude designing a new plan |
| `calculate_volume_progression(start, peak, weeks, recovery)` | Get volume curve reference | Claude designing weekly volumes |
| `suggest_volume_adjustment(current, ctl, goal_distance)` | Get safe volume ranges | Claude determining start/peak volumes |
| `create_workout(type, duration, profile, target_rpe)` | Create workout with paces/zones | Claude designing individual workouts |
| `validate_guardrails(plan, profile)` | Check plan for violations | Claude validating designed plan |
| `detect_adaptation_triggers(workout, metrics, profile)` | Detect physiological triggers | Claude assessing workout suitability |
| `assess_override_risk(triggers, workout, memories)` | Assess injury risk | Claude presenting options to athlete |

#### Profile Operations (api.profile)
| Function | Purpose | When to Use |
|----------|---------|-------------|
| `get_profile()` | Get athlete profile | User asks about their settings |
| `update_profile(**fields)` | Update profile fields | User changes preferences |
| `set_goal(race_type, target_date, ...)` | Set a race goal | User sets a new goal |

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

### Direct Data Access

For exploration or custom queries, use RepositoryIO directly:
```python
from sports_coach_engine.core.repository import RepositoryIO

repo = RepositoryIO()
profile = repo.read_yaml("athlete/profile.yaml")
activities = repo.list_files("activities/**/*.yaml")
raw_metrics = repo.read_yaml("metrics/daily/2026-01-12.yaml")
```

## Resources

- Full PRD: `docs/mvp/v0_product_requirements_document.md` (comprehensive, read this for complete understanding)
- Technical spec: `docs/mvp/v0_technical_specification.md` (architecture and modules)
- API layer spec: `docs/specs/api_layer.md` (detailed API design)
- 80/20 methodology: `docs/training_books/80_20_matt_fitzgerald.md` (core training philosophy)
