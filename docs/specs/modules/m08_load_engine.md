# Load engine

## Purpose

`resilio/core/load.py` computes Resilio-owned training load from a validated
`CanonicalActivity` and a selected 1–10 RPE. Intervals.icu load and readiness
values are never authoritative.

Each calculation produces:

- a TSS-equivalent base effort from duration and RPE;
- systemic and lower-body sport multipliers;
- explicit multiplier and interval adjustments;
- easy, moderate, quality, or race classification; and
- a provider-neutral `LoadCalculation` persisted under
  `CanonicalActivity.calculated_load`.

Systemic load feeds CTL, ATL, TSB, and ACWR. Lower-body load gates running
quality and long-session decisions for multi-sport athletes.

## Public computation surface

```python
compute_load(
    activity: CanonicalActivity,
    estimated_rpe: int,
    repo: RepositoryIO | None = None,
) -> LoadCalculation

compute_loads_batch(
    activities: list[tuple[CanonicalActivity, int]],
    repo: RepositoryIO | None = None,
) -> list[LoadCalculation]

persist_load_to_activity(
    activity_path: str,
    load: LoadCalculation,
    repo: RepositoryIO,
) -> None
```

Pure helpers calculate the base effort, choose canonical sport multipliers,
apply adjustments, classify the session, and validate the result.

## Load rules

The base calculation is:

```text
hours × intensity_factor(RPE)² × 100
```

Canonical sport multipliers account for running variants, cycling, swimming,
climbing/bouldering, strength, CrossFit, hiking, walking, yoga, and `other`.
Adjustments are inspectable strings and may reflect lower- or upper-body
strength focus, high elevation, long duration, race classification, or
interval/recovery structure.

Session classification is:

| RPE | Session |
|---:|---|
| 1–4 | easy |
| 5–6 | moderate |
| 7–8 | quality |
| 9–10 | race |

An explicit source race subtype overrides the RPE classification. Structured
segments or interval evidence apply the documented recovery adjustment.

## Invariants

- Duration is positive and derives from canonical elapsed seconds.
- RPE is between 1 and 10.
- All load values are finite and non-negative.
- Multipliers stay within schema bounds.
- `activity_id` is the immutable local activity ID.
- Calculated load records their algorithm version.
- `climb` covers both RockClimbing and Bouldering.
- Unknown external sport labels never reach this module; mapping quarantines
  them before domain calculation.
- Recomputing identical inputs with the same algorithm version is
  deterministic.

## Dependency direction

The load engine consumes only canonical domain data and repository I/O for its
narrow persistence helper. It must not import external DTOs, HTTP transports,
API, or CLI modules. Daily/weekly aggregation and readiness metrics consume
its output in later layers.

## Verification

Unit tests cover every canonical sport multiplier, boundary RPE values,
elevation/strength/duration/race adjustments, interval detection, batch
behavior, persistence, invalid input, and output validation. Archive and
metrics reconciliation tests protect deterministic historical totals.
