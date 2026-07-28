# Notes and RPE analyzer

## Purpose

`resilio/core/notes.py` is a provider-neutral quantitative toolkit. It accepts
a validated `CanonicalActivity` and athlete profile, then returns:

- every RPE estimate supported by the available canonical data; and
- a multi-signal treadmill classification.

The toolkit does not select a final subjective RPE, parse injuries or illness,
or persist activity data. Coaching logic resolves conflicting estimates using
athlete context.

## Inputs and outputs

The public entry points are:

```python
analyze_activity(activity: CanonicalActivity, athlete_profile: AthleteProfile)
    -> AnalysisResult

estimate_rpe(activity: CanonicalActivity, athlete_profile: AthleteProfile)
    -> list[RPEEstimate]

detect_treadmill(
    activity_name: str,
    description: str | None,
    has_gps: bool,
    sport_type: str,
    sub_type: str | None,
    device_name: str | None,
) -> TreadmillDetection
```

RPE estimates may come from explicit athlete input, preserved historical
relative-effort calibration, heart rate, running pace plus VDOT, or a
low-confidence sport/duration fallback. No external DTO or raw provider score
enters this module. A preserved historical estimate is explicitly tagged
`historical_relative_effort`; it is migration provenance, not a live-provider
dependency.

## Rules

- Return all available estimates; never silently resolve disagreement.
- Treat explicit athlete input as high-confidence evidence.
- Use canonical SI measurements and computed views only.
- Pace estimation applies only to canonical running sports with distance and
  an athlete VDOT.
- Duration is a conservative fallback and must not masquerade as sensor data.
- Treadmill classification combines exact upstream subtype, title or
  description keywords, GPS absence, and device evidence.
- Non-running activities classify as not treadmill.
- Output contains no raw activity payload, credential, or transport metadata.

## Dependency direction

`core/notes.py` may depend on domain schemas and athlete profile schemas. It
must not import the Intervals.icu integration, API, CLI, repositories, or sync
services. Completed-activity mapping happens before this module, while load
calculation and metric aggregation happen after coaching selects an RPE.

## Verification

Unit tests cover explicit input, historical calibration, HR thresholds and
duration adjustment, pace/VDOT zones, sport-duration fallback, treadmill
signals, missing optionals, and non-running activities. Architecture tests
prohibit external DTO imports in notes/coaching consumers.
