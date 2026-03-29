import json
import sys
from io import StringIO
from types import SimpleNamespace

from deep_coder.tools.ask_user.tool import AskUserTool


def test_ask_user_tool_emits_question_event_and_returns_answers(tmp_path, monkeypatch):
    tool = AskUserTool(config=SimpleNamespace(), workdir=tmp_path)
    stdout = StringIO()
    stdin = StringIO(
        json.dumps({"answers": {"Which approach should I use?": "Option B"}}) + "\n"
    )
    session = SimpleNamespace(
        session_id="session-a",
        root=tmp_path,
        events=[],
        current_turn_id="turn-1",
    )

    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stdin", stdin)

    result = tool.exec(
        {
            "questions": [
                {
                    "question": "Which approach should I use?",
                    "options": [
                        {"label": "Option A", "description": "Fast but less accurate"},
                        {"label": "Option B", "description": "Slower but more accurate"},
                    ],
                }
            ]
        },
        session=session,
    )

    live_event = json.loads(stdout.getvalue().strip())

    assert live_event["type"] == "question_asked"
    assert live_event["session_id"] == "session-a"
    assert live_event["turn_id"] == "turn-1"
    assert live_event["questions"][0]["options"][-1] == {
        "label": "Other",
        "description": "Type your own answer",
    }
    assert json.loads(result.output_text) == {
        "Which approach should I use?": "Option B"
    }
    assert session.events == [
        {
            "type": "question_asked",
            "session_id": "session-a",
            "turn_id": "turn-1",
            "questions": live_event["questions"],
            "answers": {"Which approach should I use?": "Option B"},
        }
    ]
    persisted_events = [
        json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()
    ]
    assert persisted_events == session.events


def test_ask_user_tool_returns_error_for_malformed_answers(tmp_path, monkeypatch):
    tool = AskUserTool(config=SimpleNamespace(), workdir=tmp_path)
    stdout = StringIO()
    stdin = StringIO("{not json}\n")
    session = SimpleNamespace(
        session_id="session-a",
        root=tmp_path,
        events=[],
        current_turn_id="turn-1",
    )

    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stdin", stdin)

    result = tool.exec(
        {
            "questions": [
                {
                    "question": "Which approach should I use?",
                    "options": [
                        {"label": "Option A", "description": "Fast but less accurate"},
                    ],
                }
            ]
        },
        session=session,
    )

    assert result.is_error is True
    assert "malformed" in result.output_text.lower()
    assert "answers" not in session.events[0]
