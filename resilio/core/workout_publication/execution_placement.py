"""Resolve retained provider dates and factual execution-date placement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.association_identity import (
    fulfillment_association_sha256,
)
from resilio.core.workout_fulfillment.evidence import (
    assert_fulfillment_authority_is_current,
    assert_fulfillment_is_usable,
)
from resilio.core.workout_fulfillment.remote_pairing_inspection import (
    validate_remote_performance_evidence,
)
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.authority_matching import (
    publication_record_has_retained_workout_authority,
    publication_record_matches_current_workout_authority,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    training_week_bounds,
)
from resilio.integrations.intervals_icu.activity_pairing import (
    activity_source_supports_pairing,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationManifest,
    PublishedWorkout,
)
from resilio.schemas.publication_placement import (
    FulfillmentProviderOccurrencePlacement,
    ProviderOccurrencePlacement,
)
from resilio.schemas.workout_fulfillment import (
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)

WorkoutIdentityKey = tuple[str, str, int, str]


@dataclass(frozen=True)
class ProviderOccurrencePlacements:
    """Current provider dates and workouts fixed to factual execution dates."""

    placements_by_local_workout_id: dict[str, ProviderOccurrencePlacement]
    fulfillment_workout_ids: frozenset[str]


def desired_provider_occurrence_placement(
    workout: AuthoritativeWorkout,
    retained_placement: ProviderOccurrencePlacement,
    verified_occurrence_dates: dict[str, date],
) -> tuple[date, ProviderOccurrencePlacement]:
    """Resolve a verified provider move over the retained placement state."""
    local_workout_id = workout.identity.local_workout_id
    retained_occurrence_date = retained_placement.effective_occurrence_date
    desired_occurrence_date = verified_occurrence_dates.get(
        local_workout_id,
        retained_occurrence_date,
    )
    if desired_occurrence_date == retained_occurrence_date:
        return desired_occurrence_date, retained_placement
    return desired_occurrence_date, ProviderOccurrencePlacement(
        calendar_source="provider_calendar",
        calendar_occurrence_date=desired_occurrence_date,
    )


def _identity_key(identity: PlanWorkoutIdentity) -> WorkoutIdentityKey:
    return (
        identity.plan_id,
        identity.plan_revision_id,
        identity.week_number,
        identity.local_workout_id,
    )


def _approved_placement(workout: AuthoritativeWorkout) -> ProviderOccurrencePlacement:
    return ProviderOccurrencePlacement.approved_schedule(workout.prescription.date)


def _fulfillment_override(
    fulfillment: WorkoutFulfillmentRecord,
) -> FulfillmentProviderOccurrencePlacement:
    return FulfillmentProviderOccurrencePlacement(
        local_activity_id=fulfillment.local_activity_id,
        fulfillment_association_sha256=fulfillment_association_sha256(fulfillment),
        execution_local_date=fulfillment.execution_local_date,
    )


def _override_matches_association(
    override: FulfillmentProviderOccurrencePlacement,
    fulfillment: WorkoutFulfillmentRecord,
) -> bool:
    return (
        override.local_activity_id == fulfillment.local_activity_id
        and override.fulfillment_association_sha256 == fulfillment_association_sha256(fulfillment)
    )


def _assert_override_has_lifecycle_authority(
    placement: ProviderOccurrencePlacement,
    fulfillment_manifest: WorkoutFulfillmentManifest,
) -> None:
    override = placement.fulfillment_override
    if override is None:
        return
    active = any(
        _override_matches_association(override, fulfillment)
        for fulfillment in fulfillment_manifest.fulfillments.values()
    )
    revoked = any(
        _override_matches_association(override, revocation.fulfillment)
        for revocation in fulfillment_manifest.revoked_fulfillments
    )
    if not active and not revoked:
        raise PublicationSafetyError(
            "Fulfillment provider placement lacks active or revoked exact authority"
        )


def _retained_calendar_placements(
    publication_manifest: PublicationManifest,
    fulfillment_manifest: WorkoutFulfillmentManifest,
    workouts: list[AuthoritativeWorkout],
) -> dict[str, ProviderOccurrencePlacement]:
    retained: dict[str, ProviderOccurrencePlacement] = {}
    for workout in workouts:
        local_workout_id = workout.identity.local_workout_id
        published = publication_manifest.workouts.get(local_workout_id)
        pending = publication_manifest.pending.get(local_workout_id)
        source_record: PublishedWorkout | PendingWorkoutPublication
        if pending is not None and publication_record_has_retained_workout_authority(
            pending,
            workout,
        ):
            placement = publication_manifest.pending_provider_occurrence_placements[
                local_workout_id
            ]
            source_record = pending
        elif published is not None and publication_record_has_retained_workout_authority(
            published,
            workout,
        ):
            placement = publication_manifest.workout_provider_occurrence_placements[
                local_workout_id
            ]
            source_record = published
        else:
            retained[local_workout_id] = _approved_placement(workout)
            continue
        _assert_override_has_lifecycle_authority(
            placement,
            fulfillment_manifest,
        )
        calendar_placement = placement.without_fulfillment_override()
        if source_record.occurrence_date != workout.prescription.date:
            calendar_placement = _approved_placement(workout)
        if calendar_placement.calendar_source == "provider_calendar" and training_week_bounds(
            calendar_placement.calendar_occurrence_date
        ) != training_week_bounds(workout.prescription.date):
            raise PublicationSafetyError(
                "Provider calendar placement is outside its approved training week"
            )
        retained[local_workout_id] = calendar_placement
    return retained


def publication_schedule_is_current(
    publication_manifest: PublicationManifest,
    workout: AuthoritativeWorkout,
) -> bool:
    """Allow provider drag adoption only while the approved date is unchanged."""
    local_workout_id = workout.identity.local_workout_id
    record = publication_manifest.pending.get(
        local_workout_id
    ) or publication_manifest.workouts.get(local_workout_id)
    return record is None or record.occurrence_date == workout.prescription.date


def resolve_provider_occurrence_placements(
    repo: RepositoryIO,
    workouts: list[AuthoritativeWorkout],
) -> ProviderOccurrencePlacements:
    """Resolve retained same-week moves and exact fulfillment execution dates."""
    fulfillment_manifest = load_fulfillment_manifest(repo)
    publication_manifest = load_manifest(repo)
    authorities_by_identity = {_identity_key(workout.identity): workout for workout in workouts}
    activities_by_id = {
        activity.local_activity_id: activity
        for activity in ActivityArchive(repo.resolve_path("data/activities")).load_all()
    }
    placements = _retained_calendar_placements(
        publication_manifest,
        fulfillment_manifest,
        workouts,
    )
    fulfillment_workout_ids: set[str] = set()
    for fulfillment in fulfillment_manifest.fulfillments.values():
        authority = authorities_by_identity.get(_identity_key(fulfillment.workout_identity))
        if authority is None:
            continue
        activity = activities_by_id.get(fulfillment.local_activity_id)
        if activity is None:
            raise PublicationSafetyError(
                "Fulfillment activity is unavailable for calendar placement"
            )
        try:
            assert_fulfillment_authority_is_current(fulfillment, authority)
            assert_fulfillment_is_usable(
                fulfillment,
                activity,
                fulfillment_manifest,
            )
        except ValueError as exc:
            raise PublicationSafetyError(str(exc)) from exc
        if fulfillment.provider_pair is not None:
            publication = publication_manifest.workouts.get(authority.identity.local_workout_id)
            pending = publication_manifest.pending.get(authority.identity.local_workout_id)
            if (
                publication is not None
                and (
                    publication.event_id != fulfillment.provider_pair.event_id
                    or not publication_record_matches_current_workout_authority(
                        publication,
                        authority,
                    )
                )
            ) or (
                publication is None
                and (
                    pending is None
                    or not publication_record_matches_current_workout_authority(
                        pending,
                        authority,
                    )
                )
            ):
                raise PublicationSafetyError(
                    "Provider-paired fulfillment does not match its exact owned publication"
                )
        execution_local_date = (
            activity.occurrence.start_time_utc.astimezone(
                ZoneInfo(fulfillment.schedule_timezone)
            ).date()
            if activity.occurrence.start_time_utc is not None
            else activity.occurrence.local_date
        )
        if execution_local_date != fulfillment.execution_local_date:
            raise PublicationSafetyError(
                "Fulfillment execution date does not match current canonical activity evidence"
            )
        local_workout_id = authority.identity.local_workout_id
        calendar_placement = placements.get(
            local_workout_id,
            _approved_placement(authority),
        )
        placements[local_workout_id] = calendar_placement.model_copy(
            update={"fulfillment_override": _fulfillment_override(fulfillment)}
        )
        fulfillment_workout_ids.add(authority.identity.local_workout_id)
    return ProviderOccurrencePlacements(
        placements_by_local_workout_id=placements,
        fulfillment_workout_ids=frozenset(fulfillment_workout_ids),
    )


def assert_fulfillment_pair_matches_remote_placement(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    placement: ProviderOccurrencePlacement,
    remote: EventDTO | None,
) -> None:
    """Preflight the live native pair before using fulfillment placement."""
    override = placement.fulfillment_override
    if override is None:
        return
    fulfillment = load_fulfillment_manifest(repo).fulfillments.get(override.local_activity_id)
    if fulfillment is None:
        raise PublicationSafetyError("Fulfillment placement lacks its active association")
    activity = ActivityArchive(repo.resolve_path("data/activities")).load(
        override.local_activity_id
    )
    if activity is None or activity.origin.intervals_icu_activity_id is None:
        raise PublicationSafetyError("Fulfillment placement lacks its Intervals activity")
    provider_activity = client.get_activity(
        activity.origin.intervals_icu_activity_id,
        intervals=True,
    )
    try:
        validate_remote_performance_evidence(
            provider_activity,
            activity,
            expected_external_activity_id=(activity.origin.intervals_icu_activity_id),
        )
    except ValueError as exc:
        raise PublicationSafetyError(str(exc)) from exc
    provider_pair = fulfillment.provider_pair
    if provider_pair is not None and (remote is None or remote.id != provider_pair.event_id):
        raise PublicationSafetyError(
            "Provider-paired fulfillment does not match the recovered remote event"
        )
    if provider_activity.paired_event_id is None:
        if provider_pair is not None and fulfillment.athlete_confirmation is None:
            raise PublicationSafetyError("Provider-observed fulfillment pair is no longer present")
        if not activity_source_supports_pairing(provider_activity):
            raise PublicationSafetyError(
                "Intervals does not allow pairing updates for this activity source"
            )
        return
    if remote is None or provider_activity.paired_event_id != remote.id:
        raise PublicationSafetyError("Fulfillment activity is paired to a different provider event")
