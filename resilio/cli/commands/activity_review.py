"""Review and approve conservative completed-activity matches."""

import typer

from resilio.api.reconciliation import (
    acknowledge_activity_quarantine_review,
    approve_activity_review,
    exclude_duplicate_activity_review,
    get_activity_quarantines,
    get_activity_reviews,
    get_external_deletion_reviews,
)
from resilio.cli.errors import (
    api_result_to_envelope,
    get_exit_code_from_envelope,
)
from resilio.cli.output import output_json

app = typer.Typer(help="Review possible completed-activity matches")


@app.command(name="list")
def list_command() -> None:
    result = get_activity_reviews()
    envelope = api_result_to_envelope(
        result,
        success_message="Activity reconciliation review queue fetched.",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="approve")
def approve_command(
    external_hash: str = typer.Option(
        ...,
        "--external-hash",
        help="Full external activity SHA-256 from the review queue",
    ),
    local_activity_id: str = typer.Option(
        ...,
        "--local-id",
        help="Exact candidate local activity ID",
    ),
    review_fingerprint: str = typer.Option(
        ...,
        "--review-fingerprint",
        help="Exact current review fingerprint from the review queue",
    ),
) -> None:
    result = approve_activity_review(
        external_activity_id_sha256=external_hash,
        local_activity_id=local_activity_id,
        review_fingerprint_sha256=review_fingerprint,
    )
    envelope = api_result_to_envelope(
        result,
        success_message="Activity match approval recorded.",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="exclude-duplicate")
def exclude_duplicate_command(
    external_hash: str = typer.Option(
        ...,
        "--external-hash",
        help="Full external activity SHA-256 from the review queue",
    ),
    local_activity_id: str = typer.Option(
        ...,
        "--local-id",
        help="Exact already-linked candidate local activity ID",
    ),
    review_fingerprint: str = typer.Option(
        ...,
        "--review-fingerprint",
        help="Exact current review fingerprint from the review queue",
    ),
) -> None:
    result = exclude_duplicate_activity_review(
        external_activity_id_sha256=external_hash,
        local_activity_id=local_activity_id,
        review_fingerprint_sha256=review_fingerprint,
    )
    envelope = api_result_to_envelope(
        result,
        success_message="Duplicate external recording exclusion recorded.",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="quarantines")
def quarantines_command() -> None:
    result = get_activity_quarantines()
    envelope = api_result_to_envelope(
        result,
        success_message="Activity quarantine review queue fetched.",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="acknowledge-quarantine")
def acknowledge_quarantine_command(
    external_hash: str = typer.Option(
        ...,
        "--external-hash",
        help="Full external activity SHA-256 from the quarantine queue",
    ),
    failure_fingerprint: str = typer.Option(
        ...,
        "--failure-fingerprint",
        help="Exact current failure fingerprint from the quarantine queue",
    ),
) -> None:
    result = acknowledge_activity_quarantine_review(
        external_activity_id_sha256=external_hash,
        failure_fingerprint_sha256=failure_fingerprint,
    )
    envelope = api_result_to_envelope(
        result,
        success_message="Activity quarantine acknowledgement recorded.",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="deletions")
def deletions_command() -> None:
    result = get_external_deletion_reviews()
    envelope = api_result_to_envelope(
        result,
        success_message="External deletion review queue fetched.",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))
