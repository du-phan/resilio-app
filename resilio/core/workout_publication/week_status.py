"""Read-only status projection for one authoritative running week."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.capabilities import (
    get_run_synchronization_capabilities,
)
from resilio.core.workout_publication.drift_confirmation import (
    observe_publication_drift_target,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.naming import provider_workout_names
from resilio.core.workout_publication.policy import (
    ProviderSemanticsMismatchError,
    PublicationSafetyError,
    RemoteWorkoutDriftError,
)
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthorities,
)
from resilio.core.workout_publication.retirement_service import (
    RetirementVerification,
    WorkoutRetirementService,
)
from resilio.core.workout_publication.week_selection import (
    select_run_week_items,
    stale_owned_run_candidates,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import IntervalsIcuError
from resilio.schemas.publication import (
    RunWeekSynchronizationReport,
    WeekSynchronizationItem,
)

VerifyWorkout = Callable[[AuthoritativeWorkout, str], date]
VerifyDeletion = Callable[
    [str, RetainedPublicationAuthorities | None],
    RetirementVerification,
]


def publication_error_type(exc: Exception) -> str:
    """Map internal publication failures to the stable public error taxonomy."""
    if isinstance(exc, ProviderSemanticsMismatchError):
        return "provider_semantics_mismatch"
    if isinstance(exc, RemoteWorkoutDriftError):
        return "remote_drift"
    if isinstance(exc, PublicationSafetyError):
        return "publication_safety"
    if isinstance(exc, IntervalsIcuError):
        return exc.error_type
    return "publication"


def _verified_workout_items(
    *,
    selected: list[AuthoritativeWorkout],
    provider_names_by_local_workout_id: dict[str, str],
    retirement_service: WorkoutRetirementService,
    verify_workout: VerifyWorkout,
    garmin_forwarding_eligible: bool,
    provider_occurrence_dates_by_local_workout_id: dict[str, date],
) -> tuple[list[WeekSynchronizationItem], bool]:
    items: list[WeekSynchronizationItem] = []
    passed = True
    for workout in selected:
        provider_name = provider_names_by_local_workout_id[workout.identity.local_workout_id]
        try:
            provider_occurrence_date = verify_workout(workout, provider_name)
        except Exception as exc:
            passed = False
            drift_token = (
                observe_publication_drift_target(
                    retirement_service,
                    local_workout_id=workout.identity.local_workout_id,
                    authoritative_workout=workout,
                ).confirmation_token_sha256
                if isinstance(exc, RemoteWorkoutDriftError)
                else None
            )
            items.append(
                WeekSynchronizationItem(
                    local_workout_id=workout.identity.local_workout_id,
                    occurrence_date=workout.prescription.date,
                    provider_occurrence_date=provider_occurrence_dates_by_local_workout_id[
                        workout.identity.local_workout_id
                    ],
                    status="error",
                    error_type=publication_error_type(exc),
                    message=str(exc),
                    drift_resolution_token_sha256=drift_token,
                )
            )
        else:
            items.append(
                WeekSynchronizationItem(
                    local_workout_id=workout.identity.local_workout_id,
                    occurrence_date=workout.prescription.date,
                    provider_occurrence_date=provider_occurrence_date,
                    status="ready",
                    garmin_forwarding_status=(
                        "eligible_unverified" if garmin_forwarding_eligible else "not_configured"
                    ),
                )
            )
    return items, passed


def _verified_deletion_items(
    repo: RepositoryIO,
    *,
    local_workout_ids: list[str],
    retained_authorities_by_local_id: dict[str, RetainedPublicationAuthorities],
    retirement_service: WorkoutRetirementService,
    verify_deletion: VerifyDeletion,
    as_of_date: date,
) -> tuple[list[WeekSynchronizationItem], list[str], bool]:
    items: list[WeekSynchronizationItem] = []
    verified_candidate_ids: list[str] = []
    passed = True
    for local_workout_id in local_workout_ids:
        retained_authorities = retained_authorities_by_local_id.get(local_workout_id)
        try:
            verification = verify_deletion(
                local_workout_id,
                retained_authorities,
            )
        except Exception as exc:
            passed = False
            manifest = load_manifest(repo)
            record = manifest.workouts.get(local_workout_id)
            pending = manifest.pending.get(local_workout_id)
            occurrence_date = (
                record.occurrence_date
                if record is not None
                else pending.occurrence_date
                if pending is not None
                else as_of_date
            )
            preferred_authority = (
                retained_authorities.preferred() if retained_authorities is not None else None
            )
            drift_token = (
                observe_publication_drift_target(
                    retirement_service,
                    local_workout_id=local_workout_id,
                    authoritative_workout=preferred_authority.workout,
                ).confirmation_token_sha256
                if isinstance(exc, RemoteWorkoutDriftError) and preferred_authority is not None
                else None
            )
            items.append(
                WeekSynchronizationItem(
                    local_workout_id=local_workout_id,
                    occurrence_date=occurrence_date,
                    status="error",
                    error_type=publication_error_type(exc),
                    message=str(exc),
                    drift_resolution_token_sha256=drift_token,
                )
            )
        else:
            verified_candidate_ids.append(local_workout_id)
            if verification.retirement_required:
                continue
            manifest = load_manifest(repo)
            record = manifest.workouts.get(local_workout_id)
            pending = manifest.pending.get(local_workout_id)
            items.append(
                WeekSynchronizationItem(
                    local_workout_id=local_workout_id,
                    occurrence_date=(
                        record.occurrence_date
                        if record is not None
                        else pending.occurrence_date
                        if pending is not None
                        else as_of_date
                    ),
                    provider_occurrence_date=(verification.provider_occurrence_date),
                    status="skipped_past",
                )
            )
    return items, verified_candidate_ids, passed


def build_run_week_status(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    *,
    retirement_service: WorkoutRetirementService,
    week_number: int,
    as_of_date: date,
    workouts: list[AuthoritativeWorkout],
    restore_local: bool,
    verify_workout: VerifyWorkout,
    verify_deletion: VerifyDeletion,
    deletion_authorities_by_local_workout_id: dict[
        str,
        RetainedPublicationAuthorities,
    ],
    provider_occurrence_dates_by_local_workout_id: dict[str, date],
) -> RunWeekSynchronizationReport:
    """Project verification results without changing local or provider state."""
    capabilities = get_run_synchronization_capabilities(client)
    selected, skipped, current_run_ids, week_identity = select_run_week_items(
        repo,
        workouts=workouts,
        as_of_date=as_of_date,
    )
    stale_ids = stale_owned_run_candidates(
        repo,
        week_identity=week_identity,
        current_run_ids=current_run_ids,
    )
    provider_names = provider_workout_names([item.prescription for item in workouts])
    workout_items, workouts_passed = _verified_workout_items(
        selected=selected,
        provider_names_by_local_workout_id=provider_names,
        retirement_service=retirement_service,
        verify_workout=verify_workout,
        garmin_forwarding_eligible=capabilities.garmin_forwarding_eligible,
        provider_occurrence_dates_by_local_workout_id=(
            provider_occurrence_dates_by_local_workout_id
        ),
    )
    deletion_items, deletion_candidate_ids, deletions_passed = _verified_deletion_items(
        repo,
        local_workout_ids=stale_ids,
        retained_authorities_by_local_id=(deletion_authorities_by_local_workout_id),
        retirement_service=retirement_service,
        verify_deletion=verify_deletion,
        as_of_date=as_of_date,
    )
    return RunWeekSynchronizationReport(
        week_number=week_number,
        as_of_date=as_of_date,
        operation="restore_local" if restore_local else "status",
        reconciliation_safe=workouts_passed and deletions_passed,
        run_workouts_considered=len(selected) + len(skipped),
        run_workouts_requiring_reconciliation=len(selected),
        partial=not workouts_passed or not deletions_passed,
        capabilities=capabilities,
        items=[*skipped, *workout_items, *deletion_items],
        owned_deletion_candidate_ids=deletion_candidate_ids,
    )
