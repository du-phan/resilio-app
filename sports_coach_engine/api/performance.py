"""Performance API - Performance baseline and fitness tracking.

Provides functions for Claude Code to assess current vs. historical performance:
- api_get_performance_baseline() - Consolidated performance view
"""

from datetime import date, datetime
from typing import Union, Optional, Dict, Any
from dataclasses import dataclass

from sports_coach_engine.api.profile import get_profile, ProfileError
from sports_coach_engine.api.metrics import get_current_metrics, MetricsError
from sports_coach_engine.api.vdot import (
    estimate_current_vdot as api_vdot_estimate_current,
    calculate_vdot_from_race,
    predict_race_times,
    VDOTError,
)
from sports_coach_engine.core.vdot import calculate_race_equivalents
from sports_coach_engine.schemas.vdot import RaceDistance


# ============================================================
# ERROR TYPES
# ============================================================


@dataclass
class PerformanceError:
    """Error result from performance operations."""

    error_type: str  # "not_found", "insufficient_data", "validation", "unknown"
    message: str


# ============================================================
# DATA TYPES
# ============================================================


@dataclass
class PerformanceBaseline:
    """Consolidated performance baseline data."""

    # Current fitness
    current_fitness: Dict[str, Any]  # {vdot_estimate, vdot_source, confidence, ctl, ctl_interpretation}

    # Peak performance (from profile)
    peak_performance: Dict[str, Any]  # {peak_vdot, peak_vdot_date, months_since_peak, regression_vdot, regression_percentage}

    # Race history (personal bests)
    race_history: Dict[str, Any]  # {personal_bests: [...], total_races}

    # Training patterns (from profile analysis)
    training_patterns: Optional[Dict[str, Any]]  # {typical_easy_pace, typical_easy_distance, typical_long_run_distance, weekly_volume_recent_4wk}

    # Equivalent race times at current VDOT
    equivalent_race_times_current_vdot: Dict[str, str]  # {"5k": "21:05", "10k": "43:40", ...}

    # Interpretation summary
    interpretation: str


# ============================================================
# PUBLIC API FUNCTIONS
# ============================================================


def api_get_performance_baseline(
    lookback_days: int = 28,
) -> Union[PerformanceBaseline, PerformanceError]:
    """Get consolidated performance baseline data.

    Combines current fitness (VDOT estimate, CTL) with historical performance
    (peak VDOT, race history) to provide complete performance context.

    Workflow:
    1. Get current VDOT estimate from recent workouts (api_vdot_estimate_current)
    2. Get current CTL from metrics (api_get_metrics)
    3. Get peak VDOT and race history from profile (get_profile)
    4. Calculate equivalent race times at current VDOT
    5. Compute regression/progression vs. peak
    6. Generate interpretation summary

    Args:
        lookback_days: Number of days to look back for VDOT estimation (default: 28)

    Returns:
        PerformanceBaseline with complete performance context

        PerformanceError on failure

    Example:
        >>> baseline = api_get_performance_baseline(lookback_days=28)
        >>> if isinstance(baseline, PerformanceError):
        ...     print(f"Error: {baseline.message}")
        ... else:
        ...     print(f"Current VDOT: {baseline.current_fitness['vdot_estimate']}")
        ...     print(f"Peak VDOT: {baseline.peak_performance['peak_vdot']}")
        ...     print(f"Interpretation: {baseline.interpretation}")
    """
    # 1. Get current VDOT estimate
    vdot_result = api_vdot_estimate_current(lookback_days=lookback_days)

    current_vdot: Optional[int] = None
    vdot_source: Optional[str] = None
    vdot_confidence: Optional[str] = None

    if not isinstance(vdot_result, VDOTError):
        current_vdot = vdot_result.estimated_vdot
        vdot_source = vdot_result.source
        vdot_confidence = vdot_result.confidence.value

    # 2. Get current CTL
    metrics_result = get_current_metrics()

    current_ctl: Optional[float] = None
    ctl_interpretation: Optional[str] = None

    if not isinstance(metrics_result, MetricsError):
        current_ctl = metrics_result.ctl.value
        ctl_interpretation = metrics_result.ctl.interpretation

    # 3. Get profile data (peak VDOT, race history)
    profile_result = get_profile()

    peak_vdot: Optional[int] = None
    peak_vdot_date: Optional[str] = None
    race_history_data: list = []

    typical_easy_pace: Optional[str] = None
    typical_easy_distance: Optional[float] = None
    typical_long_run_distance: Optional[float] = None
    weekly_volume_recent: Optional[float] = None

    if not isinstance(profile_result, ProfileError):
        peak_vdot = profile_result.peak_vdot
        peak_vdot_date = profile_result.peak_vdot_date

        # Extract race history
        if profile_result.race_history:
            for race in profile_result.race_history:
                race_vdot_result = calculate_vdot_from_race(
                    race_distance=race.distance.value,
                    race_time=race.time,
                    race_date=race.date,
                )

                race_vdot = None
                if not isinstance(race_vdot_result, VDOTError):
                    race_vdot = race_vdot_result.vdot

                race_history_data.append({
                    "distance": race.distance.value,
                    "time": race.time,
                    "vdot": race_vdot,
                    "date": race.date,
                })

        # Extract training patterns
        if profile_result.typical_easy_distance_km:
            typical_easy_distance = profile_result.typical_easy_distance_km
        if profile_result.typical_long_run_distance_km:
            typical_long_run_distance = profile_result.typical_long_run_distance_km

    # 4. Calculate equivalent race times at current VDOT
    equivalent_times: Dict[str, str] = {}

    if current_vdot:
        # Use VDOT table to get equivalent race times
        try:
            from sports_coach_engine.core.vdot.tables import VDOT_TABLE

            # Find VDOT entry
            vdot_entry = next((entry for entry in VDOT_TABLE if entry.vdot == current_vdot), None)

            if vdot_entry:
                equivalent_times = {
                    "5k": _format_time(vdot_entry.race_5k_seconds),
                    "10k": _format_time(vdot_entry.race_10k_seconds),
                    "half_marathon": _format_time(vdot_entry.race_half_marathon_seconds),
                    "marathon": _format_time(vdot_entry.race_marathon_seconds),
                }
        except Exception:
            # If VDOT table lookup fails, leave equivalent_times empty
            pass

    # 5. Compute regression/progression vs. peak
    months_since_peak: Optional[int] = None
    regression_vdot: Optional[int] = None
    regression_percentage: Optional[float] = None

    if peak_vdot and peak_vdot_date and current_vdot:
        try:
            peak_date = datetime.fromisoformat(peak_vdot_date).date()
            today = date.today()
            months_since_peak = ((today.year - peak_date.year) * 12 + today.month - peak_date.month)
            regression_vdot = current_vdot - peak_vdot
            regression_percentage = (regression_vdot / peak_vdot) * 100
        except Exception:
            pass

    # 6. Generate interpretation
    interpretation = _generate_interpretation(
        current_vdot=current_vdot,
        peak_vdot=peak_vdot,
        regression_vdot=regression_vdot,
        regression_percentage=regression_percentage,
        current_ctl=current_ctl,
    )

    # Build result
    current_fitness_data = {
        "vdot_estimate": current_vdot,
        "vdot_source": vdot_source,
        "confidence": vdot_confidence,
        "ctl": current_ctl,
        "ctl_interpretation": ctl_interpretation,
    }

    peak_performance_data = {
        "peak_vdot": peak_vdot,
        "peak_vdot_date": peak_vdot_date,
        "months_since_peak": months_since_peak,
        "regression_vdot": regression_vdot,
        "regression_percentage": regression_percentage,
    }

    race_history_result = {
        "personal_bests": race_history_data,
        "total_races": len(race_history_data),
    }

    training_patterns_data = None
    if any([typical_easy_distance, typical_long_run_distance]):
        training_patterns_data = {
            "typical_easy_distance": typical_easy_distance,
            "typical_long_run_distance": typical_long_run_distance,
        }

    baseline = PerformanceBaseline(
        current_fitness=current_fitness_data,
        peak_performance=peak_performance_data,
        race_history=race_history_result,
        training_patterns=training_patterns_data,
        equivalent_race_times_current_vdot=equivalent_times,
        interpretation=interpretation,
    )

    return baseline


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _format_time(seconds: int) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def _generate_interpretation(
    current_vdot: Optional[int],
    peak_vdot: Optional[int],
    regression_vdot: Optional[int],
    regression_percentage: Optional[float],
    current_ctl: Optional[float],
) -> str:
    """Generate human-readable interpretation of performance baseline."""

    if not current_vdot:
        return "Unable to estimate current fitness. No quality workouts found in recent training."

    if not peak_vdot:
        return f"Current fitness estimated at VDOT {current_vdot}. No historical peak data available."

    if regression_vdot is not None and regression_percentage is not None:
        if regression_vdot > 0:
            return f"Current fitness (VDOT {current_vdot}) is {abs(regression_percentage):.1f}% above peak (VDOT {peak_vdot}). Excellent progression!"
        elif regression_vdot < 0:
            ctl_note = f" CTL: {current_ctl:.0f}" if current_ctl else ""
            return f"Current fitness (VDOT {current_vdot}) is {abs(regression_percentage):.1f}% below peak (VDOT {peak_vdot}).{ctl_note}"
        else:
            return f"Current fitness (VDOT {current_vdot}) matches historical peak (VDOT {peak_vdot}). Excellent consistency!"

    return f"Current fitness estimated at VDOT {current_vdot}."
