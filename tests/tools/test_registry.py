from deep_coder.config import RuntimeConfig
from deep_coder.tools.result import ToolExecutionResult
from deep_coder.tools.registry import ToolRegistry


def test_registry_returns_builtin_tool_schemas(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path)

    registry = ToolRegistry.from_builtin(config=config, workdir=tmp_path)

    names = [schema["function"]["name"] for schema in registry.schemas()]

    assert names == [
        "bash",
        "read_file",
        "write_file",
        "edit_file",
        "think",
        "task_create",
        "task_update",
        "task_list",
        "task_get",
        "search_history",
        "load_history_artifacts",
        "load_skill",
    ]


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


def test_registry_executes_load_skill_and_returns_tool_result(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    state_dir = tmp_path / ".deepcode"
    skills_dir = state_dir / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "python-tests.md").write_text(
        "---\n"
        "name: python-tests\n"
        "title: Python Test Fixing\n"
        "summary: Use when diagnosing pytest failures.\n"
        "---\n\n"
        "Skill body.\n"
    )
    registry = ToolRegistry.from_builtin(
        config=RuntimeConfig.from_env(workdir=tmp_path, state_dir=state_dir),
        workdir=tmp_path,
    )
    session = type("Session", (), {"active_skills": []})()

    result = registry.execute(
        "load_skill",
        {"name": "python-tests"},
        session=session,
    )

    assert result.name == "load_skill"
    assert result.is_error is False
    assert "python-tests" in result.model_output
    assert session.active_skills[0]["name"] == "python-tests"


def test_registry_executes_think_and_returns_reasoning_result(
    tmp_path, monkeypatch
):
    class FakeThinkTool:
        def __init__(self, config, workdir):
            self.config = config
            self.workdir = workdir

        def schema(self):
            return {
                "type": "function",
                "function": {
                    "name": "think",
                    "description": "Think through a prompt.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"},
                        },
                        "required": ["prompt"],
                    },
                },
            }

        def exec(self, arguments, session=None):
            result = ToolExecutionResult(
                name="think",
                display_command="think",
                model_output='{"final_answer":"ship it"}',
                output_text="ship it",
            )
            result.reasoning_content = "step by step"
            result.metadata = {"final_content": "ship it"}
            return result

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("deep_coder.tools.registry.ThinkTool", FakeThinkTool, raising=False)
    registry = ToolRegistry.from_builtin(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
    )
    session = type("Session", (), {})()

    result = registry.execute("think", {"prompt": "plan the fix"}, session=session)

    assert result.name == "think"
    assert getattr(result, "reasoning_content", None) == "step by step"
    assert "final_answer" in result.model_output


def test_registry_wraps_think_failures_as_tool_errors(tmp_path, monkeypatch):
    class RaisingThinkTool:
        def __init__(self, config, workdir):
            self.config = config
            self.workdir = workdir

        def schema(self):
            return {
                "type": "function",
                "function": {
                    "name": "think",
                    "description": "Think through a prompt.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"},
                        },
                        "required": ["prompt"],
                    },
                },
            }

        def exec(self, arguments, session=None):
            raise RuntimeError("reasoner unavailable")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        "deep_coder.tools.registry.ThinkTool",
        RaisingThinkTool,
        raising=False,
    )
    registry = ToolRegistry.from_builtin(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
    )
    session = type("Session", (), {})()

    result = registry.execute("think", {"prompt": "plan the fix"}, session=session)

    assert result.is_error is True
    assert result.output_text == "reasoner unavailable"
