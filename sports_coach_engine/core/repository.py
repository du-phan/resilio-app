"""
M3 - Repository I/O

Centralized file system operations for all data persistence.
Handles YAML/JSON read/write, atomic writes, file locking, schema validation.
"""

import yaml
from pathlib import Path
from typing import Optional, Type, TypeVar, Union

from pydantic import BaseModel

from sports_coach_engine.core.config import get_repo_root
from sports_coach_engine.schemas.repository import RepoError, RepoErrorType, ReadOptions

T = TypeVar("T", bound=BaseModel)


class RepositoryIO:
    """Centralized repository for file I/O operations."""

    def __init__(self, config=None):
        """
        Initialize repository.

        Args:
            config: Configuration object (optional, for future use)
        """
        self.config = config
        self.repo_root = get_repo_root()

    def resolve_path(self, relative_path: str | Path) -> Path:
        """
        Resolve a path relative to repository root.

        Args:
            relative_path: Path relative to repo root or absolute path

        Returns:
            Resolved absolute path
        """
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return self.repo_root / path

    def read_yaml(
        self,
        path: str | Path,
        schema: Type[T],
        options: Optional[ReadOptions] = None,
    ) -> Union[T, None, RepoError]:
        """
        Read and parse a YAML file with schema validation.

        Args:
            path: Path to YAML file (relative to repo root)
            schema: Pydantic model class for validation
            options: Read options (defaults to validate=True, allow_missing=False)

        Returns:
            Validated data model, None (if allow_missing=True), or RepoError
        """
        options = options or ReadOptions()
        resolved_path = self.resolve_path(path)

        # Check file exists
        if not resolved_path.exists():
            if options.allow_missing:
                return None
            return RepoError(
                error_type=RepoErrorType.FILE_NOT_FOUND,
                message=f"File not found",
                path=str(resolved_path),
            )

        # Read and parse
        try:
            with open(resolved_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return RepoError(
                error_type=RepoErrorType.PARSE_ERROR,
                message=str(e),
                path=str(resolved_path),
            )

        # Validate against schema
        if options.validate:
            try:
                return schema.model_validate(data)
            except Exception as e:
                return RepoError(
                    error_type=RepoErrorType.VALIDATION_ERROR,
                    message=f"Validation failed: {e}",
                    path=str(resolved_path),
                )

        return schema.model_validate(data)

    def file_exists(self, path: str | Path) -> bool:
        """
        Check if a file exists.

        Args:
            path: Path to check (relative to repo root)

        Returns:
            True if file exists, False otherwise
        """
        return self.resolve_path(path).exists()

    def list_files(self, pattern: str) -> list[Path]:
        """
        List files matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "activities/**/*.yaml")

        Returns:
            List of matching Path objects
        """
        return list(self.repo_root.glob(pattern))

    # ============================================================
    # WRITE OPERATIONS
    # ============================================================

    def write_yaml(
        self, path: str | Path, data: BaseModel, atomic: bool = True
    ) -> Optional["RepoError"]:
        """
        Write data to a YAML file with optional atomic write.

        Args:
            path: Path to YAML file (relative to repo root)
            data: Pydantic model to serialize
            atomic: Use atomic write (default: True)

        Returns:
            None on success, RepoError on failure
        """
        resolved_path = self.resolve_path(path)

        # Ensure parent directory exists
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize to YAML
        # Use model_dump(mode='json') to get JSON-serializable types
        # This converts enums to their string values, dates to ISO strings, etc.
        try:
            yaml_content = yaml.safe_dump(
                data.model_dump(mode='json'), sort_keys=False, allow_unicode=True
            )
        except Exception as e:
            return RepoError(
                error_type=RepoErrorType.VALIDATION_ERROR,
                message=f"Serialization failed: {e}",
            )

        if atomic:
            return self._atomic_write(resolved_path, yaml_content)
        else:
            try:
                resolved_path.write_text(yaml_content)
                return None
            except Exception as e:
                return RepoError(
                    error_type=RepoErrorType.WRITE_ERROR,
                    message=str(e),
                    path=str(resolved_path),
                )

    def _atomic_write(self, path: Path, content: str) -> Optional["RepoError"]:
        """
        Write content atomically using temp file + rename.

        Args:
            path: Target file path
            content: Content to write

        Returns:
            None on success, RepoError on failure
        """
        import os
        import tempfile

        directory = path.parent

        try:
            # Write to temp file in same directory
            fd, temp_path_str = tempfile.mkstemp(
                dir=directory, prefix=f".{path.name}.", suffix=".tmp"
            )
            temp_path = Path(temp_path_str)

            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)

                # Atomic rename
                os.replace(temp_path, path)
                return None
            except Exception:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            return RepoError(
                error_type=RepoErrorType.WRITE_ERROR,
                message=str(e),
                path=str(path),
            )

    # ============================================================
    # FILE LOCKING
    # ============================================================

    def acquire_lock(
        self,
        operation: str,
        paths: Optional[list[str]] = None,
        timeout_ms: int = 300000,
    ) -> Union["FileLock", "RepoError"]:
        """
        Acquire an exclusive lock for an operation.

        Args:
            operation: Description of the operation
            paths: List of paths being locked (optional)
            timeout_ms: Timeout in milliseconds (default: 5 minutes)

        Returns:
            FileLock object on success, RepoError on timeout
        """
        import os
        import time
        from datetime import datetime

        from sports_coach_engine.schemas.repository import FileLock

        lock_path = self.resolve_path("config/.sync_lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        start_time = time.time()

        while (time.time() - start_time) * 1000 < timeout_ms:
            # Check existing lock
            if lock_path.exists():
                existing = self.read_yaml(lock_path, FileLock)
                if not isinstance(existing, RepoError):
                    # Check if stale (>5 min) or dead process
                    try:
                        lock_time = datetime.fromisoformat(existing.acquired_at)
                        lock_age = datetime.now() - lock_time
                        if lock_age.total_seconds() > 300 or not self._process_running(
                            existing.pid
                        ):
                            # Break stale lock
                            lock_path.unlink()
                        else:
                            # Active lock, wait
                            time.sleep(0.1)
                            continue
                    except Exception:
                        # Invalid lock file, remove it
                        lock_path.unlink()

            # Create new lock
            new_lock = FileLock(
                id=f"lock_{int(time.time())}_{os.getpid()}",
                pid=os.getpid(),
                operation=operation,
                acquired_at=datetime.now().isoformat(),
                locked_paths=paths or [],
            )

            self.write_yaml(lock_path, new_lock)

            # Verify we got the lock
            time.sleep(0.01)
            verify = self.read_yaml(lock_path, FileLock)
            if not isinstance(verify, RepoError) and verify.pid == os.getpid():
                return new_lock

        return RepoError(
            error_type=RepoErrorType.LOCK_TIMEOUT, message="Timed out waiting for lock"
        )

    def release_lock(self, lock: "FileLock") -> None:
        """
        Release a previously acquired lock.

        Args:
            lock: Lock object to release
        """
        lock_path = self.resolve_path("config/.sync_lock")
        if lock_path.exists():
            lock_path.unlink()

    @staticmethod
    def _process_running(pid: int) -> bool:
        """
        Check if a process is running.

        Args:
            pid: Process ID to check

        Returns:
            True if process is running, False otherwise
        """
        import os

        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
