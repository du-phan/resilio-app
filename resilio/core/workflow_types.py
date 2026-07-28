"""Shared application-service errors and result contracts."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from resilio.schemas.metrics import DailyMetrics


class WorkflowError(Exception):
    pass


class WorkflowLockError(WorkflowError):
    pass


class WorkflowRollbackError(WorkflowError):
    pass


class WorkflowValidationError(WorkflowError):
    pass


@dataclass
class WorkflowResult:
    success: bool
    warnings: list[str] = field(default_factory=list)
    partial_failure: bool = False


@dataclass
class MetricsRefreshResult(WorkflowResult):
    metrics: Optional[DailyMetrics] = None
    date_refreshed: Optional[date] = None


@dataclass
class PlanGenerationResult(WorkflowResult):
    plan: Optional[Any] = None
    archived_plan_path: Optional[str] = None


@dataclass
class AdaptationCheckResult(WorkflowResult):
    workout: Optional[Any] = None
    triggers: list[Any] = field(default_factory=list)
    risk_assessment: Optional[Any] = None
    auto_applied_overrides: list[str] = field(default_factory=list)
