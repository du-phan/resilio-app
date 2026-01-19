"""
Race API - Race performance tracking and PB management.

Provides functions for Claude Code to manage race history, track personal bests,
and analyze progression/regression over time.
"""

from datetime import date as dt_date, datetime
from typing import Optional, Union, List, Dict, Any
from dataclasses import dataclass

from sports_coach_engine.core.paths import athlete_profile_path, get_activities_dir
from sports_coach_engine.core.repository import RepositoryIO, ReadOptions
from sports_coach_engine.schemas.repository import RepoError
from sports_coach_engine.schemas.profile import AthleteProfile, RacePerformance
from sports_coach_engine.schemas.vdot import RaceSource, RaceDistance
from sports_coach_engine.schemas.activity import NormalizedActivity
from sports_coach_engine.api.vdot import calculate_vdot_from_race, VDOTError


# ============================================================
# ERROR TYPES
# ============================================================


@dataclass
class RaceError:
    """Error result from race operations."""

    error_type: str  # "not_found", "validation", "unknown", "profile_error"
    message: str


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _load_profile() -> Union[AthleteProfile, RaceError]:
    """Load athlete profile or return error."""
    repo = RepositoryIO()
    profile_path = athlete_profile_path()
    result = repo.read_yaml(profile_path, AthleteProfile, ReadOptions(allow_missing=True))

    if result is None:
        return RaceError(
            error_type="not_found",
            message="No athlete profile found. Create one with 'sce profile create'",
        )

    if isinstance(result, RepoError):
        return RaceError(error_type="profile_error", message=f"Failed to load profile: {result.message}")

    return result


def _save_profile(profile: AthleteProfile) -> Optional[RaceError]:
    """Save athlete profile or return error."""
    repo = RepositoryIO()
    profile_path = athlete_profile_path()
    result = repo.write_yaml(profile_path, profile)

    if isinstance(result, RepoError):
        return RaceError(error_type="profile_error", message=f"Failed to save profile: {result.message}")

    return None


def _recalculate_peak_vdot(profile: AthleteProfile) -> None:
    """Recalculate peak VDOT from race history.

    Modifies profile in place by updating peak_vdot and peak_vdot_date.
    """
    if not profile.race_history:
        profile.peak_vdot = None
        profile.peak_vdot_date = None
        return

    # Find race with highest VDOT
    best_race = max(profile.race_history, key=lambda r: r.vdot)
    profile.peak_vdot = best_race.vdot
    profile.peak_vdot_date = best_race.date


def _update_pb_flags(profile: AthleteProfile) -> None:
    """Update is_pb flags for races in profile.

    For each distance, marks the race with the fastest time as PB.
    Modifies profile.race_history in place.
    """
    # Group races by distance
    races_by_distance: Dict[str, List[RacePerformance]] = {}
    for race in profile.race_history:
        if race.distance not in races_by_distance:
            races_by_distance[race.distance] = []
        races_by_distance[race.distance].append(race)

    # For each distance, find the race with highest VDOT (fastest time)
    for distance, races in races_by_distance.items():
        if not races:
            continue

        # Find best race (highest VDOT)
        best_race = max(races, key=lambda r: r.vdot)

        # Update flags
        for race in races:
            race.is_pb = race == best_race


# ============================================================
# PUBLIC API FUNCTIONS
# ============================================================


def add_race_performance(
    distance: str,
    time: str,
    date: str,
    location: Optional[str] = None,
    source: str = "gps_watch",
    notes: Optional[str] = None,
) -> Union[RacePerformance, RaceError]:
    """
    Add a race performance to athlete's race history.

    Automatically:
    - Calculates VDOT for the race
    - Updates PB flags if this is a new PB
    - Recalculates peak_vdot if this is the best performance
    - Migrates recent_race to race_history if needed

    Args:
        distance: Race distance ("5k", "10k", "half_marathon", "marathon")
        time: Race time ("MM:SS" or "HH:MM:SS")
        date: Race date (ISO format "YYYY-MM-DD")
        location: Race name or location (optional)
        source: Race source ("official_race", "gps_watch", "estimated")
        notes: Additional notes about the race (optional)

    Returns:
        RacePerformance on success, RaceError on failure

    Example:
        >>> result = add_race_performance(
        ...     distance="10k",
        ...     time="42:30",
        ...     date="2025-06-15",
        ...     location="City 10K Championship",
        ...     source="official_race",
        ...     notes="Perfect conditions"
        ... )
        >>> if isinstance(result, RaceError):
        ...     print(f"Error: {result.message}")
        ... else:
        ...     print(f"Added race: {result.distance} in {result.time} (VDOT {result.vdot})")
    """
    # Load profile
    profile = _load_profile()
    if isinstance(profile, RaceError):
        return profile

    # Validate distance
    valid_distances = ["5k", "10k", "half_marathon", "marathon", "mile", "15k"]
    if distance.lower() not in valid_distances:
        return RaceError(
            error_type="validation",
            message=f"Invalid distance '{distance}'. Valid: {', '.join(valid_distances)}",
        )

    # Validate source
    try:
        race_source = RaceSource(source.lower())
    except ValueError:
        valid_sources = [s.value for s in RaceSource]
        return RaceError(
            error_type="validation",
            message=f"Invalid source '{source}'. Valid: {', '.join(valid_sources)}",
        )

    # Validate date format
    try:
        dt_date.fromisoformat(date)
    except ValueError:
        return RaceError(
            error_type="validation",
            message=f"Invalid date format '{date}'. Use ISO format YYYY-MM-DD",
        )

    # Calculate VDOT for this race
    vdot_result = calculate_vdot_from_race(distance, time)
    if isinstance(vdot_result, VDOTError):
        return RaceError(
            error_type="validation",
            message=f"Failed to calculate VDOT: {vdot_result.message}",
        )

    # Create new race performance
    new_race = RacePerformance(
        distance=distance.lower(),
        time=time,
        date=date,
        location=location,
        source=race_source,
        vdot=float(vdot_result.vdot),
        notes=notes,
        is_pb=False,  # Will be set by _update_pb_flags
    )

    # Add to race history
    profile.race_history.append(new_race)

    # Update PB flags
    _update_pb_flags(profile)

    # Recalculate peak VDOT
    _recalculate_peak_vdot(profile)

    # Save profile
    save_error = _save_profile(profile)
    if save_error:
        return save_error

    return new_race


def list_race_history(
    distance_filter: Optional[str] = None,
    since_date: Optional[str] = None,
) -> Union[Dict[str, List[RacePerformance]], RaceError]:
    """
    List race history grouped by distance.

    Args:
        distance_filter: Optional distance filter ("5k", "10k", "half_marathon", "marathon")
        since_date: Optional date filter (ISO format "YYYY-MM-DD") - only show races after this date

    Returns:
        Dictionary mapping distance to list of races (sorted by date, newest first)

        RaceError on failure

    Example:
        >>> races = list_race_history()
        >>> if isinstance(races, RaceError):
        ...     print(f"Error: {races.message}")
        ... else:
        ...     for distance, race_list in races.items():
        ...         print(f"{distance}: {len(race_list)} races")
    """
    # Load profile
    profile = _load_profile()
    if isinstance(profile, RaceError):
        return profile

    # Filter races
    races = profile.race_history

    if distance_filter:
        races = [r for r in races if r.distance == distance_filter.lower()]

    if since_date:
        try:
            cutoff_date = dt_date.fromisoformat(since_date)
            races = [r for r in races if dt_date.fromisoformat(r.date) >= cutoff_date]
        except ValueError:
            return RaceError(
                error_type="validation",
                message=f"Invalid since_date format '{since_date}'. Use ISO format YYYY-MM-DD",
            )

    # Group by distance
    grouped: Dict[str, List[RacePerformance]] = {}
    for race in races:
        if race.distance not in grouped:
            grouped[race.distance] = []
        grouped[race.distance].append(race)

    # Sort each group by date (newest first)
    for distance in grouped:
        grouped[distance] = sorted(grouped[distance], key=lambda r: r.date, reverse=True)

    return grouped


def import_races_from_strava(
    since_date: Optional[str] = None,
) -> Union[List[RacePerformance], RaceError]:
    """
    Auto-detect potential race activities from synced Strava activities.

    Detection criteria:
    - workout_type == 1 (Strava race flag)
    - Keywords in title/description: "race", "5K", "10K", "HM", "PB", "PR"
    - Distance matches standard race distances (±5%)

    Returns list of detected races for user confirmation (not automatically added to profile).

    Args:
        since_date: Optional date filter (ISO format "YYYY-MM-DD") - only detect races after this date

    Returns:
        List of detected RacePerformance objects (not yet saved to profile)

        RaceError on failure

    Example:
        >>> detected = import_races_from_strava(since_date="2025-01-01")
        >>> if isinstance(detected, RaceError):
        ...     print(f"Error: {detected.message}")
        ... else:
        ...     print(f"Found {len(detected)} potential races")
        ...     # User confirms, then calls add_race_performance for each
    """
    # Load profile
    profile = _load_profile()
    if isinstance(profile, RaceError):
        return profile

    # Load activities
    repo = RepositoryIO()
    activities_dir = get_activities_dir()

    # Get all activity files
    from pathlib import Path

    activity_files = list(Path(activities_dir).glob("*.json"))
    if not activity_files:
        return []  # No activities synced

    # Load all activities
    activities: List[NormalizedActivity] = []
    for activity_file in activity_files:
        result = repo.read_json(str(activity_file), NormalizedActivity, ReadOptions())
        if isinstance(result, NormalizedActivity):
            activities.append(result)

    # Filter by sport type (running only)
    activities = [a for a in activities if a.sport_type.lower() == "run"]

    # Filter by date if provided
    if since_date:
        try:
            cutoff_date = dt_date.fromisoformat(since_date)
            activities = [
                a
                for a in activities
                if dt_date.fromisoformat(a.start_date.split("T")[0]) >= cutoff_date
            ]
        except ValueError:
            return RaceError(
                error_type="validation",
                message=f"Invalid since_date format '{since_date}'. Use ISO format YYYY-MM-DD",
            )

    # Detect potential races
    detected_races: List[RacePerformance] = []
    race_keywords = ["race", "5k", "10k", "half", "marathon", "pb", "pr", "hm"]

    # Standard race distances in meters (with 5% tolerance)
    standard_distances = {
        "5k": (5000, 4750, 5250),  # (target, min, max)
        "10k": (10000, 9500, 10500),
        "half_marathon": (21097, 20042, 22152),
        "marathon": (42195, 40085, 44305),
    }

    for activity in activities:
        # Check workout_type (1 = race in Strava)
        is_race_type = activity.workout_type == 1

        # Check for race keywords in title or description
        title = (activity.title or "").lower()
        description = (activity.description or "").lower()
        has_keyword = any(keyword in title or keyword in description for keyword in race_keywords)

        # Check if distance matches standard race distance
        distance_km = activity.distance_km
        matched_distance = None
        for race_dist, (target_m, min_m, max_m) in standard_distances.items():
            target_km = target_m / 1000
            min_km = min_m / 1000
            max_km = max_m / 1000
            if min_km <= distance_km <= max_km:
                matched_distance = race_dist
                break

        # Detect if this is likely a race
        if (is_race_type or has_keyword) and matched_distance:
            # Calculate VDOT
            time_str = f"{activity.moving_time_seconds // 3600:02d}:{(activity.moving_time_seconds % 3600) // 60:02d}:{activity.moving_time_seconds % 60:02d}"
            vdot_result = calculate_vdot_from_race(matched_distance, time_str)

            if not isinstance(vdot_result, VDOTError):
                # Check if this race already exists in profile
                race_date = activity.start_date.split("T")[0]
                already_exists = any(
                    r.distance == matched_distance and r.date == race_date for r in profile.race_history
                )

                if not already_exists:
                    detected_race = RacePerformance(
                        distance=matched_distance,
                        time=time_str,
                        date=race_date,
                        location=activity.title,
                        source=RaceSource.GPS_WATCH,
                        vdot=float(vdot_result.vdot),
                        notes=f"Auto-detected from Strava (activity_id: {activity.activity_id})",
                        is_pb=False,
                    )
                    detected_races.append(detected_race)

    return detected_races


def get_peak_vdot_info(profile: AthleteProfile) -> Optional[Dict[str, Any]]:
    """
    Get peak VDOT information from profile.

    Returns:
        Dictionary with peak_vdot, peak_vdot_date, and corresponding race info
        None if no race history

    Example:
        >>> info = get_peak_vdot_info(profile)
        >>> if info:
        ...     print(f"Peak VDOT: {info['peak_vdot']} on {info['date']}")
    """
    if not profile.race_history or not profile.peak_vdot:
        return None

    # Find race with peak VDOT
    peak_race = next(
        (r for r in profile.race_history if r.vdot == profile.peak_vdot and r.date == profile.peak_vdot_date),
        None,
    )

    if not peak_race:
        return None

    return {
        "peak_vdot": profile.peak_vdot,
        "date": profile.peak_vdot_date,
        "distance": peak_race.distance,
        "time": peak_race.time,
        "location": peak_race.location,
        "source": peak_race.source,
    }
