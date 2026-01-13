"""
Logger schemas - Data models for M14 Conversation Logger.

This module defines Pydantic schemas for two-tier conversation logging:
- Transcripts: Full verbatim conversation logs (60-day retention)
- Summaries: Compact decision-relevant summaries (180-day retention)

The two-tier approach achieves 10x token reduction when M1 loads recent context.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# ENUMS
# ============================================================


class MessageRole(str, Enum):
    """Role of the message sender."""

    USER = "user"           # Athlete's message
    COACH = "coach"         # Coach's response
    SYSTEM = "system"       # System messages (sync results, errors, etc.)


# ============================================================
# MESSAGE AND SESSION MODELS
# ============================================================


class Message(BaseModel):
    """A single message in a conversation."""

    timestamp: datetime                     # When message was sent
    role: MessageRole                       # Who sent it
    content: str                            # Message text
    metadata: Optional[dict] = None         # Optional metadata (e.g., function calls)

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class Session(BaseModel):
    """A complete conversation session."""

    id: str                                 # Unique session ID (e.g., "2026-01-15_session")
    athlete_name: str                       # Athlete's name
    started_at: datetime                    # Session start time
    ended_at: Optional[datetime] = None     # Session end time (None if ongoing)
    messages: list[Message] = Field(default_factory=list)  # All messages

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class SessionSummary(BaseModel):
    """Compact summary of a session for efficient context loading."""

    id: str                                 # Session ID (matches transcript filename)
    date: str                               # Date in YYYY-MM-DD format
    message_count: int                      # Number of messages
    duration_minutes: int                   # Session duration
    topics: list[str]                       # Key topics discussed

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )
