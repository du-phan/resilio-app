"""Presentation-neutral desired-state synchronization for running workouts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal, Mapping, Optional

from resilio.core.config import ConfigError, load_config
from resilio.core.locking import OperationLockError
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.remote_unpairing import (
    reconcile_actionable_unpair_operations,
)
from resilio.core.workout_publication.capabilities import (
    get_run_synchronization_capabilities,
)
from resilio.core.workout_publication.locking import (
    coordinated_publication_plan_activity_lock,
)
from resilio.core.workout_publication.policy import (
    ProviderSemanticsMismatchError,
    PublicationSafetyError,
)
from resilio.core.workout_publication.preferences import (
    load_run_synchronization_preferences,
    save_run_synchronization_preferences,
)
from resilio.core.workout_publication.week_service import (
    RunWeekSynchronizationService,
)
from resilio.integrations.intervals_icu import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import IntervalsIcuError
from resilio.schemas.publication import (
    RunSynchronizationCapabilities,
    RunWeekSynchronizationReport,
    RunWorkoutSynchronizationPreferences,
)
from resilio.schemas.workout_pairing import RemotePairingOperationsReport


@dataclass(frozen=True)
class PublicationError:
    error_type: str
    message: str


def get_run_workout_synchronization_preferences() -> (
    RunWorkoutSynchronizationPreferences | PublicationError
):
    try:
        return load_run_synchronization_preferences(RepositoryIO())
    except (ValueError, OSError) as exc:
        return PublicationError("synchronization_preferences", str(exc))


def configure_run_workout_synchronization(
    *,
    run_synchronization_mode: Literal["disabled", "after_weekly_apply"],
    athlete_confirmation_reference: Optional[str] = None,
) -> RunWorkoutSynchronizationPreferences | PublicationError:
    try:
        preferences = RunWorkoutSynchronizationPreferences(
            run_synchronization_mode=run_synchronization_mode,
            athlete_confirmation_reference=(
                athlete_confirmation_reference
                if run_synchronization_mode == "after_weekly_apply"
                else None
            ),
            confirmed_at_utc=(
                datetime.now(timezone.utc)
                if run_synchronization_mode == "after_weekly_apply"
                else None
            ),
        )
        save_run_synchronization_preferences(RepositoryIO(), preferences)
        return preferences
    except (ValueError, OSError) as exc:
        return PublicationError("synchronization_preferences", str(exc))


def get_run_workout_synchronization_capabilities(
    *,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
) -> RunSynchronizationCapabilities | PublicationError:
    result = _with_intervals_client(environment=environment, client=client)
    if isinstance(result, PublicationError):
        return result
    integration, owned_client = result
    try:
        return get_run_synchronization_capabilities(integration)
    except ProviderSemanticsMismatchError as exc:
        return PublicationError("provider_semantics_mismatch", str(exc))
    except PublicationSafetyError as exc:
        return PublicationError("publication_safety", str(exc))
    except IntervalsIcuError as exc:
        return PublicationError(exc.error_type, str(exc))
    except Exception as exc:
        return PublicationError("publication", str(exc))
    finally:
        if owned_client:
            integration.close()


def get_week_run_workout_sync_status(
    week_number: int,
    *,
    as_of_date: Optional[date] = None,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
) -> RunWeekSynchronizationReport | PublicationError:
    return _run_week_sync_operation(
        week_number,
        operation="status",
        as_of_date=as_of_date,
        environment=environment,
        client=client,
    )


def reconcile_week_run_workouts(
    week_number: int,
    *,
    as_of_date: Optional[date] = None,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
) -> RunWeekSynchronizationReport | PublicationError:
    return _run_week_sync_operation(
        week_number,
        operation="reconcile",
        as_of_date=as_of_date,
        environment=environment,
        client=client,
    )


def restore_local_week_run_workouts(
    week_number: int,
    *,
    athlete_confirmation_reference: str,
    confirmed_drift_target_tokens: list[str],
    as_of_date: Optional[date] = None,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
) -> RunWeekSynchronizationReport | PublicationError:
    return _run_week_sync_operation(
        week_number,
        operation="restore_local",
        as_of_date=as_of_date,
        environment=environment,
        client=client,
        athlete_confirmation_reference=athlete_confirmation_reference,
        confirmed_drift_target_tokens=confirmed_drift_target_tokens,
    )


def resolve_week_run_workout_pairing_drift(
    week_number: int,
    *,
    athlete_confirmation_reference: str,
    confirmed_pairing_drift_tokens: list[str],
    as_of_date: Optional[date] = None,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
) -> RunWeekSynchronizationReport | PublicationError:
    return _run_week_sync_operation(
        week_number,
        operation="resolve_pairing_drift",
        as_of_date=as_of_date,
        environment=environment,
        client=client,
        athlete_confirmation_reference=athlete_confirmation_reference,
        confirmed_pairing_drift_tokens=confirmed_pairing_drift_tokens,
    )


def _run_week_sync_operation(
    week_number: int,
    *,
    operation: Literal[
        "status",
        "reconcile",
        "restore_local",
        "resolve_pairing_drift",
    ],
    as_of_date: Optional[date],
    environment: Optional[Mapping[str, str]],
    client: Optional[IntervalsIcuClient],
    athlete_confirmation_reference: Optional[str] = None,
    confirmed_drift_target_tokens: list[str] | None = None,
    confirmed_pairing_drift_tokens: list[str] | None = None,
) -> RunWeekSynchronizationReport | PublicationError:
    result = _with_intervals_client(environment=environment, client=client)
    if isinstance(result, PublicationError):
        return result
    integration, owned_client = result
    try:
        service = RunWeekSynchronizationService(RepositoryIO(), integration)
        resolved_date = _resolved_as_of_date(
            service,
            week_number=week_number,
            supplied_date=as_of_date,
            operation=operation,
        )
        if operation == "status":
            return service.status_week(week_number, as_of_date=resolved_date)
        if operation == "restore_local":
            return service.restore_local_week(
                week_number,
                as_of_date=resolved_date,
                athlete_confirmation_reference=athlete_confirmation_reference or "",
                confirmed_drift_target_tokens=confirmed_drift_target_tokens or [],
            )
        if operation == "resolve_pairing_drift":
            return service.resolve_pairing_drift_week(
                week_number,
                as_of_date=resolved_date,
                athlete_confirmation_reference=athlete_confirmation_reference or "",
                confirmed_pairing_drift_tokens=confirmed_pairing_drift_tokens or [],
            )
        return service.reconcile_week(week_number, as_of_date=resolved_date)
    except ProviderSemanticsMismatchError as exc:
        return PublicationError("provider_semantics_mismatch", str(exc))
    except PublicationSafetyError as exc:
        return PublicationError("publication_safety", str(exc))
    except IntervalsIcuError as exc:
        return PublicationError(exc.error_type, str(exc))
    except Exception as exc:
        return PublicationError("publication", str(exc))
    finally:
        if owned_client:
            integration.close()


def _with_intervals_client(
    *,
    environment: Optional[Mapping[str, str]],
    client: Optional[IntervalsIcuClient],
) -> tuple[IntervalsIcuClient, bool] | PublicationError:
    if client is not None:
        return client, False
    repo = RepositoryIO()
    config = load_config(repo.repo_root, environment=environment)
    if isinstance(config, ConfigError):
        return PublicationError(config.error_type.value, config.message)
    return IntervalsIcuClient(config), True


def _resolved_as_of_date(
    service: RunWeekSynchronizationService,
    *,
    week_number: int,
    supplied_date: Optional[date],
    operation: Literal[
        "status",
        "reconcile",
        "restore_local",
        "resolve_pairing_drift",
    ],
) -> date:
    current_schedule_date = service.current_schedule_date(week_number)
    if operation == "status" and supplied_date is not None:
        return supplied_date
    if supplied_date is not None and supplied_date != current_schedule_date:
        raise PublicationSafetyError(
            "Live calendar mutation requires today's date in the applied week's "
            "captured schedule timezone"
        )
    return current_schedule_date


def reconcile_remote_workout_pairing_operations(
    *,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
) -> RemotePairingOperationsReport | PublicationError:
    """Drain durable unpair obligations without requiring an active plan week."""
    resolved_client = _with_intervals_client(environment=environment, client=client)
    if isinstance(resolved_client, PublicationError):
        return resolved_client
    integration, owned_client = resolved_client
    repo = RepositoryIO()
    try:
        with coordinated_publication_plan_activity_lock(
            repo,
            "reconcile_remote_workout_pairing_operations",
        ):
            return reconcile_actionable_unpair_operations(repo, integration)
    except (IntervalsIcuError, OperationLockError, OSError, ValueError) as exc:
        return PublicationError("remote_pairing_reconciliation", str(exc))
    finally:
        if owned_client:
            integration.close()
