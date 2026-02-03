# Methodology & Metrics Update Implementation Plan

**Purpose**: Provide a decision-complete spec for updating Sports Coach Engine’s methodology, metrics, and coaching logic based on expert feedback, current implementation reality, and training literature. This document is for the coding agent implementing improvements.

**Scope**: Phase 1 implementation (correctness + consistency + safer messaging) with Phase 2/3 design guidance captured for follow-on work.

**Compatibility policy**: **No backward compatibility required**. Prefer clean, explicit schemas and naming even if outputs change.

---

## 0. Ground Truth Inputs

**Primary references**

- `docs/coaching/methodology.md` (current methodology)
- `docs/coaching/methodology_expert_feedback/methodology_expert_review.md` (question set)
- Expert reviews:
  - `docs/coaching/methodology_expert_feedback/claude_methodolog_review.md`
  - `docs/coaching/methodology_expert_feedback/chatgpt_methodology_review.md`
- Core implementation:
  - `sports_coach_engine/core/metrics.py` (CTL/ATL/TSB/ACWR/Readiness)
  - `sports_coach_engine/core/load.py` (load + multipliers)
  - `sports_coach_engine/core/adaptation.py` (M11 triggers)
  - `sports_coach_engine/core/analysis/risk.py` (risk aggregation)
  - `sports_coach_engine/core/workflows.py` (adaptation workflow)
  - `sports_coach_engine/core/enrichment.py` (interpretations)
  - Schemas + CLI

**Key design principle**

- **Toolkit paradigm**: code computes metrics; AI Coach decides. Do not encode rigid coaching decisions into the engine.

**Interface contract**

- **CLI-first**: AI Coach should operate through CLI outputs; Python APIs remain internal.

---

## 1. Phase Plan (Roadmap)

### Phase 1 (Implement Now)

Goal: Fix correctness, align docs + code, reduce false certainty, and simplify AI Coach inputs without hiding data.

**Deliverables**

1. Fix load trend computation bug (today’s missing metrics treated as 0).
2. Readiness objective-only: weights 40/40 + score cap + low confidence (no sleep/wellness in v0).
3. TSB zone refinement: add explicit race-ready band and detraining risk band; remove PEAKED.
4. ACWR messaging: keep thresholds but remove “2–4x injury probability” claims; position as load spike indicator.
5. Risk model cleanup: weight values match risk score increments; rename fields to “risk_index”.
6. Schema cleanup: rename `injury_risk_elevated` → `load_spike_elevated`; remove unused wellness schemas/overrides.
7. Add “primary signals summary” in enriched metrics (additive field, no raw metric removals).
8. Align key docs, CLI copy, and skill references with new zone labels and safer wording.

### Phase 2 (Next)

Goal: Improve multi-sport robustness and AI decision clarity **without** introducing subjective inputs.

**Design-only commitments (spec-level, no code in Phase 2 unless explicitly scheduled)**

1. **Running-specific load track (parallel to all-sport load)**
   - Compute **running-only** systemic load series and derive `running_ctl`, `running_atl`, `running_tsb`, `running_acwr`.
   - Use running-only metrics **only** for run-specific decisions (quality/long run gating), while all-sport metrics continue to drive global fatigue and safe-volume logic.
   - Schema proposal (additive):
     - `DailyMetrics.running_ctl_atl` (mirrors `ctl_atl`)
     - `DailyMetrics.running_acwr` (mirrors `acwr`)
     - `EnrichedMetrics.primary_signals.running_load_spike` (optional)
   - Acceptance: running-only ACWR changes only when running activities occur.

2. **Lower-body gating refinement**
   - Replace fixed `CTL * 2.5` threshold with a two-part rule:
     - **Acute lower-body spike**: 2-day lower-body sum > `max(CTL * 2.0, 1.4 × 7-day median lower-body load)`
     - **Dense quality**: ≥2 quality/long-run stressors in last 4 days.
   - Output a `lower_body_load_status` object (values: `ok`, `elevated`, `high`) with thresholds exposed for AI Coach.

3. **Multiplier configuration + athlete overrides**
   - Move sport multipliers into a single config table (e.g., `config/multipliers.yaml`).
   - Allow per-athlete overrides in profile (`profile.load_multipliers`) with validation and audit logging.
   - Add CLI helper to print effective multipliers.

4. **Decision hierarchy hints (AI Coach support)**
   - Provide a deterministic **priority order** in docs:
     1. Safety overrides (severe illness/injury flags).
     2. High load spikes (`acwr >= 1.5` or `running_acwr >= 1.5`).
     3. Readiness (objective-only).
     4. CTL/volume progression.
   - Expose this hierarchy in `primary_signals` to reduce cognitive load.

### Phase 3 (Later)

Goal: Validation, calibration, and optional subjective inputs (if product decides).

**Planned follow-ups**

1. **Calibration reports**
   - Add CLI report: rolling distributions for CTL/ATL/TSB/ACWR, readiness score histogram, and trigger frequency.
   - Highlight outliers (e.g., chronic ACWR > 1.3, persistent TSB > 25).

2. **Multiplier and gating tuning**
   - Aggregate anonymized athlete summaries to assess whether multipliers and lower-body thresholds are systematically too strict/lenient.
   - Produce a tuning guide with recommended deltas (no automatic updates).

3. **Optional subjective readiness (product-dependent)**
   - If enabled, add a minimal subjective input pipeline (sleep quality, soreness).
   - Gate readiness confidence (`LOW` → `MEDIUM/HIGH`) based on input availability.
   - Add explicit UI/CLI prompts for data entry; do not infer subjective scores from notes without user confirmation.

---

## 2. Methodology Decisions (Phase 1)

### 2.1 ACWR: Keep thresholds, change meaning and messaging

**Keep thresholds:** `<0.8` undertrained, `0.8–1.3` safe, `1.3–1.5` caution, `>=1.5` high spike.

**Messaging rules**

- Do **not** claim injury probability or causation.
- Use: “load spike indicator” / “elevated load relative to recent weeks.”
- Add endurance caveat in methodology doc (team-sport origin, interpret as guidance).

### 2.2 TSB Zones: Separate “quality-ready” vs “race-ready”

**New banding**

- `< -25`: OVERREACHED
- `-25 to -10`: PRODUCTIVE
- `-10 to +5`: OPTIMAL (balanced training)
- `+5 to +15`: FRESH (quality-ready)
- `+15 to +25`: RACE_READY
- `> +25`: DETRAINING_RISK

### 2.3 Readiness: objective-only fallback (now) + confidence demotion

**Objective-only formula (v0)**

- Weights: `TSB 40%`, `Load trend 40%`.
- Score cap: `max 65`.
- Confidence: `LOW` (objective-only in v0).
- `data_coverage = "objective_only"`.

### 2.4 Risk Model: Keep additive heuristic, remove “probability” framing

- Risk score remains additive; band thresholds unchanged in Phase 1.
- Rename fields to `risk_index_pct` / `risk_index` to avoid medical framing.
- All user-facing copy should avoid “you will get injured.”

### 2.5 Primary Signals Summary (CLI / Enriched Metrics)

Add a summary object without hiding raw metrics:

- `primary_signals.readiness`: score, level, confidence, data_coverage
- `primary_signals.load_spike`: ACWR value, zone, availability, caveat
- Optional: note that planned workout suitability is outside `sce status` (context needed).

---

## 3. Implementation Plan (Phase 1)

### 3.1 Code Changes

**A) Fix load trend computation**

- Update `compute_load_trend()` to accept today’s actual load and avoid defaulting to 0 when today’s metrics file is missing.
- If any of the last 7 days is missing data (other than today’s provided load), return neutral score (65) to avoid false freshness.

**Files**:

- `sports_coach_engine/core/metrics.py`

**B) Readiness objective-only update**

- Update `READINESS_WEIGHTS_OBJECTIVE_ONLY` to `{tsb: 0.40, load_trend: 0.40}`.
- Add `READINESS_MAX_OBJECTIVE_ONLY = 65`.
- Add `data_coverage` field to `ReadinessScore` schema (`objective_only` only in v0).
- Confidence = LOW (objective-only).
- Remove sleep/wellness components from `ReadinessComponents` schema.

**Files**:

- `sports_coach_engine/core/metrics.py`
- `sports_coach_engine/schemas/metrics.py`

**C) TSB zones update**

- Add `RACE_READY` and `DETRAINING_RISK` to `TSBZone`.
- Update `_classify_tsb_zone()` and `TSB_CONTEXT`.

**Files**:

- `sports_coach_engine/schemas/metrics.py`
- `sports_coach_engine/core/metrics.py`
- `sports_coach_engine/core/enrichment.py`

**D) ACWR messaging cleanup**

- Replace “injury risk” language with “load spike” / “elevated load” language.
- Update schema comments, enrichment explanations, plan explanations.

**Files**:

- `sports_coach_engine/schemas/metrics.py`
- `sports_coach_engine/core/enrichment.py`
- `sports_coach_engine/core/plan.py`

**E) Risk model consistency**

- Ensure `risk_score` increments match `RiskFactor.weight` values.
- Rename fields to `risk_index` / `risk_index_pct` for clarity.
- Update option text to avoid “injury probability.”

**Files**:

- `sports_coach_engine/core/analysis/risk.py`
- `sports_coach_engine/schemas/analysis.py`
- `sports_coach_engine/schemas/adaptation.py`
- `sports_coach_engine/core/adaptation.py`

**F) Add primary signals summary to enriched metrics**

- Introduce new schema in `sports_coach_engine/schemas/enrichment.py` for `PrimarySignals`.
- Populate in `sports_coach_engine/core/enrichment.py`.

**Files**:

- `sports_coach_engine/schemas/enrichment.py`
- `sports_coach_engine/core/enrichment.py`

**G) Schema + workflow cleanup (no backward-compat)**

- Rename `ACWRMetrics.injury_risk_elevated` → `load_spike_elevated`.
- Remove unused wellness schemas and overrides (no sleep/wellness in v0).
- Remove any legacy `PEAKED` zones from enums and docs.

**Files**:

- `sports_coach_engine/schemas/metrics.py`
- `sports_coach_engine/core/metrics.py`
- `sports_coach_engine/schemas/common.py`
- `sports_coach_engine/schemas/activity.py`
- `sports_coach_engine/core/workflows.py`

### 3.2 Documentation Updates (Phase 1)

**Update**:

- `docs/coaching/methodology.md`
- `docs/specs/modules/m09_metrics_engine.md`
- `docs/specs/modules/m01_workflows.md`
- `docs/specs/modules/m11_adaptation_toolkit.md`
- `docs/specs/modules/m12_enrichment.md`
- `docs/coaching/scenarios.md`
- `docs/specs/api_layer.md`
- `docs/coaching/cli/index.md`
- `docs/coaching/cli/cli_activity.md`
- `docs/coaching/cli/cli_metrics.md`
- `docs/coaching/cli/cli_risk.md`
- `CLAUDE.md`
- `.claude/skills/**` references to TSB taper targets

**Specific wording changes**

- ACWR: “load spike indicator” + caveat; remove “2–4x injury probability.”
- TSB: add “race-ready band +15 to +25”; “quality-ready +5 to +15.”
- Readiness: objective-only uses capped score + low confidence (no subjective inputs in v0).
- Risk outputs: rename fields to `risk_index_pct` / `risk_index`.
- ACWR flag: rename to `load_spike_elevated`.

---

## 4. Test Plan (Phase 1)

**Unit tests**

- `tests/unit/test_metrics.py`
  - Readiness weights updated
  - Readiness confidence updated (objective-only = LOW)
  - New cap behavior
  - Add test: load_trend uses today load
- `tests/unit/test_enrichment.py`
  - TSB interpretations updated
  - ACWR interpretation text updated
  - New `primary_signals` field (if used in comparisons)
- `tests/unit/test_adaptation.py`
  - `risk_index` field rename coverage

**Integration tests**

- `tests/integration/test_phase3_integration.py`
  - Readiness confidence may now be LOW without subjective inputs

---

## 4.1 Phase 1 Implementation Notes (Current Repo State)

These items are implemented in the current codebase and should be treated as source of truth for Phase 1:

- `compute_load_trend` now accepts today’s load and returns neutral when any of the last 7 days are missing.
- Readiness is **objective-only**: 40/40 weights, cap 65, confidence LOW, `data_coverage="objective_only"`.
- TSB zones include `FRESH` (5–15), `RACE_READY` (15–25), `DETRAINING_RISK` (>25); legacy `PEAKED` removed.
- ACWR is framed as a **load spike** indicator; schema flag renamed to `load_spike_elevated`.
- Risk outputs renamed to `risk_index_pct` / `risk_index` (no “injury probability” fields).
- `primary_signals` added to enriched metrics (readiness + load spike summary).
- Wellness schemas and overrides removed; readiness components no longer include sleep/wellness fields.

---

## 5. Acceptance Criteria (Phase 1)

- Load trend no longer treats today as 0 when metrics file missing.
- Readiness objective-only scores capped at 65 and confidence marked LOW.
- TSB zone classification includes race-ready band (15–25) and detraining risk (>25).
- ACWR messaging no longer claims injury probability; uses load spike language.
- Risk factor weights align with score increments; risk output is described as a heuristic index.
- Risk fields renamed to `risk_index_pct` / `risk_index`.
- ACWR flag renamed to `load_spike_elevated`.
- PEAKED zone removed from enums and docs.
- CLI output includes a `primary_signals` summary without removing raw metric fields.
- Docs reflect actual implementation and match code thresholds.

---

## 6. Migration / Recompute Guidance

Any change to multipliers or readiness math affects historical metrics. For Phase 1:

- **Recommend recomputing metrics** after updating readiness and TSB zones.
- Provide a note in docs/CLI to run the existing metrics refresh workflow (no new command required).
- **Breaking schema changes**: renamed fields (`risk_index_pct`, `risk_index`, `load_spike_elevated`) require regenerating or migrating stored metrics.
