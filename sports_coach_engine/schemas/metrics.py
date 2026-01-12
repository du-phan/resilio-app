"""
Metrics schemas - Training metrics data models.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import date


class DailyMetrics(BaseModel):
    """Daily training metrics."""
    date: date
    systemic_daily_load_au: float
    lower_body_daily_load_au: float
    ctl: float
    atl: float
    tsb: float
    acwr: Optional[float] = None


class MetricInterpretation(BaseModel):
    """A metric value with interpretive context."""
    value: float
    formatted_value: str
    zone: str
    interpretation: str
    trend: Optional[str] = None


class EnrichedMetrics(BaseModel):
    """Metrics with enriched context."""
    date: date
    ctl: MetricInterpretation
    atl: MetricInterpretation
    tsb: MetricInterpretation
    acwr: Optional[MetricInterpretation] = None
    readiness: MetricInterpretation


class ReadinessScore(BaseModel):
    """Readiness score with breakdown."""
    score: int
    level: str
    components: dict
    recommendation: str


class TrainingStatus(BaseModel):
    """Current training status."""
    fitness: MetricInterpretation
    fatigue: MetricInterpretation
    form: MetricInterpretation
    acwr: Optional[MetricInterpretation] = None
    readiness: MetricInterpretation


class WeeklyStatus(BaseModel):
    """Weekly status overview."""
    week_number: int
    phase: str
    days: list
    progress: dict
    load_summary: dict
    metrics: EnrichedMetrics
