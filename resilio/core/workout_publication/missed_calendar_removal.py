"""Explicit owned-calendar deletion without changing missed-run history."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from resilio.core.planning.schedule import schedule_authority_deadline_utc
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.calendar_removal_repository import (
    load_removal_manifest,
    save_removal_manifest,
)
from resilio.core.workout_publication.locking import coordinated_publication_plan_activity_lock
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    assert_remote_ownership,
    provider_event_state_fingerprint,
    provider_local_date,
)
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.core.workout_publication.retained_authority import retained_publication_authority
from resilio.core.workout_publication.retained_publication_semantics import (
    remote_matches_retained_record,
)
from resilio.core.workout_publication.retirement_mutation import delete_remote_if_fresh
from resilio.core.workout_publication.retirement_recovery import recover_absent_existing_publication
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.integrations.intervals_icu.errors import IntervalsNotFoundError
from resilio.schemas.calendar_removal import MissedWorkoutCalendarRemoval
from resilio.schemas.publication import PublishedWorkout


def _require_missed_prescription(
    repo: RepositoryIO, publication: PublishedWorkout, timestamp: datetime
) -> None:
    authority = retained_publication_authority(repo, publication).workout
    if (
        schedule_authority_deadline_utc(
            authority.prescription, training_timezone=authority.schedule_timezone
        )
        > timestamp
    ):
        raise PublicationSafetyError("Only an elapsed missed workout can be removed")
    if any(
        record.workout_identity == publication.workout_identity
        for record in load_fulfillment_manifest(repo).fulfillments.values()
    ):
        raise PublicationSafetyError("A fulfilled workout cannot be removed as missed")


def _verify_unpaired_remote(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    publication: PublishedWorkout,
    remote: EventDTO,
    timestamp: datetime,
) -> None:
    assert_remote_ownership(remote, uid=publication.uid, external_id=publication.external_id)
    authority = retained_publication_authority(repo, publication)
    if not remote_matches_retained_record(client, remote, publication, authority):
        raise PublicationSafetyError("Remote missed workout differs from its approved semantics")
    local_today = timestamp.astimezone(ZoneInfo(publication.schedule_timezone)).date()
    if (
        remote.start_date_local is None
        or provider_local_date(remote.start_date_local) >= local_today
    ):
        raise PublicationSafetyError("A future calendar occurrence cannot be removed as missed")
    _require_no_native_pair(client, remote.id, local_today)


def _require_no_native_pair(client: IntervalsIcuClient, event_id: int, local_today: date) -> None:
    """Prove all provider history without inventing an execution-offset bound."""
    windows = [(date.min, local_today)]
    while windows:
        oldest, newest = windows.pop()
        summaries = client.list_activity_pairings(oldest, newest)
        if any(summary.paired_event_id == event_id for summary in summaries):
            raise PublicationSafetyError("A provider-paired workout cannot be removed as missed")
        if len(summaries) < 1000:
            continue
        if oldest == newest:
            raise PublicationSafetyError("Single-day completed activity read may be truncated")
        midpoint = oldest + (newest - oldest) // 2
        windows.extend([(oldest, midpoint), (midpoint + date.resolution, newest)])


def _finish_removal(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    removal: MissedWorkoutCalendarRemoval,
    timestamp: datetime,
) -> MissedWorkoutCalendarRemoval:
    publication = removal.publication
    workout_id = publication.workout_identity.local_workout_id
    manifest = load_manifest(repo)
    current = manifest.workouts.get(workout_id)
    if workout_id in manifest.pending:
        raise PublicationSafetyError("A pending publication update must be resolved before removal")
    _require_missed_prescription(repo, publication, timestamp)
    if client.get_athlete().id != removal.athlete_id:
        raise PublicationSafetyError("Calendar removal belongs to a different provider athlete")
    try:
        remote = get_exact_event(client, publication.event_id, athlete_id=removal.athlete_id)
    except IntervalsNotFoundError:
        remote = None
    if remote is not None:
        _verify_unpaired_remote(repo, client, publication, remote, timestamp)
        if provider_event_state_fingerprint(remote) != removal.observed_remote_fingerprint_sha256:
            raise PublicationSafetyError(
                "Remote event changed after calendar removal was requested"
            )
    if current is not None and current != publication:
        raise PublicationSafetyError(
            "Local publication changed after calendar removal was requested"
        )
    if remote is not None:
        # Use the same destructive guard before and after ownership cleanup.
        # Native pairing belongs to the activity, so event fingerprints alone
        # cannot prove the fresh event is still unpaired.
        delete_remote_if_fresh(
            client,
            remote,
            athlete_id=removal.athlete_id,
            expected_uid=publication.uid,
            expected_external_id=publication.external_id,
            expected_remote_target=(
                publication.event_id,
                removal.observed_remote_fingerprint_sha256,
            ),
            verify_semantics=lambda fresh: _verify_unpaired_remote(
                repo, client, publication, fresh, timestamp
            ),
        )
    if current is not None:
        authority = retained_publication_authority(repo, publication)
        recover_absent_existing_publication(
            repo,
            workout_id,
            manifest=manifest,
            record=publication,
            pending=None,
            retained_authorities=None,
            authoritative_workout=authority.workout,
            provider_name=authority.provider_name,
        )
    return MissedWorkoutCalendarRemoval.model_validate(
        {
            **removal.model_dump(mode="python"),
            "completed_at_utc": removal.completed_at_utc or timestamp,
        }
    )


def remove_missed_calendar_workout(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    *,
    local_workout_id: str,
    athlete_confirmation_reference: str,
    requested_at_utc: datetime | None = None,
) -> MissedWorkoutCalendarRemoval:
    """Stage an exact removal before deletion; keep planning and adherence intact."""
    if not 10 <= len(athlete_confirmation_reference.strip()) <= 1000:
        raise PublicationSafetyError(
            "Missed calendar removal requires explicit athlete confirmation"
        )
    timestamp = requested_at_utc or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PublicationSafetyError("Calendar removal requires an aware current timestamp")
    with coordinated_publication_plan_activity_lock(repo, "remove_missed_calendar_workout"):
        removals = load_removal_manifest(repo)
        removal = removals.removals.get(local_workout_id)
        if removal is None:
            manifest = load_manifest(repo)
            if local_workout_id in manifest.pending:
                raise PublicationSafetyError(
                    "A pending publication update must be resolved before removal"
                )
            publication = manifest.workouts.get(local_workout_id)
            if publication is None:
                raise PublicationSafetyError(
                    "Missed calendar removal requires exact published ownership"
                )
            _require_missed_prescription(repo, publication, timestamp)
            athlete_id = client.get_athlete().id
            remote = get_exact_event(client, publication.event_id, athlete_id=athlete_id)
            _verify_unpaired_remote(repo, client, publication, remote, timestamp)
            removal = MissedWorkoutCalendarRemoval(
                athlete_id=athlete_id,
                publication=publication,
                observed_remote_fingerprint_sha256=provider_event_state_fingerprint(remote),
                athlete_confirmation_reference=athlete_confirmation_reference,
                requested_at_utc=timestamp,
            )
            removals.removals[local_workout_id] = removal
            save_removal_manifest(repo, removals)
        completed = _finish_removal(repo, client, removal, timestamp)
        if completed != removal:
            removals.removals[local_workout_id] = completed
            save_removal_manifest(repo, removals)
        return completed
