"""
Profile schemas - Athlete profile data models.
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import date
from enum import Enum
import warnings

from sports_coach_engine.schemas.adaptation import AdaptationThresholds


# ============================================================
# ENUMS
# ============================================================


class Weekday(str, Enum):
    """Days of the week."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class RunningPriority(str, Enum):
    """Priority level for running relative to other sports."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EQUAL = "equal"


class ConflictPolicy(str, Enum):
    """Policy for resolving conflicts between running and other sports."""

    PRIMARY_SPORT_WINS = "primary_sport_wins"
    RUNNING_GOAL_WINS = "running_goal_wins"
    ASK_EACH_TIME = "ask_each_time"


class GoalType(str, Enum):
    """Type of running goal."""

    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"
    GENERAL_FITNESS = "general_fitness"




class DetailLevel(str, Enum):
    """Level of detail in coaching responses."""

    BRIEF = "brief"
    MODERATE = "moderate"
    DETAILED = "detailed"


class CoachingStyle(str, Enum):
    """Coaching communication style."""

    SUPPORTIVE = "supportive"
    DIRECT = "direct"
    ANALYTICAL = "analytical"


class IntensityMetric(str, Enum):
    """Primary intensity metric for prescribing workouts."""

    PACE = "pace"
    HR = "hr"
    RPE = "rpe"


# ============================================================
# CORE MODELS
# ============================================================


class VitalSigns(BaseModel):
    """Athlete vital signs and HR zones."""

    resting_hr: Optional[int] = Field(default=None, ge=30, le=100)
    max_hr: Optional[int] = Field(default=None, ge=120, le=220)


class Goal(BaseModel):
    """Training goal."""

    type: GoalType
    target_date: Optional[str] = None  # ISO date string
    target_time: Optional[str] = None  # HH:MM:SS format


class TrainingConstraints(BaseModel):
    """Training constraints and availability.

    Uses subtractive scheduling model: specify days you CAN'T run,
    rather than listing all days you CAN run.
    """

    blocked_run_days: List[Weekday] = Field(
        default_factory=list,
        description="Days you absolutely cannot run (e.g., fixed climbing/yoga commitments)"
    )
    preferred_long_run_days: List[Weekday] = Field(
        default_factory=lambda: [Weekday.SATURDAY, Weekday.SUNDAY],
        description="Preferred days for long runs (soft preference)"
    )
    min_run_days_per_week: int = Field(ge=0, le=7)
    max_run_days_per_week: int = Field(ge=0, le=7)
    max_time_per_session_minutes: Optional[int] = Field(default=90, ge=0)


class OtherSport(BaseModel):
    """Other sport commitment."""

    sport: str
    days: Optional[List[Weekday]] = None  # Preferred/fixed days (None = flexible)
    frequency_per_week: Optional[int] = Field(
        default=None, ge=1, le=7, description="How many times per week (required if days not specified)"
    )
    typical_duration_minutes: int = Field(default=60, ge=0)
    typical_intensity: str = "moderate"  # easy, moderate, hard, moderate_to_hard
    is_flexible: bool = False  # Can this commitment be rescheduled?
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_frequency_and_days(self) -> "OtherSport":
        """
        Validate and auto-fill frequency_per_week and is_flexible fields.

        Rules:
        - If days provided and frequency not set → auto-set frequency = len(days)
        - If frequency provided without days → auto-set is_flexible = True
        - At least one of days or frequency_per_week must be provided
        """
        if self.days is not None and self.frequency_per_week is None:
            # Auto-set frequency from days length
            self.frequency_per_week = len(self.days)

        if self.frequency_per_week is not None and self.days is None:
            # Frequency without specific days means flexible scheduling
            self.is_flexible = True

        # Validate: at least one must be provided
        if self.days is None and self.frequency_per_week is None:
            raise ValueError(
                "Either 'days' or 'frequency_per_week' must be provided. "
                "Specify fixed days (--days monday,wednesday) or frequency (--frequency 3)."
            )

        return self


class CommunicationPreferences(BaseModel):
    """Communication and coaching preferences."""

    detail_level: DetailLevel = DetailLevel.MODERATE
    coaching_style: CoachingStyle = CoachingStyle.SUPPORTIVE
    intensity_metric: IntensityMetric = IntensityMetric.PACE


class StravaConnection(BaseModel):
    """Strava connection info."""

    athlete_id: str


class PBEntry(BaseModel):
    """Personal best for a single distance."""

    time: str  # HH:MM:SS or MM:SS format
    date: str  # ISO date string (YYYY-MM-DD)
    vdot: float = Field(ge=30.0, le=85.0, description="Pre-calculated VDOT for this PB")


class AthleteProfile(BaseModel):
    """Complete athlete profile."""

    # Basic Info
    name: str
    created_at: str  # ISO date string
    age: Optional[int] = Field(default=None, ge=0, le=120)

    # Vital Signs
    vital_signs: Optional[VitalSigns] = None

    # Strava Connection
    strava: Optional[StravaConnection] = None

    # Running Background
    running_experience_years: Optional[float] = Field(default=None, ge=0)

    # Recent Fitness Snapshot
    current_weekly_run_km: Optional[float] = Field(default=None, ge=0)
    vdot: Optional[float] = Field(
        default=None,
        ge=30.0,
        le=85.0,
        description="Jack Daniels VDOT (calculated from recent_race or estimated)"
    )

    # Personal Bests & Peak Performance Tracking
    personal_bests: dict[str, PBEntry] = Field(
        default_factory=dict,
        description="Personal bests by distance (e.g., '10k' -> PBEntry)"
    )
    peak_vdot: Optional[float] = Field(
        default=None,
        ge=30.0,
        le=85.0,
        description="Highest VDOT achieved (from personal_bests)"
    )
    peak_vdot_date: Optional[str] = Field(
        default=None,
        description="ISO date when peak VDOT was achieved"
    )

    # Workout Pattern Fields (computed from activity history)
    typical_easy_distance_km: Optional[float] = Field(
        default=None,
        ge=0,
        description="Athlete's typical easy run distance (last 60 days avg)"
    )
    typical_easy_duration_min: Optional[float] = Field(
        default=None,
        ge=0,
        description="Athlete's typical easy run duration (last 60 days avg)"
    )
    typical_long_run_distance_km: Optional[float] = Field(
        default=None,
        ge=0,
        description="Athlete's typical long run distance (last 60 days avg)"
    )
    typical_long_run_duration_min: Optional[float] = Field(
        default=None,
        ge=0,
        description="Athlete's typical long run duration (last 60 days avg)"
    )

    # Training Constraints
    constraints: TrainingConstraints

    # Other Sports
    other_sports: Optional[List[OtherSport]] = Field(default_factory=list)

    # Priority Setting
    running_priority: RunningPriority
    primary_sport: Optional[str] = None

    # Conflict Resolution
    conflict_policy: ConflictPolicy

    # Current Goal
    goal: Goal

    # Communication Preferences
    preferences: CommunicationPreferences = Field(
        default_factory=CommunicationPreferences
    )

    # Adaptation Thresholds (Phase 5: Toolkit Paradigm)
    adaptation_thresholds: AdaptationThresholds = Field(
        default_factory=AdaptationThresholds,
        description="Athlete-specific thresholds for adaptation triggers"
    )

    @model_validator(mode="after")
    def validate_multi_sport_awareness(self) -> "AthleteProfile":
        """
        Remind about other_sports completeness.

        Note: This is a simple reminder. Full validation happens in API layer
        with access to actual activity data via analyze_profile_from_activities().
        """
        if not self.other_sports or len(self.other_sports) == 0:
            warnings.warn(
                "Profile has empty other_sports. If you have any regular non-running "
                "activities (climbing, cycling, yoga, etc.), add them for accurate load "
                "calculations. Run 'sce profile analyze' to see your sport distribution, "
                "then: sce profile add-sport --sport <name> --days <days> --duration <mins>",
                UserWarning
            )
        return self
