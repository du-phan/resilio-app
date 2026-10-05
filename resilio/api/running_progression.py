"""Presentation-neutral progression authoring operations."""

from pathlib import Path

from resilio.api.plan import PlanError
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.progression_assessment import ProgressionKind
from resilio.core.planning.progression_authoring import assess_progression, bind_progression_review
from resilio.core.repository import RepositoryIO
from resilio.schemas.running_progression import ProgressionAssessmentV1


def assess_running_progression(
    path: Path, *, kind: ProgressionKind
) -> ProgressionAssessmentV1 | PlanError:
    try:
        return assess_progression(RepositoryIO(), path, kind=kind)
    except (OSError, ValueError, PlanOperationError) as exc:
        return PlanError("validation", str(exc))


def bind_running_progression_review(
    path: Path,
    review_path: Path,
    output_path: Path,
    *,
    kind: ProgressionKind,
) -> dict[str, object] | PlanError:
    try:
        return bind_progression_review(RepositoryIO(), path, review_path, output_path, kind=kind)
    except (OSError, ValueError, PlanOperationError) as exc:
        return PlanError("validation", str(exc))
