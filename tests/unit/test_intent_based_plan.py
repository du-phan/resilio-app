"""Unit tests for intent-based workout generation."""

import pytest
from datetime import date

from sports_coach_engine.api.plan import (
    _distribute_evenly,
    _calculate_date,
    _create_workout_prescription,
    _generate_workouts_from_pattern,
    suggest_optimal_run_count,
    _score_run_distribution,
)


class TestDistributeEvenly:
    """Test even distribution of volume across runs."""

    def test_distribute_evenly_simple(self):
        """Test simple even distribution."""
        distances = _distribute_evenly(12.0, 3)
        assert len(distances) == 3
        assert sum(distances) == 12.0
        # All should be close to 4.0km
        assert all(3.5 <= d <= 4.5 for d in distances)

    def test_distribute_evenly_uneven(self):
        """Test distribution with rounding adjustment."""
        distances = _distribute_evenly(12.5, 3)
        assert len(distances) == 3
        assert sum(distances) == 12.5
        # Should be approximately 4.17km each
        assert all(3.5 <= d <= 4.5 for d in distances)

    def test_distribute_evenly_real_example(self):
        """Test real example from Du's plan (Week 1)."""
        # Week 1: 23km - 10.5km long run = 12.5km for 3 easy runs
        distances = _distribute_evenly(12.5, 3)
        assert len(distances) == 3
        assert sum(distances) == 12.5
        # Expect: [4.0, 4.5, 4.0] or similar
        assert 4.0 <= distances[0] <= 4.5
        assert 4.0 <= distances[1] <= 5.0
        assert 4.0 <= distances[2] <= 4.5

    def test_distribute_evenly_single_run(self):
        """Test distribution with single run."""
        distances = _distribute_evenly(10.0, 1)
        assert len(distances) == 1
        assert distances[0] == 10.0

    def test_distribute_evenly_many_runs(self):
        """Test distribution across many runs."""
        distances = _distribute_evenly(35.0, 5)
        assert len(distances) == 5
        assert sum(distances) == 35.0
        # Each should be around 7km
        assert all(6.0 <= d <= 8.0 for d in distances)


class TestCalculateDate:
    """Test date calculation from week start and day of week."""

    def test_calculate_date_monday(self):
        """Test Monday (day 1)."""
        # Week starting 2026-01-19 (Monday)
        result = _calculate_date("2026-01-19", 1)
        assert result == "2026-01-19"

    def test_calculate_date_tuesday(self):
        """Test Tuesday (day 2)."""
        result = _calculate_date("2026-01-19", 2)
        assert result == "2026-01-20"

    def test_calculate_date_sunday(self):
        """Test Sunday (day 7)."""
        result = _calculate_date("2026-01-19", 7)
        assert result == "2026-01-25"

    def test_calculate_date_wednesday(self):
        """Test Wednesday (day 3)."""
        result = _calculate_date("2026-01-19", 3)
        assert result == "2026-01-21"


class TestCreateWorkoutPrescription:
    """Test workout prescription creation."""

    def test_create_easy_workout(self):
        """Test creating easy run prescription."""
        workout = _create_workout_prescription(
            week_number=1,
            date_str="2026-01-20",
            day_of_week=2,
            distance_km=5.0,
            workout_type="easy",
            phase="base",
            pace_range="6:30-6:50",
            max_hr=189
        )

        # Check required fields
        assert workout["week_number"] == 1
        assert workout["date"] == "2026-01-20"
        assert workout["day_of_week"] == 2
        assert workout["distance_km"] == 5.0
        assert workout["workout_type"] == "easy"
        assert workout["phase"] == "base"
        assert workout["pace_range_min_km"] == "6:30"
        assert workout["pace_range_max_km"] == "6:50"
        assert workout["intensity_zone"] == "zone_2"
        assert workout["target_rpe"] == 4
        assert workout["status"] == "scheduled"
        assert workout["key_workout"] is False

        # Check HR zones are reasonable (65-75% of 189 = 123-142)
        assert 120 <= workout["hr_range_low"] <= 130
        assert 135 <= workout["hr_range_high"] <= 145

        # Check duration is reasonable (5km at ~6:40 pace = ~33min)
        assert 30 <= workout["duration_minutes"] <= 40

    def test_create_long_run_workout(self):
        """Test creating long run prescription."""
        workout = _create_workout_prescription(
            week_number=1,
            date_str="2026-01-25",
            day_of_week=7,
            distance_km=10.5,
            workout_type="long_run",
            phase="base",
            pace_range="6:30-6:50",
            max_hr=189
        )

        # Check long run specifics
        assert workout["workout_type"] == "long_run"
        assert workout["distance_km"] == 10.5
        assert workout["key_workout"] is True  # Long runs are key workouts

        # Duration should be ~70min (10.5km at ~6:40 pace)
        assert 60 <= workout["duration_minutes"] <= 80


class TestGenerateWorkoutsFromPattern:
    """Test complete workout generation from pattern."""

    def test_generate_week1_pattern(self):
        """Test Week 1 from Du's plan (23km, 3 easy + 1 long)."""
        pattern = {
            "structure": "3 easy + 1 long",
            "run_days": [2, 4, 6, 7],  # Tue, Thu, Sat, Sun
            "long_run_day": 7,  # Sunday
            "long_run_pct": 0.45,
            "easy_run_paces": "6:30-6:50",
            "long_run_pace": "6:30-6:50"
        }

        workouts = _generate_workouts_from_pattern(
            week_number=1,
            target_volume_km=23.0,
            pattern=pattern,
            start_date="2026-01-19",
            phase="base",
            max_hr=189
        )

        # Check count
        assert len(workouts) == 4

        # Check total distance
        total_distance = sum(w["distance_km"] for w in workouts)
        assert total_distance == 23.0, f"Total distance {total_distance} != 23.0"

        # Check long run
        long_runs = [w for w in workouts if w["workout_type"] == "long_run"]
        assert len(long_runs) == 1
        assert long_runs[0]["day_of_week"] == 7  # Sunday
        assert long_runs[0]["date"] == "2026-01-25"
        # Long run should be ~45% of 23km = ~10.5km
        assert 10.0 <= long_runs[0]["distance_km"] <= 11.0

        # Check easy runs
        easy_runs = [w for w in workouts if w["workout_type"] == "easy"]
        assert len(easy_runs) == 3
        # Each easy run should be reasonable (3.5-5.5km)
        for run in easy_runs:
            assert 3.5 <= run["distance_km"] <= 5.5

        # Check dates
        dates = [w["date"] for w in workouts]
        expected_dates = ["2026-01-20", "2026-01-22", "2026-01-24", "2026-01-25"]
        assert sorted(dates) == sorted(expected_dates)

    def test_generate_week4_pattern(self):
        """Test Week 4 from Du's plan (21km, 2 easy + 1 long, recovery)."""
        pattern = {
            "structure": "2 easy + 1 long",
            "run_days": [2, 4, 7],  # Tue, Thu, Sun
            "long_run_day": 7,  # Sunday
            "long_run_pct": 0.52,
            "easy_run_paces": "6:30-6:50",
            "long_run_pace": "6:30-6:50"
        }

        workouts = _generate_workouts_from_pattern(
            week_number=4,
            target_volume_km=21.0,
            pattern=pattern,
            start_date="2026-02-09",
            phase="recovery",
            max_hr=189
        )

        # Check count
        assert len(workouts) == 3

        # Check total distance
        total_distance = sum(w["distance_km"] for w in workouts)
        assert total_distance == 21.0, f"Total distance {total_distance} != 21.0"

        # Check long run is larger percentage (52%)
        long_runs = [w for w in workouts if w["workout_type"] == "long_run"]
        assert len(long_runs) == 1
        # Long run should be ~52% of 21km = ~11km
        assert 10.5 <= long_runs[0]["distance_km"] <= 11.5

        # Check easy runs
        easy_runs = [w for w in workouts if w["workout_type"] == "easy"]
        assert len(easy_runs) == 2

    def test_generate_arithmetic_guaranteed(self):
        """Test that arithmetic is always correct regardless of inputs."""
        test_cases = [
            (23.0, 4, 0.45),  # Week 1
            (26.0, 4, 0.46),  # Week 2
            (30.0, 4, 0.45),  # Week 3
            (21.0, 3, 0.52),  # Week 4
            (18.0, 3, 0.44),  # Low volume
            (48.0, 5, 0.40),  # High volume
        ]

        for target_km, num_runs, long_pct in test_cases:
            pattern = {
                "structure": f"{num_runs-1} easy + 1 long",
                "run_days": list(range(1, num_runs + 1)),
                "long_run_day": num_runs,
                "long_run_pct": long_pct,
                "easy_run_paces": "6:30-6:50",
                "long_run_pace": "6:30-6:50"
            }

            workouts = _generate_workouts_from_pattern(
                week_number=1,
                target_volume_km=target_km,
                pattern=pattern,
                start_date="2026-01-19",
                phase="base",
                max_hr=189
            )

            # THE CRITICAL TEST: Sum must equal target exactly
            total_distance = sum(w["distance_km"] for w in workouts)
            assert abs(total_distance - target_km) < 0.01, \
                f"Arithmetic error: {total_distance} != {target_km} for {num_runs} runs with {long_pct} long run %"

    def test_generate_pattern_missing_field(self):
        """Test that missing pattern fields raise appropriate error."""
        pattern = {
            # Missing run_days
            "long_run_day": 7,
            "long_run_pct": 0.45,
            "easy_run_paces": "6:30-6:50",
            "long_run_pace": "6:30-6:50"
        }

        with pytest.raises(KeyError):
            _generate_workouts_from_pattern(
                week_number=1,
                target_volume_km=23.0,
                pattern=pattern,
                start_date="2026-01-19",
                phase="base",
                max_hr=189
            )


class TestIntegrationArithmetic:
    """Integration tests focusing on arithmetic correctness."""

    def test_no_arithmetic_errors_across_weeks(self):
        """Test that arithmetic is correct across multiple weeks."""
        weeks = [
            {"target_km": 23.0, "runs": 4, "long_pct": 0.45},
            {"target_km": 26.0, "runs": 4, "long_pct": 0.46},
            {"target_km": 30.0, "runs": 4, "long_pct": 0.45},
            {"target_km": 21.0, "runs": 3, "long_pct": 0.52},
        ]

        for i, week_spec in enumerate(weeks, 1):
            pattern = {
                "structure": f"{week_spec['runs']-1} easy + 1 long",
                "run_days": list(range(1, week_spec['runs'] + 1)),
                "long_run_day": week_spec['runs'],
                "long_run_pct": week_spec['long_pct'],
                "easy_run_paces": "6:30-6:50",
                "long_run_pace": "6:30-6:50"
            }

            workouts = _generate_workouts_from_pattern(
                week_number=i,
                target_volume_km=week_spec['target_km'],
                pattern=pattern,
                start_date="2026-01-19",
                phase="base",
                max_hr=189
            )

            # Verify sum
            total = sum(w["distance_km"] for w in workouts)
            assert abs(total - week_spec['target_km']) < 0.01, \
                f"Week {i}: {total} != {week_spec['target_km']}"


class TestSuggestOptimalRunCount:
    """Test intelligent run count suggestion."""

    def test_suggest_optimal_run_count_low_volume(self):
        """Test that low volume recommends fewer runs."""
        result = suggest_optimal_run_count(
            target_volume_km=18.0,
            max_runs=4,
            phase="base"
        )

        # Should recommend 2-3 runs, not 4
        assert result["recommended_runs"] <= 3
        assert "below" in result["rationale"].lower() or result["recommended_runs"] < 4

        # Check distribution preview exists
        assert "with_2_runs" in result["distribution_preview"]
        assert "with_3_runs" in result["distribution_preview"]
        assert "with_4_runs" in result["distribution_preview"]

        # Check that 4 runs option has concerns
        four_runs = result["distribution_preview"]["with_4_runs"]
        assert len(four_runs["concerns"]) > 0

    def test_suggest_optimal_run_count_high_volume(self):
        """Test that high volume can use max runs."""
        result = suggest_optimal_run_count(
            target_volume_km=35.0,
            max_runs=4,
            phase="base"
        )

        # Should be able to use 4 runs safely
        assert result["recommended_runs"] == 4

        # 4 runs option should have no concerns
        four_runs = result["distribution_preview"]["with_4_runs"]
        assert len(four_runs["concerns"]) == 0

        # All easy runs should be above minimum
        assert all(d >= 5.0 for d in four_runs["easy"])

    def test_run_count_distribution_preview(self):
        """Test distribution preview shows all options."""
        result = suggest_optimal_run_count(
            target_volume_km=23.0,
            max_runs=4,
            phase="base"
        )

        # Should have previews for 2, 3, and 4 runs
        assert "with_2_runs" in result["distribution_preview"]
        assert "with_3_runs" in result["distribution_preview"]
        assert "with_4_runs" in result["distribution_preview"]

        # Each preview should have required fields
        for key in result["distribution_preview"]:
            preview = result["distribution_preview"][key]
            assert "easy" in preview
            assert "long" in preview
            assert "avg_easy" in preview
            assert "concerns" in preview

            # Verify arithmetic
            total = sum(preview["easy"]) + preview["long"]
            assert abs(total - 23.0) < 0.5  # Allow small rounding difference

    def test_suggest_recovery_week_uses_fewer_runs(self):
        """Test that recovery weeks with lower volume use fewer runs."""
        result = suggest_optimal_run_count(
            target_volume_km=21.0,
            max_runs=4,
            phase="recovery"
        )

        # Recovery with 21km should recommend fewer runs
        assert result["recommended_runs"] <= 3

    def test_suggest_with_profile_minimums(self):
        """Test that athlete profile minimums are respected."""
        profile = {
            "typical_easy_distance_km": 7.0,
            "typical_long_run_distance_km": 12.0
        }

        result = suggest_optimal_run_count(
            target_volume_km=25.0,
            max_runs=4,
            phase="base",
            profile=profile
        )

        # With higher minimums (80% of 7km = 5.6km, 80% of 12km = 9.6km)
        # Should adjust recommendations accordingly
        assert result["easy_min_km"] == 5.6
        assert result["long_min_km"] == 9.6

    def test_minimum_and_comfortable_volumes(self):
        """Test that minimum/comfortable volume calculations are correct."""
        result = suggest_optimal_run_count(
            target_volume_km=23.0,
            max_runs=4,
            phase="base"
        )

        # For 4 runs: (4-1) × 5 + 8 = 23km minimum
        assert result["minimum_volume_for_max_runs"] == 23.0

        # Comfortable: 23 + 4 = 27km
        assert result["comfortable_volume_for_max_runs"] == 27.0


class TestScoreRunDistribution:
    """Test run distribution scoring function."""

    def test_score_penalizes_short_easy_runs(self):
        """Test that short easy runs get lower scores."""
        # Good distribution: 6km easy runs
        good_score = _score_run_distribution(
            avg_easy=6.0,
            long_km=10.0,
            total_km=28.0,
            easy_min=5.0,
            long_min=8.0
        )

        # Bad distribution: 3km easy runs (below minimum)
        bad_score = _score_run_distribution(
            avg_easy=3.0,
            long_km=10.0,
            total_km=19.0,
            easy_min=5.0,
            long_min=8.0
        )

        assert good_score > bad_score

    def test_score_rewards_sweet_spot(self):
        """Test that sweet spot (min+1 to min+2) gets bonus."""
        # Sweet spot: 6km (5 + 1)
        sweet_score = _score_run_distribution(
            avg_easy=6.0,
            long_km=10.0,
            total_km=28.0,
            easy_min=5.0,
            long_min=8.0
        )

        # Above sweet spot: 8km
        high_score = _score_run_distribution(
            avg_easy=8.0,
            long_km=10.0,
            total_km=34.0,
            easy_min=5.0,
            long_min=8.0
        )

        # Sweet spot should have bonus
        assert sweet_score > high_score

    def test_score_optimal_long_run_percentage(self):
        """Test that 40-50% long run percentage gets rewarded."""
        # Optimal: 45% long run
        optimal_score = _score_run_distribution(
            avg_easy=6.0,
            long_km=12.0,  # 45% of ~27km
            total_km=27.0,
            easy_min=5.0,
            long_min=8.0
        )

        # Too small: 30% long run
        small_score = _score_run_distribution(
            avg_easy=7.0,
            long_km=9.0,  # 30% of 30km
            total_km=30.0,
            easy_min=5.0,
            long_min=8.0
        )

        # Too large: 60% long run
        large_score = _score_run_distribution(
            avg_easy=5.0,
            long_km=15.0,  # 60% of 25km
            total_km=25.0,
            easy_min=5.0,
            long_min=8.0
        )

        # Optimal should score higher than both extremes
        assert optimal_score > small_score
        assert optimal_score > large_score
