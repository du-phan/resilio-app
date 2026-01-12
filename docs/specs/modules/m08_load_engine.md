# M8 — Load Engine

## 1. Metadata

| Field | Value |
|-------|-------|
| Module ID | M8 |
| Name | Load Engine |
| Code Module | `core/load.py` |
| Version | 1.0.2 |
| Status | Draft |
| Dependencies | M3 (Repository I/O), M6 (Activity Normalization), M7 (Notes & RPE Analyzer) |

## 2. Purpose

Compute training load values for each activity using the two-channel load model. Produces systemic load (drives CTL/ATL/TSB) and lower-body load (gates quality running sessions) values that form the foundation for all training metrics.

### 2.1 Scope Boundaries

**In Scope:**
- Computing base_effort_au from RPE and duration
- Applying sport-specific multipliers (systemic and lower-body)
- Adjusting multipliers based on workout characteristics
- Assigning session type (easy/moderate/quality/race)
- Handling unknown sports with conservative defaults
- Persisting calculated fields to activity files

**Out of Scope:**
- Aggregating daily/weekly loads (M9)
- Computing CTL/ATL/TSB (M9)
- Estimating RPE (M7)
- Activity normalization (M6)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage |
|--------|-------|
| M3 | Update activity files with calculated fields |
| M6 | Receives normalized activities |
| M7 | Receives RPE estimates |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
```

## 4. Internal Interface

**Note:** This module is called internally by M1 workflows as part of the sync pipeline. Claude Code should NOT import from `core/load.py` directly.

### 4.1 Type Definitions

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SessionType(str, Enum):
    """Training session intensity classification"""
    EASY = "easy"           # Recovery, zone 1-2, RPE 1-4
    MODERATE = "moderate"   # Steady-state, zone 3, RPE 5-6
    QUALITY = "quality"     # Tempo, intervals, threshold, RPE 7-8
    RACE = "race"           # Competition or time trial, RPE 9-10


class SportMultipliers(BaseModel):
    """Load multipliers for a sport type"""
    sport: str
    systemic: float       # 0.0 - 1.5
    lower_body: float     # 0.0 - 1.5
    description: str


class LoadCalculation(BaseModel):
    """Complete load calculation for an activity"""
    activity_id: str

    # Input values
    duration_minutes: int
    estimated_rpe: int
    sport_type: str
    surface_type: Optional[str] = None

    # Base calculation
    base_effort_au: float

    # Multipliers used
    systemic_multiplier: float
    lower_body_multiplier: float
    multiplier_adjustments: list[str] = Field(default_factory=list)  # Explanations for any adjustments

    # Final loads
    systemic_load_au: float
    lower_body_load_au: float

    # Session classification
    session_type: SessionType


class MultiplierAdjustment(BaseModel):
    """Record of an adjustment made to base multipliers"""
    reason: str
    channel: str  # "systemic" | "lower_body"
    original: float
    adjusted: float
```

### 4.2 Default Sport Multipliers

```python
# From PRD Section 1 - canonical multiplier table
DEFAULT_MULTIPLIERS: dict[str, SportMultipliers] = {
    # Running variants
    "run": SportMultipliers("run", 1.00, 1.00, "Road/general running"),
    "trail_run": SportMultipliers("trail_run", 1.05, 1.10, "Trail running (more impact)"),
    "treadmill_run": SportMultipliers("treadmill_run", 1.00, 0.90, "Treadmill (reduced impact)"),
    "track_run": SportMultipliers("track_run", 1.00, 1.00, "Track running"),

    # Cycling
    "cycle": SportMultipliers("cycle", 0.85, 0.35, "Cycling (low leg impact)"),

    # Swimming
    "swim": SportMultipliers("swim", 0.70, 0.10, "Swimming (minimal leg load)"),

    # Climbing
    "climb": SportMultipliers("climb", 0.60, 0.10, "Climbing/bouldering (upper-body)"),

    # Strength training
    "strength": SportMultipliers("strength", 0.55, 0.40, "General strength training"),

    # CrossFit
    "crossfit": SportMultipliers("crossfit", 0.75, 0.55, "CrossFit/metcon (mixed)"),

    # Hiking/Walking
    "hike": SportMultipliers("hike", 0.60, 0.50, "Hiking"),
    "walk": SportMultipliers("walk", 0.35, 0.25, "Walking"),

    # Yoga
    "yoga": SportMultipliers("yoga", 0.35, 0.10, "Flow yoga"),

    # Unknown/Other
    "other": SportMultipliers("other", 0.70, 0.30, "Unknown sport (conservative)"),
}

# Restorative activities (no training load)
ZERO_LOAD_SPORTS = {"yoga_restorative", "stretching", "meditation", "rest"}
```

### 4.3 Function Signatures

```python
from typing import Sequence


def compute_load(
    activity: "NormalizedActivity",
    rpe_estimate: int,
    analysis_result: Optional["AnalysisResult"] = None,
) -> LoadCalculation:
    """
    Compute training load for a single activity.

    Args:
        activity: Normalized activity from M6
        rpe_estimate: RPE from M7 (1-10)
        analysis_result: Optional full analysis for adjustment hints

    Returns:
        Complete load calculation with all derived values
    """
    ...


def compute_loads_batch(
    activities: Sequence["NormalizedActivity"],
    rpe_estimates: dict[str, int],
    analysis_results: Optional[dict[str, "AnalysisResult"]] = None,
) -> list[LoadCalculation]:
    """
    Compute loads for multiple activities.

    Args:
        activities: List of normalized activities
        rpe_estimates: Map of activity_id -> RPE
        analysis_results: Optional map of activity_id -> AnalysisResult

    Returns:
        List of load calculations
    """
    ...


def get_multipliers(
    sport_type: str,
    surface_type: Optional[str] = None,
) -> SportMultipliers:
    """
    Get base multipliers for a sport.

    Args:
        sport_type: Normalized sport type
        surface_type: Optional surface (for running variants)

    Returns:
        Sport multipliers (uses defaults for unknown sports)
    """
    ...


def adjust_multipliers(
    base_multipliers: SportMultipliers,
    activity: "NormalizedActivity",
    analysis_result: Optional["AnalysisResult"],
) -> tuple[float, float, list[str]]:
    """
    Apply workout-specific adjustments to multipliers.

    Adjustments:
    - Lower-body dominant strength → increase lower_body
    - Upper-body dominant → decrease lower_body
    - High intensity → slight systemic increase
    - Hills/elevation → increase both

    Returns:
        (adjusted_systemic, adjusted_lower_body, adjustment_reasons)
    """
    ...


def classify_session_type(
    sport_type: str,
    rpe: int,
    workout_type: Optional[int],
    notes_analysis: Optional["AnalysisResult"],
) -> SessionType:
    """
    Classify session intensity for 80/20 tracking.

    Args:
        sport_type: Activity sport type
        rpe: Estimated RPE (1-10)
        workout_type: Strava workout type (1=race, 2=long, 3=workout)
        notes_analysis: Optional analysis for keyword hints

    Returns:
        Session type classification
    """
    ...


def calculate_base_effort(
    duration_minutes: int,
    rpe: int,
) -> float:
    """
    Calculate base effort in Arbitrary Units (AU).

    Formula: base_effort_au = RPE × duration_minutes

    Args:
        duration_minutes: Activity duration
        rpe: Perceived exertion (1-10)

    Returns:
        Base effort in AU
    """
    ...


def persist_load_to_activity(
    activity_path: str,
    load_calc: LoadCalculation,
    repo: "RepositoryIO",
) -> None:
    """
    Update activity file with calculated load fields.

    Args:
        activity_path: Path to activity YAML file
        load_calc: Computed load values
        repo: Repository I/O instance
    """
    ...
```

### 4.4 Error Types

```python
class LoadCalculationError(Exception):
    """Base error for load computation"""
    pass


class MissingRPEError(LoadCalculationError):
    """RPE required but not provided"""
    def __init__(self, activity_id: str):
        super().__init__(f"No RPE estimate for activity {activity_id}")
        self.activity_id = activity_id


class InvalidDurationError(LoadCalculationError):
    """Duration is invalid for load calculation"""
    def __init__(self, activity_id: str, duration: int):
        super().__init__(f"Invalid duration {duration} for activity {activity_id}")
        self.activity_id = activity_id
        self.duration = duration
```

## 5. Core Algorithms

### 5.1 Load Calculation Formula

```python
def compute_load(
    activity: "NormalizedActivity",
    rpe_estimate: int,
    analysis_result: Optional["AnalysisResult"] = None,
) -> LoadCalculation:
    """
    Core load calculation implementing two-channel model.

    Formula:
        base_effort_au = RPE × duration_minutes
        systemic_load_au = base_effort_au × systemic_multiplier
        lower_body_load_au = base_effort_au × lower_body_multiplier
    """
    # Validate inputs
    if rpe_estimate < 1 or rpe_estimate > 10:
        rpe_estimate = max(1, min(10, rpe_estimate))

    if activity.duration_minutes <= 0:
        raise InvalidDurationError(activity.id, activity.duration_minutes)

    # Get base multipliers
    base_mults = get_multipliers(activity.sport_type, activity.surface_type)

    # Apply adjustments
    systemic_mult, lower_body_mult, adjustments = adjust_multipliers(
        base_mults, activity, analysis_result
    )

    # Calculate base effort
    base_effort = calculate_base_effort(activity.duration_minutes, rpe_estimate)

    # Apply multipliers
    systemic_load = base_effort * systemic_mult
    lower_body_load = base_effort * lower_body_mult

    # Classify session
    session_type = classify_session_type(
        activity.sport_type,
        rpe_estimate,
        activity.workout_type,
        analysis_result,
    )

    return LoadCalculation(
        activity_id=activity.id,
        duration_minutes=activity.duration_minutes,
        estimated_rpe=rpe_estimate,
        sport_type=activity.sport_type,
        surface_type=activity.surface_type,
        base_effort_au=base_effort,
        systemic_multiplier=systemic_mult,
        lower_body_multiplier=lower_body_mult,
        multiplier_adjustments=adjustments,
        systemic_load_au=round(systemic_load, 1),
        lower_body_load_au=round(lower_body_load, 1),
        session_type=session_type,
    )


def calculate_base_effort(duration_minutes: int, rpe: int) -> float:
    """
    Simple effort calculation: RPE × duration.

    Examples:
        60 min @ RPE 5 = 300 AU
        45 min @ RPE 7 = 315 AU
        30 min @ RPE 8 = 240 AU
    """
    return float(rpe * duration_minutes)
```

### 5.2 Multiplier Selection and Adjustment

```python
def get_multipliers(
    sport_type: str,
    surface_type: Optional[str] = None,
) -> SportMultipliers:
    """
    Get multipliers for sport type with surface override.
    """
    # Normalize sport type
    sport_lower = sport_type.lower().replace(" ", "_")

    # Check for zero-load activities
    if sport_lower in ZERO_LOAD_SPORTS:
        return SportMultipliers(sport_lower, 0.0, 0.0, "Restorative activity")

    # Surface type override for running
    if sport_lower == "run" and surface_type:
        surface_mapping = {
            "treadmill": "treadmill_run",
            "trail": "trail_run",
            "track": "track_run",
        }
        if surface_type.lower() in surface_mapping:
            sport_lower = surface_mapping[surface_type.lower()]

    # Look up multipliers
    if sport_lower in DEFAULT_MULTIPLIERS:
        return DEFAULT_MULTIPLIERS[sport_lower]

    # Unknown sport - use conservative defaults
    return DEFAULT_MULTIPLIERS["other"]


def adjust_multipliers(
    base_multipliers: SportMultipliers,
    activity: "NormalizedActivity",
    analysis_result: Optional["AnalysisResult"],
) -> tuple[float, float, list[str]]:
    """
    Apply context-aware adjustments to base multipliers.
    """
    systemic = base_multipliers.systemic
    lower_body = base_multipliers.lower_body
    adjustments = []

    # Adjustment 1: Strength training body focus
    if base_multipliers.sport in {"strength", "crossfit"}:
        body_focus = _detect_body_focus(activity, analysis_result)

        if body_focus == "lower":
            # Leg day - increase lower body load
            lower_body = min(0.80, lower_body + 0.25)
            adjustments.append(f"Lower-body focus: +0.25 lower_body → {lower_body:.2f}")

        elif body_focus == "upper":
            # Upper body day - reduce lower body load
            lower_body = max(0.10, lower_body - 0.20)
            adjustments.append(f"Upper-body focus: -0.20 lower_body → {lower_body:.2f}")

    # Adjustment 2: High elevation gain
    if activity.elevation_gain_m and activity.distance_km:
        gradient = activity.elevation_gain_m / (activity.distance_km * 10)  # m per 100m
        if gradient > 30:  # Significant hills
            systemic = min(1.20, systemic + 0.05)
            lower_body = min(1.30, lower_body + 0.10)
            adjustments.append(f"High elevation ({gradient:.0f}m/km): +0.05 sys, +0.10 lb")

    # Adjustment 3: Long duration sessions (metabolic stress)
    if activity.duration_minutes > 120:
        systemic = min(1.15, systemic + 0.05)
        adjustments.append(f"Long duration ({activity.duration_minutes}min): +0.05 systemic")

    # Adjustment 4: Race effort (additional stress)
    if activity.workout_type == 1:  # Strava race indicator
        systemic = min(1.30, systemic + 0.10)
        adjustments.append("Race effort: +0.10 systemic")

    return systemic, lower_body, adjustments


def _detect_body_focus(
    activity: "NormalizedActivity",
    analysis_result: Optional["AnalysisResult"],
) -> Optional[str]:
    """
    Detect if strength/crossfit session was upper or lower body focused.

    Keywords:
    - Lower: squat, deadlift, lunge, leg press, leg day
    - Upper: bench, press, pull-up, row, arm day
    """
    text = f"{activity.name or ''} {activity.description or ''}".lower()

    lower_keywords = ["squat", "deadlift", "lunge", "leg press", "leg day",
                      "leg", "glute", "hamstring", "quad", "calf"]
    upper_keywords = ["bench", "press", "pull-up", "pullup", "row", "arm",
                      "bicep", "tricep", "shoulder", "chest", "back day"]

    lower_score = sum(1 for kw in lower_keywords if kw in text)
    upper_score = sum(1 for kw in upper_keywords if kw in text)

    if lower_score > upper_score and lower_score >= 2:
        return "lower"
    elif upper_score > lower_score and upper_score >= 2:
        return "upper"
    return None
```

### 5.3 Session Type Classification

```python
def classify_session_type(
    sport_type: str,
    rpe: int,
    workout_type: Optional[int],
    notes_analysis: Optional["AnalysisResult"],
) -> SessionType:
    """
    Classify session for 80/20 intensity distribution tracking.

    Classification Rules:
    - Race (workout_type=1 or RPE 9-10): RACE
    - Intervals/tempo (workout_type=3 or RPE 7-8): QUALITY
    - Steady state (RPE 5-6): MODERATE
    - Recovery (RPE 1-4): EASY
    """
    # Check for explicit race
    if workout_type == 1:
        return SessionType.RACE

    # Check RPE-based classification
    if rpe >= 9:
        return SessionType.RACE
    elif rpe >= 7:
        return SessionType.QUALITY
    elif rpe >= 5:
        return SessionType.MODERATE
    else:
        return SessionType.EASY


# Extended classification with keyword support
SESSION_TYPE_KEYWORDS = {
    SessionType.RACE: ["race", "competition", "pr attempt", "time trial"],
    SessionType.QUALITY: ["tempo", "threshold", "intervals", "fartlek",
                          "speed work", "track workout", "vo2max"],
    SessionType.MODERATE: ["steady", "aerobic", "long run", "endurance"],
    SessionType.EASY: ["recovery", "easy", "shake out", "warm up", "cool down"],
}


def classify_with_keywords(
    base_classification: SessionType,
    activity_name: Optional[str],
    description: Optional[str],
) -> SessionType:
    """
    Refine classification using keyword analysis.
    """
    text = f"{activity_name or ''} {description or ''}".lower()

    # Keywords can override RPE-based classification
    for session_type, keywords in SESSION_TYPE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            # Quality/Race keywords can upgrade
            if session_type in {SessionType.QUALITY, SessionType.RACE}:
                return session_type
            # Easy keywords can downgrade (even moderate sessions)
            if session_type == SessionType.EASY:
                return session_type

    return base_classification
```

### 5.4 Unknown Sport Handling

```python
def handle_unknown_sport(
    sport_type: str,
    activity: "NormalizedActivity",
) -> tuple[SportMultipliers, str]:
    """
    Handle activities with unknown sport types.

    Strategy:
    1. Use conservative default multipliers
    2. Generate user clarification prompt
    3. Log for pattern analysis
    """
    default_mults = SportMultipliers(
        sport=sport_type,
        systemic=0.70,
        lower_body=0.30,
        description=f"Unknown sport: {sport_type} (conservative estimate)"
    )

    # Generate user prompt for next conversation
    clarification = (
        f"I classified your '{sport_type}' activity with conservative load estimates. "
        "Was it:\n"
        "A) Mostly cardio/full-body (like rowing, skiing)\n"
        "B) Mostly upper-body (like kayaking, rock climbing)\n"
        "C) Leg-heavy (like skating, skiing with lots of turns)\n"
        "This helps me count it correctly toward your fatigue."
    )

    return default_mults, clarification
```

### 5.5 Persist to Activity File

```python
def persist_load_to_activity(
    activity_path: str,
    load_calc: LoadCalculation,
    repo: "RepositoryIO",
) -> None:
    """
    Add calculated fields to activity file.

    Updates the 'calculated' section of the activity YAML.
    """
    # Read current activity
    activity_data = repo.read_yaml(activity_path)

    # Add/update calculated fields
    activity_data["calculated"] = {
        "estimated_rpe": load_calc.estimated_rpe,
        "base_effort_au": load_calc.base_effort_au,
        "systemic_multiplier": load_calc.systemic_multiplier,
        "lower_body_multiplier": load_calc.lower_body_multiplier,
        "systemic_load_au": load_calc.systemic_load_au,
        "lower_body_load_au": load_calc.lower_body_load_au,
        "session_type": load_calc.session_type.value,
        "multiplier_adjustments": load_calc.multiplier_adjustments,
    }

    # Persist atomically
    repo.write_yaml(activity_path, activity_data)
```

## 6. Data Structures

### 6.1 Calculated Fields Schema

```yaml
# Added to activities/YYYY-MM/*.yaml by M8
calculated:
  estimated_rpe: 6
  base_effort_au: 360.0         # 6 × 60 minutes
  systemic_multiplier: 1.05
  lower_body_multiplier: 1.10
  systemic_load_au: 378.0       # 360 × 1.05
  lower_body_load_au: 396.0     # 360 × 1.10
  session_type: "moderate"
  multiplier_adjustments:
    - "Trail running: +0.05 systemic, +0.10 lower_body"
```

### 6.2 Sport Multipliers Quick Reference

| Sport | Systemic | Lower-Body | Notes |
|-------|----------|------------|-------|
| Run (road) | 1.00 | 1.00 | Baseline |
| Run (trail) | 1.05 | 1.10 | More impact |
| Run (treadmill) | 1.00 | 0.90 | Less impact |
| Cycling | 0.85 | 0.35 | Low leg impact |
| Swimming | 0.70 | 0.10 | Minimal legs |
| Climbing | 0.60 | 0.10 | Upper-body |
| Strength | 0.55 | 0.40 | Adjustable |
| CrossFit | 0.75 | 0.55 | Mixed |
| Hiking | 0.60 | 0.50 | Moderate |
| Yoga (flow) | 0.35 | 0.10 | Low load |
| Unknown | 0.70 | 0.30 | Conservative |

### 6.3 Session Type Thresholds

| RPE Range | Session Type | 80/20 Bucket |
|-----------|--------------|--------------|
| 1-4 | Easy | Low intensity (80%) |
| 5-6 | Moderate | Moderate intensity |
| 7-8 | Quality | High intensity (20%) |
| 9-10 | Race | High intensity (20%) |

## 7. Integration Points

### 7.1 Integration with API Layer

This module is called internally by M1 workflows as part of the sync pipeline. Claude Code does NOT call M8 directly.

```
Claude Code → api.sync.sync_strava()
                    │
                    ▼
              M1::run_sync_workflow()
                    │
                    ├─► M5::fetch_activities()
                    ├─► M6::normalize_activity()
                    ├─► M7::analyze_notes()
                    ├─► M8::calculate_loads() ← HERE
                    └─► M9::compute_daily_metrics()
```

### 7.2 Called By

| Module | When |
|--------|------|
| M1 (Workflows) | During sync pipeline after M7 analysis |

### 7.3 Calls To

| Module | Purpose |
|--------|---------|
| M3 | Update activity files with calculated fields |

### 7.4 Returns To

| Module | Data |
|--------|------|
| M9 | Load values for metrics computation |

### 7.5 Pipeline Position

```
[M6 Normalization]
        │
        ▼ NormalizedActivity
[M7 Notes Analyzer]
        │
        ▼ RPE + AnalysisResult
[M8 Load Engine]
        │
        ├── LoadCalculation ──────► [M9 Metrics Engine]
        │
        └── Update activity file ─► [M3 Repository I/O]
```

## 8. Test Scenarios

### 8.1 Unit Tests

```python
def test_base_effort_calculation():
    """Base effort is RPE × duration"""
    result = calculate_base_effort(duration_minutes=60, rpe=5)
    assert result == 300.0


def test_load_calculation_road_run():
    """Road running uses 1.0/1.0 multipliers"""
    activity = mock_activity(
        sport_type="run",
        surface_type="road",
        duration_minutes=45,
    )

    load = compute_load(activity, rpe_estimate=6)

    assert load.base_effort_au == 270.0  # 45 × 6
    assert load.systemic_multiplier == 1.0
    assert load.lower_body_multiplier == 1.0
    assert load.systemic_load_au == 270.0
    assert load.lower_body_load_au == 270.0


def test_load_calculation_treadmill():
    """Treadmill has reduced lower-body load"""
    activity = mock_activity(
        sport_type="run",
        surface_type="treadmill",
        duration_minutes=30,
    )

    load = compute_load(activity, rpe_estimate=5)

    assert load.systemic_multiplier == 1.0
    assert load.lower_body_multiplier == 0.9  # Reduced
    assert load.lower_body_load_au == 135.0  # 150 × 0.9


def test_load_calculation_climbing():
    """Climbing is mostly upper-body"""
    activity = mock_activity(
        sport_type="climb",
        duration_minutes=120,
    )

    load = compute_load(activity, rpe_estimate=7)

    assert load.systemic_multiplier == 0.6
    assert load.lower_body_multiplier == 0.1
    assert load.systemic_load_au == 504.0  # 840 × 0.6
    assert load.lower_body_load_au == 84.0  # 840 × 0.1


def test_strength_lower_body_adjustment():
    """Leg day increases lower-body multiplier"""
    activity = mock_activity(
        sport_type="strength",
        name="Leg Day - Squats and Deadlifts",
        duration_minutes=60,
    )

    load = compute_load(activity, rpe_estimate=7)

    # Base: systemic=0.55, lower_body=0.40
    # Adjustment: lower_body +0.25 = 0.65
    assert load.lower_body_multiplier == 0.65
    assert "Lower-body focus" in load.multiplier_adjustments[0]


def test_unknown_sport_conservative():
    """Unknown sports use conservative multipliers"""
    activity = mock_activity(
        sport_type="underwater_hockey",
        duration_minutes=60,
    )

    load = compute_load(activity, rpe_estimate=6)

    assert load.systemic_multiplier == 0.70
    assert load.lower_body_multiplier == 0.30


def test_session_type_classification():
    """Session type based on RPE"""
    assert classify_session_type("run", rpe=3, workout_type=None, notes_analysis=None) == SessionType.EASY
    assert classify_session_type("run", rpe=5, workout_type=None, notes_analysis=None) == SessionType.MODERATE
    assert classify_session_type("run", rpe=7, workout_type=None, notes_analysis=None) == SessionType.QUALITY
    assert classify_session_type("run", rpe=9, workout_type=None, notes_analysis=None) == SessionType.RACE


def test_session_type_race_override():
    """Strava workout_type=1 indicates race"""
    result = classify_session_type("run", rpe=6, workout_type=1, notes_analysis=None)
    assert result == SessionType.RACE


def test_zero_load_restorative():
    """Restorative yoga has zero load"""
    mults = get_multipliers("yoga_restorative")

    assert mults.systemic == 0.0
    assert mults.lower_body == 0.0
```

### 8.2 Integration Tests

```python
@pytest.mark.integration
def test_full_load_pipeline():
    """End-to-end load calculation with persistence"""
    activity = create_test_activity("2025-03-15_run_0730.yaml")
    rpe = 6

    load = compute_load(activity, rpe)
    persist_load_to_activity(activity.file_path, load, repo)

    # Verify persisted
    saved = repo.read_yaml(activity.file_path)
    assert saved["calculated"]["systemic_load_au"] == load.systemic_load_au
    assert saved["calculated"]["session_type"] == "moderate"
```

### 8.3 Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| RPE = 0 | Clamp to 1 |
| RPE = 11 | Clamp to 10 |
| Duration = 0 | Raise InvalidDurationError |
| Duration = 600 (10h) | Valid, apply long duration adjustment |
| Unknown sport + high RPE | Conservative mults, suggest clarification |
| Yoga (restorative) | Zero load |
| Race with RPE 5 | Classify as RACE (workout_type wins) |

## 9. Configuration

### 9.1 Customizable Multipliers

```python
# Future: Allow user customization via config
MULTIPLIER_OVERRIDES: dict[str, SportMultipliers] = {}

def load_custom_multipliers(config_path: str) -> None:
    """Load user-defined multiplier overrides"""
    # Read from config/multipliers.yaml if exists
    ...
```

### 9.2 Adjustment Thresholds

```python
LOAD_CONFIG = {
    "elevation_gradient_threshold": 30,    # m per km
    "long_duration_threshold": 120,        # minutes
    "lower_body_focus_keyword_threshold": 2,  # keywords needed
}
```

## 10. Formulas Reference

### 10.1 Core Formulas

```
base_effort_au = RPE × duration_minutes

systemic_load_au = base_effort_au × systemic_multiplier

lower_body_load_au = base_effort_au × lower_body_multiplier
```

### 10.2 Example Calculations

**Easy 60-min road run (RPE 4):**
```
base_effort = 4 × 60 = 240 AU
systemic = 240 × 1.0 = 240 AU
lower_body = 240 × 1.0 = 240 AU
```

**Hard 45-min tempo (RPE 7):**
```
base_effort = 7 × 45 = 315 AU
systemic = 315 × 1.0 = 315 AU
lower_body = 315 × 1.0 = 315 AU
```

**2-hour climbing session (RPE 7):**
```
base_effort = 7 × 120 = 840 AU
systemic = 840 × 0.6 = 504 AU
lower_body = 840 × 0.1 = 84 AU
```

**90-min cycling (RPE 5):**
```
base_effort = 5 × 90 = 450 AU
systemic = 450 × 0.85 = 382.5 AU
lower_body = 450 × 0.35 = 157.5 AU
```

## 11. Performance Notes

- Load calculation is pure computation (no I/O)
- 100 activities compute in < 10ms
- Batch processing available for efficiency
- File writes are the bottleneck (delegate to M3 batching)

## 12. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.2 | 2026-01-12 | Added code module path (`core/load.py`) and API layer integration notes. |
| 1.0.1 | 2026-01-12 | **Fixed type consistency**: Converted all `@dataclass` types to `BaseModel` for Pydantic consistency (SportMultipliers, LoadCalculation, MultiplierAdjustment - 3 types converted). Removed `dataclass` import, added `Field` for default factories. Algorithms were already complete and correct. |
| 1.0.0 | 2026-01-12 | Initial specification |
