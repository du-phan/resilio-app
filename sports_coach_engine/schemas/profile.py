"""
Profile schemas - Athlete profile data models.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from enum import Enum


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


class TimePreference(str, Enum):
    """Preferred time of day for training."""

    MORNING = "morning"
    EVENING = "evening"
    FLEXIBLE = "flexible"


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
    lthr: Optional[int] = Field(
        default=None, ge=100, le=200
    )  # Lactate threshold heart rate


class Goal(BaseModel):
    """Training goal."""

    type: GoalType
    race_name: Optional[str] = None
    target_date: Optional[str] = None  # ISO date string
    target_time: Optional[str] = None  # HH:MM:SS format
    effort_level: Optional[str] = None  # pr_attempt, comfortable, just_finish


class TrainingConstraints(BaseModel):
    """Training constraints and availability."""

    available_run_days: List[Weekday]
    preferred_run_days: Optional[List[Weekday]] = None
    min_run_days_per_week: int = Field(ge=0, le=7)
    max_run_days_per_week: int = Field(ge=0, le=7)
    max_time_per_session_minutes: Optional[int] = Field(default=90, ge=0)
    time_preference: TimePreference = TimePreference.FLEXIBLE


class OtherSport(BaseModel):
    """Other sport commitment."""

    sport: str
    days: List[Weekday]
    typical_duration_minutes: int = Field(ge=0)
    typical_intensity: str  # easy, moderate, hard, moderate_to_hard
    is_fixed: bool = True
    notes: Optional[str] = None


class CommunicationPreferences(BaseModel):
    """Communication and coaching preferences."""

    detail_level: DetailLevel = DetailLevel.MODERATE
    coaching_style: CoachingStyle = CoachingStyle.SUPPORTIVE
    intensity_metric: IntensityMetric = IntensityMetric.PACE


class StravaConnection(BaseModel):
    """Strava connection info."""

    athlete_id: str


class RecentRace(BaseModel):
    """Recent race result for fitness estimation."""

    distance: str  # 5k, 10k, half_marathon, marathon
    time: str  # HH:MM:SS format
    date: str  # ISO date string


class AthleteProfile(BaseModel):
    """Complete athlete profile."""

    # Basic Info
    name: str
    email: Optional[str] = None
    created_at: str  # ISO date string
    age: Optional[int] = Field(default=None, ge=0, le=120)

    # Vital Signs
    vital_signs: Optional[VitalSigns] = None

    # Strava Connection
    strava: Optional[StravaConnection] = None

    # Running Background
    running_experience_years: Optional[int] = Field(default=None, ge=0)
    injury_history: Optional[str] = None

    # Recent Fitness Snapshot
    recent_race: Optional[RecentRace] = None
    current_weekly_run_km: Optional[float] = Field(default=None, ge=0)
    current_run_days_per_week: Optional[int] = Field(default=None, ge=0, le=7)

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
