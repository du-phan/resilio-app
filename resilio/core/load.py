"""
M8 - Load Engine

Compute training loads using two-channel model (systemic + lower-body).
Applies sport-specific multipliers and workout-specific adjustments to
base effort (RPE × duration).

This module handles:
- Base effort calculation (RPE × duration_minutes)
- Sport multiplier application (13 canonical sport types)
- Multiplier adjustments (leg day, elevation, long duration, race effort)
- Session type classification (easy/moderate/quality/race)
- Load persistence to activity files

The two-channel model enables proper multi-sport training:
- Systemic load: Overall cardio/fatigue → feeds CTL/ATL/TSB/ACWR
- Lower-body load: Leg impact → gates quality/long runs
"""

from typing import Optional

from resilio.core.repository import RepositoryIO
from resilio.schemas.repository import RepoError
from resilio.schemas.activity import (
    LoadCalculation,
    NormalizedActivity,
    SessionType,
    SportType,
    SurfaceType,
)


# ============================================================
# ERROR TYPES
# ============================================================


class LoadCalculationError(Exception):
    """Base exception for load calculation errors."""

    pass


class InvalidLoadInputError(LoadCalculationError):
    """Input data is invalid or missing required fields."""

    pass


# ============================================================
# SPORT MULTIPLIERS
# ============================================================

# Default multipliers for each canonical sport type
# Format: (systemic_multiplier, lower_body_multiplier)
DEFAULT_MULTIPLIERS = {
    # Running variants
    SportType.RUN: (1.0, 1.0),  # Baseline
    SportType.TRAIL_RUN: (1.05, 1.10),  # More demanding
    SportType.TREADMILL_RUN: (1.0, 0.9),  # Less impact
    SportType.TRACK_RUN: (1.0, 1.0),  # Same as road
    # Cycling
    SportType.CYCLE: (0.85, 0.35),  # Low leg impact
    # Swimming
    SportType.SWIM: (0.70, 0.10),  # Minimal legs
    # Climbing
    SportType.CLIMB: (0.60, 0.10),  # Upper-body dominant
    # Strength
    SportType.STRENGTH: (0.55, 0.40),  # Adjustable by body focus
    # CrossFit
    SportType.CROSSFIT: (0.75, 0.55),  # Mixed intensity
    # Yoga
    SportType.YOGA: (0.35, 0.10),  # Low load
    # Hiking
    SportType.HIKE: (0.60, 0.50),  # Moderate legs
    # Walking
    SportType.WALK: (0.40, 0.30),  # Low intensity
    # Other/Unknown
    SportType.OTHER: (0.70, 0.30),  # Conservative default
}


# ============================================================
# CORE LOAD CALCULATION
# ============================================================


def compute_load(
    activity: NormalizedActivity,
    estimated_rpe: int,
    repo: Optional[RepositoryIO] = None,
) -> LoadCalculation:
    """
    Compute training load for an activity.

    Uses two-channel model:
    - Systemic load: RPE × duration × systemic_multiplier
    - Lower-body load: RPE × duration × lower_body_multiplier

    Args:
        activity: Normalized activity with all required fields
        estimated_rpe: RPE estimate from M7 (1-10 scale)
        repo: Repository I/O for persistence (optional)

    Returns:
        LoadCalculation with all computed values

    Raises:
        InvalidLoadInputError: If required fields missing or invalid
    """
    # Validate inputs
    if activity.duration_minutes <= 0:
        raise InvalidLoadInputError("duration_minutes must be positive")
    if not (1 <= estimated_rpe <= 10):
        raise InvalidLoadInputError(f"RPE must be 1-10, got {estimated_rpe}")

    # Calculate base effort using TSS formula
    base_effort_au = calculate_base_effort_tss(estimated_rpe, activity.duration_minutes)

    # Get sport multipliers
    systemic_mult, lower_body_mult = get_multipliers(
        sport_type=activity.sport_type,
        surface_type=activity.surface_type,
    )

    # Apply adjustments
    adjustments = []
    systemic_mult, lower_body_mult, adjustments = adjust_multipliers(
        activity=activity,
        systemic_mult=systemic_mult,
        lower_body_mult=lower_body_mult,
    )

    # Classify session type
    session_type = classify_session_type(
        rpe=estimated_rpe,
        workout_type=activity.workout_type,
    )

    # Apply interval adjustment if applicable
    base_effort_au, interval_note = adjust_tss_for_intervals(
        base_effort_au, session_type, activity
    )
    if interval_note != "No interval adjustment":
        adjustments.append(interval_note)

    # Calculate final loads (after interval adjustment)
    systemic_load_au = base_effort_au * systemic_mult
    lower_body_load_au = base_effort_au * lower_body_mult

    return LoadCalculation(
        activity_id=activity.id,
        duration_minutes=activity.duration_minutes,
        estimated_rpe=estimated_rpe,
        sport_type=activity.sport_type,
        surface_type=activity.surface_type or "unknown",
        base_effort_au=base_effort_au,
        systemic_multiplier=systemic_mult,
        lower_body_multiplier=lower_body_mult,
        multiplier_adjustments=adjustments,
        systemic_load_au=round(systemic_load_au, 1),
        lower_body_load_au=round(lower_body_load_au, 1),
        session_type=session_type,
    )


def calculate_base_effort_tss(rpe: int, duration_minutes: int) -> float:
    """
    Calculate base effort using TSS-equivalent formula.

    Formula: TSS = hours × IF² × 100
    Where IF is intensity factor derived from RPE, anchored to threshold (RPE 7-8).

    This replaces the previous RPE × duration formula which generated loads
    3-5x higher than sport science standards (TrainingPeaks/Coggan).

    References:
    - Coggan & Allen: Training Stress Score (TSS)
    - Foster et al. (2001): Session-RPE method
    - TrainingPeaks: TSS calculation standards

    Args:
        rpe: Rate of Perceived Exertion (1-10)
        duration_minutes: Activity duration in minutes

    Returns:
        TSS in arbitrary units (AU), matching TrainingPeaks standards

    Examples:
        >>> calculate_base_effort_tss(rpe=3, duration_minutes=60)
        42.3  # Easy hour ≈ 42 TSS

        >>> calculate_base_effort_tss(rpe=8, duration_minutes=60)
        100.0  # Threshold hour = 100 TSS
    """
    # RPE-to-IF mapping (anchored at lactate threshold = RPE 7-8)
    RPE_TO_IF = {
        1: 0.50,   # Recovery (Zone 1)
        2: 0.55,   # Very easy (Zone 1)
        3: 0.65,   # Easy (Zone 2)
        4: 0.75,   # Moderate easy (Zone 2)
        5: 0.82,   # Steady state (Zone 3 lower)
        6: 0.88,   # Tempo (Zone 3 upper)
        7: 0.95,   # Threshold (Zone 4 - LT)
        8: 1.00,   # Threshold high (Zone 4+)
        9: 1.05,   # VO2max intervals (Zone 5)
        10: 1.10,  # Max effort (Zone 5+)
    }

    intensity_factor = RPE_TO_IF.get(rpe, 0.70)  # Conservative default
    hours = duration_minutes / 60.0

    # Coggan's TSS formula: hours × IF² × 100
    tss = hours * (intensity_factor ** 2) * 100

    return round(tss, 1)


def adjust_tss_for_intervals(
    base_tss: float,
    session_type: SessionType,
    activity: NormalizedActivity,
) -> tuple[float, str]:
    """
    Adjust TSS for interval training to account for recovery periods.

    Traditional TSS calculation assumes continuous effort. Interval training
    and intermittent activities (like climbing) include recovery periods where
    intensity drops significantly, reducing the effective physiological stress.

    Args:
        base_tss: TSS calculated from RPE × duration
        session_type: EASY/MODERATE/QUALITY/RACE
        activity: Activity with name/description for interval detection

    Returns:
        Tuple of (adjusted_tss, explanation)

    Detection heuristics:
    - Keywords: "intervals", "repeats", "x", "reps", "@"
    - Session type: QUALITY or RACE with high RPE
    - Workout type: Strava structured workout flag
    """
    # Check for interval indicators
    text = f"{activity.name} {activity.description or ''}".lower()
    interval_keywords = ["interval", "repeat", "rep", "x ", "@ "]

    is_intervals = (
        any(kw in text for kw in interval_keywords)
        or activity.workout_type == 3  # Strava "workout" type
        or (session_type in [SessionType.QUALITY, SessionType.RACE])
    )

    if not is_intervals:
        return base_tss, "No interval adjustment"

    # Interval training typically has 1:1 to 2:1 work:rest ratio
    # Effective intensity is lower than peak RPE suggests
    # Conservative adjustment: -15% for intervals
    adjusted_tss = base_tss * 0.85

    return round(adjusted_tss, 1), "Interval training: -15% (work:rest recovery)"


def calculate_base_effort(rpe: int, duration_minutes: int) -> float:
    """
    Calculate base effort from RPE and duration.

    Formula: base_effort_au = RPE × duration_minutes

    Args:
        rpe: Rate of Perceived Exertion (1-10)
        duration_minutes: Activity duration in minutes

    Returns:
        Base effort in arbitrary units (AU)
    """
    return float(rpe * duration_minutes)


def get_multipliers(
    sport_type: str,
    surface_type: Optional[str] = None,
) -> tuple[float, float]:
    """
    Get sport-specific multipliers.

    Surface type can override running multipliers:
    - TREADMILL: Reduced lower-body impact (0.9 vs 1.0)
    - TRAIL: Increased both multipliers (1.05, 1.10)
    - TRACK: Standard running multipliers (1.0, 1.0)

    Args:
        sport_type: Canonical sport type from SportType enum
        surface_type: Optional surface type for running activities

    Returns:
        Tuple of (systemic_multiplier, lower_body_multiplier)
    """
    # Convert string to SportType enum for lookup
    # (sport_type is a string due to use_enum_values=True in schema)
    sport_enum = SportType(sport_type)

    # Get base multipliers for sport
    if sport_enum not in DEFAULT_MULTIPLIERS:
        # Fallback to OTHER if sport not found
        sport_enum = SportType.OTHER

    systemic, lower_body = DEFAULT_MULTIPLIERS[sport_enum]

    # Apply surface overrides for running
    if sport_enum == SportType.RUN and surface_type:
        if surface_type == SurfaceType.TREADMILL.value:
            lower_body = 0.9  # Reduced impact
        elif surface_type == SurfaceType.TRAIL.value:
            systemic = 1.05
            lower_body = 1.10  # More demanding
        elif surface_type == SurfaceType.TRACK.value:
            # Track uses standard running multipliers
            pass

    return systemic, lower_body


def adjust_multipliers(
    activity: NormalizedActivity,
    systemic_mult: float,
    lower_body_mult: float,
) -> tuple[float, float, list[str]]:
    """
    Apply workout-specific adjustments to multipliers.

    Adjustments:
    - Leg day (strength): +0.25 lower-body
    - Upper-body day (strength): -0.15 lower-body
    - High elevation: +0.05 systemic, +0.10 lower-body
    - Long duration (>120min): +0.05 systemic
    - Race effort: +0.10 systemic

    Args:
        activity: Normalized activity
        systemic_mult: Base systemic multiplier
        lower_body_mult: Base lower-body multiplier

    Returns:
        Tuple of (adjusted_systemic, adjusted_lower_body, adjustment_reasons)
    """
    adjustments = []

    # Strength training body focus detection
    if activity.sport_type == SportType.STRENGTH.value:
        description_lower = (activity.description or "").lower()
        name_lower = activity.name.lower()
        combined_text = f"{name_lower} {description_lower}"

        # Leg day keywords
        leg_keywords = ["leg", "squat", "deadlift", "lunge", "lower body"]
        if any(kw in combined_text for kw in leg_keywords):
            lower_body_mult += 0.25
            adjustments.append("Leg-focused strength: +0.25 lower-body")

        # Upper-body keywords
        upper_keywords = ["upper body", "bench", "pull-up", "shoulder", "chest", "back"]
        if any(kw in combined_text for kw in upper_keywords):
            lower_body_mult = max(0.15, lower_body_mult - 0.15)
            adjustments.append("Upper-body strength: -0.15 lower-body")

    # High elevation adjustment
    if activity.elevation_gain_m and activity.distance_meters:
        gradient = activity.elevation_gain_m / (activity.distance_meters / 1000)
        if gradient > 30:  # >30m elevation per km
            systemic_mult += 0.05
            lower_body_mult += 0.10
            adjustments.append(
                f"High elevation ({int(gradient)}m/km): +0.05 systemic, +0.10 lower-body"
            )

    # Long duration adjustment
    if activity.duration_minutes > 120:
        systemic_mult += 0.05
        adjustments.append("Long duration (>120min): +0.05 systemic")

    # Race effort adjustment
    if activity.workout_type == 1:  # Strava race type
        systemic_mult += 0.10
        adjustments.append("Race effort: +0.10 systemic")

    return systemic_mult, lower_body_mult, adjustments


def classify_session_type(
    rpe: int,
    workout_type: Optional[int] = None,
) -> SessionType:
    """
    Classify session type based on RPE and workout type.

    Classification:
    - RPE 1-4: EASY (recovery, zone 1-2)
    - RPE 5-6: MODERATE (steady-state, zone 3)
    - RPE 7-8: QUALITY (tempo, intervals, threshold)
    - RPE 9-10: RACE (competition)
    - workout_type=1: Always RACE (overrides RPE)

    Args:
        rpe: Rate of Perceived Exertion (1-10)
        workout_type: Optional Strava workout type (1=race)

    Returns:
        SessionType enum value
    """
    # Race flag always wins
    if workout_type == 1:
        return SessionType.RACE

    # Classify by RPE
    if rpe <= 4:
        return SessionType.EASY
    elif rpe <= 6:
        return SessionType.MODERATE
    elif rpe <= 8:
        return SessionType.QUALITY
    else:
        return SessionType.RACE


# ============================================================
# BATCH OPERATIONS
# ============================================================


def compute_loads_batch(
    activities: list[tuple[NormalizedActivity, int]],
    repo: Optional[RepositoryIO] = None,
) -> list[LoadCalculation]:
    """
    Compute loads for multiple activities.

    Args:
        activities: List of (activity, estimated_rpe) tuples
        repo: Repository I/O for persistence (optional)

    Returns:
        List of LoadCalculation objects
    """
    results = []
    for activity, rpe in activities:
        try:
            load = compute_load(activity, rpe, repo)
            results.append(load)
        except LoadCalculationError:
            # Skip activities with invalid data
            continue

    return results


# ============================================================
# PERSISTENCE
# ============================================================


def persist_load_to_activity(
    activity_path: str,
    load: LoadCalculation,
    repo: RepositoryIO,
) -> None:
    """
    Update activity file with calculated load fields.

    Adds 'calculated' section to activity YAML with all load values.

    Args:
        activity_path: Path to activity file
        load: Calculated load values
        repo: Repository I/O instance

    Raises:
        LoadCalculationError: If file update fails
    """
    # Read existing activity
    activity = repo.read_yaml(activity_path, NormalizedActivity)
    if isinstance(activity, (Exception, RepoError)):
        raise LoadCalculationError(f"Failed to read activity: {activity}")

    # Create updated activity with calculated fields
    # Note: We update the internal dict to add the calculated section
    # This preserves all original fields while adding load data
    activity_dict = activity.model_dump(mode="json")
    activity_dict["calculated"] = {
        "estimated_rpe": load.estimated_rpe,
        "base_effort_au": load.base_effort_au,
        "systemic_multiplier": load.systemic_multiplier,
        "lower_body_multiplier": load.lower_body_multiplier,
        "systemic_load_au": load.systemic_load_au,
        "lower_body_load_au": load.lower_body_load_au,
        "session_type": load.session_type.value,
        "multiplier_adjustments": load.multiplier_adjustments,
    }

    # Re-create activity with calculated fields
    updated_activity = NormalizedActivity(**activity_dict)

    # Write back atomically
    result = repo.write_yaml(activity_path, updated_activity)
    if result is not None:
        raise LoadCalculationError(f"Failed to write activity: {result.message}")


# ============================================================
# VALIDATION
# ============================================================


def validate_load(load: LoadCalculation) -> list[str]:
    """
    Validate calculated load values.

    Checks:
    - Loads are non-negative
    - Multipliers in reasonable ranges
    - Session type matches RPE

    Args:
        load: Calculated load to validate

    Returns:
        List of warning messages (empty if all checks pass)
    """
    warnings = []

    # Load validation
    if load.systemic_load_au < 0:
        warnings.append("Systemic load is negative")
    if load.lower_body_load_au < 0:
        warnings.append("Lower-body load is negative")

    # Multiplier validation
    if load.systemic_multiplier < 0 or load.systemic_multiplier > 2.0:
        warnings.append(
            f"Systemic multiplier outside expected range: {load.systemic_multiplier}"
        )
    if load.lower_body_multiplier < 0 or load.lower_body_multiplier > 2.0:
        warnings.append(
            f"Lower-body multiplier outside expected range: {load.lower_body_multiplier}"
        )

    # Session type consistency
    if load.session_type == SessionType.EASY and load.estimated_rpe > 4:
        warnings.append("Session marked EASY but RPE > 4")
    if load.session_type == SessionType.RACE and load.estimated_rpe < 7:
        warnings.append("Session marked RACE but RPE < 7")

    return warnings
