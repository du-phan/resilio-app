"""Ownership-proven deletion of obsolete published events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.identity_discovery import (
    discover_owned_identity_matches,
)
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.past_publication_retention import (
    resolve_past_existing_publication,
)
from resilio.core.workout_publication.pending_publication_retirement import (
    retire_pending_publication,
)
from resilio.core.workout_publication.pending_retirement_recovery import (
    restored_provider_occurrence_date,
)
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_ownership,
    assert_remote_unchanged,
    pending_matches,
    provider_event_state_fingerprint,
    provider_local_date,
    publication_fingerprint,
)
from resilio.core.workout_publication.preparation import (
    RetainedPublicationVerification,
    prepare_retained_publication_verification,
)
from resilio.core.workout_publication.publication_deletion_staging import (
    authority_candidate,
    stage_dual_publication_deletion,
)
from resilio.core.workout_publication.publication_deletions import (
    activate_publication_deletion_monitoring,
)
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthorities,
    RetainedPublicationAuthority,
)
from resilio.core.workout_publication.retained_publication_semantics import (
    remote_matches_retained_record,
)
from resilio.core.workout_publication.retirement_mutation import (
    assert_expected_remote_target,
    delete_remote_if_fresh,
)
from resilio.core.workout_publication.retirement_recovery import (
    recover_absent_existing_publication,
)
from resilio.core.workout_publication.tombstone_retirement import (
    retire_existing_tombstone,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.integrations.intervals_icu.errors import IntervalsNotFoundError
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationManifest,
    PublicationResult,
    PublishedWorkout,
)
from resilio.schemas.publication_operations import PendingPublicationDeletionOperation


@dataclass(frozen=True)
class RetirementVerification:
    """Read-only classification of one obsolete owned publication."""

    provider_occurrence_date: date
    retirement_required: bool


def _provider_occurrence_is_past(
    record: PublishedWorkout | PendingWorkoutPublication,
    provider_occurrence_date: date,
    *,
    restore_local: bool,
    as_of_date: date | None,
) -> bool:
    if as_of_date is None:
        return False
    effective_date = (
        restored_provider_occurrence_date(record, provider_occurrence_date)
        if restore_local
        else provider_occurrence_date
    )
    return effective_date < as_of_date


class WorkoutRetirementService:
    """Verify and remove only exact locally owned Intervals.icu events."""

    def __init__(self, repo: RepositoryIO, client: IntervalsIcuClient):
        self.repo = repo
        self.client = client

    def _pending_identity_matches(
        self,
        prepared: RetainedPublicationVerification,
        pending: PendingWorkoutPublication,
        previous: PublishedWorkout | None,
    ) -> list[EventDTO]:
        return discover_owned_identity_matches(
            self.client,
            prepared,
            previous=previous,
            pending=pending,
        )

    def _prepare_pending(
        self,
        authority: RetainedPublicationAuthority,
        *,
        require_pending_only: bool = True,
    ) -> tuple[
        PendingWorkoutPublication,
        RetainedPublicationVerification,
        list[EventDTO],
    ]:
        authoritative_workout = authority.workout
        local_workout_id = authoritative_workout.identity.local_workout_id
        manifest = load_manifest(self.repo)
        pending = manifest.pending.get(local_workout_id)
        previous = manifest.workouts.get(local_workout_id)
        if pending is None or (require_pending_only and previous is not None):
            raise PublicationSafetyError(
                "Pending retirement requires one pending-only ownership record"
            )
        athlete = self.client.get_athlete()
        prepared = prepare_retained_publication_verification(
            authoritative_workout,
            pending,
            athlete_id=athlete.id,
            provider_name=authority.provider_name,
            provider_occurrence_date=provider_local_date(pending.provider_start_date_local),
        )
        if not pending_matches(
            pending,
            uid=prepared.event.uid,
            external_id=prepared.event.external_id,
            fingerprint=publication_fingerprint(
                prepared.event,
                pending.sport_settings_version_sha256,
            ),
        ):
            raise PublicationSafetyError(
                "Pending publication intent differs from applied workout authority"
            )
        return (
            pending,
            prepared,
            self._pending_identity_matches(
                prepared,
                pending,
                previous,
            ),
        )

    def _assert_remote_matches_published_or_pending(
        self,
        remote: EventDTO,
        record: PublishedWorkout,
        *,
        retained_authorities: RetainedPublicationAuthorities | None,
        authoritative_workout: AuthoritativeWorkout | None,
        provider_name: str | None,
    ) -> None:
        published_authority = authority_candidate(
            retained_authorities,
            pending=False,
            authoritative_workout=authoritative_workout,
            provider_name=provider_name,
        )
        if published_authority is not None and remote_matches_retained_record(
            self.client, remote, record, published_authority
        ):
            return
        manifest = load_manifest(self.repo)
        pending = manifest.pending.get(record.workout_identity.local_workout_id)
        pending_authority = authority_candidate(
            retained_authorities,
            pending=True,
            authoritative_workout=authoritative_workout,
            provider_name=provider_name,
        )
        if (
            pending is not None
            and pending_authority is not None
            and remote_matches_retained_record(self.client, remote, pending, pending_authority)
        ):
            return
        if published_authority is None and pending_authority is None:
            assert_remote_unchanged(remote, record)
            return
        raise RemoteWorkoutDriftError(
            "Remote event matches neither published nor pending owned semantics"
        )

    def verify(
        self,
        local_workout_id: str,
        *,
        restore_local: bool,
        retained_authorities: RetainedPublicationAuthorities | None = None,
        authoritative_workout: AuthoritativeWorkout | None = None,
        provider_name: str | None = None,
        as_of_date: date | None = None,
    ) -> RetirementVerification:
        manifest = load_manifest(self.repo)
        record = manifest.workouts.get(local_workout_id)
        if record is None:
            authority = authority_candidate(
                retained_authorities,
                pending=True,
                authoritative_workout=authoritative_workout,
                provider_name=provider_name,
            )
            if authority is None:
                raise PublicationSafetyError(
                    "Future deletion lacks exact local ownership authority"
                )
            pending, prepared, matches = self._prepare_pending(authority)
            if (
                matches
                and not restore_local
                and not remote_matches_retained_record(self.client, matches[0], pending, authority)
            ):
                raise RemoteWorkoutDriftError(
                    "Pending owned event differs from its prepared workout"
                )
            provider_occurrence_date = (
                provider_local_date(matches[0].start_date_local)
                if matches and matches[0].start_date_local is not None
                else provider_local_date(pending.provider_start_date_local)
            )
            return RetirementVerification(
                provider_occurrence_date=provider_occurrence_date,
                retirement_required=(as_of_date is None or provider_occurrence_date >= as_of_date),
            )
        persisted_provider_occurrence_date = provider_local_date(record.provider_start_date_local)
        athlete = self.client.get_athlete()
        try:
            remote = get_exact_event(
                self.client,
                record.event_id,
                athlete_id=athlete.id,
            )
        except IntervalsNotFoundError:
            return RetirementVerification(
                provider_occurrence_date=persisted_provider_occurrence_date,
                retirement_required=(
                    as_of_date is None or persisted_provider_occurrence_date >= as_of_date
                ),
            )
        assert_remote_ownership(remote, uid=record.uid, external_id=record.external_id)
        if remote.start_date_local is None:
            raise PublicationSafetyError("Owned remote event lacks a provider occurrence timestamp")
        remote_provider_occurrence_date = provider_local_date(remote.start_date_local)
        if not restore_local:
            self._assert_remote_matches_published_or_pending(
                remote,
                record,
                retained_authorities=retained_authorities,
                authoritative_workout=authoritative_workout,
                provider_name=provider_name,
            )
        if (
            as_of_date is not None
            and (
                restored_provider_occurrence_date(
                    manifest.pending.get(local_workout_id) or record,
                    remote_provider_occurrence_date,
                )
                if restore_local
                else remote_provider_occurrence_date
            )
            < as_of_date
        ):
            return RetirementVerification(
                provider_occurrence_date=remote_provider_occurrence_date,
                retirement_required=False,
            )
        return RetirementVerification(
            provider_occurrence_date=remote_provider_occurrence_date,
            retirement_required=True,
        )

    def observe_remote_target(
        self,
        local_workout_id: str,
        *,
        authoritative_workout: AuthoritativeWorkout,
        provider_name: str,
    ) -> tuple[int, str]:
        """Return the exact owned remote event ID and bytes awaiting confirmation."""
        manifest = load_manifest(self.repo)
        record = manifest.workouts.get(local_workout_id)
        if record is not None:
            athlete = self.client.get_athlete()
            remote = get_exact_event(
                self.client,
                record.event_id,
                athlete_id=athlete.id,
            )
            assert_remote_ownership(
                remote,
                uid=record.uid,
                external_id=record.external_id,
            )
            return remote.id, provider_event_state_fingerprint(remote)
        _, _, matches = self._prepare_pending(
            RetainedPublicationAuthority(
                workout=authoritative_workout,
                provider_name=provider_name,
            )
        )
        if len(matches) != 1:
            raise PublicationSafetyError(
                "Confirmed drift target does not identify one remote owned event"
            )
        return matches[0].id, provider_event_state_fingerprint(matches[0])

    def _finalize_existing_retirement(
        self,
        manifest: PublicationManifest,
        record: PublishedWorkout,
        deletion_operation: PendingPublicationDeletionOperation | None,
        *,
        provider_occurrence_date: date,
    ) -> PublicationResult:
        local_workout_id = record.workout_identity.local_workout_id
        if deletion_operation is not None:
            activate_publication_deletion_monitoring(self.repo, deletion_operation)
        else:
            manifest.pending.pop(local_workout_id, None)
        del manifest.workouts[local_workout_id]
        del manifest.workout_provider_occurrence_placements[local_workout_id]
        save_manifest(self.repo, manifest)
        return PublicationResult(
            action="deleted",
            local_workout_id=local_workout_id,
            event_id=record.event_id,
            uid=record.uid,
            external_id=record.external_id,
            provider_occurrence_date=provider_occurrence_date,
        )

    def _retire_existing_publication(
        self,
        local_workout_id: str,
        *,
        manifest: PublicationManifest,
        record: PublishedWorkout,
        restore_local: bool,
        expected_remote_target: tuple[int, str] | None,
        retained_authorities: RetainedPublicationAuthorities | None,
        authoritative_workout: AuthoritativeWorkout | None,
        provider_name: str | None,
        as_of_date: date | None,
    ) -> PublicationResult:
        published_pending = manifest.pending.get(local_workout_id)
        athlete = self.client.get_athlete()
        try:
            remote = get_exact_event(
                self.client,
                record.event_id,
                athlete_id=athlete.id,
            )
        except IntervalsNotFoundError:
            return recover_absent_existing_publication(
                self.repo,
                local_workout_id,
                manifest=manifest,
                record=record,
                pending=published_pending,
                retained_authorities=retained_authorities,
                authoritative_workout=authoritative_workout,
                provider_name=provider_name,
            )
        assert_remote_ownership(remote, uid=record.uid, external_id=record.external_id)
        if remote.start_date_local is None:
            raise PublicationSafetyError("Owned remote event lacks a provider occurrence timestamp")
        remote_provider_occurrence_date = provider_local_date(remote.start_date_local)
        assert_expected_remote_target(
            remote,
            expected_remote_target,
            message="Remote event changed after athlete retirement confirmation",
        )
        if not restore_local:
            self._assert_remote_matches_published_or_pending(
                remote,
                record,
                retained_authorities=retained_authorities,
                authoritative_workout=authoritative_workout,
                provider_name=provider_name,
            )
        if _provider_occurrence_is_past(
            published_pending or record,
            remote_provider_occurrence_date,
            restore_local=restore_local,
            as_of_date=as_of_date,
        ):
            return resolve_past_existing_publication(
                self.repo,
                self.client,
                record,
                published_pending,
                remote,
                provider_occurrence_date=remote_provider_occurrence_date,
                restore_local=restore_local,
                retained_authorities=retained_authorities,
                authoritative_workout=authoritative_workout,
                provider_name=provider_name,
                expected_remote_target=expected_remote_target,
            )
        deletion_operation = (
            stage_dual_publication_deletion(
                self.repo,
                published_pending,
                record,
                retained_authorities=retained_authorities,
                authoritative_workout=authoritative_workout,
                provider_name=provider_name,
            )
            if published_pending is not None
            else None
        )
        verify_semantics = (
            None
            if restore_local
            else lambda fresh: self._assert_remote_matches_published_or_pending(
                fresh,
                record,
                retained_authorities=retained_authorities,
                authoritative_workout=authoritative_workout,
                provider_name=provider_name,
            )
        )
        delete_remote_if_fresh(
            self.client,
            remote,
            athlete_id=athlete.id,
            expected_uid=record.uid,
            expected_external_id=record.external_id,
            expected_remote_target=expected_remote_target,
            verify_semantics=verify_semantics,
        )
        return self._finalize_existing_retirement(
            manifest,
            record,
            deletion_operation,
            provider_occurrence_date=remote_provider_occurrence_date,
        )

    def retire_published(
        self,
        local_workout_id: str,
        *,
        restore_local: bool = False,
        expected_remote_target: tuple[int, str] | None = None,
        retained_authorities: RetainedPublicationAuthorities | None = None,
        authoritative_workout: AuthoritativeWorkout | None = None,
        provider_name: str | None = None,
        as_of_date: date | None = None,
    ) -> PublicationResult:
        manifest = load_manifest(self.repo)
        record = manifest.workouts.get(local_workout_id)
        if record is None:
            tombstone_result = retire_existing_tombstone(
                self.repo,
                self.client,
                local_workout_id,
            )
            if tombstone_result is not None:
                return tombstone_result
            authority = authority_candidate(
                retained_authorities,
                pending=True,
                authoritative_workout=authoritative_workout,
                provider_name=provider_name,
            )
            if authority is None:
                raise PublicationSafetyError(
                    "Pending deletion requires exact applied-workout authority"
                )
            pending, prepared, matches = self._prepare_pending(authority)
            remote = matches[0] if matches else None
            return retire_pending_publication(
                self.repo,
                self.client,
                pending,
                prepared,
                remote,
                authority,
                restore_local=restore_local,
                expected_remote_target=expected_remote_target,
                as_of_date=as_of_date,
            )
        return self._retire_existing_publication(
            local_workout_id,
            manifest=manifest,
            record=record,
            restore_local=restore_local,
            expected_remote_target=expected_remote_target,
            retained_authorities=retained_authorities,
            authoritative_workout=authoritative_workout,
            provider_name=provider_name,
            as_of_date=as_of_date,
        )
