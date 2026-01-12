# M13 — Memory & Insights

## 1. Metadata

| Field | Value |
|-------|-------|
| Module ID | M13 |
| Name | Memory & Insights |
| Code Module | `core/memory.py` |
| Version | 1.0.2 |
| Status | Draft |
| Dependencies | M3 (Repository I/O), M7 (Notes & RPE Analyzer) |

### Changelog
- **1.0.2** (2026-01-12): Added code module path (`core/memory.py`) and API layer integration notes.
- **1.0.1** (2026-01-12): Converted all dataclass types to BaseModel for consistency. Added complete algorithms for `process_user_message()`, `merge_memories()`, `get_memories_by_type()`, `archive_memory()`, and `cleanup_archived()` to remove `...` placeholders and make spec LLM-implementable.
- **1.0.0** (initial): Initial draft with comprehensive memory extraction and deduplication algorithms

## 2. Purpose

Extract and persist durable athlete facts from activity notes and conversations. Builds a long-term memory of preferences, injury history, training responses, and contextual factors that inform personalized coaching.

### 2.1 Scope Boundaries

**In Scope:**
- Extracting facts from activity notes
- Extracting facts from user messages
- Memory deduplication and updates
- Confidence scoring
- Memory archival when superseded
- Pattern detection across multiple sessions

**Out of Scope:**
- Analyzing activity notes for RPE (M7)
- Enriching memories with interpretations (M12 - Data Enrichment)
- Storing conversation transcripts (M14)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage |
|--------|-------|
| M3 | Read/write memories.yaml |
| M7 | Receives analysis results with extracted signals |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
```

## 4. Internal Interface

**Note:** This module is called internally by M1 workflows and the API layer. Claude Code should NOT import from `core/memory.py` directly—memories are accessed through enriched data returned by API functions (e.g., `WorkoutRecommendation.relevant_memories`).

### 4.1 Type Definitions

```python
from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Categories of memories"""
    INJURY_HISTORY = "injury_history"       # Past or ongoing injuries
    PREFERENCE = "preference"               # Training preferences
    CONTEXT = "context"                     # Life context, background
    INSIGHT = "insight"                     # Observed patterns
    TRAINING_RESPONSE = "training_response" # How athlete responds to stimuli


class MemoryConfidence(str, Enum):
    """Confidence level in the memory"""
    HIGH = "high"       # Explicit statement or 3+ occurrences
    MEDIUM = "medium"   # Single clear instance
    LOW = "low"         # Inferred from ambiguous text


class MemorySource(str, Enum):
    """Where the memory was extracted from"""
    ACTIVITY_NOTE = "activity_note"
    USER_MESSAGE = "user_message"
    PATTERN_ANALYSIS = "pattern_analysis"
    MANUAL = "manual"


class Memory(BaseModel):
    """A single durable fact about the athlete"""
    id: str
    type: MemoryType
    content: str                    # The fact itself
    source: MemorySource
    source_reference: Optional[str] = None # Activity ID or message timestamp
    created_at: datetime
    updated_at: datetime
    confidence: MemoryConfidence
    occurrences: int = 1           # How many times observed
    tags: list[str] = Field(default_factory=list)  # Entity tags


class ArchivedMemory(BaseModel):
    """Memory that has been superseded"""
    id: str
    original_content: str
    superseded_by: str             # ID of replacing memory
    archived_at: datetime
    reason: str                    # Why it was archived


class ExtractionResult(BaseModel):
    """Result of memory extraction"""
    new_memories: list[Memory]
    updated_memories: list[Memory]
    archived_memories: list[ArchivedMemory]


class PatternInsight(BaseModel):
    """Insight derived from pattern analysis"""
    pattern_type: str              # e.g., "recovery_time", "injury_prone"
    description: str
    evidence: list[str]            # References to supporting data
    confidence: MemoryConfidence
```

### 4.2 Entity Lists for Matching

```python
# Body parts for injury tracking
BODY_PARTS = [
    "knee", "ankle", "calf", "shin", "hip", "hamstring",
    "quad", "achilles", "foot", "heel", "back", "shoulder",
    "it band", "plantar", "glute"
]

# Time preferences
TIME_PREFERENCES = [
    "morning", "evening", "afternoon", "lunch",
    "early", "late", "before work", "after work"
]

# Intensity preferences
INTENSITY_TOPICS = [
    "easy", "hard", "tempo", "intervals", "long run",
    "recovery", "speed work", "hill repeats"
]

# Context topics
CONTEXT_TOPICS = [
    "job", "work", "travel", "family", "kids",
    "commute", "gym", "climbing", "cycling"
]
```

### 4.3 Function Signatures

```python
def extract_memories(
    text: str,
    source: MemorySource,
    source_reference: Optional[str] = None,
) -> list[Memory]:
    """
    Extract durable facts from text.

    Args:
        text: Activity note or user message
        source: Where the text came from
        source_reference: Activity ID or timestamp

    Returns:
        List of extracted memories
    """
    ...


def process_activity_notes(
    activity: "NormalizedActivity",
    analysis: "AnalysisResult",
) -> ExtractionResult:
    """
    Extract memories from activity notes and analysis.

    Called after M7 analysis completes.
    """
    ...


def process_user_message(
    message: str,
    timestamp: datetime,
) -> ExtractionResult:
    """
    Extract memories from conversational user message.

    Process:
        1. Extract memories using pattern matching
        2. Source is USER_MESSAGE with timestamp reference
        3. Deduplicate against existing memories
        4. Return extraction result

    Args:
        message: User's conversational message
        timestamp: When the message was sent

    Returns:
        ExtractionResult with new/updated/archived memories
    """
    # Extract memories from message
    extracted = extract_memories(
        text=message,
        source=MemorySource.USER_MESSAGE,
        source_reference=timestamp.isoformat(),
    )

    if not extracted:
        return ExtractionResult([], [], [])

    # Deduplicate against existing
    repo = get_repo()  # Injected dependency
    existing = load_memories(repo)

    new_memories = []
    updated_memories = []
    archived_memories = []

    for memory in extracted:
        result, archived = deduplicate_memory(memory, existing)

        if archived:
            archived_memories.append(archived)
            updated_memories.append(result)
            # Update existing list
            existing = [m for m in existing if m.id != archived.id]
            existing.append(result)
        elif result.id == memory.id:
            # Truly new
            new_memories.append(result)
            existing.append(result)
        else:
            # Updated existing
            updated_memories.append(result)

    return ExtractionResult(
        new_memories=new_memories,
        updated_memories=updated_memories,
        archived_memories=archived_memories,
    )


def deduplicate_memory(
    new_memory: Memory,
    existing_memories: list[Memory],
) -> tuple[Memory, Optional[ArchivedMemory]]:
    """
    Check if memory duplicates or updates existing.

    Strategy:
    1. Exact match → increment occurrences
    2. Same type + entity → update content
    3. No match → create new

    Returns:
        (result_memory, archived if replaced)
    """
    ...


def merge_memories(
    memories: list[Memory],
    repo: "RepositoryIO",
) -> ExtractionResult:
    """
    Merge new memories into persistent storage.

    Process:
        1. Load existing memories from athlete/memories.yaml
        2. Deduplicate each new memory against existing
        3. Track new, updated, and archived memories
        4. Write updated memories.yaml
        5. Return ExtractionResult

    Args:
        memories: List of new memories to merge
        repo: RepositoryIO instance

    Returns:
        ExtractionResult with new/updated/archived counts
    """
    # Load existing memories
    existing = load_memories(repo)

    new_memories = []
    updated_memories = []
    archived_memories = []

    # Deduplicate each memory
    for memory in memories:
        result, archived = deduplicate_memory(memory, existing)

        if archived:
            # Memory was superseded
            archived_memories.append(archived)
            updated_memories.append(result)
            # Update existing list
            existing = [m for m in existing if m.id != archived.id]
            existing.append(result)
        elif result.id == memory.id:
            # Truly new memory
            new_memories.append(result)
            existing.append(result)
        else:
            # Existing memory updated (occurrences incremented)
            updated_memories.append(result)

    # Write back to file
    memories_data = repo.read_yaml("athlete/memories.yaml")
    memories_data["memories"] = [m.model_dump() for m in existing]

    # Add archived records
    existing_archived = memories_data.get("archived", [])
    for archived in archived_memories:
        existing_archived.append(archived.model_dump())
    memories_data["archived"] = existing_archived

    repo.write_yaml("athlete/memories.yaml", memories_data)

    return ExtractionResult(
        new_memories=new_memories,
        updated_memories=updated_memories,
        archived_memories=archived_memories,
    )


def get_memories_by_type(
    memory_type: MemoryType,
    repo: "RepositoryIO",
) -> list[Memory]:
    """
    Get all memories of a specific type.

    Process:
        1. Load all memories from athlete/memories.yaml
        2. Filter by memory_type
        3. Sort by confidence then updated_at (most recent first)
        4. Return filtered list

    Args:
        memory_type: The type of memories to retrieve
        repo: RepositoryIO instance

    Returns:
        List of memories matching the type
    """
    all_memories = load_memories(repo)

    # Filter by type
    filtered = [m for m in all_memories if m.type == memory_type]

    # Sort by confidence (HIGH first) then recency
    confidence_order = {
        MemoryConfidence.HIGH: 3,
        MemoryConfidence.MEDIUM: 2,
        MemoryConfidence.LOW: 1,
    }

    filtered.sort(
        key=lambda m: (confidence_order.get(m.confidence, 0), m.updated_at),
        reverse=True
    )

    return filtered


def get_relevant_memories(
    context: str,
    repo: "RepositoryIO",
    limit: int = 5,
) -> list[Memory]:
    """
    Get memories relevant to a given context.

    Used to provide context for coaching responses.
    """
    ...


def analyze_patterns(
    activities: list["NormalizedActivity"],
    memories: list[Memory],
) -> list[PatternInsight]:
    """
    Analyze training history for patterns.

    Patterns detected:
    - Recurring injury triggers
    - Recovery time patterns
    - Performance correlations
    - Override patterns (from M11)
    """
    ...


def archive_memory(
    memory_id: str,
    superseded_by: str,
    reason: str,
    repo: "RepositoryIO",
) -> ArchivedMemory:
    """
    Archive a memory that has been superseded.

    Process:
        1. Load memories.yaml
        2. Find memory by ID
        3. Create ArchivedMemory record
        4. Move to archived list
        5. Remove from active list
        6. Write updated memories.yaml
        7. Return ArchivedMemory

    Args:
        memory_id: ID of memory to archive
        superseded_by: ID of memory that replaces it
        reason: Human-readable reason for archiving
        repo: RepositoryIO instance

    Returns:
        ArchivedMemory record
    """
    # Load memories
    memories_data = repo.read_yaml("athlete/memories.yaml")
    active_memories = memories_data.get("memories", [])
    archived_memories = memories_data.get("archived", [])

    # Find the memory to archive
    memory_to_archive = next(
        (m for m in active_memories if m["id"] == memory_id),
        None
    )

    if not memory_to_archive:
        raise ValueError(f"Memory not found: {memory_id}")

    # Create archived record
    archived = ArchivedMemory(
        id=memory_id,
        original_content=memory_to_archive["content"],
        superseded_by=superseded_by,
        archived_at=datetime.now(),
        reason=reason,
    )

    # Add to archived list
    archived_memories.append(archived.model_dump())

    # Remove from active list
    active_memories = [m for m in active_memories if m["id"] != memory_id]

    # Update file
    memories_data["memories"] = active_memories
    memories_data["archived"] = archived_memories
    repo.write_yaml("athlete/memories.yaml", memories_data)

    return archived


def cleanup_archived(
    repo: "RepositoryIO",
    retention_days: int = 90,
) -> int:
    """
    Remove archived memories older than retention period.

    Process:
        1. Load memories.yaml
        2. Filter archived memories older than retention_days
        3. Remove old archived memories
        4. Write updated memories.yaml
        5. Return count deleted

    Args:
        repo: RepositoryIO instance
        retention_days: Days to retain archived memories (default 90)

    Returns:
        Count of memories deleted
    """
    from datetime import timedelta

    # Load memories
    memories_data = repo.read_yaml("athlete/memories.yaml")
    archived_memories = memories_data.get("archived", [])

    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    # Filter out old archived memories
    initial_count = len(archived_memories)
    archived_memories = [
        m for m in archived_memories
        if datetime.fromisoformat(m["archived_at"]) > cutoff_date
    ]

    deleted_count = initial_count - len(archived_memories)

    if deleted_count > 0:
        # Update file
        memories_data["archived"] = archived_memories
        repo.write_yaml("athlete/memories.yaml", memories_data)

    return deleted_count
```

### 4.4 Error Types

```python
class MemoryError(Exception):
    """Base error for memory operations"""
    pass


class DuplicateMemoryError(MemoryError):
    """Memory already exists (informational)"""
    def __init__(self, existing_id: str):
        super().__init__(f"Memory duplicates existing: {existing_id}")
        self.existing_id = existing_id
```

## 5. Core Algorithms

### 5.1 Memory Extraction

```python
import re
import uuid
from datetime import datetime


# Extraction patterns
EXTRACTION_PATTERNS = {
    MemoryType.INJURY_HISTORY: [
        # "knee pain", "tight calf", "achilles issues"
        (r'\b(knee|ankle|calf|shin|hip|hamstring|quad|achilles|foot|back|shoulder)\b.*?\b(pain|tight|sore|injury|issues?|problem|hurt)\b', "body_part_issue"),
        (r'\b(pain|tight|sore|injury|issues?|problem|hurt)\b.*?\b(knee|ankle|calf|shin|hip|hamstring|quad|achilles|foot|back|shoulder)\b', "issue_body_part"),
        # "history of X", "recurring X"
        (r'\b(history of|recurring|chronic|old)\b.*?\b(injury|pain|issue)', "chronic_indicator"),
    ],
    MemoryType.PREFERENCE: [
        # "I prefer morning runs"
        (r'\bi prefer\b.*?(morning|evening|early|late|short|long|easy|hard)', "explicit_prefer"),
        # "morning works best"
        (r'\b(morning|evening|early|late)\b.*?\b(works? best|is best|suits me)', "time_preference"),
        # "I like/love X"
        (r'\bi (like|love|enjoy)\b.*?(running|tempo|intervals|long runs?|easy)', "positive_preference"),
        # "I hate/dislike X"
        (r'\bi (hate|dislike|don\'t like)\b.*?(running|tempo|intervals|long runs?|treadmill)', "negative_preference"),
    ],
    MemoryType.CONTEXT: [
        # "I work as", "my job is"
        (r'\b(i work as|my job is|i\'m a)\b\s+(\w+)', "job_context"),
        # "I have X kids"
        (r'\bi have\b.*?(\d+)\s*(kids?|children)', "family_context"),
        # "I also do X"
        (r'\bi also (do|train|practice)\b\s+(\w+)', "other_sport"),
        # "I climb X times per week"
        (r'\bi\s+(climb|cycle|swim)\b.*?(\d+)\s*(times?|days?)\s*(per|a)\s*week', "sport_frequency"),
    ],
    MemoryType.TRAINING_RESPONSE: [
        # "I recover quickly/slowly"
        (r'\bi recover\b\s*(quickly|slowly|fast|well)', "recovery_rate"),
        # "X makes me tired/sore"
        (r'(intervals?|tempo|long runs?|hills?)\b.*?\b(make me|leave me)\s*(tired|sore|exhausted)', "training_response"),
    ],
}


def extract_memories(
    text: str,
    source: MemorySource,
    source_reference: Optional[str] = None,
) -> list[Memory]:
    """
    Extract memories from text using pattern matching.
    """
    if not text or not text.strip():
        return []

    text_lower = text.lower()
    now = datetime.now()
    memories = []

    for memory_type, patterns in EXTRACTION_PATTERNS.items():
        for pattern, pattern_name in patterns:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)

            for match in matches:
                # Extract the matched content
                content = _clean_extracted_content(match.group(0), memory_type)

                # Determine confidence
                confidence = _assess_confidence(match.group(0), pattern_name)

                # Extract entity tags
                tags = _extract_entity_tags(match.group(0), memory_type)

                memory = Memory(
                    id=f"mem_{uuid.uuid4().hex[:8]}",
                    type=memory_type,
                    content=content,
                    source=source,
                    source_reference=source_reference,
                    created_at=now,
                    updated_at=now,
                    confidence=confidence,
                    occurrences=1,
                    tags=tags,
                )

                memories.append(memory)

    return memories


def _clean_extracted_content(raw: str, memory_type: MemoryType) -> str:
    """Clean and normalize extracted content"""
    # Capitalize first letter
    content = raw.strip().capitalize()

    # Remove filler words at start
    for filler in ["i ", "my ", "the "]:
        if content.lower().startswith(filler):
            content = content[len(filler):].capitalize()

    return content


def _assess_confidence(text: str, pattern_name: str) -> MemoryConfidence:
    """Assess confidence based on pattern type and explicitness"""
    explicit_patterns = ["explicit_prefer", "chronic_indicator", "job_context"]

    if pattern_name in explicit_patterns:
        return MemoryConfidence.HIGH
    elif "prefer" in pattern_name or "response" in pattern_name:
        return MemoryConfidence.MEDIUM
    else:
        return MemoryConfidence.LOW


def _extract_entity_tags(text: str, memory_type: MemoryType) -> list[str]:
    """Extract entity tags for deduplication matching"""
    tags = []
    text_lower = text.lower()

    if memory_type == MemoryType.INJURY_HISTORY:
        for part in BODY_PARTS:
            if part in text_lower:
                tags.append(f"body:{part}")

    elif memory_type == MemoryType.PREFERENCE:
        for time_pref in TIME_PREFERENCES:
            if time_pref in text_lower:
                tags.append(f"time:{time_pref}")
        for intensity in INTENSITY_TOPICS:
            if intensity in text_lower:
                tags.append(f"intensity:{intensity}")

    elif memory_type == MemoryType.CONTEXT:
        for topic in CONTEXT_TOPICS:
            if topic in text_lower:
                tags.append(f"context:{topic}")

    return tags
```

### 5.2 Deduplication Algorithm

```python
def deduplicate_memory(
    new_memory: Memory,
    existing_memories: list[Memory],
) -> tuple[Memory, Optional[ArchivedMemory]]:
    """
    Three-step deduplication:
    1. Exact content match → increment occurrences
    2. Same type + entity tags → update content
    3. No match → return as new
    """
    # Normalize for comparison
    new_content_normalized = _normalize_for_comparison(new_memory.content)

    # Step 1: Exact match check
    for existing in existing_memories:
        existing_normalized = _normalize_for_comparison(existing.content)

        if new_content_normalized == existing_normalized:
            # Exact match - increment occurrences
            existing.occurrences += 1
            existing.updated_at = datetime.now()

            # Upgrade confidence if multiple occurrences
            if existing.occurrences >= 3 and existing.confidence != MemoryConfidence.HIGH:
                existing.confidence = MemoryConfidence.HIGH

            return existing, None

    # Step 2: Type + entity match
    for existing in existing_memories:
        if existing.type != new_memory.type:
            continue

        # Check for overlapping entity tags
        overlap = set(new_memory.tags) & set(existing.tags)

        if overlap:
            # Same entity - newer content supersedes
            archived = ArchivedMemory(
                id=existing.id,
                original_content=existing.content,
                superseded_by=new_memory.id,
                archived_at=datetime.now(),
                reason=f"Updated by newer observation about {', '.join(overlap)}",
            )

            # Transfer occurrence count
            new_memory.occurrences = existing.occurrences + 1
            new_memory.updated_at = datetime.now()

            return new_memory, archived

    # Step 3: No match - truly new memory
    return new_memory, None


def _normalize_for_comparison(content: str) -> str:
    """Normalize content for exact comparison"""
    # Lowercase, collapse whitespace, strip punctuation
    normalized = content.lower()
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'[^\w\s]', '', normalized)
    return normalized.strip()
```

### 5.3 Memory Processing Pipeline

```python
def process_activity_notes(
    activity: "NormalizedActivity",
    analysis: "AnalysisResult",
) -> ExtractionResult:
    """
    Process activity notes for memories.
    """
    new_memories = []
    updated_memories = []
    archived_memories = []

    # Combine all text sources
    text_sources = [
        activity.name or "",
        activity.description or "",
        activity.private_note or "",
    ]
    combined_text = " ".join(text_sources)

    if not combined_text.strip():
        return ExtractionResult([], [], [])

    # Extract memories from text
    extracted = extract_memories(
        text=combined_text,
        source=MemorySource.ACTIVITY_NOTE,
        source_reference=activity.id,
    )

    # Process injury flags from analysis
    if analysis.injury_flags:
        for flag in analysis.injury_flags:
            injury_memory = Memory(
                id=f"mem_{uuid.uuid4().hex[:8]}",
                type=MemoryType.INJURY_HISTORY,
                content=f"{flag.body_part.value} {flag.severity.value}: {flag.source_text}",
                source=MemorySource.ACTIVITY_NOTE,
                source_reference=activity.id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                confidence=MemoryConfidence.HIGH,
                tags=[f"body:{flag.body_part.value}"],
            )
            extracted.append(injury_memory)

    # Deduplicate against existing
    repo = get_repo()  # Injected dependency
    existing = load_memories(repo)

    for memory in extracted:
        result, archived = deduplicate_memory(memory, existing)

        if archived:
            archived_memories.append(archived)
            updated_memories.append(result)
            # Update existing list
            existing = [m for m in existing if m.id != archived.id]
            existing.append(result)
        elif result.id == memory.id:
            # Truly new
            new_memories.append(result)
            existing.append(result)
        else:
            # Updated existing
            updated_memories.append(result)

    return ExtractionResult(
        new_memories=new_memories,
        updated_memories=updated_memories,
        archived_memories=archived_memories,
    )
```

### 5.4 Pattern Analysis

```python
def analyze_patterns(
    activities: list["NormalizedActivity"],
    memories: list[Memory],
) -> list[PatternInsight]:
    """
    Detect patterns across training history.
    """
    insights = []

    # Pattern 1: Recurring injury location
    injury_memories = [m for m in memories if m.type == MemoryType.INJURY_HISTORY]
    body_part_counts = {}
    for mem in injury_memories:
        for tag in mem.tags:
            if tag.startswith("body:"):
                part = tag.split(":")[1]
                body_part_counts[part] = body_part_counts.get(part, 0) + 1

    for part, count in body_part_counts.items():
        if count >= 3:
            insights.append(PatternInsight(
                pattern_type="recurring_injury",
                description=f"Recurring {part} issues detected ({count} occurrences)",
                evidence=[m.id for m in injury_memories if f"body:{part}" in m.tags],
                confidence=MemoryConfidence.HIGH,
            ))

    # Pattern 2: Override patterns (from M11 tracking)
    override_memories = [
        m for m in memories
        if "override" in m.content.lower() or m.type == MemoryType.TRAINING_RESPONSE
    ]
    if len(override_memories) >= 3:
        insights.append(PatternInsight(
            pattern_type="override_tendency",
            description="Athlete frequently overrides rest suggestions",
            evidence=[m.id for m in override_memories[:5]],
            confidence=MemoryConfidence.MEDIUM,
        ))

    # Pattern 3: Recovery time correlation
    # (Simplified - full implementation would analyze activity sequences)

    return insights
```

### 5.5 Relevant Memory Retrieval

```python
def get_relevant_memories(
    context: str,
    repo: "RepositoryIO",
    limit: int = 5,
) -> list[Memory]:
    """
    Get memories relevant to current context.

    Used to provide context for coaching responses.
    """
    all_memories = load_memories(repo)

    # Score memories by relevance
    scored = []
    context_lower = context.lower()

    for memory in all_memories:
        score = 0

        # Content overlap
        memory_words = set(memory.content.lower().split())
        context_words = set(context_lower.split())
        overlap = len(memory_words & context_words)
        score += overlap * 2

        # Tag relevance
        for tag in memory.tags:
            entity = tag.split(":")[-1]
            if entity in context_lower:
                score += 5

        # Confidence boost
        if memory.confidence == MemoryConfidence.HIGH:
            score += 3
        elif memory.confidence == MemoryConfidence.MEDIUM:
            score += 1

        # Recency boost
        days_old = (datetime.now() - memory.updated_at).days
        if days_old < 7:
            score += 2
        elif days_old < 30:
            score += 1

        if score > 0:
            scored.append((memory, score))

    # Sort by score, return top N
    scored.sort(key=lambda x: x[1], reverse=True)
    return [m for m, s in scored[:limit]]
```

## 6. Data Structures

### 6.1 Memories File Schema

```yaml
# athlete/memories.yaml
_schema:
  format_version: "1.0.0"
  schema_type: "memories"

memories:
  - id: "mem_a1b2c3d4"
    type: "injury_history"
    content: "Left knee pain after long runs over 18km"
    source: "activity_note"
    source_reference: "act_12345"
    created_at: "2025-02-15T10:30:00Z"
    updated_at: "2025-03-10T08:45:00Z"
    confidence: "high"
    occurrences: 4
    tags:
      - "body:knee"

  - id: "mem_e5f6g7h8"
    type: "preference"
    content: "Prefers morning runs before work"
    source: "user_message"
    source_reference: "2025-03-01T09:00:00Z"
    created_at: "2025-03-01T09:00:00Z"
    updated_at: "2025-03-01T09:00:00Z"
    confidence: "medium"
    occurrences: 1
    tags:
      - "time:morning"

  - id: "mem_i9j0k1l2"
    type: "context"
    content: "Climbs 2-3 times per week, primary sport"
    source: "pattern_analysis"
    source_reference: null
    created_at: "2025-02-01T00:00:00Z"
    updated_at: "2025-03-15T12:00:00Z"
    confidence: "high"
    occurrences: 12
    tags:
      - "context:climbing"

archived:
  - id: "mem_old123"
    original_content: "Occasional knee soreness"
    superseded_by: "mem_a1b2c3d4"
    archived_at: "2025-02-20T15:00:00Z"
    reason: "Updated by newer observation about body:knee"
```

## 7. Integration Points

**Integration with API Layer:**

This module is called internally by M1 workflows during sync and conversation processing. Claude Code receives memories indirectly through enriched API responses.

**Memory Flow:**

```
Automatic extraction (during sync):
    M1::run_sync_workflow()
        ↓
    M7::analyze_notes() → extracts injury flags, wellness signals
        ↓
    M13::process_activity_notes() → extracts memories
        ↓
    M13::merge_memories() → deduplicate and persist
        ↓
    M3::write_yaml("athlete/memories.yaml")

User message processing:
    Claude Code (receives user message)
        ↓
    M1::process_conversation()
        ↓
    M13::process_user_message() → extract memories
        ↓
    M13::merge_memories() → deduplicate and persist

Memory usage in responses:
    Claude Code → api.coach.get_todays_workout()
        ↓
    M10::get_todays_workout()
        ↓
    M13::get_relevant_memories(context="today's workout")
        ↓
    M12::enrich_workout(workout, memories) → WorkoutRecommendation
        ↓ (includes)
    WorkoutRecommendation.relevant_memories
```

### 7.1 Called By

| Module | When |
|--------|------|
| M1 | After sync completes (process activity notes) |
| M1 | During conversation (process user messages) |
| M11 | Track override patterns |

### 7.2 Calls To

| Module | Purpose |
|--------|---------|
| M3 | Read/write memories.yaml |

### 7.3 Returns To

| Module | Data |
|--------|------|
| M1 | Context for personalized responses |
| M11 | Pattern insights for adaptation |
| M12 - Data Enrichment | Memories for inclusion in enriched responses |

## 8. Test Scenarios

### 8.1 Extraction Tests

```python
def test_extract_injury_pattern():
    """Injury patterns are extracted"""
    text = "Left knee pain started around km 15"
    memories = extract_memories(text, MemorySource.ACTIVITY_NOTE)

    assert len(memories) >= 1
    assert any(m.type == MemoryType.INJURY_HISTORY for m in memories)
    assert any("body:knee" in m.tags for m in memories)


def test_extract_preference():
    """Preferences are extracted"""
    text = "I prefer morning runs, they energize me for the day"
    memories = extract_memories(text, MemorySource.USER_MESSAGE)

    assert any(m.type == MemoryType.PREFERENCE for m in memories)


def test_dedup_exact_match():
    """Exact matches increment occurrences"""
    existing = [Memory(
        id="mem_123",
        type=MemoryType.INJURY_HISTORY,
        content="Knee pain after long runs",
        source=MemorySource.ACTIVITY_NOTE,
        source_reference="act_1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        confidence=MemoryConfidence.MEDIUM,
        occurrences=2,
        tags=["body:knee"],
    )]

    new = Memory(
        id="mem_456",
        type=MemoryType.INJURY_HISTORY,
        content="Knee pain after long runs",
        source=MemorySource.ACTIVITY_NOTE,
        source_reference="act_2",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        confidence=MemoryConfidence.MEDIUM,
        occurrences=1,
        tags=["body:knee"],
    )

    result, archived = deduplicate_memory(new, existing)

    assert result.id == "mem_123"
    assert result.occurrences == 3
    assert archived is None


def test_dedup_type_entity_supersedes():
    """Same type+entity supersedes old memory"""
    existing = [Memory(
        id="mem_old",
        type=MemoryType.INJURY_HISTORY,
        content="Occasional knee soreness",
        source=MemorySource.ACTIVITY_NOTE,
        source_reference="act_old",
        created_at=datetime.now() - timedelta(days=30),
        updated_at=datetime.now() - timedelta(days=30),
        confidence=MemoryConfidence.LOW,
        occurrences=1,
        tags=["body:knee"],
    )]

    new = Memory(
        id="mem_new",
        type=MemoryType.INJURY_HISTORY,
        content="Chronic knee pain after runs over 15km",
        source=MemorySource.ACTIVITY_NOTE,
        source_reference="act_new",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        confidence=MemoryConfidence.HIGH,
        occurrences=1,
        tags=["body:knee"],
    )

    result, archived = deduplicate_memory(new, existing)

    assert result.id == "mem_new"
    assert archived is not None
    assert archived.id == "mem_old"
    assert archived.superseded_by == "mem_new"
```

## 9. Configuration

### 9.1 Memory Settings

```python
MEMORY_CONFIG = {
    "archive_retention_days": 90,
    "high_confidence_threshold": 3,  # Occurrences for HIGH
    "max_memories_per_type": 50,
    "relevance_score_threshold": 2,
}
```

## 10. Privacy Considerations

- Memories are stored locally only
- No transmission to external services
- User can request memory deletion
- Memories used only for coaching context
