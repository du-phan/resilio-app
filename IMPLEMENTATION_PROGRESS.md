# Sports Coach Engine - Implementation Progress

**Version**: 0.1.0
**Last Updated**: 2026-01-13
**Status**: Phase 2 Complete & Production Ready (M7 ✅, M6 ✅, M8 ✅, M5 ✅)

---

## Overall Progress: 72%

- [x] Documentation complete & updated with real data insights
- [x] Repository structure designed
- [x] Package scaffolding created
- [x] Module implementations (7/14 complete: M2, M3, M4, M5, M6, M7, M8)
- [ ] API layer implementations (0/5 modules)
- [x] Schema definitions (4/6 modules: config, repository, profile, activity) - updated with real Strava types
- [x] Testing infrastructure (pytest configured, 107 Phase 2 tests passing)
- [x] Integration testing (verified M5→M7→M6→M8 pipeline with real Strava data)
- [x] Phase 1 end-to-end validation complete
- [x] Phase 2 complete: M7 (84%), M6 (83%), M8 (84%), M5 (94%)
- [x] Real Strava data validation: 17 activities processed (7 climbing, 5 running, 5 yoga)
- [x] Documentation aligned with actual Strava API behavior

---

## Phase 1: Core Infrastructure (100% - M2 ✅, M3 ✅, M4 ✅)

### M2 - Config & Secrets (100% ✅)

- [x] Config loading from YAML
- [x] Secret validation
- [x] Error handling for missing configs
- [ ] Environment variable support (deferred - not needed for v0)
- [ ] Token refresh (deferred to Phase 2 with M5 Strava integration)
- **Depends on**: None
- **Priority**: P0 (blocks everything)
- **Estimate**: 1 day
- **Actual**: 1 day
- **Tests**: 8/8 passing
- **Files**:
  - `sports_coach_engine/schemas/config.py` (created)
  - `sports_coach_engine/core/config.py` (implemented)
  - `tests/unit/test_config.py` (created)
  - `config/settings.yaml` (created from template)
  - `config/secrets.local.yaml` (created from template)

### M3 - Repository I/O (100% ✅)

- [x] YAML read/write with validation
- [x] Atomic write operations (temp + rename)
- [x] File locking mechanism (PID-based, cross-platform)
- [x] Path resolution
- [x] List files with glob patterns
- [ ] Schema migration support (deferred - not needed for v0)
- **Depends on**: M2
- **Priority**: P0 (blocks everything)
- **Estimate**: 2-3 days
- **Actual**: 1.5 days
- **Tests**: 18/18 passing
- **Files**:
  - `sports_coach_engine/schemas/repository.py` (created)
  - `sports_coach_engine/core/repository.py` (implemented)
  - `tests/unit/test_repository.py` (created)

### M4 - Athlete Profile Service (100% ✅)

- [x] Profile CRUD operations (load, save, update, delete)
- [x] Complete profile schema with all fields (enums, constraints, goals, preferences)
- [x] Constraint validation logic (4 validation rules per M4 spec)
- [x] VDOT calculation from race times (Jack Daniels' formula)
- [ ] Pace derivation (deferred to Phase 3 when M10 Plan Generator needs it)
- **Depends on**: M2, M3
- **Priority**: P0
- **Estimate**: 1-2 days
- **Actual Phase 1E+1F**: 3 hours total
- **Status**: Complete
- **Tests**: 24/24 passing
  - 11 CRUD tests (load, save, update, delete, validation)
  - 6 VDOT calculation tests (including time parsing)
  - 7 constraint validation tests (errors, warnings, edge cases)
- **Files**:
  - `sports_coach_engine/schemas/profile.py` (expanded with full schema)
  - `sports_coach_engine/core/profile.py` (implemented CRUD, VDOT, constraints)
  - `tests/unit/test_profile.py` (created with 24 tests)
  - `sports_coach_engine/core/repository.py` (fixed serialization: mode='json')

---

## Phase 2: Data Ingestion & Processing (100% - M7 ✅, M6 ✅, M8 ✅, M5 ✅)

### M7 - Notes & RPE Analyzer (100% ✅)

- [x] RPE estimation from HR (HR zones → RPE mapping)
- [x] RPE estimation from text (40+ keywords)
- [x] Strava suffer_score normalization
- [x] RPE conflict resolution (high-intensity uses MAX, easy trusts text)
- [x] Treadmill detection (multi-signal: sub_type, title, GPS, device)
- [x] Wellness extraction (sleep quality/hours, soreness, stress, fatigue, energy)
- [x] Injury flag detection (17 keywords, 11 body parts, severity classification)
- [x] Illness flag detection (12 patterns with rest day recommendations)
- [x] Contextual factors (fasted, heat, cold, altitude, time of day)
- **Depends on**: M3, M4
- **Priority**: P0
- **Estimate**: 2-3 days
- **Actual**: 1.5 days
- **Tests**: 31/31 passing (84% coverage)
- **Files**:
  - `sports_coach_engine/core/notes.py` (1,142 lines - complete implementation)
  - `sports_coach_engine/schemas/activity.py` (458 lines - expanded with Phase 2 models)
  - `sports_coach_engine/schemas/profile.py` (added VitalSigns model)
  - `tests/unit/test_notes.py` (621 lines, 31 comprehensive tests)

### M6 - Activity Normalization (100% ✅)

- [x] Sport type normalization (40+ Strava aliases → 13 canonical types)
- [x] Surface type detection using M7 treadmill detection
- [x] Data quality assessment (HIGH/MEDIUM/LOW/TREADMILL)
- [x] Unit conversions (meters→km, seconds→minutes)
- [x] Filename generation with collision handling
- [x] Activity validation (duration, pace, HR sanity checks)
- [x] File persistence via M3 Repository I/O
- **Depends on**: M3, M7
- **Priority**: P0
- **Estimate**: 1-2 days
- **Actual**: 1 day
- **Tests**: 25/25 passing (83% coverage)
- **Files**:
  - `sports_coach_engine/core/normalization.py` (557 lines - complete implementation)
  - `tests/unit/test_normalization.py` (489 lines, 25 comprehensive tests)
  - Sport type mapping: 40+ aliases covering running variants, cycling, strength, climbing, etc.
  - Surface detection: Multi-priority decision tree (explicit sport type → M7 detection → GPS heuristics)
  - Filename format: `activities/YYYY-MM/YYYY-MM-DD_sport_HHmm.yaml` with automatic collision handling

### M5 - Strava Integration (100% ✅)

- [x] OAuth flow implementation (manual authorization)
- [x] Token refresh logic (automatic when <5min remaining)
- [x] Fetch activities endpoint with pagination
- [x] Fetch activity details (including private notes)
- [x] Two-tier deduplication (primary key + fuzzy match)
- [x] Rate limit handling with exponential backoff (tenacity)
- [x] Error recovery (partial syncs, graceful degradation)
- [x] Manual activity creation
- [x] Strava → RawActivity mapping
- **Depends on**: M2, M3
- **Priority**: P0
- **Estimate**: 2-3 days
- **Actual**: 1.5 days
- **Tests**: 28/28 passing (94% coverage)
- **Files**:
  - `sports_coach_engine/core/strava.py` (662 lines - complete implementation)
  - `tests/unit/test_strava.py` (710 lines, 28 comprehensive tests)
  - OAuth flow: Authorization URL → Code exchange → Token refresh
  - Rate limiting: 3 retries, exponential backoff (2s-8s)
  - Deduplication: Tier 1 (source+id) → Tier 2 (fuzzy fingerprint)
  - Manual activities: Generated ID format `manual_{uuid}`

### M8 - Load Engine (100% ✅)

- [x] Base effort calculation (RPE × duration)
- [x] Systemic load calculation with sport multipliers
- [x] Lower-body load calculation with sport multipliers
- [x] Sport multiplier table (13 canonical sports)
- [x] Multiplier adjustments (leg day, elevation, long duration, race effort)
- [x] Session type classification (easy/moderate/quality/race)
- [x] Batch load computation
- [x] Load validation (sanity checks)
- **Depends on**: M3, M6, M7
- **Priority**: P0
- **Estimate**: 1-2 days
- **Actual**: 1 day
- **Tests**: 23/23 passing (84% coverage)
- **Files**:
  - `sports_coach_engine/core/load.py` (449 lines - complete implementation)
  - `tests/unit/test_load.py` (625 lines, 23 comprehensive tests)
  - Two-channel model: systemic (cardio/fatigue) + lower-body (leg impact)
  - Sport multipliers: Running (1.0,1.0), Trail (1.05,1.10), Treadmill (1.0,0.9), Cycle (0.85,0.35), Climb (0.6,0.1)
  - Dynamic adjustments: Leg day (+0.25 lower-body), High elevation (+0.05 systemic, +0.10 lower-body)

---

## Phase 2 Validation & Production Readiness ✅

### Real Strava Data Testing (2026-01-13)

**Test Scope**: 17 real activities from user's Strava account (last 30 days)

- 7 Rock Climbing sessions
- 5 Running sessions
- 5 Yoga sessions

**Full Pipeline Validation**: M5 → M7 → M6 → M8

| Activity | Duration | RPE Source         | Load (Systemic / Lower-body) | Session Type |
| -------- | -------- | ------------------ | ---------------------------- | ------------ |
| Running  | 43 min   | HR-based (158 bpm) | 301 / 301 AU                 | QUALITY      |
| Climbing | 105 min  | User input (5)     | 315 / 52 AU                  | MODERATE     |
| Yoga     | 28 min   | Duration heuristic | 20 / 6 AU                    | EASY         |

**Key Discoveries**:

- ✅ Strava returns HR as floats (158.1, 175.7) not ints - Fixed schema
- ✅ Strava uses undocumented workout_type values (28, 31) - Updated docs
- ✅ User-entered perceived_exertion properly extracted - RPE 5, 4
- ✅ Injury keywords detected in notes ("right ankle")
- ✅ Two-channel model validates correctly with real multi-sport data

**Documentation Updates**:

- Updated `m05_strava.md`: HR field types (int→float), workout_type enum (28, 31 added)
- Updated `v0_product_requirements_document.md`: HR example (158.1 instead of 158)
- Updated `CLAUDE.md`: Added real-world validation data with load calculations
- Created `STRAVA_TESTING_RESULTS.md`: Complete test report

**Files Created**:

- `oauth_helper.py` - OAuth authorization helper
- `get_strava_token.py` - Token exchange script
- `sync_strava.py` - Activity sync utility
- `test_pipeline.py` - End-to-end pipeline test
- `data_samples/` - 3 sample activities for inspection

**Status**: Phase 2 **PRODUCTION READY** - All modules validated with real data

---

## Phase 3: Metrics & Analysis (0%)

### M9 - Metrics Engine (0%)

- [ ] Daily load aggregation
- [ ] CTL calculation (42-day EWMA)
- [ ] ATL calculation (7-day EWMA)
- [ ] TSB calculation (CTL - ATL)
- [ ] ACWR calculation
- [ ] Readiness score computation
- [ ] Weekly intensity distribution
- [ ] High-intensity session counting
- [ ] Cold start handling
- **Depends on**: M3, M8
- **Priority**: P0
- **Estimate**: 2-3 days

---

## Phase 4: Planning & Adaptation (0%)

### M10 - Plan Generator (0%)

- [ ] Master plan generation
- [ ] Weekly structure by run days
- [ ] Goal-specific minimum specificity
- [ ] Periodization phases
- [ ] Conflict policy application
- [ ] Training guardrail enforcement
- [ ] Long run caps
- [ ] Intensity limits (T/I/R)
- [ ] Weekly refinement
- [ ] Goal change handling
- [ ] Reset workflows (soft/hard)
- **Depends on**: M3, M4, M9
- **Priority**: P1
- **Estimate**: 4-5 days

### M11 - Adaptation Engine (0%)

- [ ] Suggestion generation (not auto-modify)
- [ ] Adaptation triggers (ACWR, readiness, etc.)
- [ ] High lower-body load detection
- [ ] Hard session spacing checks
- [ ] Safety overrides (illness, injury)
- [ ] Conflict policy integration
- [ ] Suggestion acceptance/decline
- [ ] Adaptation logging
- [ ] Injury/illness flag duration
- **Depends on**: M3, M9, M10
- **Priority**: P1
- **Estimate**: 3-4 days

---

## Phase 5: Enrichment & UX (0%)

### M12 - Data Enrichment (0%)

- [ ] Metric interpretations (CTL → "solid recreational level")
- [ ] Zone classifications
- [ ] Trend calculations
- [ ] Workout rationale generation
- [ ] Progressive disclosure levels
- [ ] Sync summary enrichment
- [ ] Suggestion enrichment
- **Depends on**: M9, M10, M11
- **Priority**: P1
- **Estimate**: 2-3 days

### M13 - Memory & Insights (0%)

- [ ] Memory extraction from notes
- [ ] Deduplication algorithm
- [ ] Confidence scoring
- [ ] Memory archival
- [ ] Entity recognition (body parts, etc.)
- **Depends on**: M3, M7
- **Priority**: P2
- **Estimate**: 2 days

### M14 - Conversation Logger (0%)

- [ ] Session transcript persistence
- [ ] Timestamped message logging
- [ ] Markdown formatting
- **Depends on**: M3
- **Priority**: P3
- **Estimate**: 1 day

---

## Phase 6: Orchestration & API (0%)

### M1 - Internal Workflows (0%)

- [ ] Sync workflow (M5→M6→M7→M8→M9→M11→M13)
- [ ] Metrics refresh workflow
- [ ] Plan generation workflow
- [ ] Adaptation check workflow
- [ ] Manual activity workflow
- [ ] Error aggregation
- [ ] Transaction handling
- **Depends on**: All other modules
- **Priority**: P1
- **Estimate**: 2-3 days

### API Layer - Coach (0%)

- [ ] get_todays_workout()
- [ ] get_weekly_status()
- [ ] get_training_status()
- **Depends on**: M1, M12
- **Priority**: P1
- **Estimate**: 1 day

### API Layer - Sync (0%)

- [ ] sync_strava()
- [ ] log_activity()
- **Depends on**: M1
- **Priority**: P1
- **Estimate**: 1 day

### API Layer - Metrics (0%)

- [ ] get_current_metrics()
- [ ] get_readiness()
- [ ] get_intensity_distribution()
- **Depends on**: M9, M12
- **Priority**: P1
- **Estimate**: 1 day

### API Layer - Plan (0%)

- [ ] get_current_plan()
- [ ] regenerate_plan()
- [ ] get_pending_suggestions()
- [ ] accept_suggestion()
- [ ] decline_suggestion()
- **Depends on**: M10, M11
- **Priority**: P1
- **Estimate**: 1 day

### API Layer - Profile (0%)

- [ ] get_profile()
- [ ] update_profile()
- [ ] set_goal()
- **Depends on**: M4
- **Priority**: P1
- **Estimate**: 1 day

---

## Phase 7: Schemas & Data Models (0%)

### Schemas - Common (0%)

- [ ] SchemaHeader
- [ ] SchemaType enum
- [ ] MetricZone enum
- [ ] Error types
- **Priority**: P0
- **Estimate**: 0.5 day

### Schemas - Activity (0%)

- [ ] Activity base model
- [ ] NormalizedActivity
- [ ] ProcessedActivity
- [ ] ActivityLoads
- [ ] NotesAnalysis
- **Priority**: P0
- **Estimate**: 1 day

### Schemas - Profile (0%)

- [ ] AthleteProfile
- [ ] Goal
- [ ] Constraints
- [ ] VitalSigns
- [ ] PersonalRecords
- **Priority**: P0
- **Estimate**: 1 day

### Schemas - Metrics (0%)

- [ ] DailyMetrics
- [ ] EnrichedMetrics
- [ ] MetricInterpretation
- [ ] ReadinessScore
- [ ] IntensityDistribution
- **Priority**: P0
- **Estimate**: 1 day

### Schemas - Plan (0%)

- [ ] TrainingPlan
- [ ] PlanPhase
- [ ] WeeklyTarget
- [ ] Adaptation
- **Priority**: P0
- **Estimate**: 1 day

### Schemas - Workout (0%)

- [ ] WorkoutPrescription
- [ ] WorkoutRecommendation
- [ ] WorkoutRationale
- [ ] PaceGuidance
- [ ] HRGuidance
- **Priority**: P0
- **Estimate**: 1 day

---

## Phase 8: Testing & Quality (0%)

### Unit Tests (0%)

- [ ] M2 config tests
- [ ] M3 repository tests
- [ ] M7 RPE analyzer tests
- [ ] M8 load engine tests
- [ ] M9 metrics engine tests
- [ ] M10 plan generator tests
- [ ] M11 adaptation engine tests
- **Estimate**: 5-7 days

### Integration Tests (0%)

- [ ] Sync workflow end-to-end
- [ ] Plan generation → adaptation flow
- [ ] API layer integration
- **Estimate**: 3-4 days

### Fixtures & Test Data (0%)

- [ ] Sample profile
- [ ] Sample activities (3 activities)
- [ ] Sample metrics
- [ ] Sample plan
- **Estimate**: 1-2 days

---

## Critical Path

```
Phase 1 (M2, M3, M4) → Phase 2 (M5, M6, M7, M8) → Phase 3 (M9)
  → Phase 4 (M10, M11) → Phase 5 (M12) → Phase 6 (M1, API)
  → Phase 8 (Testing)
```

**Estimated Total**: 35-50 days of focused development

---

## Next Steps

### ✅ Phase 1 & 2: COMPLETE (Jan 1-13)

- [x] M2, M3, M4 (Core Infrastructure)
- [x] M5, M6, M7, M8 (Data Ingestion & Processing)
- [x] 107 Phase 2 tests passing (86% avg coverage)
- [x] Real Strava data validation (17 activities)
- [x] Documentation updated with real API insights

### ⏭️ Phase 3: Ready to Start (Week 2)

**Immediate (Next)**:

1. **Implement M9 - Metrics Engine**

   - Daily load aggregation from Phase 2 loads
   - CTL calculation (42-day EWMA)
   - ATL calculation (7-day EWMA)
   - TSB calculation (CTL - ATL)
   - ACWR calculation (7-day / 28-day)
   - Readiness score computation
   - Dependency: M8 (load data)
   - Estimate: 2-3 days

2. **Define Metrics Schemas**

   - DailyMetrics (CTL, ATL, TSB, ACWR, readiness)
   - MetricInterpretation (contextual meanings)
   - ReadinessScore (0-100 with factors)

3. **M9 Testing**
   - Unit tests with real load data
   - Validation of EWMA calculations
   - Edge cases (cold start, gaps)
   - Estimate: 1 day

### Short-term (Week 3-4):

- Implement M10 (Plan Generator)
- Implement M11 (Adaptation Engine)
- Schema definitions for plans and adaptations

### Mid-term (Week 5+):

- Implement M12 (Data Enrichment)
- Implement M1 (Internal Workflows)
- Implement API layer (5 modules)
- Complete testing suite

---

## Notes

- **Modular approach**: Each module can be developed and tested independently
- **Test-driven**: Write unit tests alongside implementation
- **Schema-first**: Define Pydantic schemas before implementing modules
- **Incremental**: Start with simplest modules (M2, M3) and build up
- **Documentation**: Keep module docstrings aligned with specs

---

## Risks & Mitigations

### Risk: Strava API rate limits

**Mitigation**: Implement exponential backoff, cache activities locally

### Risk: Data corruption from concurrent access

**Mitigation**: File locking in M3, atomic writes, backup system

### Risk: Cold start edge cases

**Mitigation**: Comprehensive testing with fixture data at different history lengths

### Risk: Schema evolution breaking old data

**Mitigation**: Schema versioning + migration system in M3

```

---

## Phase 5: Testing Infrastructure

### 5.1 Test Directory Structure

```

tests/
├── **init**.py
├── conftest.py # Pytest fixtures
├── unit/
│ ├── **init**.py
│ ├── test_config.py # M2 tests
│ ├── test_repository.py # M3 tests
│ ├── test_profile.py # M4 tests
│ ├── test_strava.py # M5 tests
│ ├── test_normalization.py # M6 tests
│ ├── test_notes.py # M7 tests
│ ├── test_load.py # M8 tests
│ ├── test_metrics.py # M9 tests
│ ├── test_plan.py # M10 tests
│ ├── test_adaptation.py # M11 tests
│ └── test_enrichment.py # M12 tests
├── integration/
│ ├── **init**.py
│ ├── test_sync_workflow.py
│ ├── test_plan_workflow.py
│ └── test_api_layer.py
└── fixtures/
├── profile_sample.yaml
├── activity_run.yaml
├── activity_climb.yaml
├── metrics_sample.yaml
└── plan_sample.yaml

```

```
