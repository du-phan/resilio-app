"""
M2 - Config & Secrets

Load configuration from settings.yaml and secrets from secrets.local.yaml.
Validate required keys and provide explicit error messages for missing secrets.
"""

from typing import Any


def load_config() -> Any:
    """
    Load configuration from config files and environment variables.
    
    Returns:
        AppConfig object with all settings and validated secrets
    """
    raise NotImplementedError("Config loading not implemented yet")


def validate_secrets() -> bool:
    """
    Validate that all required secrets are present.
    
    Returns:
        True if all secrets are valid, raises error otherwise
    """
    raise NotImplementedError("Secret validation not implemented yet")
