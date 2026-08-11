"""Preflight and reconcile one exact applied week's running workouts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.service import PlanOperationError
from resilio.core.planning.state_repository import required_planning_state_unlocked
from resilio.core.planning.workout_evidence import load_publishable_workouts_unlocked
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.remote_pairing import (
    WorkoutPairingReconciliationService,
)
from resilio.core.workout_fulfillment.remote_unpairing import (
    WorkoutUnpairingReconciliationService,
)
from resilio.core.workout_publication.drift_confirmation import (
    confirm_publication_drift_targets,
)
from resilio.core.workout_publication.locking import (
    coordinated_publication_plan_activity_lock,
    coordinated_publication_plan_lock,
)
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.naming import provider_workout_names
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    assert_remote_matches,
    assert_remote_ownership,
    assert_remote_unchanged,
    pending_matches,
)
from resilio.core.workout_publication.preparation import prepare_publication
from resilio.core.workout_publication.retained_authority import (
    retained_pending_publication_authorities,
)
from resilio.core.workout_publication.retirement_service import (
    WorkoutRetirementService,
)
from resilio.core.workout_publication.service import WorkoutPublicationService
from resilio.core.workout_publication.week_deletions import (
    reconcile_owned_future_deletions,
)
from resilio.core.workout_publication.week_pairing import (
    attach_remote_pairing_status,
    confirmed_pairing_drift_retry_tokens,
)
from resilio.core.workout_publication.week_selection import (
    select_run_week_items,
)
from resilio.core.workout_publication.week_status import (
    build_run_week_status,
    publication_error_type,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.schemas.publication import (
    PublicationDriftResolution,
    RunWeekSynchronizationReport,
    WeekSynchronizationItem,
)


class RunWeekSynchronizationService:
    """Run-only orchestration over exact applied-week authority."""

    def __init__(self, repo: RepositoryIO, client: IntervalsIcuClient):
        self.repo = repo
        self.client = client
        self.workout_service = WorkoutPublicationService(repo, client)
        self.retirement_service = WorkoutRetirementService(repo, client)
        self.pairing_service = WorkoutPairingReconciliationService(repo, client)
        self.unpairing_service = WorkoutUnpairingReconciliationService(repo, client)

    def _with_remote_pairing_status(
        self,
        report: RunWeekSynchronizationReport,
        *,
        workouts: list[AuthoritativeWorkout],
        mutate: bool,
    ) -> RunWeekSynchronizationReport:
        return attach_remote_pairing_status(
            repo=self.repo,
            pairing_service=self.pairing_service,
            unpairing_service=self.unpairing_service,
            report=report,
            workouts=workouts,
            mutate=mutate,
        )

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
        selected = [workout for workout in workouts if workout.identity.week_number == week_number]
        if not selected:
            raise PublicationSafetyError(
                f"Week {week_number} has no exact active applied-week authority"
            )
        return selected

    def current_schedule_date(
        self,
        week_number: int,
        *,
        now_utc: datetime | None = None,
    ) -> date:
        """Resolve today in the immutable timezone captured by the applied week."""
        with coordinated_publication_plan_lock(
            self.repo,
            "resolve_run_week_schedule_date",
        ):
            workouts = self._load_authoritative_week_unlocked(week_number)
            schedule_timezones = {workout.schedule_timezone for workout in workouts}
            if len(schedule_timezones) != 1:
                raise PublicationSafetyError(
                    "Applied week does not have one captured schedule timezone"
                )
            timestamp = now_utc or datetime.now(timezone.utc)
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise PublicationSafetyError("Current timestamp must be timezone-aware")
            return timestamp.astimezone(ZoneInfo(schedule_timezones.pop())).date()

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
        authoritative_workout: AuthoritativeWorkout | None,
        provider_name: str | None,
    ) -> None:
        self.retirement_service.verify(
            local_workout_id,
            restore_local=restore_local,
            authoritative_workout=authoritative_workout,
            provider_name=provider_name,
        )

    def _status_authoritative_week(
        self,
        week_number: int,
        *,
        as_of_date: date,
        workouts: list[AuthoritativeWorkout],
        restore_local: bool = False,
        confirmed_remote_targets: dict[str, tuple[int, str]] | None = None,
    ) -> RunWeekSynchronizationReport:
        deletion_authorities, deletion_provider_names = (
            retained_pending_publication_authorities(self.repo, workouts)
        )
        return build_run_week_status(
            self.repo,
            self.client,
            retirement_service=self.retirement_service,
            week_number=week_number,
            as_of_date=as_of_date,
            workouts=workouts,
            restore_local=restore_local,
            verify_workout=lambda workout, provider_name: self._verify_one(
                workout,
                restore_local=(
                    restore_local
                    and confirmed_remote_targets is not None
                    and workout.identity.local_workout_id in confirmed_remote_targets
                ),
                provider_name=provider_name,
            ),
            verify_deletion=lambda local_workout_id, workout, provider_name: (
                self._verify_owned_future_deletion(
                    local_workout_id,
                    restore_local=(
                        restore_local
                        and confirmed_remote_targets is not None
                        and local_workout_id in confirmed_remote_targets
                    ),
                    authoritative_workout=workout,
                    provider_name=provider_name,
                )
            ),
            deletion_authorities_by_local_workout_id=deletion_authorities,
            deletion_provider_names_by_local_workout_id=(
                deletion_provider_names
            ),
        )

    def status_week(
        self,
        week_number: int,
        *,
        as_of_date: date,
    ) -> RunWeekSynchronizationReport:
        with coordinated_publication_plan_activity_lock(
            self.repo,
            "status_run_week_synchronization",
        ):
            workouts = self._load_authoritative_week_unlocked(week_number)
            return self._with_remote_pairing_status(
                self._status_authoritative_week(
                    week_number,
                    as_of_date=as_of_date,
                    workouts=workouts,
                ),
                workouts=workouts,
                mutate=False,
            )

    def reconcile_week(
        self,
        week_number: int,
        *,
        as_of_date: date,
    ) -> RunWeekSynchronizationReport:
        with coordinated_publication_plan_activity_lock(
            self.repo,
            "reconcile_run_week",
        ):
            workouts = self._load_authoritative_week_unlocked(week_number)
            status = self._with_remote_pairing_status(
                self._status_authoritative_week(
                    week_number,
                    as_of_date=as_of_date,
                    workouts=workouts,
                ),
                workouts=workouts,
                mutate=False,
            )
            if not status.reconciliation_safe:
                return status.model_copy(update={"operation": "reconcile"})
            report = self._reconcile_status(
                status,
                workouts=workouts,
                as_of_date=as_of_date,
                restore_local=False,
            )
            if report.partial:
                return report
            return self._with_remote_pairing_status(
                report,
                workouts=workouts,
                mutate=True,
            )

    def restore_local_week(
        self,
        week_number: int,
        *,
        as_of_date: date,
        athlete_confirmation_reference: str,
        confirmed_drift_target_tokens: list[str],
    ) -> RunWeekSynchronizationReport:
        """Replace exact owned drift only after explicit athlete confirmation."""
        confirmation = athlete_confirmation_reference.strip()
        if not confirmation:
            raise PublicationSafetyError(
                "Restore-local drift resolution requires athlete confirmation evidence"
            )
        with coordinated_publication_plan_activity_lock(
            self.repo,
            "restore_local_run_week",
        ):
            workouts = self._load_authoritative_week_unlocked(week_number)
            ordinary_status = self._status_authoritative_week(
                week_number,
                as_of_date=as_of_date,
                workouts=workouts,
            )
            error_types = {
                item.error_type for item in ordinary_status.items if item.status == "error"
            }
            if not error_types:
                raise PublicationSafetyError(
                    "Restore-local requested, but there is no owned remote drift"
                )
            if error_types != {"remote_drift"}:
                return ordinary_status.model_copy(update={"operation": "restore_local"})
            identity = workouts[0].identity
            manifest = load_manifest(self.repo)
            provider_names = provider_workout_names([item.prescription for item in workouts])
            workouts_by_id = {item.identity.local_workout_id: item for item in workouts}
            drift_items = [
                item
                for item in ordinary_status.items
                if item.status == "error" and item.error_type == "remote_drift"
            ]
            confirmed_targets = confirm_publication_drift_targets(
                self.retirement_service,
                drift_items=drift_items,
                authoritative_workouts_by_local_id=workouts_by_id,
                provider_names_by_local_workout_id=provider_names,
                supplied_confirmation_tokens=confirmed_drift_target_tokens,
            )
            manifest.drift_resolutions.append(
                PublicationDriftResolution(
                    plan_id=identity.plan_id,
                    plan_revision_id=identity.plan_revision_id,
                    week_number=week_number,
                    strategy="restore_local",
                    confirmed_targets=confirmed_targets,
                    athlete_confirmation_reference=confirmation,
                    confirmed_at_utc=datetime.now(timezone.utc),
                )
            )
            save_manifest(self.repo, manifest)
            confirmed_remote_targets = {
                target.local_workout_id: (
                    target.event_id,
                    target.observed_remote_fingerprint_sha256,
                )
                for target in confirmed_targets
            }
            status = self._status_authoritative_week(
                week_number,
                as_of_date=as_of_date,
                workouts=workouts,
                restore_local=True,
                confirmed_remote_targets=confirmed_remote_targets,
            )
            if not status.reconciliation_safe:
                return status
            report = self._reconcile_status(
                status,
                workouts=workouts,
                as_of_date=as_of_date,
                restore_local=True,
                confirmed_remote_targets=confirmed_remote_targets,
            )
            if report.partial:
                return report
            return self._with_remote_pairing_status(
                report,
                workouts=workouts,
                mutate=True,
            )

    def resolve_pairing_drift_week(
        self,
        week_number: int,
        *,
        as_of_date: date,
        athlete_confirmation_reference: str,
        confirmed_pairing_drift_tokens: list[str],
    ) -> RunWeekSynchronizationReport:
        """Restore exact removed native pairs after athlete confirmation."""
        confirmation = athlete_confirmation_reference.strip()
        if not confirmation:
            raise PublicationSafetyError(
                "Pairing drift resolution requires athlete confirmation"
            )
        with coordinated_publication_plan_activity_lock(
            self.repo,
            "resolve_run_week_pairing_drift",
        ):
            workouts = self._load_authoritative_week_unlocked(week_number)
            publication_status = self._status_authoritative_week(
                week_number,
                as_of_date=as_of_date,
                workouts=workouts,
            )
            if not publication_status.reconciliation_safe:
                return publication_status.model_copy(
                    update={"operation": "resolve_pairing_drift"}
                )
            pairing_status = self._with_remote_pairing_status(
                publication_status,
                workouts=workouts,
                mutate=False,
            )
            drift_items = [
                item
                for item in pairing_status.items
                if item.pairing_drift_token_sha256 is not None
            ]
            observed_tokens = {
                item.pairing_drift_token_sha256 for item in drift_items
            }
            supplied_tokens = set(confirmed_pairing_drift_tokens)
            if len(supplied_tokens) != len(confirmed_pairing_drift_tokens):
                raise PublicationSafetyError(
                    "Pairing drift confirmation tokens must be unique"
                )
            confirmed_retry_tokens = confirmed_pairing_drift_retry_tokens(
                self.repo,
                pairing_status,
                supplied_tokens,
            )
            if not observed_tokens and not confirmed_retry_tokens:
                raise PublicationSafetyError(
                    "There is no Resilio-authored native pairing drift to resolve"
                )
            if observed_tokens | confirmed_retry_tokens != supplied_tokens:
                raise PublicationSafetyError(
                    "Pairing drift confirmations must match the exact displayed token set"
                )
            if any(item.remote_pairing_operation_id is None for item in drift_items):
                raise PublicationSafetyError("Pairing drift lacks its durable operation identity")
            if drift_items:
                self.pairing_service.confirm_pairing_drifts(
                    [
                        (
                            item.remote_pairing_operation_id,
                            item.pairing_drift_token_sha256,
                            confirmation,
                        )
                        for item in drift_items
                        if item.remote_pairing_operation_id is not None
                        and item.pairing_drift_token_sha256 is not None
                    ]
                )
            report = self._reconcile_status(
                publication_status,
                workouts=workouts,
                as_of_date=as_of_date,
                restore_local=False,
            )
            if not report.partial:
                report = self._with_remote_pairing_status(
                    report,
                    workouts=workouts,
                    mutate=True,
                )
            return report.model_copy(update={"operation": "resolve_pairing_drift"})

    def _reconcile_status(
        self,
        status: RunWeekSynchronizationReport,
        *,
        workouts: list[AuthoritativeWorkout],
        as_of_date: date,
        restore_local: bool,
        confirmed_remote_targets: dict[str, tuple[int, str]] | None = None,
    ) -> RunWeekSynchronizationReport:
        selected, skipped, _, _ = select_run_week_items(
            self.repo,
            workouts=workouts,
            as_of_date=as_of_date,
        )
        provider_names = provider_workout_names([item.prescription for item in workouts])
        deletion_authorities, deletion_provider_names = (
            retained_pending_publication_authorities(self.repo, workouts)
        )
        items = list(skipped)
        partial = False
        for workout in selected:
            expected_remote_target = (
                confirmed_remote_targets.get(workout.identity.local_workout_id)
                if confirmed_remote_targets is not None
                else None
            )
            try:
                result = self.workout_service._publish(
                    workout,
                    restore_local=restore_local and expected_remote_target is not None,
                    provider_name=provider_names[workout.identity.local_workout_id],
                    expected_remote_target=expected_remote_target,
                )
            except Exception as exc:
                partial = True
                items.append(
                    WeekSynchronizationItem(
                        local_workout_id=workout.identity.local_workout_id,
                        occurrence_date=workout.prescription.date,
                        status="error",
                        error_type=publication_error_type(exc),
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
            deletion_items, deletion_partial = reconcile_owned_future_deletions(
                repo=self.repo,
                retirement_service=self.retirement_service,
                local_workout_ids=status.owned_future_deletion_ids,
                authoritative_workouts_by_local_id=deletion_authorities,
                provider_names_by_local_workout_id=deletion_provider_names,
                as_of_date=as_of_date,
                restore_local=restore_local,
                confirmed_remote_targets=confirmed_remote_targets,
                error_type_for=publication_error_type,
            )
            items.extend(deletion_items)
            partial = deletion_partial
        return status.model_copy(
            update={
                "operation": "restore_local" if restore_local else "reconcile",
                "partial": partial,
                "items": items,
            }
        )
