"""
Coach API - Daily coaching operations and training status.

Provides functions for Claude Code to get workout recommendations,
weekly status, and overall training status.
"""

from datetime import date, timedelta
from typing import Optional, Union
from dataclasses import dataclass, field

from sports_coach_engine.core.paths import (
    daily_metrics_path,
    athlete_profile_path,
    current_plan_path,
    activities_month_dir,
)
from sports_coach_engine.core.repository import RepositoryIO, ReadOptions
from sports_coach_engine.schemas.repository import RepoError
from sports_coach_engine.core.workflows import run_adaptation_check, WorkflowError
from sports_coach_engine.core.enrichment import enrich_workout, enrich_metrics
from sports_coach_engine.core.logger import log_message, MessageRole
from sports_coach_engine.schemas.enrichment import EnrichedWorkout, EnrichedMetrics
from sports_coach_engine.schemas.metrics import DailyMetrics
from sports_coach_engine.schemas.activity import NormalizedActivity
from sports_coach_engine.schemas.plan import MasterPlan, WorkoutPrescription
from sports_coach_engine.schemas.profile import AthleteProfile


# ============================================================
# ERROR TYPES
# ============================================================


@dataclass
class CoachError:
    """Error result from coach operations."""

    error_type: str  # "not_found", "no_plan", "insufficient_data", "validation", "unknown"
    message: str


# ============================================================
# RESULT TYPES
# ============================================================


@dataclass
class WeeklyStatus:
    """Weekly training status summary."""

    week_start: date
    week_end: date
    planned_workouts: int
    completed_workouts: int
    completion_rate: float  # 0.0-1.0
    total_duration_minutes: int
    total_load_au: float

    # Activities summary
    activities: list[dict] = field(default_factory=list)  # Brief activity summaries

    # Metrics snapshot
    current_ctl: Optional[float] = None
    current_tsb: Optional[float] = None
    current_readiness: Optional[int] = None

    # Week-over-week changes
    ctl_change: Optional[float] = None
    tsb_change: Optional[float] = None

    # Suggestions
    pending_suggestions: int = 0


# ============================================================
# PUBLIC API FUNCTIONS
# ============================================================


def get_todays_workout(
    target_date: Optional[date] = None,
) -> Union[EnrichedWorkout, CoachError]:
    """
    Get today's workout with adaptation checks and enriched context.

    Workflow:
    1. Load current training plan
    2. Get workout for target date (defaults to today)
    3. Call M1 run_adaptation_check() to:
       - Load current metrics (M9)
       - Detect adaptation triggers (M11)
       - Assess override risk (M11)
       - Apply safety overrides if necessary
    4. Enrich workout via M12 for interpretable data
    5. Log operation via M14
    6. Return enriched workout with rationale and context

    Args:
        target_date: Date to get workout for. Defaults to today.

    Returns:
        EnrichedWorkout containing:
        - workout_id: Unique workout identifier
        - date: Workout date
        - workout_type: "tempo", "easy", "long_run", "intervals", etc.
        - workout_type_display: Human-readable type
        - duration_minutes: Planned duration
        - target_rpe: Target perceived exertion
        - intensity_zone: "zone_2", "zone_4", etc.
        - intensity_description: "Easy", "Threshold", etc.
        - pace_guidance: Target pace range with feel description
        - hr_guidance: Target HR range with zone name
        - purpose: Training purpose for this workout
        - rationale: Why this workout today (with current metrics context)
        - current_readiness: Readiness score for today
        - has_pending_suggestion: Whether adaptations are suggested
        - suggestion_summary: Brief summary of suggested changes
        - coach_notes: Additional context or warnings

        CoachError on failure containing error details

    Example:
        >>> workout = get_todays_workout()
        >>> if isinstance(workout, CoachError):
        ...     print(f"No workout available: {workout.message}")
        ... else:
        ...     print(f"{workout.workout_type_display}: {workout.duration_minutes} min")
        ...     print(f"Purpose: {workout.purpose}")
        ...     print(f"Readiness: {workout.current_readiness.value}/100")
        ...     if workout.has_pending_suggestion:
        ...         print(f"Note: {workout.suggestion_summary}")
    """
    repo = RepositoryIO()

    # Default to today
    if target_date is None:
        target_date = date.today()

    # Log user request
    log_message(repo, MessageRole.USER, f"get_todays_workout(date={target_date})")

    # Call M1 adaptation check workflow
    try:
        result = run_adaptation_check(repo, target_date=target_date)
    except WorkflowError as e:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Adaptation check failed: {str(e)}",
        )
        return CoachError(
            error_type="unknown",
            message=f"Failed to check workout: {str(e)}",
        )
    except Exception as e:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Adaptation check failed: {str(e)}",
        )
        return CoachError(
            error_type="unknown",
            message=f"Unexpected error: {str(e)}",
        )

    # Handle workflow failure or missing workout
    if not result.success or result.workout is None:
        error_msg = "; ".join(result.warnings) if result.warnings else "No workout available"
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"No workout for {target_date}: {error_msg}",
        )

        # Check if it's because there's no plan
        if "plan" in error_msg.lower() or "not found" in error_msg.lower():
            return CoachError(
                error_type="no_plan",
                message="No training plan found. Set a goal to generate a plan.",
            )
        else:
            return CoachError(
                error_type="not_found",
                message=f"No workout scheduled for {target_date}",
            )

    # Load metrics and profile for enrichment
    metrics_path = daily_metrics_path(target_date)
    metrics_result = repo.read_yaml(metrics_path, DailyMetrics, ReadOptions(allow_missing=True, should_validate=True))

    if isinstance(metrics_result, RepoError) or metrics_result is None:
        # No metrics available, return workout without enrichment
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"No metrics available for enrichment, returning basic workout",
        )
        return CoachError(
            error_type="insufficient_data",
            message="No metrics available to assess workout suitability",
        )

    metrics = metrics_result

    # Load profile
    profile_path = athlete_profile_path()
    profile_result = repo.read_yaml(profile_path, AthleteProfile, ReadOptions(should_validate=True))

    if isinstance(profile_result, RepoError):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to load profile: {str(profile_result)}",
        )
        return CoachError(
            error_type="validation",
            message=f"Failed to load profile: {str(profile_result)}",
        )

    profile = profile_result

    # Enrich workout via M12
    try:
        enriched = enrich_workout(
            workout=result.workout,
            metrics=metrics,
            profile=profile,
            suggestions=result.triggers,  # Pass triggers as suggestions
        )
    except Exception as e:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to enrich workout: {str(e)}",
        )
        return CoachError(
            error_type="unknown",
            message=f"Failed to enrich workout: {str(e)}",
        )

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Workout for {target_date}: {enriched.workout_type_display}, "
        f"{enriched.duration_minutes}min, RPE {enriched.target_rpe}",
    )

    return enriched


def get_weekly_status() -> Union[WeeklyStatus, CoachError]:
    """
    Get overview of current week's training.

    Workflow:
    1. Determine current week boundaries (Monday-Sunday)
    2. Load current training plan
    3. Count planned workouts for this week
    4. Load completed activities for this week
    5. Calculate completion rate and totals
    6. Load current metrics
    7. Calculate week-over-week changes
    8. Check for pending suggestions
    9. Log operation via M14
    10. Return weekly status

    Returns:
        WeeklyStatus containing:
        - week_start: Monday of current week
        - week_end: Sunday of current week
        - planned_workouts: Count of planned workouts this week
        - completed_workouts: Count of completed workouts
        - completion_rate: Percentage complete (0.0-1.0)
        - total_duration_minutes: Total training time
        - total_load_au: Total systemic load
        - activities: Brief summaries of completed activities
        - current_ctl/tsb/readiness: Current metrics
        - ctl_change/tsb_change: Week-over-week changes
        - pending_suggestions: Count of pending adaptation suggestions

        CoachError on failure containing error details

    Example:
        >>> status = get_weekly_status()
        >>> if isinstance(status, CoachError):
        ...     print(f"Error: {status.message}")
        ... else:
        ...     print(f"Week {status.week_start} to {status.week_end}")
        ...     print(f"Completed: {status.completed_workouts}/{status.planned_workouts} "
        ...           f"({status.completion_rate*100:.0f}%)")
        ...     print(f"Total time: {status.total_duration_minutes} minutes")
        ...     print(f"CTL: {status.current_ctl} (change: {status.ctl_change:+.1f})")
    """
    repo = RepositoryIO()

    # Log user request
    log_message(repo, MessageRole.USER, "get_weekly_status()")

    # Determine current week boundaries (Monday-Sunday)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)  # Sunday

    # Load current plan to count planned workouts
    planned_workouts = 0
    plan_path = current_plan_path()
    plan_result = repo.read_yaml(plan_path, MasterPlan, ReadOptions(allow_missing=True, should_validate=True))

    if isinstance(plan_result, RepoError):
        # Plan load error
        pass  # Continue without plan data
    elif plan_result is not None:
        # Count workouts in current week
        for week in plan_result.weeks:
            if week.week_start <= today <= week.week_end:
                planned_workouts = len([w for w in week.workouts if w is not None])
                break

    # Load activities for current week
    activities = []
    completed_workouts = 0
    total_duration = 0
    total_load = 0.0

    for i in range(7):
        check_date = week_start + timedelta(days=i)
        activity_dir = activities_month_dir(check_date.strftime('%Y-%m'))
        activity_files = repo.list_files(f"{activity_dir}/*.yaml")

        for activity_file in activity_files:
            activity_result = repo.read_yaml(
                activity_file,
                NormalizedActivity,
                ReadOptions(allow_missing=True, should_validate=True),
            )

            if isinstance(activity_result, RepoError) or activity_result is None:
                continue

            activity = activity_result
            if activity.date == check_date:
                completed_workouts += 1
                total_duration += activity.duration_minutes

                # Add load if calculated
                if activity.calculated:
                    total_load += activity.calculated.systemic_load_au
                    systemic_load = activity.calculated.systemic_load_au
                else:
                    systemic_load = 0.0

                activities.append({
                    "date": str(activity.date),
                    "sport_type": activity.sport_type,
                    "duration_minutes": activity.duration_minutes,
                    "systemic_load_au": systemic_load,
                })

    # Calculate completion rate
    completion_rate = 0.0
    if planned_workouts > 0:
        completion_rate = completed_workouts / planned_workouts

    # Load current metrics
    current_ctl = None
    current_tsb = None
    current_readiness = None
    ctl_change = None
    tsb_change = None

    metrics_path = daily_metrics_path(today)
    metrics_result = repo.read_yaml(metrics_path, DailyMetrics, ReadOptions(allow_missing=True, should_validate=True))

    if not isinstance(metrics_result, RepoError) and metrics_result is not None:
        current_ctl = metrics_result.ctl_atl.ctl
        current_tsb = metrics_result.ctl_atl.tsb
        if metrics_result.readiness:
            current_readiness = metrics_result.readiness.score

        # Calculate week-over-week changes
        week_ago_path = daily_metrics_path(today - timedelta(days=7))
        week_ago_result = repo.read_yaml(
            week_ago_path,
            DailyMetrics,
            ReadOptions(allow_missing=True, should_validate=True),
        )

        if not isinstance(week_ago_result, RepoError) and week_ago_result is not None:
            ctl_change = current_ctl - week_ago_result.ctl_atl.ctl
            tsb_change = current_tsb - week_ago_result.ctl_atl.tsb

    # Check for pending suggestions (simplified for v0)
    # Full implementation would query suggestions directory
    pending_suggestions = 0

    status = WeeklyStatus(
        week_start=week_start,
        week_end=week_end,
        planned_workouts=planned_workouts,
        completed_workouts=completed_workouts,
        completion_rate=completion_rate,
        total_duration_minutes=total_duration,
        total_load_au=total_load,
        activities=activities,
        current_ctl=current_ctl,
        current_tsb=current_tsb,
        current_readiness=current_readiness,
        ctl_change=ctl_change,
        tsb_change=tsb_change,
        pending_suggestions=pending_suggestions,
    )

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Weekly status: {completed_workouts}/{planned_workouts} workouts, "
        f"{total_duration} minutes, CTL={current_ctl}",
    )

    return status


def get_training_status() -> Union[EnrichedMetrics, CoachError]:
    """
    Get overall training status with current metrics.

    This is a convenience function that wraps get_current_metrics()
    from the metrics API with coach-specific logging.

    Workflow:
    1. Load most recent DailyMetrics
    2. Enrich via M12
    3. Log operation via M14
    4. Return enriched metrics

    Returns:
        EnrichedMetrics containing full training status

        CoachError on failure

    Example:
        >>> status = get_training_status()
        >>> if isinstance(status, CoachError):
        ...     print(f"Error: {status.message}")
        ... else:
        ...     print(f"Fitness (CTL): {status.ctl.interpretation}")
        ...     print(f"Form (TSB): {status.tsb.interpretation}")
        ...     print(f"Readiness: {status.readiness.formatted_value}/100")
    """
    repo = RepositoryIO()

    # Log user request
    log_message(repo, MessageRole.USER, "get_training_status()")

    # Find most recent metrics
    latest_metrics_date = _find_latest_metrics_date(repo)
    if latest_metrics_date is None:
        log_message(
            repo,
            MessageRole.SYSTEM,
            "No training data available",
        )
        return CoachError(
            error_type="not_found",
            message="No training data available yet. Sync activities to generate metrics.",
        )

    # Load metrics
    metrics_path = daily_metrics_path(latest_metrics_date)
    result = repo.read_yaml(metrics_path, DailyMetrics, ReadOptions(should_validate=True))

    if isinstance(result, RepoError):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to load metrics: {str(result)}",
        )
        return CoachError(
            error_type="validation",
            message=f"Failed to load metrics: {str(result)}",
        )

    daily_metrics = result

    # Enrich metrics via M12
    try:
        enriched = enrich_metrics(daily_metrics, repo)
    except Exception as e:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to enrich metrics: {str(e)}",
        )
        return CoachError(
            error_type="unknown",
            message=f"Failed to enrich metrics: {str(e)}",
        )

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Training status: CTL={enriched.ctl.formatted_value}, "
        f"TSB={enriched.tsb.formatted_value}, "
        f"readiness={enriched.readiness.formatted_value}",
    )

    return enriched


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _find_latest_metrics_date(repo: RepositoryIO) -> Optional[date]:
    """
    Find the most recent date with metrics available.

    Returns:
        Date of most recent metrics, or None if no metrics exist.
    """
    # Check last 30 days for metrics files
    today = date.today()
    for i in range(30):
        check_date = today - timedelta(days=i)
        metrics_path = daily_metrics_path(check_date)
        resolved_path = repo.resolve_path(metrics_path)
        if resolved_path.exists():
            return check_date

    return None
