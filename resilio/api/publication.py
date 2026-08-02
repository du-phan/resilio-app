"""Presentation-neutral desired-state synchronization for running workouts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal, Mapping, Optional
from zoneinfo import ZoneInfo

from resilio.core.config import ConfigError, load_config
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.capabilities import (
    get_run_synchronization_capabilities,
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
    )


def _run_week_sync_operation(
    week_number: int,
    *,
    operation: Literal["status", "reconcile", "restore_local"],
    as_of_date: Optional[date],
    environment: Optional[Mapping[str, str]],
    client: Optional[IntervalsIcuClient],
    athlete_confirmation_reference: Optional[str] = None,
) -> RunWeekSynchronizationReport | PublicationError:
    result = _with_intervals_client(environment=environment, client=client)
    if isinstance(result, PublicationError):
        return result
    integration, owned_client = result
    try:
        resolved_date = _resolved_as_of_date(integration, as_of_date)
        service = RunWeekSynchronizationService(RepositoryIO(), integration)
        if operation == "status":
            return service.status_week(week_number, as_of_date=resolved_date)
        if operation == "restore_local":
            return service.restore_local_week(
                week_number,
                as_of_date=resolved_date,
                athlete_confirmation_reference=athlete_confirmation_reference or "",
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
    integration: IntervalsIcuClient,
    supplied_date: Optional[date],
) -> date:
    if supplied_date is not None:
        return supplied_date
    capabilities = get_run_synchronization_capabilities(integration)
    return datetime.now(ZoneInfo(capabilities.athlete_timezone)).date()
