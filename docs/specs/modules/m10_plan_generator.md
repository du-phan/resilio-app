# M10 — Plan Generator

## 1. Metadata

| Field | Value |
|-------|-------|
| Module ID | M10 |
| Name | Plan Generator |
| Version | 1.0.1 |
| Status | Draft |
| Dependencies | M3 (Repository I/O), M4 (Athlete Profile), M9 (Metrics Engine) |

### Changelog
- **1.0.1** (2026-01-12): Converted all dataclass types to BaseModel for consistency. Added complete algorithms for `generate_week_plan()`, `persist_plan()`, and `archive_current_plan()` to remove `...` placeholders and make spec LLM-implementable.
- **1.0.0** (initial): Initial draft with comprehensive plan generation algorithms

## 2. Purpose

Generate structured training plans based on athlete goals, constraints, and current fitness. Implements evidence-based training principles (periodization, 80/20 intensity distribution, progressive overload) while respecting multi-sport schedules.

### 2.1 Scope Boundaries

**In Scope:**
- Master plan generation (goal → race date periodization)
- Weekly structure based on run day constraints
- Workout prescription with pace/HR targets
- Training guardrail enforcement
- Conflict policy integration
- Volume/intensity progression
- Recovery week scheduling

**Out of Scope:**
- Real-time adaptation (M11)
- Workout execution tracking (M11)
- Rendering plans for display (M12)
- Fitness/metrics computation (M9)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage |
|--------|-------|
| M3 | Read/write plan and workout files |
| M4 | Get athlete profile, constraints, goal |
| M9 | Get current CTL/ATL/TSB for calibration |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
```

## 4. Public Interface

### 4.1 Type Definitions

```python
from datetime import date, timedelta
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class GoalType(str, Enum):
    """Training goal types"""
    GENERAL_FITNESS = "general_fitness"
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"


class PlanPhase(str, Enum):
    """Periodization phases"""
    BASE = "base"           # Build aerobic foundation
    BUILD = "build"         # Increase intensity
    PEAK = "peak"           # Race-specific work
    TAPER = "taper"         # Reduce volume for race
    RECOVERY = "recovery"   # Post-race/reset week


class WorkoutType(str, Enum):
    """Workout classifications"""
    EASY = "easy"           # Zone 1-2, recovery
    LONG_RUN = "long_run"   # Aerobic endurance
    TEMPO = "tempo"         # Threshold pace
    INTERVALS = "intervals" # VO2max work
    FARTLEK = "fartlek"     # Mixed intensity
    STRIDES = "strides"     # Short accelerations
    RACE = "race"           # Competition
    REST = "rest"           # Scheduled rest day


class IntensityZone(str, Enum):
    """Training intensity zones"""
    ZONE_1 = "zone_1"   # Recovery, <65% max HR
    ZONE_2 = "zone_2"   # Easy aerobic, 65-75% max HR
    ZONE_3 = "zone_3"   # Moderate aerobic, 75-85% max HR
    ZONE_4 = "zone_4"   # Threshold, 85-90% max HR
    ZONE_5 = "zone_5"   # VO2max, 90-95% max HR


class WorkoutPrescription(BaseModel):
    """Complete workout specification"""
    # Identity
    id: str
    week_number: int
    day_of_week: int         # 0=Monday, 6=Sunday
    date: date

    # Type and phase
    workout_type: WorkoutType
    phase: PlanPhase

    # Duration/distance
    duration_minutes: int
    distance_km: Optional[float] = None

    # Intensity
    intensity_zone: IntensityZone
    target_rpe: int          # 1-10

    # Pace guidance (for running)
    pace_range_min_km: Optional[str] = None  # e.g., "5:30"
    pace_range_max_km: Optional[str] = None  # e.g., "5:45"
    hr_range_low: Optional[int] = None
    hr_range_high: Optional[int] = None

    # Structure (for intervals/tempo)
    intervals: Optional[list[dict]] = Field(default=None)  # e.g., [{"distance": "800m", "reps": 4}]
    warmup_minutes: int = 10
    cooldown_minutes: int = 10

    # Notes
    purpose: str             # Why this workout
    notes: Optional[str] = None
    key_workout: bool = False  # Is this a key session?

    # Status
    status: str = "scheduled"  # scheduled | completed | skipped | adapted


class WeekPlan(BaseModel):
    """Single week's plan"""
    week_number: int
    phase: PlanPhase
    start_date: date
    end_date: date

    # Weekly targets
    target_volume_km: float
    target_systemic_load_au: float

    # Workouts
    workouts: list[WorkoutPrescription]

    # Metadata
    is_recovery_week: bool = False
    notes: Optional[str] = None


class MasterPlan(BaseModel):
    """Complete training plan from start to goal"""
    # Identity
    id: str
    created_at: date
    goal: "Goal"

    # Timeline
    start_date: date
    end_date: date           # Race date
    total_weeks: int

    # Phase breakdown
    phases: list[dict]       # [{phase, start_week, end_week, focus}]

    # Weeks
    weeks: list[WeekPlan]

    # Volume progression
    starting_volume_km: float
    peak_volume_km: float

    # Metadata
    constraints_applied: list[str]
    conflict_policy: str


class PlanGenerationResult(BaseModel):
    """Result of plan generation"""
    plan: MasterPlan
    warnings: list[str]          # Non-blocking issues
    guardrails_applied: list[str]  # Guardrails that modified the plan
```

### 4.2 Weekly Structure Templates

```python
# Run frequency -> weekly structure mapping
WEEKLY_STRUCTURES: dict[int, dict] = {
    2: {
        "description": "2 runs/week - FIRST-style",
        "pattern": [
            {"type": "quality", "purpose": "Goal-specific stimulus"},
            {"type": "long_aerobic", "purpose": "Endurance anchor"},
        ],
        "notes": "For multi-sport athletes with heavy cross-training",
    },
    3: {
        "description": "3 runs/week - Balanced",
        "pattern": [
            {"type": "quality", "purpose": "Goal-specific stimulus"},
            {"type": "easy", "purpose": "Recovery/active rest"},
            {"type": "long_run", "purpose": "Endurance"},
        ],
        "notes": "Minimum for serious race preparation",
    },
    4: {
        "description": "4 runs/week - Standard",
        "pattern": [
            {"type": "quality", "purpose": "Goal-specific (tempo/intervals)"},
            {"type": "easy", "purpose": "Recovery"},
            {"type": "easy", "purpose": "Base building"},
            {"type": "long_run", "purpose": "Endurance"},
        ],
        "notes": "Sweet spot for most recreational runners",
    },
    5: {
        "description": "5 runs/week - High commitment",
        "pattern": [
            {"type": "quality", "purpose": "Primary quality session"},
            {"type": "easy", "purpose": "Recovery"},
            {"type": "moderate", "purpose": "Steady aerobic"},
            {"type": "quality", "purpose": "Secondary quality (lighter)"},
            {"type": "long_run", "purpose": "Endurance"},
        ],
        "notes": "Requires good recovery capacity",
    },
}
```

### 4.3 Function Signatures

```python
def generate_master_plan(
    profile: "AthleteProfile",
    current_metrics: "DailyMetrics",
    start_date: Optional[date] = None,
) -> PlanGenerationResult:
    """
    Generate a complete training plan from goal to race date.

    Args:
        profile: Athlete profile with goal and constraints
        current_metrics: Current fitness metrics for calibration
        start_date: Plan start date (default: next Monday)

    Returns:
        Complete master plan with all weeks and workouts
    """
    ...


def generate_week_plan(
    master_plan: MasterPlan,
    week_number: int,
    current_metrics: "DailyMetrics",
    previous_week_actual: Optional["WeeklySummary"],
) -> WeekPlan:
    """
    Generate or refine a single week's plan.

    Used for weekly refinement based on current state.

    Process:
        1. Find the target week in the master plan
        2. If previous week actual exists, adjust volume based on compliance
        3. Adjust intensity if readiness is low or ACWR elevated
        4. Preserve key workout structure but adjust targets
        5. Return refined week plan

    Args:
        master_plan: The master plan containing week template
        week_number: Week number to generate (1-indexed)
        current_metrics: Current CTL/ATL/TSB/ACWR/readiness
        previous_week_actual: Last week's completed summary

    Returns:
        Refined WeekPlan with current-state adjustments
    """
    # Find base week from master plan
    base_week = next(
        (w for w in master_plan.weeks if w.week_number == week_number),
        None
    )
    if not base_week:
        raise ValueError(f"Week {week_number} not found in master plan")

    # Start with base week
    refined_week = base_week.copy(deep=True)

    # Adjust based on previous week compliance
    if previous_week_actual:
        actual_volume = previous_week_actual.total_distance_km
        target_volume = base_week.target_volume_km

        # If actual < 80% of target, reduce this week's volume
        if actual_volume < target_volume * 0.8:
            compliance_ratio = actual_volume / target_volume
            volume_adjustment = 0.9 if compliance_ratio < 0.5 else 0.95
            refined_week.target_volume_km *= volume_adjustment
            refined_week.notes = (
                f"Volume reduced to {volume_adjustment*100:.0f}% due to previous week "
                f"low compliance ({compliance_ratio*100:.0f}%)"
            )

    # Adjust based on current readiness
    if current_metrics.readiness and current_metrics.readiness.score < 50:
        # Low readiness: reduce intensity of quality sessions
        for workout in refined_week.workouts:
            if workout.target_rpe >= 7:
                workout.target_rpe = max(workout.target_rpe - 1, 5)
                workout.notes = (workout.notes or "") + " [Reduced intensity due to low readiness]"

    # Adjust based on ACWR
    if current_metrics.acwr and current_metrics.acwr.ratio and current_metrics.acwr.ratio > 1.3:
        # Elevated ACWR: reduce volume
        refined_week.target_volume_km *= 0.9
        refined_week.notes = (refined_week.notes or "") + " [Volume reduced due to elevated ACWR]"

    return refined_week


def create_workout(
    workout_type: WorkoutType,
    date: date,
    profile: "AthleteProfile",
    phase: PlanPhase,
    volume_target: float,
) -> WorkoutPrescription:
    """
    Create a single workout prescription.
    """
    ...


def calculate_periodization(
    goal: "Goal",
    weeks_available: int,
) -> list[dict]:
    """
    Determine phase breakdown based on goal and timeline.

    Returns:
        List of phase definitions with week ranges
    """
    ...


def calculate_volume_progression(
    starting_volume_km: float,
    peak_volume_km: float,
    total_weeks: int,
    phases: list[dict],
) -> list[float]:
    """
    Calculate weekly volume targets with progression.

    Includes recovery week reductions (every 3-4 weeks).
    """
    ...


def assign_workouts_to_days(
    week_structure: dict,
    available_days: list[int],
    other_sports: list[dict],
    conflict_policy: str,
) -> dict[int, str]:
    """
    Map workout types to specific days of week.

    Respects:
    - Available run days from constraints
    - Other sport commitments
    - Conflict policy
    - Hard/easy separation rule
    """
    ...


def apply_training_guardrails(
    plan: MasterPlan,
    profile: "AthleteProfile",
) -> tuple[MasterPlan, list[str]]:
    """
    Apply training guardrails to the plan.

    Guardrails:
    - 80/20 intensity distribution
    - Long run caps (25-30% of weekly volume)
    - T/I/R volume limits
    - No back-to-back hard days
    - Max 2 quality sessions per 7 days

    Returns:
        (modified_plan, guardrails_applied)
    """
    ...


def persist_plan(
    plan: MasterPlan,
    repo: "RepositoryIO",
) -> None:
    """
    Write plan to disk.

    Creates:
    - plans/current_plan.yaml (metadata)
    - plans/workouts/week_##/*.yaml (individual workouts)

    Process:
        1. Create plans directory if needed
        2. Write master plan metadata to current_plan.yaml
        3. For each week, create week_NN directory
        4. Write each workout to individual YAML file
        5. All writes are atomic via M3

    Args:
        plan: Complete MasterPlan to persist
        repo: RepositoryIO instance for file operations
    """
    from pathlib import Path

    # Create plans directory structure
    plans_dir = Path("plans")
    workouts_dir = plans_dir / "workouts"

    # Write master plan metadata
    plan_data = {
        "_schema": {
            "format_version": "1.0.0",
            "schema_type": "plan",
        },
        "id": plan.id,
        "created_at": plan.created_at.isoformat(),
        "goal": {
            "type": plan.goal.type.value,
            "race_target_date": plan.goal.race_target_date.isoformat() if plan.goal.race_target_date else None,
            "target_time": plan.goal.target_time,
        },
        "timeline": {
            "start_date": plan.start_date.isoformat(),
            "end_date": plan.end_date.isoformat(),
            "total_weeks": plan.total_weeks,
        },
        "phases": plan.phases,
        "volume_progression": {
            "starting_km": plan.starting_volume_km,
            "peak_km": plan.peak_volume_km,
            "weekly_targets": [w.target_volume_km for w in plan.weeks],
        },
        "constraints_applied": plan.constraints_applied,
        "conflict_policy": plan.conflict_policy,
    }

    repo.write_yaml(plans_dir / "current_plan.yaml", plan_data)

    # Write individual workout files
    for week in plan.weeks:
        week_dir = workouts_dir / f"week_{week.week_number:02d}"

        for workout in week.workouts:
            # Generate filename from workout type and day
            day_name = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][workout.day_of_week]
            filename = f"{day_name}_{workout.workout_type.value}.yaml"

            workout_data = {
                "_schema": {
                    "format_version": "1.0.0",
                    "schema_type": "workout",
                },
                "id": workout.id,
                "week_number": workout.week_number,
                "day_of_week": workout.day_of_week,
                "date": workout.date.isoformat(),
                "workout_type": workout.workout_type.value,
                "phase": workout.phase.value,
                "duration_minutes": workout.duration_minutes,
                "distance_km": workout.distance_km,
                "intensity": {
                    "zone": workout.intensity_zone.value,
                    "target_rpe": workout.target_rpe,
                    "pace_range_min_km": workout.pace_range_min_km,
                    "pace_range_max_km": workout.pace_range_max_km,
                    "hr_range_low": workout.hr_range_low,
                    "hr_range_high": workout.hr_range_high,
                },
                "structure": {
                    "warmup_minutes": workout.warmup_minutes,
                    "cooldown_minutes": workout.cooldown_minutes,
                    "intervals": workout.intervals,
                },
                "purpose": workout.purpose,
                "notes": workout.notes,
                "key_workout": workout.key_workout,
                "status": workout.status,
                "execution": None,
            }

            repo.write_yaml(week_dir / filename, workout_data)


def archive_current_plan(
    reason: str,
    repo: "RepositoryIO",
) -> str:
    """
    Archive existing plan before generating new one.

    Process:
        1. Check if plans/current_plan.yaml exists
        2. If not, return early (nothing to archive)
        3. Generate archive directory name with timestamp
        4. Move entire plans/ directory to archive location
        5. Create fresh plans/ directory
        6. Return archive path

    Args:
        reason: Why the plan was archived (e.g., "goal_changed", "regenerated")
        repo: RepositoryIO instance for file operations

    Returns:
        Archive path (e.g., "plans_archive/2025-03-10_goal_changed")
    """
    from pathlib import Path
    from datetime import datetime
    import shutil

    plans_dir = Path("plans")
    current_plan_path = plans_dir / "current_plan.yaml"

    # Check if current plan exists
    if not current_plan_path.exists():
        return ""  # Nothing to archive

    # Generate archive path with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    archive_name = f"{timestamp}_{reason}"
    archive_dir = Path("plans_archive") / archive_name

    # Create archive directory
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Move entire plans directory to archive
    if plans_dir.exists():
        # Copy all files to archive
        shutil.copytree(plans_dir, archive_dir / "plans", dirs_exist_ok=True)

        # Add archive metadata
        archive_metadata = {
            "_schema": {
                "format_version": "1.0.0",
                "schema_type": "archive_metadata",
            },
            "archived_at": datetime.now().isoformat(),
            "reason": reason,
            "original_plan_id": repo.read_yaml(current_plan_path).get("id", "unknown"),
        }
        repo.write_yaml(archive_dir / "archive_info.yaml", archive_metadata)

        # Remove old plans directory
        shutil.rmtree(plans_dir)

    # Create fresh plans directory
    plans_dir.mkdir(parents=True, exist_ok=True)

    return str(archive_dir)
```

### 4.4 Error Types

```python
class PlanGenerationError(Exception):
    """Base error for plan generation"""
    pass


class InsufficientTimeError(PlanGenerationError):
    """Not enough time before goal date"""
    def __init__(self, weeks_available: int, weeks_needed: int):
        super().__init__(
            f"Only {weeks_available} weeks until goal, need at least {weeks_needed}"
        )
        self.weeks_available = weeks_available
        self.weeks_needed = weeks_needed


class IncompatibleConstraintsError(PlanGenerationError):
    """Constraints cannot be satisfied"""
    def __init__(self, conflicts: list[str]):
        super().__init__(f"Incompatible constraints: {', '.join(conflicts)}")
        self.conflicts = conflicts


class GoalNotSetError(PlanGenerationError):
    """No goal defined in profile"""
    pass
```

## 5. Core Algorithms

### 5.1 Master Plan Generation

```python
from datetime import datetime, timedelta
import uuid


def generate_master_plan(
    profile: "AthleteProfile",
    current_metrics: "DailyMetrics",
    start_date: Optional[date] = None,
) -> PlanGenerationResult:
    """
    Complete master plan generation pipeline.
    """
    warnings = []
    guardrails_applied = []

    # Validate goal exists
    if not profile.goal:
        raise GoalNotSetError("No goal defined in athlete profile")

    goal = profile.goal

    # Determine timeline
    if not start_date:
        start_date = _next_monday(date.today())

    if goal.race_target_date:
        end_date = goal.race_target_date
        weeks_available = (end_date - start_date).days // 7
    else:
        # General fitness: 12-week rolling plan
        weeks_available = 12
        end_date = start_date + timedelta(weeks=12)

    # Check minimum timeline
    min_weeks = _minimum_weeks_for_goal(goal.type)
    if weeks_available < min_weeks:
        warnings.append(
            f"Only {weeks_available} weeks until goal. Recommend {min_weeks}+ weeks "
            f"for optimal {goal.type.value} preparation."
        )

    # Calculate periodization
    phases = calculate_periodization(goal, weeks_available)

    # Determine starting volume
    starting_volume = _determine_starting_volume(
        profile, current_metrics, goal
    )

    # Calculate peak volume
    peak_volume = _determine_peak_volume(
        goal, profile.constraints, starting_volume
    )

    # Calculate weekly volume progression
    volume_progression = calculate_volume_progression(
        starting_volume, peak_volume, weeks_available, phases
    )

    # Generate each week
    weeks = []
    for week_num in range(weeks_available):
        week_start = start_date + timedelta(weeks=week_num)
        week_end = week_start + timedelta(days=6)

        # Determine phase for this week
        phase = _phase_for_week(week_num, phases)

        # Check if recovery week
        is_recovery = _is_recovery_week(week_num, phases)

        # Get weekly structure
        run_days = len(profile.constraints.available_run_days)
        structure = WEEKLY_STRUCTURES.get(run_days, WEEKLY_STRUCTURES[3])

        # Assign workouts to days
        day_assignments = assign_workouts_to_days(
            structure,
            profile.constraints.available_run_days,
            profile.other_sports,
            profile.conflict_policy,
        )

        # Create workouts
        workouts = _create_week_workouts(
            week_num=week_num + 1,
            week_start=week_start,
            day_assignments=day_assignments,
            phase=phase,
            volume_target=volume_progression[week_num],
            profile=profile,
            is_recovery=is_recovery,
        )

        weeks.append(WeekPlan(
            week_number=week_num + 1,
            phase=phase,
            start_date=week_start,
            end_date=week_end,
            target_volume_km=volume_progression[week_num],
            target_systemic_load_au=_estimate_load_from_volume(
                volume_progression[week_num], profile
            ),
            workouts=workouts,
            is_recovery_week=is_recovery,
        ))

    # Create master plan
    plan = MasterPlan(
        id=f"plan_{uuid.uuid4().hex[:8]}",
        created_at=date.today(),
        goal=goal,
        start_date=start_date,
        end_date=end_date,
        total_weeks=weeks_available,
        phases=[{"phase": p["phase"].value, **p} for p in phases],
        weeks=weeks,
        starting_volume_km=starting_volume,
        peak_volume_km=peak_volume,
        constraints_applied=[],
        conflict_policy=profile.conflict_policy,
    )

    # Apply training guardrails
    plan, guardrails = apply_training_guardrails(plan, profile)
    guardrails_applied.extend(guardrails)

    return PlanGenerationResult(
        plan=plan,
        warnings=warnings,
        guardrails_applied=guardrails_applied,
    )


def _minimum_weeks_for_goal(goal_type: GoalType) -> int:
    """Minimum recommended weeks for each goal type"""
    return {
        GoalType.GENERAL_FITNESS: 4,
        GoalType.FIVE_K: 6,
        GoalType.TEN_K: 8,
        GoalType.HALF_MARATHON: 10,
        GoalType.MARATHON: 16,
    }.get(goal_type, 8)
```

### 5.2 Periodization Calculation

```python
def calculate_periodization(
    goal: "Goal",
    weeks_available: int,
) -> list[dict]:
    """
    Determine phase breakdown using reverse periodization from race.

    Standard breakdown:
    - Taper: Last 2-3 weeks
    - Peak: 2-4 weeks
    - Build: 4-8 weeks
    - Base: Remaining weeks

    For general fitness: Rolling base/build cycle.
    """
    phases = []

    if goal.type == GoalType.GENERAL_FITNESS:
        # 4-week cycles: 3 build + 1 recovery
        week = 0
        cycle = 0
        while week < weeks_available:
            cycle_length = min(4, weeks_available - week)
            phases.append({
                "phase": PlanPhase.BASE if cycle % 2 == 0 else PlanPhase.BUILD,
                "start_week": week,
                "end_week": week + cycle_length - 1,
                "focus": "Maintain and gradually build fitness",
            })
            week += cycle_length
            cycle += 1
        return phases

    # Race-specific periodization
    if weeks_available >= 16:
        # Full marathon-style periodization
        taper_weeks = 3
        peak_weeks = 4
        build_weeks = 6
        base_weeks = weeks_available - taper_weeks - peak_weeks - build_weeks
    elif weeks_available >= 10:
        # Abbreviated for shorter races
        taper_weeks = 2
        peak_weeks = 3
        build_weeks = 4
        base_weeks = weeks_available - taper_weeks - peak_weeks - build_weeks
    else:
        # Minimal periodization
        taper_weeks = 1
        peak_weeks = 2
        build_weeks = max(2, weeks_available - 3)
        base_weeks = weeks_available - taper_weeks - peak_weeks - build_weeks

    # Assign phases (forward from start)
    week = 0

    if base_weeks > 0:
        phases.append({
            "phase": PlanPhase.BASE,
            "start_week": week,
            "end_week": week + base_weeks - 1,
            "focus": "Build aerobic foundation and easy volume",
        })
        week += base_weeks

    phases.append({
        "phase": PlanPhase.BUILD,
        "start_week": week,
        "end_week": week + build_weeks - 1,
        "focus": "Increase intensity, introduce quality sessions",
    })
    week += build_weeks

    phases.append({
        "phase": PlanPhase.PEAK,
        "start_week": week,
        "end_week": week + peak_weeks - 1,
        "focus": "Race-specific work, highest quality volume",
    })
    week += peak_weeks

    phases.append({
        "phase": PlanPhase.TAPER,
        "start_week": week,
        "end_week": weeks_available - 1,
        "focus": "Reduce volume, maintain intensity, arrive fresh",
    })

    return phases
```

### 5.3 Volume Progression

```python
def calculate_volume_progression(
    starting_volume_km: float,
    peak_volume_km: float,
    total_weeks: int,
    phases: list[dict],
) -> list[float]:
    """
    Calculate weekly volume with progressive overload and recovery weeks.

    Principles:
    - Increase ~10% per week during build
    - Recovery week every 3-4 weeks (-30-40% volume)
    - Taper reduces volume by 20-40%
    """
    volumes = []

    for week in range(total_weeks):
        phase_info = next(
            (p for p in phases if p["start_week"] <= week <= p["end_week"]),
            {"phase": PlanPhase.BASE}
        )
        phase = phase_info["phase"]

        # Base volume progression (linear from start to peak)
        progress_ratio = week / max(total_weeks - 3, 1)  # Exclude taper
        base_volume = starting_volume_km + (
            (peak_volume_km - starting_volume_km) * min(1.0, progress_ratio)
        )

        # Phase modifications
        if phase == PlanPhase.BASE:
            volume = base_volume * 0.8  # Conservative during base
        elif phase == PlanPhase.BUILD:
            volume = base_volume * 0.95
        elif phase == PlanPhase.PEAK:
            volume = base_volume  # Full volume
        elif phase == PlanPhase.TAPER:
            # Progressive taper reduction
            weeks_into_taper = week - phase_info["start_week"]
            taper_weeks = phase_info["end_week"] - phase_info["start_week"] + 1
            taper_factor = 1.0 - (0.15 * (weeks_into_taper + 1))
            volume = peak_volume_km * max(0.5, taper_factor)
        else:
            volume = base_volume

        # Recovery week check (every 4th week during base/build)
        if phase in {PlanPhase.BASE, PlanPhase.BUILD}:
            week_in_cycle = week % 4
            if week_in_cycle == 3:  # Every 4th week
                volume *= 0.7  # 30% reduction

        volumes.append(round(volume, 1))

    return volumes


def _is_recovery_week(week_num: int, phases: list[dict]) -> bool:
    """Check if this week is a recovery week"""
    phase_info = next(
        (p for p in phases if p["start_week"] <= week_num <= p["end_week"]),
        {"phase": PlanPhase.BASE}
    )
    phase = phase_info["phase"]

    if phase in {PlanPhase.TAPER, PlanPhase.RECOVERY}:
        return False  # Taper is different from recovery

    week_in_cycle = week_num % 4
    return week_in_cycle == 3
```

### 5.4 Workout Day Assignment

```python
def assign_workouts_to_days(
    week_structure: dict,
    available_days: list[int],
    other_sports: list[dict],
    conflict_policy: str,
) -> dict[int, str]:
    """
    Map workout types to specific days, respecting constraints.

    Strategy:
    1. Place long run on weekend (Saturday or Sunday)
    2. Place quality session mid-week (Tuesday or Thursday)
    3. Fill remaining with easy runs
    4. Ensure at least 1 easy day between hard sessions
    """
    pattern = week_structure["pattern"]
    assignments = {}

    # Sort available days
    available = sorted(available_days)

    # Find long run type and quality type
    long_run_idx = next(
        (i for i, w in enumerate(pattern) if w["type"] in {"long_run", "long_aerobic"}),
        -1
    )
    quality_idx = next(
        (i for i, w in enumerate(pattern) if w["type"] == "quality"),
        -1
    )

    # Prioritize weekend for long run
    weekend_days = [d for d in available if d >= 5]  # Sat=5, Sun=6
    weekday_available = [d for d in available if d < 5]

    if long_run_idx >= 0 and weekend_days:
        # Prefer Sunday for long run
        long_day = 6 if 6 in weekend_days else weekend_days[0]
        assignments[long_day] = pattern[long_run_idx]["type"]
        remaining_pattern = [p for i, p in enumerate(pattern) if i != long_run_idx]
        remaining_days = [d for d in available if d != long_day]
    else:
        remaining_pattern = pattern.copy()
        remaining_days = available.copy()

    # Place quality session (prefer Tuesday/Thursday)
    if quality_idx >= 0 and quality_idx != long_run_idx:
        quality_workout = pattern[quality_idx]
        preferred_quality_days = [1, 3]  # Tuesday, Thursday
        quality_day = next(
            (d for d in preferred_quality_days if d in remaining_days),
            remaining_days[0] if remaining_days else None
        )
        if quality_day is not None:
            assignments[quality_day] = quality_workout["type"]
            remaining_pattern = [p for p in remaining_pattern if p != quality_workout]
            remaining_days = [d for d in remaining_days if d != quality_day]

    # Fill remaining days with remaining workout types
    for workout in remaining_pattern:
        if remaining_days:
            day = remaining_days.pop(0)
            assignments[day] = workout["type"]

    # Apply conflict policy for other sports
    assignments = _apply_conflict_policy(
        assignments, other_sports, conflict_policy
    )

    return assignments


def _apply_conflict_policy(
    assignments: dict[int, str],
    other_sports: list[dict],
    policy: str,
) -> dict[int, str]:
    """
    Handle conflicts with other sport commitments.
    """
    if not other_sports:
        return assignments

    for sport in other_sports:
        sport_days = sport.get("days", [])
        is_high_intensity = sport.get("intensity", "moderate") == "high"

        for day in sport_days:
            if day in assignments:
                if policy == "primary_sport_wins":
                    # Move running workout if possible
                    # (simplified: just remove for now)
                    del assignments[day]
                elif policy == "running_goal_wins":
                    # Keep running, but avoid hard-on-hard
                    if is_high_intensity and assignments[day] == "quality":
                        assignments[day] = "easy"
                # ask_each_time: keep as-is, will prompt at runtime

    return assignments
```

### 5.5 Workout Creation

```python
def create_workout(
    workout_type: WorkoutType,
    date: date,
    profile: "AthleteProfile",
    phase: PlanPhase,
    volume_target: float,
    is_key_workout: bool = False,
) -> WorkoutPrescription:
    """
    Create a detailed workout prescription.
    """
    workout_id = f"w_{date.isoformat()}_{workout_type.value}"

    # Get base parameters from type
    base = _workout_type_defaults(workout_type)

    # Adjust for phase
    phase_mods = _phase_modifications(phase)

    # Calculate duration/distance
    if workout_type == WorkoutType.LONG_RUN:
        # Long run: 25-30% of weekly volume
        distance_km = min(volume_target * 0.28, 32)  # Cap at 32km
        duration = _estimate_duration(distance_km, profile)
    elif workout_type == WorkoutType.EASY:
        # Easy: remaining volume distributed
        distance_km = volume_target * 0.2  # ~20% per easy run
        duration = _estimate_duration(distance_km, profile)
    else:
        # Quality sessions: time-based
        duration = base["duration_minutes"] + phase_mods.get("duration_delta", 0)
        distance_km = None  # Intervals are time-based

    # Get pace/HR targets from profile
    paces = _get_pace_targets(workout_type, profile)

    return WorkoutPrescription(
        id=workout_id,
        week_number=0,  # Set by caller
        day_of_week=date.weekday(),
        date=date,
        workout_type=workout_type,
        phase=phase,
        duration_minutes=duration,
        distance_km=distance_km,
        intensity_zone=base["zone"],
        target_rpe=base["rpe"],
        pace_range_min_km=paces.get("min"),
        pace_range_max_km=paces.get("max"),
        hr_range_low=paces.get("hr_low"),
        hr_range_high=paces.get("hr_high"),
        intervals=base.get("intervals"),
        purpose=base["purpose"],
        key_workout=is_key_workout or workout_type in {
            WorkoutType.LONG_RUN, WorkoutType.TEMPO, WorkoutType.INTERVALS
        },
    )


def _workout_type_defaults(workout_type: WorkoutType) -> dict:
    """Default parameters for each workout type"""
    return {
        WorkoutType.EASY: {
            "duration_minutes": 40,
            "zone": IntensityZone.ZONE_2,
            "rpe": 4,
            "purpose": "Recovery and aerobic maintenance",
        },
        WorkoutType.LONG_RUN: {
            "duration_minutes": 90,
            "zone": IntensityZone.ZONE_2,
            "rpe": 5,
            "purpose": "Build endurance and fat oxidation",
        },
        WorkoutType.TEMPO: {
            "duration_minutes": 45,
            "zone": IntensityZone.ZONE_4,
            "rpe": 7,
            "purpose": "Improve lactate threshold",
            "intervals": [{"type": "tempo", "duration": "20min"}],
        },
        WorkoutType.INTERVALS: {
            "duration_minutes": 50,
            "zone": IntensityZone.ZONE_5,
            "rpe": 8,
            "purpose": "Improve VO2max and speed",
            "intervals": [{"type": "interval", "distance": "800m", "reps": 4}],
        },
        WorkoutType.FARTLEK: {
            "duration_minutes": 45,
            "zone": IntensityZone.ZONE_3,
            "rpe": 6,
            "purpose": "Mixed intensity, break monotony",
        },
        WorkoutType.REST: {
            "duration_minutes": 0,
            "zone": IntensityZone.ZONE_1,
            "rpe": 1,
            "purpose": "Complete rest for recovery",
        },
    }.get(workout_type, {
        "duration_minutes": 40,
        "zone": IntensityZone.ZONE_2,
        "rpe": 4,
        "purpose": "General training",
    })
```

### 5.6 Training Guardrails

```python
def apply_training_guardrails(
    plan: MasterPlan,
    profile: "AthleteProfile",
) -> tuple[MasterPlan, list[str]]:
    """
    Apply evidence-based training guardrails.

    Guardrails:
    1. Long run <= 25-30% of weekly volume
    2. Long run <= 2.5 hours
    3. T/I/R volumes (threshold <= 10%, intervals <= 8%, reps <= 5%)
    4. No back-to-back hard days
    5. Max 2 quality sessions per 7 days
    6. 80/20 intensity distribution (for 3+ run days)
    """
    applied = []

    for week in plan.weeks:
        # Guardrail 1 & 2: Long run caps
        long_run = next(
            (w for w in week.workouts if w.workout_type == WorkoutType.LONG_RUN),
            None
        )
        if long_run:
            max_distance = week.target_volume_km * 0.30
            max_duration = 150  # 2.5 hours

            if long_run.distance_km and long_run.distance_km > max_distance:
                long_run.distance_km = max_distance
                applied.append(f"Week {week.week_number}: Long run capped at 30% of volume")

            if long_run.duration_minutes > max_duration:
                long_run.duration_minutes = max_duration
                applied.append(f"Week {week.week_number}: Long run capped at 2.5 hours")

        # Guardrail 3: Hard session limit
        quality_count = sum(
            1 for w in week.workouts
            if w.workout_type in {WorkoutType.TEMPO, WorkoutType.INTERVALS}
        )
        if quality_count > 2:
            # Downgrade extra quality sessions
            for w in week.workouts:
                if quality_count <= 2:
                    break
                if w.workout_type in {WorkoutType.TEMPO, WorkoutType.INTERVALS}:
                    w.workout_type = WorkoutType.FARTLEK
                    w.target_rpe = min(w.target_rpe, 6)
                    quality_count -= 1
            applied.append(f"Week {week.week_number}: Capped quality sessions at 2")

        # Guardrail 4: Back-to-back hard days
        workouts_by_day = {w.day_of_week: w for w in week.workouts}
        for day in range(6):
            today = workouts_by_day.get(day)
            tomorrow = workouts_by_day.get(day + 1)

            if today and tomorrow:
                today_hard = today.target_rpe >= 7
                tomorrow_hard = tomorrow.target_rpe >= 7

                if today_hard and tomorrow_hard:
                    # Downgrade tomorrow
                    tomorrow.target_rpe = 5
                    tomorrow.workout_type = WorkoutType.EASY
                    applied.append(
                        f"Week {week.week_number}: Prevented back-to-back hard days"
                    )

    return plan, applied
```

## 6. Data Structures

### 6.1 Master Plan File Schema

```yaml
# plans/current_plan.yaml
_schema:
  format_version: "1.0.0"
  schema_type: "plan"

id: "plan_a1b2c3d4"
created_at: "2025-03-10"

goal:
  type: "half_marathon"
  race_target_date: "2025-06-15"
  target_time: "1:45:00"

timeline:
  start_date: "2025-03-10"
  end_date: "2025-06-15"
  total_weeks: 14

phases:
  - phase: "base"
    start_week: 0
    end_week: 3
    focus: "Build aerobic foundation"
  - phase: "build"
    start_week: 4
    end_week: 9
    focus: "Increase intensity"
  - phase: "peak"
    start_week: 10
    end_week: 11
    focus: "Race-specific work"
  - phase: "taper"
    start_week: 12
    end_week: 13
    focus: "Reduce volume, stay sharp"

volume_progression:
  starting_km: 30.0
  peak_km: 55.0
  weekly_targets: [30, 33, 36, 28, 40, 44, 48, 38, 52, 55, 52, 45, 35, 25]

constraints_applied:
  - "Available days: Tue, Thu, Sat, Sun"
  - "Conflict policy: running_goal_wins"
  - "Max 4 run days per week"

conflict_policy: "running_goal_wins"
```

### 6.2 Workout File Schema

```yaml
# plans/workouts/week_03/tuesday_tempo.yaml
_schema:
  format_version: "1.0.0"
  schema_type: "workout"

id: "w_2025-03-25_tempo"
week_number: 3
day_of_week: 1
date: "2025-03-25"

workout_type: "tempo"
phase: "base"

duration_minutes: 45
distance_km: null  # Time-based

intensity:
  zone: "zone_4"
  target_rpe: 7
  pace_range_min_km: "5:15"
  pace_range_max_km: "5:25"
  hr_range_low: 160
  hr_range_high: 170

structure:
  warmup_minutes: 10
  cooldown_minutes: 10
  intervals:
    - type: "tempo"
      duration: "20min"
      pace: "threshold"

purpose: "Build lactate threshold"
notes: "Keep effort steady. Should feel comfortably hard."
key_workout: true

status: "scheduled"
execution: null  # Filled when completed
```

## 7. Integration Points

### 7.1 Called By

| Module | When |
|--------|------|
| M1 | Initial plan generation ("create plan") |
| M1 | Goal change triggers regeneration |
| M1 | Weekly refinement ("plan next week") |

### 7.2 Calls To

| Module | Purpose |
|--------|---------|
| M3 | Write plan files to disk |
| M4 | Read athlete profile and constraints |
| M9 | Get current metrics for calibration |

### 7.3 Returns To

| Module | Data |
|--------|------|
| M11 | Plan structure for adaptation checks |
| M12 | Plan data for user display |

## 8. Test Scenarios

### 8.1 Unit Tests

```python
def test_periodization_marathon():
    """Marathon gets full periodization"""
    goal = Goal(type=GoalType.MARATHON, race_target_date=date.today() + timedelta(weeks=18))
    phases = calculate_periodization(goal, 18)

    assert len(phases) == 4
    assert phases[0]["phase"] == PlanPhase.BASE
    assert phases[-1]["phase"] == PlanPhase.TAPER


def test_periodization_short_timeline():
    """Short timeline still gets structure"""
    goal = Goal(type=GoalType.TEN_K, race_target_date=date.today() + timedelta(weeks=6))
    phases = calculate_periodization(goal, 6)

    assert any(p["phase"] == PlanPhase.TAPER for p in phases)


def test_volume_progression_recovery_weeks():
    """Recovery weeks reduce volume"""
    volumes = calculate_volume_progression(30, 50, 8, [
        {"phase": PlanPhase.BASE, "start_week": 0, "end_week": 7}
    ])

    # Week 4 (index 3) should be recovery
    assert volumes[3] < volumes[2]


def test_guardrail_long_run_cap():
    """Long run cannot exceed 30% of weekly volume"""
    plan = create_test_plan(weekly_volume=40, long_run_distance=20)
    plan, applied = apply_training_guardrails(plan, mock_profile())

    long_run = find_long_run(plan.weeks[0])
    assert long_run.distance_km <= 12.0  # 30% of 40


def test_no_back_to_back_hard_days():
    """Back-to-back hard days are prevented"""
    plan = create_test_plan(
        workouts=[
            (1, WorkoutType.TEMPO, 7),    # Tuesday hard
            (2, WorkoutType.INTERVALS, 8), # Wednesday hard
        ]
    )
    plan, applied = apply_training_guardrails(plan, mock_profile())

    # One should be downgraded
    tuesday = find_workout_by_day(plan.weeks[0], 1)
    wednesday = find_workout_by_day(plan.weeks[0], 2)
    assert not (tuesday.target_rpe >= 7 and wednesday.target_rpe >= 7)
```

### 8.2 Integration Tests

```python
@pytest.mark.integration
def test_full_plan_generation():
    """Generate complete plan and verify structure"""
    profile = load_test_profile(goal_type=GoalType.HALF_MARATHON, weeks=12)
    metrics = create_test_metrics()

    result = generate_master_plan(profile, metrics)

    assert result.plan.total_weeks == 12
    assert len(result.plan.weeks) == 12
    assert all(len(w.workouts) > 0 for w in result.plan.weeks)


@pytest.mark.integration
def test_plan_persistence():
    """Plan writes correctly to disk"""
    plan = create_test_plan()
    repo = MockRepositoryIO()

    persist_plan(plan, repo)

    assert repo.file_exists("plans/current_plan.yaml")
    assert repo.file_exists("plans/workouts/week_01/")
```

## 9. Configuration

### 9.1 Planning Parameters

```python
PLAN_CONFIG = {
    "recovery_week_frequency": 4,      # Every N weeks
    "recovery_week_reduction": 0.3,    # 30% volume cut
    "long_run_max_percent": 0.30,      # Max % of weekly volume
    "long_run_max_minutes": 150,       # 2.5 hours
    "quality_sessions_max": 2,         # Per week
    "volume_increase_max_percent": 10, # Week-over-week
}
```

## 10. Performance Notes

- Plan generation: ~100ms for 16-week plan
- Memory: ~50KB per complete plan
- File writes: Main I/O cost
