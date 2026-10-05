"""Presentation-neutral exact-file macro amendment operations."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from resilio.api.plan import PlanError
from resilio.core.planning.amendments import apply_macro_amendment, validate_macro_amendment
from resilio.core.planning.errors import PlanOperationError
from resilio.core.repository import RepositoryIO
from resilio.schemas.planning.amendments import MacroAmendmentValidation


class AppliedMacroAmendmentResult(BaseModel):
    amendment_id: str
    plan_id: str
    plan_revision_id: str
    amended_week_numbers: list[int]
    local_application_status: str = "applied"
    workout_synchronization_status: str = "requires_weekly_approval_and_application"

    model_config = ConfigDict(extra="forbid")


def validate_macro_amendment_file(path: Path) -> MacroAmendmentValidation | PlanError:
    try:
        return validate_macro_amendment(RepositoryIO(), path.expanduser().resolve())
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))


def apply_macro_amendment_file(
    path: Path,
    *,
    expected_file_sha256: str,
    athlete_confirmation_reference: str,
) -> AppliedMacroAmendmentResult | PlanError:
    try:
        state = apply_macro_amendment(
            RepositoryIO(),
            path,
            expected_file_sha256=expected_file_sha256,
            athlete_confirmation_reference=athlete_confirmation_reference,
        )
        assert state.active_plan is not None
        audit = state.active_plan.macro_amendments[-1]
        return AppliedMacroAmendmentResult(
            amendment_id=audit.amendment_id,
            plan_id=state.active_plan.plan.id,
            plan_revision_id=state.active_plan.plan.plan_revision_id,
            amended_week_numbers=audit.affected_week_numbers,
        )
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))
