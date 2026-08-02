"""Pure identity, rendering-fingerprint, and device-safety policies."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, time, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from resilio.core.workout_publication.semantics import (
    StepSemantics,
    WorkoutSemanticsError,
    assert_workout_semantics_match,
)
from resilio.integrations.intervals_icu.dto import (
    ActivityFilterDTO,
    EventDTO,
    EventWriteDTO,
    SportSettingsDTO,
)
from resilio.schemas.plan import WorkoutPrescription
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import (
    GarminForwardingStatus,
    PendingWorkoutPublication,
    PublicationPushError,
    PublishedWorkout,
)
from resilio.schemas.structured_workout import TargetMode, WorkoutSport

OWNERSHIP_PREFIX = "resilio:v1:workout:"


class PublicationSafetyError(RuntimeError):
    """Publication cannot proceed without complete ownership and safety proof."""


class ProviderSemanticsMismatchError(PublicationSafetyError):
    """Intervals parsed a different executable workout than prescribed."""


class RemoteWorkoutDriftError(PublicationSafetyError):
    """An exact owned event differs from its last verified remote fields."""


def external_id_for(workout_id: str) -> str:
    return f"{OWNERSHIP_PREFIX}{workout_id}"


def uid_for(workout_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, external_id_for(workout_id)))


def sha256_text(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


def sport_settings_version(settings: SportSettingsDTO) -> str:
    payload = settings.model_dump(mode="json", exclude_none=False)
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def publication_settings_version(
    settings: SportSettingsDTO,
    *,
    target_modes: set[str],
    target_units: set[str],
) -> str:
    """Hash only provider settings that can change prescribed step targets."""
    payload: dict[str, object] = {
        "target_modes": sorted(target_modes),
        "target_units": sorted(target_units),
    }
    if TargetMode.PACE in target_modes:
        payload["threshold_speed_meters_per_second"] = (
            settings.threshold_speed_meters_per_second
        )
        payload["pace_zones"] = settings.pace_zones
    if "percent_lthr" in target_units:
        payload["lactate_threshold_heart_rate_beats_per_minute"] = settings.lthr
    if "percent_max_heart_rate" in target_units:
        payload["maximum_heart_rate_beats_per_minute"] = settings.max_hr
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def publication_fingerprint(
    event: EventWriteDTO,
    settings_version: str,
) -> str:
    payload = {
        "event": event.model_dump(mode="json", exclude_none=False),
        "sport_settings_version": settings_version,
    }
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def provider_event_fingerprint(remote: EventDTO) -> str:
    """Fingerprint only provider fields owned and verified by Resilio."""
    payload = {
        "uid": remote.uid,
        "external_id": remote.external_id,
        "category": remote.category,
        "type": remote.type,
        "name": remote.name,
        "description": remote.description,
        "start_date_local": remote.start_date_local,
        "target": remote.target,
    }
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def assert_remote_unchanged(remote: EventDTO, previous: PublishedWorkout) -> None:
    if provider_event_fingerprint(remote) != previous.provider_event_fingerprint_sha256:
        raise RemoteWorkoutDriftError(
            "Remote event changed since Resilio verified the previous publication"
        )


def event_type_for_sport(sport: str) -> str:
    if sport == WorkoutSport.RUN:
        return "Run"
    raise PublicationSafetyError(
        f"Only running workouts can be published; received sport {sport!r}"
    )


def event_target_for_modes(
    modes: set[str],
) -> Literal["AUTO", "POWER", "HR", "PACE"]:
    if len(modes) != 1:
        return "AUTO"
    mode = next(iter(modes))
    if mode == TargetMode.PACE.value:
        return "PACE"
    if mode == TargetMode.HEART_RATE.value:
        return "HR"
    if mode == TargetMode.POWER.value:
        return "POWER"
    raise PublicationSafetyError(f"Unsupported workout target mode: {mode}")


def settings_for_event_type(
    settings: list[SportSettingsDTO],
    event_type: str,
) -> SportSettingsDTO:
    matches = [item for item in settings if event_type in item.types]
    if len(matches) != 1:
        raise PublicationSafetyError(
            f"Expected one sport-settings record for {event_type}, found {len(matches)}"
        )
    return matches[0]


def assert_remote_ownership(
    remote: EventDTO,
    *,
    uid: str,
    external_id: str,
) -> None:
    if remote.uid != uid or remote.external_id != external_id:
        raise PublicationSafetyError(
            "Remote event ownership proof failed: UID/external ID mismatch"
        )
    if not external_id.startswith(OWNERSHIP_PREFIX):
        raise PublicationSafetyError("Remote event is outside the Resilio namespace")


def assert_remote_external_ownership(
    remote: EventDTO,
    *,
    external_id: str,
) -> str:
    """Accept a server UID only when the external namespace survives."""
    if remote.external_id != external_id:
        raise PublicationSafetyError("Remote event ownership proof failed: external ID mismatch")
    if not external_id.startswith(OWNERSHIP_PREFIX):
        raise PublicationSafetyError("Remote event is outside the Resilio namespace")
    if not remote.uid:
        raise PublicationSafetyError("Remote event ownership proof failed: server UID is missing")
    return remote.uid


def assert_remote_matches(
    remote: EventDTO,
    event: EventWriteDTO,
    expected_step_semantics: tuple[StepSemantics, ...],
) -> None:
    """Require the remote owned event to match every rendered field."""
    if (
        remote.category != event.category
        or remote.start_date_local != event.start_date_local
        or remote.type != event.type
        or remote.name != event.name
        or remote.description != event.description
        or remote.target != event.target
    ):
        raise PublicationSafetyError(
            "Remote event read-back does not match the owned rendered workout"
        )
    if remote.workout_doc is None:
        raise ProviderSemanticsMismatchError(
            "Remote event read-back has no parsed workout document"
        )
    try:
        assert_workout_semantics_match(expected_step_semantics, remote.workout_doc)
    except WorkoutSemanticsError as exc:
        raise ProviderSemanticsMismatchError(
            f"Provider workout semantics mismatch: {exc}"
        ) from exc


def garmin_filter_allows(
    filters: list[ActivityFilterDTO],
    event_type: str,
) -> bool:
    """Prove that Garmin forwarding is unrestricted or admits the event type."""
    if not filters:
        return True
    type_filters = [item for item in filters if item.field_id == "type"]
    if not type_filters:
        return False
    target = event_type.casefold()
    negative_operators = {"!=", "not", "not_in", "notin"}
    for item in type_filters:
        values = _filter_values(item.value)
        if item.code:
            values.add(item.code.casefold())
        if (
            target in values
            and not item.not_
            and (item.operator or "").casefold() not in negative_operators
        ):
            return True
    return False


def _filter_values(value: object) -> set[str]:
    if isinstance(value, str):
        return {value.casefold()}
    if isinstance(value, (list, tuple, set)):
        return {nested for item in value for nested in _filter_values(item)}
    if isinstance(value, dict):
        return {nested for item in value.values() for nested in _filter_values(item)}
    return set()


def validated_local_start(
    occurrence_date: date,
    local_time: time | None,
    timezone_name: str,
) -> str:
    """Project an optional approved wall time into Intervals' local timestamp."""
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise PublicationSafetyError(
            f"Athlete timezone is not recognized: {timezone_name}"
        ) from exc

    naive = datetime.combine(occurrence_date, local_time or time.min)
    valid_offsets = {
        aware.utcoffset()
        for fold in (0, 1)
        if (aware := naive.replace(tzinfo=zone, fold=fold))
        .astimezone(timezone.utc)
        .astimezone(zone)
        .replace(tzinfo=None)
        == naive
    }
    if not valid_offsets:
        raise PublicationSafetyError(
            "Local workout time does not exist because of a daylight-saving transition"
        )
    if len(valid_offsets) > 1:
        raise PublicationSafetyError(
            "Local workout time is ambiguous because of a daylight-saving transition"
        )
    return naive.isoformat()


def provider_push_errors(remote: EventDTO) -> list[PublicationPushError]:
    return [
        PublicationPushError(
            service=error.service,
            message=error.message,
            observed_at_utc=error.date,
        )
        for error in remote.push_errors
    ]


def garmin_forwarding_status(
    *,
    eligible: bool,
    remote: EventDTO,
) -> GarminForwardingStatus:
    has_garmin_error = any("garmin" in error.service.casefold() for error in remote.push_errors)
    if has_garmin_error:
        return "provider_error_observed"
    return "eligible_unverified" if eligible else "not_configured"


def pending_matches(
    pending: PendingWorkoutPublication,
    *,
    uid: str,
    external_id: str,
    fingerprint: str,
) -> bool:
    return (
        pending.uid == uid
        and pending.external_id == external_id
        and pending.publication_fingerprint_sha256 == fingerprint
    )


def published_record(
    *,
    workout: WorkoutPrescription,
    workout_identity: PlanWorkoutIdentity,
    event_id: int,
    requested_uid: str,
    uid: str,
    external_id: str,
    fingerprint: str,
    rendered_hash: str,
    settings_version: str,
    provider_start_local: str,
    garmin_eligible: bool,
    remote: EventDTO,
) -> PublishedWorkout:
    """Build a verified provider read-back record."""
    return PublishedWorkout(
        workout_identity=workout_identity,
        event_id=event_id,
        requested_uid=requested_uid,
        uid=uid,
        external_id=external_id,
        publication_fingerprint_sha256=fingerprint,
        rendered_workout_sha256=rendered_hash,
        sport_settings_version_sha256=settings_version,
        provider_event_fingerprint_sha256=provider_event_fingerprint(remote),
        sport=str(workout.sport),
        occurrence_date=workout.date,
        approved_start_time_local=workout.start_time_local,
        provider_start_date_local=provider_start_local,
        garmin_forwarding_status=garmin_forwarding_status(
            eligible=garmin_eligible,
            remote=remote,
        ),
        provider_push_errors=provider_push_errors(remote),
        provider_computed_aerobic_load_points=remote.icu_training_load,
        provider_relative_intensity_percent=remote.icu_intensity,
        provider_fitness_load_points=remote.icu_ctl,
        provider_fatigue_load_points=remote.icu_atl,
        verified_at_utc=datetime.now(timezone.utc),
    )
