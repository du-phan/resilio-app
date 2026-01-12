# Sports Coach Engine - Implementation Progress

**Version**: 0.1.0
**Last Updated**: 2026-01-12
**Status**: Phase 2 Data Ingestion - In Progress (M7 ✅)

---

## Overall Progress: 50%

- [x] Documentation complete
- [x] Repository structure designed
- [x] Package scaffolding created
- [x] Module implementations (4/14 complete: M2, M3, M4, M7)
- [ ] API layer implementations (0/5 modules)
- [x] Schema definitions (4/6 modules: config, repository, profile, activity)
- [x] Testing infrastructure (pytest configured, 81 tests passing)
- [x] Integration testing (verified M7↔M4 integration)
- [x] Phase 1 end-to-end validation complete
- [x] Phase 2 M7 complete with 84% test coverage

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

## Phase 2: Data Ingestion & Processing (25% - M7 ✅)

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

### M6 - Activity Normalization (0%)

- [ ] Sport type normalization
- [ ] Unit conversions
- [ ] Surface type detection (treadmill)
- [ ] Data quality flags
- [ ] Schema enforcement
- **Depends on**: M3, M7
- **Priority**: P0
- **Estimate**: 1-2 days

### M5 - Strava Integration (0%)

- [ ] OAuth flow implementation
- [ ] Token refresh logic
- [ ] Fetch activities endpoint
- [ ] Activity deduplication
- [ ] Rate limit handling
- [ ] Error recovery
- **Depends on**: M2, M3
- **Priority**: P0
- **Estimate**: 2-3 days

### M8 - Load Engine (0%)

- [ ] Base effort calculation (RPE × duration)
- [ ] Systemic load calculation
- [ ] Lower-body load calculation
- [ ] Sport multipliers application
- [ ] Workout-type adjustments
- [ ] Session type classification
- **Depends on**: M3
- **Priority**: P0
- **Estimate**: 1-2 days

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

1. **Immediate (Week 1)**:

   - Implement M2 (Config)
   - Implement M3 (Repository I/O)
   - Define common schemas
   - Set up testing infrastructure

2. **Short-term (Week 2-3)**:

   - Implement M4 (Profile Service)
   - Implement M5 (Strava Integration)
   - Implement M6-M8 (Activity processing pipeline)
   - Define activity schemas

3. **Mid-term (Week 4-5)**:

   - Implement M9 (Metrics Engine)
   - Implement M10 (Plan Generator)
   - Define metrics and plan schemas

4. **Long-term (Week 6-8)**:
   - Implement M11 (Adaptation Engine)
   - Implement M12 (Data Enrichment)
   - Implement M1 (Workflows)
   - Implement API layer
   - Complete testing

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
