"""Ownership-proven deletion of obsolete published events."""

from __future__ import annotations

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_external_ownership,
    assert_remote_matches,
    assert_remote_ownership,
    assert_remote_unchanged,
    pending_matches,
    provider_event_fingerprint,
)
from resilio.core.workout_publication.preparation import (
    PreparedPublication,
    prepare_publication,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.integrations.intervals_icu.errors import IntervalsNotFoundError
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationResult,
    PublishedWorkout,
)


class WorkoutRetirementService:
    """Verify and remove only exact locally owned Intervals.icu events."""

    def __init__(self, repo: RepositoryIO, client: IntervalsIcuClient):
        self.repo = repo
        self.client = client

    def _pending_identity_matches(
        self,
        prepared: PreparedPublication,
        pending: PendingWorkoutPublication,
    ) -> list[EventDTO]:
        events = self.client.list_events(
            min(prepared.workout.date, pending.occurrence_date),
            max(prepared.workout.date, pending.occurrence_date),
            athlete_id=prepared.athlete_id,
        )
        matches = [
            event
            for event in events
            if event.uid == prepared.event.uid or event.external_id == prepared.external_id
        ]
        if len(matches) > 1:
            raise PublicationSafetyError(
                "Multiple remote events claim the workout ownership identity"
            )
        for remote in matches:
            assert_remote_external_ownership(
                remote,
                external_id=prepared.external_id,
            )
        return matches

    def _prepare_pending(
        self,
        authoritative_workout: AuthoritativeWorkout,
        *,
        provider_name: str,
        require_pending_only: bool = True,
    ) -> tuple[PendingWorkoutPublication, PreparedPublication, list[EventDTO]]:
        local_workout_id = authoritative_workout.identity.local_workout_id
        manifest = load_manifest(self.repo)
        pending = manifest.pending.get(local_workout_id)
        previous = manifest.workouts.get(local_workout_id)
        if pending is None or (require_pending_only and previous is not None):
            raise PublicationSafetyError(
                "Pending retirement requires one pending-only ownership record"
            )
        prepared = prepare_publication(
            self.client,
            authoritative_workout,
            previous=previous,
            provider_name=provider_name,
        )
        if not pending_matches(
            pending,
            uid=prepared.event.uid,
            external_id=prepared.external_id,
            fingerprint=prepared.publication_fingerprint_sha256,
        ):
            raise PublicationSafetyError(
                "Pending publication intent differs from applied workout authority"
            )
        return pending, prepared, self._pending_identity_matches(prepared, pending)

    def _assert_remote_matches_published_or_pending(
        self,
        remote: EventDTO,
        record: PublishedWorkout,
        *,
        authoritative_workout: AuthoritativeWorkout | None,
        provider_name: str | None,
    ) -> None:
        try:
            assert_remote_unchanged(remote, record)
            return
        except RemoteWorkoutDriftError:
            if authoritative_workout is None or provider_name is None:
                raise
        _, prepared, matches = self._prepare_pending(
            authoritative_workout,
            provider_name=provider_name,
            require_pending_only=False,
        )
        if len(matches) != 1 or matches[0].id != remote.id:
            raise RemoteWorkoutDriftError(
                "Remote event matches neither published nor pending owned state"
            )
        try:
            assert_remote_matches(
                remote,
                prepared.event,
                prepared.expected_step_semantics,
            )
        except PublicationSafetyError as exc:
            raise RemoteWorkoutDriftError(
                "Remote event matches neither published nor pending owned state"
            ) from exc

    def verify(
        self,
        local_workout_id: str,
        *,
        restore_local: bool,
        authoritative_workout: AuthoritativeWorkout | None,
        provider_name: str | None,
    ) -> None:
        manifest = load_manifest(self.repo)
        record = manifest.workouts.get(local_workout_id)
        if record is None:
            if authoritative_workout is None or provider_name is None:
                raise PublicationSafetyError(
                    "Future deletion lacks exact local ownership authority"
                )
            _, prepared, matches = self._prepare_pending(
                authoritative_workout,
                provider_name=provider_name,
            )
            if matches and not restore_local:
                try:
                    assert_remote_matches(
                        matches[0],
                        prepared.event,
                        prepared.expected_step_semantics,
                    )
                except PublicationSafetyError as exc:
                    raise RemoteWorkoutDriftError(
                        "Pending owned event differs from its prepared workout"
                    ) from exc
            return
        athlete = self.client.get_athlete()
        try:
            remote = self.client.get_event(record.event_id, athlete_id=athlete.id)
        except IntervalsNotFoundError:
            return
        assert_remote_ownership(remote, uid=record.uid, external_id=record.external_id)
        if not restore_local:
            self._assert_remote_matches_published_or_pending(
                remote,
                record,
                authoritative_workout=authoritative_workout,
                provider_name=provider_name,
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
            remote = self.client.get_event(record.event_id, athlete_id=athlete.id)
            assert_remote_ownership(
                remote,
                uid=record.uid,
                external_id=record.external_id,
            )
            return remote.id, provider_event_fingerprint(remote)
        _, _, matches = self._prepare_pending(
            authoritative_workout,
            provider_name=provider_name,
        )
        if len(matches) != 1:
            raise PublicationSafetyError(
                "Confirmed drift target does not identify one remote owned event"
            )
        return matches[0].id, provider_event_fingerprint(matches[0])

    def retire_published(
        self,
        local_workout_id: str,
        *,
        restore_local: bool = False,
        expected_remote_target: tuple[int, str] | None = None,
        authoritative_workout: AuthoritativeWorkout | None = None,
        provider_name: str | None = None,
    ) -> PublicationResult:
        manifest = load_manifest(self.repo)
        record = manifest.workouts.get(local_workout_id)
        if record is None:
            if authoritative_workout is None or provider_name is None:
                raise PublicationSafetyError(
                    "Pending deletion requires exact applied-workout authority"
                )
            pending, prepared, matches = self._prepare_pending(
                authoritative_workout,
                provider_name=provider_name,
            )
            remote = matches[0] if matches else None
            if remote is not None:
                if expected_remote_target is not None and (
                    remote.id != expected_remote_target[0]
                    or provider_event_fingerprint(remote) != expected_remote_target[1]
                ):
                    raise PublicationSafetyError(
                        "Remote event changed after athlete deletion confirmation"
                    )
                if not restore_local:
                    assert_remote_matches(
                        remote,
                        prepared.event,
                        prepared.expected_step_semantics,
                    )
                athlete = self.client.get_athlete()
                self.client.delete_event(remote.id, athlete_id=athlete.id)
                try:
                    self.client.get_event(remote.id, athlete_id=athlete.id)
                except IntervalsNotFoundError:
                    pass
                else:
                    raise PublicationSafetyError("Deleted event still exists on read-back")
            manifest.pending.pop(local_workout_id, None)
            save_manifest(self.repo, manifest)
            return PublicationResult(
                action="deleted" if remote is not None else "recovered_deleted",
                local_workout_id=local_workout_id,
                event_id=remote.id if remote is not None else None,
                uid=pending.uid,
                external_id=pending.external_id,
            )
        athlete = self.client.get_athlete()
        try:
            remote = self.client.get_event(record.event_id, athlete_id=athlete.id)
        except IntervalsNotFoundError:
            manifest.pending.pop(local_workout_id, None)
            del manifest.workouts[local_workout_id]
            save_manifest(self.repo, manifest)
            return PublicationResult(
                action="recovered_deleted",
                local_workout_id=local_workout_id,
                event_id=record.event_id,
                uid=record.uid,
                external_id=record.external_id,
            )
        assert_remote_ownership(remote, uid=record.uid, external_id=record.external_id)
        if expected_remote_target is not None and (
            remote.id != expected_remote_target[0]
            or provider_event_fingerprint(remote) != expected_remote_target[1]
        ):
            raise PublicationSafetyError(
                "Remote event changed after athlete retirement confirmation"
            )
        if not restore_local:
            self._assert_remote_matches_published_or_pending(
                remote,
                record,
                authoritative_workout=authoritative_workout,
                provider_name=provider_name,
            )
        self.client.delete_event(record.event_id, athlete_id=athlete.id)
        try:
            self.client.get_event(record.event_id, athlete_id=athlete.id)
        except IntervalsNotFoundError:
            pass
        else:
            raise PublicationSafetyError("Deleted event still exists on read-back")
        manifest.pending.pop(local_workout_id, None)
        del manifest.workouts[local_workout_id]
        save_manifest(self.repo, manifest)
        return PublicationResult(
            action="deleted",
            local_workout_id=local_workout_id,
            event_id=record.event_id,
            uid=record.uid,
            external_id=record.external_id,
        )
