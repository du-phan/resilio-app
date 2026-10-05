"""Project demonstrated running without treating planned targets as completion."""

from datetime import date, timedelta

from resilio.canonical import canonical_data_sha256
from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.coaching_context.coverage import build_sync_evidence_coverage
from resilio.core.coaching_context.exposure import intensity_context, other_sport_exposure
from resilio.core.coaching_context.recovery import build_recovery_context
from resilio.core.planning.source_state import coaching_evidence_source_sha256_unlocked
from resilio.core.repository import RepositoryIO
from resilio.core.training_state_repository import load_wellness
from resilio.schemas.activity import ActivityStatus, is_running_sport
from resilio.schemas.running_progression import (
    RunningProgressionEvidenceV1,
    RunningRecording,
    RunningSession,
    RunningWeek,
)


def distance_change_percent(
    candidate_meters: float | None, baseline_meters: float | None
) -> float | None:
    if candidate_meters is None or baseline_meters is None or baseline_meters <= 0:
        return None
    return 100 * (candidate_meters / baseline_meters - 1)


def comparison_window(candidate_date: date, as_of_date: date) -> tuple[date, date, date]:
    end = candidate_date - timedelta(days=1)
    return candidate_date - timedelta(days=30), end, min(end, as_of_date)


def group_recordings(
    recordings: list[RunningRecording],
) -> tuple[list[RunningSession], list[str]]:
    """Join adjacent known recordings across pauses strictly shorter than 15 minutes.

    Overlapping recordings remain separate; no duplicate or ownership inference.
    Session date is the first recording's canonical local date, including midnight.
    """
    timed = sorted(
        (item for item in recordings if item.start_time_utc is not None),
        key=lambda item: (item.start_time_utc, item.activity_id),
    )
    groups: list[list[RunningRecording]] = []
    limitations: set[str] = set()
    ambiguous: set[str] = set()
    active: list[RunningRecording] = []
    for item in timed:
        assert item.start_time_utc is not None
        active = [
            previous
            for previous in active
            if previous.start_time_utc is not None
            and previous.start_time_utc + timedelta(seconds=previous.elapsed_duration_seconds)
            > item.start_time_utc
        ]
        if active:
            ambiguous.update(previous.activity_id for previous in active)
            ambiguous.add(item.activity_id)
        active.append(item)
    if ambiguous:
        limitations.add("overlapping_recordings")
    for item in timed:
        if (
            groups
            and item.activity_id not in ambiguous
            and groups[-1][-1].activity_id not in ambiguous
        ):
            previous = groups[-1][-1]
            assert previous.start_time_utc is not None and item.start_time_utc is not None
            end = previous.start_time_utc + timedelta(seconds=previous.elapsed_duration_seconds)
            pause_seconds = (item.start_time_utc - end).total_seconds()
            if 0 <= pause_seconds < 900:
                groups[-1].append(item)
                continue
        groups.append([item])
    untimed = [item for item in recordings if item.start_time_utc is None]
    if untimed:
        limitations.add("missing_recording_start_times")
    groups.extend([item] for item in untimed)
    sessions = [_session(group) for group in groups]
    return sorted(sessions, key=lambda item: (item.local_date, item.activity_ids)), sorted(
        limitations
    )


def _session(group: list[RunningRecording]) -> RunningSession:
    first, last = group[0], group[-1]
    elapsed_seconds = sum(item.elapsed_duration_seconds for item in group)
    wall_seconds = None
    if first.start_time_utc is not None and last.start_time_utc is not None:
        wall_seconds = int((last.start_time_utc - first.start_time_utc).total_seconds())
        wall_seconds += last.elapsed_duration_seconds
    distances = [item.distance_meters for item in group]
    return RunningSession(
        activity_ids=[item.activity_id for item in group],
        local_date=first.local_date,
        distance_meters=(
            sum(value for value in distances if value is not None)
            if all(value is not None for value in distances)
            else None
        ),
        moving_duration_seconds=sum(item.moving_duration_seconds for item in group),
        elapsed_duration_seconds=elapsed_seconds,
        pause_duration_seconds=wall_seconds - elapsed_seconds if wall_seconds is not None else 0,
        wall_span_seconds=wall_seconds,
    )


def _weekly_totals(
    sessions: list[RunningSession], recordings: list[RunningRecording], start: date, end: date
) -> RunningWeek:
    observed = [item for item in recordings if start <= item.local_date <= end]
    distances = [item.distance_meters for item in observed]
    total = sum(value for value in distances if value is not None)
    complete = all(value is not None for value in distances)
    recorded_distances = {item.activity_id: item.distance_meters for item in observed}
    contributions = [
        sum(
            recorded_distances[identifier] or 0
            for identifier in session.activity_ids
            if identifier in recorded_distances
        )
        for session in sessions
    ]
    return RunningWeek(
        start_date=start,
        observed_end_date=end,
        session_count=sum(start <= item.local_date <= end for item in sessions),
        running_day_count=len({item.local_date for item in observed}),
        distance_meters=total if complete else None,
        moving_duration_seconds=sum(item.moving_duration_seconds for item in observed),
        elapsed_duration_seconds=sum(item.elapsed_duration_seconds for item in observed),
        supporting_distance_meters=total - max(contributions, default=0) if complete else None,
    )


def build_running_progression_evidence_unlocked(
    repo: RepositoryIO,
    *,
    as_of_date: date,
) -> RunningProgressionEvidenceV1:
    """Caller owns publication/plan/activity locks when binding or consuming evidence."""
    start = as_of_date - timedelta(days=as_of_date.weekday(), weeks=5)
    activities = ActivityArchive(repo.resolve_path("data/activities")).load_all()
    recordings = []
    for activity in activities:
        if (
            activity.status != ActivityStatus.ACTIVE
            or not is_running_sport(activity.sport)
            or not start <= activity.occurrence.local_date <= as_of_date
        ):
            continue
        feedback = activity.feedback
        recordings.append(
            RunningRecording(
                activity_id=activity.local_activity_id,
                canonical_sha256=canonical_data_sha256(activity),
                local_date=activity.occurrence.local_date,
                start_time_utc=activity.occurrence.start_time_utc,
                distance_meters=activity.distance_meters,
                moving_duration_seconds=activity.duration.moving_seconds,
                elapsed_duration_seconds=activity.duration.elapsed_seconds,
                surface=str(activity.classification.surface),
                feedback=[
                    str(value)
                    for value in feedback.model_dump(mode="json").values()
                    if value is not None
                ]
                if feedback is not None
                else [],
            )
        )
    recordings.sort(key=lambda item: (item.local_date, item.activity_id))
    sessions, limitations = group_recordings(recordings)
    week_starts = [start + timedelta(weeks=index) for index in range(6)]
    coverage = [
        build_sync_evidence_coverage(
            repo,
            requested_window_start=week_start,
            requested_window_end=min(week_start + timedelta(days=6), as_of_date),
        )
        for week_start in week_starts
    ]
    weekly_activities = [
        [
            activity
            for activity in activities
            if activity.status == ActivityStatus.ACTIVE
            and week_start
            <= activity.occurrence.local_date
            <= min(week_start + timedelta(days=6), as_of_date)
        ]
        for week_start in week_starts
    ]
    recovery = build_recovery_context(load_wellness(repo), as_of_date=as_of_date)
    if any(item.distance_meters is None for item in recordings):
        limitations.append("missing_recorded_distances")
    if any(
        week.status not in ("complete", "complete_with_declared_exclusions") for week in coverage
    ):
        limitations.append("incomplete_source_coverage_recorded_maxima_only")
    limitations.append("planned_duration_is_nominal_not_demonstrated_tolerance")
    return RunningProgressionEvidenceV1(
        as_of_date=as_of_date,
        window_start_date=start,
        source_state_sha256=coaching_evidence_source_sha256_unlocked(
            repo, evidence_as_of_date=as_of_date, evidence_window_start=start
        ),
        recordings=recordings,
        sessions=sessions,
        weeks=[
            _weekly_totals(
                sessions, recordings, week_start, min(week_start + timedelta(days=6), as_of_date)
            )
            for week_start in week_starts
        ],
        recovery=recovery,
        coverage_by_week=[item.model_dump(mode="json") for item in coverage],
        other_sport_exposure_by_week=[
            {
                "week_start": week_start.isoformat(),
                "sports": [item.model_dump(mode="json") for item in other_sport_exposure(observed)],
            }
            for week_start, observed in zip(week_starts, weekly_activities, strict=True)
        ],
        intensity_evidence_by_week=[
            {
                "week_start": week_start.isoformat(),
                "intensity": intensity_context(
                    observed,
                    due_planned_low_intensity_duration_seconds=0,
                    due_planned_moderate_intensity_duration_seconds=0,
                    due_planned_high_intensity_duration_seconds=0,
                ).model_dump(mode="json"),
            }
            for week_start, observed in zip(week_starts, weekly_activities, strict=True)
        ],
        limitations=sorted(set(limitations)),
    )
