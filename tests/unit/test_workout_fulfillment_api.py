"""Presentation-neutral API wiring for workout fulfillment lifecycle actions."""

from contextlib import contextmanager

import resilio.api as stable_api
from resilio.api import publication as publication_api
from resilio.api import workout_fulfillment as fulfillment_api
from resilio.core.locking import OperationLockError
from resilio.core.workout_fulfillment.service import WorkoutFulfillmentError
from resilio.integrations.intervals_icu.errors import IntervalsTransportError


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


def test_stable_api_exports_the_complete_native_pairing_fulfillment_surface() -> None:
    expected_names = {
        "FulfillmentError",
        "confirm_workout_fulfillment",
        "dismiss_workout_fulfillment_candidate",
        "get_workout_fulfillment_candidates",
        "get_workout_fulfillment_week_status",
        "reconcile_remote_publication_deletions",
        "reconcile_remote_workout_pairing_operations",
        "resolve_remote_publication_deletion_drift",
        "revoke_workout_fulfillment",
    }

    assert expected_names.issubset(stable_api.__all__)
    assert all(hasattr(stable_api, name) for name in expected_names)


def test_global_pairing_drain_returns_a_typed_lock_error(monkeypatch) -> None:
    @contextmanager
    def locked(*_args, **_kwargs):
        raise OperationLockError("activity mutation lock is held")
        yield

    monkeypatch.setattr(
        publication_api,
        "_with_intervals_client",
        lambda **_kwargs: (object(), False),
    )
    monkeypatch.setattr(
        publication_api,
        "coordinated_publication_plan_activity_lock",
        locked,
    )

    result = publication_api.reconcile_remote_workout_pairing_operations()

    assert isinstance(result, publication_api.PublicationError)
    assert result.error_type == "remote_pairing_reconciliation"
    assert "lock is held" in result.message


def test_global_publication_deletion_reaper_returns_a_typed_lock_error(
    monkeypatch,
) -> None:
    @contextmanager
    def locked(*_args, **_kwargs):
        raise OperationLockError("publication mutation lock is held")
        yield

    monkeypatch.setattr(
        publication_api,
        "_with_intervals_client",
        lambda **_kwargs: (object(), False),
    )
    monkeypatch.setattr(
        publication_api,
        "coordinated_publication_plan_lock",
        locked,
    )

    result = publication_api.reconcile_remote_publication_deletions()

    assert isinstance(result, publication_api.PublicationError)
    assert result.error_type == "publication_safety"
    assert "lock is held" in result.message


def test_global_publication_deletion_reaper_translates_cross_proof_failure(
    monkeypatch,
) -> None:
    @contextmanager
    def unlocked(*_args, **_kwargs):
        yield

    monkeypatch.setattr(
        publication_api,
        "_with_intervals_client",
        lambda **_kwargs: (object(), False),
    )
    monkeypatch.setattr(
        publication_api,
        "coordinated_publication_plan_lock",
        unlocked,
    )
    monkeypatch.setattr(
        publication_api,
        "reconcile_publication_deletion_operations",
        lambda *_args: (_ for _ in ()).throw(
            publication_api.PublicationSafetyError(
                "tombstone lost its retained ownership intent"
            )
        ),
    )

    result = publication_api.reconcile_remote_publication_deletions()

    assert isinstance(result, publication_api.PublicationError)
    assert result.error_type == "publication_safety"
    assert "lost its retained ownership" in result.message


def test_global_publication_deletion_reaper_preserves_provider_error_type(
    monkeypatch,
) -> None:
    @contextmanager
    def unlocked(*_args, **_kwargs):
        yield

    monkeypatch.setattr(
        publication_api,
        "_with_intervals_client",
        lambda **_kwargs: (object(), False),
    )
    monkeypatch.setattr(
        publication_api,
        "coordinated_publication_plan_lock",
        unlocked,
    )
    monkeypatch.setattr(
        publication_api,
        "reconcile_publication_deletion_operations",
        lambda *_args: (_ for _ in ()).throw(
            IntervalsTransportError(
                "provider request failed",
                operation="reconcile_publication_deletions",
            )
        ),
    )

    result = publication_api.reconcile_remote_publication_deletions()

    assert isinstance(result, publication_api.PublicationError)
    assert result.error_type == "transport"


def test_publication_deletion_drift_api_preserves_safety_error_type(monkeypatch) -> None:
    @contextmanager
    def unlocked(*_args, **_kwargs):
        yield

    monkeypatch.setattr(
        publication_api,
        "_with_intervals_client",
        lambda **_kwargs: (object(), False),
    )
    monkeypatch.setattr(
        publication_api,
        "coordinated_publication_plan_lock",
        unlocked,
    )
    monkeypatch.setattr(
        publication_api,
        "resolve_publication_deletion_drifts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            publication_api.PublicationSafetyError("drift token is stale")
        ),
    )

    result = publication_api.resolve_remote_publication_deletion_drift(
        confirmed_drift_tokens=["a" * 64],
        athlete_confirmation_reference="Athlete confirmed the exact target.",
    )

    assert isinstance(result, publication_api.PublicationError)
    assert result.error_type == "publication_safety"


def test_publication_deletion_drift_api_preserves_provider_error_type(monkeypatch) -> None:
    @contextmanager
    def unlocked(*_args, **_kwargs):
        yield

    monkeypatch.setattr(
        publication_api,
        "_with_intervals_client",
        lambda **_kwargs: (object(), False),
    )
    monkeypatch.setattr(
        publication_api,
        "coordinated_publication_plan_lock",
        unlocked,
    )
    monkeypatch.setattr(
        publication_api,
        "resolve_publication_deletion_drifts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            IntervalsTransportError(
                "provider request failed",
                operation="resolve_publication_deletion_drift",
            )
        ),
    )

    result = publication_api.resolve_remote_publication_deletion_drift(
        confirmed_drift_tokens=["a" * 64],
        athlete_confirmation_reference="Athlete confirmed the exact target.",
    )

    assert isinstance(result, publication_api.PublicationError)
    assert result.error_type == "transport"
