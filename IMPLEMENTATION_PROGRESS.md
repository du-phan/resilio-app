# Sports Coach Engine - Implementation Progress

**Version**: 0.1.0
**Last Updated**: 2026-01-13
**Status**: Phase 5 Complete ✅ | Toolkit Paradigm Refactoring Implemented

---

## Overall Progress: 95%

### Summary

- ✅ **12 of 14 core modules complete** (M2-M13, excluding M1 workflows and M14 logger)
- ✅ **315 tests passing** across all modules
- ✅ **Toolkit paradigm refactored** in M7, M10, M11 (57% code reduction)
- ✅ **Real Strava data validated** with 17 multi-sport activities
- ✅ **Full pipeline operational**: Strava → Normalize → Analyze → Metrics → Planning → Adaptation
- ⏳ **Remaining**: M1 orchestration workflows, M14 conversation logger, API layer

### Completed Modules (12/14)

| Phase | Module                    | Status | Tests | Coverage | Notes                                  |
| ----- | ------------------------- | ------ | ----- | -------- | -------------------------------------- |
| 1     | M2 - Config & Secrets     | ✅     | 8     | 94%      | Core infrastructure                    |
| 1     | M3 - Repository I/O       | ✅     | 18    | 95%      | File operations with atomic writes     |
| 1     | M4 - Profile Service      | ✅     | 24    | 90%      | VDOT calculation, constraints          |
| 2     | M5 - Strava Integration   | ✅     | 28    | 94%      | OAuth, sync, deduplication             |
| 2     | M6 - Normalization        | ✅     | 25    | 83%      | 40+ sport aliases → 13 canonical       |
| 2     | M7 - Notes & RPE Analyzer | ✅     | 26    | 84%      | **Toolkit refactored** (65% reduction) |
| 2     | M8 - Load Engine          | ✅     | 23    | 84%      | Two-channel load model                 |
| 3     | M9 - Metrics Engine       | ✅     | 32    | 94%      | CTL/ATL/TSB/ACWR/readiness             |
| 4     | M10 - Plan Toolkit        | ✅     | 51    | 88%      | **Toolkit refactored** (52% reduction) |
| 4     | M11 - Adaptation Toolkit  | ✅     | 26    | 85%      | **Toolkit refactored** (55% reduction) |
| 4     | M12 - Data Enrichment     | ✅     | 31    | 87%      | Metric interpretations                 |
| 4     | M13 - Memory & Insights   | ✅     | 23    | 82%      | AI-driven extraction                   |

### Pending Modules (2/14)

| Module                    | Status     | Dependencies | Estimated Effort |
| ------------------------- | ---------- | ------------ | ---------------- |
| M1 - Internal Workflows   | ⏳ Pending | All modules  | 2-3 days         |
| M14 - Conversation Logger | ⏳ Pending | M3           | 1 day            |

---

## Phase 1: Core Infrastructure (100% ✅)

### M2 - Config & Secrets

- ✅ YAML config loading with validation
- ✅ Secret management (Strava tokens)
- ✅ Error handling for missing configs
- **Tests**: 8/8 passing (94% coverage)
- **Files**: `schemas/config.py`, `core/config.py`

### M3 - Repository I/O

- ✅ YAML read/write with Pydantic validation
- ✅ Atomic writes (temp file + rename)
- ✅ PID-based file locking (cross-platform)
- ✅ Glob pattern support for file discovery
- **Tests**: 18/18 passing (95% coverage)
- **Files**: `schemas/repository.py`, `core/repository.py`

### M4 - Profile Service

- ✅ Profile CRUD operations
- ✅ VDOT calculation from race PRs (Jack Daniels' formula)
- ✅ Training constraint validation (4 rules)
- ✅ Goal management with target dates/times
- **Tests**: 24/24 passing (90% coverage)
- **Files**: `schemas/profile.py`, `core/profile.py`

---

## Phase 2: Data Ingestion & Processing (100% ✅)

### M5 - Strava Integration

- ✅ OAuth 2.0 flow (authorization + token refresh)
- ✅ Activity sync with pagination and rate limiting
- ✅ Two-tier deduplication (primary key + fuzzy match)
- ✅ Manual activity creation (`manual_{uuid}` IDs)
- ✅ **Real data validation**: 17 activities synced successfully
- **Tests**: 28/28 passing (94% coverage)
- **Files**: `core/strava.py` (662 lines)

### M6 - Activity Normalization

- ✅ Sport type normalization (40+ Strava aliases → 13 canonical types)
- ✅ Surface detection (road/trail/treadmill) using M7
- ✅ Unit conversions (meters→km, seconds→minutes)
- ✅ Data quality assessment (HIGH/MEDIUM/LOW/TREADMILL)
- ✅ Filename generation with collision handling
- **Tests**: 25/25 passing (83% coverage)
- **Files**: `core/normalization.py` (557 lines)

### M7 - Notes & RPE Analyzer ✨ **TOOLKIT REFACTORED**

- ✅ **Refactored to toolkit paradigm** (1,142 → ~400 lines, 65% reduction)
- ✅ Returns multiple RPE estimates (HR, pace, Strava, duration)
- ✅ Treadmill detection (multi-signal scoring)
- ❌ **Removed**: Pattern extraction, conflict resolution (→ Claude Code)
- ❌ **Removed**: Injury/illness extraction (→ Claude Code via conversation)
- **Tests**: 26/26 passing (84% coverage)
- **Files**: `core/notes.py` (~400 lines)

**Key Change**: Module computes quantitative RPE estimates; Claude Code resolves conflicts using athlete context.

### M8 - Load Engine

- ✅ Two-channel load model (systemic + lower-body)
- ✅ Sport multipliers for 13 canonical sports
- ✅ Dynamic adjustments (leg day, elevation, duration, race effort)
- ✅ Session type classification (easy/moderate/quality/race)
- ✅ **Validated with real multi-sport data** (run: 301/301 AU, climb: 315/52 AU)
- **Tests**: 23/23 passing (84% coverage)
- **Files**: `core/load.py` (449 lines)

---

## Phase 3: Metrics & Analysis (100% ✅)

### M9 - Metrics Engine

- ✅ CTL calculation (42-day EWMA, α=0.024)
- ✅ ATL calculation (7-day EWMA, α=0.133)
- ✅ TSB calculation (CTL - ATL)
- ✅ ACWR calculation (7-day / 28-day ratio)
- ✅ Readiness score (weighted: TSB 20%, trend 25%, sleep 25%, wellness 30%)
- ✅ Weekly summary with 80/20 intensity distribution
- ✅ Zone classifications (CTL, TSB, ACWR, readiness levels)
- ✅ Cold start handling (<14 days baseline, <28 days ACWR)
- **Tests**: 32 unit + 4 integration = 36 tests passing (94% coverage)
- **Files**: `core/metrics.py` (979 lines), `schemas/metrics.py` (327 lines)

---

## Phase 4: Planning, Adaptation & Enrichment (100% ✅)

### M10 - Plan Toolkit ✨ **TOOLKIT REFACTORED**

- ✅ **Refactored to toolkit paradigm** (1,249 → ~600 lines, 52% reduction)
- ✅ Periodization calculations (Base/Build/Peak/Taper phases)
- ✅ Volume progression with recovery weeks (every 4th at 70%)
- ✅ Volume recommendations (CTL-based safe ranges)
- ✅ Workout creation (VDOT paces + HR zones)
- ✅ Guardrail validation (80/20, long run caps, hard/easy separation)
- ✅ Workout modification helpers (downgrade, shorten, recovery estimation)
- ❌ **Removed**: Auto-scheduling, conflict resolution, complete plan generation
- **Tests**: 51/51 passing (88% coverage)
- **Files**: `core/plan.py` (~600 lines), `schemas/plan.py` (300 lines)

**Key Change**: Provides planning tools; Claude Code designs plans workout-by-workout considering athlete schedule and context.

### M11 - Adaptation Toolkit ✨ **TOOLKIT REFACTORED**

- ✅ **Refactored to toolkit paradigm** (1,018 → 459 lines, 55% reduction)
- ✅ Trigger detection (ACWR, readiness, TSB, lower-body load, session density)
- ✅ Risk assessment (injury probability calculation)
- ✅ Recovery time estimation (days needed per trigger)
- ✅ Thresholds moved to AthleteProfile (customizable per athlete)
- ❌ **Removed**: Suggestion generation, auto-override logic, generic rationales
- **Tests**: 26/26 passing (85% coverage)
- **Files**: `core/adaptation.py` (459 lines), `schemas/adaptation.py` (330 lines)

**Key Change**: Detects triggers and assesses risk; Claude Code decides adaptations with athlete using M13 memories.

### M12 - Data Enrichment

- ✅ Metric interpretations (CTL 44 → "solid recreational level")
- ✅ Zone classifications (beginner/recreational/competitive/elite)
- ✅ Trend calculations (+2 from last week)
- ✅ Context tables for CTL, ACWR, readiness levels
- ❌ **Removed**: Generic workout rationales (→ Claude Code)
- **Tests**: 31/31 passing (87% coverage)
- **Files**: `core/enrichment.py`, `schemas/enrichment.py`

### M13 - Memory & Insights

- ✅ AI-driven memory extraction from notes/conversations
- ✅ Deduplication with confidence scoring
- ✅ Pattern detection (injury history, override preferences)
- ✅ Tag-based retrieval (body:knee, preference:morning-runs)
- ✅ Memory archival with importance decay
- **Tests**: 23/23 passing (82% coverage)
- **Files**: `core/memory.py` (562 lines), `schemas/memory.py` (158 lines)

---

## Phase 5: Toolkit Paradigm Refactoring (100% ✅)

**Duration**: 2026-01-13 (1 day)
**Goal**: Transform from "Algorithm Generator" to "Computational Toolkit"

### The Core Innovation

**Fundamental Principle**:

> Modules compute (formulas, lookups), Claude Code coaches (judgment, context, personalization)

**Decision Framework**:

- **Quantitative** (modules) → Pure math, lookup tables, deterministic logic
- **Qualitative** (Claude Code) → Pattern recognition, conflict resolution, personalization, rationale

### Implementation Complete ✅

#### 1. Schema Updates

- ✅ `schemas/activity.py`: Simplified AnalysisResult, removed flags
- ✅ `schemas/plan.py`: Added VolumeRecommendation, GuardrailViolation, PhaseAllocation, WeeklyVolume
- ✅ `schemas/adaptation.py`: Added OverrideRiskAssessment, RecoveryEstimate, AdaptationThresholds
- ✅ `schemas/profile.py`: Added AdaptationThresholds field with defaults

#### 2. M7 - Notes & RPE Analyzer Refactored

**Lines**: 1,142 → ~400 (65% reduction)

**Removed** (~800 lines):

- ❌ `resolve_rpe_conflict()` - Algorithmic conflict resolution
- ❌ `extract_injury_flags()`, `extract_illness_flags()`, `extract_wellness_indicators()`
- ❌ `RPE_KEYWORDS`, `INJURY_KEYWORDS`, `ILLNESS_PATTERNS` dictionaries
- ❌ Text-based pattern extraction

**Kept** (quantitative only):

- ✅ `estimate_rpe_from_hr()` - HR zone mapping formula
- ✅ `estimate_rpe_from_pace()` - VDOT pace zones
- ✅ `estimate_rpe_from_strava_relative()` - Suffer score normalization
- ✅ `estimate_rpe_from_duration()` - Sport + duration heuristic
- ✅ `detect_treadmill()` - Multi-signal scoring

**Result**: Returns list of RPE estimates with reasoning; Claude Code decides which to use.

#### 3. M10 - Plan Toolkit Refactored

**Lines**: 1,249 → ~600 (52% reduction)

**Removed** (~800 lines):

- ❌ `generate_master_plan()` - Complete plan generation
- ❌ `assign_workouts_to_days()` - Auto-scheduling with conflict resolution
- ❌ `_resolve_conflicts()`, `_find_best_day()` - Day selection algorithms
- ❌ Auto-enforcement of guardrails (now detects only)

**Added** (toolkit functions):

- ✅ `suggest_volume_adjustment()` - CTL-based volume recommendations
- ✅ `validate_guardrails()` - Detects violations (does NOT auto-fix)
- ✅ `validate_week()` - Single week validation
- ✅ `create_downgraded_workout()` - Workout modification helper
- ✅ `create_shortened_workout()` - Duration reduction helper
- ✅ `estimate_recovery_days()` - Recovery time estimation

**Result**: Provides planning tools; Claude Code designs plans considering athlete schedule, preferences, knee history, etc.

#### 4. M11 - Adaptation Toolkit Refactored

**Lines**: 1,018 → 459 (55% reduction)

**Removed** (~600 lines):

- ❌ `generate_adaptation_suggestions()` - Auto-suggestion generation
- ❌ `_create_suggestion()` - Proposes changes algorithmically
- ❌ `_generate_rationale()` - Template-based rationales
- ❌ `_apply_safety_override()` - Auto-modifications

**Added** (toolkit functions):

- ✅ `detect_adaptation_triggers()` - Structured trigger detection with zones
- ✅ `assess_override_risk()` - Injury probability calculation
- ✅ `estimate_recovery_time()` - Days needed per trigger type

**Refactored**:

- ✅ Moved thresholds to `AthleteProfile.adaptation_thresholds` (Claude-adjustable)
- ✅ Enhanced trigger detection with full context (value, threshold, zone, applies_to)

**Result**: Returns trigger data + risk assessment; Claude Code interprets with athlete context and decides adaptations.

#### 5. Documentation & Cleanup

- ✅ Updated `CLAUDE.md`: Added Section 5 "The Core Innovation"
- ✅ Updated module docstrings: M7, M10, M11 reflect toolkit paradigm
- ✅ Removed 7 legacy schema tests (~180 lines) - codebase hygiene
- ✅ Verified all 315 tests passing

### Impact Summary

| Module           | Before      | After       | Reduction | Tests          |
| ---------------- | ----------- | ----------- | --------- | -------------- |
| M7 (Notes)       | 1,142 lines | ~400 lines  | 65%       | 26/26 ✅       |
| M10 (Plan)       | 1,249 lines | ~600 lines  | 52%       | 51/51 ✅       |
| M11 (Adaptation) | 1,018 lines | 459 lines   | 55%       | 26/26 ✅       |
| **Total**        | 3,409 lines | 1,459 lines | **57%**   | **103/103 ✅** |

### Before vs After Examples

#### M7: RPE Conflict Resolution

**Before (Algorithm Decides)**:

```python
if is_high_intensity_session(workout_type):
    return max(hr_rpe, text_rpe)  # Trust HR
else:
    return text_rpe  # Trust user
```

**After (Claude Decides)**:

```python
# M7 returns multiple estimates
estimates = [
    RPEEstimate(7, "hr_based", "Zone 3 (78% max HR)"),
    RPEEstimate(5, "pace_based", "Easy pace for VDOT 45"),
    RPEEstimate(4, "text", "User said 'felt easy'")
]
# Claude: "HR says 7, pace says 5. High HR could be from heat/caffeine.
#          Your pace was easy for your VDOT. Trusting pace → RPE 5"
```

#### M10: Training Plan Design

**Before (Algorithm Decides)**:

```python
plan = generate_master_plan(profile, goal="half_marathon", weeks=12)
# Returns: Complete plan with workouts assigned to days
# Problem: Can't handle "I climb Tuesdays", "knee flares >18km"
```

**After (Claude Designs)**:

```python
# Claude uses toolkit conversationally
phases = calculate_periodization(12, "half_marathon")
vol_rec = suggest_volume_adjustment(35, 44, 21.1, 12)
volumes = calculate_volume_progression(35, 55, 12, [4, 8], phases)

# For each week, Claude decides:
# "You climb Tuesdays → quality Wednesday + long run Saturday"
# "Knee history → cap long runs at 18km"
workout = create_workout("tempo", 40, profile)
violations = validate_guardrails(plan, profile)
# Claude reviews violations and enforces selectively
```

#### M11: Workout Adaptation

**Before (Algorithm Decides)**:

```python
if acwr > 1.5:
    return Suggestion(type="DOWNGRADE", message="Reduce tempo to easy run")
```

**After (Claude Decides)**:

```python
triggers = detect_adaptation_triggers(workout, metrics, profile)
# Returns: [ACWR_ELEVATED(1.45), LOWER_BODY_LOAD_HIGH(340 AU)]

risk = assess_override_risk(triggers, workout, athlete_memories)
# Returns: OverrideRiskAssessment(risk="moderate", probability=0.15)

# Claude reasons with context:
# "ACWR 1.45 + climbed yesterday + knee history. Options:
#  A) Easy run (safest) B) Move to Thursday C) Proceed (15% risk)"
```

---

## Phase 6: Schemas (100% ✅)

All schema modules complete and integrated:

| Schema        | Lines | Key Models                                                  | Status |
| ------------- | ----- | ----------------------------------------------------------- | ------ |
| config.py     | 83    | AppSettings, StravaConfig, SecretsConfig                    | ✅     |
| repository.py | 37    | SchemaMetadata, LockInfo, ReadOptions                       | ✅     |
| profile.py    | 210   | AthleteProfile, Goal, TrainingConstraints, VitalSigns       | ✅     |
| activity.py   | 458   | RawActivity, NormalizedActivity, AnalysisResult             | ✅     |
| metrics.py    | 327   | DailyMetrics, CTLATLMetrics, ACWRMetrics, ReadinessScore    | ✅     |
| plan.py       | 300   | MasterPlan, WeekPlan, WorkoutPrescription, toolkit models   | ✅     |
| adaptation.py | 330   | AdaptationTrigger, OverrideRiskAssessment, RecoveryEstimate | ✅     |
| enrichment.py | ~150  | EnrichedMetrics, MetricInterpretation, context tables       | ✅     |
| memory.py     | 158   | Memory, MemoryTag, pattern models                           | ✅     |

---

## Testing Infrastructure (100% ✅)

### Unit Tests: 315 passing

| Module             | Tests   | Coverage    | Notes                       |
| ------------------ | ------- | ----------- | --------------------------- |
| M2 (Config)        | 8       | 94%         | Config loading, validation  |
| M3 (Repository)    | 18      | 95%         | Atomic writes, file locking |
| M4 (Profile)       | 24      | 90%         | CRUD, VDOT, constraints     |
| M5 (Strava)        | 28      | 94%         | OAuth, sync, deduplication  |
| M6 (Normalization) | 25      | 83%         | 40+ sport aliases           |
| M7 (Notes)         | 26      | 84%         | RPE estimation toolkit      |
| M8 (Load)          | 23      | 84%         | Two-channel model           |
| M9 (Metrics)       | 32      | 94%         | CTL/ATL/TSB/ACWR            |
| M10 (Plan)         | 51      | 88%         | Planning toolkit            |
| M11 (Adaptation)   | 26      | 85%         | Trigger detection, risk     |
| M12 (Enrichment)   | 31      | 87%         | Metric interpretations      |
| M13 (Memory)       | 23      | 82%         | AI extraction               |
| **Total**          | **315** | **88% avg** | **All passing ✅**          |

### Integration Tests: 4 passing

1. **Phase 1 E2E**: M2 → M3 → M4 pipeline
2. **Phase 2 Sync**: M5 → M6 → M7 → M8 → M9 full pipeline (17 real activities)
3. **Phase 3 Metrics**: 30-day multi-sport simulation, CTL/ATL convergence
4. **Phase 4 Planning**: M10 → M11 integration, multi-sport conflict handling

### Real Strava Data Validation ✅

**17 activities synced and processed** (last 30 days):

- 7 Rock Climbing sessions
- 5 Running sessions
- 5 Yoga sessions

**Key Validations**:

- ✅ Two-channel load model: Running (301/301 AU), Climbing (315/52 AU), Yoga (20/6 AU)
- ✅ HR data as floats: 158.1 bpm (not ints)
- ✅ User-entered RPE extraction: perceived_exertion field
- ✅ Undocumented Strava workout_type values: 28, 31
- ✅ Multi-sport metrics aggregation

---

## Remaining Work

### Phase 7: Orchestration & API (2-4 days)

#### M1 - Internal Workflows ⏳

**Purpose**: Orchestrate multi-step operations

**Functions Needed**:

- `sync_workflow()`: M5→M6→M7→M8→M9 with error handling
- `plan_workflow()`: M10 toolkit orchestration
- `adaptation_workflow()`: M11 toolkit orchestration
- `metrics_refresh_workflow()`: Recompute metrics for date range

**Estimate**: 2-3 days

#### M14 - Conversation Logger ⏳

**Purpose**: Session transcript persistence

**Functions Needed**:

- `log_message()`: Append to JSONL file
- `get_session_transcript()`: Retrieve session history
- `search_conversations()`: Query past sessions

**Estimate**: 1 day

#### API Layer (0/5 modules)

**Purpose**: Public interface for Claude Code

**Modules**:

1. `api.sync`: `sync_strava()`, `log_activity()`
2. `api.coach`: `get_todays_workout()`, `get_weekly_status()`
3. `api.metrics`: `get_current_metrics()`, `get_readiness()`
4. `api.plan`: Toolkit function exposure + `get_current_plan()`
5. `api.profile`: `get_profile()`, `update_profile()`, `set_goal()`

**Estimate**: 2 days (lightweight wrappers around modules)

### Timeline Estimate

**Remaining Effort**: ~4-6 days

- M1 Internal Workflows: 2-3 days
- M14 Conversation Logger: 1 day
- API Layer: 2 days

**After completion**: System ready for Claude Code integration and user testing

---

## Critical Path Summary

```
✅ Phase 1 (M2, M3, M4) - Infrastructure
  ↓
✅ Phase 2 (M5, M6, M7, M8) - Data Ingestion
  ↓
✅ Phase 3 (M9) - Metrics Engine
  ↓
✅ Phase 4 (M10, M11, M12, M13) - Planning, Adaptation, Enrichment, Memory
  ↓
✅ Phase 5 - Toolkit Paradigm Refactoring
  ↓
⏳ Phase 7 (M1, M14, API) - Orchestration & API
  ↓
🎯 Ready for Claude Code Integration
```

---

## Key Achievements

### Architectural Innovation ✨

- **Toolkit Paradigm**: Modules compute, Claude Code coaches
- **57% code reduction** in core modules (M7, M10, M11)
- **Qualitative reasoning → AI**: Pattern extraction, conflict resolution, plan design
- **Quantitative computation → Modules**: Formulas, lookup tables, detection

### Production Readiness ✅

- **315 tests passing** with 88% average coverage
- **Real data validated** with 17 Strava activities
- **Full pipeline operational** from sync to adaptation
- **Multi-sport awareness** throughout (two-channel load model)

### Data Quality 📊

- **Comprehensive schema validation** (9 Pydantic modules)
- **Atomic file operations** (temp + rename pattern)
- **File locking** (PID-based, cross-platform)
- **Integration testing** at every phase

---

## Notes

- **Modular architecture**: Each module independently testable
- **Test-driven**: Unit tests alongside implementation
- **Schema-first**: Pydantic models before implementation
- **Incremental progress**: Phase-by-phase validation
- **Real data testing**: Strava integration validated with actual activities
- **Clean codebase**: No dead code, legacy tests removed
- **Documentation aligned**: CLAUDE.md reflects actual implementation

---

## Version History

- **v0.1.0** (2026-01-13): Phase 5 complete, toolkit paradigm refactored in code
  - M7, M10, M11 refactored (57% code reduction)
  - 315 tests passing
  - All schemas updated
  - Documentation updated
