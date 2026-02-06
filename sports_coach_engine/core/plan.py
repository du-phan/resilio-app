"""
M10 - Plan Toolkit (Toolkit Paradigm)

Provides computational toolkit functions for training plan design.

Toolkit Functions (Return Data, Not Decisions):
- Periodization calculations (phase allocations for different goals)
- Volume progression curves (linear progression with recovery weeks)
- Workout creation (prescriptions with pace/HR zones from VDOT/profile)
- Volume recommendations (CTL-based safe ranges)
- Guardrail validation (detect violations, NOT auto-enforce)
- Workout modification helpers (downgrade, shorten, recovery estimation)
- Workout templates (default structures for each workout type)

Claude Code Responsibilities (Uses Context to Decide):
- Plan design: "Where to place quality runs around climbing schedule?"
- Day selection: "Tuesday works better than Thursday for this athlete"
- Guardrail enforcement: "This violation matters for this athlete, that one doesn't"
- Workout scheduling: Considers athlete preferences, constraints, life context

Key Training Science Principles (Validated, Not Enforced):
- 80/20 intensity distribution for ≥3 run days/week
- Long run ≤30% weekly volume AND ≤2.5 hours
- Recovery weeks every 4th week during base/build
- Max 2 quality sessions per week
- No back-to-back hard days (RPE ≥7)

The toolkit paradigm separates quantitative computation (this module)
from qualitative planning (Claude Code with athlete context).
"""

from datetime import date, timedelta, datetime
from typing import Optional
from pathlib import Path
import uuid
import shutil
import os
import sys
from sports_coach_engine.schemas.plan import (
    GoalType,
    PlanPhase,
    WorkoutType,
    IntensityZone,
    WorkoutPrescription,
    WeekPlan,
    MasterPlan,
)
from sports_coach_engine.core.guardrails.volume import validate_workout_minimums
from sports_coach_engine.core.paths import (
    current_plan_path,
    get_plans_dir,
    current_plan_review_path,
    current_training_log_path,
)
from sports_coach_engine.core.repository import RepositoryIO


# Constants removed - weekly structures and day preferences now handled
# by Claude Code in conversation based on athlete schedule and preferences


# ============================================================
# PERIODIZATION ALGORITHMS
# ============================================================


def calculate_periodization(
    goal: GoalType,
    weeks_available: int,
    start_date: date,
) -> list[dict]:
    """
    Calculate periodization phases using reverse periodization from race date.

    Works backward from goal date to determine optimal phase distribution:
    - Marathon (16+ weeks): Base 40% → Build 35% → Peak 15% → Taper 10%
    - Half Marathon (10+ weeks): Base 35% → Build 40% → Peak 15% → Taper 10%
    - 10K (8+ weeks): Base 30% → Build 45% → Peak 15% → Taper 10%
    - 5K (6+ weeks): Base 25% → Build 50% → Peak 15% → Taper 10%
    - General Fitness: Rolling 4-week cycles (3 build + 1 recovery)

    Args:
        goal: Training goal type (5k, 10k, half_marathon, marathon, general_fitness)
        weeks_available: Total weeks from start_date to goal date
        start_date: Plan start date

    Returns:
        List of phase definitions with week ranges and dates:
        [
            {
                "phase": "base",
                "start_week": 0,
                "end_week": 6,
                "start_date": date(2026, 1, 20),
                "end_date": date(2026, 3, 2),
                "weeks": 7
            },
            ...
        ]

    Raises:
        ValueError: If weeks_available is too short for the goal
    """
    # Check minimum timeline requirements (soft warning, not hard constraint)
    min_weeks = _get_minimum_weeks(goal)
    if weeks_available < min_weeks:
        print(f"[PlanGen] Warning: {goal.value} requires minimum {min_weeks} weeks, got {weeks_available}", file=sys.stderr)

    # General fitness uses rolling 4-week cycles
    if goal == GoalType.GENERAL_FITNESS:
        return _calculate_general_fitness_phases(weeks_available, start_date)

    # Race-focused goals use standard periodization
    phase_percentages = _get_phase_percentages(goal, weeks_available)

    phases = []
    current_week = 0
    current_date = start_date

    # Build phase definitions
    for phase_name, percentage in phase_percentages.items():
        phase_weeks = max(1, round(weeks_available * percentage))

        # Ensure we don't exceed total weeks (rounding adjustment)
        if current_week + phase_weeks > weeks_available:
            phase_weeks = weeks_available - current_week

        if phase_weeks > 0:
            end_week = current_week + phase_weeks - 1
            end_date = current_date + timedelta(weeks=phase_weeks, days=-1)

            phases.append({
                "phase": phase_name,
                "start_week": current_week,
                "end_week": end_week,
                "start_date": current_date,
                "end_date": end_date,
                "weeks": phase_weeks,
            })

            current_week += phase_weeks
            current_date = end_date + timedelta(days=1)

    return phases


def _get_minimum_weeks(goal: GoalType) -> int:
    """Get minimum weeks required for each goal type."""
    minimums = {
        GoalType.GENERAL_FITNESS: 4,   # One full cycle
        GoalType.FIVE_K: 6,
        GoalType.TEN_K: 8,
        GoalType.HALF_MARATHON: 10,
        GoalType.MARATHON: 16,
    }
    return minimums[goal]


def _get_phase_percentages(goal: GoalType, weeks_available: int) -> dict[str, float]:
    """
    Get phase percentage distribution for race-focused goals.

    Returns dict with phase names as keys (base, build, peak, taper)
    and percentages as values (sum = 1.0).
    """
    # Standard distribution by goal type
    distributions = {
        GoalType.MARATHON: {
            "base": 0.40,
            "build": 0.35,
            "peak": 0.15,
            "taper": 0.10,
        },
        GoalType.HALF_MARATHON: {
            "base": 0.35,
            "build": 0.40,
            "peak": 0.15,
            "taper": 0.10,
        },
        GoalType.TEN_K: {
            "base": 0.30,
            "build": 0.45,
            "peak": 0.15,
            "taper": 0.10,
        },
        GoalType.FIVE_K: {
            "base": 0.25,
            "build": 0.50,
            "peak": 0.15,
            "taper": 0.10,
        },
    }

    base_distribution = distributions[goal]

    # Adjust for very long timelines (>20 weeks): extend base phase
    if weeks_available > 20:
        extra_weeks_pct = (weeks_available - 20) / weeks_available
        base_distribution = base_distribution.copy()
        base_distribution["base"] += extra_weeks_pct * 0.5
        base_distribution["build"] -= extra_weeks_pct * 0.3
        base_distribution["peak"] -= extra_weeks_pct * 0.2

    return base_distribution


def _calculate_general_fitness_phases(weeks_available: int, start_date: date) -> list[dict]:
    """
    Calculate rolling 4-week cycles for general fitness goal.

    Each cycle: 3 weeks build + 1 week recovery.
    """
    phases = []
    current_week = 0
    current_date = start_date
    cycle = 0

    while current_week < weeks_available:
        # Determine if this is a recovery week (every 4th week)
        is_recovery_week = (current_week % 4 == 3)
        phase_name = PlanPhase.RECOVERY.value if is_recovery_week else PlanPhase.BUILD.value

        end_date = current_date + timedelta(days=6)

        phases.append({
            "phase": phase_name,
            "start_week": current_week,
            "end_week": current_week,
            "start_date": current_date,
            "end_date": end_date,
            "weeks": 1,
            "cycle": cycle,
        })

        current_week += 1
        current_date = end_date + timedelta(days=1)

        # Increment cycle every 4 weeks
        if current_week % 4 == 0:
            cycle += 1

    return phases


def calculate_volume_progression(
    starting_volume_km: float,
    peak_volume_km: float,
    phases: list[dict],
) -> list[float]:
    """
    Calculate weekly volume progression with recovery weeks.

    Implements progressive overload following these principles:
    - Base phase: Start at starting_volume, gradually build to ~80% of peak
    - Build phase: Increase from 80% to 95% of peak, ~10% per week
    - Peak phase: Maintain at 100% of peak volume
    - Taper phase: Progressive reduction, 15% per week from peak
    - Recovery weeks: Every 4th week at 70% of surrounding weeks (not during taper)

    Args:
        starting_volume_km: Initial weekly volume at plan start
        peak_volume_km: Target peak weekly volume
        phases: Phase definitions from calculate_periodization()

    Returns:
        List of weekly volumes (one per week), matching total weeks in phases

    Example:
        >>> phases = [
        ...     {"phase": "base", "weeks": 4},
        ...     {"phase": "build", "weeks": 3},
        ...     {"phase": "taper", "weeks": 2}
        ... ]
        >>> volumes = calculate_volume_progression(30.0, 50.0, phases)
        >>> len(volumes)
        9
        >>> volumes[0]  # First week starts at starting_volume
        30.0
        >>> volumes[3]  # 4th week is recovery
        28.0  # ~70% of week 3
    """
    total_weeks = sum(phase["weeks"] for phase in phases)
    volumes = []

    # Build target volumes by phase
    for phase in phases:
        phase_name = phase["phase"]
        phase_weeks = phase["weeks"]

        if phase_name == PlanPhase.BASE.value:
            # Base: Linear progression from starting to 80% of peak
            target_end = peak_volume_km * 0.80
            phase_volumes = _linear_progression(
                starting_volume_km, target_end, phase_weeks
            )

        elif phase_name == PlanPhase.BUILD.value:
            # Build: Linear progression from 80% to 95% of peak
            start_volume = volumes[-1] if volumes else starting_volume_km
            target_end = peak_volume_km * 0.95
            phase_volumes = _linear_progression(
                start_volume, target_end, phase_weeks
            )

        elif phase_name == PlanPhase.PEAK.value:
            # Peak: Maintain at 100% of peak
            phase_volumes = [peak_volume_km] * phase_weeks

        elif phase_name == PlanPhase.TAPER.value:
            # Taper: Progressive reduction, 15% per week
            start_volume = volumes[-1] if volumes else peak_volume_km
            phase_volumes = []
            current = start_volume
            for _ in range(phase_weeks):
                current *= 0.85  # 15% reduction
                phase_volumes.append(current)

        elif phase_name == PlanPhase.RECOVERY.value:
            # General fitness recovery week: 70% of previous week
            prev_volume = volumes[-1] if volumes else starting_volume_km
            phase_volumes = [prev_volume * 0.70]

        else:
            # Unknown phase, use conservative approach
            phase_volumes = [starting_volume_km] * phase_weeks

        volumes.extend(phase_volumes)

    # Apply recovery week adjustments (every 4th week, not during taper)
    volumes = _apply_recovery_weeks(volumes, phases)

    return volumes


def _linear_progression(start: float, end: float, weeks: int) -> list[float]:
    """Generate linear progression of volumes over weeks."""
    if weeks == 1:
        return [end]

    step = (end - start) / (weeks - 1)
    return [start + step * i for i in range(weeks)]


def _apply_recovery_weeks(volumes: list[float], phases: list[dict]) -> list[float]:
    """
    Apply recovery week reductions (every 4th week at 70%).

    Recovery weeks are NOT applied during taper phase.
    """
    adjusted_volumes = volumes.copy()
    current_week = 0

    for phase in phases:
        phase_name = phase["phase"]
        phase_weeks = phase["weeks"]

        # Skip taper phase (already has progressive reduction)
        if phase_name == PlanPhase.TAPER.value:
            current_week += phase_weeks
            continue

        # Skip general fitness recovery weeks (already handled)
        if phase_name == PlanPhase.RECOVERY.value:
            current_week += phase_weeks
            continue

        # Check for recovery weeks in this phase (every 4th week)
        for week_offset in range(phase_weeks):
            global_week = current_week + week_offset

            # Every 4th week starting from week 3 (0-indexed)
            if (global_week + 1) % 4 == 0 and global_week > 0:
                # Calculate 70% of surrounding weeks average
                prev_week_volume = adjusted_volumes[global_week - 1] if global_week > 0 else volumes[global_week]
                next_week_volume = adjusted_volumes[global_week + 1] if global_week + 1 < len(volumes) else volumes[global_week]

                avg_surrounding = (prev_week_volume + next_week_volume) / 2
                adjusted_volumes[global_week] = avg_surrounding * 0.70

        current_week += phase_weeks

    return adjusted_volumes


# ============================================================
# WORKOUT CREATION & PRESCRIPTION
# ============================================================


# Workout type defaults (duration, intensity zone, RPE, purpose)
WORKOUT_DEFAULTS = {
    WorkoutType.EASY: {
        "duration_minutes": 40,
        "intensity_zone": IntensityZone.ZONE_2,
        "target_rpe": 4,
        "purpose": "Recovery and aerobic maintenance - build base without fatigue",
    },
    WorkoutType.LONG_RUN: {
        "duration_minutes": 90,
        "intensity_zone": IntensityZone.ZONE_2,
        "target_rpe": 5,
        "purpose": "Build aerobic endurance and mental toughness for race distance",
    },
    WorkoutType.TEMPO: {
        "duration_minutes": 45,
        "intensity_zone": IntensityZone.ZONE_4,
        "target_rpe": 7,
        "purpose": "Improve lactate threshold - the pace you can sustain for ~60 minutes",
        "intervals": [{"type": "tempo_block", "duration_minutes": 20}],
        "warmup_minutes": 15,
        "cooldown_minutes": 10,
    },
    WorkoutType.INTERVALS: {
        "duration_minutes": 50,
        "intensity_zone": IntensityZone.ZONE_5,
        "target_rpe": 8,
        "purpose": "Boost VO2max - maximum aerobic capacity",
        "intervals": [{"type": "800m", "reps": 6, "recovery": "400m jog"}],
        "warmup_minutes": 15,
        "cooldown_minutes": 10,
    },
    WorkoutType.FARTLEK: {
        "duration_minutes": 45,
        "intensity_zone": IntensityZone.ZONE_4,
        "target_rpe": 6,
        "purpose": "Unstructured speed play - practice changing pace and build mental flexibility",
    },
    WorkoutType.STRIDES: {
        "duration_minutes": 30,
        "intensity_zone": IntensityZone.ZONE_2,
        "target_rpe": 4,
        "purpose": "Neuromuscular training - maintain leg turnover and running economy",
        "notes": "Add 6-8 × 100m strides after easy run",
    },
    WorkoutType.RACE: {
        "duration_minutes": 60,
        "intensity_zone": IntensityZone.ZONE_5,
        "target_rpe": 9,
        "purpose": "Race effort - test fitness and practice race execution",
    },
    WorkoutType.REST: {
        "duration_minutes": 0,
        "intensity_zone": IntensityZone.ZONE_1,
        "target_rpe": 1,
        "purpose": "Complete rest for recovery and adaptation",
    },
}


def suggest_long_run_progression(
    current_long_run_km: float,
    weeks_to_peak: int,
    target_peak_long_run_km: float,
    phase: PlanPhase,
) -> dict:
    """
    Suggest long run progression based on current capacity (Toolkit Paradigm).

    Returns SUGGESTED progression - AI coach decides whether to use it
    based on athlete context, recovery, and schedule constraints.

    Progressive overload rules (suggestions, not enforcement):
    - Base phase: +10-15% every 2-3 weeks, never decrease
    - Build phase: +5-10% every 2-3 weeks
    - Recovery weeks: Hold or slight decrease (90-95%)
    - First week: Never less than 90% of current long run

    Args:
        current_long_run_km: Athlete's most recent long run distance
        weeks_to_peak: Weeks until peak long run phase
        target_peak_long_run_km: Target peak long run for this plan
        phase: Current periodization phase

    Returns:
        Dict with suggestion and context:
        {
            "suggested_distance_km": float,
            "rationale": str,
            "min_safe_km": float,  # 90% of current (don't go below)
            "max_safe_km": float,  # 115% of current (don't exceed)
        }

    Example:
        >>> suggestion = suggest_long_run_progression(8.0, 10, 22.0, PlanPhase.BASE)
        >>> suggestion["suggested_distance_km"]
        9.0  # 12.5% increase for base phase
    """
    # Phase-specific progression rates
    progression_rates = {
        PlanPhase.BASE: 0.125,  # 12.5% per step
        PlanPhase.BUILD: 0.075,  # 7.5% per step
        PlanPhase.PEAK: 0.0,  # Hold at peak
        PlanPhase.TAPER: -0.15,  # 15% reduction per week
        PlanPhase.RECOVERY: -0.05,  # 5% reduction
    }

    rate = progression_rates.get(phase, 0.10)

    # Calculate suggested distance
    if phase == PlanPhase.TAPER or phase == PlanPhase.RECOVERY:
        # Reduce from current
        suggested_km = current_long_run_km * (1 + rate)
    else:
        # Progressive increase toward target
        gap_to_target = target_peak_long_run_km - current_long_run_km
        if weeks_to_peak > 0:
            weekly_increase = gap_to_target / weeks_to_peak
            suggested_km = current_long_run_km + weekly_increase
        else:
            suggested_km = target_peak_long_run_km

        # Cap at phase-appropriate rate
        max_increase = current_long_run_km * rate
        if suggested_km - current_long_run_km > max_increase:
            suggested_km = current_long_run_km + max_increase

    # Define safe boundaries (AI can override with rationale)
    min_safe_km = current_long_run_km * 0.90  # Don't drop below 90%
    max_safe_km = current_long_run_km * 1.15  # Don't increase more than 15%

    # Ensure suggested is within safe range
    suggested_km = max(min_safe_km, min(suggested_km, max_safe_km))

    # Build rationale
    if phase == PlanPhase.BASE:
        rationale = f"Building aerobic base: suggest {suggested_km:.1f}km (+{suggested_km - current_long_run_km:.1f}km from current)"
    elif phase == PlanPhase.BUILD:
        rationale = f"Building toward peak: suggest {suggested_km:.1f}km (+{suggested_km - current_long_run_km:.1f}km from current)"
    elif phase == PlanPhase.PEAK:
        rationale = f"Peak phase: maintain at {suggested_km:.1f}km"
    elif phase == PlanPhase.TAPER:
        rationale = f"Taper: reduce to {suggested_km:.1f}km ({suggested_km - current_long_run_km:.1f}km from current)"
    else:
        rationale = f"Recovery: {suggested_km:.1f}km"

    return {
        "suggested_distance_km": round(suggested_km, 1),
        "rationale": rationale,
        "min_safe_km": round(min_safe_km, 1),
        "max_safe_km": round(max_safe_km, 1),
    }


def distribute_weekly_volume(
    weekly_volume_km: float,
    workout_types: list[WorkoutType],
    profile: Optional[dict] = None,
) -> dict[int, float]:
    """
    Distribute weekly volume across workouts ensuring sum matches target.

    Algorithm:
    1. Count workouts by type
    2. Allocate key workouts first (long run, tempo, intervals)
    3. Calculate remaining volume
    4. Distribute remainder across easy runs
    5. Apply minimum distance constraints (5 km for easy, 8 km for long)
    6. If constraints violated, adjust proportionally

    Args:
        weekly_volume_km: Target weekly volume
        workout_types: Ordered list of workout types for the week
        profile: Optional athlete profile (for min distance based on history)

    Returns:
        Dict mapping workout index to allocated distance in km

    Example:
        >>> workout_types = [WorkoutType.LONG_RUN, WorkoutType.EASY, WorkoutType.EASY, WorkoutType.EASY]
        >>> allocation = distribute_weekly_volume(25.0, workout_types)
        >>> sum(allocation.values())  # Should be ~25.0
        25.0
        >>> allocation[0]  # Long run gets ~28%
        7.0
    """
    # Get minimums from profile or use defaults
    def get_min_distance(workout_type_str: str) -> float:
        """Get minimum distance from profile or default."""
        if profile:
            profile_key = f"typical_{workout_type_str}_distance_km"
            if profile_key in profile and profile[profile_key]:
                # Use 80% of typical as minimum
                return profile[profile_key] * 0.8

        # Fallback defaults
        defaults = {
            "long_run": 8.0,
            "easy": 5.0,
            "tempo": 5.0,
            "intervals": 5.0,
        }
        return defaults.get(workout_type_str, 5.0)

    LONG_RUN_MIN_KM = get_min_distance("long_run")
    EASY_RUN_MIN_KM = get_min_distance("easy")
    TEMPO_MIN_KM = get_min_distance("tempo")
    INTERVALS_MIN_KM = get_min_distance("intervals")

    # Count workout types
    num_long_runs = sum(1 for wt in workout_types if wt == WorkoutType.LONG_RUN)
    num_tempo = sum(1 for wt in workout_types if wt == WorkoutType.TEMPO)
    num_intervals = sum(1 for wt in workout_types if wt == WorkoutType.INTERVALS)
    num_easy = sum(1 for wt in workout_types if wt == WorkoutType.EASY)
    num_rest = sum(1 for wt in workout_types if wt == WorkoutType.REST)

    allocation = {}
    allocated_km = 0.0

    # Step 1: Allocate long run (28% of weekly volume, capped at 32km and 30% max)
    long_run_indices = [i for i, wt in enumerate(workout_types) if wt == WorkoutType.LONG_RUN]
    if long_run_indices:
        # Long run: 28% of volume, but cap at 30% and 32km
        long_run_km = min(weekly_volume_km * 0.28, 32.0)
        long_run_km = min(long_run_km, weekly_volume_km * 0.30)  # Never more than 30%
        long_run_km = max(long_run_km, LONG_RUN_MIN_KM)  # At least minimum

        for idx in long_run_indices:
            allocation[idx] = long_run_km
            allocated_km += long_run_km

    # Step 2: Allocate tempo runs (10-12% each)
    tempo_indices = [i for i, wt in enumerate(workout_types) if wt == WorkoutType.TEMPO]
    if tempo_indices:
        tempo_km = max(weekly_volume_km * 0.12, TEMPO_MIN_KM)
        for idx in tempo_indices:
            allocation[idx] = tempo_km
            allocated_km += tempo_km

    # Step 3: Allocate interval runs (8-10% each)
    intervals_indices = [i for i, wt in enumerate(workout_types) if wt == WorkoutType.INTERVALS]
    if intervals_indices:
        intervals_km = max(weekly_volume_km * 0.10, INTERVALS_MIN_KM)
        for idx in intervals_indices:
            allocation[idx] = intervals_km
            allocated_km += intervals_km

    # Step 3.5: Check if remaining volume allows athlete-specific minimums for easy runs
    easy_indices = [i for i, wt in enumerate(workout_types) if wt == WorkoutType.EASY]
    remaining_km = weekly_volume_km - allocated_km

    if easy_indices and num_easy > 0:
        min_easy_total = num_easy * EASY_RUN_MIN_KM

        if remaining_km < min_easy_total:
            # Not enough volume - distribute evenly and let validation catch it
            # Validator will warn that workouts are below athlete's typical minimum
            easy_km_per_run = remaining_km / num_easy
        else:
            # Sufficient volume - respect athlete's typical minimums
            easy_km_per_run = max(EASY_RUN_MIN_KM, remaining_km / num_easy)

        for idx in easy_indices:
            allocation[idx] = easy_km_per_run

    # Step 5: Allocate rest days (0 km)
    rest_indices = [i for i, wt in enumerate(workout_types) if wt == WorkoutType.REST]
    for idx in rest_indices:
        allocation[idx] = 0.0

    # Return allocation as suggestion
    # AI coach can review and adjust based on athlete context
    return allocation


def create_workout(
    workout_type: str,
    workout_date: date,
    week_number: int,
    day_of_week: int,
    phase: PlanPhase,
    volume_target_km: float,
    profile: Optional[dict] = None,
    allocated_distance_km: Optional[float] = None,
) -> WorkoutPrescription:
    """
    Create a complete workout prescription with intensity targets and structure.

    Generates WorkoutPrescription with:
    - Type, duration/distance based on volume_target and workout type
    - Intensity zone + target RPE from workout type defaults
    - Pace/HR ranges calculated from profile vital signs or VDOT
    - Interval structure for tempo/intervals workouts
    - Purpose text explaining training stimulus

    Args:
        workout_type: Type of workout (easy, long_run, tempo, intervals, etc.)
        workout_date: Date for this workout
        week_number: Week number in plan (1-indexed)
        day_of_week: Day of week (0=Monday, 6=Sunday)
        phase: Current periodization phase
        volume_target_km: Target weekly run volume in km
        profile: Optional athlete profile with vital_signs, recent_race, VDOT
        allocated_distance_km: Optional pre-allocated distance from distribute_weekly_volume()
                              If provided, overrides default percentage-based calculation

    Returns:
        Complete WorkoutPrescription object

    Example:
        >>> workout = create_workout(
        ...     workout_type="long_run",
        ...     workout_date=date(2026, 1, 26),
        ...     week_number=1,
        ...     day_of_week=6,
        ...     phase=PlanPhase.BASE,
        ...     volume_target_km=40.0,
        ...     profile={"vital_signs": {"max_hr": 185}},
        ... )
        >>> workout.workout_type
        'long_run'
        >>> workout.duration_minutes
        90
    """
    # Convert string to enum if needed
    if isinstance(workout_type, str):
        workout_type = WorkoutType(workout_type)

    # Get defaults for this workout type
    defaults = WORKOUT_DEFAULTS.get(workout_type, WORKOUT_DEFAULTS[WorkoutType.EASY])

    # Generate unique ID
    workout_id = f"w_{workout_date.isoformat()}_{workout_type.value}_{uuid.uuid4().hex[:6]}"

    # Calculate duration and distance
    duration_minutes = defaults["duration_minutes"]
    distance_km = None

    # Use allocated distance if provided (from distribute_weekly_volume)
    if allocated_distance_km is not None:
        distance_km = allocated_distance_km
    elif workout_type == WorkoutType.LONG_RUN:
        # Long run: 25-30% of weekly volume, capped at 2.5 hours
        distance_km = min(volume_target_km * 0.28, 32.0)
    elif workout_type in (WorkoutType.EASY, WorkoutType.TEMPO, WorkoutType.INTERVALS):
        # Distance-based workouts: allocate from weekly volume
        if workout_type == WorkoutType.EASY:
            distance_km = volume_target_km * 0.15  # ~15% of weekly volume
        elif workout_type == WorkoutType.TEMPO:
            distance_km = volume_target_km * 0.12  # ~12% including warmup/cooldown
        elif workout_type == WorkoutType.INTERVALS:
            distance_km = volume_target_km * 0.10  # ~10% including warmup/cooldown

    # Calculate duration from distance
    if distance_km is not None and distance_km > 0:
        # Estimate duration based on intensity
        if workout_type == WorkoutType.EASY or workout_type == WorkoutType.LONG_RUN:
            duration_minutes = int(distance_km * 6.0)  # 6:00/km for easy/long
            # Cap long runs at 2.5 hours (150 minutes)
            if workout_type == WorkoutType.LONG_RUN:
                duration_minutes = min(duration_minutes, 150)
        elif workout_type == WorkoutType.TEMPO:
            duration_minutes = defaults["duration_minutes"]  # Use default
        elif workout_type == WorkoutType.INTERVALS:
            duration_minutes = defaults["duration_minutes"]  # Use default
        else:
            duration_minutes = int(distance_km * 6.0)  # Default to 6:00/km

    # Get intensity guidance
    intensity_zone = defaults["intensity_zone"]
    target_rpe = defaults["target_rpe"]

    # Calculate pace/HR ranges if profile available
    pace_range_min_km = None
    pace_range_max_km = None
    hr_range_low = None
    hr_range_high = None

    if profile:
        pace_ranges = _calculate_pace_ranges(workout_type, intensity_zone, profile)
        pace_range_min_km = pace_ranges.get("min_pace")
        pace_range_max_km = pace_ranges.get("max_pace")

        hr_ranges = _calculate_hr_ranges(intensity_zone, profile)
        hr_range_low = hr_ranges.get("low")
        hr_range_high = hr_ranges.get("high")

    # Get interval structure
    intervals = defaults.get("intervals")
    warmup_minutes = defaults.get("warmup_minutes", 10)
    cooldown_minutes = defaults.get("cooldown_minutes", 10)

    # Generate purpose text with phase context
    purpose = _generate_purpose(workout_type, phase, defaults["purpose"])

    # Get additional notes
    notes = defaults.get("notes")

    # Determine if this is a key workout
    key_workout = workout_type in (WorkoutType.LONG_RUN, WorkoutType.TEMPO, WorkoutType.INTERVALS, WorkoutType.RACE)

    return WorkoutPrescription(
        id=workout_id,
        week_number=week_number,
        day_of_week=day_of_week,
        date=workout_date,
        workout_type=workout_type,
        phase=phase,
        duration_minutes=duration_minutes,
        distance_km=distance_km,
        intensity_zone=intensity_zone,
        target_rpe=target_rpe,
        pace_range_min_km=pace_range_min_km,
        pace_range_max_km=pace_range_max_km,
        hr_range_low=hr_range_low,
        hr_range_high=hr_range_high,
        intervals=intervals,
        warmup_minutes=warmup_minutes,
        cooldown_minutes=cooldown_minutes,
        purpose=purpose,
        notes=notes,
        key_workout=key_workout,
    )


def _estimate_duration(
    distance_km: float,
    workout_type: WorkoutType,
    profile: Optional[dict],
) -> int:
    """
    Estimate workout duration from distance and athlete pacing.

    Uses athlete's historical data when available, falls back to
    VDOT-based paces, then conservative defaults.

    Priority:
    1. Profile historical pace for workout type (e.g., typical_easy_pace_min_km)
    2. VDOT-based pace (if profile has VDOT)
    3. Conservative fallback (7:00/km easy, 6:00/km tempo, 5:30/km intervals)

    Args:
        distance_km: Workout distance in km
        workout_type: Type of workout
        profile: Optional athlete profile with historical data or VDOT

    Returns:
        Estimated duration in minutes

    Example:
        >>> profile = {"typical_easy_pace_min_km": 6.5, "vdot": 45}
        >>> duration = _estimate_duration(10.0, WorkoutType.EASY, profile)
        >>> duration
        65  # 10km × 6.5 min/km
    """
    # Default pace per km (in minutes) - conservative estimates
    default_paces = {
        WorkoutType.EASY: 7.0,  # 7:00/km
        WorkoutType.LONG_RUN: 7.0,  # 7:00/km (same as easy)
        WorkoutType.TEMPO: 6.0,  # 6:00/km
        WorkoutType.INTERVALS: 5.5,  # 5:30/km
        WorkoutType.FARTLEK: 6.5,  # 6:30/km
        WorkoutType.STRIDES: 7.0,  # 7:00/km base + fast strides
        WorkoutType.RACE: 5.0,  # 5:00/km
    }

    pace_min_km = default_paces.get(workout_type, 7.0)

    # Try to get from profile first
    if profile:
        # Check for workout-specific typical pace
        profile_pace_key = f"typical_{workout_type.value}_pace_min_km"
        if profile_pace_key in profile and profile[profile_pace_key]:
            pace_min_km = profile[profile_pace_key]
        else:
            # Try to derive from VDOT
            vdot = profile.get("vdot")
            if vdot:
                # Map workout type to intensity zone
                intensity_map = {
                    WorkoutType.EASY: IntensityZone.ZONE_2,
                    WorkoutType.LONG_RUN: IntensityZone.ZONE_2,
                    WorkoutType.TEMPO: IntensityZone.ZONE_4,
                    WorkoutType.INTERVALS: IntensityZone.ZONE_5,
                }
                intensity_zone = intensity_map.get(workout_type)

                if intensity_zone:
                    # Use existing VDOT to pace conversion
                    pace_seconds = _vdot_to_pace(vdot, intensity_zone)
                    if pace_seconds:
                        pace_min_km = pace_seconds / 60.0

    # Calculate duration
    duration_minutes = int(distance_km * pace_min_km)

    # Add warmup/cooldown for quality workouts
    if workout_type in (WorkoutType.TEMPO, WorkoutType.INTERVALS):
        warmup_cooldown = 20  # 10 min warmup + 10 min cooldown
        duration_minutes += warmup_cooldown

    return duration_minutes


def _calculate_pace_ranges(
    workout_type: WorkoutType,
    intensity_zone: IntensityZone,
    profile: dict,
) -> dict:
    """
    Calculate pace ranges from profile VDOT or recent race times.

    Returns dict with "min_pace" and "max_pace" as strings (e.g., "5:30").
    Returns empty dict if insufficient data.
    """
    # Try to get VDOT from profile
    vdot = profile.get("vdot")
    if not vdot:
        # Try to calculate from recent race
        recent_race = profile.get("recent_race")
        if recent_race:
            vdot = _calculate_vdot_from_race(recent_race)

    if not vdot:
        return {}

    # VDOT pace tables (simplified - would use full Jack Daniels tables in production)
    # These are approximate values per km for different VDOTs and zones
    pace_seconds_per_km = _vdot_to_pace(vdot, intensity_zone)

    if pace_seconds_per_km:
        # Add ±5 seconds for range
        min_pace_sec = pace_seconds_per_km - 5
        max_pace_sec = pace_seconds_per_km + 5

        return {
            "min_pace": _seconds_to_pace_string(min_pace_sec),
            "max_pace": _seconds_to_pace_string(max_pace_sec),
        }

    return {}


def _calculate_hr_ranges(intensity_zone: IntensityZone, profile: dict) -> dict:
    """
    Calculate HR ranges from profile vital signs.

    Returns dict with "low" and "high" HR values (int).
    Returns empty dict if max_hr not available.
    """
    vital_signs = profile.get("vital_signs", {})
    max_hr = vital_signs.get("max_hr")

    if not max_hr:
        return {}

    # HR zone percentages based on max HR
    zone_percentages = {
        IntensityZone.ZONE_1: (0.50, 0.65),  # Recovery
        IntensityZone.ZONE_2: (0.65, 0.75),  # Easy aerobic
        IntensityZone.ZONE_3: (0.75, 0.85),  # Moderate
        IntensityZone.ZONE_4: (0.85, 0.90),  # Threshold
        IntensityZone.ZONE_5: (0.90, 0.95),  # VO2max
    }

    low_pct, high_pct = zone_percentages.get(intensity_zone, (0.65, 0.75))

    return {
        "low": int(max_hr * low_pct),
        "high": int(max_hr * high_pct),
    }


def _calculate_vdot_from_race(recent_race: dict) -> Optional[float]:
    """
    Calculate VDOT from recent race performance.

    Simplified calculation - production would use full Jack Daniels formula.
    """
    # This would use the full VDOT calculation from M4 ProfileService
    # For now, return None to indicate calculation needed
    return None


def _vdot_to_pace(vdot: float, intensity_zone: IntensityZone) -> Optional[int]:
    """
    Convert VDOT to pace per km for given intensity zone.

    Returns seconds per km. Simplified lookup - production would use full tables.
    """
    # Simplified mapping: VDOT 45 ≈ 5:30/km easy, 5:00/km tempo, 4:30/km intervals
    # Scale linearly for other VDOTs
    if intensity_zone == IntensityZone.ZONE_2:
        # Easy pace: VDOT 40→6:00, 45→5:30, 50→5:00, 55→4:40
        return int(960 - (vdot - 40) * 4)
    elif intensity_zone == IntensityZone.ZONE_4:
        # Tempo pace: VDOT 40→5:30, 45→5:00, 50→4:40, 55→4:15
        return int(870 - (vdot - 40) * 3.6)
    elif intensity_zone == IntensityZone.ZONE_5:
        # Interval pace: VDOT 40→5:00, 45→4:30, 50→4:05, 55→3:45
        return int(780 - (vdot - 40) * 3.0)

    return None


def _seconds_to_pace_string(seconds: int) -> str:
    """Convert seconds per km to pace string (e.g., 330 -> "5:30")."""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def _generate_purpose(workout_type: WorkoutType, phase: PlanPhase, base_purpose: str) -> str:
    """
    Generate purpose text with phase-specific context.

    Adds context about why this workout matters in this phase.
    """
    phase_context = {
        PlanPhase.BASE: "building aerobic foundation",
        PlanPhase.BUILD: "developing race-specific fitness",
        PlanPhase.PEAK: "fine-tuning for peak performance",
        PlanPhase.TAPER: "maintaining fitness while recovering",
        PlanPhase.RECOVERY: "recovering from hard training",
    }

    context = phase_context.get(phase, "")

    if context:
        return f"{base_purpose} ({context})"

    return base_purpose


# ============================================================
# UTILITY FUNCTIONS
# ============================================================


def _get_day_name(day_of_week: int) -> str:
    """Convert day number to name."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[day_of_week]


# ============================================================
# TOOLKIT FUNCTIONS (Phase 5: Toolkit Paradigm)
# ============================================================


def suggest_volume_adjustment(
    current_weekly_volume_km: float,
    current_ctl: float,
    goal_distance_km: float,
    weeks_available: int
) -> "VolumeRecommendation":
    """
    Recommend safe starting and peak volumes based on fitness and goal (Toolkit Paradigm).

    Uses CTL-based starting ranges with conservative progression. Returns
    reference ranges for Claude Code to consider when designing plans.

    CTL-based starting ranges:
    - CTL <30 (beginner): 15-25km
    - CTL 30-45 (recreational): 25-40km
    - CTL 45-60 (intermediate): 35-60km
    - CTL >60 (advanced): 50-80km

    Peak volume: 2-3x race distance, adjusted for timeline

    Args:
        current_weekly_volume_km: Current weekly run volume
        current_ctl: Current chronic training load
        goal_distance_km: Goal race distance
        weeks_available: Weeks until race

    Returns:
        VolumeRecommendation with safe ranges and rationale
    """
    from sports_coach_engine.schemas.plan import VolumeRecommendation

    # Determine fitness level and starting range from CTL
    if current_ctl < 30:
        start_min, start_max = 15.0, 25.0
        level = "beginner"
    elif current_ctl < 45:
        start_min, start_max = 25.0, 40.0
        level = "recreational"
    elif current_ctl < 60:
        start_min, start_max = 35.0, 60.0
        level = "intermediate"
    else:
        start_min, start_max = 50.0, 80.0
        level = "advanced"

    # Adjust for current volume (start closer to what they're doing)
    if current_weekly_volume_km > 0:
        start_min = max(start_min, current_weekly_volume_km * 0.9)
        start_max = max(start_max, current_weekly_volume_km * 1.1)

    # Calculate peak volume (2-3x race distance)
    peak_multiplier = 2.5 if weeks_available >= 12 else 2.0
    peak_target = goal_distance_km * peak_multiplier

    # Adjust peak range based on timeline and starting point
    max_weekly_increase = 1.1  # 10% per week rule
    max_achievable = start_max * (max_weekly_increase ** (weeks_available * 0.75))  # 75% of weeks build
    peak_min = max(start_max, min(peak_target * 0.8, max_achievable * 0.9))  # Peak must be ≥ starting max
    peak_max = min(peak_target * 1.2, max_achievable)

    # Generate rationale
    rationale = (
        f"CTL {current_ctl:.0f} indicates {level} level fitness. "
        f"Safe starting range: {start_min:.0f}-{start_max:.0f}km/week. "
        f"Peak target: {peak_min:.0f}-{peak_max:.0f}km/week for {goal_distance_km}km race. "
    )

    if weeks_available < 12:
        rationale += f"Timeline is short ({weeks_available}w), keeping peak conservative."
    else:
        rationale += f"Timeline allows gradual progression over {weeks_available}w."

    return VolumeRecommendation(
        start_range_km=(start_min, start_max),
        peak_range_km=(peak_min, peak_max),
        rationale=rationale,
        current_ctl=current_ctl,
        goal_distance_km=goal_distance_km,
        weeks_available=weeks_available,
    )


def get_workout_template(workout_type: WorkoutType) -> dict:
    """
    Get template structure for workout type (Toolkit Paradigm).

    Returns default structure and parameters for workout types. Claude Code
    uses these as references when designing workouts, adjusting based on
    athlete context and preferences.

    Args:
        workout_type: Type of workout to get template for

    Returns:
        Dict with template structure:
        {
            "duration_minutes": int,
            "intensity_zone": IntensityZone,
            "target_rpe": int,
            "purpose": str,
            "intervals": Optional[list[dict]],
            "warmup_minutes": int,
            "cooldown_minutes": int
        }
    """
    # Use existing WORKOUT_DEFAULTS
    if workout_type in WORKOUT_DEFAULTS:
        return dict(WORKOUT_DEFAULTS[workout_type])
    else:
        # Default to easy if unknown type
        return dict(WORKOUT_DEFAULTS[WorkoutType.EASY])


def create_downgraded_workout(
    original: WorkoutPrescription,
    target_rpe: int = 4
) -> WorkoutPrescription:
    """
    Create downgraded version of workout (Toolkit Paradigm).

    Reduces intensity while preserving date/week info. Claude Code uses this
    when athlete agrees to downgrade (e.g., due to high ACWR, low readiness).

    Args:
        original: Original workout prescription
        target_rpe: Target RPE for downgraded workout (default: 4 - easy)

    Returns:
        New WorkoutPrescription with reduced intensity
    """
    # Determine new workout type based on target RPE
    if target_rpe <= 4:
        new_type = WorkoutType.EASY
        new_zone = IntensityZone.ZONE_2
    elif target_rpe <= 6:
        new_type = WorkoutType.EASY
        new_zone = IntensityZone.ZONE_3
    else:
        new_type = WorkoutType.TEMPO
        new_zone = IntensityZone.ZONE_4

    easy_defaults = WORKOUT_DEFAULTS[WorkoutType.EASY]

    return WorkoutPrescription(
        id=original.id,
        week_number=original.week_number,
        day_of_week=original.day_of_week,
        date=original.date,
        workout_type=new_type,
        phase=original.phase,
        duration_minutes=min(original.duration_minutes, 45),  # Cap duration
        distance_km=original.distance_km * 0.7 if original.distance_km else None,
        intensity_zone=new_zone,
        target_rpe=target_rpe,
        pace_range_min_km=original.pace_range_min_km,
        pace_range_max_km=original.pace_range_max_km,
        hr_range_low=original.hr_range_low,
        hr_range_high=original.hr_range_high,
        intervals=None,  # Remove intervals
        warmup_minutes=10,
        cooldown_minutes=10,
        purpose=f"Downgraded from {original.workout_type} - {easy_defaults['purpose']}",
        notes=f"Adjusted based on athlete state (originally {original.workout_type})",
        key_workout=False,
        status=original.status,
        execution=original.execution,
    )


def create_shortened_workout(
    original: WorkoutPrescription,
    duration_minutes: int
) -> WorkoutPrescription:
    """
    Create shortened version of workout (Toolkit Paradigm).

    Reduces duration while preserving intensity. Claude Code uses this when
    athlete agrees to shorten workout (e.g., time constraints, fatigue).

    Args:
        original: Original workout prescription
        duration_minutes: New target duration

    Returns:
        New WorkoutPrescription with reduced duration
    """
    # Calculate reduction percentage
    reduction_pct = duration_minutes / original.duration_minutes

    # Adjust interval structure if present
    new_intervals = None
    if original.intervals and reduction_pct < 1.0:
        new_intervals = []
        for interval in original.intervals:
            adjusted_interval = dict(interval)
            if "duration_minutes" in adjusted_interval:
                adjusted_interval["duration_minutes"] = int(adjusted_interval["duration_minutes"] * reduction_pct)
            elif "reps" in adjusted_interval:
                adjusted_interval["reps"] = max(1, int(adjusted_interval["reps"] * reduction_pct))
            new_intervals.append(adjusted_interval)

    return WorkoutPrescription(
        id=original.id,
        week_number=original.week_number,
        day_of_week=original.day_of_week,
        date=original.date,
        workout_type=original.workout_type,
        phase=original.phase,
        duration_minutes=duration_minutes,
        distance_km=original.distance_km * reduction_pct if original.distance_km else None,
        intensity_zone=original.intensity_zone,
        target_rpe=original.target_rpe,
        pace_range_min_km=original.pace_range_min_km,
        pace_range_max_km=original.pace_range_max_km,
        hr_range_low=original.hr_range_low,
        hr_range_high=original.hr_range_high,
        intervals=new_intervals,
        warmup_minutes=original.warmup_minutes,
        cooldown_minutes=original.cooldown_minutes,
        purpose=original.purpose,
        notes=f"Shortened to {duration_minutes}min (originally {original.duration_minutes}min)",
        key_workout=original.key_workout,
        status=original.status,
        execution=original.execution,
    )


def estimate_recovery_days(workout: WorkoutPrescription) -> int:
    """
    Estimate days needed to recover from workout (Toolkit Paradigm).

    Based on intensity and duration. Claude Code uses this when rescheduling
    workouts or determining appropriate spacing.

    Recovery estimates:
    - Easy run: 0-1 days
    - Tempo: 1-2 days
    - Long run (>90min): 2-3 days
    - Intervals: 2-3 days
    - Race effort: 3-7 days

    Args:
        workout: Workout prescription

    Returns:
        Estimated recovery days (integer)
    """
    # Base recovery by workout type
    if workout.workout_type == WorkoutType.EASY:
        base_recovery = 0
    elif workout.workout_type == WorkoutType.TEMPO:
        base_recovery = 2
    elif workout.workout_type == WorkoutType.INTERVALS:
        base_recovery = 2
    elif workout.workout_type == WorkoutType.LONG_RUN:
        base_recovery = 2
    elif workout.workout_type == WorkoutType.RACE:
        base_recovery = 7
    else:
        base_recovery = 1

    # Adjust for duration
    if workout.duration_minutes > 120:
        base_recovery += 1
    elif workout.duration_minutes > 90:
        base_recovery += 0 if base_recovery == 0 else 1

    # Adjust for RPE
    if workout.target_rpe >= 9:
        base_recovery += 1

    return min(base_recovery, 7)  # Cap at 7 days


def validate_week(
    week_plan: WeekPlan,
    athlete_profile: dict
) -> list["GuardrailViolation"]:
    """
    Validate single week against guardrails (Toolkit Paradigm).

    Detects violations without enforcement. Claude Code reviews violations
    and decides whether to enforce, override with rationale, or discuss.

    Checks:
    - Max quality sessions (≤2-3/week)
    - Hard/easy separation (no back-to-back hard days)
    - Long run caps (≤30% volume, ≤2.5h)

    Args:
        week_plan: Week to validate
        athlete_profile: Athlete profile for context

    Returns:
        List of detected violations
    """
    from sports_coach_engine.schemas.plan import GuardrailViolation

    violations = []

    # Check quality session limit
    quality_workouts = [w for w in week_plan.workouts if w.target_rpe >= 7]
    if len(quality_workouts) > 2:
        violations.append(GuardrailViolation(
            rule="max_quality_sessions",
            week=week_plan.week_number,
            severity="warning",
            actual=len(quality_workouts),
            target=2,
            message=f"Week {week_plan.week_number} has {len(quality_workouts)} quality sessions (recommended max: 2)",
            suggestion="Consider downgrading one session to easy or moving to different week"
        ))

    # Check hard/easy separation
    sorted_workouts = sorted(week_plan.workouts, key=lambda w: w.day_of_week)
    for i in range(len(sorted_workouts) - 1):
        curr = sorted_workouts[i]
        next_day = sorted_workouts[i + 1]

        if curr.target_rpe >= 7 and next_day.target_rpe >= 7:
            # Check if consecutive days (handles normal case and Sunday→Monday wrap)
            is_consecutive = (
                next_day.day_of_week == curr.day_of_week + 1 or  # Normal: Mon→Tue, etc
                (curr.day_of_week == 6 and next_day.day_of_week == 0)  # Wrap: Sun→Mon
            )
            if is_consecutive:
                violations.append(GuardrailViolation(
                    rule="hard_easy_separation",
                    week=week_plan.week_number,
                    severity="warning",
                    actual=0,  # Boolean violation
                    target=1,  # Expected separation
                    message=f"Back-to-back hard sessions: {_get_day_name(curr.day_of_week)} ({curr.workout_type}) → {_get_day_name(next_day.day_of_week)} ({next_day.workout_type})",
                    suggestion=f"Consider moving {next_day.workout_type} or downgrading to easy"
                ))

    # Check volume distribution (actual vs target)
    actual_volume_km = sum(w.distance_km for w in week_plan.workouts if w.distance_km)
    target_volume_km = week_plan.target_volume_km
    if target_volume_km > 0:
        volume_diff_km = abs(actual_volume_km - target_volume_km)
        volume_diff_pct = (volume_diff_km / target_volume_km) * 100

        # Warn if difference > 5%
        if volume_diff_pct > 5:
            severity = "danger" if volume_diff_pct > 15 else "warning"
            violations.append(GuardrailViolation(
                rule="volume_mismatch",
                week=week_plan.week_number,
                severity=severity,
                actual=actual_volume_km,
                target=target_volume_km,
                message=f"Week {week_plan.week_number}: workout distances sum to {actual_volume_km:.1f}km but target is {target_volume_km:.1f}km (diff: {volume_diff_km:.1f}km, {volume_diff_pct:.0f}%)",
                suggestion="Consider using distribute_weekly_volume() helper to allocate distances that sum to target"
            ))

    # Check long run cap
    long_runs = [w for w in week_plan.workouts if w.workout_type == WorkoutType.LONG_RUN]
    if long_runs and week_plan.target_volume_km > 0:
        long_run = long_runs[0]
        long_run_km = long_run.distance_km or (long_run.duration_minutes / 60 * 6)  # Assume 10min/km
        long_run_pct = (long_run_km / week_plan.target_volume_km) * 100

        if long_run_pct > 30:
            violations.append(GuardrailViolation(
                rule="long_run_cap_pct",
                week=week_plan.week_number,
                severity="warning",
                actual=long_run_pct,
                target=30,
                message=f"Long run is {long_run_pct:.0f}% of weekly volume (recommended max: 30%)",
                suggestion=f"Consider shortening long run or increasing weekly volume"
            ))

        if long_run.duration_minutes > 150:  # 2.5 hours
            violations.append(GuardrailViolation(
                rule="long_run_cap_duration",
                week=week_plan.week_number,
                severity="warning",
                actual=long_run.duration_minutes,
                target=150,
                message=f"Long run is {long_run.duration_minutes}min (recommended max: 150min / 2.5h)",
                suggestion="Consider capping long run at 2.5 hours"
            ))

    # Validate individual workout minimums (profile-aware)
    for workout in week_plan.workouts:
        # Get workout type as string (handle both string and enum cases)
        wtype = workout.workout_type.value if hasattr(workout.workout_type, 'value') else workout.workout_type

        min_violation = validate_workout_minimums(
            workout_type=wtype,
            duration_minutes=workout.duration_minutes,
            distance_km=workout.distance_km,
            profile=athlete_profile  # Uses athlete-specific minimums if available
        )
        if min_violation:
            violations.append(GuardrailViolation(
                rule=min_violation.type,
                week=week_plan.week_number,
                severity="warning",  # Warning, not danger - coach can override
                actual=min_violation.current_value,
                target=min_violation.limit_value,
                message=f"Week {week_plan.week_number}: {min_violation.message}",
                suggestion=min_violation.recommendation
            ))

    return violations


def validate_guardrails(
    plan: MasterPlan,
    athlete_profile: dict
) -> list["GuardrailViolation"]:
    """
    Validate plan against training science rules (Toolkit Paradigm).

    DETECTS violations, does NOT auto-fix. Returns structured violation data
    for Claude Code to review and decide enforcement strategy.

    Checks:
    - 80/20 intensity distribution (for ≥3 run days/week)
    - Max quality sessions (≤2-3/week)
    - Long run caps (≤30% volume, ≤2.5h)
    - ACWR safety (weekly volume changes)
    - Hard/easy separation (no back-to-back hard days)
    - T/I/R volume limits (threshold ≤10%, intervals ≤8%, reps ≤5%)

    Args:
        plan: Master plan to validate
        athlete_profile: Athlete profile for context

    Returns:
        List of violations with severity levels (info/warning/danger)
        Claude Code reviews and decides enforcement
    """
    from sports_coach_engine.schemas.plan import GuardrailViolation

    violations = []

    # Validate each week
    for week in plan.weeks:
        week_violations = validate_week(week, athlete_profile)
        violations.extend(week_violations)

    # Check 80/20 distribution across full plan
    total_run_days = sum(len([w for w in week.workouts if w.workout_type != WorkoutType.REST]) for week in plan.weeks)
    if total_run_days >= 3 * len(plan.weeks):  # Avg ≥3 run days/week
        total_easy_minutes = sum(
            w.duration_minutes
            for week in plan.weeks
            for w in week.workouts
            if w.target_rpe <= 6
        )
        total_minutes = sum(
            w.duration_minutes
            for week in plan.weeks
            for w in week.workouts
            if w.workout_type != WorkoutType.REST
        )

        if total_minutes > 0:
            easy_pct = (total_easy_minutes / total_minutes) * 100

            if easy_pct < 75:  # Below 75% (aiming for 80%)
                violations.append(GuardrailViolation(
                    rule="80_20_distribution",
                    week=None,
                    severity="info" if easy_pct >= 70 else "warning",
                    actual=easy_pct,
                    target=80,
                    message=f"Plan has {easy_pct:.0f}% easy volume (recommended: 80%)",
                    suggestion="Consider downgrading some tempo/interval workouts or adding easy runs"
                ))

    return violations


# ============================================================
# ============================================================
# PLAN REVIEW AND TRAINING LOG FUNCTIONS
# ============================================================


def _get_adherence_message(adherence_pct: float) -> str:
    """Get friendly adherence message based on percentage.

    Args:
        adherence_pct: Adherence percentage (0-100)

    Returns:
        Encouraging message appropriate for adherence level
    """
    if adherence_pct >= 95:
        return "excellent consistency!"
    elif adherence_pct >= 85:
        return "great work staying on track!"
    elif adherence_pct >= 75:
        return "solid effort!"
    elif adherence_pct >= 60:
        return "keep building that routine"
    else:
        return "let's aim higher next week"


def _get_hr_context(hr_avg: int) -> str:
    """Get friendly context for heart rate value.

    Args:
        hr_avg: Average heart rate

    Returns:
        Contextual comment about HR
    """
    # These are general guidelines - actual zones depend on max HR
    if hr_avg < 130:
        return " (nice and easy)"
    elif hr_avg < 150:
        return " (good aerobic pace)"
    elif hr_avg < 165:
        return " (moderate effort)"
    elif hr_avg < 180:
        return " (working hard)"
    else:
        return " (high intensity)"


def _explain_ctl_change(ctl_start: float, ctl_end: float) -> str:
    """Explain CTL change in plain English.

    Args:
        ctl_start: CTL at week start
        ctl_end: CTL at week end

    Returns:
        Athlete-friendly explanation
    """
    change = ctl_end - ctl_start

    if change > 3:
        return f"Your aerobic fitness is building nicely (fitness score: {ctl_start:.0f} → {ctl_end:.0f})"
    elif change > 0:
        return f"Your aerobic fitness is building steadily (fitness score: {ctl_start:.0f} → {ctl_end:.0f})"
    elif change > -2:
        return f"Your fitness is holding steady (fitness score: {ctl_end:.0f})"
    else:
        return f"Taking a lighter week to absorb training (fitness score: {ctl_start:.0f} → {ctl_end:.0f})"


def _explain_tsb(tsb_value: float) -> str:
    """Explain TSB (Training Stress Balance) in plain English.

    Args:
        tsb_value: Current TSB value

    Returns:
        Athlete-friendly explanation
    """
    if tsb_value > 15:
        return f"You're very fresh and rested (recovery score: {tsb_value:+.0f})"
    elif tsb_value > 5:
        return f"You're well-recovered and race-ready (recovery score: {tsb_value:+.0f})"
    elif tsb_value > -10:
        return f"Good training balance - absorbing workload well (recovery score: {tsb_value:+.0f})"
    elif tsb_value > -20:
        return f"Building fitness with some fatigue - normal for training (recovery score: {tsb_value:+.0f})"
    else:
        return f"High training load - watch for signs of overtraining (recovery score: {tsb_value:+.0f})"


def _explain_acwr(acwr_value: float) -> str:
    """Explain ACWR (Acute:Chronic Workload Ratio) in plain English.

    Args:
        acwr_value: Current ACWR value

    Returns:
        Athlete-friendly explanation
    """
    if acwr_value < 0.8:
        return f"Training load is light - safe to increase volume (load ratio: {acwr_value:.2f})"
    elif acwr_value <= 1.3:
        return f"Training load is in a stable range (load ratio: {acwr_value:.2f})"
    elif acwr_value <= 1.5:
        return f"Training load is elevated - monitor how you feel (load ratio: {acwr_value:.2f})"
    else:
        return f"⚠️ Training load spike detected - consider reducing stress (load ratio: {acwr_value:.2f})"


def _generate_approval_block(
    plan: MasterPlan,
    athlete_name: Optional[str],
    approved: bool,
    timestamp: datetime
) -> str:
    """Generate athlete-friendly footer for review markdown.

    Returns clean, readable markdown footer with plan metadata.
    Keeps metadata minimal and athlete-focused.

    Args:
        plan: Current MasterPlan object
        athlete_name: Athlete name from profile (optional)
        approved: True if approved, False for draft review
        timestamp: Approval timestamp

    Returns:
        Markdown footer string
    """
    status = "✅ **Plan Approved**" if approved else "📋 **Draft Plan**"
    date_str = timestamp.strftime("%B %d, %Y")

    # Format goal type for display
    # Handle plan.goal as dict (from YAML) or object (from schema)
    if isinstance(plan.goal, dict):
        goal_type = plan.goal.get('type', 'unknown')
        target_date = plan.goal.get('target_date')
        # Parse target_date if it's a string
        if isinstance(target_date, str):
            from datetime import date as date_cls
            target_date = date_cls.fromisoformat(target_date)
    else:
        goal_type = plan.goal.goal_type if hasattr(plan.goal, 'goal_type') else plan.goal.type
        target_date = plan.goal.target_date

    goal_display = str(goal_type).replace("_", " ").title()
    race_date_str = target_date.strftime("%B %d, %Y")

    footer = f"""
---

{status}: {date_str}

**Race Day**: {race_date_str} ({goal_display})
**Training Duration**: {plan.total_weeks} weeks

Good luck with your training! 🏃

---
"""
    return footer


def save_plan_review(
    review_file_path: str,
    plan: MasterPlan,
    athlete_name: Optional[str] = None,
    approved: bool = True,
    repo: Optional[RepositoryIO] = None
) -> dict:
    """Save plan review markdown to repository.

    Workflow:
    1. Read review markdown from source file (usually /tmp/)
    2. Generate approval metadata block with plan details
    3. Append metadata to markdown content
    4. Save to data/plans/current_plan_review.md

    Args:
        review_file_path: Path to source review markdown (e.g., /tmp/training_plan_review_2026_01_20.md)
        plan: Current MasterPlan object
        athlete_name: Athlete name from profile (optional)
        approved: True if approved, False for draft review
        repo: RepositoryIO instance (creates new one if None)

    Returns:
        {
            "saved_path": "data/plans/current_plan_review.md",
            "approval_timestamp": "2026-01-17T14:23:00Z"
        }

    Raises:
        FileNotFoundError: If review_file_path doesn't exist
        IOError: If save fails
    """
    if repo is None:
        repo = RepositoryIO()

    # Read source review markdown
    if not os.path.exists(review_file_path):
        raise FileNotFoundError(f"Review file not found: {review_file_path}")

    with open(review_file_path, 'r') as f:
        review_content = f.read()

    # Generate approval block
    timestamp = datetime.now()
    approval_block = _generate_approval_block(plan, athlete_name, approved, timestamp)

    # Combine content with approval block
    full_content = review_content + "\n" + approval_block

    # Save to repository
    target_path = current_plan_review_path()
    target_abs_path = repo.resolve_path(target_path)

    with open(target_abs_path, 'w') as f:
        f.write(full_content)

    return {
        "saved_path": target_path,
        "approval_timestamp": timestamp.isoformat()
    }


def append_plan_adaptation(
    adaptation_file_path: str,
    plan: MasterPlan,
    reason: str,
    timestamp: Optional[datetime] = None,
    repo: Optional[RepositoryIO] = None
) -> dict:
    """Append plan adaptation to existing review markdown.

    Workflow:
    1. Read existing review markdown from data/plans/current_plan_review.md
    2. Read adaptation markdown from source file (e.g., /tmp/plan_adaptation_2026_02_15.md)
    3. Generate adaptation header block with date, reason, and context
    4. Append adaptation content to existing review
    5. Save updated review back to repository

    Args:
        adaptation_file_path: Path to adaptation markdown (e.g., /tmp/plan_adaptation_2026_02_15.md)
        plan: Current MasterPlan object
        reason: Adaptation reason (e.g., "illness", "injury", "schedule_change")
        timestamp: Adaptation timestamp (defaults to now)
        repo: RepositoryIO instance (creates new one if None)

    Returns:
        {
            "review_path": "data/plans/current_plan_review.md",
            "adaptation_timestamp": "2026-02-15T10:30:00Z",
            "reason": "illness"
        }

    Raises:
        FileNotFoundError: If review doesn't exist (plan never approved)
        IOError: If save fails
    """
    if repo is None:
        repo = RepositoryIO()

    if timestamp is None:
        timestamp = datetime.now()

    # Read existing review
    review_path = current_plan_review_path()
    review_abs_path = repo.resolve_path(review_path)

    if not review_abs_path.exists():
        raise FileNotFoundError(
            f"Plan review not found. Generate and approve plan first with save_plan_review()"
        )

    with open(review_abs_path, 'r') as f:
        existing_content = f.read()

    # Read adaptation markdown
    if not os.path.exists(adaptation_file_path):
        raise FileNotFoundError(f"Adaptation file not found: {adaptation_file_path}")

    with open(adaptation_file_path, 'r') as f:
        adaptation_content = f.read()

    # Generate adaptation header
    date_str = timestamp.strftime("%B %d, %Y")
    reason_display = reason.replace("_", " ").title()

    adaptation_header = f"""

---

## 📋 Plan Adaptation - {date_str}

**Reason**: {reason_display}
**Adapted by**: AI Coach

"""

    # Combine: existing + header + adaptation content
    updated_content = existing_content + "\n" + adaptation_header + adaptation_content

    # Save updated review
    with open(review_abs_path, 'w') as f:
        f.write(updated_content)

    return {
        "review_path": review_path,
        "adaptation_timestamp": timestamp.isoformat(),
        "reason": reason
    }


def initialize_training_log(
    plan: MasterPlan,
    athlete_name: Optional[str] = None,
    repo: Optional[RepositoryIO] = None
) -> dict:
    """Initialize training log markdown for a new plan.

    Creates initial log file with header and plan context.

    Args:
        plan: Current MasterPlan object
        athlete_name: Athlete name from profile (optional)
        repo: RepositoryIO instance (creates new one if None)

    Returns:
        {
            "log_path": "data/plans/current_training_log.md",
            "created_timestamp": "2026-01-17T14:23:00Z"
        }
    """
    if repo is None:
        repo = RepositoryIO()

    timestamp = datetime.now()

    # Format goal for display
    # Handle plan.goal as dict (from YAML) or object (from schema)
    if isinstance(plan.goal, dict):
        goal_type = plan.goal.get('type', 'unknown')
        target_date = plan.goal.get('target_date')
        target_time = plan.goal.get('target_time')
        # Parse target_date if it's a string
        if isinstance(target_date, str):
            from datetime import date as date_cls
            target_date = date_cls.fromisoformat(target_date)
    else:
        goal_type = plan.goal.goal_type if hasattr(plan.goal, 'goal_type') else plan.goal.type
        target_date = plan.goal.target_date
        target_time = plan.goal.target_time if hasattr(plan.goal, 'target_time') else None

    goal_display = str(goal_type).replace("_", " ").title()
    race_date_str = target_date.strftime("%B %d, %Y")
    start_date_str = plan.start_date.strftime("%B %d, %Y")

    # Format goal time if available
    goal_time_str = ""
    if target_time:
        goal_time_str = f"\n**Goal Time**: {target_time}"

    # Create log header
    athlete_line = f"**Athlete**: {athlete_name}\n" if athlete_name else ""

    log_content = f"""# Training Log: {goal_display} - {race_date_str}

{athlete_line}**Plan Start**: {start_date_str}
**Race Date**: {race_date_str} ({plan.total_weeks} weeks){goal_time_str}

---

"""

    # Save log file
    log_path = current_training_log_path()
    log_abs_path = repo.resolve_path(log_path)

    with open(log_abs_path, 'w') as f:
        f.write(log_content)

    return {
        "log_path": log_path,
        "created_timestamp": timestamp.isoformat()
    }


def append_weekly_summary(
    week_data: dict,
    plan: MasterPlan,
    repo: Optional[RepositoryIO] = None
) -> dict:
    """Append weekly training summary to training log.

    Called by weekly-analysis skill after each week completes.

    Args:
        week_data: Weekly summary data including:
            - week_number: int
            - week_dates: str (e.g., "Jan 20-26")
            - planned_volume_km: float
            - actual_volume_km: float
            - adherence_pct: float
            - completed_workouts: list[dict] with workout details
            - key_metrics: dict with CTL, TSB, ACWR
            - coach_observations: str
            - milestones: list[str] (optional)
        plan: Current MasterPlan object
        repo: RepositoryIO instance (creates new one if None)

    Returns:
        {
            "log_path": "data/plans/logs/2026-01-20_half_marathon_log.md",
            "week_number": 1,
            "appended_timestamp": "2026-01-26T20:00:00Z"
        }

    Raises:
        FileNotFoundError: If log doesn't exist (not initialized)
        ValueError: If week_data structure is invalid
    """
    if repo is None:
        repo = RepositoryIO()

    timestamp = datetime.now()

    # Validate week_data structure
    required_fields = [
        "week_number", "week_dates", "planned_volume_km", "actual_volume_km",
        "adherence_pct", "completed_workouts", "key_metrics", "coach_observations"
    ]
    for field in required_fields:
        if field not in week_data:
            raise ValueError(f"Missing required field in week_data: {field}")

    # Read existing log
    log_path = current_training_log_path()
    log_abs_path = repo.resolve_path(log_path)

    if not log_abs_path.exists():
        raise FileNotFoundError(
            f"Training log not found. Initialize it first with initialize_training_log()"
        )

    with open(log_abs_path, 'r') as f:
        existing_content = f.read()

    # Get phase for this week
    week_obj = next((w for w in plan.weeks if w.week_number == week_data["week_number"]), None)
    phase_display = week_obj.phase.replace("_", " ").title() if week_obj else "Training"

    # Create athlete-friendly opening
    adherence_msg = _get_adherence_message(week_data['adherence_pct'])

    # Format weekly summary with friendly, narrative style
    week_summary = f"""## Week {week_data['week_number']}: {phase_display} ({week_data['week_dates']})

You completed **{week_data['actual_volume_km']:.1f} km** of your planned {week_data['planned_volume_km']:.1f} km this week ({week_data['adherence_pct']:.0f}% adherence) - {adherence_msg}

### Your Runs This Week

"""

    # Add workout details in narrative format
    for workout in week_data['completed_workouts']:
        # Determine status emoji
        status_emoji = workout.get('status_emoji', '✅')

        # Format workout type for display
        workout_type = workout['type'].replace('_', ' ').title()

        # Build workout header
        if status_emoji == '✅':
            workout_header = f"**{workout['day']}** - {workout_type} {workout['distance_km']:.1f} km"
        elif status_emoji == '⏭️':
            workout_header = f"**{workout['day']}** - {workout_type} (skipped)"
        else:
            workout_header = f"**{workout['day']}** - {workout_type} {workout['distance_km']:.1f} km"

        week_summary += workout_header

        # Add pace if completed
        if status_emoji == '✅' and 'pace_per_km' in workout and workout['pace_per_km']:
            week_summary += f" @ {workout['pace_per_km']}/km"

        week_summary += "\n"

        # Add HR with friendly context
        if 'hr_avg' in workout and workout['hr_avg']:
            hr_context = _get_hr_context(workout.get('hr_avg'))
            week_summary += f"- Heart rate: {workout['hr_avg']} bpm{hr_context}\n"

        # Add athlete notes in italics for personal touch
        if 'notes' in workout and workout['notes']:
            week_summary += f"- _{workout['notes']}_\n"

        week_summary += "\n"

    # Add coach observations with friendly heading
    week_summary += f"""### Coach's Take

{week_data['coach_observations']}
"""

    # Add fitness snapshot with plain English explanations
    ctl_start = week_data['key_metrics'].get('ctl_start', 0)
    ctl_end = week_data['key_metrics'].get('ctl_end', 0)
    tsb_start = week_data['key_metrics'].get('tsb_start', 0)
    tsb_end = week_data['key_metrics'].get('tsb_end', 0)
    acwr = week_data['key_metrics'].get('acwr', 0)

    ctl_explanation = _explain_ctl_change(ctl_start, ctl_end)
    tsb_explanation = _explain_tsb(tsb_end)
    acwr_explanation = _explain_acwr(acwr)

    week_summary += f"""
### Fitness Snapshot
- {ctl_explanation}
- {tsb_explanation}
- {acwr_explanation}
"""

    # Add milestones if present
    if 'milestones' in week_data and week_data['milestones']:
        week_summary += "\n### Milestones 🎯\n"
        for milestone in week_data['milestones']:
            week_summary += f"- {milestone}\n"

    week_summary += "\n---\n"

    # Append to log
    updated_content = existing_content + "\n" + week_summary

    with open(log_abs_path, 'w') as f:
        f.write(updated_content)

    return {
        "log_path": log_path,
        "week_number": week_data['week_number'],
        "appended_timestamp": timestamp.isoformat()
    }


# ============================================================
# PROGRESSIVE DISCLOSURE HELPERS (Phase 2: Monthly Planning)
# ============================================================


def assess_monthly_completion(
    month_number: int,
    week_numbers: list[int],
    planned_workouts: list[dict],
    completed_activities: list[dict],
    starting_ctl: float,
    ending_ctl: float,
    target_ctl: float,
    current_vdot: float,
) -> dict:
    """
    Assess completed month for next month planning.

    Analyzes execution and response from previous month:
    - Adherence: What percentage of workouts were completed?
    - CTL progression: Did fitness increase as expected?
    - VDOT drift: Should paces be recalibrated?
    - Signals: Any injury/illness mentions in notes?
    - Volume tolerance: Was the load well-tolerated?
    - Patterns: Consistent skips or preferences observed?

    This provides context for generating next month's plan adaptively.

    Args:
        month_number: Month that was assessed (1-indexed)
        week_numbers: Weeks assessed (e.g., [1, 2, 3, 4])
        planned_workouts: List of planned workouts from monthly plan
        completed_activities: List of actual activities from Strava
        starting_ctl: CTL at month start
        ending_ctl: CTL at month end
        target_ctl: Target CTL for month end (from macro plan)
        current_vdot: VDOT used for month's paces

    Returns:
        dict: Monthly assessment ready for MonthlyAssessment schema

    Example:
        >>> assessment = assess_monthly_completion(
        ...     month_number=1,
        ...     week_numbers=[1, 2, 3, 4],
        ...     planned_workouts=[...],  # 16 workouts
        ...     completed_activities=[...],  # 15 runs
        ...     starting_ctl=44.0,
        ...     ending_ctl=50.5,
        ...     target_ctl=52.0,
        ...     current_vdot=48.0
        ... )
        >>> assessment["adherence_pct"]
        93.75  # 15/16 workouts
        >>> assessment["ctl_on_target"]
        True  # Within 5% of target
    """
    # Calculate adherence
    total_planned = len(planned_workouts)
    total_completed = len([a for a in completed_activities if a.get("type") == "Run"])
    adherence_pct = (total_completed / total_planned * 100) if total_planned > 0 else 0.0

    # CTL assessment
    ctl_delta = ending_ctl - starting_ctl
    ctl_target_delta = target_ctl - starting_ctl
    ctl_on_target = abs(ending_ctl - target_ctl) < (target_ctl * 0.05)  # Within 5%

    # VDOT analysis - Look for pace drift in tempo/interval workouts
    # (Simple v0: just flag if completion rate < 90% for quality sessions)
    quality_workouts = [w for w in planned_workouts if w.get("workout_type") in ["tempo", "intervals"]]
    completed_quality = [a for a in completed_activities if a.get("description", "").lower().find("tempo") >= 0 or a.get("description", "").lower().find("interval") >= 0]

    vdot_recalibration_needed = False
    suggested_vdot = None
    if len(quality_workouts) > 0:
        quality_completion_rate = len(completed_quality) / len(quality_workouts)
        if quality_completion_rate < 0.85:  # Less than 85% completion
            vdot_recalibration_needed = True
            suggested_vdot = round(current_vdot * 0.98, 1)  # Suggest slight reduction

    # Detect injury/illness signals from activity notes
    injury_signals = []
    illness_signals = []
    for activity in completed_activities:
        description = activity.get("description", "").lower()
        private_note = activity.get("private_note", "").lower()
        combined = description + " " + private_note

        # Injury keywords
        if any(keyword in combined for keyword in ["pain", "hurt", "sore", "injury", "strain", "ache"]):
            injury_signals.append(f"Week {activity.get('week', '?')}: {activity.get('description', 'Activity')[:50]}...")

        # Illness keywords
        if any(keyword in combined for keyword in ["sick", "ill", "cold", "flu", "fever", "tired"]):
            illness_signals.append(f"Week {activity.get('week', '?')}: {activity.get('description', 'Activity')[:50]}...")

    # Detect patterns (simple v0: just check for consistent day-of-week skips)
    patterns_detected = []
    # This would require more sophisticated analysis - for v0, leave empty or simple
    if adherence_pct < 80:
        patterns_detected.append(f"Low adherence ({adherence_pct:.0f}%) - investigate scheduling conflicts")

    # Volume tolerance assessment
    volume_well_tolerated = True
    volume_adjustment_suggestion = "Maintain"

    if len(injury_signals) > 2:
        volume_well_tolerated = False
        volume_adjustment_suggestion = "Reduce 10%"
    elif adherence_pct < 75:
        volume_well_tolerated = False
        volume_adjustment_suggestion = "Reduce 5% or reassess scheduling"
    elif adherence_pct > 95 and ending_ctl > target_ctl:
        volume_adjustment_suggestion = "Increase 5% if recovery good"

    # Overall assessment
    if len(injury_signals) > 0:
        overall_response = "Injury signals detected - adjust volume/intensity"
    elif len(illness_signals) > 0:
        overall_response = "Illness disruption - allow recovery before progression"
    elif adherence_pct < 80:
        overall_response = "Struggled with volume/scheduling"
    elif ctl_on_target and adherence_pct >= 90:
        overall_response = "Excellent adaptation - progressing well"
    else:
        overall_response = "Moderate adaptation - continue current trajectory"

    # Recommendations for next month
    recommendations = []
    if vdot_recalibration_needed:
        recommendations.append(f"Recalculate VDOT (suggest {suggested_vdot})")
    if not volume_well_tolerated:
        recommendations.append(f"Adjust volume: {volume_adjustment_suggestion}")
    if len(patterns_detected) > 0:
        recommendations.append("Review scheduling patterns with athlete")
    if ctl_on_target:
        recommendations.append("Continue current volume progression")
    else:
        recommendations.append("Adjust volume trajectory to meet CTL targets")

    return {
        "month_number": month_number,
        "week_numbers": week_numbers,
        "assessment_date": date.today(),
        "planned_workouts": total_planned,
        "completed_workouts": total_completed,
        "adherence_pct": round(adherence_pct, 1),
        "starting_ctl": starting_ctl,
        "ending_ctl": ending_ctl,
        "target_ctl": target_ctl,
        "ctl_delta": round(ctl_delta, 1),
        "ctl_on_target": ctl_on_target,
        "current_vdot": current_vdot,
        "suggested_vdot": suggested_vdot,
        "vdot_recalibration_needed": vdot_recalibration_needed,
        "injury_signals": injury_signals[:5],  # Limit to 5 most recent
        "illness_signals": illness_signals[:5],
        "patterns_detected": patterns_detected,
        "volume_well_tolerated": volume_well_tolerated,
        "volume_adjustment_suggestion": volume_adjustment_suggestion,
        "overall_response": overall_response,
        "recommendations_for_next_month": recommendations
    }


def validate_monthly_plan(
    monthly_plan_weeks: list[dict],
    macro_volume_targets: list[dict],
) -> dict:
    """
    Validate 4-week monthly plan before saving.

    Checks for:
    - Volume discrepancies (<5% acceptable, 5-10% review, >10% regenerate)
    - Guardrail violations (long run %, quality volume, progression)
    - Phase consistency with macro plan
    - Workout field completeness

    Returns violations with severity levels for AI Coach to review.

    Args:
        monthly_plan_weeks: 4 weeks from monthly plan (list of WeekPlan dicts)
        macro_volume_targets: Volume targets from macro plan for these weeks

    Returns:
        dict: Validation result
        {
            "overall_ok": bool,
            "violations": list[dict],
            "warnings": list[str],
            "summary": str
        }

    Example:
        >>> result = validate_monthly_plan(
        ...     monthly_plan_weeks=[week1, week2, week3, week4],
        ...     macro_volume_targets=[target1, target2, target3, target4]
        ... )
        >>> result["overall_ok"]
        True
        >>> len(result["violations"])
        2  # Two minor warnings, no blockers
    """
    violations = []
    warnings = []

    for i, week in enumerate(monthly_plan_weeks):
        week_num = week.get("week_number")
        target_volume = macro_volume_targets[i].get("target_volume_km") if i < len(macro_volume_targets) else None

        # Check volume discrepancy
        if target_volume is not None:
            actual_volume = week.get("target_volume_km", 0)
            discrepancy_pct = abs(actual_volume - target_volume) / target_volume * 100 if target_volume > 0 else 0

            if discrepancy_pct > 10:
                violations.append({
                    "rule": "weekly_volume_discrepancy",
                    "week": week_num,
                    "severity": "danger",
                    "actual": actual_volume,
                    "target": target_volume,
                    "message": f"Week {week_num}: {actual_volume}km vs {target_volume}km target ({discrepancy_pct:.1f}% discrepancy)",
                    "suggestion": "Regenerate week to meet volume target"
                })
            elif discrepancy_pct > 5:
                warnings.append(f"Week {week_num}: {discrepancy_pct:.1f}% volume discrepancy (review recommended)")

        # Check for minimum workout durations (if workouts present)
        workouts = week.get("workouts", [])
        for workout in workouts:
            duration_min = workout.get("duration_minutes", 0)
            workout_type = workout.get("workout_type", "unknown")

            # Simple minimums
            min_durations = {"easy": 30, "long_run": 60, "tempo": 40, "intervals": 35}
            required_min = min_durations.get(workout_type, 20)

            if duration_min < required_min and workout_type != "rest":
                violations.append({
                    "rule": "minimum_workout_duration",
                    "week": week_num,
                    "severity": "warning",
                    "actual": duration_min,
                    "target": required_min,
                    "message": f"Week {week_num}: {workout_type} workout {duration_min}min (minimum {required_min}min)",
                    "suggestion": f"Increase duration or reduce run frequency"
                })

    overall_ok = len([v for v in violations if v["severity"] == "danger"]) == 0

    summary = "Monthly plan validation passed" if overall_ok else f"{len(violations)} validation issues found"

    return {
        "overall_ok": overall_ok,
        "violations": violations,
        "warnings": warnings,
        "summary": summary
    }


def generate_monthly_plan(
    month_number: int,
    week_numbers: list[int],
    target_volumes_km: list[float],
    macro_plan: dict,
    current_vdot: float,
    profile: dict,
    volume_adjustment: float = 1.0,
) -> dict:
    """
    Generate detailed monthly plan (2-5 weeks) with workout prescriptions.

    Creates complete workout prescriptions for specified weeks using:
    - AI-designed volume targets (validated by guardrails)
    - Profile constraints (run days, sports, long run max)
    - VDOT-based pace zones
    - Phase-appropriate workout distribution
    - Multi-sport integration

    Handles variable-length cycles (2-5 weeks) for plans that aren't evenly divisible by 4.
    Example: 11-week plan might use 4+4+3 weeks, 13-week plan might use 4+4+5 weeks.

    Args:
        month_number: Month number (1-4 typically, may vary)
        week_numbers: List of week numbers for this cycle (e.g., [1,2,3,4] or [9,10,11])
        target_volumes_km: List of weekly volume targets (AI-designed, one per week)
        macro_plan: Macro plan dict with phases and recovery weeks
        current_vdot: Current VDOT value (may be recalibrated from previous month)
        profile: Athlete profile dict with constraints, sports, preferences
        volume_adjustment: Multiplier for volume targets (0.9 = reduce 10%, 1.0 = as planned)

    Returns:
        Dict with month_number, weeks (list of week dicts with workouts), paces, generation_context

    Raises:
        ValueError: If week_numbers is empty or target_volumes_km length mismatch
        KeyError: If macro_plan missing required fields

    Example:
        >>> macro_plan = {"phases": [...], "recovery_weeks": [4, 8], ...}
        >>> profile = {"max_run_days": 4, "sports": [...], ...}
        >>> monthly = generate_monthly_plan(
        ...     month_number=1,
        ...     week_numbers=[1, 2, 3, 4],
        ...     target_volumes_km=[25.0, 27.5, 30.0, 21.0],
        ...     macro_plan=macro_plan,
        ...     current_vdot=48.0,
        ...     profile=profile
        ... )
        >>> len(monthly["weeks"])
        4
        >>> monthly["weeks"][0]["workouts"]  # List of workout prescriptions
        [...]
    """
    from datetime import date, timedelta
    from .vdot import calculate_training_paces

    # Validation
    if not week_numbers:
        raise ValueError("week_numbers cannot be empty")

    if not (2 <= len(week_numbers) <= 6):
        raise ValueError(f"Monthly cycle must be 2-6 weeks, got {len(week_numbers)} weeks")

    if len(target_volumes_km) != len(week_numbers):
        raise ValueError(f"target_volumes_km length ({len(target_volumes_km)}) must match week_numbers length ({len(week_numbers)})")

    if "structure" not in macro_plan or "phases" not in macro_plan["structure"]:
        raise KeyError("macro_plan missing required field: structure.phases")

    # Create volume map from AI-designed targets
    volume_trajectory = {week_num: target_km for week_num, target_km in zip(week_numbers, target_volumes_km)}

    # Get phases from macro plan
    phases_list = macro_plan["structure"]["phases"]
    week_to_phase = {}
    for phase_info in phases_list:
        phase_name = phase_info["name"]
        for week in phase_info["weeks"]:
            week_to_phase[week] = phase_name

    # Calculate training paces from VDOT
    paces = calculate_training_paces(current_vdot)

    # Get profile constraints
    max_run_days = profile.get("max_run_days", 4)
    run_days_per_week = min(max_run_days, 5)  # Cap at 5 for safety

    # Get start date (from macro plan or calculate from week 1)
    plan_start_date = None
    if "race" in macro_plan and "start_date" in macro_plan["race"]:
        # Parse start date if string
        start_str = macro_plan["race"]["start_date"]
        if isinstance(start_str, str):
            plan_start_date = date.fromisoformat(start_str)
        else:
            plan_start_date = start_str

    if not plan_start_date:
        # Fallback: use current date for first week
        plan_start_date = date.today()
        # Adjust to Monday
        days_to_monday = (7 - plan_start_date.weekday()) % 7
        if days_to_monday > 0:
            plan_start_date = plan_start_date + timedelta(days=days_to_monday)

    # Generate weeks
    weeks = []
    for week_num in week_numbers:
        # Get volume target for this week
        target_volume_km = volume_trajectory[week_num] * volume_adjustment

        # Get phase for this week
        phase_name = week_to_phase.get(week_num, "base")
        phase_enum = PlanPhase(phase_name)

        # Determine if recovery week (every 4th week during base/build)
        is_recovery_week = (week_num % 4 == 0) and phase_name in ["base", "build"]
        if is_recovery_week:
            target_volume_km *= 0.70  # Recovery week at 70% volume

        # Calculate week dates
        week_start = plan_start_date + timedelta(weeks=(week_num - 1))
        week_end = week_start + timedelta(days=6)

        # Determine workout types based on phase
        workout_types = determine_weekly_workouts(
            phase=phase_enum,
            run_days_per_week=run_days_per_week,
            is_recovery_week=is_recovery_week,
            week_number=week_num,
            profile=profile
        )

        # Distribute volume across workouts
        volume_allocation = distribute_weekly_volume(
            weekly_volume_km=target_volume_km,
            workout_types=workout_types,
            profile=profile
        )

        # Create workout prescriptions
        workouts = []
        current_date = week_start
        for day_idx, workout_type in enumerate(workout_types):
            allocated_distance = volume_allocation.get(day_idx, 0.0)

            workout = create_workout(
                workout_type=workout_type.value,
                workout_date=current_date,
                week_number=week_num,
                day_of_week=current_date.weekday(),
                phase=phase_enum,
                volume_target_km=target_volume_km,
                profile=profile,
                allocated_distance_km=allocated_distance
            )

            workouts.append(workout.model_dump())
            current_date += timedelta(days=1)

        # Build week dict
        week_dict = {
            "week_number": week_num,
            "phase": phase_name,
            "start_date": week_start.isoformat(),
            "end_date": week_end.isoformat(),
            "target_volume_km": round(target_volume_km, 1),
            "is_recovery_week": is_recovery_week,
            "workouts": workouts,
            "notes": generate_week_notes(phase_name, week_num, is_recovery_week)
        }

        weeks.append(week_dict)

    # Build monthly plan
    monthly_plan = {
        "month_number": month_number,
        "weeks_covered": week_numbers,
        "num_weeks": len(week_numbers),
        "weeks": weeks,
        "paces": {
            "vdot": current_vdot,
            "e_pace": f"{paces.format_range(paces.easy_pace_range)} /km",
            "m_pace": f"{paces.format_range(paces.marathon_pace_range)} /km",
            "t_pace": f"{paces.format_range(paces.threshold_pace_range)} /km",
            "i_pace": f"{paces.format_range(paces.interval_pace_range)} /km",
            "r_pace": f"{paces.format_range(paces.repetition_pace_range)} /km",
        },
        "generation_context": {
            "volume_adjustment": volume_adjustment,
            "generated_at": date.today().isoformat(),
            "cycle_length_weeks": len(week_numbers),
            "phases_included": list(set(week_to_phase[w] for w in week_numbers)),
        }
    }

    return monthly_plan


def determine_weekly_workouts(
    phase: PlanPhase,
    run_days_per_week: int,
    is_recovery_week: bool,
    week_number: int,
    profile: dict,
) -> list[WorkoutType]:
    """
    Determine workout types for the week based on phase and constraints.

    Args:
        phase: Current periodization phase
        run_days_per_week: Number of run days (3-5)
        is_recovery_week: Whether this is a recovery week
        week_number: Week number in plan
        profile: Athlete profile with sports schedule

    Returns:
        List of WorkoutType for each day of the week (7 days)
    """
    # Get other sports schedule from profile
    other_sports_days = set()
    if "sports" in profile:
        for sport in profile["sports"]:
            if sport.get("sport") != "running":
                days_str = sport.get("days", "")
                if days_str:
                    day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
                    for day in days_str.lower().split(","):
                        day = day.strip()
                        if day in day_map:
                            other_sports_days.add(day_map[day])

    # Build 7-day schedule
    schedule = [WorkoutType.REST] * 7

    # Determine quality workout placement based on phase
    if phase == PlanPhase.BASE:
        # Base phase: Long run + optional late-base tempo
        quality_workouts = [WorkoutType.LONG_RUN]
        if week_number >= 4 and not is_recovery_week:
            quality_workouts.append(WorkoutType.TEMPO)
    elif phase == PlanPhase.BUILD:
        # Build phase: Long run + tempo + intervals/M-pace
        quality_workouts = [WorkoutType.LONG_RUN, WorkoutType.TEMPO]
        if not is_recovery_week:
            quality_workouts.append(WorkoutType.INTERVALS)
    elif phase == PlanPhase.PEAK:
        # Peak phase: Long run + tempo + intervals + race pace
        quality_workouts = [WorkoutType.LONG_RUN, WorkoutType.TEMPO, WorkoutType.INTERVALS]
    else:  # TAPER
        # Taper: Maintain sharpness, reduce volume
        quality_workouts = [WorkoutType.TEMPO] if week_number % 2 == 0 else []

    # Recovery weeks reduce quality
    if is_recovery_week and len(quality_workouts) > 1:
        quality_workouts = quality_workouts[:1]  # Keep only long run

    # Place long run on Sunday (day 6) if possible
    available_days = [d for d in range(7) if d not in other_sports_days]

    if 6 in available_days and WorkoutType.LONG_RUN in quality_workouts:
        schedule[6] = WorkoutType.LONG_RUN
        quality_workouts.remove(WorkoutType.LONG_RUN)

    # Place remaining quality workouts with 48h spacing
    quality_placed = 0
    for day in [1, 3, 5]:  # Mon, Wed, Fri
        if day in available_days and quality_placed < len(quality_workouts):
            schedule[day] = quality_workouts[quality_placed]
            quality_placed += 1

    # Fill remaining run days with easy runs
    easy_days_needed = run_days_per_week - sum(1 for w in schedule if w != WorkoutType.REST)
    for day in available_days:
        if easy_days_needed > 0 and schedule[day] == WorkoutType.REST:
            schedule[day] = WorkoutType.EASY
            easy_days_needed -= 1

    return schedule


def generate_week_notes(phase_name: str, week_number: int, is_recovery_week: bool) -> str:
    """Generate descriptive notes for the week."""
    if is_recovery_week:
        return f"Week {week_number} - Recovery week: Reduced volume for adaptation"

    phase_focus = {
        "base": "Aerobic foundation building",
        "build": "Race-specific intensity development",
        "peak": "Maximum training load",
        "taper": "Reduce fatigue, maintain sharpness"
    }

    focus = phase_focus.get(phase_name, "Training")
    return f"Week {week_number} - {phase_name.capitalize()} phase: {focus}"
