"""
Workout schemas - Workout prescription data models.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import date


class WorkoutPrescription(BaseModel):
    """Workout prescription."""
    workout_id: str
    date: date
    workout_type: str
    duration_minutes: int
    target_rpe: int


class WorkoutRationale(BaseModel):
    """Explanation for workout prescription."""
    primary_reason: str
    training_purpose: str
    phase_context: Optional[str] = None
    safety_notes: List[str] = []


class WorkoutRecommendation(BaseModel):
    """Workout with full context."""
    workout: WorkoutPrescription
    rationale: WorkoutRationale
    metrics_context: "EnrichedMetrics"
    pending_suggestions: List = []
    warnings: List[str] = []
