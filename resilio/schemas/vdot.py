"""VDOT race-performance and approved-evidence contracts."""

from datetime import date
from enum import Enum
from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# ENUMS
# ============================================================


class RaceDistance(str, Enum):
    """Supported race distances for VDOT calculation."""

    MILE = "mile"
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"


# ============================================================
# CORE VDOT MODELS
# ============================================================


class VDOTResult(BaseModel):
    """Result of VDOT calculation from race performance."""

    vdot: int = Field(..., ge=30, le=85, description="VDOT value (fitness level)")
    vdot_raw: float = Field(
        ...,
        ge=30,
        le=85,
        allow_inf_nan=False,
        description="Unrounded Daniels–Gilbert VDOT",
    )
    source_race: RaceDistance = Field(
        ...,
        description="Race distance used for calculation",
    )
    source_time_seconds: int = Field(..., gt=0, description="Race time in seconds")
    source_time_formatted: str = Field(
        ...,
        description="Race time formatted as MM:SS or HH:MM:SS",
    )
    performance_date: date | None = None
    performance_age_days: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class RaceEquivalents(BaseModel):
    """Predicted race times for other distances based on VDOT."""

    vdot: int = Field(..., ge=30, le=85)
    vdot_raw: float = Field(..., ge=30, le=85, allow_inf_nan=False)
    source_race: RaceDistance
    source_time_formatted: str

    # Predicted times for each distance (formatted as HH:MM:SS or MM:SS)
    predictions: Dict[RaceDistance, str] = Field(..., description="Predicted race times")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class VDOTEstimate(BaseModel):
    """Approved or recent-race VDOT evidence."""

    estimated_vdot: int = Field(..., ge=30, le=85, description="Estimated current VDOT")
    evidence_type: str
    evidence_date: date | None = None
    evidence_age_days: int | None = Field(default=None, ge=0)
    athlete_approved: bool
    applicability_window_days: int | None = Field(default=None, gt=0)
    source: str = Field(..., description="Exact evidence source")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )
