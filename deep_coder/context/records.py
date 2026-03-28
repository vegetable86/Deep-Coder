def make_journal_entry(
    event_id: str,
    turn_id: str,
    kind: str,
    role: str,
    tool_name: str | None = None,
    artifact_ids: list[str] | None = None,
    summary_ids: list[str] | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "turn_id": turn_id,
        "kind": kind,
        "role": role,
        "tool_name": tool_name,
        "artifact_ids": artifact_ids or [],
        "summary_ids": summary_ids or [],
    }


def make_evidence_record(
    evidence_id: str,
    event_id: str,
    role: str,
    content: str,
    artifact_id: str | None = None,
    **metadata,
) -> dict:
    record = {
        "evidence_id": evidence_id,
        "event_id": event_id,
        "role": role,
        "content": content,
        "artifact_id": artifact_id,
    }
    record.update(metadata)
    return record


def make_summary_record(
    summary_id: str,
    covered_event_ids: list[str],
    goal: str,
    **metadata,
) -> dict:
    record = {
        "summary_id": summary_id,
        "covered_event_ids": covered_event_ids,
        "goal": goal,
    }
    record.update(metadata)
    return record
