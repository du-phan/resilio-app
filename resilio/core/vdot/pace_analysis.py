"""Recent pace analysis for VDOT estimation.

This module analyzes recent running activities to estimate current VDOT from:
1. Quality workouts (tempo, threshold, interval) - existing logic
2. Easy runs detected by HR zones - NEW
3. Fallback to user-provided easy pace if no HR data

Key Innovation: HR-based easy pace detection
- Uses 65-78% max HR to identify easy efforts (Daniels' E-pace zone)
- Infers VDOT from easy paces using VDOT table
- More data points = more robust estimates
"""

from typing import List, Optional, Tuple
from datetime import date, timedelta

from resilio.schemas.vdot import (
    WorkoutPaceData,
    EasyPaceData,
    PaceAnalysisResult,
)
from resilio.schemas.activity import NormalizedActivity
from resilio.core.vdot.tables import VDOT_TABLE


def calculate_easy_hr_range(max_hr: int) -> Tuple[int, int]:
    """
    Calculate easy HR zone (65-78% max HR).

    Based on Daniels' E-pace: conversational effort, aerobic development.

    Args:
        max_hr: Maximum heart rate

    Returns:
        Tuple of (min_hr, max_hr) for easy zone
    """
    min_hr = int(max_hr * 0.65)
    max_hr_zone = int(max_hr * 0.78)
    return (min_hr, max_hr_zone)


def is_easy_effort_by_hr(activity: NormalizedActivity, max_hr: int) -> bool:
    """
    Check if activity is an easy effort based on heart rate.

    Args:
        activity: Activity to check
        max_hr: Athlete's max HR

    Returns:
        True if average HR falls in easy zone (65-78% max)
    """
    if not activity.average_hr or not max_hr:
        return False

    min_hr, max_hr_zone = calculate_easy_hr_range(max_hr)
    return min_hr <= activity.average_hr <= max_hr_zone


def is_quality_workout(activity: NormalizedActivity) -> bool:
    """
    Check if activity is a quality workout (tempo, threshold, interval).

    Uses keyword detection in title/description.

    Args:
        activity: Activity to check

    Returns:
        True if quality workout keywords detected
    """
    quality_keywords = ["tempo", "threshold", "interval", "track", "speed", "workout"]
    title = (activity.name or "").lower()
    description = (activity.description or "").lower()

    return any(keyword in title or keyword in description for keyword in quality_keywords)


def find_vdot_from_pace(pace_sec_per_km: int, zone_type: str = "threshold") -> Optional[int]:
    """
    Find VDOT that corresponds to a given pace.

    Searches VDOT table for entry where pace falls within zone range (±5 sec tolerance).

    Args:
        pace_sec_per_km: Pace in seconds per km
        zone_type: Zone type ("easy", "threshold", "interval")

    Returns:
        VDOT value, or None if pace out of range
    """
    # Map zone type to table fields
    pace_field_map = {
        "threshold": ("threshold_min_sec_per_km", "threshold_max_sec_per_km"),
        "interval": ("interval_min_sec_per_km", "interval_max_sec_per_km"),
        "easy": ("easy_min_sec_per_km", "easy_max_sec_per_km"),
    }

    if zone_type not in pace_field_map:
        return None

    min_field, max_field = pace_field_map[zone_type]

    # Find VDOT where pace falls within range
    for entry in VDOT_TABLE:
        min_pace = getattr(entry, min_field)
        max_pace = getattr(entry, max_field)

        # Check if pace falls within this VDOT's range (with tolerance)
        if min_pace - 5 <= pace_sec_per_km <= max_pace + 5:
            return entry.vdot

    return None


def find_vdot_from_easy_pace(pace_sec_per_km: int) -> Optional[int]:
    """
    Find VDOT from easy pace.

    Wrapper for find_vdot_from_pace with zone_type="easy".

    Args:
        pace_sec_per_km: Easy pace in seconds per km

    Returns:
        VDOT value, or None if pace out of range
    """
    return find_vdot_from_pace(pace_sec_per_km, "easy")


def analyze_recent_paces(
    activities: List[NormalizedActivity],
    lookback_days: int,
    max_hr: Optional[int] = None
) -> PaceAnalysisResult:
    """
    Analyze recent running paces for VDOT estimation.

    Two detection methods:
    1. Quality workouts: keyword + pace <6:00/km (existing)
    2. Easy runs: HR-based (65-78% max HR) + pace inference (NEW)

    Args:
        activities: Recent activities (pre-filtered to runs)
        lookback_days: Days to look back from today
        max_hr: Athlete's max HR (required for HR-based easy detection)

    Returns:
        PaceAnalysisResult with detected workouts and easy runs
    """
    from datetime import date as dt_date
    from resilio.schemas.activity import SportType, SurfaceType

    today = dt_date.today()
    cutoff_date = today - timedelta(days=lookback_days)

    # Filter: recent runs, valid distance/duration, exclude treadmill (no GPS pace)
    recent_runs = [
        a for a in activities
        if a.date >= cutoff_date
        and a.distance_km is not None
        and a.distance_km > 1.0  # Minimum 1km to avoid warmups/cooldowns
        and a.duration_seconds >= 300  # Minimum 5 minutes
        and a.sport_type != SportType.TREADMILL_RUN  # Exclude treadmill (pace unreliable)
        and a.surface_type != SurfaceType.TREADMILL  # Also check surface type
        and a.has_gps_data  # Require GPS data for pace reliability
    ]

    quality_workouts: List[WorkoutPaceData] = []
    easy_runs: List[EasyPaceData] = []

    # Detect quality workouts (existing logic)
    for activity in recent_runs:
        if is_quality_workout(activity):
            avg_pace_sec_per_km = int(activity.duration_seconds / activity.distance_km)

            # Only quality if pace <6:00/km (360 sec/km)
            if avg_pace_sec_per_km < 360:
                implied_vdot = find_vdot_from_pace(avg_pace_sec_per_km, "threshold")

                if implied_vdot:
                    workout_type = "tempo" if "tempo" in (activity.name or "").lower() else "interval"
                    quality_workouts.append(WorkoutPaceData(
                        date=activity.date.isoformat(),
                        workout_type=workout_type,
                        pace_sec_per_km=avg_pace_sec_per_km,
                        implied_vdot=implied_vdot
                    ))

    # Detect easy runs by HR (NEW)
    detection_method = "none"
    if max_hr:
        for activity in recent_runs:
            # Skip if already classified as quality workout
            if any(qw.date == activity.date.isoformat() for qw in quality_workouts):
                continue

            # Check if easy effort by HR
            if is_easy_effort_by_hr(activity, max_hr):
                avg_pace_sec_per_km = int(activity.duration_seconds / activity.distance_km)
                implied_vdot = find_vdot_from_easy_pace(avg_pace_sec_per_km)

                if implied_vdot:
                    easy_runs.append(EasyPaceData(
                        date=activity.date.isoformat(),
                        pace_sec_per_km=avg_pace_sec_per_km,
                        average_hr=activity.average_hr,
                        implied_vdot=implied_vdot,
                        detected_by="heart_rate"
                    ))

        detection_method = "heart_rate" if easy_runs else "none"

    # Calculate implied VDOT range from all data
    all_vdots = [qw.implied_vdot for qw in quality_workouts] + [er.implied_vdot for er in easy_runs]
    implied_vdot_range = (min(all_vdots), max(all_vdots)) if all_vdots else None

    # Calculate detected easy pace range
    easy_paces = [er.pace_sec_per_km for er in easy_runs]
    detected_easy_pace_range = (min(easy_paces), max(easy_paces)) if easy_paces else None

    return PaceAnalysisResult(
        quality_workouts=quality_workouts,
        easy_runs=easy_runs,
        implied_vdot_range=implied_vdot_range,
        detected_easy_pace_range=detected_easy_pace_range,
        detection_method=detection_method,
        no_hr_data=(max_hr is None)
    )
