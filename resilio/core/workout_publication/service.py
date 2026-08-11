"""Ownership-proven idempotent workout publication."""

from __future__ import annotations

from datetime import date, datetime, timezone

from resilio.core.locking import OperationLock
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.identity_discovery import (
    discover_owned_identity_matches,
)
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError as PublicationSafetyError,
)
from resilio.core.workout_publication.policy import (
    RemoteWorkoutDriftError,
    assert_remote_external_ownership,
    assert_remote_matches,
    assert_remote_ownership,
    assert_remote_unchanged,
    garmin_forwarding_status,
    pending_matches,
    provider_event_fingerprint,
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
    prepare_current_authority_pending,
    prepare_publication,
)
from resilio.core.workout_publication.publication_deletions import (
    publication_deletion_workout_ids,
)
from resilio.core.workout_publication.retirement_service import (
    WorkoutRetirementService,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.integrations.intervals_icu.errors import (
    IntervalsIcuError,
    IntervalsRequestNotSubmittedError,
)
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationManifest,
    PublicationResult,
    PublishedWorkout,
)


def _prepared_published_record(
    prepared: PreparedPublication,
    remote: EventDTO,
) -> PublishedWorkout:
    return published_record(
        workout=prepared.workout,
        workout_identity=prepared.workout_identity,
        applied_week_approval_id=prepared.applied_week_approval_id,
        applied_running_workouts_sha256=prepared.applied_running_workouts_sha256,
        workout_prescription_sha256=prepared.workout_prescription_sha256,
        schedule_timezone=prepared.schedule_timezone,
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


class WorkoutPublicationService:
    def __init__(
        self,
        repo: RepositoryIO,
        client: IntervalsIcuClient,
    ):
        self.repo = repo
        self.client = client

    def _publish(
        self,
        authoritative_workout: AuthoritativeWorkout,
        *,
        provider_occurrence_date: date,
        restore_local: bool = False,
        provider_name: str | None = None,
        expected_remote_target: tuple[int, str] | None = None,
    ) -> PublicationResult:
        workout = authoritative_workout.prescription
        if workout.id in publication_deletion_workout_ids(self.repo):
            raise PublicationSafetyError(
                "Workout ID is permanently reserved by a publication deletion tombstone"
            )
        manifest = load_manifest(self.repo)
        previous = manifest.workouts.get(workout.id)
        prepared = prepare_publication(
            self.client,
            authoritative_workout,
            previous=previous,
            provider_name=provider_name,
            provider_occurrence_date=provider_occurrence_date,
        )
        pending = manifest.pending.get(workout.id)
        identity_matches = self._identity_matches(prepared, previous, pending)
        superseded_pending_result = self._recover_superseded_pending_intent(
            authoritative_workout,
            manifest=manifest,
            prepared=prepared,
            previous=previous,
            pending=pending,
            identity_matches=identity_matches,
            restore_local=restore_local,
            provider_name=provider_name,
            expected_remote_target=expected_remote_target,
        )
        if superseded_pending_result is not None:
            return superseded_pending_result
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
            expected_remote_target=expected_remote_target,
        )
        if recovered is not None:
            return recovered
        recovered_or_noop = self._reconcile_previous(
            prepared,
            manifest,
            previous,
            pending,
            restore_local=restore_local,
            expected_remote_target=expected_remote_target,
        )
        if recovered_or_noop is not None:
            return recovered_or_noop
        return self._upsert(prepared, manifest, previous)

    def _recover_superseded_pending_intent(
        self,
        authoritative_workout: AuthoritativeWorkout,
        *,
        manifest: PublicationManifest,
        prepared: PreparedPublication,
        previous: PublishedWorkout | None,
        pending: PendingWorkoutPublication | None,
        identity_matches: list[EventDTO],
        restore_local: bool,
        provider_name: str | None,
        expected_remote_target: tuple[int, str] | None,
    ) -> PublicationResult | None:
        if pending is None or not identity_matches or pending_matches(
            pending,
            uid=prepared.event.uid,
            external_id=prepared.external_id,
            fingerprint=prepared.publication_fingerprint_sha256,
        ):
            return None
        if expected_remote_target is not None:
            remote = identity_matches[0]
            self._assert_confirmed_remote_target(
                remote,
                expected_remote_target=expected_remote_target,
            )
            return self._upsert(prepared, manifest, previous)
        if restore_local:
            raise PublicationSafetyError(
                "Restoring superseded pending drift requires one exact confirmed target"
            )
        if provider_name is None:
            raise PublicationSafetyError(
                "Superseded pending publication requires its deterministic provider name"
            )
        pending_prepared = prepare_current_authority_pending(
            self.client,
            authoritative_workout,
            previous=previous,
            pending=pending,
            provider_name=provider_name,
        )
        remote = identity_matches[0]
        if previous is not None:
            try:
                assert_remote_unchanged(remote, previous)
            except RemoteWorkoutDriftError:
                pass
            else:
                del manifest.pending[prepared.workout.id]
                save_manifest(self.repo, manifest)
                return self._publish(
                    authoritative_workout,
                    provider_name=provider_name,
                    provider_occurrence_date=prepared.provider_occurrence_date,
                )
        self._publish(
            authoritative_workout,
            provider_name=provider_name,
            provider_occurrence_date=pending_prepared.provider_occurrence_date,
        )
        return self._publish(
            authoritative_workout,
            provider_name=provider_name,
            provider_occurrence_date=prepared.provider_occurrence_date,
        )

    def _identity_matches(
        self,
        prepared: PreparedPublication,
        previous: PublishedWorkout | None,
        pending: PendingWorkoutPublication | None,
    ) -> list[EventDTO]:
        return discover_owned_identity_matches(
            self.client,
            prepared,
            previous=previous,
            pending=pending,
        )

    @staticmethod
    def _assert_confirmed_remote_target(
        remote: EventDTO,
        *,
        expected_remote_target: tuple[int, str] | None,
    ) -> None:
        if expected_remote_target is None:
            return
        if (
            remote.id != expected_remote_target[0]
            or provider_event_fingerprint(remote) != expected_remote_target[1]
        ):
            raise PublicationSafetyError("Remote event changed after athlete drift confirmation")

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
        expected_remote_target: tuple[int, str] | None,
    ) -> PublicationResult | None:
        if pending is not None and identity_matches:
            recovered = identity_matches[0]
            self._assert_confirmed_remote_target(
                recovered,
                expected_remote_target=expected_remote_target,
            )
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
                    applied_week_approval_id=prepared.applied_week_approval_id,
                    applied_running_workouts_sha256=(prepared.applied_running_workouts_sha256),
                    workout_prescription_sha256=prepared.workout_prescription_sha256,
                    schedule_timezone=prepared.schedule_timezone,
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
                    provider_occurrence_date=prepared.provider_occurrence_date,
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
        expected_remote_target: tuple[int, str] | None,
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
            self._assert_confirmed_remote_target(
                remote,
                expected_remote_target=expected_remote_target,
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
                    manifest.workouts[prepared.workout.id] = _prepared_published_record(
                        prepared,
                        remote,
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
                        provider_occurrence_date=prepared.provider_occurrence_date,
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
                manifest.workouts[prepared.workout.id] = _prepared_published_record(
                    prepared,
                    remote,
                )
                save_manifest(self.repo, manifest)
                return PublicationResult(
                    action="noop",
                    local_workout_id=prepared.workout.id,
                    event_id=previous.event_id,
                    uid=prepared.event.uid,
                    external_id=prepared.external_id,
                    fingerprint_sha256=prepared.publication_fingerprint_sha256,
                    provider_occurrence_date=prepared.provider_occurrence_date,
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
            applied_week_approval_id=prepared.applied_week_approval_id,
            applied_running_workouts_sha256=prepared.applied_running_workouts_sha256,
            workout_prescription_sha256=prepared.workout_prescription_sha256,
            schedule_timezone=prepared.schedule_timezone,
            uid=prepared.event.uid,
            external_id=prepared.external_id,
            publication_fingerprint_sha256=(prepared.publication_fingerprint_sha256),
            rendered_workout_sha256=prepared.rendered_workout_sha256,
            sport_settings_version_sha256=prepared.settings_version_sha256,
            sport="run",
            occurrence_date=workout.date,
            approved_start_time_local=workout.start_time_local,
            provider_start_date_local=prepared.provider_start_date_local,
            prepared_at_utc=datetime.now(timezone.utc),
        )
        save_manifest(self.repo, manifest)
        try:
            response = self.client.upsert_event(
                prepared.event,
                athlete_id=prepared.athlete_id,
            )
        except IntervalsRequestNotSubmittedError:
            del manifest.pending[workout.id]
            save_manifest(self.repo, manifest)
            raise
        except IntervalsIcuError as exc:
            if (
                exc.status_code is not None
                and 400 <= exc.status_code < 500
                and exc.status_code != 408
            ):
                del manifest.pending[workout.id]
                save_manifest(self.repo, manifest)
            raise
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
            applied_week_approval_id=prepared.applied_week_approval_id,
            applied_running_workouts_sha256=prepared.applied_running_workouts_sha256,
            workout_prescription_sha256=prepared.workout_prescription_sha256,
            schedule_timezone=prepared.schedule_timezone,
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
            provider_occurrence_date=prepared.provider_occurrence_date,
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
        return WorkoutRetirementService(self.repo, self.client).retire_published(
            local_workout_id,
            restore_local=restore_local,
        )
