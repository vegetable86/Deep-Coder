from types import SimpleNamespace

from deep_coder.context.records import make_evidence_record, make_journal_entry
from deep_coder.context.session import Session
from deep_coder.context.strategies.layered_history.strategy import (
    LayeredHistoryContextStrategy,
)


class FakeSummarizer:
    def __init__(self):
        self.calls = []

    def summarize_span(self, session, entries: list[dict]) -> dict:
        self.calls.append(
            {
                "session_id": session.session_id,
                "event_ids": [entry["event_id"] for entry in entries],
            }
        )
        return {
            "goal": "inspect repo",
            "open_questions": ["find app entrypoint"],
        }


def _config(**overrides):
    values = {
        "context_recent_turns": 2,
        "context_compact_threshold": 4500,
        "context_summary_max_tokens": 1200,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_layered_strategy_builds_prompt_from_summary_plus_recent_turns(tmp_path):
    session = Session(session_id="s1", root=tmp_path)
    session.summaries = [
        {
            "summary_id": "sum-1",
            "covered_event_ids": ["evt-1"],
            "goal": "inspect repo",
            "open_questions": ["find app entrypoint"],
        }
    ]
    session.journal = [
        make_journal_entry(
            event_id="evt-9",
            turn_id="turn-9",
            kind="assistant_message",
            role="assistant",
        ),
        make_journal_entry(
            event_id="evt-10",
            turn_id="turn-10",
            kind="user_message",
            role="user",
        ),
    ]
    session.evidence = [
        make_evidence_record(
            evidence_id="evd-9",
            event_id="evt-9",
            role="assistant",
            content="look at cli.py",
        ),
        make_evidence_record(
            evidence_id="evd-10",
            event_id="evt-10",
            role="user",
            content="continue",
        ),
    ]

    strategy = LayeredHistoryContextStrategy(
        config=_config(),
        summarizer=FakeSummarizer(),
    )

    messages = strategy.prepare_messages(session, "system text", "next step")

    assert messages[0] == {"role": "system", "content": "system text"}
    assert "inspect repo" in messages[1]["content"]
    assert "find app entrypoint" in messages[1]["content"]
    assert any(message["content"] == "look at cli.py" for message in messages)
    assert any(message["content"] == "continue" for message in messages)
    assert messages[-1] == {"role": "user", "content": "next step"}


def test_layered_strategy_compacts_old_spans_when_budget_is_exceeded(tmp_path):
    session = Session(session_id="s1", root=tmp_path)
    session.journal = [
        make_journal_entry(
            event_id="evt-1",
            turn_id="turn-1",
            kind="user_message",
            role="user",
        ),
        make_journal_entry(
            event_id="evt-2",
            turn_id="turn-2",
            kind="assistant_message",
            role="assistant",
        ),
        make_journal_entry(
            event_id="evt-3",
            turn_id="turn-3",
            kind="user_message",
            role="user",
        ),
    ]
    session.evidence = [
        make_evidence_record(
            evidence_id="evd-1",
            event_id="evt-1",
            role="user",
            content="inspect repository",
        ),
        make_evidence_record(
            evidence_id="evd-2",
            event_id="evt-2",
            role="assistant",
            content="look at cli.py",
        ),
        make_evidence_record(
            evidence_id="evd-3",
            event_id="evt-3",
            role="user",
            content="continue",
        ),
    ]
    summarizer = FakeSummarizer()
    strategy = LayeredHistoryContextStrategy(
        config=_config(context_recent_turns=1),
        summarizer=summarizer,
    )

    compacted = strategy.maybe_compact(session, usage={"prompt_tokens": 9000})

    assert compacted is True
    assert session.summaries[-1]["covered_event_ids"] == ["evt-1", "evt-2"]
    assert session.journal[0]["summary_ids"] == [session.summaries[-1]["summary_id"]]
    assert summarizer.calls == [
        {
            "session_id": "s1",
            "event_ids": ["evt-1", "evt-2"],
        }
    ]
