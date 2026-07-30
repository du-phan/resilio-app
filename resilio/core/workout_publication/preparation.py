"""Provider-aware validation and rendering for one publication attempt."""

from __future__ import annotations

from dataclasses import dataclass

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    event_target_for_modes,
    event_type_for_sport,
    external_id_for,
    garmin_filter_allows,
    publication_fingerprint,
    settings_for_event_type,
    sha256_text,
    sport_settings_version,
    uid_for,
    validated_local_start,
)
from resilio.core.workout_publication.renderer import render_structured_workout
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import (
    AthleteDTO,
    ConnectionsDTO,
    EventWriteDTO,
    SportSettingsDTO,
)
from resilio.schemas.plan import WorkoutPrescription
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import PublishedWorkout
from resilio.schemas.structured_workout import TargetMode


@dataclass(frozen=True)
class PreparedPublication:
    """All immutable inputs required to reconcile one remote event."""

    workout: WorkoutPrescription
    workout_identity: PlanWorkoutIdentity
    athlete_id: str
    event: EventWriteDTO
    requested_uid: str
    external_id: str
    settings_version_sha256: str
    publication_fingerprint_sha256: str
    rendered_workout_sha256: str
    start_date_local: str


def prepare_publication(
    client: IntervalsIcuClient,
    authoritative_workout: AuthoritativeWorkout,
    *,
    previous: PublishedWorkout | None,
) -> PreparedPublication:
    """Validate device policy, render content, and bind deterministic identity."""
    workout = authoritative_workout.prescription
    if previous is not None and previous.workout_identity != authoritative_workout.identity:
        raise PublicationSafetyError("Published workout ID belongs to a different plan lineage")
    if workout.structured_workout is None:
        raise PublicationSafetyError("Publishing requires a typed structured_workout")
    if str(workout.structured_workout.sport) != str(workout.sport):
        raise PublicationSafetyError("Workout sport does not match its structure")

    athlete = client.get_athlete()
    if not athlete.timezone:
        raise PublicationSafetyError("Athlete timezone is required for publication")
    connections = client.get_connections(athlete.id)
    event_type = event_type_for_sport(workout.sport)
    settings = settings_for_event_type(
        client.get_sport_settings(athlete.id),
        event_type,
    )
    modes = workout.structured_workout.target_modes()
    _validate_device_policy(
        event_type=event_type,
        modes=modes,
        athlete=athlete,
        connections=connections,
        settings=settings,
        workout=workout,
    )

    if workout.start_time_local is None:
        raise PublicationSafetyError(
            "Publishing requires the exact athlete-approved local start time"
        )
    rendered = render_structured_workout(workout.structured_workout.steps)
    external_id = external_id_for(workout.id)
    requested_uid = uid_for(workout.id)
    start_local = validated_local_start(
        workout.date,
        workout.start_time_local,
        athlete.timezone,
    )
    event = EventWriteDTO(
        uid=previous.uid if previous is not None else requested_uid,
        external_id=external_id,
        type=event_type,
        name=workout.purpose or str(workout.workout_type),
        description=rendered,
        start_date_local=start_local,
        target=event_target_for_modes(modes),
    )
    settings_version_sha256 = sport_settings_version(settings)
    return PreparedPublication(
        workout=workout,
        workout_identity=authoritative_workout.identity,
        athlete_id=athlete.id,
        event=event,
        requested_uid=requested_uid,
        external_id=external_id,
        settings_version_sha256=settings_version_sha256,
        publication_fingerprint_sha256=publication_fingerprint(
            event,
            settings_version_sha256,
        ),
        rendered_workout_sha256=sha256_text(rendered),
        start_date_local=start_local,
    )


def _validate_device_policy(
    *,
    event_type: str,
    modes: set[str],
    athlete: AthleteDTO,
    connections: ConnectionsDTO,
    settings: SportSettingsDTO,
    workout: WorkoutPrescription,
) -> None:
    """Enforce provider device and sport-setting preconditions."""
    garmin_connected = connections.garmin_training_connected
    wahoo_connected = connections.wahoo_connected
    if not (garmin_connected or wahoo_connected):
        raise PublicationSafetyError("No supported device workout connection is active")
    if garmin_connected:
        if athlete.garmin_upload_workouts is not True:
            raise PublicationSafetyError("Garmin planned-workout forwarding is not enabled")
        if not garmin_filter_allows(
            athlete.garmin_upload_filters,
            event_type,
        ):
            raise PublicationSafetyError(f"Garmin workout filters do not admit {event_type}")
    if wahoo_connected and athlete.wahoo_upload_workouts is not True:
        raise PublicationSafetyError("Wahoo planned-workout forwarding is not enabled")
    if TargetMode.PACE in modes and (
        settings.threshold_speed_meters_per_second is None or not settings.pace_zones
    ):
        raise PublicationSafetyError(
            "Pace-target publication requires threshold pace and pace zones"
        )
    if TargetMode.POWER in modes and settings.ftp is None:
        raise PublicationSafetyError("Power-target publication requires FTP")
    if wahoo_connected and len(modes) > 1:
        raise PublicationSafetyError("Mixed target modes are blocked for Wahoo publication")
    assert workout.structured_workout is not None
    if wahoo_connected and workout.structured_workout.uses_lap_press():
        raise PublicationSafetyError(
            "Lap-button steps are blocked for Wahoo until device support is verified"
        )
