"""
Activity schemas - Activity data models.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import date


class Activity(BaseModel):
    """Base activity model."""
    id: str
    source: str
    sport_type: str
    date: date
    duration_minutes: int
    distance_km: Optional[float] = None


class NormalizedActivity(Activity):
    """Activity after normalization."""
    pass


class ProcessedActivity(BaseModel):
    """Activity after full processing pipeline."""
    pass
