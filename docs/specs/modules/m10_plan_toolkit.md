# M10 — Plan Toolkit

## 1. Metadata

| Field        | Value                                           |
| ------------ | ----------------------------------------------- |
| Module ID    | M10                                             |
| Name         | Plan Toolkit                                    |
| Code Module  | `core/plan.py`                                  |
| Version      | 2.0.0                                           |
| Status       | Draft                                           |
| Dependencies | M3 (Repository I/O), M4 (Profile), M9 (Metrics) |

## 2. Purpose

Provides computational tools for training plan design. Claude Code uses these toolkit functions to design personalized training plans workout by workout, considering athlete schedule, preferences, fitness level, and training science guardrails.

### 2.1 Scope Boundaries

**In Scope:**

- Periodization calculation (suggest phase allocation based on weeks and goal type)
- Volume progression (calculate week-by-week volume curves with recovery weeks)
- Volume recommendations (suggest safe start/peak volumes based on current fitness)
- Workout construction (create workouts with VDOT paces and HR zones)
- Guardrail validation (check plans against training science rules)
- Workout templates (library of standard workouts with parameters)

**Out of Scope:**

- Complete plan generation (Claude Code designs plans using toolkit)
- Workout scheduling decisions (Claude Code places workouts considering athlete schedule)
- Conflict resolution (Claude Code reasons with athlete about trade-offs)
- Volume decisions (Claude Code assesses readiness and discusses with athlete)
- Adaptation triggers (M11)
- Metrics calculation (M9)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage                                           |
| ------ | ----------------------------------------------- |
| M3     | Read/write plan files                           |
| M4     | Get athlete profile (VDOT, max_hr, preferences) |
| M9     | Get current CTL for volume recommendations      |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
```

## 4. Internal Interface

This module is called by M1 workflows and directly by Claude Code via API layer.

### 4.1 Type Definitions

```python
from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PhaseType(str, Enum):
    """Training phase types"""
    BASE = "base"           # Aerobic base building
    BUILD = "build"         # Adding intensity
    PEAK = "peak"           # Race-specific work
    TAPER = "taper"         # Pre-race recovery


class WorkoutType(str, Enum):
    """Standardized workout types"""
    EASY = "easy"
    LONG_RUN = "long_run"
    TEMPO = "tempo"
    INTERVALS = "intervals"
    REPETITIONS = "repetitions"
    RECOVERY = "recovery"
    RACE_PACE = "race_pace"
    PROGRESSION = "progression"
    FARTLEK = "fartlek"


class IntensityZone(str, Enum):
    """Intensity zones for guardrail validation"""
    LOW = "low"             # RPE 1-4
    MODERATE = "moderate"   # RPE 5-6
    HIGH = "high"           # RPE 7-10


class PhaseAllocation(BaseModel):
    """Suggested phase allocation"""
    base_weeks: int
    build_weeks: int
    peak_weeks: int
    taper_weeks: int
    total_weeks: int
    reasoning: str


class WeeklyVolume(BaseModel):
    """Suggested volume for a single week"""
    week_number: int
    volume_km: float
    is_recovery_week: bool
    phase: PhaseType
    reasoning: str


class VolumeRecommendation(BaseModel):
    """Safe volume range recommendation"""
    start_range_km: tuple[float, float]
    peak_range_km: tuple[float, float]
    rationale: str
    current_ctl: float
    goal_distance_km: float
    weeks_available: int


class WorkoutPrescription(BaseModel):
    """Complete workout prescription"""
    workout_type: WorkoutType
    duration_minutes: int
    target_rpe: int

    # VDOT-based pace zones (running)
    easy_pace: Optional[str] = None       # "6:30-7:00 min/km"
    marathon_pace: Optional[str] = None
    threshold_pace: Optional[str] = None
    interval_pace: Optional[str] = None

    # HR zones
    zone_1_hr: Optional[str] = None       # "100-120 bpm"
    zone_2_hr: Optional[str] = None
    zone_3_hr: Optional[str] = None
    zone_4_hr: Optional[str] = None
    zone_5_hr: Optional[str] = None

    # Workout structure
    structure: Optional[str] = None
    instructions: str


class GuardrailViolation(BaseModel):
    """Training science guardrail violation"""
    rule: str
    week: Optional[int] = None
    severity: str              # "info", "warning", "danger"
    actual: float
    target: float
    message: str
    suggestion: str


class DayPlan(BaseModel):
    """Single day in training plan"""
    date: date
    workout: Optional[WorkoutPrescription] = None
    notes: Optional[str] = None


class WeekPlan(BaseModel):
    """Single week in training plan"""
    week_number: int
    start_date: date
    end_date: date
    target_volume_km: float
    phase: PhaseType
    days: list[DayPlan]
    week_notes: Optional[str] = None


class Goal(BaseModel):
    """Race goal"""
    race_type: str
    target_date: date
    target_time: Optional[str] = None
    race_name: Optional[str] = None


class TrainingPlan(BaseModel):
    """Complete training plan"""
    id: str
    athlete_name: str
    goal: Goal
    created_at: date
    weeks: list[WeekPlan]
    starting_volume_km: float
    peak_volume_km: float
    designed_by: str = "claude_code"
    notes: Optional[str] = None
```

### 4.2 Toolkit Functions

```python
# Periodization
def calculate_periodization(weeks: int, goal_type: str) -> PhaseAllocation
def suggest_volume_adjustment(current_weekly_volume_km: float, current_ctl: float,
                               goal_distance_km: float, weeks_available: int) -> VolumeRecommendation
def calculate_volume_progression(starting_volume_km: float, peak_volume_km: float,
                                  weeks: int, recovery_weeks: list[int],
                                  phase_allocation: PhaseAllocation) -> list[WeeklyVolume]

# Workout construction
def create_workout(workout_type: WorkoutType, duration_minutes: int,
                   athlete_profile: "AthleteProfile", target_rpe: Optional[int] = None,
                   structure: Optional[str] = None) -> WorkoutPrescription
def get_workout_template(workout_type: WorkoutType) -> dict

# Validation
def validate_guardrails(plan: TrainingPlan, athlete_profile: "AthleteProfile") -> list[GuardrailViolation]
def validate_week(week_plan: WeekPlan, athlete_profile: "AthleteProfile") -> list[GuardrailViolation]

# Helpers
def create_downgraded_workout(original: WorkoutPrescription, target_rpe: int = 4) -> WorkoutPrescription
def create_shortened_workout(original: WorkoutPrescription, duration_minutes: int) -> WorkoutPrescription
def estimate_recovery_days(workout: WorkoutPrescription) -> int
```

### 4.3 Error Types

```python
class M10PlanningError(Exception):
    """Base exception for M10 planning errors"""
    pass

class InvalidPlanError(M10PlanningError):
    """Plan violates critical guardrails"""
    pass

class InsufficientTimeError(M10PlanningError):
    """Not enough weeks to safely prepare for goal"""
    pass
```

## 5. Core Algorithms

### 5.1 Periodization Calculation

Suggests phase allocation using standard periodization models.

**Standard Models**:

```python
templates = {
    "5k": {"base": 0.25, "build": 0.50, "peak": 0.15, "taper": 0.10},
    "10k": {"base": 0.25, "build": 0.50, "peak": 0.15, "taper": 0.10},
    "half_marathon": {"base": 0.30, "build": 0.45, "peak": 0.15, "taper": 0.10},
    "marathon": {"base": 0.35, "build": 0.40, "peak": 0.15, "taper": 0.10},
}
```

**Example**: 12 weeks, half marathon → 3w base, 6w build, 2w peak, 1w taper

Claude Code uses this as a reference and adjusts based on athlete context (e.g., existing base fitness, schedule constraints).

### 5.2 Volume Progression

Calculates week-by-week volume using linear progression with recovery weeks and taper.

**Algorithm**:

- Linear increase from starting volume to peak
- Recovery weeks: -20% from trend
- Taper: -40%, -60%, -70% in final weeks

**Example**:

```
start=35km, peak=55km, weeks=12, recovery=[4,8]
→ [35, 38, 41, 33, 44, 47, 50, 40, 53, 55, 38, 22]
```

Claude Code uses this as a baseline and adjusts individual weeks based on athlete readiness and schedule.

### 5.3 Volume Recommendation

Recommends safe starting and peak volumes based on:

- Current CTL (fitness level)
- Goal distance (need adequate volume)
- Time available (safe progression rate)
- Training science (ACWR safety, 10% rule)

**CTL-based starting volumes**:

- CTL <30 (beginner): 15-25km
- CTL 30-45 (recreational): 25-40km
- CTL 45-60 (competitive): 35-60km
- CTL >60 (elite): 50-80km

**Goal-based peak**: weekly volume = 2-3x race distance

### 5.4 Workout Construction

Creates workout prescription with VDOT paces and HR zones.

**Process**:

1. Get athlete's training paces from VDOT (M4 profile)
2. Calculate HR zones from max_hr and lthr
3. Map workout type to pace zone and target RPE
4. Generate structure and instructions

**Example**:

```python
create_workout("tempo", 40, profile)
→ WorkoutPrescription(
    workout_type="tempo",
    duration_minutes=40,
    target_rpe=7,
    threshold_pace="5:15 min/km",
    zone_4_hr="160-170 bpm",
    structure="10min warmup, 20min @ threshold, 10min cooldown",
    instructions="Run at comfortably hard pace..."
)
```

### 5.5 Guardrail Validation

Checks training plans against evidence-based rules:

**Validated Rules**:

- **80/20 distribution**: ≥80% low intensity for ≥3 run days/week
- **Max quality sessions**: ≤2-3 per week
- **Long run caps**: ≤30% weekly volume, ≤2.5 hours
- **ACWR safety**: Weekly volume changes shouldn't exceed ACWR 1.5
- **Hard/easy separation**: No back-to-back quality sessions
- **T/I/R volume limits**: Threshold ≤10%, Intervals ≤8%, Reps ≤5%

**Severity Levels**:

- **Info**: Informational, no action required
- **Warning**: Recommend adjustment, not critical
- **Danger**: High injury risk, strongly recommend change

Claude Code reviews violations and decides whether to enforce, override, or discuss with athlete.

## 6. Integration Points

### 6.1 Called By

| Caller            | Functions             | When                                  |
| ----------------- | --------------------- | ------------------------------------- |
| M1 (Workflows)    | validate_guardrails() | During plan generation workflow       |
| Claude Code (API) | All toolkit functions | When designing plans conversationally |

### 6.2 Calls

| Module | Function                  | Purpose                            |
| ------ | ------------------------- | ---------------------------------- |
| M3     | read_yaml(), write_yaml() | Persist training plans             |
| M4     | get_athlete_profile()     | Get VDOT, max_hr, preferences      |
| M9     | get_current_metrics()     | Get CTL for volume recommendations |

### 6.3 Data Flow

```
[User requests plan for half marathon in 12 weeks]
    │
    ▼
[Claude Code uses toolkit to design plan]
    │
    ├─> calculate_periodization(12, "half_marathon")
    ├─> suggest_volume_adjustment(35, 44, 21.1, 12)
    ├─> calculate_volume_progression(35, 55, 12, [4,8], phases)
    ├─> create_workout("easy", 45, profile) for each workout
    ├─> validate_guardrails(designed_plan, profile)
    └─> Reviews violations, adjusts, validates again
    │
    ▼
[Claude Code presents personalized plan to athlete]
```

## 7. Testing Requirements

### 7.1 Unit Tests

| Test Case                    | Input                             | Expected Output                  |
| ---------------------------- | --------------------------------- | -------------------------------- |
| Periodization, 12w half      | weeks=12, goal="half_marathon"    | base=3, build=6, peak=2, taper=1 |
| Volume progression, linear   | start=30, peak=60, weeks=10       | Linear increase ~3km/week        |
| Volume progression, recovery | start=30, peak=60, recovery=[4,8] | -20% on weeks 4,8                |
| Workout creation, tempo      | type="tempo", duration=40         | Threshold pace, Zone 4 HR        |
| Guardrail, 80/20 pass        | 85% low intensity                 | No violations                    |
| Guardrail, 80/20 fail        | 70% low intensity                 | Violation: warning               |
| Guardrail, ACWR spike        | ACWR=1.6                          | Violation: danger                |

### 7.2 Integration Tests

| Test Case             | Scenario                          | Validation                     |
| --------------------- | --------------------------------- | ------------------------------ |
| Full toolkit flow     | Design 12w plan using all tools   | Plan validates cleanly         |
| Guardrail enforcement | Plan with 4 quality sessions/week | Returns violation              |
| Volume recommendation | CTL=50, goal=marathon             | Recommended volumes achievable |

## 8. Performance Considerations

- **Periodization**: O(1) - Simple arithmetic
- **Volume progression**: O(n) where n=weeks
- **Workout creation**: O(1) - Lookup tables
- **Guardrail validation**: O(n×m) where n=weeks, m=workouts/week

**Total planning toolkit latency**: <100ms for full 16-week plan validation

## 9. Workout Type Reference

| Workout Type | RPE  | Pace Zone  | HR Zone  | Purpose           | Frequency |
| ------------ | ---- | ---------- | -------- | ----------------- | --------- |
| Easy         | 3-4  | Easy       | Zone 2   | Aerobic base      | 3-5x/week |
| Long Run     | 4-5  | Easy       | Zone 2   | Endurance         | 1x/week   |
| Tempo        | 7    | Threshold  | Zone 4   | Lactate threshold | 1x/week   |
| Intervals    | 8-9  | Interval   | Zone 5   | VO2max            | 0-1x/week |
| Repetitions  | 9-10 | Repetition | Zone 5   | Speed             | 0-1x/week |
| Recovery     | 2-3  | Easy       | Zone 1-2 | Active recovery   | As needed |

---

**END OF M10 SPEC**
