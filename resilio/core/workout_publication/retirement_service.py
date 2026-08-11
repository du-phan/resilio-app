"""Ownership-proven retirement of obsolete or early-fulfilled events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import canonical_data_sha256
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
    PublicationManifest,
    PublicationResult,
    RetiredPendingWorkoutPublication,
    RetiredWorkoutPublication,
)
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentRecord


class WorkoutRetirementService:
    """Verify and remove only exact locally owned Intervals.icu events."""

    def __init__(self, repo: RepositoryIO, client: IntervalsIcuClient):
        self.repo = repo
        self.client = client

    @staticmethod
    def _record_published_retirement(
        manifest: PublicationManifest,
        local_workout_id: str,
        retirement: RetiredWorkoutPublication,
    ) -> None:
        previous = manifest.retired.get(local_workout_id)
        if previous is not None:
            if previous.reopened_at_utc is None:
                raise PublicationSafetyError(
                    "A current retirement cannot be overwritten without reopening"
                )
            manifest.retirement_history.append(previous)
        manifest.retired[local_workout_id] = retirement

    @staticmethod
    def _record_pending_retirement(
        manifest: PublicationManifest,
        local_workout_id: str,
        retirement: RetiredPendingWorkoutPublication,
    ) -> None:
        previous = manifest.retired_pending.get(local_workout_id)
        if previous is not None:
            if previous.reopened_at_utc is None:
                raise PublicationSafetyError(
                    "A current pending retirement cannot be overwritten without reopening"
                )
            manifest.pending_retirement_history.append(previous)
        manifest.retired_pending[local_workout_id] = retirement

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
    ) -> tuple[PendingWorkoutPublication, PreparedPublication, list[EventDTO]]:
        local_workout_id = authoritative_workout.identity.local_workout_id
        manifest = load_manifest(self.repo)
        pending = manifest.pending.get(local_workout_id)
        if pending is None or local_workout_id in manifest.workouts:
            raise PublicationSafetyError(
                "Pending retirement requires one pending-only ownership record"
            )
        prepared = prepare_publication(
            self.client,
            authoritative_workout,
            previous=None,
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
            assert_remote_unchanged(remote, record)

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
        fulfillment: WorkoutFulfillmentRecord | None = None,
        expected_remote_target: tuple[int, str] | None = None,
    ) -> PublicationResult:
        manifest = load_manifest(self.repo)
        record = manifest.workouts.get(local_workout_id)
        if record is None:
            raise PublicationSafetyError("Deletion requires a local publication manifest record")
        athlete = self.client.get_athlete()
        try:
            remote = self.client.get_event(record.event_id, athlete_id=athlete.id)
        except IntervalsNotFoundError:
            recovered_action: Literal[
                "recovered_deleted", "recovered_retired"
            ] = "recovered_deleted"
            if fulfillment is not None:
                self._record_published_retirement(
                    manifest,
                    local_workout_id,
                    RetiredWorkoutPublication(
                        publication=record,
                        fulfilling_local_activity_id=fulfillment.local_activity_id,
                        fulfillment_record_sha256_at_retirement=canonical_data_sha256(fulfillment),
                        execution_local_date_at_retirement=(fulfillment.execution_local_date),
                        schedule_offset_days_at_retirement=(fulfillment.schedule_offset_days),
                        provider_deletion_status="already_absent",
                        retired_at_utc=datetime.now(timezone.utc),
                    ),
                )
                self._remove_superseding_pending(
                    manifest,
                    local_workout_id=local_workout_id,
                    fulfillment=fulfillment,
                )
                recovered_action = "recovered_retired"
            else:
                self._remove_superseding_pending(
                    manifest,
                    local_workout_id=local_workout_id,
                    fulfillment=None,
                )
            del manifest.workouts[local_workout_id]
            save_manifest(self.repo, manifest)
            return PublicationResult(
                action=recovered_action,
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
            assert_remote_unchanged(remote, record)
        self.client.delete_event(record.event_id, athlete_id=athlete.id)
        try:
            self.client.get_event(record.event_id, athlete_id=athlete.id)
        except IntervalsNotFoundError:
            pass
        else:
            raise PublicationSafetyError("Deleted event still exists on read-back")
        deletion_action: Literal["deleted", "retired"] = "deleted"
        if fulfillment is not None:
            self._record_published_retirement(
                manifest,
                local_workout_id,
                RetiredWorkoutPublication(
                    publication=record,
                    fulfilling_local_activity_id=fulfillment.local_activity_id,
                    fulfillment_record_sha256_at_retirement=canonical_data_sha256(fulfillment),
                    execution_local_date_at_retirement=fulfillment.execution_local_date,
                    schedule_offset_days_at_retirement=fulfillment.schedule_offset_days,
                    provider_deletion_status="deleted",
                    retired_at_utc=datetime.now(timezone.utc),
                ),
            )
            self._remove_superseding_pending(
                manifest,
                local_workout_id=local_workout_id,
                fulfillment=fulfillment,
            )
            deletion_action = "retired"
        else:
            self._remove_superseding_pending(
                manifest,
                local_workout_id=local_workout_id,
                fulfillment=None,
            )
        del manifest.workouts[local_workout_id]
        save_manifest(self.repo, manifest)
        return PublicationResult(
            action=deletion_action,
            local_workout_id=local_workout_id,
            event_id=record.event_id,
            uid=record.uid,
            external_id=record.external_id,
        )

    def _remove_superseding_pending(
        self,
        manifest: PublicationManifest,
        *,
        local_workout_id: str,
        fulfillment: WorkoutFulfillmentRecord | None,
    ) -> None:
        """Cancel a durable update intent alongside its superseded event."""
        pending = manifest.pending.pop(local_workout_id, None)
        if pending is None or fulfillment is None:
            return
        self._record_pending_retirement(
            manifest,
            local_workout_id,
            RetiredPendingWorkoutPublication(
                pending_publication=pending,
                fulfilling_local_activity_id=fulfillment.local_activity_id,
                fulfillment_record_sha256_at_retirement=canonical_data_sha256(fulfillment),
                execution_local_date_at_retirement=fulfillment.execution_local_date,
                schedule_offset_days_at_retirement=fulfillment.schedule_offset_days,
                provider_deletion_status="no_remote_event",
                remote_event_id=None,
                retired_at_utc=datetime.now(timezone.utc),
            ),
        )

    def retire_pending(
        self,
        authoritative_workout: AuthoritativeWorkout,
        *,
        fulfillment: WorkoutFulfillmentRecord,
        restore_local: bool,
        provider_name: str,
        expected_remote_target: tuple[int, str] | None = None,
    ) -> PublicationResult:
        pending, prepared, matches = self._prepare_pending(
            authoritative_workout,
            provider_name=provider_name,
        )
        remote_event_id = None
        deletion_status: Literal["deleted", "no_remote_event"] = "no_remote_event"
        if matches:
            remote = matches[0]
            if expected_remote_target is not None and (
                remote.id != expected_remote_target[0]
                or provider_event_fingerprint(remote) != expected_remote_target[1]
            ):
                raise PublicationSafetyError(
                    "Remote event changed after athlete retirement confirmation"
                )
            if not restore_local:
                try:
                    assert_remote_matches(
                        remote,
                        prepared.event,
                        prepared.expected_step_semantics,
                    )
                except PublicationSafetyError as exc:
                    raise RemoteWorkoutDriftError(
                        "Pending owned event differs from its prepared workout"
                    ) from exc
            self.client.delete_event(remote.id, athlete_id=prepared.athlete_id)
            try:
                self.client.get_event(remote.id, athlete_id=prepared.athlete_id)
            except IntervalsNotFoundError:
                pass
            else:
                raise PublicationSafetyError("Deleted pending event still exists on read-back")
            remote_event_id = remote.id
            deletion_status = "deleted"
        local_workout_id = authoritative_workout.identity.local_workout_id
        manifest = load_manifest(self.repo)
        self._record_pending_retirement(
            manifest,
            local_workout_id,
            RetiredPendingWorkoutPublication(
                pending_publication=pending,
                fulfilling_local_activity_id=fulfillment.local_activity_id,
                fulfillment_record_sha256_at_retirement=canonical_data_sha256(fulfillment),
                execution_local_date_at_retirement=fulfillment.execution_local_date,
                schedule_offset_days_at_retirement=fulfillment.schedule_offset_days,
                provider_deletion_status=deletion_status,
                remote_event_id=remote_event_id,
                retired_at_utc=datetime.now(timezone.utc),
            ),
        )
        del manifest.pending[local_workout_id]
        save_manifest(self.repo, manifest)
        return PublicationResult(
            action="retired" if remote_event_id is not None else "recovered_retired",
            local_workout_id=local_workout_id,
            event_id=remote_event_id,
            uid=pending.uid,
            external_id=pending.external_id,
        )
