"""Macro-plan creation service kept independent of presentation layers."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from resilio.core.paths import current_plan_path, daily_metrics_path, get_plans_dir
from resilio.core.plan import calculate_periodization, suggest_volume_adjustment
from resilio.core.profile import ProfileService
from resilio.core.repository import RepositoryIO
from resilio.core.workflow_types import PlanGenerationResult, WorkflowError
from resilio.schemas.metrics import DailyMetrics
from resilio.schemas.plan import MasterPlan
from resilio.schemas.profile import Goal, GoalType
from resilio.schemas.repository import ReadOptions, RepoError
from resilio.utils.dates import get_next_monday


logger = logging.getLogger(__name__)


def _fallback_phases(start: date, end: date, total_weeks: int) -> list[dict]:
    if total_weeks <= 4:
        return [
            {
                "phase": "base",
                "start_week": 0,
                "end_week": total_weeks - 2,
                "start_date": start,
                "end_date": start + timedelta(weeks=total_weeks - 1, days=-1),
                "weeks": total_weeks - 1,
            },
            {
                "phase": "taper",
                "start_week": total_weeks - 1,
                "end_week": total_weeks - 1,
                "start_date": start + timedelta(weeks=total_weeks - 1),
                "end_date": end,
                "weeks": 1,
            },
        ]

    taper_weeks = max(1, round(total_weeks * 0.15))
    build_weeks = total_weeks - taper_weeks
    base_weeks = max(1, round(build_weeks * 0.4))
    peak_weeks = build_weeks - base_weeks
    return [
        {
            "phase": "base",
            "start_week": 0,
            "end_week": base_weeks - 1,
            "start_date": start,
            "end_date": start + timedelta(weeks=base_weeks, days=-1),
            "weeks": base_weeks,
        },
        {
            "phase": "build",
            "start_week": base_weeks,
            "end_week": base_weeks + peak_weeks - 1,
            "start_date": start + timedelta(weeks=base_weeks),
            "end_date": start + timedelta(weeks=base_weeks + peak_weeks, days=-1),
            "weeks": peak_weeks,
        },
        {
            "phase": "taper",
            "start_week": build_weeks,
            "end_week": total_weeks - 1,
            "start_date": start + timedelta(weeks=build_weeks),
            "end_date": end,
            "weeks": taper_weeks,
        },
    ]


def _current_ctl(repo: RepositoryIO, target: date) -> float:
    result = repo.read_yaml(
        daily_metrics_path(target),
        DailyMetrics,
        ReadOptions(allow_missing=True),
    )
    if isinstance(result, DailyMetrics):
        return float(result.ctl_atl.ctl)
    return 20.0


def run_plan_generation(
    repo: RepositoryIO,
    goal: Optional[Goal] = None,
) -> PlanGenerationResult:
    result = PlanGenerationResult(success=False)
    try:
        profile_service = ProfileService(repo)
        profile = profile_service.load_profile()
        if goal is not None:
            profile.goal = goal
            profile_service.save_profile(profile)

        plan_path = current_plan_path()
        if repo.file_exists(plan_path):
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            archive_path = f"{get_plans_dir()}/archive_plan_{timestamp}.yaml"
            previous = repo.read_yaml(
                plan_path,
                MasterPlan,
                ReadOptions(allow_missing=True, should_validate=True),
            )
            if isinstance(previous, MasterPlan):
                error = repo.write_yaml(archive_path, previous)
                if error is None:
                    result.archived_plan_path = archive_path

        today = date.today()
        if profile.goal and profile.goal.target_date:
            raw_target = profile.goal.target_date
            target = (
                date.fromisoformat(raw_target)
                if isinstance(raw_target, str)
                else raw_target
            )
        else:
            target = today + timedelta(weeks=12)
        start = get_next_monday(today)
        total_weeks = max(1, (target - start).days // 7)

        goal_type = profile.goal.type if profile.goal else GoalType.GENERAL_FITNESS
        try:
            phases = calculate_periodization(
                goal=goal_type,
                weeks_available=total_weeks,
                start_date=start,
            )
        except ValueError:
            phases = _fallback_phases(start, target, total_weeks)

        goal_distance = {
            GoalType.FIVE_K: 5.0,
            GoalType.TEN_K: 10.0,
            GoalType.HALF_MARATHON: 21.1,
            GoalType.MARATHON: 42.2,
            GoalType.GENERAL_FITNESS: 10.0,
        }.get(goal_type, 10.0)
        volume = suggest_volume_adjustment(
            current_weekly_volume_km=0.0,
            current_ctl=_current_ctl(repo, today),
            goal_distance_km=goal_distance,
            weeks_available=total_weeks,
        )
        starting_volume = sum(volume.start_range_km) / 2
        peak_volume = sum(volume.peak_range_km) / 2
        conflict_policy = (
            profile.conflict_policy.value
            if profile.conflict_policy
            else "ask_each_time"
        )
        constraints = profile.constraints
        plan_data = {
            "id": f"plan_{uuid.uuid4().hex[:12]}",
            "created_at": today.isoformat(),
            "goal": (
                profile.goal.model_dump()
                if profile.goal
                else {
                    "type": "general_fitness",
                    "target_date": None,
                    "target_time": None,
                }
            ),
            "start_date": start.isoformat(),
            "end_date": target.isoformat(),
            "total_weeks": total_weeks,
            "phases": phases,
            "weeks": [],
            "starting_volume_km": starting_volume,
            "peak_volume_km": peak_volume,
            "conflict_policy": conflict_policy,
            "constraints_applied": (
                [
                    (
                        "runs_per_week: "
                        f"{constraints.min_run_days_per_week}-"
                        f"{constraints.max_run_days_per_week}"
                    ),
                    (
                        "available_days: "
                        f"{7 - len(constraints.unavailable_run_days)}"
                    ),
                    (
                        "max_session_minutes: "
                        f"{constraints.max_time_per_session_minutes}"
                    ),
                ]
                if constraints
                else []
            ),
        }
        plan = MasterPlan.model_validate(plan_data)
        error = repo.write_yaml(current_plan_path(), plan)
        if error is not None:
            raise WorkflowError(f"Failed to save plan: {error}")
        result.success = True
        result.plan = plan_data
        return result
    except WorkflowError:
        raise
    except Exception as exc:
        raise WorkflowError(f"Plan generation failed: {exc}") from exc
