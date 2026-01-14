"""
M14 - Conversation Logger

Two-tier conversation logging for auditability and efficient context loading.

Architecture:
- Tier 1 (Transcripts): Full verbatim logs in JSONL format (60-day retention)
- Tier 2 (Summaries): Compact decision summaries in JSON format (180-day retention)

Token Efficiency:
- Full transcript: ~500-2000 tokens per session
- Compact summary: ~50-100 tokens per session
- 10x reduction when loading recent context

File Structure:
conversations/
├── transcripts/YYYY-MM/
│   └── 2026-01-15_session_001.jsonl  # One message per line
└── summaries/YYYY-MM/
    └── 2026-01-15_summary.json       # Daily summary

Session Boundaries:
- Start: First message of day OR 30+ min idle timeout
- End: 30 min idle OR explicit end OR midnight
- Session ID: YYYY-MM-DD_session_NNN
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from sports_coach_engine.core.paths import (
    transcripts_dir,
    summaries_dir,
    transcript_path,
    summary_path,
)
from sports_coach_engine.core.repository import RepositoryIO


# ============================================================
# ERROR TYPES
# ============================================================


class LoggerError(Exception):
    """Base exception for logger errors."""

    pass


class SessionNotFoundError(LoggerError):
    """Session does not exist."""

    pass


# ============================================================
# ENUMS & TYPES
# ============================================================


class MessageRole(str, Enum):
    """Message role in conversation."""

    USER = "user"
    COACH = "coach"
    SYSTEM = "system"


class SearchMode(str, Enum):
    """Search mode for conversations."""

    TOPIC = "topic"
    DATE_RANGE = "date_range"
    CONTENT = "content"


# ============================================================
# DATA MODELS
# ============================================================


@dataclass
class Message:
    """Single conversation message."""

    timestamp: datetime
    role: MessageRole
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "role": self.role.value if isinstance(self.role, MessageRole) else self.role,
            "content": self.content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            role=MessageRole(data["role"]),
            content=data["content"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class SessionState:
    """Current session state (in-memory)."""

    id: str
    athlete_name: str
    started_at: datetime
    last_activity_at: datetime
    message_count: int = 0
    topics: set[str] = field(default_factory=set)
    key_decisions: list[str] = field(default_factory=list)
    is_active: bool = True


@dataclass
class SessionSummary:
    """Compact session summary for efficient context loading."""

    id: str
    date: date
    started_at: datetime
    ended_at: datetime
    message_count: int
    duration_minutes: int
    topics: list[str]
    key_decisions: list[str]
    metrics_snapshot: Optional[dict] = None


@dataclass
class Session:
    """Full session with all messages."""

    id: str
    athlete_name: str
    started_at: datetime
    ended_at: Optional[datetime]
    messages: list[Message]


# ============================================================
# CONSTANTS
# ============================================================

# Session timeouts
SESSION_IDLE_TIMEOUT_MINUTES = 30

# Retention periods (days)
TRANSCRIPT_RETENTION_DAYS = 60
SUMMARY_RETENTION_DAYS = 180

# Topic keywords for deterministic extraction
TOPIC_KEYWORDS = {
    "strava_sync": ["sync", "import", "strava", "activities"],
    "workout_recommendation": ["workout", "should i do", "todays", "today's"],
    "acwr_elevated": ["acwr", "1.3", "1.4", "1.5", "injury risk", "workload"],
    "injury_flag": ["pain", "injured", "hurts", "sore", "strain"],
    "illness_flag": ["sick", "fever", "flu", "cold", "ill"],
    "goal_change": ["new goal", "change goal", "race date", "target"],
    "suggestion_accepted": ["accept", "yes", "ok", "sounds good", "let's do"],
    "suggestion_declined": ["decline", "no", "keep original", "i'll do it anyway"],
    "plan_generated": ["generate", "create plan", "new plan"],
    "profile_updated": ["update profile", "change settings", "preferences"],
}


# ============================================================
# SESSION MANAGEMENT
# ============================================================


# Global session state (in-memory)
_current_session: Optional[SessionState] = None


def start_session(
    repo: RepositoryIO,
    athlete_name: str,
) -> str:
    """
    Start a new conversation session.

    Args:
        repo: Repository for file operations
        athlete_name: Name of athlete

    Returns:
        Session ID (e.g., "2026-01-15_session_001")
    """
    global _current_session

    # End previous session if active
    if _current_session and _current_session.is_active:
        end_session(repo)

    # Generate session ID
    today = date.today()
    session_number = _get_next_session_number(repo, today)
    session_id = f"{today.isoformat()}_session_{session_number:03d}"

    # Create session state
    _current_session = SessionState(
        id=session_id,
        athlete_name=athlete_name,
        started_at=datetime.now(timezone.utc),
        last_activity_at=datetime.now(timezone.utc),
    )

    print(f"[Logger] Started session: {session_id}")

    return session_id


def end_session(repo: RepositoryIO) -> Optional[SessionSummary]:
    """
    End current session and generate summary.

    Args:
        repo: Repository for file operations

    Returns:
        SessionSummary if session was active, None otherwise
    """
    global _current_session

    if not _current_session or not _current_session.is_active:
        return None

    # Load transcript
    transcript_path = _get_transcript_path(_current_session.id)
    messages = []

    if repo.file_exists(transcript_path):
        # Read JSONL transcript
        content = repo.read_file(transcript_path)
        for line in content.strip().split("\n"):
            if line.strip():
                msg_data = json.loads(line)
                messages.append(Message.from_dict(msg_data))

    # Generate summary
    summary = _generate_summary(_current_session, messages)

    # Save summary
    summary_path = _get_summary_path(_current_session.started_at.date())
    repo.write_json(summary_path, summary.__dict__)

    # Mark session as inactive
    _current_session.is_active = False

    print(
        f"[Logger] Ended session: {_current_session.id} "
        f"({len(messages)} messages, {summary.duration_minutes} min)"
    )

    return summary


def should_start_new_session(last_message_time: Optional[datetime]) -> bool:
    """
    Determine if new session should start.

    Args:
        last_message_time: Timestamp of last message

    Returns:
        True if new session should start
    """
    if last_message_time is None:
        return True

    now = datetime.now(timezone.utc)

    # New day
    if last_message_time.date() < now.date():
        return True

    # Idle timeout (30 minutes)
    time_since_last = now - last_message_time
    if time_since_last > timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES):
        return True

    return False


# ============================================================
# MESSAGE LOGGING
# ============================================================


def log_message(
    repo: RepositoryIO,
    role: MessageRole,
    content: str,
    metadata: Optional[dict] = None,
) -> None:
    """
    Log a conversation message to current session.

    Creates new session if none active or session timed out.

    Args:
        repo: Repository for file operations
        role: Message role (user, coach, system)
        content: Message content
        metadata: Optional metadata (metrics, triggers, etc.)
    """
    global _current_session

    # Auto-start session if needed
    if _current_session is None:
        # Try to load athlete name from profile
        try:
            from sports_coach_engine.core.profile import ProfileService

            profile_service = ProfileService(repo)
            profile = profile_service.load_profile()
            athlete_name = profile.name
        except Exception:
            athlete_name = "Athlete"

        start_session(repo, athlete_name)

    # Check if session timed out
    elif should_start_new_session(_current_session.last_activity_at):
        end_session(repo)
        start_session(repo, _current_session.athlete_name)

    # Create message
    message = Message(
        timestamp=datetime.now(timezone.utc),
        role=role,
        content=content,
        metadata=metadata or {},
    )

    # Append to JSONL transcript
    transcript_path = _get_transcript_path(_current_session.id)
    repo.ensure_directory(Path(transcript_path).parent)

    # Append as single line
    message_line = json.dumps(message.to_dict()) + "\n"
    repo.append_to_file(transcript_path, message_line)

    # Update session state
    _current_session.last_activity_at = message.timestamp
    _current_session.message_count += 1

    # Extract topics (deterministic keyword matching)
    content_lower = content.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in content_lower for kw in keywords):
            _current_session.topics.add(topic)

    # Extract key decisions (user responses to suggestions)
    if role == MessageRole.USER:
        if any(kw in content_lower for kw in ["accept", "yes", "ok", "let's"]):
            _current_session.key_decisions.append(f"User accepted: {content[:50]}")
        elif any(kw in content_lower for kw in ["decline", "no", "keep"]):
            _current_session.key_decisions.append(f"User declined: {content[:50]}")


# ============================================================
# SESSION RETRIEVAL
# ============================================================


def get_session_transcript(
    repo: RepositoryIO,
    session_id: str,
) -> Session:
    """
    Retrieve full session transcript.

    Args:
        repo: Repository for file operations
        session_id: Session ID (e.g., "2026-01-15_session_001")

    Returns:
        Session with all messages

    Raises:
        SessionNotFoundError: If session does not exist
    """
    try:
        transcript_path = _get_transcript_path(session_id)
    except (ValueError, IndexError):
        # Invalid session ID format
        raise SessionNotFoundError(f"Invalid session ID format: {session_id}")

    if not repo.file_exists(transcript_path):
        raise SessionNotFoundError(f"Session not found: {session_id}")

    # Read JSONL transcript
    content = repo.read_file(transcript_path)
    messages = []

    for line in content.strip().split("\n"):
        if line.strip():
            msg_data = json.loads(line)
            messages.append(Message.from_dict(msg_data))

    # Parse session metadata from ID
    date_str = session_id.split("_session_")[0]
    session_date = datetime.fromisoformat(date_str).date()

    return Session(
        id=session_id,
        athlete_name="Athlete",  # Not stored in transcript
        started_at=messages[0].timestamp if messages else datetime.now(timezone.utc),
        ended_at=messages[-1].timestamp if messages else None,
        messages=messages,
    )


def get_recent_summaries(
    repo: RepositoryIO,
    days: int = 7,
) -> list[SessionSummary]:
    """
    Get recent session summaries for context loading.

    Args:
        repo: Repository for file operations
        days: Number of days to look back

    Returns:
        List of SessionSummary objects, most recent first
    """
    summaries = []
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Iterate through date range
    current_date = start_date
    while current_date <= end_date:
        summary_path = _get_summary_path(current_date)

        if repo.file_exists(summary_path):
            try:
                summary_data = repo.read_json(summary_path)
                summary = SessionSummary(**summary_data)
                summaries.append(summary)
            except Exception as e:
                print(f"[Logger] Error loading summary for {current_date}: {e}")

        current_date += timedelta(days=1)

    # Sort by date (most recent first)
    summaries.sort(key=lambda s: s.started_at, reverse=True)

    return summaries


# ============================================================
# SEARCH
# ============================================================


def search_conversations(
    repo: RepositoryIO,
    query: str,
    mode: SearchMode = SearchMode.TOPIC,
    limit: int = 10,
) -> list[SessionSummary]:
    """
    Search conversations by topic, date range, or content.

    Args:
        repo: Repository for file operations
        query: Search query (topic name, date range, or content keywords)
        mode: Search mode (topic, date_range, content)
        limit: Maximum results to return

    Returns:
        List of matching SessionSummary objects
    """
    results = []

    if mode == SearchMode.TOPIC:
        # Search summaries by topic
        results = _search_by_topic(repo, query, limit)

    elif mode == SearchMode.DATE_RANGE:
        # Parse date range (format: "2026-01-01:2026-01-15")
        try:
            start_str, end_str = query.split(":")
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
            results = _search_by_date_range(repo, start_date, end_date, limit)
        except (ValueError, IndexError):
            print(f"[Logger] Invalid date range format: {query}")

    elif mode == SearchMode.CONTENT:
        # Grep through transcripts
        results = _search_content(repo, query, limit)

    return results


def _search_by_topic(
    repo: RepositoryIO,
    topic: str,
    limit: int,
) -> list[SessionSummary]:
    """Search summaries containing a specific topic."""
    results = []

    # Search last 60 days (transcript retention period)
    end_date = date.today()
    start_date = end_date - timedelta(days=TRANSCRIPT_RETENTION_DAYS)

    current_date = start_date
    while current_date <= end_date and len(results) < limit:
        summary_path = _get_summary_path(current_date)

        if repo.file_exists(summary_path):
            try:
                summary_data = repo.read_json(summary_path)
                summary = SessionSummary(**summary_data)

                # Check if topic in summary topics
                if topic in summary.topics:
                    results.append(summary)
            except Exception as e:
                print(f"[Logger] Error searching summary for {current_date}: {e}")

        current_date += timedelta(days=1)

    return results[:limit]


def _search_by_date_range(
    repo: RepositoryIO,
    start_date: date,
    end_date: date,
    limit: int,
) -> list[SessionSummary]:
    """Search summaries within date range."""
    results = []

    current_date = start_date
    while current_date <= end_date and len(results) < limit:
        summary_path = _get_summary_path(current_date)

        if repo.file_exists(summary_path):
            try:
                summary_data = repo.read_json(summary_path)
                summary = SessionSummary(**summary_data)
                results.append(summary)
            except Exception as e:
                print(f"[Logger] Error loading summary for {current_date}: {e}")

        current_date += timedelta(days=1)

    return results


def _search_content(
    repo: RepositoryIO,
    query: str,
    limit: int,
) -> list[SessionSummary]:
    """Grep through transcripts for content."""
    results = []
    query_lower = query.lower()

    # Search last 60 days
    end_date = date.today()
    start_date = end_date - timedelta(days=TRANSCRIPT_RETENTION_DAYS)

    current_date = start_date
    while current_date <= end_date and len(results) < limit:
        # Get all session transcripts for this date
        year_month = current_date.strftime("%Y-%m")
        transcripts_dir = transcripts_dir(year_month)

        if repo.directory_exists(transcripts_dir):
            try:
                files = repo.list_files(f"{transcripts_dir}/*.jsonl")

                for file_path in files:
                    if len(results) >= limit:
                        break

                    # Check if transcript contains query
                    content = repo.read_file(file_path)
                    if query_lower in content.lower():
                        # Extract session ID from filename
                        session_id = Path(file_path).stem

                        # Load corresponding summary
                        summary_path = _get_summary_path(current_date)
                        if repo.file_exists(summary_path):
                            summary_data = repo.read_json(summary_path)
                            summary = SessionSummary(**summary_data)
                            results.append(summary)

            except Exception as e:
                print(f"[Logger] Error searching content for {current_date}: {e}")

        current_date += timedelta(days=1)

    return results


# ============================================================
# CLEANUP
# ============================================================


def cleanup_old_conversations(repo: RepositoryIO) -> dict[str, int]:
    """
    Archive old conversations based on retention policy.

    - Transcripts: Delete after 60 days
    - Summaries: Delete after 180 days

    Args:
        repo: Repository for file operations

    Returns:
        Dictionary with cleanup stats
    """
    stats = {
        "transcripts_deleted": 0,
        "summaries_deleted": 0,
    }

    today = date.today()

    # Cleanup transcripts (60 days)
    transcript_cutoff = today - timedelta(days=TRANSCRIPT_RETENTION_DAYS)
    stats["transcripts_deleted"] = _cleanup_transcripts_before(repo, transcript_cutoff)

    # Cleanup summaries (180 days)
    summary_cutoff = today - timedelta(days=SUMMARY_RETENTION_DAYS)
    stats["summaries_deleted"] = _cleanup_summaries_before(repo, summary_cutoff)

    print(
        f"[Logger] Cleanup complete: {stats['transcripts_deleted']} transcripts, "
        f"{stats['summaries_deleted']} summaries deleted"
    )

    return stats


def _cleanup_transcripts_before(
    repo: RepositoryIO,
    cutoff_date: date,
) -> int:
    """Delete transcript files before cutoff date."""
    deleted_count = 0

    # Iterate through year-month directories
    current_date = cutoff_date - timedelta(days=60)  # Look back 2 months
    while current_date <= cutoff_date:
        year_month = current_date.strftime("%Y-%m")
        transcripts_dir = transcripts_dir(year_month)

        if repo.directory_exists(transcripts_dir):
            try:
                files = repo.list_files(f"{transcripts_dir}/*.jsonl")

                for file_path in files:
                    # Parse date from filename
                    filename = Path(file_path).stem
                    date_str = filename.split("_session_")[0]
                    file_date = datetime.fromisoformat(date_str).date()

                    if file_date < cutoff_date:
                        repo.delete_file(file_path)
                        deleted_count += 1

            except Exception as e:
                print(f"[Logger] Error cleaning transcripts for {year_month}: {e}")

        current_date += timedelta(days=30)  # Move to next month

    return deleted_count


def _cleanup_summaries_before(
    repo: RepositoryIO,
    cutoff_date: date,
) -> int:
    """Delete summary files before cutoff date."""
    deleted_count = 0

    # Iterate through year-month directories
    current_date = cutoff_date - timedelta(days=180)  # Look back 6 months
    while current_date <= cutoff_date:
        year_month = current_date.strftime("%Y-%m")
        summaries_dir = summaries_dir(year_month)

        if repo.directory_exists(summaries_dir):
            try:
                files = repo.list_files(f"{summaries_dir}/*.json")

                for file_path in files:
                    # Parse date from filename
                    filename = Path(file_path).stem
                    date_str = filename.replace("_summary", "")
                    file_date = datetime.fromisoformat(date_str).date()

                    if file_date < cutoff_date:
                        repo.delete_file(file_path)
                        deleted_count += 1

            except Exception as e:
                print(f"[Logger] Error cleaning summaries for {year_month}: {e}")

        current_date += timedelta(days=30)  # Move to next month

    return deleted_count


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _get_next_session_number(repo: RepositoryIO, target_date: date) -> int:
    """Get next available session number for a date."""
    year_month = target_date.strftime("%Y-%m")
    trans_dir = transcripts_dir(year_month)

    if not repo.directory_exists(trans_dir):
        return 1

    # Find existing sessions for this date
    date_str = target_date.isoformat()
    pattern = f"{transcripts_dir}/{date_str}_session_*.jsonl"

    try:
        files = repo.list_files(pattern)
        if not files:
            return 1

        # Extract session numbers
        numbers = []
        for file_path in files:
            filename = Path(file_path).stem
            match = re.search(r"session_(\d+)$", filename)
            if match:
                numbers.append(int(match.group(1)))

        return max(numbers) + 1 if numbers else 1

    except Exception:
        return 1


def _get_transcript_path(session_id: str) -> str:
    """Get file path for session transcript."""
    # Extract date from session ID (format: YYYY-MM-DD_session_NNN)
    date_str = session_id.split("_session_")[0]
    session_date = datetime.fromisoformat(date_str).date()
    year_month = session_date.strftime("%Y-%m")

    return transcript_path(year_month, session_id)


def _get_summary_path(target_date: date) -> str:
    """Get file path for session summary."""
    year_month = target_date.strftime("%Y-%m")
    date_str = target_date.isoformat()

    return summary_path(year_month, date_str)


def _generate_summary(
    session_state: SessionState,
    messages: list[Message],
) -> SessionSummary:
    """
    Generate compact summary from session state and messages.

    Uses deterministic keyword extraction (no LLM).

    Args:
        session_state: Current session state
        messages: Full message list

    Returns:
        SessionSummary with extracted topics and decisions
    """
    ended_at = datetime.now(timezone.utc)
    duration_minutes = int(
        (ended_at - session_state.started_at).total_seconds() / 60
    )

    # Extract metrics snapshot from last system message
    metrics_snapshot = None
    for message in reversed(messages):
        if message.role == MessageRole.SYSTEM and message.metadata:
            if "metrics" in message.metadata:
                metrics_snapshot = message.metadata["metrics"]
                break

    return SessionSummary(
        id=session_state.id,
        date=session_state.started_at.date(),
        started_at=session_state.started_at,
        ended_at=ended_at,
        message_count=len(messages),
        duration_minutes=duration_minutes,
        topics=list(session_state.topics),
        key_decisions=session_state.key_decisions,
        metrics_snapshot=metrics_snapshot,
    )
