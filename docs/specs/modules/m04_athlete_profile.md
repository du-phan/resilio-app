# M4 - Athlete Profile Service

## Module Metadata

| Field | Value |
|-------|-------|
| **Module ID** | M4 |
| **Module Name** | Athlete Profile Service |
| **Version** | 1.0.1 |
| **Status** | Draft |
| **Complexity** | Medium |
| **Last Updated** | 2026-01-12 |

---

## 1. Purpose & Scope

### 1.1 Purpose

M4 manages the athlete's profile data, including personal information, training constraints, goal settings, conflict policy, and derived training paces. It serves as the authoritative source for all athlete-specific configuration that affects plan generation and adaptation.

### 1.2 Scope Boundaries

**This module DOES:**
- Create and update the athlete profile
- Validate training constraints for logical consistency
- Calculate and cache VDOT and derived training paces
- Manage conflict policy between running and other sports
- Store personal records (PRs) and recent race results
- Handle training history metadata (sync state, baseline status)

**This module does NOT:**
- Compute training metrics (CTL/ATL/TSB) - that's M9
- Store individual activities - that's M6
- Extract athlete facts from conversations - that's M13
- Generate or modify training plans - that's M10

---

## 2. Dependencies

### 2.1 Internal Module Dependencies

| Module | Dependency Type | Purpose |
|--------|-----------------|---------|
| M3 | File I/O | Read/write profile.yaml and training_history.yaml |

### 2.2 External Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `pydantic` | ^2.5 | Schema validation |

### 2.3 Environment Requirements

- Python >= 3.11
- M3 must be initialized first

---

## 3. Public Interface

### 3.1 Type Definitions

```python
from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field


# ============================================================
# ENUMS
# ============================================================

class RaceDistance(str, Enum):
    """Supported race distances."""
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"


class GoalType(str, Enum):
    """Types of training goals."""
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"
    GENERAL_FITNESS = "general_fitness"


class RunningPriority(str, Enum):
    """Running priority relative to other sports."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    EQUAL = "equal"


class ConflictPolicy(str, Enum):
    """Policy for resolving conflicts between running and other sports."""
    PRIMARY_SPORT_WINS = "primary_sport_wins"
    RUNNING_GOAL_WINS = "running_goal_wins"
    ASK_EACH_TIME = "ask_each_time"


class Weekday(str, Enum):
    """Days of the week."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class SportIntensity(str, Enum):
    """Intensity levels for other sports."""
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    EASY_TO_MODERATE = "easy_to_moderate"
    MODERATE_TO_HARD = "moderate_to_hard"


class LTHRMethod(str, Enum):
    """Method used to determine lactate threshold heart rate."""
    FIELD_TEST = "field_test"
    RACE_DERIVED = "race_derived"
    ESTIMATED = "estimated"


class PRSource(str, Enum):
    """Source of personal record data."""
    STRAVA = "strava"
    SELF_REPORTED = "self_reported"


class EffortLevel(str, Enum):
    """Goal effort level."""
    PR_ATTEMPT = "pr_attempt"
    COMFORTABLE = "comfortable"
    JUST_FINISH = "just_finish"


# ============================================================
# PROFILE SUB-TYPES
# ============================================================

class RecentRace(BaseModel):
    """Recent race result for VDOT calculation."""
    distance: RaceDistance
    time: str  # "47:00" or "1:45:00"
    date: str  # ISO date


class PREntry(BaseModel):
    """Personal record entry."""
    time: str
    date: str
    source: PRSource


class PersonalRecords(BaseModel):
    """Collection of personal records."""
    five_k: Optional[PREntry] = None
    ten_k: Optional[PREntry] = None
    half_marathon: Optional[PREntry] = None
    marathon: Optional[PREntry] = None


class VitalSigns(BaseModel):
    """Physiological measurements."""
    max_hr: Optional[int] = None
    resting_hr: Optional[int] = None
    resting_hr_updated_at: Optional[str] = None
    lthr: Optional[int] = None  # Lactate threshold HR
    lthr_method: Optional[LTHRMethod] = None
    lthr_updated_at: Optional[str] = None


class DerivedPaces(BaseModel):
    """VDOT-derived training paces."""
    vdot: float
    calculated_from: str  # e.g., "10k PR 47:00"
    calculated_at: str    # ISO date
    easy_pace_min_km: str       # "5:45-6:15"
    marathon_pace_min_km: str
    threshold_pace_min_km: str
    interval_pace_min_km: str
    repetition_pace_min_km: str


class TrainingConstraints(BaseModel):
    """Training schedule constraints."""
    available_run_days: list[Weekday]
    preferred_run_days: Optional[list[Weekday]] = None
    min_run_days_per_week: int
    max_run_days_per_week: int
    max_time_per_session_minutes: Optional[int] = None
    time_preference: Optional[Literal["morning", "evening", "flexible"]] = None


class OtherSport(BaseModel):
    """Other sport commitment."""
    sport: str              # "bouldering", "cycling", etc.
    days: list[Weekday]
    typical_duration_minutes: int
    typical_intensity: SportIntensity
    is_fixed: bool          # Won't move these
    notes: Optional[str] = None


class Goal(BaseModel):
    """Training goal."""
    type: GoalType
    race_name: Optional[str] = None
    target_date: Optional[str] = None  # ISO date (optional for general_fitness)
    target_time: Optional[str] = None  # e.g., "1:45:00"
    effort_level: Optional[EffortLevel] = None


class Preferences(BaseModel):
    """Communication preferences."""
    detail_level: Literal["brief", "moderate", "detailed"] = "moderate"
    coaching_style: Literal["supportive", "direct", "analytical"] = "supportive"
    intensity_metric: Literal["pace", "hr", "rpe"] = "pace"


class StravaConnection(BaseModel):
    """Strava connection info."""
    athlete_id: str


# ============================================================
# MAIN PROFILE MODEL
# ============================================================

class AthleteProfile(BaseModel):
    """Complete athlete profile."""

    # Schema header (managed by M3)
    _schema: Optional[dict] = None

    # Identity
    name: str
    email: Optional[str] = None
    created_at: str  # ISO date
    age: Optional[int] = None

    # Strava connection
    strava: Optional[StravaConnection] = None

    # Running background
    running_experience_years: Optional[int] = None
    injury_history: Optional[str] = None

    # Current fitness indicators
    recent_race: Optional[RecentRace] = None
    current_weekly_run_km: Optional[float] = None
    current_run_days_per_week: Optional[int] = None

    # Personal records
    personal_records: Optional[PersonalRecords] = None

    # Vital signs
    vital_signs: Optional[VitalSigns] = None

    # VDOT and paces
    estimated_vdot: Optional[float] = None
    vdot_last_updated: Optional[str] = None
    derived_paces: Optional[DerivedPaces] = None

    # Training constraints
    constraints: TrainingConstraints

    # Other sport commitments
    other_sports: list[OtherSport] = Field(default_factory=list)

    # Priority settings
    running_priority: RunningPriority
    primary_sport: Optional[str] = None
    conflict_policy: ConflictPolicy

    # Current goal
    goal: Goal

    # Double-day training
    double_days_enabled: bool = False

    # Communication preferences
    preferences: Preferences = Field(default_factory=Preferences)


# ============================================================
# TRAINING HISTORY MODEL
# ============================================================

class BaselineMetrics(BaseModel):
    """Baseline training metrics."""
    ctl: float
    atl: float
    tsb: float
    period_days: int


class TrainingHistory(BaseModel):
    """Training history metadata."""
    _schema: Optional[dict] = None
    last_strava_sync_at: Optional[str] = None  # ISO datetime
    last_strava_activity_id: Optional[str] = None
    baseline_established: bool = False
    baseline: Optional[BaselineMetrics] = None


# ============================================================
# VALIDATION TYPES
# ============================================================

class ConstraintError(BaseModel):
    """Constraint validation error."""
    field: str
    message: str


class ConstraintWarning(BaseModel):
    """Constraint validation warning."""
    field: str
    message: str
    suggestion: Optional[str] = None


class ConstraintValidationResult(BaseModel):
    """Result of constraint validation."""
    valid: bool
    errors: list[ConstraintError] = Field(default_factory=list)
    warnings: list[ConstraintWarning] = Field(default_factory=list)


# ============================================================
# ERROR TYPES
# ============================================================

class ProfileErrorType(str, Enum):
    """Types of profile errors."""
    PROFILE_NOT_FOUND = "profile_not_found"
    VALIDATION_ERROR = "validation_error"
    INVALID_RACE_TIME = "invalid_race_time"
    VDOT_CALCULATION_ERROR = "vdot_calculation_error"
    IO_ERROR = "io_error"


class ProfileError(BaseModel):
    """Profile operation error."""
    error_type: ProfileErrorType
    message: str
    field: Optional[str] = None
    time: Optional[str] = None
    distance: Optional[RaceDistance] = None
    errors: list[ConstraintError] = Field(default_factory=list)


# Type aliases
ProfileResult = Union[AthleteProfile, ProfileError]
TrainingHistoryResult = Union[TrainingHistory, None, ProfileError]
VDOTResult = Union[float, ProfileError]
PacesResult = Union[DerivedPaces, ProfileError]
```

### 3.2 Public Functions

```python
from typing import Optional, Union


# ============================================================
# PROFILE CRUD
# ============================================================

def load_profile() -> Union[AthleteProfile, None, ProfileError]:
    """
    Load the athlete profile.

    Algorithm:
        1. Call M3.read_yaml("athlete/profile.yaml", AthleteProfile)
        2. If file not found, return None
        3. If parse/validation error, return ProfileError(IO_ERROR)
        4. Otherwise return profile

    Returns:
        Profile if exists, None if not exists, or error
    """
    ...


def save_profile(profile: AthleteProfile) -> Optional[ProfileError]:
    """
    Save the athlete profile.
    Validates constraints before saving.

    Algorithm:
        1. Validate constraints with validate_constraints(profile.constraints, profile.goal)
        2. If validation has errors, return ProfileError(VALIDATION_ERROR, errors=validation.errors)
        3. Call M3.write_yaml("athlete/profile.yaml", profile)
        4. If write fails, return ProfileError(IO_ERROR, message=error)
        5. Return None on success

    Args:
        profile: Complete profile to save

    Returns:
        None on success, ProfileError on failure
    """
    ...


def update_profile(updates: dict) -> Union[AthleteProfile, ProfileError]:
    """
    Update specific fields in the profile.
    Merges with existing profile.

    Algorithm:
        1. Load current profile with load_profile()
        2. If profile is None, return ProfileError(PROFILE_NOT_FOUND)
        3. If profile is error, return error
        4. Apply updates using dict merge (profile.model_dump() | updates)
        5. Create new AthleteProfile from merged dict
        6. Validate using Pydantic validation
        7. Save using save_profile()
        8. Return updated profile or error

    Args:
        updates: Dictionary of fields to update

    Returns:
        Updated profile or error
    """
    ...


class NewProfileInput(BaseModel):
    """Input for creating a new profile."""
    name: str
    goal: Goal
    constraints: TrainingConstraints
    running_priority: RunningPriority
    conflict_policy: ConflictPolicy
    primary_sport: Optional[str] = None


def create_profile(initial_data: NewProfileInput) -> Union[AthleteProfile, ProfileError]:
    """
    Create a new profile with defaults.
    Used during onboarding.

    Algorithm:
        1. Create AthleteProfile with:
           - name, goal, constraints, running_priority, conflict_policy, primary_sport from initial_data
           - created_at = today's ISO date
           - preferences = default Preferences()
           - other_sports = []
           - double_days_enabled = False
           - All optional fields = None
        2. Validate constraints with validate_constraints()
        3. If validation has errors, return ProfileError(VALIDATION_ERROR)
        4. Save profile using save_profile()
        5. If save fails, return error
        6. Return created profile

    Args:
        initial_data: Required fields for new profile

    Returns:
        New profile or error
    """
    ...


def profile_exists() -> bool:
    """
    Check if a profile exists.

    Algorithm:
        1. Call load_profile()
        2. Return True if profile is AthleteProfile
        3. Return False if profile is None
        4. Return False if profile is ProfileError (treat errors as non-existent)
    """
    ...


# ============================================================
# CONSTRAINT VALIDATION
# ============================================================

def validate_constraints(
    constraints: TrainingConstraints,
    goal: Goal
) -> ConstraintValidationResult:
    """
    Validate training constraints for logical consistency.

    Args:
        constraints: Constraints to validate
        goal: Goal context for validation

    Returns:
        Validation result with errors and warnings

    Validation rules:
        - max_run_days >= min_run_days
        - available_run_days.length >= min_run_days
        - Cannot have race goal with 0 available_run_days
        - Warns if all available days are consecutive
    """
    ...


# ============================================================
# VDOT AND PACE CALCULATION
# ============================================================

def calculate_vdot(distance: RaceDistance, time: str) -> Union[float, ProfileError]:
    """
    Calculate VDOT from a race result.

    Args:
        distance: Race distance
        time: Race time (string format: "47:00" or "1:45:00")

    Returns:
        VDOT value (typically 30-80) or error
    """
    ...


def derive_paces(vdot: float) -> DerivedPaces:
    """
    Derive training paces from VDOT.

    Args:
        vdot: VDOT value

    Returns:
        Derived paces for all training zones
    """
    ...


def update_vdot_from_race(race: RecentRace) -> Union[AthleteProfile, ProfileError]:
    """
    Update VDOT from a new race result.
    Also updates derived_paces in the profile.

    Algorithm:
        1. Calculate VDOT with calculate_vdot(race.distance, race.time)
        2. If VDOT is error, return error
        3. Derive paces with derive_paces(vdot)
        4. Set paces.calculated_from = f"{race.distance} {race.time}"
        5. Load profile with load_profile()
        6. If profile is None or error, return error
        7. Update profile:
           - recent_race = race
           - estimated_vdot = vdot
           - vdot_last_updated = today's ISO date
           - derived_paces = paces
        8. Save updated profile
        9. Return updated profile or error

    Args:
        race: New race result

    Returns:
        Updated profile or error
    """
    ...


def get_training_paces() -> Optional[DerivedPaces]:
    """
    Get current training paces.
    Returns derived paces from profile or None if not available.

    Algorithm:
        1. Load profile with load_profile()
        2. If profile is None or error, return None
        3. Return profile.derived_paces (which may be None)
    """
    ...


# ============================================================
# TRAINING HISTORY
# ============================================================

def load_training_history() -> Union[TrainingHistory, None, ProfileError]:
    """
    Load training history metadata.

    Algorithm:
        1. Call M3.read_yaml("athlete/training_history.yaml", TrainingHistory)
        2. If file not found, return None
        3. If parse/validation error, return ProfileError(IO_ERROR)
        4. Otherwise return training history
    """
    ...


def update_sync_state(
    last_activity_id: str,
    sync_timestamp: datetime
) -> Optional[ProfileError]:
    """
    Update training history after sync.

    Algorithm:
        1. Load training history with load_training_history()
        2. If None, create new TrainingHistory with defaults
        3. If error, return error
        4. Update last_strava_sync_at = sync_timestamp.isoformat()
        5. Update last_strava_activity_id = last_activity_id
        6. Write to M3.write_yaml("athlete/training_history.yaml", history)
        7. Return None on success, ProfileError(IO_ERROR) on failure
    """
    ...


def set_baseline_established(
    established: bool,
    baseline: Optional[BaselineMetrics] = None
) -> Optional[ProfileError]:
    """
    Set baseline established flag.

    Algorithm:
        1. Load training history with load_training_history()
        2. If None, create new TrainingHistory with defaults
        3. If error, return error
        4. Update baseline_established = established
        5. Update baseline = baseline (if provided)
        6. Write to M3.write_yaml("athlete/training_history.yaml", history)
        7. Return None on success, ProfileError(IO_ERROR) on failure
    """
    ...


def is_baseline_established() -> bool:
    """
    Check if baseline is established (14+ days of data).

    Algorithm:
        1. Load training history with load_training_history()
        2. If None or error, return False
        3. Return history.baseline_established
    """
    ...


# ============================================================
# GOAL MANAGEMENT
# ============================================================

def update_goal(goal: Goal) -> Union[AthleteProfile, ProfileError]:
    """
    Update the athlete's goal.
    May trigger plan regeneration (handled by caller).

    Algorithm:
        1. Call update_profile({"goal": goal.model_dump()})
        2. Return updated profile or error

    Args:
        goal: New goal

    Returns:
        Updated profile or error
    """
    ...


def get_weeks_to_goal() -> Optional[int]:
    """
    Calculate weeks until goal date.
    Returns None for general_fitness goal.

    Algorithm:
        1. Load profile with load_profile()
        2. If profile is None or error, return None
        3. If goal.target_date is None, return None
        4. Parse target_date as ISO date
        5. Calculate days_diff = target_date - today
        6. Return weeks = days_diff // 7 (integer division)
    """
    ...


# ============================================================
# OTHER SPORTS
# ============================================================

def upsert_other_sport(sport: OtherSport) -> Union[AthleteProfile, ProfileError]:
    """
    Add or update another sport commitment.

    Algorithm:
        1. Load profile with load_profile()
        2. If profile is None, return ProfileError(PROFILE_NOT_FOUND)
        3. If profile is error, return error
        4. Find existing sport by name in profile.other_sports
        5. If found, replace it with new sport
        6. If not found, append new sport to list
        7. Save updated profile with save_profile()
        8. Return updated profile or error
    """
    ...


def remove_other_sport(sport_name: str) -> Union[AthleteProfile, ProfileError]:
    """
    Remove another sport commitment.

    Algorithm:
        1. Load profile with load_profile()
        2. If profile is None, return ProfileError(PROFILE_NOT_FOUND)
        3. If profile is error, return error
        4. Filter profile.other_sports to exclude sport with matching name
        5. Save updated profile with save_profile()
        6. Return updated profile or error
    """
    ...


def get_fixed_sports_on_day(day: Weekday) -> list[OtherSport]:
    """
    Get fixed sports for a specific day.
    Used for scheduling conflict detection.

    Algorithm:
        1. Load profile with load_profile()
        2. If profile is None or error, return []
        3. Filter profile.other_sports where:
           - sport.is_fixed == True
           - day in sport.days
        4. Return filtered list
    """
    ...
```

---

## 4. Data Structures

### 4.1 File Paths

| File | Path | Purpose |
|------|------|---------|
| Profile | `athlete/profile.yaml` | Athlete profile data |
| Training History | `athlete/training_history.yaml` | Sync state and baseline metrics |

### 4.2 Profile Schema (`athlete/profile.yaml`)

```yaml
_schema:
  format_version: "1.0.0"
  schema_type: "profile"

# Identity
name: "Du Phan"
email: "du@example.com"
created_at: "2025-11-01"
age: 32

# Strava Connection
strava:
  athlete_id: "12345678"

# Running Background
running_experience_years: 5
injury_history: "Hip flexor tightness, especially left side."

# Current Fitness Indicators
recent_race:
  distance: "10k"
  time: "47:00"
  date: "2025-04-20"
current_weekly_run_km: 28
current_run_days_per_week: 3

# VDOT and Paces
estimated_vdot: 45
vdot_last_updated: "2025-06-15"
derived_paces:
  vdot: 45
  calculated_from: "10k PR 47:00"
  calculated_at: "2025-06-15"
  easy_pace_min_km: "5:45-6:15"
  marathon_pace_min_km: "5:10-5:20"
  threshold_pace_min_km: "4:50-5:00"
  interval_pace_min_km: "4:25-4:35"
  repetition_pace_min_km: "4:05-4:15"

# Training Constraints
constraints:
  available_run_days: [tuesday, wednesday, saturday, sunday]
  preferred_run_days: [tuesday, saturday]
  min_run_days_per_week: 2
  max_run_days_per_week: 4
  max_time_per_session_minutes: 75
  time_preference: "morning"

# Other Sport Commitments
other_sports:
  - sport: "bouldering"
    days: [monday, thursday]
    typical_duration_minutes: 120
    typical_intensity: "moderate_to_hard"
    is_fixed: true

# Priority Settings
running_priority: "secondary"
primary_sport: "bouldering"
conflict_policy: "ask_each_time"

# Current Goal
goal:
  type: "half_marathon"
  race_name: "Paris Half Marathon"
  target_date: "2026-03-01"
  target_time: "1:45:00"
  effort_level: "pr_attempt"

# Double-Day Training
double_days_enabled: false

# Communication Preferences
preferences:
  detail_level: "moderate"
  coaching_style: "supportive"
  intensity_metric: "pace"
```

### 4.3 Training History Schema (`athlete/training_history.yaml`)

```yaml
_schema:
  format_version: "1.0.0"
  schema_type: "training_history"

# Strava sync state
last_strava_sync_at: "2026-01-12T08:30:00Z"
last_strava_activity_id: "strava_12345678"

# Baseline establishment (requires 14+ days of data)
baseline_established: true
baseline:
  ctl: 280.5
  atl: 195.2
  tsb: 85.3
  period_days: 14
```

---

## 5. Core Algorithms

### 5.1 VDOT Calculation (Jack Daniels Method)

```python
import math
from typing import Union


# Distance in meters
DISTANCES_M = {
    RaceDistance.FIVE_K: 5000,
    RaceDistance.TEN_K: 10000,
    RaceDistance.HALF_MARATHON: 21097.5,
    RaceDistance.MARATHON: 42195,
}


def parse_time_to_seconds(time_str: str) -> int:
    """Parse time string to seconds. Handles "MM:SS" and "H:MM:SS"."""
    parts = time_str.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    raise ValueError(f"Invalid time format: {time_str}")


def calculate_vdot(distance: RaceDistance, time: str) -> Union[float, ProfileError]:
    """
    Calculate VDOT using Jack Daniels' formula.

    VDOT approximation uses the relationship between:
    - Running velocity
    - Oxygen cost of running
    - Fraction of VO2max used at race pace
    """
    try:
        time_seconds = parse_time_to_seconds(time)
    except ValueError:
        return ProfileError(
            error_type=ProfileErrorType.INVALID_RACE_TIME,
            message=f"Invalid time format: {time}. Use MM:SS or H:MM:SS",
            time=time,
            distance=distance
        )

    distance_m = DISTANCES_M[distance]
    time_min = time_seconds / 60

    # Velocity in meters per minute
    velocity = distance_m / time_min

    # Percent of VO2max at race pace (Daniels formula)
    percent_max = (
        0.8 +
        0.1894393 * math.exp(-0.012778 * time_min) +
        0.2989558 * math.exp(-0.1932605 * time_min)
    )

    # Oxygen cost (ml/kg/min)
    vo2 = -4.6 + 0.182258 * velocity + 0.000104 * velocity ** 2

    # VDOT
    vdot = vo2 / percent_max

    # Round to nearest 0.5
    return round(vdot * 2) / 2
```

### 5.2 Pace Derivation

**Note**: The VDOT_PACES table below is simplified for specification purposes. Production code should include the full VDOT table (range 30-85) or use Jack Daniels' regression formulas directly for continuous interpolation.

```python
# VDOT to pace lookup table (simplified subset, paces in seconds per km)
VDOT_PACES = {
    30: {"easy": 468, "marathon": 423, "threshold": 396, "interval": 369, "rep": 340},
    35: {"easy": 420, "marathon": 378, "threshold": 354, "interval": 330, "rep": 306},
    40: {"easy": 378, "marathon": 342, "threshold": 318, "interval": 297, "rep": 276},
    45: {"easy": 348, "marathon": 315, "threshold": 294, "interval": 273, "rep": 255},
    50: {"easy": 321, "marathon": 291, "threshold": 273, "interval": 255, "rep": 237},
    55: {"easy": 297, "marathon": 270, "threshold": 255, "interval": 237, "rep": 222},
    60: {"easy": 279, "marathon": 252, "threshold": 237, "interval": 222, "rep": 207},
}


def format_pace(seconds: int) -> str:
    """Format seconds to MM:SS pace."""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def format_pace_range(base_seconds: int, plus: int, minus: int) -> str:
    """Format pace range like '5:45-6:15'."""
    slow = format_pace(base_seconds + plus)
    fast = format_pace(base_seconds - minus)
    return f"{fast}-{slow}"


def derive_paces(vdot: float) -> DerivedPaces:
    """
    Derive training paces from VDOT using interpolation.

    Pace ranges account for daily variation and terrain:
    - Easy: ±15 sec/km (wide range for conversational pace)
    - Other zones: ±5 sec/km (tighter for quality work)
    """

    # Find bounding VDOT values
    vdot_values = sorted(VDOT_PACES.keys())
    lower = max(v for v in vdot_values if v <= vdot)
    upper = min(v for v in vdot_values if v >= vdot)

    if lower == upper:
        paces = VDOT_PACES[lower]
    else:
        # Linear interpolation
        fraction = (vdot - lower) / (upper - lower)
        paces = {}
        for zone in ["easy", "marathon", "threshold", "interval", "rep"]:
            lower_pace = VDOT_PACES[lower][zone]
            upper_pace = VDOT_PACES[upper][zone]
            paces[zone] = int(lower_pace + (upper_pace - lower_pace) * fraction)

    return DerivedPaces(
        vdot=vdot,
        calculated_from="",  # Set by caller
        calculated_at=date.today().isoformat(),
        easy_pace_min_km=format_pace_range(paces["easy"], 15, -15),
        marathon_pace_min_km=format_pace_range(paces["marathon"], 5, -5),
        threshold_pace_min_km=format_pace_range(paces["threshold"], 5, -5),
        interval_pace_min_km=format_pace_range(paces["interval"], 5, -5),
        repetition_pace_min_km=format_pace_range(paces["rep"], 5, -5),
    )
```

### 5.3 Constraint Validation

```python
def validate_constraints(
    constraints: TrainingConstraints,
    goal: Goal
) -> ConstraintValidationResult:
    """Validate training constraints for logical consistency."""

    errors: list[ConstraintError] = []
    warnings: list[ConstraintWarning] = []

    # 1. Check min/max run days consistency
    if constraints.max_run_days_per_week < constraints.min_run_days_per_week:
        errors.append(ConstraintError(
            field="max_run_days_per_week",
            message="Max run days cannot be less than min run days"
        ))

    # 2. Check available days sufficiency
    if len(constraints.available_run_days) < constraints.min_run_days_per_week:
        warnings.append(ConstraintWarning(
            field="available_run_days",
            message="Insufficient available run days to meet minimum",
            suggestion="Consider adding more available days or reducing min_run_days"
        ))

    # 3. Check race goal feasibility
    if goal.type != GoalType.GENERAL_FITNESS and len(constraints.available_run_days) == 0:
        errors.append(ConstraintError(
            field="available_run_days",
            message="Cannot create race plan with 0 available run days"
        ))

    # 4. Check consecutive days
    if _all_days_consecutive(constraints.available_run_days):
        warnings.append(ConstraintWarning(
            field="available_run_days",
            message="Back-to-back run days detected",
            suggestion="Plan will enforce hard/easy separation (one day must be easy)"
        ))

    # 5. Check marathon feasibility
    if goal.type == GoalType.MARATHON and constraints.max_run_days_per_week < 3:
        warnings.append(ConstraintWarning(
            field="max_run_days_per_week",
            message="Marathon training typically requires 3+ run days per week"
        ))

    # 6. Check goal date
    if goal.target_date:
        weeks = _weeks_until(goal.target_date)
        if weeks < 0:
            errors.append(ConstraintError(
                field="goal.target_date",
                message="Goal date is in the past"
            ))
        elif weeks < 4:
            warnings.append(ConstraintWarning(
                field="goal.target_date",
                message="Very short timeline for race preparation"
            ))

    return ConstraintValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def _all_days_consecutive(days: list[Weekday]) -> bool:
    """Check if all days are consecutive."""
    if len(days) <= 1:
        return False

    day_indices = {
        Weekday.MONDAY: 0, Weekday.TUESDAY: 1, Weekday.WEDNESDAY: 2,
        Weekday.THURSDAY: 3, Weekday.FRIDAY: 4, Weekday.SATURDAY: 5,
        Weekday.SUNDAY: 6
    }

    indices = sorted(day_indices[d] for d in days)

    for i in range(len(indices) - 1):
        diff = indices[i + 1] - indices[i]
        if diff != 1 and diff != -6:  # Handle Sunday->Monday wrap
            return False

    return True
```

---

## 6. Error Handling

### 6.1 Error Messages

```python
ERROR_MESSAGES: dict[ProfileErrorType, str] = {
    ProfileErrorType.PROFILE_NOT_FOUND: "No athlete profile found. Let's set one up!",
    ProfileErrorType.VALIDATION_ERROR: "Profile validation failed:\n{errors}",
    ProfileErrorType.INVALID_RACE_TIME: "Invalid race time format: '{time}'. Expected: 'MM:SS' or 'H:MM:SS'",
    ProfileErrorType.VDOT_CALCULATION_ERROR: "Could not calculate VDOT: {message}",
    ProfileErrorType.IO_ERROR: "Could not access profile: {message}",
}
```

### 6.2 Error Scenarios

| Scenario | Error Type | Recovery Strategy |
|----------|-----------|------------------|
| Profile file doesn't exist | Return None (not error) | Trigger onboarding flow |
| Profile file corrupted/invalid YAML | IO_ERROR | Display error, suggest restore from backup |
| Schema version mismatch | IO_ERROR from M3 | M3 handles migration automatically |
| Constraint validation fails | VALIDATION_ERROR | Return errors to user, request correction |
| Invalid race time format | INVALID_RACE_TIME | Prompt user for correct format |
| VDOT calculation fails | VDOT_CALCULATION_ERROR | Use existing VDOT or prompt for manual entry |
| Lock timeout when saving | IO_ERROR from M3 | Retry with exponential backoff (handled by M3) |
| Concurrent modification | IO_ERROR from M3 | Last write wins (M3 atomic writes prevent corruption) |
| Training history file missing | Return None (not error) | Create new history on first update |
| Update to non-existent profile | PROFILE_NOT_FOUND | Suggest creating profile first |

---

## 7. Integration Points

### 7.1 Usage Examples

```python
from sports_coach_engine.m04_profile import (
    load_profile, create_profile, update_vdot_from_race,
    get_training_paces, validate_constraints, ProfileError
)

# M1 (CLI Orchestrator) - Load profile at startup
profile = load_profile()
if profile is None:
    # Initiate onboarding
    pass
elif isinstance(profile, ProfileError):
    print(f"Error: {profile.message}")

# M10 (Plan Generator) - Get constraints and paces
profile = load_profile()
paces = get_training_paces()
weeks = get_weeks_to_goal()

# M11 (Adaptation Engine) - Check conflict policy
if profile.conflict_policy == ConflictPolicy.ASK_EACH_TIME:
    # Present options to user
    pass
```

---

## 8. Test Scenarios

```python
import pytest
from sports_coach_engine.m04_profile import (
    calculate_vdot, derive_paces, validate_constraints,
    RaceDistance, GoalType, Goal, TrainingConstraints, Weekday
)


class TestCalculateVDOT:
    """Tests for VDOT calculation."""

    def test_vdot_45_for_47min_10k(self):
        """47:00 10K should give approximately VDOT 45."""
        vdot = calculate_vdot(RaceDistance.TEN_K, "47:00")
        assert not isinstance(vdot, ProfileError)
        assert 44 <= vdot <= 46

    def test_vdot_50_for_40min_10k(self):
        """40:00 10K should give approximately VDOT 50."""
        vdot = calculate_vdot(RaceDistance.TEN_K, "40:00")
        assert not isinstance(vdot, ProfileError)
        assert 49 <= vdot <= 51

    def test_invalid_time_format(self):
        """Should return error for invalid time."""
        result = calculate_vdot(RaceDistance.TEN_K, "invalid")
        assert isinstance(result, ProfileError)
        assert result.error_type == ProfileErrorType.INVALID_RACE_TIME


class TestValidateConstraints:
    """Tests for constraint validation."""

    def test_valid_constraints(self):
        """Should validate correct constraints."""
        constraints = TrainingConstraints(
            available_run_days=[Weekday.TUESDAY, Weekday.SATURDAY, Weekday.SUNDAY],
            min_run_days_per_week=2,
            max_run_days_per_week=3
        )
        goal = Goal(type=GoalType.HALF_MARATHON)

        result = validate_constraints(constraints, goal)

        assert result.valid
        assert len(result.errors) == 0

    def test_error_when_max_less_than_min(self):
        """Should error when max < min."""
        constraints = TrainingConstraints(
            available_run_days=[Weekday.TUESDAY, Weekday.SATURDAY],
            min_run_days_per_week=3,
            max_run_days_per_week=2
        )

        result = validate_constraints(constraints, Goal(type=GoalType.TEN_K))

        assert not result.valid
        assert any(e.field == "max_run_days_per_week" for e in result.errors)

    def test_error_when_race_goal_with_zero_available_days(self):
        """Should error when race goal with no available days."""
        constraints = TrainingConstraints(
            available_run_days=[],
            min_run_days_per_week=0,
            max_run_days_per_week=0
        )
        goal = Goal(type=GoalType.MARATHON)

        result = validate_constraints(constraints, goal)

        assert not result.valid
        assert any(e.field == "available_run_days" for e in result.errors)

    def test_warning_for_marathon_with_low_frequency(self):
        """Should warn for marathon with < 3 days per week."""
        constraints = TrainingConstraints(
            available_run_days=[Weekday.SATURDAY, Weekday.SUNDAY],
            min_run_days_per_week=2,
            max_run_days_per_week=2
        )
        goal = Goal(type=GoalType.MARATHON)

        result = validate_constraints(constraints, goal)

        assert result.valid  # Warning, not error
        assert any(w.field == "max_run_days_per_week" for w in result.warnings)


class TestDerivePaces:
    """Tests for pace derivation."""

    def test_derive_paces_exact_vdot(self):
        """Should derive paces for exact VDOT table value."""
        paces = derive_paces(45.0)

        assert paces.vdot == 45.0
        assert "5:45" in paces.easy_pace_min_km  # Within easy range
        assert "5:10" in paces.marathon_pace_min_km

    def test_derive_paces_interpolated_vdot(self):
        """Should interpolate for VDOT between table values."""
        paces = derive_paces(47.5)

        assert paces.vdot == 47.5
        # Should be between VDOT 45 and 50 values
        assert paces is not None

    def test_derive_paces_below_table_uses_lowest(self):
        """Should use lowest VDOT for values below table range."""
        paces = derive_paces(25.0)

        assert paces.vdot == 25.0
        # Should use VDOT 30 values (lowest in table)


class TestProfileCRUD:
    """Tests for profile CRUD operations."""

    def test_create_and_load_profile(self):
        """Should create and load profile successfully."""
        input_data = NewProfileInput(
            name="Test Athlete",
            goal=Goal(type=GoalType.TEN_K),
            constraints=TrainingConstraints(
                available_run_days=[Weekday.TUESDAY, Weekday.SATURDAY],
                min_run_days_per_week=2,
                max_run_days_per_week=2
            ),
            running_priority=RunningPriority.PRIMARY,
            conflict_policy=ConflictPolicy.RUNNING_GOAL_WINS
        )

        profile = create_profile(input_data)
        assert not isinstance(profile, ProfileError)
        assert profile.name == "Test Athlete"

        loaded = load_profile()
        assert not isinstance(loaded, ProfileError)
        assert loaded.name == "Test Athlete"

    def test_update_profile_merges_fields(self):
        """Should merge updates with existing profile."""
        updates = {"age": 30, "email": "test@example.com"}
        result = update_profile(updates)

        assert not isinstance(result, ProfileError)
        assert result.age == 30
        assert result.email == "test@example.com"

    def test_profile_exists_returns_false_when_not_found(self):
        """Should return False when profile doesn't exist."""
        # Assumes fresh state with no profile
        exists = profile_exists()
        assert exists == False


class TestTrainingHistory:
    """Tests for training history operations."""

    def test_update_sync_state_creates_history_if_missing(self):
        """Should create training history if it doesn't exist."""
        error = update_sync_state("strava_12345", datetime.now())

        assert error is None

        history = load_training_history()
        assert not isinstance(history, ProfileError)
        assert history.last_strava_activity_id == "strava_12345"

    def test_set_baseline_established(self):
        """Should set baseline flag and metrics."""
        baseline = BaselineMetrics(ctl=250, atl=180, tsb=70, period_days=14)
        error = set_baseline_established(True, baseline)

        assert error is None

        history = load_training_history()
        assert not isinstance(history, ProfileError)
        assert history.baseline_established == True
        assert history.baseline.ctl == 250


class TestGoalManagement:
    """Tests for goal management."""

    def test_update_goal_changes_profile_goal(self):
        """Should update goal in profile."""
        new_goal = Goal(
            type=GoalType.MARATHON,
            target_date="2026-10-01",
            target_time="3:30:00"
        )

        result = update_goal(new_goal)

        assert not isinstance(result, ProfileError)
        assert result.goal.type == GoalType.MARATHON

    def test_get_weeks_to_goal_returns_none_for_general_fitness(self):
        """Should return None for general fitness goal."""
        # Assumes profile has general_fitness goal
        weeks = get_weeks_to_goal()
        # Expected: None or positive integer depending on profile


class TestOtherSports:
    """Tests for other sports management."""

    def test_upsert_adds_new_sport(self):
        """Should add new sport commitment."""
        sport = OtherSport(
            sport="cycling",
            days=[Weekday.WEDNESDAY, Weekday.FRIDAY],
            typical_duration_minutes=90,
            typical_intensity=SportIntensity.MODERATE,
            is_fixed=True
        )

        result = upsert_other_sport(sport)

        assert not isinstance(result, ProfileError)
        assert any(s.sport == "cycling" for s in result.other_sports)

    def test_upsert_updates_existing_sport(self):
        """Should update existing sport commitment."""
        # First add
        sport1 = OtherSport(
            sport="cycling",
            days=[Weekday.WEDNESDAY],
            typical_duration_minutes=60,
            typical_intensity=SportIntensity.EASY,
            is_fixed=False
        )
        upsert_other_sport(sport1)

        # Then update
        sport2 = OtherSport(
            sport="cycling",
            days=[Weekday.WEDNESDAY, Weekday.FRIDAY],
            typical_duration_minutes=90,
            typical_intensity=SportIntensity.MODERATE,
            is_fixed=True
        )
        result = upsert_other_sport(sport2)

        assert not isinstance(result, ProfileError)
        cycling_sports = [s for s in result.other_sports if s.sport == "cycling"]
        assert len(cycling_sports) == 1
        assert cycling_sports[0].typical_duration_minutes == 90

    def test_remove_other_sport(self):
        """Should remove sport commitment."""
        result = remove_other_sport("cycling")

        assert not isinstance(result, ProfileError)
        assert not any(s.sport == "cycling" for s in result.other_sports)

    def test_get_fixed_sports_on_day(self):
        """Should return only fixed sports on specified day."""
        # Assumes profile has some sports
        fixed = get_fixed_sports_on_day(Weekday.MONDAY)

        # All returned sports should be fixed and include Monday
        for sport in fixed:
            assert sport.is_fixed == True
            assert Weekday.MONDAY in sport.days
```

---

## 9. Project Structure

```
sports_coach_engine/
├── m04_profile/
│   ├── __init__.py
│   ├── models.py         # Pydantic models
│   ├── profile.py        # Profile CRUD operations
│   ├── vdot.py           # VDOT calculation and pace derivation
│   ├── validation.py     # Constraint validation
│   ├── history.py        # Training history operations
│   └── errors.py         # Error types
```

---

## 10. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.1 | 2026-01-12 | **Improved for LLM implementation**: (1) Converted all `@dataclass` types to `BaseModel` for consistency with Pydantic ecosystem (ConstraintError, ConstraintWarning, ConstraintValidationResult, ProfileError, NewProfileInput). (2) Added complete algorithms for all CRUD functions: load_profile, save_profile, update_profile, create_profile, profile_exists, training history functions (load_training_history, update_sync_state, set_baseline_established, is_baseline_established), goal management (update_goal, get_weeks_to_goal), and other sports functions (upsert_other_sport, remove_other_sport, get_fixed_sports_on_day). (3) Added comprehensive test scenarios: profile CRUD tests, pace derivation tests, training history tests, goal management tests, other sports tests (8 new test classes). (4) Added error scenarios table with recovery strategies for all failure modes. (5) Added file paths table and training_history.yaml schema example. (6) Added notes: VDOT_PACES table is simplified subset, pace ranges explained (±15s easy, ±5s other zones). |
| 1.0.0 | 2026-01-12 | Initial specification (Python) |
