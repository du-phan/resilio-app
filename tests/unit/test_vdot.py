"""
Unit tests for Daniels–Gilbert race-performance equivalence.

Tests strict VDOT calculations and equivalent-race predictions.
"""

from datetime import date

import pytest

from resilio.core.vdot import (
    calculate_race_equivalents,
    calculate_raw_vdot,
    calculate_vdot,
    format_time_seconds,
    parse_time_string,
)
from resilio.schemas.vdot import RaceDistance

# ============================================================
# TIME PARSING & FORMATTING TESTS
# ============================================================


class TestTimeFormatting:
    """Tests for time parsing and formatting utilities."""

    def test_parse_mm_ss_format(self):
        """Parse MM:SS format correctly."""
        assert parse_time_string("5:30") == 330  # 5 * 60 + 30
        assert parse_time_string("10:45") == 645  # 10 * 60 + 45

    def test_parse_hh_mm_ss_format(self):
        """Parse HH:MM:SS format correctly."""
        assert parse_time_string("1:30:00") == 5400  # 1 * 3600 + 30 * 60
        assert parse_time_string("2:45:30") == 9930  # 2 * 3600 + 45 * 60 + 30

    def test_parse_invalid_format_raises(self):
        """Invalid time format should raise ValueError."""
        with pytest.raises(ValueError):
            parse_time_string("invalid")
        with pytest.raises(ValueError):
            parse_time_string("5:30:45:10")  # Too many parts

    def test_format_time_short(self):
        """Format time < 1 hour as MM:SS."""
        assert format_time_seconds(150) == "2:30"
        assert format_time_seconds(645) == "10:45"

    def test_format_time_long(self):
        """Format time ≥ 1 hour as HH:MM:SS."""
        assert format_time_seconds(3665) == "1:01:05"
        assert format_time_seconds(5400) == "1:30:00"


# ============================================================
# VDOT CALCULATION TESTS
# ============================================================


class TestVDOTCalculation:
    """Tests for VDOT calculation from race performance."""

    def test_10k_42_30_matches_daniels_gilbert_equation(self):
        result = calculate_vdot(RaceDistance.TEN_K, 2550)  # 42:30 = 2550s

        assert result.vdot == 48
        assert result.vdot_raw == pytest.approx(48.3904559, abs=1e-7)
        assert result.source_race == RaceDistance.TEN_K
        assert result.source_time_seconds == 2550
        assert result.performance_date is None
        assert result.performance_age_days is None

    def test_half_marathon_90_minute_golden_vector(self):
        result = calculate_vdot(RaceDistance.HALF_MARATHON, 5400)  # 1:30:00

        assert result.vdot == 51
        assert result.vdot_raw == pytest.approx(50.9769063, abs=1e-7)

    def test_official_vdot_50_five_k_reference(self):
        result = calculate_vdot(RaceDistance.FIVE_K, 1200)

        assert result.vdot == 50
        assert result.vdot_raw == pytest.approx(49.8062334, abs=1e-7)

    def test_invalid_race_time_raises(self):
        """Zero or negative race time should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            calculate_vdot(RaceDistance.TEN_K, 0)

        with pytest.raises(ValueError, match="must be positive"):
            calculate_vdot(RaceDistance.TEN_K, -100)

    def test_raw_vdot_range_is_enforced_before_rounding(self):
        with pytest.raises(ValueError, match="outside the supported range"):
            calculate_raw_vdot(RaceDistance.TEN_K, 9 * 60 * 60)


# ============================================================
# RACE EQUIVALENTS TESTS
# ============================================================


class TestRaceEquivalents:
    """Tests for race time predictions."""

    def test_10k_42_30_predicts_all_distances(self):
        """10K @ 42:30 should predict times for all distances."""
        equiv = calculate_race_equivalents(RaceDistance.TEN_K, 2550)

        assert equiv.vdot == 48
        assert equiv.source_race == RaceDistance.TEN_K

        # Should have predictions for all distances
        assert RaceDistance.FIVE_K in equiv.predictions
        assert RaceDistance.TEN_K in equiv.predictions
        assert RaceDistance.HALF_MARATHON in equiv.predictions
        assert RaceDistance.MARATHON in equiv.predictions

        # Source race time should match input
        assert equiv.source_time_formatted == "42:30"

    def test_5k_20_min_predicts_slower_10k(self):
        """5K @ 20:00 should predict slower 10K time."""
        equiv = calculate_race_equivalents(RaceDistance.FIVE_K, 1200)  # 20:00

        # 10K should be slower than 40:00 (not double the 5K time)
        ten_k_seconds = parse_time_string(equiv.predictions[RaceDistance.TEN_K])
        assert ten_k_seconds > 2400  # > 40:00

    def test_predictions_consistent_with_vdot(self):
        """Predictions should match VDOT table for that race distance."""
        # Use 10K @ 42:30
        equiv = calculate_race_equivalents(RaceDistance.TEN_K, 2550)
        # Cross-check: Calculate VDOT from predicted half marathon time
        half_time_str = equiv.predictions[RaceDistance.HALF_MARATHON]
        half_time_seconds = parse_time_string(half_time_str)

        # Rounded predicted seconds stay within one hundredth of a VDOT point.
        vdot_check = calculate_vdot(RaceDistance.HALF_MARATHON, half_time_seconds)
        assert abs(vdot_check.vdot_raw - equiv.vdot_raw) < 0.01


# ============================================================
# API INTEGRATION TESTS
# ============================================================


class TestVDOTAPIFunctions:
    """Tests for high-level API functions."""

    def test_api_calculate_vdot_from_race(self):
        """API function should parse string inputs and return result."""
        from resilio.api.vdot import calculate_vdot_from_race

        result = calculate_vdot_from_race("10k", "42:30")

        # Should return VDOTResult, not error
        assert hasattr(result, "vdot")
        assert result.vdot == 48

    def test_api_predict_race_times(self):
        """API function should predict race times."""
        from resilio.api.vdot import predict_race_times

        result = predict_race_times("10k", "42:30")

        assert hasattr(result, "predictions")
        assert RaceDistance.HALF_MARATHON in result.predictions

    def test_api_invalid_race_distance_returns_error(self):
        """API should return error for invalid race distance."""
        from resilio.api.vdot import calculate_vdot_from_race

        result = calculate_vdot_from_race("100k", "5:00:00")  # Invalid distance

        # Should return VDOTError
        assert hasattr(result, "error_type")
        assert result.error_type == "invalid_input"

    def test_api_invalid_time_format_returns_error(self):
        """API should return error for invalid time format."""
        from resilio.api.vdot import calculate_vdot_from_race

        result = calculate_vdot_from_race("10k", "invalid")

        assert hasattr(result, "error_type")
        assert result.error_type == "invalid_input"

    @pytest.mark.parametrize("race_time", ["1:60", "1:99", "00:99:99"])
    def test_api_rejects_out_of_range_clock_components(self, race_time):
        from resilio.api.vdot import VDOTError, calculate_vdot_from_race

        result = calculate_vdot_from_race("10k", race_time)

        assert isinstance(result, VDOTError)
        assert result.error_type == "invalid_input"

    @pytest.mark.parametrize("race_time", ["0:01", "9:00:00"])
    def test_api_rejects_performances_outside_supported_vdot_table(
        self,
        race_time,
    ):
        from resilio.api.vdot import VDOTError, calculate_vdot_from_race

        result = calculate_vdot_from_race("10k", race_time)

        assert isinstance(result, VDOTError)
        assert result.error_type == "out_of_range"


def test_estimate_current_vdot_rejects_unverifiable_approval(
    tmp_path,
    monkeypatch,
) -> None:
    from datetime import datetime, timezone
    from unittest.mock import Mock

    from resilio.api.vdot import VDOTError, estimate_current_vdot
    from resilio.schemas.approvals import (
        PlanningState,
        VDOTApproval,
        VDOTProposal,
    )

    approval = VDOTApproval(
        approval_id="vdot_approval_0123456789abcdef",
        approved_vdot=45,
        proposal_file=str(tmp_path / "missing-proposal.json"),
        proposal_file_sha256="0" * 64,
        evidence_type="race_performance",
        proposal_snapshot=VDOTProposal.model_validate(
            {
                "proposed_vdot": 45,
                "evidence": {
                    "evidence_type": "race_performance",
                    "race_distance": "10k",
                    "elapsed_time_seconds": 2700,
                    "performance_date": "2026-07-20",
                    "performance_timezone": "UTC",
                    "source_local_activity_id": "act_i_test",
                    "source_external_fingerprint_sha256": "a" * 64,
                },
                "evidence_summary": (
                    "The exact synchronized race evidence supports this baseline."
                ),
                "generated_at_utc": "2026-07-24T09:00:00Z",
            }
        ),
        approved_at_utc=datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    state = PlanningState(
        vdot_approvals=[approval],
        active_vdot_approval_id=approval.approval_id,
    )
    profile = Mock()
    profile.personal_bests_by_distance = {}
    profile.training_timezone = "UTC"
    monkeypatch.setattr(
        "resilio.api.vdot._load_profile_unlocked",
        lambda _repo: profile,
    )
    monkeypatch.setattr(
        "resilio.api.vdot._load_planning_state_unlocked",
        lambda _repo: state,
    )

    result = estimate_current_vdot(as_of_date=date(2026, 7, 30))

    assert isinstance(result, VDOTError)
    assert result.error_type == "stale_approval_evidence"


def test_estimate_current_vdot_rejects_future_approved_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    import hashlib
    import json
    from datetime import date, datetime, time, timedelta, timezone
    from unittest.mock import Mock

    from resilio.api.vdot import VDOTError, estimate_current_vdot
    from resilio.schemas.approvals import PlanningState, VDOTApproval, VDOTProposal

    as_of_date = date(2026, 7, 30)
    future_date = as_of_date + timedelta(days=1)
    generated_at_utc = datetime.combine(
        future_date,
        time(hour=9),
        tzinfo=timezone.utc,
    )
    proposal_path = tmp_path / "future-vdot.json"
    proposal_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "proposed_vdot": 45,
                "evidence": {
                    "evidence_type": "manual_athlete_value",
                    "athlete_confirmed_vdot": 45,
                    "confirmation_reference": "future-dated test confirmation",
                },
                "evidence_summary": ("Future-dated approved evidence must fail explicitly."),
                "generated_at_utc": generated_at_utc.isoformat(),
            }
        )
    )
    proposal_snapshot = VDOTProposal.model_validate_json(proposal_path.read_text())
    approval = VDOTApproval(
        approval_id="vdot_approval_0123456789abcdef",
        approved_vdot=45,
        proposal_file=str(proposal_path),
        proposal_file_sha256=hashlib.sha256(proposal_path.read_bytes()).hexdigest(),
        evidence_type="manual_athlete_value",
        proposal_snapshot=proposal_snapshot,
        approved_at_utc=generated_at_utc,
    )
    state = PlanningState(
        vdot_approvals=[approval],
        active_vdot_approval_id=approval.approval_id,
    )
    profile = Mock()
    profile.personal_bests_by_distance = {}
    profile.training_timezone = "UTC"
    monkeypatch.setattr(
        "resilio.api.vdot._load_profile_unlocked",
        lambda _repo: profile,
    )
    monkeypatch.setattr(
        "resilio.api.vdot._load_planning_state_unlocked",
        lambda _repo: state,
    )

    result = estimate_current_vdot(as_of_date=as_of_date)

    assert isinstance(result, VDOTError)
    assert result.error_type == "invalid_input"


# ============================================================
# VDOT ESTIMATION TESTS (RACE HISTORY FALLBACK)
# ============================================================


class TestVDOTEstimationRaceHistoryFallback:
    """Tests for estimate_current_vdot() race history fallback."""

    as_of_date = date(2026, 7, 30)

    @pytest.fixture(autouse=True)
    def no_approved_vdot(self, monkeypatch):
        """Exercise race fallback independently of the live planning aggregate."""
        monkeypatch.setattr(
            "resilio.api.vdot._load_planning_state_unlocked",
            lambda _repo: None,
        )

    def test_fallback_recent_race_no_decay(self, tmp_path, monkeypatch):
        """Test VDOT estimation fallback with recent race (<3 months) - no decay."""
        from datetime import timedelta
        from unittest.mock import Mock

        from resilio.api.vdot import estimate_current_vdot
        from resilio.schemas.vdot import VDOTEstimate

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("RESILIO_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("resilio.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create mock profile with recent PB (2 months ago)
        mock_profile = Mock()
        recent_pb_date = (self.as_of_date - timedelta(days=60)).isoformat()
        mock_profile.personal_bests_by_distance = {
            "10k": Mock(
                time="42:30",
                performance_date=date.fromisoformat(recent_pb_date),
                vdot=45.0,
            )
        }

        # Mock get_profile to return our mock profile
        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr(
            "resilio.api.vdot._load_profile_unlocked",
            lambda _repo: mock_get_profile(),
        )

        # Execute
        result = estimate_current_vdot(
            lookback_days=90,
            as_of_date=self.as_of_date,
        )

        # Verify
        assert isinstance(result, VDOTEstimate)
        assert result.estimated_vdot == 45  # No decay for recent PB
        assert result.evidence_type == "personal_best"
        assert result.evidence_age_days == 60
        assert result.applicability_window_days == 90
        assert "recent_personal_best" in result.source
        assert "10k" in result.source
        assert recent_pb_date in result.source

    def test_stale_race_is_not_silently_decayed(self, tmp_path, monkeypatch):
        """Old race evidence must remain old rather than becoming inferred fitness."""
        from datetime import date, timedelta
        from unittest.mock import Mock

        from resilio.api.vdot import VDOTError, estimate_current_vdot

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("RESILIO_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("resilio.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create mock profile with 4-month old PB
        mock_profile = Mock()
        old_pb_date = (self.as_of_date - timedelta(days=120)).isoformat()
        mock_profile.personal_bests_by_distance = {
            "10k": Mock(
                time="42:30",
                performance_date=date.fromisoformat(old_pb_date),
                vdot=45.0,
            )
        }

        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr(
            "resilio.api.vdot._load_profile_unlocked",
            lambda _repo: mock_get_profile(),
        )

        # Execute
        result = estimate_current_vdot(
            lookback_days=28,
            as_of_date=self.as_of_date,
        )

        # Verify
        assert isinstance(result, VDOTError)
        assert result.error_type == "not_found"
        assert "120 days old" in result.message

    def test_year_old_race_is_not_presented_as_current(self, tmp_path, monkeypatch):
        """A year-old performance cannot become a current VDOT through a heuristic."""
        from datetime import date, timedelta
        from unittest.mock import Mock

        from resilio.api.vdot import VDOTError, estimate_current_vdot

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("RESILIO_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("resilio.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create mock profile with 12-month old PB
        mock_profile = Mock()
        old_pb_date = (self.as_of_date - timedelta(days=365)).isoformat()
        mock_profile.personal_bests_by_distance = {
            "10k": Mock(
                time="49:33",
                performance_date=date.fromisoformat(old_pb_date),
                vdot=38.0,
            )
        }

        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr(
            "resilio.api.vdot._load_profile_unlocked",
            lambda _repo: mock_get_profile(),
        )

        # Execute
        result = estimate_current_vdot(
            lookback_days=28,
            as_of_date=self.as_of_date,
        )

        # Verify
        assert isinstance(result, VDOTError)
        assert result.error_type == "not_found"
        assert "365 days old" in result.message

    def test_fallback_uses_most_recent_race(self, tmp_path, monkeypatch):
        """Test that fallback uses the most recent race when multiple exist."""
        from datetime import timedelta
        from unittest.mock import Mock

        from resilio.api.vdot import estimate_current_vdot
        from resilio.schemas.vdot import VDOTEstimate

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("RESILIO_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("resilio.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create mock profile with multiple PBs
        mock_profile = Mock()
        mock_profile.personal_bests_by_distance = {
            "10k": Mock(  # Older PB
                time="50:00",
                performance_date=self.as_of_date - timedelta(days=365),
                vdot=35.0,
            ),
            "5k": Mock(  # More recent PB - should be used
                time="22:30",
                performance_date=self.as_of_date - timedelta(days=60),
                vdot=42.0,
            ),
        }

        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr(
            "resilio.api.vdot._load_profile_unlocked",
            lambda _repo: mock_get_profile(),
        )

        # Execute
        result = estimate_current_vdot(
            lookback_days=90,
            as_of_date=self.as_of_date,
        )

        # Verify - should use the 5K PB (more recent, VDOT 42)
        assert isinstance(result, VDOTEstimate)
        assert result.estimated_vdot == 42
        assert "5k" in result.source

    def test_no_workouts_no_pbs_returns_error(self, tmp_path, monkeypatch):
        """Test that error is returned when no workouts and no PBs."""
        from unittest.mock import Mock

        from resilio.api.vdot import VDOTError, estimate_current_vdot

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("RESILIO_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("resilio.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create mock profile with no PBs
        mock_profile = Mock()
        mock_profile.personal_bests_by_distance = {}

        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr(
            "resilio.api.vdot._load_profile_unlocked",
            lambda _repo: mock_get_profile(),
        )

        # Execute
        result = estimate_current_vdot(
            lookback_days=28,
            as_of_date=self.as_of_date,
        )

        # Verify
        assert isinstance(result, VDOTError)
        assert result.error_type == "not_found"
        assert "No approved VDOT" in result.message

    def test_very_old_race_is_rejected_instead_of_clamped(self, tmp_path, monkeypatch):
        """No arbitrary decay or floor may manufacture a current VDOT."""
        from datetime import date, timedelta
        from unittest.mock import Mock

        from resilio.api.vdot import VDOTError, estimate_current_vdot

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("RESILIO_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("resilio.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create mock profile with very old, low VDOT PB
        mock_profile = Mock()
        old_pb_date = (self.as_of_date - timedelta(days=730)).isoformat()
        mock_profile.personal_bests_by_distance = {
            "10k": Mock(
                time="55:00",
                performance_date=date.fromisoformat(old_pb_date),
                vdot=32.0,
            )
        }

        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr(
            "resilio.api.vdot._load_profile_unlocked",
            lambda _repo: mock_get_profile(),
        )

        # Execute
        result = estimate_current_vdot(
            lookback_days=28,
            as_of_date=self.as_of_date,
        )

        # Verify - should clamp to minimum of 30
        assert isinstance(result, VDOTError)
        assert result.error_type == "not_found"
        assert "730 days old" in result.message
