"""Training-plan adaptation checks."""

from __future__ import annotations

from datetime import date
from typing import Optional

from resilio.core.paths import current_plan_path, daily_metrics_path
from resilio.core.profile import ProfileService
from resilio.core.repository import RepositoryIO
from resilio.core.workflow_types import AdaptationCheckResult, WorkflowError
from resilio.schemas.metrics import DailyMetrics
from resilio.schemas.plan import MasterPlan
from resilio.schemas.repository import ReadOptions, RepoError


def run_adaptation_check(
    repo: RepositoryIO,
    target_date: Optional[date] = None,
) -> AdaptationCheckResult:
    target = target_date or date.today()
    result = AdaptationCheckResult(success=False)
    try:
        metrics = None
        if repo.file_exists(daily_metrics_path(target)):
            metrics_value = repo.read_yaml(daily_metrics_path(target), DailyMetrics)
            if isinstance(metrics_value, DailyMetrics):
                metrics = metrics_value

        ProfileService(repo).load_profile()
        if not repo.file_exists(current_plan_path()):
            result.success = True
            result.warnings.append("No training plan found")
            return result

        plan = repo.read_yaml(
            current_plan_path(),
            MasterPlan,
            ReadOptions(should_validate=True),
        )
        if isinstance(plan, RepoError):
            result.success = True
            result.warnings.append(f"Failed to load plan: {plan}")
            return result

        workout = next(
            (
                workout
                for week in plan.weeks
                for workout in week.workouts
                if workout.date == target
            ),
            None,
        )
        if workout is None:
            result.success = True
            result.warnings.append(f"No workout scheduled for {target}")
            return result
        result.workout = workout

        triggers: list[dict] = []
        if metrics is not None:
            if metrics.acwr and metrics.acwr.acwr > 1.5:
                triggers.append(
                    {
                        "type": "acwr_high_risk",
                        "value": metrics.acwr.acwr,
                        "threshold": 1.5,
                        "zone": "danger",
                    }
                )
            if metrics.readiness.score < 35:
                triggers.append(
                    {
                        "type": "readiness_very_low",
                        "value": metrics.readiness.score,
                        "threshold": 35,
                        "zone": "danger",
                    }
                )
        result.triggers = triggers
        acwr_high = any(
            trigger["type"] == "acwr_high_risk" and trigger["value"] > 1.5
            for trigger in triggers
        )
        readiness_low = any(
            trigger["type"] == "readiness_very_low" and trigger["value"] < 35
            for trigger in triggers
        )
        if acwr_high and readiness_low:
            result.auto_applied_overrides.append(
                "SAFETY OVERRIDE: ACWR > 1.5 + readiness < 35 → rest day mandatory"
            )
        result.success = True
        return result
    except Exception as exc:
        raise WorkflowError(f"Adaptation check failed: {exc}") from exc
