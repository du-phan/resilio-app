"""Signal-first training-state and wellness trend extraction."""

from __future__ import annotations

from datetime import date, timedelta
from statistics import median
from typing import Callable, Optional

from resilio.schemas.coaching import (
    RecoveryContext,
    RecoverySignal,
    TrainingStateSnapshot,
)
from resilio.schemas.training_state import WellnessDay

MINIMUM_BASELINE_SAMPLES = 7
BASELINE_WINDOW_DAYS = 28

_SignalAccessor = Callable[[WellnessDay], Optional[float]]

_SIGNALS: tuple[tuple[str, str, _SignalAccessor], ...] = (
    ("resting_hr", "bpm", lambda row: _number(row.resting_hr_bpm)),
    ("hrv_rmssd", "ms", lambda row: row.hrv_rmssd_ms),
    ("hrv_sdnn", "ms", lambda row: row.hrv_sdnn_ms),
    (
        "sleep_duration",
        "seconds",
        lambda row: _number(row.sleep_duration_seconds),
    ),
    ("sleep_score", "provider_score", lambda row: row.sleep_score),
    (
        "sleep_quality",
        "provider_scale_1_to_4",
        lambda row: _number(row.sleep_quality),
    ),
    (
        "average_sleeping_hr",
        "bpm",
        lambda row: row.average_sleeping_hr_bpm,
    ),
    ("soreness", "provider_scale_0_to_4", lambda row: _number(row.soreness)),
    (
        "subjective_fatigue",
        "provider_scale_0_to_4",
        lambda row: _number(row.subjective_fatigue),
    ),
    ("stress", "provider_scale_0_to_4", lambda row: _number(row.stress)),
    ("mood", "provider_scale_1_to_4", lambda row: _number(row.mood)),
    (
        "motivation",
        "provider_scale_1_to_4",
        lambda row: _number(row.motivation),
    ),
    ("injury", "provider_scale_1_to_4", lambda row: _number(row.injury)),
    (
        "hydration",
        "provider_scale_1_to_4",
        lambda row: _number(row.hydration),
    ),
    (
        "provider_hydration_volume",
        "provider_defined",
        lambda row: row.provider_hydration_volume_value,
    ),
    (
        "provider_readiness",
        "provider_score",
        lambda row: row.provider_readiness_value,
    ),
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
    name: str,
    unit: str,
    accessor: _SignalAccessor,
    current: WellnessDay,
    wellness: dict[date, WellnessDay],
    as_of_date: date,
) -> RecoverySignal | None:
    current_value = accessor(current)
    if current_value is None:
        return None
    baseline_start = current.local_date - timedelta(days=BASELINE_WINDOW_DAYS)
    baseline_values = [
        value
        for day, row in sorted(wellness.items())
        if baseline_start <= day < current.local_date
        if (value := accessor(row)) is not None
    ]
    baseline = (
        float(median(baseline_values)) if len(baseline_values) >= MINIMUM_BASELINE_SAMPLES else None
    )
    return RecoverySignal(
        name=name,
        current_date=current.local_date,
        current_value=current_value,
        unit=unit,
        observation_age_days=(as_of_date - current.local_date).days,
        is_temporary=(current.resting_hr_is_temporary if name == "resting_hr" else None),
        personal_baseline_median=baseline,
        difference_from_baseline=(current_value - baseline if baseline is not None else None),
        baseline_sample_count=len(baseline_values),
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
        for name, unit, accessor in _SIGNALS:
            current_signal = next(
                (
                    row
                    for _day, row in sorted(
                        eligible.items(),
                        reverse=True,
                    )
                    if accessor(row) is not None
                ),
                None,
            )
            if current_signal is None:
                missing.append(name)
                continue
            mapped = _signal(
                name=name,
                unit=unit,
                accessor=accessor,
                current=current_signal,
                wellness=eligible,
                as_of_date=as_of_date,
            )
            if mapped is None:
                missing.append(name)
            else:
                signals.append(mapped)
    else:
        missing.extend(name for name, _unit, _accessor in _SIGNALS)
    days = sorted(eligible)
    return RecoveryContext(
        as_of_date=as_of_date,
        signals=signals,
        missing_signals=sorted(set(missing)),
        wellness_window_start=days[0] if days else None,
        wellness_window_end=days[-1] if days else None,
        wellness_days_available=len(days),
    )
