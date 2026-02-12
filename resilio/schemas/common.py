"""
Common schemas used across multiple modules.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SchemaType(str, Enum):
    """Types of data schemas in the system."""
    ACTIVITY = "activity"
    PROFILE = "profile"
    DAILY_METRICS = "daily_metrics"
    WEEKLY_SUMMARY = "weekly_summary"
    PLAN = "plan"
    WORKOUT = "workout"
    MEMORIES = "memories"
    TRAINING_HISTORY = "training_history"
    PENDING_SUGGESTIONS = "pending_suggestions"
    SETTINGS = "settings"


class SchemaHeader(BaseModel):
    """Schema version header present in all data files."""
    format_version: str = "1.0.0"
    schema_type: SchemaType


class MetricZone(str, Enum):
    """Classification zones for training metrics."""
    # CTL zones
    BEGINNER = "beginner"
    DEVELOPING = "developing"
    RECREATIONAL = "recreational"
    TRAINED = "trained"
    COMPETITIVE = "competitive"
    ELITE = "elite"

    # TSB zones
    OVERREACHED = "overreached"
    PRODUCTIVE = "productive"
    OPTIMAL = "optimal"
    FRESH = "fresh"
    RACE_READY = "race_ready"
    DETRAINING_RISK = "detraining_risk"

    # ACWR zones
    UNDERTRAINED = "undertrained"
    SAFE = "safe"
    CAUTION = "caution"
    HIGH_RISK = "high_risk"

    # Readiness zones
    REST_RECOMMENDED = "rest_recommended"
    EASY_ONLY = "easy_only"
    READY = "ready"
    PRIMED = "primed"


class SportType(str, Enum):
    """Normalized sport types."""
    RUNNING_ROAD = "running_road"
    RUNNING_TREADMILL = "running_treadmill"
    RUNNING_TRAIL = "running_trail"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    CLIMBING = "climbing"
    STRENGTH = "strength"
    HIKING = "hiking"
    CROSSFIT = "crossfit"
    YOGA_FLOW = "yoga_flow"
    YOGA_RESTORATIVE = "yoga_restorative"
    OTHER = "other"


class ConflictPolicy(str, Enum):
    """How to handle conflicts between running and primary sport."""
    PRIMARY_SPORT_WINS = "primary_sport_wins"
    RUNNING_GOAL_WINS = "running_goal_wins"
    ASK_EACH_TIME = "ask_each_time"


class RunningPriority(str, Enum):
    """Priority level for running relative to other sports."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    EQUAL = "equal"


class GoalType(str, Enum):
    """Training goal types."""
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"
    GENERAL_FITNESS = "general_fitness"
