"""
API Layer - Public interface for Claude Code.

This package provides high-level functions that Claude Code calls to fulfill
user requests. Functions return rich Pydantic models with interpretive context.

Modules:
    - coach: Coaching operations (get_todays_workout, etc.)
    - sync: Strava sync and activity logging
    - metrics: Metrics queries with interpretations
    - plan: Training plan operations
    - profile: Athlete profile management
"""

# Note: Re-exports commented out until modules are implemented
# Re-export all public functions
# from sports_coach_engine.api.coach import *
# from sports_coach_engine.api.sync import *
# from sports_coach_engine.api.metrics import *
# from sports_coach_engine.api.plan import *
# from sports_coach_engine.api.profile import *
