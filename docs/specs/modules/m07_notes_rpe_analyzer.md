# M7 — Notes & RPE Analyzer

## 1. Metadata

| Field        | Value                                     |
| ------------ | ----------------------------------------- |
| Module ID    | M7                                        |
| Name         | Notes & RPE Analyzer                      |
| Code Module  | `core/notes.py`                           |
| Version      | 2.0.0                                     |
| Status       | Draft                                     |
| Dependencies | M3 (Repository I/O), M4 (Athlete Profile) |

## 2. Purpose

Computational toolkit for quantitative RPE estimation from physiological data. Returns multiple RPE estimates from different sources (HR zones, pace, duration, Strava metrics) and detects treadmill/indoor activities using multi-signal scoring. Claude Code uses these estimates with conversation context to determine final RPE.

### 2.1 Scope Boundaries

**In Scope:**

- HR-based RPE estimation (HR zones → RPE lookup)
- Duration-based RPE estimation (sport + duration heuristic)
- Strava relative effort normalization (suffer_score → RPE formula)
- Treadmill/indoor activity detection (multi-signal scoring)
- Pace-based RPE estimation (pace → effort zone → RPE)
- Multiple RPE estimates with reasoning

**Out of Scope:**

- Text-based RPE extraction (Claude Code parses naturally)
- RPE conflict resolution (Claude Code reasons with context)
- Injury/illness detection (Claude Code extracts via conversation)
- Wellness parsing (Claude Code understands naturally)
- Contextual factors extraction (Claude Code notes)
- Computing load values (M8)
- Persisting flags to daily metrics (M9)
- Long-term memory extraction (M13)
- Activity normalization (M6)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage                                                   |
| ------ | ------------------------------------------------------- |
| M3     | Read activity files                                     |
| M4     | Get athlete vital signs (max_hr, lthr) for HR-based RPE |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
```

## 4. Internal Interface

This module is called internally by M1 workflows as part of the sync pipeline.

### 4.1 Type Definitions

```python
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RPESource(str, Enum):
    """Source of RPE estimate"""
    USER_INPUT = "user_input"
    HR_BASED = "hr_based"
    PACE_BASED = "pace_based"
    STRAVA_RELATIVE = "strava_relative"
    DURATION_HEURISTIC = "duration_heuristic"


class RPEEstimate(BaseModel):
    """RPE estimate with source and confidence"""
    value: int  # 1-10
    source: RPESource
    confidence: str  # "high" | "medium" | "low"
    reasoning: str
    source_data: Optional[dict] = None


class TreadmillDetection(BaseModel):
    """Result of treadmill/indoor detection"""
    is_treadmill: bool
    confidence: str  # "high" | "medium" | "low"
    signals: list[str] = Field(default_factory=list)
    signal_count: int


class AnalysisResult(BaseModel):
    """Complete analysis result for an activity"""
    activity_id: str
    rpe_estimates: list[RPEEstimate] = Field(default_factory=list)
    treadmill_detection: TreadmillDetection
    analyzed_at: datetime
    notes_present: bool
```

### 4.2 Function Signatures

```python
def analyze_activity(activity: "NormalizedActivity",
                     athlete_profile: "AthleteProfile") -> AnalysisResult

def estimate_rpe_from_hr(avg_hr: float, max_hr: int,
                         lthr: Optional[int] = None) -> RPEEstimate

def estimate_rpe_from_duration(sport_type: str,
                                duration_minutes: int) -> RPEEstimate

def estimate_rpe_from_strava_relative(suffer_score: float,
                                      duration_minutes: int) -> RPEEstimate

def estimate_rpe_from_pace(avg_pace_per_km: float, athlete_vdot: int,
                           sport_type: str = "run") -> Optional[RPEEstimate]

def detect_treadmill(activity: "NormalizedActivity") -> TreadmillDetection
```

### 4.3 Error Types

```python
class M7AnalysisError(Exception):
    """Base exception for M7 analysis errors"""
    pass

class InsufficientDataError(M7AnalysisError):
    """Cannot estimate RPE - no HR, pace, or Strava data available"""
    pass

class InvalidVitalSignsError(M7AnalysisError):
    """Athlete profile missing required vital signs (max_hr)"""
    pass
```

## 5. Core Algorithms

### 5.1 RPE Estimation Strategy

Returns ALL available estimates. Claude Code uses these with conversation context to determine final RPE.

**Process**:
1. User input (if provided) - Highest confidence
2. HR-based (if HR data available)
3. Pace-based (if running with pace)
4. Strava relative effort (if available)
5. Duration heuristic (always available, fallback)

**Example**:
```
Activity: HR=155, pace=5:30/km, user said "felt easy"

M7 returns:
- RPE 7 (HR-based, Zone 3)
- RPE 5 (pace-based, easy pace)
- RPE 5 (duration heuristic, 45min)

Claude Code reasons:
"HR says 7, pace says 5, user said 'easy'. High HR could be from
 heat/caffeine. Trusting user perception → RPE 5"
```

### 5.2 HR-Based RPE Estimation

Uses 5-zone heart rate model to estimate RPE.

**Zone Mapping**:
- Zone 1 (<60% max): RPE 2
- Zone 2 (60-70%): RPE 4
- Zone 3 (70-80% or <LTHR): RPE 6
- Zone 4 (80-90% or LTHR-90%): RPE 8
- Zone 5 (>90%): RPE 10

**Confidence**:
- High: LTHR available (zones refined)
- Medium: Using default LTHR assumption (85% max)

### 5.3 Duration-Based RPE Estimation

Conservative fallback when physiological data unavailable.

**Duration-Effort Curves**:
- **Running**: <30min → RPE 4, 30-60min → RPE 5, 60-90min → RPE 6, >90min → RPE 7
- **Cycling**: <60min → RPE 4, 60-120min → RPE 5, >120min → RPE 6
- **Climbing**: <60min → RPE 5, 60-120min → RPE 6, >120min → RPE 7
- **Swimming**: <30min → RPE 5, 30-60min → RPE 6, >60min → RPE 7

Confidence: Low (Claude Code should prefer HR/pace/user input)

### 5.4 Strava Relative Effort Normalization

Converts Strava's suffer_score to RPE scale.

**Formula**:
```
effort_rate = suffer_score / duration_minutes

<0.75 → RPE 3
0.75-1.25 → RPE 4
1.25-1.75 → RPE 5
1.75-2.5 → RPE 6
2.5-3.25 → RPE 7
3.25-4.0 → RPE 8
4.0-4.75 → RPE 9
>4.75 → RPE 10
```

Confidence: Medium (more reliable than duration, less than HR)

### 5.5 Pace-Based RPE Estimation

Maps running pace to VDOT training zones.

**Zone Mapping** (using athlete VDOT):
- Slower than easy pace: RPE 3
- Easy pace: RPE 4
- Marathon pace: RPE 6
- Threshold pace: RPE 7
- Interval pace: RPE 8
- Repetition pace: RPE 9

**Trail running**: Add +1 RPE for technical terrain

Confidence: High for road running, medium for trails

### 5.6 Treadmill Detection

Multi-signal scoring for indoor/treadmill detection.

**Signals**:
1. GPS: No GPS data or <10m variance
2. Elevation: Flat profile (<5m gain for >3km)
3. Flags: Strava "indoor" flag
4. Device: Device name contains "treadmill"
5. Name: Activity name contains "treadmill", "indoor", "gym"
6. Location: Starting point matches known gym (optional)

**Scoring**:
- 3+ signals → High confidence treadmill
- 1-2 signals → Low confidence treadmill
- 0 signals → Outdoor (high confidence)

**Why This Matters**: Treadmill running has 10% lower lower-body load (M8 applies 0.90 multiplier)

## 6. Integration Points

### 6.1 Called By

| Caller | Function        | When                                             |
| ------ | --------------- | ------------------------------------------------ |
| M1     | analyze_activity() | During activity sync (after M6 normalization) |

### 6.2 Calls

| Module | Function           | Purpose                              |
| ------ | ------------------ | ------------------------------------ |
| M4     | get_athlete_profile() | Fetch vital signs (max_hr, lthr, vdot) |

### 6.3 Data Flow

```
[M6 - Normalized Activity]
    ↓
[M7.analyze_activity()] → Returns multiple RPE estimates + treadmill detection
    ↓
[M8 - Load Engine] → Calculates systemic/lower-body load
    ↓
[M9 - Metrics] → Updates CTL/ATL/TSB/ACWR
    ↓
[Claude Code] → Decides final RPE using:
    - M7's multiple estimates
    - Conversation context
    - M13 memories
    - Activity notes
    ↓
[api.sync.log_activity()] → Saves with Claude-decided RPE
```

## 7. Testing Requirements

### 7.1 Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|-----------------|
| HR RPE, Zone 2 | avg_hr=130, max_hr=190 | RPE=4, zone="Zone 2" |
| HR RPE, Zone 4 | avg_hr=165, max_hr=190, lthr=170 | RPE=8, zone="Zone 4" |
| Duration, 60min run | sport="run", duration=60 | RPE=5, confidence="low" |
| Strava, moderate | suffer_score=120, duration=60 | RPE=6, rate=2.0 |
| Pace, easy run | pace=6.5, vdot=45 | RPE=4, zone="Easy" |
| Multiple estimates | HR + pace + Strava all available | 3+ RPEEstimate objects |
| Treadmill, 3 signals | no GPS + indoor flag + name="treadmill" | is_treadmill=True, confidence="high" |
| Outdoor, 0 signals | GPS + elevation + outdoor name | is_treadmill=False |

### 7.2 Edge Cases

| Test Case | Input | Expected Behavior |
|-----------|-------|-------------------|
| HR exceeds max | avg_hr=195, max_hr=190 | Cap at 100%, flag profile error |
| Negative duration | duration=-10 | Raise ValueError |
| Missing max_hr | avg_hr=150, max_hr=None | Skip HR estimate, use others |
| VDOT=0 | pace=6.0, vdot=0 | Skip pace estimate |

## 8. Performance Considerations

- **HR-based RPE**: O(1) - Simple arithmetic
- **Duration-based RPE**: O(1) - Lookup table
- **Strava normalization**: O(1) - Division + thresholds
- **Pace-based RPE**: O(1) - VDOT table lookup
- **Treadmill detection**: O(n) where n = GPS points (<1000)

**Total**: ~1-2ms per activity

## 9. VDOT Training Pace Reference

Sample VDOT paces (min/km):

| VDOT | Easy  | Marathon | Threshold | Interval | Repetition |
|------|-------|----------|-----------|----------|------------|
| 35   | 7:30  | 6:45     | 6:15      | 5:30     | 5:00       |
| 40   | 7:00  | 6:15     | 5:45      | 5:00     | 4:30       |
| 45   | 6:30  | 5:45     | 5:15      | 4:30     | 4:00       |
| 50   | 6:00  | 5:15     | 4:45      | 4:00     | 3:30       |
| 55   | 5:30  | 4:45     | 4:15      | 3:30     | 3:00       |
| 60   | 5:00  | 4:15     | 3:45      | 3:00     | 2:30       |

---

**END OF M7 SPEC**
