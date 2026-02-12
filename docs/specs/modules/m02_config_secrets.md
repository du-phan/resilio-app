# M2 - Config & Secrets

## Module Metadata

| Field | Value |
|-------|-------|
| **Module ID** | M2 |
| **Module Name** | Config & Secrets |
| **Code Module** | `core/config.py` |
| **Version** | 1.0.2 |
| **Status** | Draft |
| **Complexity** | Low |
| **Last Updated** | 2026-01-12 |

### Changelog
- **1.0.2** (2026-01-12): Added code module path (`core/config.py`) and API layer integration notes
- **1.0.1** (2026-01-12): Added `ConversationLoggerSettings` for M14 configuration (two-tier retention, summary generation settings)
- **1.0.0** (initial): Initial draft with core config/secrets types

---

## 1. Purpose & Scope

### 1.1 Purpose

M2 is responsible for loading, validating, and providing access to application configuration and secrets. It serves as the single source of truth for all configuration values, ensuring consistent access patterns across the system.

### 1.2 Scope Boundaries

**This module DOES:**
- Load `config/settings.yaml` (non-secret configuration)
- Load `config/secrets.local.yaml` (Strava tokens, credentials)
- Support environment variable overrides
- Validate required configuration keys
- Refresh Strava OAuth tokens when expired
- Provide typed configuration objects to other modules

**This module does NOT:**
- Persist configuration changes (read-only for most flows)
- Handle user preferences (that's M4 - Athlete Profile)
- Manage training-related settings (those belong in profile)

---

## 2. Dependencies

### 2.1 Internal Module Dependencies

| Module | Dependency Type | Purpose |
|--------|-----------------|---------|
| None | - | M2 is a foundation module with no internal dependencies |

### 2.2 External Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `pyyaml` | ^6.0 | Parse YAML configuration files |
| `pydantic` | ^2.5 | Runtime schema validation and data classes |
| `httpx` | ^0.25 | Strava token refresh HTTP calls (async support) |

### 2.3 Environment Requirements

- Python >= 3.11
- File system read access to `config/` directory
- Network access for Strava token refresh (optional, only when tokens expire)

---

## 3. Internal Interface

**Note:** This module is called internally by other core modules and the API layer. Claude Code should NOT import from `core/config.py` directly for configuration access.

### 3.1 Type Definitions

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field


# ============================================================
# CONFIGURATION TYPES
# ============================================================

class PathSettings(BaseModel):
    """File path configuration (relative to repo root)."""
    athlete_dir: str = "athlete"
    activities_dir: str = "activities"
    metrics_dir: str = "metrics"
    plans_dir: str = "plans"


class StravaSettings(BaseModel):
    """Strava API configuration."""
    api_base_url: str = "https://www.strava.com/api/v3"
    auth_url: str = "https://www.strava.com/oauth/authorize"
    token_url: str = "https://www.strava.com/oauth/token"
    scopes: list[str] = Field(default_factory=lambda: ["read", "activity:read_all"])
    history_import_weeks: int = 12


class TrainingDefaults(BaseModel):
    """Training calculation defaults."""
    ctl_time_constant: int = 42  # days (Chronic Training Load)
    atl_time_constant: int = 7   # days (Acute Training Load)
    acwr_acute_window: int = 7   # days
    acwr_chronic_window: int = 28  # days
    baseline_days_threshold: int = 14
    acwr_minimum_days: int = 28


class SystemSettings(BaseModel):
    """System configuration."""
    lock_timeout_ms: int = 300_000  # 5 minutes
    lock_retry_count: int = 3
    lock_retry_delay_ms: int = 2_000
    metrics_stale_hours: int = 24


class Settings(BaseModel):
    """Complete settings configuration."""
    paths: PathSettings = Field(default_factory=PathSettings)
    strava: StravaSettings = Field(default_factory=StravaSettings)
    training_defaults: TrainingDefaults = Field(default_factory=TrainingDefaults)
    system: SystemSettings = Field(default_factory=SystemSettings)


class StravaSecrets(BaseModel):
    """Strava authentication secrets."""
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    token_expires_at: int  # Unix timestamp


class Secrets(BaseModel):
    """All application secrets."""
    strava: StravaSecrets


class Config(BaseModel):
    """Complete application configuration."""
    settings: Settings
    secrets: Secrets
    loaded_at: datetime


# ============================================================
# TOKEN TYPES
# ============================================================

class StravaTokenResponse(BaseModel):
    """Response from Strava OAuth token endpoint."""
    access_token: str
    refresh_token: str
    expires_at: int
    expires_in: int
    token_type: str


# ============================================================
# VALIDATION TYPES
# ============================================================

@dataclass
class ValidationError:
    """Single validation error."""
    field: str
    message: str
    value: Optional[str] = None


@dataclass
class ValidationWarning:
    """Single validation warning."""
    field: str
    message: str
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationWarning] = field(default_factory=list)


# ============================================================
# ERROR TYPES
# ============================================================

class ConfigErrorType(Enum):
    """Types of configuration errors."""
    FILE_NOT_FOUND = "file_not_found"
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    MISSING_SECRET = "missing_secret"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"
    NETWORK_ERROR = "network_error"


@dataclass
class ConfigError:
    """Configuration error with details."""
    error_type: ConfigErrorType
    message: str
    path: Optional[str] = None
    field: Optional[str] = None
    details: Optional[dict] = None


# Type alias for results
ConfigResult = Union[Config, ConfigError]
SettingsResult = Union[Settings, ConfigError]
TokenResult = Union[StravaTokenResponse, ConfigError]
```

### 3.2 Public Functions

```python
from pathlib import Path
from typing import Optional, TypeVar, Union

T = TypeVar('T')


# ============================================================
# CONFIGURATION LOADING
# ============================================================

def load_config(repo_root: Optional[Path] = None) -> ConfigResult:
    """
    Load and validate the complete configuration.

    This is the primary entry point for configuration access.

    Args:
        repo_root: Repository root directory (auto-detected if None)

    Returns:
        Config object or ConfigError

    Load order:
        1. Load settings.yaml (fail if missing)
        2. Apply environment variable overrides
        3. Load secrets.local.yaml (fail if missing)
        4. Apply secret environment variable overrides
        5. Validate all required fields
    """
    ...


def load_settings(repo_root: Optional[Path] = None) -> SettingsResult:
    """
    Load only the settings (non-secret configuration).

    Useful for initialization when secrets aren't needed yet.
    """
    ...


def validate_secrets(secrets: Secrets) -> ValidationResult:
    """
    Validate that all required secrets are present and well-formed.

    Does NOT validate that tokens are actually valid with Strava.
    """
    ...


# ============================================================
# TOKEN MANAGEMENT
# ============================================================

def is_token_expired(secrets: StravaSecrets, buffer_seconds: int = 300) -> bool:
    """
    Check if the current Strava access token is expired or about to expire.

    Args:
        secrets: Strava secrets containing token_expires_at
        buffer_seconds: Time buffer before expiration (default: 300 = 5 min)

    Returns:
        True if token needs refresh
    """
    ...


async def refresh_strava_token(
    secrets: StravaSecrets,
    settings: StravaSettings
) -> TokenResult:
    """
    Refresh the Strava access token using the refresh token.

    Updates secrets.local.yaml with new tokens.

    Args:
        secrets: Current Strava secrets with refresh_token
        settings: Strava settings with token_url

    Returns:
        New token response or ConfigError

    Process:
        1. Call Strava OAuth token endpoint with refresh_token
        2. Parse response for new access_token, refresh_token, expires_at
        3. Update secrets.local.yaml atomically
        4. Return new token data
    """
    ...


async def get_valid_strava_token(config: Config) -> Union[str, ConfigError]:
    """
    Get a valid Strava access token, refreshing if necessary.

    This is the recommended way to get a token for API calls.
    """
    ...


# ============================================================
# FILE UPDATES (FOR TOKEN REFRESH)
# ============================================================

async def update_secrets_file(
    token_response: StravaTokenResponse,
    repo_root: Optional[Path] = None
) -> Union[bool, ConfigError]:
    """
    Atomically update secrets.local.yaml with new token data.

    Args:
        token_response: New token data from Strava
        repo_root: Repository root (auto-detected if None)

    Returns:
        True on success, ConfigError on failure

    Process:
        1. Read current secrets.local.yaml
        2. Update only token fields (preserve client_id/client_secret)
        3. Write atomically (temp file + rename)
        4. Verify write succeeded
    """
    ...


# ============================================================
# ENVIRONMENT VARIABLE HELPERS
# ============================================================

def apply_env_overrides(data: dict, env_map: dict[str, str]) -> dict:
    """
    Apply environment variable overrides to config data.

    Used internally by load_config.

    Args:
        data: Configuration dict to update
        env_map: Mapping of env var names to config paths

    Returns:
        Updated data dict
    """
    ...


def parse_value(value: str) -> Any:
    """
    Parse string environment variable value to appropriate type.

    Tries: int → bool → str (fallback)
    """
    ...


def set_nested_value(data: dict, path: str, value: Any) -> None:
    """
    Set a value at a nested dot-notation path (e.g., 'strava.client_id').

    Creates intermediate dicts as needed.
    """
    ...


def get_config_value(
    key: str,
    env_var: str,
    default: Optional[T] = None
) -> Optional[T]:
    """
    Get a configuration value with environment variable override support.

    Environment variables take precedence over file values.

    Args:
        key: Dot-notation path (e.g., "strava.client_id")
        env_var: Environment variable name to check
        default: Fallback if neither source has value

    Returns:
        Configuration value or default
    """
    ...


def get_repo_root() -> Path:
    """
    Determine the repository root directory.

    Walks up from current working directory looking for:
    1. .git directory
    2. CLAUDE.md file

    Returns:
        Path to repository root

    Raises:
        FileNotFoundError: If root cannot be determined (walked to filesystem root)
    """
    ...
```

---

## 4. Data Structures

### 4.1 Owned Files

M2 owns the following files (read-only access except for token refresh):

#### `config/settings.yaml`

```yaml
# Resilio Configuration
# Non-secret settings for the application

# File paths (relative to repository root)
paths:
  athlete_dir: "athlete"
  activities_dir: "activities"
  metrics_dir: "metrics"
  plans_dir: "plans"

# Strava API configuration
strava:
  api_base_url: "https://www.strava.com/api/v3"
  auth_url: "https://www.strava.com/oauth/authorize"
  token_url: "https://www.strava.com/oauth/token"
  scopes:
    - "read"
    - "activity:read_all"
  history_import_weeks: 12  # How many weeks to import on first setup

# Training calculation defaults
training_defaults:
  ctl_time_constant: 42      # days (Chronic Training Load)
  atl_time_constant: 7       # days (Acute Training Load)
  acwr_acute_window: 7       # days
  acwr_chronic_window: 28    # days
  baseline_days_threshold: 14  # days before baseline_established = true
  acwr_minimum_days: 28      # minimum days before ACWR is calculated

# System settings
system:
  lock_timeout_ms: 300000    # 5 minutes
  lock_retry_count: 3
  lock_retry_delay_ms: 2000
  metrics_stale_hours: 24
```

#### `config/secrets.local.yaml`

```yaml
# SENSITIVE - DO NOT COMMIT
# This file should be in .gitignore

strava:
  client_id: "YOUR_CLIENT_ID"
  client_secret: "YOUR_CLIENT_SECRET"
  access_token: "YOUR_ACCESS_TOKEN"
  refresh_token: "YOUR_REFRESH_TOKEN"
  token_expires_at: 1704067200  # Unix timestamp
```

### 4.2 Environment Variable Mapping

| Environment Variable | Config Path | Description |
|---------------------|-------------|-------------|
| `RESILIO_STRAVA_CLIENT_ID` | `secrets.strava.client_id` | Strava OAuth client ID |
| `RESILIO_STRAVA_CLIENT_SECRET` | `secrets.strava.client_secret` | Strava OAuth client secret |
| `RESILIO_STRAVA_ACCESS_TOKEN` | `secrets.strava.access_token` | Current access token |
| `RESILIO_STRAVA_REFRESH_TOKEN` | `secrets.strava.refresh_token` | Token for refresh |
| `RESILIO_STRAVA_TOKEN_EXPIRES_AT` | `secrets.strava.token_expires_at` | Token expiration timestamp |
| `RESILIO_HISTORY_IMPORT_WEEKS` | `settings.strava.history_import_weeks` | Initial import depth |

### 4.3 Validation Rules

#### Required Fields (Settings)

| Field | Validation | Default |
|-------|------------|---------|
| `paths.*` | Non-empty string | As shown above |
| `strava.api_base_url` | Valid URL | `https://www.strava.com/api/v3` |
| `training_defaults.ctl_time_constant` | Integer > 0 | 42 |
| `training_defaults.atl_time_constant` | Integer > 0 | 7 |

#### Required Fields (Secrets)

| Field | Validation | Required? |
|-------|------------|-----------|
| `strava.client_id` | Non-empty string, numeric | Yes |
| `strava.client_secret` | Non-empty string, 40 chars | Yes |
| `strava.access_token` | Non-empty string | Yes |
| `strava.refresh_token` | Non-empty string | Yes |
| `strava.token_expires_at` | Integer (Unix timestamp) | Yes |

---

## 5. Core Algorithms

### 5.1 Configuration Loading Algorithm

```python
def load_config(repo_root: Path | None = None) -> ConfigResult:
    """Configuration loading algorithm."""

    # 1. Determine config directory path
    if repo_root is None:
        repo_root = get_repo_root()
    config_dir = repo_root / "config"

    # 2. Load settings
    settings_path = config_dir / "settings.yaml"
    if not settings_path.exists():
        return ConfigError(
            error_type=ConfigErrorType.FILE_NOT_FOUND,
            message="Configuration file not found",
            path=str(settings_path)
        )

    try:
        with open(settings_path) as f:
            settings_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return ConfigError(
            error_type=ConfigErrorType.PARSE_ERROR,
            message=str(e),
            path=str(settings_path)
        )

    # 3. Apply environment variable overrides
    settings_data = apply_env_overrides(settings_data, SETTINGS_ENV_MAP)

    # 4. Validate and create Settings object
    try:
        settings = Settings.model_validate(settings_data or {})
    except ValidationError as e:
        return ConfigError(
            error_type=ConfigErrorType.VALIDATION_ERROR,
            message="Settings validation failed",
            details={"errors": e.errors()}
        )

    # 5. Load secrets (similar process)
    secrets_path = config_dir / "secrets.local.yaml"
    if not secrets_path.exists():
        return ConfigError(
            error_type=ConfigErrorType.FILE_NOT_FOUND,
            message="Secrets file not found",
            path=str(secrets_path)
        )

    # ... similar loading and validation for secrets

    # 6. Return complete config
    return Config(
        settings=settings,
        secrets=secrets,
        loaded_at=datetime.now()
    )
```

### 5.2 Token Refresh Algorithm

```python
async def refresh_strava_token(
    secrets: StravaSecrets,
    settings: StravaSettings
) -> TokenResult:
    """Token refresh algorithm."""

    # 1. Prepare refresh request
    payload = {
        "client_id": secrets.client_id,
        "client_secret": secrets.client_secret,
        "refresh_token": secrets.refresh_token,
        "grant_type": "refresh_token"
    }

    # 2. Call Strava token endpoint
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                settings.token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        except httpx.RequestError as e:
            return ConfigError(
                error_type=ConfigErrorType.NETWORK_ERROR,
                message=f"Network error: {e}"
            )

    # 3. Handle response
    if response.status_code == 200:
        token_data = response.json()
        token_response = StravaTokenResponse.model_validate(token_data)

        # 4. Update secrets file atomically
        await update_secrets_file(token_response)

        return token_response
    else:
        return ConfigError(
            error_type=ConfigErrorType.TOKEN_REFRESH_FAILED,
            message=f"Token refresh failed: {response.status_code}",
            details={"response": response.text}
        )
```

### 5.3 Environment Variable Override Logic

```python
import os
from typing import Any

SETTINGS_ENV_MAP = {
    "RESILIO_HISTORY_IMPORT_WEEKS": "strava.history_import_weeks",
}

SECRETS_ENV_MAP = {
    "RESILIO_STRAVA_CLIENT_ID": "strava.client_id",
    "RESILIO_STRAVA_CLIENT_SECRET": "strava.client_secret",
    "RESILIO_STRAVA_ACCESS_TOKEN": "strava.access_token",
    "RESILIO_STRAVA_REFRESH_TOKEN": "strava.refresh_token",
    "RESILIO_STRAVA_TOKEN_EXPIRES_AT": "strava.token_expires_at",
}


def apply_env_overrides(data: dict, env_map: dict[str, str]) -> dict:
    """Apply environment variable overrides to config data."""

    for env_var, config_path in env_map.items():
        value = os.environ.get(env_var)
        if value is not None:
            set_nested_value(data, config_path, parse_value(value))

    return data


def parse_value(value: str) -> Any:
    """Parse string value to appropriate type."""

    # Try integer
    try:
        return int(value)
    except ValueError:
        pass

    # Try boolean
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    # Return as string
    return value


def set_nested_value(data: dict, path: str, value: Any) -> None:
    """Set a value at a nested path (e.g., 'strava.client_id')."""

    keys = path.split(".")
    current = data

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value
```

### 5.4 Repository Root Detection Algorithm

```python
from pathlib import Path


def get_repo_root() -> Path:
    """
    Find repository root by walking up from current directory.

    Algorithm:
        1. Start at current working directory
        2. Check if .git directory exists
        3. If not, check if CLAUDE.md exists
        4. If found, return current path
        5. If not found, move to parent directory
        6. Repeat until filesystem root or match found
        7. If reached filesystem root without match, raise FileNotFoundError
    """
    current = Path.cwd()

    while True:
        # Check for .git directory
        if (current / ".git").exists():
            return current

        # Check for CLAUDE.md
        if (current / "CLAUDE.md").exists():
            return current

        # Move to parent
        parent = current.parent

        # If we've reached filesystem root, fail
        if parent == current:
            raise FileNotFoundError(
                "Could not find repository root (.git or CLAUDE.md not found). "
                "Are you running from within the repository?"
            )

        current = parent
```

### 5.5 Secrets File Update Algorithm

```python
import yaml
from pathlib import Path


async def update_secrets_file(
    token_response: StravaTokenResponse,
    repo_root: Optional[Path] = None
) -> Union[bool, ConfigError]:
    """
    Atomically update secrets.local.yaml with refreshed token data.

    Uses temp file + rename pattern for atomic writes (same as M3).
    """
    # 1. Determine secrets file path
    if repo_root is None:
        repo_root = get_repo_root()
    secrets_path = repo_root / "config" / "secrets.local.yaml"

    # 2. Read current secrets
    try:
        with open(secrets_path) as f:
            secrets_data = yaml.safe_load(f)
    except FileNotFoundError:
        return ConfigError(
            error_type=ConfigErrorType.FILE_NOT_FOUND,
            message="Secrets file not found",
            path=str(secrets_path)
        )

    # 3. Update only token fields (preserve client_id/client_secret)
    secrets_data["strava"]["access_token"] = token_response.access_token
    secrets_data["strava"]["refresh_token"] = token_response.refresh_token
    secrets_data["strava"]["token_expires_at"] = token_response.expires_at

    # 4. Write atomically using temp file + rename
    temp_path = secrets_path.with_suffix(".tmp")
    try:
        with open(temp_path, "w") as f:
            yaml.safe_dump(secrets_data, f, sort_keys=False)

        # Atomic rename (POSIX guarantees atomicity on same filesystem)
        temp_path.rename(secrets_path)

        return True

    except Exception as e:
        # Clean up temp file on failure
        if temp_path.exists():
            temp_path.unlink()

        return ConfigError(
            error_type=ConfigErrorType.VALIDATION_ERROR,
            message=f"Failed to update secrets file: {e}",
            path=str(secrets_path)
        )
```

---

## 6. Error Handling

### 6.1 Error Scenarios

| Scenario | Error Type | Recovery Action |
|----------|------------|-----------------|
| `settings.yaml` not found | `FILE_NOT_FOUND` | Fatal - user must create config |
| `secrets.local.yaml` not found | `FILE_NOT_FOUND` | Fatal - guide user through setup |
| Invalid YAML syntax | `PARSE_ERROR` | Show line/column of error |
| Missing required field | `VALIDATION_ERROR` | List all missing fields |
| Token refresh fails (401) | `TOKEN_REFRESH_FAILED` | Prompt re-authentication |
| Token refresh fails (network) | `NETWORK_ERROR` | Retry with backoff |

### 6.2 User-Facing Error Messages

```python
ERROR_MESSAGES: dict[ConfigErrorType, str] = {
    ConfigErrorType.FILE_NOT_FOUND: "Configuration file not found: {path}. Run setup to create it.",
    ConfigErrorType.PARSE_ERROR: "Invalid YAML in {path}: {message}",
    ConfigErrorType.VALIDATION_ERROR: "Configuration validation failed:\n{errors}",
    ConfigErrorType.MISSING_SECRET: "Missing required secret: {field}. Check config/secrets.local.yaml",
    ConfigErrorType.TOKEN_REFRESH_FAILED: "Could not refresh Strava token: {message}. Please re-authenticate.",
    ConfigErrorType.NETWORK_ERROR: "Network error during token refresh: {message}. Check your connection.",
}


def format_error(error: ConfigError) -> str:
    """Format a ConfigError for user display."""
    template = ERROR_MESSAGES.get(error.error_type, "Unknown error: {message}")
    return template.format(
        path=error.path or "",
        message=error.message,
        field=error.field or "",
        errors=error.details.get("errors", []) if error.details else []
    )
```

### 6.3 Recovery Strategies

1. **File Not Found**: Cannot recover automatically. Display setup instructions.
2. **Parse Error**: Cannot recover automatically. Show exact error location.
3. **Validation Error**: Show all errors at once (don't fail on first).
4. **Token Refresh Failed**:
   - If 401: Tokens are invalid, prompt re-authentication
   - If network error: Retry up to 3 times with 2s delay
5. **Stale Token on API Call**: Automatically attempt refresh before failing

---

## 7. Integration Points

### 7.1 Integration with API Layer

This module is called internally by core modules and the API layer. Claude Code does NOT call M2 directly.

```
API Layer → M1 (workflows) → M5 (strava) → M2::get_valid_strava_token()
                           → M9 (metrics) → M2::load_config()
```

### 7.2 How Other Modules Call M2

```python
from resilio.core.config import load_config, get_valid_strava_token, ConfigError

# M1, M5, and others call load_config() at startup
config = load_config()
if isinstance(config, ConfigError):
    # Handle error
    raise ConfigurationException(format_error(config))

# M5 (Strava Integration) gets Strava token
token = await get_valid_strava_token(config)
if isinstance(token, ConfigError):
    # Handle token error - may need re-auth
    pass

# Access configuration values
api_base_url = config.settings.strava.api_base_url
ctl_time_constant = config.settings.training_defaults.ctl_time_constant
```

### 7.3 Module Dependencies (Who Calls M2)

| Module | Usage |
|--------|-------|
| API Layer | Initialize configuration for API functions |
| M1 (Workflows) | Load config at workflow startup |
| M3 (Repository I/O) | Get path settings |
| M5 (Strava Integration) | Get Strava tokens and API config |
| M9 (Metrics Engine) | Get CTL/ATL time constants |

### 7.4 Events/Hooks

M2 does not emit events. It is a synchronous configuration provider (except for async token refresh).

---

## 8. Test Scenarios

### 8.1 Unit Tests

```python
import pytest
from pathlib import Path
from resilio.m02_config import (
    load_config, validate_secrets, refresh_strava_token,
    is_token_expired, ConfigError, ConfigErrorType
)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_valid_settings_and_secrets(self, tmp_path: Path):
        """Should load valid config files."""
        # Setup: Create valid config files
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        # ... create settings.yaml and secrets.local.yaml

        result = load_config(tmp_path)

        assert not isinstance(result, ConfigError)
        assert result.settings.strava.api_base_url == "https://www.strava.com/api/v3"

    def test_returns_file_not_found_when_settings_missing(self, tmp_path: Path):
        """Should return error when settings.yaml is missing."""
        result = load_config(tmp_path)

        assert isinstance(result, ConfigError)
        assert result.error_type == ConfigErrorType.FILE_NOT_FOUND

    def test_returns_parse_error_for_invalid_yaml(self, tmp_path: Path):
        """Should return error for malformed YAML."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "settings.yaml").write_text("invalid: yaml: content:")

        result = load_config(tmp_path)

        assert isinstance(result, ConfigError)
        assert result.error_type == ConfigErrorType.PARSE_ERROR

    def test_applies_environment_variable_overrides(self, tmp_path: Path, monkeypatch):
        """Should use env vars over file values."""
        # Setup config files
        monkeypatch.setenv("RESILIO_STRAVA_CLIENT_ID", "env_client_id")

        result = load_config(tmp_path)

        assert result.secrets.strava.client_id == "env_client_id"

    def test_applies_default_values_for_missing_optional_fields(self, tmp_path: Path):
        """Should populate defaults for optional fields."""
        # Create minimal settings.yaml
        result = load_config(tmp_path)

        assert result.settings.training_defaults.ctl_time_constant == 42


class TestValidateSecrets:
    """Tests for validate_secrets function."""

    def test_returns_valid_for_complete_secrets(self):
        """Should validate complete secrets."""
        secrets = Secrets(strava=StravaSecrets(
            client_id="123",
            client_secret="x" * 40,
            access_token="token",
            refresh_token="refresh",
            token_expires_at=1704067200
        ))

        result = validate_secrets(secrets)

        assert result.valid
        assert len(result.errors) == 0


class TestIsTokenExpired:
    """Tests for is_token_expired function."""

    def test_returns_true_when_token_expired(self):
        """Should detect expired token."""
        secrets = StravaSecrets(
            client_id="123",
            client_secret="secret",
            access_token="token",
            refresh_token="refresh",
            token_expires_at=int((datetime.now() - timedelta(hours=1)).timestamp())
        )

        assert is_token_expired(secrets) is True

    def test_returns_true_within_buffer(self):
        """Should consider token expired within buffer time."""
        secrets = StravaSecrets(
            client_id="123",
            client_secret="secret",
            access_token="token",
            refresh_token="refresh",
            token_expires_at=int((datetime.now() + timedelta(seconds=60)).timestamp())
        )

        assert is_token_expired(secrets, buffer_seconds=300) is True

    def test_returns_false_when_token_valid(self):
        """Should recognize valid token."""
        secrets = StravaSecrets(
            client_id="123",
            client_secret="secret",
            access_token="token",
            refresh_token="refresh",
            token_expires_at=int((datetime.now() + timedelta(hours=1)).timestamp())
        )

        assert is_token_expired(secrets) is False


@pytest.mark.asyncio
class TestRefreshStravaToken:
    """Tests for refresh_strava_token function."""

    async def test_refreshes_token_successfully(self, httpx_mock):
        """Should refresh token and return new data."""
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            json={
                "access_token": "new_token",
                "refresh_token": "new_refresh",
                "expires_at": 1704067200,
                "expires_in": 21600,
                "token_type": "Bearer"
            }
        )

        result = await refresh_strava_token(secrets, settings)

        assert not isinstance(result, ConfigError)
        assert result.access_token == "new_token"

    async def test_returns_error_for_401_response(self, httpx_mock):
        """Should handle authentication failure."""
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            status_code=401
        )

        result = await refresh_strava_token(secrets, settings)

        assert isinstance(result, ConfigError)
        assert result.error_type == ConfigErrorType.TOKEN_REFRESH_FAILED
```

### 8.2 Integration Tests

```python
import pytest
from pathlib import Path


class TestConfigIntegration:
    """End-to-end tests with real file I/O."""

    def test_full_config_load_flow(self, tmp_path: Path):
        """Test complete load flow with files."""
        # Setup: Create valid config directory
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Write settings.yaml
        settings_content = """
paths:
  athlete_dir: "athlete"
  activities_dir: "activities"
strava:
  api_base_url: "https://www.strava.com/api/v3"
training_defaults:
  ctl_time_constant: 42
  atl_time_constant: 7
"""
        (config_dir / "settings.yaml").write_text(settings_content)

        # Write secrets.local.yaml
        secrets_content = """
strava:
  client_id: "12345"
  client_secret: "abcdefghijklmnopqrstuvwxyz1234567890abcd"
  access_token: "token123"
  refresh_token: "refresh123"
  token_expires_at: 1704067200
"""
        (config_dir / "secrets.local.yaml").write_text(secrets_content)

        # Load config
        result = load_config(tmp_path)

        # Verify
        assert not isinstance(result, ConfigError)
        assert result.settings.paths.athlete_dir == "athlete"
        assert result.secrets.strava.client_id == "12345"

    @pytest.mark.asyncio
    async def test_token_refresh_updates_file(self, tmp_path: Path, httpx_mock):
        """Test that token refresh actually updates secrets.local.yaml."""
        # Setup config files
        # ... (similar to above)

        # Mock Strava token endpoint
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            json={
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_at": 1704153600,
                "expires_in": 21600,
                "token_type": "Bearer"
            }
        )

        # Load config
        config = load_config(tmp_path)

        # Refresh token
        result = await refresh_strava_token(
            config.secrets.strava,
            config.settings.strava
        )

        # Verify token was updated in file
        updated_config = load_config(tmp_path)
        assert updated_config.secrets.strava.access_token == "new_access_token"
        assert updated_config.secrets.strava.refresh_token == "new_refresh_token"


class TestConcurrentTokenRefresh:
    """Tests for concurrent token refresh scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_refresh_attempts_are_safe(self, tmp_path: Path, httpx_mock):
        """Multiple concurrent refresh calls should not corrupt secrets file."""
        # Setup
        config = load_config(tmp_path)

        # Mock response
        httpx_mock.add_response(
            url="https://www.strava.com/oauth/token",
            json={
                "access_token": "concurrent_token",
                "refresh_token": "concurrent_refresh",
                "expires_at": 1704067200,
                "expires_in": 21600,
                "token_type": "Bearer"
            }
        )

        # Launch 3 concurrent refresh attempts
        results = await asyncio.gather(
            refresh_strava_token(config.secrets.strava, config.settings.strava),
            refresh_strava_token(config.secrets.strava, config.settings.strava),
            refresh_strava_token(config.secrets.strava, config.settings.strava),
        )

        # All should succeed
        assert all(not isinstance(r, ConfigError) for r in results)

        # File should be intact (not corrupted)
        final_config = load_config(tmp_path)
        assert not isinstance(final_config, ConfigError)
        assert final_config.secrets.strava.access_token == "concurrent_token"

    @pytest.mark.asyncio
    async def test_token_refresh_during_active_api_call(self, tmp_path: Path):
        """Token refresh while API call is in progress should not break file."""
        # This tests the atomic write behavior
        # ... implementation would test file integrity during concurrent read/write
        pass
```

### 8.3 Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Empty settings.yaml | Use all defaults |
| secrets.local.yaml has extra fields | Ignore extra fields (Pydantic behavior) |
| Environment variable is empty string | Treat as not set |
| Token expires during operation | Refresh before failing |
| Concurrent config loads | Safe (read-only) |
| Concurrent token refresh attempts | Last write wins (atomic rename ensures no corruption) |
| Token refresh fails mid-write | Temp file cleaned up, original secrets.local.yaml unchanged |
| Parent directory doesn't exist for temp file | Create intermediate directories or fail gracefully |

---

## 9. Implementation Notes

### 9.1 File Location Strategy

All configuration files are located in `config/` at the repository root:
- `config/settings.yaml` - Committed to git (non-secret)
- `config/secrets.local.yaml` - NOT committed (in .gitignore)

### 9.2 Security Considerations

1. **Never log secret values** - Log field names but not values
2. **secrets.local.yaml must be in .gitignore** - Verify on every load
3. **Environment variables for CI/CD** - Support for deployment without files
4. **Token refresh writes atomically** - Prevent partial updates

### 9.3 Performance Considerations

- Configuration is loaded once at startup and cached
- Token expiration check is O(1)
- Token refresh is async (non-blocking)
- No file watching - restart required for config changes

### 9.4 Project Structure

```
resilio/
├── __init__.py
├── m02_config/
│   ├── __init__.py
│   ├── config.py         # Main Config class and load_config
│   ├── settings.py       # Settings models
│   ├── secrets.py        # Secrets models
│   ├── token.py          # Token refresh logic
│   └── env.py            # Environment variable handling
```

---

## 10. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.1 | 2026-01-12 | Added missing algorithms: `get_repo_root()`, `update_secrets_file()`. Added `apply_env_overrides()`, `parse_value()`, `set_nested_value()` to public interface. Added integration tests and concurrent token refresh test scenarios. Improved edge case documentation. |
| 1.0.0 | 2026-01-12 | Initial specification (Python) |
