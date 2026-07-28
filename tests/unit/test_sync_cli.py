"""Activity-sync CLI messaging regression tests."""

from resilio.cli.commands.sync import _success_message
from resilio.schemas.sync import SyncReport


def test_partial_sync_message_does_not_claim_completion() -> None:
    report = SyncReport(
        run_id="sync-test",
        partial=True,
        activities_created=2,
        activities_unchanged=3,
        ambiguous_rows=4,
        quarantined_rows=1,
    )

    message = _success_message(report)

    assert message.startswith("Activity sync partial:")
    assert "4 ambiguous" in message
    assert "1 quarantined" in message


def test_complete_sync_message_reports_completion() -> None:
    report = SyncReport(run_id="sync-test", partial=False)

    assert _success_message(report).startswith("Activity sync complete:")
