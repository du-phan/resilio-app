"""Presentation-neutral VDOT calculations owned by Resilio."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from resilio.core.local_dates import athlete_local_date
from resilio.core.locking import OperationLockError
from resilio.core.planning.approval_evidence import (
    ApprovalEvidenceError,
    load_vdot_approval_evidence_unlocked,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.state_repository import (
    load_planning_aggregate_unlocked,
)
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.core.vdot import (
    VDOTCalculationRangeError,
    calculate_race_equivalents,
    calculate_vdot,
    parse_time_string,
)
from resilio.schemas.approvals import (
    PerformanceVDOTEvidence,
    PlanningState,
    VDOTApproval,
    VDOTProposal,
)
from resilio.schemas.profile import AthleteProfile
from resilio.schemas.vdot import (
    RaceDistance,
    RaceEquivalents,
    VDOTEstimate,
    VDOTResult,
)


@dataclass(frozen=True)
class VDOTError:
    """A typed VDOT operation failure."""

    error_type: str
    message: str


def _race_distance(value: str) -> RaceDistance | VDOTError:
    try:
        return RaceDistance(value.casefold())
    except ValueError:
        valid = ", ".join(item.value for item in RaceDistance)
        return VDOTError("invalid_input", f"Invalid race distance {value!r}. Valid: {valid}")


def _time_seconds(value: str, *, label: str) -> int | VDOTError:
    try:
        return parse_time_string(value)
    except ValueError as exc:
        return VDOTError("invalid_input", f"Invalid {label} {value!r}: {exc}")


def calculate_vdot_from_race(
    race_distance: str,
    race_time: str,
    race_date: str | None = None,
    *,
    as_of_date: date | None = None,
) -> VDOTResult | VDOTError:
    """Calculate VDOT from a measured race performance."""
    distance = _race_distance(race_distance)
    if isinstance(distance, VDOTError):
        return distance
    time_seconds = _time_seconds(race_time, label="race time")
    if isinstance(time_seconds, VDOTError):
        return time_seconds

    try:
        result = calculate_vdot(distance, time_seconds)
    except VDOTCalculationRangeError as exc:
        return VDOTError("out_of_range", str(exc))
    except ValueError as exc:
        return VDOTError("calculation_failed", f"VDOT calculation failed: {exc}")

    if race_date is not None:
        if as_of_date is None:
            return VDOTError(
                "invalid_input",
                "as_of_date is required when race_date is supplied",
            )
        try:
            performance_date = date.fromisoformat(race_date)
            days_old = (as_of_date - performance_date).days
        except ValueError:
            return VDOTError("invalid_input", "race_date must use YYYY-MM-DD")
        if days_old < 0:
            return VDOTError("invalid_input", "race_date cannot be in the future")
        result = result.model_copy(
            update={
                "performance_date": performance_date,
                "performance_age_days": days_old,
            }
        )
    return result


def predict_race_times(
    race_distance: str,
    race_time: str,
) -> RaceEquivalents | VDOTError:
    """Calculate equivalent race performances from one measured result."""
    distance = _race_distance(race_distance)
    if isinstance(distance, VDOTError):
        return distance
    time_seconds = _time_seconds(race_time, label="race time")
    if isinstance(time_seconds, VDOTError):
        return time_seconds
    try:
        return calculate_race_equivalents(distance, time_seconds)
    except ValueError as exc:
        return VDOTError("calculation_failed", f"Race prediction failed: {exc}")


def _load_profile_unlocked(repo: RepositoryIO) -> AthleteProfile | None:
    return ProfileRepository(repo)._load_unlocked(allow_missing=True)


def _load_planning_state_unlocked(
    repo: RepositoryIO,
) -> PlanningState | None:
    return load_planning_aggregate_unlocked(repo, allow_missing=True)


def _estimate_from_approval(
    *,
    approval: VDOTApproval,
    proposal: VDOTProposal,
    profile: AthleteProfile,
    as_of_date: date,
) -> VDOTEstimate | VDOTError:
    evidence_date = (
        proposal.evidence.performance_date
        if isinstance(proposal.evidence, PerformanceVDOTEvidence)
        else approval.approved_at_utc.astimezone(
            ZoneInfo(profile.training_timezone)
        ).date()
    )
    evidence_age_days = (as_of_date - evidence_date).days
    if evidence_age_days < 0:
        return VDOTError(
            "invalid_input",
            "Approved VDOT evidence cannot be dated in the future.",
        )
    return VDOTEstimate(
        estimated_vdot=approval.approved_vdot,
        evidence_type=proposal.evidence_type,
        evidence_date=evidence_date,
        evidence_age_days=evidence_age_days,
        athlete_approved=True,
        applicability_window_days=None,
        source=f"athlete_approved_vdot_proposal:{approval.approval_id}",
    )


def _estimate_from_personal_best(
    *,
    profile: AthleteProfile,
    lookback_days: int,
    as_of_date: date,
) -> VDOTEstimate | VDOTError:
    dated_personal_bests = list(
        profile.personal_bests_by_distance.items()
    )
    if not dated_personal_bests:
        return VDOTError(
            "not_found",
            "No approved VDOT or dated race performance is available.",
        )
    distance_name, personal_best = max(
        dated_personal_bests,
        key=lambda item: item[1].performance_date,
    )
    performance_date = personal_best.performance_date
    days_old = (as_of_date - performance_date).days
    if days_old < 0:
        return VDOTError(
            "invalid_input",
            "Personal-best dates cannot be in the future",
        )
    if days_old > lookback_days:
        return VDOTError(
            "not_found",
            f"Most recent race evidence is {days_old} days old; "
            f"the requested lookback is {lookback_days} days.",
        )
    return VDOTEstimate(
        estimated_vdot=round(personal_best.vdot),
        evidence_type="personal_best",
        evidence_date=performance_date,
        evidence_age_days=days_old,
        athlete_approved=False,
        applicability_window_days=lookback_days,
        source=(
            f"recent_personal_best:{distance_name}:"
            f"{performance_date.isoformat()}"
        ),
    )


def estimate_current_vdot(
    lookback_days: int = 28,
    *,
    as_of_date: date | None = None,
) -> VDOTEstimate | VDOTError:
    """Return approved or race-derived VDOT evidence without inferred decay.

    The lookback argument defines how recent a personal best must be to count as
    current evidence. Older performances are deliberately not decayed or
    converted into a current-fitness claim.
    """
    if lookback_days <= 0:
        return VDOTError("invalid_input", "lookback_days must be positive")
    repository = RepositoryIO()
    try:
        with coordinated_plan_lock(
            repository,
            "estimate_current_vdot",
        ):
            profile = _load_profile_unlocked(repository)
            if profile is None:
                return VDOTError(
                    "not_found",
                    "Athlete profile does not exist",
                )
            planning_state = _load_planning_state_unlocked(repository)
            resolved_as_of_date = as_of_date or athlete_local_date(
                profile.training_timezone
            )
            if (
                planning_state is not None
                and planning_state.vdot_approval is not None
            ):
                approval, proposal = (
                    load_vdot_approval_evidence_unlocked(
                        repository,
                        planning_state.vdot_approval,
                    )
                )
                return _estimate_from_approval(
                    approval=approval,
                    proposal=proposal,
                    profile=profile,
                    as_of_date=resolved_as_of_date,
                )
            return _estimate_from_personal_best(
                profile=profile,
                lookback_days=lookback_days,
                as_of_date=resolved_as_of_date,
            )
    except ApprovalEvidenceError as exc:
        return VDOTError("stale_approval_evidence", str(exc))
    except OperationLockError:
        return VDOTError(
            "temporarily_unavailable",
            "VDOT evidence is temporarily unavailable during a state transition",
        )
    except (OSError, ValueError, PlanOperationError) as exc:
        return VDOTError("invalid_state", str(exc))
