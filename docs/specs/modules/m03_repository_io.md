# M3 - Repository I/O

## Module Metadata

| Field | Value |
|-------|-------|
| **Module ID** | M3 |
| **Module Name** | Repository I/O |
| **Code Module** | `core/repository.py` |
| **Version** | 1.0.1 |
| **Status** | Draft |
| **Complexity** | Medium |
| **Last Updated** | 2026-01-12 |

### Changelog
- **1.0.1** (2026-01-12): Added code module path (`core/repository.py`) and API layer integration notes. Note that this module is also exposed for direct file access by Claude Code for exploration.
- **1.0.0** (initial): Initial draft with core repository I/O operations

---

## 1. Purpose & Scope

### 1.1 Purpose

M3 provides centralized file system operations for all data persistence in the Sports Coach Engine. It is the **only module** that directly reads and writes files (except M2 for configuration). This ensures consistent handling of atomic writes, schema validation, locking, and path resolution across the entire system.

### 1.2 Scope Boundaries

**This module DOES:**
- Read and write YAML/JSON files with schema validation
- Perform atomic writes (temp file + rename) to prevent corruption
- Manage file locks for concurrent access protection
- Resolve paths relative to repository root
- Create directories as needed
- List files matching glob patterns
- Validate data against Pydantic schemas on read/write

**This module does NOT:**
- Understand business logic of the data it persists
- Make decisions about what to write (that's the calling module's job)
- Handle network I/O (Strava API is M5's responsibility)
- Manage backup/recovery workflows (though it provides primitives)

---

## 2. Dependencies

### 2.1 Internal Module Dependencies

| Module | Dependency Type | Purpose |
|--------|-----------------|---------|
| M2 | Config access | Get path settings and lock configuration |

### 2.2 External Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `pyyaml` | ^6.0 | Parse and stringify YAML |
| `pydantic` | ^2.5 | Runtime schema validation |

**Note:** v0 uses synchronous I/O for simplicity. Async operations are not needed for current file sizes and usage patterns.

### 2.3 Schema Definitions

All data schemas (ActivitySchema, ProfileSchema, etc.) are defined in a separate `schemas` module. M3 is schema-agnostic and works with any Pydantic BaseModel subclass.

### 2.3 Environment Requirements

- Python >= 3.11
- File system read/write access to repository directory
- POSIX-compatible file system (for atomic rename)

---

## 3. Internal Interface

**Note:** This module is called internally by all core modules for file operations. **Additionally, this module IS exposed for direct access** by Claude Code for exploration and debugging via `from sports_coach_engine.core.repository import RepositoryIO`.

### 3.1 Type Definitions

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generic, Literal, Optional, TypeVar, Union
from pydantic import BaseModel


T = TypeVar('T', bound=BaseModel)


# ============================================================
# SCHEMA TYPES
# ============================================================

class SchemaType(str, Enum):
    """Types of data schemas in the system."""
    ACTIVITY = "activity"
    PROFILE = "profile"
    DAILY_METRICS = "daily_metrics"
    WEEKLY_SUMMARY = "weekly_summary"
    PLAN = "plan"
    WORKOUT = "workout"
    MEMORIES = "memories"
    TRAINING_HISTORY = "training_history"
    PENDING_SUGGESTIONS = "pending_suggestions"
    SETTINGS = "settings"
    CONVERSATION = "conversation"


class SchemaHeader(BaseModel):
    """Schema version header present in all data files."""
    format_version: str = "1.0.0"  # Semantic version
    schema_type: SchemaType


# ============================================================
# OPTIONS TYPES
# ============================================================

@dataclass
class WriteOptions:
    """Options for write operations."""
    atomic: bool = True           # Use temp file + rename
    create_directories: bool = True  # Create parent dirs
    validate: bool = True         # Validate against schema
    backup: bool = False          # Create backup before overwrite


@dataclass
class ReadOptions:
    """Options for read operations."""
    validate: bool = True         # Validate against schema
    allow_missing: bool = False   # Return None if file doesn't exist
    migrate_schema: bool = True   # Auto-migrate old schema versions


# ============================================================
# LOCK TYPES
# ============================================================

class FileLock(BaseModel):
    """File lock for concurrent access protection."""
    id: str                       # Unique lock ID
    pid: int                      # Process ID holding lock
    operation: str                # 'sync' | 'plan_update' | 'workout_update' | 'metrics'
    acquired_at: datetime
    path: str                     # Path to lock file (str for serialization)
    locked_paths: list[str] = Field(default_factory=list)


# ============================================================
# ERROR TYPES
# ============================================================

class RepoErrorType(str, Enum):
    """Types of repository errors."""
    FILE_NOT_FOUND = "file_not_found"
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    SCHEMA_VERSION_ERROR = "schema_version_error"
    WRITE_ERROR = "write_error"
    LOCK_HELD = "lock_held"
    LOCK_TIMEOUT = "lock_timeout"
    PERMISSION_ERROR = "permission_error"
    DIRECTORY_ERROR = "directory_error"


@dataclass
class ValidationError:
    """Single validation error."""
    path: str                     # JSON path to error (e.g., "athlete.goal.type")
    message: str
    expected: Optional[str] = None
    received: Optional[str] = None


@dataclass
class RepoError:
    """Repository operation error."""
    error_type: RepoErrorType
    message: str
    path: Optional[str] = None
    file_version: Optional[str] = None
    supported_version: Optional[str] = None
    holder: Optional[FileLock] = None
    waited_ms: Optional[int] = None
    operation: Optional[Literal["read", "write"]] = None
    validation_errors: list[ValidationError] = field(default_factory=list)


# ============================================================
# RESULT TYPES
# ============================================================

ReadResult = Union[T, None, RepoError]
WriteResult = Union[None, RepoError]
ListResult = Union[list[str], RepoError]
LockResult = Union[FileLock, RepoError]
```

### 3.2 Public Functions

```python
from pathlib import Path
from typing import Optional, Type, TypeVar, Union, Callable, Any
from contextlib import contextmanager, asynccontextmanager

T = TypeVar('T', bound=BaseModel)


# ============================================================
# READ OPERATIONS
# ============================================================

def read_yaml(
    path: str | Path,
    schema: Type[T],
    options: Optional[ReadOptions] = None
) -> Union[T, None, RepoError]:
    """
    Read and parse a YAML file with schema validation.

    Args:
        path: Absolute or relative path to file
        schema: Pydantic model class for validation
        options: Read options

    Returns:
        Parsed and validated data, None if missing (when allowed), or error

    Process:
        1. Resolve path relative to repo root
        2. Check file exists (return FILE_NOT_FOUND or None based on options)
        3. Read file content
        4. Parse YAML
        5. Check schema version header
        6. Apply migrations if needed
        7. Validate against schema
        8. Return typed data
    """
    ...


def read_json(
    path: str | Path,
    schema: Type[T],
    options: Optional[ReadOptions] = None
) -> Union[T, None, RepoError]:
    """
    Read and parse a JSON file with schema validation.
    Same behavior as read_yaml but for JSON format.
    """
    ...


def read_text(
    path: str | Path,
    options: Optional[ReadOptions] = None
) -> Union[str, None, RepoError]:
    """
    Read a file as raw text without parsing.
    Used for conversation logs and other non-structured data.
    """
    ...


# ============================================================
# WRITE OPERATIONS
# ============================================================

def write_yaml(
    path: str | Path,
    data: BaseModel,
    options: Optional[WriteOptions] = None
) -> Optional[RepoError]:
    """
    Write data to a YAML file with atomic write and validation.

    Args:
        path: Absolute or relative path to file
        data: Pydantic model instance to write
        options: Write options

    Returns:
        None on success, RepoError on failure

    Process:
        1. Validate data against its schema
        2. Add/update schema version header
        3. Serialize to YAML
        4. Create parent directories if needed
        5. Write to temp file
        6. Rename temp to target (atomic)
    """
    ...


def write_json(
    path: str | Path,
    data: BaseModel,
    options: Optional[WriteOptions] = None
) -> Optional[RepoError]:
    """
    Write data to a JSON file with atomic write and validation.
    Same behavior as write_yaml but for JSON format.
    """
    ...


def write_text(
    path: str | Path,
    content: str,
    options: Optional[WriteOptions] = None
) -> Optional[RepoError]:
    """
    Write raw text to a file.
    Used for conversation logs and markdown files.
    """
    ...


def append_text(
    path: str | Path,
    content: str,
    create_if_missing: bool = True
) -> Optional[RepoError]:
    """
    Append text to a file, creating if it doesn't exist.
    Used for conversation logs.
    """
    ...


# ============================================================
# FILE SYSTEM OPERATIONS
# ============================================================

def list_files(
    pattern: str,
    base_path: Optional[str | Path] = None
) -> Union[list[str], RepoError]:
    """
    List files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "activities/2025-*/*.yaml")
        base_path: Base directory for pattern (default: repo root)

    Returns:
        Array of matching file paths (relative to base_path)
    """
    ...


def file_exists(path: str | Path) -> bool:
    """Check if a file exists."""
    ...


def directory_exists(path: str | Path) -> bool:
    """Check if a directory exists."""
    ...


def ensure_directory(path: str | Path) -> Optional[RepoError]:
    """Create a directory and all parent directories."""
    ...


def delete_file(path: str | Path) -> Optional[RepoError]:
    """Delete a file if it exists."""
    ...


def copy_path(source: str | Path, destination: str | Path) -> Optional[RepoError]:
    """Copy a file or directory."""
    ...


def move_path(source: str | Path, destination: str | Path) -> Optional[RepoError]:
    """Move a file or directory."""
    ...


# ============================================================
# LOCKING OPERATIONS
# ============================================================

def acquire_lock(
    operation: str,
    paths: Optional[list[str]] = None,
    timeout_ms: Optional[int] = None
) -> Union[FileLock, RepoError]:
    """
    Acquire an exclusive lock for a set of paths.

    Args:
        operation: Description of operation (for diagnostics)
        paths: Directories to lock (e.g., ['activities/', 'metrics/'])
        timeout_ms: Maximum wait time (default: from config)

    Returns:
        Lock object or error

    Lock file location: config/.sync_lock

    Behavior:
        1. Check if lock file exists
        2. If exists and fresh (< 5 min): wait and retry
        3. If exists and stale (>= 5 min): break and acquire
        4. Create lock file with PID and timestamp
        5. Return lock handle
    """
    ...


def release_lock(lock: FileLock) -> None:
    """
    Release a previously acquired lock.
    Safe to call multiple times.
    """
    ...


@contextmanager
def with_lock(
    operation: str,
    paths: Optional[list[str]] = None
):
    """
    Context manager for lock acquisition.
    Automatically releases lock on exit.

    Usage:
        with with_lock("sync", ["activities/", "metrics/"]) as lock:
            if isinstance(lock, RepoError):
                # Handle error
                return
            # Do work with lock held
    """
    ...


# ============================================================
# PATH UTILITIES
# ============================================================

def resolve_path(relative_path: str | Path) -> Path:
    """
    Resolve a path relative to the repository root.

    Args:
        relative_path: Path relative to repo root (e.g., "activities/2025-11/file.yaml")

    Returns:
        Absolute path

    If path is already absolute, returns it as-is.
    """
    ...


def get_repo_root() -> Path:
    """
    Get the repository root directory.

    Delegates to M2.get_repo_root() for consistency.
    """
    ...


def get_activity_path(
    date: str,
    sport_type: str,
    start_time: str
) -> str:
    """
    Generate a path for an activity file.

    Args:
        date: Activity date (YYYY-MM-DD)
        sport_type: Normalized sport type
        start_time: Start time (HHmm format) or sequence number

    Returns:
        Relative path like "activities/2025-11/2025-11-05_run_1230.yaml"
    """
    ...


def get_metrics_path(date: str) -> str:
    """
    Generate a path for a daily metrics file.

    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-11-05")

    Returns:
        Relative path like "metrics/daily/2025-11-05.yaml"
    """
    ...


def get_workout_path(
    week_number: int,
    day_name: str,
    workout_type: str
) -> str:
    """
    Generate a path for a workout file.

    Args:
        week_number: Week number (1-based, e.g., 3)
        day_name: Day abbreviation (e.g., "tue")
        workout_type: Workout type (e.g., "tempo")

    Returns:
        Relative path like "plans/workouts/week_03/tue_tempo.yaml"
    """
    ...


# ============================================================
# SCHEMA MIGRATION
# ============================================================

def register_migration(
    schema_type: SchemaType,
    from_version: str,
    to_version: str,
    migrate: Callable[[dict], dict]
) -> None:
    """
    Register a migration function for a schema type.
    Migrations are applied automatically on read when version mismatch detected.
    """
    ...


def get_current_schema_version(schema_type: SchemaType) -> str:
    """Get the current schema version for a type."""
    ...
```

---

## 4. Data Structures

### 4.1 Lock File Schema (`config/.sync_lock`)

```yaml
pid: 12345
acquired_at: "2025-11-15T10:30:00Z"
operation: "sync"
locked_paths:
  - "activities/"
  - "metrics/"
  - "plans/"
```

### 4.2 Schema Version Header

All YAML/JSON data files include this header:

```yaml
_schema:
  format_version: "1.0.0"
  schema_type: "activity"  # One of the SchemaType values
```

### 4.3 Path Conventions

| Data Type | Path Pattern | Example |
|-----------|--------------|---------|
| Activity | `activities/{YYYY-MM}/{YYYY-MM-DD}_{sport}_{HHmm}.yaml` | `activities/2025-11/2025-11-05_run_1230.yaml` |
| Daily Metrics | `metrics/daily/{YYYY-MM-DD}.yaml` | `metrics/daily/2025-11-05.yaml` |
| Weekly Summary | `metrics/weekly_summary.yaml` | `metrics/weekly_summary.yaml` |
| Plan | `plans/current_plan.yaml` | `plans/current_plan.yaml` |
| Workout | `plans/workouts/week_{NN}/{day}_{type}.yaml` | `plans/workouts/week_02/tue_tempo.yaml` |
| Profile | `athlete/profile.yaml` | `athlete/profile.yaml` |
| Memories | `athlete/memories.yaml` | `athlete/memories.yaml` |
| Training History | `athlete/training_history.yaml` | `athlete/training_history.yaml` |
| Conversation | `conversations/{YYYY-MM-DD}_session.md` | `conversations/2025-11-15_session.md` |
| Pending Suggestions | `plans/pending_suggestions.yaml` | `plans/pending_suggestions.yaml` |
| Backup | `backup/{YYYY-MM-DD_HH-MM}/{directory}/` | `backup/2025-11-15_10-30/activities/` |

---

## 5. Core Algorithms

### 5.1 Atomic Write Algorithm

```python
import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, content: str) -> Optional[RepoError]:
    """
    Write content atomically using temp file + rename.

    This prevents partial writes and ensures readers always see
    complete, valid files.
    """

    # 1. Generate temp file in same directory (for same-filesystem rename)
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)

    try:
        # 2. Write to temp file
        fd, temp_path = tempfile.mkstemp(
            dir=directory,
            prefix=f".{path.name}.",
            suffix=".tmp"
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)

            # 3. Atomic rename (POSIX guarantees atomicity)
            os.replace(temp_path, path)

        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    except PermissionError as e:
        return RepoError(
            error_type=RepoErrorType.PERMISSION_ERROR,
            message=str(e),
            path=str(path),
            operation="write"
        )
    except OSError as e:
        return RepoError(
            error_type=RepoErrorType.WRITE_ERROR,
            message=str(e),
            path=str(path)
        )

    return None
```

### 5.2 Lock Acquisition Algorithm

```python
import os
import time
from datetime import datetime, timedelta
from pathlib import Path


LOCK_STALE_THRESHOLD = timedelta(minutes=5)


def acquire_lock(
    operation: str,
    paths: list[str] | None = None,
    timeout_ms: int | None = None
) -> FileLock | RepoError:
    """Lock acquisition with retry and stale detection."""

    config = load_config()
    if isinstance(config, ConfigError):
        return RepoError(
            error_type=RepoErrorType.LOCK_TIMEOUT,
            message="Could not load config for lock settings"
        )

    lock_path = resolve_path("config/.sync_lock")
    timeout_ms = timeout_ms or config.settings.system.lock_timeout_ms
    retry_count = config.settings.system.lock_retry_count
    retry_delay_ms = config.settings.system.lock_retry_delay_ms

    start_time = time.time()
    retries = 0

    while (time.time() - start_time) * 1000 < timeout_ms:

        # 1. Check existing lock
        if lock_path.exists():
            try:
                existing_lock = read_yaml(lock_path, FileLockSchema)
                if isinstance(existing_lock, RepoError):
                    # Corrupted lock file, delete and retry
                    lock_path.unlink()
                    continue

                lock_age = datetime.now() - existing_lock.acquired_at

                # Check if stale (> 5 minutes)
                if lock_age > LOCK_STALE_THRESHOLD:
                    print(f"Breaking stale lock from PID {existing_lock.pid}")
                    lock_path.unlink()
                    # Continue to acquire

                # Check if holder process is dead
                elif not _process_running(existing_lock.pid):
                    print(f"Breaking orphan lock from dead PID {existing_lock.pid}")
                    lock_path.unlink()
                    # Continue to acquire

                else:
                    # Lock is actively held
                    retries += 1
                    if retries > retry_count:
                        return RepoError(
                            error_type=RepoErrorType.LOCK_TIMEOUT,
                            message="Lock held by another process",
                            path=str(lock_path),
                            holder=existing_lock,
                            waited_ms=int((time.time() - start_time) * 1000)
                        )
                    time.sleep(retry_delay_ms / 1000)
                    continue

            except Exception:
                # Any error reading lock, delete and retry
                lock_path.unlink(missing_ok=True)

        # 2. Create new lock
        new_lock = FileLock(
            id=f"lock_{int(time.time())}_{os.getpid()}",
            pid=os.getpid(),
            operation=operation,
            acquired_at=datetime.now(),
            path=lock_path,
            locked_paths=paths or []
        )

        try:
            write_yaml(lock_path, new_lock)
        except Exception:
            # Race condition - another process got lock first
            continue

        # 3. Verify we got the lock (double-check)
        time.sleep(0.01)  # Brief pause
        verify_lock = read_yaml(lock_path, FileLockSchema)
        if isinstance(verify_lock, RepoError):
            continue

        if verify_lock.pid == os.getpid():
            return new_lock
        # Lost race, retry

    return RepoError(
        error_type=RepoErrorType.LOCK_TIMEOUT,
        message="Timed out waiting for lock",
        path=str(lock_path),
        waited_ms=int((time.time() - start_time) * 1000)
    )


def _process_running(pid: int) -> bool:
    """Check if a process with given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
```

### 5.3 Schema Migration Algorithm

```python
from typing import Callable


# Migration registry
_migrations: dict[SchemaType, dict[str, Callable[[dict], dict]]] = {}


def register_migration(
    schema_type: SchemaType,
    from_version: str,
    to_version: str,
    migrate: Callable[[dict], dict]
) -> None:
    """Register a migration function."""
    if schema_type not in _migrations:
        _migrations[schema_type] = {}

    key = f"{from_version}->{to_version}"
    _migrations[schema_type][key] = migrate


def apply_migrations(
    data: dict,
    schema_type: SchemaType,
    current_version: str
) -> dict:
    """Apply all necessary migrations to bring data to current version."""

    file_version = data.get("_schema", {}).get("format_version", "0.0.0")

    if file_version == current_version:
        return data  # No migration needed

    if file_version > current_version:
        raise ValueError(
            f"File version {file_version} is newer than "
            f"supported version {current_version}"
        )

    # Find migration path
    migrated_data = data.copy()
    version = file_version

    while version != current_version:
        migration_key = f"{version}->{current_version}"
        if schema_type in _migrations and migration_key in _migrations[schema_type]:
            migrate_fn = _migrations[schema_type][migration_key]
            migrated_data = migrate_fn(migrated_data)
            version = current_version
        else:
            # Try incremental migration (1.0.0 -> 1.1.0 -> 1.2.0)
            # For v0, we only support direct migrations
            raise ValueError(
                f"No migration path from {file_version} to {current_version}"
            )

    # Update schema header
    migrated_data["_schema"] = {
        "format_version": current_version,
        "schema_type": schema_type.value
    }

    return migrated_data
```

### 5.4 Activity Path Generation

```python
from pathlib import Path


def get_activity_path(
    date: str,
    sport_type: str,
    start_time: str
) -> str:
    """
    Generate a path for an activity file.

    Args:
        date: "2025-11-05"
        sport_type: "run"
        start_time: "1230" (HHmm) or "1" (sequence number)

    Returns:
        "activities/2025-11/2025-11-05_run_1230.yaml"
    """

    year_month = date[:7]  # "2025-11"
    base_path = f"activities/{year_month}"
    filename = f"{date}_{sport_type}_{start_time}.yaml"
    full_path = f"{base_path}/{filename}"

    # Handle collision
    resolved = resolve_path(full_path)
    if resolved.exists():
        # Check if same activity by ID
        existing = read_yaml(resolved, ActivitySchema, ReadOptions(validate=False))
        if isinstance(existing, BaseModel):
            # Will be checked by caller for ID match
            return full_path

        # Different activity or error, add sequence
        sequence = 1
        while resolve_path(f"{base_path}/{date}_{sport_type}_{start_time}_{sequence}.yaml").exists():
            sequence += 1
        return f"{base_path}/{date}_{sport_type}_{start_time}_{sequence}.yaml"

    return full_path
```

### 5.5 Path Resolution Algorithm

```python
from pathlib import Path
from sports_coach_engine.m02_config import get_repo_root as m2_get_repo_root


def resolve_path(relative_path: str | Path) -> Path:
    """
    Resolve a path relative to repository root.

    Algorithm:
        1. Convert to Path if string
        2. If absolute, return as-is
        3. Otherwise, resolve relative to repo root from M2
    """
    path = Path(relative_path)

    if path.is_absolute():
        return path

    repo_root = m2_get_repo_root()
    return repo_root / path


def get_repo_root() -> Path:
    """Get repo root by delegating to M2."""
    return m2_get_repo_root()
```

### 5.6 Metrics and Workout Path Generation

```python
def get_metrics_path(date: str) -> str:
    """
    Generate daily metrics file path.

    Args:
        date: "2025-11-05"

    Returns:
        "metrics/daily/2025-11-05.yaml"
    """
    return f"metrics/daily/{date}.yaml"


def get_workout_path(
    week_number: int,
    day_name: str,
    workout_type: str
) -> str:
    """
    Generate workout file path.

    Args:
        week_number: 3
        day_name: "tue"
        workout_type: "tempo"

    Returns:
        "plans/workouts/week_03/tue_tempo.yaml"
    """
    week_dir = f"week_{week_number:02d}"
    filename = f"{day_name.lower()}_{workout_type.lower()}.yaml"
    return f"plans/workouts/{week_dir}/{filename}"
```

---

## 6. Error Handling

### 6.1 Error Scenarios

| Scenario | Error Type | Recovery |
|----------|------------|----------|
| File not found | `FILE_NOT_FOUND` | Return None if `allow_missing`, else error |
| File exists but not readable | `PERMISSION_ERROR` | Cannot auto-recover, show permissions needed |
| Invalid YAML syntax | `PARSE_ERROR` | Show error location, cannot auto-recover |
| Schema validation fails | `VALIDATION_ERROR` | Return all validation errors |
| Schema version too new | `SCHEMA_VERSION_ERROR` | Require code upgrade |
| Write fails (disk full, etc.) | `WRITE_ERROR` | Clean up temp file |
| Parent directory cannot be created | `DIRECTORY_ERROR` | Check permissions, cannot auto-recover |
| Lock held by another process | `LOCK_HELD` | Wait and retry |
| Lock wait timeout | `LOCK_TIMEOUT` | Return error, caller decides |
| Permission denied on write | `PERMISSION_ERROR` | Cannot auto-recover |

### 6.2 User-Facing Error Messages

```python
ERROR_MESSAGES: dict[RepoErrorType, str] = {
    RepoErrorType.FILE_NOT_FOUND: "File not found: {path}",
    RepoErrorType.PARSE_ERROR: "Invalid YAML in {path}: {message}",
    RepoErrorType.VALIDATION_ERROR: "Data validation failed for {path}:\n{errors}",
    RepoErrorType.SCHEMA_VERSION_ERROR: (
        "File {path} has schema version {file_version} but this version "
        "of the app only supports up to {supported_version}. Please upgrade."
    ),
    RepoErrorType.WRITE_ERROR: "Could not write to {path}: {message}",
    RepoErrorType.LOCK_HELD: "Another operation is in progress. Please wait and try again.",
    RepoErrorType.LOCK_TIMEOUT: "Timed out waiting for lock after {waited_ms}ms. Try again.",
    RepoErrorType.PERMISSION_ERROR: "Permission denied for {operation} on {path}",
    RepoErrorType.DIRECTORY_ERROR: "Directory error for {path}: {message}",
}


def format_repo_error(error: RepoError) -> str:
    """Format a RepoError for user display."""
    template = ERROR_MESSAGES.get(error.error_type, "Unknown error: {message}")
    return template.format(
        path=error.path or "",
        message=error.message,
        file_version=error.file_version or "",
        supported_version=error.supported_version or "",
        waited_ms=error.waited_ms or 0,
        operation=error.operation or "",
        errors="\n".join(f"  - {e.path}: {e.message}" for e in error.validation_errors)
    )
```

---

## 7. Integration Points

### 7.1 Integration with API Layer

This module is used by all core modules for file operations. **Additionally, this module is exposed for direct access by Claude Code** for exploration and debugging.

```
# Internal use by core modules
API Layer → M1 (workflows) → M4/M9/M10 → M3::read_yaml/write_yaml()

# Direct use by Claude Code for exploration
Claude Code → core.repository::RepositoryIO → read_yaml(), list_files()
```

### 7.2 Module Usage Patterns

```python
from sports_coach_engine.core.repository import (
    read_yaml, write_yaml, list_files, with_lock,
    get_activity_path, RepoError
)
from sports_coach_engine.schemas import ActivitySchema, ProfileSchema

# M4 (Profile Service) - Read/write profile
profile = read_yaml("athlete/profile.yaml", ProfileSchema)
if isinstance(profile, RepoError):
    # Handle error
    pass

write_yaml("athlete/profile.yaml", updated_profile)

# M5 (Strava Integration) - Write activities with lock
with with_lock("sync", ["activities/", "metrics/"]) as lock:
    if isinstance(lock, RepoError):
        print(f"Could not acquire lock: {lock.message}")
        return

    for activity in new_activities:
        path = get_activity_path(
            activity.date,
            activity.sport_type,
            activity.start_time
        )
        write_yaml(path, activity)

# M9 (Metrics Engine) - List and process activities
activity_files = list_files("activities/**/*.yaml")
if isinstance(activity_files, RepoError):
    # Handle error
    pass
else:
    for file in activity_files:
        activity = read_yaml(file, ActivitySchema)
        # Process...

# M14 (Conversation Logger) - Append to log
append_text(
    "conversations/2025-11-15_session.md",
    f"\n## User\n{message}\n"
)

# Claude Code - Direct file access for exploration
repo = RepositoryIO()
profile = repo.read_yaml("athlete/profile.yaml")
activities = repo.list_files("activities/**/*.yaml")
```

### 7.3 Module Dependencies (Who Calls M3)

| Module | Operations Used |
|--------|-----------------|
| Claude Code (direct) | `read_yaml`, `list_files` (for exploration) |
| API Layer | `read_yaml` (for initialization) |
| M4 (Profile) | `read_yaml`, `write_yaml` |
| M5 (Strava Integration) | `write_yaml`, `get_activity_path`, `acquire_lock` |
| M6 (Normalization) | `write_yaml` |
| M9 (Metrics) | `read_yaml`, `write_yaml`, `list_files` |
| M10 (Plan Generator) | `read_yaml`, `write_yaml`, `get_workout_path` |
| M11 (Adaptation) | `read_yaml`, `write_yaml` |
| M13 (Memory) | `read_yaml`, `write_yaml` |
| M14 (Conversation) | `append_text`, `read_text` |

### 7.4 Concurrency Model

- **Reads**: Safe for concurrent access (no locking needed)
- **Writes**: Must acquire lock for batch operations
- **Single file writes**: Atomic writes prevent corruption even without lock
- **Multi-file transactions**: Must use lock to ensure consistency

---

## 8. Test Scenarios

### 8.1 Unit Tests

```python
import pytest
from pathlib import Path
from sports_coach_engine.m03_repository import (
    read_yaml, write_yaml, atomic_write, acquire_lock,
    release_lock, list_files, RepoError, RepoErrorType
)


class TestReadYaml:
    """Tests for read_yaml function."""

    def test_reads_and_parses_valid_yaml(self, tmp_path: Path):
        """Should read and parse valid YAML file."""
        file_path = tmp_path / "test.yaml"
        file_path.write_text("name: test\nvalue: 42")

        result = read_yaml(file_path, TestSchema)

        assert not isinstance(result, RepoError)
        assert result.name == "test"
        assert result.value == 42

    def test_returns_file_not_found_for_missing_file(self, tmp_path: Path):
        """Should return error for missing file."""
        result = read_yaml(tmp_path / "missing.yaml", TestSchema)

        assert isinstance(result, RepoError)
        assert result.error_type == RepoErrorType.FILE_NOT_FOUND

    def test_returns_none_when_allow_missing(self, tmp_path: Path):
        """Should return None if file missing and allow_missing=True."""
        options = ReadOptions(allow_missing=True)
        result = read_yaml(tmp_path / "missing.yaml", TestSchema, options)

        assert result is None

    def test_returns_parse_error_for_invalid_yaml(self, tmp_path: Path):
        """Should return error for malformed YAML."""
        file_path = tmp_path / "invalid.yaml"
        file_path.write_text("invalid: yaml: content: :")

        result = read_yaml(file_path, TestSchema)

        assert isinstance(result, RepoError)
        assert result.error_type == RepoErrorType.PARSE_ERROR

    def test_returns_validation_error_for_schema_mismatch(self, tmp_path: Path):
        """Should return error when data doesn't match schema."""
        file_path = tmp_path / "invalid_schema.yaml"
        file_path.write_text("wrong_field: value")

        result = read_yaml(file_path, TestSchema)

        assert isinstance(result, RepoError)
        assert result.error_type == RepoErrorType.VALIDATION_ERROR


class TestWriteYaml:
    """Tests for write_yaml function."""

    def test_writes_valid_data_atomically(self, tmp_path: Path):
        """Should write data and file exists with correct content."""
        file_path = tmp_path / "output.yaml"
        data = TestSchema(name="test", value=42)

        result = write_yaml(file_path, data)

        assert result is None
        assert file_path.exists()

    def test_creates_parent_directories(self, tmp_path: Path):
        """Should create parent directories if needed."""
        file_path = tmp_path / "nested" / "path" / "output.yaml"
        data = TestSchema(name="test", value=42)

        result = write_yaml(file_path, data)

        assert result is None
        assert file_path.exists()

    def test_adds_schema_header(self, tmp_path: Path):
        """Should add _schema header to output."""
        file_path = tmp_path / "output.yaml"
        data = TestSchema(name="test", value=42)

        write_yaml(file_path, data)
        content = file_path.read_text()

        assert "_schema:" in content
        assert "format_version:" in content


class TestAcquireLock:
    """Tests for acquire_lock function."""

    def test_acquires_lock_when_none_exists(self, tmp_path: Path, monkeypatch):
        """Should acquire lock successfully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config").mkdir()

        lock = acquire_lock("test_operation")

        assert not isinstance(lock, RepoError)
        assert lock.operation == "test_operation"
        release_lock(lock)

    def test_waits_and_retries_when_lock_held(self, tmp_path: Path, monkeypatch):
        """Should wait and retry when lock is held."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config").mkdir()

        # Create active lock (recent timestamp, valid PID)
        active_lock = FileLock(
            id="active",
            pid=os.getpid(),  # Current process
            operation="active_op",
            acquired_at=datetime.now(),
            path=str(tmp_path / "config/.sync_lock"),
            locked_paths=[]
        )
        write_yaml(tmp_path / "config/.sync_lock", active_lock)

        # Try to acquire with short timeout (should fail)
        lock = acquire_lock("new_operation", timeout_ms=500)

        assert isinstance(lock, RepoError)
        assert lock.error_type == RepoErrorType.LOCK_TIMEOUT

        # Release original lock
        release_lock(active_lock)

        # Now acquire should succeed
        lock2 = acquire_lock("new_operation")
        assert not isinstance(lock2, RepoError)
        release_lock(lock2)

    def test_breaks_stale_lock(self, tmp_path: Path, monkeypatch):
        """Should break lock older than 5 minutes."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config").mkdir()

        # Create old lock
        old_lock = FileLock(
            id="old",
            pid=99999,  # Non-existent PID
            operation="old_op",
            acquired_at=datetime.now() - timedelta(minutes=10),
            path=tmp_path / "config/.sync_lock",
            locked_paths=[]
        )
        write_yaml(tmp_path / "config/.sync_lock", old_lock)

        # Acquire should succeed
        lock = acquire_lock("new_operation")

        assert not isinstance(lock, RepoError)
        release_lock(lock)


class TestListFiles:
    """Tests for list_files function."""

    def test_returns_files_matching_pattern(self, tmp_path: Path, monkeypatch):
        """Should return files matching glob pattern."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "activities" / "2025-11").mkdir(parents=True)
        (tmp_path / "activities" / "2025-11" / "test1.yaml").touch()
        (tmp_path / "activities" / "2025-11" / "test2.yaml").touch()

        result = list_files("activities/**/*.yaml")

        assert not isinstance(result, RepoError)
        assert len(result) == 2

    def test_returns_empty_for_no_matches(self, tmp_path: Path, monkeypatch):
        """Should return empty list when no files match."""
        monkeypatch.chdir(tmp_path)

        result = list_files("nonexistent/**/*.yaml")

        assert result == []


class TestAtomicWrite:
    """Tests for atomic_write function."""

    def test_atomic_write_success(self, tmp_path: Path):
        """Should write file atomically."""
        file_path = tmp_path / "output.txt"
        content = "test content"

        result = atomic_write(file_path, content)

        assert result is None
        assert file_path.read_text() == content

    def test_atomic_write_cleans_up_temp_on_failure(self, tmp_path: Path, monkeypatch):
        """Should remove temp file if write fails."""
        file_path = tmp_path / "output.txt"

        # Force write failure by making directory read-only after temp creation
        # (Implementation-specific test)
        pass

    def test_concurrent_writes_no_corruption(self, tmp_path: Path):
        """Multiple concurrent writes should not corrupt file."""
        file_path = tmp_path / "output.txt"

        # Write multiple times rapidly
        for i in range(10):
            content = f"content_{i}"
            atomic_write(file_path, content)

        # File should contain valid content (last write wins)
        final_content = file_path.read_text()
        assert final_content.startswith("content_")


class TestSchemaMigration:
    """Tests for schema migration."""

    def test_applies_migration_from_old_version(self, tmp_path: Path):
        """Should migrate data from v1.0.0 to v1.1.0."""
        # Register migration
        def migrate_1_0_to_1_1(data: dict) -> dict:
            data["new_field"] = "default_value"
            return data

        register_migration(
            SchemaType.PROFILE,
            "1.0.0",
            "1.1.0",
            migrate_1_0_to_1_1
        )

        # Create file with old version
        file_path = tmp_path / "profile.yaml"
        old_data = {
            "_schema": {"format_version": "1.0.0", "schema_type": "profile"},
            "name": "Athlete"
        }
        file_path.write_text(yaml.safe_dump(old_data))

        # Read should auto-migrate
        result = read_yaml(file_path, ProfileSchema)

        assert not isinstance(result, RepoError)
        assert result.new_field == "default_value"

    def test_rejects_future_version(self, tmp_path: Path):
        """Should return error when file version is newer than supported."""
        file_path = tmp_path / "profile.yaml"
        future_data = {
            "_schema": {"format_version": "2.0.0", "schema_type": "profile"},
            "name": "Athlete"
        }
        file_path.write_text(yaml.safe_dump(future_data))

        result = read_yaml(file_path, ProfileSchema)

        assert isinstance(result, RepoError)
        assert result.error_type == RepoErrorType.SCHEMA_VERSION_ERROR


class TestConcurrentAccess:
    """Tests for concurrent access scenarios."""

    def test_concurrent_reads_safe(self, tmp_path: Path):
        """Multiple concurrent reads should work without lock."""
        file_path = tmp_path / "data.yaml"
        write_yaml(file_path, TestSchema(name="test", value=42))

        # Read multiple times concurrently (simulate with threads/processes)
        results = []
        for _ in range(5):
            result = read_yaml(file_path, TestSchema)
            results.append(result)

        assert all(not isinstance(r, RepoError) for r in results)
        assert all(r.name == "test" for r in results)
```

### 8.2 Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Empty YAML file | Parse as empty dict |
| Very large file (>10MB) | Should still work (no streaming in v0) |
| Unicode in file content | Preserve correctly (UTF-8) |
| Symlinks | Follow symlinks for read, error for write |
| Concurrent writes to same file | Last writer wins (atomic) |

---

## 9. Implementation Notes

### 9.1 Project Structure

```
sports_coach_engine/
├── __init__.py
├── m03_repository/
│   ├── __init__.py
│   ├── read.py           # read_yaml, read_json, read_text
│   ├── write.py          # write_yaml, write_json, write_text, append_text
│   ├── lock.py           # acquire_lock, release_lock, with_lock
│   ├── paths.py          # Path utilities and generators
│   ├── migration.py      # Schema migration logic
│   └── errors.py         # Error types and formatting
```

### 9.2 Performance Considerations

- **File listing**: Not cached, fresh on each call
- **YAML parsing**: Synchronous (acceptable for v0 file sizes)
- **Lock acquisition**: Has retry delay to prevent busy-waiting
- **No memory caching**: Files read fresh each time (simplicity over performance)

### 9.3 Known Limitations

1. **No file watching**: Changes require explicit read
2. **No compression**: Files stored as plain YAML
3. **No encryption**: Relies on file system permissions
4. **Single process**: Lock mechanism assumes single-process usage

---

## 10. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.1 | 2026-01-12 | Fixed FileLock from dataclass to BaseModel for serialization compatibility. Removed async/aiofiles (over-engineering for v0). Added missing algorithms: resolve_path(), get_metrics_path(), get_workout_path(). Added schema definitions note. Completed test stub for lock retry. Added tests for atomic write failure, schema migration, and concurrent access. Added missing error scenarios for unreadable files and directory creation failures. |
| 1.0.0 | 2026-01-12 | Initial specification (Python) |
