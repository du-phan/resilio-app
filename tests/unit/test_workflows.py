"""
Unit tests for M1 - Internal Workflows (core/workflows.py).

Tests workflow orchestration, transaction management, and error handling.
"""

import pytest
import yaml
from datetime import date, datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from resilio.core.workflows import (
    WorkflowLock,
    TransactionLog,
    WorkflowError,
    WorkflowLockError,
    WorkflowRollbackError,
    run_sync_workflow,
    run_metrics_refresh,
    run_plan_generation,
    run_adaptation_check,
    run_manual_activity_workflow,
)
from resilio.core.repository import RepositoryIO
from resilio.core.paths import current_plan_path
from resilio.schemas.plan import MasterPlan
from resilio.schemas.profile import ConflictPolicy, Goal, GoalType, TrainingConstraints
from resilio.schemas.sync import SyncPhase


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_repo(tmp_path):
    """Real RepositoryIO with temp directory for file operations."""
    repo = RepositoryIO()
    repo.repo_root = tmp_path
    # Ensure config directory exists
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    return repo


@pytest.fixture
def mock_config():
    """Mock configuration object."""
    config = Mock()
    config.settings = Mock()
    config.secrets = Mock()
    config.secrets.strava = Mock()
    config.secrets.strava.access_token = "mock_token"
    return config


# ============================================================
# WORKFLOWLOCK TESTS
# ============================================================


class TestWorkflowLock:
    """Test WorkflowLock for preventing concurrent access."""

    def test_acquire_lock_success(self, mock_repo, tmp_path):
        """Test successful lock acquisition."""
        lock_file = tmp_path / "config" / ".workflow_lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)

        with WorkflowLock(operation="test", repo=mock_repo):
            # Lock should be acquired
            assert lock_file.exists()

        # Lock should be released after context
        assert not lock_file.exists()

    def test_lock_prevents_concurrent_access(self, mock_repo, tmp_path):
        """Test that lock prevents concurrent access."""
        lock_file = tmp_path / "config" / ".workflow_lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)

        with WorkflowLock(operation="test1", repo=mock_repo):
            # Try to acquire another lock (should fail or wait)
            with pytest.raises(WorkflowLockError):
                with WorkflowLock(operation="test2", repo=mock_repo, retry_attempts=1, retry_wait_seconds=0.1):
                    pass

    def test_stale_lock_detection(self, mock_repo, tmp_path):
        """Test that stale locks are detected and broken."""
        import json
        import os

        lock_file = tmp_path / "config" / ".workflow_lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)

        # Create a stale lock (old timestamp, dead PID)
        stale_lock = {
            "pid": 99999,  # Non-existent PID
            "operation": "stale_op",
            "acquired_at": (datetime.now() - timedelta(minutes=10)).isoformat(),
        }
        lock_file.write_text(json.dumps(stale_lock))

        # Should be able to acquire lock (breaks stale lock)
        with WorkflowLock(operation="new_op", repo=mock_repo):
            assert lock_file.exists()
            # Verify it's our lock, not the stale one
            lock_data = json.loads(lock_file.read_text())
            assert lock_data["pid"] == os.getpid()


# ============================================================
# TRANSACTIONLOG TESTS
# ============================================================


class TestTransactionLog:
    """Test TransactionLog for rollback capability."""

    def test_record_create(self, tmp_path, mock_repo):
        """Test recording file creation."""
        txn = TransactionLog(repo=mock_repo)
        test_file = tmp_path / "test.yaml"

        txn.record_create(str(test_file))

        assert str(test_file) in txn.created_files

    def test_record_modify(self, tmp_path, mock_repo):
        """Test recording file modification with backup."""
        txn = TransactionLog(repo=mock_repo)
        test_file = tmp_path / "test.yaml"
        test_file.write_text("original content")

        txn.record_modify(str(test_file), {"backup": "data"})

        assert str(test_file) in txn.modified_files
        assert txn.modified_files[str(test_file)] == {"backup": "data"}

    def test_rollback_create(self, tmp_path, mock_repo):
        """Test rolling back file creation."""
        txn = TransactionLog(repo=mock_repo)
        test_file = tmp_path / "test.yaml"
        test_file.write_text("content")

        txn.record_create(str(test_file))
        txn.rollback()

        assert not test_file.exists()

    @pytest.mark.skip(reason="TransactionLog rollback for modifications requires BaseModel, not dict - covered by integration tests")
    def test_rollback_modify(self, tmp_path, mock_repo):
        """Test rolling back file modification."""
        import yaml

        txn = TransactionLog(repo=mock_repo)
        test_file = tmp_path / "test.yaml"

        original_data = {"original": "data"}
        test_file.write_text(yaml.dump(original_data))

        txn.record_modify(str(test_file), original_data)

        # Modify the file
        test_file.write_text(yaml.dump({"modified": "data"}))

        # Rollback
        txn.rollback()

        # Should restore original
        restored = yaml.safe_load(test_file.read_text())
        assert restored == original_data


# ============================================================
# WORKFLOW FUNCTION TESTS
# ============================================================


class TestRunSyncWorkflow:
    """Test run_sync_workflow orchestration."""

    @patch("resilio.core.workflows.sync_strava_generator")
    @patch("resilio.core.workflows._fetch_and_update_athlete_profile")
    def test_sync_workflow_success(self, mock_profile, mock_generator, mock_repo, mock_config):
        """Test successful sync workflow."""
        # Mock successful sync with no activities (empty generator)
        mock_generator.return_value = iter([])
        mock_profile.return_value = []

        result = run_sync_workflow(mock_repo, mock_config)

        assert result.phase == SyncPhase.DONE
        assert result.activities_imported == 0
        mock_generator.assert_called_once()

    @patch("resilio.core.workflows.sync_strava_generator")
    @patch("resilio.core.workflows._fetch_and_update_athlete_profile")
    def test_sync_workflow_fetch_failure(self, mock_profile, mock_generator, mock_repo, mock_config):
        """Test sync workflow with fetch failure."""
        # Generator raises exception (note: profile failures don't block sync)
        mock_generator.side_effect = Exception("API error")
        mock_profile.return_value = []

        # Fatal errors raise WorkflowError
        with pytest.raises(WorkflowError, match="API error"):
            run_sync_workflow(mock_repo, mock_config)

    @patch("resilio.core.workflows.sync_strava_generator")
    @patch("resilio.core.workflows._fetch_and_update_athlete_profile")
    def test_sync_workflow_lock_required(self, mock_profile, mock_generator, mock_repo, mock_config, tmp_path):
        """Test that sync workflow acquires lock."""
        mock_repo.repo_root = tmp_path
        mock_generator.return_value = iter([])
        mock_profile.return_value = []

        result = run_sync_workflow(mock_repo, mock_config)

        # Verify lock was used (indirectly through successful completion)
        assert result.phase == SyncPhase.DONE

    @patch("resilio.core.workflows.sync_strava_generator")
    @patch("resilio.core.workflows._fetch_and_update_athlete_profile")
    def test_sync_workflow_malformed_history_does_not_crash(
        self, mock_profile, mock_generator, mock_repo
    ):
        """Malformed training_history fields should not crash sync startup."""
        history_path = mock_repo.resolve_path("data/athlete/training_history.yaml")
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(
            "backfill_in_progress: maybe\n"
            "target_start_date: not-a-date\n"
            "resume_before_timestamp: nope\n"
            "last_progress_at: bad-time\n"
        )

        mock_generator.return_value = iter([])
        mock_profile.return_value = []

        config = Mock()
        result = run_sync_workflow(mock_repo, config)

        assert result.phase == SyncPhase.DONE
        saved_history = yaml.safe_load(history_path.read_text())
        assert saved_history["backfill_in_progress"] is False
        assert saved_history["target_start_date"] is None
        assert saved_history["resume_before_timestamp"] is None
        assert saved_history["last_progress_at"] is not None


class TestRunMetricsRefresh:
    """Test run_metrics_refresh workflow."""

    @pytest.mark.skip(reason="Complex workflow test - covered by API integration tests")
    @patch("resilio.core.workflows.compute_daily_metrics")
    def test_metrics_refresh_success(self, mock_compute, mock_repo):
        """Test successful metrics refresh."""
        from resilio.schemas.metrics import DailyMetrics

        mock_metrics = Mock(spec=DailyMetrics)
        mock_compute.return_value = mock_metrics

        result = run_metrics_refresh(mock_repo, target_date=date.today())

        assert result.success
        assert result.metrics == mock_metrics

    @pytest.mark.skip(reason="Complex workflow test - covered by API integration tests")
    @patch("resilio.core.workflows.compute_daily_metrics")
    def test_metrics_refresh_failure(self, mock_compute, mock_repo):
        """Test metrics refresh with computation failure."""
        mock_compute.side_effect = Exception("Computation error")

        result = run_metrics_refresh(mock_repo, target_date=date.today())

        assert not result.success
        assert "Computation error" in str(result.warnings)


class TestRunManualActivityWorkflow:
    """Test run_manual_activity_workflow."""

    @pytest.mark.skip(reason="Complex workflow test - covered by API integration tests")
    @patch("resilio.core.workflows.normalize_activity")
    @patch("resilio.core.workflows.analyze_notes_and_rpe")
    @patch("resilio.core.workflows.calculate_loads")
    def test_manual_activity_success(
        self, mock_loads, mock_analyze, mock_normalize, mock_repo
    ):
        """Test successful manual activity logging."""
        from resilio.schemas.activity import NormalizedActivity

        mock_activity = Mock(spec=NormalizedActivity)
        mock_normalize.return_value = mock_activity
        mock_analyze.return_value = mock_activity
        mock_loads.return_value = mock_activity

        result = run_manual_activity_workflow(
            repo=mock_repo,
            sport_type="run",
            duration_minutes=45,
            rpe=6,
        )

        assert result.success
        assert result.activity == mock_activity

    @pytest.mark.skip(reason="Complex workflow test - covered by API integration tests")
    def test_manual_activity_invalid_sport_type(self, mock_repo):
        """Test manual activity with invalid sport type."""
        result = run_manual_activity_workflow(
            repo=mock_repo,
            sport_type="invalid_sport",
            duration_minutes=45,
        )

        # Should handle gracefully or fail with validation error
        assert not result.success or result.warnings


class TestRunAdaptationCheck:
    """Test run_adaptation_check workflow."""

    @pytest.mark.skip(reason="Complex workflow test - covered by API integration tests")
    @patch("resilio.core.workflows.load_workout_for_date")
    @patch("resilio.core.workflows.load_daily_metrics")
    @patch("resilio.core.workflows.detect_adaptation_triggers")
    def test_adaptation_check_success(
        self, mock_triggers, mock_metrics, mock_workout, mock_repo
    ):
        """Test successful adaptation check."""
        mock_workout.return_value = Mock()
        mock_metrics.return_value = Mock()
        mock_triggers.return_value = []

        result = run_adaptation_check(mock_repo, target_date=date.today())

        assert result.success
        assert result.workout is not None

    @pytest.mark.skip(reason="Complex workflow test - covered by API integration tests")
    @patch("resilio.core.workflows.load_workout_for_date")
    def test_adaptation_check_no_workout(self, mock_workout, mock_repo):
        """Test adaptation check when no workout is scheduled."""
        mock_workout.return_value = None

        result = run_adaptation_check(mock_repo, target_date=date.today())

        assert not result.success
        assert result.workout is None


class TestRunPlanGeneration:
    """Test run_plan_generation workflow."""

    def _mock_profile(self):
        profile = Mock()
        profile.goal = Goal(
            type=GoalType.GENERAL_FITNESS,
            target_date=(date.today() + timedelta(weeks=12)).isoformat(),
            target_time=None,
        )
        profile.constraints = TrainingConstraints(
            min_run_days_per_week=3,
            max_run_days_per_week=5,
            unavailable_run_days=[],
            max_time_per_session_minutes=90,
        )
        profile.conflict_policy = ConflictPolicy.ASK_EACH_TIME
        return profile

    def _minimal_master_plan(self):
        today = date.today()
        return MasterPlan.model_validate(
            {
                "id": "plan_old",
                "created_at": today.isoformat(),
                "goal": {"type": "general_fitness", "target_date": None, "target_time": None},
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(weeks=4)).isoformat(),
                "total_weeks": 4,
                "phases": [
                    {
                        "phase": "base",
                        "start_week": 0,
                        "end_week": 3,
                        "start_date": today.isoformat(),
                        "end_date": (today + timedelta(weeks=4, days=-1)).isoformat(),
                        "weeks": 4,
                    }
                ],
                "weeks": [],
                "starting_volume_km": 20.0,
                "peak_volume_km": 30.0,
                "conflict_policy": "ask_each_time",
                "constraints_applied": [],
            }
        )

    @patch("resilio.core.workflows.suggest_volume_adjustment")
    @patch("resilio.core.workflows.calculate_periodization")
    @patch("resilio.core.workflows.ProfileService")
    def test_plan_generation_archives_valid_current_plan(
        self, mock_profile_service_cls, mock_periodization, mock_volume, mock_repo
    ):
        """Valid current plan should be archived without crashing."""
        old_plan = self._minimal_master_plan()
        mock_repo.write_yaml(current_plan_path(), old_plan)

        profile_service = Mock()
        profile_service.load_profile.return_value = self._mock_profile()
        mock_profile_service_cls.return_value = profile_service
        mock_periodization.return_value = [
            {
                "phase": "base",
                "start_week": 0,
                "end_week": 11,
                "start_date": date.today(),
                "end_date": date.today() + timedelta(weeks=12, days=-1),
                "weeks": 12,
            }
        ]
        mock_volume.return_value = Mock(start_range_km=(20.0, 24.0), peak_range_km=(40.0, 48.0))

        result = run_plan_generation(mock_repo)

        assert result.success is True
        assert result.archived_plan_path is not None
        assert mock_repo.file_exists(result.archived_plan_path)

    @patch("resilio.core.workflows.suggest_volume_adjustment")
    @patch("resilio.core.workflows.calculate_periodization")
    @patch("resilio.core.workflows.ProfileService")
    def test_plan_generation_skips_archive_for_malformed_current_plan(
        self, mock_profile_service_cls, mock_periodization, mock_volume, mock_repo
    ):
        """Malformed current plan should not crash plan generation."""
        plan_path = mock_repo.resolve_path(current_plan_path())
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text("invalid: [")

        profile_service = Mock()
        profile_service.load_profile.return_value = self._mock_profile()
        mock_profile_service_cls.return_value = profile_service
        mock_periodization.return_value = [
            {
                "phase": "base",
                "start_week": 0,
                "end_week": 11,
                "start_date": date.today(),
                "end_date": date.today() + timedelta(weeks=12, days=-1),
                "weeks": 12,
            }
        ]
        mock_volume.return_value = Mock(start_range_km=(20.0, 24.0), peak_range_km=(40.0, 48.0))

        result = run_plan_generation(mock_repo)

        assert result.success is True
        assert result.archived_plan_path is None

    @pytest.mark.skip(reason="Complex workflow test - covered by API integration tests")
    @patch("resilio.core.workflows.load_profile")
    @patch("resilio.core.workflows.load_daily_metrics")
    @patch("resilio.core.workflows.calculate_periodization")
    @patch("resilio.core.workflows.suggest_volume_adjustment")
    def test_plan_generation_success(
        self, mock_volume, mock_periodization, mock_metrics, mock_profile, mock_repo
    ):
        """Test successful plan generation."""
        from resilio.schemas.profile import Goal, GoalType

        mock_profile.return_value = Mock()
        mock_metrics.return_value = Mock()
        mock_periodization.return_value = Mock()
        mock_volume.return_value = Mock()

        goal = Goal(
            goal_type=GoalType.HALF_MARATHON,
            target_date=date.today() + timedelta(weeks=12),
        )

        result = run_plan_generation(mock_repo, goal=goal)

        assert result.success
        # Note: plan will be None in simplified implementation
        # Full implementation would generate actual plan

    @pytest.mark.skip(reason="Complex workflow test - covered by API integration tests")
    @patch("resilio.core.workflows.load_profile")
    def test_plan_generation_no_goal(self, mock_profile, mock_repo):
        """Test plan generation when no goal is set."""
        profile = Mock()
        profile.goal = None
        mock_profile.return_value = profile

        result = run_plan_generation(mock_repo, goal=None)

        assert not result.success


# ============================================================
# ERROR HANDLING TESTS
# ============================================================


class TestErrorHandling:
    """Test error handling and propagation."""

    def test_workflow_error_creation(self):
        """Test WorkflowError exception."""
        error = WorkflowError("Test error")
        assert str(error) == "Test error"

    def test_workflow_lock_error_creation(self):
        """Test WorkflowLockError exception."""
        error = WorkflowLockError("Lock timeout")
        assert str(error) == "Lock timeout"
        assert isinstance(error, WorkflowError)

    def test_workflow_rollback_error_creation(self):
        """Test WorkflowRollbackError exception."""
        error = WorkflowRollbackError("Rollback failed")
        assert str(error) == "Rollback failed"
        assert isinstance(error, WorkflowError)
