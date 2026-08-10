"""Source-verifiable VDOT proposal evidence."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.service import (
    PlanOperationError,
    approve_vdot_proposal,
)
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.schemas.activity import (
    ActivityAudit,
    ActivityOccurrence,
    ActivityOrigin,
    ActivityOriginKind,
)
from resilio.schemas.approvals import VDOTProposal
from resilio.schemas.profile import (
    AthleteProfile,
    RunningFirstTrainingPriority,
    TrainingConstraints,
)
from tests.factories import make_activity

SOURCE_LOCAL_ACTIVITY_ID = "act_i_vdot_source"
SOURCE_PERFORMANCE_EVIDENCE_SHA256 = "a" * 64


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RepositoryIO:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repository = RepositoryIO()
    ProfileRepository(repository).create(
        AthleteProfile(
            athlete_name="Alex",
            created_on=date(2026, 7, 1),
            training_timezone="Europe/Paris",
            constraints=TrainingConstraints(
                minimum_run_days_per_week=2,
                maximum_run_days_per_week=4,
            ),
            training_priority=RunningFirstTrainingPriority(),
        )
    )
    activity = make_activity(
        id=SOURCE_LOCAL_ACTIVITY_ID,
        date=date(2026, 7, 20),
        duration_seconds=2_700,
        moving_seconds=2_700,
        distance_meters=10_000,
    ).model_copy(
        update={
            "occurrence": ActivityOccurrence(
                local_date=date(2026, 7, 20),
                start_time_utc=datetime(2026, 7, 20, 6, tzinfo=timezone.utc),
                start_time_local=datetime(
                    2026,
                    7,
                    20,
                    8,
                    tzinfo=ZoneInfo("Europe/Paris"),
                ),
                timezone="Europe/Paris",
            ),
            "origin": ActivityOrigin(
                kind=ActivityOriginKind.INTERVALS_ICU,
                intervals_icu_activity_id="i-vdot-source",
            ),
            "audit": ActivityAudit(
                imported_at_utc=datetime(2026, 7, 20, 9, tzinfo=timezone.utc),
                provider_snapshot_sha256="b" * 64,
                performance_evidence_sha256=(SOURCE_PERFORMANCE_EVIDENCE_SHA256),
                canonical_mapping_version=9,
            ),
        }
    )
    ActivityArchive(repository.resolve_path("data/activities")).write(activity)
    return repository


def _write_race_proposal(
    path: Path,
    *,
    source_performance_evidence_sha256: str = (SOURCE_PERFORMANCE_EVIDENCE_SHA256),
) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "proposed_vdot": 45,
                "evidence": {
                    "evidence_type": "race_performance",
                    "race_distance": "10k",
                    "elapsed_time_seconds": 2_700,
                    "performance_date": "2026-07-20",
                    "performance_timezone": "Europe/Paris",
                    "source_local_activity_id": SOURCE_LOCAL_ACTIVITY_ID,
                    "source_performance_evidence_sha256": (source_performance_evidence_sha256),
                    "measured_distance_meters": 10_000,
                    "official_distance_confirmation_reference": (
                        "Athlete confirmed this synchronized effort as an official 10K."
                    ),
                },
                "evidence_summary": ("The exact synchronized 10K race supports this baseline."),
                "generated_at_utc": "2026-07-25T08:00:00Z",
            }
        )
    )
    return path


def test_race_proposal_requires_an_exact_synchronized_activity_source(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    state = approve_vdot_proposal(
        repo,
        _write_race_proposal(tmp_path / "race-vdot.json"),
        approved_at_utc=datetime(2026, 7, 25, 9, tzinfo=timezone.utc),
    )

    assert state.active_vdot_approval is not None
    assert state.active_vdot_approval.approved_vdot == 45


def test_race_proposal_rejects_a_changed_source_fingerprint(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    proposal = _write_race_proposal(
        tmp_path / "race-vdot.json",
        source_performance_evidence_sha256="b" * 64,
    )

    with pytest.raises(PlanOperationError, match="fingerprint"):
        approve_vdot_proposal(repo, proposal)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("duration", 2_701, "elapsed time"),
        ("date", date(2026, 7, 21), "performance date"),
        ("sport", "cycle", "running activity"),
        ("timezone", "UTC", "performance timezone"),
        ("distance", 9_950, "measured distance"),
    ],
)
def test_race_proposal_rejects_source_fact_drift(
    repo: RepositoryIO,
    tmp_path: Path,
    field: str,
    replacement: object,
    message: str,
) -> None:
    archive = ActivityArchive(repo.resolve_path("data/activities"))
    activity = archive.load_all()[0]
    if field == "duration":
        activity.duration.elapsed_seconds = int(replacement)
        activity.duration.moving_seconds = int(replacement)
    elif field == "date":
        drift_date = replacement
        assert isinstance(drift_date, date)
        activity.occurrence = activity.occurrence.model_copy(
            update={
                "local_date": drift_date,
                "start_time_utc": datetime(
                    2026,
                    7,
                    21,
                    6,
                    tzinfo=timezone.utc,
                ),
                "start_time_local": datetime(
                    2026,
                    7,
                    21,
                    8,
                    tzinfo=ZoneInfo("Europe/Paris"),
                ),
            }
        )
    elif field == "sport":
        activity.sport = str(replacement)
        activity.source_sport_type = str(replacement)
    elif field == "timezone":
        activity.occurrence = activity.occurrence.model_copy(update={"timezone": str(replacement)})
    else:
        activity.distance_meters = float(replacement)
    archive.write(activity)

    with pytest.raises(PlanOperationError, match=message):
        approve_vdot_proposal(
            repo,
            _write_race_proposal(tmp_path / "race-vdot.json"),
        )


def test_personal_best_proposal_is_bound_to_the_confirmed_profile_record(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    ProfileRepository(repo).update(
        {
            "personal_bests_by_distance": {
                "10k": {
                    "elapsed_time_seconds": 2_700,
                    "performance_date": "2026-07-20",
                    "vdot": 45,
                }
            }
        }
    )
    proposal_path = tmp_path / "personal-best-vdot.json"
    proposal_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "proposed_vdot": 45,
                "evidence": {
                    "evidence_type": "personal_best",
                    "race_distance": "10k",
                    "elapsed_time_seconds": 2_700,
                    "performance_date": "2026-07-20",
                    "performance_timezone": "Europe/Paris",
                },
                "evidence_summary": (
                    "The exact athlete-confirmed personal best supports this baseline."
                ),
                "generated_at_utc": "2026-07-25T08:00:00Z",
            }
        )
    )

    state = approve_vdot_proposal(repo, proposal_path)

    assert state.active_vdot_approval is not None
    ProfileRepository(repo).update(
        {
            "personal_bests_by_distance": {
                "10k": {
                    "elapsed_time_seconds": 2_699,
                    "performance_date": "2026-07-20",
                    "vdot": 45,
                }
            }
        }
    )
    with pytest.raises(PlanOperationError, match="personal best"):
        approve_vdot_proposal(repo, proposal_path)

    ProfileRepository(repo).update(
        {
            "personal_bests_by_distance": {
                "10k": {
                    "elapsed_time_seconds": 2_700,
                    "performance_date": "2026-07-20",
                    "vdot": 45,
                }
            }
        }
    )
    payload = json.loads(proposal_path.read_text())
    payload["evidence"]["performance_timezone"] = "UTC"
    proposal_path.write_text(json.dumps(payload))
    with pytest.raises(PlanOperationError, match="timezone.*athlete profile"):
        approve_vdot_proposal(repo, proposal_path)


def test_race_proposal_date_is_compared_in_its_declared_timezone() -> None:
    payload = {
        "schema_version": 2,
        "proposed_vdot": 45,
        "evidence": {
            "evidence_type": "race_performance",
            "race_distance": "10k",
            "elapsed_time_seconds": 2_700,
            "performance_date": "2026-07-30",
            "performance_timezone": "Europe/Paris",
            "source_local_activity_id": SOURCE_LOCAL_ACTIVITY_ID,
            "source_performance_evidence_sha256": (SOURCE_PERFORMANCE_EVIDENCE_SHA256),
            "measured_distance_meters": 10_000,
            "official_distance_confirmation_reference": (
                "Athlete confirmed this synchronized effort as an official 10K."
            ),
        },
        "evidence_summary": ("The athlete-local performance date is valid across UTC midnight."),
        "generated_at_utc": "2026-07-29T22:30:00Z",
    }

    proposal = VDOTProposal.model_validate(payload)

    assert proposal.evidence.performance_date == date(2026, 7, 30)
    payload["evidence"]["performance_timezone"] = "UTC"
    with pytest.raises(ValidationError, match="cannot postdate"):
        VDOTProposal.model_validate(payload)


def test_vdot_estimation_fails_closed_during_a_profile_plan_transition(
    repo: RepositoryIO,
) -> None:
    from resilio.api.vdot import VDOTError, estimate_current_vdot

    with coordinated_plan_lock(repo, "profile_plan_writer"):
        result = estimate_current_vdot(as_of_date=date(2026, 7, 30))

    assert isinstance(result, VDOTError)
    assert result.error_type == "temporarily_unavailable"
