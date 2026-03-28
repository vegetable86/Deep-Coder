import json
from pathlib import Path

import pytest

from deep_coder.context.manager import ContextManager
from deep_coder.context.session import Session
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore
from deep_coder.context.strategies.simple_history.strategy import (
    SimpleHistoryContextStrategy,
)
from deep_coder.tools.result import ToolExecutionResult


def test_filesystem_store_creates_and_lists_sessions(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)

    session = store.open()
    store.save(session)

    session_dir = tmp_path / "sessions" / session.session_id
    assert store.list_sessions() == [session.meta()]
    assert (session_dir / "meta.json").exists()
    assert (session_dir / "messages.jsonl").exists()


def test_filesystem_store_persists_messages_and_strategy_state(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)

    session = store.open()
    session.append({"role": "user", "content": "hello"})
    session.strategy_name = "simple_history"
    session.strategy_state = {"message_count": 1}
    store.save(session)

    reopened = store.open(locator={"id": session.session_id})
    state_path = (
        tmp_path
        / "sessions"
        / session.session_id
        / "context"
        / "simple_history"
        / "state.json"
    )

    assert reopened.messages == [{"role": "user", "content": "hello"}]
    assert reopened.strategy_name == "simple_history"
    assert reopened.strategy_state == {"message_count": 1}
    assert json.loads(state_path.read_text()) == {
        "message_count": 1,
        "task_system": {
            "next_task_id": 1,
            "tasks": [],
        },
    }


def test_filesystem_store_persists_layered_context_state(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)
    session = store.open()
    session.journal.append({"event_id": "evt-1", "kind": "user_message"})
    session.evidence.append(
        {"evidence_id": "evd-1", "event_id": "evt-1", "content": "hello"}
    )
    session.summaries.append(
        {
            "summary_id": "sum-1",
            "covered_event_ids": ["evt-1"],
            "goal": "hello",
        }
    )

    store.save(session)
    reopened = store.open(locator={"id": session.session_id})

    assert reopened.journal[0]["event_id"] == "evt-1"
    assert reopened.evidence[0]["evidence_id"] == "evd-1"
    assert reopened.summaries[0]["summary_id"] == "sum-1"


def test_filesystem_store_projects_legacy_messages_into_layered_records(tmp_path):
    session_dir = tmp_path / "sessions" / "session-a"
    session_dir.mkdir(parents=True)
    (session_dir / "meta.json").write_text('{"id": "session-a"}')
    (session_dir / "messages.jsonl").write_text(
        '{"role":"user","content":"show tree"}\n'
    )

    reopened = FileSystemSessionStore(root=tmp_path).open(locator={"id": "session-a"})

    assert reopened.journal[0]["kind"] == "user_message"
    assert reopened.evidence[0]["content"] == "show tree"


def test_filesystem_store_persists_events_and_project_meta(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    store = FileSystemSessionStore(
        root=tmp_path,
        project_key="repo-abc123",
        workspace_path=workspace,
    )

    session = store.open()
    session.events.append({"type": "turn_started", "turn_id": "t1"})
    store.save(session)

    reopened = store.open(locator={"id": session.session_id})

    assert reopened.events == [{"type": "turn_started", "turn_id": "t1"}]
    assert reopened.meta()["project_key"] == "repo-abc123"
    assert reopened.meta()["workspace_path"] == str(workspace)


def test_filesystem_store_lists_session_preview_from_first_user_message(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)

    session = store.open()
    session.append(
        {
            "role": "user",
            "content": "  make   history\nselector   readable  ",
        }
    )
    session.append({"role": "assistant", "content": "ok"})
    store.save(session)

    listed = store.list_sessions()
    reopened = store.open(locator={"id": session.session_id})

    assert listed[0]["preview"] == "make history selector readable"
    assert reopened.meta()["preview"] == "make history selector readable"


def test_filesystem_store_backfills_preview_for_existing_session_metadata(tmp_path):
    session_dir = tmp_path / "sessions" / "session-a"
    session_dir.mkdir(parents=True)
    (session_dir / "meta.json").write_text(json.dumps({"id": "session-a"}, indent=2))
    (session_dir / "messages.jsonl").write_text(
        json.dumps(
            {
                "role": "user",
                "content": "show me the first prompt in history",
            }
        )
        + "\n"
    )

    store = FileSystemSessionStore(root=tmp_path)

    listed = store.list_sessions()

    assert listed == [
        {
            "id": "session-a",
            "preview": "show me the first prompt in history",
        }
    ]


def test_filesystem_store_persists_task_state(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)
    session = store.open()
    session.next_task_id = 3
    session.tasks = [
        {
            "id": 1,
            "subject": "inspect repo",
            "description": "",
            "status": "completed",
            "blocked_by": [],
            "blocks": [2],
        },
        {
            "id": 2,
            "subject": "edit app",
            "description": "",
            "status": "pending",
            "blocked_by": [],
            "blocks": [],
        },
    ]

    store.save(session)
    reopened = store.open(locator={"id": session.session_id})

    assert reopened.next_task_id == 3
    assert reopened.tasks[1]["subject"] == "edit app"


def test_filesystem_store_round_trips_active_skills(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)
    session = store.open(locator={"id": "session-a"})
    session.active_skills = [
        {
            "name": "python-tests",
            "title": "Python Test Fixing",
            "hash": "sha256:test",
            "activated_at": "2026-03-27T00:00:00Z",
            "source": "model",
        }
    ]

    store.save(session)
    reloaded = store.open(locator={"id": "session-a"})

    assert reloaded.active_skills[0]["source"] == "model"


def test_filesystem_store_round_trips_reasoning_artifacts(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)
    manager = ContextManager(
        store=store,
        strategy=SimpleHistoryContextStrategy(),
    )
    session = manager.open()

    manager.record_tool_result(
        session,
        turn_id="turn-1",
        tool_call={
            "id": "tool-1",
            "name": "think",
            "arguments": {"prompt": "plan the fix"},
        },
        output=ToolExecutionResult(
            name="think",
            display_command="think",
            model_output="[think result]",
            output_text="ship it",
            reasoning_content="cot",
            metadata={"final_content": "ship it"},
        ),
    )
    store.save(session)

    reopened = store.open(locator={"id": session.session_id})
    artifact = next(iter(reopened.artifacts.values()))

    assert artifact["reasoning_content"] == "cot"


def test_session_meta_includes_active_skills(tmp_path):
    session = Session(
        session_id="session-1",
        root=tmp_path,
        active_skills=[
            {
                "name": "python-tests",
                "title": "Python Test Fixing",
                "hash": "sha256:test",
                "activated_at": "2026-03-27T00:00:00Z",
                "source": "user",
            }
        ],
    )

    assert session.meta()["active_skills"][0]["name"] == "python-tests"


def test_filesystem_store_save_is_atomic_when_write_fails(tmp_path, monkeypatch):
    store = FileSystemSessionStore(root=tmp_path)
    session = store.open()
    session.append({"role": "user", "content": "before"})
    session.events.append({"type": "turn_started", "turn_id": "turn-1"})
    store.save(session)

    session.append({"role": "assistant", "content": "after"})
    session.events.append(
        {"type": "message_committed", "role": "assistant", "text": "after"}
    )

    original_messages = (
        tmp_path / "sessions" / session.session_id / "messages.jsonl"
    ).read_text()
    original_events = (
        tmp_path / "sessions" / session.session_id / "events.jsonl"
    ).read_text()

    real_write_text = Path.write_text

    def flaky_write(self, data, *args, **kwargs):
        if self.name.startswith("events.jsonl"):
            raise OSError("simulated write failure")
        return real_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write)

    with pytest.raises(OSError, match="simulated write failure"):
        store.save(session)

    reopened = store.open(locator={"id": session.session_id})

    assert reopened.messages == [{"role": "user", "content": "before"}]
    assert reopened.events == [{"type": "turn_started", "turn_id": "turn-1"}]
    assert (
        tmp_path / "sessions" / session.session_id / "messages.jsonl"
    ).read_text() == original_messages
    assert (
        tmp_path / "sessions" / session.session_id / "events.jsonl"
    ).read_text() == original_events
