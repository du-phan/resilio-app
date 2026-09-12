"""Ownership-proven idempotent workout publication."""

from __future__ import annotations

from datetime import date

from resilio.core.locking import OperationLock
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.authority_matching import (
    publication_record_has_retained_workout_authority,
)
from resilio.core.workout_publication.execution_placement import (
    assert_fulfillment_pair_matches_remote_placement,
)
from resilio.core.workout_publication.identity_discovery import (
    discover_owned_identity_matches,
)
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.pending_recovery import (
    remote_matches_previous_at_desired_date,
    superseded_pending_action,
)
from resilio.core.workout_publication.policy import (
    PublicationSafetyError as PublicationSafetyError,
)
from resilio.core.workout_publication.policy import (
    RemoteWorkoutDriftError,
    assert_remote_matches,
    assert_remote_ownership,
    assert_remote_unchanged,
    pending_matches,
    provider_event_state_fingerprint,
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
from resilio.core.workout_publication.publication_records import (
    persist_prepared_publication,
    persist_recovered_publication,
    publication_result,
)
from resilio.core.workout_publication.publication_upsert import (
    upsert_prepared_publication,
)
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.core.workout_publication.retirement_service import (
    WorkoutRetirementService,
)
from resilio.core.workout_publication.schedule_adoption import (
    record_independently_observed_same_week_date,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationAction,
    PublicationManifest,
    PublicationResult,
    PublishedWorkout,
)
from resilio.schemas.publication_placement import ProviderOccurrencePlacement


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
        adopt_remote_schedule: bool = False,
        provider_occurrence_placement: ProviderOccurrencePlacement | None = None,
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
            provider_occurrence_placement=provider_occurrence_placement,
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
            adopt_remote_schedule=adopt_remote_schedule,
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
            adopt_remote_schedule=adopt_remote_schedule,
        )
        if recovered_or_noop is not None:
            return recovered_or_noop
        return self._upsert(
            prepared,
            manifest,
            previous,
            expected_existing_target=expected_remote_target,
        )

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
        adopt_remote_schedule: bool,
    ) -> PublicationResult | None:
        if (
            pending is None
            or not identity_matches
            or pending_matches(
                pending,
                uid=prepared.event.uid,
                external_id=prepared.external_id,
                fingerprint=prepared.publication_fingerprint_sha256,
            )
        ):
            return None
        if not publication_record_has_retained_workout_authority(
            pending,
            authoritative_workout,
        ):
            raise PublicationSafetyError(
                "Superseded pending publication lacks retained workout authority"
            )
        if expected_remote_target is not None:
            remote = identity_matches[0]
            self._assert_confirmed_remote_target(
                remote,
                expected_remote_target=expected_remote_target,
            )
            return self._upsert(
                prepared,
                manifest,
                previous,
                expected_existing_target=(
                    remote.id,
                    provider_event_state_fingerprint(remote),
                ),
            )
        if restore_local:
            raise PublicationSafetyError(
                "Restoring superseded pending drift requires one exact confirmed target"
            )
        try:
            pending_prepared = prepare_current_authority_pending(
                self.client,
                authoritative_workout,
                previous=previous,
                pending=pending,
                pending_occurrence_placement=(
                    manifest.pending_provider_occurrence_placements[prepared.workout.id]
                ),
                provider_name=provider_name or prepared.event.name,
            )
        except PublicationSafetyError:
            pending_prepared = None
        remote = identity_matches[0]
        action = superseded_pending_action(
            self.repo,
            self.client,
            remote,
            prepared,
            pending_prepared,
            previous,
            adopt_remote_schedule=adopt_remote_schedule,
            current_settings_changed=(
                pending.sport_settings_version_sha256 != prepared.settings_version_sha256
            ),
        )
        if action == "persist_current":
            if previous is None:
                assert_fulfillment_pair_matches_remote_placement(
                    self.repo,
                    self.client,
                    prepared.provider_occurrence_placement,
                    remote,
                )
            remote = self._fresh_recovery_readback(prepared, remote)
            return persist_recovered_publication(
                self.repo,
                manifest,
                prepared,
                remote,
            )
        return self._upsert(
            prepared,
            manifest,
            previous,
            remote_identity_exists=True,
            expected_existing_target=(
                remote.id,
                provider_event_state_fingerprint(remote),
            ),
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

    def _fresh_recovery_readback(
        self,
        prepared: PreparedPublication,
        observed: EventDTO,
    ) -> EventDTO:
        """Recheck exact event bytes after every recovery preflight provider call."""
        fresh = get_exact_event(
            self.client,
            observed.id,
            athlete_id=prepared.athlete_id,
        )
        if provider_event_state_fingerprint(fresh) != provider_event_state_fingerprint(observed):
            raise RemoteWorkoutDriftError(
                "Remote event changed immediately before pending recovery"
            )
        assert_remote_matches(
            fresh,
            prepared.event,
            prepared.expected_step_semantics,
        )
        return fresh

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
            or provider_event_state_fingerprint(remote) != expected_remote_target[1]
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
            del manifest.pending_provider_occurrence_placements[prepared.workout.id]
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
                if previous is None:
                    assert_fulfillment_pair_matches_remote_placement(
                        self.repo,
                        self.client,
                        prepared.provider_occurrence_placement,
                        recovered,
                    )
                recovered = self._fresh_recovery_readback(prepared, recovered)
                return persist_recovered_publication(
                    self.repo,
                    manifest,
                    prepared,
                    recovered,
                )
        return None

    def _persist_verified_readback(
        self,
        manifest: PublicationManifest,
        prepared: PreparedPublication,
        remote: EventDTO,
        *,
        action: PublicationAction,
    ) -> PublicationResult:
        persist_prepared_publication(manifest, prepared, remote)
        save_manifest(self.repo, manifest)
        return publication_result(prepared, remote, action=action)

    def _owned_previous_remote(
        self,
        prepared: PreparedPublication,
        previous: PublishedWorkout,
    ) -> EventDTO:
        if (
            previous.requested_uid != prepared.requested_uid
            or previous.external_id != prepared.external_id
        ):
            raise PublicationSafetyError("Local manifest ownership identity drifted")
        remote = get_exact_event(
            self.client,
            previous.event_id,
            athlete_id=prepared.athlete_id,
        )
        assert_remote_ownership(
            remote,
            uid=prepared.event.uid,
            external_id=prepared.external_id,
        )
        return remote

    def _reconcile_previous(
        self,
        prepared: PreparedPublication,
        manifest: PublicationManifest,
        previous: PublishedWorkout | None,
        pending: PendingWorkoutPublication | None,
        *,
        restore_local: bool,
        expected_remote_target: tuple[int, str] | None,
        adopt_remote_schedule: bool,
    ) -> PublicationResult | None:
        if previous is not None:
            remote = self._owned_previous_remote(prepared, previous)
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
                    return self._persist_verified_readback(
                        manifest, prepared, remote, action="recovered"
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
                    try:
                        assert_remote_unchanged(remote, previous)
                    except PublicationSafetyError as drift_error:
                        try:
                            assert_remote_matches(
                                remote,
                                prepared.event,
                                prepared.expected_step_semantics,
                            )
                        except PublicationSafetyError:
                            if not (
                                adopt_remote_schedule
                                and remote_matches_previous_at_desired_date(
                                    self.repo,
                                    self.client,
                                    remote,
                                    previous,
                                    prepared,
                                )
                            ):
                                raise drift_error
                            return self._upsert(
                                prepared,
                                manifest,
                                previous,
                                expected_existing_target=(
                                    remote.id,
                                    provider_event_state_fingerprint(remote),
                                ),
                            )
                        else:
                            persisted_prepared = record_independently_observed_same_week_date(
                                prepared,
                                previous,
                                remote,
                            )
                            return self._persist_verified_readback(
                                manifest,
                                persisted_prepared,
                                remote,
                                action="recovered",
                            )
                    if (
                        adopt_remote_schedule
                        and previous.publication_fingerprint_sha256
                        != prepared.publication_fingerprint_sha256
                    ):
                        raise RemoteWorkoutDriftError(
                            "Remote schedule changed after date-only move verification"
                        )
            if previous.publication_fingerprint_sha256 == prepared.publication_fingerprint_sha256:
                assert_remote_matches(
                    remote,
                    prepared.event,
                    prepared.expected_step_semantics,
                )
                return self._persist_verified_readback(manifest, prepared, remote, action="noop")
        return None

    def _upsert(
        self,
        prepared: PreparedPublication,
        manifest: PublicationManifest,
        previous: PublishedWorkout | None,
        *,
        remote_identity_exists: bool = False,
        expected_existing_target: tuple[int, str] | None = None,
    ) -> PublicationResult:
        return upsert_prepared_publication(
            self.repo,
            self.client,
            prepared,
            manifest,
            previous,
            remote_identity_exists=remote_identity_exists,
            expected_existing_target=expected_existing_target,
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
