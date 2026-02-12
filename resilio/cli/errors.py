"""
Error mapping from API errors to CLI exit codes and output envelopes.

Maps domain-specific API errors (ProfileError, SyncError, etc.) to standardized
CLI exit codes that Claude Code can branch on.
"""

from typing import Any, Union

from resilio.api.helpers import get_error_message, is_error
from resilio.cli.output import OutputEnvelope, create_error_envelope, create_success_envelope


# Exit codes (following plan specification)
EXIT_SUCCESS = 0
EXIT_CONFIG_MISSING = 2
EXIT_AUTH_FAILURE = 3
EXIT_NETWORK_ERROR = 4
EXIT_VALIDATION_ERROR = 5
EXIT_NOT_IMPLEMENTED = 6
EXIT_INTERNAL_ERROR = 1


def get_exit_code_for_error_type(error_type: str) -> int:
    """Map API error type to CLI exit code.

    Args:
        error_type: API error type string (e.g., "auth", "config", "validation")

    Returns:
        Appropriate exit code (0-6)
    """
    # Error type to exit code mapping
    error_map = {
        # Config/setup issues
        "not_found": EXIT_CONFIG_MISSING,
        "no_plan": EXIT_CONFIG_MISSING,
        "no_goal": EXIT_CONFIG_MISSING,
        "insufficient_data": EXIT_CONFIG_MISSING,
        "config": EXIT_CONFIG_MISSING,
        # Auth issues
        "auth": EXIT_AUTH_FAILURE,
        # Network issues
        "rate_limit": EXIT_NETWORK_ERROR,
        "network": EXIT_NETWORK_ERROR,
        # Validation issues
        "validation": EXIT_VALIDATION_ERROR,
        "invalid_input": EXIT_VALIDATION_ERROR,
        "out_of_range": EXIT_VALIDATION_ERROR,
        # Calculation failures
        "calculation_failed": EXIT_INTERNAL_ERROR,
        # Not implemented
        "not_implemented": EXIT_NOT_IMPLEMENTED,
        # Catch-all
        "unknown": EXIT_INTERNAL_ERROR,
    }

    return error_map.get(error_type, EXIT_INTERNAL_ERROR)


def api_result_to_envelope(
    result: Any,
    success_message: str,
    include_raw_result: bool = True,
) -> OutputEnvelope:
    """Convert an API result (success or error) to an output envelope.

    This is the bridge between the API layer (Pydantic models, error objects)
    and the CLI layer (JSON envelopes, exit codes).

    Args:
        result: API result (either a success model or an error object)
        success_message: Message to use if result is successful
        include_raw_result: Whether to include the full result in data field

    Returns:
        OutputEnvelope ready for JSON/text output
    """
    # Check if it's an error
    if is_error(result):
        # Extract error details
        error_type = getattr(result, "error_type", "unknown")
        error_message = get_error_message(result) or "Unknown error"

        # Build error data with additional context
        error_data = {}

        # Include all error attributes (like retry_after, minimum_days_needed, etc.)
        if hasattr(result, "__dict__"):
            for key, value in result.__dict__.items():
                if key not in ["error_type", "message"]:
                    error_data[key] = value

        # Add next_steps guidance for common errors
        if error_type == "auth":
            error_data["next_steps"] = (
                "Run: resilio auth url to get authorization link, "
                "then resilio auth exchange --code YOUR_CODE"
            )
        elif error_type == "config":
            error_data["next_steps"] = "Run: resilio init to create data directories and config"
        elif error_type == "no_goal":
            error_data["next_steps"] = "Run: resilio goal set --type 10k --date 2026-06-01"
        elif error_type == "insufficient_data":
            days_available = error_data.get("days_available", 0)
            days_needed = error_data.get("minimum_days_needed", 14)
            days_remaining = days_needed - days_available
            error_data["next_steps"] = (
                f"Keep logging activities. You'll get full metrics in {days_remaining} more days."
            )

        return create_error_envelope(
            error_type=error_type,
            message=error_message,
            data=error_data if error_data else None,
        )

    # Success case
    if include_raw_result:
        # For most commands, include the full result
        return create_success_envelope(
            message=success_message,
            data=result,
        )
    else:
        # For some commands (like init), no data needed
        return create_success_envelope(
            message=success_message,
            data=None,
        )


def get_exit_code_from_envelope(envelope: OutputEnvelope) -> int:
    """Extract exit code from an output envelope.

    Args:
        envelope: Output envelope

    Returns:
        Appropriate exit code
    """
    if envelope.ok:
        return EXIT_SUCCESS

    # Map error type to exit code
    if envelope.error_type:
        return get_exit_code_for_error_type(envelope.error_type)

    # Fallback
    return EXIT_INTERNAL_ERROR
