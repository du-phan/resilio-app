# M13 — Memory & Insights

## 1. Metadata

| Field        | Value                                          |
| ------------ | ---------------------------------------------- |
| Module ID    | M13                                            |
| Name         | Memory & Insights                              |
| Code Module  | `core/memory.py`                               |
| Version      | 2.0.0                                          |
| Status       | Draft                                          |
| Dependencies | M3 (Repository I/O)                            |

### Changelog

- **2.0.0** (2026-01-13): **MAJOR CHANGE - Simplified to storage-only layer**. Removed pattern-based extraction logic (Claude Code now handles extraction using AI intelligence). M13 now focuses on: storage with `save_memory()`, smart deduplication, retrieval by type/tag/relevance, pattern analysis on stored data. Removed sections: 4.2 (entity lists), 5.1 (extraction patterns), 5.3 (processing pipeline), 8.1 (extraction tests). Added `CLAUDE_CODE` to MemorySource enum. This architectural change reduces complexity, improves flexibility, and leverages Claude Code's sports training expertise for nuanced fact extraction.
- **1.0.2** (2026-01-12): Added code module path (`core/memory.py`) and API layer integration notes.
- **1.0.1** (2026-01-12): Converted all dataclass types to BaseModel for consistency. Added complete algorithms for `process_user_message()`, `merge_memories()`, `get_memories_by_type()`, `archive_memory()`, and `cleanup_archived()` to remove `...` placeholders and make spec LLM-implementable.
- **1.0.0** (initial): Initial draft with comprehensive memory extraction and deduplication algorithms

## 2. Purpose

**Persist and retrieve durable athlete facts extracted by Claude Code.** M13 provides a storage layer with smart deduplication, confidence scoring, and pattern detection. Claude Code handles fact extraction using its sports training expertise to understand nuance and context.

**Design Philosophy:** Leverage Claude Code's AI intelligence for extraction (understands "knee pain after long runs" vs "slight knee soreness") rather than rigid regex patterns. M13 focuses on robust storage, preventing duplicate memories, and efficient retrieval.

### 2.1 Scope Boundaries

**In Scope:**

- Storing memories with automatic deduplication
- Confidence scoring and upgrades (3+ occurrences → HIGH)
- Memory archival when superseded
- Retrieval by type, tag, and relevance
- Pattern detection from stored memories (3+ mentions = pattern)

**Out of Scope:**

- Extracting facts from text (Claude Code handles this)
- Analyzing activity notes for RPE (M7)
- Enriching memories with interpretations (M12 - Data Enrichment)
- Storing conversation transcripts (M14)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage                    |
| ------ | ------------------------ |
| M3     | Read/write memories.yaml |

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
    CLAUDE_CODE = "claude_code"           # AI-extracted by Claude Code
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

### 4.2 Function Signatures

```python
# ============================================================
# STORAGE FUNCTIONS
# ============================================================

def save_memory(
    memory: Memory,
    repo: "RepositoryIO",
) -> tuple[Memory, Optional[ArchivedMemory]]:
    """
    Save a single memory with automatic deduplication.
    Called by Claude Code after extraction.

    Process:
        1. Load existing memories from athlete/memories.yaml
        2. Deduplicate against existing using three-step algorithm
        3. Write updated memories back to file
        4. Return final memory and archived memory (if superseded)

    Args:
        memory: Memory to save (extracted by Claude Code)
        repo: RepositoryIO instance

    Returns:
        (final_memory, archived_memory_if_superseded)
    """
    ...


def load_memories(repo: "RepositoryIO") -> list[Memory]:
    """
    Load all active memories from athlete/memories.yaml.

    Returns:
        List of all active (non-archived) memories
    """
    ...


def load_archived_memories(repo: "RepositoryIO") -> list[ArchivedMemory]:
    """
    Load all archived memories from athlete/memories.yaml.

    Returns:
        List of archived memories
    """
    ...


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_memory(
    new_memory: Memory,
    existing_memories: list[Memory],
) -> tuple[Memory, Optional[ArchivedMemory]]:
    """
    Three-step deduplication algorithm:
    1. Exact content match → increment occurrences
    2. Same type + overlapping tags → update content (supersede old)
    3. No match → return as new memory

    Args:
        new_memory: Memory to check
        existing_memories: List of existing memories

    Returns:
        (result_memory, archived_memory_if_replaced)
    """
    ...


def _normalize_for_comparison(content: str) -> str:
    """
    Normalize content for exact comparison.
    Lowercases, removes extra whitespace, strips punctuation.

    Args:
        content: Memory content string

    Returns:
        Normalized string for comparison
    """
    ...


# ============================================================
# RETRIEVAL FUNCTIONS
# ============================================================

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
    Get memories relevant to current context using keyword matching.

    Scoring:
        - Content overlap (keyword matching)
        - Tag matching
        - Confidence level (HIGH > MEDIUM > LOW)
        - Recency (more recent = higher score)

    Args:
        context: Context string to match against (e.g., "knee pain")
        repo: RepositoryIO instance
        limit: Maximum number of memories to return

    Returns:
        List of most relevant memories, sorted by relevance score
    """
    ...


def get_memories_with_tag(
    tag: str,
    repo: "RepositoryIO",
) -> list[Memory]:
    """
    Get all memories with a specific tag.

    Args:
        tag: Tag to filter by (e.g., "body:knee")
        repo: RepositoryIO instance

    Returns:
        List of memories with the specified tag
    """
    ...


# ============================================================
# PATTERN ANALYSIS
# ============================================================

def analyze_memory_patterns(
    repo: "RepositoryIO",
) -> list[PatternInsight]:
    """
    Detect patterns from stored memories.

    Patterns detected:
        - Recurring injury locations (3+ mentions)
        - Training response patterns (consistent reactions)
        - Preference consistency

    Args:
        repo: RepositoryIO instance

    Returns:
        List of pattern insights with evidence
    """
    ...


# ============================================================
# ARCHIVAL
# ============================================================

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

**Note**: Memory extraction is handled by Claude Code using AI intelligence. M13 provides storage, deduplication, and retrieval algorithms only.

### 5.1 Deduplication Algorithm

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

### 5.2 Pattern Analysis (on Stored Data)

```python
def analyze_memory_patterns(
    repo: "RepositoryIO",
) -> list[PatternInsight]:
    """
    Detect patterns from stored memories.

    Patterns detected:
        - Recurring injury locations (3+ mentions)
        - Training response patterns (consistent reactions)
        - Preference consistency
    """
    memories = load_memories(repo)
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

### 5.3 Relevant Memory Retrieval

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

M13 provides storage/retrieval functions called by M1 workflows and Claude Code. **Claude Code handles memory extraction** using its AI intelligence to understand sports training context and athlete statements.

**Memory Flow:**

```
Memory extraction and storage (Claude Code-driven):
    Claude Code (reads activity note or user message)
        ↓
    Claude Code extracts facts using AI understanding
        ↓
    Claude Code → M13::save_memory(memory, repo)
        ↓
    M13::deduplicate_memory() → smart deduplication
        ↓
    M3::write_yaml("athlete/memories.yaml")

Memory retrieval for coaching responses:
    Claude Code → api.coach.get_todays_workout()
        ↓
    M10::get_todays_workout()
        ↓
    M13::get_relevant_memories(context="today's workout")
        ↓
    M12::enrich_workout(workout, memories) → WorkoutRecommendation
        ↓ (includes)
    WorkoutRecommendation.relevant_memories
        ↓
    Claude Code (crafts natural response using memories)

Pattern analysis (periodic):
    M1::analyze_training_patterns()
        ↓
    M13::analyze_memory_patterns(repo)
        ↓
    Returns list[PatternInsight] (e.g., "recurring knee issues")
```

### 7.1 Called By

| Module      | When                                    |
| ----------- | --------------------------------------- |
| Claude Code | After extracting facts from text        |
| M1          | For pattern analysis and memory cleanup |
| M12         | For enriching responses with context    |

### 7.2 Calls To

| Module | Purpose                  |
| ------ | ------------------------ |
| M3     | Read/write memories.yaml |

### 7.3 Returns To

| Module                | Data                                         |
| --------------------- | -------------------------------------------- |
| M1                    | Context for personalized responses           |
| M11                   | Pattern insights for adaptation              |
| M12 - Data Enrichment | Memories for inclusion in enriched responses |

## 8. Test Scenarios

**Note**: Memory extraction is handled by Claude Code (not tested in M13). M13 tests focus on storage, deduplication, retrieval, and pattern analysis.

### 8.1 Storage Tests

```python
def test_save_memory_new():
    """New memory is saved correctly"""
    repo = MockRepo()
    memory = Memory(
        id="mem_123",
        type=MemoryType.INJURY_HISTORY,
        content="Knee pain after long runs",
        source=MemorySource.CLAUDE_CODE,
        source_reference=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        confidence=MemoryConfidence.MEDIUM,
        occurrences=1,
        tags=["body:knee"],
    )

    result, archived = save_memory(memory, repo)

    assert result.id == "mem_123"
    assert archived is None
    assert repo.memories_written is True


### 8.2 Deduplication Tests

```python
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
