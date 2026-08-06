"""Presentation-neutral exact completed-activity coaching evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from resilio.core.coaching_context.exact_activity import (
    build_exact_activity_coaching_evidence,
)
from resilio.core.config import ConfigError, load_config
from resilio.core.repository import RepositoryIO
from resilio.integrations.intervals_icu import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import (
    IntervalsIcuError,
    IntervalsNotFoundError,
)
from resilio.schemas.activity_evidence import ExactActivityCoachingEvidence


@dataclass(frozen=True)
class ActivityEvidenceError:
    error_type: str
    message: str


def get_exact_activity_coaching_evidence(
    *,
    local_activity_id: str,
    include_provider_heart_rate_curve: bool = False,
    environment: Optional[Mapping[str, str]] = None,
    client: Optional[IntervalsIcuClient] = None,
) -> ExactActivityCoachingEvidence | ActivityEvidenceError:
    """Return local exact evidence, optionally enriched by a read-only HR curve."""
    repo = RepositoryIO()
    try:
        local_evidence = build_exact_activity_coaching_evidence(
            repo,
            local_activity_id=local_activity_id,
        )
    except (OSError, ValueError) as exc:
        return ActivityEvidenceError("validation", str(exc))
    if not include_provider_heart_rate_curve:
        return local_evidence
    external_activity_id = local_evidence.activity.origin.intervals_icu_activity_id
    if external_activity_id is None:
        return build_exact_activity_coaching_evidence(
            repo,
            local_activity_id=local_activity_id,
            provider_heart_rate_curve_requested=True,
        )
    integration = client
    owned_client = integration is None
    if integration is None:
        config = load_config(repo.repo_root, environment=environment)
        if isinstance(config, ConfigError):
            return ActivityEvidenceError(str(config.error_type.value), config.message)
        integration = IntervalsIcuClient(config)
    try:
        curve = integration.get_activity_heart_rate_curve(external_activity_id)
        return build_exact_activity_coaching_evidence(
            repo,
            local_activity_id=local_activity_id,
            provider_heart_rate_curve=curve,
            provider_heart_rate_curve_requested=True,
        )
    except IntervalsNotFoundError:
        return build_exact_activity_coaching_evidence(
            repo,
            local_activity_id=local_activity_id,
            provider_heart_rate_curve_requested=True,
        )
    except IntervalsIcuError as exc:
        return ActivityEvidenceError(exc.error_type, str(exc))
    finally:
        if owned_client:
            integration.close()
