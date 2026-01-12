# M14 — Conversation Logger

## 1. Metadata

| Field        | Value               |
| ------------ | ------------------- |
| Module ID    | M14                 |
| Name         | Conversation Logger |
| Code Module  | `core/logger.py`    |
| Version      | 1.0.3               |
| Status       | Draft               |
| Dependencies | M3 (Repository I/O) |

### Changelog

- **1.0.3** (2026-01-12): Added code module path (`core/logger.py`) and API layer integration notes.
- **1.0.2** (2026-01-12): Added two-tier logging system (session summaries + full transcripts) for efficient context loading. Summary generation uses Claude Code session (no external API). Dynamic retention policies (60 days transcripts, 180 days summaries). New functions: `generate_session_summary()`, `persist_summary()`, `list_session_summaries()`, `get_summary_by_date()`, `get_transcript_by_date()`. Modified `end_session()` to return both paths.
- **1.0.1** (2026-01-12): Converted all dataclass types to BaseModel for consistency. Added complete algorithm for `get_session_by_date()` to remove `...` placeholder and make spec LLM-implementable.
- **1.0.0** (initial): Initial draft with comprehensive conversation logging algorithms

## 2. Purpose

Persist conversation sessions between user and coach for auditability, context recovery, and debugging. Stores timestamped, role-tagged messages in human-readable markdown format.

### 2.1 Scope Boundaries

**In Scope:**

- Logging user messages
- Logging coach responses
- Session management (start, end)
- Generating session transcripts
- Retention management

**Out of Scope:**

- Parsing user intent (M1)
- Enriching data for responses (M12 - Data Enrichment)
- Extracting memories from conversations (M13)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage                    |
| ------ | ------------------------ |
| M3     | Write conversation files |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models (minimal)
```

## 4. Internal Interface

**Note:** This module is called internally by M1 workflows to log conversations. Claude Code does NOT import from `core/logger.py` directly—logging happens automatically as part of M1's orchestration.

### 4.1 Type Definitions

```python
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Who sent the message"""
    USER = "user"
    COACH = "coach"
    SYSTEM = "system"


class Message(BaseModel):
    """A single message in the conversation"""
    timestamp: datetime
    role: MessageRole
    content: str
    metadata: Optional[dict] = None  # Additional context


class Session(BaseModel):
    """A conversation session"""
    id: str
    athlete_name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    messages: list[Message]


class SessionSummary(BaseModel):
    """Summary of a session for listing"""
    id: str
    date: str
    message_count: int
    duration_minutes: int
    topics: list[str]
```

### 4.2 Function Signatures

```python
def start_session(
    athlete_name: str,
) -> Session:
    """
    Start a new conversation session.

    Returns:
        New session object with unique ID
    """
    ...


def log_message(
    session: Session,
    role: MessageRole,
    content: str,
    metadata: Optional[dict] = None,
) -> Message:
    """
    Log a message to the current session.

    Args:
        session: Current session
        role: Who sent the message
        content: Message content
        metadata: Optional context (intent, metrics snapshot, etc.)

    Returns:
        Logged message
    """
    ...


def end_session(
    session: Session,
    repo: "RepositoryIO",
) -> tuple[str, str]:
    """
    End session and persist both transcript and summary to disk.

    Returns:
        Tuple of (transcript_path, summary_path)
    """
    ...


def persist_transcript(
    session: Session,
    repo: "RepositoryIO",
) -> str:
    """
    Write full session transcript to markdown file.

    Format: conversations/transcripts/YYYY-MM-DD_session.md
    """
    ...


def persist_summary(
    session: Session,
    summary: str,
    repo: "RepositoryIO",
) -> str:
    """
    Write session summary to markdown file.

    Format: conversations/summaries/YYYY-MM-DD_summary.md
    """
    ...


def generate_session_summary(
    session: Session,
    repo: "RepositoryIO",
) -> str:
    """
    Generate compact session summary using Claude Code instance.

    Extracts only decision-relevant information:
    - User concerns and questions
    - Key decisions and adaptations
    - Important feedback (injury, fatigue, preferences)
    - Metrics context at time of session
    - Follow-up items

    Returns:
        Markdown summary (10-20 lines, ~100-300 tokens)
    """
    ...


def load_session(
    session_path: str,
    repo: "RepositoryIO",
) -> Session:
    """
    Load a previous session from disk.
    """
    ...


def list_sessions(
    repo: "RepositoryIO",
    limit: int = 10,
) -> list[SessionSummary]:
    """
    List recent conversation sessions (metadata only).
    """
    ...


def list_session_summaries(
    repo: "RepositoryIO",
    limit: int = 10,
) -> list[str]:
    """
    List recent session summaries (full summary content).

    Used by M1 for loading historical context efficiently.

    Returns:
        List of summary markdown strings
    """
    ...


def get_session_by_date(
    target_date: str,
    repo: "RepositoryIO",
) -> Optional[Session]:
    """
    Get full session transcript for a specific date.

    Process:
        1. List conversation transcript files
        2. Find file matching target_date pattern (YYYY-MM-DD)
        3. If multiple sessions on same date, return first one
        4. Load and return session
        5. Return None if no session found

    Args:
        target_date: Date string in YYYY-MM-DD format
        repo: RepositoryIO instance

    Returns:
        Session object if found, None otherwise
    """
    # List conversation transcript files
    files = repo.list_files("conversations/transcripts", pattern=f"{target_date}*.md")

    if not files:
        return None

    # Return first match (or could prompt user if multiple)
    filepath = files[0]

    try:
        session = load_session(filepath, repo)
        return session
    except Exception:
        return None


def get_summary_by_date(
    target_date: str,
    repo: "RepositoryIO",
) -> Optional[str]:
    """
    Get session summary for a specific date.

    Args:
        target_date: Date string in YYYY-MM-DD format
        repo: RepositoryIO instance

    Returns:
        Summary markdown string if found, None otherwise
    """
    files = repo.list_files("conversations/summaries", pattern=f"{target_date}*.md")

    if not files:
        return None

    try:
        return repo.read_text(files[0])
    except Exception:
        return None


def get_transcript_by_date(
    target_date: str,
    repo: "RepositoryIO",
) -> Optional[Session]:
    """
    Alias for get_session_by_date() for clarity.

    Used when specifically requesting full transcript (not summary).
    """
    return get_session_by_date(target_date, repo)


def cleanup_old_sessions(
    repo: "RepositoryIO",
    transcript_retention_days: int = 60,
    summary_retention_days: int = 180,
) -> tuple[int, int]:
    """
    Remove old transcripts and summaries based on retention policies.

    Transcripts have shorter retention (bulky, debug-only).
    Summaries have longer retention (compact, decision-relevant).

    Args:
        repo: RepositoryIO instance
        transcript_retention_days: Days to retain full transcripts (default 60)
        summary_retention_days: Days to retain summaries (default 180)

    Returns:
        Tuple of (transcripts_deleted, summaries_deleted)
    """
    ...


def format_session_markdown(session: Session) -> str:
    """
    Format session as markdown for file storage.
    """
    ...
```

### 4.3 Error Types

```python
class LoggerError(Exception):
    """Base error for logging operations"""
    pass


class SessionNotFoundError(LoggerError):
    """Session file not found"""
    def __init__(self, session_id: str):
        super().__init__(f"Session not found: {session_id}")
        self.session_id = session_id
```

## 5. Core Algorithms

### 5.1 Session Management

```python
import uuid
from datetime import datetime


_current_session: Optional[Session] = None


def start_session(athlete_name: str) -> Session:
    """Start a new conversation session."""
    global _current_session

    session = Session(
        id=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        athlete_name=athlete_name,
        started_at=datetime.now(),
        ended_at=None,
        messages=[],
    )

    _current_session = session
    return session


def log_message(
    session: Session,
    role: MessageRole,
    content: str,
    metadata: Optional[dict] = None,
) -> Message:
    """Add a message to the session."""
    message = Message(
        timestamp=datetime.now(),
        role=role,
        content=content,
        metadata=metadata,
    )

    session.messages.append(message)
    return message


def end_session(
    session: Session,
    repo: "RepositoryIO",
) -> tuple[str, str]:
    """End session, persist transcript, and generate summary."""
    global _current_session

    session.ended_at = datetime.now()

    # 1. Persist full transcript
    transcript_path = persist_transcript(session, repo)

    # 2. Generate session summary (synchronous, ~2-3s)
    summary = generate_session_summary(session, repo)

    # 3. Persist summary
    summary_path = persist_summary(session, summary, repo)

    _current_session = None
    return transcript_path, summary_path


def get_current_session() -> Optional[Session]:
    """Get the current active session."""
    return _current_session
```

### 5.2 Markdown Formatting

````python
def format_session_markdown(session: Session) -> str:
    """
    Format session as readable markdown.

    Output format:
    ```
    # Conversation — March 15, 2025

    **Athlete:** John Doe
    **Session:** 10:30 AM - 10:45 AM

    ---

    **10:30:15** [user]
    > sync my strava

    **10:30:18** [coach]
    > Syncing your Strava activities...

    **10:30:25** [coach]
    > ## Sync Complete ✓
    > **3 new activities imported:**
    > ...
    ```
    """
    lines = []

    # Header
    date_str = session.started_at.strftime("%B %d, %Y")
    lines.append(f"# Conversation — {date_str}")
    lines.append("")

    # Session info
    lines.append(f"**Athlete:** {session.athlete_name}")
    start_time = session.started_at.strftime("%I:%M %p")
    end_time = session.ended_at.strftime("%I:%M %p") if session.ended_at else "ongoing"
    lines.append(f"**Session:** {start_time} - {end_time}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Messages
    for message in session.messages:
        timestamp = message.timestamp.strftime("%H:%M:%S")
        role = message.role.value
        lines.append(f"**{timestamp}** [{role}]")

        # Quote the content
        content_lines = message.content.split("\n")
        for content_line in content_lines:
            lines.append(f"> {content_line}")
        lines.append("")

    return "\n".join(lines)
````

### 5.3 Persistence

```python
from pathlib import Path


def persist_transcript(
    session: Session,
    repo: "RepositoryIO",
) -> str:
    """Write full session transcript to conversations/transcripts directory."""
    # Generate filename
    date_str = session.started_at.strftime("%Y-%m-%d")
    time_str = session.started_at.strftime("%H%M")

    # Check for existing sessions on same day
    transcripts_dir = "conversations/transcripts"
    existing = repo.list_files(transcripts_dir, pattern=f"{date_str}*.md")

    if existing:
        # Add time suffix for uniqueness
        filename = f"{date_str}_{time_str}_session.md"
    else:
        filename = f"{date_str}_session.md"

    filepath = f"{transcripts_dir}/{filename}"

    # Format and write
    content = format_session_markdown(session)
    repo.write_text(filepath, content)

    return filepath


def persist_summary(
    session: Session,
    summary: str,
    repo: "RepositoryIO",
) -> str:
    """Write session summary to conversations/summaries directory."""
    # Generate filename (matching transcript naming)
    date_str = session.started_at.strftime("%Y-%m-%d")
    time_str = session.started_at.strftime("%H%M")

    # Check for existing summaries on same day
    summaries_dir = "conversations/summaries"
    existing = repo.list_files(summaries_dir, pattern=f"{date_str}*.md")

    if existing:
        # Add time suffix for uniqueness
        filename = f"{date_str}_{time_str}_summary.md"
    else:
        filename = f"{date_str}_summary.md"

    filepath = f"{summaries_dir}/{filename}"

    # Add header to summary
    header = f"# Session Summary — {session.started_at.strftime('%B %d, %Y')}\n\n"
    header += f"**Duration**: {session.started_at.strftime('%I:%M %p')}"
    if session.ended_at:
        header += f" - {session.ended_at.strftime('%I:%M %p')}"
    header += f"\n**Athlete**: {session.athlete_name}\n\n"

    full_content = header + summary

    # Write summary
    repo.write_text(filepath, full_content)

    return filepath


def load_session(
    session_path: str,
    repo: "RepositoryIO",
) -> Session:
    """Load session from markdown file."""
    content = repo.read_text(session_path)
    return _parse_session_markdown(content, session_path)


def _parse_session_markdown(content: str, path: str) -> Session:
    """Parse markdown back into Session object."""
    lines = content.split("\n")

    # Extract header info
    athlete_name = "Unknown"
    started_at = datetime.now()
    messages = []

    for i, line in enumerate(lines):
        if line.startswith("**Athlete:**"):
            athlete_name = line.replace("**Athlete:**", "").strip()

        if line.startswith("**Session:**"):
            # Parse time range
            time_part = line.replace("**Session:**", "").strip()
            start_str = time_part.split(" - ")[0]
            # Would need date from filename for full datetime

        # Parse messages
        if line.startswith("**") and "[" in line and "]" in line:
            # Extract timestamp and role
            timestamp_match = re.search(r'\*\*(\d{2}:\d{2}:\d{2})\*\*', line)
            role_match = re.search(r'\[(\w+)\]', line)

            if timestamp_match and role_match:
                time_str = timestamp_match.group(1)
                role_str = role_match.group(1)

                # Collect content (quoted lines following)
                content_lines = []
                j = i + 1
                while j < len(lines) and lines[j].startswith(">"):
                    content_lines.append(lines[j][2:])  # Remove "> "
                    j += 1

                messages.append(Message(
                    timestamp=_parse_time(time_str, started_at),
                    role=MessageRole(role_str),
                    content="\n".join(content_lines),
                ))

    return Session(
        id=Path(path).stem,
        athlete_name=athlete_name,
        started_at=started_at,
        ended_at=None,
        messages=messages,
    )
```

### 5.4 Session Listing

```python
def list_sessions(
    repo: "RepositoryIO",
    limit: int = 10,
) -> list[SessionSummary]:
    """List recent sessions with metadata (not full content)."""
    files = repo.list_files("conversations/transcripts", pattern="*.md")

    # Sort by filename (date-based)
    files.sort(reverse=True)

    summaries = []
    for filepath in files[:limit]:
        try:
            session = load_session(filepath, repo)
            duration = 0
            if session.ended_at and session.started_at:
                duration = int((session.ended_at - session.started_at).total_seconds() / 60)

            # Extract topics (simple: first user message)
            topics = []
            for msg in session.messages:
                if msg.role == MessageRole.USER:
                    words = msg.content.lower().split()[:5]
                    topics.extend(words)
                    break

            summaries.append(SessionSummary(
                id=session.id,
                date=session.started_at.strftime("%Y-%m-%d"),
                message_count=len(session.messages),
                duration_minutes=duration,
                topics=topics[:3],
            ))
        except Exception:
            continue

    return summaries


def list_session_summaries(
    repo: "RepositoryIO",
    limit: int = 10,
) -> list[str]:
    """
    List recent session summaries (full summary content).

    Used by M1 for loading historical context efficiently.
    Returns summaries sorted by date (most recent first).

    Returns:
        List of summary markdown strings
    """
    files = repo.list_files("conversations/summaries", pattern="*.md")

    # Sort by filename (date-based), most recent first
    files.sort(reverse=True)

    summaries = []
    for filepath in files[:limit]:
        try:
            summary_content = repo.read_text(filepath)
            summaries.append(summary_content)
        except Exception:
            continue

    return summaries
```

### 5.5 Cleanup

```python
from datetime import timedelta


def cleanup_old_sessions(
    repo: "RepositoryIO",
    transcript_retention_days: int = 60,
    summary_retention_days: int = 180,
) -> tuple[int, int]:
    """Remove old transcripts and summaries based on retention policies."""
    now = datetime.now()
    transcript_cutoff = now - timedelta(days=transcript_retention_days)
    summary_cutoff = now - timedelta(days=summary_retention_days)

    transcript_cutoff_str = transcript_cutoff.strftime("%Y-%m-%d")
    summary_cutoff_str = summary_cutoff.strftime("%Y-%m-%d")

    # Clean up transcripts
    transcript_files = repo.list_files("conversations/transcripts", pattern="*.md")
    transcripts_deleted = 0

    for filepath in transcript_files:
        filename = Path(filepath).name
        file_date = filename[:10]  # YYYY-MM-DD

        if file_date < transcript_cutoff_str:
            repo.delete_file(filepath)
            transcripts_deleted += 1

    # Clean up summaries
    summary_files = repo.list_files("conversations/summaries", pattern="*.md")
    summaries_deleted = 0

    for filepath in summary_files:
        filename = Path(filepath).name
        file_date = filename[:10]  # YYYY-MM-DD

        if file_date < summary_cutoff_str:
            repo.delete_file(filepath)
            summaries_deleted += 1

    return transcripts_deleted, summaries_deleted
```

### 5.6 Session Summary Generation

```python
def generate_session_summary(
    session: Session,
    repo: "RepositoryIO",
) -> str:
    """
    Generate compact session summary using Claude Code instance.

    This function prepares the session transcript and returns a prompt
    that will be used by M1 to ask Claude to generate the summary.

    Process:
        1. Format full session transcript
        2. Write transcript to temporary file for Claude to read
        3. Return structured prompt for summary generation
        4. M1 sends this prompt to Claude (current session)
        5. Claude reads transcript and generates summary
        6. M1 receives summary and passes to persist_summary()

    Returns:
        Summary markdown string (generated by Claude)
    """
    # Format the full conversation
    full_transcript = format_session_markdown(session)

    # Write transcript to temp file for Claude to read
    temp_path = f"/tmp/session_{session.id}_transcript.md"
    with open(temp_path, "w") as f:
        f.write(full_transcript)

    # In actual implementation, M1 will coordinate with Claude to generate summary
    # For now, return the prompt that M1 will use
    summary_prompt = f"""Please summarize the conversation transcript at {temp_path}.

Extract ONLY the decision-relevant information that would help the coach make better recommendations in future sessions.

Generate a compact summary (10-20 lines max) with these sections:

**User Concerns**: What questions, worries, or issues did the athlete raise?
**Decisions**: What choices were made (workout modifications, plan changes, goal adjustments)?
**Metrics Context**: Key metrics at the time (CTL, ATL, TSB, ACWR, readiness)
**Adaptations**: Were any automatic adaptations triggered? Why?
**Follow-up**: Any action items or things to monitor?

EXCLUDE:
- Routine status messages ("Syncing Strava...")
- Conversational pleasantries
- Verbose workout formatting
- Repeated metric explanations

Be concise. Focus on what a coach needs to know for future decisions.

Format as markdown with the sections above."""

    # NOTE: In production, this will be called by M1 which will handle
    # the interaction with Claude to generate and receive the summary.
    # This is a simplified version showing the prompt structure.

    # Fallback: If Claude coordination is not yet implemented,
    # generate a basic summary from key messages
    return _generate_fallback_summary(session)


def _generate_fallback_summary(session: Session) -> str:
    """
    Generate basic summary when Claude summary generation is not available.

    Extracts:
    - First user message (likely main question)
    - Any decision points
    - Session duration
    """
    lines = ["## Key Points", ""]

    # Extract first user message
    user_messages = [m for m in session.messages if m.role == MessageRole.USER]
    if user_messages:
        first_msg = user_messages[0]
        lines.append(f"**User Question**: {first_msg.content[:200]}...")
        lines.append("")

    # Count messages
    lines.append(f"**Messages**: {len(session.messages)} total")
    lines.append(f"**User messages**: {len(user_messages)}")
    lines.append("")

    # Note that this is a fallback
    lines.append("*(Basic summary - full Claude-generated summary not yet available)*")

    return "\n".join(lines)
```

## 6. Data Structures

### 6.1 Conversation File Format

```markdown
# Conversation — March 15, 2025

**Athlete:** Alex Runner
**Session:** 10:30 AM - 10:52 AM

---

**10:30:15** [user]

> sync my strava

**10:30:18** [coach]

> Syncing your Strava activities...

**10:30:25** [coach]

> ## Sync Complete ✓
>
> **3 new activities imported:**
>
> - Trail Running (12.5km, 1h 5min) ✓
> - Bouldering (2h) ✓
> - Easy Run (5km, 28min) ✓
>
> **Metrics updated:**
>
> - Fitness (CTL): ↑ 1.2

**10:31:00** [user]

> what should I do today?

**10:31:05** [coach]

> ## Saturday March 15th
>
> **Long Run**
>
> - Duration: 90 minutes
> - Intensity: RPE 5/10 — Easy aerobic
>   ...

**10:35:20** [user]

> my knee feels a bit tight, should I still go?

**10:35:28** [coach]

> I'd suggest being cautious. Since you mentioned knee tightness:
>
> **Option 1:** Proceed with the long run but keep it very easy
> (RPE 4 max) and cut short if the tightness worsens.
>
> **Option 2:** Swap to an easy 45-minute run instead.
>
> Which would you prefer?
```

### 6.2 Directory Structure

```
conversations/
  transcripts/                    # Full verbatim conversation logs
    ├── 2025-03-15_session.md
    ├── 2025-03-14_session.md
    ├── 2025-03-14_1830_session.md  # Second session same day
    └── ...
  summaries/                      # Compact decision summaries
    ├── 2025-03-15_summary.md
    ├── 2025-03-14_summary.md
    ├── 2025-03-14_1830_summary.md
    └── ...
```

**Rationale for Two-Tier Structure:**
- **Transcripts** (60-day retention): Full audit trail for debugging, bulky (~2000 tokens each)
- **Summaries** (180-day retention): Decision-relevant context for coaching, compact (~150 tokens each)
- M1 loads summaries for efficient context (10x token reduction)
- Full transcripts available on-demand for user recall or debugging

## 7. Integration Points

**Integration with API Layer:**

This module is called internally by M1 workflows to automatically log all user interactions. Conversation logging is transparent to Claude Code and happens behind the scenes.

**Logging Flow:**

```
User interaction:
    Claude Code (receives user message)
        ↓
    M1::process_message()
        ↓ (automatic)
    M14::log_message(role=USER, content=message)
        ↓
    M14::log_message(role=COACH, content=response)
        ↓
    Session maintained in memory

Session end:
    M1::end_conversation_session()
        ↓
    M14::end_session()
        ↓
    M14::persist_transcript() → conversations/transcripts/YYYY-MM-DD_session.md
        ↓
    M14::generate_session_summary() → uses Claude Code to summarize
        ↓
    M14::persist_summary() → conversations/summaries/YYYY-MM-DD_summary.md

Future sessions (context loading):
    M1::load_recent_context()
        ↓
    M14::list_session_summaries(limit=5) → returns summaries
        ↓ (efficient)
    M1 includes summaries in system context
```

**Note:** Summaries are used for efficient context loading (10x token reduction vs full transcripts).

### 7.1 Called By

| Module | When                   |
| ------ | ---------------------- |
| M1     | On each user message   |
| M1     | On each coach response |
| M1     | Session start/end      |

### 7.2 Calls To

| Module | Purpose                  |
| ------ | ------------------------ |
| M3     | Write conversation files |

### 7.3 Data Flow

```
[User Input]
      │
      ▼
[M1 Orchestrator] ──────────────────────────────┐
      │                                          │
      ├── log_message(user, content) ───────────►│
      │                                          │
      ▼                                          │
[Process & Generate Response]                    │
      │                                          │
      ├── log_message(coach, response) ─────────►│
      │                                          │
      ▼                                          ▼
[User sees response]                    [M14 Conversation Logger]
                                                 │
                                                 ▼
                                        [conversations/*.md]
```

## 8. Test Scenarios

### 8.1 Unit Tests

```python
def test_start_session():
    """Session starts with correct defaults"""
    session = start_session("Test Athlete")

    assert session.athlete_name == "Test Athlete"
    assert session.messages == []
    assert session.ended_at is None


def test_log_message():
    """Messages are logged with timestamps"""
    session = start_session("Test")
    before = datetime.now()

    msg = log_message(session, MessageRole.USER, "Hello")

    assert len(session.messages) == 1
    assert msg.role == MessageRole.USER
    assert msg.content == "Hello"
    assert msg.timestamp >= before


def test_format_markdown():
    """Session formats to readable markdown"""
    session = start_session("Alex")
    log_message(session, MessageRole.USER, "sync strava")
    log_message(session, MessageRole.COACH, "Syncing...")

    md = format_session_markdown(session)

    assert "# Conversation" in md
    assert "**Athlete:** Alex" in md
    assert "[user]" in md
    assert "[coach]" in md
    assert "sync strava" in md


def test_multiline_content():
    """Multiline content is properly quoted"""
    session = start_session("Test")
    log_message(session, MessageRole.COACH, "Line 1\nLine 2\nLine 3")

    md = format_session_markdown(session)

    assert "> Line 1" in md
    assert "> Line 2" in md
    assert "> Line 3" in md
```

### 8.2 Integration Tests

```python
@pytest.mark.integration
def test_persist_and_load():
    """Session persists and loads correctly"""
    repo = MockRepositoryIO()
    session = start_session("Test")
    log_message(session, MessageRole.USER, "Test message")

    path = end_session(session, repo)
    loaded = load_session(path, repo)

    assert loaded.athlete_name == "Test"
    assert len(loaded.messages) == 1
    assert loaded.messages[0].content == "Test message"
```

## 9. Configuration

### 9.1 Logger Settings

```python
LOGGER_CONFIG = {
    # Retention policies (two-tier)
    "transcript_retention_days": 60,   # Full transcripts: shorter retention
    "summary_retention_days": 180,     # Summaries: longer retention

    # Summary generation
    "summary_enabled": True,            # Enable automatic summary generation
    "summary_fallback_enabled": True,   # Use fallback if Claude unavailable

    # Message handling
    "max_message_length": 10000,
    "include_metadata": False,          # Include metadata in markdown
    "auto_persist_interval": 5,         # Messages between auto-saves
}
```

**Rationale:**
- **Transcript retention**: 60 days sufficient for debugging recent issues
- **Summary retention**: 180 days provides longer-term coaching context
- **Summary generation**: Uses existing Claude Code session, no external API
- **Fallback mode**: Basic summary if Claude coordination unavailable

## 10. Privacy Notes

- All conversations (transcripts + summaries) stored locally only
- Summary generation uses existing Claude Code session (no external API calls)
- No data transmitted to external services
- User can delete any transcript or summary
- Automatic retention policies:
  - Transcripts: 60 days (bulky debug logs)
  - Summaries: 180 days (compact coaching context)
- User can disable summary generation (transcript-only mode via config)
