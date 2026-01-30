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
    export_plan_structure,
    build_macro_template,
    create_macro_plan,
    regenerate_plan,
    get_plan_weeks,
    get_pending_suggestions,
    accept_suggestion,
    decline_suggestion,
    PlanError,
    AcceptResult,
    DeclineResult,
    PlanWeeksResult,
)
from sports_coach_engine.schemas.plan import MasterPlan
from sports_coach_engine.schemas.profile import Goal, GoalType, AthleteProfile
from sports_coach_engine.schemas.repository import RepoError, RepoErrorType
from types import SimpleNamespace


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


@pytest.fixture
def mock_log():
    """Mock logger."""
    return Mock()


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
        mock_repo.read_yaml.assert_called_once()

    @patch("sports_coach_engine.api.plan.RepositoryIO")
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
        assert "No training plan found" in result.message

    @patch("sports_coach_engine.api.plan.RepositoryIO")
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
# EXPORT_PLAN_STRUCTURE TESTS
# ============================================================


@patch("sports_coach_engine.api.plan.get_current_plan")
def test_export_plan_structure_uses_race_week_from_plan(mock_get_plan, mock_log):
    """Race week should match the week that contains goal date."""
    weeks = [
        SimpleNamespace(
            week_number=1,
            start_date=date(2026, 1, 26),
            end_date=date(2026, 2, 1),
            target_volume_km=23.0,
            is_recovery_week=False,
        ),
        SimpleNamespace(
            week_number=2,
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 8),
            target_volume_km=28.0,
            is_recovery_week=False,
        ),
        SimpleNamespace(
            week_number=3,
            start_date=date(2026, 2, 9),
            end_date=date(2026, 2, 15),
            target_volume_km=32.0,
            is_recovery_week=False,
        ),
    ]
    plan = SimpleNamespace(
        total_weeks=3,
        goal={"type": "marathon", "target_date": date(2026, 2, 12)},
        phases=[
            {"phase": "base", "start_week": 1, "end_week": 3},
        ],
        weeks=weeks,
    )
    mock_get_plan.return_value = plan

    result = export_plan_structure()

    assert not isinstance(result, PlanError)
    assert result.race_week == 3


@patch("sports_coach_engine.api.plan.get_current_plan")
def test_export_plan_structure_derives_phases_and_volumes(mock_get_plan, mock_log):
    """Phases, volumes, and recovery weeks should match stored plan."""
    weeks = [
        SimpleNamespace(
            week_number=1,
            start_date=date(2026, 1, 26),
            end_date=date(2026, 2, 1),
            target_volume_km=23.0,
            is_recovery_week=False,
        ),
        SimpleNamespace(
            week_number=2,
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 8),
            target_volume_km=28.0,
            is_recovery_week=True,
        ),
        SimpleNamespace(
            week_number=3,
            start_date=date(2026, 2, 9),
            end_date=date(2026, 2, 15),
            target_volume_km=32.0,
            is_recovery_week=False,
        ),
    ]
    plan = SimpleNamespace(
        total_weeks=3,
        goal={"type": "marathon", "target_date": date(2026, 2, 12)},
        phases=[
            {"phase": "base", "start_week": 1, "end_week": 2},
            {"phase": "build", "start_week": 3, "end_week": 3},
        ],
        weeks=weeks,
    )
    mock_get_plan.return_value = plan

    result = export_plan_structure()

    assert not isinstance(result, PlanError)
    assert result.phases == {"base": 2, "build": 1}
    assert result.weekly_volumes_km == [23.0, 28.0, 32.0]
    assert result.recovery_weeks == [2]


# ============================================================
# BUILD_MACRO_TEMPLATE TESTS
# ============================================================


def test_build_macro_template_shape():
    """Template should include required fields and null placeholders."""
    template = build_macro_template(3)

    assert template["template_version"] == "macro_template_v1"
    assert template["total_weeks"] == 3
    assert template["weekly_volumes_km"] == [None, None, None]
    assert template["target_systemic_load_au"] == [None, None, None]
    assert len(template["workout_structure_hints"]) == 3


# ============================================================
# CREATE_MACRO_PLAN TESTS
# ============================================================


@patch("sports_coach_engine.core.plan.persist_plan")
@patch("sports_coach_engine.core.repository.RepositoryIO")
def test_create_macro_plan_with_valid_template(mock_repo_cls, mock_persist):
    """Test creating macro plan with valid template (single-sport, no systemic load)."""
    mock_repo = Mock()
    mock_repo_cls.return_value = mock_repo

    weekly_volumes = [25.0, 28.0, 30.0, 28.0]  # 4-week plan
    weekly_hints = [
        {
            "quality": {"max_sessions": 1, "types": ["strides_only"]},
            "long_run": {"emphasis": "steady", "pct_range": [25, 30]},
            "intensity_balance": {"low_intensity_pct": 0.85}
        }
    ] * 4

    result = create_macro_plan(
        goal_type="10k",
        race_date=date(2026, 6, 1),
        target_time="00:45:00",
        total_weeks=4,
        start_date=date(2026, 5, 4),  # Monday
        current_ctl=35.0,
        baseline_vdot=48.0,
        weekly_volumes_km=weekly_volumes,
        weekly_structure_hints=weekly_hints,
    )

    # Should return MasterPlan, not error
    assert not isinstance(result, PlanError)
    assert result.total_weeks == 4
    assert len(result.weeks) == 4
    assert result.weeks[0].target_volume_km == 25.0
    assert result.weeks[0].target_systemic_load_au == 0.0  # Default for single-sport


@patch("sports_coach_engine.core.plan.persist_plan")
@patch("sports_coach_engine.core.repository.RepositoryIO")
def test_create_macro_plan_with_systemic_load_targets(mock_repo_cls, mock_persist):
    """Test creating macro plan with systemic load targets (multi-sport)."""
    mock_repo = Mock()
    mock_repo_cls.return_value = mock_repo

    weekly_volumes = [40.0, 45.0, 50.0, 45.0]
    weekly_systemic = [95.0, 105.0, 110.0, 100.0]  # Multi-sport total load
    weekly_hints = [
        {
            "quality": {"max_sessions": 2, "types": ["tempo", "intervals"]},
            "long_run": {"emphasis": "progression", "pct_range": [28, 32]},
            "intensity_balance": {"low_intensity_pct": 0.80}
        }
    ] * 4

    result = create_macro_plan(
        goal_type="half_marathon",
        race_date=date(2026, 6, 15),
        target_time="1:30:00",
        total_weeks=4,
        start_date=date(2026, 5, 18),  # Monday
        current_ctl=44.0,
        baseline_vdot=50.0,
        weekly_volumes_km=weekly_volumes,
        weekly_systemic_load_au=weekly_systemic,
        weekly_structure_hints=weekly_hints,
    )

    assert not isinstance(result, PlanError)
    assert result.total_weeks == 4
    assert result.weeks[0].target_systemic_load_au == 95.0
    assert result.weeks[1].target_systemic_load_au == 105.0
    assert result.weeks[2].target_systemic_load_au == 110.0


@patch("sports_coach_engine.core.plan.persist_plan")
@patch("sports_coach_engine.core.repository.RepositoryIO")
def test_create_macro_plan_validates_volumes_positive(mock_repo_cls, mock_persist):
    """Test that negative or zero volumes are rejected."""
    mock_repo = Mock()
    mock_repo_cls.return_value = mock_repo

    weekly_volumes = [25.0, -10.0, 30.0]  # Invalid: negative volume
    weekly_hints = [
        {
            "quality": {"max_sessions": 1, "types": ["strides_only"]},
            "long_run": {"emphasis": "steady", "pct_range": [25, 30]},
            "intensity_balance": {"low_intensity_pct": 0.85}
        }
    ] * 3

    result = create_macro_plan(
        goal_type="10k",
        race_date=date(2026, 6, 1),
        target_time="00:45:00",
        total_weeks=3,
        start_date=date(2026, 5, 11),
        current_ctl=35.0,
        weekly_volumes_km=weekly_volumes,
        weekly_structure_hints=weekly_hints,
    )

    assert isinstance(result, PlanError)
    assert result.error_type == "validation"
    assert "positive number" in result.message


@patch("sports_coach_engine.core.plan.persist_plan")
@patch("sports_coach_engine.core.repository.RepositoryIO")
def test_create_macro_plan_derives_starting_peak_volumes(mock_repo_cls, mock_persist):
    """Test that starting/peak volumes are derived from weekly_volumes_km."""
    mock_repo = Mock()
    mock_repo_cls.return_value = mock_repo

    weekly_volumes = [20.0, 25.0, 30.0, 35.0, 32.0]  # Peak is 35.0
    weekly_hints = [
        {
            "quality": {"max_sessions": 1, "types": ["strides_only"]},
            "long_run": {"emphasis": "steady", "pct_range": [25, 30]},
            "intensity_balance": {"low_intensity_pct": 0.85}
        }
    ] * 5

    result = create_macro_plan(
        goal_type="10k",
        race_date=date(2026, 6, 8),
        target_time="00:45:00",
        total_weeks=5,
        start_date=date(2026, 5, 4),
        current_ctl=35.0,
        weekly_volumes_km=weekly_volumes,
        weekly_structure_hints=weekly_hints,
    )

    assert not isinstance(result, PlanError)
    # Volumes are stored in week plans, not top-level
    assert result.weeks[0].target_volume_km == 20.0  # Starting
    assert max(w.target_volume_km for w in result.weeks) == 35.0  # Peak


@patch("sports_coach_engine.core.plan.persist_plan")
@patch("sports_coach_engine.core.repository.RepositoryIO")
def test_create_macro_plan_validates_structure_hints_schema(mock_repo_cls, mock_persist):
    """Test that invalid structure hints are rejected."""
    mock_repo = Mock()
    mock_repo_cls.return_value = mock_repo

    weekly_volumes = [25.0, 28.0, 30.0]
    weekly_hints = [
        {
            "quality": {"invalid_field": "bad"},  # Invalid schema
            "long_run": {"emphasis": "steady", "pct_range": [25, 30]},
            "intensity_balance": {"low_intensity_pct": 0.85}
        }
    ] * 3

    result = create_macro_plan(
        goal_type="10k",
        race_date=date(2026, 6, 1),
        target_time="00:45:00",
        total_weeks=3,
        start_date=date(2026, 5, 11),
        current_ctl=35.0,
        weekly_volumes_km=weekly_volumes,
        weekly_structure_hints=weekly_hints,
    )

    assert isinstance(result, PlanError)
    assert result.error_type == "validation"
    assert "invalid" in result.message.lower()


@patch("sports_coach_engine.core.plan.persist_plan")
@patch("sports_coach_engine.core.repository.RepositoryIO")
def test_create_macro_plan_rejects_length_mismatch(mock_repo_cls, mock_persist):
    """Test that volume/hint length mismatches are rejected."""
    mock_repo = Mock()
    mock_repo_cls.return_value = mock_repo

    weekly_volumes = [25.0, 28.0, 30.0]  # 3 weeks
    weekly_hints = [
        {
            "quality": {"max_sessions": 1, "types": ["strides_only"]},
            "long_run": {"emphasis": "steady", "pct_range": [25, 30]},
            "intensity_balance": {"low_intensity_pct": 0.85}
        }
    ] * 4  # 4 weeks - MISMATCH

    result = create_macro_plan(
        goal_type="10k",
        race_date=date(2026, 6, 1),
        target_time="00:45:00",
        total_weeks=3,
        start_date=date(2026, 5, 11),
        current_ctl=35.0,
        weekly_volumes_km=weekly_volumes,
        weekly_structure_hints=weekly_hints,
    )

    assert isinstance(result, PlanError)
    assert result.error_type == "validation"
    assert "length" in result.message


@patch("sports_coach_engine.core.plan.persist_plan")
@patch("sports_coach_engine.core.repository.RepositoryIO")
def test_create_macro_plan_validates_systemic_load_length(mock_repo_cls, mock_persist):
    """Test that systemic load length must match total_weeks."""
    mock_repo = Mock()
    mock_repo_cls.return_value = mock_repo

    weekly_volumes = [25.0, 28.0, 30.0]
    weekly_systemic = [95.0, 105.0]  # Wrong length (2 instead of 3)
    weekly_hints = [
        {
            "quality": {"max_sessions": 1, "types": ["strides_only"]},
            "long_run": {"emphasis": "steady", "pct_range": [25, 30]},
            "intensity_balance": {"low_intensity_pct": 0.85}
        }
    ] * 3

    result = create_macro_plan(
        goal_type="10k",
        race_date=date(2026, 6, 1),
        target_time="00:45:00",
        total_weeks=3,
        start_date=date(2026, 5, 11),
        current_ctl=35.0,
        weekly_volumes_km=weekly_volumes,
        weekly_systemic_load_au=weekly_systemic,
        weekly_structure_hints=weekly_hints,
    )

    assert isinstance(result, PlanError)
    assert result.error_type == "validation"
    assert "weekly_systemic_load_au length" in result.message


@patch("sports_coach_engine.core.plan.persist_plan")
@patch("sports_coach_engine.core.repository.RepositoryIO")
def test_create_macro_plan_validates_systemic_load_non_negative(mock_repo_cls, mock_persist):
    """Test that negative systemic load values are rejected."""
    mock_repo = Mock()
    mock_repo_cls.return_value = mock_repo

    weekly_volumes = [25.0, 28.0, 30.0]
    weekly_systemic = [95.0, -10.0, 110.0]  # Invalid: negative
    weekly_hints = [
        {
            "quality": {"max_sessions": 1, "types": ["strides_only"]},
            "long_run": {"emphasis": "steady", "pct_range": [25, 30]},
            "intensity_balance": {"low_intensity_pct": 0.85}
        }
    ] * 3

    result = create_macro_plan(
        goal_type="10k",
        race_date=date(2026, 6, 1),
        target_time="00:45:00",
        total_weeks=3,
        start_date=date(2026, 5, 11),
        current_ctl=35.0,
        weekly_volumes_km=weekly_volumes,
        weekly_systemic_load_au=weekly_systemic,
        weekly_structure_hints=weekly_hints,
    )

    assert isinstance(result, PlanError)
    assert result.error_type == "validation"
    assert "non-negative" in result.message


@patch("sports_coach_engine.core.plan.persist_plan")
@patch("sports_coach_engine.core.repository.RepositoryIO")
def test_create_macro_plan_defaults_systemic_load_to_zero(mock_repo_cls, mock_persist):
    """Test that systemic load defaults to 0.0 when not provided (single-sport)."""
    mock_repo = Mock()
    mock_repo_cls.return_value = mock_repo

    weekly_volumes = [25.0, 28.0, 30.0]
    weekly_hints = [
        {
            "quality": {"max_sessions": 1, "types": ["strides_only"]},
            "long_run": {"emphasis": "steady", "pct_range": [25, 30]},
            "intensity_balance": {"low_intensity_pct": 0.85}
        }
    ] * 3

    result = create_macro_plan(
        goal_type="10k",
        race_date=date(2026, 6, 1),
        target_time="00:45:00",
        total_weeks=3,
        start_date=date(2026, 5, 11),
        current_ctl=35.0,
        weekly_volumes_km=weekly_volumes,
        weekly_systemic_load_au=None,  # Not provided
        weekly_structure_hints=weekly_hints,
    )

    assert not isinstance(result, PlanError)
    assert all(w.target_systemic_load_au == 0.0 for w in result.weeks)


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
        assert call_args.kwargs["goal"] is None

    @patch("sports_coach_engine.api.plan.RepositoryIO")
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
        assert call_args.kwargs["goal"] == new_goal

    @patch("sports_coach_engine.api.plan.RepositoryIO")
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
        assert "Failed to load profile" in result.message

    @patch("sports_coach_engine.api.plan.RepositoryIO")
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
        assert "Failed to generate plan" in result.message

    @patch("sports_coach_engine.api.plan.RepositoryIO")
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


# ============================================================
# GET_PLAN_WEEKS TESTS
# ============================================================


@pytest.fixture
def mock_plan_with_weeks():
    """Mock MasterPlan with multiple weeks."""
    plan = Mock(spec=MasterPlan)
    plan.total_weeks = 9
    plan.end_date = date.today() + timedelta(weeks=9)
    plan.starting_volume_km = 20.0
    plan.peak_volume_km = 45.19
    plan.conflict_policy = "running_goal_wins"

    # Create mock goal
    plan.goal = {
        "type": "marathon",
        "target_date": date.today() + timedelta(weeks=9),
        "target_time": "4:34:00"
    }

    # Create mock weeks
    plan.weeks = []
    for i in range(1, 10):
        week = Mock()
        week.week_number = i
        week.phase = "build" if i < 7 else "taper"
        week.start_date = date.today() + timedelta(weeks=i-3)
        week.end_date = week.start_date + timedelta(days=6)
        week.workouts = [Mock(), Mock()]  # 2 mock workouts per week
        plan.weeks.append(week)

    return plan


class TestGetPlanWeeks:
    """Test get_plan_weeks() function."""

    @patch("sports_coach_engine.api.plan.get_current_plan")
    def test_get_current_week_default(self, mock_get_plan, mock_plan_with_weeks):
        """Test retrieving current week (default behavior)."""
        mock_get_plan.return_value = mock_plan_with_weeks

        result = get_plan_weeks()

        # Should return PlanWeeksResult
        assert isinstance(result, PlanWeeksResult)
        assert len(result.weeks) == 1
        assert result.current_week_number == 3  # Week containing today
        assert result.total_weeks == 9
        assert "Week 3 of 9" in result.week_range

    @patch("sports_coach_engine.api.plan.get_current_plan")
    def test_get_next_week(self, mock_get_plan, mock_plan_with_weeks):
        """Test retrieving next week with --next flag."""
        mock_get_plan.return_value = mock_plan_with_weeks

        result = get_plan_weeks(next_week=True)

        # Should return next week
        assert isinstance(result, PlanWeeksResult)
        assert len(result.weeks) == 1
        assert result.weeks[0].week_number == 4  # Next week
        assert "Week 4 of 9" in result.week_range

    @patch("sports_coach_engine.api.plan.get_current_plan")
    def test_get_specific_week_number(self, mock_get_plan, mock_plan_with_weeks):
        """Test retrieving specific week by number."""
        mock_get_plan.return_value = mock_plan_with_weeks

        result = get_plan_weeks(week_number=5)

        # Should return week 5
        assert isinstance(result, PlanWeeksResult)
        assert len(result.weeks) == 1
        assert result.weeks[0].week_number == 5
        assert "Week 5 of 9" in result.week_range

    @patch("sports_coach_engine.api.plan.get_current_plan")
    def test_get_week_by_date(self, mock_get_plan, mock_plan_with_weeks):
        """Test retrieving week containing specific date."""
        mock_get_plan.return_value = mock_plan_with_weeks

        # Get week 5's start date
        target_date = mock_plan_with_weeks.weeks[4].start_date

        result = get_plan_weeks(target_date=target_date)

        # Should return week 5
        assert isinstance(result, PlanWeeksResult)
        assert len(result.weeks) == 1
        assert result.weeks[0].week_number == 5

    @patch("sports_coach_engine.api.plan.get_current_plan")
    def test_get_multiple_consecutive_weeks(self, mock_get_plan, mock_plan_with_weeks):
        """Test retrieving multiple consecutive weeks with --count."""
        mock_get_plan.return_value = mock_plan_with_weeks

        result = get_plan_weeks(week_number=5, count=2)

        # Should return weeks 5-6
        assert isinstance(result, PlanWeeksResult)
        assert len(result.weeks) == 2
        assert result.weeks[0].week_number == 5
        assert result.weeks[1].week_number == 6
        assert "Weeks 5-6 of 9" in result.week_range

    @patch("sports_coach_engine.api.plan.get_current_plan")
    def test_get_week_out_of_range(self, mock_get_plan, mock_plan_with_weeks):
        """Test error when week number is out of range."""
        mock_get_plan.return_value = mock_plan_with_weeks

        result = get_plan_weeks(week_number=99)

        # Should return PlanError
        assert isinstance(result, PlanError)
        assert result.error_type == "validation"
        assert "out of range" in result.message

    @patch("sports_coach_engine.api.plan.get_current_plan")
    def test_get_next_week_beyond_plan_end(self, mock_get_plan, mock_plan_with_weeks):
        """Test error when next week is beyond plan end."""
        # Adjust all weeks so week 9 is the current week
        # Set weeks 1-8 to be in the past, week 9 to contain today
        today = date.today()
        for i, week in enumerate(mock_plan_with_weeks.weeks):
            if i < 8:  # Weeks 1-8 are in the past
                week.start_date = today - timedelta(weeks=(9-i))
                week.end_date = week.start_date + timedelta(days=6)
            else:  # Week 9 contains today
                week.start_date = today
                week.end_date = today + timedelta(days=6)

        mock_get_plan.return_value = mock_plan_with_weeks

        result = get_plan_weeks(next_week=True)

        # Should return PlanError
        assert isinstance(result, PlanError)
        assert result.error_type == "not_found"
        assert "beyond plan end" in result.message

    @patch("sports_coach_engine.api.plan.get_current_plan")
    def test_get_week_by_date_not_found(self, mock_get_plan, mock_plan_with_weeks):
        """Test error when date is not in any week."""
        mock_get_plan.return_value = mock_plan_with_weeks

        # Use a date far in the past
        old_date = date.today() - timedelta(days=365)

        result = get_plan_weeks(target_date=old_date)

        # Should return PlanError
        assert isinstance(result, PlanError)
        assert result.error_type == "not_found"
        assert "No week found" in result.message

    @patch("sports_coach_engine.api.plan.get_current_plan")
    def test_get_weeks_no_plan_exists(self, mock_get_plan):
        """Test error when no plan exists."""
        mock_get_plan.return_value = PlanError(
            error_type="not_found",
            message="No training plan found"
        )

        result = get_plan_weeks()

        # Should return PlanError
        assert isinstance(result, PlanError)
        assert result.error_type == "not_found"

    @patch("sports_coach_engine.api.plan.get_current_plan")
    def test_plan_context_included(self, mock_get_plan, mock_plan_with_weeks):
        """Test that plan context is included in result."""
        mock_get_plan.return_value = mock_plan_with_weeks

        result = get_plan_weeks()

        # Should include plan context
        assert isinstance(result, PlanWeeksResult)
        assert result.plan_context["starting_volume_km"] == 20.0
        assert result.plan_context["peak_volume_km"] == 45.19
        assert result.plan_context["conflict_policy"] == "running_goal_wins"

    @patch("sports_coach_engine.api.plan.get_current_plan")
    def test_goal_details_included(self, mock_get_plan, mock_plan_with_weeks):
        """Test that goal details are included in result."""
        mock_get_plan.return_value = mock_plan_with_weeks

        result = get_plan_weeks()

        # Should include goal details
        assert isinstance(result, PlanWeeksResult)
        assert result.goal["type"] == "marathon"
        assert result.goal["target_time"] == "4:34:00"
