"""
Integration tests for incremental sync workflow.

Tests the new streaming architecture that processes activities
one-by-one instead of buffering, enabling partial progress on
rate limits and errors.
"""

import json

import pytest
import yaml
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from sports_coach_engine.core.workflows import run_sync_workflow
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.config import Config, Secrets, Settings
from sports_coach_engine.schemas.config import StravaSecrets
from sports_coach_engine.schemas.sync import SyncPhase, SyncReport


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
        assert result.phase == SyncPhase.DONE
        assert result.activities_imported == 3

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
                    # Raise StopIteration with SyncReport value
                    raise StopIteration(
                        SyncReport(
                            activities_imported=2,
                            activities_skipped=1,  # Existing activity skipped
                            activities_failed=0,
                            laps_fetched=0,
                            laps_skipped_age=0,
                            lap_fetch_failures=0,
                            phase=SyncPhase.PAUSED_RATE_LIMIT,
                            rate_limited=True,
                            errors=["Strava API Rate Limit Reached - Sync Paused"],
                        )
                    )

        mock_generator.return_value = GeneratorWithRateLimit()
        mock_profile.return_value = []
        mock_metrics.return_value = {"metrics_computed": 2}

        # First sync
        result1 = run_sync_workflow(repo_with_activities, mock_config)

        # Should succeed with 2 activities
        assert result1.phase == SyncPhase.PAUSED_RATE_LIMIT
        assert result1.activities_imported == 2

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
        assert result2.phase == SyncPhase.DONE
        assert result2.activities_imported == 1

    @patch("sports_coach_engine.core.workflows.sync_strava_generator")
    @patch("sports_coach_engine.core.workflows._fetch_and_update_athlete_profile")
    @patch("sports_coach_engine.core.workflows.recompute_all_metrics")
    def test_rate_limit_persists_resume_cursor_state(
        self,
        mock_metrics,
        mock_profile,
        mock_generator,
        repo_with_activities,
        mock_config,
    ):
        """Rate-limit pause should persist backfill/resume cursor state."""
        from sports_coach_engine.schemas.activity import ActivitySource, RawActivity

        raw_activity = RawActivity(
            id="strava_300",
            source=ActivitySource.STRAVA,
            sport_type="Run",
            name="Activity RL",
            date=date(2026, 1, 18),
            start_time=datetime(2026, 1, 18, 7, 0, tzinfo=timezone.utc),
            duration_seconds=1800,
        )

        def generator_factory(*args, **kwargs):
            progress_hook = kwargs.get("progress_hook")

            class _Gen:
                def __init__(self):
                    self._idx = 0

                def __iter__(self):
                    return self

                def __next__(self):
                    if self._idx == 0:
                        if progress_hook:
                            progress_hook(
                                {
                                    "phase": "fetching",
                                    "current_page": 1,
                                    "activities_seen": 0,
                                    "cursor_before_timestamp": 1736500000,
                                }
                            )
                        self._idx += 1
                        return raw_activity
                    raise StopIteration(
                        SyncReport(
                            activities_imported=1,
                            activities_skipped=0,
                            activities_failed=0,
                            laps_fetched=0,
                            laps_skipped_age=0,
                            lap_fetch_failures=0,
                            phase=SyncPhase.PAUSED_RATE_LIMIT,
                            rate_limited=True,
                            errors=["Strava API Rate Limit Reached - Sync Paused"],
                        )
                    )

            return _Gen()

        mock_generator.side_effect = generator_factory
        mock_profile.return_value = []
        mock_metrics.return_value = {"metrics_computed": 1}

        since = datetime(2025, 2, 12, tzinfo=timezone.utc)
        result = run_sync_workflow(repo_with_activities, mock_config, since=since)

        assert result.phase == SyncPhase.PAUSED_RATE_LIMIT

        training_history = yaml.safe_load(
            (repo_with_activities.repo_root / "data" / "athlete" / "training_history.yaml").read_text()
        )
        assert training_history["backfill_in_progress"] is True
        assert training_history["target_start_date"] == "2025-02-12"
        assert training_history["resume_before_timestamp"] == 1736500000
        assert training_history["last_progress_at"] is not None

        progress_file = repo_with_activities.repo_root / "config" / ".sync_progress.json"
        assert progress_file.exists()
        progress_payload = json.loads(progress_file.read_text())
        assert progress_payload["phase"] == "paused_rate_limit"
        assert progress_payload["cursor_before_timestamp"] == 1736500000
        assert progress_payload["updated_at"] is not None

    @patch("sports_coach_engine.core.workflows.sync_strava_generator")
    @patch("sports_coach_engine.core.workflows._fetch_and_update_athlete_profile")
    @patch("sports_coach_engine.core.workflows.recompute_all_metrics")
    def test_completion_clears_resume_state_and_progress_file(
        self,
        mock_metrics,
        mock_profile,
        mock_generator,
        repo_with_activities,
        mock_config,
    ):
        """Successful completion after paused state should clear resume cursor/progress."""
        from sports_coach_engine.schemas.activity import ActivitySource, RawActivity

        # Seed a paused backfill state + heartbeat progress file.
        repo_with_activities.write_yaml(
            "data/athlete/training_history.yaml",
            {
                "backfill_in_progress": True,
                "target_start_date": "2025-02-12",
                "resume_before_timestamp": 1736500000,
                "last_progress_at": "2026-02-12T12:00:00+00:00",
            },
        )
        repo_with_activities.write_json(
            "config/.sync_progress.json",
            {
                "phase": "paused_rate_limit",
                "activities_seen": 10,
                "activities_imported": 8,
                "activities_skipped": 2,
                "activities_failed": 0,
                "updated_at": "2026-02-12T12:00:00+00:00",
            },
        )

        raw_activity = RawActivity(
            id="strava_400",
            source=ActivitySource.STRAVA,
            sport_type="Run",
            name="Activity Done",
            date=date(2026, 1, 19),
            start_time=datetime(2026, 1, 19, 7, 0, tzinfo=timezone.utc),
            duration_seconds=1800,
        )

        def generator_factory(*args, **kwargs):
            progress_hook = kwargs.get("progress_hook")
            if progress_hook:
                progress_hook(
                    {
                        "phase": "fetching",
                        "current_page": 1,
                        "activities_seen": 0,
                        "cursor_before_timestamp": 1736400000,
                    }
                )

            class _Gen:
                def __iter__(self):
                    return self

                def __next__(self):
                    if not hasattr(self, "_done"):
                        self._done = True
                        return raw_activity
                    raise StopIteration(
                        SyncReport(
                            activities_imported=1,
                            activities_skipped=0,
                            activities_failed=0,
                            laps_fetched=0,
                            laps_skipped_age=0,
                            lap_fetch_failures=0,
                            phase=SyncPhase.DONE,
                            rate_limited=False,
                            errors=[],
                        )
                    )

            return _Gen()

        mock_generator.side_effect = generator_factory
        mock_profile.return_value = []
        mock_metrics.return_value = {"metrics_computed": 1}

        result = run_sync_workflow(repo_with_activities, mock_config)
        assert result.phase == SyncPhase.DONE

        training_history = yaml.safe_load(
            (repo_with_activities.repo_root / "data" / "athlete" / "training_history.yaml").read_text()
        )
        assert training_history["backfill_in_progress"] is False
        assert training_history["target_start_date"] is None
        assert training_history["resume_before_timestamp"] is None
        assert training_history["last_progress_at"] is not None
        assert repo_with_activities.file_exists("config/.sync_progress.json") is False

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
        assert result.phase == SyncPhase.DONE
        assert result.activities_imported == 1
        # Profile failure should be surfaced as sync errors
        assert any("Profile update failed" in e for e in result.errors)

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
        assert result.phase == SyncPhase.DONE
        assert result.activities_imported == 1
        # Metrics failure should be surfaced as sync errors
        assert any("Failed to recompute metrics" in e for e in result.errors)

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
        assert result1.phase == SyncPhase.DONE
        assert result1.activities_imported == 1

        # Second sync (same activity)
        mock_generator.return_value = iter([activity])
        result2 = run_sync_workflow(repo_with_activities, mock_config)
        assert result2.phase == SyncPhase.DONE
        assert result2.activities_imported == 0  # Skipped
        assert result2.activities_skipped == 1

        # Verify only one file exists
        activity_files = list(
            (repo_with_activities.repo_root / "data" / "activities" / "2026-01").glob(
                "2026-01-15_*.yaml"
            )
        )
        assert len(activity_files) == 1
