"""
Unit tests for Profile API (api/profile.py).

Tests get_profile(), update_profile(), and set_goal().
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch

from sports_coach_engine.api.profile import (
    get_profile,
    update_profile,
    set_goal,
    ProfileError,
)
from sports_coach_engine.schemas.profile import AthleteProfile, Goal, GoalType
from sports_coach_engine.schemas.repository import RepoError, RepoErrorType


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_profile():
    """Mock AthleteProfile."""
    profile = Mock(spec=AthleteProfile)
    profile.name = "Test Athlete"
    profile.goal = None
    profile.constraints = Mock()
    profile.constraints.runs_per_week = 3
    return profile


@pytest.fixture
def mock_profile_with_goal():
    """Mock AthleteProfile with goal."""
    profile = Mock(spec=AthleteProfile)
    profile.name = "Test Athlete"
    profile.goal = Mock(spec=Goal)
    profile.goal.type = GoalType.HALF_MARATHON
    profile.goal.target_date = date.today() + timedelta(weeks=12)
    return profile


# ============================================================
# GET_PROFILE TESTS
# ============================================================


class TestGetProfile:
    """Test get_profile() function."""

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    def test_get_profile_success(self, mock_repo_cls, mock_log, mock_profile):
        """Test successful profile retrieval."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock loading profile
        mock_repo.read_yaml.return_value = mock_profile

        result = get_profile()

        # Should return AthleteProfile
        assert isinstance(result, Mock)  # Mock of AthleteProfile
        assert result == mock_profile
        assert result.name == "Test Athlete"

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    def test_get_profile_with_goal(self, mock_repo_cls, mock_log, mock_profile_with_goal):
        """Test profile retrieval with goal set."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile_with_goal

        result = get_profile()

        # Should return AthleteProfile with goal
        assert isinstance(result, Mock)
        assert result.goal is not None
        assert result.goal.type == GoalType.HALF_MARATHON

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    def test_get_profile_not_found(self, mock_repo_cls, mock_log):
        """Test profile retrieval when file not found."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock file not found error
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.FILE_NOT_FOUND, "File not found")

        result = get_profile()

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "not_found"
        assert "Failed to load profile" in result.message

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    def test_get_profile_validation_error(self, mock_repo_cls, mock_log):
        """Test profile retrieval with validation error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock validation error
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.VALIDATION_ERROR, "Invalid profile data")

        result = get_profile()

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "validation"
        assert "Failed to load profile" in result.message


# ============================================================
# UPDATE_PROFILE TESTS
# ============================================================


class TestUpdateProfile:
    """Test update_profile() function."""

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    @patch("sports_coach_engine.api.profile.AthleteProfile")
    def test_update_profile_success(self, mock_profile_cls, mock_repo_cls, mock_log, mock_profile):
        """Test successful profile update."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock loading profile
        mock_repo.read_yaml.return_value = mock_profile

        # Mock validation
        mock_profile_cls.model_validate.return_value = mock_profile
        mock_profile.model_dump.return_value = {"name": "Test Athlete"}

        # Mock saving
        mock_repo.write_yaml.return_value = None

        result = update_profile(name="Updated Athlete")

        # Should return updated AthleteProfile
        assert isinstance(result, Mock)
        assert result == mock_profile

        # Verify save was called
        mock_repo.write_yaml.assert_called_once()

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    def test_update_profile_invalid_field(self, mock_repo_cls, mock_log, mock_profile):
        """Test updating profile with invalid field."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile

        result = update_profile(invalid_field="value")

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "validation"
        assert "Invalid field" in result.message

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    def test_update_profile_not_found(self, mock_repo_cls, mock_log):
        """Test updating profile when file not found."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock file not found
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.FILE_NOT_FOUND, "File not found")

        result = update_profile(name="Updated Athlete")

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "not_found"
        assert "Failed to load profile" in result.message

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    @patch("sports_coach_engine.api.profile.AthleteProfile")
    def test_update_profile_validation_error(
        self, mock_profile_cls, mock_repo_cls, mock_log, mock_profile
    ):
        """Test updating profile with validation error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile

        # Mock validation error
        mock_profile.model_dump.return_value = {"name": "Test"}
        mock_profile_cls.model_validate.side_effect = Exception("Validation failed")

        result = update_profile(name="Updated")

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "validation"
        assert "Invalid profile data" in result.message

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    @patch("sports_coach_engine.api.profile.AthleteProfile")
    def test_update_profile_save_error(
        self, mock_profile_cls, mock_repo_cls, mock_log, mock_profile
    ):
        """Test updating profile with save error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile
        mock_profile.model_dump.return_value = {"name": "Test"}
        mock_profile_cls.model_validate.return_value = mock_profile

        # Mock save error
        mock_repo.write_yaml.return_value = RepoError(RepoErrorType.WRITE_ERROR, "Write failed")

        result = update_profile(name="Updated")

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "unknown"
        assert "Failed to save profile" in result.message


# ============================================================
# SET_GOAL TESTS
# ============================================================


class TestSetGoal:
    """Test set_goal() function."""

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    @patch("sports_coach_engine.api.profile.regenerate_plan")
    def test_set_goal_success(self, mock_regenerate, mock_repo_cls, mock_log, mock_profile):
        """Test successful goal setting."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock loading and saving profile
        mock_repo.read_yaml.return_value = mock_profile
        mock_repo.write_yaml.return_value = None

        # Mock plan regeneration
        mock_plan = Mock()
        mock_plan.total_weeks = 12
        mock_regenerate.return_value = mock_plan

        target_date = date.today() + timedelta(weeks=12)
        result = set_goal(
            race_type="half_marathon",
            target_date=target_date,
            target_time="1:45:00",
        )

        # Should return Goal
        assert isinstance(result, Goal)
        assert result.type == GoalType.HALF_MARATHON
        assert result.target_date == target_date.isoformat()  # Goal stores as ISO string
        assert result.target_time == "1:45:00"

        # Verify plan was regenerated
        mock_regenerate.assert_called_once()

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    def test_set_goal_invalid_race_type(self, mock_repo_cls, mock_log):
        """Test setting goal with invalid race type."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        result = set_goal(
            race_type="invalid_race",
            target_date=date.today() + timedelta(weeks=12),
        )

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "validation"
        assert "Invalid race type" in result.message

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    def test_set_goal_profile_not_found(self, mock_repo_cls, mock_log):
        """Test setting goal when profile not found."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock profile load error
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.FILE_NOT_FOUND, "Profile not found")

        result = set_goal(
            race_type="half_marathon",
            target_date=date.today() + timedelta(weeks=12),
        )

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "not_found"
        assert "Failed to load profile" in result.message

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    def test_set_goal_save_error(self, mock_repo_cls, mock_log, mock_profile):
        """Test setting goal with save error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile

        # Mock save error
        mock_repo.write_yaml.return_value = RepoError(RepoErrorType.WRITE_ERROR, "Write failed")

        result = set_goal(
            race_type="half_marathon",
            target_date=date.today() + timedelta(weeks=12),
        )

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "unknown"
        assert "Failed to save profile" in result.message

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    @patch("sports_coach_engine.api.profile.regenerate_plan")
    def test_set_goal_plan_generation_error(
        self, mock_regenerate, mock_repo_cls, mock_log, mock_profile
    ):
        """Test setting goal when plan generation fails."""
        from sports_coach_engine.api.plan import PlanError

        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile
        mock_repo.write_yaml.return_value = None

        # Mock plan generation failure
        mock_regenerate.return_value = PlanError(
            error_type="unknown",
            message="Plan generation failed",
        )

        result = set_goal(
            race_type="half_marathon",
            target_date=date.today() + timedelta(weeks=12),
        )

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "unknown"
        assert "plan generation failed" in result.message.lower()

    @patch("sports_coach_engine.api.profile.log_message")
    @patch("sports_coach_engine.api.profile.RepositoryIO")
    @patch("sports_coach_engine.api.profile.regenerate_plan")
    def test_set_goal_without_target_time(
        self, mock_regenerate, mock_repo_cls, mock_log, mock_profile
    ):
        """Test setting goal without target time."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile
        mock_repo.write_yaml.return_value = None

        mock_plan = Mock()
        mock_plan.total_weeks = 12
        mock_regenerate.return_value = mock_plan

        target_date = date.today() + timedelta(weeks=12)
        result = set_goal(
            race_type="10k",
            target_date=target_date,
        )

        # Should return Goal without target_time
        assert isinstance(result, Goal)
        assert result.type == GoalType.TEN_K
        assert result.target_date == target_date.isoformat()  # Goal stores as ISO string
        assert result.target_time is None
