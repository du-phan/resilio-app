"""Source-aware completed-activity presentation tests."""

from datetime import date, datetime, timezone

from resilio.cli.commands.activity import (
    GARMIN_DATA_ATTRIBUTION,
    _load_activities_in_range,
    _search_activities,
)
from resilio.core.repository import RepositoryIO
from resilio.schemas.activity import (
    ActivityAudit,
    ActivityOrigin,
    ActivityOriginKind,
    RecordingProvider,
)
from tests.factories import make_activity


def test_garmin_activity_list_and_search_include_attribution(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    activity = make_activity(
        id="garmin-run",
        date=date(2026, 7, 28),
        sport="run",
        recording_provider="garmin",
        description="Controlled progression",
    )
    repo.write_yaml("data/activities/2026-07/garmin-run.yaml", activity)

    listed = _load_activities_in_range(
        repo,
        date(2026, 7, 28),
        date(2026, 7, 28),
    )
    searched = _search_activities(listed, "progression")

    assert listed[0]["attribution"] == GARMIN_DATA_ATTRIBUTION
    assert searched[0]["attribution"] == GARMIN_DATA_ATTRIBUTION


def test_non_garmin_activity_has_no_garmin_attribution(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    activity = make_activity(
        id="wahoo-ride",
        date=date(2026, 7, 28),
        sport="cycle",
        recording_provider="wahoo",
    )
    repo.write_yaml("data/activities/2026-07/wahoo-ride.yaml", activity)

    listed = _load_activities_in_range(
        repo,
        date(2026, 7, 28),
        date(2026, 7, 28),
    )

    assert listed[0]["attribution"] is None


def test_deleted_activity_is_excluded_from_active_list(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    deleted = make_activity(
        id="deleted-run",
        date=date(2026, 7, 28),
        sport="run",
    ).model_copy(
        update={
            "status": "external_deleted",
            "origin": ActivityOrigin(
                kind=ActivityOriginKind.HISTORICAL_IMPORT,
                recording_provider=RecordingProvider.GARMIN,
                intervals_icu_activity_id="deleted-external",
            ),
        }
    )
    repo.write_yaml("data/activities/2026-07/deleted-run.yaml", deleted)

    listed = _load_activities_in_range(
        repo,
        date(2026, 7, 28),
        date(2026, 7, 28),
    )

    assert listed == []


def test_activity_list_exposes_exact_vdot_source_identity(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    source_fingerprint = "a" * 64
    activity = make_activity(
        id="act_i_race_source",
        date=date(2026, 7, 20),
        sport="run",
        duration_seconds=2_550,
        moving_seconds=2_540,
        distance_meters=10_000,
    ).model_copy(
        update={
            "audit": ActivityAudit(
                imported_at_utc=datetime(2026, 7, 20, 9, tzinfo=timezone.utc),
                provider_snapshot_sha256=source_fingerprint,
                performance_evidence_sha256="b" * 64,
                canonical_mapping_version=9,
            )
        }
    )
    repo.write_yaml(
        "data/activities/2026-07/act_i_race_source.yaml",
        activity,
    )

    listed = _load_activities_in_range(
        repo,
        date(2026, 7, 20),
        date(2026, 7, 20),
    )

    assert listed[0]["elapsed_duration_seconds"] == 2_550
    assert listed[0]["activity_timezone"] == "UTC"
    assert listed[0]["provider_snapshot_sha256"] == source_fingerprint
    assert listed[0]["performance_evidence_sha256"] == "b" * 64
