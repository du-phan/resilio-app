"""Narrow planned-workout publication API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Optional, Union

from resilio.core.config import ConfigError, load_config
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.service import (
    PublicationSafetyError,
    WorkoutPublicationService,
)
from resilio.integrations.intervals_icu import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import IntervalsIcuError
from resilio.schemas.publication import (
    PlanPublicationReport,
    PublicationResult,
)


@dataclass
class PublicationError:
    error_type: str
    message: str


def publish_workout(
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
        return WorkoutPublicationService(repo, integration).publish(workout_id)
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
        return WorkoutPublicationService(repo, integration).publish_plan(
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
