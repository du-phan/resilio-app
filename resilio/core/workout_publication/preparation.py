"""Provider-aware validation and rendering for one publication attempt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.workout_publication.naming import provider_workout_name
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    event_target_for_modes,
    event_type_for_sport,
    external_id_for,
    garmin_filter_allows,
    provider_local_date,
    publication_fingerprint,
    publication_settings_version,
    settings_for_event_type,
    sha256_text,
    uid_for,
    validated_local_start,
)
from resilio.core.workout_publication.renderer import render_structured_workout
from resilio.core.workout_publication.semantics import (
    StepSemantics,
    WorkoutSemanticsError,
    expected_workout_semantics,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import (
    AthleteDTO,
    ConnectionsDTO,
    EventWriteDTO,
    SportSettingsDTO,
)
from resilio.schemas.activity import SportType
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout
from resilio.schemas.structured_workout import TargetMode, TargetUnit


@dataclass(frozen=True)
class PreparedPublication:
    """All immutable inputs required to reconcile one remote event."""

    workout: RunningWorkoutPrescription
    workout_identity: PlanWorkoutIdentity
    applied_week_approval_id: str
    applied_running_workouts_sha256: str
    workout_prescription_sha256: str
    schedule_timezone: str
    athlete_id: str
    event: EventWriteDTO
    requested_uid: str
    external_id: str
    settings_version_sha256: str
    publication_fingerprint_sha256: str
    rendered_workout_sha256: str
    provider_occurrence_date: date
    provider_start_date_local: str
    garmin_forwarding_eligible: bool
    expected_step_semantics: tuple[StepSemantics, ...]


def rendered_workout_sha256(workout: RunningWorkoutPrescription) -> str:
    """Identify the provider workout body independent of provider settings."""
    if workout.structured_workout is None:
        raise PublicationSafetyError("Publishing requires a typed structured_workout")
    rendered_steps = render_structured_workout(workout.structured_workout.steps)
    purpose = " ".join((workout.purpose or "").split())
    rendered = f"{purpose}\n\n{rendered_steps}" if purpose else rendered_steps
    return sha256_text(rendered)


def prepare_publication(
    client: IntervalsIcuClient,
    authoritative_workout: AuthoritativeWorkout,
    *,
    previous: PublishedWorkout | None,
    provider_occurrence_date: date,
    provider_name: str | None = None,
) -> PreparedPublication:
    """Validate device policy, render content, and bind deterministic identity."""
    workout = authoritative_workout.prescription
    if previous is not None and previous.workout_identity != authoritative_workout.identity:
        raise PublicationSafetyError("Published workout belongs to different plan lineage")
    if workout.structured_workout is None:
        raise PublicationSafetyError("Publishing requires a typed structured_workout")
    if SportType(workout.structured_workout.sport) != SportType(workout.sport):
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
    _validate_target_settings(
        modes=modes,
        settings=settings,
        workout=workout,
    )
    garmin_eligible = _garmin_forwarding_eligible(
        event_type=event_type,
        athlete=athlete,
        connections=connections,
    )

    rendered_steps = render_structured_workout(workout.structured_workout.steps)
    purpose = " ".join((workout.purpose or "").split())
    rendered = f"{purpose}\n\n{rendered_steps}" if purpose else rendered_steps
    try:
        expected_semantics = expected_workout_semantics(workout.structured_workout.steps)
    except WorkoutSemanticsError as exc:
        raise PublicationSafetyError(str(exc)) from exc
    external_id = external_id_for(workout.id)
    requested_uid = uid_for(workout.id)
    start_local = validated_local_start(
        provider_occurrence_date,
        workout.start_time_local,
        athlete.timezone,
    )
    event = EventWriteDTO(
        uid=previous.uid if previous is not None else requested_uid,
        external_id=external_id,
        type=event_type,
        name=provider_name or provider_workout_name(workout),
        description=rendered,
        start_date_local=start_local,
        target=event_target_for_modes(modes),
    )
    target_units = {str(target.unit) for target in workout.structured_workout.targets()}
    settings_version_sha256 = publication_settings_version(
        settings,
        target_modes=modes,
        target_units=target_units,
    )
    return PreparedPublication(
        workout=workout,
        workout_identity=authoritative_workout.identity,
        applied_week_approval_id=authoritative_workout.applied_week_approval_id,
        applied_running_workouts_sha256=(authoritative_workout.applied_running_workouts_sha256),
        workout_prescription_sha256=canonical_data_sha256(workout),
        schedule_timezone=authoritative_workout.schedule_timezone,
        athlete_id=athlete.id,
        event=event,
        requested_uid=requested_uid,
        external_id=external_id,
        settings_version_sha256=settings_version_sha256,
        publication_fingerprint_sha256=publication_fingerprint(
            event,
            settings_version_sha256,
        ),
        rendered_workout_sha256=rendered_workout_sha256(workout),
        provider_occurrence_date=provider_occurrence_date,
        provider_start_date_local=start_local,
        garmin_forwarding_eligible=garmin_eligible,
        expected_step_semantics=expected_semantics,
    )


def prepare_current_authority_pending(
    client: IntervalsIcuClient,
    authoritative_workout: AuthoritativeWorkout,
    *,
    previous: PublishedWorkout | None,
    pending: PendingWorkoutPublication,
    provider_name: str,
) -> PreparedPublication:
    """Rebuild and prove one pending intent from unchanged current authority."""
    prepared = prepare_publication(
        client,
        authoritative_workout,
        previous=previous,
        provider_name=provider_name,
        provider_occurrence_date=provider_local_date(
            pending.provider_start_date_local
        ),
    )
    if (
        pending.workout_identity != prepared.workout_identity
        or pending.applied_week_approval_id != prepared.applied_week_approval_id
        or pending.applied_running_workouts_sha256
        != prepared.applied_running_workouts_sha256
        or pending.workout_prescription_sha256
        != prepared.workout_prescription_sha256
        or pending.schedule_timezone != prepared.schedule_timezone
        or pending.occurrence_date != prepared.workout.date
        or pending.approved_start_time_local != prepared.workout.start_time_local
        or pending.uid != prepared.event.uid
        or pending.external_id != prepared.external_id
        or pending.publication_fingerprint_sha256
        != prepared.publication_fingerprint_sha256
        or pending.rendered_workout_sha256 != prepared.rendered_workout_sha256
        or pending.sport_settings_version_sha256
        != prepared.settings_version_sha256
        or pending.provider_start_date_local != prepared.provider_start_date_local
    ):
        raise PublicationSafetyError(
            "Pending publication intent differs from current applied workout authority"
        )
    return prepared


def _garmin_forwarding_eligible(
    *,
    event_type: str,
    athlete: AthleteDTO,
    connections: ConnectionsDTO,
) -> bool:
    return (
        connections.garmin_training_connected
        and athlete.garmin_upload_workouts is True
        and garmin_filter_allows(athlete.garmin_upload_filters, event_type)
    )


def _validate_target_settings(
    *,
    modes: set[str],
    settings: SportSettingsDTO,
    workout: RunningWorkoutPrescription,
) -> None:
    """Enforce sport-setting requirements that preserve prescribed targets."""
    assert workout.structured_workout is not None
    target_units = {str(target.unit) for target in workout.structured_workout.targets()}
    if len(modes) > 1:
        raise PublicationSafetyError("A published running workout must use at most one target mode")
    if TargetMode.PACE in modes and (
        settings.threshold_speed_meters_per_second is None or not settings.pace_zones
    ):
        raise PublicationSafetyError(
            "Pace-target publication requires threshold pace and pace zones"
        )
    if TargetMode.POWER in modes:
        raise PublicationSafetyError(
            "Running workout publication supports targetless, pace, or heart-rate steps"
        )
    if TargetUnit.PERCENT_LTHR in target_units and settings.lthr is None:
        raise PublicationSafetyError(
            "Percent-LTHR publication requires lactate-threshold heart rate"
        )
    if TargetUnit.PERCENT_MAX_HEART_RATE in target_units and settings.max_hr is None:
        raise PublicationSafetyError(
            "Percent-max-heart-rate publication requires maximum heart rate"
        )
