"""
Approval state schemas for progressive disclosure workflows.
"""

from typing import Optional
from pydantic import BaseModel, Field


class WeeklyApproval(BaseModel):
    """Approval record for a single week's plan."""

    week_number: int = Field(..., ge=1, description="Approved week number")
    approved_at: str = Field(..., description="ISO timestamp of approval")
    approved_file: str = Field(..., description="Path to approved weekly JSON payload")


class ApprovalState(BaseModel):
    """Approval state persisted between skills."""

    approved_baseline_vdot: Optional[float] = Field(
        default=None,
        ge=30,
        le=85,
        description="Approved baseline VDOT"
    )
    vdot_approval_ts: Optional[str] = Field(
        default=None,
        description="ISO timestamp of baseline VDOT approval"
    )
    macro_approved: bool = Field(default=False, description="Macro plan approved")
    macro_approval_ts: Optional[str] = Field(
        default=None,
        description="ISO timestamp of macro approval"
    )
    weekly_approval: Optional[WeeklyApproval] = Field(
        default=None,
        description="Most recent weekly approval"
    )
