"""
Profile API - Athlete profile management.

Provides functions for Claude Code to manage athlete profiles,
goals, and constraints.
"""

from datetime import date, datetime, timedelta
from typing import Optional, Union, Any, Dict, List
from dataclasses import dataclass
from collections import defaultdict, Counter

from sports_coach_engine.core.paths import athlete_profile_path, get_activities_dir
from sports_coach_engine.core.repository import RepositoryIO, ReadOptions
from sports_coach_engine.schemas.repository import RepoError, RepoErrorType
from sports_coach_engine.schemas.profile import (
    AthleteProfile,
    Goal,
    GoalType,
    TrainingConstraints,
    Weekday,
    RunningPriority,
    ConflictPolicy,
    TimePreference,
    VitalSigns,
    CommunicationPreferences,
    DetailLevel,
    CoachingStyle,
    IntensityMetric,
)
from sports_coach_engine.schemas.activity import NormalizedActivity


# ============================================================
# ERROR TYPES
# ============================================================


@dataclass
class ProfileError:
    """Error result from profile operations."""

    error_type: str  # "not_found", "validation", "unknown"
    message: str


# ============================================================
# PUBLIC API FUNCTIONS
# ============================================================


def create_profile(
    name: str,
    age: Optional[int] = None,
    email: Optional[str] = None,
    max_hr: Optional[int] = None,
    resting_hr: Optional[int] = None,
    lthr: Optional[int] = None,
    running_experience_years: Optional[int] = None,
    current_weekly_run_km: Optional[float] = None,
    current_run_days_per_week: Optional[int] = None,
    vdot: Optional[float] = None,
    running_priority: str = "equal",
    primary_sport: Optional[str] = None,
    conflict_policy: str = "ask_each_time",
    min_run_days: int = 2,
    max_run_days: int = 4,
    available_run_days: Optional[List[Weekday]] = None,
    preferred_run_days: Optional[List[Weekday]] = None,
    time_preference: Optional[TimePreference] = None,
    detail_level: Optional["DetailLevel"] = None,
    coaching_style: Optional["CoachingStyle"] = None,
    intensity_metric: Optional["IntensityMetric"] = None,
) -> Union[AthleteProfile, ProfileError]:
    """
    Create a new athlete profile with sensible defaults.

    This is the initial profile creation function. Use update_profile()
    to modify fields later.

    Workflow:
    1. Check if profile already exists
    2. Create AthleteProfile with provided fields and defaults
    3. Save profile to athlete_profile_path()
    4. Log operation via M14
    5. Return profile

    Args:
        name: Athlete name (required)
        age: Age in years (optional)
        email: Contact email (optional)
        max_hr: Maximum heart rate (optional)
        resting_hr: Resting heart rate (optional)
        lthr: Lactate threshold heart rate (optional)
        running_experience_years: Years of running experience (optional)
        current_weekly_run_km: Current weekly run volume baseline (optional)
        current_run_days_per_week: Current run frequency baseline (optional)
        vdot: Jack Daniels VDOT (optional, 30.0-85.0)
        running_priority: "primary", "secondary", or "equal" (default: "equal")
        primary_sport: Primary sport name for multi-sport athletes (optional)
        conflict_policy: "primary_sport_wins", "running_goal_wins", or "ask_each_time" (default: "ask_each_time")
        min_run_days: Minimum run days per week (default: 2)
        max_run_days: Maximum run days per week (default: 4)

    Returns:
        Created AthleteProfile

        ProfileError if profile already exists or validation fails

    Example:
        >>> profile = create_profile(
        ...     name="Alex",
        ...     age=32,
        ...     max_hr=190,
        ...     running_priority="equal"
        ... )
        >>> if isinstance(profile, ProfileError):
        ...     print(f"Error: {profile.message}")
        ... else:
        ...     print(f"Created profile for {profile.name}")
    """
    repo = RepositoryIO()
    # Check if profile already exists
    profile_path = athlete_profile_path()
    existing_result = repo.read_yaml(
        profile_path, AthleteProfile, ReadOptions(allow_missing=True)
    )

    # allow_missing=True returns None if file doesn't exist, RepoError on other errors
    # So we need to check if it's an AthleteProfile (not None, not RepoError)
    if existing_result is not None and not isinstance(existing_result, RepoError):
        return ProfileError(
            error_type="validation",
            message="Profile already exists. Use 'sce profile set' to update it or delete the existing profile first.",
        )

    # Parse enums
    try:
        priority_enum = RunningPriority(running_priority.lower())
    except ValueError:
        valid = ", ".join([p.value for p in RunningPriority])
        return ProfileError(
            error_type="validation",
            message=f"Invalid running_priority '{running_priority}'. Valid values: {valid}",
        )

    try:
        policy_enum = ConflictPolicy(conflict_policy.lower())
    except ValueError:
        valid = ", ".join([p.value for p in ConflictPolicy])
        return ProfileError(
            error_type="validation",
            message=f"Invalid conflict_policy '{conflict_policy}'. Valid values: {valid}",
        )

    # Create vital signs if any HR values provided
    vital_signs = None
    if max_hr is not None or resting_hr is not None or lthr is not None:
        vital_signs = VitalSigns(
            max_hr=max_hr,
            resting_hr=resting_hr,
            lthr=lthr,
        )

    # Create constraints
    # Use provided values, or defaults
    if available_run_days is None:
        # Default: all days available
        available_run_days = [day for day in Weekday]

    constraints = TrainingConstraints(
        available_run_days=available_run_days,
        preferred_run_days=preferred_run_days,
        min_run_days_per_week=min_run_days,
        max_run_days_per_week=max_run_days,
        time_preference=time_preference if time_preference is not None else TimePreference.FLEXIBLE,
    )

    # Create preferences with provided values or defaults
    preferences = CommunicationPreferences(
        detail_level=detail_level if detail_level is not None else DetailLevel.MODERATE,
        coaching_style=coaching_style if coaching_style is not None else CoachingStyle.SUPPORTIVE,
        intensity_metric=intensity_metric if intensity_metric is not None else IntensityMetric.PACE,
    )

    # Create default goal (general fitness)
    goal = Goal(type=GoalType.GENERAL_FITNESS)

    # Create profile
    try:
        profile = AthleteProfile(
            name=name,
            email=email,
            created_at=datetime.now().date().isoformat(),
            age=age,
            vital_signs=vital_signs,
            running_experience_years=running_experience_years,
            current_weekly_run_km=current_weekly_run_km,
            current_run_days_per_week=current_run_days_per_week,
            vdot=vdot,
            constraints=constraints,
            running_priority=priority_enum,
            primary_sport=primary_sport,
            conflict_policy=policy_enum,
            goal=goal,
            preferences=preferences,
        )
    except Exception as e:
        return ProfileError(
            error_type="validation",
            message=f"Invalid profile data: {str(e)}",
        )

    # Save profile
    write_result = repo.write_yaml(profile_path, profile)
    if isinstance(write_result, RepoError):
        return ProfileError(
            error_type="unknown",
            message=f"Failed to save profile: {str(write_result)}",
        )
    return profile


def get_profile() -> Union[AthleteProfile, ProfileError]:
    """
    Get current athlete profile.

    Workflow:
    1. Load profile from athlete_profile_path()
    2. Log operation via M14
    3. Return profile

    Returns:
        AthleteProfile containing:
        - name: Athlete name
        - goal: Current training goal
        - constraints: Training constraints (runs per week, preferred days, etc.)
        - conflict_policy: How to handle sport conflicts
        - strava_connection: Strava integration settings
        - recent_races: Recent race results
        - vital_signs: Resting HR, max HR, etc.

        ProfileError on failure containing error details

    Example:
        >>> profile = get_profile()
        >>> if isinstance(profile, ProfileError):
        ...     print(f"Error: {profile.message}")
        ... else:
        ...     print(f"Athlete: {profile.name}")
        ...     if profile.goal:
        ...         print(f"Goal: {profile.goal.type.value} on {profile.goal.target_date}")
        ...     print(f"Runs per week: {profile.constraints.runs_per_week}")
    """
    repo = RepositoryIO()
    # Load profile
    profile_path = athlete_profile_path()
    result = repo.read_yaml(profile_path, AthleteProfile, ReadOptions(should_validate=True))

    if isinstance(result, RepoError):
        error_type = "not_found" if result.error_type == RepoErrorType.FILE_NOT_FOUND else "validation"
        return ProfileError(
            error_type=error_type,
            message=f"Failed to load profile: {str(result)}",
        )

    profile = result
    goal_str = f", goal={profile.goal.type.value}" if profile.goal else ", no goal set"
    return profile


def update_profile(**fields: Any) -> Union[AthleteProfile, ProfileError]:
    """
    Update athlete profile fields.

    Workflow:
    1. Load current profile
    2. Update specified fields
    3. Validate updated profile
    4. Save updated profile
    5. Log operation via M14
    6. Return updated profile

    Args:
        **fields: Fields to update. Valid fields include:
            - name: str
            - constraints: TrainingConstraints dict or object
            - conflict_policy: ConflictPolicy enum value
            - vital_signs: VitalSigns dict or object
            - recent_races: list of RecentRace
            - strava_connection: StravaConnection dict or object

    Returns:
        Updated AthleteProfile

        ProfileError on failure containing error details

    Example:
        >>> # Update training constraints
        >>> profile = update_profile(
        ...     constraints={
        ...         "runs_per_week": 4,
        ...         "preferred_run_days": ["monday", "wednesday", "friday", "sunday"]
        ...     }
        ... )
        >>> if isinstance(profile, ProfileError):
        ...     print(f"Error: {profile.message}")
        ... else:
        ...     print(f"Updated: {profile.constraints.runs_per_week} runs/week")
    """
    repo = RepositoryIO()
    field_names = ", ".join(fields.keys())# Load current profile
    profile_path = athlete_profile_path()
    result = repo.read_yaml(profile_path, AthleteProfile, ReadOptions(should_validate=True))

    if isinstance(result, RepoError):
        return ProfileError(
            error_type="not_found",
            message=f"Failed to load profile: {str(result)}",
        )

    profile = result

    # Update fields using dict-merging (safer than setattr)
    # Convert profile to dict, merge updates, then validate
    profile_dict = profile.model_dump(mode='json')

    # Merge updates into profile dict
    profile_dict.update(fields)

    # Validate updated profile (Pydantic will catch invalid fields and validation errors)
    try:
        profile = AthleteProfile.model_validate(profile_dict)
    except Exception as e:
        return ProfileError(
            error_type="validation",
            message=f"Invalid profile data: {str(e)}",
        )

    # Save updated profile
    write_result = repo.write_yaml(profile_path, profile)
    if isinstance(write_result, RepoError):
        return ProfileError(
            error_type="unknown",
            message=f"Failed to save profile: {str(write_result)}",
        )
    return profile


def set_goal(
    race_type: str,
    target_date: date,
    target_time: Optional[str] = None,
) -> Union[Goal, ProfileError]:
    """
    Set a new race goal.

    This updates the athlete's goal in their profile. Plan generation happens
    separately when Claude Code is ready (after gathering constraints, schedule,
    preferences, etc.).

    Workflow:
    1. Create Goal object from inputs
    2. Update athlete profile with new goal
    3. Log operation via M14
    4. Return goal

    Args:
        race_type: Type of race. Valid values:
            - "5k", "10k", "half_marathon", "marathon"
        target_date: Race date
        target_time: Target finish time (optional, e.g., "1:45:00" for HH:MM:SS)

    Returns:
        New Goal object

        ProfileError on failure containing error details

    Example:
        >>> # Set half marathon goal
        >>> goal = set_goal(
        ...     race_type="half_marathon",
        ...     target_date=date(2024, 6, 15),
        ...     target_time="1:45:00"
        ... )
        >>> if isinstance(goal, ProfileError):
        ...     print(f"Error: {goal.message}")
        ... else:
        ...     print(f"Goal set: {goal.type.value} on {goal.target_date}")
        ...     # Plan generation happens later via Claude Code conversation
    """
    repo = RepositoryIO()
    # Parse race type
    try:
        goal_type = GoalType(race_type.lower())
    except ValueError:
        valid_types = ", ".join([t.value for t in GoalType])
        return ProfileError(
            error_type="validation",
            message=f"Invalid race type '{race_type}'. Valid types: {valid_types}",
        )

    # Create goal object
    # Convert date to ISO string if needed
    target_date_str = target_date.isoformat() if isinstance(target_date, date) else target_date

    goal = Goal(
        type=goal_type,
        target_date=target_date_str,
        target_time=target_time,
    )

    # Update profile with new goal
    profile_path = athlete_profile_path()
    profile_result = repo.read_yaml(profile_path, AthleteProfile, ReadOptions(should_validate=True))

    if isinstance(profile_result, RepoError):
        return ProfileError(
            error_type="not_found",
            message=f"Failed to load profile: {str(profile_result)}",
        )

    profile = profile_result
    profile.goal = goal

    # Save updated profile
    write_result = repo.write_yaml(profile_path, profile)
    if isinstance(write_result, RepoError):
        return ProfileError(
            error_type="unknown",
            message=f"Failed to save profile: {str(write_result)}",
        )
    return goal


# ============================================================
# PROFILE ANALYSIS (from synced activities)
# ============================================================


@dataclass
class ProfileAnalysis:
    """Analysis of synced activity data for profile setup insights.

    IMPORTANT: This analyzes only the activities synced from Strava,
    NOT the athlete's complete training history. The date range reflects
    the sync window, not how long they've been training.
    """

    # Synced data window (NOT athlete's full history)
    synced_data_start: Optional[date]  # First activity in sync
    synced_data_end: Optional[date]    # Last activity in sync
    data_window_days: int              # Days between first and last activity
    activities_synced: int             # Total activities in window
    activity_density: float            # activities_synced / data_window_days

    # Activity gaps (breaks > 7 days within synced window)
    activity_gaps: List[Dict[str, Any]]  # [{start_date, end_date, days}]

    # Heart rate insights
    max_hr_observed: Optional[int]  # Peak HR from all activities
    avg_hr_mean: Optional[int]      # Mean of all average HRs
    activities_with_hr: int

    # Volume analysis
    weekly_run_km_avg: Optional[float]
    weekly_run_km_recent_4wk: Optional[float]  # Last 4 weeks
    total_activities: int

    # Training patterns
    training_days_distribution: Dict[str, int]  # {"monday": 15, "tuesday": 12, ...}
    preferred_days: List[str]  # Top 3-4 days by frequency

    # Multi-sport analysis
    sport_distribution: Dict[str, int]  # {"run": 26, "climb": 39, ...}
    sport_percentages: Dict[str, float]
    run_to_other_ratio: Optional[float]  # Running % vs everything else

    # Recommendations
    suggested_max_hr: Optional[int]
    suggested_weekly_km: Optional[float]
    suggested_run_days: List[str]
    suggested_running_priority: str  # "primary" | "equal" | "secondary"


def analyze_profile_from_activities() -> Union[ProfileAnalysis, ProfileError]:
    """
    Analyze historical activity data to provide profile setup insights.

    Pure computation on local data - no API calls.

    Workflow:
    1. Load all activities from data/activities/**/*.yaml
    2. Compute date ranges, gaps, volume stats
    3. Analyze HR data from activities with HR
    4. Identify training day patterns
    5. Classify sport distribution and priorities
    6. Generate recommendations

    Returns:
        ProfileAnalysis with quantifiable insights
        ProfileError if no activities found or computation fails

    Example CLI usage:
        sce profile analyze

    Example output:
        {
          "synced_data_start": "2025-08-24",
          "synced_data_end": "2026-01-14",
          "data_window_days": 143,
          "activities_synced": 93,
          "activity_density": 0.65,
          "activity_gaps": [
            {"start_date": "2025-11-15", "end_date": "2025-11-29", "days": 14}
          ],
          "max_hr_observed": 199,
          "avg_hr_mean": 165,
          "weekly_run_km_avg": 22.5,
          "training_days_distribution": {
            "monday": 15, "tuesday": 18, "wednesday": 12, ...
          },
          "sport_distribution": {"run": 26, "climb": 39, "yoga": 13, ...},
          "suggested_max_hr": 199,
          "suggested_run_days": ["tuesday", "thursday", "saturday", "sunday"]
        }

    Note: Dates reflect synced data window, not athlete's full training history.
    """
    repo = RepositoryIO()
    # Load all activities
    try:
        activities = _load_all_activities(repo)
    except Exception as e:
        return ProfileError(
            error_type="unknown",
            message=f"Failed to load activities: {e}"
        )

    if not activities:
        return ProfileError(
            error_type="not_found",
            message="No activities found. Run 'sce sync' first to import activities."
        )

    # Sort by date
    activities.sort(key=lambda a: a.date)

    # 1. Synced data window analysis (NOT athlete's full history)
    synced_start = activities[0].date
    synced_end = activities[-1].date
    data_window_days = (synced_end - synced_start).days + 1
    activities_synced = len(activities)
    activity_density = activities_synced / data_window_days if data_window_days > 0 else 0

    # 2. Activity gaps (> 7 days)
    gaps = _find_activity_gaps(activities, min_gap_days=7)

    # 3. HR analysis
    hr_data = _analyze_heart_rate(activities)

    # 4. Volume analysis
    volume_data = _analyze_volume(activities)

    # 5. Training day patterns
    day_patterns = _analyze_training_days(activities)

    # 6. Sport distribution
    sport_data = _analyze_sport_distribution(activities)

    # 7. Generate recommendations
    recommendations = _generate_recommendations(
        hr_data, volume_data, day_patterns, sport_data
    )

    # Build result
    analysis = ProfileAnalysis(
        synced_data_start=synced_start,
        synced_data_end=synced_end,
        data_window_days=data_window_days,
        activities_synced=activities_synced,
        activity_density=round(activity_density, 2),
        activity_gaps=gaps,
        max_hr_observed=hr_data['max_hr'],
        avg_hr_mean=hr_data['avg_hr_mean'],
        activities_with_hr=hr_data['count_with_hr'],
        weekly_run_km_avg=volume_data['weekly_avg'],
        weekly_run_km_recent_4wk=volume_data['recent_4wk'],
        total_activities=len(activities),
        training_days_distribution=day_patterns['distribution'],
        preferred_days=day_patterns['preferred'],
        sport_distribution=sport_data['counts'],
        sport_percentages=sport_data['percentages'],
        run_to_other_ratio=sport_data['run_ratio'],
        suggested_max_hr=recommendations['max_hr'],
        suggested_weekly_km=recommendations['weekly_km'],
        suggested_run_days=recommendations['run_days'],
        suggested_running_priority=recommendations['running_priority'],
    )

    return analysis


def _load_all_activities(repo: RepositoryIO) -> List[NormalizedActivity]:
    """Load all activities from data/activities/**/*.yaml."""
    pattern = "data/activities/**/*.yaml"
    activity_files = repo.list_files(pattern)

    activities = []
    for file_path in activity_files:
        result = repo.read_yaml(file_path, NormalizedActivity, ReadOptions(should_validate=False))
        if not isinstance(result, RepoError):
            activities.append(result)

    return activities


def _find_activity_gaps(activities: List[NormalizedActivity], min_gap_days: int) -> List[Dict]:
    """Find gaps in training > min_gap_days."""
    gaps = []
    for i in range(1, len(activities)):
        prev_date = activities[i-1].date
        curr_date = activities[i].date
        gap_days = (curr_date - prev_date).days

        if gap_days > min_gap_days:
            gaps.append({
                "start_date": prev_date.isoformat(),
                "end_date": curr_date.isoformat(),
                "days": gap_days
            })

    return gaps


def _analyze_heart_rate(activities: List[NormalizedActivity]) -> Dict:
    """Extract HR insights."""
    hr_values = []
    avg_hr_values = []

    for a in activities:
        if a.max_hr:
            hr_values.append(int(a.max_hr))
        if a.average_hr:
            avg_hr_values.append(int(a.average_hr))

    return {
        'max_hr': max(hr_values) if hr_values else None,
        'avg_hr_mean': int(sum(avg_hr_values) / len(avg_hr_values)) if avg_hr_values else None,
        'count_with_hr': len(hr_values)
    }


def _analyze_volume(activities: List[NormalizedActivity]) -> Dict:
    """Analyze running volume patterns."""
    weekly_km = defaultdict(float)
    for a in activities:
        if a.sport_type in ["run", "trail_run", "treadmill_run"] and a.distance_km:
            week_key = a.date.isocalendar()[:2]  # (year, week)
            weekly_km[week_key] += a.distance_km

    if not weekly_km:
        return {'weekly_avg': None, 'recent_4wk': None}

    weeks = sorted(weekly_km.keys())
    volumes = [weekly_km[w] for w in weeks]

    return {
        'weekly_avg': sum(volumes) / len(volumes) if volumes else None,
        'recent_4wk': sum(volumes[-4:]) / min(4, len(volumes)) if volumes else None
    }


def _analyze_training_days(activities: List[NormalizedActivity]) -> Dict:
    """Find which days athlete typically trains."""
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_counts = Counter(a.date.weekday() for a in activities)

    distribution = {day_names[i]: day_counts.get(i, 0) for i in range(7)}

    # Top 3-4 days by frequency
    sorted_days = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
    preferred = [day for day, count in sorted_days[:4] if count >= 5]  # At least 5 activities

    return {
        'distribution': distribution,
        'preferred': preferred
    }


def _analyze_sport_distribution(activities: List[NormalizedActivity]) -> Dict:
    """Classify sport participation."""
    sport_counts = Counter(a.sport_type for a in activities)
    total = len(activities)

    run_types = ["run", "trail_run", "treadmill_run"]
    run_count = sum(sport_counts.get(s, 0) for s in run_types)

    percentages = {sport: (count / total) * 100 for sport, count in sport_counts.items()}
    run_pct = (run_count / total) * 100 if total > 0 else 0

    return {
        'counts': dict(sport_counts),
        'percentages': percentages,
        'run_ratio': run_pct
    }


def _generate_recommendations(hr_data, volume_data, day_patterns, sport_data) -> Dict:
    """Generate profile field suggestions."""
    # Max HR: Use observed max if available
    suggested_max_hr = hr_data['max_hr']

    # Weekly volume: Use recent 4-week average, or overall average
    suggested_km = volume_data['recent_4wk'] or volume_data['weekly_avg']

    # Run days: Use top 3-4 days
    suggested_run_days = day_patterns['preferred']

    # Running priority
    run_ratio = sport_data['run_ratio']
    if run_ratio >= 60:
        priority = "primary"
    elif run_ratio >= 30:
        priority = "equal"
    else:
        priority = "secondary"

    return {
        'max_hr': suggested_max_hr,
        'weekly_km': suggested_km,
        'run_days': suggested_run_days,
        'running_priority': priority
    }


# ============================================================
# MULTI-SPORT MANAGEMENT
# ============================================================


def add_sport_to_profile(
    sport: str,
    days: Optional[List[Weekday]] = None,
    duration: int = 60,
    intensity: str = "moderate",
    flexible: bool = False,
    notes: Optional[str] = None
) -> Union[AthleteProfile, ProfileError]:
    """
    Add a sport commitment to the athlete's profile.

    Args:
        sport: Name of the sport (e.g., "climbing", "yoga", "cycling")
        days: Days of the week for this sport (optional, None for flexible scheduling)
        duration: Typical session duration in minutes (default: 60)
        intensity: Intensity level (easy, moderate, hard, moderate_to_hard) (default: moderate)
        flexible: Whether this commitment is flexible (True) or fixed (False)
        notes: Optional notes about the commitment

    Returns:
        Updated AthleteProfile or ProfileError

    Examples:
        >>> add_sport_to_profile("climbing", [Weekday.TUESDAY, Weekday.THURSDAY], 120, "moderate_to_hard", notes="Gym 6-7pm")
        >>> add_sport_to_profile("yoga", intensity="easy")  # Flexible scheduling
    """
    from sports_coach_engine.schemas.profile import OtherSport

    repo = RepositoryIO()
    profile_path = athlete_profile_path()

    # Load current profile
    result = repo.read_yaml(
        profile_path, AthleteProfile, ReadOptions(should_validate=True)
    )

    if isinstance(result, RepoError):
        if result.error_type == RepoErrorType.NOT_FOUND:
            return ProfileError(
                error_type="not_found",
                message="Profile not found. Create a profile first using 'sce profile create'",
            )
        return ProfileError(
            error_type="unknown",
            message=f"Failed to load profile: {result.message}",
        )

    profile = result

    # Create new sport commitment
    new_sport = OtherSport(
        sport=sport,
        days=days,
        typical_duration_minutes=duration,
        typical_intensity=intensity,
        is_flexible=flexible,
        notes=notes
    )

    # Add to profile's other_sports list
    if profile.other_sports is None:
        profile.other_sports = []

    profile.other_sports.append(new_sport)

    # Save updated profile
    write_result = repo.write_yaml(profile_path, profile)
    if isinstance(write_result, RepoError):
        return ProfileError(
            error_type="unknown",
            message=f"Failed to save profile: {write_result.message}",
        )
        return profile


def remove_sport_from_profile(sport: str) -> Union[AthleteProfile, ProfileError]:
    """
    Remove a sport commitment from the athlete's profile.

    Args:
        sport: Name of the sport to remove (case-insensitive)

    Returns:
        Updated AthleteProfile or ProfileError

    Example:
        >>> remove_sport_from_profile("climbing")
    """
    repo = RepositoryIO()
    profile_path = athlete_profile_path()

    # Load current profile
    result = repo.read_yaml(
        profile_path, AthleteProfile, ReadOptions(should_validate=True)
    )

    if isinstance(result, RepoError):
        if result.error_type == RepoErrorType.NOT_FOUND:
            return ProfileError(
                error_type="not_found",
                message="Profile not found. Create a profile first using 'sce profile create'",
            )
        return ProfileError(
            error_type="unknown",
            message=f"Failed to load profile: {result.message}",
        )

    profile = result

    # Check if any sports configured
    if not profile.other_sports:
        return ProfileError(
            error_type="validation",
            message="No sports configured in profile"
        )

    # Remove sport (case-insensitive match)
    sport_lower = sport.lower()
    updated_sports = [s for s in profile.other_sports if s.sport.lower() != sport_lower]

    # Check if sport was found
    if len(updated_sports) == len(profile.other_sports):
        return ProfileError(
            error_type="validation",
            message=f"Sport '{sport}' not found in profile. Use 'sce profile list-sports' to see configured sports."
        )

    profile.other_sports = updated_sports

    # Save updated profile
    write_result = repo.write_yaml(profile_path, profile)
    if isinstance(write_result, RepoError):
        return ProfileError(
            error_type="unknown",
            message=f"Failed to save profile: {write_result.message}",
        )
        return profile
