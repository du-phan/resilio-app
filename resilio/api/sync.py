"""Completed-activity synchronization API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Optional, Union

from resilio.core.activity_sync.service import ActivitySyncService
from resilio.core.config import ConfigError, load_config
from resilio.core.locking import OperationLockError
from resilio.core.metrics_workflow import recompute_all_metrics
from resilio.core.repository import RepositoryIO
from resilio.integrations.intervals_icu import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import IntervalsIcuError
from resilio.schemas.sync import SyncReport


@dataclass
class SyncError:
    error_type: str
    message: str
    retry_after: Optional[int] = None


def sync_activities(
    *,
    full: bool = False,
    confirm_deletions: bool = False,
    as_of_date: Optional[date] = None,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
) -> Union[SyncReport, SyncError]:
    repo = RepositoryIO()
    config = load_config(repo.repo_root, environment=environment)
    if isinstance(config, ConfigError):
        return SyncError(
            error_type=str(config.error_type.value),
            message=config.message,
        )

    owned_client = client is None
    integration = client or IntervalsIcuClient(config)
    try:
        service = ActivitySyncService(
            repo,
            config,
            integration,
            metrics_recompute=recompute_all_metrics,
        )
        return service.run(
            today=as_of_date or date.today(),
            full=full,
            confirm_deletions=confirm_deletions,
        )
    except IntervalsIcuError as exc:
        return SyncError(
            error_type=exc.error_type,
            message=str(exc),
            retry_after=exc.retry_after_seconds,
        )
    except OperationLockError as exc:
        return SyncError(error_type="lock", message=str(exc))
    except Exception as exc:
        return SyncError(
            error_type="sync",
            message=f"Activity sync failed: {exc}",
        )
    finally:
        if owned_client:
            integration.close()
