"""Window completeness and idempotent completed-activity sync tests."""

import json
from datetime import date, datetime, time, timezone
from pathlib import Path

import pytest

from resilio.core.activity_sync.activity_merge import merge_reviewed_activity
from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.activity_sync.review import list_external_deletion_reviews
from resilio.core.activity_sync.service import (
    ActivitySyncService,
    _requires_full_reconciliation,
)
from resilio.core.activity_sync.staged_reconciliation import _sanitized_decision
from resilio.core.activity_sync.windowing import (
    SaturatedActivityWindowError,
    enumerate_windows,
    fetch_complete_window,
)
from resilio.core.planning.adherence_evidence import (
    ApprovedWorkoutWindow,
    AuthoritativeWorkout,
)
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import (
    read_sync_progress,
    read_sync_state,
    write_sync_state,
)
from resilio.core.workout_fulfillment.candidates import (
    FulfillmentWorkoutAuthority,
    build_fulfillment_candidates,
)
from resilio.core.workout_fulfillment.repository import (
    WorkoutFulfillmentCutoverRequiredError,
    load_fulfillment_manifest,
    save_fulfillment_manifest,
)
from resilio.core.workout_publication.manifest import save_manifest
from resilio.integrations.intervals_icu.activity_mapper import map_activity
from resilio.integrations.intervals_icu.dto import (
    ActivityDTO,
    AthleteDTO,
    ConnectionsDTO,
    HiddenActivityDTO,
    SportSettingsDTO,
    WellnessDTO,
)
from resilio.integrations.intervals_icu.errors import (
    IntervalsNotFoundError,
    IntervalsTransportError,
)
from resilio.schemas.activity import (
    ActivityAudit,
    ActivityOrigin,
    ActivityOriginKind,
    ActivityStatus,
    RecordingProvider,
)
from resilio.schemas.config import Config, IntervalsIcuSettings, Settings
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.publication import (
    HistoricalLegacyWorkoutPublication,
    PublicationManifest,
    PublishedWorkout,
)
from resilio.schemas.reconciliation import (
    ReconciliationAction,
    ReconciliationDecision,
)
from resilio.schemas.sync import (
    ActivityCoverageWindow,
    ActivitySyncState,
    SourceCoverageExclusion,
)
from resilio.schemas.workout_fulfillment import (
    HistoricalLegacyWorkoutFulfillment,
    ProviderPairedFulfillmentEvidence,
    WorkoutFulfillmentCandidateDismissal,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)
from tests.factories import make_activity


def _activity(activity_id: str, day: int = 28) -> ActivityDTO:
    return ActivityDTO(
        id=activity_id,
        type="Run",
        name="Imported run",
        start_date=f"2026-07-{day:02d}T05:00:00Z",
        start_date_local=f"2026-07-{day:02d}T07:00:00+02:00",
        timezone="Europe/Paris",
        elapsed_time=2700,
        moving_time=2700,
        distance=8000,
        perceived_exertion=5,
        source="WAHOO",
    )


class BisectionClient:
    def __init__(self):
        self.calls: list[tuple[date, date]] = []

    def list_activities(self, oldest, newest, *, athlete_id=None, limit=2):
        self.calls.append((oldest, newest))
        if oldest != newest:
            return [_activity("saturated-a"), _activity("saturated-b")]
        return [_activity(oldest.isoformat(), oldest.day)]


def test_windows_cover_inclusive_range_without_overlap() -> None:
    assert enumerate_windows(
        date(2026, 1, 1),
        date(2026, 4, 1),
        90,
    ) == [
        (date(2026, 1, 1), date(2026, 3, 31)),
        (date(2026, 4, 1), date(2026, 4, 1)),
    ]


def test_full_reconciliation_runs_on_initial_and_monthly_cadence() -> None:
    empty = ActivitySyncState()
    assert _requires_full_reconciliation(
        today=date(2026, 7, 28),
        state=empty,
        requested=False,
        cadence_days=30,
    )

    recent = ActivitySyncState(
        last_successful_incremental_at_utc=datetime(
            2026,
            7,
            27,
            tzinfo=timezone.utc,
        ),
        last_full_reconciliation_at_utc=datetime(
            2026,
            7,
            1,
            tzinfo=timezone.utc,
        ),
    )
    assert not _requires_full_reconciliation(
        today=date(2026, 7, 28),
        state=recent,
        requested=False,
        cadence_days=30,
    )
    assert _requires_full_reconciliation(
        today=date(2026, 7, 31),
        state=recent,
        requested=False,
        cadence_days=30,
    )


def test_saturated_window_is_bisected_and_keeps_descending_order() -> None:
    client = BisectionClient()

    rows = fetch_complete_window(
        client,
        date(2026, 7, 27),
        date(2026, 7, 28),
        athlete_id="athlete",
        limit=2,
    )

    assert [row.id for row in rows] == ["2026-07-28", "2026-07-27"]
    assert len(client.calls) == 3


def test_saturated_single_day_fails_partial_instead_of_truncating() -> None:
    class AlwaysFull:
        def list_activities(self, *_args, **_kwargs):
            return [_activity("one"), _activity("two")]

    with pytest.raises(SaturatedActivityWindowError):
        fetch_complete_window(
            AlwaysFull(),
            date(2026, 7, 28),
            date(2026, 7, 28),
            athlete_id="athlete",
            limit=2,
        )


@pytest.mark.parametrize(
    ("local_id", "review_fingerprint"),
    [(None, "a" * 64), ("local-activity", None)],
)
def test_source_duplicate_disposition_requires_both_review_bindings(
    local_id,
    review_fingerprint,
) -> None:
    with pytest.raises(ValueError, match="requires local identity"):
        SourceCoverageExclusion(
            external_activity_id_sha256="b" * 64,
            local_date=date(2026, 7, 28),
            reason="represented_duplicate_recording",
            represented_by_local_activity_id=local_id,
            review_fingerprint_sha256=review_fingerprint,
        )


@pytest.mark.parametrize(
    ("local_id", "review_fingerprint"),
    [(None, "a" * 64), ("local-activity", None)],
)
def test_nonduplicate_disposition_forbids_review_bindings(
    local_id,
    review_fingerprint,
) -> None:
    with pytest.raises(ValueError, match="other dispositions forbid"):
        SourceCoverageExclusion(
            external_activity_id_sha256="b" * 64,
            local_date=date(2026, 7, 28),
            reason="source_hidden",
            represented_by_local_activity_id=local_id,
            review_fingerprint_sha256=review_fingerprint,
        )


class SyncClient:
    def __init__(self):
        self.row = _activity("external-1")

    def get_athlete(self):
        return AthleteDTO(id="athlete-1", timezone="Europe/Paris")

    def get_connections(self, _athlete_id):
        return ConnectionsDTO(id="athlete-1")

    def get_sport_settings(self, _athlete_id):
        return []

    def get_wellness(self, _oldest, _newest, *, athlete_id=None):
        return []

    def list_activities(self, *_args, **_kwargs):
        return [self.row]

    def get_activities(self, _ids, **_kwargs):
        return [self.row]


def test_incremental_sync_merges_explicit_historical_coverage(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    write_sync_state(
        repo,
        ActivitySyncState(
            last_successful_incremental_at_utc=datetime(2026, 7, 27, tzinfo=timezone.utc),
            last_full_reconciliation_at_utc=datetime(2026, 7, 27, tzinfo=timezone.utc),
            complete_activity_windows=[
                ActivityCoverageWindow(
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 7, 27),
                )
            ],
        ),
    )

    ActivitySyncService(repo, _config(), SyncClient()).run(today=date(2026, 7, 28))

    state = read_sync_state(repo)
    assert state.complete_activity_windows == [
        ActivityCoverageWindow(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 7, 28),
        )
    ]


def test_sync_fails_before_provider_access_or_progress_when_cutover_is_required(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    legacy_path = repo.resolve_path("data/state/workout_completions.json")
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text('{"schema_version":3,"matches":{}}')

    class ProviderMustNotBeCalled(SyncClient):
        def get_athlete(self):
            raise AssertionError("provider access must follow local cutover preflight")

    with pytest.raises(WorkoutFulfillmentCutoverRequiredError, match="requires"):
        ActivitySyncService(repo, _config(), ProviderMustNotBeCalled()).run(today=date(2026, 7, 28))

    assert read_sync_progress(repo) is None


def test_sync_preflights_legacy_publication_without_completion_state(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    publication_path = repo.resolve_path("data/state/workout_publications.json")
    publication_path.parent.mkdir(parents=True, exist_ok=True)
    publication_path.write_text(
        '{"schema_version":6,"workouts":{},"pending":{},"drift_resolutions":[]}'
    )

    class ProviderMustNotBeCalled(SyncClient):
        def get_athlete(self):
            raise AssertionError("provider access must follow local cutover preflight")

    with pytest.raises(WorkoutFulfillmentCutoverRequiredError, match="requires"):
        ActivitySyncService(repo, _config(), ProviderMustNotBeCalled()).run(today=date(2026, 7, 28))

    assert read_sync_progress(repo) is None


def test_partial_retrieval_invalidates_previously_complete_window(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    write_sync_state(
        repo,
        ActivitySyncState(
            last_successful_incremental_at_utc=datetime(2026, 7, 27, tzinfo=timezone.utc),
            complete_activity_windows=[
                ActivityCoverageWindow(
                    start_date=date(2026, 7, 28),
                    end_date=date(2026, 7, 28),
                )
            ],
        ),
    )
    config = Config(
        settings=Settings(
            intervals_icu=IntervalsIcuSettings(
                history_start_date=date(2026, 7, 28),
                initial_window_days=90,
                list_limit=1,
            )
        ),
        intervals_icu_api_key="fake",
        loaded_at=datetime.now(timezone.utc),
    )

    report = ActivitySyncService(repo, config, SyncClient()).run(
        today=date(2026, 7, 28),
        full=True,
    )

    assert report.partial
    state = read_sync_state(repo)
    assert len(state.source_coverage_gaps) == 1
    assert state.source_coverage_gaps[0].start_date == date(2026, 7, 28)
    assert read_sync_progress(repo).phase == "partial"


def test_sync_commits_native_training_domains_without_inferred_load(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    class NativeSyncClient(SyncClient):
        def __init__(self):
            super().__init__()
            self.row = self.row.model_copy(
                update={
                    "icu_training_load": 64,
                    "hr_load": 64,
                    "load_order": "HR_PACE_POWER",
                    "icu_intensity": 78,
                }
            )

        def get_sport_settings(self, _athlete_id):
            return [
                SportSettingsDTO(
                    id=1,
                    types=["Run"],
                    lthr=170,
                    max_hr=190,
                    hr_zones=[135, 150, 162, 170, 177, 183, 190],
                    hr_zone_names=[
                        "Recovery",
                        "Aerobic",
                        "Tempo",
                        "SubThreshold",
                        "SuperThreshold",
                        "Aerobic Capacity",
                        "Anaerobic",
                    ],
                    hr_load_type="HRSS",
                    load_order="HR_PACE_POWER",
                    tiz_order="HR_PACE_POWER",
                    workout_order="PACE_HR_POWER",
                )
            ]

        def get_wellness(self, _oldest, _newest, *, athlete_id=None):
            return [
                WellnessDTO(
                    id="2026-07-28",
                    ctl=40,
                    atl=45,
                    rampRate=1.5,
                    restingHR=49,
                )
            ]

    report = ActivitySyncService(
        RepositoryIO(),
        _config(),
        NativeSyncClient(),
    ).run(today=date(2026, 7, 28))

    stored = ActivityArchive(tmp_path / "data" / "activities").load_all()[0]
    assert stored.aerobic_load is not None
    assert stored.aerobic_load.aerobic_load_points == 64
    assert not hasattr(stored, "calculated_load")
    assert report.activities_with_native_aerobic_load == 1
    assert report.wellness_days_received == 1
    assert report.wellness_days_changed == 1
    assert len(report.sport_settings_fingerprint_sha256) == 64
    wellness_payload = json.loads((tmp_path / "data" / "wellness" / "2026-07.json").read_text())
    assert wellness_payload[0]["fitness_load_points"] == 40
    settings_payload = json.loads((tmp_path / "data" / "state" / "sport_settings.json").read_text())
    assert settings_payload["settings"][0]["lactate_threshold_hr_bpm"] == 170


def test_wellness_transport_failure_leaves_all_active_state_unchanged(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    archive = tmp_path / "data" / "activities"
    archive.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    class FailedWellnessClient(SyncClient):
        def get_wellness(self, _oldest, _newest, *, athlete_id=None):
            raise IntervalsTransportError(
                "network",
                operation="get_wellness",
            )

    with pytest.raises(IntervalsTransportError):
        ActivitySyncService(
            RepositoryIO(),
            _config(),
            FailedWellnessClient(),
        ).run(today=date(2026, 7, 28))

    assert ActivityArchive(archive).load_all() == []
    assert not (tmp_path / "data" / "wellness").exists()
    assert not (tmp_path / "data" / "state" / "sport_settings.json").exists()


def _config() -> Config:
    return Config(
        settings=Settings(
            intervals_icu=IntervalsIcuSettings(
                history_start_date=date(2026, 7, 28),
                initial_window_days=90,
            )
        ),
        intervals_icu_api_key="fake",
        loaded_at=datetime.now(timezone.utc),
    )


def _linked_historical(activity_id: str = "external-1"):
    activity = make_activity(
        id="historical-local",
        date=date(2026, 7, 28),
        duration_seconds=2700,
        moving_seconds=2700,
        distance_meters=8000,
        name="Imported run",
    )
    return activity.model_copy(
        update={
            "origin": ActivityOrigin(
                kind=ActivityOriginKind.HISTORICAL_IMPORT,
                recording_provider=RecordingProvider.WAHOO,
                intervals_icu_activity_id=activity_id,
            ),
            "audit": ActivityAudit(
                imported_at_utc=activity.audit.imported_at_utc,
                provider_snapshot_sha256="0" * 64,
                performance_evidence_sha256="1" * 64,
                canonical_mapping_version=9,
            ),
        }
    )


def _publication(
    *,
    event_id: int = 42,
    workout_id: str = "planned-run",
) -> PublishedWorkout:
    return PublishedWorkout(
        workout_identity=PlanWorkoutIdentity(
            plan_id="plan_test",
            plan_revision_id="plan_revision_1111111111111111",
            week_number=1,
            local_workout_id=workout_id,
        ),
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        workout_prescription_sha256="2" * 64,
        schedule_timezone="Europe/Paris",
        event_id=event_id,
        requested_uid=f"uid-{workout_id}",
        uid=f"uid-{workout_id}",
        external_id=f"resilio:v1:workout:{workout_id}",
        publication_fingerprint_sha256="a" * 64,
        rendered_workout_sha256="b" * 64,
        sport_settings_version_sha256="c" * 64,
        provider_event_fingerprint_sha256="d" * 64,
        sport="run",
        occurrence_date=date(2026, 7, 28),
        approved_start_time_local=time(7),
        provider_start_date_local="2026-07-28T07:00:00",
        garmin_forwarding_status="eligible_unverified",
        verified_at_utc=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )


def _save_publication(repo: RepositoryIO, publication: PublishedWorkout) -> None:
    save_manifest(
        repo,
        PublicationManifest(workouts={publication.workout_identity.local_workout_id: publication}),
    )


def _publication_with_authority() -> tuple[PublishedWorkout, AuthoritativeWorkout]:
    publication = _publication()
    prescription = RunningWorkoutPrescription.model_validate(
        {
            "id": publication.workout_identity.local_workout_id,
            "date": publication.occurrence_date,
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
    authority = AuthoritativeWorkout(
        identity=publication.workout_identity,
        prescription=prescription,
        applied_week_approval_id=publication.applied_week_approval_id,
        applied_running_workouts_sha256=(publication.applied_running_workouts_sha256),
        schedule_timezone=publication.schedule_timezone,
    )
    return (
        publication.model_copy(
            update={"workout_prescription_sha256": canonical_data_sha256(prescription)}
        ),
        authority,
    )


def _fulfillment(
    *,
    local_activity_id: str,
    publication: PublishedWorkout,
) -> WorkoutFulfillmentRecord:
    return WorkoutFulfillmentRecord(
        local_activity_id=local_activity_id,
        workout_identity=publication.workout_identity,
        applied_week_approval_id=publication.applied_week_approval_id,
        applied_running_workouts_sha256=publication.applied_running_workouts_sha256,
        workout_prescription_sha256=publication.workout_prescription_sha256,
        activity_performance_evidence_sha256="9" * 64,
        schedule_timezone=publication.schedule_timezone,
        scheduled_local_date=publication.occurrence_date,
        execution_local_date=publication.occurrence_date,
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            provenance="provider_observed",
            event_id=publication.event_id,
            observed_at_utc=datetime(2026, 7, 29, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 29, tzinfo=timezone.utc),
    )


def test_immediate_repeat_sync_creates_zero_duplicates(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    config = _config()
    service = ActivitySyncService(
        repo,
        config,
        SyncClient(),
    )
    first = service.run(today=date(2026, 7, 28))
    second = service.run(today=date(2026, 7, 28))

    assert first.activities_created == 1
    assert second.activities_created == 0
    assert second.activities_unchanged == 1
    assert len(ActivityArchive(tmp_path / "data" / "activities").load_all()) == 1


def test_exact_paired_event_links_completion_idempotently(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    publication, authority = _publication_with_authority()
    _save_publication(repo, publication)
    monkeypatch.setattr(
        "resilio.core.activity_sync.staged_reconciliation." "load_approved_workouts_for_date_range",
        lambda *_args, **_kwargs: ApprovedWorkoutWindow(
            status="available",
            workouts=[authority],
        ),
    )
    client = SyncClient()
    client.row = client.row.model_copy(update={"paired_event_id": publication.event_id})
    service = ActivitySyncService(repo, _config(), client)

    first = service.run(today=date(2026, 7, 28))
    first_manifest = load_fulfillment_manifest(repo)
    second = service.run(today=date(2026, 7, 28))
    second_manifest = load_fulfillment_manifest(repo)
    client.row = client.row.model_copy(update={"paired_event_id": None})
    unpaired = service.run(today=date(2026, 7, 28))
    final_manifest = load_fulfillment_manifest(repo)

    local_activity_id = next(iter(first_manifest.fulfillments))
    assert first.workout_fulfillments_linked == 1
    assert second.workout_fulfillments_linked == 0
    assert first_manifest == second_manifest
    assert unpaired.partial
    assert unpaired.workout_provider_pairs_withdrawn == 0
    assert final_manifest.fulfillments == first_manifest.fulfillments
    assert local_activity_id in final_manifest.unresolved_fulfillment_conflicts
    assert (
        first_manifest.fulfillments[local_activity_id].workout_identity
        == publication.workout_identity
    )


def test_dismissed_candidate_blocks_later_automatic_provider_pair(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    publication, authority = _publication_with_authority()
    _save_publication(repo, publication)
    monkeypatch.setattr(
        "resilio.core.activity_sync.staged_reconciliation." "load_approved_workouts_for_date_range",
        lambda *_args, **_kwargs: ApprovedWorkoutWindow(
            status="available",
            workouts=[authority],
        ),
    )
    client = SyncClient()
    service = ActivitySyncService(repo, _config(), client)
    service.run(today=date(2026, 7, 28))
    activity = ActivityArchive(repo.resolve_path("data/activities")).load_all()[0]
    candidate = build_fulfillment_candidates(
        activity=activity,
        workout_authorities=[
            FulfillmentWorkoutAuthority(
                identity=authority.identity,
                prescription=authority.prescription,
                applied_week_approval_id=authority.applied_week_approval_id,
                applied_running_workouts_sha256=(authority.applied_running_workouts_sha256),
                schedule_timezone=authority.schedule_timezone,
            )
        ],
        manifest=WorkoutFulfillmentManifest(),
    )[0]
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(
            dismissed_candidates={
                candidate.candidate_sha256: WorkoutFulfillmentCandidateDismissal(
                    candidate_sha256=candidate.candidate_sha256,
                    local_activity_id=activity.local_activity_id,
                    workout_identity=authority.identity,
                    athlete_response_reference=(
                        "Athlete said this activity did not fulfill the workout."
                    ),
                    dismissed_at_utc=datetime(
                        2026,
                        7,
                        28,
                        9,
                        tzinfo=timezone.utc,
                    ),
                )
            }
        ),
    )
    client.row = client.row.model_copy(update={"paired_event_id": publication.event_id})

    report = service.run(today=date(2026, 7, 28))
    manifest = load_fulfillment_manifest(repo)

    assert report.partial
    assert manifest.fulfillments == {}
    assert (
        manifest.unresolved_fulfillment_conflicts[activity.local_activity_id].rule
        == "paired_event_fulfillment_was_dismissed"
    )


def test_running_activity_reclassification_durably_suspends_fulfillment(
    tmp_path,
    monkeypatch,
) -> None:
    repo, archive = _repo_with_linked_history(tmp_path, monkeypatch)
    publication = _publication()
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(
            fulfillments={
                "historical-local": _fulfillment(
                    local_activity_id="historical-local",
                    publication=publication,
                )
            }
        ),
    )
    client = SyncClient()
    client.row = client.row.model_copy(update={"type": "Ride"})

    first = ActivitySyncService(repo, _config(), client).run(today=date(2026, 7, 28))
    second = ActivitySyncService(repo, _config(), client).run(today=date(2026, 7, 28))

    assert first.partial and second.partial
    assert ActivityArchive(archive).load_all()[0].sport == "run"
    conflict = load_fulfillment_manifest(repo).unresolved_fulfillment_conflicts["historical-local"]
    assert conflict.rule == "fulfilled_activity_sport_changed"


@pytest.mark.parametrize(
    ("paired_event_id", "performance_matches", "expect_conflict"),
    [(41, True, False), (41, False, True), (42, True, True), (None, True, True)],
)
def test_historical_pair_never_promotes_to_active_fulfillment(
    tmp_path,
    monkeypatch,
    paired_event_id: int | None,
    performance_matches: bool,
    expect_conflict: bool,
) -> None:
    repo, _ = _repo_with_linked_history(tmp_path, monkeypatch)
    activity = _linked_historical()
    legacy_source = _publication(event_id=41, workout_id="historical-run")
    historical_publication = HistoricalLegacyWorkoutPublication.model_validate(
        legacy_source.model_dump(
            mode="python",
            exclude={
                "applied_week_approval_id",
                "applied_running_workouts_sha256",
                "workout_prescription_sha256",
                "schedule_timezone",
            },
        )
    )
    current_publication = _publication(event_id=42, workout_id="current-run")
    client = SyncClient()
    client.row = client.row.model_copy(update={"paired_event_id": paired_event_id})
    reconciled_activity = merge_reviewed_activity(
        activity,
        map_activity(client.row, default_timezone="Europe/Paris"),
    )
    save_manifest(
        repo,
        PublicationManifest(
            workouts={"current-run": current_publication},
            historical_legacy_workouts={"historical-run": historical_publication},
        ),
    )
    historical_fulfillment = HistoricalLegacyWorkoutFulfillment(
        local_activity_id=activity.local_activity_id,
        workout_identity=historical_publication.workout_identity,
        activity_performance_evidence_sha256=(
            activity_performance_evidence_sha256(reconciled_activity)
            if performance_matches
            else "f" * 64
        ),
        scheduled_local_date=historical_publication.occurrence_date,
        execution_local_date=activity.occurrence.local_date,
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            provenance="provider_observed",
            event_id=historical_publication.event_id,
            observed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
        ),
        matched_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(
            historical_legacy_fulfillments={activity.local_activity_id: historical_fulfillment}
        ),
    )
    report = ActivitySyncService(repo, _config(), client).run(today=date(2026, 7, 28))
    manifest = load_fulfillment_manifest(repo)

    assert report.partial is expect_conflict
    assert manifest.fulfillments == {}
    assert activity.local_activity_id in manifest.historical_legacy_fulfillments
    assert (
        activity.local_activity_id in manifest.unresolved_fulfillment_conflicts
    ) is expect_conflict


def test_unpaired_activity_is_not_automatically_linked(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    publication = _publication()
    _save_publication(repo, publication)

    report = ActivitySyncService(repo, _config(), SyncClient()).run(today=date(2026, 7, 28))

    assert not report.partial
    assert report.workout_fulfillments_linked == 0
    assert load_fulfillment_manifest(repo).fulfillments == {}
    artifact = json.loads(
        next((tmp_path / "data" / "state" / "sync-runs").rglob("quarantine.json")).read_text()
    )
    assert "completion_candidates" not in artifact


def test_paired_event_sport_mismatch_fails_safe_without_completion_link(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    publication = _publication()
    _save_publication(repo, publication)
    client = SyncClient()
    client.row = client.row.model_copy(
        update={
            "type": "Ride",
            "paired_event_id": publication.event_id,
        }
    )

    report = ActivitySyncService(repo, _config(), client).run(today=date(2026, 7, 28))

    assert report.partial
    assert report.quarantined_rows == 1
    assert report.workout_fulfillments_linked == 0
    assert load_fulfillment_manifest(repo).fulfillments == {}
    artifact = json.loads(
        next((tmp_path / "data" / "state" / "sync-runs").rglob("quarantine.json")).read_text()
    )
    assert artifact["ambiguous_decisions"][0]["rule"] == ("paired_event_sport_mismatch")


def test_invalid_external_row_is_quarantined_without_archive_write(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    config = _config()
    client = SyncClient()
    client.row = client.row.model_copy(update={"type": "UnknownFutureSport"})

    report = ActivitySyncService(repo, config, client).run(today=date(2026, 7, 28))

    assert report.partial
    assert report.quarantined_rows == 1
    assert ActivityArchive(tmp_path / "data" / "activities").load_all() == []
    quarantine = next(
        (tmp_path / "data" / "state" / "sync-runs").rglob("quarantine.json")
    ).read_text()
    assert "external-1" not in quarantine


def test_ambiguous_decision_artifact_hashes_external_id() -> None:
    payload = _sanitized_decision(
        ReconciliationDecision(
            action=ReconciliationAction.AMBIGUOUS,
            rule="review_window_candidates",
            external_activity_id="external-sensitive-id",
            candidate_local_ids=["act_h_safe"],
        )
    )

    assert "external_activity_id" not in payload
    assert payload["external_activity_id_sha256"] == (
        "cc1c8adb6d6fe06d59abf1d7218b35d1e1d5d6cd8c63eca411b12e8f46a0d3f0"
    )


class ReconciliationClient(SyncClient):
    def __init__(self, rows, *, detail_result=None, detail_error=None):
        super().__init__()
        self.rows = rows
        self.detail_result = detail_result
        self.detail_error = detail_error

    def list_activities(self, *_args, **_kwargs):
        return self.rows

    def get_activities(self, ids, **_kwargs):
        complete = [row for row in self.rows if isinstance(row, ActivityDTO)]
        return [row for row in complete if row.id in ids]

    def get_activity(self, _activity_id, **_kwargs):
        if self.detail_error is not None:
            raise self.detail_error
        return self.detail_result or self.row


def _repo_with_linked_history(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    archive = tmp_path / "data" / "activities"
    archive.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    ActivityArchive(archive).write(_linked_historical())
    return RepositoryIO(), archive


def test_hidden_list_row_never_becomes_a_deletion_candidate(
    tmp_path,
    monkeypatch,
) -> None:
    repo, archive = _repo_with_linked_history(tmp_path, monkeypatch)
    hidden = HiddenActivityDTO(
        id="external-1",
        start_date_local="2026-07-28T07:00:00+02:00",
        _note="Unavailable through this API",
    )
    client = ReconciliationClient(
        [hidden],
        detail_error=IntervalsNotFoundError(
            "not found",
            operation="get_activity",
            status_code=404,
        ),
    )

    report = ActivitySyncService(repo, _config(), client).run(
        today=date(2026, 7, 28),
        full=True,
        confirm_deletions=True,
    )

    restored = ActivityArchive(archive).load_all()[0]
    assert not report.partial
    assert report.hidden_rows == 1
    assert report.activities_tombstoned == 0
    assert restored.status == ActivityStatus.ACTIVE
    state = read_sync_state(repo)
    assert state.schema_version == 3
    assert len(state.source_coverage_exclusions) == 1
    exclusion = state.source_coverage_exclusions[0]
    assert exclusion.reason == "source_hidden"
    assert exclusion.local_date == date(2026, 7, 28)
    assert exclusion.source_recording_provider is None
    assert "external-1" not in exclusion.model_dump_json()


def test_list_omission_with_successful_detail_is_partial_not_deleted(
    tmp_path,
    monkeypatch,
) -> None:
    repo, archive = _repo_with_linked_history(tmp_path, monkeypatch)
    report = ActivitySyncService(
        repo,
        _config(),
        ReconciliationClient([], detail_result=_activity("external-1")),
    ).run(
        today=date(2026, 7, 28),
        full=True,
        confirm_deletions=True,
    )

    assert report.partial
    assert report.activities_tombstoned == 0
    assert "still exists" in report.errors[0]
    assert ActivityArchive(archive).load_all()[0].status == ActivityStatus.ACTIVE


def test_confirmed_404_tombstones_exact_linked_record(
    tmp_path,
    monkeypatch,
) -> None:
    repo, archive = _repo_with_linked_history(tmp_path, monkeypatch)
    client = ReconciliationClient(
        [],
        detail_error=IntervalsNotFoundError(
            "not found",
            operation="get_activity",
            status_code=404,
        ),
    )

    report = ActivitySyncService(repo, _config(), client).run(
        today=date(2026, 7, 28),
        full=True,
        confirm_deletions=True,
    )

    tombstone = ActivityArchive(archive).load_all()[0]
    assert not report.partial
    assert report.activities_tombstoned == 1
    assert tombstone.status == ActivityStatus.EXTERNAL_DELETED
    assert tombstone.origin.intervals_icu_activity_id == "external-1"
    assert not hasattr(tombstone, "calculated_load")


def test_confirmed_404_durably_suspends_fulfillment_before_tombstone(
    tmp_path,
    monkeypatch,
) -> None:
    repo, archive = _repo_with_linked_history(tmp_path, monkeypatch)
    publication = _publication()
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(
            fulfillments={
                "historical-local": _fulfillment(
                    local_activity_id="historical-local",
                    publication=publication,
                )
            }
        ),
    )
    client = ReconciliationClient(
        [],
        detail_error=IntervalsNotFoundError(
            "not found",
            operation="get_activity",
            status_code=404,
        ),
    )

    report = ActivitySyncService(repo, _config(), client).run(
        today=date(2026, 7, 28),
        full=True,
        confirm_deletions=True,
    )

    assert report.partial
    assert report.activities_tombstoned == 0
    assert ActivityArchive(archive).load_all()[0].status == ActivityStatus.ACTIVE
    conflict = load_fulfillment_manifest(repo).unresolved_fulfillment_conflicts["historical-local"]
    assert conflict.rule == "fulfilled_activity_provider_deleted"


def test_unconfirmed_404_is_exposed_in_local_deletion_review(
    tmp_path,
    monkeypatch,
) -> None:
    repo, archive = _repo_with_linked_history(tmp_path, monkeypatch)
    client = ReconciliationClient(
        [],
        detail_error=IntervalsNotFoundError(
            "not found",
            operation="get_activity",
            status_code=404,
        ),
    )

    report = ActivitySyncService(repo, _config(), client).run(
        today=date(2026, 7, 28),
        full=True,
        confirm_deletions=False,
    )
    reviews = list_external_deletion_reviews(repo)

    assert report.partial
    assert report.activities_tombstoned == 0
    assert ActivityArchive(archive).load_all()[0].status == (ActivityStatus.ACTIVE)
    assert len(reviews) == 1
    assert reviews[0].local_activity_id == "historical-local"
    assert reviews[0].local_date == date(2026, 7, 28)
    assert reviews[0].sport == "run"


def test_deletion_confirmation_transport_failure_retains_active_record(
    tmp_path,
    monkeypatch,
) -> None:
    repo, archive = _repo_with_linked_history(tmp_path, monkeypatch)
    client = ReconciliationClient(
        [],
        detail_error=IntervalsTransportError(
            "network",
            operation="get_activity",
        ),
    )

    report = ActivitySyncService(repo, _config(), client).run(
        today=date(2026, 7, 28),
        full=True,
        confirm_deletions=True,
    )

    assert report.partial
    assert report.activities_tombstoned == 0
    assert "transport" in report.errors[0]
    assert ActivityArchive(archive).load_all()[0].status == ActivityStatus.ACTIVE


def test_batch_detail_extra_id_fails_partial_without_archive_write(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    archive = tmp_path / "data" / "activities"
    archive.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    class ExtraDetailClient(SyncClient):
        def get_activities(self, _ids, **_kwargs):
            return [self.row, _activity("unrequested")]

    report = ActivitySyncService(
        RepositoryIO(),
        _config(),
        ExtraDetailClient(),
    ).run(today=date(2026, 7, 28), full=True)

    assert report.partial
    assert report.quarantined_rows == 1
    assert "unrequested" in report.errors[0]
    assert ActivityArchive(archive).load_all() == []


def test_sync_state_failure_restores_workout_fulfillment_manifest(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    archive = tmp_path / "data" / "activities"
    archive.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    old_publication = _publication(workout_id="older-workout")
    old_publication = old_publication.model_copy(
        update={
            "workout_identity": PlanWorkoutIdentity(
                plan_id="plan_old",
                plan_revision_id="plan_revision_2222222222222222",
                week_number=1,
                local_workout_id="older-workout",
            )
        }
    )
    old_fulfillment = _fulfillment(
        local_activity_id="act_h_0123456789abcdef01234567",
        publication=old_publication,
    )
    original_manifest = WorkoutFulfillmentManifest(
        fulfillments={old_fulfillment.local_activity_id: old_fulfillment}
    )
    save_fulfillment_manifest(repo, original_manifest)
    publication = _publication()
    _save_publication(repo, publication)
    client = SyncClient()
    client.row = client.row.model_copy(update={"paired_event_id": publication.event_id})

    def fail_state_write(*_args, **_kwargs):
        raise RuntimeError("simulated state failure")

    monkeypatch.setattr(
        "resilio.core.activity_sync.service.write_sync_state",
        fail_state_write,
    )
    with pytest.raises(RuntimeError, match="simulated state failure"):
        ActivitySyncService(repo, _config(), client).run(today=date(2026, 7, 28))

    assert ActivityArchive(archive).load_all() == []
    assert load_fulfillment_manifest(repo) == original_manifest


def test_fulfillment_save_revalidates_mutated_mapping(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    publication = _publication()
    first = _fulfillment(
        local_activity_id="act_h_0123456789abcdef01234567",
        publication=publication,
    )
    manifest = WorkoutFulfillmentManifest(fulfillments={first.local_activity_id: first})
    second = first.model_copy(update={"local_activity_id": "act_h_89abcdef0123456701234567"})
    manifest.fulfillments[second.local_activity_id] = second

    with pytest.raises(
        ValueError,
        match="cannot fulfill multiple activities",
    ):
        save_fulfillment_manifest(repo, manifest)


def test_interrupted_archive_swap_is_recovered_before_retry(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    archive = tmp_path / "data" / "activities"
    archive.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    service = ActivitySyncService(repo, _config(), SyncClient())

    real_replace = __import__(
        "resilio.core.activity_sync.service",
        fromlist=["os"],
    ).os.replace
    interrupted = False

    def interrupt_after_candidate_swap(source, target):
        nonlocal interrupted
        source_path = Path(source)
        target_path = Path(target)
        is_candidate_swap = (
            not interrupted
            and source_path.name == "archive"
            and "sync-runs" in source_path.parts
            and target_path == archive
        )
        result = real_replace(source, target)
        if is_candidate_swap:
            interrupted = True
            raise KeyboardInterrupt("simulated process interruption")
        return result

    monkeypatch.setattr(
        "resilio.core.activity_sync.service.os.replace",
        interrupt_after_candidate_swap,
    )

    with pytest.raises(KeyboardInterrupt, match="process interruption"):
        service.run(today=date(2026, 7, 28))

    assert len(ActivityArchive(archive).load_all()) == 1
    recovered = service.run(today=date(2026, 7, 28))

    assert recovered.activities_created == 1
    assert len(ActivityArchive(archive).load_all()) == 1
    assert read_sync_progress(repo) is None
    interrupted_archives = list(
        (tmp_path / "data" / "state" / "sync-runs").glob("*/interrupted-archive")
    )
    assert len(interrupted_archives) == 1
