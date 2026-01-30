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

import logging
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
    athlete_profile_path,
    daily_metrics_path,
    current_plan_path,
    plan_archive_dir,
    activity_path,
    weekly_metrics_summary_path,
)
from sports_coach_engine.core.repository import RepositoryIO, ReadOptions
from sports_coach_engine.core.profile import ProfileService
from sports_coach_engine.schemas.repository import RepoError
from sports_coach_engine.core.strava import (
    fetch_activities,
    fetch_activity_details,
    fetch_athlete_profile,
    sync_strava,
    map_strava_to_raw,
    StravaAuthError,
    StravaRateLimitError,
    StravaAPIError,
    DEFAULT_WAIT_BETWEEN_REQUESTS,
)
from sports_coach_engine.core.normalization import normalize_activity
from sports_coach_engine.core.notes import analyze_activity
from sports_coach_engine.core.load import compute_load
from sports_coach_engine.core.metrics import compute_daily_metrics, compute_weekly_summary, _read_activities_for_date
from sports_coach_engine.core.adaptation import (
    detect_adaptation_triggers,
    assess_override_risk,
)
from sports_coach_engine.core.memory import save_memory, Memory, MemoryType, MemorySource
from sports_coach_engine.core.plan import calculate_periodization, suggest_volume_adjustment
from sports_coach_engine.utils.dates import get_next_monday
from sports_coach_engine.schemas.activity import (
    RawActivity,
    NormalizedActivity,
    RPEEstimate,
    RPESource,
)
from sports_coach_engine.schemas.metrics import DailyMetrics
from sports_coach_engine.schemas.profile import AthleteProfile, Goal, GoalType, StravaConnection
# ProfileError import removed to avoid circular dependency - using duck typing instead
from sports_coach_engine.schemas.plan import WeekPlan, MasterPlan, PlanPhase


logger = logging.getLogger(__name__)


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def select_best_rpe_estimate(estimates: list[RPEEstimate]) -> int:
    """
    Select best RPE estimate using confidence-based priority.

    Priority order (evidence-based, sport science):
    1. User input (explicit entry, always trust)
    2. HR-based (objective physiological data, high confidence)
    3. Pace-based (VDOT zones, if available)
    4. Strava relative effort (reasonable algorithm)
    5. Duration heuristic (fallback only, low confidence)

    Within each source, prefer higher confidence estimates.

    Args:
        estimates: List of RPE estimates from different sources

    Returns:
        Single RPE value (1-10) based on best available estimate
    """
    if not estimates:
        return 5  # Conservative fallback

    # Priority by source quality (aligned with sport science)
    for source in [
        RPESource.USER_INPUT,
        RPESource.HR_BASED,
        RPESource.PACE_BASED,
        RPESource.STRAVA_RELATIVE,
        RPESource.DURATION_HEURISTIC,
    ]:
        matching = [e for e in estimates if e.source == source]
        if matching:
            # Within source, prefer higher confidence
            matching.sort(
                key=lambda e: {"high": 3, "medium": 2, "low": 1}.get(e.confidence, 0),
                reverse=True,
            )
            return matching[0].value

    # Should never reach here, but fallback to first estimate
    return estimates[0].value


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
    activities_skipped: int = 0
    activities_failed: int = 0
    metrics_updated: Optional[DailyMetrics] = None
    suggestions_generated: list[Any] = field(default_factory=list)
    memories_extracted: list[Memory] = field(default_factory=list)
    profile_fields_updated: Optional[list[str]] = None  # Fields updated from Strava athlete profile


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
                    logger.warning(
                        "[WorkflowLock] Breaking stale lock from PID %s",
                        lock_data.get("pid"),
                    )
                    self.repo.delete_file(self.lock_file)
                else:
                    # Active lock held by another process
                    if attempt < self.retry_attempts - 1:
                        logger.info(
                            "[WorkflowLock] Lock held by PID %s, waiting %ss... (attempt %s/%s)",
                            lock_data.get("pid"),
                            self.retry_wait_seconds,
                            attempt + 1,
                            self.retry_attempts,
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
                logger.warning("[WorkflowLock] Error releasing lock: %s", e)

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


def _fetch_and_update_athlete_profile(
    config: Config,
    repo: RepositoryIO,
    txn: "TransactionLog"
) -> Optional[list[str]]:
    """
    Fetch athlete profile from Strava and update local profile.

    Best-effort operation - failures don't block activity sync.
    Only updates fields if:
    - Athlete has disclosed them in Strava
    - Local profile doesn't already have them (no overwrites)

    Strava field mappings:
    - athlete.firstname → profile.name (if profile.name is empty)
    - athlete.sex → Not in schema (skip for now)
    - athlete.weight → Not in schema (skip for now)
    - athlete.id → profile.strava.athlete_id

    Args:
        config: Config with Strava credentials
        repo: Repository for file operations
        txn: Transaction log for rollback tracking

    Returns:
        List of field names that were updated, or None if no updates made

    Raises:
        StravaAuthError: Fatal - auth token invalid (propagate to caller)
    """
    try:
        athlete_data = fetch_athlete_profile(config)
        if not athlete_data:
            return None

        # Load current profile
        profile_service = ProfileService(repo)
        profile = profile_service.load_profile()

        # If no profile exists, skip (profile should be created via `sce profile create`)
        # Use duck typing to check for error (has error_type attribute)
        if profile is None or hasattr(profile, 'error_type'):
            return None

        # Track for rollback
        txn.record_modify(athlete_profile_path(), profile)

        # Update only if fields are empty
        updates = {}

        # Name (from firstname, or firstname + lastname)
        if not profile.name and athlete_data.get('firstname'):
            firstname = athlete_data.get('firstname', '')
            lastname = athlete_data.get('lastname', '')
            full_name = f"{firstname} {lastname}".strip() if lastname else firstname
            updates['name'] = full_name

        # Strava athlete ID
        if athlete_data.get('id'):
            if not profile.strava:
                profile.strava = StravaConnection(athlete_id=str(athlete_data['id']))
                updates['strava'] = profile.strava
            elif not profile.strava.athlete_id:
                profile.strava.athlete_id = str(athlete_data['id'])
                updates['strava'] = profile.strava

        # Apply updates if any
        if updates:
            profile_service.update_profile(updates)
            logger.info("[Sync] Updated profile from Strava: %s", ", ".join(updates.keys()))
            return list(updates.keys())

        return None

    except StravaAuthError:
        # Auth errors are fatal - propagate
        raise
    except (StravaAPIError, StravaRateLimitError) as e:
        # Non-fatal - log warning and continue
        logger.warning("[Sync] Could not fetch athlete profile: %s", e)
        return None
    except Exception as e:
        # Unexpected errors - log but don't block sync
        logger.warning("[Sync] Profile update failed: %s", e)
        return None


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
            # Step 0: Fetch and update athlete profile from Strava (best-effort)
            profile_fields_updated = _fetch_and_update_athlete_profile(config, repo, txn)
            if profile_fields_updated:
                result.profile_fields_updated = profile_fields_updated


            # Step 1: Sync activities from Strava (Greedy/Reverse-Chronological)
            # Build existing IDs set for skipping
            existing_strava_ids = {id for id in existing_ids if id.startswith("strava_")}
            
            logger.info("[Sync] Syncing with Strava (since=%s)...", since)
            
            # Delegate to core sync function
            # This handles pagination, rate limits, and detail fetching efficiently
            raw_activities_from_sync, sync_cmd_result = sync_strava(
                config,
                since=since,
                existing_ids=existing_strava_ids
            )
            
            # Merge errors/warnings
            if sync_cmd_result.errors:
                result.warnings.extend(sync_cmd_result.errors)
            
            # Check for rate limit pause
            rate_limit_paused = any("Rate Limit" in str(e) for e in sync_cmd_result.errors)
            if rate_limit_paused:
                 logger.warning("[Sync] Paused due to Strava rate limits")

            if not raw_activities_from_sync:
                if not sync_cmd_result.errors or rate_limit_paused:
                    # Successful (but maybe empty or paused)
                    result.success = True
                    if not rate_limit_paused:
                        result.warnings.append("No new activities found")
                    return result
            
            logger.info(
                "[Sync] Fetched %s new activities",
                len(raw_activities_from_sync),
            )

            # Step 2-8: Process each activity through pipeline
            for raw_activity in raw_activities_from_sync:
                try:
                    # Double-check existence (idempotency)
                    if raw_activity.id in existing_ids:
                        result.activities_skipped += 1
                        continue

                    # M6: Normalize
                    normalized = normalize_activity(raw_activity, repo)

                    # Skip fuzzy duplicates (manual logs or previously imported with different IDs)
                    existing_on_day = existing_by_date.get(normalized.date, [])
                    if _is_fuzzy_duplicate(normalized, existing_on_day):
                        result.activities_skipped += 1
                        continue

                    # M7: Analyze notes & RPE
                    profile_service = ProfileService(repo)
                    profile = profile_service.load_profile()
                    analysis = analyze_activity(normalized, profile)

                    # Resolve RPE (use intelligent selection with confidence-based priority)
                    estimated_rpe = select_best_rpe_estimate(analysis.rpe_estimates)

                    # M8: Compute loads
                    load_result = compute_load(normalized, estimated_rpe, repo)
                    normalized.calculated = load_result

                    # Save normalized activity
                    activity_path = _get_activity_path(normalized)
                    txn.record_create(activity_path)
                    repo.write_yaml(activity_path, normalized)

                    result.activities_imported.append(normalized)
                    existing_ids.add(normalized.id)
                    existing_by_date.setdefault(normalized.date, []).append(normalized)

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
                    activity_id = raw_activity.id if raw_activity else 'unknown'
                    result.warnings.append(
                        f"Failed to process activity {activity_id}: {e}"
                    )
                    continue

            # Step 9: Recompute all metrics (including rest days and weekly summary)
            # This is now delegated to a standalone function for better separation of concerns
            if result.activities_imported:
                try:
                    # Get earliest activity date to start metrics computation
                    earliest = min(act.date for act in result.activities_imported)

                    # Recompute metrics from earliest imported activity to today
                    # This includes activity days, rest days, and weekly summary
                    metrics_result = recompute_all_metrics(
                        repo,
                        start_date=earliest,
                        end_date=date.today()
                    )

                    logger.info(
                        "[Sync] Computed %s days of metrics",
                        metrics_result["metrics_computed"],
                    )
                    metrics_path = daily_metrics_path(date.today())
                    metrics = repo.read_yaml(
                        metrics_path,
                        DailyMetrics,
                        ReadOptions(allow_missing=True, should_validate=True),
                    )
                    if metrics is None or isinstance(metrics, RepoError):
                        result.warnings.append(
                            "Metrics recomputed but latest daily metrics could not be loaded"
                        )
                    else:
                        result.metrics_updated = metrics
                except Exception as e:
                    result.warnings.append(f"Failed to recompute metrics: {e}")

            # Step 10: Update last_sync_at
            training_history_path = athlete_training_history_path()
            if repo.file_exists(training_history_path):
                history = repo.read_yaml(training_history_path, schema=None)
                # If read failed (RepoError), start fresh
                if isinstance(history, RepoError) or history is None:
                    history = {}
            else:
                history = {}

            history["last_strava_sync_at"] = datetime.now(timezone.utc).isoformat()
            if activity_summaries:
                history["last_strava_activity_id"] = activity_summaries[-1]['id']

            repo.write_yaml(training_history_path, history)

            # Success
            result.success = True
            result.partial_failure = result.activities_failed > 0

            logger.info(
                "[Sync] Complete: %s imported, %s failed",
                len(result.activities_imported),
                result.activities_failed,
            )

            return result

        except (StravaAuthError, StravaRateLimitError, StravaAPIError):
            # Don't rollback on Strava errors - preserve state
            raise

        except Exception as e:
            # Fatal error: rollback all changes
            logger.error("[Sync] Fatal error, rolling back: %s", e)
            try:
                txn.rollback()
            except WorkflowRollbackError as rollback_err:
                logger.error("[Sync] Rollback had errors: %s", rollback_err)

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
        logger.info("[MetricsRefresh] Computing metrics for %s...", target_date)

        # Compute metrics (M9)
        metrics = compute_daily_metrics(target_date, repo)

        result.success = True
        result.metrics = metrics
        result.date_refreshed = target_date

        logger.info("[MetricsRefresh] Complete: CTL=%.1f", metrics.ctl_atl.ctl)

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
        logger.info("[PlanGen] Generating training plan...")

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
            logger.info("[PlanGen] Archived old plan to %s", archive_path)

        # Create minimal valid plan skeleton (Claude Code will fill in weeks)
        # Generate unique plan ID
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"

        # Calculate timeline (deterministic based on goal)
        today = date.today()
        if profile.goal and profile.goal.target_date:
            target_date_str = profile.goal.target_date
            target_date = date.fromisoformat(target_date_str) if isinstance(target_date_str, str) else target_date_str
        else:
            # Default to 12 weeks if no goal date
            target_date = today + timedelta(weeks=12)

        # Align start_date to next Monday for proper week structure (Monday=0, Sunday=6)
        # This ensures all weeks follow Monday-Sunday convention and plan starts in the future
        start_date = get_next_monday(today)
        total_weeks = max(1, (target_date - start_date).days // 7)
        end_date = target_date

        # Get current CTL and weekly volume for recommendations (graceful fallback)
        current_ctl = 20.0  # Default for new athletes
        current_weekly_volume = 0.0
        try:
            from sports_coach_engine.api.coach import get_current_metrics
            metrics = get_current_metrics()
            if hasattr(metrics, 'ctl') and metrics.ctl is not None:
                current_ctl = metrics.ctl
        except Exception:
            pass  # No metrics available - will use defaults

        # Get phase structure from toolkit (quantitative data)
        goal_type = profile.goal.type if profile.goal else GoalType.GENERAL_FITNESS
        try:
            phases = calculate_periodization(
                goal=goal_type,
                weeks_available=total_weeks,
                start_date=start_date
            )
        except ValueError as e:
            # Timeline too short for goal - create basic phase structure as fallback
            # Claude Code will need to address this in conversation
            logger.warning("[PlanGen] Warning: %s", e)
            logger.info(
                "[PlanGen] Creating fallback phase structure - Claude Code will refine based on constraints"
            )

            # Create simple phase structure for any timeline
            if total_weeks <= 4:
                # Very short: Just base + taper
                phases = [
                    {
                        "phase": "base",
                        "start_week": 0,
                        "end_week": total_weeks - 2,
                        "start_date": start_date,
                        "end_date": start_date + timedelta(weeks=total_weeks - 1, days=-1),
                        "weeks": total_weeks - 1
                    },
                    {
                        "phase": "taper",
                        "start_week": total_weeks - 1,
                        "end_week": total_weeks - 1,
                        "start_date": start_date + timedelta(weeks=total_weeks - 1),
                        "end_date": end_date,
                        "weeks": 1
                    }
                ]
            else:
                # Split into build + taper phases
                taper_weeks = max(1, round(total_weeks * 0.15))  # ~15% taper
                build_weeks = total_weeks - taper_weeks
                base_weeks = max(1, round(build_weeks * 0.4))
                peak_weeks = build_weeks - base_weeks

                phases = [
                    {
                        "phase": "base",
                        "start_week": 0,
                        "end_week": base_weeks - 1,
                        "start_date": start_date,
                        "end_date": start_date + timedelta(weeks=base_weeks, days=-1),
                        "weeks": base_weeks
                    },
                    {
                        "phase": "build",
                        "start_week": base_weeks,
                        "end_week": base_weeks + peak_weeks - 1,
                        "start_date": start_date + timedelta(weeks=base_weeks),
                        "end_date": start_date + timedelta(weeks=base_weeks + peak_weeks, days=-1),
                        "weeks": peak_weeks
                    },
                    {
                        "phase": "taper",
                        "start_week": build_weeks,
                        "end_week": total_weeks - 1,
                        "start_date": start_date + timedelta(weeks=build_weeks),
                        "end_date": end_date,
                        "weeks": taper_weeks
                    }
                ]

        # Get volume recommendations from toolkit (suggestions, not final values)
        # Map goal type to distance
        goal_distance_map = {
            GoalType.FIVE_K: 5.0,
            GoalType.TEN_K: 10.0,
            GoalType.HALF_MARATHON: 21.1,
            GoalType.MARATHON: 42.2,
            GoalType.GENERAL_FITNESS: 10.0,  # Default moderate distance
        }
        goal_distance = goal_distance_map.get(goal_type, 10.0)

        volume_rec = suggest_volume_adjustment(
            current_weekly_volume_km=current_weekly_volume,
            current_ctl=current_ctl,
            goal_distance_km=goal_distance,
            weeks_available=total_weeks
        )

        # Extract suggested ranges (toolkit returns tuples)
        starting_volume_km = (volume_rec.start_range_km[0] + volume_rec.start_range_km[1]) / 2
        peak_volume_km = (volume_rec.peak_range_km[0] + volume_rec.peak_range_km[1]) / 2

        # Extract conflict policy from profile
        conflict_policy = profile.conflict_policy.value if profile.conflict_policy else "ask_each_time"

        # Assemble minimal valid plan skeleton
        plan_data = {
            # Required identifiers
            "id": plan_id,
            "created_at": today.isoformat(),

            # Goal (from profile)
            "goal": profile.goal.model_dump() if profile.goal else {
                "type": "general_fitness",
                "target_date": None,
                "target_time": None,
            },

            # Timeline (deterministic calculation)
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_weeks": total_weeks,

            # Phase structure (toolkit provides dates/structure)
            "phases": phases,

            # Weekly plans (EMPTY - Claude Code fills in)
            "weeks": [],

            # Volume recommendations (toolkit suggestions as defaults)
            "starting_volume_km": starting_volume_km,
            "peak_volume_km": peak_volume_km,

            # Policy (from profile)
            "conflict_policy": conflict_policy,

            # Constraints summary
            "constraints_applied": [
                f"runs_per_week: {profile.constraints.min_run_days_per_week}-{profile.constraints.max_run_days_per_week}",
                f"available_days: {len(profile.constraints.available_run_days)}",
                f"max_session_minutes: {profile.constraints.max_time_per_session_minutes}",
            ] if profile.constraints else [],
        }

        # Validate and convert to MasterPlan object before saving
        try:
            plan_object = MasterPlan.model_validate(plan_data)
        except Exception as e:
            raise WorkflowError(f"Plan validation failed: {e}") from e

        # Save plan (write_yaml expects Pydantic model)
        write_result = repo.write_yaml(current_plan_path(), plan_object)
        if write_result is not None:
            # write_result is RepoError
            raise WorkflowError(f"Failed to save plan: {write_result}")

        result.success = True
        result.plan = plan_data  # Return dict for API layer

        logger.info(
            "[PlanGen] Complete: Plan created for %s",
            profile.goal.type if profile.goal else "general fitness",
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
        logger.info("[AdaptCheck] Checking adaptations for %s...", target_date)

        # Load metrics (M9) - optional for future dates
        metrics = None
        metrics_path = daily_metrics_path(target_date)
        if repo.file_exists(metrics_path):
            metrics = repo.read_yaml(metrics_path, schema=DailyMetrics)
        else:
            logger.info(
                "[AdaptCheck] No metrics for %s (future date or no activities yet)",
                target_date,
            )

        # Load profile
        profile_service = ProfileService(repo)
        profile = profile_service.load_profile()

        # Load training plan and find workout for target date (M10)
        plan_path = current_plan_path()
        if not repo.file_exists(plan_path):
            result.success = True
            result.warnings.append("No training plan found")
            return result

        plan = repo.read_yaml(plan_path, schema=MasterPlan, options=ReadOptions(should_validate=True))
        if isinstance(plan, RepoError):
            result.success = True
            result.warnings.append(f"Failed to load plan: {plan}")
            return result

        # Find workout for target_date
        workout = None
        for week in plan.weeks:
            for w in week.workouts:
                if w.date == target_date:
                    workout = w
                    break
            if workout:
                break

        if workout is None:
            result.success = True
            result.warnings.append(f"No workout scheduled for {target_date}")
            return result

        # Store workout in result
        result.workout = workout

        # Detect adaptation triggers (M11)
        # Note: This is a placeholder - full M11 integration requires workout context
        triggers = []

        # Only check triggers if metrics exist (not for future dates)
        if metrics:
            # Check ACWR
            if metrics.acwr and metrics.acwr.acwr > 1.5:
                triggers.append(
                    {
                        "type": "acwr_high_risk",
                        "value": metrics.acwr.acwr,
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
                logger.warning("[AdaptCheck] Safety override: Force rest day")

        result.success = True

        if triggers:
            logger.info(
                "[AdaptCheck] Complete: %s triggers detected, %s auto-applied",
                len(triggers),
                len(result.auto_applied_overrides),
            )
        else:
            logger.info("[AdaptCheck] Complete: No adaptations needed")

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
        logger.info(
            "[ManualActivity] Logging %s activity for %s...",
            sport_type,
            activity_date,
        )

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
            # Use intelligent RPE estimate selection (confidence-based priority)
            estimated_rpe = select_best_rpe_estimate(analysis.rpe_estimates)
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

        logger.info(
            "[ManualActivity] Complete: %s logged (%s min, RPE %s)",
            sport_type,
            duration_minutes,
            estimated_rpe,
        )

        return result

    except Exception as e:
        raise WorkflowError(f"Manual activity logging failed: {e}") from e


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _load_existing_activity_index(
    repo: RepositoryIO,
    activities_dir: str,
    since_date: Optional[date],
) -> tuple[set[str], dict[date, list[NormalizedActivity]]]:
    """Build an index of existing activities to prevent duplicate imports."""
    existing_ids: set[str] = set()
    existing_by_date: dict[date, list[NormalizedActivity]] = {}

    pattern = f"{activities_dir}/**/*.yaml"
    for file_path in repo.list_files(pattern):
        file_date = _parse_activity_date_from_filename(Path(file_path).name)
        if since_date and file_date and file_date < since_date:
            continue

        activity = repo.read_yaml(
            file_path,
            NormalizedActivity,
            ReadOptions(allow_missing=True, should_validate=True),
        )
        if activity is None or isinstance(activity, RepoError):
            continue

        existing_ids.add(activity.id)
        existing_by_date.setdefault(activity.date, []).append(activity)

    return existing_ids, existing_by_date


def _parse_activity_date_from_filename(filename: str) -> Optional[date]:
    """Extract YYYY-MM-DD date from activity filename, if present."""
    if len(filename) < 10:
        return None
    try:
        return datetime.strptime(filename[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _is_fuzzy_duplicate(
    new_activity: NormalizedActivity,
    existing_activities: list[NormalizedActivity],
) -> bool:
    """Check if activity matches an existing one by date, sport, time, and duration."""
    for existing in existing_activities:
        if new_activity.sport_type != existing.sport_type:
            continue

        if not new_activity.start_time or not existing.start_time:
            continue

        time_diff = abs(
            (new_activity.start_time - existing.start_time).total_seconds()
        )
        if time_diff > 1800:  # 30 minutes
            continue

        duration_diff = abs(new_activity.duration_seconds - existing.duration_seconds)
        if duration_diff > 300:  # 5 minutes
            continue

        return True

    return False


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


def _get_existing_metrics_dates(repo: RepositoryIO) -> list[date]:
    """
    Get list of all dates that have computed metrics.

    Returns:
        Sorted list of dates with existing metrics files
    """
    metrics_dir = "data/metrics/daily"

    try:
        # List all YAML files in metrics/daily/
        files = repo.list_files(f"{metrics_dir}/*.yaml")

        dates = []
        for file_path in files:
            # Extract date from filename (e.g., "2026-01-14.yaml" → "2026-01-14")
            filename = Path(file_path).stem
            try:
                dates.append(date.fromisoformat(filename))
            except ValueError:
                # Skip invalid filenames
                continue

        return sorted(dates)

    except Exception:
        return []


def _get_earliest_activity_date(repo: RepositoryIO) -> Optional[date]:
    """
    Find earliest activity date from disk.

    Scans all activity files to determine the earliest activity date,
    which is used as the starting point for metrics recomputation.

    Args:
        repo: Repository I/O instance

    Returns:
        Earliest activity date, or None if no activities exist
    """
    try:
        activity_files = repo.list_files("data/activities/**/*.yaml")
        if not activity_files:
            return None

        dates = []
        for file_path in activity_files:
            # Extract date from filename: "2026-01-14_run_0930.yaml" → "2026-01-14"
            filename = Path(file_path).name
            date_str = filename.split('_')[0]
            try:
                dates.append(date.fromisoformat(date_str))
            except ValueError:
                # Skip invalid filenames
                continue

        return min(dates) if dates else None

    except Exception:
        return None


def recompute_all_metrics(
    repo: RepositoryIO,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    """
    Recompute metrics for all dates from start to end.

    Reads activity files from disk, computes daily metrics (including rest days),
    and updates weekly summary. NO external API calls - completely offline.

    This function enables:
    - Fixing metric calculation bugs without re-syncing from Strava
    - Backfilling rest days for historical data
    - Regenerating metrics after manual activity edits

    Args:
        repo: Repository I/O instance
        start_date: Start date (default: earliest activity date)
        end_date: End date (default: today)

    Returns:
        Dict with metrics_computed, rest_days_filled counts

    Raises:
        MetricsCalculationError: If no activities found or computation fails
    """
    from sports_coach_engine.core.metrics import (
        compute_daily_metrics,
        compute_weekly_summary,
        MetricsCalculationError,
    )
    from sports_coach_engine.core.paths import (
        daily_metrics_path,
        weekly_metrics_summary_path,
    )

    # Step 1: Discover date range from existing activities
    if start_date is None:
        start_date = _get_earliest_activity_date(repo)
        if start_date is None:
            raise MetricsCalculationError("No activities found")

    if end_date is None:
        end_date = date.today()

    logger.info("[Metrics] Recomputing from %s to %s", start_date, end_date)

    # Step 2: Compute metrics for ALL dates (activities + rest days)
    metrics_computed = 0
    rest_days_filled = 0

    current_date = start_date
    while current_date <= end_date:
        # Check if rest day by reading activities for this date
        activities = _read_activities_for_date(current_date, repo)
        is_rest_day = len(activities) == 0

        # Compute metrics (compute_daily_metrics persists to disk)
        metrics = compute_daily_metrics(current_date, repo)

        metrics_computed += 1
        if is_rest_day:
            rest_days_filled += 1

        current_date += timedelta(days=1)

    # Step 3: Recompute weekly summary for current week
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    weekly_summary = compute_weekly_summary(week_start, repo)
    repo.write_yaml(weekly_metrics_summary_path(), weekly_summary.model_dump())

    logger.info(
        "[Metrics] Computed %s days (%s rest days)",
        metrics_computed,
        rest_days_filled,
    )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "metrics_computed": metrics_computed,
        "rest_days_filled": rest_days_filled,
    }
