"""Intervals.icu documented-field disposition registry tests."""

from resilio.integrations.intervals_icu.field_policy import (
    FieldDisposition,
    ProviderResource,
    documented_field_policy,
    documented_fields,
)


def test_every_pinned_documented_field_has_one_disposition() -> None:
    for resource in ProviderResource:
        fields = documented_fields(resource)
        policies = [documented_field_policy(resource, field) for field in fields]

        assert fields
        assert len(policies) == len(fields)
        assert all(policy.provider_field in fields for policy in policies)


def test_coaching_feedback_and_wellness_comments_are_persisted() -> None:
    for resource, field in (
        (ProviderResource.ACTIVITY, "description"),
        (ProviderResource.ACTIVITY, "icu_rpe"),
        (ProviderResource.ACTIVITY, "feel"),
        (ProviderResource.WELLNESS, "comments"),
        (ProviderResource.WELLNESS, "sleepSecs"),
        (ProviderResource.WELLNESS, "steps"),
    ):
        assert documented_field_policy(resource, field).disposition == (
            FieldDisposition.PERSISTED_COACHING
        )


def test_sensitive_wellness_and_unbounded_activity_data_are_excluded() -> None:
    assert (
        documented_field_policy(
            ProviderResource.WELLNESS,
            "bloodGlucose",
        ).disposition
        == FieldDisposition.VALIDATED_EXCLUDED_SENSITIVE
    )
    assert (
        documented_field_policy(
            ProviderResource.ACTIVITY_ENDPOINT,
            "streams",
        ).disposition
        == FieldDisposition.EXCLUDED_UNBOUNDED_OR_LOCATION
    )
    assert (
        documented_field_policy(
            ProviderResource.ACTIVITY_ENDPOINT,
            "messages",
        ).disposition
        == FieldDisposition.EXCLUDED_ATHLETE_COMMUNICATION
    )


def test_hr_curve_is_explicitly_on_demand() -> None:
    assert (
        documented_field_policy(
            ProviderResource.ACTIVITY_ENDPOINT,
            "hr_curve",
        ).disposition
        == FieldDisposition.ON_DEMAND_EXACT_REVIEW
    )
