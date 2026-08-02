"""Contracts for baseline-assessment plans and benchmark evidence."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from resilio.schemas.approvals import ActivePlanState, PlanningState
from resilio.schemas.plan import BaselineAssessmentPlan
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.structured_workout import StructuredWorkout


def _assessment_plan_payload() -> dict[str, object]:
    return {
        "kind": "baseline_assessment",
        "id": "plan_august_assessment",
        "plan_revision_id": "plan_revision_0123456789abcdef",
        "planning_context_reference": {
            "artifact_type": "assessment_planning_context",
            "artifact_sha256": "a" * 64,
        },
        "planning_profile_sha256": "b" * 64,
        "created_at_utc": "2026-08-01T08:00:00Z",
        "planning_rationale": (
            "A gradual return follows the recorded running interruption before "
            "one athlete-approved five-kilometre benchmark."
        ),
        "adaptation_decisions": [
            {
                "decision_type": "starting_volume",
                "evidence_ids": ["recent_week.2026-07-27"],
                "observed_facts": (
                    "Synchronized evidence contains no recent running after the "
                    "recorded interruption in early June."
                ),
                "planning_change": (
                    "Use two progressive return weeks before the benchmark week."
                ),
                "affected_week_numbers": [1, 2, 3],
            },
            {
                "decision_type": "benchmark_scheduling",
                "evidence_ids": ["profile.current_constraints"],
                "observed_facts": (
                    "The athlete is unavailable from Friday through Monday for "
                    "a holiday and keeps bouldering flexible."
                ),
                "planning_change": (
                    "Prefer Thursday 20 August with a fallback from Tuesday 18 "
                    "through Thursday 20 August."
                ),
                "affected_week_numbers": [3],
            },
        ],
        "assessment_reasons": ["post_inactivity_baseline"],
        "benchmark_intent": {
            "race_distance": "5k",
            "preferred_date": "2026-08-20",
            "fallback_window_start": "2026-08-18",
            "fallback_window_end": "2026-08-20",
        },
        "weeks": [
            {
                "week_number": week_number,
                "phase": "base" if week_number < 3 else "assessment",
                "start_date": start_date,
                "end_date": end_date,
                "target_run_volume_meters": target_run_volume_meters,
                "workout_structure_hints": {
                    "quality": {
                        "maximum_sessions": 0 if week_number < 3 else 1,
                        "types": [] if week_number < 3 else ["benchmark"],
                    },
                    "long_run": None,
                    "intensity_distribution": None,
                },
                "workouts": [],
                "is_recovery_week": False,
            }
            for week_number, start_date, end_date, target_run_volume_meters in (
                (1, "2026-08-03", "2026-08-09", 8_000),
                (2, "2026-08-10", "2026-08-16", 11_000),
                (3, "2026-08-17", "2026-08-23", 12_000),
            )
        ],
        "constraints_snapshot": {
            "minimum_run_days_per_week": 2,
            "maximum_run_days_per_week": 3,
            "active_other_sports": [
                {
                    "sport_name": "climb",
                    "sessions_per_week": 3,
                    "typical_session_duration_seconds": 7_200,
                    "typical_intensity": "moderate",
                }
            ],
            "running_priority": "secondary",
            "primary_sport_name": "climb",
            "training_timezone": "Europe/Paris",
        },
        "conflict_policy": "ask_each_time",
        "medical_rehabilitation_excluded": True,
    }


def test_assessment_plan_has_no_vdot_or_methodology_dependency() -> None:
    plan = BaselineAssessmentPlan.model_validate(_assessment_plan_payload())

    assert plan.kind == "baseline_assessment"
    assert plan.benchmark_intent.preferred_date == date(2026, 8, 20)
    assert "vdot_approval_id" not in BaselineAssessmentPlan.model_fields
    assert "methodology" not in BaselineAssessmentPlan.model_fields

    state = PlanningState(active_plan=ActivePlanState(plan=plan))
    assert state.schema_version == 5
    assert state.active_vdot_approval is None


def test_long_assessment_requires_explicit_confirmation_and_rationale() -> None:
    payload = _assessment_plan_payload()
    payload["benchmark_intent"] = {
        "race_distance": "half_marathon",
        "preferred_date": "2026-08-20",
        "fallback_window_start": "2026-08-18",
        "fallback_window_end": "2026-08-20",
    }

    with pytest.raises(ValidationError, match="longer than 5k"):
        BaselineAssessmentPlan.model_validate(payload)


def test_date_only_timed_distance_benchmark_is_valid_but_has_no_intensity_target() -> None:
    workout = StructuredWorkout.model_validate(
        {
            "sport": "run",
            "steps": [
                {
                    "kind": "timed_distance",
                    "distance_meters": 5_000,
                    "nominal_seconds": 1_800,
                    "cue": "Run a controlled best sustainable effort.",
                }
            ],
        }
    )

    assert workout.nominal_duration_seconds() == 1_800
    assert workout.target_modes() == set()
    assert workout.timed_distance_steps()[0].distance_meters == 5_000


def test_workout_lineage_is_plan_kind_neutral() -> None:
    identity = PlanWorkoutIdentity(
        plan_id="plan_august_assessment",
        plan_revision_id="plan_revision_0123456789abcdef",
        week_number=3,
        local_workout_id="w_benchmark_5k",
    )

    assert identity.model_dump()["plan_revision_id"] == "plan_revision_0123456789abcdef"
    assert set(identity.model_dump()) == {
        "plan_id",
        "plan_revision_id",
        "week_number",
        "local_workout_id",
    }


def test_benchmark_window_must_contain_preferred_date_and_plan_horizon() -> None:
    payload = _assessment_plan_payload()
    payload["benchmark_intent"] = {
        "race_distance": "5k",
        "preferred_date": "2026-08-24",
        "fallback_window_start": "2026-08-18",
        "fallback_window_end": "2026-08-20",
    }

    with pytest.raises(ValidationError, match="preferred date"):
        BaselineAssessmentPlan.model_validate(payload)


def test_assessment_creation_timestamp_must_be_aware() -> None:
    payload = _assessment_plan_payload()
    payload["created_at_utc"] = datetime(2026, 8, 1, 8)

    with pytest.raises(ValidationError, match="timezone-aware"):
        BaselineAssessmentPlan.model_validate(payload)


def test_assessment_plan_preserves_temporary_athlete_unavailability() -> None:
    payload = _assessment_plan_payload()
    payload["temporary_schedule_constraints"] = [
        {
            "unavailable_start_date": "2026-08-21",
            "unavailable_end_date": "2026-08-24",
            "reason": "Athlete is away on holiday for the complete date range.",
            "athlete_confirmation_reference": (
                "Athlete confirmed on 2026-08-01 that 21-24 August is unavailable."
            ),
        }
    ]

    plan = BaselineAssessmentPlan.model_validate(payload)

    constraint = plan.temporary_schedule_constraints[0]
    assert constraint.unavailable_start_date == date(2026, 8, 21)
    assert constraint.unavailable_end_date == date(2026, 8, 24)


def test_benchmark_preferred_date_cannot_fall_in_temporary_unavailability() -> None:
    payload = _assessment_plan_payload()
    payload["temporary_schedule_constraints"] = [
        {
            "unavailable_start_date": "2026-08-20",
            "unavailable_end_date": "2026-08-24",
            "reason": "Athlete is away on holiday for the complete date range.",
            "athlete_confirmation_reference": (
                "Athlete confirmed on 2026-08-01 that 20-24 August is unavailable."
            ),
        }
    ]

    with pytest.raises(ValidationError, match="preferred date"):
        BaselineAssessmentPlan.model_validate(payload)


def test_benchmark_fallback_window_cannot_include_temporary_unavailability() -> None:
    payload = _assessment_plan_payload()
    payload["temporary_schedule_constraints"] = [
        {
            "unavailable_start_date": "2026-08-18",
            "unavailable_end_date": "2026-08-18",
            "reason": "The athlete is unavailable for the complete Tuesday date.",
            "athlete_confirmation_reference": (
                "Athlete confirmed on 2026-08-01 that 18 August is unavailable."
            ),
        }
    ]

    with pytest.raises(ValidationError, match="fallback window"):
        BaselineAssessmentPlan.model_validate(payload)


def test_assessment_skeleton_requires_one_executable_benchmark_week() -> None:
    payload = _assessment_plan_payload()
    benchmark_week = payload["weeks"][2]
    benchmark_week["workout_structure_hints"]["quality"] = {
        "maximum_sessions": 0,
        "types": [],
    }

    with pytest.raises(ValidationError, match="benchmark week"):
        BaselineAssessmentPlan.model_validate(payload)


def test_assessment_plan_can_temporarily_reduce_other_sport_commitments() -> None:
    payload = _assessment_plan_payload()
    payload["temporary_other_sport_commitment_overrides"] = [
        {
            "week_start_date": "2026-08-17",
            "sport_name": "climb",
            "sessions_per_week": 2,
            "reason": "The four-day holiday shortens the available assessment week.",
            "planning_rationale": (
                "Temporarily reduce climbing so the shortened assessment week "
                "does not cram sessions before the benchmark."
            ),
        }
    ]

    plan = BaselineAssessmentPlan.model_validate(payload)

    override = plan.temporary_other_sport_commitment_overrides[0]
    assert override.sessions_per_week == 2
    assert override.sport_name == "climb"
