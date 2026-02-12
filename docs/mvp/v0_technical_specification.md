# v0 Technical Specification — Resilio (Running-First, Multi‑Sport Aware)

**Status:** Draft  
**Last Updated:** March 2026  
**Scope:** Technical spec that operationalizes `docs/mvp/v0_product_requirements_document.md` for implementation later.

---

## 1. Goals (v0)

- Provide a local, file-backed running coach that is **multi-sport aware** (other sports influence fatigue/readiness and scheduling).
- Keep architecture **clean and modular** so methodology can evolve without rewriting storage and core workflows.
- Support a user-defined conflict policy: when running and the primary sport collide, **the user decides what wins** (explicitly or via a profile setting).
- Enforce evidence-based training guardrails (intensity balance, long-run caps, spacing of hard sessions).

## 2. Non-Goals (v0)

- No web UI, no hosted backend, no database server.
- No “perfect physiology model”: v0 uses simple heuristics that are robust for multi-sport athletes.
- No automatic background sync; Strava sync is triggered intentionally by the user.

---

## 3. System Overview

### 3.1 Primary Workflows

1. **Setup**
   - Create athlete profile.
   - Configure Strava connection (required for v0).
2. **Sync / Log Training**
   - Pull activities from Strava (manual logging deferred to future versions).
   - Normalize activities into YAML files.
3. **Compute Metrics**
   - Compute daily loads (systemic + lower-body).
   - Compute CTL/ATL/TSB and systemic ACWR.
4. **Plan + Adapt**
   - Generate a running plan from goal + constraints.
   - Adapt upcoming workouts based on metrics, injury flags, and conflict policy.
5. **Coach Conversation**
   - Provide a “what should I do today?” answer with a specific workout prescription, plus explanation tied to the athlete’s data.

### 3.2 Design Principles

- **Separation of concerns**
  - Storage/filesystem concerns are isolated from training logic.
  - Training load computation is isolated from plan generation.
  - Adaptation is rule-based and transparent.
- **Deterministic core**
  - Given the same inputs, the computed outputs should be stable and explainable.
- **Auditability**
  - Every adaptation writes an entry describing “what changed and why”.

---

## 4. Modular Architecture (v0)

This section organizes v0 features into **clean modules** with explicit responsibilities,
inputs/outputs, and data ownership. The goal is to keep the system maintainable and
easy to evolve while avoiding overengineering.

### 4.0 Claude Code as Interface

**Architectural Decision:** Claude Code (the AI) is the user interface. The package provides an **API layer** (`resilio/api/`) that Claude Code calls. This means:

- **Claude Code handles:** Intent understanding, conversation management, response formatting
- **Package provides:** Callable Python functions that return rich, structured data
- **No keyword-based intent parsing:** Claude naturally understands user intent

```
┌─────────────────────────────────────────────────────────────────┐
│                         Claude Code                              │
│  (Intent understanding, conversation, response formatting)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ calls
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Layer (PUBLIC)                            │
│  resilio.api.*                                       │
│  - sync_strava(), get_todays_workout(), get_current_metrics()    │
│  - Returns: EnrichedWorkout, SyncSummary, EnrichedMetrics        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ calls internally
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Internal Modules (M1-M13)                       │
│  Pure domain logic, no intent parsing, no prose generation       │
└─────────────────────────────────────────────────────────────────┘
```

See `docs/specs/api_layer.md` for full API documentation.

### 4.1 Module Map (v0)

| Module ID | Name                    | Code Path              | Primary Responsibility                               | Owned Data                 |
| --------- | ----------------------- | ---------------------- | ---------------------------------------------------- | -------------------------- |
| API       | API Layer               | `api/*.py`             | Public interface for Claude Code                     | None                       |
| M1        | Internal Workflows      | `core/workflows.py`    | Orchestrate multi-step operations                    | None                       |
| M2        | Config & Secrets        | `core/config.py`       | Read/validate settings and secrets                   | `config/` files            |
| M3        | Repository I/O          | `core/repository.py`   | Read/write YAML/JSON, atomic writes                  | All persisted files        |
| M4        | Athlete Profile Service | `core/profile.py`      | CRUD for profile + preferences                       | `athlete/profile.yaml`     |
| M5        | Strava Integration      | `core/strava.py`       | Import activities from Strava + manual logging       | None                       |
| M6        | Activity Normalization  | `core/normalization.py`| Normalize sport types, units, structure              | `activities/` (normalized) |
| M7        | Notes & RPE Analyzer    | `core/notes.py`        | Extract RPE, soreness, wellness, red flags           | Derived fields in activity |
| M8        | Load Engine             | `core/load.py`         | Compute systemic + lower-body loads                  | Derived fields in activity |
| M9        | Metrics Engine          | `core/metrics.py`      | Compute CTL/ATL/TSB/ACWR, readiness                  | `metrics/`                 |
| M10       | Plan Generator          | `core/plan.py`         | Build plan/workouts with guardrails                  | `plans/`                   |
| M11       | Adaptation Engine       | `core/adaptation.py`   | Apply rules to adjust workouts                       | `plans/`                   |
| M12       | Data Enrichment         | `core/enrichment.py`   | Add interpretive context to raw data                 | None                       |
| M13       | Memory & Insights       | `core/memory.py`       | Extract durable athlete facts                        | `athlete/memories.yaml`    |

#### Initialization Sequence (Cold Start)

When an athlete first connects with no training history, the system must handle the "cold start" gracefully:

1. **If `metrics/daily/` is empty (new user):**

   - M10 generates plan assuming CTL = 0, ATL = 0, TSB = 0
   - Use conservative defaults: lower volume, no high-intensity sessions in first week
   - Set `baseline_established: false` in `athlete/training_history.yaml`

2. **After first 8–12 weeks of history is imported (Strava sync or manual logging):**

   - Recompute CTL/ATL/TSB (M9) with actual historical data
   - Set `baseline_established: true`
   - Regenerate plan with adjusted volume/intensity (M10)
   - Notify user: "I now have enough training history to calibrate your plan. I'm adjusting upcoming workouts based on your actual fitness."

3. **ACWR Safeguard:**

   - If 28-day average systemic load = 0: ACWR is undefined (do NOT divide by zero)
   - Skip ACWR-based adaptations until at least 28 days of data exist
   - Rely on readiness score and conservative defaults during this bootstrap period

4. **Lower-body load threshold fallback:**
   - If < 14 days of data: use absolute threshold (300 AU) instead of relative threshold
   - See Section 9.2 for full threshold specification

### 4.2 Module Contracts (Responsibilities + Interfaces)

Each module has a narrow, testable contract. Modules do **not** mutate each other’s data directly.
All persistence flows through `M3 Repository I/O`.

#### M1 — Internal Workflows

**Responsibilities**

- Orchestrate multi-step operations by chaining modules
- Coordinate transactional operations (rollback on failure)
- Handle inter-module data flow (output of M5 feeds M6 feeds M7...)

**Note:** M1 is an **internal module** called by the API layer. Claude Code does NOT call M1 directly—it calls API functions (`sync_strava()`, `get_todays_workout()`, etc.) which delegate to M1 workflows internally.

**What M1 Does NOT Do:**

- Intent parsing (Claude Code handles this naturally)
- Response formatting (Claude Code handles this conversationally)
- User interaction (the API layer handles this)

**Inputs**

- Repository instance
- Config object (from M2)
- Parameters from API layer

**Outputs**

- Structured workflow results (`SyncWorkflowResult`, `MetricsRefreshResult`, etc.)
- These are enriched by M12 before returning to Claude Code

**Key Workflows**

| Workflow | Pipeline | Called by API |
| -------- | -------- | ------------- |
| `run_sync_workflow()` | M5 → M6 → M7 → M8 → M9 → M11 → M13 | `api.sync.sync_strava()` |
| `run_metrics_refresh()` | M9 → M11 | `api.metrics.get_current_metrics()` |
| `run_plan_generation()` | M4 → M9 → M10 | `api.plan.regenerate_plan()` |
| `run_adaptation_check()` | M9 → M10 → M11 | `api.coach.get_todays_workout()` |

**Depends on**

- M2, M3, M4, M5, M6, M7, M8, M9, M10, M11, M12, M13

See `docs/specs/modules/m01_workflows.md` for full specification.

#### Cross-Cutting Concerns (Validation & Resilience)

- **Schema validation:** Every read/write should validate against the expected shape (required keys, enum values). Fail fast with a helpful error that points to the offending file path.
- **Atomic writes:** Always write to a temp file then rename; never leave half-written YAML. Prefer idempotent operations (e.g., activity ingestion keyed by id+date).
- **Graceful degradation:** If Strava is unreachable, allow manual logging and note the partial state; do not block plan/metrics computation.
- **Defaults and clamps:** Apply safe defaults for missing optional fields (e.g., RPE fallback, conservative multipliers) and clamp calculated values to sane ranges.
- **Testable fixtures:** Provide small fixture sets (profile, 3 activities) to regression-test M6–M9 and adaptation rules without calling Strava.

#### M2 — Config & Secrets

**Responsibilities**

- Load `config/settings.yaml` and `config/secrets.local.yaml`.
- Validate required keys; return explicit error messages for missing secrets.

**Inputs**

- Config files + env vars

**Outputs**

- Validated config object

**Owns**

- `config/` files (read-only for most flows)

#### M3 — Repository I/O

**Responsibilities**

- Centralized read/write for YAML/JSON files.
- Path resolution and directory creation.
- Atomic writes to prevent partial files.

**Inputs**

- File paths + data objects

**Outputs**

- Persisted files on disk

**Failure modes**

- Invalid YAML → surface to caller
- Missing directories → create

#### M4 — Athlete Profile Service

**Responsibilities**

- Create/update profile fields.
- Enforce required fields and default values.
- Store conflict policy and constraints.
- Validate constraints for logical consistency.

**Inputs**

- Profile updates (partial)

**Outputs**

- Updated `athlete/profile.yaml`

**Constraint Validation Rules**

On profile save, M4 must validate:

| Validation                                                      | Action                                                                                                                            |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `max_run_days < min_run_days`                                                | Error: "Max run days cannot be less than min run days"                                                                            |
| `available_days = 7 - len(unavailable_run_days)` is `< min_run_days`             | Warning: "Insufficient available run days to meet min_run_days_per_week. Consider adjusting constraints."                         |
| `len(unavailable_run_days) = 7` AND `goal.type ≠ general_fitness`                | Error: "Cannot create a race-focused plan with all days unavailable. Remove some unavailable days or switch to general_fitness goal."     |
| All `available_days` are consecutive (e.g., Sat+Sun only)                     | Warning: "Back-to-back run days detected. Plan will enforce hard/easy separation (one day must be easy)."                         |

**Depends on**

- M3

#### M5 — Strava Integration

**Responsibilities**

- Strava sync (manual trigger, idempotent)
- Manual activity logging (user-provided)
- Update sync state (`last_strava_sync_at`, `last_strava_activity_id`)
- Handle Strava OAuth token refresh

**Inputs**

- Strava API payloads OR user input

**Outputs**

- Raw activity objects (in-memory) passed to M6
- Updated `athlete/training_history.yaml` sync fields

**Depends on**

- M2 (secrets), M3 (persistence)

**Integration with API Layer**

This module is called internally by M1 workflows. Claude Code should NOT import from `core/strava.py` directly.

```
Claude Code → api/sync.py::sync_strava() → M1::run_sync_workflow() → M5::fetch_activities()
```

**Strava API Limitations:**

- **Best Efforts/PRs**: Available via `best_efforts` field in DetailedActivity, but requires fetching each activity individually (rate-limited). No dedicated PR/best-effort endpoint.
- **Strategy**: Ask users for PRs at onboarding; build `best_efforts` cache incrementally from synced activities.
- **Race Detection**: `workout_type=1` indicates race (undocumented field, values 0-3 for running). Many users don't tag races.
- **Strategy**: Check `workout_type=1` as signal; also parse descriptions for race keywords ("race", "5K", "PB", "PR").

See `docs/specs/modules/m05_strava.md` for full specification.

#### M6 — Activity Normalization

**Responsibilities**

- Normalize sport types and units.
- Derive core fields (date, duration, distance).
- Enforce activity schema shape.
- Set `surface_type` based on M7 detection results.
- Set `data_quality` fields based on surface type and GPS availability.

**Inputs**

- Raw activity objects
- Treadmill detection result from M7

**Outputs**

- Normalized activity objects persisted to `activities/`
- Includes `surface_type`, `surface_type_confidence`, and `data_quality` fields

**Depends on**

- M3, M7

#### M7 — Notes & RPE Analyzer

**Responsibilities**

- Extract perceived effort, soreness, sleep, and injury/illness/overtraining flags from notes.
- Provide RPE estimate when HR data is missing.
- Detect treadmill/indoor runs from activity metadata (title, description, GPS absence).
- Extract wellness indicators and contextual factors.

**Inputs**

- `description` / `private_note`
- Activity `name` (title)
- GPS polyline availability
- Device metadata (sport_type, indoor flag)

**Outputs**

- `estimated_rpe`, wellness flags, injury/illness flags
- Treadmill detection result: `(is_treadmill: bool, confidence: "high"|"low", signals: list)`

**Depends on**

- M3 (for activity read/write)

#### M8 — Load Engine

**Responsibilities**

- Compute `base_effort_au`, `systemic_load_au`, `lower_body_load_au`.
- Apply default multipliers + minimal workout-type adjustments.
- Assign `session_type` from sport/sub_type + RPE.

**Inputs**

- Normalized activity + `estimated_rpe`

**Outputs**

- `calculated.*` fields in activity file

**Depends on**

- M3

#### M9 — Metrics Engine

**Responsibilities**

- Aggregate daily systemic/lower-body loads.
- Compute CTL/ATL/TSB and systemic ACWR.
- Compute readiness score + confidence.
- Compute weekly intensity distribution (low/moderate/high).
- Compute `high_intensity_sessions_7d` across all sports.

**Inputs**

- Activity loads

**Outputs**

- `metrics/daily/*.yaml`
- `metrics/weekly_summary.yaml`

**Depends on**

- M3

#### M10 — Plan Generator

**Responsibilities**

- Generate plan + workouts from goal/constraints.
- Enforce training guardrails (intensity balance, long-run caps, T/I/R volume).
- Respect conflict policy and run-day constraints.

**Inputs**

- Athlete profile
- Constraints + goal

**Outputs**

- `plans/current_plan.yaml`
- `plans/workouts/...`

**Depends on**

- M3

#### M11 — Adaptation Engine

**Responsibilities**

- Generate adaptation **suggestions** based on metrics and flags.
- Protect recovery by preventing stacked hard sessions.
- Respect `conflict_policy`.
- Log all suggestions and their outcomes for auditability.

**Inputs**

- Plan + workouts
- Metrics + readiness + intensity distribution
- Injury/illness flags / lower-body load thresholds

**Outputs**

- Suggestion objects written to `plans/pending_suggestions.yaml`
- Updated plan/workouts (only after user accepts suggestion or safety override)
- Adaptation log entries

**Depends on**

- M3, M4, M9, M10

#### M11 Adaptation Philosophy: Suggest, Don't Auto-Modify

M11 generates **suggestions** rather than directly modifying the plan. This ensures:

- **Plan stability:** No "churn" with each sync—the plan is a stable reference
- **Athlete autonomy:** User decides what changes to accept
- **Transparency:** All suggestions visible with rationale in `pending_suggestions.yaml`

**Core Functions:**

| Function                                                | Purpose                                         |
| ------------------------------------------------------- | ----------------------------------------------- |
| `generate_adaptation_suggestions(metrics, plan, flags)` | Analyze current state, return `Suggestion[]`    |
| `apply_suggestion(suggestion_id)`                       | Called when user accepts; modifies workout file |
| `decline_suggestion(suggestion_id)`                     | Logs decline; plan unchanged                    |
| `expire_stale_suggestions()`                            | Runs on each sync; marks expired suggestions    |

**Suggestion Generation Flow:**

```
On sync completion:
1. M9 provides current metrics (CTL, ATL, TSB, ACWR, readiness)
2. M11.generate_adaptation_suggestions() evaluates triggers
3. For each triggered condition → create Suggestion object
4. Write to plans/pending_suggestions.yaml
5. M12 presents pending suggestions to user
```

**Safety-Critical Exceptions (auto-apply with notification):**

Some conditions are too dangerous to await user approval. These auto-apply immediately but notify the user:

| Condition                            | Auto-Action              | User Can Override?       |
| ------------------------------------ | ------------------------ | ------------------------ |
| Injury flag detected in notes        | Force rest day           | Yes, with warning        |
| ACWR > 1.5 AND readiness < 35        | Auto-downgrade intensity | Yes, with strong warning |
| Illness flag (fever, chest symptoms) | Force rest 48-72h        | No (safety)              |

**Override Workflow:**

If user overrides a safety suggestion:

1. Log override with timestamp
2. Show warning: "I strongly recommend rest. Proceeding with [workout] increases injury risk."
3. Add `user_override: true` flag to workout execution
4. Track for pattern analysis (repeated overrides → memory insight)

**Conflict Policy + Safety Override Priority:**

When multiple concerns apply, resolve in this order:

1. **Safety overrides** (illness, injury) → always apply, bypass conflict policy
2. **ACWR > 1.5** → apply with notification, bypass conflict policy
3. **All other triggers** → respect conflict policy setting
   - If `ask_each_time`: present suggestion and wait for response
   - If `primary_sport_wins` or `running_goal_wins`: apply policy logic

#### M12 — Data Enrichment

**Responsibilities**

- Add interpretive context to raw metric values (CTL=44 → "solid recreational level")
- Provide training zone classifications ("safe", "productive", "high_risk")
- Calculate trends and deltas with context
- Enrich workout prescriptions with rationale and guidance
- Return structured data models with interpretive fields

**Note:** M12 does NOT generate prose or formatted text. It returns **structured data** that Claude Code uses to craft natural responses.

**Inputs**

- Raw metrics from M9
- Raw workout prescriptions from M10
- Historical data for trend calculation

**Outputs**

- `EnrichedMetrics` — metrics with interpretations and zones
- `EnrichedWorkout` — workout with rationale and current context
- `SyncSummary` — sync result with metric changes
- Other enriched data models

**Depends on**

- M3, M9, M10, M11

**Integration with API Layer**

This module is called by the API layer to enrich workflow results before returning to Claude Code.

```
M1 Workflow returns: DailyMetrics (raw numbers)
        │
        ▼
API Layer calls: enrich_metrics(raw_metrics)
        │
        ▼
M12 returns: EnrichedMetrics (numbers + interpretations)
        │
        ▼
API Layer returns to Claude Code: EnrichedMetrics
        │
        ▼
Claude Code crafts: Natural conversational response
```

**Key Enrichment Functions:**

- `enrich_metrics()` — Add context to CTL/ATL/TSB/ACWR/readiness
- `enrich_workout()` — Add rationale and guidance to workout prescription
- `enrich_sync_result()` — Summarize sync with metric changes
- `interpret_metric()` — Get zone and interpretation for a single metric

**Example Enriched Data:**

```python
# EnrichedMetrics returned to Claude Code
{
    "ctl": {
        "value": 44,
        "formatted_value": "44",
        "zone": "recreational",
        "interpretation": "solid recreational level",
        "trend": "+2 from last week"
    },
    "tsb": {
        "value": -8,
        "formatted_value": "-8",
        "zone": "productive",
        "interpretation": "productive training zone",
        "trend": None
    },
    "disclosure_level": "intermediate",  # Progressive disclosure
    "low_intensity_percent": 82.5,
    "intensity_on_target": True
}
```

See `docs/specs/modules/m12_enrichment.md` for full specification.

#### M13 — Memory & Insights

**Responsibilities**

- Extract durable, athlete-specific facts from activity notes and user messages.
- Write new memories or update existing ones with confidence and provenance.

**Inputs**

- Activity notes + user messages (relevant snippets)

**Outputs**

- Updated `athlete/memories.yaml`

**Depends on**

- M3, M7

**Memory Extraction Algorithm (v0):**

1. **TRIGGER:** After each activity note analysis (M7) and after each user message

2. **EXTRACTION PATTERNS:**

   - **injury_history:** keywords (pain, tight, sore, injured, hurts) + body part → type: injury_history
   - **preference:** explicit statements ("I prefer...", "I like...", "morning works best") → type: preference
   - **context:** training background, life situation, sport-specific facts → type: context
   - **insight:** patterns observed over multiple sessions → type: insight
   - **training_response:** how athlete handles specific stimuli → type: training_response

3. **DEDUPLICATION (Concrete Algorithm v0):**

   Memory deduplication uses deterministic matching (no fuzzy/semantic matching in v0):

   **Step 1: Exact Match Check**

   - Normalize: lowercase, collapse whitespace, strip punctuation
   - If new memory content matches existing memory content → UPDATE existing (don't create)

   **Step 2: Type + Entity Match**

   - If same `type` AND same key entity mentioned:
     - `injury_history`: same body part (knee, ankle, calf, etc.) → UPDATE
     - `preference`: same topic (time-of-day, intensity, workout-type) → UPDATE
     - `context`: same subject (job, family, sport commitment) → UPDATE
   - Entity extraction: simple keyword matching against predefined lists

   **Step 3: Recency Rule**

   - If conflicting information (same type+entity but different content):
     - Newer memory supersedes older
     - Archive old memory with `superseded_by: <new_memory_id>`

   **Step 4: No Match**

   - If neither exact match nor type+entity match → create new memory

   **Entity Lists (v0):**

   - Body parts: knee, ankle, calf, shin, hip, hamstring, quad, achilles, foot, back, shoulder
   - Time preferences: morning, evening, afternoon, lunch, early, late
   - Intensity topics: easy, hard, tempo, intervals, long run, recovery

4. **CONFIDENCE SCORING:**

   - `high`: Explicit statement or consistent pattern (3+ occurrences)
   - `medium`: Inferred from single clear instance
   - `low`: Inferred from ambiguous text

5. **ARCHIVAL:**
   - If new memory contradicts existing: archive old with `superseded_by` reference
   - Keep archived memories for 90 days, then delete

### 4.3 Workflow Data Flow (v0)

**Sync flow**

1. M1 → M2 (config) → M5 (Strava) → M6 (normalize) → M7 (RPE) → M8 (load)
2. M13 updates memories if new durable facts are found
3. M9 recomputes daily metrics
4. M11 applies adaptations if triggered
5. M12 summarizes results

**"What should I do today?" flow**

1. M1 reads profile + plan (M3/M4/M10)
2. M9 computes current status (if stale)
3. M11 checks if adaptation needed
4. M12 renders today's workout + rationale

### 4.4 Transaction Model (v0)

The sync pipeline (M5→M9) involves multiple file writes that must succeed or fail together. v0 uses a simple transaction model to prevent partial writes:

**Sync Transaction Boundary:**

```
1. BEGIN: Acquire write lock on activities/, metrics/, plans/
2. M5: Fetch activities from Strava (network I/O)
3. M6: Normalize all activities in memory (no disk writes yet)
4. M7: Extract RPE and flags in memory
5. M8: Calculate loads in memory
6. M9: Compute metrics in memory
7. COMMIT: Write all files atomically (temp file + rename for each)
8. RELEASE: Release lock
9. ON FAILURE at any step: Discard all in-memory changes; no partial writes
```

**Single-Workout Transaction:**

For updates to individual workouts (e.g., user skips a workout):

- Smaller scope: lock only the affected workout file + daily metrics for that date
- Same temp-file-then-rename pattern

**Lock Implementation (v0 Simplified):**

- Use a lockfile (`config/.sync_lock`) with PID and timestamp
- If lock exists and is < 5 minutes old: wait or abort
- If lock exists and is ≥ 5 minutes old: assume stale, break and acquire
- All M3 writes must check lock before proceeding

**Lock Retry Strategy (v0):**

```
1. Attempt to acquire lock
2. If lock held by another process (PID valid AND lock < 5 min old):
   - Wait 2 seconds
   - Retry (max 3 retries = 6 seconds total wait)
   - On failure after retries: abort with message
     "Another sync in progress. Try again in a moment."
3. If lock stale (> 5 min old OR PID not running):
   - Log warning: "Breaking stale lock from PID {pid}"
   - Delete lock file
   - Acquire new lock
4. Always release lock in finally block (even on error)
```

**Lock File Format:**

```yaml
pid: 12345
acquired_at: "2025-03-15T10:30:00Z"
operation: "sync" # sync | plan_update | workout_update
```

**Idempotency Guarantee:**

Re-running sync with the same date range produces identical state. This is ensured by:

- Activity deduplication by `(source, id)`
- Metric recomputation from activity files (not deltas)
- Adaptation rules are deterministic given inputs

---

## 5. Repository File Layout (v0)

This spec assumes the file layout described in the PRD. v0 adds a key privacy constraint:

- `config/secrets.local.yaml` contains tokens/credentials and must **not** be committed.

Recommended layout:

```
config/
  settings.yaml
  secrets.local.yaml          # ignored by VCS

athlete/
  profile.yaml
  memories.yaml
  training_history.yaml

activities/YYYY-MM/*.yaml

metrics/daily/YYYY-MM-DD.yaml
metrics/weekly_summary.yaml

plans/current_plan.yaml
plans/archive/*.yaml
plans/workouts/week_##/*.yaml
```

---

## 6. Data Model & Schemas (v0)

v0 uses YAML for human readability and easy diffing.

### 6.0 Schema Versioning (All File Types)

All persisted YAML files must include a schema header for future migration support:

```yaml
_schema:
  format_version: "1.0.0" # Semantic versioning
  schema_type: "activity" # activity|profile|daily_metrics|plan|workout|memories|training_history
```

**Migration Rules:**

- On read, M3 must check `format_version` and apply migrations if schema is outdated
- If file version is newer than supported code version: fail with clear error
- If file has no `_schema` field: assume version "0.0.0" and migrate to current
- Migrations must be idempotent (safe to run multiple times)

**Version History (v0):**

| Version | Date    | Changes          |
| ------- | ------- | ---------------- |
| 1.0.0   | Initial | v0 launch schema |

### 6.1 Athlete Profile (`athlete/profile.yaml`)

**Required (minimum)**

- `name: str`
- `created_at: date`
- `running_priority: enum(primary|secondary|equal)`
- `primary_sport: str`
- `conflict_policy: enum(primary_sport_wins|running_goal_wins|ask_each_time)`
- `constraints.unavailable_run_days: list[weekday]`
- `constraints.min_run_days_per_week: int`
- `constraints.max_run_days_per_week: int`
- `goal.type: enum(5k|10k|half_marathon|marathon|general_fitness)`

**Optional (recommended)**

- `injury_history: str`
- `age: int` (for recovery guidance)
- PRs + VDOT estimate fields + `vdot_last_updated`
- `recent_race` (distance, time, date for current fitness)
- `current_weekly_run_km: float`
- `current_run_days_per_week: int`
- `preferences.intensity_metric: enum(pace|hr|rpe)`
- `other_sports[]` commitments
- `vital_signs.max_hr: int` - maximum heart rate
- `vital_signs.resting_hr: int` - baseline resting heart rate
- `vital_signs.lthr: int` - lactate threshold heart rate
- `vital_signs.lthr_method: enum(field_test|race_derived|estimated)`
- `derived_paces{}` - cached VDOT-derived training paces (see PRD for structure)

### 6.2 Training History (`athlete/training_history.yaml`)

**Required**

- `last_strava_sync_at: datetime`
- `last_strava_activity_id: str`

**Optional**

- `baseline.ctl: float`
- `baseline.atl: float`
- `baseline.tsb: float`
- `baseline.period_days: int`

### 6.3 Activity File (`activities/YYYY-MM/YYYY-MM-DD_<sport>_<HHmm>.yaml`)

**File Naming Convention (Updated):**

To prevent filename collisions when multiple activities occur on the same day:

```
Format: YYYY-MM-DD_<sport_type>_<HHmm>.yaml

Examples:
- 2025-11-05_run_1230.yaml      (run at 12:30)
- 2025-11-05_run_1830.yaml      (run at 18:30)
- 2025-11-05_climb_1900.yaml    (climb at 19:00)

Fallback (if no start_time):
- 2025-11-05_run_1.yaml         (first run of day)
- 2025-11-05_run_2.yaml         (second run of day)
```

**Collision Handling:**

- If exact filename exists: check if same activity (by id) → update; else append index
- On Strava sync: use `start_date_local` to extract time
- On manual log: require start_time or auto-assign based on creation order

**Required**

- `id: str` (Strava id or local id)
- `source: enum(strava|manual)`
- `sport_type: str` (normalized primary sport)
- `date: date`
- `duration_minutes: int`

**Optional**

- `distance_km: float`
- `average_hr/max_hr/has_hr_data`
- `description/private_note`
- `surface_type: enum(road|track|trail|grass|treadmill|mixed)` - running surface (optional)

**Derived fields (computed)**

- `calculated.estimated_rpe: int (1..10)`
- `calculated.base_effort_au: float` (`estimated_rpe * duration_minutes`)
- `calculated.systemic_multiplier: float`
- `calculated.lower_body_multiplier: float`
- `calculated.systemic_load_au: float`
- `calculated.lower_body_load_au: float`
- `calculated.session_type: enum(easy|moderate|quality|race)` # drives intensity distribution

### 6.4 Daily Metrics (`metrics/daily/YYYY-MM-DD.yaml`)

**Required**

- `date: date`
- `activities[]` each with `systemic_load_au` and `lower_body_load_au`
- `systemic_daily_load_au: float`
- `lower_body_daily_load_au: float`

**Derived**

- `ctl, atl, tsb` (computed from `systemic_daily_load_au`)
- `acwr` (systemic ACWR computed from systemic loads)
- `readiness.score` + `readiness.confidence`

### 6.5 Weekly Summary (`metrics/weekly_summary.yaml`)

**Required**

- `week_start: date`
- `week_end: date`
- `total_systemic_load_au: float` # actual
- `total_lower_body_load_au: float` # actual

**Optional**

- `run_sessions: int`
- `key_sessions_completed: int`
- `intensity_distribution: { low_minutes: float, moderate_minutes: float, high_minutes: float }`
- `high_intensity_sessions_7d: int` # across all sports
- `notes: str`

### 6.6 Plan (`plans/current_plan.yaml`) and Workouts (`plans/workouts/...`)

**Plan file (key additions)**
No special additions required in v0 beyond what the PRD already defines. The source of truth is the workout files under `plans/workouts/`.

**Workout file (key additions)**

- `status: enum(scheduled|completed|skipped|adapted)`
- `execution.{actual_activity_id, actual_duration_minutes, actual_distance_km, average_hr, average_pace_min_km, session_rpe, pain_flag, execution_notes}`
- `coach_review: str`

### 6.7 Coach Memories (`athlete/memories.yaml`)

**Required**

- `memories[]` list with:
  - `id: str`
  - `type: str`
  - `content: str`
  - `source: str`
  - `created_at: date`
  - `confidence: enum(low|medium|high)`

**Optional**

- `archived[]` list with:
  - `id: str`
  - `content: str`
  - `superseded_by: str`
  - `archived_at: date`

### 6.9 Load Multipliers Configuration

**Location:** Hardcoded in M8 (Load Engine) for v0. Future versions may move to `config/multipliers.yaml` for user customization.

**Default Multipliers:** See PRD Section 1 "Default Multipliers (v0)" table.

#### Unknown Sport Handling

When an activity has a `sport_type` not in the multiplier table:

1. **Apply conservative fallback:** `{ systemic: 0.70, lower_body: 0.30 }`
2. **Log a warning:** "Unknown sport '{sport_type}'; using conservative multipliers."
3. **Ask user in next conversation (if a key run follows):**
   "I classified your '{sport_type}' activity with conservative load estimates. Was it:
   A) Mostly cardio/full-body (like rowing, skiing)
   B) Mostly upper-body (like kayaking, rock climbing)
   C) Leg-heavy (like skating, skiing with lots of turns)
   This helps me count it correctly toward your fatigue."

**Known sport aliases to normalize:**

- "indoor_cycling" → "cycling"
- "virtual_ride" → "cycling"
- "rock_climb" / "indoor_climb" → "climbing"
- "walk" → "walking"
- "hike" → "hiking"
- "crossfit" / "functional_fitness" → "crossfit"

### 6.10 Pending Suggestions (`plans/pending_suggestions.yaml`)

The Pending Suggestions queue stores adaptation recommendations that await user approval. This supports the "Suggest, Don't Auto-Modify" philosophy where the plan remains stable until the user explicitly accepts changes.

**Schema:**

```yaml
_schema:
  format_version: "1.0.0"
  schema_type: "pending_suggestions"

pending_suggestions:
  - id: str # "sugg_YYYY-MM-DD_NNN" (e.g., "sugg_2025-03-15_001")
    created_at: datetime
    trigger: str # acwr_elevated | low_readiness | high_lower_body | injury_flag | hard_session_cap
    trigger_value: float # The metric value that triggered (e.g., ACWR=1.42)
    affected_workout:
      file: str # "week_03/tuesday_tempo.yaml"
      date: date
    suggestion_type: str # downgrade | skip | move | substitute
    original:
      type: str # e.g., "tempo"
      duration_minutes: int
      intensity: str # e.g., "moderate"
    proposed:
      type: str # e.g., "easy"
      duration_minutes: int
      intensity: str # e.g., "low"
    rationale: str # Human-readable explanation
    status: str # pending | accepted | declined | expired
    expires_at: datetime
    user_response: str | null # Optional user comment on accept/decline
    response_at: datetime | null
```

**Status Transitions:**

- `pending` → `accepted` (user approves via M1)
- `pending` → `declined` (user rejects via M1)
- `pending` → `expired` (`expires_at` passed without response)

**Expiration Rules:**

- Suggestions expire at end of the affected workout's scheduled date (23:59 local)
- On each sync, M11 runs `expire_stale_suggestions()` to clean up
- Expired suggestions are logged for analytics but not shown to user

**Trigger Types:**

| Trigger            | Condition                                      | Typical Suggestion           |
| ------------------ | ---------------------------------------------- | ---------------------------- |
| `acwr_elevated`    | ACWR > 1.3                                     | Downgrade intensity or skip  |
| `low_readiness`    | Readiness < 50                                 | Reduce duration or intensity |
| `high_lower_body`  | Lower-body load > threshold before quality run | Move or substitute           |
| `injury_flag`      | Pain/injury detected in notes                  | Force rest or easy-only      |
| `hard_session_cap` | 2+ hard sessions in 7 days                     | Downgrade to easy            |

**Deduplication:**

- Only one pending suggestion per workout file at a time
- If new trigger fires for same workout: update existing suggestion (don't create duplicate)
- Track original suggestion ID in `superseded_by` if replaced

---

## 7. Load & Fatigue Computation (v0)

### 7.1 RPE Estimation

RPE sources, in priority order:

1. Explicit user RPE (`strava_perceived_exertion`, if present)
2. HR-based estimate (if reliable HR present)
3. Text-based estimate from notes (keywords + workout description)
4. Strava relative effort normalization (if present)
5. Sport + duration heuristic fallback

For short intervals or hill reps, prefer RPE over HR (HR lags).

#### RPE Conflict Resolution

When multiple sources provide conflicting RPE estimates (differ by >2 points):

**Resolution Priority (in order):**

1. **Explicit user RPE always wins** (they entered it intentionally in Strava via `perceived_exertion` field)

   - If present: use this value; ignore all other estimates

2. **If no explicit user RPE, determine if session is high-intensity:**

   - High-intensity indicators: HR > 85% of `vital_signs.max_hr` OR `sub_type ∈ {intervals, tempo, race}` OR keywords in notes (intervals, tempo, threshold, race-pace)
   - If high-intensity: use `MAX(HR-based, text-based)` RPE
   - If NOT high-intensity: use text-based RPE (HR may be elevated by heat, dehydration, stress)

3. **If spread > 3 points after step 2:**
   - Use `MAX(all estimates)` as the final RPE (conservative = higher load)
   - Log warning: "RPE estimates differ significantly; using conservative value"
   - Flag for user clarification in next conversation

**"Conservative" Definition:**

- Conservative = MAX (not average, not median)
- Rationale: Overestimating load is safer than underestimating (prevents overtraining)

**Example:**

- HR-based estimate: RPE 5 (moderate)
- Text-based estimate: RPE 8 ("hard", "challenging", "tired after")
- Spread: 3 points → conflict detected
- Session type from notes: intervals (high-intensity indicator)
- Resolution: MAX(5, 8) = RPE 8 (trust text since notes explicitly describe difficulty)

#### Treadmill-Specific RPE Estimation

For activities where `surface_type == "treadmill"`, modify the standard RPE priority to account for unreliable pace data:

**Modified priority for treadmill runs:**

1. Explicit user RPE (`strava_perceived_exertion`) — unchanged, always wins
2. HR-based estimate — **elevated priority** (most reliable for treadmill)
3. Strava relative effort (suffer_score) — **elevated priority** (HR-derived)
4. Text-based estimate from notes
5. Duration heuristic (conservative default: RPE 6)

**Key differences:**

- **Skip pace-based RPE estimation entirely** for treadmill runs (pace is unreliable)
- **Prioritize HR over text** when both available (reverse of outdoor logic for non-high-intensity)
- If no HR data and no text signals: default to RPE 6 (moderate effort assumption)

**Rationale:**
Treadmill pace/distance derives from accelerometer algorithms with 5-15% variance. Heart rate remains a reliable effort indicator regardless of surface, making it the primary signal for treadmill sessions.

### 7.2 Two-Channel Load Model

For each activity:

- `base_effort_au = estimated_rpe * duration_minutes`
- `systemic_load_au = base_effort_au * systemic_multiplier`
- `lower_body_load_au = base_effort_au * lower_body_multiplier`

**Multiplier defaults** are defined in the PRD and should be centralized in one place (e.g., a config map), so they can evolve without changing schemas.

**Strength/CrossFit rule (v0, minimal):**

- Default multipliers assume "mixed" stimulus.
- If notes clearly indicate lower-body dominance, bump `lower_body_multiplier`.
- If notes clearly indicate upper-body dominance, reduce `lower_body_multiplier`.
- If unclear and a key run is imminent, ask the athlete.

**Treadmill multiplier adjustment:**

For running activities where `surface_type == "treadmill"`:

- `systemic_multiplier = 1.00` (unchanged - cardio effort is equivalent)
- `lower_body_multiplier = 0.90` (10% reduction for reduced impact)

**Rationale:** Treadmill belts absorb ~10% of impact force compared to road/track running. This reduces lower-body stress while maintaining aerobic stimulus. The adjustment helps accurately model treadmill's role as a lower-impact training option for multi-sport athletes.

### 7.3 CTL/ATL/TSB (Systemic)

- `ctl` and `atl` are computed from **systemic** daily loads only.
- `lower_body` is used as a **compatibility constraint**, not as fitness.

### 7.4 Intensity Distribution (80/20)

- Use `calculated.session_type` and RPE to bucket time into low/moderate/high.
- Track weekly totals in `metrics/weekly_summary.yaml`.
- For athletes running >= 3 days/week, target ~80% low intensity and <= 20% moderate+high within running time.
- Track `high_intensity_sessions_7d` across all sports for global fatigue gating.

---

## 8. Planning Method (v0)

### 8.1 Weekly Structure by Run Days

v0 uses the PRD table; the key case is **2 runs/week**:

- 1 long/aerobic session (anchor)
- 1 quality session (goal-specific)

### 8.2 Goal-Specific “Minimum Specificity”

This is the minimum weekly running stimulus needed to progress with low run frequency:

- `general_fitness`: aerobic run; optional strides
- `5k`: speed/VO2 stimulus every 7–10 days
- `10k`: threshold stimulus weekly
- `half_marathon`: long run weekly + threshold/HM-specific work weekly
- `marathon`: supported, but warn if < 3 run days/week

### 8.3 Conflict Policy (User-Defined)

When a plan decision conflicts with the athlete's primary sport or reality:

- `primary_sport_wins`: adjust running first.
- `running_goal_wins`: preserve key running sessions unless injury risk is high.
- `ask_each_time`: present options with trade-offs and ask.

#### Conflict Policy Application During Plan Generation

| Policy               | Plan Generation Behavior                                                                                                                                            |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `primary_sport_wins` | If athlete reports a conflict, keep primary sport and mark running as unavailable on those days, then reschedule runs within remaining days.                       |
| `running_goal_wins`  | Protect key running workouts (long run, quality run). If conflicts arise, suggest moving or pausing other sports.                                                    |
| `ask_each_time`      | Generate plan assuming ideal running days. When conflicts arise at runtime, ask user to choose and update unavailable run days as needed.                            |

### 8.4 Goal Change Mid-Plan

When `athlete.goal` changes (type, target_date, or target_time):

1. **Archive current plan:**

   ```
   plans/archive/plan_<old_goal>_<timestamp>.yaml
   ```

2. **Calculate new timeline:**

   - If new goal has a specific `race_target_date`: count backwards for periodization
   - If `race_target_date` is < 4 weeks away: warn user that timeline is very short for optimal prep

3. **Cutover timing (Partial Week Handling):**

   **If goal changes on Monday-Wednesday:**

   - New plan starts THIS Monday (retroactive adjustment of current week)
   - Mark already-completed workouts as "completed (old goal)"
   - Adjust remaining days of current week to match new plan

   **If goal changes on Thursday-Sunday:**

   - New plan starts NEXT Monday (complete current week as-is)
   - No changes to current week; old plan remains active until Sunday

   **Edge case - Last Day of Current Plan:**

   - If today is the LAST DAY of current plan (race day):
   - Archive immediately
   - New plan starts tomorrow if Monday, else next Monday

4. **Notify user:**
   "Your goal changed from {old_goal} to {new_goal}. I've archived your previous plan and generated a fresh one starting [date]."

5. **Do NOT delete old workouts** until new plan is ready (user can compare if needed)

### 8.5 Training Guardrails (v0)

- Long run caps: <= 25-30% of weekly run volume and <= 2.5 hours.
- Limit quality sessions to 2 per 7 days across all sports.
- Avoid back-to-back high-intensity days; keep at least 1 easy day between.
- VDOT updates no more than every 3-4 weeks, or after a new race.
- **Treadmill exclusion:** Activities where `surface_type == "treadmill"` are EXCLUDED from VDOT recalculation and personal record updates (pace data is unreliable for fitness assessment).
- Apply running pace/zone prescriptions only to running; other sports use RPE/HR/time guidance.
- Cross-training can replace aerobic stimulus but not running economy/impact tolerance.

### 8.6 Two-Tier Plan Architecture (v0)

v0 uses a two-tier approach to balance long-term visibility with weekly adaptability:

**Tier 1: Master Plan (generated at onboarding or goal change)**

- Covers all weeks from start to goal date
- Contains:
  - Periodization phases (base → build → peak → taper)
  - Weekly volume progression
  - Workout types per week (e.g., "1 long run, 1 tempo, 2 easy")
  - Recovery week scheduling (typically every 3-4 weeks)
- Purpose: Athlete visibility into the full training journey
- Generated by: M10 during initial setup or goal change
- Stored in: `plans/current_plan.yaml` (meta) + `plans/workouts/week_##/` (workout files)

**Tier 2: Weekly Refinement (at week boundary)**

- Takes pre-planned structure for next week from Master Plan
- Refines specific details based on current state:
  - Adjust pace targets if fitness improved (higher CTL)
  - Reduce duration if fatigue accumulated (negative TSB)
  - Swap days if schedule changed (user request)
  - Add recovery elements if ACWR elevated
- **STRUCTURE stays consistent** with Master Plan
- **DETAILS adapt** to current reality
- Triggered by: Sunday sync (proactive offer) OR explicit request ("plan next week")
- Generated by: M10 with M9 metrics input

**Weekly Refinement Workflow:**

```
End of week (Sunday sync or explicit request):
1. M9 generates weekly summary (what was completed, CTL delta, ACWR)
2. M10 reads Master Plan week_N+1 structure
3. M10 refines: adjust paces, durations, intensity based on current metrics
4. M12 presents refined week to user: "Here's next week based on how training went"
5. User confirms OR requests adjustments
6. M3 writes refined workout files
```

**Refinement Rules:**

| Condition                        | Refinement Action                                   |
| -------------------------------- | --------------------------------------------------- |
| `execution_rate < 80%`           | Reduce next week volume by 10%                      |
| `CTL_delta > 3` (fitness gain)   | Can increase intensity slightly                     |
| `ACWR > 1.3`                     | Cap intensity at moderate; no quality sessions      |
| Missed quality session this week | Offer to add quality elements to long run (if safe) |
| `TSB < -25` (deep fatigue)       | Reduce volume by 15%; prioritize easy runs          |

**Master Plan Regeneration Triggers:**

The Master Plan is regenerated (not just refined) when:

- Goal changes (distance, race date, goal time)
- Major injury requiring 2+ weeks off
- User explicitly requests "new plan" or "reset"

### 8.7 Reset Workflows (v0)

v0 supports three levels of reset to handle different scenarios:

#### 8.7.1 Goal Change (preserves data)

**Use case:** Athlete changes race distance, goal time, or race date.

**Workflow:**

1. Archive current plan to `plans/archive/YYYY-MM-DD_goal_change/`
2. Update `athlete/profile.yaml` with new goal
3. M10 generates new Master Plan using existing CTL/ATL/TSB
4. Preserve all activities, metrics, and memories

**Data preserved:** Everything (activities, metrics, memories, profile)

#### 8.7.2 Soft Reset (new training block)

**Use case:** Athlete returning after long break, wants fresh start but same identity.

**Workflow:**

1. Archive current plan to `plans/archive/YYYY-MM-DD_soft_reset/`
2. Keep `athlete/profile.yaml` and `athlete/memories.yaml` (same athlete)
3. Keep `athlete/training_history.yaml` and recent activities/metrics intact
4. M10 generates a fresh plan using existing history (favoring recent weeks)

**Data preserved:** Profile, memories, activities, metrics
**Data archived:** Plan only

**Trigger phrases:** "start fresh", "new training block", "returning after break"

#### 8.7.3 Hard Reset (new athlete)

**Use case:** Different person using the system, or complete clean slate.

**Workflow:**

1. Delete all data directories: `athlete/`, `activities/`, `metrics/`, `plans/`, `state/`
2. Re-initialize data directory structure
3. Return to Scenario 1 (new user setup flow)
4. Requires explicit double-confirmation

**Data preserved:** None
**Data removed:** Everything (no archival)

**Confirmation requirement:**

```
Coach: This will delete ALL your data and start completely fresh.
       Your training history, memories, and profile will be removed
       with no backup. Type "confirm hard reset" to proceed.
User: confirm hard reset
Coach: Done. Let's start fresh. What's your name?
```

**Trigger phrases:** "hard reset", "new athlete", "different person", "start over completely"

---

## 9. Adaptation Rules (v0)

v0 adaptation is rule-based, explainable, and conservative:

### 9.1 Key Inputs

- `systemic_acwr` + `ctl/atl/tsb`
- `readiness.score` + confidence
- `lower_body_daily_load_au` (yesterday and 2–3 day trend)
- injury/illness flags extracted from notes
- weekly intensity distribution and recent high-intensity count

### 9.2 High Lower-Body Load (Definition)

v0 uses a tiered threshold system to handle both established and new athletes:

#### Tier 1: Sufficient History (≥14 days of data)

```
high_lower_body = yesterday_lower_body_au > 1.5 × median(lower_body_daily_load last 14 days)
```

#### Tier 2: Insufficient History (<14 days of data)

```
high_lower_body = yesterday_lower_body_au > 300 AU
```

(300 AU is a conservative absolute threshold, e.g., RPE 6 × 50 min or RPE 5 × 60 min)

#### Sport-Adjusted Thresholds

| Condition                                                                                  | Threshold Adjustment                                   |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| `primary_sport` is leg-dominant (climbing with high heel hooks, cycling, CrossFit, skiing) | +20% threshold (they're accustomed to higher leg load) |
| `running_priority = "primary"`                                                             | -10% threshold (protect running more aggressively)     |

#### Cumulative Window Check (v0 Enhancement)

To catch consecutive moderate-load days that compound fatigue, also check the 3-day rolling average:

```
rolling_3d = (day0_lower_body + day1_lower_body + day2_lower_body) / 3
If rolling_3d > 1.3 × median(14d): trigger adaptation
```

#### Threshold Evaluation Order (Precise)

Evaluate thresholds in this order; stop on first trigger:

```
1. Check single-day threshold (Tier 1 or Tier 2):
   - If ≥14 days data: yesterday_lower_body_au > 1.5 × median(14d) → TRIGGER
   - If <14 days data: yesterday_lower_body_au > 300 AU → TRIGGER

2. Check cumulative threshold:
   - If ≥14 days data: rolling_3d_avg > 1.3 × median(14d) → TRIGGER
   - If <14 days data: rolling_3d_avg > 250 AU → TRIGGER

3. Apply sport adjustment BEFORE comparison:
   - Leg-dominant primary sport (cycling, climbing, CrossFit): threshold × 1.2
   - Running is primary sport: threshold × 0.9

4. Trigger condition: ANY check fires → adaptation triggered
   (These are OR conditions, not AND)
```

**Example:**

- Athlete: bouldering primary, 14 days history, median lower_body = 150 AU
- Yesterday lower_body = 240 AU
- Base threshold = 1.5 × 150 = 225 AU
- Sport adjustment: +20% → 270 AU
- Is 240 > 270? No → do NOT trigger adaptation (athlete is accustomed to this load)

**Edge Case: Tier Transition**

- When data crosses from 13 to 14 days: use Tier 1 from day 14 onward
- No retroactive recalculation; thresholds apply going forward

### 9.3 Adaptation Outcomes

- For a scheduled **key** workout:
  - Prefer to move 24–48 hours before downgrading, unless injury flags are present.
  - If systemic ACWR is high or readiness is very low, downgrade (don’t “force” it).
  - If 2+ high-intensity sessions occurred in the last 7 days, move or downgrade.
- For non-key workouts:
  - Remove or convert to easy without guilt.

Every adaptation must write:

- `original`
- `adapted_to`
- `reason` (metrics + notes)
- `conflict_policy_applied` (if relevant)

### 9.4 Workout Execution Assessment (Treadmill Handling)

When assessing whether a completed activity met the prescribed workout (for compliance tracking and adaptation decisions):

**Standard assessment (outdoor runs):**

- Duration compliance: Compare actual vs prescribed duration
- Pace zone compliance: Compare actual pace vs prescribed pace zones
- HR zone compliance: Compare actual HR vs prescribed HR zones (if HR data available)
- Overall compliance: Derive from all three metrics

**Treadmill-specific assessment:**

For activities where `surface_type == "treadmill"`:

| Metric    | Assessment Method                                          | Confidence  |
| --------- | ---------------------------------------------------------- | ----------- |
| Duration  | Compare actual vs prescribed                               | High        |
| HR zone   | Compare actual HR vs prescribed HR zones (if HR available) | High        |
| Pace zone | Mark as `"unverifiable_treadmill"`                         | N/A         |
| Overall   | Derive from duration + HR only (exclude pace)              | Medium-High |

**Rationale:** Treadmill pace data is unreliable (5-15% variance) and should not be used to assess workout execution. Heart rate remains the primary effort indicator for treadmill sessions.

**Coach feedback template:**

```
For treadmill tempo run:
"Your treadmill tempo session:
- Duration: 30 min ✓ (prescribed: 30 min)
- Heart rate: Avg 165 bpm ✓ (tempo zone: 160-170 bpm)
- Pace: 5:10/km displayed (treadmill calibration varies; using HR as primary indicator)

Overall: Good execution—HR confirms you hit tempo effort correctly."
```

### 9.5 Injury/Illness Flag Duration (v0)

When M7 detects injury or illness signals from activity notes, the system applies protective constraints. This section defines how long those constraints remain active.

#### Injury Flag

**Detection triggers:** Keywords like "pain", "injured", "hurts", "strain", "pulled" + body part

**Duration:** 3 days from detection OR until user explicitly reports improvement

**Constraints while active:**

- Readiness score capped at 25 (easy runs only)
- Quality sessions blocked
- Auto-suggestion: "I noticed you mentioned [injury]. Taking it easy for a few days."

**User override:** Allowed with warning

```
User: "I want to do my tempo run anyway"
Coach: "I recommend rest given your [knee pain]. Running through pain can
        extend recovery time. If you proceed, I'll note this as an override.
        Do you want to continue with the tempo run?"
```

**Clearing the flag:**

- User says: "feeling better", "pain is gone", "it's fine now", "cleared to run"
- M13 creates memory: "Recovered from [injury] on [date]"
- Readiness returns to calculated value

#### Illness Flag

**Detection triggers:** Keywords like "sick", "fever", "flu", "cold", "chest congestion", "covid"

**Duration:** 48-72 hours minimum from detection (based on severity)

| Severity                                  | Duration                     | Override?         |
| ----------------------------------------- | ---------------------------- | ----------------- |
| Mild (cold, sniffles)                     | 48 hours                     | Yes, with warning |
| Moderate (fever, flu-like)                | 72 hours                     | No                |
| Severe (chest symptoms, breathing issues) | Until user confirms recovery | No                |

**Constraints while active:**

- Readiness score capped at 20 (force rest)
- ALL training blocked (not just quality)
- Auto-message: "Rest is critical when sick. Exercise while ill can prolong recovery and has cardiac risks."

**Cannot override (safety):**

- Fever or chest symptoms require mandatory rest
- User must wait for flag expiration OR explicitly confirm recovery

**Clearing the flag:**

- Flag auto-expires after duration
- OR user confirms: "fever gone", "feeling much better", "recovered"
- For severe: require explicit "I'm fully recovered and ready to train"

#### Flag State Storage

Flags are stored in `metrics/daily/YYYY-MM-DD.yaml`:

```yaml
flags:
  injury:
    active: true
    body_part: "left_knee"
    detected_at: "2025-03-15T10:30:00Z"
    expires_at: "2025-03-18T10:30:00Z"
    source: "activity_note" # activity_note | user_message
  illness:
    active: false
    severity: null
    detected_at: null
    expires_at: null
```

---

## 10. Strava Integration (v0)

The PRD defines the endpoints and manual sync flow.

v0 additional constraints:

- Tokens/credentials are read from `config/secrets.local.yaml` (or environment variables).
- The sync process must be idempotent: re-running sync should not duplicate activity files.

### 10.1 Activity Deduplication

**Primary Key:** `(source, id)`

- Strava activities: `(source="strava", id=strava_activity_id)`
- Manual activities: `(source="manual", id=generated_uuid)`

**On Sync:**

1. Check if `activities/YYYY-MM/` contains a file with matching `(source, id)`
2. If found AND Strava's `updated_at` matches local file: **skip** (no changes)
3. If found AND Strava's `updated_at` is newer: **update** local file (user re-edited in Strava)
4. If not found: **create** new activity file

**Fallback Key** (if `id` is missing or corrupted): `(date, sport_type, start_time ±30min, duration_minutes ±5min)`

**Fallback Matching Rules:**

- If multiple activities match fallback key: DO NOT auto-merge; ask user to confirm
- Source precedence if forced to choose: Strava > manual (Strava has more accurate data)
- Warn user: "Found a similar activity by date/time/duration. Is this the same session? [Y/N]"
- Log all fallback matches for debugging: `config/.dedup_warnings.log`

**Idempotency Guarantee:** Re-running sync with the same date range produces identical state.

**Track Last Sync Timestamp:**

- Update `athlete/training_history.yaml` with `last_strava_sync_at` after successful sync
- On next sync, fetch only activities since `last_strava_sync_at` (reduces API calls)

### 10.2 Strava Sync Error Handling

**Transaction Model:**

1. Fetch activity list (cheap API call)
2. For each new activity, fetch full details including `private_note` (expensive)
3. Collect all activities in memory (do NOT write yet)
4. Write all files in single batch to `activities/`
5. Update `training_history.yaml` with `last_strava_sync_at` ONLY after all writes succeed

**On Failure:**

| Failure Type                       | Action                                                                  |
| ---------------------------------- | ----------------------------------------------------------------------- |
| API timeout during fetch           | Retry up to 2× with exponential backoff (2s, 4s), then abort            |
| Strava rate limit (429)            | Wait for `Retry-After` header duration, then retry once                 |
| Partial write failure (disk error) | Roll back all files written in this sync batch                          |
| Token expired (401)                | Attempt token refresh; if refresh fails, prompt user to re-authenticate |

**Critical:** Never update `last_strava_sync_at` on failure. This ensures next sync will retry the same range.

**User Message on Failure:**
"Strava sync failed. Your existing data is safe. Please try again in a moment, or check your internet connection."

---

## 11. Prompting / "AI Coach" Integration (v0)

This spec assumes the coaching agent can read/write the repository files.

Minimum prompt inputs for “What should I do today?”:

- Athlete profile summary (goal, constraints, conflict_policy)
- Last 7 days of activities (systemic + lower-body summary)
- Current metrics (systemic CTL/ATL/TSB/ACWR, readiness)
- Weekly intensity distribution + high-intensity count
- Next scheduled workout(s)

Minimum prompt outputs:

- Workout prescription (time/distance, intensity guidance)
- If adapted: explicit "changed X → Y because …"
- One question if a key ambiguity blocks the decision (e.g., "Was yesterday's CrossFit leg-heavy?")

---

## 12. Data Integrity (v0)

### 12.1 Integrity Checks

On startup (before any operation):

1. **Parse Validation:** Validate all YAML files parse correctly
2. **Required Fields:** Flag files with missing required fields (warn, don't block)
3. **Staleness Check:** Warn if metrics are >24h older than latest activity
4. **Schema Version:** Check `_schema.format_version` on all files; migrate if needed

**Integrity Report Format:**

```
[INFO] Validated 47 files
[WARN] metrics/daily/2025-11-10.yaml missing 'readiness' field
[WARN] Metrics stale by 36 hours; recommend running sync
[OK] All files pass schema validation
```

### 12.2 Corruption Recovery

If a YAML file is corrupted (won't parse):

1. For activity files: offer to re-fetch from Strava (if source=strava)
2. For metrics files: delete and recompute from activities
3. For plans/workouts: regenerate plan and workouts from current profile
4. For profile/memories: prompt user to re-enter critical fields
   - For metrics files: regenerate from activities
   - For plan files: warn user; may need to regenerate plan
4. Log corruption event to `config/.corruption_log`
