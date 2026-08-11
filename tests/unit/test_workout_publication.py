"""Structured rendering and ownership-safe publication tests."""

import re
from datetime import date, datetime, time, timezone

import pytest
from pydantic import ValidationError

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import (
    load_manifest,
    save_manifest,
)
from resilio.core.workout_publication.naming import (
    MAX_PROVIDER_WORKOUT_NAME_CHARACTERS,
    provider_workout_name,
    provider_workout_names,
)
from resilio.core.workout_publication.renderer import render_structured_workout
from resilio.core.workout_publication.semantics import (
    WorkoutSemanticsError,
    assert_workout_semantics_match,
    expected_workout_semantics,
)
from resilio.core.workout_publication.service import (
    PublicationSafetyError,
    uid_for,
)
from resilio.core.workout_publication.service import (
    WorkoutPublicationService as ProductionWorkoutPublicationService,
)
from resilio.integrations.intervals_icu.dto import (
    ActivityDTO,
    AthleteDTO,
    ConnectionsDTO,
    EventDTO,
    EventWriteDTO,
    SportSettingsDTO,
    WorkoutDocumentDTO,
)
from resilio.integrations.intervals_icu.errors import (
    IntervalsNotFoundError,
    IntervalsTransportError,
)
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.workouts import RunningWorkoutPrescription, WorkoutType
from resilio.schemas.publication import PublicationManifest
from resilio.schemas.structured_workout import StructuredWorkout


def _structure(
    *,
    mixed: bool = False,
    lap_press: bool = False,
) -> StructuredWorkout:
    steps = [
        {
            "kind": "steady",
            "duration": {"unit": "seconds", "value": 600},
            "target": {
                "mode": "pace",
                "unit": "seconds_per_kilometer",
                "minimum": 300,
                "maximum": 330,
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
                        "mode": "pace",
                        "unit": "seconds_per_kilometer",
                        "minimum": 250,
                        "maximum": 260,
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
    return StructuredWorkout.model_validate({"sport": "run", "steps": steps})


def _workout(
    *,
    workout_id: str = "workout-1",
    occurrence: date = date(2026, 10, 25),
    mixed: bool = False,
    lap_press: bool = False,
) -> RunningWorkoutPrescription:
    return RunningWorkoutPrescription(
        id=workout_id,
        date=occurrence,
        start_time_local=time(7),
        workout_type=WorkoutType.INTERVALS,
        planned_duration_seconds=1_725,
        planned_distance_meters=9_000,
        planned_low_intensity_duration_seconds=960,
        planned_moderate_intensity_duration_seconds=0,
        planned_high_intensity_duration_seconds=765,
        target_rpe_1_to_10=8,
        purpose="Three controlled repetitions",
        structured_workout=_structure(mixed=mixed, lap_press=lap_press),
    )


def _targetless_workout(
    *,
    workout_id: str = "targetless",
    planned_distance_meters: float = 1_500,
) -> RunningWorkoutPrescription:
    return RunningWorkoutPrescription.model_validate(
        {
            "id": workout_id,
            "date": date(2026, 10, 25),
            "sport": "run",
            "workout_type": "easy",
            "planned_duration_seconds": 600,
            "planned_distance_meters": planned_distance_meters,
            "planned_low_intensity_duration_seconds": 600,
            "planned_moderate_intensity_duration_seconds": 0,
            "planned_high_intensity_duration_seconds": 0,
            "target_rpe_1_to_10": 3,
            "purpose": "Easy conversational running.",
            "structured_workout": {
                "sport": "run",
                "steps": [
                    {
                        "kind": "steady",
                        "duration": {"unit": "seconds", "value": 600},
                        "intensity": "active",
                    }
                ],
            },
        }
    )


def test_structured_workout_allows_date_only_approval_and_requires_nominal_duration() -> None:
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

    date_only = RunningWorkoutPrescription(**common)
    assert date_only.start_time_local is None
    with pytest.raises(ValidationError, match="nominal duration"):
        RunningWorkoutPrescription(
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

    def publish(self, workout):
        self._approved_workouts[workout.id] = self._authoritative(workout)
        return super().publish(workout.id)

    def _load_approved_workout(self, workout_id):
        return self._approved_workouts[workout_id]

    @staticmethod
    def _authoritative(workout):
        return AuthoritativeWorkout(
            identity=PlanWorkoutIdentity(
                plan_id="plan_publication_test",
                plan_revision_id="plan_revision_1111111111111111",
                week_number=1,
                local_workout_id=workout.id,
            ),
            prescription=workout,
            applied_week_approval_id="week_approval_0123456789abcdef",
            applied_running_workouts_sha256="1" * 64,
            schedule_timezone="Europe/Paris",
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
        self.activities: dict[str, ActivityDTO] = {}
        self.activity_pairing_updates: list[tuple[str, int | None]] = []
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
        stored = EventDTO(
            id=event_id,
            workout_doc={"steps": _parse_fake_workout_steps(event.description)},
            **event.model_dump(),
        )
        self.events[event_id] = stored
        return stored

    def delete_event(self, event_id, *, athlete_id=None):
        del self.events[event_id]

    def get_activity(self, activity_id, *, intervals=True):
        return self.activities.setdefault(
            activity_id,
            ActivityDTO(
                id=activity_id,
                type="Run",
                name="Completed run",
                start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
                start_date_local=datetime(2026, 8, 10, 7),
                elapsed_time=1800,
                moving_time=1800,
                source="GARMIN_CONNECT",
            ),
        )

    def update_activity_pairing(self, activity_id, pairing):
        self.activity_pairing_updates.append((activity_id, pairing.paired_event_id))
        updated = self.get_activity(activity_id).model_copy(
            update={"paired_event_id": pairing.paired_event_id}
        )
        self.activities[activity_id] = updated
        return updated


def _parse_fake_workout_steps(description: str) -> list[dict[str, object]]:
    """Independent narrow fake of the Intervals text parser used by unit tests."""
    roots: list[dict[str, object]] = []
    stack: list[tuple[int, list[dict[str, object]]]] = [(-1, roots)]
    for raw_line in description.splitlines():
        stripped = raw_line.strip()
        indentation = len(raw_line) - len(raw_line.lstrip())
        repeat_match = re.fullmatch(r".+\s(\d+)x", stripped)
        if repeat_match:
            while stack[-1][0] >= indentation:
                stack.pop()
            nested: list[dict[str, object]] = []
            block: dict[str, object] = {
                "reps": int(repeat_match.group(1)),
                "steps": nested,
            }
            stack[-1][1].append(block)
            stack.append((indentation, nested))
            continue
        if not stripped.startswith("- "):
            continue
        while stack[-1][0] >= indentation:
            stack.pop()
        stack[-1][1].append(_parse_fake_step(stripped[2:]))
    return roots


def _parse_fake_step(payload: str) -> dict[str, object]:
    tokens = payload.split()
    termination_index = next(
        index
        for index, token in enumerate(tokens)
        if re.fullmatch(r"\d+(?:\.\d+)?mtr|\d+[ms]", token)
    )
    result: dict[str, object] = {}
    if termination_index:
        result["text"] = " ".join(tokens[:termination_index])
    termination = tokens[termination_index]
    if termination.endswith("mtr"):
        result["distance"] = float(termination[:-3])
    elif termination.endswith("m"):
        result["duration"] = float(termination[:-1]) * 60
    else:
        result["duration"] = float(termination[:-1])
    remaining_tokens = tokens[termination_index + 1 :]
    for token_index, token in enumerate(
        remaining_tokens,
        start=termination_index + 1,
    ):
        if token.startswith("intensity="):
            result["intensity"] = token.removeprefix("intensity=")
        elif pace_match := re.fullmatch(
            r"(\d+):(\d{2})-(\d+):(\d{2})/km",
            token,
        ):
            first = int(pace_match.group(1)) * 60 + int(pace_match.group(2))
            second = int(pace_match.group(3)) * 60 + int(pace_match.group(4))
            result["pace"] = {
                "start": first,
                "end": second,
                "units": "secs/km",
            }
        elif token.lower() == "bpm" and token_index:
            bounds = tokens[token_index - 1].split("-")
            result["hr"] = {
                "start": float(bounds[0]),
                "end": float(bounds[-1]),
                "units": "bpm",
            }
        elif token == "HR" and token_index:
            bounds = tokens[token_index - 1].removesuffix("%").split("-")
            result["hr"] = {
                "start": float(bounds[0]),
                "end": float(bounds[-1]),
                "units": "%hr",
            }
    return result


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return RepositoryIO()


def test_recursive_native_text_render_is_deterministic() -> None:
    first = render_structured_workout(_structure().steps)
    second = render_structured_workout(_structure().steps)

    assert first == second
    assert "Repeat 3x" in first
    assert ("- Smooth and controlled 1000mtr 4:10-4:20/km " "intensity=interval") in first
    assert "- 10m 5:00-5:30/km intensity=warmup" in first
    assert first.endswith("\n")


def test_provider_names_are_date_independent_and_reuse_identical_structures() -> None:
    first = _targetless_workout(workout_id="a", planned_distance_meters=4_000)
    moved = _targetless_workout(
        workout_id="b",
        planned_distance_meters=4_000,
    ).model_copy(update={"date": date(2026, 11, 1)})

    names = provider_workout_names([moved, first])

    assert provider_workout_name(first) == "Easy4K"
    assert provider_workout_name(moved) == "Easy4K"
    assert names == {"a": "Easy4K", "b": "Easy4K"}
    assert all(len(name) <= MAX_PROVIDER_WORKOUT_NAME_CHARACTERS for name in names.values())


def test_provider_name_describes_the_primary_repeat_structure() -> None:
    workout = RunningWorkoutPrescription.model_validate(
        {
            "id": "tempo-2x7",
            "date": date(2026, 10, 25),
            "sport": "run",
            "workout_type": "tempo",
            "planned_duration_seconds": 1_680,
            "planned_distance_meters": 5_000,
            "planned_low_intensity_duration_seconds": 760,
            "planned_moderate_intensity_duration_seconds": 0,
            "planned_high_intensity_duration_seconds": 920,
            "target_rpe_1_to_10": 7,
            "purpose": "Two controlled seven-minute tempo repetitions.",
            "structured_workout": {
                "sport": "run",
                "steps": [
                    {
                        "kind": "steady",
                        "duration": {"unit": "seconds", "value": 180},
                        "intensity": "warmup",
                    },
                    {
                        "kind": "repeat",
                        "repetitions": 4,
                        "steps": [
                            {
                                "kind": "steady",
                                "duration": {"unit": "seconds", "value": 20},
                                "intensity": "active",
                            },
                            {
                                "kind": "steady",
                                "duration": {"unit": "seconds", "value": 40},
                                "intensity": "recovery",
                            },
                        ],
                    },
                    {
                        "kind": "repeat",
                        "repetitions": 2,
                        "steps": [
                            {
                                "kind": "steady",
                                "duration": {"unit": "seconds", "value": 420},
                                "intensity": "interval",
                            },
                            {
                                "kind": "steady",
                                "duration": {"unit": "seconds", "value": 120},
                                "intensity": "recovery",
                            },
                        ],
                    },
                    {
                        "kind": "steady",
                        "duration": {"unit": "seconds", "value": 180},
                        "intensity": "cooldown",
                    },
                ],
            },
        }
    )

    assert provider_workout_name(workout) == "Tempo2x7m"


def test_provider_name_uses_the_complete_interval_label() -> None:
    assert provider_workout_name(_workout()) == "Interval3x1K"


def test_provider_name_describes_a_timed_distance_benchmark() -> None:
    workout = RunningWorkoutPrescription.model_validate(
        {
            "id": "benchmark-5k",
            "date": date(2026, 10, 25),
            "sport": "run",
            "workout_type": "benchmark",
            "planned_duration_seconds": 1_500,
            "planned_distance_meters": 5_000,
            "planned_low_intensity_duration_seconds": 0,
            "planned_moderate_intensity_duration_seconds": 0,
            "planned_high_intensity_duration_seconds": 1_500,
            "target_rpe_1_to_10": 9,
            "purpose": "Establish a current five-kilometre baseline.",
            "structured_workout": {
                "sport": "run",
                "steps": [
                    {
                        "kind": "timed_distance",
                        "distance_meters": 5_000,
                        "nominal_seconds": 1_500,
                    }
                ],
            },
        }
    )

    assert provider_workout_name(workout) == "5KTest"


def test_provider_names_disambiguate_different_structures_with_same_summary() -> None:
    first = _targetless_workout(workout_id="a")
    payload = _targetless_workout(workout_id="b").model_dump(mode="json")
    payload["structured_workout"]["steps"] = [
        {
            "kind": "steady",
            "duration": {"unit": "seconds", "value": 300},
            "intensity": "warmup",
        },
        {
            "kind": "steady",
            "duration": {"unit": "seconds", "value": 300},
            "intensity": "active",
        },
    ]
    second = RunningWorkoutPrescription.model_validate(payload)

    names = provider_workout_names([second, first])

    assert set(names.values()) == {"Easy1.5K-1", "Easy1.5K-2"}


def test_distance_semantics_ignore_provider_estimated_duration() -> None:
    structure = StructuredWorkout.model_validate(
        {
            "sport": "run",
            "steps": [
                {
                    "kind": "steady",
                    "duration": {
                        "unit": "meters",
                        "value": 500,
                        "nominal_seconds": 300,
                    },
                    "intensity": "warmup",
                    "cue": "Easy warm-up",
                }
            ],
        }
    )
    provider_document = WorkoutDocumentDTO.model_validate(
        {
            "steps": [
                {
                    "distance": 500,
                    "duration": 180,
                    "intensity": "warmup",
                    "text": "Easy warm-up",
                }
            ]
        }
    )

    assert_workout_semantics_match(
        expected_workout_semantics(structure.steps),
        provider_document,
    )


def test_ramp_syntax_and_direction_match_provider_semantics() -> None:
    structure = StructuredWorkout.model_validate(
        {
            "sport": "run",
            "steps": [
                {
                    "kind": "ramp",
                    "duration": {"unit": "seconds", "value": 300},
                    "start_target": {
                        "mode": "pace",
                        "unit": "seconds_per_kilometer",
                        "minimum": 330,
                        "maximum": 330,
                    },
                    "end_target": {
                        "mode": "pace",
                        "unit": "seconds_per_kilometer",
                        "minimum": 270,
                        "maximum": 270,
                    },
                    "intensity": "active",
                    "cue": "Build",
                }
            ],
        }
    )
    document = WorkoutDocumentDTO.model_validate(
        {
            "steps": [
                {
                    "duration": 300,
                    "ramp": True,
                    "intensity": "active",
                    "text": "Build",
                    "pace": {
                        "start": 330,
                        "end": 270,
                        "units": "secs/km",
                    },
                }
            ]
        }
    )

    assert (
        render_structured_workout(structure.steps)
        == "- Build 5m ramp 5:30-4:30/km intensity=active\n"
    )
    assert_workout_semantics_match(
        expected_workout_semantics(structure.steps),
        document,
    )


def test_lap_press_semantics_require_provider_confirmation() -> None:
    structure = StructuredWorkout.model_validate(
        {
            "sport": "run",
            "steps": [
                {
                    "kind": "steady",
                    "duration": {
                        "unit": "until_lap_press",
                        "nominal_seconds": 120,
                    },
                    "intensity": "recovery",
                }
            ],
        }
    )
    missing_lap_flag = WorkoutDocumentDTO.model_validate(
        {"steps": [{"duration": 120, "intensity": "recovery"}]}
    )
    confirmed_lap_flag = WorkoutDocumentDTO.model_validate(
        {
            "steps": [
                {
                    "duration": 120,
                    "press_lap": True,
                    "intensity": "recovery",
                }
            ]
        }
    )

    expected = expected_workout_semantics(structure.steps)
    with pytest.raises(WorkoutSemanticsError, match="step 1"):
        assert_workout_semantics_match(expected, missing_lap_flag)
    assert_workout_semantics_match(expected, confirmed_lap_flag)


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

    assert rendered == "- 5000mtr 65-75% HR intensity=active\n"
    assert "5000m " not in rendered
    assert "% max HR" not in rendered


@pytest.mark.parametrize(
    ("target_unit", "settings_update", "expected_message"),
    [
        ("percent_lthr", {"lthr": None}, "lactate-threshold heart rate"),
        ("percent_max_heart_rate", {"max_hr": None}, "maximum heart rate"),
    ],
)
def test_relative_heart_rate_targets_require_their_exact_reference_setting(
    repo,
    target_unit,
    settings_update,
    expected_message,
) -> None:
    client = FakeClient()
    client.settings[0] = client.settings[0].model_copy(
        update={"lthr": 176, "max_hr": 195, **settings_update}
    )
    structure = StructuredWorkout.model_validate(
        {
            "sport": "run",
            "steps": [
                {
                    "kind": "steady",
                    "duration": {"unit": "seconds", "value": 600},
                    "target": {
                        "mode": "heart_rate",
                        "unit": target_unit,
                        "minimum": 80,
                        "maximum": 90,
                    },
                    "intensity": "active",
                }
            ],
        }
    )
    workout = _workout().model_copy(
        update={
            "planned_duration_seconds": 600,
            "planned_low_intensity_duration_seconds": 600,
            "planned_high_intensity_duration_seconds": 0,
            "structured_workout": structure,
        }
    )

    with pytest.raises(PublicationSafetyError, match=expected_message):
        WorkoutPublicationService(repo, client).publish(workout)


def test_absolute_heart_rate_target_does_not_require_threshold_settings(repo) -> None:
    client = FakeClient()
    client.settings[0] = client.settings[0].model_copy(
        update={"lthr": None, "max_hr": None, "hr_zones": []}
    )
    structure = StructuredWorkout.model_validate(
        {
            "sport": "run",
            "steps": [
                {
                    "kind": "steady",
                    "duration": {"unit": "seconds", "value": 600},
                    "target": {
                        "mode": "heart_rate",
                        "unit": "beats_per_minute",
                        "minimum": 120,
                        "maximum": 140,
                    },
                    "intensity": "active",
                }
            ],
        }
    )
    workout = _workout().model_copy(
        update={
            "planned_duration_seconds": 600,
            "planned_distance_meters": 1_500,
            "planned_low_intensity_duration_seconds": 600,
            "planned_high_intensity_duration_seconds": 0,
            "structured_workout": structure,
        }
    )

    assert WorkoutPublicationService(repo, client).publish(workout).action == "created"


def test_repeated_publication_is_remote_noop(repo) -> None:
    client = FakeClient()
    service = WorkoutPublicationService(repo, client)

    created = service.publish(_workout())
    repeated = service.publish(_workout())

    assert created.action == "created"
    assert repeated.action == "noop"
    assert client.upserts == 1
    assert len(client.events) == 1


def test_targetless_workout_ignores_unrelated_pace_setting_changes(repo) -> None:
    client = FakeClient()
    service = WorkoutPublicationService(repo, client)
    service.publish(_targetless_workout())
    client.settings[0] = client.settings[0].model_copy(
        update={
            "threshold_speed_meters_per_second": 4.0,
            "pace_zones": [400, 360, 320],
        }
    )

    repeated = service.publish(_targetless_workout())

    assert repeated.action == "noop"
    assert client.upserts == 1


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


def test_run_only_publication_manifest_uses_schema_version_seven() -> None:
    assert PublicationManifest().schema_version == 8
    with pytest.raises(ValidationError):
        PublicationManifest.model_validate({"schema_version": 6})


def test_publication_uses_exact_approved_local_start_time(repo) -> None:
    client = FakeClient()
    client.settings[0] = client.settings[0].model_copy(update={"default_workout_time": None})
    workout = _workout().model_copy(update={"start_time_local": time(6, 30)})

    result = WorkoutPublicationService(repo, client).publish(workout)

    assert result.action == "created"
    event = client.events[result.event_id]
    assert event.start_date_local.endswith("06:30:00")


def test_date_only_publication_uses_provider_midnight_and_preserves_approval(repo) -> None:
    client = FakeClient()
    workout = _workout().model_copy(update={"start_time_local": None})

    result = WorkoutPublicationService(repo, client).publish(workout)
    record = load_manifest(repo).workouts[workout.id]

    assert client.events[result.event_id].start_date_local == "2026-10-25T00:00:00"
    assert record.approved_start_time_local is None
    assert record.provider_start_date_local == "2026-10-25T00:00:00"


def test_remote_drift_blocks_same_fingerprint_noop(repo) -> None:
    client = FakeClient()
    service = WorkoutPublicationService(repo, client)
    created = service.publish(_workout())
    client.events[created.event_id] = client.events[created.event_id].model_copy(
        update={"description": "changed outside Resilio"}
    )

    with pytest.raises(PublicationSafetyError, match="changed since Resilio verified"):
        service.publish(_workout())

    assert client.upserts == 1


def test_remote_drift_blocks_an_otherwise_valid_local_update(repo) -> None:
    client = FakeClient()
    service = WorkoutPublicationService(repo, client)
    created = service.publish(_workout())
    client.events[created.event_id] = client.events[created.event_id].model_copy(
        update={"description": "changed outside Resilio"}
    )

    with pytest.raises(PublicationSafetyError, match="changed since Resilio verified"):
        service.publish(_workout(occurrence=date(2026, 10, 26)))

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


def test_read_back_requires_a_semantically_complete_parsed_workout_document(repo) -> None:
    class UnparsedWorkoutClient(FakeClient):
        def upsert_event(self, event: EventWriteDTO, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            self.events[stored.id] = EventDTO.model_validate(
                {
                    **stored.model_dump(mode="json", exclude={"workout_doc"}),
                    "workout_doc": {"steps": [{"duration": 600}]},
                }
            )
            return self.events[stored.id]

    with pytest.raises(PublicationSafetyError, match="semantics"):
        WorkoutPublicationService(repo, UnparsedWorkoutClient()).publish(_workout())


def test_provider_push_errors_are_persisted_and_reported(repo) -> None:
    class PushErrorClient(FakeClient):
        def upsert_event(self, event: EventWriteDTO, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            self.events[stored.id] = EventDTO(
                **stored.model_dump(exclude={"push_errors"}),
                push_errors=[
                    {
                        "service": "GARMIN",
                        "message": "Provider rejected the workout",
                        "date": datetime(2026, 10, 25, 6, tzinfo=timezone.utc),
                    }
                ],
            )
            return self.events[stored.id]

    result = WorkoutPublicationService(repo, PushErrorClient()).publish(_workout())
    record = load_manifest(repo).workouts["workout-1"]

    assert result.garmin_forwarding_status == "provider_error_observed"
    assert result.provider_push_errors[0].service == "GARMIN"
    assert record.provider_push_errors == result.provider_push_errors


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


def test_owned_delete_rejects_remote_content_drift(repo) -> None:
    client = FakeClient()
    service = WorkoutPublicationService(repo, client)
    created = service.publish(_workout())
    client.events[created.event_id] = client.events[created.event_id].model_copy(
        update={"description": "Athlete edited this event in Intervals.icu"}
    )

    with pytest.raises(PublicationSafetyError, match="changed since Resilio"):
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


def test_target_settings_fail_closed_without_applying_wahoo_constraints(repo) -> None:
    with pytest.raises(PublicationSafetyError, match="threshold pace"):
        WorkoutPublicationService(
            repo,
            FakeClient(threshold_speed_meters_per_second=None),
        ).publish(_workout())

    assert (
        WorkoutPublicationService(repo, FakeClient(wahoo=True)).publish(_workout()).action
        == "created"
    )


def test_mixed_step_target_modes_are_rejected_before_remote_mutation(repo) -> None:
    client = FakeClient()

    with pytest.raises(PublicationSafetyError, match="at most one target mode"):
        WorkoutPublicationService(repo, client).publish(_workout(mixed=True))

    assert client.upserts == 0


def test_wahoo_state_does_not_block_garmin_focused_run_publication(repo) -> None:
    client = FakeClient(wahoo=True, wahoo_upload_workouts=False)

    result = WorkoutPublicationService(repo, client).publish(_workout())

    assert result.action == "created"
    assert result.garmin_forwarding_status == "eligible_unverified"


def test_device_forwarding_settings_are_reported_separately(repo) -> None:
    client = FakeClient(garmin_upload_workouts=False)
    disabled = WorkoutPublicationService(
        repo,
        client,
    ).publish(_workout())
    assert disabled.garmin_forwarding_status == "not_configured"

    client.athlete = AthleteDTO(
        id="athlete-1",
        timezone="Europe/Paris",
        icu_garmin_upload_workouts=True,
        icu_garmin_upload_filters=[
            {
                "field_id": "type",
                "operator": "=",
                "value": {"value": "Ride"},
            }
        ],
    )
    filtered = WorkoutPublicationService(
        repo,
        client,
    ).publish(_workout(workout_id="filtered"))
    assert filtered.garmin_forwarding_status == "not_configured"

    client.athlete = AthleteDTO(
        id="athlete-1",
        timezone="Europe/Paris",
        icu_garmin_upload_workouts=True,
        icu_garmin_upload_filters=[
            {
                "field_id": "type",
                "operator": "=",
                "value": {"value": "Run"},
            }
        ],
    )
    assert (
        WorkoutPublicationService(repo, client)
        .publish(_workout(workout_id="allowed"))
        .garmin_forwarding_status
        == "eligible_unverified"
    )

    client.connections = client.connections.model_copy(update={"wahoo_connected": True})
    client.athlete = client.athlete.model_copy(update={"wahoo_upload_workouts": False})
    wahoo_disabled = WorkoutPublicationService(
        repo,
        client,
    ).publish(_workout(workout_id="wahoo-disabled"))
    assert wahoo_disabled.garmin_forwarding_status == "eligible_unverified"


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
