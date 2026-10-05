"""Canonical candidate identities and factual progression comparisons."""

from datetime import date, timedelta
from typing import Literal, TypeAlias

from resilio.canonical import canonical_data_sha256
from resilio.core.coaching_context.running_progression import (
    comparison_window,
    distance_change_percent,
)
from resilio.schemas.macro_plan_draft import MacroPlanDraft
from resilio.schemas.methodology import MethodologyChoice
from resilio.schemas.planning.amendments import MacroAmendmentProposal
from resilio.schemas.planning.applications import WeekApplication
from resilio.schemas.planning.constraints import PlanningConstraintsSnapshot
from resilio.schemas.planning.plans import RaceMacroPlan
from resilio.schemas.planning.weeks import WeekPlan
from resilio.schemas.running_progression import (
    ProgressionAssessmentV1,
    RunningProgressionEvidenceV1,
    SessionProgressionComparison,
    WeekProgressionComparison,
)

ProgressionKind = Literal["macro", "amendment", "week"]
ProgressionCandidate: TypeAlias = MacroPlanDraft | MacroAmendmentProposal | WeekApplication


def macro_draft_from_plan(plan: RaceMacroPlan) -> MacroPlanDraft:
    return MacroPlanDraft(
        goal=plan.goal,
        methodology=MethodologyChoice(
            identifier=plan.methodology.identifier,
            selection_rationale=plan.methodology.selection_rationale,
        ),
        weeks=plan.weeks,
        vdot_approval_id=plan.vdot_approval_id,
        planning_context_reference=plan.planning_context_reference,
        planning_rationale=plan.planning_rationale,
        adaptation_decisions=plan.adaptation_decisions,
    )


def candidate_sha256(candidate: ProgressionCandidate) -> str:
    """Full semantic proposal, excluding only context references to avoid a hash cycle."""
    payload = candidate.model_dump(mode="json")
    payload.pop("planning_context_reference", None)
    payload.pop("planning_context_references", None)
    return canonical_data_sha256(payload)


def _session_comparison(
    evidence: RunningProgressionEvidenceV1,
    *,
    key: str,
    week: WeekPlan,
    candidate_date: date | None,
    distance_meters: float | None,
    nominal_duration_seconds: int | None,
) -> SessionProgressionComparison:
    if candidate_date is None:
        end = evidence.as_of_date
        start, observed_end = end - timedelta(days=29), end
    else:
        start, end, observed_end = comparison_window(candidate_date, evidence.as_of_date)
    sessions = [item for item in evidence.sessions if start <= item.local_date <= observed_end]
    known_distances = [item for item in sessions if item.distance_meters is not None]
    longest_distance = max(
        known_distances, key=lambda item: item.distance_meters or 0, default=None
    )
    longest_moving = max(sessions, key=lambda item: item.moving_duration_seconds, default=None)
    longest_elapsed = max(sessions, key=lambda item: item.elapsed_duration_seconds, default=None)
    baseline = longest_distance.distance_meters if longest_distance else None
    return SessionProgressionComparison(
        key=key,
        week_number=week.week_number,
        candidate_date=candidate_date,
        candidate_distance_meters=distance_meters,
        nominal_duration_seconds=nominal_duration_seconds,
        comparator_start_date=start,
        comparator_end_date=end,
        observed_comparator_end_date=observed_end,
        longest_distance_activity_ids=longest_distance.activity_ids if longest_distance else [],
        longest_recorded_distance_meters=baseline,
        longest_moving_duration_activity_ids=longest_moving.activity_ids if longest_moving else [],
        longest_recorded_moving_duration_seconds=(
            longest_moving.moving_duration_seconds if longest_moving else None
        ),
        longest_elapsed_duration_activity_ids=longest_elapsed.activity_ids
        if longest_elapsed
        else [],
        longest_recorded_elapsed_duration_seconds=(
            longest_elapsed.elapsed_duration_seconds if longest_elapsed else None
        ),
        distance_change_percent=distance_change_percent(distance_meters, baseline),
        weekly_distance_share_percent=(
            100 * distance_meters / week.target_run_volume_meters
            if distance_meters is not None and week.target_run_volume_meters > 0
            else None
        ),
    )


def build_progression_assessment(
    candidate: ProgressionCandidate,
    *,
    kind: ProgressionKind,
    evidence: RunningProgressionEvidenceV1,
    target_week: WeekPlan | None = None,
    constraints: PlanningConstraintsSnapshot,
) -> ProgressionAssessmentV1:
    if isinstance(candidate, WeekApplication):
        if target_week is None:
            raise ValueError("Exact weekly assessment requires its approved target week")
        weeks = [target_week.model_copy(update={"running_workouts": candidate.running_workouts})]
    else:
        weeks = candidate.weeks
    comparisons = []
    sessions = []
    for week in weeks:
        workouts = week.running_workouts
        known_distances = [item.planned_distance_meters for item in workouts]
        largest_distance = max(
            (value for value in known_distances if value is not None), default=None
        )
        hints = week.workout_structure_hints.long_run
        long_distance = (
            largest_distance if workouts else (hints.target_distance_meters if hints else None)
        )
        comparisons.append(
            WeekProgressionComparison(
                week_number=week.week_number,
                target_distance_meters=week.target_run_volume_meters,
                intended_running_day_count=len({item.date for item in workouts})
                if workouts
                else None,
                nominal_duration_seconds=sum(item.planned_duration_seconds for item in workouts)
                if workouts
                else None,
                moderate_intensity_duration_seconds=sum(
                    item.planned_moderate_intensity_duration_seconds for item in workouts
                )
                if workouts
                else None,
                high_intensity_duration_seconds=sum(
                    item.planned_high_intensity_duration_seconds for item in workouts
                )
                if workouts
                else None,
                supporting_distance_meters=(
                    week.target_run_volume_meters - long_distance
                    if long_distance is not None
                    else None
                ),
            )
        )
        if workouts:
            for workout in workouts:
                sessions.append(
                    _session_comparison(
                        evidence,
                        key=f"workout.{workout.id}",
                        week=week,
                        candidate_date=workout.date,
                        distance_meters=workout.planned_distance_meters,
                        nominal_duration_seconds=workout.planned_duration_seconds,
                    )
                )
        else:
            sessions.append(
                _session_comparison(
                    evidence,
                    key=f"long_target.{week.week_number}",
                    week=week,
                    candidate_date=None,
                    distance_meters=long_distance,
                    nominal_duration_seconds=None,
                )
            )
    return ProgressionAssessmentV1(
        kind=kind,
        minimum_run_days_per_week=constraints.minimum_run_days_per_week,
        maximum_run_days_per_week=constraints.maximum_run_days_per_week,
        candidate_sha256=candidate_sha256(candidate),
        evidence_sha256=canonical_data_sha256(evidence),
        evidence=evidence,
        weeks=comparisons,
        sessions=sessions,
    )
