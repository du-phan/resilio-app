# v0 Technical Specification — Sports Coach Engine (Running-First, Multi‑Sport Aware)

**Status:** Draft  
**Last Updated:** January 2026  
**Scope:** Technical spec that operationalizes `docs/mvp/v0_product_requirements_document.md` for implementation later.

---

## 1. Goals (v0)

- Provide a local, file-backed running coach that is **multi-sport aware** (other sports influence fatigue/readiness and scheduling).
- Keep architecture **clean and modular** so methodology can evolve without rewriting storage and core workflows.
- Support a user-defined conflict policy: when running and the primary sport collide, **the user decides what wins** (explicitly or via a profile setting).

## 2. Non-Goals (v0)

- No web UI, no hosted backend, no database server.
- No “perfect physiology model”: v0 uses simple heuristics that are robust for multi-sport athletes.
- No automatic background sync; Strava sync is triggered intentionally by the user.

---

## 3. System Overview

### 3.1 Primary Workflows

1. **Setup**
   - Create athlete profile.
   - Configure Strava (optional).
2. **Sync / Log Training**
   - Pull activities from Strava and/or log manual activities.
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

### 4.1 Module Map (v0)

| Module ID | Name | Primary Responsibility | Inputs | Outputs | Owned Data |
| --------- | ---- | ---------------------- | ------ | ------- | ---------- |
| M1 | CLI / Conversation Orchestrator | Interpret user intent and orchestrate workflows | User command, config | Console response, module calls | None |
| M2 | Config & Secrets | Read/validate settings and secrets | `config/` files, env vars | Config object | `config/` files |
| M3 | Repository I/O | Read/write YAML/JSON, resolve paths, ensure atomic writes | File paths, data objects | Persisted files | All persisted files |
| M4 | Athlete Profile Service | CRUD for profile + preferences + conflict policy | Profile updates | `athlete/profile.yaml` | `athlete/profile.yaml` |
| M5 | Activity Ingestion | Import activities (Strava + manual) | Strava data / user input | Raw activity objects + sync state update | None |
| M6 | Activity Normalization | Normalize sport types, units, structure | Raw activity objects | Normalized activity objects | `activities/` (normalized) |
| M7 | Notes & RPE Analyzer | Extract RPE, soreness, wellness signals | Activity notes | Estimated RPE + flags | Derived fields in activity |
| M8 | Load Engine | Compute systemic + lower-body loads | Normalized activity + RPE | `calculated.*` fields | Derived fields in activity |
| M9 | Metrics Engine | Compute daily/weekly metrics | Activity loads | `metrics/daily/*.yaml`, summary | `metrics/` |
| M10 | Plan Generator | Build plan/workouts from goal + constraints | Profile + constraints | `plans/current_plan.yaml`, workouts | `plans/` |
| M11 | Adaptation Engine | Apply rules to adjust workouts | Plan + metrics + flags | Updated plan/workouts + logs | `plans/` |
| M12 | Coach Response Formatter | Render outputs for the user | Plan + metrics + context | Console responses | None |
| M13 | Memory & Insights | Extract durable athlete facts | Activity notes + conversation snippets | Updated memories | `athlete/memories.yaml` |
| M14 | Conversation Logger | Persist session transcripts | User/coach messages | Markdown logs | `conversations/` |

### 4.2 Module Contracts (Responsibilities + Interfaces)

Each module has a narrow, testable contract. Modules do **not** mutate each other’s data directly.
All persistence flows through `M3 Repository I/O`.

#### M1 — CLI / Conversation Orchestrator

**Responsibilities**
- Parse user intent (sync, log activity, show plan, ask for today’s workout).
- Invoke the minimal set of modules to fulfill the request.
- Handle user confirmation questions (e.g., conflict policy set to `ask_each_time`).

**Inputs**
- User text input
- Config object (from M2)

**Outputs**
- Human-readable response (via M12)
- Module calls to M4–M11

**Depends on**
- M2, M3, M4, M5, M6, M7, M8, M9, M10, M11, M12, M13, M14

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

**Inputs**
- Profile updates (partial)

**Outputs**
- Updated `athlete/profile.yaml`

**Depends on**
- M3

#### M5 — Activity Ingestion

**Responsibilities**
- Strava sync (manual trigger, idempotent).
- Manual activity logging (user-provided).
- Update sync state (`last_strava_sync_at`, `last_strava_activity_id`).

**Inputs**
- Strava API payloads OR user input

**Outputs**
- Raw activity objects (in-memory) passed to M6
- Updated `athlete/training_history.yaml` sync fields

**Depends on**
- M2 (secrets), M3 (persistence)

#### M6 — Activity Normalization

**Responsibilities**
- Normalize sport types and units.
- Derive core fields (date, duration, distance).
- Enforce activity schema shape.

**Inputs**
- Raw activity objects

**Outputs**
- Normalized activity objects persisted to `activities/`

**Depends on**
- M3

#### M7 — Notes & RPE Analyzer

**Responsibilities**
- Extract perceived effort, soreness, sleep, and injury flags from notes.
- Provide RPE estimate when HR data is missing.

**Inputs**
- `description` / `private_note`

**Outputs**
- `estimated_rpe`, wellness flags, injury flags

**Depends on**
- M3 (for activity read/write)

#### M8 — Load Engine

**Responsibilities**
- Compute `base_effort_au`, `systemic_load_au`, `lower_body_load_au`.
- Apply default multipliers + minimal workout-type adjustments.

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
- Apply adaptation rules based on metrics and flags.
- Respect `conflict_policy`.
- Log adaptations for auditability.

**Inputs**
- Plan + workouts
- Metrics + readiness
- Injury flags / lower-body load thresholds

**Outputs**
- Updated plan/workouts + adaptation log entries

**Depends on**
- M3, M4, M9, M10

#### M12 — Coach Response Formatter

**Responsibilities**
- Render concise, actionable responses in terminal.
- Explain the “why” using metrics and the athlete’s context.

**Inputs**
- Plan + metrics + recent activities

**Outputs**
- User-facing output text

**Depends on**
- M3, M9, M10, M11

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

#### M14 — Conversation Logger

**Responsibilities**
- Persist conversation sessions for auditability and context.
- Store timestamps + role-tagged messages.

**Inputs**
- User and coach messages for a session

**Outputs**
- `conversations/YYYY-MM-DD_session.md`

**Depends on**
- M3

### 4.3 Workflow Data Flow (v0)

**Sync flow**
1. M1 → M2 (config) → M5 (Strava) → M6 (normalize) → M7 (RPE) → M8 (load)
2. M13 updates memories if new durable facts are found
3. M9 recomputes daily metrics
4. M11 applies adaptations if triggered
5. M12 summarizes results
6. M14 logs the session transcript

**“What should I do today?” flow**
1. M1 reads profile + plan (M3/M4/M10)
2. M9 computes current status (if stale)
3. M11 checks if adaptation needed
4. M12 renders today’s workout + rationale
5. M14 logs the session transcript

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

conversations/YYYY-MM-DD_session.md
```

---

## 6. Data Model & Schemas (v0)

v0 uses YAML for human readability and easy diffing.

### 6.1 Athlete Profile (`athlete/profile.yaml`)

**Required (minimum)**
- `name: str`
- `created_at: date`
- `running_priority: enum(primary|secondary|equal)`
- `primary_sport: str`
- `conflict_policy: enum(primary_sport_wins|running_goal_wins|ask_each_time)`
- `constraints.available_run_days: list[weekday]`
- `constraints.min_run_days_per_week: int`
- `constraints.max_run_days_per_week: int`
- `goal.type: enum(5k|10k|half_marathon|marathon|general_fitness)`

**Optional (recommended)**
- `injury_history: str`
- PRs + VDOT estimate fields
- `other_sports[]` commitments

### 6.2 Training History (`athlete/training_history.yaml`)

**Required**
- `last_strava_sync_at: datetime`
- `last_strava_activity_id: str`

**Optional**
- `baseline.ctl: float`
- `baseline.atl: float`
- `baseline.tsb: float`
- `baseline.period_days: int`

### 6.3 Activity File (`activities/YYYY-MM/YYYY-MM-DD_<sport>_<slug>.yaml`)

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

**Derived fields (computed)**
- `calculated.estimated_rpe: int (1..10)`
- `calculated.base_effort_au: float` (`estimated_rpe * duration_minutes`)
- `calculated.systemic_multiplier: float`
- `calculated.lower_body_multiplier: float`
- `calculated.systemic_load_au: float`
- `calculated.lower_body_load_au: float`

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

### 6.8 Conversation Logs (`conversations/YYYY-MM-DD_session.md`)

**Required (minimal)**
- Timestamped, role-tagged lines (user/coach/assistant).
- Include a short session header (date + athlete name).

---

## 7. Load & Fatigue Computation (v0)

### 7.1 RPE Estimation

RPE sources, in priority order:
1. Explicit user RPE (`strava_perceived_exertion`, if present)
2. HR-based estimate (if reliable HR present)
3. Text-based estimate from notes (keywords + workout description)
4. Strava relative effort normalization (if present)
5. Sport + duration heuristic fallback

### 7.2 Two-Channel Load Model

For each activity:

- `base_effort_au = estimated_rpe * duration_minutes`
- `systemic_load_au = base_effort_au * systemic_multiplier`
- `lower_body_load_au = base_effort_au * lower_body_multiplier`

**Multiplier defaults** are defined in the PRD and should be centralized in one place (e.g., a config map), so they can evolve without changing schemas.

**Strength/CrossFit rule (v0, minimal):**
- Default multipliers assume “mixed” stimulus.
- If notes clearly indicate lower-body dominance, bump `lower_body_multiplier`.
- If notes clearly indicate upper-body dominance, reduce `lower_body_multiplier`.
- If unclear and a key run is imminent, ask the athlete.

### 7.3 CTL/ATL/TSB (Systemic)

- `ctl` and `atl` are computed from **systemic** daily loads only.
- `lower_body` is used as a **compatibility constraint**, not as fitness.

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

When a plan decision conflicts with the athlete’s primary sport or reality:

- `primary_sport_wins`: adjust running first.
- `running_goal_wins`: preserve key running sessions unless injury risk is high.
- `ask_each_time`: present options with trade-offs and ask.

---

## 9. Adaptation Rules (v0)

v0 adaptation is rule-based, explainable, and conservative:

### 9.1 Key Inputs

- `systemic_acwr` + `ctl/atl/tsb`
- `readiness.score` + confidence
- `lower_body_daily_load_au` (yesterday and 2–3 day trend)
- injury flags extracted from notes

### 9.2 High Lower-Body Load (Definition)

v0 should define “high lower-body load” using a simple, athlete-relative threshold:

- Preferred: `yesterday_lower_body > 1.5 × median(lower_body_daily_load last 14 days)`
- Fallback (new user / little history): absolute threshold tuned conservatively (and later refined)

### 9.3 Adaptation Outcomes

- For a scheduled **key** workout:
  - Prefer to move 24–48 hours before downgrading, unless injury flags are present.
  - If systemic ACWR is high or readiness is very low, downgrade (don’t “force” it).
- For non-key workouts:
  - Remove or convert to easy without guilt.

Every adaptation must write:
- `original`
- `adapted_to`
- `reason` (metrics + notes)
- `conflict_policy_applied` (if relevant)

---

## 10. Strava Integration (v0)

The PRD defines the endpoints and manual sync flow.

v0 additional constraints:
- Tokens/credentials are read from `config/secrets.local.yaml` (or environment variables).
- The sync process must be idempotent: re-running sync should not duplicate activity files.

---

## 11. Prompting / “AI Coach” Integration (v0)

This spec assumes the coaching agent can read/write the repository files.

Minimum prompt inputs for “What should I do today?”:
- Athlete profile summary (goal, constraints, conflict_policy)
- Last 7 days of activities (systemic + lower-body summary)
- Current metrics (systemic CTL/ATL/TSB/ACWR, readiness)
- Next scheduled workout(s)

Minimum prompt outputs:
- Workout prescription (time/distance, intensity guidance)
- If adapted: explicit “changed X → Y because …”
- One question if a key ambiguity blocks the decision (e.g., “Was yesterday’s CrossFit leg-heavy?”)
