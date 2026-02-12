"""
Helper functions for API error handling.

Provides utilities to make error checking concise and clear when using
the Resilio API from coaching scripts.
"""

from typing import Optional, Union


def is_error(result) -> bool:
    """
    Check if API result is any error type.

    Use this to check if an API call returned an error before accessing fields.

    Args:
        result: Return value from any API function

    Returns:
        True if result is an error type, False if it's a success type

    Example:
        >>> from resilio.api import get_profile
        >>> profile = get_profile()
        >>> if is_error(profile):
        ...     print(f"Error: {profile.message}")
        ... else:
        ...     print(f"Name: {profile.name}")
    """
    # Import here to avoid circular dependencies
    from resilio.api.profile import ProfileError
    from resilio.api.sync import SyncError
    from resilio.api.coach import CoachError
    from resilio.api.metrics import MetricsError
    from resilio.api.plan import PlanError
    from resilio.api.vdot import VDOTError
    from resilio.api.guardrails import GuardrailsError
    from resilio.api.analysis import AnalysisError
    from resilio.api.validation import ValidationError

    return isinstance(
        result,
        (
            ProfileError,
            SyncError,
            CoachError,
            MetricsError,
            PlanError,
            VDOTError,
            GuardrailsError,
            AnalysisError,
            ValidationError,
        ),
    )


def get_error_message(result) -> Optional[str]:
    """
    Extract error message if result is an error, otherwise None.

    Args:
        result: Return value from any API function

    Returns:
        Error message string if result is an error, None otherwise

    Example:
        >>> result = sync_strava()
        >>> if error_msg := get_error_message(result):
        ...     print(f"Sync failed: {error_msg}")
        ... else:
        ...     print(f"Success: {result.activities_imported} activities")
    """
    if is_error(result):
        return result.message
    return None


def handle_error(result, context: str = "Operation") -> bool:
    """
    Print error if present and return True if error, False otherwise.

    Convenience function for simple error handling with logging.
    Returns True if error (allowing early return), False if success.

    Args:
        result: Return value from any API function
        context: Description of the operation for error message

    Returns:
        True if result is an error (allows early return), False if success

    Example:
        >>> metrics = get_current_metrics()
        >>> if handle_error(metrics, "Getting metrics"):
        ...     return  # Exit early on error
        >>> print(f"CTL: {metrics.ctl.value}")  # Safe to access
    """
    if is_error(result):
        print(f"{context} failed: {result.message}")
        return True
    return False
