# M11 — Adaptation Engine

## 1. Metadata

| Field | Value |
|-------|-------|
| Module ID | M11 |
| Name | Adaptation Engine |
| Version | 1.0.1 |
| Status | Draft |
| Dependencies | M3 (Repository I/O), M4 (Athlete Profile), M9 (Metrics Engine), M10 (Plan Generator) |

### Changelog
- **1.0.1** (2026-01-12): Converted all dataclass types to BaseModel for consistency. Added complete algorithms for `expire_stale_suggestions()`, `get_pending_suggestions()`, and `track_override_pattern()` to remove `...` placeholders and make spec LLM-implementable.
- **1.0.0** (initial): Initial draft with comprehensive adaptation trigger logic

## 2. Purpose

Generate workout adaptation suggestions based on current metrics, health flags, and training status. Implements the "Suggest, Don't Auto-Modify" philosophy where the plan remains stable until the user accepts changes (with safety-critical exceptions).

### 2.1 Scope Boundaries

**In Scope:**
- Generating adaptation suggestions from triggers
- Managing pending suggestions queue
- Applying accepted suggestions
- Safety-critical auto-overrides (illness, injury)
- Workout execution assessment
- Override tracking and pattern analysis
- Expiring stale suggestions

**Out of Scope:**
- Computing metrics (M9)
- Generating the original plan (M10)
- Extracting flags from notes (M7)
- Formatting suggestions for display (M12)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage |
|--------|-------|
| M3 | Read/write workout files, suggestions file |
| M4 | Get conflict policy, constraints |
| M9 | Get current metrics (CTL/ATL/TSB, ACWR, readiness) |
| M10 | Read plan structure, workout details |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
```

## 4. Public Interface

### 4.1 Type Definitions

```python
from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AdaptationTrigger(str, Enum):
    """Conditions that trigger adaptation suggestions"""
    ACWR_ELEVATED = "acwr_elevated"           # ACWR > 1.3
    ACWR_HIGH_RISK = "acwr_high_risk"         # ACWR > 1.5
    LOW_READINESS = "low_readiness"           # Readiness < 50
    VERY_LOW_READINESS = "very_low_readiness" # Readiness < 35
    HIGH_LOWER_BODY = "high_lower_body"       # Lower-body load above threshold
    INJURY_FLAG = "injury_flag"               # Pain/injury detected
    ILLNESS_FLAG = "illness_flag"             # Sickness detected
    HARD_SESSION_CAP = "hard_session_cap"     # 2+ hard in 7 days
    OVERREACHED = "overreached"               # TSB < -25
    MISSED_WORKOUT = "missed_workout"         # Scheduled workout not done


class SuggestionType(str, Enum):
    """Types of workout modifications"""
    DOWNGRADE = "downgrade"     # Reduce intensity (tempo → easy)
    SKIP = "skip"               # Skip workout entirely
    MOVE = "move"               # Move to different day
    SUBSTITUTE = "substitute"   # Replace with different workout
    SHORTEN = "shorten"         # Reduce duration
    FORCE_REST = "force_rest"   # Mandatory rest (safety)


class SuggestionStatus(str, Enum):
    """Status of a suggestion"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    AUTO_APPLIED = "auto_applied"  # Safety override


class OverrideRisk(str, Enum):
    """Risk level if user overrides suggestion"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"  # Cannot override


class WorkoutReference(BaseModel):
    """Reference to a specific workout"""
    file_path: str
    date: date
    workout_type: str
    is_key_workout: bool


class ProposedChange(BaseModel):
    """The proposed modification to a workout"""
    workout_type: str
    duration_minutes: int
    intensity_zone: str
    target_rpe: int
    notes: Optional[str] = None


class Suggestion(BaseModel):
    """A single adaptation suggestion"""
    # Identity
    id: str
    created_at: datetime

    # Trigger
    trigger: AdaptationTrigger
    trigger_value: float              # The metric value that triggered
    trigger_threshold: float          # The threshold exceeded

    # Affected workout
    affected_workout: WorkoutReference

    # Changes
    suggestion_type: SuggestionType
    original: dict                    # Original workout params
    proposed: ProposedChange

    # Explanation
    rationale: str                    # Human-readable explanation
    override_risk: OverrideRisk       # Risk if declined

    # Status
    status: SuggestionStatus
    expires_at: datetime              # When suggestion becomes stale

    # Response (filled when resolved)
    user_response: Optional[str] = None
    response_at: Optional[datetime] = None
    override_warning_shown: bool = False


class SafetyOverride(BaseModel):
    """Record of an automatic safety override"""
    id: str
    applied_at: datetime
    trigger: AdaptationTrigger
    affected_workout: WorkoutReference
    action_taken: str
    user_notified: bool
    user_can_override: bool
    override_warning: Optional[str] = None


class AdaptationResult(BaseModel):
    """Result of running adaptation analysis"""
    suggestions: list[Suggestion]
    safety_overrides: list[SafetyOverride]
    warnings: list[str]
    metrics_snapshot: dict
```

### 4.2 Trigger Configuration

```python
# Adaptation triggers with thresholds
TRIGGER_CONFIG = {
    AdaptationTrigger.ACWR_ELEVATED: {
        "threshold": 1.3,
        "suggestion_type": SuggestionType.DOWNGRADE,
        "override_risk": OverrideRisk.MODERATE,
        "message": "ACWR elevated ({value:.2f}). Consider reducing intensity.",
    },
    AdaptationTrigger.ACWR_HIGH_RISK: {
        "threshold": 1.5,
        "suggestion_type": SuggestionType.DOWNGRADE,
        "override_risk": OverrideRisk.HIGH,
        "auto_apply_with": AdaptationTrigger.VERY_LOW_READINESS,
        "message": "ACWR high risk ({value:.2f}). Strong recommendation to rest.",
    },
    AdaptationTrigger.LOW_READINESS: {
        "threshold": 50,
        "direction": "below",
        "suggestion_type": SuggestionType.DOWNGRADE,
        "override_risk": OverrideRisk.MODERATE,
        "message": "Readiness low ({value}). Recovery day recommended.",
    },
    AdaptationTrigger.VERY_LOW_READINESS: {
        "threshold": 35,
        "direction": "below",
        "suggestion_type": SuggestionType.FORCE_REST,
        "override_risk": OverrideRisk.HIGH,
        "message": "Readiness very low ({value}). Rest strongly recommended.",
    },
    AdaptationTrigger.INJURY_FLAG: {
        "suggestion_type": SuggestionType.FORCE_REST,
        "override_risk": OverrideRisk.HIGH,
        "duration_days": 3,
        "message": "Injury detected ({body_part}). Rest recommended for recovery.",
    },
    AdaptationTrigger.ILLNESS_FLAG: {
        "suggestion_type": SuggestionType.FORCE_REST,
        "override_risk": OverrideRisk.SEVERE,  # Cannot override severe illness
        "duration_days_by_severity": {"mild": 2, "moderate": 3, "severe": 4},
        "message": "Illness detected. Rest is critical for recovery.",
    },
    AdaptationTrigger.HARD_SESSION_CAP: {
        "threshold": 2,
        "suggestion_type": SuggestionType.DOWNGRADE,
        "override_risk": OverrideRisk.MODERATE,
        "message": "Already {value} hard sessions in 7 days. Easy day recommended.",
    },
    AdaptationTrigger.HIGH_LOWER_BODY: {
        "suggestion_type": SuggestionType.MOVE,
        "override_risk": OverrideRisk.MODERATE,
        "message": "Lower-body load elevated. Consider moving quality run.",
    },
}
```

### 4.3 Function Signatures

```python
from typing import Sequence


def generate_adaptation_suggestions(
    metrics: "DailyMetrics",
    plan: "MasterPlan",
    profile: "AthleteProfile",
    flags: Optional[dict] = None,
) -> AdaptationResult:
    """
    Analyze current state and generate adaptation suggestions.

    Called after each sync to check if workouts need adjustment.

    Args:
        metrics: Current metrics from M9
        plan: Active plan from M10
        profile: Athlete profile for conflict policy
        flags: Active injury/illness flags

    Returns:
        Suggestions and any auto-applied safety overrides
    """
    ...


def apply_suggestion(
    suggestion_id: str,
    repo: "RepositoryIO",
    user_comment: Optional[str] = None,
) -> bool:
    """
    Apply an accepted suggestion to the workout.

    Args:
        suggestion_id: ID of suggestion to apply
        repo: Repository for file updates
        user_comment: Optional user comment

    Returns:
        True if successfully applied
    """
    ...


def decline_suggestion(
    suggestion_id: str,
    repo: "RepositoryIO",
    user_comment: Optional[str] = None,
) -> dict:
    """
    Decline a suggestion. Logs the decline and shows warning if risky.

    Returns:
        Warning message if override is risky, else empty
    """
    ...


def expire_stale_suggestions(
    repo: "RepositoryIO",
) -> int:
    """
    Mark expired suggestions. Called on each sync.

    Process:
        1. Load pending_suggestions.yaml
        2. Check expires_at for each pending suggestion
        3. Mark as expired if past expiration datetime
        4. Write updated suggestions back to file
        5. Return count of newly expired suggestions

    Returns:
        Number of suggestions expired
    """
    from datetime import datetime

    # Load suggestions
    suggestions_data = repo.read_yaml("plans/pending_suggestions.yaml")
    suggestions = suggestions_data.get("pending_suggestions", [])

    now = datetime.now()
    expired_count = 0

    for suggestion in suggestions:
        if suggestion["status"] == "pending":
            expires_at = datetime.fromisoformat(suggestion["expires_at"])
            if now > expires_at:
                suggestion["status"] = "expired"
                expired_count += 1

    # Write back if any changed
    if expired_count > 0:
        repo.write_yaml("plans/pending_suggestions.yaml", suggestions_data)

    return expired_count


def get_pending_suggestions(
    repo: "RepositoryIO",
) -> list[Suggestion]:
    """
    Get all pending suggestions.

    Process:
        1. Load pending_suggestions.yaml
        2. Filter for status == "pending"
        3. Parse each into Suggestion object
        4. Sort by created_at (oldest first)
        5. Return list

    Returns:
        List of pending Suggestion objects
    """
    from datetime import datetime

    # Load suggestions file
    try:
        suggestions_data = repo.read_yaml("plans/pending_suggestions.yaml")
    except FileNotFoundError:
        return []

    suggestions_list = suggestions_data.get("pending_suggestions", [])

    # Filter and parse pending suggestions
    pending = []
    for sugg_dict in suggestions_list:
        if sugg_dict["status"] == "pending":
            # Parse datetime strings
            sugg_dict["created_at"] = datetime.fromisoformat(sugg_dict["created_at"])
            sugg_dict["expires_at"] = datetime.fromisoformat(sugg_dict["expires_at"])
            if sugg_dict.get("response_at"):
                sugg_dict["response_at"] = datetime.fromisoformat(sugg_dict["response_at"])

            # Parse nested objects
            sugg_dict["affected_workout"] = WorkoutReference(**sugg_dict["affected_workout"])
            sugg_dict["proposed"] = ProposedChange(**sugg_dict["proposed"])

            # Create Suggestion object
            suggestion = Suggestion(**sugg_dict)
            pending.append(suggestion)

    # Sort by created_at (oldest first)
    pending.sort(key=lambda s: s.created_at)

    return pending


def check_workout_triggers(
    workout: "WorkoutPrescription",
    metrics: "DailyMetrics",
    flags: Optional[dict],
) -> list[AdaptationTrigger]:
    """
    Check which triggers apply to a specific workout.
    """
    ...


def calculate_lower_body_threshold(
    metrics_history: list["DailyMetrics"],
    profile: "AthleteProfile",
) -> float:
    """
    Calculate lower-body load threshold for adaptation triggers.

    Uses tiered approach:
    - >= 14 days: 1.5 × median(14-day lower_body)
    - < 14 days: 300 AU absolute threshold
    """
    ...


def assess_workout_execution(
    workout: "WorkoutPrescription",
    activity: "NormalizedActivity",
    load_calc: "LoadCalculation",
) -> dict:
    """
    Assess how well a completed activity matched the prescription.

    Returns compliance metrics and coach review.
    """
    ...


def track_override_pattern(
    athlete_id: str,
    suggestion_id: str,
    trigger: AdaptationTrigger,
    repo: "RepositoryIO",
) -> Optional[str]:
    """
    Track override patterns for memory extraction.

    If athlete repeatedly overrides same trigger type,
    generate insight for M13.

    Process:
        1. Load adaptation_log.yaml
        2. Count recent declined suggestions for this trigger
        3. If >= 3 declined in last 30 days, generate insight
        4. Return insight message for M13 to store as memory

    Returns:
        Pattern insight if detected, else None
    """
    from datetime import datetime, timedelta

    # Load adaptation log
    try:
        log_data = repo.read_yaml("plans/adaptation_log.yaml")
    except FileNotFoundError:
        log_data = {"_schema": {"format_version": "1.0.0", "schema_type": "adaptation_log"}, "adaptations": []}

    # Add current decline to log
    log_entry = {
        "id": suggestion_id,
        "date": datetime.now().isoformat(),
        "trigger": trigger.value,
        "status": "declined",
        "athlete_id": athlete_id,
    }
    log_data.setdefault("adaptations", []).append(log_entry)

    # Count recent declines for this trigger type
    cutoff_date = datetime.now() - timedelta(days=30)
    recent_declines = [
        entry for entry in log_data["adaptations"]
        if (
            entry.get("trigger") == trigger.value
            and entry.get("status") == "declined"
            and datetime.fromisoformat(entry["date"]) > cutoff_date
        )
    ]

    # Write updated log
    repo.write_yaml("plans/adaptation_log.yaml", log_data)

    # Check for pattern (3+ declines in 30 days)
    decline_count = len(recent_declines)
    if decline_count >= 3:
        # Generate insight message
        trigger_messages = {
            AdaptationTrigger.ACWR_ELEVATED: "tends to push through elevated ACWR warnings",
            AdaptationTrigger.LOW_READINESS: "often overrides low readiness suggestions",
            AdaptationTrigger.HIGH_LOWER_BODY: "prefers to proceed with workouts despite high lower-body load",
            AdaptationTrigger.HARD_SESSION_CAP: "comfortable with higher training frequency than typical",
        }

        pattern_description = trigger_messages.get(
            trigger,
            f"frequently declines {trigger.value} suggestions"
        )

        insight = (
            f"Pattern detected: Athlete {pattern_description} "
            f"({decline_count} times in last 30 days). "
            "Consider adjusting trigger thresholds or discussing training philosophy."
        )

        return insight

    return None
```

### 4.4 Error Types

```python
class AdaptationError(Exception):
    """Base error for adaptation operations"""
    pass


class SuggestionNotFoundError(AdaptationError):
    """Suggestion ID not found"""
    def __init__(self, suggestion_id: str):
        super().__init__(f"Suggestion not found: {suggestion_id}")
        self.suggestion_id = suggestion_id


class SuggestionExpiredError(AdaptationError):
    """Cannot apply expired suggestion"""
    def __init__(self, suggestion_id: str):
        super().__init__(f"Suggestion expired: {suggestion_id}")
        self.suggestion_id = suggestion_id


class CannotOverrideError(AdaptationError):
    """Safety override cannot be declined"""
    def __init__(self, reason: str):
        super().__init__(f"Cannot override: {reason}")
        self.reason = reason
```

## 5. Core Algorithms

### 5.1 Suggestion Generation Pipeline

```python
from datetime import datetime, timedelta
import uuid


def generate_adaptation_suggestions(
    metrics: "DailyMetrics",
    plan: "MasterPlan",
    profile: "AthleteProfile",
    flags: Optional[dict] = None,
) -> AdaptationResult:
    """
    Main adaptation analysis pipeline.
    """
    suggestions = []
    safety_overrides = []
    warnings = []

    # Get upcoming workouts (next 3 days)
    today = date.today()
    upcoming = _get_upcoming_workouts(plan, today, days=3)

    for workout in upcoming:
        # Check all triggers for this workout
        triggers = check_workout_triggers(workout, metrics, flags)

        for trigger in triggers:
            # Check if safety override applies
            if _is_safety_override(trigger, flags):
                override = _apply_safety_override(
                    trigger, workout, flags, profile
                )
                safety_overrides.append(override)
                continue

            # Generate suggestion
            suggestion = _create_suggestion(
                trigger=trigger,
                workout=workout,
                metrics=metrics,
                profile=profile,
            )

            # Deduplicate (one suggestion per workout)
            existing = next(
                (s for s in suggestions
                 if s.affected_workout.file_path == workout.file_path),
                None
            )
            if existing:
                # Keep higher priority trigger
                if _trigger_priority(trigger) > _trigger_priority(existing.trigger):
                    suggestions.remove(existing)
                    suggestions.append(suggestion)
            else:
                suggestions.append(suggestion)

    # Check conflict policy
    suggestions = _apply_conflict_policy(suggestions, profile.conflict_policy)

    return AdaptationResult(
        suggestions=suggestions,
        safety_overrides=safety_overrides,
        warnings=warnings,
        metrics_snapshot={
            "ctl": metrics.ctl_atl.ctl,
            "atl": metrics.ctl_atl.atl,
            "tsb": metrics.ctl_atl.tsb,
            "acwr": metrics.acwr.acwr,
            "readiness": metrics.readiness.score,
        },
    )


def _trigger_priority(trigger: AdaptationTrigger) -> int:
    """Higher number = higher priority (more urgent)"""
    return {
        AdaptationTrigger.ILLNESS_FLAG: 100,
        AdaptationTrigger.INJURY_FLAG: 90,
        AdaptationTrigger.ACWR_HIGH_RISK: 80,
        AdaptationTrigger.VERY_LOW_READINESS: 70,
        AdaptationTrigger.ACWR_ELEVATED: 50,
        AdaptationTrigger.LOW_READINESS: 40,
        AdaptationTrigger.HIGH_LOWER_BODY: 30,
        AdaptationTrigger.HARD_SESSION_CAP: 20,
        AdaptationTrigger.MISSED_WORKOUT: 10,
    }.get(trigger, 0)
```

### 5.2 Trigger Evaluation

```python
def check_workout_triggers(
    workout: "WorkoutPrescription",
    metrics: "DailyMetrics",
    flags: Optional[dict],
) -> list[AdaptationTrigger]:
    """
    Evaluate all triggers for a specific workout.
    """
    triggers = []

    # Only check quality workouts for intensity-based triggers
    is_quality = workout.workout_type in {"tempo", "intervals", "long_run"}

    # ACWR checks
    if metrics.acwr.acwr is not None:
        if metrics.acwr.acwr > 1.5:
            triggers.append(AdaptationTrigger.ACWR_HIGH_RISK)
        elif metrics.acwr.acwr > 1.3 and is_quality:
            triggers.append(AdaptationTrigger.ACWR_ELEVATED)

    # Readiness checks
    if metrics.readiness.score < 35:
        triggers.append(AdaptationTrigger.VERY_LOW_READINESS)
    elif metrics.readiness.score < 50 and is_quality:
        triggers.append(AdaptationTrigger.LOW_READINESS)

    # TSB overreach check
    if metrics.ctl_atl.tsb < -25:
        triggers.append(AdaptationTrigger.OVERREACHED)

    # Lower-body load check (for quality/long runs)
    if is_quality:
        lb_threshold = _get_lower_body_threshold(metrics)
        yesterday_lb = _get_yesterday_lower_body(metrics)
        if yesterday_lb > lb_threshold:
            triggers.append(AdaptationTrigger.HIGH_LOWER_BODY)

    # Hard session cap check
    if is_quality:
        hard_count = metrics.intensity_distribution.high_intensity_sessions_7d
        if hard_count >= 2:
            triggers.append(AdaptationTrigger.HARD_SESSION_CAP)

    # Flag checks
    if flags:
        if flags.get("injury", {}).get("active"):
            triggers.append(AdaptationTrigger.INJURY_FLAG)
        if flags.get("illness", {}).get("active"):
            triggers.append(AdaptationTrigger.ILLNESS_FLAG)

    return triggers
```

### 5.3 Safety Override Logic

```python
def _is_safety_override(
    trigger: AdaptationTrigger,
    flags: Optional[dict],
) -> bool:
    """
    Determine if trigger requires automatic safety override.

    Safety overrides bypass suggestion queue and apply immediately.
    """
    # Illness with severe symptoms = always override
    if trigger == AdaptationTrigger.ILLNESS_FLAG:
        severity = flags.get("illness", {}).get("severity", "mild")
        if severity in {"moderate", "severe"}:
            return True
        # Check for chest symptoms (always severe)
        symptoms = flags.get("illness", {}).get("symptoms", [])
        chest_symptoms = {"chest", "breathing", "fever"}
        if any(s in " ".join(symptoms).lower() for s in chest_symptoms):
            return True

    # ACWR > 1.5 AND readiness < 35 = combined danger
    # (This is checked at suggestion generation level)

    return False


def _apply_safety_override(
    trigger: AdaptationTrigger,
    workout: "WorkoutPrescription",
    flags: dict,
    profile: "AthleteProfile",
) -> SafetyOverride:
    """
    Apply automatic safety override.
    """
    override_id = f"override_{uuid.uuid4().hex[:8]}"
    now = datetime.now()

    # Determine action and message based on trigger
    if trigger == AdaptationTrigger.ILLNESS_FLAG:
        severity = flags.get("illness", {}).get("severity", "moderate")
        rest_days = {"mild": 2, "moderate": 3, "severe": 4}.get(severity, 3)
        action = f"Force rest for {rest_days} days"
        can_override = severity == "mild"
        warning = (
            "Rest is critical when sick. Exercise while ill can prolong "
            "recovery and has cardiac risks." if not can_override else
            "I recommend rest, but you can override if symptoms are mild."
        )
    elif trigger == AdaptationTrigger.INJURY_FLAG:
        body_part = flags.get("injury", {}).get("body_part", "unknown")
        action = f"Force rest day due to {body_part} pain"
        can_override = True
        warning = (
            f"I noticed you mentioned {body_part} pain. Running through "
            "pain can extend recovery time."
        )
    else:
        action = "Force rest day"
        can_override = True
        warning = "Strong recommendation to rest today."

    # Modify workout file
    _force_workout_to_rest(workout)

    return SafetyOverride(
        id=override_id,
        applied_at=now,
        trigger=trigger,
        affected_workout=WorkoutReference(
            file_path=workout.file_path,
            date=workout.date,
            workout_type=workout.workout_type,
            is_key_workout=workout.key_workout,
        ),
        action_taken=action,
        user_notified=True,
        user_can_override=can_override,
        override_warning=warning,
    )
```

### 5.4 Suggestion Creation

```python
def _create_suggestion(
    trigger: AdaptationTrigger,
    workout: "WorkoutPrescription",
    metrics: "DailyMetrics",
    profile: "AthleteProfile",
) -> Suggestion:
    """
    Create a suggestion based on trigger type.
    """
    suggestion_id = f"sugg_{date.today().isoformat()}_{uuid.uuid4().hex[:4]}"
    now = datetime.now()

    config = TRIGGER_CONFIG[trigger]
    suggestion_type = config["suggestion_type"]
    override_risk = config["override_risk"]

    # Get trigger value
    trigger_value = _get_trigger_value(trigger, metrics)
    threshold = config.get("threshold", 0)

    # Calculate proposed change based on suggestion type
    if suggestion_type == SuggestionType.DOWNGRADE:
        proposed = _calculate_downgrade(workout)
    elif suggestion_type == SuggestionType.SKIP:
        proposed = ProposedChange(
            workout_type="rest",
            duration_minutes=0,
            intensity_zone="zone_1",
            target_rpe=1,
            notes="Skipped due to recovery needs",
        )
    elif suggestion_type == SuggestionType.MOVE:
        proposed = _calculate_move(workout, metrics)
    elif suggestion_type == SuggestionType.SHORTEN:
        proposed = _calculate_shorten(workout)
    else:  # FORCE_REST
        proposed = ProposedChange(
            workout_type="rest",
            duration_minutes=0,
            intensity_zone="zone_1",
            target_rpe=1,
            notes="Rest day for recovery",
        )

    # Build rationale
    rationale = config["message"].format(
        value=trigger_value,
        body_part=getattr(metrics, 'injury_body_part', 'affected area'),
    )

    # Set expiration (end of workout day)
    expires_at = datetime.combine(
        workout.date,
        datetime.max.time()
    )

    return Suggestion(
        id=suggestion_id,
        created_at=now,
        trigger=trigger,
        trigger_value=trigger_value,
        trigger_threshold=threshold,
        affected_workout=WorkoutReference(
            file_path=workout.file_path,
            date=workout.date,
            workout_type=workout.workout_type,
            is_key_workout=workout.key_workout,
        ),
        suggestion_type=suggestion_type,
        original={
            "workout_type": workout.workout_type,
            "duration_minutes": workout.duration_minutes,
            "intensity_zone": workout.intensity_zone,
            "target_rpe": workout.target_rpe,
        },
        proposed=proposed,
        rationale=rationale,
        override_risk=override_risk,
        status=SuggestionStatus.PENDING,
        expires_at=expires_at,
    )


def _calculate_downgrade(workout: "WorkoutPrescription") -> ProposedChange:
    """
    Calculate downgraded workout parameters.
    """
    # Reduce intensity by 2 RPE points, change type if needed
    new_rpe = max(3, workout.target_rpe - 2)

    if workout.workout_type in {"intervals", "tempo"}:
        new_type = "easy"
        new_zone = "zone_2"
    else:
        new_type = workout.workout_type
        new_zone = "zone_2"

    return ProposedChange(
        workout_type=new_type,
        duration_minutes=workout.duration_minutes,  # Keep duration
        intensity_zone=new_zone,
        target_rpe=new_rpe,
        notes=f"Downgraded from {workout.workout_type} due to fatigue",
    )


def _calculate_shorten(workout: "WorkoutPrescription") -> ProposedChange:
    """
    Calculate shortened workout (reduce duration by 25-30%).
    """
    new_duration = int(workout.duration_minutes * 0.7)

    return ProposedChange(
        workout_type=workout.workout_type,
        duration_minutes=new_duration,
        intensity_zone=workout.intensity_zone,
        target_rpe=workout.target_rpe,
        notes=f"Shortened from {workout.duration_minutes}min",
    )
```

### 5.5 Suggestion Application

```python
def apply_suggestion(
    suggestion_id: str,
    repo: "RepositoryIO",
    user_comment: Optional[str] = None,
) -> bool:
    """
    Apply an accepted suggestion to the workout file.
    """
    # Load suggestions
    suggestions_data = repo.read_yaml("plans/pending_suggestions.yaml")
    suggestions = suggestions_data.get("pending_suggestions", [])

    # Find suggestion
    suggestion = next(
        (s for s in suggestions if s["id"] == suggestion_id),
        None
    )
    if not suggestion:
        raise SuggestionNotFoundError(suggestion_id)

    if suggestion["status"] == "expired":
        raise SuggestionExpiredError(suggestion_id)

    # Load and modify workout file
    workout_path = suggestion["affected_workout"]["file"]
    workout_data = repo.read_yaml(workout_path)

    # Apply proposed changes
    proposed = suggestion["proposed"]
    workout_data["workout_type"] = proposed["workout_type"]
    workout_data["duration_minutes"] = proposed["duration_minutes"]
    workout_data["intensity"]["zone"] = proposed["intensity_zone"]
    workout_data["intensity"]["target_rpe"] = proposed["target_rpe"]
    workout_data["status"] = "adapted"
    workout_data["adaptation"] = {
        "suggestion_id": suggestion_id,
        "original": suggestion["original"],
        "trigger": suggestion["trigger"],
        "applied_at": datetime.now().isoformat(),
    }

    # Write workout
    repo.write_yaml(workout_path, workout_data)

    # Update suggestion status
    suggestion["status"] = "accepted"
    suggestion["response_at"] = datetime.now().isoformat()
    suggestion["user_response"] = user_comment

    # Write suggestions
    repo.write_yaml("plans/pending_suggestions.yaml", suggestions_data)

    return True


def decline_suggestion(
    suggestion_id: str,
    repo: "RepositoryIO",
    user_comment: Optional[str] = None,
) -> dict:
    """
    Decline a suggestion with appropriate warnings.
    """
    # Load suggestions
    suggestions_data = repo.read_yaml("plans/pending_suggestions.yaml")
    suggestions = suggestions_data.get("pending_suggestions", [])

    suggestion = next(
        (s for s in suggestions if s["id"] == suggestion_id),
        None
    )
    if not suggestion:
        raise SuggestionNotFoundError(suggestion_id)

    # Check if can be overridden
    override_risk = suggestion["override_risk"]
    if override_risk == "severe":
        raise CannotOverrideError(
            "This is a safety-critical recommendation that cannot be overridden."
        )

    # Generate warning based on risk
    warning = None
    if override_risk == "high":
        warning = (
            "I strongly recommend following this suggestion. "
            f"Proceeding with {suggestion['affected_workout']['workout_type']} "
            "increases injury risk. Are you sure you want to override?"
        )
    elif override_risk == "moderate":
        warning = (
            "Consider this suggestion carefully. Your metrics indicate "
            "elevated fatigue. Proceeding is your choice."
        )

    # Update suggestion
    suggestion["status"] = "declined"
    suggestion["response_at"] = datetime.now().isoformat()
    suggestion["user_response"] = user_comment
    suggestion["override_warning_shown"] = warning is not None

    # Track override for pattern analysis
    track_override_pattern(
        athlete_id="current",
        suggestion_id=suggestion_id,
        trigger=suggestion["trigger"],
        repo=repo,
    )

    # Write suggestions
    repo.write_yaml("plans/pending_suggestions.yaml", suggestions_data)

    return {"warning": warning} if warning else {}
```

### 5.6 Lower-Body Threshold Calculation

```python
def calculate_lower_body_threshold(
    metrics_history: list["DailyMetrics"],
    profile: "AthleteProfile",
) -> float:
    """
    Calculate adaptive lower-body load threshold.

    Tiered approach:
    - Tier 1 (≥14 days): 1.5 × median(14-day lower_body)
    - Tier 2 (<14 days): 300 AU absolute

    Sport adjustments:
    - Leg-dominant primary sport: +20%
    - Running is primary: -10%
    """
    days_of_data = len(metrics_history)

    if days_of_data >= 14:
        # Tier 1: Relative threshold
        lower_body_loads = [
            m.daily_load.lower_body_daily_load_au
            for m in metrics_history[-14:]
        ]
        median_lb = sorted(lower_body_loads)[len(lower_body_loads) // 2]
        base_threshold = median_lb * 1.5
    else:
        # Tier 2: Absolute threshold
        base_threshold = 300.0

    # Apply sport adjustments
    leg_dominant_sports = {"cycling", "crossfit", "skiing", "climbing"}
    if profile.primary_sport.lower() in leg_dominant_sports:
        base_threshold *= 1.2  # +20% for acclimatized athletes
    elif profile.running_priority == "primary":
        base_threshold *= 0.9  # -10% to protect running more

    return base_threshold
```

### 5.7 Workout Execution Assessment

```python
def assess_workout_execution(
    workout: "WorkoutPrescription",
    activity: "NormalizedActivity",
    load_calc: "LoadCalculation",
) -> dict:
    """
    Assess how well execution matched prescription.
    """
    assessment = {
        "duration_compliance": None,
        "pace_compliance": None,
        "hr_compliance": None,
        "overall_compliance": None,
        "notes": [],
    }

    # Duration compliance
    prescribed_duration = workout.duration_minutes
    actual_duration = activity.duration_minutes
    duration_ratio = actual_duration / prescribed_duration if prescribed_duration > 0 else 1

    if 0.9 <= duration_ratio <= 1.1:
        assessment["duration_compliance"] = "good"
    elif 0.75 <= duration_ratio < 0.9:
        assessment["duration_compliance"] = "short"
        assessment["notes"].append(f"Shorter than prescribed ({actual_duration} vs {prescribed_duration} min)")
    elif duration_ratio > 1.1:
        assessment["duration_compliance"] = "long"
        assessment["notes"].append(f"Longer than prescribed ({actual_duration} vs {prescribed_duration} min)")
    else:
        assessment["duration_compliance"] = "very_short"

    # HR compliance (if available)
    if activity.has_hr_data and workout.hr_range_low:
        avg_hr = activity.average_hr
        if workout.hr_range_low <= avg_hr <= workout.hr_range_high:
            assessment["hr_compliance"] = "good"
        elif avg_hr < workout.hr_range_low:
            assessment["hr_compliance"] = "under"
            assessment["notes"].append("HR below target zone")
        else:
            assessment["hr_compliance"] = "over"
            assessment["notes"].append("HR above target zone")

    # Pace compliance (skip for treadmill)
    if activity.surface_type != "treadmill" and activity.distance_km:
        assessment["pace_compliance"] = _assess_pace(
            activity.distance_km,
            activity.duration_minutes,
            workout.pace_range_min_km,
            workout.pace_range_max_km,
        )
    elif activity.surface_type == "treadmill":
        assessment["pace_compliance"] = "unverifiable_treadmill"
        assessment["notes"].append("Treadmill pace not verified (calibration varies)")

    # Overall compliance
    good_count = sum(
        1 for k, v in assessment.items()
        if isinstance(v, str) and v == "good"
    )
    total_checked = sum(
        1 for k, v in assessment.items()
        if v is not None and k.endswith("_compliance") and v != "unverifiable_treadmill"
    )

    if total_checked == 0:
        assessment["overall_compliance"] = "unknown"
    elif good_count == total_checked:
        assessment["overall_compliance"] = "excellent"
    elif good_count >= total_checked * 0.5:
        assessment["overall_compliance"] = "acceptable"
    else:
        assessment["overall_compliance"] = "poor"

    return assessment
```

## 6. Data Structures

### 6.1 Pending Suggestions File

```yaml
# plans/pending_suggestions.yaml
_schema:
  format_version: "1.0.0"
  schema_type: "pending_suggestions"

pending_suggestions:
  - id: "sugg_2025-03-15_a1b2"
    created_at: "2025-03-15T08:30:00Z"
    trigger: "acwr_elevated"
    trigger_value: 1.42
    trigger_threshold: 1.3
    affected_workout:
      file: "plans/workouts/week_03/tuesday_tempo.yaml"
      date: "2025-03-18"
      workout_type: "tempo"
      is_key_workout: true
    suggestion_type: "downgrade"
    original:
      workout_type: "tempo"
      duration_minutes: 45
      intensity_zone: "zone_4"
      target_rpe: 7
    proposed:
      workout_type: "easy"
      duration_minutes: 45
      intensity_zone: "zone_2"
      target_rpe: 4
      notes: "Downgraded from tempo due to fatigue"
    rationale: "ACWR elevated (1.42). Consider reducing intensity."
    override_risk: "moderate"
    status: "pending"
    expires_at: "2025-03-18T23:59:59Z"
    user_response: null
    response_at: null
```

### 6.2 Adaptation Log Schema

```yaml
# plans/adaptation_log.yaml
_schema:
  format_version: "1.0.0"
  schema_type: "adaptation_log"

adaptations:
  - id: "sugg_2025-03-15_a1b2"
    date: "2025-03-18"
    trigger: "acwr_elevated"
    original_workout: "tempo"
    action: "downgraded to easy"
    status: "accepted"
    metrics_at_decision:
      acwr: 1.42
      readiness: 58
      tsb: -12

  - id: "override_2025-03-10_x1y2"
    date: "2025-03-10"
    trigger: "illness_flag"
    original_workout: "intervals"
    action: "force_rest"
    status: "auto_applied"
    notes: "Flu symptoms detected"
```

## 7. Integration Points

### 7.1 Called By

| Module | When |
|--------|------|
| M1 | After sync completes |
| M1 | Before "what should I do today" response |
| M1 | When user accepts/declines suggestion |

### 7.2 Calls To

| Module | Purpose |
|--------|---------|
| M3 | Read/write workout and suggestion files |
| M4 | Get conflict policy |
| M9 | Get current metrics |
| M10 | Read plan structure |

### 7.3 Returns To

| Module | Data |
|--------|------|
| M12 | Suggestions for user display |
| M13 | Override patterns for memory extraction |

## 8. Test Scenarios

### 8.1 Trigger Tests

```python
def test_acwr_elevated_triggers():
    """ACWR > 1.3 triggers suggestion for quality workouts"""
    metrics = mock_metrics(acwr=1.35)
    workout = mock_workout(workout_type="tempo")

    triggers = check_workout_triggers(workout, metrics, None)

    assert AdaptationTrigger.ACWR_ELEVATED in triggers


def test_acwr_safe_no_trigger():
    """ACWR in safe zone doesn't trigger"""
    metrics = mock_metrics(acwr=1.1)
    workout = mock_workout(workout_type="tempo")

    triggers = check_workout_triggers(workout, metrics, None)

    assert AdaptationTrigger.ACWR_ELEVATED not in triggers


def test_illness_forces_rest():
    """Severe illness auto-applies rest"""
    flags = {"illness": {"active": True, "severity": "moderate"}}

    result = generate_adaptation_suggestions(
        mock_metrics(), mock_plan(), mock_profile(), flags
    )

    assert len(result.safety_overrides) > 0
    assert result.safety_overrides[0].action_taken.startswith("Force rest")
```

### 8.2 Suggestion Management Tests

```python
def test_apply_suggestion():
    """Accepted suggestion modifies workout"""
    repo = MockRepositoryIO()
    setup_test_suggestion(repo)

    apply_suggestion("sugg_test_001", repo)

    workout = repo.read_yaml("plans/workouts/test.yaml")
    assert workout["status"] == "adapted"


def test_decline_with_warning():
    """Declining high-risk shows warning"""
    repo = MockRepositoryIO()
    setup_test_suggestion(repo, override_risk="high")

    result = decline_suggestion("sugg_test_001", repo)

    assert "warning" in result
    assert "injury risk" in result["warning"]


def test_cannot_override_severe():
    """Cannot decline severe safety override"""
    repo = MockRepositoryIO()
    setup_test_suggestion(repo, override_risk="severe")

    with pytest.raises(CannotOverrideError):
        decline_suggestion("sugg_test_001", repo)
```

### 8.3 Lower-Body Threshold Tests

```python
def test_threshold_tier1():
    """14+ days uses relative threshold"""
    history = [mock_metrics(lower_body=200) for _ in range(14)]
    profile = mock_profile(primary_sport="climbing")

    threshold = calculate_lower_body_threshold(history, profile)

    # 200 median × 1.5 = 300, × 1.2 (climbing) = 360
    assert threshold == pytest.approx(360, rel=0.05)


def test_threshold_tier2():
    """<14 days uses absolute threshold"""
    history = [mock_metrics() for _ in range(7)]
    profile = mock_profile()

    threshold = calculate_lower_body_threshold(history, profile)

    assert threshold == 300.0
```

## 9. Configuration

### 9.1 Adaptation Thresholds

```python
ADAPTATION_CONFIG = {
    "acwr_elevated_threshold": 1.3,
    "acwr_high_risk_threshold": 1.5,
    "readiness_low_threshold": 50,
    "readiness_very_low_threshold": 35,
    "hard_session_cap": 2,
    "lower_body_absolute_threshold": 300,
    "lower_body_relative_multiplier": 1.5,
    "suggestion_expiry_hours": 24,
}
```

## 10. Safety Philosophy

### 10.1 Suggest, Don't Auto-Modify

The default behavior is to generate suggestions that the user can accept or decline. This preserves:
- Plan stability (no unexpected changes)
- Athlete autonomy (user makes final call)
- Transparency (all suggestions logged with rationale)

### 10.2 Safety-Critical Exceptions

Some conditions are too dangerous to await approval:

| Condition | Action | Override? |
|-----------|--------|-----------|
| Severe illness | Force rest | No |
| Fever/chest symptoms | Force rest 72h | No |
| Injury + ACWR > 1.5 | Force rest | Yes, with warning |
| ACWR > 1.5 + readiness < 35 | Auto-downgrade | Yes, with strong warning |
