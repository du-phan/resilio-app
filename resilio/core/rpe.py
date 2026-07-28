"""Selection policy for multiple provider-neutral RPE estimates."""

from resilio.schemas.activity import RPEEstimate, RPESource


def select_best_rpe_estimate(estimates: list[RPEEstimate]) -> int:
    if not estimates:
        return 5
    for source in [
        RPESource.USER_INPUT,
        RPESource.HR_BASED,
        RPESource.PACE_BASED,
        RPESource.HISTORICAL_RELATIVE_EFFORT,
        RPESource.DURATION_HEURISTIC,
    ]:
        matching = [estimate for estimate in estimates if estimate.source == source]
        if matching:
            matching.sort(
                key=lambda item: {"high": 3, "medium": 2, "low": 1}.get(
                    item.confidence,
                    0,
                ),
                reverse=True,
            )
            return matching[0].value
    return estimates[0].value
