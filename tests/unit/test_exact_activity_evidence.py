"""Bounded, exact-activity coaching evidence tests."""

from datetime import date, datetime, timezone

import pytest

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.coaching_context.exact_activity import (
    build_exact_activity_coaching_evidence,
)
from resilio.core.repository import RepositoryIO
from resilio.core.training_state_repository import write_wellness
from resilio.integrations.intervals_icu.dto import HeartRateCurveDTO
from resilio.schemas.activity import ActivityOrigin, ActivityOriginKind
from resilio.schemas.training_state import WellnessDay
from tests.factories import make_activity


def test_exact_activity_evidence_includes_feedback_intervals_and_wellness(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    activity = make_activity(
        id="run-with-feedback",
        date=date(2026, 8, 6),
        description="Felt relaxed until the final climb.",
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)
    write_wellness(
        repo,
        {
            date(2026, 8, 6): WellnessDay(
                local_date=date(2026, 8, 6),
                sleep_duration_seconds=27_000,
                hrv_rmssd_ms=54,
                athlete_comments="Slept well; legs slightly heavy.",
            )
        },
    )

    evidence = build_exact_activity_coaching_evidence(
        repo,
        local_activity_id=activity.local_activity_id,
    )

    assert evidence.activity.feedback.provider_description == (
        "Felt relaxed until the final climb."
    )
    assert evidence.recovery_context.athlete_notes[0].text == ("Slept well; legs slightly heavy.")
    assert evidence.recovery_evidence_timing.pre_activity_causality == "not_established"
    assert evidence.activity_feedback_trust_boundary == ("athlete_authored_untrusted_text")
    assert "raw_streams" in evidence.evidence_excluded_from_context


def test_exact_activity_evidence_maps_requested_provider_hr_curve(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    activity = make_activity(id="act_i_curve_run", date=date(2026, 8, 6)).model_copy(
        update={
            "origin": ActivityOrigin(
                kind=ActivityOriginKind.INTERVALS_ICU,
                intervals_icu_activity_id="a1",
            )
        }
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)

    evidence = build_exact_activity_coaching_evidence(
        repo,
        local_activity_id=activity.local_activity_id,
        provider_heart_rate_curve=HeartRateCurveDTO(
            id="a1",
            secs=[5, 60, 300],
            values=[170, 160, 150],
        ),
        provider_heart_rate_curve_requested=True,
    )

    assert evidence.provider_heart_rate_curve_status == "available"
    assert [point.duration_seconds for point in evidence.provider_heart_rate_curve] == [
        5,
        60,
        300,
    ]
    assert evidence.provider_heart_rate_curve[1].heart_rate_beats_per_minute == 160


def test_provider_hr_curve_requires_parallel_duration_and_value_arrays() -> None:
    try:
        HeartRateCurveDTO(id="a1", secs=[5, 60], values=[170])
    except ValueError as exc:
        assert "same number" in str(exc)
    else:
        raise AssertionError("mismatched HR curve arrays must fail validation")


@pytest.mark.parametrize(
    ("seconds", "values", "message"),
    [
        ([5, 5], [170, 169], "strictly increasing"),
        ([5], [300], "heart rates"),
        (list(range(1, 1_002)), [150] * 1_001, "at most 1000"),
    ],
)
def test_provider_hr_curve_is_bounded_and_physiologically_typed(
    seconds,
    values,
    message,
) -> None:
    with pytest.raises(ValueError, match=message):
        HeartRateCurveDTO(id="a1", secs=seconds, values=values)


def test_provider_hr_curve_client_uses_read_only_json_endpoint() -> None:
    import httpx

    from resilio.integrations.intervals_icu.client import IntervalsIcuClient
    from resilio.schemas.config import Config, Settings

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/activity/a1/hr-curve.json"
        return httpx.Response(200, json={"id": "a1", "secs": [5], "values": [170]})

    config = Config(
        settings=Settings(),
        intervals_icu_api_key="never-log-this-test-key",
        loaded_at=datetime.now(timezone.utc),
    )
    with IntervalsIcuClient(config, transport=httpx.MockTransport(handler)) as client:
        curve = client.get_activity_heart_rate_curve("a1")

    assert curve.values == [170]
