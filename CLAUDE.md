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

### 4. Claude Code as Interface

**Claude Code (the AI) is the user interface.** The sports-coach-engine package provides an API layer designed for Claude Code to call. Claude Code handles:
- Understanding user intent (natural language)
- Managing conversation flow and context
- Formatting responses appropriately for the user

**The package provides:**
- `sports_coach_engine.api` — Public functions for all operations
- Rich return types with interpretations (CTL=44 → "solid recreational level")
- Direct file access via `RepositoryIO` for exploration

### 5. Modular Architecture (v0)

The technical spec defines 14 modules. Claude Code calls the API layer, which internally orchestrates the modules.

**API Layer (Public):**
| Module | Code Path | Purpose |
|--------|-----------|---------|
| api/coach.py | `api.coach` | Workouts, weekly status |
| api/sync.py | `api.sync` | Strava sync, manual logging |
| api/metrics.py | `api.metrics` | CTL/ATL/TSB/ACWR/readiness |
| api/plan.py | `api.plan` | Plans, suggestions |
| api/profile.py | `api.profile` | Athlete profile management |

**Internal Modules:**
| Module | Code Path | Responsibility |
|--------|-----------|---------------|
| M1 - Internal Workflows | `core/workflows.py` | Orchestrate multi-step operations |
| M2 - Config & Secrets | `core/config.py` | Load settings, validate secrets |
| M3 - Repository I/O | `core/repository.py` | Centralized YAML/JSON read/write |
| M4 - Profile Service | `core/profile.py` | CRUD for athlete profile |
| M5 - Strava Integration | `core/strava.py` | Import from Strava + manual logging |
| M6 - Activity Normalization | `core/normalization.py` | Normalize sport types, units |
| M7 - Notes & RPE Analyzer | `core/notes.py` | Extract wellness/effort from text |
| M8 - Load Engine | `core/load.py` | Compute systemic + lower-body loads |
| M9 - Metrics Engine | `core/metrics.py` | Compute CTL/ATL/TSB/ACWR/readiness |
| M10 - Plan Generator | `core/plan.py` | Build plans with training guardrails |
| M11 - Adaptation Engine | `core/adaptation.py` | Apply rules to adjust workouts |
| M12 - Data Enrichment | `core/enrichment.py` | Add interpretive context to raw data |
| M13 - Memory & Insights | `core/memory.py` | Extract durable athlete facts |
| M14 - Conversation Logger | `core/logger.py` | Persist session transcripts |

### 6. Training Science Guardrails

The system enforces evidence-based training principles:

- **80/20 intensity distribution**: ~80% low intensity, ≤20% moderate+high (for ≥3 run days/week)
- **ACWR safety**: ACWR > 1.5 = high injury risk, triggers automatic adaptations
- **Long run caps**: ≤25-30% of weekly run volume, ≤2.5 hours
- **Hard/easy separation**: No back-to-back high-intensity sessions across all sports
- **T/I/R volume limits**: Threshold ≤10%, Intervals ≤8%, Repetition ≤5% of weekly mileage
- **Conflict policy**: User-defined rules for when running and primary sport collide

### 7. User Interaction Model

Users interact via natural conversation. Claude Code understands intent and calls the appropriate API functions:
- "Sync my Strava" → `sync_strava()` → imports activities, recalculates metrics
- "What should I do today?" → `get_todays_workout()` → gets workout with rationale
- "I'm feeling tired" → triggers adaptation logic via `get_todays_workout(wellness_override=...)`
- "Change my goal to 10K in March" → `set_goal()` + `regenerate_plan()`

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
Automatic adaptations fire when:
- ACWR > 1.5 (high injury risk)
- Readiness score < 50 (reduce intensity)
- Readiness < 35 (rest recommended)
- High lower-body load yesterday before quality/long run
- Injury/pain flags in activity notes
- 2+ high-intensity sessions in 7 days

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

### Typical "What should I do today?" Flow
```
User: "what should I do today?"
    │
    ▼
Claude Code: understands intent
    │
    ▼ calls
api.coach.get_todays_workout()
    │
    ▼ internally orchestrates
M1 (workflows) → M9 (metrics) → M10 (plan) → M11 (adaptations)
    │
    ▼ returns
EnrichedWorkout (enriched by M12) with:
    - workout prescription
    - rationale (why this workout today)
    - current metrics context
    - any pending suggestions
    │
    ▼
Claude Code: crafts natural response from structured data
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

**Not yet implemented**:
- All 14 modules
- File I/O infrastructure
- Strava OAuth/API integration
- Load calculation engine
- Plan generation
- Adaptation rules engine
- Coaching conversation layer

**Complete**:
- Product requirements (v0_product_requirements_document.md)
- Technical specification (v0_technical_specification.md)
- Training methodology references
- File schemas and data models

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

#### Plan Operations (api.plan)
| Function | Purpose | When to Use |
|----------|---------|-------------|
| `get_current_plan()` | Get full training plan | User asks to see their plan |
| `regenerate_plan(goal=None)` | Generate new plan | User wants fresh plan, changes goal |
| `get_pending_suggestions()` | Get adaptation suggestions | User asks about adjustments |
| `accept_suggestion(id)` | Accept an adaptation | User says "yes", "accept" to suggestion |
| `decline_suggestion(id)` | Decline an adaptation | User says "no", "decline" to suggestion |

#### Profile Operations (api.profile)
| Function | Purpose | When to Use |
|----------|---------|-------------|
| `get_profile()` | Get athlete profile | User asks about their settings |
| `update_profile(**fields)` | Update profile fields | User changes preferences |
| `set_goal(race_type, target_date, ...)` | Set a race goal | User sets a new goal |

### Return Types

All API functions return **rich Pydantic models** with interpretive context:

```python
# EnrichedMetrics example
metrics.ctl.value          # 44 (raw number)
metrics.ctl.interpretation # "solid recreational level"
metrics.ctl.zone           # MetricZone.RECREATIONAL
metrics.ctl.trend          # "+2 from last week"

# EnrichedWorkout example
workout.workout_type_display  # "Tempo Run"
workout.duration_formatted    # "45 minutes"
workout.rationale.primary_reason  # "Form is good"
workout.rationale.training_purpose  # "lactate threshold improvement"
workout.current_readiness.interpretation  # "ready for normal training"
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
