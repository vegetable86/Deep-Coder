from deep_coder.config import RuntimeConfig
from deep_coder.tools.registry import ToolRegistry


def test_registry_returns_builtin_tool_schemas(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path)

    registry = ToolRegistry.from_builtin(config=config, workdir=tmp_path)

    names = [schema["function"]["name"] for schema in registry.schemas()]

    assert names == ["bash", "read_file", "write_file", "edit_file"]
