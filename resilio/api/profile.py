"""Presentation-neutral athlete-profile operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from pydantic import ValidationError

from resilio.api.vdot import VDOTError, calculate_vdot_from_race
from resilio.core.local_dates import athlete_local_date
from resilio.core.profile.candidates import build_provider_profile_candidates
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.core.training_state_repository import load_sport_settings, load_wellness
from resilio.core.vdot import parse_time_string
from resilio.schemas.profile import (
    AthleteManagedSport,
    AthleteManagedSportFirstPriority,
    AthleteProfile,
    BalancedTrainingPriority,
    FlexibleWeeklyParticipation,
    Goal,
    GoalType,
    PauseReason,
    PBEntry,
    RecurringWeeklyParticipation,
    RunningFirstTrainingPriority,
    RunSameDayPermission,
    TrainingConstraints,
    TrainingPriority,
    TypicalIntensity,
    Weekday,
)
from resilio.schemas.training_state import ProviderProfileCandidates
from resilio.schemas.vdot import RaceDistance


@dataclass(frozen=True)
class ProfileError:
    error_type: str
    message: str


def _repository() -> ProfileRepository:
    return ProfileRepository(RepositoryIO())


def _profile_failure(exc: Exception) -> ProfileError:
    return ProfileError("validation", str(exc))


def _sport_lookup_key(sport_name: str) -> str:
    return sport_name.strip().casefold()


def create_profile(
    *,
    athlete_name: str,
    training_timezone: str,
    age_years: int | None = None,
    running_experience_years: float | None = None,
    minimum_run_days_per_week: int = 2,
    maximum_run_days_per_week: int = 4,
    unavailable_run_days: list[Weekday] | None = None,
    maximum_session_duration_minutes: int | None = 90,
    weather_location: str | None = None,
) -> AthleteProfile | ProfileError:
    """Create one athlete-confirmed profile without provider-derived fields."""
    repository = _repository()
    try:
        weather_preferences = None
        if weather_location is not None:
            from resilio.schemas.weather import WeatherLocation

            weather_preferences = WeatherLocation(location_query=weather_location.strip())
        profile = AthleteProfile(
            athlete_name=athlete_name,
            created_on=athlete_local_date(training_timezone),
            training_timezone=training_timezone,
            age_years=age_years,
            running_experience_years=running_experience_years,
            constraints=TrainingConstraints(
                unavailable_run_days=unavailable_run_days or [],
                minimum_run_days_per_week=minimum_run_days_per_week,
                maximum_run_days_per_week=maximum_run_days_per_week,
                maximum_session_duration_minutes=maximum_session_duration_minutes,
            ),
            training_priority=BalancedTrainingPriority(),
            weather_preferences=weather_preferences,
        )
        return repository.create(profile)
    except (OSError, ValueError, ValidationError) as exc:
        if str(exc) == "Athlete profile already exists":
            return ProfileError("already_exists", str(exc))
        return _profile_failure(exc)


def get_profile() -> AthleteProfile | ProfileError:
    try:
        profile = _repository().load(allow_missing=True)
    except (OSError, ValueError) as exc:
        return _profile_failure(exc)
    if profile is None:
        return ProfileError("not_found", "Athlete profile does not exist")
    return profile


def update_profile(**fields: Any) -> AthleteProfile | ProfileError:
    """Update explicit current-schema fields; unknown fields are rejected."""
    if not fields:
        return ProfileError("validation", "At least one field is required")
    try:
        return _repository().update(fields)
    except (OSError, ValueError, ValidationError) as exc:
        return _profile_failure(exc)


def set_personal_best(
    *,
    distance: str,
    elapsed_time: str,
    performance_date: date,
) -> AthleteProfile | ProfileError:
    try:
        race_distance = RaceDistance(distance.casefold())
    except ValueError:
        return ProfileError("validation", f"Unsupported race distance: {distance}")
    profile = get_profile()
    if isinstance(profile, ProfileError):
        return profile
    result = calculate_vdot_from_race(
        race_distance.value,
        elapsed_time,
        performance_date.isoformat(),
        as_of_date=athlete_local_date(profile.training_timezone),
    )
    if isinstance(result, VDOTError):
        return ProfileError(result.error_type, result.message)
    personal_bests = dict(profile.personal_bests_by_distance)
    personal_bests[race_distance.value] = PBEntry(
        elapsed_time_seconds=result.source_time_seconds,
        performance_date=performance_date,
        vdot=result.vdot,
    )
    return update_profile(
        personal_bests_by_distance={
            name: entry.model_dump(mode="json") for name, entry in personal_bests.items()
        }
    )


def set_goal(
    race_type: str,
    target_date: date | None = None,
    target_time: str | None = None,
) -> Goal | ProfileError:
    try:
        goal_type = GoalType(race_type)
        target_finish_time_seconds = (
            parse_time_string(target_time) if target_time is not None else None
        )
        goal = Goal(
            type=goal_type,
            target_date=target_date,
            target_finish_time_seconds=target_finish_time_seconds,
        )
    except (ValueError, ValidationError) as exc:
        return _profile_failure(exc)
    result = update_profile(goal=goal.model_dump(mode="json"))
    return result if isinstance(result, ProfileError) else result.goal


def _training_priority(
    kind: str,
    *,
    priority_sport_name: str | None,
) -> TrainingPriority:
    if kind == "running_first":
        if priority_sport_name is not None:
            raise ValueError("running-first priority cannot name another sport")
        return RunningFirstTrainingPriority()
    if kind == "balanced":
        if priority_sport_name is not None:
            raise ValueError("balanced priority cannot name another sport")
        return BalancedTrainingPriority()
    if kind == "athlete_managed_sport_first":
        if priority_sport_name is None:
            raise ValueError("athlete-managed-sport-first priority requires a sport name")
        return AthleteManagedSportFirstPriority(sport_name=priority_sport_name)
    raise ValueError(f"Unsupported training priority kind: {kind}")


def set_training_priority(
    *,
    kind: str,
    priority_sport_name: str | None = None,
) -> AthleteProfile | ProfileError:
    try:
        priority = _training_priority(
            kind,
            priority_sport_name=priority_sport_name,
        )
    except (ValueError, ValidationError) as exc:
        return _profile_failure(exc)
    return update_profile(training_priority=priority.model_dump(mode="json"))


def _upsert_athlete_managed_sport(
    profile: AthleteProfile,
    sport: AthleteManagedSport,
) -> AthleteProfile | ProfileError:
    target = _sport_lookup_key(sport.sport_name)
    existing = next(
        (
            item
            for item in profile.athlete_managed_sports
            if _sport_lookup_key(item.sport_name) == target
        ),
        None,
    )
    if existing is not None:
        payload = sport.model_dump(mode="json")
        payload.update(
            {
                "active": existing.active,
                "pause_reason": existing.pause_reason,
                "paused_on": existing.paused_on,
            }
        )
        sport = AthleteManagedSport.model_validate(payload)
    sports = [
        item
        for item in profile.athlete_managed_sports
        if _sport_lookup_key(item.sport_name) != target
    ]
    sports.append(sport)
    return update_profile(athlete_managed_sports=[item.model_dump(mode="json") for item in sports])


def set_flexible_athlete_managed_sport(
    *,
    sport_name: str,
    expected_sessions_per_week: int,
    typical_session_duration_minutes: int = 60,
    typical_intensity: str = "moderate",
    athlete_context_note: str | None = None,
) -> AthleteProfile | ProfileError:
    profile = get_profile()
    if isinstance(profile, ProfileError):
        return profile
    try:
        sport = AthleteManagedSport(
            sport_name=sport_name,
            participation_pattern=FlexibleWeeklyParticipation(
                expected_sessions_per_week=expected_sessions_per_week,
            ),
            typical_session_duration_minutes=typical_session_duration_minutes,
            athlete_reported_typical_intensity=TypicalIntensity(typical_intensity),
            athlete_context_note=athlete_context_note,
        )
        return _upsert_athlete_managed_sport(profile, sport)
    except (ValueError, ValidationError) as exc:
        return _profile_failure(exc)


def set_recurring_athlete_managed_sport(
    *,
    sport_name: str,
    weekdays: list[Weekday],
    run_same_day_permission: str,
    typical_session_duration_minutes: int = 60,
    typical_intensity: str = "moderate",
    athlete_context_note: str | None = None,
) -> AthleteProfile | ProfileError:
    profile = get_profile()
    if isinstance(profile, ProfileError):
        return profile
    try:
        sport = AthleteManagedSport(
            sport_name=sport_name,
            participation_pattern=RecurringWeeklyParticipation(
                weekdays=weekdays,
                run_same_day_permission=RunSameDayPermission(run_same_day_permission),
            ),
            typical_session_duration_minutes=typical_session_duration_minutes,
            athlete_reported_typical_intensity=TypicalIntensity(typical_intensity),
            athlete_context_note=athlete_context_note,
        )
        return _upsert_athlete_managed_sport(profile, sport)
    except (ValueError, ValidationError) as exc:
        return _profile_failure(exc)


def remove_athlete_managed_sport(sport_name: str) -> AthleteProfile | ProfileError:
    profile = get_profile()
    if isinstance(profile, ProfileError):
        return profile
    target = _sport_lookup_key(sport_name)
    sports = [
        item
        for item in profile.athlete_managed_sports
        if _sport_lookup_key(item.sport_name) != target
    ]
    if len(sports) == len(profile.athlete_managed_sports):
        return ProfileError("not_found", f"No athlete-managed sport named {sport_name!r}")
    return update_profile(athlete_managed_sports=[item.model_dump(mode="json") for item in sports])


def set_sport_active_state(
    *,
    sport_name: str,
    active: bool,
    pause_reason: str | None = None,
    paused_on: date | None = None,
) -> AthleteProfile | ProfileError:
    profile = get_profile()
    if isinstance(profile, ProfileError):
        return profile
    target = _sport_lookup_key(sport_name)
    found = False
    sports: list[AthleteManagedSport] = []
    try:
        for item in profile.athlete_managed_sports:
            if _sport_lookup_key(item.sport_name) != target:
                sports.append(item)
                continue
            found = True
            payload = item.model_dump(mode="json")
            payload.update(
                {
                    "active": active,
                    "pause_reason": (None if active else PauseReason(pause_reason or "").value),
                    "paused_on": (
                        None
                        if active
                        else (paused_on or athlete_local_date(profile.training_timezone))
                    ),
                }
            )
            sports.append(AthleteManagedSport.model_validate(payload))
    except (ValueError, ValidationError) as exc:
        return _profile_failure(exc)
    if not found:
        return ProfileError("not_found", f"No athlete-managed sport named {sport_name!r}")
    return update_profile(athlete_managed_sports=[item.model_dump(mode="json") for item in sports])


def get_provider_profile_candidates(
    *,
    as_of_date: date,
    generated_at_utc: datetime | None = None,
) -> ProviderProfileCandidates | ProfileError:
    """Return provider evidence without mutating the athlete profile."""
    repo = RepositoryIO()
    try:
        return build_provider_profile_candidates(
            load_sport_settings(repo),
            load_wellness(repo),
            as_of_date=as_of_date,
            generated_at_utc=generated_at_utc or datetime.now(timezone.utc),
        )
    except (OSError, ValueError, ValidationError) as exc:
        return _profile_failure(exc)
