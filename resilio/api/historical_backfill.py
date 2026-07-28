"""Callable surface for the one-time historical activity backfill."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

from resilio.core.config import ConfigError, load_config, load_settings
from resilio.core.historical_activity_backfill import (
    HistoricalActivityBackfillError,
    HistoricalActivityBackfillService,
)
from resilio.core.historical_activity_backfill.repository import (
    HistoricalBackfillRepositoryError,
)
from resilio.core.locking import OperationLockError
from resilio.core.repository import RepositoryIO
from resilio.integrations.intervals_icu import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import IntervalsIcuError
from resilio.schemas.config import Config
from resilio.schemas.historical_backfill import ApprovalStage


@dataclass
class BackfillOperationError:
    error_type: str
    message: str
    retry_after: Optional[int] = None


def _repo(repo_root: Optional[Path]) -> RepositoryIO:
    repo = RepositoryIO()
    if repo_root is not None:
        repo.repo_root = repo_root.resolve()
    return repo


def _offline_config(repo: RepositoryIO) -> Config | BackfillOperationError:
    settings = load_settings(repo.repo_root)
    if isinstance(settings, ConfigError):
        return BackfillOperationError(
            error_type=settings.error_type.value,
            message=settings.message,
        )
    return Config(
        settings=settings,
        intervals_icu_api_key="offline-operation",
        loaded_at=datetime.now(timezone.utc),
    )


def _error(exc: Exception) -> BackfillOperationError:
    if isinstance(exc, IntervalsIcuError):
        return BackfillOperationError(
            error_type=exc.error_type,
            message=str(exc),
            retry_after=exc.retry_after_seconds,
        )
    if isinstance(exc, OperationLockError):
        return BackfillOperationError(error_type="lock", message=str(exc))
    return BackfillOperationError(error_type="backfill_safety", message=str(exc))


def dry_run_historical_backfill(
    *,
    as_of_date: Optional[date] = None,
    downloads_disabled_confirmed: bool = False,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
    repo_root: Optional[Path] = None,
):
    repo = _repo(repo_root)
    config = load_config(repo.repo_root, environment=environment)
    if isinstance(config, ConfigError):
        return BackfillOperationError(
            error_type=config.error_type.value,
            message=config.message,
        )
    owned_client = client is None
    integration = client or IntervalsIcuClient(config)
    try:
        return HistoricalActivityBackfillService(repo, config, integration).dry_run(
            today=as_of_date or date.today(),
            downloads_disabled_confirmed=downloads_disabled_confirmed,
        )
    except Exception as exc:
        return _error(exc)
    finally:
        if owned_client:
            integration.close()


def record_historical_backfill_approval(
    *,
    stage: ApprovalStage,
    plan_digest_sha256: str,
    canary_digest_sha256: Optional[str] = None,
    repo_root: Optional[Path] = None,
):
    repo = _repo(repo_root)
    config = _offline_config(repo)
    if isinstance(config, BackfillOperationError):
        return config
    try:
        return HistoricalActivityBackfillService(
            repo,
            config,
            None,
        ).record_approval(
            stage=stage,
            plan_digest_sha256=plan_digest_sha256,
            canary_digest_sha256=canary_digest_sha256,
        )
    except Exception as exc:
        return _error(exc)


def historical_backfill_status(*, repo_root: Optional[Path] = None):
    repo = _repo(repo_root)
    config = _offline_config(repo)
    if isinstance(config, BackfillOperationError):
        return config
    try:
        return HistoricalActivityBackfillService(repo, config, None).status()
    except Exception as exc:
        return _error(exc)


def mutate_historical_backfill(
    *,
    operation: str,
    plan_digest_sha256: str,
    canary_digest_sha256: Optional[str] = None,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
    repo_root: Optional[Path] = None,
):
    repo = _repo(repo_root)
    config = load_config(repo.repo_root, environment=environment)
    if isinstance(config, ConfigError):
        return BackfillOperationError(
            error_type=config.error_type.value,
            message=config.message,
        )
    owned_client = client is None
    integration = client or IntervalsIcuClient(config)
    service = HistoricalActivityBackfillService(repo, config, integration)
    try:
        if operation == "canary":
            return service.canary(plan_digest_sha256=plan_digest_sha256)
        if canary_digest_sha256 is None:
            raise HistoricalActivityBackfillError(
                f"{operation} requires the exact approved canary digest"
            )
        if operation == "apply":
            return service.apply(
                plan_digest_sha256=plan_digest_sha256,
                canary_digest_sha256=canary_digest_sha256,
            )
        if operation == "resume":
            return service.resume(
                plan_digest_sha256=plan_digest_sha256,
                canary_digest_sha256=canary_digest_sha256,
            )
        if operation == "rollback":
            return service.rollback(
                plan_digest_sha256=plan_digest_sha256,
                canary_digest_sha256=canary_digest_sha256,
            )
        raise ValueError(f"Unsupported historical backfill operation: {operation}")
    except (
        HistoricalActivityBackfillError,
        HistoricalBackfillRepositoryError,
        IntervalsIcuError,
        OperationLockError,
        OSError,
        ValueError,
    ) as exc:
        return _error(exc)
    finally:
        if owned_client:
            integration.close()
