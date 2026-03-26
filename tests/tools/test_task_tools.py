from deep_coder.config import RuntimeConfig
from deep_coder.context.session import Session
from deep_coder.tools.registry import ToolRegistry


def test_task_create_tool_updates_session_and_returns_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    registry = ToolRegistry.from_builtin(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
    )
    session = Session(session_id="session-a", root=tmp_path)

    result = registry.execute("task_create", {"subject": "inspect repo"}, session=session)

    assert session.tasks[0]["subject"] == "inspect repo"
    assert result.timeline_events[0]["type"] == "task_snapshot"


def test_task_update_rejects_self_dependency(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    registry = ToolRegistry.from_builtin(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
    )
    session = Session(session_id="session-a", root=tmp_path)

    registry.execute("task_create", {"subject": "inspect repo"}, session=session)
    result = registry.execute(
        "task_update",
        {"task_id": 1, "add_blocks": [1]},
        session=session,
    )

    assert result.is_error is True
    assert "self" in result.output_text
