"""Presentation-neutral API wiring for workout fulfillment lifecycle actions."""

import resilio.api as stable_api
from resilio.api import workout_fulfillment as fulfillment_api
from resilio.core.workout_fulfillment.service import WorkoutFulfillmentError


def test_fulfillment_api_routes_every_lifecycle_action(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeService:
        def __init__(self, _repo) -> None:
            pass

        def candidates(self, **kwargs):
            calls.append(("candidates", kwargs))
            return ["candidate"]

        def confirm(self, **kwargs):
            calls.append(("confirm", kwargs))
            return "confirmed"

        def dismiss_candidate(self, **kwargs):
            calls.append(("dismiss", kwargs))
            return "dismissed"

        def revoke(self, **kwargs):
            calls.append(("revoke", kwargs))
            return "revoked"

        def week_status(self, **kwargs):
            calls.append(("status", kwargs))
            return "status"

    monkeypatch.setattr(fulfillment_api, "WorkoutFulfillmentService", FakeService)

    assert fulfillment_api.get_workout_fulfillment_candidates(local_activity_id="act-1") == [
        "candidate"
    ]
    assert (
        fulfillment_api.confirm_workout_fulfillment(
            local_activity_id="act-1",
            local_workout_id="run-1",
            candidate_sha256="a" * 64,
            athlete_confirmation_reference="Athlete confirmed.",
            coaching_rationale="The exact evidence supports this association.",
        )
        == "confirmed"
    )
    assert (
        fulfillment_api.dismiss_workout_fulfillment_candidate(
            local_activity_id="act-1",
            local_workout_id="run-1",
            candidate_sha256="a" * 64,
            athlete_response_reference="Athlete rejected this association.",
        )
        == "dismissed"
    )
    assert (
        fulfillment_api.revoke_workout_fulfillment(
            local_activity_id="act-1",
            local_workout_id="run-1",
            reason="association_incorrect",
            athlete_confirmation_reference="Athlete withdrew this association.",
            coaching_rationale="The synchronized evidence contradicts the association.",
        )
        == "revoked"
    )
    assert fulfillment_api.get_workout_fulfillment_week_status(week_number=2) == "status"
    assert [name for name, _ in calls] == [
        "candidates",
        "confirm",
        "dismiss",
        "revoke",
        "status",
    ]


def test_fulfillment_api_returns_typed_validation_error(monkeypatch) -> None:
    class FailingService:
        def __init__(self, _repo) -> None:
            pass

        def candidates(self, **_kwargs):
            raise WorkoutFulfillmentError("candidate evidence is stale")

    monkeypatch.setattr(fulfillment_api, "WorkoutFulfillmentService", FailingService)

    result = fulfillment_api.get_workout_fulfillment_candidates(local_activity_id="act-1")

    assert isinstance(result, fulfillment_api.FulfillmentError)
    assert result.error_type == "validation"
    assert result.message == "candidate evidence is stale"


def test_stable_api_exports_the_complete_fulfillment_and_retirement_surface() -> None:
    expected_names = {
        "FulfillmentError",
        "confirm_workout_fulfillment",
        "dismiss_workout_fulfillment_candidate",
        "get_workout_fulfillment_candidates",
        "get_workout_fulfillment_week_status",
        "retire_fulfilled_week_run_workouts",
        "revoke_workout_fulfillment",
    }

    assert expected_names.issubset(stable_api.__all__)
    assert all(hasattr(stable_api, name) for name in expected_names)
