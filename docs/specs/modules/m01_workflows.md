# M1 — Internal Workflows

## 1. Metadata

| Field        | Value                |
| ------------ | -------------------- |
| Module ID    | M1                   |
| Name         | Internal Workflows   |
| Code Module  | `core/workflows.py`  |
| Version      | 2.0.0                |
| Status       | Draft                |
| Dependencies | M2-M14 (all modules) |

### Changelog

- **2.0.0** (2026-01-12): Complete rewrite as internal workflow module. Removed intent parsing (now handled by Claude Code). Module provides workflow orchestration functions called by the API layer. Returns structured data instead of formatted responses.
- **1.0.2** (2026-01-12): Added dynamic context loading from M14 session summaries.
- **1.0.1** (2026-01-12): Converted all dataclass types to BaseModel.
- **1.0.0** (initial): Initial draft with orchestration logic and intent parsing.

## 2. Purpose

Orchestrate multi-step operations by chaining internal modules together in the correct sequence. This module provides **workflow functions** that handle complex operations requiring multiple module calls.

**Architectural Role:** M1 is an **internal module** called by the API layer (`sports_coach_engine/api/`). Claude Code does NOT call M1 directly—it calls API functions which delegate to M1 workflows internally.

### 2.1 What This Module Does

- Chain modules for complex operations (sync → normalize → analyze → compute)
- Coordinate transactional operations (rollback on failure)
- Handle inter-module data flow (output of M5 feeds M6 feeds M7...)
- Return structured workflow results to the API layer

### 2.2 What This Module Does NOT Do

- **Intent parsing**: Claude Code understands user intent naturally
- **Response formatting**: Claude Code formats responses contextually
- **Session management**: The API layer and Claude Code manage conversation context
- **Entity extraction**: Claude Code extracts entities from natural language
- **User interaction**: No direct interaction—called internally by API layer

### 2.3 Scope Boundaries

**In Scope:**

- Workflow orchestration across modules
- Module chaining sequences (sync pipeline, metrics refresh, etc.)
- Error aggregation from multi-step operations
- Workflow result types with full context

**Out of Scope:**

- Intent recognition (Claude Code)
- Response formatting (Claude Code)
- Conversation management (API layer + Claude Code)
- Direct user interaction

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage                          |
| ------ | ------------------------------ |
| M2     | Load configuration and secrets |
| M3     | Repository I/O operations      |
| M4     | Profile service                |
| M5     | Strava sync                    |
| M6     | Activity normalization         |
| M7     | Notes & RPE analysis           |
| M8     | Load calculation               |
| M9     | Metrics computation            |
| M10    | Plan generation                |
| M11    | Adaptation engine              |
| M12    | Data enrichment                |
| M13    | Memory & insights              |
| M14    | Conversation logging           |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
```

## 4. Internal Interface

**Note:** These functions are called by the API layer, not by Claude Code directly.

### 4.1 Type Definitions

```python
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class WorkflowError(BaseModel):
    """Error that occurred during a workflow step."""
    step: str                    # Which step failed (e.g., "strava_fetch", "normalize")
    message: str                 # Human-readable error message
    recoverable: bool = True     # Can the workflow continue?
    details: Optional[dict] = None


class SyncWorkflowResult(BaseModel):
    """Result of the Strava sync workflow."""
    success: bool
    activities_imported: int
    activities_skipped: int      # Duplicates
    activities_failed: int       # Failed to process

    # Processed activities with full context
    processed_activities: list["ProcessedActivity"]

    # Updated metrics after sync
    metrics_before: Optional["DailyMetrics"] = None
    metrics_after: Optional["DailyMetrics"] = None

    # Adaptation suggestions triggered by new data
    suggestions: list["Suggestion"] = Field(default_factory=list)

    # Memories extracted from activity notes
    memories_extracted: list["Memory"] = Field(default_factory=list)

    # Any errors that occurred (workflow may partially succeed)
    errors: list[WorkflowError] = Field(default_factory=list)


class ProcessedActivity(BaseModel):
    """An activity after full processing pipeline."""
    activity: "NormalizedActivity"   # From M6
    analysis: "NotesAnalysis"        # From M7
    loads: "ActivityLoads"           # From M8


class MetricsRefreshResult(BaseModel):
    """Result of metrics recomputation."""
    success: bool
    date: date
    metrics: "DailyMetrics"
    previous_metrics: Optional["DailyMetrics"] = None
    delta: Optional["MetricsDelta"] = None  # Change from previous
    errors: list[WorkflowError] = Field(default_factory=list)


class MetricsDelta(BaseModel):
    """Change in metrics between two computations."""
    ctl_change: float
    atl_change: float
    tsb_change: float
    acwr_change: Optional[float] = None


class PlanGenerationResult(BaseModel):
    """Result of plan generation workflow."""
    success: bool
    plan: Optional["TrainingPlan"] = None
    weeks_generated: int = 0

    # Context used for generation
    profile_snapshot: "AthleteProfile"
    metrics_snapshot: "DailyMetrics"

    errors: list[WorkflowError] = Field(default_factory=list)


class AdaptationCheckResult(BaseModel):
    """Result of checking for needed adaptations."""
    success: bool

    # Suggestions that should be presented to user
    suggestions: list["Suggestion"] = Field(default_factory=list)

    # Automatic adaptations already applied (safety overrides)
    auto_applied: list["AppliedAdaptation"] = Field(default_factory=list)

    # Current readiness context
    readiness: "ReadinessScore"

    errors: list[WorkflowError] = Field(default_factory=list)


class AppliedAdaptation(BaseModel):
    """An adaptation that was automatically applied."""
    reason: str                  # "illness", "high_acwr", etc.
    description: str             # What was changed
    original_workout: Optional["WorkoutPrescription"] = None
    adapted_workout: Optional["WorkoutPrescription"] = None


class ManualActivityResult(BaseModel):
    """Result of logging a manual activity."""
    success: bool
    activity: Optional["NormalizedActivity"] = None
    loads: Optional["ActivityLoads"] = None
    metrics_updated: bool = False
    errors: list[WorkflowError] = Field(default_factory=list)
```

### 4.2 Function Signatures

```python
def run_sync_workflow(
    repo: "RepositoryIO",
    config: "AppConfig",
    since: Optional[datetime] = None,
) -> SyncWorkflowResult:
    """
    Execute full Strava sync pipeline.

    Pipeline: M5 (fetch) → M6 (normalize) → M7 (analyze) → M8 (loads)
              → M9 (metrics) → M11 (adaptations) → M13 (memories)

    Args:
        repo: Repository for file operations
        config: Application configuration with Strava credentials
        since: Only fetch activities after this time (default: last_sync_at)

    Returns:
        SyncWorkflowResult with all processed activities and updated metrics
    """
    ...


def run_metrics_refresh(
    repo: "RepositoryIO",
    target_date: Optional[date] = None,
) -> MetricsRefreshResult:
    """
    Recompute metrics for a specific date.

    Pipeline: M9 (compute) → M11 (check adaptations)

    Args:
        repo: Repository for file operations
        target_date: Date to compute metrics for (default: today)

    Returns:
        MetricsRefreshResult with computed metrics and delta
    """
    ...


def run_plan_generation(
    repo: "RepositoryIO",
    goal: Optional["Goal"] = None,
) -> PlanGenerationResult:
    """
    Generate a new training plan.

    Pipeline: M4 (profile) → M9 (current metrics) → M10 (generate)

    Args:
        repo: Repository for file operations
        goal: Optional new goal (uses profile goal if not provided)

    Returns:
        PlanGenerationResult with generated plan
    """
    ...


def run_adaptation_check(
    repo: "RepositoryIO",
    target_date: Optional[date] = None,
) -> AdaptationCheckResult:
    """
    Check if adaptations are needed for a workout.

    Pipeline: M9 (metrics) → M10 (get workout) → M11 (evaluate)

    Args:
        repo: Repository for file operations
        target_date: Date to check adaptations for (default: today)
    Returns:
        AdaptationCheckResult with suggestions and any auto-applied changes
    """
    ...


def run_manual_activity_workflow(
    repo: "RepositoryIO",
    sport_type: str,
    duration_minutes: int,
    rpe: Optional[int] = None,
    notes: Optional[str] = None,
    activity_date: Optional[date] = None,
    distance_km: Optional[float] = None,
) -> ManualActivityResult:
    """
    Log a manual activity through full processing pipeline.

    Pipeline: (create) → M6 (normalize) → M7 (analyze) → M8 (loads) → M9 (metrics)

    Args:
        repo: Repository for file operations
        sport_type: Type of sport (running, cycling, etc.)
        duration_minutes: Duration in minutes
        rpe: Optional RPE (1-10)
        notes: Optional activity notes
        activity_date: Date of activity (default: today)
        distance_km: Optional distance in kilometers

    Returns:
        ManualActivityResult with processed activity
    """
    ...
```

### 4.3 Error Types

```python
class WorkflowExecutionError(Exception):
    """Critical error that halts workflow execution."""
    def __init__(self, step: str, message: str, cause: Optional[Exception] = None):
        super().__init__(f"Workflow failed at {step}: {message}")
        self.step = step
        self.cause = cause
```

## 5. Core Algorithms

### 5.1 Sync Workflow

```python
from datetime import date, datetime
from typing import Optional

# Internal module imports
from sports_coach_engine.core.config import AppConfig
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.core.strava import fetch_activities, StravaActivity
from sports_coach_engine.core.normalization import normalize_activity
from sports_coach_engine.core.notes import analyze_activity_notes
from sports_coach_engine.core.load import calculate_loads
from sports_coach_engine.core.metrics import compute_daily_metrics, get_latest_metrics
from sports_coach_engine.core.adaptation import evaluate_adaptations
from sports_coach_engine.core.memory import extract_memories_from_activity


def run_sync_workflow(
    repo: RepositoryIO,
    config: AppConfig,
    since: Optional[datetime] = None,
) -> SyncWorkflowResult:
    """Execute full Strava sync pipeline."""

    errors: list[WorkflowError] = []
    processed_activities: list[ProcessedActivity] = []
    memories_extracted: list[Memory] = []

    # Capture metrics before sync for comparison
    metrics_before = get_latest_metrics(repo)

    # Step 1: Fetch from Strava (M5)
    try:
        fetch_result = fetch_activities(
            access_token=config.strava_access_token,
            refresh_token=config.strava_refresh_token,
            since=since or _get_last_sync_time(repo),
            repo=repo,
        )
    except Exception as e:
        return SyncWorkflowResult(
            success=False,
            activities_imported=0,
            activities_skipped=0,
            activities_failed=0,
            processed_activities=[],
            errors=[WorkflowError(
                step="strava_fetch",
                message=str(e),
                recoverable=False,
            )],
        )

    activities_skipped = 0
    activities_failed = 0

    # Step 2-4: Process each activity through pipeline
    for raw_activity in fetch_result.activities:

        # Check for duplicates
        if _activity_exists(raw_activity.strava_id, repo):
            activities_skipped += 1
            continue

        try:
            # M6: Normalize
            normalized = normalize_activity(raw_activity)

            # M7: Analyze notes and estimate RPE
            analysis = analyze_activity_notes(normalized, repo)
            if analysis.rpe_estimate:
                normalized = normalized.with_rpe(analysis.rpe_estimate.value)

            # M8: Calculate loads
            loads = calculate_loads(normalized)

            # Save activity
            _save_activity(normalized, loads, repo)

            # M13: Extract memories if relevant signals found
            if analysis.injury_flags or analysis.illness_flags:
                memories = extract_memories_from_activity(normalized, analysis, repo)
                memories_extracted.extend(memories)

            processed_activities.append(ProcessedActivity(
                activity=normalized,
                analysis=analysis,
                loads=loads,
            ))

        except Exception as e:
            activities_failed += 1
            errors.append(WorkflowError(
                step="activity_processing",
                message=f"Failed to process activity {raw_activity.strava_id}: {e}",
                recoverable=True,
                details={"strava_id": raw_activity.strava_id},
            ))

    # Step 5: Recompute metrics (M9)
    try:
        metrics_after = compute_daily_metrics(date.today(), repo)
    except Exception as e:
        errors.append(WorkflowError(
            step="metrics_compute",
            message=str(e),
            recoverable=True,
        ))
        metrics_after = metrics_before

    # Step 6: Check for adaptations (M11)
    suggestions: list[Suggestion] = []
    try:
        suggestions = evaluate_adaptations(repo)
    except Exception as e:
        errors.append(WorkflowError(
            step="adaptation_check",
            message=str(e),
            recoverable=True,
        ))

    # Update last sync timestamp
    _update_last_sync_time(repo)

    return SyncWorkflowResult(
        success=len(processed_activities) > 0 or activities_skipped > 0,
        activities_imported=len(processed_activities),
        activities_skipped=activities_skipped,
        activities_failed=activities_failed,
        processed_activities=processed_activities,
        metrics_before=metrics_before,
        metrics_after=metrics_after,
        suggestions=suggestions,
        memories_extracted=memories_extracted,
        errors=errors,
    )
```

### 5.2 Metrics Refresh Workflow

```python
def run_metrics_refresh(
    repo: RepositoryIO,
    target_date: Optional[date] = None,
) -> MetricsRefreshResult:
    """Recompute metrics for a specific date."""

    target = target_date or date.today()
    errors: list[WorkflowError] = []

    # Get previous metrics for comparison
    previous_metrics = get_latest_metrics(repo)

    # M9: Compute metrics
    try:
        metrics = compute_daily_metrics(target, repo)
    except Exception as e:
        return MetricsRefreshResult(
            success=False,
            date=target,
            metrics=previous_metrics,  # Return old metrics on failure
            errors=[WorkflowError(
                step="metrics_compute",
                message=str(e),
                recoverable=False,
            )],
        )

    # Calculate delta if we have previous metrics
    delta = None
    if previous_metrics:
        delta = MetricsDelta(
            ctl_change=metrics.ctl - previous_metrics.ctl,
            atl_change=metrics.atl - previous_metrics.atl,
            tsb_change=metrics.tsb - previous_metrics.tsb,
            acwr_change=(metrics.acwr - previous_metrics.acwr) if metrics.acwr and previous_metrics.acwr else None,
        )

    return MetricsRefreshResult(
        success=True,
        date=target,
        metrics=metrics,
        previous_metrics=previous_metrics,
        delta=delta,
        errors=errors,
    )
```

### 5.3 Plan Generation Workflow

```python
def run_plan_generation(
    repo: RepositoryIO,
    goal: Optional[Goal] = None,
) -> PlanGenerationResult:
    """Generate a new training plan."""

    errors: list[WorkflowError] = []

    # M4: Get current profile
    try:
        profile = get_profile(repo)
    except Exception as e:
        return PlanGenerationResult(
            success=False,
            errors=[WorkflowError(
                step="profile_load",
                message=str(e),
                recoverable=False,
            )],
        )

    # Update goal if provided
    if goal:
        profile = profile.with_goal(goal)
        save_profile(profile, repo)

    # M9: Get current metrics for plan context
    try:
        metrics = compute_daily_metrics(date.today(), repo)
    except Exception as e:
        errors.append(WorkflowError(
            step="metrics_compute",
            message=str(e),
            recoverable=True,
        ))
        metrics = DailyMetrics.default()  # Use conservative defaults

    # M10: Generate plan
    try:
        plan = generate_plan(profile, metrics, repo)
    except Exception as e:
        return PlanGenerationResult(
            success=False,
            profile_snapshot=profile,
            metrics_snapshot=metrics,
            errors=errors + [WorkflowError(
                step="plan_generate",
                message=str(e),
                recoverable=False,
            )],
        )

    return PlanGenerationResult(
        success=True,
        plan=plan,
        weeks_generated=len(plan.weeks),
        profile_snapshot=profile,
        metrics_snapshot=metrics,
        errors=errors,
    )
```

### 5.4 Adaptation Check Workflow

```python
def run_adaptation_check(
    repo: RepositoryIO,
    target_date: Optional[date] = None,
) -> AdaptationCheckResult:
    """Check if adaptations are needed for a workout."""

    target = target_date or date.today()
    errors: list[WorkflowError] = []
    auto_applied: list[AppliedAdaptation] = []

    # M9: Get current metrics and readiness
    try:
        metrics = compute_daily_metrics(target, repo)
        readiness = compute_readiness_score(metrics, repo)
    except Exception as e:
        return AdaptationCheckResult(
            success=False,
            readiness=ReadinessScore.default(),
            errors=[WorkflowError(
                step="metrics_compute",
                message=str(e),
                recoverable=False,
            )],
        )

    # Check for safety overrides (very low readiness + high ACWR)
    if metrics.acwr and metrics.acwr > 1.5:
        # High load spike - automatic reduction
        override_result = apply_safety_override('high_acwr', repo)
        auto_applied.append(AppliedAdaptation(
            reason="high_acwr",
            description=override_result.description,
            original_workout=override_result.original,
            adapted_workout=override_result.adapted,
        ))

    # M11: Evaluate non-critical adaptations (user-choice suggestions)
    try:
        suggestions = evaluate_adaptations(
            repo,
            target_date=target,
        )
    except Exception as e:
        errors.append(WorkflowError(
            step="adaptation_evaluate",
            message=str(e),
            recoverable=True,
        ))
        suggestions = []

    return AdaptationCheckResult(
        success=True,
        suggestions=suggestions,
        auto_applied=auto_applied,
        readiness=readiness,
        errors=errors,
    )
```

### 5.5 Manual Activity Workflow

```python
def run_manual_activity_workflow(
    repo: RepositoryIO,
    sport_type: str,
    duration_minutes: int,
    rpe: Optional[int] = None,
    notes: Optional[str] = None,
    activity_date: Optional[date] = None,
    distance_km: Optional[float] = None,
) -> ManualActivityResult:
    """Log a manual activity through full processing pipeline."""

    target = activity_date or date.today()
    errors: list[WorkflowError] = []

    # Create raw activity
    raw_activity = RawActivity(
        source="manual",
        sport_type=sport_type,
        start_time=datetime.combine(target, datetime.min.time()),
        duration_seconds=duration_minutes * 60,
        distance_meters=int(distance_km * 1000) if distance_km else None,
        notes=notes,
    )

    # M6: Normalize
    try:
        normalized = normalize_activity(raw_activity)
    except Exception as e:
        return ManualActivityResult(
            success=False,
            errors=[WorkflowError(
                step="normalize",
                message=str(e),
                recoverable=False,
            )],
        )

    # Apply RPE if provided, otherwise estimate from M7
    if rpe:
        normalized = normalized.with_rpe(rpe)
    elif notes:
        try:
            analysis = analyze_activity_notes(normalized, repo)
            if analysis.rpe_estimate:
                normalized = normalized.with_rpe(analysis.rpe_estimate.value)
        except Exception as e:
            errors.append(WorkflowError(
                step="notes_analyze",
                message=str(e),
                recoverable=True,
            ))

    # M8: Calculate loads
    try:
        loads = calculate_loads(normalized)
    except Exception as e:
        return ManualActivityResult(
            success=False,
            activity=normalized,
            errors=errors + [WorkflowError(
                step="load_calculate",
                message=str(e),
                recoverable=False,
            )],
        )

    # Save activity
    _save_activity(normalized, loads, repo)

    # M9: Update metrics
    metrics_updated = False
    try:
        compute_daily_metrics(target, repo)
        metrics_updated = True
    except Exception as e:
        errors.append(WorkflowError(
            step="metrics_update",
            message=str(e),
            recoverable=True,
        ))

    return ManualActivityResult(
        success=True,
        activity=normalized,
        loads=loads,
        metrics_updated=metrics_updated,
        errors=errors,
    )
```

## 6. Integration with API Layer

This module is called internally by the API layer functions. Claude Code should call API functions, not M1 workflows directly.

### 6.1 API to Workflow Mapping

| API Function (public)               | Workflow Function (internal)     |
| ----------------------------------- | -------------------------------- |
| `api.sync.sync_strava()`            | `run_sync_workflow()`            |
| `api.metrics.get_current_metrics()` | `run_metrics_refresh()`          |
| `api.plan.regenerate_plan()`        | `run_plan_generation()`          |
| `api.coach.get_todays_workout()`    | `run_adaptation_check()`         |
| `api.sync.log_activity()`           | `run_manual_activity_workflow()` |

### 6.2 Data Flow Example

```
Claude Code calls:  api.sync_strava()
                         │
                         ▼
API Layer:          sync.py::sync_strava()
                         │
                         ▼ calls internally
Workflows (M1):     run_sync_workflow()
                         │
                         ├─► M5: fetch_activities()
                         ├─► M6: normalize_activity()  (for each)
                         ├─► M7: analyze_activity_notes()
                         ├─► M8: calculate_loads()
                         ├─► M9: compute_daily_metrics()
                         ├─► M11: evaluate_adaptations()
                         └─► M13: extract_memories()
                         │
                         ▼ returns
API Layer:          SyncWorkflowResult
                         │
                         ▼ enriches with M12
API Layer:          EnrichedSyncResult (returned to Claude Code)
```

### 6.3 Example API Layer Usage

```python
# In api/sync.py
from sports_coach_engine.core.workflows import run_sync_workflow
from sports_coach_engine.core.enrichment import enrich_sync_result


def sync_strava(
    since: Optional[datetime] = None,
) -> SyncResult | SyncError:
    """
    Public API function called by Claude Code.
    Delegates to M1 workflow, then enriches result with M12.
    """
    repo = get_repository()
    config = get_config()

    # Call M1 workflow
    workflow_result = run_sync_workflow(repo, config, since)

    if not workflow_result.success and not workflow_result.processed_activities:
        return SyncError(
            message="Sync failed",
            errors=workflow_result.errors,
        )

    # M12: Enrich with interpretations
    enriched = enrich_sync_result(workflow_result)

    return enriched
```

## 7. Helper Functions

```python
def _get_last_sync_time(repo: RepositoryIO) -> datetime:
    """Get the last Strava sync timestamp."""
    sync_meta = repo.read_yaml("config/sync_metadata.yaml")
    if sync_meta and sync_meta.get("last_sync_at"):
        return datetime.fromisoformat(sync_meta["last_sync_at"])
    # Default: 30 days ago
    return datetime.now() - timedelta(days=30)


def _update_last_sync_time(repo: RepositoryIO) -> None:
    """Update the last sync timestamp."""
    repo.write_yaml("config/sync_metadata.yaml", {
        "last_sync_at": datetime.now().isoformat(),
    })


def _activity_exists(strava_id: str, repo: RepositoryIO) -> bool:
    """Check if an activity with this Strava ID already exists."""
    existing = repo.list_files("activities", pattern=f"*_{strava_id}.yaml")
    return len(existing) > 0


def _save_activity(
    activity: NormalizedActivity,
    loads: ActivityLoads,
    repo: RepositoryIO,
) -> str:
    """Save an activity to the repository."""
    # Organize by month
    month_dir = activity.start_time.strftime("%Y-%m")
    filename = f"{activity.start_time.strftime('%Y-%m-%d')}_{activity.id}.yaml"
    path = f"activities/{month_dir}/{filename}"

    repo.write_yaml(path, {
        **activity.model_dump(),
        "loads": loads.model_dump(),
    })

    return path
```

## 8. Test Scenarios

### 8.1 Unit Tests

```python
def test_sync_workflow_handles_empty_response():
    """Sync workflow handles no new activities gracefully."""
    repo = MockRepositoryIO()
    config = MockConfig()

    with mock_strava_api(activities=[]):
        result = run_sync_workflow(repo, config)

    assert result.success  # No activities is still success
    assert result.activities_imported == 0
    assert len(result.errors) == 0


def test_sync_workflow_skips_duplicates():
    """Sync workflow skips already-imported activities."""
    repo = MockRepositoryIO()
    config = MockConfig()

    # Pre-populate with existing activity
    repo.write_yaml("activities/2026-01/2026-01-01_123.yaml", {})

    with mock_strava_api(activities=[MockActivity(strava_id="123")]):
        result = run_sync_workflow(repo, config)

    assert result.activities_imported == 0
    assert result.activities_skipped == 1


def test_sync_workflow_continues_on_activity_error():
    """Workflow continues processing if one activity fails."""
    repo = MockRepositoryIO()
    config = MockConfig()

    activities = [
        MockActivity(strava_id="1"),  # Will succeed
        MockActivity(strava_id="2", invalid=True),  # Will fail
        MockActivity(strava_id="3"),  # Will succeed
    ]

    with mock_strava_api(activities=activities):
        result = run_sync_workflow(repo, config)

    assert result.activities_imported == 2
    assert result.activities_failed == 1
    assert len(result.errors) == 1
    assert result.errors[0].recoverable


def test_metrics_refresh_calculates_delta():
    """Metrics refresh includes delta from previous."""
    repo = MockRepositoryIO()

    # Set up previous metrics
    repo.write_yaml("metrics/daily/2026-01-11.yaml", {
        "ctl": 40.0, "atl": 35.0, "tsb": 5.0, "acwr": 1.1
    })

    result = run_metrics_refresh(repo, date(2026, 1, 12))

    assert result.success
    assert result.delta is not None
    assert result.previous_metrics is not None


def test_adaptation_check_auto_applies_safety():
    """Critical conditions trigger automatic safety overrides."""
    repo = MockRepositoryIO()

    # Assume metrics already indicate ACWR > 1.5 and very low readiness
    result = run_adaptation_check(repo)

    assert result.success
    assert len(result.auto_applied) == 1
    assert result.auto_applied[0].reason == "high_acwr"
    assert len(result.suggestions) == 0  # No suggestions when safety applied
```

### 8.2 Integration Tests

```python
@pytest.mark.integration
def test_full_sync_pipeline():
    """Complete sync pipeline processes activities correctly."""
    repo = create_test_repository()
    config = create_test_config()

    with mock_strava_api(activities=create_test_activities(5)):
        result = run_sync_workflow(repo, config)

    assert result.success
    assert result.activities_imported == 5
    assert result.metrics_after is not None
    assert result.metrics_after.ctl > 0

    # Verify activities were saved
    saved_files = repo.list_files("activities", pattern="*.yaml")
    assert len(saved_files) == 5


@pytest.mark.integration
def test_manual_activity_updates_metrics():
    """Manual activity logging updates metrics."""
    repo = create_test_repository()

    result = run_manual_activity_workflow(
        repo,
        sport_type="running",
        duration_minutes=45,
        rpe=6,
        notes="Easy morning run",
    )

    assert result.success
    assert result.metrics_updated
    assert result.activity.sport_type == "running"
    assert result.loads.systemic_load_au > 0
```

## 9. Configuration

### 9.1 Workflow Settings

```python
WORKFLOW_CONFIG = {
    "sync_default_lookback_days": 30,     # How far back to sync on first run
    "max_activities_per_sync": 100,       # Limit per sync batch
    "safety_acwr_threshold": 1.5,         # Auto-apply safety above this
    "safety_readiness_threshold": 35,     # Auto-apply safety below this
}
```

## 10. Design Principles

### 10.1 Partial Success

Workflows support partial success. If one activity fails to process during sync, the workflow continues with the rest. Errors are collected and returned alongside successful results.

### 10.2 Idempotency

All workflows are designed to be idempotent:

- Sync skips already-imported activities
- Metrics refresh overwrites rather than appending
- Plan generation replaces the current plan

### 10.3 Transactional Boundaries

Each workflow function is a transactional unit. If a critical step fails, the workflow returns an error result. Partial state is only committed for non-critical failures.

### 10.4 Separation from API Layer

This module focuses purely on orchestration logic. It:

- Does NOT format responses for users (API layer + Claude Code do this)
- Does NOT parse user intent (Claude Code does this)
- Does NOT manage conversation state (API layer does this)
- ONLY chains modules and returns structured results
