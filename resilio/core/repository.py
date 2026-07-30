"""
M3 - Repository I/O

Centralized file system operations for all data persistence.
Handles YAML/JSON read/write, atomic writes, file locking, schema validation.
"""

from pathlib import Path
from typing import Any, Optional, Type, TypeVar, Union, cast, overload

import yaml
from pydantic import BaseModel

from resilio.core.config import get_repo_root
from resilio.core.state_permissions import (
    ensure_private_directory_tree,
    harden_sensitive_file,
)
from resilio.schemas.repository import ReadOptions, RepoError, RepoErrorType

T = TypeVar("T", bound=BaseModel)


class RepositoryIO:
    """Centralized repository for file I/O operations."""

    def __init__(self) -> None:
        """
        Initialize repository.

        Args:
            config: Configuration object (optional, for future use)
        """
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

    def _prepare_parent(self, resolved_path: Path) -> bool:
        """Create a parent and return whether the target is private state."""
        data_root = self.repo_root / "data"
        try:
            resolved_path.relative_to(data_root)
        except ValueError:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            return False
        ensure_private_directory_tree(data_root, resolved_path.parent)
        return True

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
            options: Read options (defaults to should_validate=True, allow_missing=False)

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
                message="File not found",
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
        if options.should_validate:
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
        self,
        path: str | Path,
        data: BaseModel | dict[str, Any] | list[Any],
        atomic: bool = True,
    ) -> Optional["RepoError"]:
        """
        Write data to a YAML file with optional atomic write.

        Args:
            path: Path to YAML file (relative to repo root)
            data: Pydantic model, dict, or list to serialize
            atomic: Use atomic write (default: True)

        Returns:
            None on success, RepoError on failure
        """
        resolved_path = self.resolve_path(path)

        # Ensure parent directory exists
        is_private_state = self._prepare_parent(resolved_path)

        # Serialize to YAML
        try:
            payload = (
                data.model_dump(mode="json", by_alias=True) if isinstance(data, BaseModel) else data
            )
            yaml_content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        except Exception as e:
            return RepoError(
                error_type=RepoErrorType.VALIDATION_ERROR,
                message=f"Serialization failed: {e}",
            )

        if atomic:
            return self._atomic_write(
                resolved_path,
                yaml_content,
                private_state=is_private_state,
            )
        else:
            try:
                if is_private_state and resolved_path.exists():
                    harden_sensitive_file(resolved_path)
                resolved_path.write_text(yaml_content)
                if is_private_state:
                    harden_sensitive_file(resolved_path)
                return None
            except Exception as e:
                return RepoError(
                    error_type=RepoErrorType.WRITE_ERROR,
                    message=str(e),
                    path=str(resolved_path),
                )

    def _atomic_write(
        self,
        path: Path,
        content: str,
        *,
        private_state: bool,
    ) -> Optional["RepoError"]:
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
                    f.flush()
                    os.fsync(f.fileno())

                # Atomic rename
                os.replace(temp_path, path)
                if private_state:
                    harden_sensitive_file(path)
                directory_descriptor = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
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
    # JSON OPERATIONS
    # ============================================================

    @overload
    def read_json(
        self,
        path: str | Path,
        schema: Type[T],
    ) -> T | None | RepoError:
        ...

    @overload
    def read_json(
        self,
        path: str | Path,
        schema: None = None,
    ) -> dict[str, Any] | None | RepoError:
        ...

    def read_json(
        self,
        path: str | Path,
        schema: Optional[Type[T]] = None,
    ) -> T | dict[str, Any] | None | RepoError:
        """
        Read and parse a JSON file.

        Args:
            path: Path to JSON file (relative to repo root)
            schema: Optional Pydantic model class for validation

        Returns:
            Validated data model (if schema provided), raw dict, None (if missing), or RepoError
        """
        import json

        resolved_path = self.resolve_path(path)

        # Check file exists
        if not resolved_path.exists():
            return None

        # Read and parse
        try:
            with open(resolved_path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return RepoError(
                error_type=RepoErrorType.PARSE_ERROR,
                message=str(e),
                path=str(resolved_path),
            )

        # Validate against schema if provided
        if schema:
            try:
                return schema.model_validate(data)
            except Exception as e:
                return RepoError(
                    error_type=RepoErrorType.VALIDATION_ERROR,
                    message=f"Validation failed: {e}",
                    path=str(resolved_path),
                )

        if not isinstance(data, dict):
            return RepoError(
                error_type=RepoErrorType.VALIDATION_ERROR,
                message="JSON document must be an object",
                path=str(resolved_path),
            )
        return cast(dict[str, Any], data)

    def write_json(
        self,
        path: str | Path,
        data: BaseModel | dict[str, Any] | list[Any],
        atomic: bool = True,
    ) -> Optional[RepoError]:
        """
        Write data to a JSON file.

        Args:
            path: Path to JSON file (relative to repo root)
            data: Pydantic model, dict, or list to serialize
            atomic: Use atomic write (default: True)

        Returns:
            None on success, RepoError on failure
        """
        import json

        resolved_path = self.resolve_path(path)

        # Ensure parent directory exists
        is_private_state = self._prepare_parent(resolved_path)

        # Serialize to JSON
        try:
            if isinstance(data, BaseModel):
                json_content = json.dumps(
                    data.model_dump(mode="json", by_alias=True),
                    indent=2,
                )
            else:
                json_content = json.dumps(data, indent=2)
        except Exception as e:
            return RepoError(
                error_type=RepoErrorType.VALIDATION_ERROR,
                message=f"Serialization failed: {e}",
            )

        if atomic:
            return self._atomic_write(
                resolved_path,
                json_content,
                private_state=is_private_state,
            )
        else:
            try:
                if is_private_state and resolved_path.exists():
                    harden_sensitive_file(resolved_path)
                resolved_path.write_text(json_content)
                if is_private_state:
                    harden_sensitive_file(resolved_path)
                return None
            except Exception as e:
                return RepoError(
                    error_type=RepoErrorType.WRITE_ERROR,
                    message=str(e),
                    path=str(resolved_path),
                )

    # ============================================================
    # FILE OPERATIONS
    # ============================================================

    def delete_file(self, path: str | Path) -> Optional[RepoError]:
        """
        Delete a file.

        Args:
            path: Path to file (relative to repo root)

        Returns:
            None on success, RepoError on failure
        """
        resolved_path = self.resolve_path(path)

        if not resolved_path.exists():
            return None  # Already deleted, success

        try:
            resolved_path.unlink()
            return None
        except Exception as e:
            return RepoError(
                error_type=RepoErrorType.WRITE_ERROR,
                message=str(e),
                path=str(resolved_path),
            )
