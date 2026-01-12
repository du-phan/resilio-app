# M7 — Notes & RPE Analyzer

## 1. Metadata

| Field | Value |
|-------|-------|
| Module ID | M7 |
| Name | Notes & RPE Analyzer |
| Code Module | `core/notes.py` |
| Version | 1.0.2 |
| Status | Draft |
| Dependencies | M3 (Repository I/O), M4 (Athlete Profile) |

## 2. Purpose

Extract structured data from unstructured activity notes and metadata. Provides RPE estimates when direct input is unavailable, detects treadmill/indoor activities, and identifies wellness flags (injury, illness, fatigue) for downstream processing.

### 2.1 Scope Boundaries

**In Scope:**
- RPE estimation from multiple sources (HR, text, Strava relative effort)
- RPE conflict resolution when sources disagree
- Treadmill/indoor activity detection
- Injury and illness flag extraction
- Wellness indicator parsing (sleep, soreness, stress)
- Contextual factor extraction (heat, altitude, fasted)

**Out of Scope:**
- Computing load values (M8)
- Persisting flags to daily metrics (M9)
- Long-term memory extraction (M13)
- Activity normalization (M6)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage |
|--------|-------|
| M3 | Read activity files |
| M4 | Get athlete vital signs (max_hr, lthr) for HR-based RPE |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
regex>=2023.0        # Enhanced regex for text parsing (optional)
```

## 4. Internal Interface

**Note:** This module is called internally by M1 workflows as part of the sync pipeline. Claude Code should NOT import from `core/notes.py` directly.

### 4.1 Type Definitions

```python
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RPESource(str, Enum):
    """Source of RPE estimate"""
    USER_INPUT = "user_input"         # Explicit Strava perceived_exertion
    HR_BASED = "hr_based"             # Derived from HR zones
    TEXT_BASED = "text_based"         # Extracted from notes
    STRAVA_RELATIVE = "strava_relative"  # Normalized suffer_score
    DURATION_HEURISTIC = "duration_heuristic"  # Sport + duration fallback


class FlagSeverity(str, Enum):
    """Severity level for health flags"""
    MILD = "mild"          # Informational, no action required
    MODERATE = "moderate"  # Consider adjustments
    SEVERE = "severe"      # Requires rest or medical attention


class BodyPart(str, Enum):
    """Tracked body parts for injury flags"""
    KNEE = "knee"
    ANKLE = "ankle"
    CALF = "calf"
    SHIN = "shin"
    HIP = "hip"
    HAMSTRING = "hamstring"
    QUAD = "quad"
    ACHILLES = "achilles"
    FOOT = "foot"
    BACK = "back"
    SHOULDER = "shoulder"
    GENERAL = "general"


class RPEEstimate(BaseModel):
    """RPE estimate with source and confidence"""
    value: int  # 1-10
    source: RPESource
    confidence: str  # "high" | "medium" | "low"
    reasoning: str  # Explanation for the estimate


class RPEConflict(BaseModel):
    """Detected conflict between RPE sources"""
    estimates: list[RPEEstimate]
    spread: int  # Difference between max and min
    resolved_value: int
    resolution_method: str


class TreadmillDetection(BaseModel):
    """Result of treadmill/indoor detection"""
    is_treadmill: bool
    confidence: str  # "high" | "low"
    signals: list[str] = Field(default_factory=list)  # Evidence for detection


class InjuryFlag(BaseModel):
    """Detected injury or pain signal"""
    body_part: BodyPart
    severity: FlagSeverity
    keywords_found: list[str] = Field(default_factory=list)
    source_text: str
    requires_rest: bool


class IllnessFlag(BaseModel):
    """Detected illness signal"""
    severity: FlagSeverity
    symptoms: list[str] = Field(default_factory=list)
    keywords_found: list[str] = Field(default_factory=list)
    source_text: str
    rest_days_recommended: int


class WellnessIndicators(BaseModel):
    """Extracted wellness signals"""
    sleep_quality: Optional[str] = None  # "good" | "poor" | "disrupted"
    sleep_hours: Optional[float] = None
    soreness_level: Optional[int] = None  # 1-10
    stress_level: Optional[str] = None  # "low" | "moderate" | "high"
    fatigue_mentioned: bool = False
    energy_level: Optional[str] = None  # "low" | "normal" | "high"


class ContextualFactors(BaseModel):
    """Environmental or situational factors"""
    is_fasted: bool = False
    heat_mentioned: bool = False
    cold_mentioned: bool = False
    altitude_mentioned: bool = False
    travel_mentioned: bool = False
    after_work: bool = False
    early_morning: bool = False


class AnalysisResult(BaseModel):
    """Complete analysis result for an activity"""
    activity_id: str

    # RPE
    estimated_rpe: RPEEstimate
    rpe_conflict: Optional[RPEConflict] = None
    all_rpe_estimates: list[RPEEstimate] = Field(default_factory=list)

    # Treadmill
    treadmill_detection: TreadmillDetection

    # Health flags
    injury_flags: list[InjuryFlag] = Field(default_factory=list)
    illness_flags: list[IllnessFlag] = Field(default_factory=list)

    # Wellness
    wellness: WellnessIndicators

    # Context
    context: ContextualFactors

    # Metadata
    analyzed_at: datetime
    notes_present: bool
```

### 4.2 Function Signatures

```python
from typing import Sequence


def analyze_activity(
    activity: "NormalizedActivity",
    athlete_profile: "AthleteProfile",
) -> AnalysisResult:
    """
    Perform complete analysis on an activity.

    Args:
        activity: Normalized activity with notes
        athlete_profile: Profile with vital signs for HR-based RPE

    Returns:
        Complete analysis including RPE, flags, and wellness

    Note:
        This is the main entry point. Calls all sub-analyzers.
    """
    ...


def estimate_rpe(
    activity: "NormalizedActivity",
    athlete_profile: "AthleteProfile",
) -> tuple[RPEEstimate, list[RPEEstimate], Optional[RPEConflict]]:
    """
    Estimate RPE from all available sources and resolve conflicts.

    Args:
        activity: Activity with HR, notes, suffer_score
        athlete_profile: Profile with max_hr, lthr

    Returns:
        (final_estimate, all_estimates, conflict if detected)
    """
    ...


def estimate_rpe_from_hr(
    average_hr: int,
    max_hr_activity: Optional[int],
    athlete_max_hr: Optional[int],
    athlete_lthr: Optional[int],
    duration_minutes: int,
) -> Optional[RPEEstimate]:
    """
    Derive RPE from heart rate data.

    Uses HR reserve method when max_hr available,
    falls back to absolute HR zones otherwise.
    """
    ...


def estimate_rpe_from_text(
    description: Optional[str],
    private_note: Optional[str],
    activity_name: Optional[str],
) -> Optional[RPEEstimate]:
    """
    Extract RPE signals from text content.

    Parses keywords like "easy", "hard", "struggled", "felt great".
    """
    ...


def estimate_rpe_from_strava_relative(
    suffer_score: Optional[int],
    duration_minutes: int,
) -> Optional[RPEEstimate]:
    """
    Normalize Strava's relative effort (suffer_score) to 1-10 RPE.

    Suffer score is HR-derived but on a different scale.
    """
    ...


def estimate_rpe_from_duration(
    sport_type: str,
    duration_minutes: int,
) -> RPEEstimate:
    """
    Fallback RPE based on sport and duration.

    Used when no other data is available.
    """
    ...


def resolve_rpe_conflict(
    estimates: list[RPEEstimate],
    is_high_intensity_session: bool,
) -> tuple[int, str]:
    """
    Resolve conflicting RPE estimates.

    Args:
        estimates: All available estimates
        is_high_intensity_session: Whether session appears high-intensity

    Returns:
        (resolved_value, resolution_method)
    """
    ...


def detect_treadmill(
    activity_name: str,
    description: Optional[str],
    has_gps: bool,
    sport_type: str,
    sub_type: Optional[str],
    device_name: Optional[str],
) -> TreadmillDetection:
    """
    Detect if activity was on treadmill/indoors.

    Signals checked:
    - Activity title contains "treadmill", "indoor", "zwift"
    - No GPS polyline
    - Strava sport_type indicates indoor
    - Device known to be indoor trainer
    """
    ...


def extract_injury_flags(
    description: Optional[str],
    private_note: Optional[str],
) -> list[InjuryFlag]:
    """
    Detect injury/pain mentions in notes.

    Looks for body part + pain keywords combinations.
    """
    ...


def extract_illness_flags(
    description: Optional[str],
    private_note: Optional[str],
) -> list[IllnessFlag]:
    """
    Detect illness signals in notes.

    Distinguishes mild (cold) from severe (fever, chest symptoms).
    """
    ...


def extract_wellness_indicators(
    description: Optional[str],
    private_note: Optional[str],
) -> WellnessIndicators:
    """
    Extract wellness signals (sleep, soreness, stress).
    """
    ...


def extract_contextual_factors(
    description: Optional[str],
    private_note: Optional[str],
    start_time: Optional[datetime],
) -> ContextualFactors:
    """
    Extract environmental and situational context.
    """
    ...


def is_high_intensity_session(
    activity: "NormalizedActivity",
    athlete_max_hr: Optional[int],
) -> bool:
    """
    Determine if session appears to be high-intensity.

    Used for RPE conflict resolution.
    """
    ...
```

### 4.3 Error Types

```python
class AnalysisError(Exception):
    """Base error for analysis failures"""
    pass


class InsufficientDataError(AnalysisError):
    """Not enough data to make a reliable estimate"""
    def __init__(self, activity_id: str, missing: list[str]):
        super().__init__(f"Insufficient data for {activity_id}: missing {missing}")
        self.activity_id = activity_id
        self.missing = missing
```

## 5. Core Algorithms

### 5.1 RPE Estimation Priority

```python
def estimate_rpe(
    activity: "NormalizedActivity",
    athlete_profile: "AthleteProfile",
) -> tuple[RPEEstimate, list[RPEEstimate], Optional[RPEConflict]]:
    """
    RPE estimation with priority-based source selection.

    Priority Order:
    1. Explicit user input (Strava perceived_exertion) - always wins
    2. HR-based estimate (when reliable HR present)
    3. Text-based estimate from notes
    4. Strava relative effort normalization
    5. Duration + sport heuristic (fallback)
    """
    estimates: list[RPEEstimate] = []

    # 1. User input - highest priority
    if activity.perceived_exertion:
        estimates.append(RPEEstimate(
            value=activity.perceived_exertion,
            source=RPESource.USER_INPUT,
            confidence="high",
            reasoning="User explicitly entered RPE in Strava"
        ))

    # 2. HR-based estimate
    if activity.has_hr_data and activity.average_hr:
        hr_estimate = estimate_rpe_from_hr(
            average_hr=activity.average_hr,
            max_hr_activity=activity.max_hr,
            athlete_max_hr=athlete_profile.vital_signs.max_hr,
            athlete_lthr=athlete_profile.vital_signs.lthr,
            duration_minutes=activity.duration_minutes,
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
            duration_minutes=activity.duration_minutes,
        )
        if rel_estimate:
            estimates.append(rel_estimate)

    # 5. Duration heuristic fallback
    duration_estimate = estimate_rpe_from_duration(
        sport_type=activity.sport_type,
        duration_minutes=activity.duration_minutes,
    )
    estimates.append(duration_estimate)

    # Resolve if we have estimates
    if not estimates:
        # Should never happen (duration fallback always works)
        return (
            RPEEstimate(5, RPESource.DURATION_HEURISTIC, "low", "No data"),
            [],
            None
        )

    # Check for conflicts
    conflict = None
    values = [e.value for e in estimates]
    spread = max(values) - min(values)

    if spread > 2 and len(estimates) > 1:
        # Conflict detected
        is_high_intensity = is_high_intensity_session(
            activity, athlete_profile.vital_signs.max_hr
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


def _select_best_estimate(estimates: list[RPEEstimate]) -> RPEEstimate:
    """Select best estimate by source priority"""
    priority = {
        RPESource.USER_INPUT: 0,
        RPESource.HR_BASED: 1,
        RPESource.TEXT_BASED: 2,
        RPESource.STRAVA_RELATIVE: 3,
        RPESource.DURATION_HEURISTIC: 4,
    }
    return min(estimates, key=lambda e: priority[e.source])
```

### 5.2 HR-Based RPE Estimation

```python
def estimate_rpe_from_hr(
    average_hr: int,
    max_hr_activity: Optional[int],
    athlete_max_hr: Optional[int],
    athlete_lthr: Optional[int],
    duration_minutes: int,
) -> Optional[RPEEstimate]:
    """
    Convert HR to RPE using % of max HR or LTHR.

    HR Zone → RPE Mapping:
    - <60% max HR: RPE 1-3 (very easy)
    - 60-70% max HR: RPE 4 (easy)
    - 70-80% max HR: RPE 5-6 (moderate)
    - 80-90% max HR: RPE 7-8 (hard)
    - >90% max HR: RPE 9-10 (very hard)

    Duration adjustment: Long sessions at moderate HR → bump RPE
    """
    # Determine max HR to use
    max_hr = athlete_max_hr or max_hr_activity
    if not max_hr:
        # Try age-based estimate if we have nothing
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
        reasoning=f"HR {average_hr} = {hr_percent:.0f}% of max ({max_hr})"
    )
```

### 5.3 Text-Based RPE Extraction

```python
import re
from typing import Optional


# Keywords mapped to RPE ranges
RPE_KEYWORDS = {
    # Very easy (1-3)
    "recovery": 2, "very easy": 2, "super easy": 2, "shake out": 2,
    "walk": 2, "stroll": 2,

    # Easy (4)
    "easy": 4, "comfortable": 4, "relaxed": 4, "light": 4,
    "conversational": 4, "zone 2": 4, "z2": 4,

    # Moderate (5-6)
    "moderate": 5, "steady": 5, "tempo": 6, "threshold": 6,
    "comfortably hard": 6, "zone 3": 5, "z3": 5, "zone 4": 6, "z4": 6,

    # Hard (7-8)
    "hard": 7, "tough": 7, "challenging": 7, "intervals": 7,
    "vo2max": 8, "vo2": 8, "race pace": 8, "fast": 7,
    "struggled": 7, "suffered": 8,

    # Very hard (9-10)
    "all out": 9, "max effort": 10, "sprint": 9, "race": 8,
    "pr": 8, "pb": 8, "destroyed": 9, "wrecked": 9,
    "brutal": 9, "hell": 9,
}

# Negative/positive modifiers
POSITIVE_MODIFIERS = ["felt great", "felt good", "strong", "fresh", "energized"]
NEGATIVE_MODIFIERS = ["tired", "fatigued", "legs heavy", "sluggish", "struggled"]


def estimate_rpe_from_text(
    description: Optional[str],
    private_note: Optional[str],
    activity_name: Optional[str],
) -> Optional[RPEEstimate]:
    """
    Extract RPE from activity text content.

    Combines title, description, and private note for analysis.
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
        reasoning=f"Keywords: {', '.join(found_keywords[:3])}"
    )
```

### 5.4 RPE Conflict Resolution

```python
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
            return max(hr_value, text_value), "High-intensity session; MAX(HR, text)"
        elif hr_value:
            return hr_value, "High-intensity session; HR-based"
        elif text_value:
            return text_value, "High-intensity session; text-based"
    else:
        # Non-high intensity: trust text over HR (HR can be elevated)
        if text_value:
            return text_value, "Non-high-intensity; text-based (HR may be elevated)"
        elif hr_value:
            return hr_value, "Non-high-intensity; HR-based (only source)"

    # Fallback: average
    avg = sum(all_values) // len(all_values)
    return avg, "Fallback: average of estimates"


def is_high_intensity_session(
    activity: "NormalizedActivity",
    athlete_max_hr: Optional[int],
) -> bool:
    """
    Detect if session appears to be high-intensity.

    Indicators:
    - HR > 85% of max
    - Workout type indicates intervals/tempo
    - Keywords in title/notes
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
        "interval", "tempo", "threshold", "race",
        "vo2", "speed", "track", "fartlek"
    ]
    combined = f"{activity.name or ''} {activity.description or ''}".lower()
    if any(kw in combined for kw in high_intensity_keywords):
        return True

    return False
```

### 5.5 Treadmill Detection

```python
TREADMILL_TITLE_KEYWORDS = [
    "treadmill", "indoor", "zwift", "peloton", "tm run",
    "dreadmill", "inside", "gym run",
]

INDOOR_DEVICE_NAMES = [
    "zwift", "peloton", "tacx", "wahoo kickr",
    "nordictrack", "proform", "sole",
]


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
            signals=["Not a running activity"]
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
        signals=signals if signals else ["No treadmill signals detected"]
    )
```

### 5.6 Injury Flag Extraction

```python
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


def extract_injury_flags(
    description: Optional[str],
    private_note: Optional[str],
) -> list[InjuryFlag]:
    """
    Extract injury/pain mentions with body part and severity.
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

        flags.append(InjuryFlag(
            body_part=body_part,
            severity=severity,
            keywords_found=[keyword],
            source_text=f"...{context}...",
            requires_rest=requires_rest,
        ))

    # Deduplicate by body part (keep highest severity)
    seen_parts = {}
    for flag in flags:
        key = flag.body_part
        if key not in seen_parts or _severity_rank(flag.severity) > _severity_rank(seen_parts[key].severity):
            seen_parts[key] = flag

    return list(seen_parts.values())


def _severity_rank(severity: FlagSeverity) -> int:
    return {FlagSeverity.MILD: 1, FlagSeverity.MODERATE: 2, FlagSeverity.SEVERE: 3}[severity]
```

### 5.7 Illness Flag Extraction

```python
ILLNESS_PATTERNS = {
    # Mild
    "cold": (FlagSeverity.MILD, 48),
    "sniffles": (FlagSeverity.MILD, 48),
    "runny nose": (FlagSeverity.MILD, 48),
    "slight cold": (FlagSeverity.MILD, 48),

    # Moderate
    "sick": (FlagSeverity.MODERATE, 72),
    "flu": (FlagSeverity.MODERATE, 72),
    "fever": (FlagSeverity.MODERATE, 72),
    "chills": (FlagSeverity.MODERATE, 72),
    "body aches": (FlagSeverity.MODERATE, 72),
    "nausea": (FlagSeverity.MODERATE, 72),

    # Severe
    "chest congestion": (FlagSeverity.SEVERE, 96),
    "chest infection": (FlagSeverity.SEVERE, 96),
    "breathing issues": (FlagSeverity.SEVERE, 96),
    "difficulty breathing": (FlagSeverity.SEVERE, 96),
    "covid": (FlagSeverity.SEVERE, 96),
    "pneumonia": (FlagSeverity.SEVERE, 96),
}


def extract_illness_flags(
    description: Optional[str],
    private_note: Optional[str],
) -> list[IllnessFlag]:
    """
    Detect illness signals with severity classification.
    """
    combined = f"{description or ''} {private_note or ''}".lower()
    if not combined.strip():
        return []

    found_symptoms = []
    max_severity = FlagSeverity.MILD
    max_rest_days = 0
    keywords_found = []

    for pattern, (severity, rest_days) in ILLNESS_PATTERNS.items():
        if pattern in combined:
            found_symptoms.append(pattern)
            keywords_found.append(pattern)
            if _severity_rank(severity) > _severity_rank(max_severity):
                max_severity = severity
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

    return [IllnessFlag(
        severity=max_severity,
        symptoms=found_symptoms,
        keywords_found=keywords_found,
        source_text=f"...{context}...",
        rest_days_recommended=max_rest_days // 24,  # Convert hours to days
    )]
```

### 5.8 Treadmill-Specific RPE Adjustment

```python
def adjust_rpe_for_treadmill(
    estimates: list[RPEEstimate],
    is_treadmill: bool,
) -> list[RPEEstimate]:
    """
    For treadmill runs, prioritize HR over pace-based estimates.

    Modifications:
    - Skip pace-based RPE entirely
    - Prioritize HR-based estimate
    - If no HR: default to RPE 6 (moderate effort assumption)
    """
    if not is_treadmill:
        return estimates

    # Filter out any pace-based estimates (shouldn't exist, but defensive)
    filtered = [e for e in estimates if "pace" not in e.reasoning.lower()]

    # Find HR-based estimate
    hr_estimates = [e for e in filtered if e.source == RPESource.HR_BASED]

    if hr_estimates:
        # Boost HR estimate confidence for treadmill
        best_hr = hr_estimates[0]
        return [RPEEstimate(
            value=best_hr.value,
            source=RPESource.HR_BASED,
            confidence="high",  # HR is most reliable for treadmill
            reasoning=f"{best_hr.reasoning} (treadmill: HR prioritized)"
        )] + [e for e in filtered if e.source != RPESource.HR_BASED]

    # No HR data - use conservative default
    if not any(e.source in {RPESource.USER_INPUT, RPESource.TEXT_BASED} for e in filtered):
        filtered.append(RPEEstimate(
            value=6,
            source=RPESource.DURATION_HEURISTIC,
            confidence="low",
            reasoning="Treadmill without HR: assuming moderate effort"
        ))

    return filtered
```

## 6. Integration Points

### 6.1 Integration with API Layer

This module is called internally by M1 workflows as part of the sync pipeline. Claude Code does NOT call M7 directly.

```
Claude Code → api.sync.sync_strava()
                    │
                    ▼
              M1::run_sync_workflow()
                    │
                    ├─► M5::fetch_activities()
                    ├─► M6::normalize_activity()
                    ├─► M7::analyze_activity_notes() ← HERE
                    ├─► M8::calculate_loads()
                    └─► M9::compute_daily_metrics()
```

### 6.2 Called By

| Module | When |
|--------|------|
| M1 (Workflows) | During sync pipeline after M6 normalization |
| M6 | Requests treadmill detection before normalization |

### 6.3 Calls To

| Module | Purpose |
|--------|---------|
| M3 | Read activity files |
| M4 | Get athlete vital signs |

### 6.4 Returns To

| Module | Data |
|--------|------|
| M6 | TreadmillDetection for surface_type |
| M8 | RPE estimates for load calculation |
| M9 | Injury/illness flags for daily metrics |
| M13 | Wellness indicators for memory extraction |

### 6.5 Analysis Pipeline Position

```
[M6 Normalization]
        │
        │ Pre-pass: detect_treadmill()
        │◄──────────────────────────────┐
        │                               │
        ▼                               │
[M7 Notes Analyzer] ────────────────────┘
        │
        ├── RPE estimate ──────────► [M8 Load Engine]
        │
        ├── Injury/illness flags ──► [M9 Metrics Engine]
        │
        └── Wellness indicators ───► [M13 Memory & Insights]
```

## 7. Test Scenarios

### 7.1 RPE Estimation Tests

```python
def test_rpe_user_input_wins():
    """User-entered RPE always takes priority"""
    activity = mock_activity(
        perceived_exertion=8,
        average_hr=140,  # Would suggest ~5-6
        description="Easy recovery run",  # Would suggest 4
    )
    result = estimate_rpe(activity, mock_profile())

    assert result[0].value == 8
    assert result[0].source == RPESource.USER_INPUT


def test_rpe_conflict_high_intensity():
    """High-intensity sessions use MAX(HR, text)"""
    activity = mock_activity(
        average_hr=175,  # ~RPE 8
        description="Felt easy",  # RPE 4
        workout_type=3,  # Workout indicator
    )
    profile = mock_profile(max_hr=180)
    result = estimate_rpe(activity, profile)

    assert result[0].value >= 7  # Should resolve high


def test_rpe_treadmill_prioritizes_hr():
    """Treadmill runs prioritize HR over other sources"""
    estimates = [
        RPEEstimate(5, RPESource.HR_BASED, "medium", "HR based"),
        RPEEstimate(7, RPESource.TEXT_BASED, "medium", "Text based"),
    ]

    adjusted = adjust_rpe_for_treadmill(estimates, is_treadmill=True)

    assert adjusted[0].source == RPESource.HR_BASED
    assert adjusted[0].confidence == "high"
```

### 7.2 Treadmill Detection Tests

```python
def test_treadmill_by_title():
    """Title keywords trigger detection"""
    result = detect_treadmill(
        activity_name="Treadmill tempo run",
        description=None,
        has_gps=True,  # Even with GPS
        sport_type="run",
        sub_type=None,
        device_name=None,
    )

    assert result.is_treadmill is True
    assert "title contains 'treadmill'" in result.signals


def test_treadmill_no_gps():
    """No GPS for run suggests treadmill"""
    result = detect_treadmill(
        activity_name="Morning run",
        description=None,
        has_gps=False,
        sport_type="run",
        sub_type=None,
        device_name=None,
    )

    assert result.is_treadmill is True
    assert "no GPS data" in result.signals


def test_not_treadmill_with_gps():
    """GPS presence without other signals = outdoor"""
    result = detect_treadmill(
        activity_name="Morning run",
        description=None,
        has_gps=True,
        sport_type="run",
        sub_type=None,
        device_name=None,
    )

    assert result.is_treadmill is False
```

### 7.3 Injury Flag Tests

```python
def test_injury_detection_with_body_part():
    """Injury keywords + body part are extracted"""
    flags = extract_injury_flags(
        description=None,
        private_note="Left knee pain at km 8, had to stop",
    )

    assert len(flags) == 1
    assert flags[0].body_part == BodyPart.KNEE
    assert flags[0].severity == FlagSeverity.MODERATE
    assert flags[0].requires_rest is True


def test_mild_soreness_no_rest():
    """Mild soreness doesn't require rest"""
    flags = extract_injury_flags(
        description="Calf felt a bit tight today",
        private_note=None,
    )

    assert len(flags) == 1
    assert flags[0].severity == FlagSeverity.MILD
    assert flags[0].requires_rest is False
```

### 7.4 Illness Flag Tests

```python
def test_severe_illness_detection():
    """Chest symptoms are severe"""
    flags = extract_illness_flags(
        description=None,
        private_note="Still have chest congestion from last week",
    )

    assert len(flags) == 1
    assert flags[0].severity == FlagSeverity.SEVERE
    assert flags[0].rest_days_recommended >= 3


def test_mild_cold_detection():
    """Minor cold is mild severity"""
    flags = extract_illness_flags(
        description="Running with a slight cold, sniffles",
        private_note=None,
    )

    assert len(flags) == 1
    assert flags[0].severity == FlagSeverity.MILD
```

## 8. Configuration

### 8.1 Default Settings

```python
ANALYZER_CONFIG = {
    "rpe_conflict_threshold": 2,     # Points difference to trigger conflict
    "conservative_resolution": True,  # Use MAX on conflict
    "treadmill_confidence_threshold": 2,  # Score needed for detection
    "default_treadmill_rpe": 6,      # RPE when no HR on treadmill
}
```

### 8.2 Keyword Customization

Keywords can be extended without code changes by adding to the dictionaries:

```python
# User can add custom keywords via config
CUSTOM_RPE_KEYWORDS = {
    "bonk": 9,
    "wall": 8,
    "cruising": 5,
}
RPE_KEYWORDS.update(CUSTOM_RPE_KEYWORDS)
```

## 9. Performance Notes

- Text analysis is CPU-bound but fast (~1ms per activity)
- No external API calls
- Regex compilation happens once at module load
- 100 activities analyze in < 200ms

## 10. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.2 | 2026-01-12 | Added code module path (`core/notes.py`) and API layer integration notes. |
| 1.0.1 | 2026-01-12 | **Fixed type consistency**: Converted all `@dataclass` types to `BaseModel` for Pydantic consistency (RPEEstimate, RPEConflict, TreadmillDetection, InjuryFlag, IllnessFlag, WellnessIndicators, ContextualFactors, AnalysisResult - 8 types converted). Removed `dataclass` and `field` imports. Added Pydantic `Field` for default factories. |
| 1.0.0 | 2026-01-12 | Initial specification |
