from deep_coder.context.records import (
    make_evidence_record,
    make_journal_entry,
    make_summary_record,
)


def test_record_helpers_capture_ids_and_provenance():
    journal = make_journal_entry(
        event_id="evt-1",
        turn_id="turn-1",
        kind="tool_result",
        role="tool",
        tool_name="read_file",
        artifact_ids=["art-1"],
    )
    evidence = make_evidence_record(
        evidence_id="evd-1",
        event_id="evt-1",
        role="tool",
        content="README contents",
    )
    summary = make_summary_record(
        summary_id="sum-1",
        covered_event_ids=["evt-1", "evt-2"],
        goal="inspect repository",
        open_questions=["find cli entrypoint"],
    )

    assert journal["artifact_ids"] == ["art-1"]
    assert evidence["event_id"] == "evt-1"
    assert summary["covered_event_ids"] == ["evt-1", "evt-2"]
    assert summary["open_questions"] == ["find cli entrypoint"]
