"""Signal-first weekly coaching context tests."""

from datetime import date, datetime, timedelta, timezone

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.coaching_context import build_weekly_coach_context
from resilio.core.coaching_context.exposure import run_exposure
from resilio.core.coaching_context.recovery import build_recovery_context
from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import write_sync_state
from resilio.core.training_state_repository import write_wellness
from resilio.schemas.activity import (
    ActivityZoneTime,
    AerobicLoad,
    NativeActivityAnalysis,
    NativeDecouplingObservation,
    NativePolarizationObservation,
    ZoneTimeDistribution,
)
from resilio.schemas.sync import (
    ActivityCoverageWindow,
    ActivitySyncState,
    SourceCoverageExclusion,
)
from resilio.schemas.training_state import WellnessDay
from tests.factories import make_activity


def _prepare_repo(tmp_path, monkeypatch) -> RepositoryIO:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return RepositoryIO()


def test_context_uses_native_training_state_and_separate_exposure_channels(
    tmp_path,
    monkeypatch,
) -> None:
    repo = _prepare_repo(tmp_path, monkeypatch)
    week_start = date(2026, 7, 27)
    wellness = {
        week_start - timedelta(days=day): WellnessDay(
            local_date=week_start - timedelta(days=day),
            fitness_load_points=40 - day * 0.2,
            fatigue_load_points=42 - day * 0.1,
            resting_hr_bpm=48 + day % 2,
            hrv_rmssd_ms=60 - day,
            sleep_duration_seconds=27_000,
        )
        for day in range(8)
    }
    wellness[date(2026, 7, 28)] = WellnessDay(
        local_date=date(2026, 7, 28),
        fitness_load_points=41.5,
        fatigue_load_points=46.0,
        ramp_load_points_per_week=1.7,
        resting_hr_bpm=50,
        hrv_rmssd_ms=55,
        sleep_duration_seconds=25_200,
        provider_readiness_value=72,
    )
    write_wellness(repo, wellness)

    run = make_activity(
        id="run-native",
        date=date(2026, 7, 28),
        sport="run",
        duration_seconds=3600,
        moving_seconds=3540,
        distance_meters=10_000,
        elevation_gain_meters=120,
        aerobic_load=AerobicLoad(
            aerobic_load_points=82,
            calculation_method="heart_rate",
            heart_rate_load_points=82,
        ),
        native_analysis=NativeActivityAnalysis(
            aerobic_decoupling=NativeDecouplingObservation(
                value_percent=2.4,
                aggregation_scope="activity",
            ),
            polarization=NativePolarizationObservation(
                value=-0.1,
                evidence_status="unlinked",
            ),
            trimp_load_points=76,
        ),
        zone_time_distributions=[
            ZoneTimeDistribution(
                measurement_method="heart_rate",
                measurement_unit="beats_per_minute",
                zones=[
                    ActivityZoneTime(
                        zone_index=1,
                        duration_seconds=600,
                    ),
                    ActivityZoneTime(
                        zone_index=4,
                        duration_seconds=1800,
                    ),
                ],
                covered_duration_seconds=2400,
                analysis_source_moving_duration_seconds=3540,
                moving_time_coverage_percent=67.7966101695,
                is_primary_time_in_zones_method=True,
                analysis_settings_sha256="c" * 64,
            )
        ],
    )
    climb = make_activity(
        id="climb-without-load",
        date=date(2026, 7, 29),
        sport="climb",
        duration_seconds=5400,
        moving_seconds=5400,
        distance_meters=None,
    )
    archive = ActivityArchive(repo.resolve_path("data/activities"))
    archive.write(run)
    archive.write(climb)

    context = build_weekly_coach_context(
        repo,
        week_start=week_start,
        as_of_date=date(2026, 7, 29),
    )

    assert context.training_state is not None
    assert context.training_state.fitness_load_points == 41.5
    assert context.training_state.fatigue_load_points == 46
    assert context.training_state.form_load_points == -4.5
    assert context.training_state.ramp_load_points_per_week == 1.7
    readiness = next(
        signal for signal in context.recovery.signals if signal.name == "provider_readiness"
    )
    assert readiness.current_value == 72
    assert readiness.current_date == date(2026, 7, 28)
    assert not hasattr(context.recovery, "composite_score")
    resting_hr = next(signal for signal in context.recovery.signals if signal.name == "resting_hr")
    assert resting_hr.current_value == 50
    assert resting_hr.unit == "bpm"
    assert resting_hr.baseline_sample_count >= 7
    assert context.run_exposure.distance_km == 10
    assert context.run_exposure.elapsed_duration_seconds == 3_600
    assert context.run_exposure.run_count == 1
    assert len(context.other_sport_exposure_by_sport) == 1
    assert context.other_sport_exposure_by_sport[0].sport == "climb"
    assert context.other_sport_exposure_by_sport[0].session_count == 1
    assert context.other_sport_exposure_by_sport[0].aerobic_load_points is None
    assert context.activities[0].aerobic_load is not None
    assert context.activities[0].aerobic_load.aerobic_load_points == 82
    assert context.activities[0].aerobic_load.calculation_method == "heart_rate"
    assert context.activities[0].native_analysis is not None
    assert context.activities[0].native_analysis.aerobic_decoupling.value_percent == 2.4
    assert context.activities[0].native_analysis.polarization.value == -0.1
    assert context.activities[0].native_analysis.trimp_load_points == 76
    assert context.data_quality.activities_with_polarization_observation == 1
    assert context.data_quality.activities_with_linked_polarization_evidence == 0
    assert context.data_quality.activities_with_decoupling_observation == 1
    assert context.data_quality.activities_with_known_decoupling_basis == 0
    assert context.activities[1].aerobic_load is None
    assert context.intensity.source_zone_evidence[0].coverage_percent == (67.7966101695)
    assert context.intensity.source_zone_evidence[0].analysis_source_moving_duration_seconds == 3540
    assert context.intensity.source_zone_evidence[0].sport == "run"
    assert context.intensity.source_zone_evidence[0].source_sport_type == "run"
    assert context.intensity.source_zone_evidence[0].is_primary_time_in_zones_method
    payload = context.model_dump(mode="json")
    rendered = str(payload)
    assert "acwr" not in rendered.casefold()
    assert "systemic_load" not in rendered
    assert "lower_body_load" not in rendered


def test_missing_wellness_is_explicit_not_neutral(
    tmp_path,
    monkeypatch,
) -> None:
    repo = _prepare_repo(tmp_path, monkeypatch)

    context = build_weekly_coach_context(
        repo,
        week_start=date(2026, 7, 27),
        as_of_date=date(2026, 7, 29),
    )

    assert context.training_state is None
    assert not hasattr(context.recovery, "composite_score")
    assert context.recovery.signals == []
    assert "fitness_load_points" in context.recovery.missing_signals
    assert context.data_quality.wellness_days_available == 0
    assert context.adherence.status == "no_plan"
    assert context.adherence.reason == "planning_state_missing"
    assert context.source_evidence_coverage.status == "unavailable"
    assert context.source_evidence_coverage.reason == "no_complete_activity_sync_window"


def test_context_declares_week_scoped_source_exclusions(
    tmp_path,
    monkeypatch,
) -> None:
    repo = _prepare_repo(tmp_path, monkeypatch)
    write_sync_state(
        repo,
        ActivitySyncState(
            schema_version=3,
            last_successful_incremental_at_utc=(datetime(2026, 7, 29, 8, tzinfo=timezone.utc)),
            complete_activity_windows=[
                ActivityCoverageWindow(
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 7, 29),
                )
            ],
            source_coverage_exclusions=[
                SourceCoverageExclusion(
                    external_activity_id_sha256="a" * 64,
                    local_date=date(2026, 7, 28),
                    source_sport_type="Run",
                    reason="source_hidden",
                ),
                SourceCoverageExclusion(
                    external_activity_id_sha256="b" * 64,
                    local_date=date(2026, 7, 20),
                    source_sport_type="Ride",
                    reason="represented_duplicate_recording",
                    represented_by_local_activity_id="local-activity",
                    review_fingerprint_sha256="c" * 64,
                ),
            ],
        ),
    )

    context = build_weekly_coach_context(
        repo,
        week_start=date(2026, 7, 27),
        as_of_date=date(2026, 7, 29),
    )

    coverage = context.source_evidence_coverage
    assert coverage.status == "complete_with_declared_exclusions"
    assert len(coverage.exclusions) == 1
    assert coverage.exclusions[0].local_date == date(2026, 7, 28)


def test_context_marks_unsynchronized_tail_incomplete(
    tmp_path,
    monkeypatch,
) -> None:
    repo = _prepare_repo(tmp_path, monkeypatch)
    write_sync_state(
        repo,
        ActivitySyncState(
            schema_version=3,
            last_successful_incremental_at_utc=(datetime(2026, 7, 28, 8, tzinfo=timezone.utc)),
            complete_activity_windows=[
                ActivityCoverageWindow(
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 7, 28),
                )
            ],
        ),
    )

    context = build_weekly_coach_context(
        repo,
        week_start=date(2026, 7, 27),
        as_of_date=date(2026, 7, 29),
    )

    assert context.source_evidence_coverage.status == "incomplete"
    assert context.source_evidence_coverage.reason == "requested_window_not_fully_synchronized"


def test_future_wellness_never_leaks_into_as_of_context(
    tmp_path,
    monkeypatch,
) -> None:
    repo = _prepare_repo(tmp_path, monkeypatch)
    write_wellness(
        repo,
        {
            date(2026, 7, 28): WellnessDay(
                local_date=date(2026, 7, 28),
                fitness_load_points=40,
                fatigue_load_points=42,
            ),
            date(2026, 7, 30): WellnessDay(
                local_date=date(2026, 7, 30),
                fitness_load_points=99,
                fatigue_load_points=99,
            ),
        },
    )

    context = build_weekly_coach_context(
        repo,
        week_start=date(2026, 7, 27),
        as_of_date=date(2026, 7, 29),
    )

    assert context.training_state is not None
    assert context.training_state.local_date == date(2026, 7, 28)
    assert context.training_state.fitness_load_points == 40


def test_week_boundaries_and_as_of_date_are_validated(
    tmp_path,
    monkeypatch,
) -> None:
    repo = _prepare_repo(tmp_path, monkeypatch)

    try:
        build_weekly_coach_context(
            repo,
            week_start=date(2026, 7, 28),
            as_of_date=date(2026, 7, 29),
        )
    except ValueError as exc:
        assert "Monday" in str(exc)
    else:
        raise AssertionError("non-Monday week start must fail")

    try:
        build_weekly_coach_context(
            repo,
            week_start=date(2026, 7, 27),
            as_of_date=date(2026, 7, 26),
        )
    except ValueError as exc:
        assert "week start" in str(exc)
    else:
        raise AssertionError("as-of date before week must fail")


def test_recovery_uses_latest_non_null_observation_per_signal() -> None:
    as_of_date = date(2026, 7, 30)
    wellness = {
        date(2026, 7, 29): WellnessDay(
            local_date=date(2026, 7, 29),
            hrv_rmssd_ms=55,
            sleep_score=82,
            sleep_quality=3,
            average_sleeping_hr_bpm=46,
            hydration=4,
            provider_hydration_volume_value=2.4,
            provider_readiness_value=71,
        ),
        as_of_date: WellnessDay(
            local_date=as_of_date,
            fitness_load_points=50,
            fatigue_load_points=55,
        ),
    }

    result = build_recovery_context(wellness, as_of_date=as_of_date)

    hrv = next(signal for signal in result.signals if signal.name == "hrv_rmssd")
    assert hrv.current_date == date(2026, 7, 29)
    assert hrv.current_value == 55
    assert "hrv_rmssd" not in result.missing_signals
    for signal_name in (
        "sleep_score",
        "sleep_quality",
        "average_sleeping_hr",
        "hydration",
        "provider_hydration_volume",
        "provider_readiness",
    ):
        signal = next(item for item in result.signals if item.name == signal_name)
        assert signal.current_date == date(2026, 7, 29)
        assert signal.observation_age_days == 1


def test_run_exposure_never_presents_partial_distance_as_complete_zero() -> None:
    missing_distance = make_activity(
        id="missing-distance",
        sport="run",
        distance_meters=None,
        elevation_gain_meters=None,
        duration_seconds=3_599,
    )

    result = run_exposure([missing_distance])

    assert result.distance_km is None
    assert result.elevation_gain_meters is None
    assert result.longest_run_distance_km is None
    assert result.elapsed_duration_seconds == 3_599
