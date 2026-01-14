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
from sports_coach_engine.schemas.plan import (
    GoalType,
    PlanPhase,
    WorkoutType,
    IntensityZone,
    WorkoutPrescription,
    WeekPlan,
    MasterPlan,
)
from sports_coach_engine.core.paths import (
    current_plan_path,
    plan_workouts_dir,
    get_plans_dir,
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
    # Validate minimum timeline requirements
    min_weeks = _get_minimum_weeks(goal)
    if weeks_available < min_weeks:
        raise ValueError(
            f"{goal.value} requires minimum {min_weeks} weeks, got {weeks_available}"
        )

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


def create_workout(
    workout_type: str,
    workout_date: date,
    week_number: int,
    day_of_week: int,
    phase: PlanPhase,
    volume_target_km: float,
    profile: Optional[dict] = None,
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

    if workout_type == WorkoutType.LONG_RUN:
        # Long run: 25-30% of weekly volume, capped at 2.5 hours
        distance_km = min(volume_target_km * 0.28, 32.0)
        # Estimate duration: assume 6:00/km pace for long run
        duration_minutes = min(int(distance_km * 6.0), 150)

    elif workout_type in (WorkoutType.EASY, WorkoutType.TEMPO, WorkoutType.INTERVALS):
        # Distance-based workouts: allocate from weekly volume
        if workout_type == WorkoutType.EASY:
            distance_km = volume_target_km * 0.15  # ~15% of weekly volume
        elif workout_type == WorkoutType.TEMPO:
            distance_km = volume_target_km * 0.12  # ~12% including warmup/cooldown
        elif workout_type == WorkoutType.INTERVALS:
            distance_km = volume_target_km * 0.10  # ~10% including warmup/cooldown

        # Estimate duration based on intensity
        if workout_type == WorkoutType.EASY:
            duration_minutes = int(distance_km * 6.0)  # 6:00/km
        elif workout_type == WorkoutType.TEMPO:
            duration_minutes = defaults["duration_minutes"]  # Use default
        elif workout_type == WorkoutType.INTERVALS:
            duration_minutes = defaults["duration_minutes"]  # Use default

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
# PLAN PERSISTENCE
# ============================================================


def persist_plan(plan: MasterPlan, repo: Optional[RepositoryIO] = None) -> None:
    """
    Persist a training plan to disk.

    File structure created:
    plans/
    ├── current_plan.yaml           # Master plan metadata
    └── workouts/
        ├── week_01/
        │   ├── monday_easy.yaml
        │   ├── wednesday_tempo.yaml
        │   └── sunday_long_run.yaml
        └── week_02/
            └── ...

    Args:
        plan: MasterPlan to persist
        repo: RepositoryIO instance (creates new one if None)

    Raises:
        RepoError: If file write fails
    """
    if repo is None:
        repo = RepositoryIO()

    # Write master plan metadata
    error = repo.write_yaml(current_plan_path(), plan)
    if error:
        raise RuntimeError(f"Failed to write master plan: {error.message}")

    # Write individual workouts
    for week in plan.weeks:
        week_dir = plan_workouts_dir(week.week_number)

        for workout in week.workouts:
            # Generate filename: "monday_tempo.yaml", "sunday_long_run.yaml"
            day_name = _get_day_name(workout.day_of_week).lower()
            workout_name = workout.workout_type.replace("_", "_")  # Already snake_case
            filename = f"{day_name}_{workout_name}.yaml"

            workout_path = f"{week_dir}/{filename}"
            error = repo.write_yaml(workout_path, workout)
            if error:
                raise RuntimeError(f"Failed to write workout {workout_path}: {error.message}")


def archive_current_plan(reason: str, repo: Optional[RepositoryIO] = None) -> Optional[str]:
    """
    Archive the current plan before regenerating.

    Moves entire plans/ directory to:
    plans_archive/YYYY-MM-DD_HHmmss_{reason}/

    Args:
        reason: Reason for archiving (e.g., "goal_changed", "regenerated")
        repo: RepositoryIO instance (creates new one if None)

    Returns:
        Archive path if plan was archived, None if no plan existed
    """
    if repo is None:
        repo = RepositoryIO()

    plans_dir = repo.resolve_path("plans")

    # Check if current plan exists
    if not plans_dir.exists():
        return None

    # Generate archive path with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    archive_name = f"{timestamp}_{reason}"
    archive_dir = repo.resolve_path(f"plans_archive/{archive_name}")

    # Create archive directory
    archive_dir.parent.mkdir(parents=True, exist_ok=True)

    # Move entire plans/ directory to archive
    shutil.move(str(plans_dir), str(archive_dir))

    # Create fresh plans/ directory
    plans_dir.mkdir(parents=True, exist_ok=True)

    # Write archive info file
    archive_info = {
        "archived_at": timestamp,
        "reason": reason,
        "original_path": f"{get_plans_dir()}/",
    }
    archive_info_path = archive_dir.parent / f"{archive_name}_info.yaml"
    with open(archive_info_path, "w") as f:
        import yaml
        yaml.safe_dump(archive_info, f)

    return str(archive_dir)
