"""
Profile API - Athlete profile management.

Provides functions for Claude Code to manage athlete profiles,
goals, and constraints.
"""

from datetime import date
from typing import Optional, Union, Any
from dataclasses import dataclass

from sports_coach_engine.core.repository import RepositoryIO, ReadOptions
from sports_coach_engine.schemas.repository import RepoError, RepoErrorType
from sports_coach_engine.core.logger import log_message, MessageRole
from sports_coach_engine.schemas.profile import AthleteProfile, Goal, GoalType
from sports_coach_engine.api.plan import regenerate_plan, PlanError


# ============================================================
# ERROR TYPES
# ============================================================


@dataclass
class ProfileError:
    """Error result from profile operations."""

    error_type: str  # "not_found", "validation", "unknown"
    message: str


# ============================================================
# PUBLIC API FUNCTIONS
# ============================================================


def get_profile() -> Union[AthleteProfile, ProfileError]:
    """
    Get current athlete profile.

    Workflow:
    1. Load profile from athlete/profile.yaml
    2. Log operation via M14
    3. Return profile

    Returns:
        AthleteProfile containing:
        - name: Athlete name
        - goal: Current training goal
        - constraints: Training constraints (runs per week, preferred days, etc.)
        - conflict_policy: How to handle sport conflicts
        - strava_connection: Strava integration settings
        - recent_races: Recent race results
        - vital_signs: Resting HR, max HR, etc.

        ProfileError on failure containing error details

    Example:
        >>> profile = get_profile()
        >>> if isinstance(profile, ProfileError):
        ...     print(f"Error: {profile.message}")
        ... else:
        ...     print(f"Athlete: {profile.name}")
        ...     if profile.goal:
        ...         print(f"Goal: {profile.goal.type.value} on {profile.goal.target_date}")
        ...     print(f"Runs per week: {profile.constraints.runs_per_week}")
    """
    repo = RepositoryIO()

    # Log user request
    log_message(repo, MessageRole.USER, "get_profile()")

    # Load profile
    profile_path = "athlete/profile.yaml"
    result = repo.read_yaml(profile_path, AthleteProfile, ReadOptions(validate=True))

    if isinstance(result, RepoError):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to load profile: {str(result)}",
        )
        error_type = "not_found" if result.error_type == RepoErrorType.FILE_NOT_FOUND else "validation"
        return ProfileError(
            error_type=error_type,
            message=f"Failed to load profile: {str(result)}",
        )

    profile = result

    # Log response
    goal_str = f", goal={profile.goal.type.value}" if profile.goal else ", no goal set"
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Returned profile: {profile.name}{goal_str}",
    )

    return profile


def update_profile(**fields: Any) -> Union[AthleteProfile, ProfileError]:
    """
    Update athlete profile fields.

    Workflow:
    1. Load current profile
    2. Update specified fields
    3. Validate updated profile
    4. Save updated profile
    5. Log operation via M14
    6. Return updated profile

    Args:
        **fields: Fields to update. Valid fields include:
            - name: str
            - constraints: TrainingConstraints dict or object
            - conflict_policy: ConflictPolicy enum value
            - vital_signs: VitalSigns dict or object
            - recent_races: list of RecentRace
            - strava_connection: StravaConnection dict or object

    Returns:
        Updated AthleteProfile

        ProfileError on failure containing error details

    Example:
        >>> # Update training constraints
        >>> profile = update_profile(
        ...     constraints={
        ...         "runs_per_week": 4,
        ...         "preferred_run_days": ["monday", "wednesday", "friday", "sunday"]
        ...     }
        ... )
        >>> if isinstance(profile, ProfileError):
        ...     print(f"Error: {profile.message}")
        ... else:
        ...     print(f"Updated: {profile.constraints.runs_per_week} runs/week")
    """
    repo = RepositoryIO()

    # Log user request
    field_names = ", ".join(fields.keys())
    log_message(repo, MessageRole.USER, f"update_profile(fields={field_names})")

    # Load current profile
    profile_path = "athlete/profile.yaml"
    result = repo.read_yaml(profile_path, AthleteProfile, ReadOptions(validate=True))

    if isinstance(result, RepoError):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to load profile: {str(result)}",
        )
        return ProfileError(
            error_type="not_found",
            message=f"Failed to load profile: {str(result)}",
        )

    profile = result

    # Update fields
    # Note: This uses simple attribute assignment
    # For nested objects (like constraints), the field should be passed as a dict
    # which Pydantic will handle during validation
    for field_name, field_value in fields.items():
        if not hasattr(profile, field_name):
            log_message(
                repo,
                MessageRole.SYSTEM,
                f"Invalid field: {field_name}",
            )
            return ProfileError(
                error_type="validation",
                message=f"Invalid field: {field_name}",
            )

        setattr(profile, field_name, field_value)

    # Validate updated profile by reconstructing it
    try:
        profile = AthleteProfile.model_validate(profile.model_dump())
    except Exception as e:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Validation failed: {str(e)}",
        )
        return ProfileError(
            error_type="validation",
            message=f"Invalid profile data: {str(e)}",
        )

    # Save updated profile
    write_result = repo.write_yaml(profile_path, profile)
    if isinstance(write_result, RepoError):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to save profile: {str(write_result)}",
        )
        return ProfileError(
            error_type="unknown",
            message=f"Failed to save profile: {str(write_result)}",
        )

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Updated profile: {field_names}",
    )

    return profile


def set_goal(
    race_type: str,
    target_date: date,
    target_time: Optional[str] = None,
) -> Union[Goal, ProfileError]:
    """
    Set a new race goal and regenerate the training plan.

    Workflow:
    1. Create Goal object from inputs
    2. Update athlete profile with new goal
    3. Call regenerate_plan() to create new plan
    4. Log operation via M14
    5. Return goal

    Args:
        race_type: Type of race. Valid values:
            - "5k", "10k", "half_marathon", "marathon"
        target_date: Race date
        target_time: Target finish time (optional, e.g., "1:45:00" for HH:MM:SS)

    Returns:
        New Goal object

        ProfileError on failure containing error details

    Example:
        >>> # Set half marathon goal
        >>> goal = set_goal(
        ...     race_type="half_marathon",
        ...     target_date=date(2024, 6, 15),
        ...     target_time="1:45:00"
        ... )
        >>> if isinstance(goal, ProfileError):
        ...     print(f"Error: {goal.message}")
        ... else:
        ...     print(f"Goal set: {goal.type.value} on {goal.target_date}")
        ...     print(f"New training plan generated")
    """
    repo = RepositoryIO()

    # Log user request
    log_message(
        repo,
        MessageRole.USER,
        f"set_goal(race_type={race_type}, target_date={target_date}, target_time={target_time})",
    )

    # Parse race type
    try:
        goal_type = GoalType(race_type.lower())
    except ValueError:
        valid_types = ", ".join([t.value for t in GoalType])
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Invalid race type: {race_type}",
        )
        return ProfileError(
            error_type="validation",
            message=f"Invalid race type '{race_type}'. Valid types: {valid_types}",
        )

    # Create goal object
    # Convert date to ISO string if needed
    target_date_str = target_date.isoformat() if isinstance(target_date, date) else target_date

    goal = Goal(
        type=goal_type,
        target_date=target_date_str,
        target_time=target_time,
    )

    # Update profile with new goal
    profile_path = "athlete/profile.yaml"
    profile_result = repo.read_yaml(profile_path, AthleteProfile, ReadOptions(validate=True))

    if isinstance(profile_result, RepoError):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to load profile: {str(profile_result)}",
        )
        return ProfileError(
            error_type="not_found",
            message=f"Failed to load profile: {str(profile_result)}",
        )

    profile = profile_result
    profile.goal = goal

    # Save updated profile
    write_result = repo.write_yaml(profile_path, profile)
    if isinstance(write_result, RepoError):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to save profile: {str(write_result)}",
        )
        return ProfileError(
            error_type="unknown",
            message=f"Failed to save profile: {str(write_result)}",
        )

    # Regenerate plan with new goal
    plan_result = regenerate_plan(goal=goal)
    if isinstance(plan_result, PlanError):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to regenerate plan: {plan_result.message}",
        )
        return ProfileError(
            error_type="unknown",
            message=f"Goal set but plan generation failed: {plan_result.message}",
        )

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Set goal: {goal.type.value} on {goal.target_date}, "
        f"generated {plan_result.total_weeks}-week plan",
    )

    return goal
