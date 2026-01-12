# M1 — CLI/Conversation Orchestrator

## 1. Metadata

| Field        | Value                         |
| ------------ | ----------------------------- |
| Module ID    | M1                            |
| Name         | CLI/Conversation Orchestrator |
| Version      | 1.0.2                         |
| Status       | Draft                         |
| Dependencies | M2-M14 (all modules)          |

### Changelog

- **1.0.2** (2026-01-12): Added dynamic context loading from M14 session summaries. Context loading strategy varies by user intent (0-10 summaries). Enables efficient historical context without token bloat. New function: `get_context_for_intent()`.
- **1.0.1** (2026-01-12): Converted all dataclass types to BaseModel for consistency with other modules, ensuring serialization compatibility across the system.
- **1.0.0** (initial): Initial draft with comprehensive orchestration logic and intent parsing

## 2. Purpose

Parse user messages to identify intent, orchestrate the appropriate module workflow, and return formatted responses. This is the main entry point that ties all modules together.

### 2.1 Scope Boundaries

**In Scope:**

- Intent recognition from natural language
- Workflow orchestration across modules
- Session management (start, continue, end)
- User confirmation handling
- Error recovery and user-friendly messaging

**Out of Scope:**

- Actual LLM API calls (uses external LLM wrapper)
- File I/O (delegates to M3)
- Business logic (delegates to domain modules)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage                                                     |
| ------ | --------------------------------------------------------- |
| M2     | Load configuration and secrets                            |
| M3     | Repository I/O operations                                 |
| M4     | Profile service                                           |
| M5     | Activity ingestion                                        |
| M6     | Activity normalization                                    |
| M7     | Notes & RPE analysis                                      |
| M8     | Load calculation                                          |
| M9     | Metrics computation                                       |
| M10    | Plan generation                                           |
| M11    | Adaptation engine                                         |
| M12    | Response formatting                                       |
| M13    | Memory & insights                                         |
| M14    | Conversation logging + load session summaries for context |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
```

## 4. Public Interface

### 4.1 Type Definitions

```python
from datetime import date
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class UserIntent(str, Enum):
    """Recognized user intents"""
    # Core actions
    SYNC = "sync"                    # "sync my strava"
    TODAY = "today"                  # "what should I do today?"
    NEXT_WEEK = "next_week"          # "show me next week"
    STATUS = "status"                # "how am I doing?"

    # Plan management
    SET_GOAL = "set_goal"            # "I want to run a 10K in March"
    REGENERATE_PLAN = "regenerate"   # "regenerate my plan"
    ADJUST_WORKOUT = "adjust"        # "swap today to tomorrow"

    # Logging
    LOG_ACTIVITY = "log_activity"    # "I did a 5K easy run"
    LOG_WELLNESS = "log_wellness"    # "I slept poorly"

    # Profile
    UPDATE_PROFILE = "update_profile"  # "change my weekly runs to 4"
    SHOW_PROFILE = "show_profile"    # "show my profile"

    # Suggestions
    ACCEPT_SUGGESTION = "accept"     # "yes" / "accept" / "sounds good"
    DECLINE_SUGGESTION = "decline"   # "no" / "decline" / "skip"

    # Information
    EXPLAIN = "explain"              # "why this workout?"
    HISTORY = "history"              # "show my activities"
    METRICS = "metrics"              # "show my CTL"

    # Other
    GREETING = "greeting"            # "hello"
    HELP = "help"                    # "help" / "what can you do?"
    UNKNOWN = "unknown"              # Unrecognized intent


class ParsedIntent(BaseModel):
    """Result of intent parsing"""
    intent: UserIntent
    confidence: float              # 0.0-1.0
    entities: dict[str, Any]       # Extracted entities
    original_message: str


class ConversationContext(BaseModel):
    """Current conversation state"""
    session_id: str
    athlete_name: str
    pending_suggestion_id: Optional[str] = None  # Awaiting user response
    last_intent: Optional[UserIntent] = None
    turn_count: int


class OrchestratorResponse(BaseModel):
    """Response from orchestrator"""
    message: str                   # Formatted response for user
    intent_handled: UserIntent
    success: bool
    data: Optional[dict] = None    # Additional structured data
    follow_up_expected: bool = False  # Waiting for user response
```

### 4.2 Function Signatures

```python
def start_conversation(
    athlete_name: str,
    config: "AppConfig",
) -> ConversationContext:
    """
    Initialize a new conversation session.

    Returns:
        Fresh conversation context
    """
    ...


def process_message(
    message: str,
    context: ConversationContext,
    repo: "RepositoryIO",
    config: "AppConfig",
) -> tuple[OrchestratorResponse, ConversationContext]:
    """
    Process a user message and return response.

    This is the main entry point for handling user input.

    Args:
        message: User's natural language input
        context: Current conversation state
        repo: Repository for file operations
        config: Application configuration

    Returns:
        Tuple of (response to show user, updated context)
    """
    ...


def parse_intent(
    message: str,
    context: ConversationContext,
) -> ParsedIntent:
    """
    Parse user message to determine intent and extract entities.

    Uses keyword matching + context awareness for intent detection.
    """
    ...


def end_conversation(
    context: ConversationContext,
    repo: "RepositoryIO",
) -> str:
    """
    End the conversation session and persist transcript.

    Returns:
        Path to saved conversation file
    """
    ...


# Workflow handlers (internal)
def _handle_sync(
    entities: dict,
    context: ConversationContext,
    repo: "RepositoryIO",
    config: "AppConfig",
) -> OrchestratorResponse:
    """Handle sync intent - import activities from Strava"""
    ...


def _handle_today(
    entities: dict,
    context: ConversationContext,
    repo: "RepositoryIO",
    config: "AppConfig",
) -> OrchestratorResponse:
    """Handle today intent - get today's workout"""
    ...


def _handle_status(
    entities: dict,
    context: ConversationContext,
    repo: "RepositoryIO",
    config: "AppConfig",
) -> OrchestratorResponse:
    """Handle status intent - show current metrics and state"""
    ...
```

### 4.3 Error Types

```python
class OrchestratorError(Exception):
    """Base error for orchestration"""
    pass


class IntentParseError(OrchestratorError):
    """Could not determine user intent"""
    def __init__(self, message: str, original_input: str):
        super().__init__(f"Could not understand: {message}")
        self.original_input = original_input


class WorkflowError(OrchestratorError):
    """Error during workflow execution"""
    def __init__(self, intent: UserIntent, cause: str):
        super().__init__(f"Error handling {intent.value}: {cause}")
        self.intent = intent
        self.cause = cause
```

## 5. Core Algorithms

### 5.1 Main Processing Loop

```python
from typing import Callable
from datetime import datetime

# Import all modules
from sports_coach.m02_config import load_config, AppConfig
from sports_coach.m03_repository import RepositoryIO
from sports_coach.m04_profile import get_profile
from sports_coach.m05_ingestion import sync_strava, log_manual_activity
from sports_coach.m06_normalization import normalize_activity
from sports_coach.m07_notes_analyzer import analyze_activity_notes
from sports_coach.m08_load_engine import calculate_loads
from sports_coach.m09_metrics import compute_daily_metrics
from sports_coach.m10_plan_generator import get_todays_workout, generate_plan
from sports_coach.m11_adaptation import evaluate_adaptations, get_pending_suggestions
from sports_coach.m12_formatter import format_workout, format_status, format_sync_result
from sports_coach.m13_memory import extract_memories
from sports_coach.m14_logger import start_session, log_message, end_session, MessageRole


def process_message(
    message: str,
    context: ConversationContext,
    repo: RepositoryIO,
    config: AppConfig,
) -> tuple[OrchestratorResponse, ConversationContext]:
    """Main message processing logic."""

    # Log user message
    log_message(context.session_id, MessageRole.USER, message)

    # Parse intent
    parsed = parse_intent(message, context)

    # Check if this is a response to pending suggestion
    if context.pending_suggestion_id:
        if parsed.intent in (UserIntent.ACCEPT_SUGGESTION, UserIntent.DECLINE_SUGGESTION):
            response = _handle_suggestion_response(
                parsed.intent == UserIntent.ACCEPT_SUGGESTION,
                context.pending_suggestion_id,
                repo,
            )
            context = _update_context(context, parsed.intent, clear_pending=True)
        else:
            # User changed topic, clear pending suggestion
            context = _update_context(context, parsed.intent, clear_pending=True)
            response = _dispatch_intent(parsed, context, repo, config)
    else:
        response = _dispatch_intent(parsed, context, repo, config)

    # Log coach response
    log_message(context.session_id, MessageRole.COACH, response.message)

    # Extract memories from the conversation
    _extract_conversation_memories(message, response, repo)

    # Update context
    new_context = _update_context(
        context,
        parsed.intent,
        pending_suggestion=response.data.get("pending_suggestion_id") if response.data else None,
    )

    return response, new_context


def _dispatch_intent(
    parsed: ParsedIntent,
    context: ConversationContext,
    repo: RepositoryIO,
    config: AppConfig,
) -> OrchestratorResponse:
    """Route intent to appropriate handler."""

    handlers: dict[UserIntent, Callable] = {
        UserIntent.SYNC: _handle_sync,
        UserIntent.TODAY: _handle_today,
        UserIntent.NEXT_WEEK: _handle_next_week,
        UserIntent.STATUS: _handle_status,
        UserIntent.SET_GOAL: _handle_set_goal,
        UserIntent.REGENERATE_PLAN: _handle_regenerate,
        UserIntent.ADJUST_WORKOUT: _handle_adjust,
        UserIntent.LOG_ACTIVITY: _handle_log_activity,
        UserIntent.LOG_WELLNESS: _handle_log_wellness,
        UserIntent.UPDATE_PROFILE: _handle_update_profile,
        UserIntent.SHOW_PROFILE: _handle_show_profile,
        UserIntent.EXPLAIN: _handle_explain,
        UserIntent.HISTORY: _handle_history,
        UserIntent.METRICS: _handle_metrics,
        UserIntent.GREETING: _handle_greeting,
        UserIntent.HELP: _handle_help,
    }

    handler = handlers.get(parsed.intent, _handle_unknown)

    try:
        return handler(parsed.entities, context, repo, config)
    except Exception as e:
        return _handle_error(parsed.intent, e)
```

### 5.2 Intent Parsing

```python
import re
from typing import Optional


# Intent patterns (order matters - more specific first)
INTENT_PATTERNS: list[tuple[UserIntent, list[str], list[str]]] = [
    # (intent, required_keywords, optional_keywords)

    # Sync
    (UserIntent.SYNC, ["sync", "strava"], []),
    (UserIntent.SYNC, ["import", "activities"], []),
    (UserIntent.SYNC, ["fetch", "strava"], []),
    (UserIntent.SYNC, ["update", "strava"], []),

    # Today's workout
    (UserIntent.TODAY, ["today"], ["workout", "do", "should", "run"]),
    (UserIntent.TODAY, ["what", "should", "do"], []),
    (UserIntent.TODAY, ["workout"], ["my", "today"]),

    # Next week
    (UserIntent.NEXT_WEEK, ["next", "week"], []),
    (UserIntent.NEXT_WEEK, ["week", "ahead"], []),
    (UserIntent.NEXT_WEEK, ["coming", "week"], []),

    # Status
    (UserIntent.STATUS, ["how", "doing"], []),
    (UserIntent.STATUS, ["status"], []),
    (UserIntent.STATUS, ["current", "state"], []),
    (UserIntent.STATUS, ["where", "stand"], []),

    # Goal setting
    (UserIntent.SET_GOAL, ["goal"], ["set", "new", "change"]),
    (UserIntent.SET_GOAL, ["race"], ["target", "aiming"]),
    (UserIntent.SET_GOAL, ["want", "run"], ["marathon", "10k", "5k", "half"]),

    # Plan regeneration
    (UserIntent.REGENERATE_PLAN, ["regenerate", "plan"], []),
    (UserIntent.REGENERATE_PLAN, ["new", "plan"], []),
    (UserIntent.REGENERATE_PLAN, ["rebuild", "plan"], []),

    # Adjustments
    (UserIntent.ADJUST_WORKOUT, ["swap"], []),
    (UserIntent.ADJUST_WORKOUT, ["move", "workout"], []),
    (UserIntent.ADJUST_WORKOUT, ["skip"], ["today", "workout"]),
    (UserIntent.ADJUST_WORKOUT, ["can't", "today"], []),
    (UserIntent.ADJUST_WORKOUT, ["reschedule"], []),

    # Manual logging
    (UserIntent.LOG_ACTIVITY, ["did", "ran", "run"], ["km", "miles", "minutes"]),
    (UserIntent.LOG_ACTIVITY, ["log", "activity"], []),
    (UserIntent.LOG_ACTIVITY, ["add", "run"], []),
    (UserIntent.LOG_ACTIVITY, ["completed"], ["workout", "run"]),

    # Wellness logging
    (UserIntent.LOG_WELLNESS, ["feeling"], ["tired", "sick", "sore", "great"]),
    (UserIntent.LOG_WELLNESS, ["slept"], ["poorly", "bad", "well"]),
    (UserIntent.LOG_WELLNESS, ["tired"], []),
    (UserIntent.LOG_WELLNESS, ["sick"], []),
    (UserIntent.LOG_WELLNESS, ["injured"], []),
    (UserIntent.LOG_WELLNESS, ["pain"], []),

    # Profile
    (UserIntent.UPDATE_PROFILE, ["change", "profile"], []),
    (UserIntent.UPDATE_PROFILE, ["update", "profile"], []),
    (UserIntent.UPDATE_PROFILE, ["set", "runs", "week"], []),
    (UserIntent.SHOW_PROFILE, ["show", "profile"], []),
    (UserIntent.SHOW_PROFILE, ["my", "profile"], []),

    # Suggestions
    (UserIntent.ACCEPT_SUGGESTION, ["yes"], []),
    (UserIntent.ACCEPT_SUGGESTION, ["accept"], []),
    (UserIntent.ACCEPT_SUGGESTION, ["sounds", "good"], []),
    (UserIntent.ACCEPT_SUGGESTION, ["ok"], []),
    (UserIntent.ACCEPT_SUGGESTION, ["sure"], []),
    (UserIntent.DECLINE_SUGGESTION, ["no"], []),
    (UserIntent.DECLINE_SUGGESTION, ["decline"], []),
    (UserIntent.DECLINE_SUGGESTION, ["skip"], []),
    (UserIntent.DECLINE_SUGGESTION, ["don't", "want"], []),

    # Information
    (UserIntent.EXPLAIN, ["why"], ["workout", "this"]),
    (UserIntent.EXPLAIN, ["explain"], []),
    (UserIntent.HISTORY, ["history"], []),
    (UserIntent.HISTORY, ["activities"], ["recent", "show", "list"]),
    (UserIntent.HISTORY, ["what", "did"], ["last", "week"]),
    (UserIntent.METRICS, ["metrics"], []),
    (UserIntent.METRICS, ["ctl"], []),
    (UserIntent.METRICS, ["atl"], []),
    (UserIntent.METRICS, ["tsb"], []),
    (UserIntent.METRICS, ["acwr"], []),
    (UserIntent.METRICS, ["fitness"], ["score", "level"]),

    # Greeting
    (UserIntent.GREETING, ["hello"], []),
    (UserIntent.GREETING, ["hi"], []),
    (UserIntent.GREETING, ["hey"], []),
    (UserIntent.GREETING, ["good", "morning"], []),

    # Help
    (UserIntent.HELP, ["help"], []),
    (UserIntent.HELP, ["what", "can", "you"], []),
    (UserIntent.HELP, ["commands"], []),
]


def parse_intent(
    message: str,
    context: ConversationContext,
) -> ParsedIntent:
    """Parse intent from natural language message."""

    message_lower = message.lower()
    words = set(re.findall(r'\b\w+\b', message_lower))

    # Try pattern matching
    for intent, required, optional in INTENT_PATTERNS:
        required_set = set(required)
        if required_set.issubset(words):
            # Calculate confidence based on optional matches
            optional_matches = len(set(optional) & words)
            confidence = 0.7 + (0.1 * min(optional_matches, 3))

            entities = _extract_entities(message, intent)

            return ParsedIntent(
                intent=intent,
                confidence=min(confidence, 1.0),
                entities=entities,
                original_message=message,
            )

    # Context-aware fallback
    if context.pending_suggestion_id:
        # Assume affirmative if unclear
        if any(word in words for word in ["yeah", "yep", "okay", "fine"]):
            return ParsedIntent(
                intent=UserIntent.ACCEPT_SUGGESTION,
                confidence=0.5,
                entities={},
                original_message=message,
            )

    # Unknown intent
    return ParsedIntent(
        intent=UserIntent.UNKNOWN,
        confidence=0.0,
        entities={},
        original_message=message,
    )


def _extract_entities(message: str, intent: UserIntent) -> dict:
    """Extract relevant entities based on intent."""
    entities = {}
    message_lower = message.lower()

    if intent == UserIntent.SET_GOAL:
        # Extract race distance
        distance_patterns = [
            (r'marathon', 'marathon'),
            (r'half[- ]?marathon', 'half_marathon'),
            (r'10k', '10k'),
            (r'5k', '5k'),
        ]
        for pattern, value in distance_patterns:
            if re.search(pattern, message_lower):
                entities['race_distance'] = value
                break

        # Extract date
        date_match = re.search(
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s*(\d{1,2})?',
            message_lower
        )
        if date_match:
            entities['target_month'] = date_match.group(1)
            if date_match.group(2):
                entities['target_day'] = int(date_match.group(2))

    elif intent == UserIntent.LOG_ACTIVITY:
        # Extract distance
        dist_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:km|k|miles?|mi)', message_lower)
        if dist_match:
            value = float(dist_match.group(1))
            if 'mile' in message_lower or 'mi' in message_lower:
                value *= 1.609  # Convert to km
            entities['distance_km'] = value

        # Extract duration
        duration_match = re.search(r'(\d+)\s*(?:min|minutes?|hrs?|hours?)', message_lower)
        if duration_match:
            minutes = int(duration_match.group(1))
            if 'hour' in message_lower or 'hr' in message_lower:
                minutes *= 60
            entities['duration_minutes'] = minutes

        # Extract effort
        if any(word in message_lower for word in ['easy', 'recovery']):
            entities['intensity'] = 'easy'
        elif any(word in message_lower for word in ['tempo', 'threshold']):
            entities['intensity'] = 'tempo'
        elif any(word in message_lower for word in ['hard', 'intervals', 'speed']):
            entities['intensity'] = 'hard'

    elif intent == UserIntent.LOG_WELLNESS:
        # Extract wellness signals
        if 'tired' in message_lower or 'fatigue' in message_lower:
            entities['fatigue'] = True
        if 'sick' in message_lower or 'ill' in message_lower:
            entities['illness'] = True
        if 'pain' in message_lower or 'sore' in message_lower:
            entities['soreness'] = True
            # Try to extract location
            body_parts = ['knee', 'ankle', 'hip', 'back', 'shin', 'calf', 'hamstring', 'quad']
            for part in body_parts:
                if part in message_lower:
                    entities['pain_location'] = part
                    break
        if 'slept' in message_lower:
            if 'poor' in message_lower or 'bad' in message_lower:
                entities['sleep_quality'] = 'poor'
            elif 'well' in message_lower or 'good' in message_lower:
                entities['sleep_quality'] = 'good'

    elif intent == UserIntent.ADJUST_WORKOUT:
        # Extract adjustment type
        if 'skip' in message_lower:
            entities['adjustment'] = 'skip'
        elif 'swap' in message_lower or 'move' in message_lower:
            entities['adjustment'] = 'swap'
        elif 'easier' in message_lower or 'shorter' in message_lower:
            entities['adjustment'] = 'reduce'

    elif intent == UserIntent.HISTORY:
        # Extract time range
        if 'last week' in message_lower:
            entities['range'] = 'last_week'
        elif 'this week' in message_lower:
            entities['range'] = 'this_week'
        elif 'month' in message_lower:
            entities['range'] = 'month'

    return entities
```

### 5.3 Workflow Handlers

```python
from datetime import date, timedelta


def _handle_sync(
    entities: dict,
    context: ConversationContext,
    repo: RepositoryIO,
    config: AppConfig,
) -> OrchestratorResponse:
    """Sync activities from Strava."""

    # M5: Sync from Strava
    sync_result = sync_strava(
        config.strava_access_token,
        config.strava_refresh_token,
        repo,
    )

    if not sync_result.success:
        return OrchestratorResponse(
            message=f"Sync failed: {sync_result.error}",
            intent_handled=UserIntent.SYNC,
            success=False,
        )

    # Process each new activity through pipeline
    for raw_activity in sync_result.activities:
        # M6: Normalize
        normalized = normalize_activity(raw_activity)

        # M7: Analyze notes and estimate RPE
        analysis = analyze_activity_notes(normalized, repo)
        normalized = normalized.with_rpe(analysis.rpe_estimate.value)

        # M8: Calculate loads
        loads = calculate_loads(normalized)

        # M13: Extract memories
        if analysis.injury_flags or analysis.illness_flags:
            extract_memories(normalized, analysis, repo)

    # M9: Recompute metrics
    compute_daily_metrics(date.today(), repo)

    # M11: Check for adaptations
    suggestions = evaluate_adaptations(repo)

    # M12: Format response
    formatted = format_sync_result(sync_result, suggestions)

    return OrchestratorResponse(
        message=formatted,
        intent_handled=UserIntent.SYNC,
        success=True,
        data={
            "activities_imported": sync_result.new_count,
            "pending_suggestion_id": suggestions[0].id if suggestions else None,
        },
        follow_up_expected=bool(suggestions),
    )


def _handle_today(
    entities: dict,
    context: ConversationContext,
    repo: RepositoryIO,
    config: AppConfig,
) -> OrchestratorResponse:
    """Get today's workout recommendation."""

    # M4: Get profile
    profile = get_profile(context.athlete_name, repo)

    # M9: Get current metrics
    metrics = compute_daily_metrics(date.today(), repo)

    # M11: Check for pending adaptations
    suggestions = get_pending_suggestions(repo)
    if suggestions:
        # There are pending suggestions - remind user
        return OrchestratorResponse(
            message=format_pending_suggestion(suggestions[0]),
            intent_handled=UserIntent.TODAY,
            success=True,
            data={"pending_suggestion_id": suggestions[0].id},
            follow_up_expected=True,
        )

    # M10: Get today's workout from plan
    workout = get_todays_workout(date.today(), repo)

    if not workout:
        return OrchestratorResponse(
            message="No workout scheduled for today. Would you like me to generate a plan?",
            intent_handled=UserIntent.TODAY,
            success=True,
            data={"no_plan": True},
        )

    # M11: Evaluate if adaptation needed
    adaptations = evaluate_adaptations(repo, target_date=date.today())

    if adaptations:
        # Suggest adaptation
        suggestion = adaptations[0]
        formatted = format_workout_with_adaptation(workout, suggestion, metrics)
        return OrchestratorResponse(
            message=formatted,
            intent_handled=UserIntent.TODAY,
            success=True,
            data={"pending_suggestion_id": suggestion.id},
            follow_up_expected=True,
        )

    # M12: Format workout
    formatted = format_workout(workout, metrics, profile)

    return OrchestratorResponse(
        message=formatted,
        intent_handled=UserIntent.TODAY,
        success=True,
    )


def _handle_status(
    entities: dict,
    context: ConversationContext,
    repo: RepositoryIO,
    config: AppConfig,
) -> OrchestratorResponse:
    """Show current training status."""

    # M4: Get profile
    profile = get_profile(context.athlete_name, repo)

    # M9: Get current metrics
    metrics = compute_daily_metrics(date.today(), repo)

    # Get recent activity summary
    activities = repo.list_files("activities", pattern="*.yaml")
    recent_activities = activities[-7:]  # Last 7 activities

    # M12: Format status
    formatted = format_status(metrics, profile, recent_activities)

    return OrchestratorResponse(
        message=formatted,
        intent_handled=UserIntent.STATUS,
        success=True,
        data={"metrics": metrics.dict()},
    )


def _handle_set_goal(
    entities: dict,
    context: ConversationContext,
    repo: RepositoryIO,
    config: AppConfig,
) -> OrchestratorResponse:
    """Set a new race goal."""

    race_distance = entities.get('race_distance')
    target_month = entities.get('target_month')

    if not race_distance:
        return OrchestratorResponse(
            message="What race distance are you targeting? (5K, 10K, half marathon, marathon)",
            intent_handled=UserIntent.SET_GOAL,
            success=True,
            follow_up_expected=True,
        )

    if not target_month:
        return OrchestratorResponse(
            message=f"When is your {race_distance} race? (e.g., 'March 15' or 'in 12 weeks')",
            intent_handled=UserIntent.SET_GOAL,
            success=True,
            follow_up_expected=True,
        )

    # M4: Update profile with goal
    profile = get_profile(context.athlete_name, repo)
    # Update goal race
    updated_profile = profile.with_goal(
        race_distance=race_distance,
        target_date=_parse_target_date(target_month, entities.get('target_day')),
    )
    repo.write_yaml(f"athlete/{context.athlete_name}/profile.yaml", updated_profile.dict())

    # M10: Generate new plan
    plan = generate_plan(updated_profile, repo)

    return OrchestratorResponse(
        message=f"Goal set: {race_distance} on {updated_profile.goal_date}.\n\nI've generated a {plan.weeks}-week plan. Here's an overview:\n\n{format_plan_overview(plan)}",
        intent_handled=UserIntent.SET_GOAL,
        success=True,
    )


def _handle_log_wellness(
    entities: dict,
    context: ConversationContext,
    repo: RepositoryIO,
    config: AppConfig,
) -> OrchestratorResponse:
    """Handle wellness logging (feeling tired, sick, etc.)."""

    # M13: Store as memory
    if entities.get('illness'):
        # Critical: illness triggers safety override
        from sports_coach.m11_adaptation import apply_safety_override
        override = apply_safety_override('illness', repo)

        return OrchestratorResponse(
            message="I hear you're not feeling well. Take care of yourself first.\n\n"
                    f"**Automatic adjustment:** {override.description}\n\n"
                    "Focus on rest and recovery. Let me know when you're feeling better.",
            intent_handled=UserIntent.LOG_WELLNESS,
            success=True,
        )

    if entities.get('fatigue'):
        # Evaluate if adaptation needed
        suggestions = evaluate_adaptations(repo, wellness_override={'fatigue': True})

        if suggestions:
            return OrchestratorResponse(
                message=f"Thanks for letting me know. Based on this, I suggest:\n\n{suggestions[0].description}\n\nWould you like me to make this adjustment?",
                intent_handled=UserIntent.LOG_WELLNESS,
                success=True,
                data={"pending_suggestion_id": suggestions[0].id},
                follow_up_expected=True,
            )

    if entities.get('soreness'):
        location = entities.get('pain_location', 'unspecified area')
        # Store as memory for future reference
        extract_memories(
            note=f"User reported soreness in {location}",
            memory_type='injury_flag',
            repo=repo,
        )

        return OrchestratorResponse(
            message=f"Noted the soreness in your {location}. I'll factor this into your recommendations. "
                    "If it persists or worsens, consider taking an extra rest day.",
            intent_handled=UserIntent.LOG_WELLNESS,
            success=True,
        )

    return OrchestratorResponse(
        message="Thanks for the update. I'll take this into account.",
        intent_handled=UserIntent.LOG_WELLNESS,
        success=True,
    )


def _handle_suggestion_response(
    accepted: bool,
    suggestion_id: str,
    repo: RepositoryIO,
) -> OrchestratorResponse:
    """Handle user response to a pending suggestion."""
    from sports_coach.m11_adaptation import accept_suggestion, decline_suggestion

    if accepted:
        result = accept_suggestion(suggestion_id, repo)
        return OrchestratorResponse(
            message=f"Got it! {result.confirmation_message}",
            intent_handled=UserIntent.ACCEPT_SUGGESTION,
            success=True,
        )
    else:
        result = decline_suggestion(suggestion_id, repo)
        return OrchestratorResponse(
            message="No problem, keeping the original plan. Let me know if anything changes.",
            intent_handled=UserIntent.DECLINE_SUGGESTION,
            success=True,
        )


def _handle_greeting(
    entities: dict,
    context: ConversationContext,
    repo: RepositoryIO,
    config: AppConfig,
) -> OrchestratorResponse:
    """Handle greeting."""

    # Get quick status for personalized greeting
    try:
        metrics = compute_daily_metrics(date.today(), repo)
        readiness = metrics.readiness_score

        if readiness >= 70:
            status_note = "You're looking fresh and ready to train!"
        elif readiness >= 50:
            status_note = "You're in good shape for training today."
        else:
            status_note = "Your body might appreciate some easier work today."

        return OrchestratorResponse(
            message=f"Hey {context.athlete_name}! {status_note}\n\nWhat would you like to know?",
            intent_handled=UserIntent.GREETING,
            success=True,
        )
    except Exception:
        return OrchestratorResponse(
            message=f"Hey {context.athlete_name}! Ready to talk training?",
            intent_handled=UserIntent.GREETING,
            success=True,
        )


def _handle_help(
    entities: dict,
    context: ConversationContext,
    repo: RepositoryIO,
    config: AppConfig,
) -> OrchestratorResponse:
    """Show help information."""

    help_text = """Here's what I can help you with:

**Daily Coaching**
- "What should I do today?" — Get your workout
- "How am I doing?" — See your current status

**Sync & Logging**
- "Sync my Strava" — Import recent activities
- "I did a 5K easy run" — Log a manual activity

**Planning**
- "I want to run a 10K in March" — Set a race goal
- "Show me next week" — Preview upcoming workouts

**Adjustments**
- "I'm feeling tired" — Let me know how you're feeling
- "Skip today's workout" — Adjust the plan

**Information**
- "Show my metrics" — See CTL/ATL/TSB/ACWR
- "Show my history" — Recent activities

Just talk naturally — I'll figure out what you need!"""

    return OrchestratorResponse(
        message=help_text,
        intent_handled=UserIntent.HELP,
        success=True,
    )


def _handle_unknown(
    entities: dict,
    context: ConversationContext,
    repo: RepositoryIO,
    config: AppConfig,
) -> OrchestratorResponse:
    """Handle unrecognized intent."""

    return OrchestratorResponse(
        message="I'm not sure what you're asking for. Try asking about:\n"
                "- Today's workout\n"
                "- Your current status\n"
                "- Syncing Strava\n"
                "- Setting a race goal\n\n"
                "Or say 'help' for more options.",
        intent_handled=UserIntent.UNKNOWN,
        success=False,
    )


def _handle_error(intent: UserIntent, error: Exception) -> OrchestratorResponse:
    """Handle errors gracefully."""

    error_messages = {
        UserIntent.SYNC: "I couldn't sync with Strava. Please check your connection and try again.",
        UserIntent.TODAY: "I had trouble getting your workout. Let me know if this persists.",
        UserIntent.SET_GOAL: "I couldn't update your goal. Please try again.",
    }

    message = error_messages.get(
        intent,
        "Something went wrong. Please try again or rephrase your request."
    )

    return OrchestratorResponse(
        message=message,
        intent_handled=intent,
        success=False,
        data={"error": str(error)},
    )
```

### 5.4 Session Management

```python
from sports_coach.m14_logger import (
    start_session as logger_start,
    end_session as logger_end,
    get_current_session,
)


def start_conversation(
    athlete_name: str,
    config: AppConfig,
) -> ConversationContext:
    """Initialize a new conversation session."""

    # Start logger session
    session = logger_start(athlete_name)

    return ConversationContext(
        session_id=session.id,
        athlete_name=athlete_name,
        pending_suggestion_id=None,
        last_intent=None,
        turn_count=0,
    )


def end_conversation(
    context: ConversationContext,
    repo: RepositoryIO,
) -> str:
    """End the conversation and persist transcript."""

    session = get_current_session()
    if session:
        return logger_end(session, repo)
    return ""


def _update_context(
    context: ConversationContext,
    intent: UserIntent,
    clear_pending: bool = False,
    pending_suggestion: str = None,
) -> ConversationContext:
    """Update conversation context after processing."""

    return ConversationContext(
        session_id=context.session_id,
        athlete_name=context.athlete_name,
        pending_suggestion_id=None if clear_pending else (pending_suggestion or context.pending_suggestion_id),
        last_intent=intent,
        turn_count=context.turn_count + 1,
    )
```

### 5.5 Memory Extraction from Conversation

```python
def _extract_conversation_memories(
    user_message: str,
    response: OrchestratorResponse,
    repo: RepositoryIO,
) -> None:
    """Extract durable memories from conversation."""

    # Keywords that indicate memory-worthy content
    memory_triggers = [
        # Preferences
        ('prefer', 'preference'),
        ('like to', 'preference'),
        ('don\'t like', 'preference'),
        ('hate', 'preference'),

        # Life context
        ('work', 'life_context'),
        ('travel', 'life_context'),
        ('vacation', 'life_context'),
        ('busy', 'life_context'),

        # Injury history
        ('injury', 'injury_history'),
        ('injured', 'injury_history'),
        ('surgery', 'injury_history'),

        # Goals
        ('goal', 'goal'),
        ('want to', 'goal'),
        ('aiming for', 'goal'),
    ]

    message_lower = user_message.lower()

    for trigger, memory_type in memory_triggers:
        if trigger in message_lower:
            # M13: Extract and store memory
            from sports_coach.m13_memory import extract_from_text
            extract_from_text(user_message, memory_type, repo)
            break  # One extraction per message
```

### 5.6 Dynamic Context Loading

```python
def get_context_for_intent(
    intent: ParsedIntent,
    repo: RepositoryIO,
) -> str:
    """
    Load appropriate session summaries based on user intent.

    Strategy:
    - Simple operations (sync, status) → 0 summaries (no historical context needed)
    - Daily advice ("what should I do today?") → 3 recent summaries
    - Plan generation/major decisions → 10 summaries
    - Adaptation discussions → 5 summaries
    - User asks about specific past date → load full transcript

    This prevents token bloat by loading only relevant historical context.

    Token efficiency:
    - 0 summaries = 0 tokens
    - 3 summaries = ~450 tokens
    - 10 summaries = ~1500 tokens
    (vs 20,000+ tokens if loading full transcripts)

    Args:
        intent: Parsed user intent with type and entities
        repo: RepositoryIO instance

    Returns:
        Formatted context string to prepend to coaching prompt
    """
    from sports_coach.m14_logger import (
        list_session_summaries,
        get_transcript_by_date,
        format_session_markdown,
    )

    # Determine how many summaries to load based on intent type
    if intent.intent in [UserIntent.SYNC, UserIntent.STATUS]:
        # Simple status operations don't need historical context
        summary_count = 0

    elif intent.intent in [UserIntent.TODAY, UserIntent.NEXT_WEEK]:
        # Daily/weekly advice benefits from recent context
        summary_count = 3

    elif intent.intent in [UserIntent.SET_GOAL, UserIntent.REGENERATE_PLAN]:
        # Major planning decisions need broader historical context
        summary_count = 10

    elif intent.intent in [UserIntent.ADJUST_WORKOUT, UserIntent.EXPLAIN]:
        # Moderate context for adaptation and explanation
        summary_count = 5

    elif intent.intent == UserIntent.HISTORY:
        # User asking about past - check if specific date requested
        target_date = intent.entities.get("date")
        if target_date:
            # Load specific full transcript
            transcript = get_transcript_by_date(target_date, repo)
            if transcript:
                return (
                    f"## Past Conversation ({target_date})\n\n"
                    f"{format_session_markdown(transcript)}"
                )
        return ""

    else:
        # Default: small recent context for other intents
        summary_count = 2

    # Load summaries if needed
    if summary_count == 0:
        return ""

    summaries = list_session_summaries(repo, limit=summary_count)

    if not summaries:
        return ""

    # Format as context for coaching prompt
    context_lines = [
        "## Recent Session Context",
        "",
        "*Recent coaching conversations for continuity:*",
        "",
    ]

    for i, summary in enumerate(summaries, 1):
        context_lines.append(f"### Session {i}")
        context_lines.append(summary)
        context_lines.append("---")
        context_lines.append("")

    return "\n".join(context_lines)
```

**Usage in Main Processing Loop:**

```python
def process_message(
    message: str,
    context: ConversationContext,
    repo: RepositoryIO,
    config: AppConfig,
) -> tuple[OrchestratorResponse, ConversationContext]:
    """
    Main message processing with dynamic context loading.
    """
    # Parse intent
    parsed = parse_intent(message, context)

    # Load historical context dynamically
    historical_context = get_context_for_intent(parsed, repo)

    # Load current state
    profile = get_profile(repo)
    current_metrics = compute_daily_metrics(repo, date.today())
    current_plan = load_current_plan(repo)

    # Build coaching prompt with historical context
    coaching_context = f"""{historical_context}

## Current State
**Profile**: {profile.name} - {profile.sport_priority}
**Metrics**: CTL {current_metrics.ctl:.1f}, ATL {current_metrics.atl:.1f}, TSB {current_metrics.tsb:.1f}, ACWR {current_metrics.acwr:.2f}
**Plan**: {current_plan.phase} - Week {current_plan.current_week}/{current_plan.total_weeks}

## User Message
{message}
"""

    # Continue with intent handling...
    # (Rest of process_message logic)
```

**Token Cost Comparison:**

| Intent Type | Summaries Loaded | Token Cost | Previous (Full Transcripts) |
|-------------|-----------------|------------|----------------------------|
| Sync/Status | 0 | 0 | ~20,000 |
| Daily advice | 3 | ~450 | ~6,000 |
| Plan generation | 10 | ~1,500 | ~20,000 |

**10-20x token reduction** for most common operations.

## 6. Data Structures

### 6.1 Conversation Flow State

```
[User Message]
      │
      ▼
[M1: Parse Intent]
      │
      ├── Known Intent ──────────────────┐
      │                                   │
      ▼                                   │
[Check Pending Suggestion]               │
      │                                   │
      ├── Has Pending ─► Handle Response │
      │                                   │
      ▼                                   │
[Dispatch to Handler] ◄──────────────────┘
      │
      ├── M5/M6/M7/M8/M9 (sync)
      ├── M10/M11 (today/plan)
      ├── M4 (profile)
      ├── M12 (format)
      │
      ▼
[Log to M14]
      │
      ▼
[Extract Memories via M13]
      │
      ▼
[Return Response]
```

## 7. Integration Points

### 7.1 Module Calls

| Intent       | Modules Called                             |
| ------------ | ------------------------------------------ |
| SYNC         | M2, M5, M6, M7, M8, M9, M11, M12, M13, M14 |
| TODAY        | M4, M9, M10, M11, M12, M14                 |
| STATUS       | M4, M9, M12, M14                           |
| SET_GOAL     | M4, M10, M14                               |
| LOG_WELLNESS | M11, M13, M14                              |
| GREETING     | M9 (optional), M14                         |
| ALL          | M14 (logging)                              |

### 7.2 Entry Point

```python
# main.py
from sports_coach.m01_orchestrator import (
    start_conversation,
    process_message,
    end_conversation,
)
from sports_coach.m02_config import load_config
from sports_coach.m03_repository import RepositoryIO


def main():
    """Main CLI entry point."""
    config = load_config()
    repo = RepositoryIO(config.data_path)

    # Get athlete name
    athlete_name = config.default_athlete or input("Athlete name: ")

    # Start conversation
    context = start_conversation(athlete_name, config)

    print(f"Coach ready! Type 'quit' to exit.\n")

    try:
        while True:
            user_input = input("> ").strip()

            if user_input.lower() in ('quit', 'exit', 'bye'):
                break

            if not user_input:
                continue

            response, context = process_message(
                user_input,
                context,
                repo,
                config,
            )

            print(f"\n{response.message}\n")

    finally:
        # Always persist the conversation
        path = end_conversation(context, repo)
        print(f"Conversation saved to {path}")


if __name__ == "__main__":
    main()
```

## 8. Test Scenarios

### 8.1 Unit Tests

```python
def test_parse_sync_intent():
    """Sync intents are recognized"""
    context = ConversationContext(
        session_id="test",
        athlete_name="Test",
        pending_suggestion_id=None,
        last_intent=None,
        turn_count=0,
    )

    messages = [
        "sync my strava",
        "Sync Strava",
        "import my activities",
        "fetch from strava",
    ]

    for msg in messages:
        parsed = parse_intent(msg, context)
        assert parsed.intent == UserIntent.SYNC


def test_parse_today_intent():
    """Today workout intents are recognized"""
    context = ConversationContext(
        session_id="test",
        athlete_name="Test",
        pending_suggestion_id=None,
        last_intent=None,
        turn_count=0,
    )

    messages = [
        "what should I do today",
        "today's workout",
        "what's my workout",
    ]

    for msg in messages:
        parsed = parse_intent(msg, context)
        assert parsed.intent == UserIntent.TODAY


def test_parse_goal_entities():
    """Goal setting extracts entities"""
    context = ConversationContext(
        session_id="test",
        athlete_name="Test",
        pending_suggestion_id=None,
        last_intent=None,
        turn_count=0,
    )

    parsed = parse_intent("I want to run a 10K in March", context)

    assert parsed.intent == UserIntent.SET_GOAL
    assert parsed.entities.get('race_distance') == '10k'
    assert parsed.entities.get('target_month') == 'march'


def test_suggestion_response_context():
    """Suggestion responses work with pending context"""
    context = ConversationContext(
        session_id="test",
        athlete_name="Test",
        pending_suggestion_id="sugg_123",
        last_intent=UserIntent.TODAY,
        turn_count=3,
    )

    parsed = parse_intent("yes", context)
    assert parsed.intent == UserIntent.ACCEPT_SUGGESTION

    parsed = parse_intent("no thanks", context)
    assert parsed.intent == UserIntent.DECLINE_SUGGESTION


def test_wellness_entity_extraction():
    """Wellness logging extracts relevant entities"""
    context = ConversationContext(
        session_id="test",
        athlete_name="Test",
        pending_suggestion_id=None,
        last_intent=None,
        turn_count=0,
    )

    parsed = parse_intent("my knee is sore", context)

    assert parsed.intent == UserIntent.LOG_WELLNESS
    assert parsed.entities.get('soreness') is True
    assert parsed.entities.get('pain_location') == 'knee'
```

### 8.2 Integration Tests

```python
@pytest.mark.integration
def test_full_sync_flow():
    """Complete sync workflow executes correctly"""
    config = MockConfig()
    repo = MockRepositoryIO()
    context = start_conversation("Test Athlete", config)

    # Mock Strava to return activities
    with mock_strava_api(activities=[mock_activity()]):
        response, context = process_message(
            "sync my strava",
            context,
            repo,
            config,
        )

    assert response.success
    assert response.intent_handled == UserIntent.SYNC
    assert "imported" in response.message.lower()


@pytest.mark.integration
def test_conversation_persisted():
    """Conversation is saved on end"""
    config = MockConfig()
    repo = MockRepositoryIO()
    context = start_conversation("Test Athlete", config)

    process_message("hello", context, repo, config)
    path = end_conversation(context, repo)

    assert path.startswith("conversations/")
    assert repo.file_exists(path)
```

## 9. Configuration

### 9.1 Orchestrator Settings

```python
ORCHESTRATOR_CONFIG = {
    "min_intent_confidence": 0.5,   # Below this, ask for clarification
    "max_suggestion_age_hours": 24, # Expire old suggestions
    "auto_persist_interval": 10,    # Auto-save every N messages
}
```

## 10. User Experience Notes

### 10.1 Response Tone

- Be conversational and warm
- Always explain the "why" behind recommendations
- Use the athlete's name occasionally
- Acknowledge feelings and context
- Be proactive about potential issues

### 10.2 Error Recovery

- Never show technical error messages
- Suggest alternatives when something fails
- Offer to try a different approach
- Persist conversation even on errors

### 10.3 Intent Fallback Strategy

1. Try keyword matching with high confidence
2. Fall back to context-aware inference
3. If still unclear, ask clarifying question
4. Never guess critical actions (deletions, plan changes)
