"""
Unit tests for M2 - Config & Secrets module.

Tests configuration loading, validation, and repository root detection.
"""

import pytest
import yaml
from pathlib import Path

from sports_coach_engine.core.config import ConfigError, get_repo_root, load_config
from sports_coach_engine.schemas.config import Config, ConfigErrorType


class TestGetRepoRoot:
    """Tests for get_repo_root function."""

    def test_get_repo_root_finds_git_directory(self):
        """Should find repo root via .git directory."""
        root = get_repo_root()
        assert (root / ".git").exists()

    def test_get_repo_root_finds_claude_md(self):
        """Should find repo root via CLAUDE.md."""
        root = get_repo_root()
        assert (root / "CLAUDE.md").exists()

    def test_get_repo_root_raises_when_not_in_repo(self, tmp_path, monkeypatch):
        """Should raise when not in repository."""
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError, match="Could not find repository root"):
            get_repo_root()


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_succeeds_with_valid_files(self, tmp_path, monkeypatch):
        """Should load valid config files."""
        # Setup config directory
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Write valid settings.yaml
        settings = {
            "paths": {
                "athlete_dir": "data/athlete",
                "activities_dir": "data/activities",
                "metrics_dir": "data/metrics",
                "plans_dir": "data/plans",
                "backup_dir": "data/backup",
            }
        }
        with open(config_dir / "settings.yaml", "w") as f:
            yaml.dump(settings, f)

        # Write valid secrets.local.yaml
        secrets = {
            "strava": {
                "client_id": "12345",
                "client_secret": "s" * 40,
                "access_token": "token",
                "refresh_token": "refresh",
                "token_expires_at": 1704067200,
            }
        }
        with open(config_dir / "secrets.local.yaml", "w") as f:
            yaml.dump(secrets, f)

        # Create .git to mark as repo root
        (tmp_path / ".git").mkdir()

        # Test
        monkeypatch.chdir(tmp_path)
        result = load_config()

        assert not isinstance(result, ConfigError)
        assert isinstance(result, Config)
        assert result.settings.paths.athlete_dir == "data/athlete"

    def test_load_config_error_missing_settings(self, tmp_path, monkeypatch):
        """Should return error when settings.yaml missing."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "config").mkdir()
        monkeypatch.chdir(tmp_path)

        result = load_config()

        assert isinstance(result, ConfigError)
        assert result.error_type == ConfigErrorType.FILE_NOT_FOUND

    def test_load_config_error_missing_secrets(self, tmp_path, monkeypatch):
        """Should return error when secrets.local.yaml missing."""
        (tmp_path / ".git").mkdir()
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create settings but not secrets
        settings = {"paths": {"athlete_dir": "data/athlete"}}
        with open(config_dir / "settings.yaml", "w") as f:
            yaml.dump(settings, f)

        monkeypatch.chdir(tmp_path)
        result = load_config()

        assert isinstance(result, ConfigError)
        assert result.error_type == ConfigErrorType.FILE_NOT_FOUND
        assert "secrets" in result.message.lower()

    def test_load_config_error_invalid_yaml(self, tmp_path, monkeypatch):
        """Should return error for malformed YAML."""
        (tmp_path / ".git").mkdir()
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Write invalid YAML
        (config_dir / "settings.yaml").write_text("invalid: yaml: content:")

        monkeypatch.chdir(tmp_path)
        result = load_config()

        assert isinstance(result, ConfigError)
        assert result.error_type == ConfigErrorType.PARSE_ERROR

    def test_load_config_uses_defaults_for_optional_fields(self, tmp_path, monkeypatch):
        """Should populate defaults for optional fields."""
        (tmp_path / ".git").mkdir()
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Minimal settings (use all defaults)
        settings = {}
        with open(config_dir / "settings.yaml", "w") as f:
            yaml.dump(settings, f)

        secrets = {
            "strava": {
                "client_id": "12345",
                "client_secret": "s" * 40,
                "access_token": "token",
                "refresh_token": "refresh",
                "token_expires_at": 1704067200,
            }
        }
        with open(config_dir / "secrets.local.yaml", "w") as f:
            yaml.dump(secrets, f)

        monkeypatch.chdir(tmp_path)
        result = load_config()

        assert not isinstance(result, ConfigError)
        # Check default values are populated
        assert result.settings.training_defaults.ctl_time_constant == 42
        assert result.settings.training_defaults.atl_time_constant == 7
        assert result.settings.paths.athlete_dir == "data/athlete"
