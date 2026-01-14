"""
M4 - Athlete Profile Service

CRUD operations for athlete profile, constraints, goals, and preferences.
Includes VDOT calculation and constraint validation.
"""

import math
from typing import Optional, Union, List
from enum import Enum

from sports_coach_engine.core.paths import athlete_profile_path
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.profile import (
    AthleteProfile,
    TrainingConstraints,
    Goal,
    GoalType,
    Weekday,
)
from sports_coach_engine.schemas.repository import RepoError, ReadOptions


# ============================================================
# ERROR TYPES
# ============================================================


class ProfileErrorType(str, Enum):
    """Profile service error types."""

    PROFILE_NOT_FOUND = "profile_not_found"
    VALIDATION_ERROR = "validation_error"
    IO_ERROR = "io_error"


class ProfileError:
    """Profile service error with details."""

    def __init__(self, error_type: ProfileErrorType, message: str):
        self.error_type = error_type
        self.message = message


# ============================================================
# RESULT TYPES
# ============================================================

ProfileResult = Union[AthleteProfile, None, ProfileError]


# ============================================================
# PROFILE SERVICE
# ============================================================


class ProfileService:
    """Service for managing athlete profile CRUD operations."""

    def __init__(self, repo: RepositoryIO):
        """
        Initialize profile service.

        Args:
            repo: Repository I/O instance for file operations
        """
        self.repo = repo

    def load_profile(self) -> ProfileResult:
        """
        Load the athlete profile.

        Returns:
            AthleteProfile if exists, None if not found (when allow_missing=True),
            or ProfileError on failure
        """
        result = self.repo.read_yaml(
            "athlete_profile_path()", AthleteProfile, ReadOptions(allow_missing=True)
        )

        if isinstance(result, RepoError):
            return ProfileError(
                error_type=ProfileErrorType.IO_ERROR, message=result.message
            )

        return result  # AthleteProfile or None

    def save_profile(self, profile: AthleteProfile) -> Optional[ProfileError]:
        """
        Save the athlete profile.

        Args:
            profile: Profile to save

        Returns:
            None on success, ProfileError on failure
        """
        result = self.repo.write_yaml("athlete_profile_path()", profile)

        if isinstance(result, RepoError):
            return ProfileError(
                error_type=ProfileErrorType.IO_ERROR, message=result.message
            )

        return None

    def update_profile(self, updates: dict) -> Union[AthleteProfile, ProfileError]:
        """
        Update specific fields in the profile.

        Args:
            updates: Dictionary of fields to update

        Returns:
            Updated AthleteProfile on success, ProfileError on failure
        """
        current = self.load_profile()

        if current is None:
            return ProfileError(
                error_type=ProfileErrorType.PROFILE_NOT_FOUND,
                message="No profile found. Create a profile first.",
            )

        if isinstance(current, ProfileError):
            return current

        # Merge updates
        # Use model_dump(mode='json') to get JSON-serializable types (converts enums to values)
        profile_dict = current.model_dump(mode='json')
        profile_dict.update(updates)

        # Validate merged data
        try:
            updated = AthleteProfile.model_validate(profile_dict)
        except Exception as e:
            return ProfileError(
                error_type=ProfileErrorType.VALIDATION_ERROR,
                message=f"Validation failed: {e}",
            )

        # Save
        error = self.save_profile(updated)
        if error:
            return error

        return updated

    def delete_profile(self) -> Optional[ProfileError]:
        """
        Delete the athlete profile.

        Returns:
            None on success, ProfileError on failure
        """
        from pathlib import Path

        profile_path = self.repo.resolve_path("athlete_profile_path()")

        if not profile_path.exists():
            return ProfileError(
                error_type=ProfileErrorType.PROFILE_NOT_FOUND,
                message="No profile found to delete.",
            )

        try:
            profile_path.unlink()
            return None
        except Exception as e:
            return ProfileError(
                error_type=ProfileErrorType.IO_ERROR,
                message=f"Failed to delete profile: {e}",
            )


# ============================================================
# VDOT CALCULATION
# ============================================================


class RaceDistance(str, Enum):
    """Standard race distances for VDOT calculation."""

    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"


# Distance in meters
DISTANCES_M = {
    RaceDistance.FIVE_K: 5000,
    RaceDistance.TEN_K: 10000,
    RaceDistance.HALF_MARATHON: 21097.5,
    RaceDistance.MARATHON: 42195,
}


def parse_time_to_seconds(time_str: str) -> int:
    """
    Parse time string to seconds.

    Args:
        time_str: Time in MM:SS or HH:MM:SS format

    Returns:
        Time in seconds

    Raises:
        ValueError: If time format is invalid
    """
    parts = time_str.split(":")

    if len(parts) == 2:  # MM:SS
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:  # HH:MM:SS
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    else:
        raise ValueError(f"Invalid time format: {time_str}. Use MM:SS or HH:MM:SS")


def calculate_vdot(distance: RaceDistance, time: str) -> Union[float, ProfileError]:
    """
    Calculate VDOT using Jack Daniels' formula.

    VDOT is an index of running ability that normalizes performance across distances.
    It represents the runner's VO2max adjusted for running economy.

    Args:
        distance: Race distance (5k, 10k, half_marathon, marathon)
        time: Race time in HH:MM:SS or MM:SS format

    Returns:
        VDOT value (rounded to nearest 0.5) or ProfileError if invalid input
    """
    try:
        time_seconds = parse_time_to_seconds(time)
    except ValueError as e:
        return ProfileError(
            error_type=ProfileErrorType.VALIDATION_ERROR, message=str(e)
        )

    distance_m = DISTANCES_M[distance]
    time_min = time_seconds / 60

    # Velocity in meters per minute
    velocity = distance_m / time_min

    # Percent of VO2max at race pace (Jack Daniels' formula)
    # This accounts for the fact that runners can't sustain 100% VO2max in races
    percent_max = (
        0.8
        + 0.1894393 * math.exp(-0.012778 * time_min)
        + 0.2989558 * math.exp(-0.1932605 * time_min)
    )

    # Oxygen cost (Jack Daniels' formula)
    # Relates running velocity to oxygen consumption
    vo2 = -4.6 + 0.182258 * velocity + 0.000104 * velocity**2

    # VDOT calculation
    vdot = vo2 / percent_max

    # Round to nearest 0.5 for practical use
    return round(vdot * 2) / 2


# ============================================================
# CONSTRAINT VALIDATION
# ============================================================


class ConstraintError:
    """Single constraint validation error."""

    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity  # "error" or "warning"


class ConstraintValidationResult:
    """Result of constraint validation."""

    def __init__(self, valid: bool, errors: Optional[List[ConstraintError]] = None):
        self.valid = valid
        self.errors = errors or []


def validate_constraints(
    constraints: TrainingConstraints, goal: Goal
) -> ConstraintValidationResult:
    """
    Validate training constraints for logical consistency.

    Checks per M4 spec:
    - max_run_days < min_run_days → Error
    - len(available_run_days) < min_run_days → Warning
    - len(available_run_days) = 0 AND goal.type ≠ general_fitness → Error
    - All available_run_days consecutive (back-to-back) → Warning

    Args:
        constraints: Training constraints to validate
        goal: Current training goal

    Returns:
        Validation result with any errors or warnings
    """
    errors = []

    # Check: max_run_days < min_run_days
    if constraints.max_run_days_per_week < constraints.min_run_days_per_week:
        errors.append(
            ConstraintError(
                field="max_run_days_per_week",
                message="Max run days cannot be less than min run days",
                severity="error",
            )
        )

    # Check: insufficient available days
    available_count = len(constraints.available_run_days)
    if available_count < constraints.min_run_days_per_week:
        errors.append(
            ConstraintError(
                field="available_run_days",
                message=f"Insufficient available run days ({available_count}) to meet minimum ({constraints.min_run_days_per_week}). Consider adjusting constraints.",
                severity="warning",
            )
        )

    # Check: no run days with race goal
    if available_count == 0 and goal.type != GoalType.GENERAL_FITNESS:
        errors.append(
            ConstraintError(
                field="available_run_days",
                message="Cannot create a race-focused plan with 0 available run days. Add at least one run day or switch to general_fitness goal.",
                severity="error",
            )
        )

    # Check: all days consecutive (back-to-back)
    if available_count >= 2:
        # Map weekdays to numbers for consecutive check
        weekday_order = {
            Weekday.MONDAY: 0,
            Weekday.TUESDAY: 1,
            Weekday.WEDNESDAY: 2,
            Weekday.THURSDAY: 3,
            Weekday.FRIDAY: 4,
            Weekday.SATURDAY: 5,
            Weekday.SUNDAY: 6,
        }

        day_numbers = sorted(
            [weekday_order[day] for day in constraints.available_run_days]
        )

        # Check if all consecutive
        all_consecutive = all(
            day_numbers[i + 1] - day_numbers[i] == 1 for i in range(len(day_numbers) - 1)
        )

        if all_consecutive:
            errors.append(
                ConstraintError(
                    field="available_run_days",
                    message="Back-to-back run days detected. Plan will enforce hard/easy separation (one day must be easy).",
                    severity="warning",
                )
            )

    # Valid if no errors (warnings don't block)
    has_errors = any(e.severity == "error" for e in errors)

    return ConstraintValidationResult(valid=not has_errors, errors=errors)
