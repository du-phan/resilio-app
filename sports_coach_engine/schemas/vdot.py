"""
VDOT schemas - Training pace calculation data models.

This module defines all Pydantic schemas for VDOT (V-dot-O2-max) calculations,
training pace generation, and race performance predictions based on Jack Daniels'
Running Formula methodology.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Dict, Tuple
from datetime import timedelta
from enum import Enum


# ============================================================
# ENUMS
# ============================================================


class RaceDistance(str, Enum):
    """Supported race distances for VDOT calculation."""
    MILE = "mile"
    FIVE_K = "5k"
    TEN_K = "10k"
    FIFTEEN_K = "15k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"


class PaceUnit(str, Enum):
    """Units for pace display."""
    MIN_PER_KM = "min_per_km"
    MIN_PER_MILE = "min_per_mile"


class ConditionType(str, Enum):
    """Environmental conditions that affect pacing."""
    ALTITUDE = "altitude"
    HEAT = "heat"
    HUMIDITY = "humidity"
    HILLS = "hills"


class ConfidenceLevel(str, Enum):
    """Confidence level for VDOT calculations (time-based)."""
    HIGH = "high"        # Recent race (<2 weeks)
    MEDIUM = "medium"    # Race 2-6 weeks old
    LOW = "low"          # Race >6 weeks or estimated


class RaceSource(str, Enum):
    """Source/quality of race timing measurement."""
    OFFICIAL_RACE = "official_race"    # Chip-timed race (highest accuracy)
    GPS_WATCH = "gps_watch"            # GPS-verified effort (good accuracy)
    ESTIMATED = "estimated"            # Calculated/estimated (lower accuracy)


# ============================================================
# CORE VDOT MODELS
# ============================================================


class VDOTResult(BaseModel):
    """Result of VDOT calculation from race performance."""

    vdot: int = Field(..., ge=30, le=85, description="VDOT value (fitness level)")
    source_race: RaceDistance = Field(..., description="Race distance used for calculation")
    source_time_seconds: int = Field(..., gt=0, description="Race time in seconds")
    source_time_formatted: str = Field(..., description="Race time formatted as MM:SS or HH:MM:SS")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH, description="Confidence in this VDOT value")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class TrainingPaces(BaseModel):
    """Training pace zones derived from VDOT.

    All paces are stored internally in seconds per kilometer.
    Ranges represent min-max for each zone.
    """

    vdot: int = Field(..., ge=30, le=85)
    unit: PaceUnit = Field(default=PaceUnit.MIN_PER_KM)

    # Pace ranges (min, max) in seconds per km
    easy_pace_range: Tuple[int, int] = Field(..., description="E-pace (Zone 1-2): aerobic base")
    marathon_pace_range: Tuple[int, int] = Field(..., description="M-pace: marathon race pace")
    threshold_pace_range: Tuple[int, int] = Field(..., description="T-pace (Zone 4): lactate threshold")
    interval_pace_range: Tuple[int, int] = Field(..., description="I-pace (Zone 5): VO2max intervals")
    repetition_pace_range: Tuple[int, int] = Field(..., description="R-pace: speed/economy repeats")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )

    def format_pace(self, seconds_per_km: int) -> str:
        """Format pace as MM:SS string."""
        if self.unit == PaceUnit.MIN_PER_MILE:
            # Convert km to mile (1 mile = 1.609344 km)
            seconds_per_mile = int(seconds_per_km * 1.609344)
            minutes = seconds_per_mile // 60
            seconds = seconds_per_mile % 60
        else:
            minutes = seconds_per_km // 60
            seconds = seconds_per_km % 60
        return f"{minutes}:{seconds:02d}"

    def format_range(self, pace_range: Tuple[int, int]) -> str:
        """Format pace range as 'MM:SS-MM:SS'."""
        return f"{self.format_pace(pace_range[0])}-{self.format_pace(pace_range[1])}"


class RaceEquivalents(BaseModel):
    """Predicted race times for other distances based on VDOT."""

    vdot: int = Field(..., ge=30, le=85)
    source_race: RaceDistance
    source_time_formatted: str
    confidence: ConfidenceLevel

    # Predicted times for each distance (formatted as HH:MM:SS or MM:SS)
    predictions: Dict[RaceDistance, str] = Field(..., description="Predicted race times")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class SixSecondRulePaces(BaseModel):
    """Training paces derived from 6-second rule for novices.

    When a runner has no recent race but has a mile time, use the 6-second rule:
    - R-pace = mile pace
    - I-pace = R-pace + 6 sec per 400m
    - T-pace = I-pace + 6 sec per 400m

    Note: For VDOT 40-50 range, use 7-8 seconds instead of 6.
    """

    source_mile_time_seconds: int = Field(..., gt=0)
    source_mile_time_formatted: str

    # Paces in seconds per 400m
    r_pace_400m: int = Field(..., description="R-pace: seconds per 400m")
    i_pace_400m: int = Field(..., description="I-pace: R + adjustment")
    t_pace_400m: int = Field(..., description="T-pace: I + adjustment")

    adjustment_seconds: int = Field(default=6, description="Seconds added per 400m (6, 7, or 8)")
    estimated_vdot_range: Tuple[int, int] = Field(..., description="Estimated VDOT range")

    note: str = Field(
        default="For more accurate paces, use Daniels Table 5.3 or complete a recent 5K race",
        description="Guidance for improvement"
    )

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class PaceAdjustment(BaseModel):
    """Pace adjustment for environmental conditions."""

    base_pace_sec_per_km: int = Field(..., description="Original pace in seconds per km")
    adjusted_pace_sec_per_km: int = Field(..., description="Adjusted pace in seconds per km")
    adjustment_seconds: int = Field(..., description="Seconds added per km")
    condition_type: ConditionType
    severity: float = Field(..., description="Severity value (altitude in ft, temp in °C, etc.)")
    reason: str = Field(..., description="Explanation of adjustment")
    recommendation: str = Field(..., description="Coaching recommendation")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


# ============================================================
# VDOT TABLE DATA STRUCTURES
# ============================================================


class VDOTTableEntry(BaseModel):
    """Single entry in VDOT lookup table."""

    vdot: int = Field(..., ge=30, le=85)

    # Race times in seconds
    mile_seconds: Optional[int] = None
    five_k_seconds: Optional[int] = None
    ten_k_seconds: Optional[int] = None
    fifteen_k_seconds: Optional[int] = None
    half_marathon_seconds: Optional[int] = None
    marathon_seconds: Optional[int] = None

    # Training paces in seconds per km
    easy_min_sec_per_km: int = Field(..., description="E-pace min")
    easy_max_sec_per_km: int = Field(..., description="E-pace max")
    marathon_min_sec_per_km: int = Field(..., description="M-pace min")
    marathon_max_sec_per_km: int = Field(..., description="M-pace max")
    threshold_min_sec_per_km: int = Field(..., description="T-pace min")
    threshold_max_sec_per_km: int = Field(..., description="T-pace max")
    interval_min_sec_per_km: int = Field(..., description="I-pace min")
    interval_max_sec_per_km: int = Field(..., description="I-pace max")
    repetition_min_sec_per_km: int = Field(..., description="R-pace min")
    repetition_max_sec_per_km: int = Field(..., description="R-pace max")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class WorkoutPaceData(BaseModel):
    """Single workout pace data point for VDOT estimation."""

    date: str = Field(..., description="Workout date (ISO format)")
    workout_type: str = Field(..., description="Workout type (tempo, interval, etc.)")
    pace_sec_per_km: int = Field(..., description="Average pace in seconds per km")
    implied_vdot: int = Field(..., description="VDOT implied by this pace")


class VDOTEstimate(BaseModel):
    """Current VDOT estimate from recent workout paces."""

    estimated_vdot: int = Field(..., ge=30, le=85, description="Estimated current VDOT")
    confidence: ConfidenceLevel = Field(..., description="Confidence in estimate")
    source: str = Field(..., description="Data source (e.g., 'tempo_workouts', 'interval_workouts')")
    supporting_data: list[WorkoutPaceData] = Field(
        default_factory=list, description="Workout paces used for estimation"
    )

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )
