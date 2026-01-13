"""
M7 - Notes & RPE Analyzer

Extract structured data from unstructured activity notes and metadata.
Provides RPE estimates when direct input is unavailable, detects treadmill/indoor
activities, and identifies wellness flags (injury, illness, fatigue) for
downstream processing.

This module handles:
- RPE estimation from multiple sources (HR, text, Strava relative effort)
- RPE conflict resolution when sources disagree
- Treadmill/indoor activity detection
- Injury and illness flag extraction
- Wellness indicator parsing (sleep, soreness, stress)
- Contextual factor extraction (heat, altitude, fasted)
"""

import re
from datetime import datetime, timezone
from typing import Optional

from sports_coach_engine.schemas.activity import (
    AnalysisResult,
    BodyPart,
    ContextualFactors,
    FlagSeverity,
    IllnessFlag,
    InjuryFlag,
    NormalizedActivity,
    RPEConflict,
    RPEEstimate,
    RPESource,
    TreadmillDetection,
    WellnessIndicators,
)
from sports_coach_engine.schemas.profile import AthleteProfile


# ============================================================
# RPE KEYWORD MAPPING
# ============================================================

# Keywords mapped to RPE values (1-10 scale)
RPE_KEYWORDS = {
    # Very easy (1-3)
    "recovery": 2,
    "very easy": 2,
    "super easy": 2,
    "shake out": 2,
    "shakeout": 2,
    "walk": 2,
    "stroll": 2,
    # Easy (4)
    "easy": 4,
    "comfortable": 4,
    "relaxed": 4,
    "light": 4,
    "conversational": 4,
    "zone 2": 4,
    "z2": 4,
    # Moderate (5-6)
    "moderate": 5,
    "steady": 5,
    "tempo": 6,
    "threshold": 6,
    "comfortably hard": 6,
    "zone 3": 5,
    "z3": 5,
    "zone 4": 6,
    "z4": 6,
    # Hard (7-8)
    "hard": 7,
    "tough": 7,
    "challenging": 7,
    "intervals": 7,
    "vo2max": 8,
    "vo2": 8,
    "race pace": 8,
    "fast": 7,
    "struggled": 7,
    "suffered": 8,
    # Very hard (9-10)
    "all out": 9,
    "max effort": 10,
    "sprint": 9,
    "race": 8,
    "pr": 8,
    "pb": 8,
    "destroyed": 9,
    "wrecked": 9,
    "brutal": 9,
    "hell": 9,
}

# Positive modifiers (reduce RPE by 1)
POSITIVE_MODIFIERS = ["felt great", "felt good", "strong", "fresh", "energized"]

# Negative modifiers (increase RPE by 1)
NEGATIVE_MODIFIERS = ["tired", "fatigued", "legs heavy", "sluggish", "struggled"]


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
# INJURY DETECTION
# ============================================================

INJURY_KEYWORDS = {
    "pain": FlagSeverity.MODERATE,
    "painful": FlagSeverity.MODERATE,
    "hurts": FlagSeverity.MODERATE,
    "hurt": FlagSeverity.MODERATE,
    "ache": FlagSeverity.MILD,
    "aching": FlagSeverity.MILD,
    "tight": FlagSeverity.MILD,
    "tightness": FlagSeverity.MILD,
    "sore": FlagSeverity.MILD,
    "soreness": FlagSeverity.MILD,
    "strain": FlagSeverity.MODERATE,
    "strained": FlagSeverity.MODERATE,
    "pulled": FlagSeverity.MODERATE,
    "injured": FlagSeverity.SEVERE,
    "injury": FlagSeverity.SEVERE,
    "sharp pain": FlagSeverity.SEVERE,
    "stabbing": FlagSeverity.SEVERE,
}

BODY_PART_PATTERNS = {
    BodyPart.KNEE: ["knee", "knees"],
    BodyPart.ANKLE: ["ankle", "ankles"],
    BodyPart.CALF: ["calf", "calves", "calf muscle"],
    BodyPart.SHIN: ["shin", "shins", "shin splint"],
    BodyPart.HIP: ["hip", "hips", "hip flexor"],
    BodyPart.HAMSTRING: ["hamstring", "hamstrings", "hammie"],
    BodyPart.QUAD: ["quad", "quads", "quadricep"],
    BodyPart.ACHILLES: ["achilles", "achilles tendon"],
    BodyPart.FOOT: ["foot", "feet", "plantar", "heel"],
    BodyPart.BACK: ["back", "lower back", "spine"],
    BodyPart.SHOULDER: ["shoulder", "shoulders"],
}


# ============================================================
# ILLNESS DETECTION
# ============================================================

ILLNESS_PATTERNS = {
    # Mild - 48 hours rest recommended
    "cold": (FlagSeverity.MILD, 48),
    "sniffles": (FlagSeverity.MILD, 48),
    "runny nose": (FlagSeverity.MILD, 48),
    "slight cold": (FlagSeverity.MILD, 48),
    # Moderate - 72 hours rest recommended
    "sick": (FlagSeverity.MODERATE, 72),
    "flu": (FlagSeverity.MODERATE, 72),
    "fever": (FlagSeverity.MODERATE, 72),
    "chills": (FlagSeverity.MODERATE, 72),
    "body aches": (FlagSeverity.MODERATE, 72),
    "nausea": (FlagSeverity.MODERATE, 72),
    # Severe - 96 hours rest recommended
    "chest congestion": (FlagSeverity.SEVERE, 96),
    "chest infection": (FlagSeverity.SEVERE, 96),
    "breathing issues": (FlagSeverity.SEVERE, 96),
    "difficulty breathing": (FlagSeverity.SEVERE, 96),
    "covid": (FlagSeverity.SEVERE, 96),
    "pneumonia": (FlagSeverity.SEVERE, 96),
}


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
    Perform complete analysis on an activity.

    This is the main entry point. Calls all sub-analyzers and combines results.

    Args:
        activity: Normalized activity with notes
        athlete_profile: Profile with vital signs for HR-based RPE

    Returns:
        Complete analysis including RPE, flags, and wellness
    """
    # Detect treadmill first (needed by RPE estimation)
    treadmill = detect_treadmill(
        activity_name=activity.name,
        description=activity.description,
        has_gps=activity.has_polyline,
        sport_type=activity.sport_type,
        sub_type=activity.sub_type,
        device_name=activity.gear_id,  # Using gear_id as proxy for device
    )

    # Estimate RPE from all sources
    final_rpe, all_estimates, conflict = estimate_rpe(activity, athlete_profile)

    # Extract injury flags
    injury_flags = extract_injury_flags(activity.description, activity.private_note)

    # Extract illness flags
    illness_flags = extract_illness_flags(activity.description, activity.private_note)

    # Extract wellness indicators
    wellness = extract_wellness_indicators(
        activity.description, activity.private_note
    )

    # Extract contextual factors
    context = extract_contextual_factors(
        activity.description, activity.private_note, activity.start_time
    )

    # Check if any notes are present
    notes_present = bool(activity.description or activity.private_note)

    return AnalysisResult(
        activity_id=activity.id,
        estimated_rpe=final_rpe,
        rpe_conflict=conflict,
        all_rpe_estimates=all_estimates,
        treadmill_detection=treadmill,
        injury_flags=injury_flags,
        illness_flags=illness_flags,
        wellness=wellness,
        context=context,
        analyzed_at=datetime.now(timezone.utc),
        notes_present=notes_present,
    )


# ============================================================
# RPE ESTIMATION
# ============================================================


def estimate_rpe(
    activity: NormalizedActivity,
    athlete_profile: AthleteProfile,
) -> tuple[RPEEstimate, list[RPEEstimate], Optional[RPEConflict]]:
    """
    Estimate RPE from all available sources and resolve conflicts.

    Priority Order:
    1. Explicit user input (Strava perceived_exertion) - always wins
    2. HR-based estimate (when reliable HR present)
    3. Text-based estimate from notes
    4. Strava relative effort normalization
    5. Duration + sport heuristic (fallback)

    Args:
        activity: Activity with HR, notes, suffer_score
        athlete_profile: Profile with max_hr, lthr

    Returns:
        (final_estimate, all_estimates, conflict if detected)
    """
    estimates: list[RPEEstimate] = []

    # 1. User input - highest priority (always wins)
    if activity.perceived_exertion:
        user_estimate = RPEEstimate(
            value=activity.perceived_exertion,
            source=RPESource.USER_INPUT,
            confidence="high",
            reasoning="User explicitly entered RPE in Strava",
        )
        # User input is absolute - return immediately
        return (user_estimate, [user_estimate], None)

    # 2. HR-based estimate
    if activity.has_hr_data and activity.average_hr:
        hr_estimate = estimate_rpe_from_hr(
            average_hr=activity.average_hr,
            max_hr_activity=activity.max_hr,
            athlete_max_hr=athlete_profile.vital_signs.max_hr
            if athlete_profile and athlete_profile.vital_signs
            else None,
            athlete_lthr=athlete_profile.vital_signs.lthr
            if athlete_profile and athlete_profile.vital_signs
            else None,
            duration_minutes=activity.duration_seconds // 60,
        )
        if hr_estimate:
            estimates.append(hr_estimate)

    # 3. Text-based estimate
    text_estimate = estimate_rpe_from_text(
        description=activity.description,
        private_note=activity.private_note,
        activity_name=activity.name,
    )
    if text_estimate:
        estimates.append(text_estimate)

    # 4. Strava relative effort
    if activity.suffer_score:
        rel_estimate = estimate_rpe_from_strava_relative(
            suffer_score=activity.suffer_score,
            duration_minutes=activity.duration_seconds // 60,
        )
        if rel_estimate:
            estimates.append(rel_estimate)

    # 5. Duration heuristic fallback
    duration_estimate = estimate_rpe_from_duration(
        sport_type=activity.sport_type,
        duration_minutes=activity.duration_seconds // 60,
    )
    estimates.append(duration_estimate)

    # Resolve if we have estimates
    if not estimates:
        # Should never happen (duration fallback always works)
        return (
            RPEEstimate(
                value=5,
                source=RPESource.DURATION_HEURISTIC,
                confidence="low",
                reasoning="No data available",
            ),
            [],
            None,
        )

    # Check for conflicts
    conflict = None
    values = [e.value for e in estimates]
    spread = max(values) - min(values)

    if spread > 2 and len(estimates) > 1:
        # Conflict detected
        is_high_intensity = is_high_intensity_session(
            activity,
            athlete_profile.vital_signs.max_hr
            if athlete_profile and athlete_profile.vital_signs
            else None,
        )
        resolved_value, method = resolve_rpe_conflict(estimates, is_high_intensity)
        conflict = RPEConflict(
            estimates=estimates,
            spread=spread,
            resolved_value=resolved_value,
            resolution_method=method,
        )
        final = RPEEstimate(
            value=resolved_value,
            source=RPESource.HR_BASED if "HR" in method else RPESource.TEXT_BASED,
            confidence="medium",
            reasoning=f"Resolved conflict: {method}",
        )
    else:
        # Use highest priority estimate (first in list with user_input priority)
        final = _select_best_estimate(estimates)

    return final, estimates, conflict


def estimate_rpe_from_hr(
    average_hr: int,
    max_hr_activity: Optional[int],
    athlete_max_hr: Optional[int],
    athlete_lthr: Optional[int],
    duration_minutes: int,
) -> Optional[RPEEstimate]:
    """
    Derive RPE from heart rate data.

    HR Zone → RPE Mapping:
    - <60% max HR: RPE 1-3 (very easy)
    - 60-70% max HR: RPE 4 (easy)
    - 70-80% max HR: RPE 5-6 (moderate)
    - 80-90% max HR: RPE 7-8 (hard)
    - >90% max HR: RPE 9-10 (very hard)

    Duration adjustment: Long sessions at moderate HR → bump RPE

    Args:
        average_hr: Average heart rate during activity
        max_hr_activity: Max HR reached during activity
        athlete_max_hr: Athlete's known max HR
        athlete_lthr: Athlete's lactate threshold heart rate
        duration_minutes: Activity duration

    Returns:
        RPE estimate or None if insufficient data
    """
    # Determine max HR to use
    max_hr = athlete_max_hr or max_hr_activity
    if not max_hr:
        return None

    hr_percent = (average_hr / max_hr) * 100

    # Base RPE from HR zones
    if hr_percent < 60:
        base_rpe = 2
    elif hr_percent < 70:
        base_rpe = 4
    elif hr_percent < 80:
        base_rpe = 5
    elif hr_percent < 85:
        base_rpe = 6
    elif hr_percent < 90:
        base_rpe = 7
    elif hr_percent < 95:
        base_rpe = 8
    else:
        base_rpe = 9

    # Duration adjustment (long sessions are harder)
    duration_adjustment = 0
    if duration_minutes > 90 and base_rpe >= 4:
        duration_adjustment = 1
    elif duration_minutes > 150 and base_rpe >= 4:
        duration_adjustment = 2

    final_rpe = min(10, base_rpe + duration_adjustment)

    # Confidence based on data quality
    confidence = "high" if athlete_max_hr else "medium"

    return RPEEstimate(
        value=final_rpe,
        source=RPESource.HR_BASED,
        confidence=confidence,
        reasoning=f"HR {average_hr} = {hr_percent:.0f}% of max ({max_hr})",
    )


def estimate_rpe_from_text(
    description: Optional[str],
    private_note: Optional[str],
    activity_name: Optional[str],
) -> Optional[RPEEstimate]:
    """
    Extract RPE from activity text content.

    Combines title, description, and private note for analysis.

    Args:
        description: Public description
        private_note: Private notes
        activity_name: Activity title

    Returns:
        RPE estimate or None if no keywords found
    """
    # Combine all text sources
    text_parts = [
        activity_name or "",
        description or "",
        private_note or "",
    ]
    combined_text = " ".join(text_parts).lower()

    if not combined_text.strip():
        return None

    # Find matching keywords
    found_keywords = []
    rpe_values = []

    for keyword, rpe in RPE_KEYWORDS.items():
        if keyword in combined_text:
            found_keywords.append(keyword)
            rpe_values.append(rpe)

    if not rpe_values:
        return None

    # Base RPE from keywords (use max for conservative estimate)
    base_rpe = max(rpe_values)

    # Apply modifiers
    modifier = 0
    for pos in POSITIVE_MODIFIERS:
        if pos in combined_text:
            modifier -= 1  # Felt good = slightly easier than expected
            break

    for neg in NEGATIVE_MODIFIERS:
        if neg in combined_text:
            modifier += 1  # Struggled = harder than expected
            break

    final_rpe = max(1, min(10, base_rpe + modifier))

    # Confidence based on keyword specificity
    confidence = "high" if len(found_keywords) > 1 else "medium"

    return RPEEstimate(
        value=final_rpe,
        source=RPESource.TEXT_BASED,
        confidence=confidence,
        reasoning=f"Keywords: {', '.join(found_keywords[:3])}",
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


def resolve_rpe_conflict(
    estimates: list[RPEEstimate],
    is_high_intensity_session: bool,
) -> tuple[int, str]:
    """
    Resolve conflicting RPE estimates using decision tree.

    Resolution Priority:
    1. User input always wins (should not reach here)
    2. For high-intensity sessions: use MAX(HR, text) - trust higher signal
    3. For non-high-intensity: use text-based (HR can be elevated by stress)
    4. If spread > 3: use MAX (conservative = higher load)

    Args:
        estimates: All available estimates
        is_high_intensity_session: Whether session appears high-intensity

    Returns:
        (resolved_value, resolution_method)
    """
    # Filter by source type
    hr_estimates = [e for e in estimates if e.source == RPESource.HR_BASED]
    text_estimates = [e for e in estimates if e.source == RPESource.TEXT_BASED]

    hr_value = hr_estimates[0].value if hr_estimates else None
    text_value = text_estimates[0].value if text_estimates else None

    # Calculate spread
    all_values = [e.value for e in estimates]
    spread = max(all_values) - min(all_values)

    # Resolution logic
    if spread > 3:
        # Large disagreement - be conservative (higher load is safer)
        return max(all_values), f"Large spread ({spread}); using MAX for safety"

    if is_high_intensity_session:
        # High intensity: trust whichever is higher
        if hr_value and text_value:
            return (
                max(hr_value, text_value),
                "High-intensity session; MAX(HR, text)",
            )
        elif hr_value:
            return hr_value, "High-intensity session; HR-based"
        elif text_value:
            return text_value, "High-intensity session; text-based"
    else:
        # Non-high intensity: trust text over HR (HR can be elevated)
        if text_value:
            return (
                text_value,
                "Non-high-intensity; text-based (HR may be elevated)",
            )
        elif hr_value:
            return hr_value, "Non-high-intensity; HR-based (only source)"

    # Fallback: average
    avg = sum(all_values) // len(all_values)
    return avg, "Fallback: average of estimates"


def is_high_intensity_session(
    activity: NormalizedActivity,
    athlete_max_hr: Optional[int],
) -> bool:
    """
    Detect if session appears to be high-intensity.

    Indicators:
    - HR > 85% of max
    - Workout type indicates intervals/tempo/race
    - Keywords in title/notes

    Args:
        activity: Normalized activity
        athlete_max_hr: Athlete's known max HR

    Returns:
        True if session appears high-intensity
    """
    # HR indicator
    if athlete_max_hr and activity.average_hr:
        hr_percent = (activity.average_hr / athlete_max_hr) * 100
        if hr_percent > 85:
            return True

    # Workout type indicator
    if activity.workout_type in {1, 3}:  # Race or Workout
        return True

    # Keyword indicator
    high_intensity_keywords = [
        "interval",
        "tempo",
        "threshold",
        "race",
        "vo2",
        "speed",
        "track",
        "fartlek",
    ]
    combined = f"{activity.name or ''} {activity.description or ''}".lower()
    if any(kw in combined for kw in high_intensity_keywords):
        return True

    return False


def _select_best_estimate(estimates: list[RPEEstimate]) -> RPEEstimate:
    """
    Select best estimate by source priority.

    Priority: USER_INPUT > HR_BASED > TEXT_BASED > STRAVA_RELATIVE > DURATION_HEURISTIC

    Args:
        estimates: List of estimates

    Returns:
        Highest priority estimate
    """
    priority = {
        RPESource.USER_INPUT: 0,
        RPESource.HR_BASED: 1,
        RPESource.TEXT_BASED: 2,
        RPESource.STRAVA_RELATIVE: 3,
        RPESource.DURATION_HEURISTIC: 4,
    }
    return min(estimates, key=lambda e: priority[e.source])


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
    confidence = "high" if confidence_score >= 4 else "low"

    return TreadmillDetection(
        is_treadmill=is_treadmill,
        confidence=confidence,
        signals=signals if signals else ["No treadmill signals detected"],
    )


# ============================================================
# INJURY FLAG EXTRACTION
# ============================================================


def extract_injury_flags(
    description: Optional[str],
    private_note: Optional[str],
) -> list[InjuryFlag]:
    """
    Extract injury/pain mentions with body part and severity.

    Args:
        description: Public description
        private_note: Private notes

    Returns:
        List of injury flags
    """
    combined = f"{description or ''} {private_note or ''}".lower()
    if not combined.strip():
        return []

    flags = []

    for keyword, severity in INJURY_KEYWORDS.items():
        if keyword not in combined:
            continue

        # Find associated body part
        body_part = BodyPart.GENERAL
        for part, patterns in BODY_PART_PATTERNS.items():
            if any(p in combined for p in patterns):
                body_part = part
                break

        # Extract surrounding context (for source_text)
        idx = combined.find(keyword)
        start = max(0, idx - 30)
        end = min(len(combined), idx + len(keyword) + 30)
        context = combined[start:end].strip()

        # Determine if rest is required
        requires_rest = severity in {FlagSeverity.MODERATE, FlagSeverity.SEVERE}

        flags.append(
            InjuryFlag(
                body_part=body_part,
                severity=severity,
                keywords_found=[keyword],
                source_text=f"...{context}...",
                requires_rest=requires_rest,
            )
        )

    # Deduplicate by body part (keep highest severity)
    seen_parts = {}
    for flag in flags:
        key = flag.body_part
        if key not in seen_parts or _severity_rank(flag.severity) > _severity_rank(
            seen_parts[key].severity
        ):
            seen_parts[key] = flag

    return list(seen_parts.values())


def _severity_rank(severity: FlagSeverity) -> int:
    """Rank severity for comparison."""
    return {
        FlagSeverity.MILD: 1,
        FlagSeverity.MODERATE: 2,
        FlagSeverity.SEVERE: 3,
    }[severity]


# ============================================================
# ILLNESS FLAG EXTRACTION
# ============================================================


def extract_illness_flags(
    description: Optional[str],
    private_note: Optional[str],
) -> list[IllnessFlag]:
    """
    Detect illness signals with severity classification.

    Args:
        description: Public description
        private_note: Private notes

    Returns:
        List of illness flags (usually 0 or 1)
    """
    combined = f"{description or ''} {private_note or ''}".lower()
    if not combined.strip():
        return []

    found_symptoms = []
    max_severity = FlagSeverity.MILD
    max_rest_days = 0
    keywords_found = []

    for pattern, (severity, rest_hours) in ILLNESS_PATTERNS.items():
        if pattern in combined:
            found_symptoms.append(pattern)
            keywords_found.append(pattern)
            if _severity_rank(severity) > _severity_rank(max_severity):
                max_severity = severity
            rest_days = rest_hours // 24
            if rest_days > max_rest_days:
                max_rest_days = rest_days

    if not found_symptoms:
        return []

    # Extract context
    first_keyword = keywords_found[0]
    idx = combined.find(first_keyword)
    start = max(0, idx - 30)
    end = min(len(combined), idx + len(first_keyword) + 30)
    context = combined[start:end].strip()

    return [
        IllnessFlag(
            severity=max_severity,
            symptoms=found_symptoms,
            keywords_found=keywords_found,
            source_text=f"...{context}...",
            rest_days_recommended=max_rest_days,
        )
    ]


# ============================================================
# WELLNESS INDICATORS
# ============================================================


def extract_wellness_indicators(
    description: Optional[str],
    private_note: Optional[str],
) -> WellnessIndicators:
    """
    Extract wellness signals (sleep, soreness, stress).

    Args:
        description: Public description
        private_note: Private notes

    Returns:
        WellnessIndicators object
    """
    combined = f"{description or ''} {private_note or ''}".lower()

    wellness = WellnessIndicators()

    if not combined.strip():
        return wellness

    # Sleep quality
    if any(kw in combined for kw in ["slept well", "good sleep", "rested", "well rested"]):
        wellness.sleep_quality = "good"
    elif any(
        kw in combined
        for kw in ["bad sleep", "poor sleep", "slept poorly", "slept bad", "didn't sleep", "insomnia"]
    ):
        wellness.sleep_quality = "poor"
    elif any(
        kw in combined for kw in ["disrupted sleep", "woke up", "restless night", "restless sleep"]
    ):
        wellness.sleep_quality = "disrupted"

    # Sleep hours (look for patterns like "5 hours sleep", "only 6 hours", "6h")
    # Try with "sleep" keyword first
    sleep_match = re.search(r"(\d+)\s*(hours?|hrs?|h)\s*(?:of\s*)?sleep", combined)
    if not sleep_match:
        # Try without "sleep" if context suggests sleep (slept, sleep quality keywords)
        if any(kw in combined for kw in ["slept", "sleep", "rested", "woke"]):
            sleep_match = re.search(r"(\d+)\s*(hours?|hrs?|h)", combined)
    if sleep_match:
        wellness.sleep_hours = float(sleep_match.group(1))

    # Soreness level (1-10 scale)
    if "very sore" in combined or "extremely sore" in combined:
        wellness.soreness_level = 8
    elif "quite sore" in combined or "pretty sore" in combined:
        wellness.soreness_level = 6
    elif "sore" in combined or "soreness" in combined:
        wellness.soreness_level = 4
    elif "slightly sore" in combined:
        wellness.soreness_level = 2

    # Stress level
    if any(kw in combined for kw in ["stressed", "stressful", "high stress"]):
        wellness.stress_level = "high"
    elif any(kw in combined for kw in ["moderate stress", "some stress"]):
        wellness.stress_level = "moderate"
    elif any(kw in combined for kw in ["relaxed", "calm", "low stress"]):
        wellness.stress_level = "low"

    # Fatigue
    wellness.fatigue_mentioned = any(
        kw in combined for kw in ["fatigued", "fatigue", "exhausted", "worn out"]
    )

    # Energy level
    if any(kw in combined for kw in ["high energy", "energized", "felt great"]):
        wellness.energy_level = "high"
    elif any(kw in combined for kw in ["low energy", "tired", "sluggish"]):
        wellness.energy_level = "low"
    else:
        wellness.energy_level = "normal"

    return wellness


# ============================================================
# CONTEXTUAL FACTORS
# ============================================================


def extract_contextual_factors(
    description: Optional[str],
    private_note: Optional[str],
    start_time: Optional[datetime],
) -> ContextualFactors:
    """
    Extract environmental and situational context.

    Args:
        description: Public description
        private_note: Private notes
        start_time: Activity start time

    Returns:
        ContextualFactors object
    """
    combined = f"{description or ''} {private_note or ''}".lower()

    context = ContextualFactors()

    if not combined.strip():
        return context

    # Fasted
    context.is_fasted = any(
        kw in combined
        for kw in ["fasted", "fasting", "no breakfast", "empty stomach"]
    )

    # Weather conditions
    context.heat_mentioned = any(kw in combined for kw in ["hot", "heat", "humid"])
    context.cold_mentioned = any(
        kw in combined for kw in ["cold", "freezing", "chilly"]
    )
    context.altitude_mentioned = any(
        kw in combined for kw in ["altitude", "elevation", "thin air", "mountains"]
    )

    # Travel
    context.travel_mentioned = any(
        kw in combined for kw in ["traveling", "travel", "trip", "vacation"]
    )

    # Time of day
    context.after_work = any(kw in combined for kw in ["after work", "evening run"])

    # Early morning detection from start_time
    if start_time:
        hour = start_time.hour
        context.early_morning = 4 <= hour <= 6

    return context
