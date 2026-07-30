"""Shared structural helpers for API result errors."""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class ErrorResult(Protocol):
    error_type: str
    message: str


def is_error(result: Any) -> bool:
    return isinstance(result, ErrorResult)


def get_error_message(result: Any) -> Optional[str]:
    return result.message if is_error(result) else None


def handle_error(result: Any, context: str = "Operation") -> bool:
    if not is_error(result):
        return False
    print(f"{context} failed: {result.message}")
    return True
