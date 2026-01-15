"""
Unit tests for workflow deduplication behavior in Strava sync.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.core import workflows
from sports_coach_engine.schemas.activity import NormalizedActivity, SportType
from sports_coach_engine.schemas.config import Config, Settings, Secrets, StravaSecrets


@pytest.fixture
def temp_repo(tmp_path, monkeypatch):
    """Create temporary repository for testing."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return RepositoryIO()


def _make_activity(
    activity_id: str,
    activity_date: date,
    start_time: datetime,
    duration_seconds: int,
    sport_type: SportType = SportType.RUN,
) -> NormalizedActivity:
    return NormalizedActivity(
        id=activity_id,
        source="strava",
        sport_type=sport_type,
        name="Test Activity",
        date=activity_date,
        start_time=start_time,
        duration_minutes=duration_seconds // 60,
        duration_seconds=duration_seconds,
        created_at=start_time,
        updated_at=start_time,
    )


def _make_config() -> Config:
    return Config(
        settings=Settings(),
        secrets=Secrets(
            strava=StravaSecrets(
                client_id="client",
                client_secret="secret",
                access_token="token",
                refresh_token="refresh",
                token_expires_at=0,
            )
        ),
        loaded_at=datetime.now(timezone.utc),
    )


def test_is_fuzzy_duplicate_matches_time_and_duration():
    activity_date = date(2026, 1, 12)
    start_time = datetime(2026, 1, 12, 7, 0, tzinfo=timezone.utc)
    existing = _make_activity("manual_1", activity_date, start_time, 3600)
    near_match = _make_activity(
        "strava_2",
        activity_date,
        start_time + timedelta(minutes=20),
        3600,
    )
    far_time = _make_activity(
        "strava_3",
        activity_date,
        start_time + timedelta(minutes=45),
        3600,
    )

    assert workflows._is_fuzzy_duplicate(near_match, [existing]) is True
    assert workflows._is_fuzzy_duplicate(far_time, [existing]) is False


def test_sync_workflow_skips_existing_strava_id(temp_repo, monkeypatch):
    activity_date = date(2026, 1, 12)
    start_time = datetime(2026, 1, 12, 7, 0, tzinfo=timezone.utc)
    existing = _make_activity("strava_123", activity_date, start_time, 3600)
    existing_path = "data/activities/2026-01/2026-01-12_run_0700.yaml"
    temp_repo.write_yaml(existing_path, existing)

    config = _make_config()

    monkeypatch.setattr(workflows, "_fetch_and_update_athlete_profile", lambda *_: None)

    def fake_fetch_activities(config, page, per_page, after):
        if page == 1:
            return [{"id": 123}]
        return []

    fetch_details = MagicMock()

    monkeypatch.setattr(workflows, "fetch_activities", fake_fetch_activities)
    monkeypatch.setattr(workflows, "fetch_activity_details", fetch_details)
    monkeypatch.setattr(workflows.time, "sleep", lambda *_: None)

    result = workflows.run_sync_workflow(
        temp_repo,
        config,
        since=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert result.success is True
    assert result.activities_skipped == 1
    assert len(result.activities_imported) == 0
    assert fetch_details.call_count == 0
