"""
M11 - Adaptation Toolkit (Toolkit Paradigm)

Provides computational toolkit functions for adaptation detection and risk assessment.

Toolkit Functions (Return Data, Not Decisions):
- Trigger detection: Detect physiological thresholds breached (ACWR, readiness, TSB, load)
- Risk assessment: Calculate heuristic risk index if athlete overrides triggers
- Recovery estimation: Estimate days needed to recover from triggered state

Claude Code Responsibilities (Uses Context to Decide):
- Adaptation decisions: "ACWR 1.45 + climbed yesterday → downgrade, move, or proceed?"
- Risk interpretation: "Elevated risk index + knee history → what does this mean for THIS athlete?"
- Option presentation: Present trade-offs and let athlete decide
- Pattern learning: Track athlete preferences (prefers moving vs downgrading)

The toolkit paradigm separates quantitative detection (this module)
from qualitative coaching decisions (Claude Code with athlete context).
"""

from datetime import datetime, date, timedelta
from typing import Optional
import uuid

from sports_coach_engine.schemas.adaptation import (
    TriggerType,
    AdaptationTrigger,
    OverrideRiskAssessment,
    RecoveryEstimate,
    RiskLevel,
    SuggestionType,
    SuggestionStatus,
    OverrideRisk,
    WorkoutReference,
    ProposedChange,
    Suggestion,
    SafetyOverride,
    AdaptationResult,
)
from sports_coach_engine.core.repository import RepositoryIO


# ============================================================
# TRIGGER CONFIGURATION
# ============================================================


TRIGGER_CONFIG = {
    TriggerType.ACWR_ELEVATED: {
        "threshold": 1.3,
        "direction": "above",
        "zone": "caution",
        "suggestion_type": SuggestionType.DOWNGRADE,
        "override_risk": OverrideRisk.MODERATE,
        "applies_to": ["tempo", "intervals", "race"],  # Quality workouts only
    },
    TriggerType.ACWR_HIGH_RISK: {
        "threshold": 1.5,
        "direction": "above",
        "zone": "danger",
        "suggestion_type": SuggestionType.DOWNGRADE,
        "override_risk": OverrideRisk.HIGH,
        "applies_to": ["tempo", "intervals", "race", "long_run"],
    },
    TriggerType.READINESS_LOW: {
        "threshold": 50,
        "direction": "below",
        "zone": "warning",
        "suggestion_type": SuggestionType.DOWNGRADE,
        "override_risk": OverrideRisk.LOW,
        "applies_to": ["tempo", "intervals", "race"],  # Quality workouts only
    },
    TriggerType.READINESS_VERY_LOW: {
        "threshold": 35,
        "direction": "below",
        "zone": "danger",
        "suggestion_type": SuggestionType.FORCE_REST,
        "override_risk": OverrideRisk.HIGH,
        "applies_to": "all",  # All workouts
    },
    TriggerType.TSB_OVERREACHED: {
        "threshold": -25,
        "direction": "below",
        "zone": "danger",
        "suggestion_type": SuggestionType.DOWNGRADE,
        "override_risk": OverrideRisk.HIGH,
        "applies_to": ["tempo", "intervals", "race", "long_run"],
    },
    TriggerType.LOWER_BODY_LOAD_HIGH: {
        "threshold": None,  # Calculated dynamically
        "direction": "above",
        "zone": "warning",
        "suggestion_type": SuggestionType.DOWNGRADE,
        "override_risk": OverrideRisk.MODERATE,
        "applies_to": ["tempo", "intervals", "long_run"],
    },
    TriggerType.SESSION_DENSITY_HIGH: {
        "threshold": 2,
        "direction": "above_eq",
        "zone": "warning",
        "suggestion_type": SuggestionType.DOWNGRADE,
        "override_risk": OverrideRisk.LOW,
        "applies_to": ["tempo", "intervals", "fartlek"],
    },
}


# Trigger priority for deduplication (higher = more important)
TRIGGER_PRIORITY = {
    TriggerType.ACWR_HIGH_RISK: 80,
    TriggerType.READINESS_VERY_LOW: 70,
    TriggerType.TSB_OVERREACHED: 65,
    TriggerType.ACWR_ELEVATED: 60,
    TriggerType.READINESS_LOW: 50,
    TriggerType.LOWER_BODY_LOAD_HIGH: 40,
    TriggerType.SESSION_DENSITY_HIGH: 30,
}


# ============================================================
# TRIGGER EVALUATION
# ============================================================


def detect_adaptation_triggers(
    workout: dict,
    metrics: dict,
    athlete_profile: dict,
) -> list[AdaptationTrigger]:
    """
    Detect physiological triggers that warrant coaching attention (Toolkit Paradigm).

    Returns structured trigger data with full context (value, threshold, zone).
    Claude Code interprets triggers with athlete history (M13 memories) and
    conversation context to decide adaptations.

    Checks:
    - ACWR elevated (>1.3) or high risk (>1.5)
    - Readiness low (<50) or very low (<35)
    - TSB overreached (<-25)
    - Lower-body load high (>1.5x 14-day median)
    - Session density high (2+ quality in 7 days)

    Uses thresholds from athlete_profile.adaptation_thresholds (can be
    customized per athlete - elite athletes may tolerate higher ACWR).

    Note: Injury/illness signals are extracted by Claude Code via conversation,
    not detected algorithmically here.

    Args:
        workout: Workout dict with type, date, RPE, etc.
        metrics: Current metrics (CTL/ATL/TSB/ACWR/readiness)
        athlete_profile: Athlete profile with adaptation_thresholds

    Returns:
        List of AdaptationTrigger objects with full context

    Example:
        >>> triggers = detect_adaptation_triggers(
        ...     workout={"workout_type": "tempo", "date": date(2026, 1, 21)},
        ...     metrics={"acwr": 1.45, "readiness": 48},
        ...     athlete_profile={"adaptation_thresholds": {...}},
        ... )
        >>> triggers[0].trigger_type
        'acwr_elevated'
        >>> triggers[0].value
        1.45
        >>> triggers[0].zone
        'caution'
    """
    triggered = []
    workout_type = workout.get("workout_type")
    workout_date = workout.get("date", date.today())

    # Get thresholds (use defaults if not in profile)
    thresholds = athlete_profile.get("adaptation_thresholds", {})
    acwr_elevated_threshold = thresholds.get("acwr_elevated", 1.3)
    acwr_high_risk_threshold = thresholds.get("acwr_high_risk", 1.5)
    readiness_low_threshold = thresholds.get("readiness_low", 50)
    readiness_very_low_threshold = thresholds.get("readiness_very_low", 35)
    tsb_overreached_threshold = thresholds.get("tsb_overreached", -25)

    # Check ACWR triggers
    acwr = metrics.get("acwr")
    if acwr is not None:
        if acwr >= acwr_high_risk_threshold and _applies_to_workout(workout_type, TRIGGER_CONFIG[TriggerType.ACWR_HIGH_RISK]):
            config = TRIGGER_CONFIG[TriggerType.ACWR_HIGH_RISK]
            triggered.append(AdaptationTrigger(
                trigger_type=TriggerType.ACWR_HIGH_RISK,
                value=acwr,
                threshold=acwr_high_risk_threshold,
                zone=config["zone"],
                applies_to=config["applies_to"],
                detected_at=workout_date,
            ))
        elif acwr >= acwr_elevated_threshold and _applies_to_workout(workout_type, TRIGGER_CONFIG[TriggerType.ACWR_ELEVATED]):
            config = TRIGGER_CONFIG[TriggerType.ACWR_ELEVATED]
            triggered.append(AdaptationTrigger(
                trigger_type=TriggerType.ACWR_ELEVATED,
                value=acwr,
                threshold=acwr_elevated_threshold,
                zone=config["zone"],
                applies_to=config["applies_to"],
                detected_at=workout_date,
            ))

    # Check readiness triggers
    readiness = metrics.get("readiness")
    if readiness is not None:
        if readiness < readiness_very_low_threshold and _applies_to_workout(workout_type, TRIGGER_CONFIG[TriggerType.READINESS_VERY_LOW]):
            config = TRIGGER_CONFIG[TriggerType.READINESS_VERY_LOW]
            triggered.append(AdaptationTrigger(
                trigger_type=TriggerType.READINESS_VERY_LOW,
                value=readiness,
                threshold=readiness_very_low_threshold,
                zone=config["zone"],
                applies_to=config["applies_to"] if isinstance(config["applies_to"], list) else [],
                detected_at=workout_date,
            ))
        elif readiness < readiness_low_threshold and _applies_to_workout(workout_type, TRIGGER_CONFIG[TriggerType.READINESS_LOW]):
            config = TRIGGER_CONFIG[TriggerType.READINESS_LOW]
            triggered.append(AdaptationTrigger(
                trigger_type=TriggerType.READINESS_LOW,
                value=readiness,
                threshold=readiness_low_threshold,
                zone=config["zone"],
                applies_to=config["applies_to"],
                detected_at=workout_date,
            ))

    # Check TSB (overreached)
    tsb = metrics.get("tsb")
    if tsb is not None and tsb < tsb_overreached_threshold:
        if _applies_to_workout(workout_type, TRIGGER_CONFIG[TriggerType.TSB_OVERREACHED]):
            config = TRIGGER_CONFIG[TriggerType.TSB_OVERREACHED]
            triggered.append(AdaptationTrigger(
                trigger_type=TriggerType.TSB_OVERREACHED,
                value=tsb,
                threshold=tsb_overreached_threshold,
                zone=config["zone"],
                applies_to=config["applies_to"],
                detected_at=workout_date,
            ))

    # TODO: Lower-body load check (requires access to recent activity history)
    # TODO: Session density check (requires access to recent activity history)
    # These will be added when we have access to the activity repository

    return triggered


def _applies_to_workout(workout_type: str, trigger_config: dict) -> bool:
    """Check if trigger applies to this workout type."""
    applies_to = trigger_config.get("applies_to", [])

    if applies_to == "all":
        return True

    return workout_type in applies_to


# ============================================================
# RISK ASSESSMENT (Toolkit Paradigm)
# ============================================================


def assess_override_risk(
    triggers: list[AdaptationTrigger],
    workout: dict,
    athlete_history: Optional[list] = None,
) -> OverrideRiskAssessment:
    """
    Assess risk if athlete ignores triggers (Toolkit Paradigm).

    Calculates quantitative risk index based on:
    1. Number and severity of triggers
    2. Workout type and intensity
    3. Athlete injury history (from M13 memories)
    4. Published training science evidence

    Claude Code presents this to athlete when discussing adaptation options,
    combining quantitative risk with qualitative context (athlete mindset,
    race importance, life stress).

    Args:
        triggers: Detected adaptation triggers
        workout: Workout dict with type, date, RPE, etc.
        athlete_history: Optional M13 memories (for injury history)

    Returns:
        OverrideRiskAssessment with risk level, heuristic risk index, evidence

    Example:
        >>> triggers = [AdaptationTrigger(type="acwr_elevated", value=1.45, ...)]
        >>> risk = assess_override_risk(triggers, workout, athlete_history)
        >>> risk.risk_level
        'moderate'
        >>> risk.risk_index
        0.15  # heuristic risk index (0.0-1.0)
    """
    if not triggers:
        # No triggers = minimal risk
        return OverrideRiskAssessment(
            risk_level=RiskLevel.LOW,
            risk_index=0.05,
            risk_factors=[],
            recommendation="No significant risk factors detected",
            evidence=[],
        )

    # Base risk index (5% baseline for any training)
    base_risk = 0.05

    # Add risk per trigger
    risk_factors = []
    for trigger in triggers:
        if trigger.zone == "danger":
            base_risk += 0.15
            risk_factors.append(f"{trigger.trigger_type.upper()} in danger zone ({trigger.value})")
        elif trigger.zone == "warning":
            base_risk += 0.10
            risk_factors.append(f"{trigger.trigger_type.upper()} in warning zone ({trigger.value})")
        elif trigger.zone == "caution":
            base_risk += 0.05
            risk_factors.append(f"{trigger.trigger_type.upper()} in caution zone ({trigger.value})")

    # Multiply by workout intensity
    workout_rpe = workout.get("target_rpe", 5)
    if workout_rpe >= 9:
        base_risk *= 1.5
        risk_factors.append(f"Very high intensity workout (RPE {workout_rpe})")
    elif workout_rpe >= 8:
        base_risk *= 1.3
        risk_factors.append(f"High intensity workout (RPE {workout_rpe})")
    elif workout_rpe >= 7:
        base_risk *= 1.2

    # Check injury history (simplified - would parse M13 memories in full implementation)
    if athlete_history:
        injury_memories = [m for m in athlete_history if isinstance(m, dict) and "injury" in str(m.get("tags", [])).lower()]
        if injury_memories:
            base_risk *= 1.3
            risk_factors.append("Previous injury history")

    # Cap at 1.0 (100%)
    risk_index = min(base_risk, 1.0)

    # Determine risk level
    if risk_index < 0.10:
        risk_level = RiskLevel.LOW
        recommendation = "Low risk - proceed with caution if feeling good"
    elif risk_index < 0.20:
        risk_level = RiskLevel.MODERATE
        recommendation = "Moderate risk - consider easier workout or moving to different day"
    elif risk_index < 0.40:
        risk_level = RiskLevel.HIGH
        recommendation = "High risk - strongly recommend adaptation (downgrade or rest)"
    else:
        risk_level = RiskLevel.SEVERE
        recommendation = "Severe risk - adaptation highly recommended to prevent injury"

    # Add training science evidence
    evidence = []
    for trigger in triggers:
        if trigger.trigger_type == TriggerType.ACWR_ELEVATED:
            evidence.append("ACWR 1.3-1.5 linked to elevated load spike risk (Gabbett, 2016)")
        elif trigger.trigger_type == TriggerType.ACWR_HIGH_RISK:
            evidence.append("ACWR >1.5 associated with higher load spike risk (Hulin et al., 2016)")
        elif trigger.trigger_type == TriggerType.READINESS_VERY_LOW:
            evidence.append("Very low readiness increases injury susceptibility (Saw et al., 2016)")
        elif trigger.trigger_type == TriggerType.TSB_OVERREACHED:
            evidence.append("TSB <-25 indicates functional overreaching (Busso, 2003)")

    return OverrideRiskAssessment(
        risk_level=risk_level,
        risk_index=risk_index,
        risk_factors=risk_factors,
        recommendation=recommendation,
        evidence=evidence,
    )


def estimate_recovery_time(
    trigger: AdaptationTrigger,
    trigger_value: Optional[float] = None,
) -> RecoveryEstimate:
    """
    Estimate days needed to recover from trigger (Toolkit Paradigm).

    Based on trigger type, severity, and training science research on recovery
    timelines. Claude Code uses this when proposing workout rescheduling.

    Args:
        trigger: Adaptation trigger detected
        trigger_value: Optional trigger value (uses trigger.value if not provided)

    Returns:
        RecoveryEstimate with days, confidence, and factors

    Example:
        >>> trigger = AdaptationTrigger(type="acwr_high_risk", value=1.55, ...)
        >>> recovery = estimate_recovery_time(trigger)
        >>> recovery.days
        3
        >>> recovery.confidence
        'high'
    """
    if trigger_value is None:
        trigger_value = trigger.value

    # Map trigger types to recovery days
    if trigger.trigger_type == TriggerType.ACWR_HIGH_RISK:
        # ACWR >1.5 needs several days of easier training
        days = 3
        confidence = "high"
        factors = [f"ACWR spike to {trigger_value:.2f}", "Need to reduce acute load"]
    elif trigger.trigger_type == TriggerType.ACWR_ELEVATED:
        # ACWR 1.3-1.5 needs 1-2 days easier
        days = 2
        confidence = "medium"
        factors = [f"ACWR at {trigger_value:.2f}", "Moderate load reduction needed"]
    elif trigger.trigger_type == TriggerType.READINESS_VERY_LOW:
        # Very low readiness (<35) needs 1-2 days rest
        days = 2
        confidence = "high"
        factors = [f"Readiness critically low ({trigger_value:.0f})", "Deep fatigue signals"]
    elif trigger.trigger_type == TriggerType.READINESS_LOW:
        # Low readiness (35-50) needs 1 day easier
        days = 1
        confidence = "medium"
        factors = [f"Readiness low ({trigger_value:.0f})", "Fatigue accumulation"]
    elif trigger.trigger_type == TriggerType.TSB_OVERREACHED:
        # TSB <-25 needs 3-5 days recovery
        days = 4
        confidence = "high"
        factors = [f"TSB critically low ({trigger_value:.0f})", "Overreaching detected"]
    elif trigger.trigger_type == TriggerType.LOWER_BODY_LOAD_HIGH:
        # High lower-body load needs 1-2 days before quality
        days = 2
        confidence = "medium"
        factors = ["Elevated lower-body load", "Leg recovery needed"]
    elif trigger.trigger_type == TriggerType.SESSION_DENSITY_HIGH:
        # Too many hard sessions - need 2-3 days easier
        days = 2
        confidence = "medium"
        factors = ["High session density", "Cumulative fatigue from quality work"]
    else:
        # Unknown trigger type - conservative estimate
        days = 2
        confidence = "low"
        factors = ["Unknown trigger type - conservative estimate"]

    return RecoveryEstimate(
        days=days,
        confidence=confidence,
        factors=factors,
    )
