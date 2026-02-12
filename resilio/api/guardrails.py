"""
Guardrails API - Volume validation and recovery planning.

Provides high-level functions for Claude Code to:
- Validate quality volume (T/I/R pace limits)
- Check weekly progression (10% rule)
- Validate long run limits
- Calculate safe volume ranges
- Plan return-to-training after breaks
- Calculate age-specific recovery adjustments
- Determine race recovery protocols
- Generate illness recovery plans

This API wraps the core guardrails module with error handling and convenient interfaces.
Multi-sport context: All recovery functions account for cross-training activities.
"""

from typing import Union, Optional
from dataclasses import dataclass
from datetime import date as dt_date

from resilio.schemas.guardrails import (
    QualityVolumeValidation,
    WeeklyProgressionValidation,
    LongRunValidation,
    FeasibleVolumeValidation,
    SafeVolumeRange,
    BreakReturnPlan,
    MastersRecoveryAdjustment,
    RaceRecoveryPlan,
    IllnessRecoveryPlan,
    IllnessSeverity,
    ProgressionContext,
)
from resilio.core.guardrails.volume import (
    validate_quality_volume as core_validate_quality,
    validate_weekly_progression as core_validate_progression,
    validate_long_run_limits as core_validate_long_run,
    validate_weekly_volume_feasibility as core_validate_feasibility,
    calculate_safe_volume_range as core_calculate_safe_range,
    analyze_weekly_progression_context as core_analyze_progression_context,
)
from resilio.core.guardrails.recovery import (
    calculate_break_return_plan as core_break_return,
    calculate_masters_recovery as core_masters_recovery,
    calculate_race_recovery as core_race_recovery,
    generate_illness_recovery_plan as core_illness_recovery,
)


# ============================================================
# ERROR TYPES
# ============================================================


@dataclass
class GuardrailsError:
    """Error result from guardrails operations."""

    error_type: str  # "invalid_input", "out_of_range", "calculation_failed"
    message: str


# ============================================================
# VOLUME VALIDATION FUNCTIONS
# ============================================================


def validate_quality_volume(
    t_pace_km: float,
    i_pace_km: float,
    r_pace_km: float,
    weekly_mileage_km: float,
) -> Union[QualityVolumeValidation, GuardrailsError]:
    """
    Validate T/I/R pace volumes against Daniels' hard constraints.

    Daniels' Rules:
    - T-pace: ≤ 10% of weekly mileage
    - I-pace: ≤ lesser of 10km OR 8% of weekly mileage
    - R-pace: ≤ lesser of 8km OR 5% of weekly mileage

    Args:
        t_pace_km: Total threshold pace volume in km
        i_pace_km: Total interval pace volume in km
        r_pace_km: Total repetition pace volume in km
        weekly_mileage_km: Total weekly mileage in km

    Returns:
        QualityVolumeValidation on success, GuardrailsError on failure

    Examples:
        >>> validate_quality_volume(4.5, 6.0, 2.0, 50.0)
        QualityVolumeValidation(i_pace_ok=False, violations=[...])

        >>> validate_quality_volume(3.0, 4.0, 2.0, 50.0)
        QualityVolumeValidation(overall_ok=True, violations=[])
    """
    try:
        # Validate inputs are non-negative
        if t_pace_km < 0 or i_pace_km < 0 or r_pace_km < 0:
            return GuardrailsError(
                error_type="invalid_input", message="Pace volumes must be non-negative"
            )

        if weekly_mileage_km <= 0:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Weekly mileage must be positive, got {weekly_mileage_km}",
            )

        # Validate paces don't exceed weekly volume
        total_quality = t_pace_km + i_pace_km + r_pace_km
        if total_quality > weekly_mileage_km:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Total quality volume ({total_quality:.1f}km) exceeds weekly mileage ({weekly_mileage_km:.1f}km)",
            )

        # Call core function
        result = core_validate_quality(t_pace_km, i_pace_km, r_pace_km, weekly_mileage_km)
        return result

    except ValueError as e:
        return GuardrailsError(
            error_type="calculation_failed", message=f"Quality volume validation failed: {e}"
        )
    except Exception as e:
        return GuardrailsError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def validate_weekly_progression(
    previous_volume_km: float,
    current_volume_km: float,
) -> Union[WeeklyProgressionValidation, GuardrailsError]:
    """
    Validate weekly volume progression using the 10% rule.

    The 10% rule: Weekly mileage should not increase by more than 10%
    from one week to the next to minimize injury risk.

    Args:
        previous_volume_km: Previous week's total volume
        current_volume_km: Current week's planned volume

    Returns:
        WeeklyProgressionValidation on success, GuardrailsError on failure

    Examples:
        >>> validate_weekly_progression(40.0, 50.0)
        WeeklyProgressionValidation(ok=False, increase_pct=25.0, ...)

        >>> validate_weekly_progression(40.0, 44.0)
        WeeklyProgressionValidation(ok=True, increase_pct=10.0, ...)
    """
    try:
        # Validate inputs are non-negative
        if previous_volume_km < 0 or current_volume_km < 0:
            return GuardrailsError(
                error_type="invalid_input", message="Volume values must be non-negative"
            )

        # Allow previous_volume_km to be zero (first week of training)
        # but current_volume_km should be positive
        if current_volume_km == 0:
            return GuardrailsError(
                error_type="invalid_input", message="Current volume must be positive"
            )

        # Call core function
        result = core_validate_progression(previous_volume_km, current_volume_km)
        return result

    except ValueError as e:
        return GuardrailsError(
            error_type="calculation_failed", message=f"Progression validation failed: {e}"
        )
    except Exception as e:
        return GuardrailsError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def analyze_weekly_progression_context(
    previous_volume_km: float,
    current_volume_km: float,
    current_ctl: Optional[float] = None,
    run_days_per_week: Optional[int] = None,
    athlete_age: Optional[int] = None,
    recent_injury: bool = False,
    injury_history: Optional[list] = None,
) -> Union[ProgressionContext, GuardrailsError]:
    """
    Analyze volume progression with rich context for AI coaching decisions.

    This function provides CONTEXT and INSIGHTS, not coaching decisions.
    Claude Code interprets this data using training methodology knowledge.

    Philosophy: CLI computes and classifies → AI coach decides.

    Args:
        previous_volume_km: Previous week's volume
        current_volume_km: Current week's planned volume
        current_ctl: Current CTL for capacity analysis (optional)
        run_days_per_week: Number of run days for per-session analysis (optional)
        athlete_age: Age for masters considerations (optional)
        recent_injury: Flag for recent injury (<90 days)
        injury_history: List of past injuries for pattern detection (optional)

    Returns:
        ProgressionContext on success, GuardrailsError on failure

    Examples:
        >>> analyze_weekly_progression_context(15.0, 20.0, current_ctl=27.0, run_days_per_week=4)
        ProgressionContext(volume_context={'category': 'low'}, protective_factors=[...])

        >>> analyze_weekly_progression_context(60.0, 75.0, current_ctl=55.0, run_days_per_week=4)
        ProgressionContext(volume_context={'category': 'high'}, risk_factors=[...])
    """
    try:
        # Validate inputs are non-negative
        if previous_volume_km < 0 or current_volume_km < 0:
            return GuardrailsError(
                error_type="invalid_input", message="Volume values must be non-negative"
            )

        # Current volume must be positive
        if current_volume_km == 0:
            return GuardrailsError(
                error_type="invalid_input", message="Current volume must be positive"
            )

        # Validate CTL if provided
        if current_ctl is not None and current_ctl < 0:
            return GuardrailsError(
                error_type="invalid_input", message=f"CTL must be non-negative, got {current_ctl}"
            )

        # Validate run_days_per_week if provided
        if run_days_per_week is not None:
            if run_days_per_week <= 0 or run_days_per_week > 7:
                return GuardrailsError(
                    error_type="invalid_input",
                    message=f"Run days per week must be between 1 and 7, got {run_days_per_week}",
                )

        # Validate athlete_age if provided
        if athlete_age is not None:
            if athlete_age < 18 or athlete_age > 100:
                return GuardrailsError(
                    error_type="out_of_range",
                    message=f"Age must be between 18 and 100, got {athlete_age}",
                )

        # Call core function
        result = core_analyze_progression_context(
            previous_volume_km=previous_volume_km,
            current_volume_km=current_volume_km,
            current_ctl=current_ctl,
            run_days_per_week=run_days_per_week,
            athlete_age=athlete_age,
            recent_injury=recent_injury,
            injury_history=injury_history,
        )
        return result

    except ValueError as e:
        return GuardrailsError(
            error_type="calculation_failed", message=f"Progression context analysis failed: {e}"
        )
    except Exception as e:
        return GuardrailsError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def validate_long_run_limits(
    long_run_km: float,
    long_run_duration_minutes: int,
    weekly_volume_km: float,
    pct_limit: float = 30.0,
    duration_limit_minutes: int = 150,
) -> Union[LongRunValidation, GuardrailsError]:
    """
    Validate long run against weekly volume and duration limits.

    Daniels/Pfitzinger guidelines:
    - Long run ≤ 25-30% of weekly volume
    - Long run ≤ 2.5 hours (150 minutes) for most runners

    Args:
        long_run_km: Long run distance in km
        long_run_duration_minutes: Expected long run duration
        weekly_volume_km: Total weekly volume
        pct_limit: Percentage limit (default 30%)
        duration_limit_minutes: Duration limit (default 150 min)

    Returns:
        LongRunValidation on success, GuardrailsError on failure

    Examples:
        >>> validate_long_run_limits(18.0, 135, 50.0)
        LongRunValidation(pct_ok=False, duration_ok=True, ...)

        >>> validate_long_run_limits(15.0, 120, 50.0)
        LongRunValidation(overall_ok=True, violations=[])
    """
    try:
        # Validate inputs
        if long_run_km <= 0:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Long run distance must be positive, got {long_run_km}",
            )

        if long_run_duration_minutes <= 0:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Long run duration must be positive, got {long_run_duration_minutes}",
            )

        if weekly_volume_km <= 0:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Weekly volume must be positive, got {weekly_volume_km}",
            )

        if long_run_km > weekly_volume_km:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Long run ({long_run_km}km) exceeds weekly volume ({weekly_volume_km}km)",
            )

        if pct_limit <= 0 or pct_limit > 100:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Percentage limit must be between 0 and 100, got {pct_limit}",
            )

        if duration_limit_minutes <= 0:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Duration limit must be positive, got {duration_limit_minutes}",
            )

        # Call core function
        result = core_validate_long_run(
            long_run_km,
            long_run_duration_minutes,
            weekly_volume_km,
            pct_limit,
            duration_limit_minutes,
        )
        return result

    except ValueError as e:
        return GuardrailsError(
            error_type="calculation_failed", message=f"Long run validation failed: {e}"
        )
    except Exception as e:
        return GuardrailsError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def validate_weekly_volume_feasibility(
    run_days_per_week: int,
    max_time_per_session_minutes: int,
    easy_pace_min_per_km: float,
    target_volume_km: Optional[float] = None,
) -> Union[FeasibleVolumeValidation, GuardrailsError]:
    """
    Validate weekly volume feasibility based on session duration constraints.

    Uses a conservative easy-pace estimate to compute the maximum feasible
    weekly volume given run frequency and max session duration.
    """
    try:
        if run_days_per_week <= 0 or run_days_per_week > 7:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Run days per week must be 1-7, got {run_days_per_week}",
            )
        if max_time_per_session_minutes <= 0:
            return GuardrailsError(
                error_type="invalid_input",
                message=(
                    f"Max session minutes must be positive, got {max_time_per_session_minutes}"
                ),
            )
        if easy_pace_min_per_km <= 0:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Easy pace must be positive, got {easy_pace_min_per_km}",
            )
        if target_volume_km is not None and target_volume_km <= 0:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Target volume must be positive, got {target_volume_km}",
            )

        result = core_validate_feasibility(
            run_days_per_week=run_days_per_week,
            max_time_per_session_minutes=max_time_per_session_minutes,
            easy_pace_min_per_km=easy_pace_min_per_km,
            target_volume_km=target_volume_km,
        )
        return result

    except ValueError as e:
        return GuardrailsError(
            error_type="calculation_failed",
            message=f"Feasibility validation failed: {e}",
        )
    except Exception as e:
        return GuardrailsError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def calculate_safe_volume_range(
    current_ctl: float,
    running_priority: str,
    goal_type: str = "fitness",
    athlete_age: Optional[int] = None,
    recent_weekly_volume_km: Optional[float] = None,
    run_days_per_week: Optional[int] = None,
) -> Union[SafeVolumeRange, GuardrailsError]:
    """
    Calculate safe weekly volume range based on current fitness and goals.

    Based on CTL zones and training methodology recommendations.

    CTL-based volume recommendations:
    - <20 (Beginner): 15-25 km/week
    - 20-35 (Recreational): 25-40 km/week
    - 35-50 (Competitive): 40-65 km/week
    - >50 (Advanced): 55-80+ km/week

    Multi-sport priority adjustments:
    - PRIMARY: Standard volumes (100%) - running is main focus
    - EQUAL: Reduced 25% - running balanced with other sports
    - SECONDARY: Reduced 50% - maintenance only, other sport is primary

    IMPORTANT: If recent_weekly_volume_km is provided, this function will recommend
    starting at or near that volume to avoid dangerous jumps, even if CTL suggests
    the athlete could handle more. The 10% rule applies to running-specific volume,
    not just overall fitness (CTL includes all sports).

    Args:
        current_ctl: Current chronic training load
        running_priority: Running priority ("primary", "equal", "secondary")
        goal_type: Race goal ("5k", "10k", "half_marathon", "marathon", "fitness")
        athlete_age: Age for masters adjustments (optional)
        recent_weekly_volume_km: Actual recent running volume (last 4 weeks avg) (optional)
        run_days_per_week: Number of run days per week (optional)

    Returns:
        SafeVolumeRange on success, GuardrailsError on failure

    Examples:
        >>> # Single-sport runner
        >>> calculate_safe_volume_range(44.0, "primary", "half_marathon", 52)
        SafeVolumeRange(recommended_start_km=30, recommended_peak_km=45, ...)

        >>> # Multi-sport athlete (running balanced with climbing)
        >>> calculate_safe_volume_range(30.0, "equal", "10k", recent_weekly_volume_km=20.7)
        SafeVolumeRange(recommended_start_km=22, recommended_peak_km=30, ...)
    """
    try:
        # Validate CTL
        if current_ctl < 0:
            return GuardrailsError(
                error_type="invalid_input", message=f"CTL must be non-negative, got {current_ctl}"
            )

        # Validate and normalize priority
        normalized_priority = running_priority.lower()
        valid_priorities = {"primary", "equal", "secondary"}
        if normalized_priority not in valid_priorities:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Invalid running_priority '{running_priority}'. Must be 'primary', 'equal', or 'secondary'.",
            )

        # Normalize goal type
        normalized_goal = goal_type.lower().replace("-", "_").replace(" ", "_")
        if normalized_goal == "general_fitness":
            normalized_goal = "fitness"

        # Validate goal type
        valid_goals = {"5k", "10k", "half_marathon", "marathon", "fitness"}
        if normalized_goal not in valid_goals:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Invalid goal type '{goal_type}'. Valid: {', '.join(valid_goals)}",
            )

        # Validate age if provided
        if athlete_age is not None:
            if athlete_age < 18 or athlete_age > 100:
                return GuardrailsError(
                    error_type="out_of_range",
                    message=f"Age must be between 18 and 100, got {athlete_age}",
                )

        # Validate recent volume if provided
        if recent_weekly_volume_km is not None:
            if recent_weekly_volume_km < 0:
                return GuardrailsError(
                    error_type="invalid_input",
                    message=f"Recent volume must be non-negative, got {recent_weekly_volume_km}",
                )

        # Call core function
        result = core_calculate_safe_range(
            current_ctl, normalized_priority, normalized_goal, athlete_age, recent_weekly_volume_km, run_days_per_week
        )
        return result

    except ValueError as e:
        return GuardrailsError(
            error_type="calculation_failed", message=f"Safe volume range calculation failed: {e}"
        )
    except Exception as e:
        return GuardrailsError(error_type="calculation_failed", message=f"Unexpected error: {e}")


# ============================================================
# RECOVERY PLANNING FUNCTIONS
# ============================================================


def calculate_break_return_plan(
    break_days: int,
    pre_break_ctl: float,
    cross_training_level: str = "none",
) -> Union[BreakReturnPlan, GuardrailsError]:
    """
    Generate return-to-training protocol per Daniels Table 9.2.

    Multi-sport context: Cross-training during break (cycling, climbing, swimming)
    reduces fitness loss and accelerates return to full training.

    Daniels' guidelines:
    - ≤5 days: 100% load, 100% VDOT
    - 6-28 days: 50% first half, 75% second half, 93-99% VDOT
    - >8 weeks: Structured multi-week (33%, 50%, 75%), 80-92% VDOT

    Args:
        break_days: Length of training break (days)
        pre_break_ctl: CTL before the break
        cross_training_level: Level of cross-training ("none", "light", "moderate", "heavy")

    Returns:
        BreakReturnPlan on success, GuardrailsError on failure

    Examples:
        >>> calculate_break_return_plan(21, 44.0, "moderate")
        BreakReturnPlan(load_phase_1_pct=50, load_phase_2_pct=75, ...)

        >>> calculate_break_return_plan(3, 35.0)
        BreakReturnPlan(load_phase_1_pct=100, estimated_full_return_weeks=0, ...)
    """
    try:
        # Validate inputs
        if break_days <= 0:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Break duration must be positive, got {break_days}",
            )

        if break_days > 365:
            return GuardrailsError(
                error_type="out_of_range",
                message=f"Break duration exceeds 1 year ({break_days} days). Consider rebuilding from scratch.",
            )

        if pre_break_ctl < 0:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Pre-break CTL must be non-negative, got {pre_break_ctl}",
            )

        # Validate cross-training level
        valid_levels = {"none", "light", "moderate", "heavy"}
        if cross_training_level.lower() not in valid_levels:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Invalid cross-training level '{cross_training_level}'. Valid: {', '.join(valid_levels)}",
            )

        # Call core function
        result = core_break_return(break_days, pre_break_ctl, cross_training_level)
        return result

    except ValueError as e:
        return GuardrailsError(
            error_type="calculation_failed", message=f"Break return plan calculation failed: {e}"
        )
    except Exception as e:
        return GuardrailsError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def calculate_masters_recovery(
    age: int,
    workout_type: str,
) -> Union[MastersRecoveryAdjustment, GuardrailsError]:
    """
    Calculate age-specific recovery adjustments (Pfitzinger).

    Masters athletes (45+) require longer recovery between hard efforts.
    This function provides evidence-based recovery adjustments by age bracket.

    Age brackets: 18-35 (base), 36-45 (+0-1 day), 46-55 (+1-2 days), 56+ (+2-3 days)

    Args:
        age: Athlete age
        workout_type: Type of workout ("vo2max", "tempo", "long_run", "race")

    Returns:
        MastersRecoveryAdjustment on success, GuardrailsError on failure

    Examples:
        >>> calculate_masters_recovery(52, "vo2max")
        MastersRecoveryAdjustment(recommended_recovery_days={'vo2max': 3, ...})

        >>> calculate_masters_recovery(28, "tempo")
        MastersRecoveryAdjustment(adjustments={'tempo': 0}, ...)
    """
    try:
        # Validate age
        if age < 18 or age > 100:
            return GuardrailsError(
                error_type="out_of_range", message=f"Age must be between 18 and 100, got {age}"
            )

        # Validate workout type
        valid_types = {"vo2max", "tempo", "long_run", "race"}
        if workout_type.lower() not in valid_types:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Invalid workout type '{workout_type}'. Valid: {', '.join(valid_types)}",
            )

        # Call core function
        result = core_masters_recovery(age, workout_type)
        return result

    except ValueError as e:
        return GuardrailsError(
            error_type="calculation_failed", message=f"Masters recovery calculation failed: {e}"
        )
    except Exception as e:
        return GuardrailsError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def calculate_race_recovery(
    race_distance: str,
    athlete_age: int,
    finishing_effort: str = "hard",
) -> Union[RaceRecoveryPlan, GuardrailsError]:
    """
    Determine post-race recovery protocol by distance and age.

    Multi-sport context: Cross-training (easy cycling, swimming) can be added
    earlier than running during recovery phase.

    Pfitzinger masters recovery tables:
    - 5K: 4-7 days
    - 10K: 6-10 days
    - Half Marathon: 7-14 days
    - Marathon: 14-28 days

    Args:
        race_distance: Race distance ("5k", "10k", "half_marathon", "marathon")
        athlete_age: Athlete age
        finishing_effort: Effort level ("easy", "moderate", "hard", "max")

    Returns:
        RaceRecoveryPlan on success, GuardrailsError on failure

    Examples:
        >>> calculate_race_recovery("half_marathon", 52, "hard")
        RaceRecoveryPlan(minimum_recovery_days=9, quality_work_resume_day=11, ...)

        >>> calculate_race_recovery("10k", 28, "moderate")
        RaceRecoveryPlan(minimum_recovery_days=6, recommended_recovery_days=7, ...)
    """
    try:
        # Validate race distance
        valid_distances = {"5k", "10k", "half_marathon", "marathon"}
        if race_distance.lower() not in valid_distances:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Invalid race distance '{race_distance}'. Valid: {', '.join(valid_distances)}",
            )

        # Validate age
        if athlete_age < 18 or athlete_age > 100:
            return GuardrailsError(
                error_type="out_of_range",
                message=f"Age must be between 18 and 100, got {athlete_age}",
            )

        # Validate effort level
        valid_efforts = {"easy", "moderate", "hard", "max"}
        if finishing_effort.lower() not in valid_efforts:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Invalid effort level '{finishing_effort}'. Valid: {', '.join(valid_efforts)}",
            )

        # Call core function
        result = core_race_recovery(race_distance, athlete_age, finishing_effort)
        return result

    except ValueError as e:
        return GuardrailsError(
            error_type="calculation_failed", message=f"Race recovery calculation failed: {e}"
        )
    except Exception as e:
        return GuardrailsError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def generate_illness_recovery_plan(
    illness_start_date: str,
    illness_end_date: str,
    severity: str = "moderate",
) -> Union[IllnessRecoveryPlan, GuardrailsError]:
    """
    Generate structured return-to-training plan after illness.

    Multi-sport context: Light cross-training (yoga, easy cycling) can resume
    before running during recovery phase.

    Conservative protocol: 1 day recovery per day sick (minimum).
    Monitor resting HR, fatigue levels, and symptoms before progression.

    Args:
        illness_start_date: Date illness began (ISO format "YYYY-MM-DD")
        illness_end_date: Date illness ended (ISO format "YYYY-MM-DD")
        severity: Illness severity ("mild", "moderate", "severe")

    Returns:
        IllnessRecoveryPlan on success, GuardrailsError on failure

    Examples:
        >>> generate_illness_recovery_plan("2026-01-10", "2026-01-15", "moderate")
        IllnessRecoveryPlan(illness_duration_days=5, full_training_resume_day=14, ...)

        >>> generate_illness_recovery_plan("2026-01-01", "2026-01-03", "mild")
        IllnessRecoveryPlan(severity="mild", estimated_ctl_drop=2.0, ...)
    """
    try:
        # Parse dates
        try:
            start_dt = dt_date.fromisoformat(illness_start_date)
            end_dt = dt_date.fromisoformat(illness_end_date)
        except ValueError:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Invalid date format. Use ISO format 'YYYY-MM-DD'",
            )

        # Validate date order
        if end_dt < start_dt:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"End date ({illness_end_date}) is before start date ({illness_start_date})",
            )

        # Calculate duration
        illness_duration = (end_dt - start_dt).days + 1  # +1 to include both start and end day

        if illness_duration > 60:
            return GuardrailsError(
                error_type="out_of_range",
                message=f"Illness duration exceeds 60 days. Consider medical consultation and full fitness rebuild.",
            )

        # Validate severity
        try:
            severity_enum = IllnessSeverity(severity.lower())
        except ValueError:
            return GuardrailsError(
                error_type="invalid_input",
                message=f"Invalid severity '{severity}'. Valid: mild, moderate, severe",
            )

        # Call core function
        result = core_illness_recovery(illness_duration, severity_enum)
        return result

    except ValueError as e:
        return GuardrailsError(
            error_type="calculation_failed", message=f"Illness recovery plan generation failed: {e}"
        )
    except Exception as e:
        return GuardrailsError(error_type="calculation_failed", message=f"Unexpected error: {e}")
