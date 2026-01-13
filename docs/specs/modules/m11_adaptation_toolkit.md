# M11 — Adaptation Toolkit

## 1. Metadata

| Field        | Value                                                         |
| ------------ | ------------------------------------------------------------- |
| Module ID    | M11                                                           |
| Name         | Adaptation Toolkit                                            |
| Code Module  | `core/adaptation.py`                                          |
| Version      | 2.0.0                                                         |
| Status       | Draft                                                         |
| Dependencies | M3 (Repository I/O), M4 (Profile), M9 (Metrics), M13 (Memory) |

## 2. Purpose

Provides computational tools for adaptation detection and risk assessment. Detects physiological triggers (ACWR, readiness, load spikes) that warrant coaching attention and assesses injury risk. Claude Code uses these tools with athlete context to decide adaptations.

### 2.1 Scope Boundaries

**In Scope:**

- Trigger detection (ACWR, readiness, load patterns, session density)
- Risk assessment (injury probability, severity levels)
- Recovery time estimation (how long to recover from trigger)
- Workout modification helpers (downgrade, shorten, reschedule)
- Threshold management (athlete-specific thresholds in profile)

**Out of Scope:**

- Adaptation suggestions (Claude Code decides with athlete)
- Automatic overrides (Claude Code presents options)
- Rationale generation (Claude Code explains)
- Decision-making (Claude Code reasons with context)
- Metrics calculation (M9)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage                                    |
| ------ | ---------------------------------------- |
| M3     | Read/write adaptation logs               |
| M4     | Get athlete profile with thresholds      |
| M9     | Get current metrics (CTL/ATL/TSB/ACWR)   |
| M13    | Get athlete memories (patterns, history) |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
```

## 4. Internal Interface

### 4.1 Type Definitions

```python
from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    """Types of adaptation triggers"""
    ACWR_ELEVATED = "acwr_elevated"
    ACWR_HIGH_RISK = "acwr_high_risk"
    READINESS_LOW = "readiness_low"
    READINESS_VERY_LOW = "readiness_very_low"
    TSB_OVERREACHED = "tsb_overreached"
    LOWER_BODY_LOAD_HIGH = "lower_body_load_high"
    SESSION_DENSITY_HIGH = "session_density_high"


class RiskLevel(str, Enum):
    """Risk levels for injury"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


class AdaptationTrigger(BaseModel):
    """Detected trigger that warrants coaching attention"""
    trigger_type: TriggerType
    value: float
    threshold: float
    zone: str  # "caution", "warning", "danger"
    applies_to: list[str]  # Workout types affected
    detected_at: date


class OverrideRiskAssessment(BaseModel):
    """Risk assessment if athlete ignores triggers"""
    risk_level: RiskLevel
    injury_probability: float  # 0.0-1.0
    risk_factors: list[str]
    recommendation: str
    evidence: list[str]  # Citations from training science


class RecoveryEstimate(BaseModel):
    """Estimated recovery time needed"""
    days: int
    confidence: str  # "low", "medium", "high"
    factors: list[str]  # What affects recovery


class AdaptationThresholds(BaseModel):
    """Athlete-specific adaptation thresholds"""
    acwr_elevated: float = 1.3
    acwr_high_risk: float = 1.5
    readiness_low: int = 50
    readiness_very_low: int = 35
    tsb_overreached: int = -25
    lower_body_load_threshold: float = 1.5  # Multiple of 14-day median
    session_density_max: int = 2  # Max quality sessions in 7 days
```

### 4.2 Toolkit Functions

```python
# Trigger Detection
def detect_adaptation_triggers(workout: "WorkoutPrescription",
                                metrics: "DailyMetrics",
                                athlete_profile: "AthleteProfile") -> list[AdaptationTrigger]

# Risk Assessment
def assess_override_risk(triggers: list[AdaptationTrigger],
                         workout: "WorkoutPrescription",
                         athlete_history: Optional[list["Memory"]]) -> OverrideRiskAssessment

# Recovery Estimation
def estimate_recovery_time(trigger: AdaptationTrigger,
                           trigger_value: float) -> RecoveryEstimate

# Workout Modification Helpers
def create_downgraded_workout(original: "WorkoutPrescription",
                               target_rpe: int = 4) -> "WorkoutPrescription"

def create_shortened_workout(original: "WorkoutPrescription",
                              duration_minutes: int) -> "WorkoutPrescription"

def estimate_safe_reschedule_date(original_date: date,
                                   recovery_days: int,
                                   plan: "TrainingPlan") -> date
```

### 4.3 Error Types

```python
class M11AdaptationError(Exception):
    """Base exception for M11 adaptation errors"""
    pass

class InvalidThresholdsError(M11AdaptationError):
    """Athlete profile has invalid adaptation thresholds"""
    pass
```

## 5. Core Algorithms

### 5.1 Trigger Detection

Detects physiological signals that warrant coaching attention.

**Triggers Detected**:

1. **ACWR Elevated** (1.3-1.5): Caution zone, monitor closely
2. **ACWR High Risk** (>1.5): High injury risk (2-4x increased)
3. **Readiness Low** (<50): Reduce intensity recommended
4. **Readiness Very Low** (<35): Rest strongly recommended
5. **TSB Overreached** (<-25): Deep fatigue, recovery needed
6. **Lower-Body Load High**: Yesterday's load >1.5x 14-day median before quality/long run
7. **Session Density High**: 2+ quality sessions in last 7 days

**Returns**: List of detected triggers with values, thresholds, and zones

Claude Code interprets triggers with athlete context (M13 memories, conversation history).

### 5.2 Risk Assessment

Assesses injury probability if athlete ignores triggers.

**Factors Considered**:

- Number and severity of triggers
- Workout type and intensity
- Athlete injury history (from M13 memories)
- Recent training pattern
- Published training science evidence

**Risk Levels**:

- **Low** (<10% injury probability): Proceed with caution
- **Moderate** (10-20%): Recommend adjustment
- **High** (20-40%): Strongly recommend rest or downgrade
- **Severe** (>40%): Rest required, high injury risk

**Example**:

```
Triggers: ACWR 1.45, lower-body load high
Workout: Tempo run
History: Knee injury 3 months ago

Risk Assessment:
- risk_level: "moderate"
- injury_probability: 0.15
- recommendation: "Consider easier workout or rest"
- evidence: ["ACWR 1.3-1.5 linked to increased injury (Gabbett, 2016)",
             "Recent knee history increases risk"]
```

Claude Code presents this to athlete with options.

### 5.3 Recovery Time Estimation

Estimates days needed to recover from trigger.

**Estimation Factors**:

- Trigger type and severity
- Athlete fitness level (CTL)
- Historical recovery patterns (M13)

**Examples**:

- ACWR 1.45: 2-3 days easy training
- Readiness 35: 1-2 days rest
- TSB -30: 3-5 days recovery
- Lower-body load spike: 1-2 days before quality

Confidence: High for common triggers, medium for athlete-specific patterns

### 5.4 Workout Modification Helpers

Tools for creating modified workouts (Claude Code decides whether to use).

**Downgrade**: Reduce intensity (tempo → easy)
**Shorten**: Reduce duration (60min → 40min)
**Reschedule**: Find safer day considering recovery and schedule

Claude Code uses these when athlete agrees to adjust workout.

## 6. Integration Points

### 6.1 Called By

| Caller            | Functions                    | When                               |
| ----------------- | ---------------------------- | ---------------------------------- |
| M1 (Workflows)    | detect_adaptation_triggers() | During daily workout retrieval     |
| Claude Code (API) | All toolkit functions        | When assessing workout suitability |

### 6.2 Calls

| Module | Function                          | Purpose                        |
| ------ | --------------------------------- | ------------------------------ |
| M3     | read_yaml(), write_yaml()         | Read adaptation logs           |
| M4     | get_athlete_profile()             | Get thresholds, preferences    |
| M9     | get_current_metrics()             | Get CTL/ATL/TSB/ACWR/readiness |
| M13    | load_memories(), query_memories() | Get injury history, patterns   |

### 6.3 Data Flow

```
[Morning of quality run]
    │
    ▼
[Claude Code checks workout suitability]
    │
    ├─> detect_adaptation_triggers(workout, metrics, profile)
    │   Returns: [ACWR_ELEVATED(1.45), LOWER_BODY_LOAD_HIGH(340 AU)]
    │
    ├─> assess_override_risk(triggers, workout, memories)
    │   Returns: OverrideRiskAssessment(risk="moderate", probability=0.15)
    │
    ├─> load_memories(tags=["injury", "body:knee"])
    │   Returns: [Memory("Knee history: tightness after 18km+")]
    │
    ▼
[Claude Code reasons with full context]
    "ACWR is 1.45 (caution zone). You climbed yesterday,
     which explains elevated lower-body load. Your knee
     history makes me cautious. Options:

     A) Easy run today (safest)
     B) Move tempo to Thursday (gives 2 days recovery)
     C) Proceed with tempo (moderate risk ~15%)

     What sounds best?"
```

## 7. Testing Requirements

### 7.1 Unit Tests

| Test Case               | Input                  | Expected Output                           |
| ----------------------- | ---------------------- | ----------------------------------------- |
| Trigger: ACWR elevated  | ACWR=1.35              | TriggerType.ACWR_ELEVATED, zone="caution" |
| Trigger: ACWR high risk | ACWR=1.6               | TriggerType.ACWR_HIGH_RISK, zone="danger" |
| Trigger: Readiness low  | readiness=45           | TriggerType.READINESS_LOW                 |
| Risk: Single trigger    | ACWR=1.35, no history  | risk="low", probability<0.10              |
| Risk: Multiple triggers | ACWR=1.5, readiness=40 | risk="high", probability>0.20             |
| Recovery: ACWR spike    | ACWR=1.5               | days=2-3, confidence="high"               |
| Downgrade workout       | Tempo run              | Easy run, RPE=4                           |

### 7.2 Integration Tests

| Test Case               | Scenario                                        | Validation                       |
| ----------------------- | ----------------------------------------------- | -------------------------------- |
| Full adaptation flow    | Detect triggers → assess risk → present options | Claude gets structured data      |
| Threshold customization | Elite athlete with higher thresholds            | Uses custom values from profile  |
| Memory integration      | Athlete with injury history                     | Risk assessment includes history |

### 7.3 Edge Cases

| Test Case         | Input                      | Expected Behavior             |
| ----------------- | -------------------------- | ----------------------------- |
| No triggers       | All metrics normal         | Empty trigger list            |
| Extreme ACWR      | ACWR=2.0                   | Severe risk, probability>0.40 |
| Custom thresholds | acwr_high_risk=1.7 (elite) | Uses custom threshold         |

## 8. Performance Considerations

- **Trigger detection**: O(1) - Threshold comparisons
- **Risk assessment**: O(n) where n=triggers - Typically <10ms
- **Recovery estimation**: O(1) - Lookup tables

**Total adaptation assessment**: <50ms

## 9. Adaptation Thresholds Reference

### Standard Thresholds (Recreational Athletes)

| Trigger         | Caution | Warning | Danger |
| --------------- | ------- | ------- | ------ |
| ACWR            | 1.3     | 1.4     | 1.5    |
| Readiness       | 60      | 50      | 35     |
| TSB             | -15     | -20     | -25    |
| Session Density | 2/week  | 3/week  | 4/week |

### Elite Athlete Adjustments

Elite athletes can tolerate higher loads:

- ACWR caution: 1.4 (vs 1.3)
- ACWR danger: 1.6 (vs 1.5)
- TSB overreached: -30 (vs -25)

### Multi-Sport Adjustments

Athletes with primary sport (e.g., climbing) may need:

- Lower lower-body thresholds (legs more fatigued)
- Higher systemic thresholds (better overall fitness)

---

**END OF M11 SPEC**
