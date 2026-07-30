"""Explicit athlete approval for conservative activity matches."""

import hashlib
from datetime import date, datetime, timezone

import pytest

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.review import (
    ReconciliationReviewError,
    acknowledge_activity_quarantine,
    approve_reconciliation_override,
    exclude_duplicate_reconciliation,
    list_activity_quarantines,
    list_reconciliation_reviews,
    load_override_ledger,
    load_quarantine_acknowledgement_ledger,
)
from resilio.core.activity_sync.service import ActivitySyncService
from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import read_sync_state
from resilio.integrations.intervals_icu.dto import (
    ActivityDTO,
    AthleteDTO,
    ConnectionsDTO,
)
from resilio.schemas.activity import (
    ActivityOccurrence,
    RecordingProvider,
)
from resilio.schemas.config import Config, IntervalsIcuSettings, Settings
from resilio.schemas.sync import SyncPhase
from tests.factories import make_activity


def _config() -> Config:
    return Config(
        settings=Settings(
            intervals_icu=IntervalsIcuSettings(
                history_start_date=date(2026, 7, 28),
            )
        ),
        intervals_icu_api_key="fake",
        loaded_at=datetime.now(timezone.utc),
    )


class ReviewClient:
    original_file = b"review-only original file fixture"

    def __init__(self):
        self.activity = ActivityDTO(
            id="review-external",
            type="Run",
            name="External run",
            start_date="2026-07-28T05:00:00Z",
            start_date_local="2026-07-28T07:00:00+02:00",
            timezone="Europe/Paris",
            elapsed_time=2700,
            moving_time=2700,
            distance=8000,
            perceived_exertion=5,
            source="WAHOO",
        )

    def get_athlete(self):
        return AthleteDTO(id="athlete-1", timezone="Europe/Paris")

    def get_connections(self, _athlete_id):
        return ConnectionsDTO(id="athlete-1")

    def get_sport_settings(self, _athlete_id):
        return []

    def get_wellness(self, _oldest, _newest, *, athlete_id=None):
        return []

    def list_activities(self, *_args, **_kwargs):
        return [self.activity]

    def get_activities(self, _ids, **_kwargs):
        return [self.activity]

    def get_original_file(self, _activity_id):
        return self.original_file


class DuplicateReviewClient(ReviewClient):
    def __init__(self):
        self.activities = {
            "already-linked-external": ActivityDTO(
                id="already-linked-external",
                type="Ride",
                name="Wahoo ride",
                start_date="2026-07-28T05:00:00Z",
                start_date_local="2026-07-28T07:00:00+02:00",
                timezone="Europe/Paris",
                elapsed_time=3600,
                moving_time=3500,
                distance=20000,
                source="WAHOO",
            ),
            "duplicate-external": ActivityDTO(
                id="duplicate-external",
                type="Ride",
                name="Garmin ride",
                start_date="2026-07-28T05:00:00Z",
                start_date_local="2026-07-28T07:00:00+02:00",
                timezone="Europe/Paris",
                elapsed_time=3601,
                moving_time=3501,
                distance=20001,
                source="GARMIN_CONNECT",
            ),
        }

    def list_activities(self, *_args, **_kwargs):
        return list(self.activities.values())

    def get_activities(self, ids, **_kwargs):
        return [self.activities[item] for item in ids]

    def get_activity(self, activity_id, **_kwargs):
        return self.activities[activity_id]

    def get_original_file(self, activity_id):
        return f"fixture:{activity_id}".encode()


@pytest.fixture
def review_repo(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    archive_root = tmp_path / "data" / "activities"
    archive_root.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    candidate = make_activity(
        id="historical-candidate",
        date=date(2026, 7, 28),
        sport="run",
        duration_seconds=2800,
        moving_seconds=2800,
        distance_meters=8000,
        name="Historical run",
    ).model_copy(
        update={
            "occurrence": ActivityOccurrence(
                local_date=date(2026, 7, 28),
            )
        }
    )
    ActivityArchive(archive_root).write(candidate)
    return repo


def test_review_approval_is_current_candidate_bound_and_idempotent(
    review_repo,
) -> None:
    service = ActivitySyncService(
        review_repo,
        _config(),
        ReviewClient(),
    )
    first = service.run(today=date(2026, 7, 28), full=True)

    assert first.phase == SyncPhase.PARTIAL
    assert first.ambiguous_rows == 1
    reviews = list_reconciliation_reviews(review_repo)
    assert len(reviews) == 1
    assert reviews[0].candidates[0].local_activity_id == ("historical-candidate")
    assert reviews[0].candidates[0].name == "Historical run"
    assert reviews[0].original_file_probe == "no_unique_match"

    with pytest.raises(ReconciliationReviewError, match="not a current"):
        approve_reconciliation_override(
            review_repo,
            external_activity_id_sha256=(reviews[0].external_activity_id_sha256),
            local_activity_id="not-a-candidate",
            review_fingerprint_sha256=(reviews[0].review_fingerprint_sha256),
        )

    approved = approve_reconciliation_override(
        review_repo,
        external_activity_id_sha256=(reviews[0].external_activity_id_sha256),
        local_activity_id="historical-candidate",
        review_fingerprint_sha256=reviews[0].review_fingerprint_sha256,
    )
    unchanged = approve_reconciliation_override(
        review_repo,
        external_activity_id_sha256=(reviews[0].external_activity_id_sha256),
        local_activity_id="historical-candidate",
        review_fingerprint_sha256=reviews[0].review_fingerprint_sha256,
    )

    assert approved.action == "approved"
    assert unchanged.action == "unchanged"
    assert len(load_override_ledger(review_repo).overrides) == 1

    second = service.run(today=date(2026, 7, 28), full=True)
    records = ActivityArchive(review_repo.resolve_path("data/activities")).load_all()

    assert second.phase == SyncPhase.DONE
    assert second.activities_linked == 1
    assert second.ambiguous_rows == 0
    assert len(records) == 1
    assert records[0].local_activity_id == "historical-candidate"
    assert records[0].origin.intervals_icu_activity_id == "review-external"


def test_review_override_is_rejected_when_review_evidence_drifts(
    review_repo,
) -> None:
    client = ReviewClient()
    service = ActivitySyncService(review_repo, _config(), client)
    service.run(today=date(2026, 7, 28), full=True)
    review = list_reconciliation_reviews(review_repo)[0]
    approve_reconciliation_override(
        review_repo,
        external_activity_id_sha256=review.external_activity_id_sha256,
        local_activity_id="historical-candidate",
        review_fingerprint_sha256=review.review_fingerprint_sha256,
    )
    client.activity = client.activity.model_copy(update={"elapsed_time": 2800, "moving_time": 2800})

    report = service.run(today=date(2026, 7, 28), full=True)

    assert report.phase == SyncPhase.PARTIAL
    assert report.quarantined_rows == 1
    checkpoint_run_id = read_sync_state(review_repo).checkpoint_run_id
    assert checkpoint_run_id is not None
    quarantine_payload = review_repo.resolve_path(
        f"data/state/sync-runs/{checkpoint_run_id}/quarantine.json"
    ).read_text()
    assert "stale_review_override" in quarantine_payload


def test_review_override_is_rejected_when_candidate_ownership_drifts(
    review_repo,
) -> None:
    client = ReviewClient()
    client.get_activity = lambda _external_id: client.activity
    service = ActivitySyncService(review_repo, _config(), client)
    service.run(today=date(2026, 7, 28), full=True)
    review = list_reconciliation_reviews(review_repo)[0]
    approve_reconciliation_override(
        review_repo,
        external_activity_id_sha256=review.external_activity_id_sha256,
        local_activity_id="historical-candidate",
        review_fingerprint_sha256=review.review_fingerprint_sha256,
    )
    archive = ActivityArchive(review_repo.resolve_path("data/activities"))
    candidate = archive.load_all()[0]
    archive.write(
        candidate.model_copy(
            update={
                "origin": candidate.origin.model_copy(
                    update={"intervals_icu_activity_id": "new-external-owner"}
                )
            }
        )
    )

    report = service.run(today=date(2026, 7, 28), full=True)

    assert report.phase == SyncPhase.PARTIAL
    assert report.quarantined_rows == 1
    assert archive.load_all()[0].origin.intervals_icu_activity_id == "new-external-owner"


def test_already_linked_cross_device_duplicate_requires_exact_exclusion(
    review_repo,
) -> None:
    archive = ActivityArchive(review_repo.resolve_path("data/activities"))
    existing = archive.load_all()[0]
    existing = existing.model_copy(
        update={
            "sport": "cycle",
            "source_sport_type": "Ride",
            "duration": existing.duration.model_copy(
                update={
                    "elapsed_seconds": 3600,
                    "moving_seconds": 3500,
                }
            ),
            "distance_meters": 20000,
            "origin": existing.origin.model_copy(
                update={
                    "recording_provider": RecordingProvider.WAHOO,
                    "intervals_icu_activity_id": ("already-linked-external"),
                }
            ),
        }
    )
    archive.write(existing)
    service = ActivitySyncService(
        review_repo,
        _config(),
        DuplicateReviewClient(),
    )

    first = service.run(today=date(2026, 7, 28), full=True)
    reviews = list_reconciliation_reviews(review_repo)

    assert first.phase == SyncPhase.PARTIAL
    assert first.ambiguous_rows == 1
    assert len(reviews) == 1
    assert len(reviews[0].candidates) == 1
    assert reviews[0].candidates[0].already_linked_to_different_external_id
    with pytest.raises(
        ReconciliationReviewError,
        match="exclude the duplicate",
    ):
        approve_reconciliation_override(
            review_repo,
            external_activity_id_sha256=(reviews[0].external_activity_id_sha256),
            local_activity_id=existing.local_activity_id,
            review_fingerprint_sha256=(reviews[0].review_fingerprint_sha256),
        )
    with pytest.raises(
        ReconciliationReviewError,
        match="fingerprint is no longer current",
    ):
        exclude_duplicate_reconciliation(
            review_repo,
            external_activity_id_sha256=(reviews[0].external_activity_id_sha256),
            local_activity_id=existing.local_activity_id,
            review_fingerprint_sha256="0" * 64,
        )

    excluded = exclude_duplicate_reconciliation(
        review_repo,
        external_activity_id_sha256=(reviews[0].external_activity_id_sha256),
        local_activity_id=existing.local_activity_id,
        review_fingerprint_sha256=(reviews[0].review_fingerprint_sha256),
    )
    second = service.run(today=date(2026, 7, 28), full=True)
    records = archive.load_all()

    assert excluded.action == "excluded"
    assert second.phase == SyncPhase.DONE
    assert second.excluded_duplicate_rows == 1
    assert second.ambiguous_rows == 0
    assert len(records) == 1
    assert records[0].origin.intervals_icu_activity_id == "already-linked-external"
    ledger = load_override_ledger(review_repo)
    assert not ledger.overrides
    assert len(ledger.exclusions) == 1


def test_original_file_hash_resolves_unique_ambiguous_candidate(
    review_repo,
) -> None:
    archive = ActivityArchive(review_repo.resolve_path("data/activities"))
    candidate = archive.load_all()[0]
    digest = hashlib.sha256(ReviewClient.original_file).hexdigest()
    archive.write(
        candidate.model_copy(
            update={"origin": candidate.origin.model_copy(update={"original_file_sha256": digest})}
        )
    )

    report = ActivitySyncService(
        review_repo,
        _config(),
        ReviewClient(),
    ).run(today=date(2026, 7, 28), full=True)
    linked = archive.load_all()[0]

    assert report.phase == SyncPhase.DONE
    assert report.activities_linked == 1
    assert report.ambiguous_rows == 0
    assert linked.origin.intervals_icu_activity_id == "review-external"
    assert linked.origin.original_file_sha256 == digest


def test_inconsistent_local_timestamp_quarantine_is_blocking(
    review_repo,
) -> None:
    client = ReviewClient()
    client.activity = client.activity.model_copy(
        update={
            "start_date_local": client.activity.start_date_local.replace(
                hour=client.activity.start_date_local.hour + 1
            )
        }
    )
    service = ActivitySyncService(review_repo, _config(), client)

    first = service.run(today=date(2026, 7, 28), full=True)
    quarantines = list_activity_quarantines(review_repo)

    assert first.phase == SyncPhase.PARTIAL
    assert first.quarantined_rows == 1
    assert first.acknowledged_quarantined_rows == 0
    assert len(quarantines) == 1
    assert not quarantines[0].acknowledgeable
    assert not quarantines[0].acknowledged
    assert quarantines[0].error_type == "ValueError"
    assert not quarantines[0].validation_issues
    artifact = next(
        review_repo.resolve_path("data/state/sync-runs").rglob("quarantine.json")
    ).read_text()
    assert "External run" not in artifact
    assert "review-external" not in artifact

    with pytest.raises(ReconciliationReviewError, match="cannot be acknowledged"):
        acknowledge_activity_quarantine(
            review_repo,
            external_activity_id_sha256=(quarantines[0].external_activity_id_sha256),
            failure_fingerprint_sha256=quarantines[0].failure_fingerprint_sha256,
        )
    assert not load_quarantine_acknowledgement_ledger(review_repo).acknowledgements


def test_unsupported_sport_quarantine_can_be_acknowledged(
    review_repo,
) -> None:
    client = ReviewClient()
    client.activity = client.activity.model_copy(update={"type": "UnknownFutureSport"})

    ActivitySyncService(review_repo, _config(), client).run(
        today=date(2026, 7, 28),
        full=True,
    )
    quarantine = list_activity_quarantines(review_repo)[0]

    assert quarantine.acknowledgeable
    acknowledged = acknowledge_activity_quarantine(
        review_repo,
        external_activity_id_sha256=(quarantine.external_activity_id_sha256),
        failure_fingerprint_sha256=(quarantine.failure_fingerprint_sha256),
    )
    assert acknowledged.action == "acknowledged"

    report = ActivitySyncService(review_repo, _config(), client).run(
        today=date(2026, 7, 28),
        full=True,
    )
    exclusions = read_sync_state(review_repo).source_coverage_exclusions

    assert report.phase == SyncPhase.DONE
    assert len(exclusions) == 1
    assert exclusions[0].reason == "acknowledged_unsupported_sport"
    assert exclusions[0].local_date == date(2026, 7, 28)
    assert exclusions[0].source_sport_type == "UnknownFutureSport"


def test_changed_unsupported_source_facts_invalidate_acknowledgement(
    review_repo,
) -> None:
    client = ReviewClient()
    client.activity = client.activity.model_copy(update={"type": "UnknownFutureSport"})
    service = ActivitySyncService(review_repo, _config(), client)
    service.run(today=date(2026, 7, 28), full=True)
    quarantine = list_activity_quarantines(review_repo)[0]
    acknowledge_activity_quarantine(
        review_repo,
        external_activity_id_sha256=(quarantine.external_activity_id_sha256),
        failure_fingerprint_sha256=(quarantine.failure_fingerprint_sha256),
    )
    client.activity = client.activity.model_copy(update={"type": "AnotherFutureSport"})

    report = service.run(today=date(2026, 7, 28), full=True)
    changed = list_activity_quarantines(review_repo)[0]

    assert report.phase == SyncPhase.PARTIAL
    assert not changed.acknowledged
    assert changed.failure_fingerprint_sha256 != quarantine.failure_fingerprint_sha256
