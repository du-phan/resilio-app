"""Historical bouldering mapping, selection, ownership, and recovery tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.reconciliation import reconcile_activity
from resilio.core.historical_activity_backfill.errors import (
    HistoricalActivityBackfillError,
)
from resilio.core.historical_activity_backfill.inventory import (
    HistoricalInventoryError,
    analyze_inventory,
)
from resilio.core.historical_activity_backfill.rendering import (
    NOON_DISCLOSURE,
    HistoricalActivityRenderingError,
    assert_remote_matches,
    render_manual_activity,
)
from resilio.core.historical_activity_backfill.repository import (
    load_ledger,
    verify_backup,
)
from resilio.core.historical_activity_backfill.service import (
    HistoricalActivityBackfillService,
)
from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import read_sync_state
from resilio.integrations.intervals_icu.activity_mapper import map_activity
from resilio.integrations.intervals_icu.dto import (
    ActivityDTO,
    AthleteDTO,
    HiddenActivityDTO,
    ManualActivityWriteDTO,
)
from resilio.integrations.intervals_icu.errors import (
    IntervalsNotFoundError,
    IntervalsTransportError,
)
from resilio.schemas.activity import (
    ActivityNotes,
    ActivityOccurrence,
    ActivityOrigin,
    ActivityOriginKind,
    PerceivedEffort,
    PerceivedEffortSource,
    RecordingProvider,
)
from resilio.schemas.config import Config, IntervalsIcuSettings, Settings
from resilio.schemas.historical_backfill import (
    ApprovalStage,
    FrozenBackfillBaseline,
    PublicationStatus,
)
from tests.factories import make_activity


def _historical_climb(
    activity_id: str,
    activity_date: date,
    *,
    hour: int | None,
    description: str | None = None,
    rpe: int | None = None,
):
    start = datetime(
        activity_date.year,
        activity_date.month,
        activity_date.day,
        hour or 7,
        30,
        tzinfo=timezone.utc,
    )
    activity = make_activity(
        id=activity_id,
        date=activity_date,
        sport="climb",
        start_time=start,
        duration_seconds=3600,
        moving_seconds=3600,
        name=f"Bouldering {activity_id}",
        description=description,
        perceived_effort=(
            PerceivedEffort(
                value=rpe,
                source=PerceivedEffortSource.ATHLETE,
            )
            if rpe is not None
            else None
        ),
    )
    occurrence = (
        ActivityOccurrence(
            local_date=activity_date,
            start_time_utc=None,
            start_time_local=None,
            timezone=None,
        )
        if hour is None
        else ActivityOccurrence(
            local_date=activity_date,
            start_time_utc=start,
            start_time_local=start,
            timezone=None,
        )
    )
    return activity.model_copy(
        update={
            "source_sport_type": "RockClimbing",
            "occurrence": occurrence,
            "origin": ActivityOrigin(
                kind=ActivityOriginKind.HISTORICAL_IMPORT,
                recording_provider=(
                    RecordingProvider.MANUAL
                    if hour is None
                    else RecordingProvider.UNKNOWN
                ),
            ),
        }
    )


def test_exact_wall_time_is_reinterpreted_in_paris_and_private_facts_stay_local():
    activity = _historical_climb(
        "act_h_exact",
        date(2026, 1, 15),
        hour=19,
        description="Public",
        rpe=7,
    ).model_copy(
        update={
            "notes": ActivityNotes(
                description="Public",
                private_note="Never upload this",
            ),
        }
    )

    rendered = render_manual_activity(activity)
    payload = rendered.payload.model_dump(mode="json", exclude_none=True)

    assert payload["type"] == "RockClimbing"
    assert payload["start_date_local"] == "2026-01-15T19:30:00"
    assert payload["start_date"] == "2026-01-15T18:30:00Z"
    assert payload["icu_rpe"] == 7
    assert payload["description"] == "Public"
    assert "private_note" not in payload
    assert "calculated_load" not in payload
    assert "segments" not in payload
    assert "device" not in payload


def test_date_only_activity_uses_local_noon_and_discloses_synthetic_time():
    activity = _historical_climb(
        "act_h_noon",
        date(2026, 7, 15),
        hour=None,
    )

    rendered = render_manual_activity(activity)

    assert rendered.payload.start_date_local.isoformat() == (
        "2026-07-15T12:00:00+02:00"
    )
    assert rendered.payload.start_date.isoformat() == (
        "2026-07-15T10:00:00+00:00"
    )
    assert rendered.payload.description == NOON_DISCLOSURE
    assert rendered.payload.icu_rpe is None


def test_remote_mismatch_reports_only_sanitized_field_names():
    activity = _historical_climb(
        "act_h_diagnostic",
        date(2026, 1, 15),
        hour=19,
        description="Approved public description",
        rpe=7,
    )
    expected = render_manual_activity(activity).payload
    remote = ActivityDTO(
        id="remote-diagnostic",
        external_id=expected.external_id,
        type=expected.type,
        name=expected.name,
        start_date=expected.start_date,
        start_date_local=expected.start_date_local,
        timezone=expected.timezone,
        elapsed_time=expected.elapsed_time,
        moving_time=0,
        description="remote-private-value-must-not-appear",
        icu_rpe=expected.icu_rpe,
    )

    with pytest.raises(
        HistoricalActivityRenderingError,
        match=r"approved fields: description, moving_time$",
    ) as captured:
        assert_remote_matches(remote, expected)

    assert "remote-private-value" not in str(captured.value)
    assert "Approved public description" not in str(captured.value)


@pytest.mark.parametrize(
    "stored",
    [
        datetime(2026, 3, 29, 2, 30, tzinfo=timezone.utc),
        datetime(2026, 10, 25, 2, 30, tzinfo=timezone.utc),
    ],
)
def test_nonexistent_or_ambiguous_paris_wall_time_fails_closed(stored):
    activity = _historical_climb(
        "act_h_dst",
        stored.date(),
        hour=stored.hour,
    )
    activity = activity.model_copy(
        update={
            "occurrence": ActivityOccurrence(
                local_date=stored.date(),
                start_time_utc=stored,
                start_time_local=stored,
                timezone=None,
            )
        }
    )

    with pytest.raises(HistoricalActivityRenderingError, match="daylight-saving"):
        render_manual_activity(activity)


def test_hidden_exclusion_requires_one_to_one_across_all_sports():
    climb = _historical_climb(
        "act_h_climb",
        date(2026, 1, 10),
        hour=18,
        description="Public",
        rpe=6,
    )
    other = make_activity(
        id="act_h_run",
        date=date(2026, 1, 10),
        sport="run",
        start_time=datetime(2026, 1, 10, 18, 30, 30, tzinfo=timezone.utc),
    )
    hidden = HiddenActivityDTO(
        id="hidden-sensitive",
        start_date_local="2026-01-10T18:30:00+01:00",
        _note="hidden",
    )
    baseline = FrozenBackfillBaseline(
        selected=1,
        hidden_excluded=1,
        publishable=0,
        exact_time=1,
        noon_adjusted=0,
    )

    with pytest.raises(HistoricalInventoryError, match="conflicts=1"):
        analyze_inventory(
            selected=[climb],
            all_records=[climb, other],
            rows=[hidden],
            baseline=baseline,
        )


def test_frozen_433_29_404_accounting_and_timestamp_coverage():
    start = date(2022, 1, 1)
    selected = []
    hidden = []
    for index in range(433):
        activity_date = start + timedelta(days=index)
        activity = _historical_climb(
            f"act_h_{index:03d}",
            activity_date,
            hour=18 if index < 405 else None,
            description="Public" if index < 39 else None,
            rpe=6 if index < 396 else None,
        )
        if index == 0:
            activity = activity.model_copy(update={"distance_meters": 25.0})
        selected.append(activity)
        if index < 29:
            hidden.append(
                HiddenActivityDTO(
                    id=f"hidden-{index}",
                    start_date_local=(
                        f"{activity_date.isoformat()}T18:30:00+01:00"
                    ),
                    _note="hidden",
                )
            )

    analysis = analyze_inventory(
        selected=selected,
        all_records=selected,
        rows=hidden,
        baseline=FrozenBackfillBaseline(),
    )

    assert analysis.coverage.selected == 433
    assert analysis.coverage.hidden_excluded == 29
    assert analysis.coverage.publishable == 404
    assert analysis.coverage.exact_time == 405
    assert analysis.coverage.noon_adjusted == 28
    assert analysis.coverage.athlete_rpe == 396
    assert analysis.coverage.public_descriptions == 39
    assert analysis.coverage.positive_distance == 1
    assert analysis.coverage.positive_elevation == 0
    assert analysis.coverage.conflicts == 0


def test_exact_owned_recovery_is_adopted_but_visible_unowned_match_conflicts():
    activity = _historical_climb(
        "act_h_owned",
        date(2026, 1, 10),
        hour=18,
        description="Public",
        rpe=6,
    )
    payload = render_manual_activity(activity).payload
    remote = ActivityDTO(
        id="remote-owned",
        external_id=payload.external_id,
        type=payload.type,
        name=payload.name,
        start_date=payload.start_date,
        start_date_local=payload.start_date_local,
        timezone=payload.timezone,
        elapsed_time=payload.elapsed_time,
        moving_time=payload.moving_time,
        description=payload.description,
        icu_rpe=payload.icu_rpe,
    )
    baseline = FrozenBackfillBaseline(
        selected=1,
        hidden_excluded=0,
        publishable=1,
        exact_time=1,
        noon_adjusted=0,
    )

    recovered = analyze_inventory(
        selected=[activity],
        all_records=[activity],
        rows=[remote],
        baseline=baseline,
    )

    assert recovered.coverage.owned_recoveries == 1
    assert recovered.decisions[0].action == "adopt_owned"

    unowned = remote.model_copy(
        update={
            "id": "remote-unowned",
            "external_id": "another-system",
        }
    )
    with pytest.raises(HistoricalInventoryError, match="conflicts=1"):
        analyze_inventory(
            selected=[activity],
            all_records=[activity],
            rows=[unowned],
            baseline=baseline,
        )


class FakeBackfillClient:
    def __init__(self, hidden: HiddenActivityDTO):
        self.hidden = hidden
        self.activities: dict[str, ActivityDTO] = {}
        self.next_id = 1
        self.bulk_calls = 0
        self.deleted: list[str] = []
        self.duplicate_upserts = False
        self.lose_next_response = False

    def get_athlete(self):
        return AthleteDTO(id="athlete-1", timezone="Europe/Paris")

    def list_activities(self, oldest, newest, **_kwargs):
        rows = [
            activity
            for activity in self.activities.values()
            if oldest <= activity.start_date_local.date() <= newest
        ]
        hidden_day = datetime.fromisoformat(self.hidden.start_date_local).date()
        if oldest <= hidden_day <= newest:
            rows.append(self.hidden)
        return rows

    def _dto(self, payload: ManualActivityWriteDTO, remote_id: str) -> ActivityDTO:
        return ActivityDTO(
            id=remote_id,
            external_id=payload.external_id,
            type=payload.type,
            name=payload.name,
            start_date=payload.start_date,
            start_date_local=payload.start_date_local,
            timezone=payload.timezone,
            elapsed_time=payload.elapsed_time,
            moving_time=payload.moving_time,
            description=payload.description,
            icu_rpe=payload.icu_rpe,
            distance=payload.distance,
            total_elevation_gain=payload.total_elevation_gain,
            source="MANUAL",
            created=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )

    def create_manual_activities(self, payloads, **_kwargs):
        self.bulk_calls += 1
        result = []
        for payload in payloads:
            existing = next(
                (
                    activity
                    for activity in self.activities.values()
                    if activity.external_id == payload.external_id
                ),
                None,
            )
            if existing is not None and not self.duplicate_upserts:
                remote = self._dto(payload, existing.id)
            else:
                remote_id = f"remote-{self.next_id}"
                self.next_id += 1
                remote = self._dto(payload, remote_id)
            self.activities[remote.id] = remote
            result.append(remote)
        if self.lose_next_response:
            self.lose_next_response = False
            raise IntervalsTransportError(
                "uncertain mutation",
                operation="create_manual_activities",
            )
        return result

    def get_activity(self, activity_id, **_kwargs):
        try:
            return self.activities[activity_id]
        except KeyError as exc:
            raise IntervalsNotFoundError(
                "not found",
                operation="get_activity",
                status_code=404,
            ) from exc

    def delete_activity(self, activity_id):
        if activity_id not in self.activities:
            raise AssertionError("attempted non-exact deletion")
        self.deleted.append(activity_id)
        del self.activities[activity_id]


def _service_fixture(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    archive_root = tmp_path / "data" / "activities"
    archive_root.mkdir(parents=True)
    metrics = tmp_path / "data" / "metrics"
    metrics.mkdir(parents=True)
    (metrics / "unchanged.txt").write_text("stable\n")
    monkeypatch.chdir(tmp_path)
    archive = ActivityArchive(archive_root)
    hidden_match = _historical_climb(
        "act_h_hidden",
        date(2026, 1, 1),
        hour=18,
    )
    noon = _historical_climb(
        "act_h_noon",
        date(2026, 1, 2),
        hour=None,
    )
    canary = _historical_climb(
        "act_h_canary",
        date(2026, 1, 3),
        hour=19,
        description="Public canary",
        rpe=7,
    )
    for activity in (hidden_match, noon, canary):
        archive.write(activity)
    hidden = HiddenActivityDTO(
        id="hidden-1",
        start_date_local="2026-01-01T18:30:00+01:00",
        _note="hidden",
    )
    client = FakeBackfillClient(hidden)
    config = Config(
        settings=Settings(
            intervals_icu=IntervalsIcuSettings(
                history_start_date=date(2026, 1, 1),
            )
        ),
        intervals_icu_api_key="fake",
        loaded_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
    )
    baseline = FrozenBackfillBaseline(
        selected=3,
        hidden_excluded=1,
        publishable=2,
        exact_time=2,
        noon_adjusted=1,
    )
    service = HistoricalActivityBackfillService(
        RepositoryIO(),
        config,
        client,
        baseline=baseline,
        clock=lambda: datetime(2026, 1, 4, tzinfo=timezone.utc),
    )
    return service, client, archive_root


def _approved_plan(service):
    plan = service.dry_run(
        today=date(2026, 1, 4),
        downloads_disabled_confirmed=True,
    )
    canary_approval = service.record_approval(
        stage=ApprovalStage.CANARY,
        plan_digest_sha256=plan.plan_digest_sha256,
    )
    assert (
        service.record_approval(
            stage=ApprovalStage.CANARY,
            plan_digest_sha256=plan.plan_digest_sha256,
        )
        == canary_approval
    )
    proof = service.canary(plan_digest_sha256=plan.plan_digest_sha256)
    service.record_approval(
        stage=ApprovalStage.APPLY,
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )
    return plan, proof


def test_canary_apply_repeat_feedback_sync_and_exact_rollback(
    tmp_path,
    monkeypatch,
):
    service, client, archive_root = _service_fixture(tmp_path, monkeypatch)
    plan, proof = _approved_plan(service)

    applied = service.apply(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )
    repeated = service.apply(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )
    records = ActivityArchive(archive_root).load_all()
    linked = [item for item in records if item.origin.intervals_icu_activity_id]

    assert applied["verified_publications"] == 2
    assert repeated["no_op"]
    assert len(records) == 3
    assert len(linked) == 2
    assert (tmp_path / "data/metrics/unchanged.txt").read_text() == "stable\n"
    assert len(read_sync_state(service.repo).external_to_local) == 2
    assert verify_backup(service.repo_root, plan)["files"]

    canary_local = next(
        item for item in linked if item.local_activity_id == "act_h_canary"
    )
    before = canary_local.model_dump(mode="json", by_alias=True)
    remote = client.get_activity(canary_local.origin.intervals_icu_activity_id)
    mapped = map_activity(
        remote,
        imported_at_utc=datetime(2026, 1, 4, tzinfo=timezone.utc),
        default_timezone="Europe/Paris",
    )
    decision = reconcile_activity(mapped, records)
    refreshed = decision.activity
    assert refreshed.local_activity_id == canary_local.local_activity_id
    assert refreshed.source_sport_type == "RockClimbing"
    assert refreshed.origin.kind == "historical_import"
    assert refreshed.origin.recording_provider == "unknown"
    assert refreshed.occurrence.model_dump() == canary_local.occurrence.model_dump()
    assert refreshed.duration == canary_local.duration
    assert refreshed.notes == canary_local.notes
    assert refreshed.calculated_load == canary_local.calculated_load
    assert before["local_activity_id"] == refreshed.local_activity_id

    rolled_back = service.rollback(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )

    assert rolled_back["restored"] == 2
    assert len(client.activities) == 0
    assert len(client.deleted) == 2
    restored = ActivityArchive(archive_root).load_all()
    assert len(restored) == 3
    assert all(item.origin.intervals_icu_activity_id is None for item in restored)
    assert read_sync_state(service.repo).external_to_local == {}
    assert all(
        item.status == PublicationStatus.ROLLED_BACK
        for item in load_ledger(service.repo).publications.values()
    )


def test_default_rpe_updates_only_missing_remote_value_and_remains_rollback_safe(
    tmp_path,
    monkeypatch,
):
    service, client, archive_root = _service_fixture(tmp_path, monkeypatch)
    plan, proof = _approved_plan(service)
    service.apply(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )
    service.record_approval(
        stage=ApprovalStage.RPE_DEFAULT,
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )
    local_before = {
        item.local_activity_id: item.model_dump(mode="json", by_alias=True)
        for item in ActivityArchive(archive_root).load_all()
    }
    metrics_before = (tmp_path / "data/metrics/unchanged.txt").read_bytes()

    result = service.set_default_rpe(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
        value=5,
    )
    repeated = service.set_default_rpe(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
        value=5,
    )

    assert result["processed"] == 1
    assert result["preserved_existing"] == 1
    assert result["verified_defaulted"] == 1
    assert repeated["no_op"]
    assert repeated["already_defaulted"] == 1
    assert sorted(item.icu_rpe for item in client.activities.values()) == [5, 7]
    ledger = load_ledger(service.repo)
    assert (
        ledger.publications["act_h_noon"].remote_athlete_rpe_override == 5
    )
    assert (
        ledger.publications["act_h_canary"].remote_athlete_rpe_override is None
    )
    local_after = {
        item.local_activity_id: item.model_dump(mode="json", by_alias=True)
        for item in ActivityArchive(archive_root).load_all()
    }
    assert local_after == local_before
    assert (tmp_path / "data/metrics/unchanged.txt").read_bytes() == metrics_before

    rolled_back = service.rollback(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )

    assert rolled_back["restored"] == 2
    assert client.activities == {}


def test_lost_default_rpe_response_is_adopted_without_duplicate_post(
    tmp_path,
    monkeypatch,
):
    service, client, _archive_root = _service_fixture(tmp_path, monkeypatch)
    plan, proof = _approved_plan(service)
    service.apply(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )
    service.record_approval(
        stage=ApprovalStage.RPE_DEFAULT,
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )
    calls_before = client.bulk_calls
    client.lose_next_response = True

    with pytest.raises(IntervalsTransportError):
        service.set_default_rpe(
            plan_digest_sha256=plan.plan_digest_sha256,
            canary_digest_sha256=proof.canary_digest_sha256,
            value=5,
        )

    assert set(load_ledger(service.repo).pending) == {"act_h_noon"}
    recovered = service.set_default_rpe(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
        value=5,
    )

    assert recovered["processed"] == 0
    assert recovered["recovered"] == 1
    assert client.bulk_calls == calls_before + 1
    assert load_ledger(service.repo).pending == {}


def test_lost_apply_response_is_recovered_without_duplicate_post(
    tmp_path,
    monkeypatch,
):
    service, client, _archive_root = _service_fixture(tmp_path, monkeypatch)
    plan, proof = _approved_plan(service)
    calls_before = client.bulk_calls
    client.lose_next_response = True

    with pytest.raises(IntervalsTransportError):
        service.apply(
            plan_digest_sha256=plan.plan_digest_sha256,
            canary_digest_sha256=proof.canary_digest_sha256,
        )

    pending = load_ledger(service.repo).pending
    assert set(pending) == {"act_h_noon"}
    assert len(client.activities) == 2

    resumed = service.resume(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )

    assert resumed["verified_publications"] == 2
    assert client.bulk_calls == calls_before + 1
    assert len(client.activities) == 2


def test_canary_duplicate_semantics_are_cleaned_and_abort_bulk(
    tmp_path,
    monkeypatch,
):
    service, client, archive_root = _service_fixture(tmp_path, monkeypatch)
    plan = service.dry_run(
        today=date(2026, 1, 4),
        downloads_disabled_confirmed=True,
    )
    service.record_approval(
        stage=ApprovalStage.CANARY,
        plan_digest_sha256=plan.plan_digest_sha256,
    )
    client.duplicate_upserts = True

    with pytest.raises(HistoricalActivityBackfillError, match="changed the activity"):
        service.canary(plan_digest_sha256=plan.plan_digest_sha256)

    assert client.activities == {}
    assert len(client.deleted) == 2
    assert load_ledger(service.repo).pending == {}
    assert all(
        item.origin.intervals_icu_activity_id is None
        for item in ActivityArchive(archive_root).load_all()
    )


def test_archive_state_commit_failure_rolls_back_then_resume_adopts_remote(
    tmp_path,
    monkeypatch,
):
    service, client, archive_root = _service_fixture(tmp_path, monkeypatch)
    plan, proof = _approved_plan(service)
    from resilio.core.historical_activity_backfill import execution

    real_write_sync_state = execution.write_sync_state

    def fail_state(*_args, **_kwargs):
        raise RuntimeError("simulated sync-state failure")

    monkeypatch.setattr(execution, "write_sync_state", fail_state)
    with pytest.raises(RuntimeError, match="sync-state failure"):
        service.apply(
            plan_digest_sha256=plan.plan_digest_sha256,
            canary_digest_sha256=proof.canary_digest_sha256,
        )

    linked = [
        item
        for item in ActivityArchive(archive_root).load_all()
        if item.origin.intervals_icu_activity_id
    ]
    assert [item.local_activity_id for item in linked] == ["act_h_canary"]
    assert len(client.activities) == 2
    assert set(load_ledger(service.repo).pending) == {"act_h_noon"}

    monkeypatch.setattr(execution, "write_sync_state", real_write_sync_state)
    resumed = service.resume(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )

    assert resumed["verified_publications"] == 2
    assert len(client.activities) == 2


def test_remote_drift_refuses_rollback_without_deletion(
    tmp_path,
    monkeypatch,
):
    service, client, archive_root = _service_fixture(tmp_path, monkeypatch)
    plan, proof = _approved_plan(service)
    service.apply(
        plan_digest_sha256=plan.plan_digest_sha256,
        canary_digest_sha256=proof.canary_digest_sha256,
    )
    drifted_id = next(iter(client.activities))
    client.activities[drifted_id] = client.activities[drifted_id].model_copy(
        update={"description": "Remote edit"}
    )

    with pytest.raises(HistoricalActivityRenderingError, match="does not match"):
        service.rollback(
            plan_digest_sha256=plan.plan_digest_sha256,
            canary_digest_sha256=proof.canary_digest_sha256,
        )

    assert client.deleted == []
    assert len(
        [
            item
            for item in ActivityArchive(archive_root).load_all()
            if item.origin.intervals_icu_activity_id
        ]
    ) == 2
