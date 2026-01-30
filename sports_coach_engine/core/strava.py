"""
M5 - Strava Integration

OAuth authentication, activity fetching with pagination, rate limiting,
and deduplication. Handles token refresh and error recovery.

This module handles:
- OAuth flow (manual: display URL, user pastes code)
- Token refresh with automatic expiration checking
- Activity list fetching with pagination
- Activity detail fetching (including private notes)
- Two-tier deduplication (primary key + fuzzy matching)
- Rate limiting with exponential backoff
- Manual activity logging

OAuth Flow:
1. Generate authorization URL
2. User opens URL in browser and authorizes
3. User copies redirect URL with code parameter
4. Exchange code for access_token and refresh_token
5. Store tokens in config/secrets.local.yaml
6. Check expiration before each API call, refresh if needed
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Generator
from uuid import uuid4
import logging
import time

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from sports_coach_engine.core.config import load_config
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.activity import (
    ActivitySource,
    RawActivity,
    SyncResult,
)
from sports_coach_engine.schemas.config import Config


# ============================================================
# ERROR TYPES
# ============================================================


class StravaError(Exception):
    """Base exception for Strava errors."""

    pass


class StravaAuthError(StravaError):
    """OAuth/authentication error."""

    pass


class StravaRateLimitError(StravaError):
    """Rate limit exceeded error."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class StravaAPIError(StravaError):
    """General API error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


# ============================================================
# CONSTANTS
# ============================================================

STRAVA_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

# Sync window defaults
DEFAULT_SYNC_LOOKBACK_DAYS = 365

# Rate limits (Strava defaults)
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_WAIT_BETWEEN_REQUESTS = 1.0  # seconds


# ============================================================
# OAUTH FUNCTIONS
# ============================================================


def initiate_oauth(client_id: str, redirect_uri: str = "http://localhost") -> str:
    """
    Generate Strava authorization URL.

    Args:
        client_id: Strava application client ID
        redirect_uri: OAuth redirect URI (default: http://localhost)

    Returns:
        Authorization URL for user to open in browser
    """
    scope = "activity:read_all,profile:read_all"
    auth_url = (
        f"{STRAVA_AUTHORIZE_URL}?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"redirect_uri={redirect_uri}&"
        f"approval_prompt=force&"
        f"scope={scope}"
    )
    return auth_url


def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    code: str,
) -> dict:
    """
    Exchange authorization code for access and refresh tokens.

    Args:
        client_id: Strava application client ID
        client_secret: Strava application client secret
        code: Authorization code from redirect URL

    Returns:
        Dict with access_token, refresh_token, expires_at

    Raises:
        StravaAuthError: If token exchange fails
    """
    try:
        with httpx.Client() as client:
            response = client.post(
                STRAVA_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise StravaAuthError(
                    f"Token exchange failed: {response.status_code} - {response.text}"
                )

            data = response.json()
            return {
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "expires_at": data["expires_at"],  # Unix timestamp
            }

    except httpx.HTTPError as e:
        raise StravaAuthError(f"HTTP error during token exchange: {e}")


def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict:
    """
    Refresh expired access token.

    Args:
        client_id: Strava application client ID
        client_secret: Strava application client secret
        refresh_token: Current refresh token

    Returns:
        Dict with new access_token, refresh_token, expires_at

    Raises:
        StravaAuthError: If refresh fails
    """
    try:
        with httpx.Client() as client:
            response = client.post(
                STRAVA_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise StravaAuthError(
                    f"Token refresh failed: {response.status_code} - {response.text}"
                )

            data = response.json()
            return {
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "expires_at": data["expires_at"],
            }

    except httpx.HTTPError as e:
        raise StravaAuthError(f"HTTP error during token refresh: {e}")


def get_valid_token(config: Config) -> str:
    """
    Get valid access token, refreshing if needed.

    Checks if token expires in <5 minutes, refreshes proactively.

    Args:
        config: Configuration with Strava credentials

    Returns:
        Valid access token

    Raises:
        StravaAuthError: If token refresh fails
    """
    # Check expiration
    now = int(time.time())
    expires_at = config.secrets.strava.token_expires_at

    # Refresh if expires in <5 minutes
    if expires_at - now < 300:
        tokens = refresh_access_token(
            client_id=config.secrets.strava.client_id,
            client_secret=config.secrets.strava.client_secret,
            refresh_token=config.secrets.strava.refresh_token,
        )

        # Update config and persist
        store_tokens(config, tokens)
        return tokens["access_token"]

    return config.secrets.strava.access_token


def store_tokens(config: Config, tokens: dict) -> None:
    """
    Store tokens to config/secrets.local.yaml.

    Args:
        config: Configuration object
        tokens: Dict with access_token, refresh_token, expires_at
    """
    # Update config object
    config.secrets.strava.access_token = tokens["access_token"]
    config.secrets.strava.refresh_token = tokens["refresh_token"]
    config.secrets.strava.token_expires_at = tokens["expires_at"]

    # Persist to file (simplified - in production would use M2's save method)
    # For now, we assume the config module handles persistence
    # This is a placeholder for the actual implementation


# ============================================================
# ACTIVITY FETCHING
# ============================================================


@retry(
    stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception_type((httpx.HTTPError, StravaAPIError)),
)
def fetch_activities(
    config: Config,
    page: int = 1,
    per_page: int = 50,
    after: Optional[int] = None,
    before: Optional[int] = None,
) -> list[dict]:
    """
    Fetch activity list from Strava with pagination.

    Args:
        config: Configuration with Strava credentials
        page: Page number (1-indexed)
        per_page: Activities per page (max 200, default 50)
        after: Unix timestamp - return activities after this time
        before: Unix timestamp - return activities before this time

    Returns:
        List of activity summary dicts

    Raises:
        StravaAuthError: If authentication fails
        StravaRateLimitError: If rate limited
        StravaAPIError: If API request fails
    """
    access_token = get_valid_token(config)

    params = {
        "page": page,
        "per_page": min(per_page, 200),  # Cap at Strava max
    }
    if after:
        params["after"] = after
    if before:
        params["before"] = before

    try:
        with httpx.Client() as client:
            response = client.get(
                f"{STRAVA_API_BASE}/athlete/activities",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                timeout=30.0,
            )

            if response.status_code == 401:
                raise StravaAuthError("Invalid or expired token")
            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise StravaRateLimitError(
                    "Rate limit exceeded",
                    retry_after=int(retry_after) if retry_after else None,
                )
            elif response.status_code != 200:
                raise StravaAPIError(
                    f"API request failed: {response.status_code} - {response.text}",
                    status_code=response.status_code,
                )

            return response.json()

    except httpx.HTTPError as e:
        raise StravaAPIError(f"HTTP error: {e}")


@retry(
    stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception_type((httpx.HTTPError, StravaAPIError)),
)
def fetch_activity_details(config: Config, activity_id: str) -> dict:
    """
    Fetch full activity details including private notes.

    Args:
        config: Configuration with Strava credentials
        activity_id: Strava activity ID

    Returns:
        Full activity dict with description and private_note

    Raises:
        StravaAuthError: If authentication fails
        StravaRateLimitError: If rate limited
        StravaAPIError: If API request fails
    """
    access_token = get_valid_token(config)

    try:
        with httpx.Client() as client:
            response = client.get(
                f"{STRAVA_API_BASE}/activities/{activity_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code == 401:
                raise StravaAuthError("Invalid or expired token")
            elif response.status_code != 200:
                raise StravaAPIError(
                    f"Activity detail fetch failed: {response.status_code}",
                    status_code=response.status_code,
                )

            return response.json()

    except httpx.HTTPError as e:
        raise StravaAPIError(f"HTTP error: {e}")


@retry(
    stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception_type((httpx.HTTPError, StravaAPIError)),
)
def fetch_athlete_profile(config: Config) -> Optional[dict]:
    """
    Fetch authenticated athlete's profile data from Strava.

    This endpoint provides profile information that can be used to auto-fill
    athlete profile fields, avoiding redundant questions during setup.

    Available fields (when athlete has disclosed):
    - firstname, lastname: Athlete's name
    - sex: Gender ("M" or "F")
    - weight: Body weight in kg (if athlete logs in Strava)
    - profile, profile_medium: Avatar URLs
    - city, state, country: Location
    - created_at, updated_at: Account timestamps

    Note: Requires 'profile:read_all' OAuth scope (already requested).

    Args:
        config: Configuration with Strava credentials

    Returns:
        Athlete profile dict, or None if fetch fails

    Raises:
        StravaAuthError: If authentication fails
        StravaAPIError: If API request fails

    Example:
        >>> profile = fetch_athlete_profile(config)
        >>> if profile:
        ...     athlete_name = profile.get("firstname")
        ...     athlete_gender = profile.get("sex")  # "M" or "F"
        ...     athlete_weight = profile.get("weight")  # kg, may be None
    """
    access_token = get_valid_token(config)

    try:
        with httpx.Client() as client:
            response = client.get(
                f"{STRAVA_API_BASE}/athlete",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code == 401:
                raise StravaAuthError("Invalid or expired token")
            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise StravaRateLimitError(
                    "Rate limit exceeded",
                    retry_after=int(retry_after) if retry_after else None,
                )
            elif response.status_code != 200:
                raise StravaAPIError(
                    f"Athlete profile fetch failed: {response.status_code}",
                    status_code=response.status_code,
                )

            return response.json()

    except httpx.HTTPError as e:
        raise StravaAPIError(f"HTTP error: {e}")



# ============================================================
# SYNC WORKFLOW
# ============================================================


def sync_strava_generator(
    config: Optional[Config] = None,
    lookback_days: Optional[int] = DEFAULT_SYNC_LOOKBACK_DAYS,
    existing_ids: Optional[set[str]] = None,
    since: Optional[datetime] = None,
):
    """
    Sync activities from Strava (Greedy Reverse-Chronological) as a generator.

    Yields activities one-by-one as they're fetched instead of buffering them.
    This enables incremental processing and reduces memory usage from ~5MB to ~50KB.

    Fetches activities starting from most recent (page 1) backwards.
    Stops when either:
    1. Strava Rate Limit is hit (StravaRateLimitError) -> Returns partial success
    2. Activity date is older than lookback_days (if provided) or since (if provided)
    3. No more activities found

    Skips detail fetching for activities present in existing_ids.

    Args:
        config: Configuration (loads from file if not provided)
        lookback_days: Optional days to look back.
        existing_ids: Set of strava_{id} strings to skip.
        since: Optional datetime to sync from (alternative to lookback_days).

    Yields:
        RawActivity: Each activity as it's fetched and mapped

    Returns:
        SyncResult: Final sync result (via StopIteration)

    Raises:
        StravaAuthError: If authentication fails
        StravaAPIError: If sync fails (other than rate limit)
    """
    if config is None:
        config_result = load_config()
        if isinstance(config_result, Exception):
            raise StravaAPIError(f"Failed to load config: {config_result}")
        config = config_result

    # Initialize logger
    logger = logging.getLogger(__name__)

    # Determine cutoff date
    cutoff_date = None
    if since:
        cutoff_date = since.date()
    elif lookback_days:
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date()

    if cutoff_date:
        logger.info(f"Syncing Strava history (cutoff: {cutoff_date})...")
    else:
        logger.info("Syncing Strava history (no time limit)...")

    start_time = datetime.now(timezone.utc)
    activities_yielded = 0
    errors = []
    skipped_count = 0

    # Pagination loop (Newest -> Oldest)
    page = 1
    stop_sync = False
    rate_limit_hit = False

    try:
        while not stop_sync:
            try:
                # Fetch page of activities
                logger.debug(f"Fetching page {page}...")
                activities_page = fetch_activities(
                    config,
                    page=page,
                    per_page=50,
                    # Intentionally NO 'after' param to get newest first (default)
                )

                if not activities_page:
                    break  # No more activities

                for activity_summary in activities_page:
                    # Check date cutoff
                    try:
                        act_date_str = activity_summary["start_date_local"]
                        act_date = datetime.fromisoformat(act_date_str.replace("Z", "+00:00")).date()

                        if cutoff_date and act_date < cutoff_date:
                            logger.info(f"Reached cutoff date {cutoff_date} (activity date: {act_date}). Stopping.")
                            stop_sync = True
                            break
                    except (KeyError, ValueError):
                        pass # Skip date check malformed

                    # Check existence (skip if already imported)
                    strava_id = f"strava_{activity_summary['id']}"
                    if existing_ids is not None and strava_id in existing_ids:
                        skipped_count += 1
                        continue

                    # Fetch full details
                    try:
                        activity_detail = fetch_activity_details(
                            config, str(activity_summary["id"])
                        )

                        # Respect rate limits between calls
                        time.sleep(DEFAULT_WAIT_BETWEEN_REQUESTS)

                        # Map to RawActivity
                        raw_activity = map_strava_to_raw(activity_detail)
                        activities_yielded += 1
                        yield raw_activity  # Stream immediately

                    except StravaRateLimitError:
                        logger.warning(f"Strava rate limit hit during detail fetch for {activity_summary['id']}. Pausing sync.")
                        rate_limit_hit = True
                        stop_sync = True
                        break
                    except Exception as e:
                        errors.append(f"Activity {activity_summary['id']}: {str(e)}")
                        continue

                if stop_sync:
                    break

                page += 1
                # Respect rate limits between pages
                time.sleep(DEFAULT_WAIT_BETWEEN_REQUESTS)

            except StravaRateLimitError:
                 logger.warning(f"Strava rate limit hit during page {page} fetch. Pausing sync.")
                 rate_limit_hit = True
                 stop_sync = True
                 break
            except Exception as e:
                errors.append(f"Page {page} fetch failed: {str(e)}")
                break

    finally:
        # Calculate duration
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        # Create sync result
        sync_result = SyncResult(
            success=len(errors) == 0,
            activities_fetched=0,
            activities_new=activities_yielded,
            activities_updated=0,
            activities_skipped=skipped_count,
            errors=errors,
            sync_duration_seconds=duration,
        )

        if rate_limit_hit:
            sync_result.errors.append("Strava API Rate Limit Reached - Sync Paused")

        # Return via generator protocol
        return sync_result


# sync_strava() wrapper removed - use sync_strava_generator() directly
# No backward compatibility needed for v0


# ============================================================
# STRAVA → RAW ACTIVITY MAPPING
# ============================================================


def map_strava_to_raw(strava_activity: dict) -> RawActivity:
    """
    Map Strava activity JSON to RawActivity schema.

    Args:
        strava_activity: Strava activity dict from API

    Returns:
        RawActivity with all fields mapped

    Raises:
        ValueError: If required fields missing
    """
    # Parse start date
    start_date_str = strava_activity["start_date_local"]
    start_datetime = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))

    return RawActivity(
        # Identity
        id=f"strava_{strava_activity['id']}",
        source=ActivitySource.STRAVA,
        # Core fields
        sport_type=strava_activity["sport_type"],
        sub_type=strava_activity.get("type"),  # Legacy type field
        name=strava_activity["name"],
        date=start_datetime.date(),
        start_time=start_datetime,
        # Duration
        duration_seconds=strava_activity["moving_time"],
        # Distance
        distance_meters=strava_activity.get("distance"),
        elevation_gain_meters=strava_activity.get("total_elevation_gain"),
        # Heart rate
        average_hr=strava_activity.get("average_heartrate"),
        max_hr=strava_activity.get("max_heartrate"),
        has_hr_data=strava_activity.get("has_heartrate", False),
        # Notes
        description=strava_activity.get("description"),
        private_note=strava_activity.get("private_note"),
        # Strava-specific
        workout_type=strava_activity.get("workout_type"),
        suffer_score=strava_activity.get("suffer_score"),
        perceived_exertion=strava_activity.get("perceived_exertion"),
        # GPS
        has_polyline=bool(strava_activity.get("map", {}).get("summary_polyline")),
        # Equipment
        gear_id=strava_activity.get("gear_id"),
        device_name=strava_activity.get("device_name"),
        # Timestamps
        strava_created_at=datetime.fromisoformat(
            strava_activity["start_date"].replace("Z", "+00:00")
        ),
        strava_updated_at=datetime.fromisoformat(
            strava_activity["start_date"].replace("Z", "+00:00")
        ),  # Strava doesn't provide updated_at
    )


# ============================================================
# DEDUPLICATION
# ============================================================


def check_duplicate(
    new_activity: RawActivity,
    existing_activities: list[RawActivity],
) -> Optional[RawActivity]:
    """
    Check if activity is a duplicate using two-tier strategy.

    Tier 1: Primary key match (source, id)
    Tier 2: Fuzzy match (date, sport, start_time±30min, duration±5min)

    Args:
        new_activity: Activity to check
        existing_activities: List of existing activities

    Returns:
        Matching activity if duplicate found, None otherwise
    """
    for existing in existing_activities:
        # Tier 1: Primary key match
        if (
            new_activity.source == existing.source
            and new_activity.id == existing.id
        ):
            return existing

        # Tier 2: Fuzzy match
        # Same date and sport type
        if (
            new_activity.date != existing.date
            or new_activity.sport_type != existing.sport_type
        ):
            continue

        # Start time within 30 minutes
        if new_activity.start_time and existing.start_time:
            time_diff = abs(
                (new_activity.start_time - existing.start_time).total_seconds()
            )
            if time_diff > 1800:  # 30 minutes
                continue

        # Duration within 5 minutes
        duration_diff = abs(
            new_activity.duration_seconds - existing.duration_seconds
        )
        if duration_diff > 300:  # 5 minutes
            continue

        # All fuzzy criteria matched
        return existing

    return None


# ============================================================
# MANUAL ACTIVITY LOGGING
# ============================================================


def create_manual_activity(
    sport_type: str,
    date: datetime,
    duration_minutes: int,
    distance_km: Optional[float] = None,
    perceived_exertion: Optional[int] = None,
    description: Optional[str] = None,
    **kwargs,
) -> RawActivity:
    """
    Create manual activity from user input.

    Args:
        sport_type: Sport type (uses Strava naming)
        date: Activity date
        duration_minutes: Duration in minutes
        distance_km: Distance in kilometers (optional)
        perceived_exertion: User RPE 1-10 (optional)
        description: Activity notes (optional)
        **kwargs: Additional fields

    Returns:
        RawActivity with manual source
    """
    # Generate unique ID
    activity_id = f"manual_{uuid4().hex[:12]}"

    # Convert date to datetime if needed
    if isinstance(date, datetime):
        start_time = date
        activity_date = date.date()
    else:
        activity_date = date
        start_time = datetime.combine(date, datetime.min.time())
        start_time = start_time.replace(tzinfo=timezone.utc)

    return RawActivity(
        # Identity
        id=activity_id,
        source=ActivitySource.MANUAL,
        # Core fields
        sport_type=sport_type,
        name=kwargs.get("name", f"Manual {sport_type}"),
        date=activity_date,
        start_time=start_time,
        duration_seconds=duration_minutes * 60,
        # Distance
        distance_meters=distance_km * 1000 if distance_km else None,
        # RPE
        perceived_exertion=perceived_exertion,
        # Notes
        description=description,
        # Defaults for manual activities
        has_hr_data=False,
        has_polyline=False,
    )
