"""
Plan schemas - Training plan data models.
"""

from pydantic import BaseModel
from typing import List, Optional
from datetime import date


class TrainingPlan(BaseModel):
    """Complete training plan."""
    goal: "Goal"
    total_weeks: int
    current_week: int
    phase: str
    weeks: List[dict]
    constraints_applied: dict


class PlanPhase(BaseModel):
    """Training phase."""
    name: str
    start_week: int
    end_week: int
    focus: str
