"""
Profile schemas - Athlete profile data models.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import date


class Goal(BaseModel):
    """Training goal."""
    type: str
    target_date: date
    target_time: Optional[str] = None


class Constraints(BaseModel):
    """Training constraints."""
    available_run_days: List[str]
    min_run_days_per_week: int
    max_run_days_per_week: int


class AthleteProfile(BaseModel):
    """Complete athlete profile."""
    name: str
    created_at: date
    running_priority: str
    primary_sport: str
    conflict_policy: str
    constraints: Constraints
    goal: Goal
