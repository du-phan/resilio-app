# M5 — Activity Ingestion

## 1. Metadata

| Field        | Value                                                            |
| ------------ | ---------------------------------------------------------------- |
| Module ID    | M5                                                               |
| Name         | Activity Ingestion                                               |
| Version      | 1.0.1                                                            |
| Status       | Draft                                                            |
| Dependencies | M2 (Config & Secrets), M3 (Repository I/O), M4 (Athlete Profile) |

## 2. Purpose

Import activities from external sources (Strava API) and manual user input. Produces raw activity objects passed to M6 for normalization. Maintains sync state to support idempotent, incremental syncs.

### 2.1 Scope Boundaries

**In Scope:**

- Strava OAuth token refresh
- Fetching activity list from Strava API
- Fetching detailed activity data (including private notes)
- Deduplication by (source, id)
- Tracking sync state
- Manual activity logging interface
- Error handling and retry logic

**Out of Scope:**

- Normalizing sport types (M6)
- Extracting RPE from notes (M7)
- Computing loads (M8)
- Writing normalized activity files (M6)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage                                          |
| ------ | ---------------------------------------------- |
| M2     | Read Strava credentials, token refresh         |
| M3     | File I/O operations                            |
| M4     | Read/update training_history.yaml (sync state) |

### 3.2 External Libraries

```
httpx>=0.25.0        # Async HTTP client for Strava API
pydantic>=2.0        # Data validation
tenacity>=8.0        # Retry logic with exponential backoff
```

### 3.3 External Services

| Service       | Endpoints Used                                    |
| ------------- | ------------------------------------------------- |
| Strava API v3 | `GET /athlete/activities`, `GET /activities/{id}` |

## 4. Public Interface

**Note on Async Operations**: This specification shows async functions for completeness. However, **v0 implementation should use synchronous I/O** to avoid over-engineering. Replace `async def` with `def`, `httpx.AsyncClient` with `httpx.Client`, and `await` with direct calls. Async can be added in future versions if performance requires it.

### 4.1 Type Definitions

```python
from datetime import datetime, date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ActivitySource(str, Enum):
    STRAVA = "strava"
    MANUAL = "manual"


class StravaWorkoutType(int, Enum):
    """Strava workout_type values for running (undocumented)"""
    DEFAULT = 0
    RACE = 1
    LONG_RUN = 2
    WORKOUT = 3


class RawActivity(BaseModel):
    """
    Raw activity data as received from source.
    Passed to M6 for normalization.
    """
    # Identity
    id: str
    source: ActivitySource

    # Core fields
    sport_type: str                      # e.g., "Run", "Ride", "Climb"
    sub_type: Optional[str] = None       # e.g., "TrailRun", "VirtualRide"
    name: str                            # Activity title
    date: date
    start_time: Optional[datetime] = None  # Local start time

    # Effort metrics
    duration_seconds: int
    distance_meters: Optional[float] = None
    elevation_gain_meters: Optional[float] = None

    # Heart rate
    average_hr: Optional[int] = None
    max_hr: Optional[int] = None
    has_hr_data: bool = False

    # User input
    description: Optional[str] = None     # Public description
    private_note: Optional[str] = None    # Private notes (Strava premium)
    perceived_exertion: Optional[int] = None  # User-entered RPE (1-10)

    # Strava-specific
    workout_type: Optional[int] = None    # Race=1, Long run=2, Workout=3
    suffer_score: Optional[int] = None    # Strava relative effort
    has_polyline: bool = False           # GPS data present
    gear_id: Optional[str] = None        # Equipment used
    device_name: Optional[str] = None    # Recording device

    # Timestamps
    strava_created_at: Optional[datetime] = None
    strava_updated_at: Optional[datetime] = None

    # Metadata
    raw_data: dict = Field(default_factory=dict)  # Full API response


class SyncState(BaseModel):
    """
    Tracks Strava sync progress for incremental syncs.

    Note: Field names match M4's training_history.yaml schema for consistency.
    """
    last_strava_sync_at: Optional[datetime] = None
    last_strava_activity_id: Optional[str] = None


class SyncResult(BaseModel):
    """Result of a sync operation"""
    success: bool
    activities_fetched: int
    activities_new: int
    activities_updated: int
    activities_skipped: int
    errors: list[str] = Field(default_factory=list)
    sync_duration_seconds: float


class ManualActivityInput(BaseModel):
    """User-provided activity data for manual logging"""
    sport_type: str
    date: date
    duration_minutes: int
    distance_km: Optional[float] = None
    description: Optional[str] = None
    perceived_exertion: Optional[int] = Field(None, ge=1, le=10)
    average_hr: Optional[int] = Field(None, ge=30, le=250)

    class Config:
        extra = "forbid"
```

### 4.2 Function Signatures

```python
from typing import AsyncIterator


async def sync_strava(
    config: "Config",  # From M2
    since: datetime | None = None,
    until: datetime | None = None,
) -> tuple[list[RawActivity], SyncResult]:
    """
    Fetch activities from Strava API.

    Args:
        config: Application config with Strava credentials
        since: Start date for sync (default: last_sync_at or 90 days ago)
        until: End date for sync (default: now)

    Returns:
        Tuple of (raw activities, sync result summary)

    Raises:
        StravaAuthError: Token refresh failed
        StravaRateLimitError: Rate limited, includes retry_after
        StravaAPIError: Other API errors
    """
    ...


async def fetch_activity_details(
    activity_id: str,
    config: "Config",
) -> RawActivity:
    """
    Fetch full details for a single activity including private notes.

    Args:
        activity_id: Strava activity ID
        config: Application config with credentials

    Returns:
        RawActivity with full details

    Note:
        Private notes require Strava premium and correct OAuth scope.
    """
    ...


def create_manual_activity(
    input_data: ManualActivityInput,
) -> RawActivity:
    """
    Create a raw activity from manual user input.

    Args:
        input_data: Validated manual activity data

    Returns:
        RawActivity with source=manual and generated ID
    """
    ...


def get_sync_state(repo: "RepositoryIO") -> SyncState:
    """
    Read current sync state from training_history.yaml.

    Algorithm:
        1. Call M4.load_training_history()
        2. If None or error, return SyncState with all None fields
        3. Extract last_strava_sync_at and last_strava_activity_id from history
        4. Parse ISO datetime string to datetime if present
        5. Return SyncState(last_strava_sync_at, last_strava_activity_id)

    Args:
        repo: Repository I/O instance

    Returns:
        Current sync state (may have None fields if never synced)
    """
    ...


def update_sync_state(
    repo: "RepositoryIO",
    activities: list[RawActivity],
) -> None:
    """
    Update sync state after successful sync.

    Algorithm:
        1. If activities list is empty, do nothing (no update needed)
        2. Find most recent activity by strava_created_at or date
        3. Call M4.update_sync_state(
             last_activity_id=most_recent.id,
             sync_timestamp=datetime.now(UTC)
           )
        4. M4 will handle file I/O and schema validation

    Args:
        repo: Repository I/O instance
        activities: List of synced activities (to extract latest timestamp)
    """
    ...


def check_duplicate(
    activity: RawActivity,
    existing_activities: list[dict],
) -> tuple[bool, str | None]:
    """
    Check if activity already exists in local storage.

    Args:
        activity: Raw activity to check
        existing_activities: List of existing activity metadata

    Returns:
        (is_duplicate, existing_id if found)

    Deduplication Strategy:
        1. Primary: Match by (source, id)
        2. Fallback: Match by (date, sport_type, start_time±30min, duration±5min)
    """
    ...


async def iter_strava_activities(
    config: "Config",
    since: datetime | None = None,
    until: datetime | None = None,
    page_size: int = 50,
) -> AsyncIterator[dict]:
    """
    Iterate over Strava activities with pagination.

    Yields:
        Raw activity summaries from Strava API

    Note:
        Handles pagination automatically. Each yield is a summary;
        use fetch_activity_details() for full data including private notes.
    """
    ...
```

### 4.3 Error Types

```python
class IngestionError(Exception):
    """Base error for activity ingestion"""
    pass


class StravaAuthError(IngestionError):
    """Strava authentication failed (token refresh failed, invalid credentials)"""
    def __init__(self, message: str, requires_reauth: bool = False):
        super().__init__(message)
        self.requires_reauth = requires_reauth


class StravaRateLimitError(IngestionError):
    """Strava API rate limit exceeded"""
    def __init__(self, retry_after: int):
        super().__init__(f"Rate limited. Retry after {retry_after}s")
        self.retry_after = retry_after


class StravaAPIError(IngestionError):
    """General Strava API error"""
    def __init__(self, status_code: int, message: str):
        super().__init__(f"Strava API error {status_code}: {message}")
        self.status_code = status_code


class DuplicateActivityError(IngestionError):
    """Activity already exists (not really an error, informational)"""
    def __init__(self, activity_id: str, existing_id: str):
        super().__init__(f"Activity {activity_id} duplicates {existing_id}")
        self.activity_id = activity_id
        self.existing_id = existing_id
```

## 5. Data Structures

### 5.1 Sync State Schema (in training_history.yaml)

**Note**: Sync state is stored in M4's training_history.yaml file. Field names below match M4's schema exactly.

```yaml
# athlete/training_history.yaml (managed by M4, updated by M5)
_schema:
  format_version: "1.0.0"
  schema_type: "training_history"

# Strava sync state (updated by M5)
last_strava_sync_at: "2025-03-15T10:30:00Z"
last_strava_activity_id: "12345678901"

# Baseline metrics (managed by M4)
baseline_established: true
baseline:
  ctl: 280.5
  atl: 195.2
  tsb: 85.3
  period_days: 14
```

### 5.2 Strava API Response Mapping

```python
def map_strava_summary_to_raw(strava_data: dict) -> RawActivity:
    """
    Map Strava activity summary to RawActivity.

    Strava Field -> RawActivity Field:
        id                    -> id
        type                  -> sport_type
        sport_type            -> sub_type (more specific)
        name                  -> name
        start_date_local      -> date, start_time
        elapsed_time          -> duration_seconds
        distance              -> distance_meters
        total_elevation_gain  -> elevation_gain_meters
        average_heartrate     -> average_hr
        max_heartrate         -> max_hr
        has_heartrate         -> has_hr_data
        workout_type          -> workout_type
        suffer_score          -> suffer_score
        map.summary_polyline  -> has_polyline (bool if present)
        gear_id               -> gear_id
        device_name           -> device_name
    """
    return RawActivity(
        id=str(strava_data["id"]),
        source=ActivitySource.STRAVA,
        sport_type=strava_data.get("type", "Unknown"),
        sub_type=strava_data.get("sport_type"),
        name=strava_data.get("name", ""),
        date=_parse_date(strava_data["start_date_local"]),
        start_time=_parse_datetime(strava_data["start_date_local"]),
        duration_seconds=strava_data.get("elapsed_time", 0),
        distance_meters=strava_data.get("distance"),
        elevation_gain_meters=strava_data.get("total_elevation_gain"),
        average_hr=_safe_int(strava_data.get("average_heartrate")),
        max_hr=_safe_int(strava_data.get("max_heartrate")),
        has_hr_data=strava_data.get("has_heartrate", False),
        description=None,  # Not in summary, need detail fetch
        private_note=None,  # Not in summary, need detail fetch
        perceived_exertion=_safe_int(strava_data.get("perceived_exertion")),
        workout_type=strava_data.get("workout_type"),
        suffer_score=strava_data.get("suffer_score"),
        has_polyline=bool(strava_data.get("map", {}).get("summary_polyline")),
        gear_id=strava_data.get("gear_id"),
        device_name=strava_data.get("device_name"),
        strava_created_at=_parse_datetime(strava_data.get("start_date")),
        strava_updated_at=None,  # Not in summary
        raw_data=strava_data,
    )


def map_strava_detail_to_raw(strava_data: dict) -> RawActivity:
    """
    Map Strava detailed activity to RawActivity.

    Additional fields from detail endpoint:
        description           -> description
        private_note          -> private_note (Strava premium only)
    """
    raw = map_strava_summary_to_raw(strava_data)
    raw.description = strava_data.get("description")
    raw.private_note = strava_data.get("private_note")
    return raw
```

## 6. Core Algorithms

### 6.1 Strava Sync Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        sync_strava()                              │
├──────────────────────────────────────────────────────────────────┤
│ 1. Load sync state from training_history.yaml                    │
│ 2. Determine date range:                                          │
│    - since = last_sync_at OR (now - 90 days)                     │
│    - until = now                                                  │
│ 3. Refresh Strava token if needed (via M2)                       │
│ 4. Fetch activity list (paginated):                              │
│    for page in iter_strava_activities(since, until):             │
│      for activity_summary in page:                               │
│        a. Check for duplicate                                     │
│        b. If new or updated: fetch_activity_details()            │
│        c. Collect in memory (no disk writes yet)                 │
│ 5. Return (activities, sync_result)                              │
│    Caller (M1) will pass to M6 for normalization & persistence   │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 Sync Date Range Logic

```python
from datetime import datetime, timedelta, timezone


def determine_sync_range(
    sync_state: SyncState,
    since: datetime | None,
    until: datetime | None,
) -> tuple[datetime, datetime]:
    """
    Determine the date range for sync.

    Priority:
    1. Explicit since/until parameters
    2. Incremental from last_strava_sync_at
    3. Default to last 90 days
    """
    now = datetime.now(timezone.utc)

    # End date
    effective_until = until or now

    # Start date
    if since:
        effective_since = since
    elif sync_state.last_strava_sync_at:
        # Overlap by 1 hour to catch any edge cases
        effective_since = sync_state.last_strava_sync_at - timedelta(hours=1)
    else:
        # First sync: default to 90 days
        effective_since = now - timedelta(days=90)

    return effective_since, effective_until
```

### 6.3 Deduplication Algorithm

```python
from datetime import timedelta


def check_duplicate(
    activity: RawActivity,
    existing_activities: list[dict],
) -> tuple[bool, str | None]:
    """
    Two-tier deduplication strategy.

    Tier 1 - Primary Key Match:
        Match by (source, id) - exact match required

    Tier 2 - Fallback Match:
        Match by (date, sport_type, start_time±30min, duration±5min)
        Used when id is missing/corrupted
    """
    # Tier 1: Primary key match
    for existing in existing_activities:
        if (existing.get("source") == activity.source.value and
            existing.get("id") == activity.id):
            return True, existing.get("id")

    # Tier 2: Fallback match
    for existing in existing_activities:
        if not _fuzzy_match(activity, existing):
            continue

        # Potential duplicate found
        return True, existing.get("id")

    return False, None


def _fuzzy_match(activity: RawActivity, existing: dict) -> bool:
    """Check if activity fuzzy-matches existing record"""
    # Same date
    if str(activity.date) != existing.get("date"):
        return False

    # Same sport type (normalized)
    if activity.sport_type.lower() != existing.get("sport_type", "").lower():
        return False

    # Start time within 30 minutes
    existing_start = existing.get("start_time")
    if activity.start_time and existing_start:
        existing_dt = datetime.fromisoformat(existing_start)
        if abs((activity.start_time - existing_dt).total_seconds()) > 1800:
            return False

    # Duration within 5 minutes
    existing_duration = existing.get("duration_seconds", 0)
    if abs(activity.duration_seconds - existing_duration) > 300:
        return False

    return True
```

### 6.4 Strava API Pagination

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


STRAVA_BASE_URL = "https://www.strava.com/api/v3"
PAGE_SIZE = 50  # Strava max is 200, 50 is safer for memory


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
)
async def _fetch_page(
    client: httpx.AsyncClient,
    access_token: str,
    after: int,
    before: int,
    page: int,
) -> list[dict]:
    """Fetch a single page of activities from Strava"""
    response = await client.get(
        f"{STRAVA_BASE_URL}/athlete/activities",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "after": after,
            "before": before,
            "page": page,
            "per_page": PAGE_SIZE,
        },
        timeout=30.0,
    )

    if response.status_code == 401:
        raise StravaAuthError("Invalid or expired token", requires_reauth=True)
    elif response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 900))
        raise StravaRateLimitError(retry_after)
    elif response.status_code != 200:
        raise StravaAPIError(response.status_code, response.text)

    return response.json()


async def iter_strava_activities(
    config: "Config",
    since: datetime | None = None,
    until: datetime | None = None,
    page_size: int = PAGE_SIZE,
) -> AsyncIterator[dict]:
    """Paginated iterator over Strava activities"""
    sync_state = get_sync_state(config.repo)
    effective_since, effective_until = determine_sync_range(
        sync_state, since, until
    )

    after = int(effective_since.timestamp())
    before = int(effective_until.timestamp())

    async with httpx.AsyncClient() as client:
        access_token = await _ensure_valid_token(config)
        page = 1

        while True:
            activities = await _fetch_page(
                client, access_token, after, before, page
            )

            if not activities:
                break

            for activity in activities:
                yield activity

            if len(activities) < page_size:
                break

            page += 1
```

### 6.5 Activity Detail Fetch

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
)
async def fetch_activity_details(
    activity_id: str,
    config: "Config",
) -> RawActivity:
    """
    Fetch full activity details including private notes.

    Rate Limiting Note:
        Strava allows ~100 requests per 15 minutes for detailed fetches.
        The caller should batch appropriately.
    """
    access_token = await _ensure_valid_token(config)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{STRAVA_BASE_URL}/activities/{activity_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )

        if response.status_code == 401:
            raise StravaAuthError("Invalid token", requires_reauth=True)
        elif response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 900))
            raise StravaRateLimitError(retry_after)
        elif response.status_code == 404:
            raise StravaAPIError(404, f"Activity {activity_id} not found")
        elif response.status_code != 200:
            raise StravaAPIError(response.status_code, response.text)

        return map_strava_detail_to_raw(response.json())
```

### 6.6 Manual Activity Creation

```python
import uuid


def create_manual_activity(input_data: ManualActivityInput) -> RawActivity:
    """
    Create a raw activity from manual user input.

    Generates a unique ID and sets appropriate defaults.
    """
    activity_id = f"manual_{uuid.uuid4().hex[:12]}"

    return RawActivity(
        id=activity_id,
        source=ActivitySource.MANUAL,
        sport_type=input_data.sport_type,
        sub_type=None,
        name=f"Manual {input_data.sport_type}",
        date=input_data.date,
        start_time=None,  # Manual activities often lack precise time
        duration_seconds=input_data.duration_minutes * 60,
        distance_meters=input_data.distance_km * 1000 if input_data.distance_km else None,
        elevation_gain_meters=None,
        average_hr=input_data.average_hr,
        max_hr=None,
        has_hr_data=input_data.average_hr is not None,
        description=input_data.description,
        private_note=None,
        perceived_exertion=input_data.perceived_exertion,
        workout_type=None,
        suffer_score=None,
        has_polyline=False,
        gear_id=None,
        device_name=None,
        strava_created_at=None,
        strava_updated_at=None,
        raw_data={},
    )
```

## 7. Error Handling

### 7.1 Retry Strategy

| Error Type            | Retry Count | Backoff                  | Recovery                  |
| --------------------- | ----------- | ------------------------ | ------------------------- |
| Network timeout       | 3           | Exponential (2s, 4s, 8s) | Retry                     |
| HTTP 429 (rate limit) | 1           | Wait Retry-After         | Wait then retry once      |
| HTTP 401 (auth)       | 1           | None                     | Refresh token, retry once |
| HTTP 5xx (server)     | 3           | Exponential              | Retry                     |
| HTTP 4xx (client)     | 0           | None                     | Fail immediately          |

### 7.2 Graceful Degradation

```python
async def sync_strava_safe(
    config: "Config",
    since: datetime | None = None,
    until: datetime | None = None,
) -> tuple[list[RawActivity], SyncResult]:
    """
    Safe wrapper that handles partial failures gracefully.

    Even if some activities fail to fetch, returns what succeeded.
    """
    activities = []
    errors = []

    try:
        async for summary in iter_strava_activities(config, since, until):
            try:
                activity = await fetch_activity_details(
                    str(summary["id"]), config
                )
                activities.append(activity)
            except StravaRateLimitError as e:
                # Hit rate limit - return what we have
                errors.append(f"Rate limited after {len(activities)} activities")
                break
            except StravaAPIError as e:
                # Log and continue
                errors.append(f"Failed to fetch {summary['id']}: {e}")
                continue

    except StravaAuthError as e:
        if e.requires_reauth:
            errors.append("Authentication failed. Please reconnect Strava.")
        else:
            errors.append(str(e))

    return activities, SyncResult(
        success=len(errors) == 0,
        activities_fetched=len(activities),
        activities_new=len(activities),  # Dedup happens in caller
        activities_updated=0,
        activities_skipped=0,
        errors=errors,
        sync_duration_seconds=0,  # Caller sets this
    )
```

### 7.3 User-Facing Error Messages

| Error                         | User Message                                                                               |
| ----------------------------- | ------------------------------------------------------------------------------------------ |
| Token expired, refresh failed | "Your Strava connection expired. Please reconnect at Settings > Strava."                   |
| Rate limited                  | "Strava sync paused—API limit reached. I synced {N} activities. Try again in {M} minutes." |
| Network error                 | "Couldn't reach Strava. Check your internet connection and try again."                     |
| Partial sync                  | "Synced {N} activities, but {M} failed. Your data is safe—try syncing again later."        |

## 8. Integration Points

### 8.1 Called By

| Module | When                                |
| ------ | ----------------------------------- |
| M1     | User triggers "sync strava" command |
| M1     | User manually logs an activity      |

### 8.2 Calls To

| Module | Purpose                               |
| ------ | ------------------------------------- |
| M2     | Get Strava credentials, refresh token |
| M3     | Read/write training_history.yaml      |

### 8.3 Returns To

| Module | Data                                  |
| ------ | ------------------------------------- |
| M6     | List of RawActivity for normalization |

### 8.4 Sync Pipeline Position

```
User Request
    │
    ▼
[M1 CLI] ──> [M5 Ingestion] ──> [M6 Normalization] ──> [M7 RPE Analyzer]
                  │                                             │
                  │                                             ▼
                  └── RawActivity[] ──────────────────> [M8 Load Engine]
                                                                │
                                                                ▼
                                                        [M9 Metrics]
```

## 9. Test Scenarios

### 9.1 Unit Tests

```python
# test_activity_ingestion.py

def test_map_strava_summary():
    """Verify correct mapping of Strava fields"""
    strava_data = {
        "id": 12345678901,
        "type": "Run",
        "sport_type": "TrailRun",
        "name": "Morning Trail Run",
        "start_date_local": "2025-03-15T07:30:00Z",
        "elapsed_time": 3600,
        "distance": 10000,
        "average_heartrate": 145,
        "has_heartrate": True,
    }

    raw = map_strava_summary_to_raw(strava_data)

    assert raw.id == "12345678901"
    assert raw.source == ActivitySource.STRAVA
    assert raw.sport_type == "Run"
    assert raw.sub_type == "TrailRun"
    assert raw.duration_seconds == 3600
    assert raw.average_hr == 145


def test_dedup_primary_key():
    """Exact (source, id) match returns duplicate"""
    activity = RawActivity(
        id="123", source=ActivitySource.STRAVA,
        sport_type="Run", sub_type=None, name="Test",
        date=date(2025, 3, 15), start_time=None,
        duration_seconds=1800, distance_meters=5000,
        elevation_gain_meters=None, average_hr=None, max_hr=None,
        has_hr_data=False, description=None, private_note=None,
        perceived_exertion=None, workout_type=None, suffer_score=None,
        has_polyline=False, gear_id=None, device_name=None,
        strava_created_at=None, strava_updated_at=None, raw_data={},
    )

    existing = [{"source": "strava", "id": "123", "date": "2025-03-15"}]

    is_dup, existing_id = check_duplicate(activity, existing)
    assert is_dup is True
    assert existing_id == "123"


def test_dedup_fuzzy_match():
    """Fallback matching by date/time/duration"""
    activity = RawActivity(
        id="new_id", source=ActivitySource.STRAVA,
        sport_type="Run", sub_type=None, name="Test",
        date=date(2025, 3, 15),
        start_time=datetime(2025, 3, 15, 7, 30),
        duration_seconds=1800, distance_meters=5000,
        elevation_gain_meters=None, average_hr=None, max_hr=None,
        has_hr_data=False, description=None, private_note=None,
        perceived_exertion=None, workout_type=None, suffer_score=None,
        has_polyline=False, gear_id=None, device_name=None,
        strava_created_at=None, strava_updated_at=None, raw_data={},
    )

    # Existing activity with different id but same fingerprint
    existing = [{
        "source": "strava",
        "id": "old_id",
        "date": "2025-03-15",
        "sport_type": "run",
        "start_time": "2025-03-15T07:35:00",  # Within 30 min
        "duration_seconds": 1750,  # Within 5 min
    }]

    is_dup, existing_id = check_duplicate(activity, existing)
    assert is_dup is True
    assert existing_id == "old_id"


def test_manual_activity_creation():
    """Manual activities get unique IDs"""
    input_data = ManualActivityInput(
        sport_type="Run",
        date=date(2025, 3, 15),
        duration_minutes=45,
        distance_km=8.5,
        perceived_exertion=6,
    )

    activity = create_manual_activity(input_data)

    assert activity.source == ActivitySource.MANUAL
    assert activity.id.startswith("manual_")
    assert activity.duration_seconds == 2700
    assert activity.distance_meters == 8500.0
    assert activity.perceived_exertion == 6


def test_sync_date_range_first_sync():
    """First sync defaults to 90 days"""
    sync_state = SyncState(
        last_strava_sync_at=None,
        last_strava_activity_id=None,
    )

    since, until = determine_sync_range(sync_state, None, None)

    # Should be approximately 90 days ago
    days_ago = (datetime.now(timezone.utc) - since).days
    assert 89 <= days_ago <= 91
```

### 9.2 Integration Tests

```python
# test_strava_integration.py

@pytest.mark.integration
async def test_strava_sync_new_user():
    """Full sync for user with no prior data"""
    config = load_test_config()

    activities, result = await sync_strava(config)

    assert result.success
    assert result.activities_fetched > 0
    assert result.activities_new == result.activities_fetched


@pytest.mark.integration
async def test_strava_sync_incremental():
    """Incremental sync only fetches new activities"""
    config = load_test_config()

    # First sync
    _, first_result = await sync_strava(config)

    # Second sync should find nothing new
    _, second_result = await sync_strava(config)

    assert second_result.activities_new == 0
    assert second_result.activities_skipped >= 0


@pytest.mark.integration
async def test_strava_rate_limit_handling():
    """Graceful handling of rate limits"""
    config = load_test_config()

    # Simulate hitting rate limit
    with mock_rate_limit_response():
        activities, result = await sync_strava_safe(config)

    assert not result.success
    assert "Rate limited" in result.errors[0]
    # Should still return partial results
    assert len(activities) >= 0
```

### 9.3 Edge Cases

| Case                            | Expected Behavior                       |
| ------------------------------- | --------------------------------------- |
| Empty Strava account            | Return empty list, success=True         |
| All activities are duplicates   | Return empty list, activities_skipped=N |
| Token expires mid-sync          | Refresh token, retry                    |
| Network timeout on one activity | Skip activity, continue sync            |
| Strava returns malformed JSON   | Log error, continue with next activity  |
| Very old activity (>2 years)    | Include if within date range            |

## 10. Configuration

### 10.1 Default Settings

```python
# In config/settings.yaml
strava:
  sync_lookback_days: 90      # Default for first sync
  page_size: 50               # Activities per API page
  fetch_details: true         # Fetch full details including private notes
  rate_limit_buffer: 0.8      # Use 80% of rate limit capacity
```

### 10.2 Environment Overrides

```bash
# Override sync lookback
STRAVA_SYNC_LOOKBACK_DAYS=180

# Disable detail fetching (faster, less data)
STRAVA_FETCH_DETAILS=false
```

## 11. Performance Considerations

### 11.1 API Rate Limits

- Strava allows ~100 requests per 15 minutes
- Activity list = 1 request per 50 activities
- Activity detail = 1 request per activity
- Strategy: Fetch list first, then batch detail requests with delays

### 11.2 Memory Usage

- Hold activities in memory during sync
- 100 activities ≈ 1 MB (with raw_data)
- For large syncs (>500 activities): consider streaming to disk

### 11.3 Sync Duration Estimates

| Activities | List Requests | Detail Requests | Est. Duration |
| ---------- | ------------- | --------------- | ------------- |
| 50         | 1             | 50              | ~30 seconds   |
| 200        | 4             | 200             | ~3 minutes    |
| 500        | 10            | 500             | ~8 minutes    |

## 12. Changelog

| Version | Date       | Changes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1.0.1   | 2026-01-12 | **Fixed cross-module consistency and over-engineering**: (1) Converted all `@dataclass` types to `BaseModel` for Pydantic consistency (RawActivity, SyncState, SyncResult). (2) **CRITICAL FIX**: Aligned SyncState field names with M4's training_history.yaml schema - changed `last_sync_at` → `last_strava_sync_at`, `last_activity_id` → `last_strava_activity_id`, removed `last_activity_timestamp` (not in M4 schema). (3) Updated training_history.yaml example to match M4's schema exactly (removed nested "strava_sync" key). (4) Added M4 to dependencies (sync state managed by M4). (5) Added note about v0 using synchronous I/O instead of async to avoid over-engineering. (6) Added complete algorithms for `get_sync_state()` and `update_sync_state()` functions. (7) Updated sync date range algorithm and tests to use corrected field names. |
| 1.0.0   | 2026-01-12 | Initial specification                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
