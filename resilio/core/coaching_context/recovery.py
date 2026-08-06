"""Signal-first training-state and wellness trend extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median
from typing import Callable, Literal, Optional

from resilio.schemas.coaching import (
    DatedAthleteWellnessNote,
    RecoveryContext,
    RecoveryObservation,
    RecoverySignal,
    TrainingStateSnapshot,
)
from resilio.schemas.training_state import WellnessDay

MINIMUM_BASELINE_SAMPLES = 7
BASELINE_WINDOW_DAYS = 28

_SignalAccessor = Callable[[WellnessDay], Optional[float]]
_ScaleDirection = Literal[
    "lower_is_better",
    "higher_is_better",
    "neutral",
    "provider_defined",
]


@dataclass(frozen=True)
class _SignalDefinition:
    name: str
    unit: str
    accessor: _SignalAccessor
    scale_direction: _ScaleDirection = "neutral"
    scale_minimum: float | None = None
    scale_maximum: float | None = None
    scale_labels: dict[int, str] = field(default_factory=dict)


_SIGNALS: tuple[_SignalDefinition, ...] = (
    _SignalDefinition("resting_hr", "bpm", lambda row: _number(row.resting_hr_bpm)),
    _SignalDefinition("hrv_rmssd", "ms", lambda row: row.hrv_rmssd_ms),
    _SignalDefinition("hrv_sdnn", "ms", lambda row: row.hrv_sdnn_ms),
    _SignalDefinition(
        name="sleep_duration",
        unit="seconds",
        accessor=lambda row: _number(row.sleep_duration_seconds),
    ),
    _SignalDefinition(
        "sleep_score",
        "provider_score",
        lambda row: row.sleep_score,
        scale_direction="provider_defined",
    ),
    _SignalDefinition(
        name="sleep_quality",
        unit="provider_scale_1_to_4",
        accessor=lambda row: _number(row.sleep_quality),
        scale_direction="lower_is_better",
        scale_minimum=1,
        scale_maximum=4,
        scale_labels={1: "excellent", 4: "poor"},
    ),
    _SignalDefinition("average_sleeping_hr", "bpm", lambda row: row.average_sleeping_hr_bpm),
    _SignalDefinition(
        "soreness",
        "provider_scale_0_to_4",
        lambda row: _number(row.soreness),
        "lower_is_better",
        0,
        4,
        {0: "none", 4: "extreme"},
    ),
    _SignalDefinition(
        "subjective_fatigue",
        "provider_scale_0_to_4",
        lambda row: _number(row.subjective_fatigue),
        "lower_is_better",
        0,
        4,
        {0: "none", 4: "extreme"},
    ),
    _SignalDefinition(
        "stress",
        "provider_scale_0_to_4",
        lambda row: _number(row.stress),
        "lower_is_better",
        0,
        4,
        {0: "none", 4: "extreme"},
    ),
    _SignalDefinition(
        "mood",
        "provider_scale_1_to_4",
        lambda row: _number(row.mood),
        "lower_is_better",
        1,
        4,
        {1: "excellent", 4: "poor"},
    ),
    _SignalDefinition(
        "motivation",
        "provider_scale_1_to_4",
        lambda row: _number(row.motivation),
        "lower_is_better",
        1,
        4,
        {1: "excellent", 4: "poor"},
    ),
    _SignalDefinition(
        "injury",
        "provider_scale_1_to_4",
        lambda row: _number(row.injury),
        "lower_is_better",
        1,
        4,
        {1: "excellent", 4: "injured"},
    ),
    _SignalDefinition(
        "hydration",
        "provider_scale_1_to_4",
        lambda row: _number(row.hydration),
        "lower_is_better",
        1,
        4,
        {1: "well_hydrated", 4: "very_dehydrated"},
    ),
    _SignalDefinition("hydration_volume", "liters", lambda row: row.hydration_volume_liters),
    _SignalDefinition(
        "provider_readiness",
        "provider_score",
        lambda row: row.provider_readiness_value,
        scale_direction="provider_defined",
    ),
    _SignalDefinition("steps", "count", lambda row: _number(row.step_count)),
    _SignalDefinition("weight", "kilograms", lambda row: row.weight_kilograms),
    _SignalDefinition("oxygen_saturation", "percent", lambda row: row.oxygen_saturation_percent),
    _SignalDefinition(
        "provider_respiration", "provider_defined", lambda row: row.provider_respiration_value
    ),
    _SignalDefinition(
        "provider_baevsky_stress_index",
        "provider_index",
        lambda row: row.provider_baevsky_stress_index,
        scale_direction="provider_defined",
    ),
    _SignalDefinition(
        "provider_vo2_max",
        "milliliters_per_kilogram_per_minute",
        lambda row: row.vo2_max_ml_per_kg_per_min,
    ),
)

_SPORT_PERFORMANCE_METRICS = (
    ("estimated_ftp", "watts"),
    ("estimated_w_prime", "joules"),
    ("estimated_pmax", "watts"),
)


def _sport_performance_value(
    row: WellnessDay,
    source_sport_type: str,
    metric_name: str,
) -> float | None:
    estimate = next(
        (
            item
            for item in row.sport_performance_estimates
            if item.source_sport_type == source_sport_type
        ),
        None,
    )
    if estimate is None:
        return None
    if metric_name == "estimated_ftp":
        return estimate.estimated_ftp_watts
    if metric_name == "estimated_w_prime":
        return estimate.estimated_w_prime_joules
    if metric_name == "estimated_pmax":
        return estimate.estimated_pmax_watts
    raise ValueError(f"Unsupported sport performance metric: {metric_name}")


def _sport_performance_accessor(
    source_sport_type: str,
    metric_name: str,
) -> _SignalAccessor:
    def accessor(row: WellnessDay) -> float | None:
        return _sport_performance_value(row, source_sport_type, metric_name)

    return accessor


def _sport_performance_signal_definitions(
    wellness: dict[date, WellnessDay],
) -> tuple[_SignalDefinition, ...]:
    scoped_metrics = {
        (item.source_sport_type, metric_name, unit)
        for row in wellness.values()
        for item in row.sport_performance_estimates
        for metric_name, unit in _SPORT_PERFORMANCE_METRICS
    }
    return tuple(
        _SignalDefinition(
            name=f"sport_{metric_name}[{source_sport_type}]",
            unit=unit,
            accessor=_sport_performance_accessor(source_sport_type, metric_name),
        )
        for source_sport_type, metric_name, unit in sorted(scoped_metrics)
    )


def _number(value: int | float | None) -> float | None:
    return float(value) if value is not None else None


def latest_wellness(
    wellness: dict[date, WellnessDay],
    as_of_date: date,
) -> WellnessDay | None:
    eligible = [day for day in wellness if day <= as_of_date]
    if not eligible:
        return None
    return wellness[max(eligible)]


def training_state(
    latest: WellnessDay | None,
) -> TrainingStateSnapshot | None:
    if latest is None or latest.fitness_load_points is None or latest.fatigue_load_points is None:
        return None
    return TrainingStateSnapshot(
        local_date=latest.local_date,
        fitness_load_points=latest.fitness_load_points,
        fatigue_load_points=latest.fatigue_load_points,
        form_load_points=(latest.fitness_load_points - latest.fatigue_load_points),
        ramp_load_points_per_week=latest.ramp_load_points_per_week,
    )


def _signal(
    *,
    definition: _SignalDefinition,
    current: WellnessDay,
    wellness: dict[date, WellnessDay],
    as_of_date: date,
) -> RecoverySignal | None:
    current_value = definition.accessor(current)
    if current_value is None:
        return None
    baseline_start = current.local_date - timedelta(days=BASELINE_WINDOW_DAYS)
    baseline_values = [
        value
        for day, row in sorted(wellness.items())
        if baseline_start <= day < current.local_date
        if (value := definition.accessor(row)) is not None
    ]
    baseline = (
        float(median(baseline_values)) if len(baseline_values) >= MINIMUM_BASELINE_SAMPLES else None
    )
    return RecoverySignal(
        name=definition.name,
        current_date=current.local_date,
        current_value=current_value,
        unit=definition.unit,
        observation_age_days=(as_of_date - current.local_date).days,
        is_temporary=(
            current.resting_hr_is_temporary
            if definition.name == "resting_hr"
            else current.weight_is_temporary
            if definition.name == "weight"
            else None
        ),
        personal_baseline_median=baseline,
        difference_from_baseline=(current_value - baseline if baseline is not None else None),
        baseline_sample_count=len(baseline_values),
        scale_direction=definition.scale_direction,
        scale_minimum=definition.scale_minimum,
        scale_maximum=definition.scale_maximum,
        scale_labels=definition.scale_labels,
        freshness=(
            "same_day"
            if current.local_date == as_of_date
            else "recent"
            if (as_of_date - current.local_date).days == 1
            else "stale"
        ),
        recent_observations=[
            RecoveryObservation(local_date=day, value=value)
            for day, row in sorted(wellness.items())
            if as_of_date - timedelta(days=6) <= day <= as_of_date
            if (value := definition.accessor(row)) is not None
        ],
        recent_coverage_observed_days=sum(
            1
            for day, row in wellness.items()
            if as_of_date - timedelta(days=6) <= day <= as_of_date
            if definition.accessor(row) is not None
        ),
        recent_coverage_percent=(
            100
            * sum(
                1
                for day, row in wellness.items()
                if as_of_date - timedelta(days=6) <= day <= as_of_date
                if definition.accessor(row) is not None
            )
            / 7
        ),
    )


def build_recovery_context(
    wellness: dict[date, WellnessDay],
    *,
    as_of_date: date,
) -> RecoveryContext:
    eligible = {day: row for day, row in wellness.items() if day <= as_of_date}
    current = latest_wellness(eligible, as_of_date)
    missing = ["fitness_load_points", "fatigue_load_points"]
    signals: list[RecoverySignal] = []
    if current is not None:
        if current.fitness_load_points is not None:
            missing.remove("fitness_load_points")
        if current.fatigue_load_points is not None:
            missing.remove("fatigue_load_points")
        definitions = (*_SIGNALS, *_sport_performance_signal_definitions(eligible))
        for definition in definitions:
            current_signal = next(
                (
                    row
                    for _day, row in sorted(
                        eligible.items(),
                        reverse=True,
                    )
                    if definition.accessor(row) is not None
                ),
                None,
            )
            if current_signal is None:
                missing.append(definition.name)
                continue
            mapped = _signal(
                definition=definition,
                current=current_signal,
                wellness=eligible,
                as_of_date=as_of_date,
            )
            if mapped is None:
                missing.append(definition.name)
            else:
                signals.append(mapped)
    else:
        missing.extend(definition.name for definition in _SIGNALS)
    days = sorted(eligible)
    return RecoveryContext(
        as_of_date=as_of_date,
        signals=signals,
        missing_signals=sorted(set(missing)),
        wellness_window_start=days[0] if days else None,
        wellness_window_end=days[-1] if days else None,
        wellness_days_available=len(days),
        athlete_notes=[
            DatedAthleteWellnessNote(local_date=day, text=row.athlete_comments.strip())
            for day, row in sorted(eligible.items())
            if as_of_date - timedelta(days=6) <= day <= as_of_date
            if row.athlete_comments is not None and row.athlete_comments.strip()
        ],
    )
