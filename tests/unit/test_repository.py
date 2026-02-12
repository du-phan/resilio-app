"""
Unit tests for M3 - Repository I/O module.

Tests file I/O operations, path resolution, and error handling.
"""

import pytest
import yaml
from pathlib import Path
from pydantic import BaseModel

from resilio.core.repository import RepositoryIO
from resilio.schemas.repository import RepoError, RepoErrorType, ReadOptions


# Test schema
class TestSchema(BaseModel):
    name: str
    value: int


class TestRepositoryIO:
    """Tests for RepositoryIO class."""

    def test_resolve_path_relative(self, tmp_path, monkeypatch):
        """Should resolve relative paths correctly."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        resolved = repo.resolve_path("test/file.yaml")

        assert resolved == tmp_path / "test" / "file.yaml"

    def test_resolve_path_absolute(self, tmp_path, monkeypatch):
        """Should return absolute paths unchanged."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        abs_path = Path("/absolute/path/file.yaml")
        resolved = repo.resolve_path(abs_path)

        assert resolved == abs_path

    def test_file_exists_returns_true_for_existing(self, tmp_path, monkeypatch):
        """Should return True for existing file."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "exists.txt").touch()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        assert repo.file_exists("exists.txt") is True

    def test_file_exists_returns_false_for_missing(self, tmp_path, monkeypatch):
        """Should return False for missing file."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        assert repo.file_exists("missing.txt") is False


class TestReadYaml:
    """Tests for read_yaml method."""

    def test_read_yaml_loads_valid_file(self, tmp_path, monkeypatch):
        """Should read and parse valid YAML file."""
        # Setup
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "test.yaml"
        test_file.write_text("name: test\nvalue: 42")

        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        # Test
        result = repo.read_yaml("test.yaml", TestSchema)

        assert not isinstance(result, RepoError)
        assert result.name == "test"
        assert result.value == 42

    def test_read_yaml_returns_none_when_allow_missing(self, tmp_path, monkeypatch):
        """Should return None for missing file when allow_missing=True."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        result = repo.read_yaml("missing.yaml", TestSchema, ReadOptions(allow_missing=True))

        assert result is None

    def test_read_yaml_returns_error_when_file_missing(self, tmp_path, monkeypatch):
        """Should return error for missing file when allow_missing=False."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        result = repo.read_yaml("missing.yaml", TestSchema)

        assert isinstance(result, RepoError)
        assert result.error_type == RepoErrorType.FILE_NOT_FOUND

    def test_read_yaml_returns_error_for_invalid_yaml(self, tmp_path, monkeypatch):
        """Should return error for malformed YAML."""
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "invalid.yaml"
        test_file.write_text("invalid: yaml: content:")

        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        result = repo.read_yaml("invalid.yaml", TestSchema)

        assert isinstance(result, RepoError)
        assert result.error_type == RepoErrorType.PARSE_ERROR

    def test_read_yaml_returns_error_for_validation_failure(self, tmp_path, monkeypatch):
        """Should return error when data doesn't match schema."""
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "bad_data.yaml"
        # Missing required 'value' field
        test_file.write_text("name: test")

        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        result = repo.read_yaml("bad_data.yaml", TestSchema)

        assert isinstance(result, RepoError)
        assert result.error_type == RepoErrorType.VALIDATION_ERROR


class TestListFiles:
    """Tests for list_files method."""

    def test_list_files_finds_matching_files(self, tmp_path, monkeypatch):
        """Should find files matching glob pattern."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "test1.yaml").touch()
        (tmp_path / "test2.yaml").touch()
        (tmp_path / "other.txt").touch()

        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        results = repo.list_files("*.yaml")

        assert len(results) == 2
        assert any(p.name == "test1.yaml" for p in results)
        assert any(p.name == "test2.yaml" for p in results)

    def test_list_files_returns_empty_for_no_matches(self, tmp_path, monkeypatch):
        """Should return empty list when no files match."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        results = repo.list_files("*.yaml")

        assert results == []


class TestWriteYaml:
    """Tests for write_yaml method."""

    def test_write_yaml_creates_file_atomically(self, tmp_path, monkeypatch):
        """Should write data atomically."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        data = TestSchema(name="test", value=42)
        error = repo.write_yaml("output.yaml", data)

        assert error is None
        assert (tmp_path / "output.yaml").exists()

        # Verify content
        result = repo.read_yaml("output.yaml", TestSchema)
        assert not isinstance(result, RepoError)
        assert result.name == "test"
        assert result.value == 42

    def test_write_yaml_creates_parent_directories(self, tmp_path, monkeypatch):
        """Should create parent directories if they don't exist."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        data = TestSchema(name="test", value=42)
        error = repo.write_yaml("nested/dir/output.yaml", data)

        assert error is None
        assert (tmp_path / "nested" / "dir" / "output.yaml").exists()

    def test_write_yaml_overwrites_existing_file(self, tmp_path, monkeypatch):
        """Should overwrite existing file."""
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "output.yaml"
        test_file.write_text("old: content")

        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        data = TestSchema(name="new", value=99)
        error = repo.write_yaml("output.yaml", data)

        assert error is None

        # Verify new content
        result = repo.read_yaml("output.yaml", TestSchema)
        assert not isinstance(result, RepoError)
        assert result.name == "new"
        assert result.value == 99


class TestFileLocking:
    """Tests for file locking methods."""

    def test_acquire_lock_succeeds_when_no_lock(self, tmp_path, monkeypatch):
        """Should acquire lock when none exists."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        lock = repo.acquire_lock("test_operation")

        assert not isinstance(lock, RepoError)
        assert lock.operation == "test_operation"

        repo.release_lock(lock)

    def test_acquire_lock_waits_for_active_lock(self, tmp_path, monkeypatch):
        """Should wait when another process holds lock."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        lock1 = repo.acquire_lock("operation1")
        assert not isinstance(lock1, RepoError)

        # Try to acquire with short timeout
        lock2 = repo.acquire_lock("operation2", timeout_ms=100)
        assert isinstance(lock2, RepoError)
        assert lock2.error_type == RepoErrorType.LOCK_TIMEOUT

        repo.release_lock(lock1)

    def test_acquire_lock_succeeds_after_release(self, tmp_path, monkeypatch):
        """Should acquire lock after previous lock is released."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        lock1 = repo.acquire_lock("operation1")
        assert not isinstance(lock1, RepoError)

        repo.release_lock(lock1)

        # Should succeed now
        lock2 = repo.acquire_lock("operation2")
        assert not isinstance(lock2, RepoError)

        repo.release_lock(lock2)

    def test_release_lock_removes_lock_file(self, tmp_path, monkeypatch):
        """Should remove lock file when released."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        lock = repo.acquire_lock("test_operation")
        assert not isinstance(lock, RepoError)

        lock_path = tmp_path / "config" / ".sync_lock"
        assert lock_path.exists()

        repo.release_lock(lock)

        assert not lock_path.exists()
