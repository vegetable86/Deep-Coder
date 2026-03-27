from deep_coder.config import RuntimeConfig
from deep_coder.context.session import Session
from deep_coder.tools.registry import ToolRegistry


def test_search_history_returns_summary_hits_before_raw_evidence(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    registry = ToolRegistry.from_builtin(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
    )
    session = Session(session_id="session-a", root=tmp_path)
    session.summaries = [
        {
            "summary_id": "sum-1",
            "covered_event_ids": ["evt-1"],
            "goal": "inspect repo entrypoint",
            "files": ["cli.py"],
        }
    ]
    session.evidence = [
        {
            "evidence_id": "evd-1",
            "event_id": "evt-1",
            "role": "assistant",
            "content": "cli.py is the app entrypoint",
            "artifact_id": None,
        }
    ]

    result = registry.execute(
        "search_history",
        {"query": "repo entrypoint"},
        session=session,
    )

    lines = result.model_output.splitlines()
    assert lines[0].startswith("Summary sum-1")
    assert "cli.py" in result.model_output
    assert "Evidence evd-1" in result.model_output


def test_load_history_artifacts_returns_exact_evidence_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    registry = ToolRegistry.from_builtin(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
    )
    session = Session(session_id="session-a", root=tmp_path)
    session.artifacts["art-1"] = {
        "tool_call_id": "tool-1",
        "tool_name": "bash",
        "arguments": {"command": "tree ."},
        "model_output": "tree output",
        "output_text": "tree output",
        "display_command": "bash: tree .",
        "diff_text": None,
        "is_error": False,
    }
    session.evidence = [
        {
            "evidence_id": "evd-1",
            "event_id": "evt-1",
            "role": "tool",
            "content": "tree output",
            "artifact_id": "art-1",
        }
    ]

    result = registry.execute(
        "load_history_artifacts",
        {"artifact_ids": ["art-1"]},
        session=session,
    )

    assert "art-1" in result.model_output
    assert "tree ." in result.model_output
    assert "tree output" in result.model_output
