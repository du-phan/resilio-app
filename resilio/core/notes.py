"""
M7 - Notes & RPE Analyzer (Toolkit Paradigm)

Provides quantitative toolkit functions for activity analysis.

Toolkit Functions (Return Data, Not Decisions):
- RPE estimation from multiple quantitative sources (HR, pace, Strava, duration)
- Treadmill/indoor activity detection using multi-signal scoring

Claude Code Responsibilities (Uses Context to Decide):
- RPE conflict resolution: "HR says 7, pace says 5 → which to trust?"
- Wellness extraction: Parse injury/illness naturally during conversation
- Final RPE selection: Choose estimate based on athlete context

The toolkit paradigm separates quantitative computation (this module)
from qualitative reasoning (Claude Code with athlete context).
"""

from datetime import datetime, timezone
from typing import Optional

from sports_coach_engine.schemas.activity import (
    AnalysisResult,
    NormalizedActivity,
    RPEEstimate,
    RPESource,
    TreadmillDetection,
)
from sports_coach_engine.schemas.profile import AthleteProfile


# ============================================================
# TREADMILL DETECTION KEYWORDS
# ============================================================

TREADMILL_TITLE_KEYWORDS = [
    "treadmill",
    "indoor",
    "zwift",
    "peloton",
    "tm run",
    "dreadmill",
    "inside",
    "gym run",
]

INDOOR_DEVICE_NAMES = [
    "zwift",
    "peloton",
    "tacx",
    "wahoo kickr",
    "nordictrack",
    "proform",
    "sole",
]


# ============================================================
# ERROR TYPES
# ============================================================


class AnalysisError(Exception):
    """Base error for analysis failures."""

    pass


class InsufficientDataError(AnalysisError):
    """Not enough data to make a reliable estimate."""

    def __init__(self, activity_id: str, missing: list[str]):
        super().__init__(f"Insufficient data for {activity_id}: missing {missing}")
        self.activity_id = activity_id
        self.missing = missing


# ============================================================
# MAIN ANALYSIS FUNCTION
# ============================================================


def analyze_activity(
    activity: NormalizedActivity,
    athlete_profile: AthleteProfile,
) -> AnalysisResult:
    """
    Analyze activity using quantitative toolkit functions (Toolkit Paradigm).

    Returns multiple RPE estimates from quantitative sources and treadmill
    detection. Claude Code handles qualitative extraction (injury,
    illness) naturally through conversation.

    Args:
        activity: Normalized activity with notes
        athlete_profile: Profile with vital signs for HR-based RPE

    Returns:
        AnalysisResult with multiple RPE estimates and treadmill detection
    """
    # Detect treadmill using multi-signal scoring
    treadmill = detect_treadmill(
        activity_name=activity.name,
        description=activity.description,
        has_gps=activity.has_gps_data,
        sport_type=activity.sport_type,
        sub_type=activity.sub_type,
        device_name=activity.gear_id,  # Using gear_id as proxy for device
    )

    # Get all available RPE estimates (no resolution)
    rpe_estimates = estimate_rpe(activity, athlete_profile)

    # Check if any notes are present (Claude Code can parse if needed)
    notes_present = bool(activity.description or activity.private_note)

    return AnalysisResult(
        activity_id=activity.id,
        rpe_estimates=rpe_estimates,
        treadmill_detection=treadmill,
        analyzed_at=datetime.now(timezone.utc),
        notes_present=notes_present,
    )


# ============================================================
# RPE ESTIMATION
# ============================================================


def estimate_rpe(
    activity: NormalizedActivity,
    athlete_profile: AthleteProfile,
) -> list[RPEEstimate]:
    """
    Estimate RPE from all available quantitative sources (Toolkit Paradigm).

    Returns ALL available RPE estimates without resolution. Claude Code
    uses these estimates with conversation context to determine final RPE.

    Sources checked:
    1. Explicit user input (Strava perceived_exertion)
    2. HR-based estimate (when reliable HR present)
    3. Strava relative effort normalization
    4. Duration + sport heuristic (always available)

    Note: Text-based extraction removed - Claude Code extracts RPE from
    notes naturally during conversation.

    Args:
        activity: Activity with HR, notes, suffer_score
        athlete_profile: Profile with max_hr for HR-based estimates

    Returns:
        List of all available RPE estimates (Claude Code decides which to use)
    """
    estimates: list[RPEEstimate] = []

    # 1. User input (if explicitly entered)
    if activity.perceived_exertion:
        user_estimate = RPEEstimate(
            value=activity.perceived_exertion,
            source=RPESource.USER_INPUT,
            confidence="high",
            reasoning="User explicitly entered RPE in Strava",
        )
        estimates.append(user_estimate)

    # 2. HR-based estimate
    if activity.has_hr_data and activity.average_hr:
        hr_estimate = estimate_rpe_from_hr(
            average_hr=activity.average_hr,
            max_hr_activity=activity.max_hr,
            athlete_max_hr=athlete_profile.vital_signs.max_hr
            if athlete_profile and athlete_profile.vital_signs
            else None,
            duration_minutes=activity.duration_seconds // 60,
        )
        if hr_estimate:
            estimates.append(hr_estimate)

    # 3. Strava relative effort
    if activity.suffer_score:
        rel_estimate = estimate_rpe_from_strava_relative(
            suffer_score=activity.suffer_score,
            duration_minutes=activity.duration_seconds // 60,
        )
        if rel_estimate:
            estimates.append(rel_estimate)

    # 4. Pace-based estimate (for running activities with pace data)
    if activity.sport_type in ["run", "trail_run", "treadmill_run", "track_run"]:
        # Calculate average pace if distance and duration available
        if activity.distance_km and activity.distance_km > 0:
            avg_pace_seconds = (activity.duration_seconds / activity.distance_km)

            # Get VDOT from athlete profile
            athlete_vdot = None
            if athlete_profile and hasattr(athlete_profile, 'vdot'):
                athlete_vdot = athlete_profile.vdot

            # Estimate RPE from pace if VDOT available
            if athlete_vdot:
                pace_estimate = estimate_rpe_from_pace(
                    avg_pace_per_km=avg_pace_seconds,
                    athlete_vdot=athlete_vdot,
                    sport_type=activity.sport_type,
                )
                if pace_estimate:
                    estimates.append(pace_estimate)

    # 5. Duration heuristic (always available as fallback)
    duration_estimate = estimate_rpe_from_duration(
        sport_type=activity.sport_type,
        duration_minutes=activity.duration_seconds // 60,
    )
    estimates.append(duration_estimate)

    return estimates


def estimate_rpe_from_hr(
    average_hr: int,
    max_hr_activity: Optional[int],
    athlete_max_hr: Optional[int],
    duration_minutes: int,
) -> Optional[RPEEstimate]:
    """
    Derive RPE from heart rate data using max HR zones.

    Max HR % zones:
       - < 60% max HR: RPE 2 (very easy)
       - 60-68% max HR: RPE 3 (easy recovery)
       - 68-78% max HR: RPE 4 (easy/aerobic, Zone 2)
       - 78-85% max HR: RPE 5 (moderate/tempo)
       - 85-90% max HR: RPE 6 (lactate threshold)
       - 90-94% max HR: RPE 7 (VO2max lower)
       - 94-97% max HR: RPE 8 (VO2max upper)
       - > 97% max HR: RPE 9 (anaerobic/maximal)

    Duration adjustment: Cumulative fatigue for long steady efforts (sport science):
       - >90 min at RPE ≥4: +1 RPE (long session; glycogen/fatigue start to matter)
       - >150 min (2.5h) at RPE ≥4: +2 RPE (very long; e.g. long marathon run, half-Iron bike)
       - >240 min (4h) at RPE ≥4: +3 RPE (ultra-long; fondo, Iron bike, marathon+; recovery scales supra-linearly)

    Key fix: Zone 2 boundary moved from 70% to 78% max HR to match sport
    science literature (80/20, Pfitzinger). This prevents easy runs from
    being miscoded as moderate intensity.

    Args:
        average_hr: Average heart rate during activity
        max_hr_activity: Max HR reached during activity
        athlete_max_hr: Athlete's known max HR
        duration_minutes: Activity duration

    Returns:
        RPE estimate or None if insufficient data
    """
    # Determine max HR to use
    max_hr = athlete_max_hr or max_hr_activity
    if not max_hr:
        return None

    hr_percent_max = (average_hr / max_hr) * 100

    # Improved thresholds (less aggressive than original)
    # Based on typical LTHR ~88-92% of max HR for trained athletes
    # Zone 2 boundary moved from 70% to 78% (key fix for 80/20 distribution)
    if hr_percent_max < 60:
        base_rpe = 2  # Very easy
    elif hr_percent_max < 68:
        base_rpe = 3  # Easy recovery
    elif hr_percent_max < 78:  # FIX: Was 70% (caused easy runs → moderate)
        base_rpe = 4  # Easy/aerobic (Zone 2)
    elif hr_percent_max < 85:  # FIX: Was 80%
        base_rpe = 5  # Moderate/tempo (Zone 3)
    elif hr_percent_max < 90:  # FIX: Was 85% (LT proxy)
        base_rpe = 6  # Lactate threshold
    elif hr_percent_max < 94:  # FIX: Was 90%
        base_rpe = 7  # VO2max (lower)
    elif hr_percent_max < 97:  # FIX: Was 95%
        base_rpe = 8  # VO2max (upper)
    else:
        base_rpe = 9  # Anaerobic/maximal

    confidence = "medium"  # Max HR% is proxy, higher variability
    reasoning = f"HR {average_hr} = {hr_percent_max:.0f}% of max ({max_hr})"

    # Duration adjustment: cumulative fatigue for long steady efforts (Foster-style session RPE,
    # Banister load: recovery demand scales supra-linearly with duration for endurance events).
    duration_adjustment = 0
    if duration_minutes > 90 and base_rpe >= 4:
        duration_adjustment = 1
    elif duration_minutes > 150 and base_rpe >= 4:
        duration_adjustment = 2
    elif duration_minutes > 240 and base_rpe >= 4:  # 4h+ (ultra-long, fondo, Iron bike)
        duration_adjustment = 3

    final_rpe = min(10, base_rpe + duration_adjustment)

    if duration_adjustment > 0:
        reasoning += f"; duration {duration_minutes}min → +{duration_adjustment} RPE (cumulative fatigue)"

    return RPEEstimate(
        value=final_rpe,
        source=RPESource.HR_BASED,
        confidence=confidence,
        reasoning=reasoning,
    )


def estimate_rpe_from_strava_relative(
    suffer_score: int,
    duration_minutes: int,
) -> Optional[RPEEstimate]:
    """
    Normalize Strava's relative effort (suffer_score) to 1-10 RPE.

    Strava suffer_score is roughly: RPE equivalent per minute.
    We normalize it based on typical ranges.

    Args:
        suffer_score: Strava's relative effort score
        duration_minutes: Activity duration

    Returns:
        RPE estimate or None if data insufficient
    """
    if suffer_score <= 0 or duration_minutes <= 0:
        return None

    # Calculate effort per minute
    effort_per_min = suffer_score / duration_minutes

    # Map effort per minute to RPE (rough calibration)
    if effort_per_min < 0.5:
        rpe = 2
    elif effort_per_min < 1.0:
        rpe = 4
    elif effort_per_min < 1.5:
        rpe = 5
    elif effort_per_min < 2.0:
        rpe = 6
    elif effort_per_min < 2.5:
        rpe = 7
    elif effort_per_min < 3.0:
        rpe = 8
    else:
        rpe = 9

    return RPEEstimate(
        value=rpe,
        source=RPESource.STRAVA_RELATIVE,
        confidence="medium",
        reasoning=f"Suffer score {suffer_score} / {duration_minutes}min = {effort_per_min:.1f} per min",
    )


def estimate_rpe_from_duration(
    sport_type: str,
    duration_minutes: int,
) -> RPEEstimate:
    """
    Fallback RPE based on sport and duration.

    Conservative default when no other data available.

    Args:
        sport_type: Activity sport type
        duration_minutes: Activity duration

    Returns:
        RPE estimate (always returns a value)
    """
    # Default RPE by sport type
    sport_defaults = {
        "run": 5,
        "trail_run": 6,
        "treadmill_run": 5,
        "track_run": 6,
        "cycle": 4,
        "swim": 5,
        "climb": 6,
        "strength": 6,
        "crossfit": 7,
        "hike": 4,
        "walk": 2,
        "yoga": 2,
    }

    base_rpe = sport_defaults.get(sport_type.lower(), 5)

    # Adjust for very long sessions
    if duration_minutes > 120:
        base_rpe = min(10, base_rpe + 1)

    return RPEEstimate(
        value=base_rpe,
        source=RPESource.DURATION_HEURISTIC,
        confidence="low",
        reasoning=f"Default for {sport_type} ({duration_minutes}min)",
    )


def estimate_rpe_from_pace(
    avg_pace_per_km: float,
    athlete_vdot: float,
    sport_type: str = "run",
) -> Optional[RPEEstimate]:
    """
    Estimate RPE from running pace using VDOT training zones (Toolkit Paradigm).

    Maps actual pace to VDOT-based training zones:
    - Easy pace (Zone 2): RPE 4
    - Marathon pace (Zone 3): RPE 6
    - Threshold/Tempo pace (Zone 4): RPE 7
    - Interval pace (Zone 5): RPE 8
    - Repetition pace (faster): RPE 9

    Args:
        avg_pace_per_km: Average pace in seconds per km
        athlete_vdot: Athlete's VDOT from profile
        sport_type: "run" or "trail_run" (adds +1 RPE for trails)

    Returns:
        RPEEstimate with pace-based RPE, or None if pace unavailable
    """
    if not avg_pace_per_km or not athlete_vdot:
        return None

    # Calculate VDOT zone paces using corrected formulas
    # Zone 2 (Easy): VDOT 40→6:00/km (360s), 45→5:30 (330s), 50→5:00 (300s)
    easy_pace = int(360 - (athlete_vdot - 40) * 6)

    # Zone 4 (Tempo): VDOT 40→5:30/km (330s), 45→5:00 (300s), 50→4:40 (280s)
    tempo_pace = int(330 - (athlete_vdot - 40) * 5)

    # Zone 5 (Intervals): VDOT 40→5:00/km (300s), 45→4:30 (270s), 50→4:05 (245s)
    interval_pace = int(300 - (athlete_vdot - 40) * 5.5)

    # Zone 3 (Marathon): Roughly between easy and tempo
    marathon_pace = (easy_pace + tempo_pace) // 2

    # Repetition pace: Faster than intervals
    repetition_pace = interval_pace - 30  # ~30s/km faster

    # Determine RPE based on pace (faster = higher RPE)
    if avg_pace_per_km <= repetition_pace:
        rpe = 9
        zone_name = "repetition"
    elif avg_pace_per_km <= interval_pace:
        rpe = 8
        zone_name = "interval"
    elif avg_pace_per_km <= tempo_pace:
        rpe = 7
        zone_name = "tempo/threshold"
    elif avg_pace_per_km <= marathon_pace:
        rpe = 6
        zone_name = "marathon"
    else:  # Slower than marathon pace
        rpe = 4
        zone_name = "easy"

    # Adjust for trail running (+1 RPE)
    if "trail" in sport_type.lower():
        rpe = min(10, rpe + 1)
        zone_name += " (trail)"

    pace_str = f"{int(avg_pace_per_km // 60)}:{int(avg_pace_per_km % 60):02d}"

    return RPEEstimate(
        value=rpe,
        source=RPESource.PACE_BASED,
        confidence="high",
        reasoning=f"Pace {pace_str}/km maps to {zone_name} pace for VDOT {athlete_vdot}",
    )


# ============================================================
# TREADMILL DETECTION
# ============================================================


def detect_treadmill(
    activity_name: str,
    description: Optional[str],
    has_gps: bool,
    sport_type: str,
    sub_type: Optional[str],
    device_name: Optional[str],
) -> TreadmillDetection:
    """
    Multi-signal treadmill detection.

    Signals (in priority order):
    1. Sub-type explicitly indicates indoor (e.g., "VirtualRun")
    2. Title contains treadmill keywords
    3. No GPS data for a running activity
    4. Device is known indoor equipment

    Args:
        activity_name: Activity title
        description: Activity description
        has_gps: Whether GPS data is present
        sport_type: Sport type
        sub_type: Sport sub-type
        device_name: Recording device name

    Returns:
        TreadmillDetection with confidence and signals
    """
    signals = []
    confidence_score = 0

    # Check if it's a running activity
    running_sports = {"run", "running", "treadmill_run", "virtual_run"}
    is_running = sport_type.lower() in running_sports

    if not is_running:
        return TreadmillDetection(
            is_treadmill=False,
            confidence="high",
            signals=["Not a running activity"],
        )

    # Signal 1: Sub-type indicates indoor
    if sub_type and sub_type.lower() in {"virtualrun", "treadmill", "indoor_run"}:
        signals.append(f"sub_type={sub_type}")
        confidence_score += 3

    # Signal 2: Title keywords
    name_lower = activity_name.lower() if activity_name else ""
    for keyword in TREADMILL_TITLE_KEYWORDS:
        if keyword in name_lower:
            signals.append(f"title contains '{keyword}'")
            confidence_score += 2
            break

    # Signal 3: No GPS
    if not has_gps:
        signals.append("no GPS data")
        confidence_score += 2

    # Signal 4: Description keywords
    if description:
        desc_lower = description.lower()
        for keyword in TREADMILL_TITLE_KEYWORDS:
            if keyword in desc_lower:
                signals.append(f"description contains '{keyword}'")
                confidence_score += 1
                break

    # Signal 5: Indoor device
    if device_name:
        device_lower = device_name.lower()
        for device in INDOOR_DEVICE_NAMES:
            if device in device_lower:
                signals.append(f"indoor device: {device_name}")
                confidence_score += 2
                break

    # Determine result
    is_treadmill = confidence_score >= 2
    confidence = "high" if confidence_score >= 2 else "low"

    return TreadmillDetection(
        is_treadmill=is_treadmill,
        confidence=confidence,
        signals=signals if signals else ["No treadmill signals detected"],
    )

