"""Planning-history v4 contract tests."""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    import_evidence_artifact,
    load_evidence_artifact,
)
from resilio.core.planning.cycle_review import confirmed_goal_outcome
from resilio.core.planning.errors import PlanOperationError
from resilio.core.repository import RepositoryIO
from resilio.schemas.plan_history import (
    GoalOutcome,
    GoalOutcomeUnavailableEvidence,
    PlanClosure,
    PlanClosureDisposition,
    PlanWorkoutIdentity,
)
from resilio.schemas.planning_evidence import (
    MacroPlanningContext,
    PlanningEvidencePointer,
)
from tests.factories import make_activity


@pytest.fixture
def repo(tmp_path, monkeypatch: pytest.MonkeyPatch) -> RepositoryIO:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return RepositoryIO()


def test_plan_workout_identity_is_fully_qualified() -> None:
    identity = PlanWorkoutIdentity(
        plan_id="plan_renewal",
        macro_revision_id="macro_revision_1111111111111111",
        week_number=3,
        local_workout_id="workout_11111111111111111111111111111111",
    )

    assert identity.plan_id == "plan_renewal"
    assert identity.week_number == 3


def test_new_closure_cannot_silently_leave_race_outcome_unknown() -> None:
    with pytest.raises(ValidationError, match="unverified"):
        PlanClosure(
            disposition=PlanClosureDisposition.COMPLETED_HORIZON,
            effective_end_date=date(2026, 7, 26),
            reason="The planned horizon ended and the athlete requested a new cycle.",
            athlete_confirmation_reference="Athlete requested the replacement in conversation.",
            cycle_review_artifact_sha256="a" * 64,
            goal_outcome=GoalOutcome(
                status="unverified",
                evidence=GoalOutcomeUnavailableEvidence(
                    reason="No canonical race activity was confirmed."
                ),
            ),
            closed_at_utc=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )


def test_general_fitness_closure_accepts_not_applicable_goal_outcome() -> None:
    closure = PlanClosure(
        disposition=PlanClosureDisposition.COMPLETED_HORIZON,
        effective_end_date=date(2026, 7, 26),
        reason="The general-fitness cycle reached its planned end date.",
        athlete_confirmation_reference="Athlete requested the next general-fitness cycle.",
        cycle_review_artifact_sha256="a" * 64,
        goal_outcome=GoalOutcome(
            status="not_applicable",
            athlete_confirmation_reference=(
                "Athlete confirmed that this goal has no target race outcome."
            ),
        ),
        closed_at_utc=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )

    assert closure.goal_outcome.status == "not_applicable"


def test_evidence_artifact_is_content_addressed_and_immutable(
    repo: RepositoryIO,
) -> None:
    outcome = GoalOutcome(
        status="not_applicable",
        athlete_confirmation_reference=(
            "Athlete confirmed that this goal has no target race outcome."
        ),
    )

    reference = import_evidence_artifact(
        repo,
        outcome,
        artifact_type="cycle_review",
    )

    assert load_evidence_artifact(repo, reference, GoalOutcome) == outcome
    artifact_path = repo.resolve_path(
        "data/plans/evidence/cycle_review/" f"{reference.artifact_sha256}.json"
    )
    artifact_path.write_text('{"status":"completed"}\n')
    with pytest.raises(PlanningArtifactError, match="invalid|changed"):
        load_evidence_artifact(repo, reference, GoalOutcome)


def test_macro_context_requires_start_after_evidence_and_unique_evidence_ids() -> None:
    payload = {
        "evidence_as_of_date": "2026-07-26",
        "intended_plan_start_date": "2026-07-27",
        "generated_at_utc": "2026-07-26T20:00:00Z",
        "planning_profile_sha256": "a" * 64,
        "current_goal": {
            "type": "general_fitness",
            "target_date": "2026-10-04",
        },
        "current_constraints": {
            "unavailable_run_days": [],
            "minimum_run_days_per_week": 3,
            "maximum_run_days_per_week": 5,
            "active_other_sports": [],
            "running_priority": "primary",
            "training_timezone": "Europe/Paris",
        },
        "active_vdot_approval_id": "vdot_approval_1111111111111111",
        "historical_plan_summaries": [],
        "historical_compact_weeks": [],
        "recent_detailed_weeks": [],
        "evidence_index": [
            {
                "evidence_id": "profile.current_constraints",
                "category": "profile",
                "description": "Athlete-confirmed current planning constraints.",
            },
            {
                "evidence_id": "vdot.active_approval",
                "category": "vdot",
                "description": "The exact currently approved VDOT evidence.",
            },
        ],
        "source_context_sha256": "b" * 64,
        "source_state_sha256": "c" * 64,
    }
    context = MacroPlanningContext.model_validate(payload)
    assert context.intended_plan_start_date.weekday() == 0

    payload["intended_plan_start_date"] = "2026-07-20"
    with pytest.raises(ValueError, match="after the evidence"):
        MacroPlanningContext.model_validate(payload)

    pointer = PlanningEvidencePointer(
        evidence_id="profile.current_constraints",
        category="profile",
        description="Athlete-confirmed current planning constraints.",
    )
    with pytest.raises(ValueError, match="unique"):
        MacroPlanningContext.model_validate(
            {
                **payload,
                "intended_plan_start_date": "2026-07-27",
                "evidence_index": [
                    pointer,
                    pointer,
                ],
            }
        )


def test_confirmed_goal_outcome_never_guesses_an_activity(
    repo: RepositoryIO,
) -> None:
    outcome = confirmed_goal_outcome(
        repo,
        status="did_not_start",
        local_activity_id=None,
        athlete_confirmation_reference=(
            "Athlete confirmed that they did not start the target event."
        ),
    )
    assert outcome.status == "did_not_start"

    with pytest.raises(PlanOperationError, match="canonical activity"):
        confirmed_goal_outcome(
            repo,
            status="completed",
            local_activity_id="act_i_missing",
            athlete_confirmation_reference=(
                "Athlete identified this exact canonical activity as the goal."
            ),
        )


def test_did_not_finish_outcome_can_retain_exact_partial_race_activity(
    repo: RepositoryIO,
) -> None:
    activity = make_activity(
        id="goal-race-dnf",
        date=date(2026, 7, 26),
        sport="run",
        distance_meters=7_400,
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)

    outcome = confirmed_goal_outcome(
        repo,
        status="did_not_finish",
        local_activity_id=activity.local_activity_id,
        athlete_confirmation_reference=(
            "Athlete confirmed this recording is the partial target-race effort."
        ),
    )

    assert outcome.status == "did_not_finish"
    assert outcome.evidence is not None
    assert outcome.evidence.local_activity_id == activity.local_activity_id
