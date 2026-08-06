"""Reviewed disposition of Intervals.icu activity and wellness evidence.

The documented field inventory is pinned to the Intervals.icu v1.0.0 OpenAPI
document reviewed on 2026-08-06 (SHA-256
``a9ef880117848c7a1fcb953e34680c3928ae2064ffa8f9973c7799b60a2fb1b7``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProviderResource(str, Enum):
    ACTIVITY = "activity"
    INTERVAL = "interval"
    WELLNESS = "wellness"
    ACTIVITY_ENDPOINT = "activity_endpoint"


class FieldDisposition(str, Enum):
    PERSISTED_COACHING = "persisted_coaching"
    PERSISTED_PROVENANCE = "persisted_provenance"
    ON_DEMAND_EXACT_REVIEW = "on_demand_exact_review"
    VALIDATED_EXCLUDED_SENSITIVE = "validated_excluded_sensitive"
    EXCLUDED_UNBOUNDED_OR_LOCATION = "excluded_unbounded_or_location"
    EXCLUDED_ATHLETE_COMMUNICATION = "excluded_athlete_communication"
    REVIEWED_NOT_INTEGRATED = "reviewed_not_integrated"


@dataclass(frozen=True)
class ProviderFieldPolicy:
    resource: ProviderResource
    provider_field: str
    disposition: FieldDisposition
    rationale: str


def _fields(value: str) -> frozenset[str]:
    return frozenset(value.split())


_DOCUMENTED_ACTIVITY_FIELDS = _fields(
    """
    analysis_issues analyzed athlete_max_hr attachments average_altitude
    average_cadence average_clouds average_feels_like average_heartrate
    average_impact_loading_rate average_leg_spring_stiffness average_speed
    average_stance_time average_stance_time_balance average_stance_time_percent
    average_step_length average_stride average_temp average_vertical_oscillation
    average_vertical_ratio average_vertical_speed average_weather_temp
    average_wind_gust average_wind_speed avg_lr_balance calories carbs_ingested
    carbs_used coach_tick coasting_time commute compliance crank_length created
    custom_zones decoupling description device_name device_watts distance elapsed_time
    external_id feel file_sport_index file_type gap gap_model gap_zone_times gear group
    has_heartrate has_segments has_weather headwind_percent hr_load hr_load_type
    icu_achievements icu_athlete_id icu_atl icu_average_watts icu_cadence_z2
    icu_chat_id icu_color icu_cooldown_time icu_ctl icu_distance
    icu_efficiency_factor icu_ftp icu_groups icu_hr_zone_times icu_hr_zones icu_hrr
    icu_ignore_hr icu_ignore_power icu_ignore_time icu_intensity icu_intervals
    icu_intervals_edited icu_joules icu_joules_above_ftp icu_lap_count
    icu_max_wbal_depletion icu_median_time_delta icu_pm_cp icu_pm_ftp
    icu_pm_ftp_secs icu_pm_ftp_watts icu_pm_p_max icu_pm_w_prime icu_power_hr
    icu_power_hr_z2 icu_power_hr_z2_mins icu_power_spike_threshold icu_power_zones
    icu_recording_time icu_resting_hr icu_rolling_cp icu_rolling_ftp
    icu_rolling_ftp_delta icu_rolling_p_max icu_rolling_w_prime icu_rpe
    icu_sweet_spot_max icu_sweet_spot_min icu_sync_date icu_sync_error
    icu_training_load icu_training_load_data icu_variability_index icu_w_prime
    icu_warmup_time icu_weight icu_weighted_avg_watts icu_zone_times id ignore_pace
    ignore_parts ignore_velocity interval_summary kg_lifted lengths lock_intervals lthr
    max_altitude max_feels_like max_heartrate max_rain max_snow max_speed max_temp
    max_weather_temp min_altitude min_feels_like min_temp min_weather_temp moving_time
    name oauth_client_id oauth_client_name p30s_exponent p_max pace pace_load
    pace_load_type pace_zone_times pace_zones paired_event_id perceived_exertion
    polarization_index pool_length power_field power_field_names power_load power_meter
    power_meter_battery power_meter_serial prevailing_wind_deg race recording_stops
    route_id session_rpe skyline_chart_bytes source ss_cp ss_p_max ss_w_prime start_date
    start_date_local strain_score strava_id stream_types sub_type tags tailwind_percent
    threshold_pace timezone tiz_order total_elevation_gain total_elevation_loss trainer
    trimp type use_elevation_correction use_gap_zone_times workout_shift_secs
    """
)

_DOCUMENTED_INTERVAL_FIELDS = _fields(
    """
    average_cadence average_dfa_a1 average_epoc average_feels_like average_gradient
    average_heartrate average_impact_loading_rate average_lactate
    average_leg_spring_stiffness average_respiration average_smo2 average_smo2_2
    average_speed average_stance_time average_stance_time_balance
    average_stance_time_percent average_step_length average_stride average_temp
    average_thb average_thb_2 average_tidal_volume average_tidal_volume_min
    average_torque average_vertical_oscillation average_vertical_ratio
    average_vertical_speed average_watts average_watts_alt average_watts_alt_acc
    average_watts_kg average_weather_temp average_wind_gust average_wind_speed
    average_yaw avg_lr_balance decoupling distance elapsed_time end_index end_time gap
    group_id headwind_percent id intensity joules joules_above_ftp label max_altitude
    max_cadence max_heartrate max_lactate max_speed max_torque max_watts max_watts_kg
    min_altitude min_cadence min_heartrate min_lactate min_speed min_torque min_watts
    moving_time prevailing_wind_deg segment_effort_ids ss_cp ss_p_max ss_w_prime
    start_index start_time strain_score tailwind_percent total_elevation_gain
    training_load type w5s_variability wbal_end wbal_start weighted_average_watts zone
    zone_max_watts zone_min_watts
    """
)

_DOCUMENTED_WELLNESS_FIELDS = _fields(
    """
    abdomen atl atlLoad avgSleepingHR baevskySI bloodGlucose bodyFat carbohydrates
    comments ctl ctlLoad diastolic fatTotal fatigue hrv hrvSDNN hydration
    hydrationVolume id injury kcalConsumed lactate locked menstrualPhase
    menstrualPhasePredicted mood motivation protein rampRate readiness respiration
    restingHR sleepQuality sleepScore sleepSecs soreness spO2 sportInfo steps stress
    systolic tempRestingHR tempWeight updated vo2max weight
    """
)

_DOCUMENTED_ACTIVITY_ENDPOINTS = _fields(
    """
    best_efforts fit_file gap_histogram gpx_file hr_curve hr_histogram hr_load_model
    interval_stats map messages original_file pace_curve pace_histogram power_curve
    power_histogram power_spike_model power_vs_hr segments streams time_at_hr
    weather_summary
    """
)

_PERSISTED_ACTIVITY_COACHING = _fields(
    """
    athlete_max_hr average_cadence average_heartrate average_speed average_stride
    average_temp calories carbs_ingested carbs_used compliance decoupling description
    distance elapsed_time feel gap gap_zone_times has_heartrate hr_load hr_load_type
    icu_average_watts icu_ftp icu_hr_zone_times icu_hr_zones icu_hrr icu_ignore_hr
    icu_ignore_power icu_ignore_time icu_intensity icu_intervals icu_power_zones
    icu_rpe icu_training_load icu_weight icu_weighted_avg_watts icu_zone_times
    ignore_pace ignore_velocity lthr max_heartrate max_speed moving_time p_max pace_load
    pace_load_type pace_zone_times pace_zones perceived_exertion polarization_index
    power_load session_rpe stream_types threshold_pace tiz_order total_elevation_gain
    trimp use_gap_zone_times
    """
)

_PERSISTED_ACTIVITY_PROVENANCE = _fields(
    """
    created device_name external_id file_type icu_sync_date id name paired_event_id
    source start_date start_date_local sub_type timezone type
    """
)

_PERSISTED_INTERVAL_COACHING = _fields(
    """
    average_cadence average_gradient average_heartrate average_speed average_stride
    average_watts decoupling distance elapsed_time end_index end_time id intensity
    joules joules_above_ftp label max_altitude max_cadence max_heartrate max_speed
    max_watts min_altitude min_cadence min_heartrate min_speed moving_time start_index
    start_time total_elevation_gain training_load type weighted_average_watts zone
    """
)

_PERSISTED_WELLNESS_COACHING = _fields(
    """
    atl atlLoad avgSleepingHR baevskySI comments ctl ctlLoad fatigue hrv hrvSDNN
    hydration hydrationVolume id injury mood motivation rampRate readiness respiration
    restingHR sleepQuality sleepScore sleepSecs soreness spO2 sportInfo steps stress
    tempRestingHR tempWeight updated vo2max weight
    """
)

_SENSITIVE_WELLNESS_FIELDS = _fields(
    """
    abdomen bloodGlucose bodyFat carbohydrates diastolic fatTotal kcalConsumed lactate
    menstrualPhase menstrualPhasePredicted protein systolic
    """
)

_ON_DEMAND_ENDPOINTS = _fields(
    """
    best_efforts hr_curve hr_histogram interval_stats pace_curve pace_histogram
    power_curve power_histogram power_vs_hr time_at_hr
    """
)
_UNBOUNDED_OR_LOCATION_ENDPOINTS = _fields(
    """
    fit_file gpx_file map original_file segments streams
    """
)

_DOCUMENTED = {
    ProviderResource.ACTIVITY: _DOCUMENTED_ACTIVITY_FIELDS,
    ProviderResource.INTERVAL: _DOCUMENTED_INTERVAL_FIELDS,
    ProviderResource.WELLNESS: _DOCUMENTED_WELLNESS_FIELDS,
    ProviderResource.ACTIVITY_ENDPOINT: _DOCUMENTED_ACTIVITY_ENDPOINTS,
}


def documented_fields(resource: ProviderResource) -> frozenset[str]:
    """Return the pinned provider inventory for one reviewed resource."""
    return _DOCUMENTED[resource]


def _disposition(resource: ProviderResource, provider_field: str) -> FieldDisposition:
    if resource == ProviderResource.ACTIVITY:
        if provider_field in _PERSISTED_ACTIVITY_COACHING:
            return FieldDisposition.PERSISTED_COACHING
        if provider_field in _PERSISTED_ACTIVITY_PROVENANCE:
            return FieldDisposition.PERSISTED_PROVENANCE
    elif resource == ProviderResource.INTERVAL:
        if provider_field in _PERSISTED_INTERVAL_COACHING:
            return FieldDisposition.PERSISTED_COACHING
    elif resource == ProviderResource.WELLNESS:
        if provider_field in _PERSISTED_WELLNESS_COACHING:
            return FieldDisposition.PERSISTED_COACHING
        if provider_field in _SENSITIVE_WELLNESS_FIELDS:
            return FieldDisposition.VALIDATED_EXCLUDED_SENSITIVE
    else:
        if provider_field in _ON_DEMAND_ENDPOINTS:
            return FieldDisposition.ON_DEMAND_EXACT_REVIEW
        if provider_field in _UNBOUNDED_OR_LOCATION_ENDPOINTS:
            return FieldDisposition.EXCLUDED_UNBOUNDED_OR_LOCATION
        if provider_field == "messages":
            return FieldDisposition.EXCLUDED_ATHLETE_COMMUNICATION
    return FieldDisposition.REVIEWED_NOT_INTEGRATED


_RATIONALES = {
    FieldDisposition.PERSISTED_COACHING: (
        "Typed, unit-explicit evidence used by coaching or exact activity review."
    ),
    FieldDisposition.PERSISTED_PROVENANCE: (
        "Stable source identity or audit provenance required for reconciliation."
    ),
    FieldDisposition.ON_DEMAND_EXACT_REVIEW: (
        "Bounded evidence retrieved only for an explicitly selected activity."
    ),
    FieldDisposition.VALIDATED_EXCLUDED_SENSITIVE: (
        "Sensitive health, nutrition, or body-composition data excluded pending consent."
    ),
    FieldDisposition.EXCLUDED_UNBOUNDED_OR_LOCATION: (
        "Raw, binary, unbounded, or location-bearing evidence excluded from coaching context."
    ),
    FieldDisposition.EXCLUDED_ATHLETE_COMMUNICATION: (
        "Provider messaging is not an athlete feedback source for Resilio."
    ),
    FieldDisposition.REVIEWED_NOT_INTEGRATED: (
        "Reviewed but not sufficiently decision-relevant for the current coaching model."
    ),
}


def documented_field_policy(
    resource: ProviderResource,
    provider_field: str,
) -> ProviderFieldPolicy:
    """Return one explicit disposition or reject an unreviewed provider field."""
    if provider_field not in _DOCUMENTED[resource]:
        raise KeyError(f"Unreviewed Intervals.icu field: {resource.value}.{provider_field}")
    disposition = _disposition(resource, provider_field)
    return ProviderFieldPolicy(
        resource=resource,
        provider_field=provider_field,
        disposition=disposition,
        rationale=_RATIONALES[disposition],
    )
