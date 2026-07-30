"""
Unit tests for M3 - Repository I/O module.

Tests file I/O operations, path resolution, and error handling.
"""

from pathlib import Path

import pytest
from pydantic import BaseModel

from resilio.core.repository import RepositoryIO
from resilio.core.state_permissions import (
    StatePermissionError,
    harden_sensitive_state_permissions,
)
from resilio.schemas.repository import ReadOptions, RepoError, RepoErrorType


# Test schema
class ExampleSchema(BaseModel):
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
        result = repo.read_yaml("test.yaml", ExampleSchema)

        assert not isinstance(result, RepoError)
        assert result.name == "test"
        assert result.value == 42

    def test_read_yaml_returns_none_when_allow_missing(self, tmp_path, monkeypatch):
        """Should return None for missing file when allow_missing=True."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        result = repo.read_yaml(
            "missing.yaml",
            ExampleSchema,
            ReadOptions(allow_missing=True),
        )

        assert result is None

    def test_read_yaml_returns_error_when_file_missing(self, tmp_path, monkeypatch):
        """Should return error for missing file when allow_missing=False."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        result = repo.read_yaml("missing.yaml", ExampleSchema)

        assert isinstance(result, RepoError)
        assert result.error_type == RepoErrorType.FILE_NOT_FOUND

    def test_read_yaml_returns_error_for_invalid_yaml(self, tmp_path, monkeypatch):
        """Should return error for malformed YAML."""
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "invalid.yaml"
        test_file.write_text("invalid: yaml: content:")

        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        result = repo.read_yaml("invalid.yaml", ExampleSchema)

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

        result = repo.read_yaml("bad_data.yaml", ExampleSchema)

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

        data = ExampleSchema(name="test", value=42)
        error = repo.write_yaml("output.yaml", data)

        assert error is None
        assert (tmp_path / "output.yaml").exists()

        # Verify content
        result = repo.read_yaml("output.yaml", ExampleSchema)
        assert not isinstance(result, RepoError)
        assert result.name == "test"
        assert result.value == 42

    def test_write_yaml_creates_parent_directories(self, tmp_path, monkeypatch):
        """Should create parent directories if they don't exist."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        data = ExampleSchema(name="test", value=42)
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

        data = ExampleSchema(name="new", value=99)
        error = repo.write_yaml("output.yaml", data)

        assert error is None

        # Verify new content
        result = repo.read_yaml("output.yaml", ExampleSchema)
        assert not isinstance(result, RepoError)
        assert result.name == "new"
        assert result.value == 99


def test_sensitive_state_permission_migration_is_idempotent(
    tmp_path: Path,
) -> None:
    profile_directory = tmp_path / "data/athlete"
    profile_directory.mkdir(parents=True, mode=0o755)
    profile_path = profile_directory / "profile.yaml"
    profile_path.write_text("athlete_name: private\n")
    profile_path.chmod(0o644)

    first = harden_sensitive_state_permissions(tmp_path)
    second = harden_sensitive_state_permissions(tmp_path)

    assert first.directories_hardened == 2
    assert first.files_hardened == 1
    assert second == first
    assert profile_directory.stat().st_mode & 0o777 == 0o700
    assert profile_path.stat().st_mode & 0o777 == 0o600


def test_sensitive_state_permission_migration_rejects_symlinks(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside\n")
    outside_file.chmod(0o644)
    (data_root / "unsafe-link").symlink_to(outside_file)

    with pytest.raises(StatePermissionError, match="cannot be a symlink"):
        harden_sensitive_state_permissions(tmp_path)

    assert outside_file.stat().st_mode & 0o777 == 0o644


def test_repository_preserves_private_modes_for_new_state_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()

    error = repo.write_yaml(
        "data/athlete/history/profile.yaml",
        ExampleSchema(name="private", value=42),
    )

    assert error is None
    for directory in (
        tmp_path / "data",
        tmp_path / "data/athlete",
        tmp_path / "data/athlete/history",
    ):
        assert directory.stat().st_mode & 0o777 == 0o700
    assert (
        tmp_path / "data/athlete/history/profile.yaml"
    ).stat().st_mode & 0o777 == 0o600
