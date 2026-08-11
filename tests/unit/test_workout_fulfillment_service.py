from datetime import date, datetime, timezone

import pytest

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.candidates import FulfillmentWorkoutAuthority
from resilio.core.workout_fulfillment.repository import (
    WorkoutFulfillmentCutoverRequiredError,
    load_fulfillment_manifest,
    save_fulfillment_manifest,
)
from resilio.core.workout_fulfillment.service import (
    WorkoutFulfillmentError,
    WorkoutFulfillmentService,
)
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.workout_fulfillment import (
    ProviderPairedFulfillmentEvidence,
    UnresolvedFulfillmentConflict,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)
from tests.factories import make_activity


def _workout() -> RunningWorkoutPrescription:
    return RunningWorkoutPrescription.model_validate(
        {
            "id": "w_easy",
            "date": "2026-08-11",
            "workout_type": "easy",
            "planned_duration_seconds": 2_400,
            "planned_distance_meters": 5_000,
            "planned_low_intensity_duration_seconds": 2_400,
            "planned_moderate_intensity_duration_seconds": 0,
            "planned_high_intensity_duration_seconds": 0,
            "target_rpe_1_to_10": 3,
            "purpose": "Complete one conversational five-kilometre run.",
            "structured_workout": {
                "sport": "run",
                "steps": [
                    {
                        "kind": "steady",
                        "duration": {"unit": "seconds", "value": 2_400},
                        "intensity": "active",
                    }
                ],
            },
        }
    )


class HarnessFulfillmentService(WorkoutFulfillmentService):
    def __init__(self, repo: RepositoryIO) -> None:
        super().__init__(repo)
        self.activity = make_activity(
            id="act_run",
            date=date(2026, 8, 10),
            start_time=datetime(2026, 8, 10, 7, tzinfo=timezone.utc),
            distance_meters=5_500,
        )
        self.authorities = [
            FulfillmentWorkoutAuthority(
                identity=PlanWorkoutIdentity(
                    plan_id="plan_example",
                    plan_revision_id="plan_revision_0123456789abcdef",
                    week_number=1,
                    local_workout_id="w_easy",
                ),
                prescription=_workout(),
                applied_week_approval_id="week_approval_0123456789abcdef",
                applied_running_workouts_sha256="1" * 64,
                schedule_timezone="Europe/Paris",
            )
        ]

    def _load_activity_unlocked(self, local_activity_id: str):
        assert local_activity_id == "act_run"
        return self.activity

    def _load_candidate_workout_authorities_unlocked(self, activity):
        assert activity == self.activity
        return self.authorities

    def _load_workout_authorities_unlocked(self):
        authority = self.authorities[0]
        return [
            AuthoritativeWorkout(
                identity=authority.identity,
                prescription=authority.prescription,
                applied_week_approval_id=authority.applied_week_approval_id,
                applied_running_workouts_sha256=(authority.applied_running_workouts_sha256),
                schedule_timezone=authority.schedule_timezone,
            )
        ]


def _service(tmp_path, monkeypatch) -> HarnessFulfillmentService:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return HarnessFulfillmentService(RepositoryIO())


def _provider_fulfillment(candidate) -> WorkoutFulfillmentRecord:
    return WorkoutFulfillmentRecord(
        local_activity_id=candidate.local_activity_id,
        workout_identity=candidate.workout_identity,
        applied_week_approval_id=candidate.applied_week_approval_id,
        applied_running_workouts_sha256=candidate.applied_running_workouts_sha256,
        workout_prescription_sha256=candidate.workout_prescription_sha256,
        activity_performance_evidence_sha256=(candidate.activity_performance_evidence_sha256),
        schedule_timezone=candidate.schedule_timezone,
        scheduled_local_date=candidate.scheduled_local_date,
        execution_local_date=candidate.execution_local_date,
        schedule_offset_days=candidate.schedule_offset_days,
        provider_pair=ProviderPairedFulfillmentEvidence(
            event_id=42,
            observed_at_utc=datetime(2026, 8, 10, 8, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 10, 8, tzinfo=timezone.utc),
    )


def test_confirmation_revalidates_candidate_and_persists_exact_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    service = _service(tmp_path, monkeypatch)
    candidate = service.candidates(local_activity_id="act_run")[0]
    confirmed_at_utc = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)

    record = service.confirm(
        local_activity_id="act_run",
        local_workout_id="w_easy",
        candidate_sha256=candidate.candidate_sha256,
        athlete_confirmation_reference="Athlete confirmed this was Tuesday's easy run.",
        coaching_rationale="The athlete described an easy conversational run matching the intent.",
        confirmed_at_utc=confirmed_at_utc,
    )

    assert record.fulfillment_basis == "athlete_confirmed"
    assert record.schedule_offset_days == -1
    assert record.athlete_confirmation is not None
    assert record.athlete_confirmation.candidate_sha256 == candidate.candidate_sha256
    assert load_fulfillment_manifest(service.repo).fulfillments["act_run"] == record


def test_week_status_fails_closed_on_an_unresolved_fulfillment_conflict(
    tmp_path,
    monkeypatch,
) -> None:
    service = _service(tmp_path, monkeypatch)
    candidate = service.candidates(local_activity_id="act_run")[0]
    service.confirm(
        local_activity_id="act_run",
        local_workout_id="w_easy",
        candidate_sha256=candidate.candidate_sha256,
        athlete_confirmation_reference="Athlete confirmed the proposed association.",
        coaching_rationale=(
            "The athlete explicitly confirmed the exact proposed workout association."
        ),
        confirmed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )
    manifest = load_fulfillment_manifest(service.repo)
    manifest.unresolved_fulfillment_conflicts["act_run"] = UnresolvedFulfillmentConflict(
        local_activity_id="act_run",
        rule="paired_event_removed",
        observed_at_utc=datetime(2026, 8, 10, 11, tzinfo=timezone.utc),
    )
    save_fulfillment_manifest(service.repo, manifest)

    with pytest.raises(WorkoutFulfillmentError, match="unresolved synchronized"):
        service.week_status(week_number=1)


def test_confirmation_enriches_an_exact_early_provider_pair_for_calendar_cleanup(
    tmp_path,
    monkeypatch,
) -> None:
    service = _service(tmp_path, monkeypatch)
    candidate = service.candidates(local_activity_id="act_run")[0]
    provider_record = _provider_fulfillment(candidate)
    save_fulfillment_manifest(
        service.repo,
        WorkoutFulfillmentManifest(fulfillments={"act_run": provider_record}),
    )

    confirmation_candidate = service.candidates(local_activity_id="act_run")[0]
    enriched = service.confirm(
        local_activity_id="act_run",
        local_workout_id="w_easy",
        candidate_sha256=confirmation_candidate.candidate_sha256,
        athlete_confirmation_reference=(
            "Athlete confirmed the early pair and authorized future-event cleanup."
        ),
        coaching_rationale=(
            "The exact provider pair and the athlete both identify this as the easy run."
        ),
        confirmed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )

    assert enriched.fulfillment_basis == "provider_paired_and_athlete_confirmed"
    assert enriched.provider_pair == provider_record.provider_pair
    assert enriched.athlete_confirmation is not None


def test_provider_paired_candidate_denial_requires_explicit_revocation(
    tmp_path,
    monkeypatch,
) -> None:
    service = _service(tmp_path, monkeypatch)
    candidate = service.candidates(local_activity_id="act_run")[0]
    save_fulfillment_manifest(
        service.repo,
        WorkoutFulfillmentManifest(fulfillments={"act_run": _provider_fulfillment(candidate)}),
    )
    provider_candidate = service.candidates(local_activity_id="act_run")[0]

    with pytest.raises(WorkoutFulfillmentError, match="explicit revocation"):
        service.dismiss_candidate(
            local_activity_id="act_run",
            local_workout_id="w_easy",
            candidate_sha256=provider_candidate.candidate_sha256,
            athlete_response_reference=(
                "Athlete said this provider pair did not fulfill the workout."
            ),
            dismissed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
        )

    assert "act_run" in load_fulfillment_manifest(service.repo).fulfillments


def test_confirmation_rejects_stale_candidate_without_writing(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    candidate = service.candidates(local_activity_id="act_run")[0]
    service.activity = service.activity.model_copy(
        update={"distance_meters": service.activity.distance_meters + 1}
    )

    with pytest.raises(WorkoutFulfillmentError, match="stale or ineligible"):
        service.confirm(
            local_activity_id="act_run",
            local_workout_id="w_easy",
            candidate_sha256=candidate.candidate_sha256,
            athlete_confirmation_reference="Athlete confirmed the proposed association.",
            coaching_rationale=(
                "The athlete explicitly confirmed the exact proposed workout association."
            ),
            confirmed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
        )

    assert load_fulfillment_manifest(service.repo).fulfillments == {}


def test_exact_confirmation_retry_is_idempotent_but_conflict_is_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    service = _service(tmp_path, monkeypatch)
    candidate = service.candidates(local_activity_id="act_run")[0]
    arguments = {
        "local_activity_id": "act_run",
        "local_workout_id": "w_easy",
        "candidate_sha256": candidate.candidate_sha256,
        "athlete_confirmation_reference": "Athlete confirmed the proposed association.",
        "coaching_rationale": (
            "The athlete explicitly confirmed the exact proposed workout association."
        ),
        "confirmed_at_utc": datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    }

    first = service.confirm(**arguments)
    assert service.confirm(**arguments) == first

    with pytest.raises(WorkoutFulfillmentError, match="conflicts"):
        service.confirm(
            **{
                **arguments,
                "athlete_confirmation_reference": "A different confirmation reference.",
            }
        )


def test_revocation_is_idempotent_and_suppresses_the_same_exact_candidate(
    tmp_path,
    monkeypatch,
) -> None:
    service = _service(tmp_path, monkeypatch)
    candidate = service.candidates(local_activity_id="act_run")[0]
    service.confirm(
        local_activity_id="act_run",
        local_workout_id="w_easy",
        candidate_sha256=candidate.candidate_sha256,
        athlete_confirmation_reference="Athlete confirmed the proposed association.",
        coaching_rationale=(
            "The athlete explicitly confirmed the exact proposed workout association."
        ),
        confirmed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )
    arguments = {
        "local_activity_id": "act_run",
        "local_workout_id": "w_easy",
        "reason": "association_incorrect",
        "athlete_confirmation_reference": (
            "Athlete withdrew the exact activity-to-workout association."
        ),
        "coaching_rationale": (
            "The athlete clarified that this activity did not fulfill the approved workout."
        ),
        "revoked_at_utc": datetime(2026, 8, 10, 11, tzinfo=timezone.utc),
    }

    first = service.revoke(**arguments)

    assert service.revoke(**arguments) == first
    assert service.candidates(local_activity_id="act_run") == []
    manifest = load_fulfillment_manifest(service.repo)
    assert manifest.fulfillments == {}
    assert manifest.revoked_fulfillments == [first]

    service.activity = service.activity.model_copy(
        update={"distance_meters": service.activity.distance_meters + 10}
    )
    changed_candidate = service.candidates(local_activity_id="act_run")[0]
    service.confirm(
        local_activity_id="act_run",
        local_workout_id="w_easy",
        candidate_sha256=changed_candidate.candidate_sha256,
        athlete_confirmation_reference="Athlete confirmed the corrected evidence.",
        coaching_rationale=(
            "The athlete reviewed the corrected activity evidence and approved the association."
        ),
        confirmed_at_utc=datetime(2026, 8, 10, 12, tzinfo=timezone.utc),
    )
    second = service.revoke(
        **{
            **arguments,
            "revoked_at_utc": datetime(2026, 8, 10, 13, tzinfo=timezone.utc),
        }
    )

    assert second.revocation_id != first.revocation_id
    assert len(load_fulfillment_manifest(service.repo).revoked_fulfillments) == 2


def test_dismissed_exact_candidate_is_not_offered_again(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    candidate = service.candidates(local_activity_id="act_run")[0]

    arguments = {
        "local_activity_id": "act_run",
        "local_workout_id": "w_easy",
        "candidate_sha256": candidate.candidate_sha256,
        "athlete_response_reference": ("Athlete said this run did not fulfill that workout."),
        "dismissed_at_utc": datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    }
    first = service.dismiss_candidate(
        **arguments,
    )

    assert service.dismiss_candidate(**arguments) == first
    assert service.candidates(local_activity_id="act_run") == []


def test_normal_fulfillment_access_is_blocked_before_legacy_cutover(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    legacy_path = tmp_path / "data/state/workout_completions.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text('{"schema_version": 3, "matches": {}}')

    with pytest.raises(WorkoutFulfillmentCutoverRequiredError, match="requires"):
        load_fulfillment_manifest(RepositoryIO())
