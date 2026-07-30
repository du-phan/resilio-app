"""Structured rendering and ownership-safe publication tests."""

from datetime import date, time

import pytest
from pydantic import ValidationError

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import (
    load_manifest,
    save_manifest,
)
from resilio.core.workout_publication.renderer import render_structured_workout
from resilio.core.workout_publication.service import (
    PublicationSafetyError,
    uid_for,
)
from resilio.core.workout_publication.service import (
    WorkoutPublicationService as ProductionWorkoutPublicationService,
)
from resilio.integrations.intervals_icu.dto import (
    AthleteDTO,
    ConnectionsDTO,
    EventDTO,
    EventWriteDTO,
    SportSettingsDTO,
)
from resilio.integrations.intervals_icu.errors import (
    IntervalsNotFoundError,
    IntervalsTransportError,
)
from resilio.schemas.plan import WorkoutPrescription, WorkoutType
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import PublicationManifest
from resilio.schemas.structured_workout import StructuredWorkout


def _structure(
    sport: str = "run",
    *,
    mixed: bool = False,
    lap_press: bool = False,
) -> StructuredWorkout:
    steps = [
        {
            "kind": "steady",
            "duration": {"unit": "seconds", "value": 600},
            "target": {
                "mode": "pace" if sport == "run" else "power",
                "unit": ("seconds_per_kilometer" if sport == "run" else "percent_ftp"),
                "minimum": 300 if sport == "run" else 85,
                "maximum": 330 if sport == "run" else 95,
            },
            "intensity": "warmup",
        },
        {
            "kind": "repeat",
            "repetitions": 3,
            "steps": [
                {
                    "kind": "steady",
                    "duration": {
                        "unit": "meters",
                        "value": 1000,
                        "nominal_seconds": 255,
                    },
                    "target": {
                        "mode": "pace" if sport == "run" else "power",
                        "unit": ("seconds_per_kilometer" if sport == "run" else "percent_ftp"),
                        "minimum": 250 if sport == "run" else 105,
                        "maximum": 260 if sport == "run" else 110,
                    },
                    "intensity": "interval",
                    "cue": "Smooth and controlled",
                },
                {
                    "kind": "steady",
                    "duration": (
                        {"unit": "until_lap_press", "nominal_seconds": 120}
                        if lap_press
                        else {"unit": "seconds", "value": 120}
                    ),
                    "target": (
                        {
                            "mode": "heart_rate",
                            "unit": "beats_per_minute",
                            "minimum": 120,
                            "maximum": 140,
                        }
                        if mixed
                        else None
                    ),
                    "intensity": "recovery",
                },
            ],
        },
    ]
    return StructuredWorkout.model_validate({"sport": sport, "steps": steps})


def _workout(
    *,
    workout_id: str = "workout-1",
    occurrence: date = date(2026, 10, 25),
    sport: str = "run",
    mixed: bool = False,
    lap_press: bool = False,
) -> WorkoutPrescription:
    return WorkoutPrescription(
        id=workout_id,
        date=occurrence,
        start_time_local=time(7),
        sport=sport,
        workout_type=WorkoutType.INTERVALS,
        planned_duration_seconds=1_725,
        planned_distance_meters=9_000 if sport == "run" else None,
        planned_low_intensity_duration_seconds=960,
        planned_moderate_intensity_duration_seconds=0,
        planned_high_intensity_duration_seconds=765,
        target_rpe_1_to_10=8,
        purpose="Three controlled repetitions",
        structured_workout=_structure(
            sport,
            mixed=mixed,
            lap_press=lap_press,
        ),
    )


def test_structured_workout_requires_exact_approved_time_and_nominal_duration() -> None:
    structure = StructuredWorkout.model_validate(
        {
            "sport": "run",
            "steps": [
                {
                    "kind": "steady",
                    "duration": {"unit": "seconds", "value": 60},
                    "intensity": "warmup",
                }
            ],
        }
    )
    common = {
        "id": "approval-integrity",
        "date": date(2026, 10, 25),
        "sport": "run",
        "workout_type": WorkoutType.EASY,
        "planned_duration_seconds": 60,
        "planned_distance_meters": 1000,
        "planned_low_intensity_duration_seconds": 60,
        "planned_moderate_intensity_duration_seconds": 0,
        "planned_high_intensity_duration_seconds": 0,
        "target_rpe_1_to_10": 2,
        "purpose": "Approval integrity",
        "structured_workout": structure,
    }

    with pytest.raises(ValidationError, match="start_time_local"):
        WorkoutPrescription(**common)
    with pytest.raises(ValidationError, match="nominal duration"):
        WorkoutPrescription(
            **{
                **common,
                "start_time_local": time(7),
                "planned_duration_seconds": 3600,
                "planned_low_intensity_duration_seconds": 3600,
            }
        )


class WorkoutPublicationService(ProductionWorkoutPublicationService):
    """Unit harness that isolates remote publication mechanics from approvals."""

    def __init__(self, repo, client):
        super().__init__(repo, client)
        self._approved_workouts = {}
        self._approved_plan_workout_ids = []

    def publish(self, workout):
        self._approved_workouts[workout.id] = self._authoritative(workout)
        return super().publish(workout.id)

    def publish_plan(self, workouts, *, from_date):
        self._approved_workouts.update(
            {workout.id: self._authoritative(workout) for workout in workouts}
        )
        self._approved_plan_workout_ids = [workout.id for workout in workouts]
        return super().publish_plan(from_date=from_date)

    def _load_approved_workout(self, workout_id):
        return self._approved_workouts[workout_id]

    def _load_approved_workouts(self):
        return [
            self._approved_workouts[workout_id] for workout_id in self._approved_plan_workout_ids
        ]

    @staticmethod
    def _authoritative(workout):
        return AuthoritativeWorkout(
            identity=PlanWorkoutIdentity(
                plan_id="plan_publication_test",
                macro_revision_id="macro_revision_1111111111111111",
                week_number=1,
                local_workout_id=workout.id,
            ),
            prescription=workout,
        )


class FakeClient:
    def __init__(
        self,
        *,
        wahoo: bool = False,
        threshold_speed_meters_per_second: float | None = 3.33,
        ftp: int | None = 250,
        garmin_upload_workouts: bool = True,
        garmin_filters: list[dict] | None = None,
        wahoo_upload_workouts: bool = True,
    ):
        self.athlete = AthleteDTO(
            id="athlete-1",
            timezone="Europe/Paris",
            icu_garmin_upload_workouts=garmin_upload_workouts,
            icu_garmin_upload_filters=garmin_filters or [],
            wahoo_upload_workouts=wahoo_upload_workouts,
        )
        self.connections = ConnectionsDTO(
            id="athlete-1",
            garmin_training_connected=True,
            wahoo_connected=wahoo,
        )
        self.settings = [
            SportSettingsDTO(
                id=1,
                types=["Run"],
                threshold_pace=threshold_speed_meters_per_second,
                pace_zones=[360, 330, 300],
                default_workout_time="07:00:00",
            ),
            SportSettingsDTO(
                id=2,
                types=["Ride"],
                ftp=ftp,
                default_workout_time="18:00:00",
            ),
        ]
        self.events: dict[int, EventDTO] = {}
        self.upserts = 0
        self.next_id = 100

    def get_athlete(self, _athlete_id=None):
        return self.athlete

    def get_connections(self, _athlete_id=None):
        return self.connections

    def get_sport_settings(self, _athlete_id=None):
        return self.settings

    def list_events(self, _oldest, _newest, *, athlete_id=None):
        return list(self.events.values())

    def get_event(self, event_id, *, athlete_id=None):
        if event_id not in self.events:
            raise IntervalsNotFoundError(
                "not found",
                operation="get_event",
                status_code=404,
            )
        return self.events[event_id]

    def upsert_event(self, event: EventWriteDTO, *, athlete_id=None):
        self.upserts += 1
        existing = next(
            (item for item in self.events.values() if item.uid == event.uid),
            None,
        )
        event_id = existing.id if existing else self.next_id
        self.next_id += 0 if existing else 1
        stored = EventDTO(id=event_id, **event.model_dump())
        self.events[event_id] = stored
        return stored

    def delete_event(self, event_id, *, athlete_id=None):
        del self.events[event_id]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return RepositoryIO()


def test_recursive_native_text_render_is_deterministic() -> None:
    first = render_structured_workout(_structure().steps)
    second = render_structured_workout(_structure().steps)

    assert first == second
    assert "3x" in first
    assert "1000mtr 4:10-4:20/km interval" in first
    assert first.endswith("\n")


def test_metric_distance_and_max_hr_use_unambiguous_intervals_tokens() -> None:
    structure = StructuredWorkout.model_validate(
        {
            "sport": "run",
            "steps": [
                {
                    "kind": "steady",
                    "duration": {
                        "unit": "meters",
                        "value": 5000,
                        "nominal_seconds": 1500,
                    },
                    "target": {
                        "mode": "heart_rate",
                        "unit": "percent_max_heart_rate",
                        "minimum": 65,
                        "maximum": 75,
                    },
                    "intensity": "active",
                }
            ],
        }
    )

    rendered = render_structured_workout(structure.steps)

    assert rendered == "- 5000mtr 65-75% HR active\n"
    assert "5000m " not in rendered
    assert "% max HR" not in rendered


def test_repeated_publication_is_remote_noop(repo) -> None:
    client = FakeClient()
    service = WorkoutPublicationService(repo, client)

    created = service.publish(_workout())
    repeated = service.publish(_workout())

    assert created.action == "created"
    assert repeated.action == "noop"
    assert client.upserts == 1
    assert len(client.events) == 1


def test_event_target_uses_intervals_enum(repo) -> None:
    client = FakeClient()

    result = WorkoutPublicationService(repo, client).publish(_workout())

    assert client.events[result.event_id].target == "PACE"


def test_publication_persists_provider_computed_readback(repo) -> None:
    class ComputedReadbackClient(FakeClient):
        def upsert_event(self, event: EventWriteDTO, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            stored = stored.model_copy(
                update={
                    "icu_training_load": 73.5,
                    "icu_intensity": 91.2,
                    "icu_ctl": 48.4,
                    "icu_atl": 55.1,
                }
            )
            self.events[stored.id] = stored
            return stored

    client = ComputedReadbackClient()

    WorkoutPublicationService(repo, client).publish(_workout())
    record = load_manifest(repo).workouts["workout-1"]

    assert record.provider_computed_aerobic_load_points == 73.5
    assert record.provider_relative_intensity_percent == 91.2
    assert record.provider_fitness_load_points == 48.4
    assert record.provider_fatigue_load_points == 55.1


def test_server_assigned_uid_is_persisted_and_reused(repo) -> None:
    class ServerUidClient(FakeClient):
        def upsert_event(self, event: EventWriteDTO, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.upserts == 1:
                stored = stored.model_copy(update={"uid": "server-assigned-uid"})
                self.events[stored.id] = stored
            return stored

    client = ServerUidClient()
    service = WorkoutPublicationService(repo, client)
    first = service.publish(_workout())
    changed = service.publish(_workout(occurrence=date(2026, 10, 26)))
    manifest = load_manifest(repo)

    assert first.uid == "server-assigned-uid"
    assert changed.uid == "server-assigned-uid"
    assert changed.event_id == first.event_id
    assert len(client.events) == 1
    assert manifest.workouts["workout-1"].requested_uid == uid_for("workout-1")
    assert manifest.workouts["workout-1"].uid == "server-assigned-uid"


def test_publication_manifest_rejects_cross_workout_identity_collisions(
    repo,
) -> None:
    client = FakeClient()
    service = WorkoutPublicationService(repo, client)
    service.publish(_workout(workout_id="first"))
    service.publish(_workout(workout_id="second"))
    payload = load_manifest(repo).model_dump(mode="json")
    payload["workouts"]["second"]["event_id"] = payload["workouts"]["first"]["event_id"]

    with pytest.raises(ValidationError, match="event IDs must be unique"):
        PublicationManifest.model_validate(payload)

    payload = load_manifest(repo).model_dump(mode="json")
    payload["workouts"]["second"]["uid"] = payload["workouts"]["first"]["uid"]
    with pytest.raises(
        ValidationError,
        match="ownership identities must be unique",
    ):
        PublicationManifest.model_validate(payload)

    mutated = load_manifest(repo)
    mutated.workouts["second"] = mutated.workouts["second"].model_copy(
        update={"event_id": mutated.workouts["first"].event_id}
    )
    with pytest.raises(ValidationError, match="event IDs must be unique"):
        save_manifest(repo, mutated)


def test_plan_publication_reconciles_future_workouts_and_reports_stale(
    repo,
) -> None:
    client = FakeClient()
    service = WorkoutPublicationService(repo, client)
    stale = service.publish(
        _workout(
            workout_id="stale-workout",
            occurrence=date(2026, 10, 24),
        )
    )
    active = _workout(
        workout_id="active-workout",
        occurrence=date(2026, 10, 26),
    )
    unstructured = WorkoutPrescription(
        id="unstructured-workout",
        date=date(2026, 10, 28),
        sport="run",
        workout_type=WorkoutType.EASY,
        planned_duration_seconds=2_700,
        planned_distance_meters=8_000,
        planned_low_intensity_duration_seconds=2_700,
        planned_moderate_intensity_duration_seconds=0,
        planned_high_intensity_duration_seconds=0,
        target_rpe_1_to_10=3,
        purpose="Build aerobic support.",
    )
    workouts = [unstructured, active]

    first = service.publish_plan(
        workouts,
        from_date=date(2026, 10, 25),
    )
    repeated = service.publish_plan(
        workouts,
        from_date=date(2026, 10, 25),
    )
    client.settings[0] = client.settings[0].model_copy(
        update={"threshold_speed_meters_per_second": 3.28}
    )
    settings_changed = service.publish_plan(
        workouts,
        from_date=date(2026, 10, 25),
    )

    assert first.workouts_considered == 2
    assert first.eligible_workouts == 1
    assert [item.status for item in first.items] == [
        "created",
        "skipped_unstructured",
    ]
    assert first.stale_manifest_workout_ids == ["stale-workout"]
    assert [item.status for item in repeated.items] == [
        "noop",
        "skipped_unstructured",
    ]
    assert settings_changed.items[0].status == "updated"
    assert stale.event_id in client.events
    assert len(client.events) == 2
    assert client.upserts == 3


def test_plan_publication_uses_canonical_local_start_time(repo) -> None:
    client = FakeClient()
    client.settings[0] = client.settings[0].model_copy(update={"default_workout_time": None})
    workout = _workout().model_copy(update={"start_time_local": time(6, 30)})

    report = WorkoutPublicationService(repo, client).publish_plan(
        [workout],
        from_date=workout.date,
    )

    assert not report.partial
    assert report.items[0].status == "created"
    event = next(iter(client.events.values()))
    assert event.start_date_local.endswith("06:30:00")


def test_plan_publication_reports_one_error_and_continues(repo) -> None:
    client = FakeClient(wahoo=True)
    report = WorkoutPublicationService(repo, client).publish_plan(
        [
            _workout(
                workout_id="unsupported-lap",
                occurrence=date(2026, 10, 25),
                lap_press=True,
            ),
            _workout(
                workout_id="valid-cycle",
                occurrence=date(2026, 10, 26),
                sport="cycle",
            ),
        ],
        from_date=date(2026, 10, 25),
    )

    assert report.partial
    assert report.eligible_workouts == 2
    assert [item.status for item in report.items] == ["error", "created"]
    assert report.items[0].error_type == "publication_safety"
    assert len(client.events) == 1


def test_cycling_power_workout_publishes_as_ride(repo) -> None:
    client = FakeClient(wahoo=True)
    result = WorkoutPublicationService(repo, client).publish(_workout(sport="cycle"))

    remote = client.events[result.event_id]
    assert remote.type == "Ride"
    assert remote.target == "POWER"
    assert remote.start_date_local.endswith("07:00:00")

    with pytest.raises(PublicationSafetyError, match="requires FTP"):
        WorkoutPublicationService(repo, FakeClient(ftp=None)).publish(
            _workout(workout_id="cycle-no-ftp", sport="cycle")
        )


def test_remote_drift_blocks_same_fingerprint_noop(repo) -> None:
    client = FakeClient()
    service = WorkoutPublicationService(repo, client)
    created = service.publish(_workout())
    client.events[created.event_id] = client.events[created.event_id].model_copy(
        update={"description": "changed outside Resilio"}
    )

    with pytest.raises(PublicationSafetyError, match="read-back"):
        service.publish(_workout())

    assert client.upserts == 1


def test_interrupted_read_back_recovers_from_durable_intent(repo) -> None:
    class InterruptedReadBackClient(FakeClient):
        fail_read_back = True

        def get_event(self, event_id, *, athlete_id=None):
            if self.fail_read_back and self.upserts:
                self.fail_read_back = False
                raise IntervalsTransportError(
                    "temporary read-back failure",
                    operation="get_event",
                )
            return super().get_event(event_id, athlete_id=athlete_id)

    client = InterruptedReadBackClient()
    service = WorkoutPublicationService(repo, client)

    with pytest.raises(IntervalsTransportError):
        service.publish(_workout())

    manifest = load_manifest(repo)
    assert "workout-1" in manifest.pending
    assert "workout-1" not in manifest.workouts

    recovered = service.publish(_workout())
    manifest = load_manifest(repo)

    assert recovered.action == "recovered"
    assert client.upserts == 1
    assert len(client.events) == 1
    assert "workout-1" not in manifest.pending
    assert manifest.workouts["workout-1"].event_id == recovered.event_id


def test_interrupted_update_before_remote_mutation_retries_safely(repo) -> None:
    class InterruptedUpsertClient(FakeClient):
        interrupt_next_upsert = False

        def upsert_event(self, event: EventWriteDTO, *, athlete_id=None):
            if self.interrupt_next_upsert:
                self.interrupt_next_upsert = False
                raise IntervalsTransportError(
                    "temporary upsert failure",
                    operation="upsert_event",
                )
            return super().upsert_event(event, athlete_id=athlete_id)

    client = InterruptedUpsertClient()
    service = WorkoutPublicationService(repo, client)
    created = service.publish(_workout())
    client.interrupt_next_upsert = True
    changed = _workout(occurrence=date(2026, 10, 26))

    with pytest.raises(IntervalsTransportError):
        service.publish(changed)

    updated = service.publish(changed)

    assert updated.action == "updated"
    assert updated.event_id == created.event_id
    assert client.upserts == 2
    assert len(client.events) == 1


def test_rejected_initial_intent_can_be_replaced_when_no_remote_exists(
    repo,
) -> None:
    class RejectingClient(FakeClient):
        reject_next_upsert = True

        def upsert_event(self, event: EventWriteDTO, *, athlete_id=None):
            if self.reject_next_upsert:
                self.reject_next_upsert = False
                raise IntervalsTransportError(
                    "rejected before remote mutation",
                    operation="upsert_event",
                    status_code=400,
                )
            return super().upsert_event(event, athlete_id=athlete_id)

    client = RejectingClient()
    service = WorkoutPublicationService(repo, client)

    with pytest.raises(IntervalsTransportError):
        service.publish(_workout())

    created = service.publish(_workout(occurrence=date(2026, 10, 26)))

    assert created.action == "created"
    assert len(client.events) == 1
    assert client.events[created.event_id].start_date_local.startswith("2026-10-26")


def test_owned_looking_remote_without_manifest_or_intent_is_rejected(repo) -> None:
    client = FakeClient()
    first = WorkoutPublicationService(repo, client).publish(_workout())
    repo.resolve_path("data/state/workout_publications.json").unlink()

    with pytest.raises(PublicationSafetyError, match="without a local manifest"):
        WorkoutPublicationService(repo, client).publish(_workout())

    assert client.upserts == 1
    assert first.event_id in client.events


def test_read_back_must_match_all_owned_rendered_fields(repo) -> None:
    class CorruptingClient(FakeClient):
        def upsert_event(self, event: EventWriteDTO, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            self.events[stored.id] = stored.model_copy(update={"category": "NOTE"})
            return self.events[stored.id]

    with pytest.raises(PublicationSafetyError, match="read-back"):
        WorkoutPublicationService(repo, CorruptingClient()).publish(_workout())


def test_reschedule_keeps_identity_and_updates_one_event(repo) -> None:
    client = FakeClient()
    service = WorkoutPublicationService(repo, client)
    first = service.publish(_workout())
    changed = service.publish(_workout(occurrence=date(2026, 10, 26)))

    assert changed.action == "updated"
    assert changed.uid == first.uid
    assert changed.external_id == first.external_id
    assert changed.event_id == first.event_id
    assert len(client.events) == 1
    assert client.events[first.event_id].start_date_local.startswith("2026-10-26")


def test_exact_owned_delete_and_unowned_rejection(repo) -> None:
    client = FakeClient()
    service = WorkoutPublicationService(repo, client)
    created = service.publish(_workout())
    client.events[created.event_id] = client.events[created.event_id].model_copy(
        update={"external_id": "somebody-else"}
    )

    with pytest.raises(PublicationSafetyError, match="ownership proof"):
        service.delete("workout-1")

    assert created.event_id in client.events


def test_interrupted_delete_verification_recovers_missing_owned_event(repo) -> None:
    class InterruptedDeleteClient(FakeClient):
        interrupt_verification = False

        def get_event(self, event_id, *, athlete_id=None):
            if self.interrupt_verification and event_id not in self.events:
                self.interrupt_verification = False
                raise IntervalsTransportError(
                    "temporary deletion verification failure",
                    operation="get_event",
                )
            return super().get_event(event_id, athlete_id=athlete_id)

    client = InterruptedDeleteClient()
    service = WorkoutPublicationService(repo, client)
    created = service.publish(_workout())
    client.interrupt_verification = True

    with pytest.raises(IntervalsTransportError):
        service.delete("workout-1")

    recovered = service.delete("workout-1")

    assert recovered.action == "recovered_deleted"
    assert recovered.event_id == created.event_id
    assert "workout-1" not in load_manifest(repo).workouts


def test_wahoo_mixed_targets_and_missing_pace_settings_fail_closed(repo) -> None:
    with pytest.raises(PublicationSafetyError, match="Mixed target"):
        WorkoutPublicationService(repo, FakeClient(wahoo=True)).publish(_workout(mixed=True))

    with pytest.raises(PublicationSafetyError, match="threshold pace"):
        WorkoutPublicationService(
            repo,
            FakeClient(threshold_speed_meters_per_second=None),
        ).publish(_workout())

    with pytest.raises(PublicationSafetyError, match="Lap-button"):
        WorkoutPublicationService(repo, FakeClient(wahoo=True)).publish(_workout(lap_press=True))


def test_device_forwarding_settings_fail_closed(repo) -> None:
    with pytest.raises(PublicationSafetyError, match="Garmin.*not enabled"):
        WorkoutPublicationService(
            repo,
            FakeClient(garmin_upload_workouts=False),
        ).publish(_workout())

    with pytest.raises(PublicationSafetyError, match="filters do not admit Run"):
        WorkoutPublicationService(
            repo,
            FakeClient(
                garmin_filters=[
                    {
                        "field_id": "type",
                        "operator": "=",
                        "value": {"value": "Ride"},
                    }
                ]
            ),
        ).publish(_workout())

    allowed = FakeClient(
        garmin_filters=[
            {
                "field_id": "type",
                "operator": "=",
                "value": {"value": "Run"},
            }
        ]
    )
    assert WorkoutPublicationService(repo, allowed).publish(_workout()).action == "created"

    with pytest.raises(PublicationSafetyError, match="Wahoo.*not enabled"):
        WorkoutPublicationService(
            repo,
            FakeClient(wahoo=True, wahoo_upload_workouts=False),
        ).publish(_workout())


@pytest.mark.parametrize(
    ("occurrence", "local_time", "message"),
    [
        (date(2026, 3, 29), time(2, 30), "does not exist"),
        (date(2026, 10, 25), time(2, 30), "ambiguous"),
    ],
)
def test_dst_transition_wall_times_fail_closed(
    repo,
    occurrence: date,
    local_time: time,
    message: str,
) -> None:
    with pytest.raises(PublicationSafetyError, match=message):
        WorkoutPublicationService(repo, FakeClient()).publish(
            _workout(occurrence=occurrence).model_copy(update={"start_time_local": local_time}),
        )
