"""
Unit tests for Plan API (api/plan.py).

Tests get_current_plan(), regenerate_plan(), get_pending_suggestions(),
accept_suggestion(), and decline_suggestion().
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch

from sports_coach_engine.api.plan import (
    get_current_plan,
    regenerate_plan,
    get_pending_suggestions,
    accept_suggestion,
    decline_suggestion,
    PlanError,
    AcceptResult,
    DeclineResult,
)
from sports_coach_engine.schemas.plan import MasterPlan
from sports_coach_engine.schemas.profile import Goal, GoalType, AthleteProfile
from sports_coach_engine.schemas.repository import RepoError, RepoErrorType


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_plan():
    """Mock MasterPlan."""
    plan = Mock(spec=MasterPlan)
    plan.total_weeks = 12
    plan.goal = Mock(spec=Goal)
    plan.goal.type = GoalType.HALF_MARATHON
    plan.goal.target_date = date.today() + timedelta(weeks=12)
    return plan


@pytest.fixture
def mock_profile():
    """Mock AthleteProfile."""
    profile = Mock(spec=AthleteProfile)
    profile.name = "Test Athlete"
    profile.goal = None
    return profile


# ============================================================
# GET_CURRENT_PLAN TESTS
# ============================================================


class TestGetCurrentPlan:
    """Test get_current_plan() function."""
    @patch("sports_coach_engine.api.plan.RepositoryIO")
    def test_get_current_plan_success(self, mock_repo_cls, mock_log, mock_plan):
        """Test successful plan retrieval."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock loading plan
        mock_repo.read_yaml.return_value = mock_plan

        result = get_current_plan()

        # Should return MasterPlan
        assert isinstance(result, Mock)  # Mock of MasterPlan
        assert result == mock_plan
        assert result.total_weeks == 12

        # Verify read_yaml was called correctly
        mock_repo.read_yaml.assert_called_once()    @patch("sports_coach_engine.api.plan.RepositoryIO")
    def test_get_current_plan_not_found(self, mock_repo_cls, mock_log):
        """Test plan retrieval when no plan exists."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock no plan found
        mock_repo.read_yaml.return_value = None

        result = get_current_plan()

        # Should return PlanError
        assert isinstance(result, PlanError)
        assert result.error_type == "not_found"
        assert "No training plan found" in result.message    @patch("sports_coach_engine.api.plan.RepositoryIO")
    def test_get_current_plan_validation_error(self, mock_repo_cls, mock_log):
        """Test plan retrieval with validation error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock validation error
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.VALIDATION_ERROR, "Invalid YAML")

        result = get_current_plan()

        # Should return PlanError
        assert isinstance(result, PlanError)
        assert result.error_type == "validation"
        assert "Failed to load plan" in result.message


# ============================================================
# REGENERATE_PLAN TESTS
# ============================================================


class TestRegeneratePlan:
    """Test regenerate_plan() function."""
    @patch("sports_coach_engine.api.plan.RepositoryIO")
    @patch("sports_coach_engine.api.plan.run_plan_generation")
    def test_regenerate_plan_no_goal(self, mock_workflow, mock_repo_cls, mock_log, mock_plan):
        """Test regenerating plan without changing goal."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock successful workflow
        mock_result = Mock()
        mock_result.success = True
        mock_result.plan = mock_plan
        mock_result.warnings = []
        mock_workflow.return_value = mock_result

        result = regenerate_plan()

        # Should return MasterPlan
        assert isinstance(result, Mock)
        assert result == mock_plan

        # Verify workflow was called
        mock_workflow.assert_called_once()
        call_args = mock_workflow.call_args
        assert call_args.kwargs["goal"] is None    @patch("sports_coach_engine.api.plan.RepositoryIO")
    @patch("sports_coach_engine.api.plan.run_plan_generation")
    def test_regenerate_plan_with_new_goal(
        self, mock_workflow, mock_repo_cls, mock_log, mock_plan, mock_profile
    ):
        """Test regenerating plan with new goal."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock profile loading and saving
        mock_repo.read_yaml.return_value = mock_profile
        mock_repo.write_yaml.return_value = None

        # Mock successful workflow
        mock_result = Mock()
        mock_result.success = True
        mock_result.plan = mock_plan
        mock_result.warnings = []
        mock_workflow.return_value = mock_result

        # Create new goal
        target_date = (date.today() + timedelta(weeks=12)).isoformat()
        new_goal = Goal(
            type=GoalType.HALF_MARATHON,
            target_date=target_date,
        )

        result = regenerate_plan(goal=new_goal)

        # Should return MasterPlan
        assert isinstance(result, Mock)
        assert result == mock_plan

        # Verify profile was updated
        mock_repo.write_yaml.assert_called_once()

        # Verify workflow was called with goal
        mock_workflow.assert_called_once()
        call_args = mock_workflow.call_args
        assert call_args.kwargs["goal"] == new_goal    @patch("sports_coach_engine.api.plan.RepositoryIO")
    def test_regenerate_plan_profile_error(self, mock_repo_cls, mock_log):
        """Test regenerating plan with profile error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock profile loading error
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.FILE_NOT_FOUND, "Profile not found")

        target_date = (date.today() + timedelta(weeks=12)).isoformat()
        new_goal = Goal(
            type=GoalType.HALF_MARATHON,
            target_date=target_date,
        )

        result = regenerate_plan(goal=new_goal)

        # Should return PlanError
        assert isinstance(result, PlanError)
        assert result.error_type == "validation"
        assert "Failed to load profile" in result.message    @patch("sports_coach_engine.api.plan.RepositoryIO")
    @patch("sports_coach_engine.api.plan.run_plan_generation")
    def test_regenerate_plan_workflow_failure(self, mock_workflow, mock_repo_cls, mock_log):
        """Test regenerating plan with workflow failure."""
        from sports_coach_engine.core.workflows import WorkflowError

        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock workflow error
        mock_workflow.side_effect = WorkflowError("No goal set")

        result = regenerate_plan()

        # Should return PlanError
        assert isinstance(result, PlanError)
        assert result.error_type == "unknown"
        assert "Failed to generate plan" in result.message    @patch("sports_coach_engine.api.plan.RepositoryIO")
    @patch("sports_coach_engine.api.plan.run_plan_generation")
    def test_regenerate_plan_no_goal_set(self, mock_workflow, mock_repo_cls, mock_log):
        """Test regenerating plan when no goal is set."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock workflow failure due to no goal
        mock_result = Mock()
        mock_result.success = False
        mock_result.plan = None
        mock_result.warnings = ["No goal set"]
        mock_workflow.return_value = mock_result

        result = regenerate_plan()

        # Should return PlanError with no_goal type
        assert isinstance(result, PlanError)
        assert result.error_type == "no_goal"
        assert "No goal set" in result.message


# ============================================================
# GET_PENDING_SUGGESTIONS TESTS
# ============================================================


class TestGetPendingSuggestions:
    """Test get_pending_suggestions() function."""
    @patch("sports_coach_engine.api.plan.RepositoryIO")
    def test_get_pending_suggestions_empty(self, mock_repo_cls, mock_log):
        """Test getting pending suggestions (v0 simplified)."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        result = get_pending_suggestions()

        # Should return empty list for v0
        assert isinstance(result, list)
        assert len(result) == 0


# ============================================================
# ACCEPT_SUGGESTION TESTS
# ============================================================


class TestAcceptSuggestion:
    """Test accept_suggestion() function."""
    @patch("sports_coach_engine.api.plan.RepositoryIO")
    def test_accept_suggestion_v0_simplified(self, mock_repo_cls, mock_log):
        """Test accepting suggestion (v0 simplified)."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        result = accept_suggestion("sugg_2024-01-15_001")

        # Should return PlanError for v0 (not fully implemented)
        assert isinstance(result, PlanError)
        assert result.error_type == "not_found"
        assert "not found" in result.message.lower()


# ============================================================
# DECLINE_SUGGESTION TESTS
# ============================================================


class TestDeclineSuggestion:
    """Test decline_suggestion() function."""
    @patch("sports_coach_engine.api.plan.RepositoryIO")
    def test_decline_suggestion_v0_simplified(self, mock_repo_cls, mock_log):
        """Test declining suggestion (v0 simplified)."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        result = decline_suggestion("sugg_2024-01-15_001")

        # Should return PlanError for v0 (not fully implemented)
        assert isinstance(result, PlanError)
        assert result.error_type == "not_found"
        assert "not found" in result.message.lower()
