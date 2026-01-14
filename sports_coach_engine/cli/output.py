"""
Output envelope system for CLI commands.

Provides consistent JSON formatting for all CLI commands, with support
for Pydantic models, dates, enums, and complex nested structures.

All commands output JSON to stdout for easy parsing by Claude Code.
"""

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional


@dataclass
class OutputEnvelope:
    """Universal output envelope for all CLI commands.

    This ensures consistent structure across all commands, making it easy for
    Claude Code to parse and interpret results.

    Attributes:
        schema_version: Version of the output schema (currently "1.0")
        ok: Whether the operation succeeded
        error_type: Category of error (config, auth, network, etc.) if ok=False
        message: Human-readable summary of the result
        data: Command-specific payload (enriched with interpretations)
    """

    schema_version: str = "1.0"
    ok: bool = True
    error_type: Optional[str] = None
    message: str = ""
    data: Any = None


def to_json_serializable(obj: Any) -> Any:
    """Convert objects to JSON-serializable types.

    Handles:
    - Pydantic models (v2): model_dump()
    - Dataclasses: asdict()
    - Dates/datetimes: ISO 8601 format
    - Enums: value
    - Lists/dicts: recursive conversion

    Args:
        obj: Object to convert

    Returns:
        JSON-serializable representation
    """
    # Pydantic v2 models
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode='json')

    # Dataclasses
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)

    # Dates and datetimes
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()

    # Enums
    if isinstance(obj, Enum):
        return obj.value

    # Lists
    if isinstance(obj, list):
        return [to_json_serializable(item) for item in obj]

    # Dicts
    if isinstance(obj, dict):
        return {key: to_json_serializable(value) for key, value in obj.items()}

    # Primitives and other types
    return obj


def output_json(envelope: OutputEnvelope) -> None:
    """Output envelope as formatted JSON to stdout.

    This is the only output mode - simple, reliable, and perfect for Claude Code.

    Args:
        envelope: Output envelope to format and print
    """
    # Convert envelope to dict
    envelope_dict = asdict(envelope)

    # Convert data field to JSON-serializable format
    if envelope_dict["data"] is not None:
        envelope_dict["data"] = to_json_serializable(envelope_dict["data"])

    # Print formatted JSON
    print(json.dumps(envelope_dict, indent=2))


def create_success_envelope(message: str, data: Any = None) -> OutputEnvelope:
    """Create a success envelope.

    Args:
        message: Human-readable success message
        data: Command-specific data payload

    Returns:
        OutputEnvelope with ok=True
    """
    return OutputEnvelope(
        ok=True,
        message=message,
        data=data,
    )


def create_error_envelope(error_type: str, message: str, data: Any = None) -> OutputEnvelope:
    """Create an error envelope.

    Args:
        error_type: Category of error (config, auth, network, etc.)
        message: Human-readable error message
        data: Additional error context (e.g., next_steps, retry_after)

    Returns:
        OutputEnvelope with ok=False
    """
    return OutputEnvelope(
        ok=False,
        error_type=error_type,
        message=message,
        data=data,
    )
