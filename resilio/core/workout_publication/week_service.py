"""Preflight and reconcile one exact applied week's running workouts."""

from __future__ import annotations

from datetime import date, datetime, timezone

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.service import PlanOperationError
from resilio.core.planning.state_repository import required_planning_state_unlocked
from resilio.core.planning.workout_evidence import load_publishable_workouts_unlocked
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.capabilities import (
    get_run_synchronization_capabilities,
)
from resilio.core.workout_publication.completions import load_completion_manifest
from resilio.core.workout_publication.locking import coordinated_publication_plan_lock
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.naming import provider_workout_names
from resilio.core.workout_publication.policy import (
    ProviderSemanticsMismatchError,
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_matches,
    assert_remote_ownership,
    assert_remote_unchanged,
    pending_matches,
)
from resilio.core.workout_publication.preparation import prepare_publication
from resilio.core.workout_publication.service import WorkoutPublicationService
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import (
    IntervalsIcuError,
    IntervalsNotFoundError,
)
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import (
    PublicationDriftResolution,
    RunWeekSynchronizationReport,
    WeekSynchronizationItem,
)


def _identity_tuple(identity: PlanWorkoutIdentity) -> tuple[str, str, int, str]:
    return (
        identity.plan_id,
        identity.plan_revision_id,
        identity.week_number,
        identity.local_workout_id,
    )


def _publication_error_type(exc: Exception) -> str:
    if isinstance(exc, ProviderSemanticsMismatchError):
        return "provider_semantics_mismatch"
    if isinstance(exc, RemoteWorkoutDriftError):
        return "remote_drift"
    if isinstance(exc, PublicationSafetyError):
        return "publication_safety"
    if isinstance(exc, IntervalsIcuError):
        return exc.error_type
    return "publication"


class RunWeekSynchronizationService:
    """Run-only orchestration over exact applied-week authority."""

    def __init__(self, repo: RepositoryIO, client: IntervalsIcuClient):
        self.repo = repo
        self.client = client
        self.workout_service = WorkoutPublicationService(repo, client)

    def _load_authoritative_week_unlocked(
        self,
        week_number: int,
    ) -> list[AuthoritativeWorkout]:
        try:
            workouts = load_publishable_workouts_unlocked(
                self.repo,
                required_planning_state_unlocked(self.repo),
            )
        except PlanOperationError as exc:
            raise PublicationSafetyError(str(exc)) from exc
        selected = [
            workout for workout in workouts if workout.identity.week_number == week_number
        ]
        if not selected:
            raise PublicationSafetyError(
                f"Week {week_number} has no exact active applied-week authority"
            )
        return selected

    def _completed_workout_identities(self) -> set[tuple[str, str, int, str]]:
        return {
            _identity_tuple(match.workout_identity)
            for match in load_completion_manifest(self.repo).matches.values()
        }

    def _selected_runs(
        self,
        workouts: list[AuthoritativeWorkout],
        as_of_date: date,
    ) -> tuple[
        list[AuthoritativeWorkout],
        list[WeekSynchronizationItem],
        int,
        set[str],
        PlanWorkoutIdentity,
    ]:
        week_identity = workouts[0].identity
        completed = self._completed_workout_identities()
        run_workouts = [item for item in workouts if str(item.prescription.sport) == "run"]
        ignored_non_runs = len(workouts) - len(run_workouts)
        selected: list[AuthoritativeWorkout] = []
        skipped: list[WeekSynchronizationItem] = []
        current_run_ids = {item.identity.local_workout_id for item in run_workouts}
        for item in sorted(
            run_workouts,
            key=lambda candidate: (
                candidate.prescription.date,
                candidate.identity.local_workout_id,
            ),
        ):
            workout = item.prescription
            if workout.date < as_of_date:
                skipped.append(
                    WeekSynchronizationItem(
                        local_workout_id=workout.id,
                        occurrence_date=workout.date,
                        status="skipped_past",
                    )
                )
            elif _identity_tuple(item.identity) in completed:
                skipped.append(
                    WeekSynchronizationItem(
                        local_workout_id=workout.id,
                        occurrence_date=workout.date,
                        status="skipped_completed",
                    )
                )
            else:
                selected.append(item)
        return selected, skipped, ignored_non_runs, current_run_ids, week_identity

    def _stale_future_owned_run_ids(
        self,
        week_identity: PlanWorkoutIdentity,
        current_run_ids: set[str],
        as_of_date: date,
    ) -> list[str]:
        manifest = load_manifest(self.repo)
        completed = self._completed_workout_identities()
        return sorted(
            local_id
            for local_id, record in manifest.workouts.items()
            if record.workout_identity.plan_id == week_identity.plan_id
            and record.workout_identity.plan_revision_id
            == week_identity.plan_revision_id
            and record.workout_identity.week_number == week_identity.week_number
            and record.sport == "run"
            and record.occurrence_date >= as_of_date
            and _identity_tuple(record.workout_identity) not in completed
            and local_id not in current_run_ids
        )

    def _verify_one(
        self,
        workout: AuthoritativeWorkout,
        *,
        restore_local: bool,
        provider_name: str,
    ) -> None:
        manifest = load_manifest(self.repo)
        previous = manifest.workouts.get(workout.identity.local_workout_id)
        prepared = prepare_publication(
            self.client,
            workout,
            previous=previous,
            provider_name=provider_name,
        )
        pending = manifest.pending.get(workout.identity.local_workout_id)
        matches = self.workout_service._identity_matches(
            prepared,
            previous,
            pending,
        )
        pending_matches_prepared = pending is not None and pending_matches(
            pending,
            uid=prepared.event.uid,
            external_id=prepared.external_id,
            fingerprint=prepared.publication_fingerprint_sha256,
        )
        if pending is not None and not pending_matches_prepared and matches:
            raise PublicationSafetyError(
                "Pending publication intent changed after a remote event claimed its identity"
            )
        if previous is None and matches and pending is None:
            raise PublicationSafetyError(
                "Remote owned-looking event exists without a local manifest"
            )
        if previous is None and matches:
            if not restore_local:
                assert_remote_matches(
                    matches[0],
                    prepared.event,
                    prepared.expected_step_semantics,
                )
        if previous is not None:
            remote = self.client.get_event(previous.event_id, athlete_id=prepared.athlete_id)
            assert_remote_ownership(
                remote,
                uid=previous.uid,
                external_id=previous.external_id,
            )
            if restore_local:
                return
            if pending_matches_prepared:
                try:
                    assert_remote_matches(
                        remote,
                        prepared.event,
                        prepared.expected_step_semantics,
                    )
                except PublicationSafetyError:
                    assert_remote_unchanged(remote, previous)
            else:
                assert_remote_unchanged(remote, previous)
            if (
                pending is None
                and previous.publication_fingerprint_sha256
                == prepared.publication_fingerprint_sha256
            ):
                assert_remote_matches(
                    remote,
                    prepared.event,
                    prepared.expected_step_semantics,
                )

    def _verify_owned_future_deletion(
        self,
        local_workout_id: str,
        *,
        restore_local: bool,
    ) -> None:
        record = load_manifest(self.repo).workouts[local_workout_id]
        athlete = self.client.get_athlete()
        try:
            remote = self.client.get_event(record.event_id, athlete_id=athlete.id)
        except IntervalsNotFoundError:
            return
        assert_remote_ownership(remote, uid=record.uid, external_id=record.external_id)
        if not restore_local:
            assert_remote_unchanged(remote, record)

    def _status_authoritative_week(
        self,
        week_number: int,
        *,
        as_of_date: date,
        workouts: list[AuthoritativeWorkout],
        restore_local: bool = False,
    ) -> RunWeekSynchronizationReport:
        capabilities = get_run_synchronization_capabilities(self.client)
        (
            selected,
            skipped,
            ignored_non_runs,
            current_run_ids,
            week_identity,
        ) = self._selected_runs(workouts, as_of_date)
        stale_ids = self._stale_future_owned_run_ids(
            week_identity,
            current_run_ids,
            as_of_date,
        )
        items = list(skipped)
        passed = True
        provider_names = provider_workout_names(
            [
                item.prescription
                for item in workouts
                if str(item.prescription.sport) == "run"
            ]
        )
        for workout in selected:
            try:
                self._verify_one(
                    workout,
                    restore_local=restore_local,
                    provider_name=provider_names[workout.identity.local_workout_id],
                )
            except Exception as exc:
                passed = False
                items.append(
                    WeekSynchronizationItem(
                        local_workout_id=workout.identity.local_workout_id,
                        occurrence_date=workout.prescription.date,
                        status="error",
                        error_type=_publication_error_type(exc),
                        message=str(exc),
                    )
                )
            else:
                items.append(
                    WeekSynchronizationItem(
                        local_workout_id=workout.identity.local_workout_id,
                        occurrence_date=workout.prescription.date,
                        status="ready",
                        garmin_forwarding_status=(
                            "eligible_unverified"
                            if capabilities.garmin_forwarding_eligible
                            else "not_configured"
                        ),
                    )
                )
        for local_workout_id in stale_ids:
            try:
                self._verify_owned_future_deletion(
                    local_workout_id,
                    restore_local=restore_local,
                )
            except Exception as exc:
                passed = False
                record = load_manifest(self.repo).workouts[local_workout_id]
                items.append(
                    WeekSynchronizationItem(
                        local_workout_id=local_workout_id,
                        occurrence_date=record.occurrence_date,
                        status="error",
                        error_type=_publication_error_type(exc),
                        message=str(exc),
                    )
                )
        return RunWeekSynchronizationReport(
            week_number=week_number,
            as_of_date=as_of_date,
            operation="restore_local" if restore_local else "status",
            reconciliation_safe=passed,
            run_workouts_considered=len(selected) + len(skipped),
            desired_future_run_workouts=len(selected),
            ignored_non_run_workouts=ignored_non_runs,
            partial=not passed,
            capabilities=capabilities,
            items=items,
            owned_future_deletion_ids=stale_ids,
        )

    def status_week(
        self,
        week_number: int,
        *,
        as_of_date: date,
    ) -> RunWeekSynchronizationReport:
        with coordinated_publication_plan_lock(
            self.repo,
            "status_run_week_synchronization",
        ):
            workouts = self._load_authoritative_week_unlocked(week_number)
            return self._status_authoritative_week(
                week_number,
                as_of_date=as_of_date,
                workouts=workouts,
            )

    def reconcile_week(
        self,
        week_number: int,
        *,
        as_of_date: date,
    ) -> RunWeekSynchronizationReport:
        with coordinated_publication_plan_lock(self.repo, "reconcile_run_week"):
            workouts = self._load_authoritative_week_unlocked(week_number)
            status = self._status_authoritative_week(
                week_number,
                as_of_date=as_of_date,
                workouts=workouts,
            )
            if not status.reconciliation_safe:
                return status.model_copy(update={"operation": "reconcile"})
            return self._reconcile_status(
                status,
                workouts=workouts,
                as_of_date=as_of_date,
                restore_local=False,
            )

    def restore_local_week(
        self,
        week_number: int,
        *,
        as_of_date: date,
        athlete_confirmation_reference: str,
    ) -> RunWeekSynchronizationReport:
        """Replace exact owned drift only after explicit athlete confirmation."""
        confirmation = athlete_confirmation_reference.strip()
        if not confirmation:
            raise PublicationSafetyError(
                "Restore-local drift resolution requires athlete confirmation evidence"
            )
        with coordinated_publication_plan_lock(self.repo, "restore_local_run_week"):
            workouts = self._load_authoritative_week_unlocked(week_number)
            ordinary_status = self._status_authoritative_week(
                week_number,
                as_of_date=as_of_date,
                workouts=workouts,
            )
            error_types = {
                item.error_type
                for item in ordinary_status.items
                if item.status == "error"
            }
            if not error_types:
                raise PublicationSafetyError(
                    "Restore-local requested, but there is no owned remote drift"
                )
            if error_types != {"remote_drift"}:
                return ordinary_status.model_copy(update={"operation": "restore_local"})
            identity = workouts[0].identity
            manifest = load_manifest(self.repo)
            manifest.drift_resolutions.append(
                PublicationDriftResolution(
                    plan_id=identity.plan_id,
                    plan_revision_id=identity.plan_revision_id,
                    week_number=week_number,
                    athlete_confirmation_reference=confirmation,
                    confirmed_at_utc=datetime.now(timezone.utc),
                )
            )
            save_manifest(self.repo, manifest)
            status = self._status_authoritative_week(
                week_number,
                as_of_date=as_of_date,
                workouts=workouts,
                restore_local=True,
            )
            if not status.reconciliation_safe:
                return status
            return self._reconcile_status(
                status,
                workouts=workouts,
                as_of_date=as_of_date,
                restore_local=True,
            )

    def _reconcile_status(
        self,
        status: RunWeekSynchronizationReport,
        *,
        workouts: list[AuthoritativeWorkout],
        as_of_date: date,
        restore_local: bool,
    ) -> RunWeekSynchronizationReport:
        selected, skipped, _, _, _ = self._selected_runs(workouts, as_of_date)
        provider_names = provider_workout_names(
            [
                item.prescription
                for item in workouts
                if str(item.prescription.sport) == "run"
            ]
        )
        items = list(skipped)
        partial = False
        for workout in selected:
            try:
                result = self.workout_service._publish(
                    workout,
                    restore_local=restore_local,
                    provider_name=provider_names[workout.identity.local_workout_id],
                )
            except Exception as exc:
                partial = True
                items.append(
                    WeekSynchronizationItem(
                        local_workout_id=workout.identity.local_workout_id,
                        occurrence_date=workout.prescription.date,
                        status="error",
                        error_type=_publication_error_type(exc),
                        message=str(exc),
                    )
                )
            else:
                items.append(
                    WeekSynchronizationItem(
                        local_workout_id=result.local_workout_id,
                        occurrence_date=workout.prescription.date,
                        status=result.action,
                        event_id=result.event_id,
                        garmin_forwarding_status=result.garmin_forwarding_status,
                        provider_push_errors=result.provider_push_errors,
                    )
                )
        if not partial:
            for local_workout_id in status.owned_future_deletion_ids:
                record = load_manifest(self.repo).workouts[local_workout_id]
                try:
                    result = self.workout_service._delete(
                        local_workout_id,
                        restore_local=restore_local,
                    )
                except Exception as exc:
                    partial = True
                    items.append(
                        WeekSynchronizationItem(
                            local_workout_id=local_workout_id,
                            occurrence_date=record.occurrence_date,
                            status="error",
                            event_id=record.event_id,
                            error_type=_publication_error_type(exc),
                            message=str(exc),
                        )
                    )
                else:
                    items.append(
                        WeekSynchronizationItem(
                            local_workout_id=local_workout_id,
                            occurrence_date=record.occurrence_date,
                            status=result.action,
                            event_id=result.event_id,
                        )
                    )
        return status.model_copy(
            update={
                "operation": "restore_local" if restore_local else "reconcile",
                "partial": partial,
                "items": items,
            }
        )
