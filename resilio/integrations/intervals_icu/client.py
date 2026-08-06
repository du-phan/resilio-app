"""Small, retry-aware HTTP client for the supported API operations."""

from __future__ import annotations

import random
import re
import time
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Optional, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from resilio import __version__
from resilio.integrations.intervals_icu.dto import (
    ActivityDTO,
    ActivitySummaryDTO,
    AthleteDTO,
    ConnectionsDTO,
    EventDTO,
    EventWriteDTO,
    HeartRateCurveDTO,
    HiddenActivityDTO,
    SportSettingsDTO,
    WellnessDTO,
)
from resilio.integrations.intervals_icu.errors import (
    IntervalsAuthenticationError,
    IntervalsAuthorizationError,
    IntervalsInvalidPayloadError,
    IntervalsNotFoundError,
    IntervalsRateLimitError,
    IntervalsTransportError,
    UnsupportedSportError,
)
from resilio.schemas.config import Config

T = TypeVar("T", bound=BaseModel)


class IntervalsIcuClient:
    """Personal-key client with a narrow, typed operation surface."""

    def __init__(
        self,
        config: Config,
        *,
        transport: Optional[httpx.BaseTransport] = None,
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ):
        settings = config.settings.intervals_icu
        self.athlete_id = settings.athlete_alias
        self.max_attempts = settings.max_read_attempts
        self._sleeper = sleeper
        self._jitter = jitter
        self._client = httpx.Client(
            base_url=settings.api_base_url.rstrip("/"),
            auth=httpx.BasicAuth(
                "API_KEY",
                config.intervals_icu_api_key.get_secret_value(),
            ),
            headers={
                "Accept": "application/json",
                "User-Agent": f"Resilio/{__version__}",
            },
            timeout=settings.request_timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "IntervalsIcuClient":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object | None,
    ) -> None:
        self.close()

    def _retry_after(self, response: httpx.Response) -> Optional[int]:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        try:
            return max(int(raw), 0)
        except ValueError:
            try:
                target = parsedate_to_datetime(raw)
                response_date = parsedate_to_datetime(response.headers["Date"])
                return max(int((target - response_date).total_seconds()), 0)
            except Exception:
                return None

    @staticmethod
    def _rejected_activity_type(
        response: httpx.Response,
        request_payload: object,
    ) -> Optional[str]:
        """Extract only a provider type rejection proven to match our request."""
        try:
            error = response.json().get("error")
        except (AttributeError, ValueError):
            return None
        if not isinstance(error, str):
            return None
        match = re.fullmatch(
            r"Activity\[(\d+)\] create failed: Invalid type \[([A-Za-z][A-Za-z0-9]*)\]",
            error,
        )
        if match is None or not isinstance(request_payload, list):
            return None
        index = int(match.group(1))
        if index >= len(request_payload) or not isinstance(request_payload[index], dict):
            return None
        rejected_type = match.group(2)
        if request_payload[index].get("type") != rejected_type:
            return None
        return rejected_type

    def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        retry_reads: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        attempts = self.max_attempts if retry_reads and method.upper() == "GET" else 1
        last_transport_error: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                response = self._client.request(method, path, **kwargs)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                last_transport_error = exc
                if attempt == attempts:
                    break
                self._sleeper(min(8.0, 0.5 * (2 ** (attempt - 1))) + self._jitter(0, 0.25))
                continue

            request_id = response.headers.get("X-Request-ID") or response.headers.get("CF-Ray")
            status = response.status_code
            if 200 <= status < 300:
                return response
            if status == 401:
                raise IntervalsAuthenticationError(
                    "Intervals.icu rejected the API credential",
                    operation=operation,
                    status_code=status,
                    request_id=request_id,
                )
            if status == 403:
                raise IntervalsAuthorizationError(
                    "Intervals.icu denied this operation",
                    operation=operation,
                    status_code=status,
                    request_id=request_id,
                )
            if status == 404:
                raise IntervalsNotFoundError(
                    "Intervals.icu resource was not found",
                    operation=operation,
                    status_code=status,
                    request_id=request_id,
                )
            if status in {400, 422}:
                rejected_type = self._rejected_activity_type(
                    response,
                    kwargs.get("json"),
                )
                if rejected_type is not None:
                    raise UnsupportedSportError(
                        f"Intervals.icu does not support activity type {rejected_type}",
                        operation=operation,
                        status_code=status,
                        request_id=request_id,
                    )
                raise IntervalsInvalidPayloadError(
                    "Intervals.icu rejected the request payload",
                    operation=operation,
                    status_code=status,
                    request_id=request_id,
                )
            if status == 429:
                retry_after = self._retry_after(response)
                if attempt < attempts and retry_reads:
                    delay = retry_after if retry_after is not None else min(8.0, 2**attempt)
                    self._sleeper(float(delay) + self._jitter(0, 0.25))
                    continue
                raise IntervalsRateLimitError(
                    "Intervals.icu rate limit reached",
                    operation=operation,
                    status_code=status,
                    retry_after_seconds=retry_after,
                    request_id=request_id,
                )
            if status >= 500 and attempt < attempts and retry_reads:
                self._sleeper(min(8.0, 0.5 * (2 ** (attempt - 1))) + self._jitter(0, 0.25))
                continue
            raise IntervalsTransportError(
                "Intervals.icu request failed",
                operation=operation,
                status_code=status,
                request_id=request_id,
            )

        raise IntervalsTransportError(
            "Intervals.icu transport failed after bounded retries",
            operation=operation,
        ) from last_transport_error

    def _validated(self, response: httpx.Response, model: type[T], operation: str) -> T:
        try:
            return model.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise IntervalsInvalidPayloadError(
                "Intervals.icu returned an invalid payload",
                operation=operation,
                status_code=response.status_code,
            ) from exc

    def _validated_list(
        self,
        response: httpx.Response,
        model: type[T],
        operation: str,
    ) -> list[T]:
        try:
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("expected a list")
            return [model.model_validate(item) for item in payload]
        except (ValueError, ValidationError) as exc:
            raise IntervalsInvalidPayloadError(
                "Intervals.icu returned an invalid collection payload",
                operation=operation,
                status_code=response.status_code,
            ) from exc

    def get_athlete(self, athlete_id: Optional[str] = None) -> AthleteDTO:
        operation = "get_athlete"
        response = self._request(
            "GET",
            f"/athlete/{athlete_id or self.athlete_id}",
            operation=operation,
        )
        return self._validated(response, AthleteDTO, operation)

    def get_connections(self, athlete_id: Optional[str] = None) -> ConnectionsDTO:
        operation = "get_connections"
        response = self._request(
            "GET",
            f"/athlete/{athlete_id or self.athlete_id}/connections",
            operation=operation,
        )
        return self._validated(response, ConnectionsDTO, operation)

    def get_sport_settings(self, athlete_id: Optional[str] = None) -> list[SportSettingsDTO]:
        operation = "get_sport_settings"
        response = self._request(
            "GET",
            f"/athlete/{athlete_id or self.athlete_id}/sport-settings",
            operation=operation,
        )
        return self._validated_list(response, SportSettingsDTO, operation)

    def get_wellness(
        self,
        oldest: date,
        newest: date,
        *,
        athlete_id: Optional[str] = None,
    ) -> list[WellnessDTO]:
        """Read inclusive daily wellness/training-state rows."""
        if newest < oldest:
            raise ValueError("newest wellness date cannot precede oldest")
        operation = "get_wellness"
        response = self._request(
            "GET",
            f"/athlete/{athlete_id or self.athlete_id}/wellness",
            operation=operation,
            params={
                "oldest": oldest.isoformat(),
                "newest": newest.isoformat(),
            },
        )
        return self._validated_list(response, WellnessDTO, operation)

    def list_activities(
        self,
        oldest: date,
        newest: date,
        *,
        athlete_id: Optional[str] = None,
        limit: int = 1000,
    ) -> list[ActivitySummaryDTO | HiddenActivityDTO]:
        operation = "list_activities"
        response = self._request(
            "GET",
            f"/athlete/{athlete_id or self.athlete_id}/activities",
            operation=operation,
            params={
                "oldest": oldest.isoformat(),
                "newest": newest.isoformat(),
                "limit": limit,
            },
        )
        try:
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("expected list")
            result: list[ActivitySummaryDTO | HiddenActivityDTO] = []
            for item in payload:
                if not isinstance(item, dict):
                    raise ValueError("activity row is not an object")
                if "_note" in item and "type" not in item:
                    result.append(HiddenActivityDTO.model_validate(item))
                else:
                    result.append(ActivitySummaryDTO.model_validate(item))
            return result
        except (ValueError, ValidationError) as exc:
            raise IntervalsInvalidPayloadError(
                "Intervals.icu returned an invalid activity list",
                operation=operation,
                status_code=response.status_code,
            ) from exc

    def get_activity(self, activity_id: str, *, intervals: bool = True) -> ActivityDTO:
        operation = "get_activity"
        response = self._request(
            "GET",
            f"/activity/{activity_id}",
            operation=operation,
            params={"intervals": str(intervals).lower()},
        )
        return self._validated(response, ActivityDTO, operation)

    def get_activity_heart_rate_curve(self, activity_id: str) -> HeartRateCurveDTO:
        """Fetch duration-to-HR evidence for one exact activity without streams."""
        operation = "get_activity_heart_rate_curve"
        response = self._request(
            "GET",
            f"/activity/{activity_id}/hr-curve.json",
            operation=operation,
        )
        return self._validated(response, HeartRateCurveDTO, operation)

    def get_activities(
        self,
        activity_ids: list[str],
        *,
        athlete_id: Optional[str] = None,
        intervals: bool = True,
    ) -> list[ActivityDTO]:
        operation = "get_activities"
        ids = ",".join(activity_ids)
        response = self._request(
            "GET",
            f"/athlete/{athlete_id or self.athlete_id}/activities/{ids}",
            operation=operation,
            params={"intervals": str(intervals).lower()},
        )
        return self._validated_list(response, ActivityDTO, operation)

    def get_original_file(self, activity_id: str) -> bytes:
        operation = "get_original_file"
        response = self._request(
            "GET",
            f"/activity/{activity_id}/file",
            operation=operation,
        )
        if not response.content:
            raise IntervalsInvalidPayloadError(
                "Intervals.icu returned an empty original activity file",
                operation=operation,
                status_code=response.status_code,
            )
        return response.content

    def delete_activity(self, activity_id: str) -> None:
        """Delete one exact activity without a blind retry."""
        self._request(
            "DELETE",
            f"/activity/{activity_id}",
            operation="delete_activity",
            retry_reads=False,
        )

    def list_events(
        self,
        oldest: date,
        newest: date,
        *,
        athlete_id: Optional[str] = None,
    ) -> list[EventDTO]:
        operation = "list_events"
        response = self._request(
            "GET",
            f"/athlete/{athlete_id or self.athlete_id}/events.json",
            operation=operation,
            params={"oldest": oldest.isoformat(), "newest": newest.isoformat()},
        )
        return self._validated_list(response, EventDTO, operation)

    def get_event(self, event_id: int, *, athlete_id: Optional[str] = None) -> EventDTO:
        operation = "get_event"
        response = self._request(
            "GET",
            f"/athlete/{athlete_id or self.athlete_id}/events/{event_id}",
            operation=operation,
        )
        return self._validated(response, EventDTO, operation)

    def upsert_event(
        self,
        event: EventWriteDTO,
        *,
        athlete_id: Optional[str] = None,
    ) -> EventDTO:
        operation = "upsert_event"
        response = self._request(
            "POST",
            f"/athlete/{athlete_id or self.athlete_id}/events",
            operation=operation,
            retry_reads=False,
            params={"upsertOnUid": "true"},
            json=event.model_dump(mode="json"),
        )
        return self._validated(response, EventDTO, operation)

    def delete_event(self, event_id: int, *, athlete_id: Optional[str] = None) -> None:
        self._request(
            "DELETE",
            f"/athlete/{athlete_id or self.athlete_id}/events/{event_id}",
            operation="delete_event",
            retry_reads=False,
            params={"others": "false"},
        )
