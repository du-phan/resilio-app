"""Map provider-native analysis without reconstructing provider metrics."""

from __future__ import annotations

from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.schemas.activity import (
    HeartRateRecoveryObservation,
    NativeActivityAnalysis,
    NativeAnalysisApplicability,
    NativeDecouplingObservation,
    NativePolarizationObservation,
)


def map_native_activity_analysis(
    activity: ActivityDTO,
) -> NativeActivityAnalysis | None:
    if not any(
        value is not None
        for value in (
            activity.decoupling,
            activity.polarization_index,
            activity.trimp,
            activity.icu_hrr,
        )
    ):
        return None
    heart_rate_recovery = activity.icu_hrr
    return NativeActivityAnalysis(
        aerobic_decoupling=(
            NativeDecouplingObservation(
                value_percent=activity.decoupling,
                aggregation_scope="activity",
            )
            if activity.decoupling is not None
            else None
        ),
        polarization=(
            NativePolarizationObservation(
                value=activity.polarization_index,
                evidence_status="unlinked",
            )
            if activity.polarization_index is not None
            else None
        ),
        trimp_load_points=activity.trimp,
        heart_rate_recovery=(
            HeartRateRecoveryObservation(
                start_sample_index=heart_rate_recovery.start_index,
                end_sample_index=heart_rate_recovery.end_index,
                start_offset_seconds=heart_rate_recovery.start_time,
                end_offset_seconds=heart_rate_recovery.end_time,
                start_heart_rate_bpm=heart_rate_recovery.start_bpm,
                end_heart_rate_bpm=heart_rate_recovery.end_bpm,
                average_power_watts=heart_rate_recovery.average_watts,
                heart_rate_recovery_bpm=heart_rate_recovery.hrr,
            )
            if heart_rate_recovery is not None
            else None
        ),
    )


def map_native_analysis_applicability(
    activity: ActivityDTO,
) -> NativeAnalysisApplicability | None:
    values = (
        activity.icu_ignore_time,
        activity.icu_ignore_power,
        activity.icu_ignore_hr,
        activity.ignore_velocity,
        activity.ignore_pace,
    )
    if not any(value is not None for value in values):
        return None
    return NativeAnalysisApplicability(
        exclude_time=activity.icu_ignore_time,
        exclude_power=activity.icu_ignore_power,
        exclude_heart_rate=activity.icu_ignore_hr,
        exclude_velocity=activity.ignore_velocity,
        exclude_pace=activity.ignore_pace,
    )
