from types import SimpleNamespace

from deep_coder.context.records import make_evidence_record, make_journal_entry
from deep_coder.context.session import Session
from deep_coder.context.summarizers.model import ModelSummarizer
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
        "context_max_tokens": 10000,
        "context_summary_max_tokens": 1200,
        "context_reasoning_max_chars": 4000,
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


def test_layered_strategy_does_not_compact_below_ninety_percent_of_context_window(
    tmp_path,
):
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
    strategy = LayeredHistoryContextStrategy(
        config=_config(context_recent_turns=1),
        summarizer=FakeSummarizer(),
    )

    should_compact = strategy.should_compact(session, usage={"prompt_tokens": 8999})

    assert should_compact is False


def test_layered_strategy_compacts_old_spans_at_ninety_percent_of_context_window(
    tmp_path,
):
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


def test_layered_strategy_skips_compaction_without_summarizable_entries(tmp_path):
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
    ]
    strategy = LayeredHistoryContextStrategy(
        config=_config(context_recent_turns=2),
        summarizer=FakeSummarizer(),
    )

    should_compact = strategy.should_compact(session, usage={"prompt_tokens": 9000})

    assert should_compact is False


def test_layered_strategy_only_compacts_unsummarized_entries_on_second_pass(tmp_path):
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
        make_journal_entry(
            event_id="evt-4",
            turn_id="turn-4",
            kind="assistant_message",
            role="assistant",
        ),
        make_journal_entry(
            event_id="evt-5",
            turn_id="turn-5",
            kind="user_message",
            role="user",
        ),
    ]
    session.evidence = [
        make_evidence_record(
            evidence_id="evd-1",
            event_id="evt-1",
            role="user",
            content="first",
        ),
        make_evidence_record(
            evidence_id="evd-2",
            event_id="evt-2",
            role="assistant",
            content="second",
        ),
        make_evidence_record(
            evidence_id="evd-3",
            event_id="evt-3",
            role="user",
            content="third",
        ),
        make_evidence_record(
            evidence_id="evd-4",
            event_id="evt-4",
            role="assistant",
            content="fourth",
        ),
        make_evidence_record(
            evidence_id="evd-5",
            event_id="evt-5",
            role="user",
            content="fifth",
        ),
    ]
    summarizer = FakeSummarizer()
    strategy = LayeredHistoryContextStrategy(
        config=_config(context_recent_turns=1),
        summarizer=summarizer,
    )

    first_compacted = strategy.maybe_compact(session, usage={"prompt_tokens": 9000})
    session.journal.append(
        make_journal_entry(
            event_id="evt-6",
            turn_id="turn-6",
            kind="assistant_message",
            role="assistant",
        )
    )
    second_compacted = strategy.maybe_compact(session, usage={"prompt_tokens": 9000})

    assert first_compacted is True
    assert second_compacted is True
    assert [summary["covered_event_ids"] for summary in session.summaries] == [
        ["evt-1", "evt-2", "evt-3", "evt-4"],
        ["evt-5"],
    ]
    assert summarizer.calls == [
        {"session_id": "s1", "event_ids": ["evt-1", "evt-2", "evt-3", "evt-4"]},
        {"session_id": "s1", "event_ids": ["evt-5"]},
    ]


def test_layered_history_rebuilds_recent_think_result_from_artifact(tmp_path):
    session = Session(session_id="s1", root=tmp_path)
    entry = make_journal_entry(
        event_id="evt-1",
        turn_id="turn-1",
        kind="tool_result",
        role="tool",
        tool_name="think",
        artifact_ids=["art-1"],
    )
    evidence = make_evidence_record(
        evidence_id="evd-1",
        event_id="evt-1",
        role="tool",
        content="[think result]",
        artifact_id="art-1",
        tool_call_id="tool-1",
    )
    session.artifacts["art-1"] = {
        "artifact_type": "think_result",
        "metadata": {"final_content": "ship it"},
        "reasoning_content": "step by step",
    }
    strategy = LayeredHistoryContextStrategy(
        config=_config(),
        summarizer=FakeSummarizer(),
    )

    message = strategy._message_for_entry(entry, evidence, session)

    assert message["role"] == "tool"
    assert "reasoning_trace" in message["content"]
    assert "final_answer" in message["content"]


def test_layered_history_truncates_reinjected_reasoning_trace(tmp_path):
    full_reasoning_text = "1234567890" * 6
    session = Session(session_id="s1", root=tmp_path)
    entry = make_journal_entry(
        event_id="evt-1",
        turn_id="turn-1",
        kind="tool_result",
        role="tool",
        tool_name="think",
        artifact_ids=["art-1"],
    )
    evidence = make_evidence_record(
        evidence_id="evd-1",
        event_id="evt-1",
        role="tool",
        content="[think result]",
        artifact_id="art-1",
        tool_call_id="tool-1",
    )
    session.artifacts["art-1"] = {
        "artifact_type": "think_result",
        "metadata": {"final_content": "ship it"},
        "reasoning_content": full_reasoning_text,
    }
    strategy = LayeredHistoryContextStrategy(
        config=_config(context_reasoning_max_chars=20),
        summarizer=FakeSummarizer(),
    )

    message = strategy._message_for_entry(entry, evidence, session)

    assert len(message["content"]) < len(full_reasoning_text) + 40


def test_model_summarizer_includes_think_content_in_transcript(tmp_path):
    class FakeModel:
        def __init__(self):
            self.calls = []

        def complete(self, request):
            self.calls.append(request)
            return {"content": '{"goal":"summarized prior context"}'}

    fake_model = FakeModel()
    summarizer = ModelSummarizer(model=fake_model, config=_config())
    session = Session(session_id="s1", root=tmp_path)
    entry = make_journal_entry(
        event_id="evt-1",
        turn_id="turn-1",
        kind="tool_result",
        role="tool",
        tool_name="think",
        artifact_ids=["art-1"],
    )
    session.evidence = [
        make_evidence_record(
            evidence_id="evd-1",
            event_id="evt-1",
            role="tool",
            content="[think result]",
            artifact_id="art-1",
        )
    ]
    session.artifacts["art-1"] = {
        "artifact_type": "think_result",
        "metadata": {"final_content": "ship it"},
        "reasoning_content": "step by step",
    }

    summarizer.summarize_span(session, [entry])

    payload = fake_model.calls[0]["messages"][-1]["content"]

    assert "reasoning_trace" in payload
