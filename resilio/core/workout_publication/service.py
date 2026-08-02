"""Ownership-proven idempotent workout publication."""

from __future__ import annotations

from datetime import datetime, timezone

from resilio.core.locking import OperationLock
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.service import (
    PlanOperationError,
    load_publishable_workout,
)
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError as PublicationSafetyError,
)
from resilio.core.workout_publication.policy import (
    assert_remote_external_ownership,
    assert_remote_matches,
    assert_remote_ownership,
    assert_remote_unchanged,
    garmin_forwarding_status,
    pending_matches,
    provider_push_errors,
    publication_fingerprint,
    published_record,
)
from resilio.core.workout_publication.policy import (
    external_id_for as external_id_for,
)
from resilio.core.workout_publication.policy import (
    uid_for as uid_for,
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
    PublishedWorkout,
)


class WorkoutPublicationService:
    def __init__(
        self,
        repo: RepositoryIO,
        client: IntervalsIcuClient,
    ):
        self.repo = repo
        self.client = client

    def _load_approved_workout(
        self,
        workout_id: str,
    ) -> AuthoritativeWorkout:
        return load_publishable_workout(self.repo, workout_id)

    def publish(
        self,
        workout_id: str,
    ) -> PublicationResult:
        lock_path = self.repo.resolve_path("data/state/.workout-publication.lock")
        with OperationLock(lock_path, "workout_publication"):
            try:
                workout = self._load_approved_workout(workout_id)
            except PlanOperationError as exc:
                raise PublicationSafetyError(str(exc)) from exc
            return self._publish(workout)

    def _publish(
        self,
        authoritative_workout: AuthoritativeWorkout,
        *,
        restore_local: bool = False,
        provider_name: str | None = None,
    ) -> PublicationResult:
        workout = authoritative_workout.prescription
        manifest = load_manifest(self.repo)
        previous = manifest.workouts.get(workout.id)
        prepared = prepare_publication(
            self.client,
            authoritative_workout,
            previous=previous,
            provider_name=provider_name,
        )
        pending = manifest.pending.get(workout.id)
        identity_matches = self._identity_matches(prepared, previous, pending)
        pending = self._normalize_pending(
            prepared,
            manifest,
            previous,
            pending,
            identity_matches,
        )
        recovered = self._recover_pending_identity(
            prepared,
            manifest,
            previous,
            pending,
            identity_matches,
            restore_local=restore_local,
        )
        if recovered is not None:
            return recovered
        recovered_or_noop = self._reconcile_previous(
            prepared,
            manifest,
            previous,
            pending,
            restore_local=restore_local,
        )
        if recovered_or_noop is not None:
            return recovered_or_noop
        return self._upsert(prepared, manifest, previous)

    def _identity_matches(
        self,
        prepared: PreparedPublication,
        previous: PublishedWorkout | None,
        pending: PendingWorkoutPublication | None,
    ) -> list[EventDTO]:
        event_range_start = prepared.workout.date
        event_range_end = prepared.workout.date
        if pending is not None:
            event_range_start = min(event_range_start, pending.occurrence_date)
            event_range_end = max(event_range_end, pending.occurrence_date)
        range_events = self.client.list_events(
            event_range_start,
            event_range_end,
            athlete_id=prepared.athlete_id,
        )
        identity_matches = [
            item
            for item in range_events
            if item.uid == prepared.event.uid or item.external_id == prepared.external_id
        ]
        if len(identity_matches) > 1:
            raise PublicationSafetyError(
                "Multiple remote events claim the workout ownership identity"
            )
        for remote in identity_matches:
            if previous is not None:
                assert_remote_ownership(
                    remote,
                    uid=previous.uid,
                    external_id=prepared.external_id,
                )
            else:
                assert_remote_external_ownership(
                    remote,
                    external_id=prepared.external_id,
                )
        return identity_matches

    def _normalize_pending(
        self,
        prepared: PreparedPublication,
        manifest: PublicationManifest,
        previous: PublishedWorkout | None,
        pending: PendingWorkoutPublication | None,
        identity_matches: list[EventDTO],
    ) -> PendingWorkoutPublication | None:
        matches_intent = pending is not None and pending_matches(
            pending,
            uid=prepared.event.uid,
            external_id=prepared.external_id,
            fingerprint=prepared.publication_fingerprint_sha256,
        )
        if pending is not None and not matches_intent:
            if identity_matches:
                raise PublicationSafetyError(
                    "Pending publication intent changed after a remote event "
                    "claimed its ownership identity"
                )
            del manifest.pending[prepared.workout.id]
            save_manifest(self.repo, manifest)
            pending = None
        if identity_matches and previous is None and pending is None:
            raise PublicationSafetyError(
                "Remote owned-looking event exists without a local manifest"
            )
        return pending

    def _recover_pending_identity(
        self,
        prepared: PreparedPublication,
        manifest: PublicationManifest,
        previous: PublishedWorkout | None,
        pending: PendingWorkoutPublication | None,
        identity_matches: list[EventDTO],
        *,
        restore_local: bool,
    ) -> PublicationResult | None:
        if pending is not None and identity_matches:
            recovered = identity_matches[0]
            try:
                assert_remote_matches(
                    recovered,
                    prepared.event,
                    prepared.expected_step_semantics,
                )
            except PublicationSafetyError:
                if previous is None:
                    if restore_local:
                        return None
                    raise
                if restore_local:
                    return None
                # A known previous version can legitimately remain when the
                # interrupted upsert failed before applying the pending update.
                assert_remote_unchanged(recovered, previous)
            else:
                remote_uid = assert_remote_external_ownership(
                    recovered,
                    external_id=prepared.external_id,
                )
                recovered_event = prepared.event.model_copy(update={"uid": remote_uid})
                recovered_fingerprint = publication_fingerprint(
                    recovered_event,
                    prepared.settings_version_sha256,
                )
                manifest.workouts[prepared.workout.id] = published_record(
                    workout=prepared.workout,
                    workout_identity=prepared.workout_identity,
                    event_id=recovered.id,
                    requested_uid=prepared.requested_uid,
                    uid=remote_uid,
                    external_id=prepared.external_id,
                    fingerprint=recovered_fingerprint,
                    rendered_hash=prepared.rendered_workout_sha256,
                    settings_version=prepared.settings_version_sha256,
                    provider_start_local=prepared.provider_start_date_local,
                    garmin_eligible=prepared.garmin_forwarding_eligible,
                    remote=recovered,
                )
                del manifest.pending[prepared.workout.id]
                save_manifest(self.repo, manifest)
                return PublicationResult(
                    action="recovered",
                    local_workout_id=prepared.workout.id,
                    event_id=recovered.id,
                    uid=remote_uid,
                    external_id=prepared.external_id,
                    fingerprint_sha256=recovered_fingerprint,
                    garmin_forwarding_status=garmin_forwarding_status(
                        eligible=prepared.garmin_forwarding_eligible,
                        remote=recovered,
                    ),
                    provider_push_errors=provider_push_errors(recovered),
                )
        return None

    def _reconcile_previous(
        self,
        prepared: PreparedPublication,
        manifest: PublicationManifest,
        previous: PublishedWorkout | None,
        pending: PendingWorkoutPublication | None,
        *,
        restore_local: bool,
    ) -> PublicationResult | None:
        if previous is not None:
            if (
                previous.requested_uid != prepared.requested_uid
                or previous.external_id != prepared.external_id
            ):
                raise PublicationSafetyError("Local manifest ownership identity drifted")
            remote = self.client.get_event(
                previous.event_id,
                athlete_id=prepared.athlete_id,
            )
            assert_remote_ownership(
                remote,
                uid=prepared.event.uid,
                external_id=prepared.external_id,
            )
            if pending is not None:
                try:
                    assert_remote_matches(
                        remote,
                        prepared.event,
                        prepared.expected_step_semantics,
                    )
                except PublicationSafetyError:
                    # The durable intent is for a not-yet-applied update. The
                    # known, manifest-owned prior version may be upserted.
                    if restore_local:
                        return None
                    assert_remote_unchanged(remote, previous)
                else:
                    manifest.workouts[prepared.workout.id] = published_record(
                        workout=prepared.workout,
                        workout_identity=prepared.workout_identity,
                        event_id=remote.id,
                        requested_uid=prepared.requested_uid,
                        uid=prepared.event.uid,
                        external_id=prepared.external_id,
                        fingerprint=prepared.publication_fingerprint_sha256,
                        rendered_hash=prepared.rendered_workout_sha256,
                        settings_version=prepared.settings_version_sha256,
                        provider_start_local=prepared.provider_start_date_local,
                        garmin_eligible=prepared.garmin_forwarding_eligible,
                        remote=remote,
                    )
                    del manifest.pending[prepared.workout.id]
                    save_manifest(self.repo, manifest)
                    return PublicationResult(
                        action="recovered",
                        local_workout_id=prepared.workout.id,
                        event_id=remote.id,
                        uid=prepared.event.uid,
                        external_id=prepared.external_id,
                        fingerprint_sha256=prepared.publication_fingerprint_sha256,
                        garmin_forwarding_status=garmin_forwarding_status(
                            eligible=prepared.garmin_forwarding_eligible,
                            remote=remote,
                        ),
                        provider_push_errors=provider_push_errors(remote),
                    )
            else:
                if restore_local:
                    try:
                        assert_remote_matches(
                            remote,
                            prepared.event,
                            prepared.expected_step_semantics,
                        )
                    except PublicationSafetyError:
                        return None
                else:
                    assert_remote_unchanged(remote, previous)
            if previous.publication_fingerprint_sha256 == prepared.publication_fingerprint_sha256:
                assert_remote_matches(
                    remote,
                    prepared.event,
                    prepared.expected_step_semantics,
                )
                manifest.workouts[prepared.workout.id] = published_record(
                    workout=prepared.workout,
                    workout_identity=prepared.workout_identity,
                    event_id=remote.id,
                    requested_uid=prepared.requested_uid,
                    uid=prepared.event.uid,
                    external_id=prepared.external_id,
                    fingerprint=prepared.publication_fingerprint_sha256,
                    rendered_hash=prepared.rendered_workout_sha256,
                    settings_version=prepared.settings_version_sha256,
                    provider_start_local=prepared.provider_start_date_local,
                    garmin_eligible=prepared.garmin_forwarding_eligible,
                    remote=remote,
                )
                save_manifest(self.repo, manifest)
                return PublicationResult(
                    action="noop",
                    local_workout_id=prepared.workout.id,
                    event_id=previous.event_id,
                    uid=prepared.event.uid,
                    external_id=prepared.external_id,
                    fingerprint_sha256=prepared.publication_fingerprint_sha256,
                    garmin_forwarding_status=garmin_forwarding_status(
                        eligible=prepared.garmin_forwarding_eligible,
                        remote=remote,
                    ),
                    provider_push_errors=provider_push_errors(remote),
                )
        return None

    def _upsert(
        self,
        prepared: PreparedPublication,
        manifest: PublicationManifest,
        previous: PublishedWorkout | None,
    ) -> PublicationResult:
        workout = prepared.workout
        manifest.pending[workout.id] = PendingWorkoutPublication(
            workout_identity=prepared.workout_identity,
            uid=prepared.event.uid,
            external_id=prepared.external_id,
            publication_fingerprint_sha256=(prepared.publication_fingerprint_sha256),
            rendered_workout_sha256=prepared.rendered_workout_sha256,
            sport_settings_version_sha256=prepared.settings_version_sha256,
            sport=str(workout.sport),
            occurrence_date=workout.date,
            approved_start_time_local=workout.start_time_local,
            provider_start_date_local=prepared.provider_start_date_local,
            prepared_at_utc=datetime.now(timezone.utc),
        )
        save_manifest(self.repo, manifest)
        response = self.client.upsert_event(
            prepared.event,
            athlete_id=prepared.athlete_id,
        )
        read_back = self.client.get_event(
            response.id,
            athlete_id=prepared.athlete_id,
        )
        remote_uid = assert_remote_external_ownership(
            read_back,
            external_id=prepared.external_id,
        )
        assert_remote_matches(
            read_back,
            prepared.event,
            prepared.expected_step_semantics,
        )
        persisted_event = prepared.event.model_copy(update={"uid": remote_uid})
        persisted_fingerprint = publication_fingerprint(
            persisted_event,
            prepared.settings_version_sha256,
        )

        manifest.workouts[workout.id] = published_record(
            workout=workout,
            workout_identity=prepared.workout_identity,
            event_id=read_back.id,
            requested_uid=prepared.requested_uid,
            uid=remote_uid,
            external_id=prepared.external_id,
            fingerprint=persisted_fingerprint,
            rendered_hash=prepared.rendered_workout_sha256,
            settings_version=prepared.settings_version_sha256,
            provider_start_local=prepared.provider_start_date_local,
            garmin_eligible=prepared.garmin_forwarding_eligible,
            remote=read_back,
        )
        del manifest.pending[workout.id]
        save_manifest(self.repo, manifest)
        return PublicationResult(
            action="updated" if previous else "created",
            local_workout_id=workout.id,
            event_id=read_back.id,
            uid=remote_uid,
            external_id=prepared.external_id,
            fingerprint_sha256=persisted_fingerprint,
            garmin_forwarding_status=garmin_forwarding_status(
                eligible=prepared.garmin_forwarding_eligible,
                remote=read_back,
            ),
            provider_push_errors=provider_push_errors(read_back),
        )

    def delete(self, local_workout_id: str) -> PublicationResult:
        lock_path = self.repo.resolve_path("data/state/.workout-publication.lock")
        with OperationLock(lock_path, "workout_publication"):
            return self._delete(local_workout_id)

    def _delete(
        self,
        local_workout_id: str,
        *,
        restore_local: bool = False,
    ) -> PublicationResult:
        manifest = load_manifest(self.repo)
        record = manifest.workouts.get(local_workout_id)
        if record is None:
            raise PublicationSafetyError("Deletion requires a local publication manifest record")
        athlete = self.client.get_athlete()
        try:
            remote = self.client.get_event(
                record.event_id,
                athlete_id=athlete.id,
            )
        except IntervalsNotFoundError:
            del manifest.workouts[local_workout_id]
            save_manifest(self.repo, manifest)
            return PublicationResult(
                action="recovered_deleted",
                local_workout_id=local_workout_id,
                event_id=record.event_id,
                uid=record.uid,
                external_id=record.external_id,
            )
        assert_remote_ownership(
            remote,
            uid=record.uid,
            external_id=record.external_id,
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
        del manifest.workouts[local_workout_id]
        save_manifest(self.repo, manifest)
        return PublicationResult(
            action="deleted",
            local_workout_id=local_workout_id,
            event_id=record.event_id,
            uid=record.uid,
            external_id=record.external_id,
        )
