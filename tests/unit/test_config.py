"""Secret-safe runtime configuration tests."""

from pathlib import Path

import pytest

from resilio.core.config import ConfigError, get_repo_root, load_config
from resilio.schemas.config import Config, ConfigErrorType


def _settings(root: Path, content: str = "{}\n") -> None:
    (root / ".git").mkdir()
    (root / "config").mkdir()
    (root / "config" / "settings.yaml").write_text(content)


def test_get_repo_root_finds_repository() -> None:
    assert (get_repo_root() / ".git").exists()


def test_get_repo_root_raises_outside_repository(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        get_repo_root()


def test_explicit_fake_environment_loads_without_local_file(
    tmp_path,
    monkeypatch,
) -> None:
    _settings(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = load_config(environment={"INTERVALS_ICU_API_KEY": "fake-injected-test-key"})

    assert isinstance(result, Config)
    assert result.intervals_icu_api_key.get_secret_value() == "fake-injected-test-key"
    assert "fake-injected-test-key" not in repr(result)
    assert result.settings.intervals_icu.initial_window_days == 90


def test_omitted_environment_reads_env_local_without_mutating_process(
    tmp_path,
    monkeypatch,
) -> None:
    _settings(tmp_path)
    (tmp_path / ".env.local").write_text("INTERVALS_ICU_API_KEY=local-test-value\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("INTERVALS_ICU_API_KEY", raising=False)

    result = load_config()

    assert isinstance(result, Config)
    assert result.intervals_icu_api_key.get_secret_value() == "local-test-value"
    assert "INTERVALS_ICU_API_KEY" not in __import__("os").environ


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({}, "missing or empty"),
        ({"INTERVALS_ICU_API_KEY": "   "}, "missing or empty"),
    ],
)
def test_missing_injected_key_is_typed_and_redacted(
    tmp_path,
    monkeypatch,
    environment,
    message,
) -> None:
    _settings(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = load_config(environment=environment)

    assert isinstance(result, ConfigError)
    assert result.error_type == ConfigErrorType.MISSING_SECRET
    assert message in result.message


def test_missing_env_local_is_typed(tmp_path, monkeypatch) -> None:
    _settings(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = load_config()

    assert isinstance(result, ConfigError)
    assert result.error_type == ConfigErrorType.MISSING_SECRET
    assert ".env.local" in result.message


def test_missing_settings_and_invalid_yaml_are_distinct(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "config").mkdir()
    monkeypatch.chdir(tmp_path)
    missing = load_config(environment={"INTERVALS_ICU_API_KEY": "fake"})
    assert isinstance(missing, ConfigError)
    assert missing.error_type == ConfigErrorType.FILE_NOT_FOUND

    (tmp_path / "config" / "settings.yaml").write_text("not: [valid\n")
    malformed = load_config(environment={"INTERVALS_ICU_API_KEY": "fake"})
    assert isinstance(malformed, ConfigError)
    assert malformed.error_type == ConfigErrorType.PARSE_ERROR


def test_unknown_settings_are_rejected(tmp_path, monkeypatch) -> None:
    _settings(tmp_path, "unknown_section: true\n")
    monkeypatch.chdir(tmp_path)

    result = load_config(environment={"INTERVALS_ICU_API_KEY": "fake"})

    assert isinstance(result, ConfigError)
    assert result.error_type == ConfigErrorType.VALIDATION_ERROR
