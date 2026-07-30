from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from resilio.api.profile import (
    ProfileError,
    create_profile,
    get_profile,
    set_personal_best,
    update_profile,
)
from resilio.core.profile.candidates import build_provider_profile_candidates
from resilio.schemas.profile import (
    AthleteProfile,
    ConflictPolicy,
    Goal,
    GoalType,
    RunningPriority,
    TrainingConstraints,
)
from resilio.schemas.training_state import (
    SportSettings,
    SportSettingsSnapshot,
    WellnessDay,
)


def test_profile_rejects_derived_and_provider_owned_legacy_fields() -> None:
    with pytest.raises(ValidationError):
        AthleteProfile.model_validate(
            {
                "schema_version": 2,
                "athlete_name": "Alex",
                "created_on": "2026-07-30",
                "constraints": {
                    "minimum_run_days_per_week": 2,
                    "maximum_run_days_per_week": 4,
                },
                "running_priority": "equal",
                "conflict_policy": "ask_each_time",
                "goal": {"type": "general_fitness"},
                "current_weekly_run_km": 42,
                "vital_signs": {"max_hr": 190},
            }
        )


def test_constraints_reject_minimum_above_actual_availability() -> None:
    with pytest.raises(ValidationError, match="available days"):
        TrainingConstraints(
            unavailable_run_days=["monday", "tuesday", "wednesday", "thursday"],
            minimum_run_days_per_week=4,
            maximum_run_days_per_week=4,
        )


@pytest.mark.parametrize(
    "run_sport_name",
    ["run", "trail_run", "treadmill_run", "track_run"],
)
def test_other_sport_commitments_reject_all_run_variants(
    run_sport_name: str,
) -> None:
    with pytest.raises(ValidationError, match="not an other-sport"):
        AthleteProfile(
            athlete_name="Alex",
            created_on=date(2026, 7, 30),
            training_timezone="Europe/Paris",
            constraints=TrainingConstraints(
                minimum_run_days_per_week=2,
                maximum_run_days_per_week=4,
            ),
            other_sport_commitments=[
                {
                    "sport_name": run_sport_name,
                    "sessions_per_week": 1,
                }
            ],
            running_priority=RunningPriority.PRIMARY,
            conflict_policy=ConflictPolicy.ASK_EACH_TIME,
        )


def test_provider_candidates_preserve_scope_units_and_temporary_status() -> None:
    settings = SportSettingsSnapshot(
        fingerprint_sha256="a" * 64,
        settings=[
            SportSettings(
                provider_settings_id=7,
                source_sport_types=["Run", "TrailRun"],
                lactate_threshold_hr_bpm=172,
                maximum_hr_bpm=194,
                threshold_speed_meters_per_second=3.9215686,
                pace_display_unit="MINS_KM",
                heart_rate_zone_upper_bounds_bpm=[140, 158, 172, 183],
            )
        ],
    )
    wellness = {
        date(2026, 7, 29): WellnessDay(
            local_date=date(2026, 7, 29),
            resting_hr_bpm=47,
        ),
        date(2026, 7, 30): WellnessDay(
            local_date=date(2026, 7, 30),
            resting_hr_bpm=51,
            resting_hr_is_temporary=True,
            vo2_max_ml_per_kg_per_min=57.2,
        ),
    }

    result = build_provider_profile_candidates(
        settings,
        wellness,
        as_of_date=date(2026, 7, 30),
        generated_at_utc=datetime(2026, 7, 30, 12, tzinfo=timezone.utc),
    )

    metrics = {candidate.metric_name: candidate for candidate in result.candidates}
    assert metrics["lactate_threshold_heart_rate"].value == 172
    assert metrics["lactate_threshold_heart_rate"].unit == "bpm"
    assert metrics["lactate_threshold_heart_rate"].source_sport_types == [
        "Run",
        "TrailRun",
    ]
    assert metrics["threshold_speed"].value == 3.9215686
    assert metrics["threshold_speed"].unit == "meters_per_second"
    assert metrics["resting_heart_rate"].observed_on == date(2026, 7, 30)
    assert metrics["resting_heart_rate"].is_temporary is True
    assert metrics["provider_vo2_max"].unit == "milliliters_per_kilogram_per_minute"


def test_provider_candidates_do_not_fill_missing_metrics() -> None:
    result = build_provider_profile_candidates(
        SportSettingsSnapshot(fingerprint_sha256="b" * 64, settings=[]),
        {},
        as_of_date=date(2026, 7, 30),
        generated_at_utc=datetime(2026, 7, 30, 12, tzinfo=timezone.utc),
    )

    assert result.candidates == []


def test_clean_profile_contract_round_trips() -> None:
    profile = AthleteProfile(
        athlete_name="Alex",
        created_on=date(2026, 7, 30),
        training_timezone="Europe/Paris",
        constraints=TrainingConstraints(
            minimum_run_days_per_week=3,
            maximum_run_days_per_week=5,
        ),
        running_priority=RunningPriority.PRIMARY,
        conflict_policy=ConflictPolicy.ASK_EACH_TIME,
        goal=Goal(type=GoalType.TEN_K, target_date=date(2026, 10, 4)),
    )

    assert AthleteProfile.model_validate(profile.model_dump()).schema_version == 2


def test_profile_api_persists_only_v2_contract(tmp_path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    created = create_profile(
        athlete_name="Alex",
        training_timezone="Europe/Paris",
        age_years=32,
        minimum_run_days_per_week=3,
        maximum_run_days_per_week=5,
    )

    assert isinstance(created, AthleteProfile)
    assert created.athlete_name == "Alex"
    assert get_profile() == created

    rejected = update_profile(current_weekly_run_km=42)
    assert isinstance(rejected, ProfileError)
    assert "Unknown athlete profile fields" in rejected.message


def test_personal_best_stores_seconds_date_and_calculated_vdot(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    assert isinstance(
        create_profile(
            athlete_name="Alex",
            training_timezone="Europe/Paris",
        ),
        AthleteProfile,
    )

    updated = set_personal_best(
        distance="10k",
        elapsed_time="42:30",
        performance_date=date(2026, 7, 1),
    )

    assert isinstance(updated, AthleteProfile)
    personal_best = updated.personal_bests_by_distance["10k"]
    assert personal_best.elapsed_time_seconds == 2_550
    assert personal_best.performance_date == date(2026, 7, 1)
    assert 30 <= personal_best.vdot <= 85
