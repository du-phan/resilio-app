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
    AthleteProfile,
    ConflictPolicy,
    Goal,
    GoalType,
    OtherSport,
    PauseReason,
    PBEntry,
    RunningPriority,
    TrainingConstraints,
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


def create_profile(
    *,
    athlete_name: str,
    training_timezone: str,
    age_years: int | None = None,
    running_experience_years: float | None = None,
    running_priority: str = RunningPriority.EQUAL.value,
    primary_sport_name: str | None = None,
    conflict_policy: str = ConflictPolicy.ASK_EACH_TIME.value,
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
            created_on=date.today(),
            training_timezone=training_timezone,
            age_years=age_years,
            running_experience_years=running_experience_years,
            constraints=TrainingConstraints(
                unavailable_run_days=unavailable_run_days or [],
                minimum_run_days_per_week=minimum_run_days_per_week,
                maximum_run_days_per_week=maximum_run_days_per_week,
                maximum_session_duration_minutes=maximum_session_duration_minutes,
            ),
            running_priority=RunningPriority(running_priority),
            primary_sport_name=primary_sport_name,
            conflict_policy=ConflictPolicy(conflict_policy),
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
    """Update explicit v2 fields; unknown and legacy fields are rejected."""
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


def add_sport_to_profile(
    *,
    sport_name: str,
    sessions_per_week: int,
    typical_session_duration_minutes: int = 60,
    typical_intensity: str = "moderate",
    unavailable_days: list[Weekday] | None = None,
    notes: str | None = None,
) -> AthleteProfile | ProfileError:
    profile = get_profile()
    if isinstance(profile, ProfileError):
        return profile
    try:
        commitment = OtherSport(
            sport_name=sport_name,
            sessions_per_week=sessions_per_week,
            typical_session_duration_minutes=typical_session_duration_minutes,
            typical_intensity=TypicalIntensity(typical_intensity),
            unavailable_days=unavailable_days or [],
            notes=notes,
        )
        commitments = [*profile.other_sport_commitments, commitment]
        return update_profile(
            other_sport_commitments=[item.model_dump(mode="json") for item in commitments]
        )
    except (ValueError, ValidationError) as exc:
        return _profile_failure(exc)


def remove_sport_from_profile(sport_name: str) -> AthleteProfile | ProfileError:
    profile = get_profile()
    if isinstance(profile, ProfileError):
        return profile
    target = sport_name.casefold()
    commitments = [
        item for item in profile.other_sport_commitments if item.sport_name.casefold() != target
    ]
    if len(commitments) == len(profile.other_sport_commitments):
        return ProfileError("not_found", f"No sport commitment named {sport_name!r}")
    return update_profile(
        other_sport_commitments=[item.model_dump(mode="json") for item in commitments]
    )


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
    target = sport_name.casefold()
    found = False
    commitments: list[OtherSport] = []
    try:
        for item in profile.other_sport_commitments:
            if item.sport_name.casefold() != target:
                commitments.append(item)
                continue
            found = True
            payload = item.model_dump(mode="json")
            payload.update(
                {
                    "active": active,
                    "pause_reason": (None if active else PauseReason(pause_reason or "").value),
                    "paused_on": None if active else (paused_on or date.today()),
                }
            )
            commitments.append(OtherSport.model_validate(payload))
    except (ValueError, ValidationError) as exc:
        return _profile_failure(exc)
    if not found:
        return ProfileError("not_found", f"No sport commitment named {sport_name!r}")
    return update_profile(
        other_sport_commitments=[item.model_dump(mode="json") for item in commitments]
    )


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
