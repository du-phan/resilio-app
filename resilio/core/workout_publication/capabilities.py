"""Read-only Intervals.icu and Garmin capability projection for running."""

from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    garmin_filter_allows,
    settings_for_event_type,
    sport_settings_version,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.schemas.publication import RunSynchronizationCapabilities


def get_run_synchronization_capabilities(
    client: IntervalsIcuClient,
) -> RunSynchronizationCapabilities:
    """Return current provider readiness without mutating local or remote state."""
    athlete = client.get_athlete()
    if not athlete.timezone:
        raise PublicationSafetyError("Athlete timezone is required for publication")
    connections = client.get_connections(athlete.id)
    settings = settings_for_event_type(client.get_sport_settings(athlete.id), "Run")

    garmin_enabled = athlete.garmin_upload_workouts is True
    garmin_run_allowed = garmin_filter_allows(athlete.garmin_upload_filters, "Run")
    garmin_eligible = (
        connections.garmin_training_connected and garmin_enabled and garmin_run_allowed
    )
    pace_ready = settings.threshold_speed_meters_per_second is not None and bool(
        settings.pace_zones
    )
    limitations: list[str] = []
    if not connections.garmin_training_connected:
        limitations.append("garmin_training_connection_missing")
    if not garmin_enabled:
        limitations.append("garmin_workout_forwarding_disabled")
    if not garmin_run_allowed:
        limitations.append("garmin_run_filter_blocked")
    if settings.lthr is None:
        limitations.append("run_lactate_threshold_heart_rate_missing")
    if settings.max_hr is None:
        limitations.append("run_maximum_heart_rate_missing")
    if not settings.hr_zones:
        limitations.append("run_heart_rate_zones_missing")
    if settings.threshold_speed_meters_per_second is None:
        limitations.append("run_threshold_pace_missing")
    if not settings.pace_zones:
        limitations.append("run_pace_zones_missing")

    threshold_pace_seconds_per_kilometer = None
    if settings.threshold_speed_meters_per_second is not None:
        threshold_pace_seconds_per_kilometer = 1_000 / settings.threshold_speed_meters_per_second
    return RunSynchronizationCapabilities(
        athlete_id=athlete.id,
        athlete_timezone=athlete.timezone,
        run_sport_settings_id=settings.id,
        sport_settings_version_sha256=sport_settings_version(settings),
        intervals_calendar_ready=True,
        garmin_connected=connections.garmin_training_connected,
        garmin_workout_forwarding_enabled=garmin_enabled,
        garmin_run_filter_allows=garmin_run_allowed,
        garmin_forwarding_eligible=garmin_eligible,
        targetless_workouts_ready=True,
        absolute_heart_rate_targets_ready=True,
        percent_lthr_targets_ready=settings.lthr is not None,
        percent_max_heart_rate_targets_ready=settings.max_hr is not None,
        pace_targets_ready=pace_ready,
        lactate_threshold_heart_rate_beats_per_minute=settings.lthr,
        maximum_heart_rate_beats_per_minute=settings.max_hr,
        heart_rate_zone_count=len(settings.hr_zones),
        threshold_pace_seconds_per_kilometer=threshold_pace_seconds_per_kilometer,
        pace_zone_count=len(settings.pace_zones),
        limitations=limitations,
    )
