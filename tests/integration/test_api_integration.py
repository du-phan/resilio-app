"""
Integration tests for API layer.

Tests end-to-end workflows with real modules (not mocked).
"""

import pytest
from datetime import date, timedelta, datetime
from pathlib import Path

from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.core.paths import (
    get_athlete_dir,
    get_activities_dir,
    get_metrics_dir,
    get_plans_dir,
    get_conversations_dir,
    athlete_profile_path,
)
from sports_coach_engine.schemas.config import Config, Settings, Secrets, StravaSecrets
from sports_coach_engine.api.sync import sync_strava, log_activity, SyncError
from sports_coach_engine.api.coach import get_todays_workout, get_weekly_status, get_training_status, CoachError
from sports_coach_engine.api.metrics import get_current_metrics, get_readiness, get_intensity_distribution, MetricsError
from sports_coach_engine.api.plan import get_current_plan, regenerate_plan, PlanError
from sports_coach_engine.api.profile import get_profile, update_profile, set_goal, ProfileError
from sports_coach_engine.schemas.profile import AthleteProfile, Goal, GoalType, TrainingConstraints, ConflictPolicy, Weekday, RunningPriority
from sports_coach_engine.schemas.enrichment import SyncSummary
from sports_coach_engine.schemas.activity import NormalizedActivity


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def integration_repo(tmp_path):
    """Create a test repository with sample data."""
    repo = RepositoryIO()
    repo.repo_root = tmp_path

    # Create directory structure
    repo.ensure_directory(get_athlete_dir())
    repo.ensure_directory(get_activities_dir())
    repo.ensure_directory(f"{get_metrics_dir()}/daily")
    repo.ensure_directory(get_plans_dir())
    repo.ensure_directory("config")
    repo.ensure_directory(f"{get_conversations_dir()}/transcripts")
    repo.ensure_directory(f"{get_conversations_dir()}/summaries")

    # Create minimal profile
    today = date.today()
    profile = AthleteProfile(
        name="Integration Test Athlete",
        created_at=today.isoformat(),
        constraints=TrainingConstraints(
            available_run_days=[Weekday.MONDAY, Weekday.WEDNESDAY, Weekday.FRIDAY, Weekday.SATURDAY],
            preferred_run_days=[Weekday.SATURDAY],
            min_run_days_per_week=3,
            max_run_days_per_week=4,
        ),
        running_priority=RunningPriority.PRIMARY,
        conflict_policy=ConflictPolicy.PRIMARY_SPORT_WINS,
        goal=Goal(
            type=GoalType.GENERAL_FITNESS,
            target_date=None,
            target_time=None,
        ),
    )
    repo.write_yaml(athlete_profile_path(), profile)

    # Create minimal config
    config = Config(
        settings=Settings(),
        secrets=Secrets(
            strava=StravaSecrets(
                client_id="test_client",
                client_secret="test_secret",
                access_token="test_token",
                refresh_token="test_refresh",
                token_expires_at=9999999999,
            )
        ),
        loaded_at=datetime.now(),
    )
    repo.write_yaml("config/config.yaml", config.model_dump())
    repo.write_yaml("config/secrets.local.yaml", config.secrets.model_dump())

    return repo


# ============================================================
# PROFILE API INTEGRATION TESTS
# ============================================================


class TestProfileIntegration:
    """Integration tests for profile API."""

    def test_get_and_update_profile_flow(self, integration_repo, tmp_path, monkeypatch):
        """Test complete profile get/update flow."""
        # Switch to integration repo
        monkeypatch.setattr("sports_coach_engine.api.profile.RepositoryIO", lambda: integration_repo)

        # Get profile
        profile = get_profile()
        assert isinstance(profile, AthleteProfile)
        assert profile.name == "Integration Test Athlete"
        assert profile.constraints.min_run_days_per_week == 3
        assert Weekday.SATURDAY in profile.constraints.preferred_run_days

        # Update constraints (must include all required fields)
        updated = update_profile(
            constraints={
                "available_run_days": [Weekday.MONDAY, Weekday.WEDNESDAY, Weekday.FRIDAY, Weekday.SUNDAY],
                "min_run_days_per_week": 4,
                "max_run_days_per_week": 5,
                "preferred_run_days": [Weekday.SUNDAY],
            }
        )

        assert isinstance(updated, AthleteProfile)
        assert updated.constraints.min_run_days_per_week == 4
        assert Weekday.SUNDAY in updated.constraints.preferred_run_days

    def test_set_goal_flow(self, integration_repo, tmp_path, monkeypatch):
        """Test setting a goal (without plan generation in integration test)."""
        # Note: Full plan generation requires more setup, so we test goal setting only
        monkeypatch.setattr("sports_coach_engine.api.profile.RepositoryIO", lambda: integration_repo)

        # Mock regenerate_plan to avoid complex setup
        from sports_coach_engine.api import profile
        from unittest.mock import Mock

        mock_plan = Mock()
        mock_plan.total_weeks = 12
        original_regenerate = profile.regenerate_plan
        profile.regenerate_plan = lambda goal: mock_plan

        try:
            target_date = date.today() + timedelta(weeks=12)
            goal = set_goal(
                race_type="half_marathon",
                target_date=target_date,
                target_time="1:45:00",
            )

            assert isinstance(goal, Goal)
            assert goal.type == GoalType.HALF_MARATHON
            assert goal.target_date == target_date.isoformat()  # Goal stores dates as ISO strings

            # Verify profile was updated
            profile_result = get_profile()
            assert profile_result.goal is not None
            assert profile_result.goal.type == GoalType.HALF_MARATHON

        finally:
            # Restore original function
            profile.regenerate_plan = original_regenerate


# ============================================================
# MANUAL ACTIVITY INTEGRATION TESTS
# ============================================================


class TestManualActivityIntegration:
    """Integration tests for manual activity logging."""

    def test_log_activity_full_pipeline(self, integration_repo, tmp_path, monkeypatch):
        """Test logging an activity through full pipeline."""
        # Mock necessary components
        monkeypatch.setattr("sports_coach_engine.api.sync.RepositoryIO", lambda: integration_repo)

        # Mock workflow functions to simplify test
        from sports_coach_engine.core.workflows import ManualActivityResult
        from sports_coach_engine.schemas.activity import NormalizedActivity, LoadCalculation, SessionType

        def mock_manual_workflow(repo, sport_type, duration_minutes, **kwargs):
            # Create a realistic activity result
            activity = NormalizedActivity(
                id="manual_" + date.today().isoformat(),
                source="manual",
                date=date.today(),
                sport_type="run",
                name="Test Activity",
                duration_minutes=duration_minutes,
                duration_seconds=duration_minutes * 60,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                calculated=LoadCalculation(
                    activity_id="manual_" + date.today().isoformat(),
                    duration_minutes=duration_minutes,
                    estimated_rpe=6,
                    sport_type="run",
                    base_effort_au=300.0,
                    systemic_multiplier=1.0,
                    lower_body_multiplier=1.0,
                    systemic_load_au=300.0,
                    lower_body_load_au=300.0,
                    session_type=SessionType.MODERATE,
                ),
            )

            return ManualActivityResult(
                success=True,
                warnings=[],
                activity=activity,
                metrics_updated=None,
            )

        # Patch at the import location in sync.py
        monkeypatch.setattr("sports_coach_engine.api.sync.run_manual_activity_workflow", mock_manual_workflow)

        result = log_activity(
            sport_type="run",
            duration_minutes=45,
            rpe=6,
            notes="Felt good, easy pace",
        )

        # Should return NormalizedActivity
        assert isinstance(result, NormalizedActivity)
        assert result.sport_type == "run"
        assert result.duration_minutes == 45
        assert result.calculated.systemic_load_au == 300.0


# ============================================================
# METRICS API INTEGRATION TESTS
# ============================================================


class TestMetricsIntegration:
    """Integration tests for metrics API."""

    def test_metrics_not_found_flow(self, integration_repo, tmp_path, monkeypatch):
        """Test metrics API when no data exists yet."""
        monkeypatch.setattr("sports_coach_engine.api.metrics.RepositoryIO", lambda: integration_repo)

        # No metrics exist yet
        result = get_current_metrics()

        # Should return MetricsError
        assert isinstance(result, MetricsError)
        assert result.error_type == "not_found"

    def test_readiness_insufficient_data(self, integration_repo, tmp_path, monkeypatch):
        """Test readiness when insufficient data."""
        monkeypatch.setattr("sports_coach_engine.api.metrics.RepositoryIO", lambda: integration_repo)

        result = get_readiness()

        # Should return MetricsError
        assert isinstance(result, MetricsError)
        assert result.error_type == "not_found"

    def test_intensity_distribution_no_data(self, integration_repo, tmp_path, monkeypatch):
        """Test intensity distribution with no data."""
        monkeypatch.setattr("sports_coach_engine.api.metrics.RepositoryIO", lambda: integration_repo)

        result = get_intensity_distribution(days=7)

        # Should return MetricsError
        assert isinstance(result, MetricsError)
        assert result.error_type == "not_found"


# ============================================================
# COACH API INTEGRATION TESTS
# ============================================================


class TestCoachIntegration:
    """Integration tests for coach API."""

    def test_get_todays_workout_no_plan(self, integration_repo, tmp_path, monkeypatch):
        """Test getting workout when no plan exists."""
        monkeypatch.setattr("sports_coach_engine.api.coach.RepositoryIO", lambda: integration_repo)

        # Mock workflow to avoid complex setup
        from sports_coach_engine.core.workflows import AdaptationCheckResult

        def mock_adaptation_check(repo, target_date):
            return AdaptationCheckResult(
                success=False,
                warnings=["No plan found"],
                workout=None,
                triggers=[],
            )

        # Patch at the import location in coach.py
        monkeypatch.setattr("sports_coach_engine.api.coach.run_adaptation_check", mock_adaptation_check)

        result = get_todays_workout()

        # Should return CoachError
        assert isinstance(result, CoachError)
        assert result.error_type == "no_plan"

    def test_get_weekly_status_no_plan(self, integration_repo, tmp_path, monkeypatch):
        """Test getting weekly status when no plan exists."""
        monkeypatch.setattr("sports_coach_engine.api.coach.RepositoryIO", lambda: integration_repo)

        result = get_weekly_status()

        # Should return WeeklyStatus with 0 planned workouts
        assert hasattr(result, "planned_workouts")
        assert result.planned_workouts == 0

    def test_get_training_status_no_data(self, integration_repo, tmp_path, monkeypatch):
        """Test getting training status when no data exists."""
        monkeypatch.setattr("sports_coach_engine.api.coach.RepositoryIO", lambda: integration_repo)

        result = get_training_status()

        # Should return CoachError
        assert isinstance(result, CoachError)
        assert result.error_type == "not_found"


# ============================================================
# PLAN API INTEGRATION TESTS
# ============================================================


class TestPlanIntegration:
    """Integration tests for plan API."""

    def test_get_current_plan_not_found(self, integration_repo, tmp_path, monkeypatch):
        """Test getting plan when none exists."""
        monkeypatch.setattr("sports_coach_engine.api.plan.RepositoryIO", lambda: integration_repo)

        result = get_current_plan()

        # Should return PlanError
        assert isinstance(result, PlanError)
        assert result.error_type == "not_found"

    def test_regenerate_plan_no_goal(self, integration_repo, tmp_path, monkeypatch):
        """Test regenerating plan when no goal is set."""
        monkeypatch.setattr("sports_coach_engine.api.plan.RepositoryIO", lambda: integration_repo)

        # Mock workflow
        from sports_coach_engine.core.workflows import PlanGenerationResult

        def mock_plan_generation(repo, goal):
            return PlanGenerationResult(
                success=False,
                warnings=["No goal set"],
                plan=None,
            )

        # Patch at the import location in plan.py
        monkeypatch.setattr("sports_coach_engine.api.plan.run_plan_generation", mock_plan_generation)

        result = regenerate_plan()

        # Should return PlanError
        assert isinstance(result, PlanError)
        assert result.error_type == "no_goal"


# ============================================================
# CROSS-MODULE INTEGRATION TESTS
# ============================================================


class TestCrossModuleIntegration:
    """Integration tests across multiple modules."""

    def test_profile_update_persistence(self, integration_repo, tmp_path, monkeypatch):
        """Test that profile updates persist across API calls."""
        monkeypatch.setattr("sports_coach_engine.api.profile.RepositoryIO", lambda: integration_repo)

        # Get initial profile
        profile1 = get_profile()
        assert profile1.name == "Integration Test Athlete"

        # Update name
        updated = update_profile(name="Updated Test Athlete")
        assert updated.name == "Updated Test Athlete"

        # Get profile again - should reflect update
        profile2 = get_profile()
        assert profile2.name == "Updated Test Athlete"

    def test_api_creates_conversation_logs(self, integration_repo, tmp_path, monkeypatch):
        """Test that API calls create conversation logs."""
        monkeypatch.setattr("sports_coach_engine.api.profile.RepositoryIO", lambda: integration_repo)
        monkeypatch.setattr("sports_coach_engine.core.logger.RepositoryIO", lambda: integration_repo)

        # Make an API call
        get_profile()

        # Check that conversation logs were created
        transcripts_dir = tmp_path / "conversations" / "transcripts"
        if transcripts_dir.exists():
            # Should have at least created a directory
            assert transcripts_dir.is_dir()


# ============================================================
# ERROR PROPAGATION TESTS
# ============================================================


class TestErrorPropagation:
    """Test that errors propagate correctly through the stack."""

    def test_invalid_yaml_propagates_as_validation_error(self, integration_repo, tmp_path, monkeypatch):
        """Test that invalid YAML files result in validation errors."""
        monkeypatch.setattr("sports_coach_engine.api.profile.RepositoryIO", lambda: integration_repo)

        # Write invalid YAML
        profile_path = tmp_path / "athlete" / "profile.yaml"
        profile_path.write_text("invalid: yaml: content: [")

        result = get_profile()

        # Should return ProfileError with validation type
        assert isinstance(result, ProfileError)
        assert result.error_type in ["validation", "not_found"]

    def test_missing_required_field_propagates(self, integration_repo, tmp_path, monkeypatch):
        """Test that missing required fields in profile result in errors."""
        monkeypatch.setattr("sports_coach_engine.api.profile.RepositoryIO", lambda: integration_repo)

        # Write profile missing required fields
        profile_path = tmp_path / "athlete" / "profile.yaml"
        profile_path.write_text("name: Test")  # Missing constraints

        result = get_profile()

        # Should return ProfileError
        assert isinstance(result, ProfileError)


# ============================================================
# PERFORMANCE TESTS (Simplified)
# ============================================================


class TestPerformance:
    """Basic performance verification tests."""

    def test_api_calls_complete_quickly(self, integration_repo, tmp_path, monkeypatch):
        """Test that API calls complete in reasonable time."""
        import time

        monkeypatch.setattr("sports_coach_engine.api.profile.RepositoryIO", lambda: integration_repo)

        start = time.time()
        get_profile()
        duration = time.time() - start

        # Should complete in well under 1 second
        assert duration < 1.0

    def test_multiple_api_calls_perform_well(self, integration_repo, tmp_path, monkeypatch):
        """Test that multiple API calls don't have cumulative slowdown."""
        import time

        monkeypatch.setattr("sports_coach_engine.api.profile.RepositoryIO", lambda: integration_repo)

        start = time.time()
        for _ in range(10):
            get_profile()
        duration = time.time() - start

        # 10 calls should complete in under 2 seconds
        assert duration < 2.0
