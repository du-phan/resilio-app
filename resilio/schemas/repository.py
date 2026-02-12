"""
Repository I/O schemas for M3 - Repository I/O module.

Defines error types, read options, and other repository-related schemas.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


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
    LOCK_TIMEOUT = "lock_timeout"


class RepoError:
    """Repository operation error with details."""

    def __init__(
        self, error_type: RepoErrorType, message: str, path: Optional[str] = None
    ):
        self.error_type = error_type
        self.message = message
        self.path = path

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        if self.path:
            return f"[{self.error_type.value}] {self.message} (path: {self.path})"
        return f"[{self.error_type.value}] {self.message}"


# ============================================================
# READ OPTIONS
# ============================================================


class ReadOptions(BaseModel):
    """Options for reading files."""

    should_validate: bool = True
    allow_missing: bool = False
    migrate_schema: bool = True


# ============================================================
# LOCK TYPES (FOR PHASE 1D)
# ============================================================


class FileLock(BaseModel):
    """File lock for concurrent access protection."""

    id: str
    pid: int
    operation: str
    acquired_at: str  # ISO datetime
    locked_paths: list[str] = []
