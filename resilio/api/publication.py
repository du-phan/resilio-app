"""Narrow planned-workout publication API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Mapping, Optional, Union

from resilio.core.config import ConfigError, load_config
from resilio.core.paths import current_plan_path
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.service import (
    PublicationSafetyError,
    WorkoutPublicationService,
)
from resilio.integrations.intervals_icu import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import IntervalsIcuError
from resilio.schemas.plan import MasterPlan, WorkoutPrescription
from resilio.schemas.publication import (
    PlanPublicationReport,
    PublicationResult,
)
from resilio.schemas.repository import RepoError


@dataclass
class PublicationError:
    error_type: str
    message: str


def _load_current_plan(repo: RepositoryIO) -> MasterPlan:
    plan = repo.read_yaml(current_plan_path(), MasterPlan)
    if plan is None:
        raise ValueError("No current training plan is available")
    if isinstance(plan, RepoError):
        raise ValueError(f"Unable to load current plan: {plan}")
    return plan


def _find_workout(repo: RepositoryIO, workout_id: str) -> WorkoutPrescription:
    plan = _load_current_plan(repo)
    for week in plan.weeks:
        for workout in week.workouts:
            if workout.id == workout_id:
                return workout
    raise ValueError(f"Workout not found in current plan: {workout_id}")


def publish_workout(
    workout_id: str,
    *,
    start_time_local: Optional[time] = None,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
) -> Union[PublicationResult, PublicationError]:
    repo = RepositoryIO()
    config = load_config(repo.repo_root, environment=environment)
    if isinstance(config, ConfigError):
        return PublicationError(config.error_type.value, config.message)
    owned_client = client is None
    integration = client or IntervalsIcuClient(config)
    try:
        workout = _find_workout(repo, workout_id)
        return WorkoutPublicationService(repo, integration).publish(
            workout,
            start_time_local=start_time_local,
        )
    except PublicationSafetyError as exc:
        return PublicationError("publication_safety", str(exc))
    except IntervalsIcuError as exc:
        return PublicationError(exc.error_type, str(exc))
    except Exception as exc:
        return PublicationError("publication", str(exc))
    finally:
        if owned_client:
            integration.close()


def publish_plan_workouts(
    *,
    from_date: Optional[date] = None,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
) -> Union[PlanPublicationReport, PublicationError]:
    repo = RepositoryIO()
    config = load_config(repo.repo_root, environment=environment)
    if isinstance(config, ConfigError):
        return PublicationError(config.error_type.value, config.message)
    owned_client = client is None
    integration = client or IntervalsIcuClient(config)
    try:
        plan = _load_current_plan(repo)
        workouts = [
            workout
            for week in plan.weeks
            for workout in week.workouts
        ]
        return WorkoutPublicationService(repo, integration).publish_plan(
            workouts,
            from_date=from_date or date.today(),
        )
    except PublicationSafetyError as exc:
        return PublicationError("publication_safety", str(exc))
    except IntervalsIcuError as exc:
        return PublicationError(exc.error_type, str(exc))
    except Exception as exc:
        return PublicationError("publication", str(exc))
    finally:
        if owned_client:
            integration.close()


def delete_published_workout(
    workout_id: str,
    *,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
) -> Union[PublicationResult, PublicationError]:
    repo = RepositoryIO()
    config = load_config(repo.repo_root, environment=environment)
    if isinstance(config, ConfigError):
        return PublicationError(config.error_type.value, config.message)
    owned_client = client is None
    integration = client or IntervalsIcuClient(config)
    try:
        return WorkoutPublicationService(repo, integration).delete(workout_id)
    except PublicationSafetyError as exc:
        return PublicationError("publication_safety", str(exc))
    except IntervalsIcuError as exc:
        return PublicationError(exc.error_type, str(exc))
    except Exception as exc:
        return PublicationError("publication", str(exc))
    finally:
        if owned_client:
            integration.close()
