"""Measured activity exposure and source-zone evidence."""

from __future__ import annotations

from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.coaching import (
    ActivityContext,
    IntensityContext,
    RunExposure,
    SourceZoneBucket,
    SourceZoneEvidence,
    SportExposure,
)

_RUN_SPORTS = {"run", "trail_run", "treadmill_run", "track_run"}


def activity_context(activity: CanonicalActivity) -> ActivityContext:
    return ActivityContext(
        local_activity_id=activity.local_activity_id,
        local_date=activity.occurrence.local_date,
        sport=str(activity.sport),
        name=activity.name,
        elapsed_duration_seconds=activity.duration.elapsed_seconds,
        moving_duration_seconds=activity.duration.moving_seconds,
        distance_km=(
            activity.distance_meters / 1_000 if activity.distance_meters is not None else None
        ),
        elevation_gain_meters=activity.elevation_gain_meters,
        aerobic_load=activity.aerobic_load,
        native_analysis=activity.native_analysis,
        native_analysis_applicability=(activity.native_analysis_applicability),
        subjective_effort=activity.subjective_effort,
        analysis_thresholds=activity.analysis_thresholds,
    )


def _complete_load_total(
    activities: list[CanonicalActivity],
) -> tuple[float | None, int]:
    available = [
        activity.aerobic_load.aerobic_load_points
        for activity in activities
        if activity.aerobic_load is not None
    ]
    if len(available) != len(activities) or not activities:
        return None, len(available)
    return sum(available), len(available)


def run_exposure(activities: list[CanonicalActivity]) -> RunExposure:
    runs = [activity for activity in activities if str(activity.sport) in _RUN_SPORTS]
    load_points, load_count = _complete_load_total(runs)
    distances = [
        activity.distance_meters / 1_000
        for activity in runs
        if activity.distance_meters is not None
    ]
    elevation_gains_meters = [
        activity.elevation_gain_meters
        for activity in runs
        if activity.elevation_gain_meters is not None
    ]
    return RunExposure(
        session_count=len(runs),
        run_count=len(runs),
        elapsed_duration_seconds=sum(activity.duration.elapsed_seconds for activity in runs),
        distance_km=(sum(distances) if len(distances) == len(runs) and runs else None),
        runs_with_distance=len(distances),
        elevation_gain_meters=(
            sum(elevation_gains_meters)
            if len(elevation_gains_meters) == len(runs) and runs
            else None
        ),
        runs_with_elevation_gain=len(elevation_gains_meters),
        longest_run_distance_km=(
            max(distances) if distances and len(distances) == len(runs) else None
        ),
        aerobic_load_points=load_points,
        sessions_with_aerobic_load=load_count,
    )


def other_sport_exposure(
    activities: list[CanonicalActivity],
) -> list[SportExposure]:
    others = [activity for activity in activities if str(activity.sport) not in _RUN_SPORTS]
    grouped = {
        sport: [activity for activity in others if str(activity.sport) == sport]
        for sport in sorted({str(activity.sport) for activity in others})
    }
    result: list[SportExposure] = []
    for sport, sport_activities in grouped.items():
        load_points, load_count = _complete_load_total(sport_activities)
        result.append(
            SportExposure(
                sport=sport,
                session_count=len(sport_activities),
                elapsed_duration_seconds=sum(
                    activity.duration.elapsed_seconds for activity in sport_activities
                ),
                aerobic_load_points=load_points,
                sessions_with_aerobic_load=load_count,
            )
        )
    return result


def intensity_context(
    activities: list[CanonicalActivity],
    *,
    due_planned_low_intensity_duration_seconds: int,
    due_planned_moderate_intensity_duration_seconds: int,
    due_planned_high_intensity_duration_seconds: int,
) -> IntensityContext:
    evidence: list[SourceZoneEvidence] = []
    for activity in activities:
        for distribution in activity.zone_time_distributions:
            evidence.append(
                SourceZoneEvidence(
                    local_activity_id=activity.local_activity_id,
                    sport=str(activity.sport),
                    source_sport_type=activity.source_sport_type,
                    measurement_method=str(distribution.measurement_method),
                    measurement_unit=distribution.measurement_unit,
                    covered_duration_seconds=(distribution.covered_duration_seconds),
                    coverage_percent=(distribution.moving_time_coverage_percent),
                    analysis_source_moving_duration_seconds=(
                        distribution.analysis_source_moving_duration_seconds
                    ),
                    is_primary_time_in_zones_method=(distribution.is_primary_time_in_zones_method),
                    analysis_settings_sha256=(distribution.analysis_settings_sha256),
                    zones=[
                        SourceZoneBucket(
                            zone_index=zone.zone_index,
                            provider_zone_id=zone.provider_zone_id,
                            name=zone.name,
                            duration_seconds=zone.duration_seconds,
                            lower_bound=zone.lower_bound,
                            upper_bound=zone.upper_bound,
                        )
                        for zone in distribution.zones
                    ],
                )
            )
    return IntensityContext(
        source_zone_evidence=evidence,
        due_planned_low_intensity_duration_seconds=(due_planned_low_intensity_duration_seconds),
        due_planned_moderate_intensity_duration_seconds=(
            due_planned_moderate_intensity_duration_seconds
        ),
        due_planned_high_intensity_duration_seconds=(due_planned_high_intensity_duration_seconds),
    )
