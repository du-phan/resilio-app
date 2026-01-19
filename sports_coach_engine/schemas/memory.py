"""
Memory schemas - Data models for M13 Memory & Insights.

This module defines Pydantic schemas for athlete memory storage and retrieval.
M13 provides a storage layer with smart deduplication and pattern detection.
Claude Code handles fact extraction using AI intelligence.

Design: M13 stores durable athlete facts (injury history, preferences, context,
training responses) with automatic deduplication. Claude Code extracts facts
using sports training expertise, M13 ensures robust storage and retrieval.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# ENUMS
# ============================================================


class MemoryType(str, Enum):
    """Categories of memories about the athlete."""

    INJURY_HISTORY = "injury_history"        # Past or ongoing injuries
    PREFERENCE = "preference"                # Training preferences
    CONTEXT = "context"                      # Life context, background
    INSIGHT = "insight"                      # Observed patterns
    TRAINING_RESPONSE = "training_response"  # How athlete responds to stimuli
    RACE_HISTORY = "race_history"            # Race performances and PBs


class MemoryConfidence(str, Enum):
    """Confidence level in the memory."""

    HIGH = "high"       # Explicit statement or 3+ occurrences
    MEDIUM = "medium"   # Single clear instance
    LOW = "low"         # Inferred from ambiguous text


class MemorySource(str, Enum):
    """Where the memory was extracted from."""

    ACTIVITY_NOTE = "activity_note"          # From activity description/notes
    USER_MESSAGE = "user_message"            # From conversational message
    CLAUDE_CODE = "claude_code"              # AI-extracted by Claude Code
    PATTERN_ANALYSIS = "pattern_analysis"    # Derived from pattern detection
    MANUAL = "manual"                        # Manually added


# ============================================================
# MEMORY MODELS
# ============================================================


class Memory(BaseModel):
    """A single durable fact about the athlete.

    Memories are extracted by Claude Code and stored by M13 with automatic
    deduplication. They provide long-term context for personalized coaching.
    """

    id: str                             # Unique identifier (e.g., "mem_a1b2c3d4")
    type: MemoryType                    # Category of memory
    content: str                        # The fact itself (e.g., "Left knee pain after long runs over 18km")
    source: MemorySource                # Where it was extracted from
    source_reference: Optional[str] = None  # Activity ID or message timestamp
    created_at: datetime                # When first observed
    updated_at: datetime                # When last updated
    confidence: MemoryConfidence        # Confidence level (upgrades at 3+ occurrences)
    occurrences: int = 1                # How many times observed (for deduplication)
    tags: list[str] = Field(default_factory=list)  # Entity tags (e.g., ["body:knee"])

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class ArchivedMemory(BaseModel):
    """Memory that has been superseded by a newer observation.

    When a memory is replaced by a more specific or accurate observation,
    the old memory is archived with reference to what replaced it.
    """

    id: str                             # Original memory ID
    original_content: str               # Original memory content
    superseded_by: str                  # ID of memory that replaced it
    archived_at: datetime               # When archived
    reason: str                         # Why it was archived (e.g., "Updated by newer observation about body:knee")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class PatternInsight(BaseModel):
    """Insight derived from pattern analysis of stored memories.

    M13 analyzes stored memories to detect recurring patterns (e.g., injury
    locations mentioned 3+ times, consistent training responses).
    """

    pattern_type: str                   # e.g., "recurring_injury", "override_tendency"
    description: str                    # Human-readable description (e.g., "Recurring knee issues detected (4 occurrences)")
    evidence: list[str]                 # Memory IDs that support this pattern
    confidence: MemoryConfidence        # Confidence in the pattern

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )
