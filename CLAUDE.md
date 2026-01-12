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

### 4. Modular Architecture (v0)

The technical spec defines 14 modules with clear responsibilities:

| Module | Responsibility |
|--------|---------------|
| M1 - CLI Orchestrator | Parse user intent, orchestrate workflows |
| M2 - Config & Secrets | Load settings, validate secrets |
| M3 - Repository I/O | Centralized YAML/JSON read/write |
| M4 - Profile Service | CRUD for athlete profile |
| M5 - Activity Ingestion | Import from Strava + manual logging |
| M6 - Activity Normalization | Normalize sport types, units |
| M7 - Notes & RPE Analyzer | Extract wellness/effort from text |
| M8 - Load Engine | Compute systemic + lower-body loads |
| M9 - Metrics Engine | Compute CTL/ATL/TSB/ACWR/readiness |
| M10 - Plan Generator | Build plans with training guardrails |
| M11 - Adaptation Engine | Apply rules to adjust workouts |
| M12 - Coach Response Formatter | Render user-facing outputs |
| M13 - Memory & Insights | Extract durable athlete facts |
| M14 - Conversation Logger | Persist session transcripts |

### 5. Training Science Guardrails

The system enforces evidence-based training principles:

- **80/20 intensity distribution**: ~80% low intensity, ≤20% moderate+high (for ≥3 run days/week)
- **ACWR safety**: ACWR > 1.5 = high injury risk, triggers automatic adaptations
- **Long run caps**: ≤25-30% of weekly run volume, ≤2.5 hours
- **Hard/easy separation**: No back-to-back high-intensity sessions across all sports
- **T/I/R volume limits**: Threshold ≤10%, Intervals ≤8%, Repetition ≤5% of weekly mileage
- **Conflict policy**: User-defined rules for when running and primary sport collide

### 6. User Interaction Model

Users interact via natural conversation:
- "Sync my Strava" → imports activities, recalculates metrics
- "What should I do today?" → gets workout with rationale based on current data
- "I'm feeling tired" → triggers adaptation logic
- "Change my goal to 10K in March" → regenerates plan

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
M1 (CLI) → M2 (config) → M5 (Strava API) → M6 (normalize)
→ M7 (analyze RPE/notes) → M8 (compute loads)
→ M13 (update memories) → M9 (recalculate metrics)
→ M11 (check adaptations) → M12 (format response)
→ M14 (log conversation)
```

### Typical "What should I do today?" Flow
```
M1 → M3/M4/M10 (read profile + plan)
→ M9 (compute current status if stale)
→ M11 (check if adaptation needed)
→ M12 (render workout + rationale)
→ M14 (log)
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

## Resources

- Full PRD: `docs/mvp/v0_product_requirements_document.md` (comprehensive, read this for complete understanding)
- Technical spec: `docs/mvp/v0_technical_specification.md` (architecture and modules)
- 80/20 methodology: `docs/training_books/80_20_matt_fitzgerald.md` (core training philosophy)
