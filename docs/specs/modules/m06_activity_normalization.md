# M6 — Activity Normalization

## 1. Metadata

| Field | Value |
|-------|-------|
| Module ID | M6 |
| Name | Activity Normalization |
| Code Module | `core/normalization.py` |
| Version | 1.0.2 |
| Status | Draft |
| Dependencies | M3 (Repository I/O), M5 (Strava Integration), M7 (Notes & RPE Analyzer) |

## 2. Purpose

Transform raw activity data from various sources into a consistent, validated schema. Normalizes sport types, units, and structure to ensure downstream modules receive uniform data.

### 2.1 Scope Boundaries

**In Scope:**
- Normalizing sport type names (aliases → canonical)
- Converting units (meters → km, seconds → minutes)
- Deriving core fields (duration, distance, date)
- Setting surface type from M7 detection
- Assigning data quality indicators
- Persisting normalized activities to disk
- Filename generation with collision handling

**Out of Scope:**
- Fetching raw activities (M5)
- Extracting RPE from notes (M7 - but receives treadmill detection from M7)
- Computing loads (M8)
- Detecting treadmill (delegates to M7, receives result)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage |
|--------|-------|
| M3 | Persist normalized activities to activities/ directory |
| M5 (Strava Integration) | Receives RawActivity objects as input |
| M7 | Receives treadmill detection results for surface_type |

### 3.2 External Libraries

```
pydantic>=2.0        # Data validation and serialization
pyyaml>=6.0          # YAML output
```

## 4. Internal Interface

**Note:** This module is called internally by M1 workflows as part of the sync pipeline. Claude Code should NOT import from `core/normalization.py` directly.

**Note on Async Operations**: This specification shows `normalize_and_persist` as async for completeness. However, **v0 implementation should use synchronous I/O** to avoid over-engineering. Replace `async def` with `def` and remove `await` keywords. Async can be added in future versions if performance requires it.

### 4.1 Type Definitions

```python
from datetime import datetime, date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SportType(str, Enum):
    """Canonical sport types"""
    RUN = "run"
    TRAIL_RUN = "trail_run"
    TREADMILL_RUN = "treadmill_run"
    TRACK_RUN = "track_run"
    CYCLE = "cycle"
    SWIM = "swim"
    CLIMB = "climb"
    STRENGTH = "strength"
    CROSSFIT = "crossfit"
    YOGA = "yoga"
    HIKE = "hike"
    WALK = "walk"
    OTHER = "other"


class SurfaceType(str, Enum):
    """Running surface types"""
    ROAD = "road"
    TRAIL = "trail"
    TRACK = "track"
    TREADMILL = "treadmill"
    GRASS = "grass"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class SessionType(str, Enum):
    """Training session intensity classification"""
    EASY = "easy"
    MODERATE = "moderate"
    QUALITY = "quality"  # Tempo, intervals, threshold
    RACE = "race"


class DataQuality(str, Enum):
    """Reliability indicator for activity data"""
    HIGH = "high"          # GPS + HR + verified source
    MEDIUM = "medium"      # Some data missing or inferred
    LOW = "low"            # Minimal data, heavy inference
    TREADMILL = "treadmill"  # Pace unreliable, HR prioritized


class TreadmillDetection(BaseModel):
    """Result from M7 treadmill detection"""
    is_treadmill: bool
    confidence: str  # "high" | "low"
    signals: list[str]  # Evidence that led to detection


class NormalizedActivity(BaseModel):
    """
    Fully normalized activity ready for downstream processing.
    This is the schema for activities/YYYY-MM/*.yaml files.
    """
    # Schema metadata
    _schema: dict = Field(default_factory=lambda: {
        "format_version": "1.0.0",
        "schema_type": "activity"
    })

    # Identity
    id: str
    source: str  # "strava" | "manual"

    # Core fields (required)
    sport_type: SportType
    sub_type: Optional[str] = None  # Original Strava sub-type if present
    name: str
    date: date
    start_time: Optional[datetime] = None
    duration_minutes: int
    duration_seconds: int

    # Distance (optional for non-distance sports)
    distance_km: Optional[float] = None
    distance_meters: Optional[float] = None
    elevation_gain_m: Optional[float] = None

    # Heart rate (optional)
    average_hr: Optional[int] = None
    max_hr: Optional[int] = None
    has_hr_data: bool = False

    # User notes
    description: Optional[str] = None
    private_note: Optional[str] = None

    # Strava-specific (preserved for reference)
    workout_type: Optional[int] = None  # 1=race, 2=long, 3=workout
    suffer_score: Optional[int] = None
    perceived_exertion: Optional[int] = None  # User-entered 1-10

    # Surface and quality
    surface_type: SurfaceType = SurfaceType.UNKNOWN
    surface_type_confidence: str = "low"  # "high" | "low"
    data_quality: DataQuality = DataQuality.MEDIUM

    # GPS data
    has_gps_data: bool = False

    # Equipment
    gear_id: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    synced_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class NormalizationResult(BaseModel):
    """Result of normalizing a single activity"""
    activity: NormalizedActivity
    file_path: str
    was_updated: bool  # True if existing file was updated
    warnings: list[str] = Field(default_factory=list)
```

### 4.2 Sport Alias Mapping

```python
SPORT_ALIASES: dict[str, SportType] = {
    # Running variants
    "run": SportType.RUN,
    "running": SportType.RUN,
    "road_run": SportType.RUN,
    "trail_run": SportType.TRAIL_RUN,
    "trailrun": SportType.TRAIL_RUN,
    "trail": SportType.TRAIL_RUN,
    "treadmill": SportType.TREADMILL_RUN,
    "treadmill_run": SportType.TREADMILL_RUN,
    "virtual_run": SportType.TREADMILL_RUN,
    "track": SportType.TRACK_RUN,
    "track_run": SportType.TRACK_RUN,

    # Cycling variants
    "ride": SportType.CYCLE,
    "cycle": SportType.CYCLE,
    "cycling": SportType.CYCLE,
    "virtual_ride": SportType.CYCLE,
    "indoor_cycling": SportType.CYCLE,
    "ebikeride": SportType.CYCLE,
    "gravel_ride": SportType.CYCLE,
    "mountain_bike_ride": SportType.CYCLE,

    # Swimming
    "swim": SportType.SWIM,
    "swimming": SportType.SWIM,
    "open_water_swimming": SportType.SWIM,

    # Climbing
    "climb": SportType.CLIMB,
    "climbing": SportType.CLIMB,
    "rock_climb": SportType.CLIMB,
    "rock_climbing": SportType.CLIMB,
    "indoor_climb": SportType.CLIMB,
    "bouldering": SportType.CLIMB,

    # Strength
    "strength": SportType.STRENGTH,
    "weight_training": SportType.STRENGTH,
    "weighttraining": SportType.STRENGTH,
    "workout": SportType.STRENGTH,

    # CrossFit
    "crossfit": SportType.CROSSFIT,
    "functional_fitness": SportType.CROSSFIT,
    "hiit": SportType.CROSSFIT,

    # Yoga
    "yoga": SportType.YOGA,

    # Hiking/Walking
    "hike": SportType.HIKE,
    "hiking": SportType.HIKE,
    "walk": SportType.WALK,
    "walking": SportType.WALK,
}
```

### 4.3 Function Signatures

```python
from typing import Sequence


def normalize_activity(
    raw: "RawActivity",
    treadmill_detection: TreadmillDetection | None = None,
) -> NormalizedActivity:
    """
    Transform a raw activity into normalized form.

    Args:
        raw: Raw activity from M5
        treadmill_detection: Optional result from M7 treadmill detection

    Returns:
        Normalized activity with consistent schema
    """
    ...


def normalize_sport_type(
    raw_sport: str,
    sub_type: str | None = None,
) -> SportType:
    """
    Map raw sport string to canonical SportType.

    Args:
        raw_sport: Original sport type string (e.g., "Run", "TrailRun")
        sub_type: Optional sub-type for more specific mapping

    Returns:
        Canonical SportType enum value
    """
    ...


def determine_surface_type(
    sport_type: SportType,
    treadmill_detection: TreadmillDetection | None,
    sub_type: str | None,
    has_gps: bool,
) -> tuple[SurfaceType, str]:
    """
    Determine running surface type.

    Args:
        sport_type: Normalized sport type
        treadmill_detection: M7 treadmill detection result
        sub_type: Original sub-type from source
        has_gps: Whether GPS data is present

    Returns:
        (surface_type, confidence) tuple
    """
    ...


def determine_data_quality(
    has_gps: bool,
    has_hr: bool,
    surface_type: SurfaceType,
    source: str,
) -> DataQuality:
    """
    Assess data quality for the activity.

    Args:
        has_gps: GPS data available
        has_hr: Heart rate data available
        surface_type: Determined surface type
        source: Activity source ("strava" | "manual")

    Returns:
        Data quality indicator
    """
    ...


def generate_activity_filename(
    activity: NormalizedActivity,
    existing_files: list[str],
) -> str:
    """
    Generate filename following convention with collision handling.

    Format: YYYY-MM-DD_<sport_type>_<HHmm>.yaml
    Fallback: YYYY-MM-DD_<sport_type>_<N>.yaml (if no start_time)

    Args:
        activity: Normalized activity
        existing_files: List of existing filenames in the month directory

    Returns:
        Generated filename (without path)
    """
    ...


async def normalize_and_persist(
    raw_activities: Sequence["RawActivity"],
    repo: "RepositoryIO",
    treadmill_results: dict[str, TreadmillDetection] | None = None,
) -> list[NormalizationResult]:
    """
    Normalize and persist multiple activities.

    Args:
        raw_activities: List of raw activities from M5
        repo: Repository I/O instance
        treadmill_results: Map of activity_id -> TreadmillDetection from M7

    Returns:
        List of normalization results with file paths

    Note:
        Uses atomic writes via M3. All activities in a batch are
        written together or none are (transaction semantics).
    """
    ...


def convert_units(
    distance_meters: float | None,
    duration_seconds: int,
    elevation_meters: float | None,
) -> dict:
    """
    Convert raw units to normalized units.

    Args:
        distance_meters: Distance in meters (from Strava)
        duration_seconds: Duration in seconds
        elevation_meters: Elevation gain in meters

    Returns:
        Dict with converted values:
        - distance_km: float | None
        - duration_minutes: int
        - elevation_gain_m: float | None (unchanged, for consistency)
    """
    ...
```

### 4.4 Error Types

```python
class NormalizationError(Exception):
    """Base error for normalization failures"""
    pass


class UnknownSportError(NormalizationError):
    """Sport type cannot be mapped"""
    def __init__(self, sport_type: str):
        super().__init__(f"Unknown sport type: {sport_type}")
        self.sport_type = sport_type


class InvalidActivityError(NormalizationError):
    """Activity fails validation"""
    def __init__(self, activity_id: str, reason: str):
        super().__init__(f"Invalid activity {activity_id}: {reason}")
        self.activity_id = activity_id
        self.reason = reason


class FilenameCollisionError(NormalizationError):
    """Cannot generate unique filename"""
    def __init__(self, base_name: str):
        super().__init__(f"Cannot generate unique filename for {base_name}")
        self.base_name = base_name
```

## 5. Core Algorithms

### 5.1 Sport Type Normalization

```python
def normalize_sport_type(
    raw_sport: str,
    sub_type: str | None = None,
) -> SportType:
    """
    Normalize sport type with sub-type consideration.

    Priority:
    1. Check sub_type first (more specific)
    2. Check raw_sport
    3. Fall back to OTHER
    """
    # Normalize strings
    raw_lower = raw_sport.lower().strip().replace(" ", "_")
    sub_lower = sub_type.lower().strip().replace(" ", "_") if sub_type else None

    # Try sub_type first (more specific)
    if sub_lower and sub_lower in SPORT_ALIASES:
        return SPORT_ALIASES[sub_lower]

    # Try raw sport
    if raw_lower in SPORT_ALIASES:
        return SPORT_ALIASES[raw_lower]

    # Log warning and return OTHER
    logger.warning(f"Unknown sport type: {raw_sport} (sub_type: {sub_type})")
    return SportType.OTHER
```

### 5.2 Surface Type Detection

```python
def determine_surface_type(
    sport_type: SportType,
    treadmill_detection: TreadmillDetection | None,
    sub_type: str | None,
    has_gps: bool,
) -> tuple[SurfaceType, str]:
    """
    Determine surface type with confidence rating.

    Decision tree:
    1. If M7 detected treadmill with high confidence → treadmill
    2. If sport_type is treadmill_run → treadmill
    3. If sport_type is trail_run → trail
    4. If sport_type is track_run → track
    5. If no GPS and running → likely treadmill (low confidence)
    6. Otherwise → road (default for running)
    """
    # Non-running sports don't have surface type
    running_types = {SportType.RUN, SportType.TRAIL_RUN,
                     SportType.TREADMILL_RUN, SportType.TRACK_RUN}
    if sport_type not in running_types:
        return SurfaceType.UNKNOWN, "n/a"

    # Check M7 treadmill detection (highest priority)
    if treadmill_detection and treadmill_detection.is_treadmill:
        return SurfaceType.TREADMILL, treadmill_detection.confidence

    # Check sport-specific types
    if sport_type == SportType.TREADMILL_RUN:
        return SurfaceType.TREADMILL, "high"
    if sport_type == SportType.TRAIL_RUN:
        return SurfaceType.TRAIL, "high"
    if sport_type == SportType.TRACK_RUN:
        return SurfaceType.TRACK, "high"

    # No GPS for generic run → likely treadmill
    if sport_type == SportType.RUN and not has_gps:
        return SurfaceType.TREADMILL, "low"

    # Default for outdoor running
    return SurfaceType.ROAD, "medium"
```

### 5.3 Data Quality Assessment

```python
def determine_data_quality(
    has_gps: bool,
    has_hr: bool,
    surface_type: SurfaceType,
    source: str,
) -> DataQuality:
    """
    Assess data quality based on available signals.

    Quality matrix:
    - HIGH: GPS + HR + Strava source
    - MEDIUM: Missing GPS or HR
    - LOW: Manual entry or minimal data
    - TREADMILL: Special case - pace unreliable
    """
    # Treadmill is special case
    if surface_type == SurfaceType.TREADMILL:
        return DataQuality.TREADMILL

    # Manual entries are lower quality (no verification)
    if source == "manual":
        return DataQuality.LOW

    # Score based on available data
    score = 0
    if has_gps:
        score += 2
    if has_hr:
        score += 1

    if score >= 3:
        return DataQuality.HIGH
    elif score >= 1:
        return DataQuality.MEDIUM
    else:
        return DataQuality.LOW
```

### 5.4 Unit Conversion

```python
def convert_units(
    distance_meters: float | None,
    duration_seconds: int,
    elevation_meters: float | None,
) -> dict:
    """
    Convert Strava units to normalized units.

    Conversions:
    - meters → kilometers (2 decimal places)
    - seconds → minutes (rounded)
    """
    return {
        "distance_km": round(distance_meters / 1000, 2) if distance_meters else None,
        "distance_meters": distance_meters,  # Preserve original
        "duration_minutes": duration_seconds // 60,
        "duration_seconds": duration_seconds,  # Preserve original
        "elevation_gain_m": round(elevation_meters, 1) if elevation_meters else None,
    }
```

### 5.5 Full Normalization Flow

```python
from datetime import datetime, timezone


def normalize_activity(
    raw: "RawActivity",
    treadmill_detection: TreadmillDetection | None = None,
) -> NormalizedActivity:
    """
    Complete normalization pipeline for a single activity.
    """
    now = datetime.now(timezone.utc)

    # 1. Normalize sport type
    sport_type = normalize_sport_type(raw.sport_type, raw.sub_type)

    # 2. Convert units
    units = convert_units(
        raw.distance_meters,
        raw.duration_seconds,
        raw.elevation_gain_meters,
    )

    # 3. Determine surface type
    surface_type, surface_confidence = determine_surface_type(
        sport_type=sport_type,
        treadmill_detection=treadmill_detection,
        sub_type=raw.sub_type,
        has_gps=raw.has_polyline,
    )

    # 4. Override sport_type if treadmill detected
    if surface_type == SurfaceType.TREADMILL and sport_type == SportType.RUN:
        sport_type = SportType.TREADMILL_RUN

    # 5. Assess data quality
    data_quality = determine_data_quality(
        has_gps=raw.has_polyline,
        has_hr=raw.has_hr_data,
        surface_type=surface_type,
        source=raw.source.value,
    )

    # 6. Build normalized activity
    return NormalizedActivity(
        id=raw.id,
        source=raw.source.value,
        sport_type=sport_type,
        sub_type=raw.sub_type,
        name=raw.name,
        date=raw.date,
        start_time=raw.start_time,
        duration_minutes=units["duration_minutes"],
        duration_seconds=units["duration_seconds"],
        distance_km=units["distance_km"],
        distance_meters=units["distance_meters"],
        elevation_gain_m=units["elevation_gain_m"],
        average_hr=raw.average_hr,
        max_hr=raw.max_hr,
        has_hr_data=raw.has_hr_data,
        description=raw.description,
        private_note=raw.private_note,
        workout_type=raw.workout_type,
        suffer_score=raw.suffer_score,
        perceived_exertion=raw.perceived_exertion,
        surface_type=surface_type,
        surface_type_confidence=surface_confidence,
        data_quality=data_quality,
        has_gps_data=raw.has_polyline,
        gear_id=raw.gear_id,
        created_at=now,
        updated_at=now,
        synced_at=now if raw.source.value == "strava" else None,
    )
```

### 5.6 Filename Generation

```python
def generate_activity_filename(
    activity: NormalizedActivity,
    existing_files: list[str],
) -> str:
    """
    Generate unique filename for activity.

    Format: YYYY-MM-DD_<sport>_<HHmm>.yaml
    Collision handling: YYYY-MM-DD_<sport>_<N>.yaml
    """
    date_str = activity.date.isoformat()
    sport_str = activity.sport_type.value.replace("_", "")  # e.g., "run", "trailrun"

    # Try time-based naming first
    if activity.start_time:
        time_str = activity.start_time.strftime("%H%M")
        filename = f"{date_str}_{sport_str}_{time_str}.yaml"

        if filename not in existing_files:
            return filename

    # Fallback: index-based naming
    for i in range(1, 100):
        filename = f"{date_str}_{sport_str}_{i}.yaml"
        if filename not in existing_files:
            return filename

    raise FilenameCollisionError(f"{date_str}_{sport_str}")
```

### 5.7 Batch Normalization and Persistence

```python
from pathlib import Path


async def normalize_and_persist(
    raw_activities: Sequence["RawActivity"],
    repo: "RepositoryIO",
    treadmill_results: dict[str, TreadmillDetection] | None = None,
) -> list[NormalizationResult]:
    """
    Normalize and persist activities atomically.
    """
    treadmill_results = treadmill_results or {}
    results = []
    activities_by_month: dict[str, list[tuple[NormalizedActivity, str]]] = {}

    for raw in raw_activities:
        # Get treadmill detection if available
        detection = treadmill_results.get(raw.id)

        # Normalize
        normalized = normalize_activity(raw, detection)

        # Determine month directory
        month_dir = f"activities/{normalized.date.strftime('%Y-%m')}"

        # Get existing files in month
        existing = repo.list_files(month_dir, pattern="*.yaml")

        # Generate filename
        filename = generate_activity_filename(normalized, existing)
        file_path = f"{month_dir}/{filename}"

        # Check if updating existing
        was_updated = any(
            f.endswith(f"_{normalized.id}.yaml") or
            existing_matches(f, normalized)
            for f in existing
        )

        # Group by month for batch write
        if month_dir not in activities_by_month:
            activities_by_month[month_dir] = []
        activities_by_month[month_dir].append((normalized, file_path))

        results.append(NormalizationResult(
            activity=normalized,
            file_path=file_path,
            was_updated=was_updated,
            warnings=[],
        ))

    # Persist all activities atomically
    for month_dir, activities in activities_by_month.items():
        repo.ensure_directory(month_dir)
        for normalized, file_path in activities:
            repo.write_yaml(
                file_path,
                normalized.model_dump(mode="json", exclude_none=True),
            )

    return results
```

## 6. Data Structures

### 6.1 Activity File Schema

```yaml
# activities/2025-03/2025-03-15_run_0730.yaml
_schema:
  format_version: "1.0.0"
  schema_type: "activity"

# Identity
id: "12345678901"
source: "strava"

# Core fields
sport_type: "run"
sub_type: "TrailRun"  # Original if present
name: "Morning Trail Run"
date: "2025-03-15"
start_time: "2025-03-15T07:30:00Z"
duration_minutes: 65
duration_seconds: 3912

# Distance
distance_km: 12.5
distance_meters: 12500.0
elevation_gain_m: 342.0

# Heart rate
average_hr: 148
max_hr: 172
has_hr_data: true

# User notes
description: "Great sunrise run on the ridge trail"
private_note: "Left calf felt tight at km 8"

# Strava metadata
workout_type: 2  # Long run
suffer_score: 87
perceived_exertion: 7

# Surface and quality
surface_type: "trail"
surface_type_confidence: "high"
data_quality: "high"

# GPS
has_gps_data: true

# Equipment
gear_id: "g12345"

# Timestamps
created_at: "2025-03-15T09:45:00Z"
updated_at: "2025-03-15T09:45:00Z"
synced_at: "2025-03-15T09:45:00Z"
```

### 6.2 Validation Rules

```python
def validate_activity(activity: NormalizedActivity) -> list[str]:
    """
    Validate normalized activity for logical consistency.

    Returns list of validation warnings (not errors for soft validation).
    """
    warnings = []

    # Duration sanity check
    if activity.duration_minutes < 1:
        warnings.append("Duration less than 1 minute")
    if activity.duration_minutes > 600:  # 10 hours
        warnings.append("Duration exceeds 10 hours")

    # Distance sanity for running
    if activity.sport_type in {SportType.RUN, SportType.TRAIL_RUN, SportType.TRACK_RUN}:
        if activity.distance_km and activity.duration_minutes:
            pace_min_per_km = activity.duration_minutes / activity.distance_km
            if pace_min_per_km < 2.5:  # Faster than 2:30/km
                warnings.append(f"Pace suspiciously fast: {pace_min_per_km:.1f} min/km")
            if pace_min_per_km > 15:  # Slower than 15:00/km
                warnings.append(f"Pace very slow: {pace_min_per_km:.1f} min/km")

    # HR sanity check
    if activity.average_hr:
        if activity.average_hr < 60:
            warnings.append(f"Average HR suspiciously low: {activity.average_hr}")
        if activity.average_hr > 220:
            warnings.append(f"Average HR exceeds 220: {activity.average_hr}")

    # Max HR should be >= average
    if activity.max_hr and activity.average_hr:
        if activity.max_hr < activity.average_hr:
            warnings.append("Max HR less than average HR")

    return warnings
```

## 7. Error Handling

### 7.1 Unknown Sports

```python
def handle_unknown_sport(
    raw_sport: str,
    activity_id: str,
) -> tuple[SportType, str]:
    """
    Handle unknown sport types gracefully.

    Strategy:
    1. Map to OTHER
    2. Log warning
    3. Return suggestion for user query
    """
    logger.warning(
        f"Unknown sport '{raw_sport}' for activity {activity_id}. "
        "Using conservative load multipliers."
    )

    suggestion = (
        f"I classified your '{raw_sport}' activity with conservative load "
        "estimates. Was it: A) Mostly cardio/full-body (like rowing, skiing) "
        "B) Mostly upper-body (like kayaking) "
        "C) Leg-heavy (like skating)? This helps me count fatigue correctly."
    )

    return SportType.OTHER, suggestion
```

### 7.2 Missing Required Fields

```python
def fill_required_defaults(raw: "RawActivity") -> "RawActivity":
    """
    Fill missing required fields with safe defaults.
    """
    if not raw.name:
        raw.name = f"{raw.sport_type} on {raw.date}"

    if raw.duration_seconds <= 0:
        # Cannot proceed without duration
        raise InvalidActivityError(
            raw.id,
            "Duration is required and must be positive"
        )

    return raw
```

## 8. Integration Points

### 8.1 Integration with API Layer

This module is called internally by M1 workflows as part of the sync pipeline. Claude Code does NOT call M6 directly.

```
Claude Code → api.sync.sync_strava()
                    │
                    ▼
              M1::run_sync_workflow()
                    │
                    ├─► M5::fetch_activities() → RawActivity[]
                    ├─► M6::normalize_activity() → NormalizedActivity[]
                    ├─► M7::analyze_notes()
                    └─► M8::calculate_loads()
```

### 8.2 Called By

| Module | When |
|--------|------|
| M1 (Workflows) | After M5 returns raw activities from sync |

### 8.3 Calls To

| Module | Purpose |
|--------|---------|
| M3 | Write normalized activities to disk |
| M7 | (Receives input) Treadmill detection results |

### 8.4 Returns To

| Module | Data |
|--------|------|
| M7 | Normalized activities for RPE extraction |
| M8 | Normalized activities for load calculation |

### 8.5 Data Flow

```
[M5 Strava Integration]
      │
      ▼ RawActivity[]
[M6 Normalization] ◄── TreadmillDetection ──[M7 Notes Analyzer]
      │                       (pre-pass)
      ▼ NormalizedActivity[]
      │
      ├──► [M3 Repository I/O] ──► activities/YYYY-MM/*.yaml
      │
      └──► [M7 RPE Extraction] ──► [M8 Load Engine]
```

## 9. Test Scenarios

### 9.1 Unit Tests

```python
def test_normalize_sport_type_aliases():
    """All aliases map correctly"""
    assert normalize_sport_type("Run") == SportType.RUN
    assert normalize_sport_type("TrailRun") == SportType.TRAIL_RUN
    assert normalize_sport_type("ride") == SportType.CYCLE
    assert normalize_sport_type("indoor_cycling") == SportType.CYCLE
    assert normalize_sport_type("rock_climb") == SportType.CLIMB


def test_normalize_sport_type_sub_type_priority():
    """Sub-type takes priority over main type"""
    # Strava reports "Run" with sub_type "TrailRun"
    result = normalize_sport_type("Run", sub_type="TrailRun")
    assert result == SportType.TRAIL_RUN


def test_normalize_unknown_sport():
    """Unknown sports map to OTHER"""
    result = normalize_sport_type("underwater_basket_weaving")
    assert result == SportType.OTHER


def test_surface_type_treadmill_detection():
    """M7 treadmill detection overrides"""
    detection = TreadmillDetection(
        is_treadmill=True,
        confidence="high",
        signals=["no_gps", "title_contains_treadmill"]
    )

    surface, confidence = determine_surface_type(
        sport_type=SportType.RUN,
        treadmill_detection=detection,
        sub_type=None,
        has_gps=False,
    )

    assert surface == SurfaceType.TREADMILL
    assert confidence == "high"


def test_data_quality_treadmill_special():
    """Treadmill gets special data quality"""
    quality = determine_data_quality(
        has_gps=False,
        has_hr=True,
        surface_type=SurfaceType.TREADMILL,
        source="strava",
    )

    assert quality == DataQuality.TREADMILL


def test_unit_conversion():
    """Units convert correctly"""
    result = convert_units(
        distance_meters=10000,
        duration_seconds=3600,
        elevation_meters=150.5,
    )

    assert result["distance_km"] == 10.0
    assert result["duration_minutes"] == 60
    assert result["elevation_gain_m"] == 150.5


def test_filename_generation_with_time():
    """Filename uses start time when available"""
    activity = NormalizedActivity(
        id="123",
        source="strava",
        sport_type=SportType.RUN,
        name="Test",
        date=date(2025, 3, 15),
        start_time=datetime(2025, 3, 15, 7, 30),
        duration_minutes=45,
        duration_seconds=2700,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    filename = generate_activity_filename(activity, [])
    assert filename == "2025-03-15_run_0730.yaml"


def test_filename_collision_handling():
    """Collision increments index"""
    activity = NormalizedActivity(
        id="123",
        source="strava",
        sport_type=SportType.RUN,
        name="Test",
        date=date(2025, 3, 15),
        start_time=None,  # No time
        duration_minutes=45,
        duration_seconds=2700,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    existing = ["2025-03-15_run_1.yaml"]
    filename = generate_activity_filename(activity, existing)
    assert filename == "2025-03-15_run_2.yaml"
```

### 9.2 Integration Tests

```python
@pytest.mark.integration
async def test_full_normalization_pipeline():
    """End-to-end normalization with persistence"""
    raw = RawActivity(
        id="test_123",
        source=ActivitySource.STRAVA,
        sport_type="Run",
        sub_type="TrailRun",
        name="Morning Trail",
        date=date(2025, 3, 15),
        start_time=datetime(2025, 3, 15, 7, 30),
        duration_seconds=3600,
        distance_meters=10000,
        # ... other fields
    )

    repo = MockRepositoryIO()
    results = await normalize_and_persist([raw], repo)

    assert len(results) == 1
    assert results[0].activity.sport_type == SportType.TRAIL_RUN
    assert results[0].activity.surface_type == SurfaceType.TRAIL
    assert "2025-03-15_trailrun_0730.yaml" in results[0].file_path
```

### 9.3 Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Duration = 0 | Raise InvalidActivityError |
| Distance = None for run | Allow (manual entry might not have) |
| Unknown sport + key run tomorrow | Log warning, return suggestion text |
| Two activities same minute | Second gets index suffix (_2) |
| Treadmill detected but GPS present | Trust M7 detection, mark as treadmill |
| Activity name is empty | Generate default: "Run on 2025-03-15" |

## 10. Configuration

### 10.1 Normalization Settings

```python
# Default settings (can be overridden)
NORMALIZATION_CONFIG = {
    "strict_validation": False,      # Warn vs error on validation
    "preserve_raw_data": False,      # Store raw API response
    "max_duration_minutes": 600,     # 10 hour cap
    "min_duration_minutes": 1,       # Minimum valid duration
}
```

## 11. Performance Notes

- Normalization is CPU-bound, not I/O bound
- 100 activities normalize in < 100ms
- File writes are the bottleneck (use batch writes)
- Memory: ~1KB per normalized activity

## 12. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.2 | 2026-01-12 | Added code module path (`core/normalization.py`) and API layer integration notes. Updated M5 references to "Strava Integration". |
| 1.0.1 | 2026-01-12 | **Fixed type consistency and over-engineering**: (1) Converted `NormalizationResult` from `@dataclass` to `BaseModel` for Pydantic consistency. (2) Removed `dataclass` import. (3) Added note about v0 using synchronous I/O instead of async for `normalize_and_persist()` to avoid over-engineering. |
| 1.0.0 | 2026-01-12 | Initial specification |
