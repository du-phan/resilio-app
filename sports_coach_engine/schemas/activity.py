"""
Activity schemas - Complete data models for Phase 2 (M5, M6, M7, M8).

This module contains all Pydantic models for the activity processing pipeline:
- RawActivity: Raw data from Strava API or manual input (M5)
- NormalizedActivity: Standardized activity format (M6)
- RPE and Analysis models: Notes analysis results (M7)
- Load models: Training load calculations (M8)
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================
# M5 - STRAVA INTEGRATION MODELS
# ============================================================


class LapData(BaseModel):
    """
    Individual lap/split from Strava (manual or auto-lap).

    Laps enable workout verification, pacing analysis, and HR drift detection.
    Used by analytical CLI tools to validate execution against planned workouts.
    """

    # Identity
    lap_index: int  # 1-based sequence number
    name: Optional[str] = None  # "Lap 1", "Warmup" (if athlete labels)

    # Time
    elapsed_time_seconds: int  # Total including stops
    moving_time_seconds: int  # Active time only
    start_date: datetime
    start_date_local: datetime

    # Distance
    distance_meters: float

    # Pace (pre-computed for display)
    average_speed_mps: Optional[float] = None  # m/s
    max_speed_mps: Optional[float] = None
    pace_per_km: Optional[str] = None  # "5:23" format for running

    # Heart Rate
    average_hr: Optional[float] = None
    max_hr: Optional[float] = None

    # Elevation
    total_elevation_gain_meters: Optional[float] = None

    # Power & Cadence (cycling, future use)
    average_watts: Optional[float] = None
    max_watts: Optional[float] = None
    average_cadence: Optional[float] = None

    # Stream indices (for future GPS overlay)
    start_index: Optional[int] = None
    end_index: Optional[int] = None

    # Split type
    split_type: str = "auto"  # "auto" | "manual" (Strava doesn't distinguish; assume auto)


class ActivitySource(str, Enum):
    """Source of activity data."""

    STRAVA = "strava"
    MANUAL = "manual"


class StravaWorkoutType(int, Enum):
    """Strava workout_type values for running (undocumented)."""

    DEFAULT = 0
    RACE = 1
    LONG_RUN = 2
    WORKOUT = 3


class RawActivity(BaseModel):
    """
    Raw activity data as received from source (Strava or manual input).
    Passed to M6 for normalization.
    """

    # Identity
    id: str
    source: ActivitySource

    # Core fields
    sport_type: str  # e.g., "Run", "Ride", "Climb"
    sub_type: Optional[str] = None  # e.g., "TrailRun", "VirtualRide"
    name: str  # Activity title
    date: date
    start_time: Optional[datetime] = None  # Local start time

    # Effort metrics
    duration_seconds: int
    distance_meters: Optional[float] = None
    elevation_gain_meters: Optional[float] = None

    # Heart rate (Strava returns floats)
    average_hr: Optional[float] = None
    max_hr: Optional[float] = None
    has_hr_data: bool = False

    # User input
    description: Optional[str] = None  # Public description
    private_note: Optional[str] = None  # Private notes (Strava premium)
    perceived_exertion: Optional[int] = None  # User-entered RPE (1-10)

    # Strava-specific
    workout_type: Optional[int] = None  # Race=1, Long run=2, Workout=3
    suffer_score: Optional[int] = None  # Strava relative effort
    has_polyline: bool = False  # GPS data present
    gear_id: Optional[str] = None  # Equipment used
    device_name: Optional[str] = None  # Recording device

    # Timestamps
    strava_created_at: Optional[datetime] = None
    strava_updated_at: Optional[datetime] = None

    # Lap data (fetched from /activities/{id}/laps endpoint)
    laps: list[LapData] = Field(default_factory=list)
    has_laps: bool = False

    # Metadata
    raw_data: dict = Field(default_factory=dict)  # Full API response


class SyncState(BaseModel):
    """
    Tracks Strava sync progress for incremental syncs.
    Field names match M4's training_history.yaml schema.
    """

    last_strava_sync_at: Optional[datetime] = None
    last_strava_activity_id: Optional[str] = None


class SyncResult(BaseModel):
    """Result of a sync operation."""

    success: bool
    activities_fetched: int
    activities_new: int
    activities_updated: int
    activities_skipped: int
    errors: list[str] = Field(default_factory=list)
    sync_duration_seconds: float
    laps_fetched: int = 0  # Laps successfully fetched
    laps_skipped_age: int = 0  # Laps skipped due to age filter (historical sync)
    lap_fetch_failures: int = 0  # Laps fetch attempts that failed


class ManualActivityInput(BaseModel):
    """User-provided activity data for manual logging."""

    sport_type: str
    date: date
    duration_minutes: int
    distance_km: Optional[float] = None
    description: Optional[str] = None
    perceived_exertion: Optional[int] = Field(None, ge=1, le=10)
    average_hr: Optional[int] = Field(None, ge=30, le=250)

    model_config = ConfigDict(extra="forbid")


# ============================================================
# M6 - ACTIVITY NORMALIZATION MODELS
# ============================================================


class SportType(str, Enum):
    """Canonical sport types."""

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
    """Running surface types."""

    ROAD = "road"
    TRAIL = "trail"
    TRACK = "track"
    TREADMILL = "treadmill"
    GRASS = "grass"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class DataQuality(str, Enum):
    """Reliability indicator for activity data."""

    HIGH = "high"  # GPS + HR + verified source
    MEDIUM = "medium"  # Some data missing or inferred
    LOW = "low"  # Minimal data, heavy inference
    TREADMILL = "treadmill"  # Pace unreliable, HR prioritized


class NormalizedActivity(BaseModel):
    """
    Fully normalized activity ready for downstream processing.
    This is the schema for activities/YYYY-MM/*.yaml files.
    """

    # Schema metadata
    schema_metadata: dict = Field(
        default_factory=lambda: {"format_version": "1.0.0", "schema_type": "activity"},
        alias="_schema",
    )

    # Identity
    id: str
    source: str  # "strava" | "manual"

    # Core fields (required)
    sport_type: SportType
    sub_type: Optional[str] = None  # Original Strava sub-type if present
    name: str
    date: date
    day_of_week: Optional[int] = None  # 0=Monday, 1=Tuesday, ..., 6=Sunday (ISO 8601)
    day_of_week_name: Optional[str] = None  # "Monday", "Tuesday", etc.
    start_time: Optional[datetime] = None
    duration_minutes: int
    duration_seconds: int

    # Distance (optional for non-distance sports)
    distance_km: Optional[float] = None
    distance_meters: Optional[float] = None
    elevation_gain_m: Optional[float] = None

    # Heart rate (optional, Strava returns floats)
    average_hr: Optional[float] = None
    max_hr: Optional[float] = None
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

    # Lap data (from Strava laps endpoint)
    laps: list[LapData] = Field(default_factory=list)
    has_laps: bool = False

    # Equipment
    gear_id: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    synced_at: Optional[datetime] = None

    # Calculated load (added by M8 Load Engine)
    calculated: Optional["LoadCalculation"] = None

    @model_validator(mode="before")
    @classmethod
    def compute_day_of_week(cls, data):
        """Automatically compute day_of_week fields from date if not provided."""
        if isinstance(data, dict):
            # Only compute if fields are not already set
            if data.get("day_of_week") is None or data.get("day_of_week_name") is None:
                activity_date = data.get("date")
                if activity_date:
                    # Handle both date objects and string dates
                    if isinstance(activity_date, str):
                        from datetime import datetime as dt

                        activity_date = dt.strptime(activity_date, "%Y-%m-%d").date()

                    # Compute day of week (0=Monday, ..., 6=Sunday per ISO 8601)
                    day_of_week = activity_date.weekday()
                    day_names = [
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                        "Sunday",
                    ]
                    day_of_week_name = day_names[day_of_week]

                    # Set the computed values
                    data["day_of_week"] = day_of_week
                    data["day_of_week_name"] = day_of_week_name

        return data

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,  # Allow both field name and alias
    )


class NormalizationResult(BaseModel):
    """Result of normalizing a single activity."""

    activity: NormalizedActivity
    file_path: str
    was_updated: bool  # True if existing file was updated
    warnings: list[str] = Field(default_factory=list)


# ============================================================
# M7 - NOTES & RPE ANALYZER MODELS
# ============================================================


class RPESource(str, Enum):
    """Source of RPE estimate."""

    USER_INPUT = "user_input"  # Explicit Strava perceived_exertion
    HR_BASED = "hr_based"  # Derived from HR zones
    PACE_BASED = "pace_based"  # Derived from pace vs VDOT zones (running only)
    TEXT_BASED = "text_based"  # Extracted from notes
    STRAVA_RELATIVE = "strava_relative"  # Normalized suffer_score
    DURATION_HEURISTIC = "duration_heuristic"  # Sport + duration fallback


class FlagSeverity(str, Enum):
    """Severity level for health flags."""

    MILD = "mild"  # Informational, no action required
    MODERATE = "moderate"  # Consider adjustments
    SEVERE = "severe"  # Requires rest or medical attention


class BodyPart(str, Enum):
    """Tracked body parts for injury flags."""

    KNEE = "knee"
    ANKLE = "ankle"
    CALF = "calf"
    SHIN = "shin"
    HIP = "hip"
    HAMSTRING = "hamstring"
    QUAD = "quad"
    ACHILLES = "achilles"
    FOOT = "foot"
    BACK = "back"
    SHOULDER = "shoulder"
    GENERAL = "general"


class RPEEstimate(BaseModel):
    """RPE estimate with source and confidence."""

    value: int  # 1-10
    source: RPESource
    confidence: str  # "high" | "medium" | "low"
    reasoning: str  # Explanation for the estimate


class RPEConflict(BaseModel):
    """Detected conflict between RPE sources."""

    estimates: list[RPEEstimate]
    spread: int  # Difference between max and min
    resolved_value: int
    resolution_method: str


class TreadmillDetection(BaseModel):
    """Result of treadmill/indoor detection."""

    is_treadmill: bool
    confidence: str  # "high" | "low"
    signals: list[str] = Field(default_factory=list)  # Evidence for detection


class InjuryFlag(BaseModel):
    """Detected injury or pain signal."""

    body_part: BodyPart
    severity: FlagSeverity
    keywords_found: list[str] = Field(default_factory=list)
    source_text: str
    requires_rest: bool


class IllnessFlag(BaseModel):
    """Detected illness signal."""

    severity: FlagSeverity
    symptoms: list[str] = Field(default_factory=list)
    keywords_found: list[str] = Field(default_factory=list)
    source_text: str
    rest_days_recommended: int


class ContextualFactors(BaseModel):
    """Environmental or situational factors."""

    is_fasted: bool = False
    heat_mentioned: bool = False
    cold_mentioned: bool = False
    altitude_mentioned: bool = False
    travel_mentioned: bool = False
    after_work: bool = False
    early_morning: bool = False


class AnalysisResult(BaseModel):
    """
    Complete analysis result for an activity (Toolkit Paradigm).

    Returns multiple RPE estimates from quantitative sources.
    Claude Code uses these estimates with conversation context to
    determine final RPE. Injury and illness extraction
    are handled by Claude Code via natural conversation.
    """

    activity_id: str

    # RPE estimates from all available quantitative sources
    # Claude Code chooses which to use based on context
    rpe_estimates: list[RPEEstimate] = Field(default_factory=list)

    # Treadmill detection (multi-signal scoring)
    treadmill_detection: TreadmillDetection

    # Metadata
    analyzed_at: datetime
    notes_present: bool  # Whether notes/description available for Claude to parse


# ============================================================
# M8 - LOAD ENGINE MODELS
# ============================================================


class SessionType(str, Enum):
    """Training session intensity classification."""

    EASY = "easy"  # Recovery, zone 1-2, RPE 1-4
    MODERATE = "moderate"  # Steady-state, zone 3, RPE 5-6
    QUALITY = "quality"  # Tempo, intervals, threshold, RPE 7-8
    RACE = "race"  # Competition or time trial, RPE 9-10


class SportMultipliers(BaseModel):
    """Load multipliers for a sport type."""

    sport: str
    systemic: float  # 0.0 - 1.5
    lower_body: float  # 0.0 - 1.5
    description: str


class LoadCalculation(BaseModel):
    """Complete load calculation for an activity."""

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
    multiplier_adjustments: list[str] = Field(
        default_factory=list
    )  # Explanations for any adjustments

    # Final loads
    systemic_load_au: float
    lower_body_load_au: float

    # Session classification
    session_type: SessionType


class MultiplierAdjustment(BaseModel):
    """Record of an adjustment made to base multipliers."""

    reason: str
    channel: str  # "systemic" | "lower_body"
    original: float
    adjusted: float


# ============================================================
# LEGACY MODELS (for backwards compatibility)
# ============================================================


class Activity(BaseModel):
    """Base activity model (legacy)."""

    id: str
    source: str
    sport_type: str
    date: date
    duration_minutes: int
    distance_km: Optional[float] = None


class ProcessedActivity(BaseModel):
    """Activity after full processing pipeline (to be implemented in Phase 3)."""

    pass
