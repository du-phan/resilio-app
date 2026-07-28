"""Ownership-proven idempotent workout publication."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from resilio.core.locking import OperationLock
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.renderer import render_structured_workout
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import (
    ActivityFilterDTO,
    EventDTO,
    EventWriteDTO,
    SportSettingsDTO,
)
from resilio.integrations.intervals_icu.errors import IntervalsNotFoundError
from resilio.schemas.plan import WorkoutPrescription, WorkoutType
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PlanPublicationItem,
    PlanPublicationReport,
    PublicationResult,
    PublishedWorkout,
)
from resilio.schemas.structured_workout import TargetMode, WorkoutSport

OWNERSHIP_PREFIX = "resilio:v1:workout:"


class PublicationSafetyError(RuntimeError):
    pass


def external_id_for(workout_id: str) -> str:
    return f"{OWNERSHIP_PREFIX}{workout_id}"


def uid_for(workout_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, external_id_for(workout_id)))


def _sha(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


def _sport_settings_version(settings: SportSettingsDTO) -> str:
    payload = settings.model_dump(mode="json", exclude_none=False)
    return _sha(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _publication_fingerprint(event: EventWriteDTO, settings_version: str) -> str:
    payload = {
        "event": event.model_dump(mode="json", exclude_none=False),
        "sport_settings_version": settings_version,
    }
    return _sha(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _event_type(sport: str) -> str:
    if sport == WorkoutSport.RUN:
        return "Run"
    if sport == WorkoutSport.CYCLE:
        return "Ride"
    raise PublicationSafetyError(f"Unsupported workout sport: {sport}")


def _event_target(modes: set[str]) -> str:
    if len(modes) != 1:
        return "AUTO"
    mode = next(iter(modes))
    targets = {
        TargetMode.PACE.value: "PACE",
        TargetMode.HEART_RATE.value: "HR",
        TargetMode.POWER.value: "POWER",
    }
    try:
        return targets[mode]
    except KeyError as exc:
        raise PublicationSafetyError(
            f"Unsupported workout target mode: {mode}"
        ) from exc


def _settings_for(
    settings: list[SportSettingsDTO],
    event_type: str,
) -> SportSettingsDTO:
    matches = [item for item in settings if event_type in item.types]
    if len(matches) != 1:
        raise PublicationSafetyError(
            f"Expected one sport-settings record for {event_type}, found {len(matches)}"
        )
    return matches[0]


def _assert_remote_ownership(
    remote: EventDTO,
    *,
    uid: str,
    external_id: str,
) -> None:
    if remote.uid != uid or remote.external_id != external_id:
        raise PublicationSafetyError(
            "Remote event ownership proof failed: UID/external ID mismatch"
        )
    if not external_id.startswith(OWNERSHIP_PREFIX):
        raise PublicationSafetyError("Remote event is outside the Resilio namespace")


def _assert_remote_external_ownership(
    remote: EventDTO,
    *,
    external_id: str,
) -> str:
    """Accept a server-assigned UID only when the external namespace survives."""
    if remote.external_id != external_id:
        raise PublicationSafetyError(
            "Remote event ownership proof failed: external ID mismatch"
        )
    if not external_id.startswith(OWNERSHIP_PREFIX):
        raise PublicationSafetyError("Remote event is outside the Resilio namespace")
    if not remote.uid:
        raise PublicationSafetyError(
            "Remote event ownership proof failed: server UID is missing"
        )
    return remote.uid


def _assert_remote_matches(remote: EventDTO, event: EventWriteDTO) -> None:
    """Require the remote owned event to match every rendered publication field."""
    if (
        remote.category != event.category
        or remote.start_date_local != event.start_date_local
        or remote.type != event.type
        or remote.name != event.name
        or remote.description != event.description
        or remote.target != event.target
    ):
        raise PublicationSafetyError(
            "Remote event read-back does not match the owned rendered workout"
        )


def _filter_values(value: object) -> set[str]:
    """Flatten the loose ActivityFilter value shape into comparable strings."""
    if isinstance(value, str):
        return {value.casefold()}
    if isinstance(value, (list, tuple, set)):
        result: set[str] = set()
        for item in value:
            result.update(_filter_values(item))
        return result
    if isinstance(value, dict):
        result = set()
        for item in value.values():
            result.update(_filter_values(item))
        return result
    return set()


def _garmin_filter_allows(
    filters: list[ActivityFilterDTO],
    event_type: str,
) -> bool:
    """Prove that Garmin forwarding is unrestricted or admits the event type."""
    if not filters:
        return True
    type_filters = [item for item in filters if item.field_id == "type"]
    if not type_filters:
        return False
    target = event_type.casefold()
    negative_operators = {"!=", "not", "not_in", "notin"}
    for item in type_filters:
        values = _filter_values(item.value)
        if item.code:
            values.add(item.code.casefold())
        if (
            target in values
            and not item.not_
            and (item.operator or "").casefold() not in negative_operators
        ):
            return True
    return False


def _validated_local_start(
    occurrence_date,
    local_time: time,
    timezone_name: str,
) -> str:
    """Reject ambiguous/nonexistent wall times before publishing."""
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise PublicationSafetyError(
            f"Athlete timezone is not recognized: {timezone_name}"
        ) from exc

    naive = datetime.combine(occurrence_date, local_time)
    valid_offsets = set()
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold)
        round_trip = (
            aware.astimezone(timezone.utc)
            .astimezone(zone)
            .replace(tzinfo=None)
        )
        if round_trip == naive:
            valid_offsets.add(aware.utcoffset())
    if not valid_offsets:
        raise PublicationSafetyError(
            "Local workout time does not exist because of a daylight-saving transition"
        )
    if len(valid_offsets) > 1:
        raise PublicationSafetyError(
            "Local workout time is ambiguous because of a daylight-saving transition"
        )
    return naive.isoformat()


def _pending_matches(
    pending: PendingWorkoutPublication,
    *,
    uid: str,
    external_id: str,
    fingerprint: str,
) -> bool:
    return (
        pending.uid == uid
        and pending.external_id == external_id
        and pending.publication_fingerprint_sha256 == fingerprint
    )


def _published_record(
    *,
    workout: WorkoutPrescription,
    event_id: int,
    requested_uid: str,
    uid: str,
    external_id: str,
    fingerprint: str,
    rendered_hash: str,
    settings_version: str,
    start_local: str,
) -> PublishedWorkout:
    return PublishedWorkout(
        local_workout_id=workout.id,
        event_id=event_id,
        requested_uid=requested_uid,
        uid=uid,
        external_id=external_id,
        publication_fingerprint_sha256=fingerprint,
        rendered_workout_sha256=rendered_hash,
        sport_settings_version_sha256=settings_version,
        sport=str(workout.sport),
        occurrence_date=workout.date,
        start_date_local=start_local,
        verified_at_utc=datetime.now(timezone.utc),
    )


class WorkoutPublicationService:
    def __init__(
        self,
        repo: RepositoryIO,
        client: IntervalsIcuClient,
    ):
        self.repo = repo
        self.client = client

    def publish(
        self,
        workout: WorkoutPrescription,
        *,
        start_time_local: Optional[time] = None,
    ) -> PublicationResult:
        lock_path = self.repo.resolve_path(
            "data/state/.workout-publication.lock"
        )
        with OperationLock(lock_path, "workout_publication"):
            return self._publish(
                workout,
                start_time_local=start_time_local,
            )

    def publish_plan(
        self,
        workouts: list[WorkoutPrescription],
        *,
        from_date: date,
    ) -> PlanPublicationReport:
        """Reconcile all future structured workouts without deleting stale events."""
        lock_path = self.repo.resolve_path(
            "data/state/.workout-publication.lock"
        )
        with OperationLock(lock_path, "workout_publication"):
            workout_ids = [workout.id for workout in workouts]
            if len(workout_ids) != len(set(workout_ids)):
                raise PublicationSafetyError(
                    "Plan contains duplicate workout IDs"
                )
            manifest = load_manifest(self.repo)
            known_workout_ids = set(workout_ids)
            report = PlanPublicationReport(
                from_date=from_date,
                stale_manifest_workout_ids=sorted(
                    (
                        set(manifest.workouts)
                        | set(manifest.pending)
                    )
                    - known_workout_ids
                ),
            )
            selected = sorted(
                (
                    workout
                    for workout in workouts
                    if workout.date >= from_date
                ),
                key=lambda workout: (workout.date, workout.id),
            )
            report.workouts_considered = len(selected)
            for workout in selected:
                if workout.workout_type == WorkoutType.REST:
                    report.items.append(
                        PlanPublicationItem(
                            local_workout_id=workout.id,
                            occurrence_date=workout.date,
                            status="skipped_rest",
                        )
                    )
                    continue
                if workout.structured_workout is None:
                    report.items.append(
                        PlanPublicationItem(
                            local_workout_id=workout.id,
                            occurrence_date=workout.date,
                            status="skipped_unstructured",
                        )
                    )
                    continue
                report.eligible_workouts += 1
                try:
                    result = self._publish(workout)
                except Exception as exc:
                    report.partial = True
                    report.items.append(
                        PlanPublicationItem(
                            local_workout_id=workout.id,
                            occurrence_date=workout.date,
                            status="error",
                            error_type=getattr(
                                exc,
                                "error_type",
                                (
                                    "publication_safety"
                                    if isinstance(
                                        exc,
                                        PublicationSafetyError,
                                    )
                                    else "publication"
                                ),
                            ),
                            message=str(exc),
                        )
                    )
                    continue
                report.items.append(
                    PlanPublicationItem(
                        local_workout_id=workout.id,
                        occurrence_date=workout.date,
                        status=result.action,
                        event_id=result.event_id,
                    )
                )
            return report

    def _publish(
        self,
        workout: WorkoutPrescription,
        *,
        start_time_local: Optional[time] = None,
    ) -> PublicationResult:
        if workout.workout_type == WorkoutType.REST:
            raise PublicationSafetyError("Rest days are never published")
        if workout.structured_workout is None:
            raise PublicationSafetyError(
                "Publishing requires a typed structured_workout"
            )
        if workout.structured_workout.sport != workout.sport:
            raise PublicationSafetyError("Workout sport does not match its structure")

        athlete = self.client.get_athlete()
        if not athlete.timezone:
            raise PublicationSafetyError("Athlete timezone is required for publication")
        connections = self.client.get_connections(athlete.id)
        all_settings = self.client.get_sport_settings(athlete.id)
        event_type = _event_type(workout.sport)
        sport_settings = _settings_for(all_settings, event_type)
        modes = workout.structured_workout.target_modes()

        if not (
            connections.garmin_training_connected or connections.wahoo_connected
        ):
            raise PublicationSafetyError(
                "No supported device workout connection is active"
            )
        if connections.garmin_training_connected:
            if athlete.garmin_upload_workouts is not True:
                raise PublicationSafetyError(
                    "Garmin planned-workout forwarding is not enabled"
                )
            if not _garmin_filter_allows(
                athlete.garmin_upload_filters,
                event_type,
            ):
                raise PublicationSafetyError(
                    f"Garmin workout filters do not admit {event_type}"
                )
        if (
            connections.wahoo_connected
            and athlete.wahoo_upload_workouts is not True
        ):
            raise PublicationSafetyError(
                "Wahoo planned-workout forwarding is not enabled"
            )
        if TargetMode.PACE in modes and (
            sport_settings.threshold_pace is None or not sport_settings.pace_zones
        ):
            raise PublicationSafetyError(
                "Pace-target publication requires threshold pace and pace zones"
            )
        if TargetMode.POWER in modes and sport_settings.ftp is None:
            raise PublicationSafetyError(
                "Power-target publication requires FTP"
            )
        if connections.wahoo_connected and len(modes) > 1:
            raise PublicationSafetyError(
                "Mixed target modes are blocked for Wahoo publication"
            )
        if connections.wahoo_connected and workout.structured_workout.uses_lap_press():
            raise PublicationSafetyError(
                "Lap-button steps are blocked for Wahoo until device support is verified"
            )

        event_time = start_time_local or workout.start_time_local
        if event_time is None and sport_settings.default_workout_time:
            try:
                event_time = time.fromisoformat(sport_settings.default_workout_time)
            except ValueError as exc:
                raise PublicationSafetyError(
                    "Sport settings contain an invalid default workout time"
                ) from exc
        if event_time is None:
            raise PublicationSafetyError(
                "A local workout time or sport-settings default is required"
            )

        rendered = render_structured_workout(workout.structured_workout.steps)
        external_id = external_id_for(workout.id)
        requested_uid = uid_for(workout.id)
        start_local = _validated_local_start(
            workout.date,
            event_time,
            athlete.timezone,
        )
        manifest = load_manifest(self.repo)
        previous = manifest.workouts.get(workout.id)
        pending = manifest.pending.get(workout.id)
        uid = previous.uid if previous is not None else requested_uid
        event = EventWriteDTO(
            uid=uid,
            external_id=external_id,
            type=event_type,
            name=workout.purpose or str(workout.workout_type),
            description=rendered,
            start_date_local=start_local,
            target=_event_target(modes),
        )
        settings_version = _sport_settings_version(sport_settings)
        fingerprint = _publication_fingerprint(event, settings_version)
        rendered_hash = _sha(rendered)
        pending_matches = (
            pending is not None
            and _pending_matches(
                pending,
                uid=uid,
                external_id=external_id,
                fingerprint=fingerprint,
            )
        )

        event_range_start = workout.date
        event_range_end = workout.date
        if pending is not None:
            event_range_start = min(event_range_start, pending.occurrence_date)
            event_range_end = max(event_range_end, pending.occurrence_date)
        range_events = self.client.list_events(
            event_range_start,
            event_range_end,
            athlete_id=athlete.id,
        )
        identity_matches = [
            item
            for item in range_events
            if item.uid == uid or item.external_id == external_id
        ]
        if len(identity_matches) > 1:
            raise PublicationSafetyError(
                "Multiple remote events claim the workout ownership identity"
            )
        for remote in identity_matches:
            if previous is not None:
                _assert_remote_ownership(
                    remote,
                    uid=previous.uid,
                    external_id=external_id,
                )
            else:
                _assert_remote_external_ownership(
                    remote,
                    external_id=external_id,
                )
        if pending is not None and not pending_matches:
            if identity_matches:
                raise PublicationSafetyError(
                    "Pending publication intent changed after a remote event "
                    "claimed its ownership identity"
                )
            del manifest.pending[workout.id]
            save_manifest(self.repo, manifest)
            pending = None
        if identity_matches and previous is None and pending is None:
            raise PublicationSafetyError(
                "Remote owned-looking event exists without a local manifest"
            )
        if pending is not None and identity_matches:
            recovered = identity_matches[0]
            try:
                _assert_remote_matches(recovered, event)
            except PublicationSafetyError:
                if previous is None:
                    raise
                # A known previous version can legitimately remain when the
                # interrupted upsert failed before applying the pending update.
            else:
                remote_uid = _assert_remote_external_ownership(
                    recovered,
                    external_id=external_id,
                )
                recovered_event = event.model_copy(
                    update={"uid": remote_uid}
                )
                recovered_fingerprint = _publication_fingerprint(
                    recovered_event,
                    settings_version,
                )
                manifest.workouts[workout.id] = _published_record(
                    workout=workout,
                    event_id=recovered.id,
                    requested_uid=requested_uid,
                    uid=remote_uid,
                    external_id=external_id,
                    fingerprint=recovered_fingerprint,
                    rendered_hash=rendered_hash,
                    settings_version=settings_version,
                    start_local=start_local,
                )
                del manifest.pending[workout.id]
                save_manifest(self.repo, manifest)
                return PublicationResult(
                    action="recovered",
                    local_workout_id=workout.id,
                    event_id=recovered.id,
                    uid=remote_uid,
                    external_id=external_id,
                    fingerprint_sha256=recovered_fingerprint,
                )
        if previous is not None:
            if (
                previous.requested_uid != requested_uid
                or previous.external_id != external_id
            ):
                raise PublicationSafetyError("Local manifest ownership identity drifted")
            remote = self.client.get_event(previous.event_id, athlete_id=athlete.id)
            _assert_remote_ownership(remote, uid=uid, external_id=external_id)
            if pending is not None:
                try:
                    _assert_remote_matches(remote, event)
                except PublicationSafetyError:
                    # The durable intent is for a not-yet-applied update. The
                    # known, manifest-owned prior version may be upserted.
                    pass
                else:
                    manifest.workouts[workout.id] = _published_record(
                        workout=workout,
                        event_id=remote.id,
                        requested_uid=requested_uid,
                        uid=uid,
                        external_id=external_id,
                        fingerprint=fingerprint,
                        rendered_hash=rendered_hash,
                        settings_version=settings_version,
                        start_local=start_local,
                    )
                    del manifest.pending[workout.id]
                    save_manifest(self.repo, manifest)
                    return PublicationResult(
                        action="recovered",
                        local_workout_id=workout.id,
                        event_id=remote.id,
                        uid=uid,
                        external_id=external_id,
                        fingerprint_sha256=fingerprint,
                    )
            if previous.publication_fingerprint_sha256 == fingerprint:
                _assert_remote_matches(remote, event)
                return PublicationResult(
                    action="noop",
                    local_workout_id=workout.id,
                    event_id=previous.event_id,
                    uid=uid,
                    external_id=external_id,
                    fingerprint_sha256=fingerprint,
                )

        manifest.pending[workout.id] = PendingWorkoutPublication(
            local_workout_id=workout.id,
            uid=uid,
            external_id=external_id,
            publication_fingerprint_sha256=fingerprint,
            rendered_workout_sha256=rendered_hash,
            sport_settings_version_sha256=settings_version,
            sport=str(workout.sport),
            occurrence_date=workout.date,
            start_date_local=start_local,
            prepared_at_utc=datetime.now(timezone.utc),
        )
        save_manifest(self.repo, manifest)
        response = self.client.upsert_event(event, athlete_id=athlete.id)
        read_back = self.client.get_event(response.id, athlete_id=athlete.id)
        remote_uid = _assert_remote_external_ownership(
            read_back,
            external_id=external_id,
        )
        _assert_remote_matches(read_back, event)
        persisted_event = event.model_copy(update={"uid": remote_uid})
        persisted_fingerprint = _publication_fingerprint(
            persisted_event,
            settings_version,
        )

        manifest.workouts[workout.id] = _published_record(
            workout=workout,
            event_id=read_back.id,
            requested_uid=requested_uid,
            uid=remote_uid,
            external_id=external_id,
            fingerprint=persisted_fingerprint,
            rendered_hash=rendered_hash,
            settings_version=settings_version,
            start_local=start_local,
        )
        del manifest.pending[workout.id]
        save_manifest(self.repo, manifest)
        return PublicationResult(
            action="updated" if previous else "created",
            local_workout_id=workout.id,
            event_id=read_back.id,
            uid=remote_uid,
            external_id=external_id,
            fingerprint_sha256=persisted_fingerprint,
        )

    def delete(self, local_workout_id: str) -> PublicationResult:
        lock_path = self.repo.resolve_path(
            "data/state/.workout-publication.lock"
        )
        with OperationLock(lock_path, "workout_publication"):
            return self._delete(local_workout_id)

    def _delete(self, local_workout_id: str) -> PublicationResult:
        manifest = load_manifest(self.repo)
        record = manifest.workouts.get(local_workout_id)
        if record is None:
            raise PublicationSafetyError(
                "Deletion requires a local publication manifest record"
            )
        athlete = self.client.get_athlete()
        try:
            remote = self.client.get_event(
                record.event_id,
                athlete_id=athlete.id,
            )
        except IntervalsNotFoundError:
            del manifest.workouts[local_workout_id]
            save_manifest(self.repo, manifest)
            return PublicationResult(
                action="recovered_deleted",
                local_workout_id=local_workout_id,
                event_id=record.event_id,
                uid=record.uid,
                external_id=record.external_id,
            )
        _assert_remote_ownership(
            remote,
            uid=record.uid,
            external_id=record.external_id,
        )
        self.client.delete_event(record.event_id, athlete_id=athlete.id)
        try:
            self.client.get_event(record.event_id, athlete_id=athlete.id)
        except IntervalsNotFoundError:
            pass
        else:
            raise PublicationSafetyError("Deleted event still exists on read-back")
        del manifest.workouts[local_workout_id]
        save_manifest(self.repo, manifest)
        return PublicationResult(
            action="deleted",
            local_workout_id=local_workout_id,
            event_id=record.event_id,
            uid=record.uid,
            external_id=record.external_id,
        )
