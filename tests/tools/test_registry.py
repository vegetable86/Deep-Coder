from deep_coder.config import RuntimeConfig
from deep_coder.tools.registry import ToolRegistry


def test_registry_returns_builtin_tool_schemas(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path)

    registry = ToolRegistry.from_builtin(config=config, workdir=tmp_path)

    names = [schema["function"]["name"] for schema in registry.schemas()]

    assert names == ["bash", "read_file", "write_file", "edit_file"]


def test_registry_returns_display_command_and_diff_for_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    registry = ToolRegistry.from_builtin(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
    )
    (tmp_path / "notes.txt").write_text("hello world\n")

    result = registry.execute(
        "edit_file",
        {"path": "notes.txt", "old_text": "world", "new_text": "runtime"},
    )

    assert result.display_command == "edit_file notes.txt"
    assert "@@" in result.diff_text
    assert "-hello world" in result.diff_text
    assert "+hello runtime" in result.diff_text
