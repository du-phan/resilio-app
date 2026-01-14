"""
M1 - Internal Workflows

Orchestrate multi-step operations by chaining modules M2-M13 in correct sequence.

This module provides workflow functions that the API layer calls. Responsibilities:
- Transaction management (atomic multi-file operations with rollback)
- Lock coordination (prevent concurrent modification)
- Module orchestration (chain M2-M13 in correct order)
- Error propagation (three-tier: fatal, partial, validation)

Design Principles:
- Idempotent: Re-running produces same state
- Atomic: All-or-nothing with rollback on failure
- Testable: Clear error types, no side effects beyond stated operations
- Toolkit paradigm: Return structured data, let Claude Code make decisions

This module does NOT:
- Parse user intent (Claude Code handles)
- Format responses (Claude Code handles)
- Make coaching decisions (uses M11 toolkit, Claude Code decides)
"""

import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sports_coach_engine.core.config import load_config, Config
from sports_coach_engine.core.paths import (
    athlete_training_history_path,
    daily_metrics_path,
    current_plan_path,
    plan_archive_dir,
    activity_path,
)
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.core.profile import ProfileService
from sports_coach_engine.core.strava import (
    fetch_activities,
    fetch_activity_details,
    map_strava_to_raw,
    StravaAuthError,
    StravaRateLimitError,
    StravaAPIError,
    DEFAULT_WAIT_BETWEEN_REQUESTS,
)
from sports_coach_engine.core.normalization import normalize_activity
from sports_coach_engine.core.notes import analyze_activity
from sports_coach_engine.core.load import compute_load
from sports_coach_engine.core.metrics import compute_daily_metrics
from sports_coach_engine.core.adaptation import (
    detect_adaptation_triggers,
    assess_override_risk,
)
from sports_coach_engine.core.memory import save_memory, Memory, MemoryType, MemorySource
from sports_coach_engine.schemas.activity import RawActivity, NormalizedActivity
from sports_coach_engine.schemas.metrics import DailyMetrics
from sports_coach_engine.schemas.profile import AthleteProfile, Goal, GoalType
from sports_coach_engine.schemas.plan import WeekPlan, MasterPlan, PlanPhase


# ============================================================
# ERROR TYPES
# ============================================================


class WorkflowError(Exception):
    """Base exception for workflow errors."""

    pass


class WorkflowLockError(WorkflowError):
    """Lock acquisition/release failed."""

    pass


class WorkflowRollbackError(WorkflowError):
    """Rollback operation failed."""

    pass


class WorkflowValidationError(WorkflowError):
    """Input validation failed."""

    pass


# ============================================================
# RESULT TYPES
# ============================================================


@dataclass
class WorkflowResult:
    """Base workflow result with success flag and warnings."""

    success: bool
    warnings: list[str] = field(default_factory=list)
    partial_failure: bool = False


@dataclass
class SyncWorkflowResult(WorkflowResult):
    """Result from run_sync_workflow."""

    activities_imported: list[NormalizedActivity] = field(default_factory=list)
    activities_failed: int = 0
    metrics_updated: Optional[DailyMetrics] = None
    suggestions_generated: list[Any] = field(default_factory=list)
    memories_extracted: list[Memory] = field(default_factory=list)


@dataclass
class MetricsRefreshResult(WorkflowResult):
    """Result from run_metrics_refresh."""

    metrics: Optional[DailyMetrics] = None
    date_refreshed: Optional[date] = None


@dataclass
class PlanGenerationResult(WorkflowResult):
    """Result from run_plan_generation."""

    plan: Optional[Any] = None  # MasterPlan schema
    archived_plan_path: Optional[str] = None


@dataclass
class AdaptationCheckResult(WorkflowResult):
    """Result from run_adaptation_check."""

    workout: Optional[Any] = None  # WorkoutPrescription
    triggers: list[Any] = field(default_factory=list)  # AdaptationTrigger
    risk_assessment: Optional[Any] = None  # OverrideRiskAssessment
    auto_applied_overrides: list[str] = field(default_factory=list)


@dataclass
class ManualActivityResult(WorkflowResult):
    """Result from run_manual_activity_workflow."""

    activity: Optional[NormalizedActivity] = None
    metrics_updated: Optional[DailyMetrics] = None


# ============================================================
# TRANSACTION INFRASTRUCTURE
# ============================================================


@dataclass
class WorkflowLock:
    """
    File-based lock for workflow coordination.

    Prevents concurrent modifications by multiple processes.
    Uses PID-based detection to break stale locks automatically.

    Lock file format: config/.workflow_lock
    {
        "pid": 12345,
        "operation": "sync",
        "acquired_at": "2026-01-15T10:30:00Z"
    }
    """

    operation: str
    repo: RepositoryIO
    lock_file: str = "config/.workflow_lock"
    stale_threshold_seconds: int = 300  # 5 minutes
    retry_attempts: int = 3
    retry_wait_seconds: int = 2

    def __post_init__(self):
        """Initialize lock state."""
        self._acquired = False
        self._lock_data = None

    def __enter__(self):
        """Acquire lock on context entry."""
        if not self.acquire():
            raise WorkflowLockError(
                f"Failed to acquire lock for '{self.operation}' after {self.retry_attempts} attempts"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock on context exit."""
        self.release()

    def acquire(self) -> bool:
        """
        Acquire lock with retry logic.

        Returns:
            True if lock acquired, False if timed out
        """
        for attempt in range(self.retry_attempts):
            # Check if lock file exists
            if self.repo.file_exists(self.lock_file):
                lock_data = self.repo.read_json(self.lock_file)

                # Handle read errors
                if isinstance(lock_data, Exception):
                    # Corrupted lock file, delete it
                    self.repo.delete_file(self.lock_file)
                elif self._is_stale(lock_data):
                    # Break stale lock
                    print(
                        f"[WorkflowLock] Breaking stale lock from PID {lock_data.get('pid')}"
                    )
                    self.repo.delete_file(self.lock_file)
                else:
                    # Active lock held by another process
                    if attempt < self.retry_attempts - 1:
                        print(
                            f"[WorkflowLock] Lock held by PID {lock_data.get('pid')}, "
                            f"waiting {self.retry_wait_seconds}s... (attempt {attempt + 1}/{self.retry_attempts})"
                        )
                        time.sleep(self.retry_wait_seconds)
                        continue
                    else:
                        # Final attempt failed
                        return False

            # Acquire lock
            self._lock_data = {
                "pid": os.getpid(),
                "operation": self.operation,
                "acquired_at": datetime.now(timezone.utc).isoformat(),
            }
            self.repo.write_json(self.lock_file, self._lock_data)
            self._acquired = True
            return True

        return False

    def release(self):
        """Release lock by deleting lock file."""
        if self._acquired and self.repo.file_exists(self.lock_file):
            try:
                # Verify we own the lock
                lock_data = self.repo.read_json(self.lock_file)
                if not isinstance(lock_data, Exception) and lock_data.get("pid") == os.getpid():
                    self.repo.delete_file(self.lock_file)
                    self._acquired = False
            except Exception as e:
                print(f"[WorkflowLock] Warning: Error releasing lock: {e}")

    def _is_stale(self, lock_data: dict) -> bool:
        """
        Check if lock is stale (>5 min old OR PID not running).

        Args:
            lock_data: Lock file data

        Returns:
            True if lock is stale and should be broken
        """
        # Check age
        acquired_at_str = lock_data.get("acquired_at")
        if acquired_at_str:
            try:
                acquired_at = datetime.fromisoformat(acquired_at_str)
                age_seconds = (datetime.now(timezone.utc) - acquired_at).total_seconds()
                if age_seconds > self.stale_threshold_seconds:
                    return True
            except (ValueError, TypeError):
                # Invalid timestamp → consider stale
                return True

        # Check if PID is running
        pid = lock_data.get("pid")
        if pid:
            try:
                # Send signal 0 to check if process exists
                os.kill(pid, 0)
                # Process exists, not stale
                return False
            except (OSError, ProcessLookupError):
                # Process doesn't exist → stale
                return True

        # Missing data → consider stale
        return True


@dataclass
class TransactionLog:
    """
    Track file operations for rollback on failure.

    Records all file creates/modifies during a workflow so they can be
    undone atomically if an error occurs.
    """

    repo: RepositoryIO
    created_files: list[str] = field(default_factory=list)
    modified_files: dict[str, Any] = field(default_factory=dict)  # path -> backup data

    def record_create(self, file_path: str):
        """
        Record a file creation.

        Args:
            file_path: Path to created file
        """
        self.created_files.append(file_path)

    def record_modify(self, file_path: str, backup_data: Any):
        """
        Record a file modification with backup.

        Args:
            file_path: Path to modified file
            backup_data: Original data before modification
        """
        if file_path not in self.modified_files:
            self.modified_files[file_path] = backup_data

    def rollback(self):
        """
        Rollback all tracked changes.

        Deletes created files and restores modified files to backup state.
        """
        errors = []

        # Delete created files
        for file_path in self.created_files:
            try:
                if self.repo.file_exists(file_path):
                    self.repo.delete_file(file_path)
            except Exception as e:
                errors.append(f"Failed to delete {file_path}: {e}")

        # Restore modified files
        for file_path, backup_data in self.modified_files.items():
            try:
                self.repo.write_yaml(file_path, backup_data)
            except Exception as e:
                errors.append(f"Failed to restore {file_path}: {e}")

        if errors:
            raise WorkflowRollbackError(
                f"Rollback completed with errors: {'; '.join(errors)}"
            )


# ============================================================
# WORKFLOW FUNCTIONS
# ============================================================


def run_sync_workflow(
    repo: RepositoryIO,
    config: Config,
    since: Optional[datetime] = None,
) -> SyncWorkflowResult:
    """
    Execute full Strava sync pipeline.

    This workflow orchestrates the complete activity import process:
    1. Fetch activities from Strava (M5)
    2. Normalize sport types and units (M6)
    3. Extract RPE and wellness signals (M7)
    4. Calculate systemic and lower-body loads (M8)
    5. Compute CTL/ATL/TSB/ACWR metrics (M9)
    6. Check for adaptation triggers (M11)
    7. Extract memories from activity notes (M13)

    Transaction Boundary:
    All file writes are atomic. On failure, all changes are rolled back
    and the repository is left in its previous consistent state.

    Args:
        repo: Repository for file operations
        config: Application configuration with Strava credentials
        since: Only fetch activities after this datetime. If None, uses
               last_strava_sync_at from training_history.yaml

    Returns:
        SyncWorkflowResult containing:
        - activities_imported: List of processed activities
        - metrics_updated: Updated metrics snapshot
        - suggestions_generated: Any adaptation suggestions
        - memories_extracted: Insights extracted from notes
        - warnings: Non-fatal errors that occurred

    Raises:
        WorkflowLockError: If lock cannot be acquired
        StravaAuthError: If Strava authentication fails
        StravaRateLimitError: If rate limited (includes retry_after)
    """
    result = SyncWorkflowResult(success=False)

    # Acquire lock
    with WorkflowLock(operation="sync", repo=repo):
        txn = TransactionLog(repo)

        try:
            # Step 1: Fetch activity summaries from Strava (M5)
            print(f"[Sync] Fetching activities from Strava (since={since})...")

            # Convert datetime to Unix timestamp for Strava API
            after_timestamp = None
            if since:
                after_timestamp = int(since.timestamp())

            activity_summaries = fetch_activities(config, after=after_timestamp)

            if not activity_summaries:
                result.success = True
                result.warnings.append("No new activities found")
                return result

            print(f"[Sync] Fetched {len(activity_summaries)} activity summaries")

            # Step 2-8: Process each activity through pipeline
            for activity_summary in activity_summaries:
                raw_activity = None  # Initialize for error handling
                try:
                    # Fetch full activity details (includes description and private_note)
                    print(f"[Sync] Fetching details for activity {activity_summary['id']}...")
                    activity_detail = fetch_activity_details(config, str(activity_summary["id"]))

                    # Rate limiting between API calls
                    time.sleep(DEFAULT_WAIT_BETWEEN_REQUESTS)

                    # Map detailed activity dict to RawActivity
                    raw_activity = map_strava_to_raw(activity_detail)

                    # M6: Normalize
                    normalized = normalize_activity(raw_activity, repo)

                    # M7: Analyze notes & RPE
                    profile_service = ProfileService(repo)
                    profile = profile_service.load_profile()
                    analysis = analyze_activity(normalized, profile)

                    # Resolve RPE (use first estimate for v0)
                    estimated_rpe = (
                        analysis.rpe_estimates[0].value
                        if analysis.rpe_estimates
                        else 5
                    )

                    # M8: Compute loads
                    load_result = compute_load(normalized, estimated_rpe, repo)
                    normalized.calculated = load_result

                    # Save normalized activity
                    activity_path = _get_activity_path(normalized)
                    txn.record_create(activity_path)
                    repo.write_yaml(activity_path, normalized)

                    result.activities_imported.append(normalized)

                    # M13: Extract memories from notes
                    if normalized.description or normalized.private_note:
                        memory_text = (
                            normalized.description or normalized.private_note
                        )
                        # Simple memory extraction (v0: just store interesting notes)
                        if any(
                            keyword in memory_text.lower()
                            for keyword in [
                                "pain",
                                "injury",
                                "prefer",
                                "like",
                                "knee",
                                "ankle",
                            ]
                        ):
                            memory = Memory(
                                id=str(uuid.uuid4()),
                                type=MemoryType.INJURY_HISTORY
                                if any(
                                    kw in memory_text.lower()
                                    for kw in ["pain", "injury", "knee"]
                                )
                                else MemoryType.PREFERENCE,
                                content=memory_text[:200],  # First 200 chars
                                source=MemorySource.ACTIVITY_NOTE,
                                confidence="medium",
                                tags=[],
                                extracted_at=datetime.now(timezone.utc),
                            )
                            saved_memory, _ = save_memory(memory, repo)
                            result.memories_extracted.append(saved_memory)

                except Exception as e:
                    result.activities_failed += 1
                    activity_id = raw_activity.id if raw_activity else raw_activity_dict.get('id', 'unknown')
                    result.warnings.append(
                        f"Failed to process activity {activity_id}: {e}"
                    )
                    continue

            # Step 9: Recompute metrics for affected dates (M9)
            if result.activities_imported:
                unique_dates = set(
                    activity.date for activity in result.activities_imported
                )
                for activity_date in sorted(unique_dates):
                    try:
                        metrics = compute_daily_metrics(activity_date, repo)
                        metrics_path = daily_metrics_path(activity_date)
                        repo.write_yaml(metrics_path, metrics.model_dump())
                        result.metrics_updated = metrics  # Keep latest
                    except Exception as e:
                        result.warnings.append(
                            f"Failed to compute metrics for {activity_date}: {e}"
                        )

            # Step 10: Update last_sync_at
            training_history_path = athlete_training_history_path()
            if repo.file_exists(training_history_path):
                history = repo.read_yaml(training_history_path, schema=None)
            else:
                history = {}

            history["last_strava_sync_at"] = datetime.now(timezone.utc).isoformat()
            if activity_summaries:
                history["last_strava_activity_id"] = activity_summaries[-1]['id']

            repo.write_yaml(training_history_path, history)

            # Success
            result.success = True
            result.partial_failure = result.activities_failed > 0

            print(
                f"[Sync] Complete: {len(result.activities_imported)} imported, "
                f"{result.activities_failed} failed"
            )

            return result

        except (StravaAuthError, StravaRateLimitError, StravaAPIError):
            # Don't rollback on Strava errors - preserve state
            raise

        except Exception as e:
            # Fatal error: rollback all changes
            print(f"[Sync] Fatal error, rolling back: {e}")
            try:
                txn.rollback()
            except WorkflowRollbackError as rollback_err:
                print(f"[Sync] Rollback had errors: {rollback_err}")

            raise WorkflowError(f"Sync workflow failed: {e}") from e


def run_metrics_refresh(
    repo: RepositoryIO,
    target_date: Optional[date] = None,
) -> MetricsRefreshResult:
    """
    Recompute metrics for a specific date.

    Use cases:
    - User manually corrects activity data
    - Recovery from corrupted metrics
    - Backfill after historical Strava sync

    Pipeline: M9 (compute metrics)

    Args:
        repo: Repository for file operations
        target_date: Date to compute metrics for (default: today)

    Returns:
        MetricsRefreshResult with computed metrics

    Raises:
        WorkflowError: If metrics computation fails
    """
    result = MetricsRefreshResult(success=False)

    if target_date is None:
        target_date = date.today()

    try:
        print(f"[MetricsRefresh] Computing metrics for {target_date}...")

        # Compute metrics (M9)
        metrics = compute_daily_metrics(target_date, repo)

        # Save metrics
        metrics_path = daily_metrics_path(target_date)
        repo.write_yaml(metrics_path, metrics.model_dump())

        result.success = True
        result.metrics = metrics
        result.date_refreshed = target_date

        print(f"[MetricsRefresh] Complete: CTL={metrics.ctl_atl.ctl:.1f}")

        return result

    except Exception as e:
        raise WorkflowError(f"Metrics refresh failed for {target_date}: {e}") from e


def run_plan_generation(
    repo: RepositoryIO,
    goal: Optional[Goal] = None,
) -> PlanGenerationResult:
    """
    Generate a new training plan using M10 toolkit functions.

    This workflow uses the toolkit paradigm: M10 provides planning tools
    (periodization, volume curves, workout templates), and this workflow
    assembles them into a basic plan structure. Claude Code will refine
    the plan workout-by-workout based on athlete context.

    Pipeline: M4 (profile) → M9 (current metrics) → M10 (toolkit functions)

    Args:
        repo: Repository for file operations
        goal: Optional new goal (uses profile goal if not provided)

    Returns:
        PlanGenerationResult with generated plan structure

    Raises:
        WorkflowError: If plan generation fails
    """
    result = PlanGenerationResult(success=False)

    try:
        print("[PlanGen] Generating training plan...")

        # Load profile (M4)
        profile_service = ProfileService(repo)
        profile = profile_service.load_profile()

        # Update goal if provided
        if goal:
            profile.goal = goal
            profile_service.save_profile(profile)

        # Archive old plan if exists
        plan_path = current_plan_path()
        if repo.file_exists(plan_path):
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            archive_path = f"{plan_archive_dir()}/plan_{timestamp}.yaml"
            repo.ensure_directory(plan_archive_dir())

            old_plan = repo.read_yaml(plan_path, schema=None)
            repo.write_yaml(archive_path, old_plan)
            result.archived_plan_path = archive_path
            print(f"[PlanGen] Archived old plan to {archive_path}")

        # Create basic plan structure (v0: minimal, Claude Code refines)
        plan_data = {
            "goal": profile.goal.model_dump() if profile.goal else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "weeks": [],
            "constraints": profile.constraints.model_dump()
            if profile.constraints
            else None,
        }

        # Save plan
        repo.write_yaml(current_plan_path(), plan_data)

        result.success = True
        result.plan = plan_data

        print(
            f"[PlanGen] Complete: Plan created for {profile.goal.type if profile.goal else 'general fitness'}"
        )

        return result

    except Exception as e:
        raise WorkflowError(f"Plan generation failed: {e}") from e


def run_adaptation_check(
    repo: RepositoryIO,
    target_date: Optional[date] = None,
    wellness_override: Optional[dict] = None,
) -> AdaptationCheckResult:
    """
    Check if adaptations are needed for a specific workout.

    Uses M11 adaptation toolkit to detect triggers and assess risk.
    Safety-critical conditions (illness, ACWR > 1.5 + low readiness)
    are auto-applied; all others generate suggestions for user decision.

    Pipeline: M9 (metrics) → M11 (detect triggers + assess risk)

    Args:
        repo: Repository for file operations
        target_date: Date to check adaptations for (default: today)
        wellness_override: Manual wellness signals (fatigue, illness)

    Returns:
        AdaptationCheckResult with triggers, risk assessment, and auto-overrides

    Raises:
        WorkflowError: If adaptation check fails
    """
    result = AdaptationCheckResult(success=False)

    if target_date is None:
        target_date = date.today()

    try:
        print(f"[AdaptCheck] Checking adaptations for {target_date}...")

        # Load metrics (M9)
        metrics_path = daily_metrics_path(target_date)
        if not repo.file_exists(metrics_path):
            result.success = True
            result.warnings.append("No metrics found for target date")
            return result

        metrics = repo.read_yaml(metrics_path, schema=DailyMetrics)

        # Load profile
        profile_service = ProfileService(repo)
        profile = profile_service.load_profile()

        # Detect adaptation triggers (M11)
        # Note: This is a placeholder - full M11 integration requires workout context
        triggers = []

        # Check ACWR
        if metrics.acwr and metrics.acwr.value > 1.5:
            triggers.append(
                {
                    "type": "acwr_high_risk",
                    "value": metrics.acwr.value,
                    "threshold": 1.5,
                    "zone": "danger",
                }
            )

        # Check readiness
        if metrics.readiness.score < 35:
            triggers.append(
                {
                    "type": "readiness_very_low",
                    "value": metrics.readiness.score,
                    "threshold": 35,
                    "zone": "danger",
                }
            )

        result.triggers = triggers

        # Auto-apply safety overrides for severe conditions
        if triggers:
            # ACWR > 1.5 + readiness < 35 → force rest
            acwr_high = any(
                t.get("type") == "acwr_high_risk" and t.get("value") > 1.5
                for t in triggers
            )
            readiness_low = any(
                t.get("type") == "readiness_very_low" and t.get("value") < 35
                for t in triggers
            )

            if acwr_high and readiness_low:
                result.auto_applied_overrides.append(
                    "SAFETY OVERRIDE: ACWR > 1.5 + readiness < 35 → rest day mandatory"
                )
                print("[AdaptCheck] Safety override: Force rest day")

        result.success = True

        if triggers:
            print(
                f"[AdaptCheck] Complete: {len(triggers)} triggers detected, "
                f"{len(result.auto_applied_overrides)} auto-applied"
            )
        else:
            print("[AdaptCheck] Complete: No adaptations needed")

        return result

    except Exception as e:
        raise WorkflowError(f"Adaptation check failed: {e}") from e


def run_manual_activity_workflow(
    repo: RepositoryIO,
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
        rpe: Optional RPE value (estimated if not provided)
        notes: Optional activity notes
        activity_date: Date of activity (default: today)
        distance_km: Optional distance in kilometers

    Returns:
        ManualActivityResult with processed activity and updated metrics

    Raises:
        WorkflowError: If activity logging fails
    """
    result = ManualActivityResult(success=False)

    if activity_date is None:
        activity_date = date.today()

    try:
        print(f"[ManualActivity] Logging {sport_type} activity for {activity_date}...")

        # Create RawActivity
        activity_id = f"manual_{uuid.uuid4()}"
        activity_name = notes[:50] if notes else f"Manual {sport_type.title()} - {activity_date}"
        raw_activity = RawActivity(
            id=activity_id,
            source="manual",
            sport_type=sport_type,
            name=activity_name,
            date=activity_date,
            duration_seconds=duration_minutes * 60,
            distance_meters=distance_km * 1000 if distance_km else None,
            description=notes,
            perceived_exertion=rpe,
            has_hr_data=False,
        )

        # M6: Normalize
        normalized = normalize_activity(raw_activity, repo)

        # M7: Analyze (get RPE estimate if not provided)
        profile_service = ProfileService(repo)
        profile = profile_service.load_profile()
        analysis = analyze_activity(normalized, profile)

        if rpe is None:
            # Use first RPE estimate
            estimated_rpe = (
                analysis.rpe_estimates[0].value if analysis.rpe_estimates else 5
            )
        else:
            estimated_rpe = rpe

        # M8: Compute loads
        load_result = compute_load(normalized, estimated_rpe, repo)
        normalized.calculated = load_result

        # Save activity
        activity_path = _get_activity_path(normalized)
        repo.write_yaml(activity_path, normalized)

        # M9: Recompute metrics for activity date
        metrics = compute_daily_metrics(activity_date, repo)
        metrics_path = daily_metrics_path(activity_date)
        repo.write_yaml(metrics_path, metrics)

        result.success = True
        result.activity = normalized
        result.metrics_updated = metrics

        print(
            f"[ManualActivity] Complete: {sport_type} logged "
            f"({duration_minutes}min, RPE {estimated_rpe})"
        )

        return result

    except Exception as e:
        raise WorkflowError(f"Manual activity logging failed: {e}") from e


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _get_activity_path(activity: NormalizedActivity) -> str:
    """
    Get file path for activity storage.

    Format: activities/YYYY-MM/YYYY-MM-DD_<sport>_<HHmm>.yaml

    Args:
        activity: Normalized activity

    Returns:
        Relative file path for activity
    """
    year_month = activity.date.strftime("%Y-%m")
    date_str = activity.date.isoformat()

    # Get time from start_time if available
    if hasattr(activity, "start_time") and activity.start_time:
        time_str = activity.start_time.strftime("%H%M")
    else:
        time_str = "0000"

    sport_str = activity.sport_type.lower().replace("_", "")
    filename = f"{date_str}_{sport_str}_{time_str}.yaml"

    return activity_path(year_month, filename)
