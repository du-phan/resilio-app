"""Explicit synthetic coach reviews for lifecycle tests, without policy bypasses."""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from resilio.canonical import canonical_data_sha256
from resilio.core.planning.progression_assessment import ProgressionKind
from resilio.core.planning.progression_authoring import assess_progression, bind_progression_review
from resilio.core.repository import RepositoryIO


def bind_test_candidate(
    repo: RepositoryIO, path: Path, *, kind: ProgressionKind, at: datetime
) -> None:
    assessment = assess_progression(repo, path, kind=kind, evaluated_at_utc=at)
    ids = [item.activity_id for item in assessment.evidence.recordings]
    frequencies = {
        week.week_number: week.intended_running_day_count or 3 for week in assessment.weeks
    }
    keys = [(f"week.{week.week_number}", week.week_number) for week in assessment.weeks]
    keys += [(session.key, session.week_number) for session in assessment.sessions]
    judgments = []
    for key, week_number in keys:
        judgments.append(
            {
                "key": key,
                "decision": "proceed",
                "intended_running_day_count": frequencies[week_number],
                "distance_and_duration": (
                    "Synthetic modest training exposure reviewed against recorded "
                    "distances and durations."
                ),
                "duration_estimate_basis": (
                    "Nominal workout durations are scheduling estimates, not measured "
                    "endurance tolerance."
                ),
                "frequency_and_supporting_volume": (
                    "Synthetic run days and supporting weekly volume are consistent "
                    "with the tested schedule."
                ),
                "combined_volume_frequency_quality": (
                    "Synthetic changes preserve easy intensity while reviewing "
                    "frequency and volume together."
                ),
                "terrain_and_travel": (
                    "No material terrain or travel changes are present in this "
                    "synthetic fixture."
                ),
                "recovery_and_feedback": (
                    "Available recovery observations are reviewed individually; "
                    "missing signals remain unknown."
                ),
                "other_sports": (
                    "Other sport exposure is reviewed separately without conversion to "
                    "equivalent running distance."
                ),
                "evidence_activity_ids": ids,
                "unknowns": ["Synthetic recovery evidence is limited."],
                "recommendation": (
                    "Proceed with the bounded synthetic prescription subject to "
                    "ordinary execution conditions."
                ),
                "execution_conditions": (
                    "Stop or shorten if new pain, unusual fatigue, or declining "
                    "recovery appears."
                ),
                "fallback": (
                    "Revise the strategic target and propose shorter easy sessions if "
                    "execution conditions fail."
                ),
                "future_prerequisites": [],
            }
        )
    reasoning_fields = [
        "distance_and_duration",
        "duration_estimate_basis",
        "frequency_and_supporting_volume",
        "combined_volume_frequency_quality",
        "terrain_and_travel",
        "recovery_and_feedback",
        "other_sports",
        "evidence_activity_ids",
        "unknowns",
    ]
    reasoning = {name: judgments[0][name] for name in reasoning_fields}
    for judgment in judgments:
        for name in reasoning_fields:
            judgment.pop(name)
        judgment["reasoning_id"] = "shared"
    review = {
        "candidate_sha256": assessment.candidate_sha256,
        "evidence_sha256": canonical_data_sha256(assessment.evidence),
        "acknowledged_limitations": assessment.evidence.limitations,
        "athlete_reports": [],
        "reasoning": {"shared": reasoning},
        "judgments": judgments,
    }
    with TemporaryDirectory(dir=path.parent) as temporary:
        review_path = Path(temporary) / "review.json"
        output_path = Path(temporary) / "bound.json"
        review_path.write_text(json.dumps(review))
        bind_progression_review(
            repo, path, review_path, output_path, kind=kind, evaluated_at_utc=at
        )
        path.write_bytes(output_path.read_bytes())
