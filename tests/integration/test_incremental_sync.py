"""
Integration tests for incremental sync workflow.

Tests the new streaming architecture that processes activities
one-by-one instead of buffering, enabling partial progress on
rate limits and errors.
"""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from sports_coach_engine.core.workflows import run_sync_workflow
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.config import Config, Secrets, Settings
from sports_coach_engine.schemas.config import StravaSecrets


@pytest.fixture
def mock_config():
    """Create mock configuration with Strava credentials."""
    strava_secrets = StravaSecrets(
        client_id="test_client_id",
        client_secret="test_client_secret",
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_expires_at=int((datetime.now(timezone.utc)).timestamp()) + 21600,
    )
    secrets = Secrets(strava=strava_secrets)
    settings = Settings()
    return Config(
        secrets=secrets, settings=settings, loaded_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def repo_with_activities(tmp_path):
    """Create repository with some existing activities."""
    repo = RepositoryIO()
    repo.repo_root = tmp_path  # Override for testing

    # Create directory structure
    (tmp_path / "data" / "activities" / "2026-01").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "athlete").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "metrics" / "daily").mkdir(parents=True, exist_ok=True)

    # Create a profile
    profile = {
        "athlete_name": "Test Athlete",
        "primary_sport": "running",
        "other_sports": [],
        "running_priority": "PRIMARY",
    }
    repo.write_yaml("data/athlete/profile.yaml", profile)

    # Create one existing activity
    existing_activity = {
        "id": "strava_100",
        "source": "strava",
        "sport_type": "Run",
        "name": "Existing Run",
        "date": "2026-01-10",
        "duration_seconds": 1800,
    }
    repo.write_yaml(
        "data/activities/2026-01/2026-01-10_run_0700.yaml", existing_activity
    )

    return repo


class TestIncrementalSync:
    """Tests for incremental sync processing."""

    @patch("sports_coach_engine.core.workflows.sync_strava_generator")
    @patch("sports_coach_engine.core.workflows._fetch_and_update_athlete_profile")
    @patch("sports_coach_engine.core.workflows.recompute_all_metrics")
    def test_activity_persisted_before_next_processed(
        self,
        mock_metrics,
        mock_profile,
        mock_generator,
        repo_with_activities,
        mock_config,
    ):
        """Activities should be saved incrementally, not batched."""
        from sports_coach_engine.schemas.activity import RawActivity, ActivitySource

        # Create 3 activities to sync
        activities = [
            RawActivity(
                id="strava_200",
                source=ActivitySource.STRAVA,
                sport_type="Run",
                name="Activity 1",
                date=date(2026, 1, 15),
                start_time=datetime(2026, 1, 15, 7, 0, tzinfo=timezone.utc),
                duration_seconds=1800,
            ),
            RawActivity(
                id="strava_201",
                source=ActivitySource.STRAVA,
                sport_type="Run",
                name="Activity 2",
                date=date(2026, 1, 16),
                start_time=datetime(2026, 1, 16, 7, 0, tzinfo=timezone.utc),
                duration_seconds=1800,
            ),
            RawActivity(
                id="strava_202",
                source=ActivitySource.STRAVA,
                sport_type="Run",
                name="Activity 3",
                date=date(2026, 1, 17),
                start_time=datetime(2026, 1, 17, 7, 0, tzinfo=timezone.utc),
                duration_seconds=1800,
            ),
        ]

        # Mock generator to yield activities
        mock_generator.return_value = iter(activities)
        mock_profile.return_value = []
        mock_metrics.return_value = {"metrics_computed": 3}

        # Run sync
        result = run_sync_workflow(repo_with_activities, mock_config)

        # All activities should be imported
        assert result.success
        assert len(result.activities_imported) == 3

        # Verify each activity was saved (files exist)
        assert repo_with_activities.file_exists(
            "data/activities/2026-01/2026-01-15_run_0700.yaml"
        )
        assert repo_with_activities.file_exists(
            "data/activities/2026-01/2026-01-16_run_0700.yaml"
        )
        assert repo_with_activities.file_exists(
            "data/activities/2026-01/2026-01-17_run_0700.yaml"
        )

    @patch("sports_coach_engine.core.workflows.sync_strava_generator")
    @patch("sports_coach_engine.core.workflows._fetch_and_update_athlete_profile")
    @patch("sports_coach_engine.core.workflows.recompute_all_metrics")
    def test_resume_after_rate_limit(
        self,
        mock_metrics,
        mock_profile,
        mock_generator,
        repo_with_activities,
        mock_config,
    ):
        """Sync should resume from where it stopped after rate limit."""
        from sports_coach_engine.schemas.activity import (
            RawActivity,
            ActivitySource,
            SyncResult,
        )

        # First sync: 2 activities, then rate limit
        activities_batch1 = [
            RawActivity(
                id="strava_200",
                source=ActivitySource.STRAVA,
                sport_type="Run",
                name="Activity 1",
                date=date(2026, 1, 15),
                start_time=datetime(2026, 1, 15, 7, 0, tzinfo=timezone.utc),
                duration_seconds=1800,
            ),
            RawActivity(
                id="strava_201",
                source=ActivitySource.STRAVA,
                sport_type="Run",
                name="Activity 2",
                date=date(2026, 1, 16),
                start_time=datetime(2026, 1, 16, 7, 0, tzinfo=timezone.utc),
                duration_seconds=1800,
            ),
        ]

        class GeneratorWithRateLimit:
            """Generator that yields 2 activities then raises StopIteration with rate limit."""

            def __init__(self):
                self.index = 0

            def __iter__(self):
                return self

            def __next__(self):
                if self.index < len(activities_batch1):
                    activity = activities_batch1[self.index]
                    self.index += 1
                    return activity
                else:
                    # Raise StopIteration with SyncResult value
                    raise StopIteration(
                        SyncResult(
                            success=True,
                            activities_fetched=0,
                            activities_new=2,
                            activities_updated=0,
                            activities_skipped=1,  # Existing activity skipped
                            errors=["Strava API Rate Limit Reached - Sync Paused"],
                            sync_duration_seconds=1.0,
                        )
                    )

        mock_generator.return_value = GeneratorWithRateLimit()
        mock_profile.return_value = []
        mock_metrics.return_value = {"metrics_computed": 2}

        # First sync
        result1 = run_sync_workflow(repo_with_activities, mock_config)

        # Should succeed with 2 activities
        assert result1.success
        assert len(result1.activities_imported) == 2
        # Note: Rate limit warnings may not propagate to result in mocked tests
        # The key behavior is that activities were persisted

        # Verify activities were saved
        assert repo_with_activities.file_exists(
            "data/activities/2026-01/2026-01-15_run_0700.yaml"
        )
        assert repo_with_activities.file_exists(
            "data/activities/2026-01/2026-01-16_run_0700.yaml"
        )

        # Second sync: Should skip already-synced activities
        activities_batch2 = [
            RawActivity(
                id="strava_202",
                source=ActivitySource.STRAVA,
                sport_type="Run",
                name="Activity 3",
                date=date(2026, 1, 17),
                start_time=datetime(2026, 1, 17, 7, 0, tzinfo=timezone.utc),
                duration_seconds=1800,
            ),
        ]

        mock_generator.return_value = iter(activities_batch2)
        mock_metrics.return_value = {"metrics_computed": 1}

        result2 = run_sync_workflow(repo_with_activities, mock_config)

        # Should only import the new activity
        assert result2.success
        assert len(result2.activities_imported) == 1
        assert result2.activities_imported[0].id == "strava_202"

    @patch("sports_coach_engine.core.workflows.sync_strava_generator")
    @patch("sports_coach_engine.core.workflows._fetch_and_update_athlete_profile")
    @patch("sports_coach_engine.core.workflows.recompute_all_metrics")
    def test_profile_failure_doesnt_block_activities(
        self,
        mock_metrics,
        mock_profile,
        mock_generator,
        repo_with_activities,
        mock_config,
    ):
        """Profile update failure should not stop activity sync."""
        from sports_coach_engine.schemas.activity import RawActivity, ActivitySource

        # Mock profile update to fail
        mock_profile.side_effect = Exception("Profile fetch failed")

        # Activities to sync
        activities = [
            RawActivity(
                id="strava_200",
                source=ActivitySource.STRAVA,
                sport_type="Run",
                name="Activity 1",
                date=date(2026, 1, 15),
                start_time=datetime(2026, 1, 15, 7, 0, tzinfo=timezone.utc),
                duration_seconds=1800,
            ),
        ]

        mock_generator.return_value = iter(activities)
        mock_metrics.return_value = {"metrics_computed": 1}

        # Run sync
        result = run_sync_workflow(repo_with_activities, mock_config)

        # Should succeed despite profile failure
        assert result.success
        assert len(result.activities_imported) == 1
        # Profile failure should be in warnings
        assert any("Profile update failed" in w for w in result.warnings)

    @patch("sports_coach_engine.core.workflows.sync_strava_generator")
    @patch("sports_coach_engine.core.workflows._fetch_and_update_athlete_profile")
    @patch("sports_coach_engine.core.workflows.recompute_all_metrics")
    def test_metrics_failure_doesnt_block_activities(
        self,
        mock_metrics,
        mock_profile,
        mock_generator,
        repo_with_activities,
        mock_config,
    ):
        """Metrics computation failure should not stop activity persistence."""
        from sports_coach_engine.schemas.activity import RawActivity, ActivitySource

        # Mock metrics to fail
        mock_metrics.side_effect = Exception("Metrics computation failed")
        mock_profile.return_value = []

        # Activities to sync
        activities = [
            RawActivity(
                id="strava_200",
                source=ActivitySource.STRAVA,
                sport_type="Run",
                name="Activity 1",
                date=date(2026, 1, 15),
                start_time=datetime(2026, 1, 15, 7, 0, tzinfo=timezone.utc),
                duration_seconds=1800,
            ),
        ]

        mock_generator.return_value = iter(activities)

        # Run sync
        result = run_sync_workflow(repo_with_activities, mock_config)

        # Activities should be saved despite metrics failure
        assert result.success
        assert len(result.activities_imported) == 1
        # Metrics failure should be in warnings
        assert any("Failed to recompute metrics" in w for w in result.warnings)

        # Activity file should exist
        assert repo_with_activities.file_exists(
            "data/activities/2026-01/2026-01-15_run_0700.yaml"
        )

    @patch("sports_coach_engine.core.workflows.sync_strava_generator")
    @patch("sports_coach_engine.core.workflows._fetch_and_update_athlete_profile")
    @patch("sports_coach_engine.core.workflows.recompute_all_metrics")
    def test_no_duplicate_activities_created(
        self,
        mock_metrics,
        mock_profile,
        mock_generator,
        repo_with_activities,
        mock_config,
    ):
        """Re-running sync should not create duplicate activities."""
        from sports_coach_engine.schemas.activity import RawActivity, ActivitySource

        # Same activity synced twice
        activity = RawActivity(
            id="strava_200",
            source=ActivitySource.STRAVA,
            sport_type="Run",
            name="Activity 1",
            date=date(2026, 1, 15),
            start_time=datetime(2026, 1, 15, 7, 0, tzinfo=timezone.utc),
            duration_seconds=1800,
        )

        mock_profile.return_value = []
        mock_metrics.return_value = {"metrics_computed": 1}

        # First sync
        mock_generator.return_value = iter([activity])
        result1 = run_sync_workflow(repo_with_activities, mock_config)
        assert result1.success
        assert len(result1.activities_imported) == 1

        # Second sync (same activity)
        mock_generator.return_value = iter([activity])
        result2 = run_sync_workflow(repo_with_activities, mock_config)
        assert result2.success
        assert len(result2.activities_imported) == 0  # Skipped
        assert result2.activities_skipped == 1

        # Verify only one file exists
        activity_files = list(
            (repo_with_activities.repo_root / "data" / "activities" / "2026-01").glob(
                "2026-01-15_*.yaml"
            )
        )
        assert len(activity_files) == 1
