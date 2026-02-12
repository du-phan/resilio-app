"""
M6 - Activity Normalization

Transform raw activities into consistent schema with normalized sport types,
units, and surface detection. Ensures all activities conform to the
NormalizedActivity schema before downstream processing.

This module handles:
- Sport type normalization (300+ Strava types → 13 canonical)
- Surface type detection (using M7 treadmill detection)
- Data quality assessment (HIGH/MEDIUM/LOW/TREADMILL)
- Unit conversions (meters→km, seconds→minutes)
- Filename generation with collision handling
- File persistence via M3 Repository I/O
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sports_coach_engine.core.notes import detect_treadmill
from sports_coach_engine.core.paths import activities_month_dir
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.activity import (
    DataQuality,
    NormalizedActivity,
    NormalizationResult,
    RawActivity,
    SportType,
    SurfaceType,
)


# ============================================================
# ERROR TYPES
# ============================================================


class NormalizationError(Exception):
    """Base exception for normalization errors."""

    pass


class InvalidActivityError(NormalizationError):
    """Activity data is invalid or missing required fields."""

    pass


# ============================================================
# SPORT TYPE MAPPING
# ============================================================

# Map 300+ Strava sport types to 13 canonical types
# Reference: https://developers.strava.com/docs/reference/#api-models-SportType
SPORT_ALIASES = {
    # Running variants
    "run": SportType.RUN,
    "running": SportType.RUN,
    "trailrun": SportType.TRAIL_RUN,
    "trail run": SportType.TRAIL_RUN,
    "trail running": SportType.TRAIL_RUN,
    "virtualrun": SportType.TREADMILL_RUN,
    "treadmill": SportType.TREADMILL_RUN,
    "treadmill run": SportType.TREADMILL_RUN,
    "treadmill running": SportType.TREADMILL_RUN,
    "indoor run": SportType.TREADMILL_RUN,
    "indoor running": SportType.TREADMILL_RUN,
    "trackrun": SportType.TRACK_RUN,
    "track": SportType.TRACK_RUN,
    "track run": SportType.TRACK_RUN,
    # Cycling variants (all map to cycle)
    "ride": SportType.CYCLE,
    "cycling": SportType.CYCLE,
    "bike": SportType.CYCLE,
    "biking": SportType.CYCLE,
    "virtualride": SportType.CYCLE,
    "ebikeride": SportType.CYCLE,
    "gravelride": SportType.CYCLE,
    "mountainbikeride": SportType.CYCLE,
    "handcycle": SportType.CYCLE,
    "velomobile": SportType.CYCLE,
    # Swimming
    "swim": SportType.SWIM,
    "swimming": SportType.SWIM,
    # Climbing variants
    "rockclimbing": SportType.CLIMB,
    "rock climbing": SportType.CLIMB,
    "climbing": SportType.CLIMB,
    "bouldering": SportType.CLIMB,
    "indoor climbing": SportType.CLIMB,
    # Strength variants
    "weighttraining": SportType.STRENGTH,
    "weight training": SportType.STRENGTH,
    "strength": SportType.STRENGTH,
    "strength training": SportType.STRENGTH,
    "workout": SportType.STRENGTH,
    # CrossFit/metcon
    "crossfit": SportType.CROSSFIT,
    "hiit": SportType.CROSSFIT,
    # Yoga
    "yoga": SportType.YOGA,
    # Hiking
    "hike": SportType.HIKE,
    "hiking": SportType.HIKE,
    # Walking
    "walk": SportType.WALK,
    "walking": SportType.WALK,
}


# ============================================================
# CORE NORMALIZATION
# ============================================================


def normalize_activity(
    raw: RawActivity,
    repo: Optional[RepositoryIO] = None,
) -> NormalizedActivity:
    """
    Normalize a raw activity into standard format.

    Performs:
    - Sport type normalization
    - Surface type detection
    - Data quality assessment
    - Unit conversions

    Args:
        raw: Raw activity from Strava or manual input
        repo: Repository I/O instance (optional, for filename check)

    Returns:
        NormalizedActivity with all fields normalized

    Raises:
        InvalidActivityError: If required fields are missing or invalid
    """
    # Validate required fields
    if not raw.sport_type:
        raise InvalidActivityError("sport_type is required")
    if raw.duration_seconds <= 0:
        raise InvalidActivityError("duration_seconds must be positive")

    # Normalize sport type
    sport_type = normalize_sport_type(raw.sport_type, raw.sub_type)

    # Detect surface type
    surface_type, surface_confidence = determine_surface_type(
        sport_type=sport_type,
        original_sport_type=raw.sport_type,
        sub_type=raw.sub_type,
        activity_name=raw.name,
        description=raw.description,
        has_gps=raw.has_polyline,
        device_name=raw.device_name,
    )

    # Assess data quality
    data_quality = determine_data_quality(
        source=raw.source,
        has_gps=raw.has_polyline,
        has_hr=raw.has_hr_data,
        surface_type=surface_type,
    )

    # Convert units
    duration_minutes = raw.duration_seconds // 60
    distance_km = (
        round(raw.distance_meters / 1000, 2) if raw.distance_meters else None
    )

    # Compute day of week from date (0=Monday, ..., 6=Sunday per ISO 8601)
    day_of_week = raw.date.weekday()
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_of_week_name = day_names[day_of_week]

    # Create normalized activity
    now = datetime.now(timezone.utc)
    normalized = NormalizedActivity(
        # Identity
        id=raw.id,
        source=raw.source.value,
        # Core fields
        sport_type=sport_type,
        sub_type=raw.sub_type,
        name=raw.name,
        date=raw.date,
        day_of_week=day_of_week,
        day_of_week_name=day_of_week_name,
        start_time=raw.start_time,
        duration_minutes=duration_minutes,
        duration_seconds=raw.duration_seconds,
        # Distance
        distance_km=distance_km,
        distance_meters=raw.distance_meters,
        elevation_gain_m=raw.elevation_gain_meters,
        # Heart rate
        average_hr=raw.average_hr,
        max_hr=raw.max_hr,
        has_hr_data=raw.has_hr_data,
        # User notes
        description=raw.description,
        private_note=raw.private_note,
        # Strava-specific
        workout_type=raw.workout_type,
        suffer_score=raw.suffer_score,
        perceived_exertion=raw.perceived_exertion,
        # Surface and quality
        surface_type=surface_type,
        surface_type_confidence=surface_confidence,
        data_quality=data_quality,
        # GPS data
        has_gps_data=raw.has_polyline,
        # Lap data (preserve from raw)
        laps=raw.laps,
        has_laps=raw.has_laps,
        # Equipment
        gear_id=raw.gear_id,
        # Timestamps
        created_at=raw.strava_created_at or now,
        updated_at=raw.strava_updated_at or now,
        synced_at=now,
    )

    return normalized


def normalize_and_persist(
    raw: RawActivity,
    repo: RepositoryIO,
) -> NormalizationResult:
    """
    Normalize activity and persist to disk.

    Args:
        raw: Raw activity from Strava or manual input
        repo: Repository I/O instance for file operations

    Returns:
        NormalizationResult with file path and status

    Raises:
        InvalidActivityError: If normalization fails
    """
    # Normalize
    normalized = normalize_activity(raw, repo)

    # Generate filename
    file_path = generate_activity_filename(normalized, repo)

    # Check if file exists (for update detection)
    was_updated = repo.file_exists(file_path)

    # Write to disk using M3
    warnings = []
    try:
        # Use write_yaml (takes BaseModel directly)
        result = repo.write_yaml(file_path, normalized)

        if result is not None:  # Error occurred
            warnings.append(f"Write warning: {result.message}")

    except Exception as e:
        raise InvalidActivityError(f"Activity write failed: {e}")

    return NormalizationResult(
        activity=normalized,
        file_path=file_path,
        was_updated=was_updated,
        warnings=warnings,
    )


# ============================================================
# SPORT TYPE NORMALIZATION
# ============================================================


def normalize_sport_type(
    sport_type: str,
    sub_type: Optional[str] = None,
) -> SportType:
    """
    Normalize sport type to canonical value.

    Priority order:
    1. Sub-type (more specific)
    2. Main sport_type
    3. Default to OTHER if unknown

    Args:
        sport_type: Main sport type from Strava
        sub_type: Optional sub-type for more specificity

    Returns:
        Canonical SportType enum value
    """
    # Try sub_type first (more specific)
    if sub_type:
        normalized = SPORT_ALIASES.get(sub_type.lower())
        if normalized:
            return normalized

    # Try main sport_type
    normalized = SPORT_ALIASES.get(sport_type.lower())
    if normalized:
        return normalized

    # Unknown sport - default to OTHER
    return SportType.OTHER


# ============================================================
# SURFACE TYPE DETECTION
# ============================================================


def determine_surface_type(
    sport_type: SportType,
    original_sport_type: str,
    sub_type: Optional[str],
    activity_name: str,
    description: Optional[str],
    has_gps: bool,
    device_name: Optional[str],
) -> tuple[SurfaceType, str]:
    """
    Determine surface type with confidence level.

    Decision tree:
    1. Use M7 treadmill detection for running
    2. Use explicit sport_type indicators (trail_run, track_run)
    3. Fall back to GPS-based heuristics
    4. Default to UNKNOWN for non-running sports

    Args:
        sport_type: Normalized sport type
        original_sport_type: Original Strava sport type
        sub_type: Sport sub-type
        activity_name: Activity title
        description: Activity description
        has_gps: Whether GPS data is present
        device_name: Recording device name

    Returns:
        Tuple of (SurfaceType, confidence: "high" | "low")
    """
    # Only determine surface for running activities
    if sport_type not in {
        SportType.RUN,
        SportType.TRAIL_RUN,
        SportType.TREADMILL_RUN,
        SportType.TRACK_RUN,
    }:
        return SurfaceType.UNKNOWN, "high"

    # Priority 1: Explicit treadmill sport type
    if sport_type == SportType.TREADMILL_RUN:
        return SurfaceType.TREADMILL, "high"

    # Priority 2: Explicit trail sport type
    if sport_type == SportType.TRAIL_RUN:
        return SurfaceType.TRAIL, "high"

    # Priority 3: Explicit track sport type
    if sport_type == SportType.TRACK_RUN:
        return SurfaceType.TRACK, "high"

    # Priority 4: M7 treadmill detection (for generic "run")
    if sport_type == SportType.RUN:
        treadmill_result = detect_treadmill(
            activity_name=activity_name,
            description=description,
            has_gps=has_gps,
            sport_type=original_sport_type,
            sub_type=sub_type,
            device_name=device_name,
        )

        if treadmill_result.is_treadmill:
            # Map M7 confidence to our confidence
            return SurfaceType.TREADMILL, treadmill_result.confidence

    # Priority 5: Default to road for outdoor running
    if has_gps:
        return SurfaceType.ROAD, "high"

    # Priority 6: No GPS suggests treadmill (but low confidence)
    return SurfaceType.TREADMILL, "low"


# ============================================================
# DATA QUALITY ASSESSMENT
# ============================================================


def determine_data_quality(
    source: str,
    has_gps: bool,
    has_hr: bool,
    surface_type: SurfaceType,
) -> DataQuality:
    """
    Assess data quality for the activity.

    Quality levels:
    - HIGH: GPS + HR + Strava source
    - MEDIUM: Missing GPS or HR
    - LOW: Manual entry or minimal data
    - TREADMILL: Special case (pace unreliable, HR prioritized)

    Args:
        source: Activity source ("strava" or "manual")
        has_gps: Whether GPS data is present
        has_hr: Whether heart rate data is present
        surface_type: Detected surface type

    Returns:
        DataQuality enum value
    """
    # Treadmill gets special quality marker
    if surface_type == SurfaceType.TREADMILL:
        return DataQuality.TREADMILL

    # Manual entries are always LOW quality
    if source == "manual":
        return DataQuality.LOW

    # Strava activities: assess based on sensor data
    if has_gps and has_hr:
        return DataQuality.HIGH
    elif has_gps or has_hr:
        return DataQuality.MEDIUM
    else:
        return DataQuality.LOW


# ============================================================
# FILENAME GENERATION
# ============================================================


def generate_activity_filename(
    activity: NormalizedActivity,
    repo: RepositoryIO,
) -> str:
    """
    Generate unique filename for activity.

    Format: activities/YYYY-MM/YYYY-MM-DD_<sport>_<HHmm>.yaml

    If start_time is missing: YYYY-MM-DD_<sport>_<N>.yaml
    If collision occurs: increment N until unique (max 99)

    Args:
        activity: Normalized activity
        repo: Repository I/O for existence checks

    Returns:
        Relative file path from repo root
    """
    # Base directory: data/activities/YYYY-MM/
    year_month = activity.date.strftime("%Y-%m")
    base_dir = activities_month_dir(year_month)

    # Date prefix: YYYY-MM-DD
    date_str = activity.date.strftime("%Y-%m-%d")

    # Sport name (lowercase, underscores)
    # Note: sport_type is already a string due to use_enum_values=True
    sport_name = activity.sport_type.replace(" ", "_")

    # Generate filename
    if activity.start_time:
        # Use time: YYYY-MM-DD_sport_HHmm.yaml
        time_str = activity.start_time.strftime("%H%M")
        base_filename = f"{date_str}_{sport_name}_{time_str}.yaml"
    else:
        # Use index: YYYY-MM-DD_sport_N.yaml
        base_filename = f"{date_str}_{sport_name}_1.yaml"

    file_path = f"{base_dir}/{base_filename}"

    # Handle collisions
    if repo.file_exists(file_path):
        # Extract index or time and increment
        if activity.start_time:
            # Multiple activities at same time - add index
            for i in range(2, 100):
                file_path = f"{base_dir}/{date_str}_{sport_name}_{time_str}_{i}.yaml"
                if not repo.file_exists(file_path):
                    break
        else:
            # Increment index
            for i in range(2, 100):
                file_path = f"{base_dir}/{date_str}_{sport_name}_{i}.yaml"
                if not repo.file_exists(file_path):
                    break

    return file_path


# ============================================================
# VALIDATION
# ============================================================


def validate_activity(activity: NormalizedActivity) -> list[str]:
    """
    Perform sanity checks on normalized activity.

    Checks:
    - Duration is reasonable (> 0, < 24 hours)
    - Pace is reasonable for the sport (if distance present)
    - Heart rate is within human ranges (30-250)

    Args:
        activity: Normalized activity to validate

    Returns:
        List of warning messages (empty if all checks pass)
    """
    warnings = []

    # Duration checks
    if activity.duration_seconds <= 0:
        warnings.append("Duration is zero or negative")
    elif activity.duration_seconds > 86400:  # 24 hours
        warnings.append("Duration exceeds 24 hours")

    # Pace checks (for distance activities)
    if activity.distance_km and activity.distance_km > 0:
        pace_min_per_km = activity.duration_minutes / activity.distance_km

        # Reasonable pace ranges by sport
        if activity.sport_type == SportType.RUN:
            if pace_min_per_km < 2.5:  # Faster than 2:30/km
                warnings.append("Running pace unrealistically fast")
            elif pace_min_per_km > 15:  # Slower than 15:00/km
                warnings.append("Running pace unrealistically slow")

        elif activity.sport_type == SportType.CYCLE:
            if pace_min_per_km < 0.5:  # Faster than 120 km/h
                warnings.append("Cycling speed unrealistically fast")

    # Heart rate checks
    if activity.average_hr:
        if activity.average_hr < 30 or activity.average_hr > 250:
            warnings.append("Average heart rate outside human range")

    if activity.max_hr:
        if activity.max_hr < 30 or activity.max_hr > 250:
            warnings.append("Max heart rate outside human range")

    if activity.average_hr and activity.max_hr:
        if activity.average_hr > activity.max_hr:
            warnings.append("Average HR exceeds max HR")

    return warnings
