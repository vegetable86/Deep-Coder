from deep_coder.tui.commands.parser import parse_command_text
from deep_coder.tui.commands.registry import CommandRegistry


def test_parse_command_text_extracts_name_and_args():
    parsed = parse_command_text("/model deepseek-chat")

    assert parsed.is_command is True
    assert parsed.name == "model"
    assert parsed.args == "deepseek-chat"


def test_registry_filters_commands_by_prefix():
    registry = CommandRegistry.with_builtin_commands()

    matches = registry.match("/hi")

    assert [match.name for match in matches] == ["history"]


def test_session_command_returns_reset_action(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()

    result = registry.execute(
        "/session",
        runtime=fake_runtime,
        project=fake_project,
        session_id="session-a",
        turn_state="idle",
    )

    assert result.reset_session is True
    assert result.status_message == "new session"


def test_model_command_lists_provider_models(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()

    matches = registry.match(
        "/model ",
        runtime=fake_runtime,
        project=fake_project,
        session_id="session-a",
        turn_state="idle",
    )

    assert [match.name for match in matches] == ["deepseek-chat", "deepseek-reasoner"]


def test_model_command_filters_provider_models_by_prefix(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()

    matches = registry.match(
        "/model deepseek-r",
        runtime=fake_runtime,
        project=fake_project,
        session_id="session-a",
        turn_state="idle",
    )

    assert [match.name for match in matches] == ["deepseek-reasoner"]


def test_history_command_returns_only_active_project_sessions(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()

    result = registry.execute(
        "/history",
        runtime=fake_runtime,
        project=fake_project,
        session_id=None,
        turn_state="idle",
    )

    assert [(item["id"], item["preview"]) for item in result.list_items] == [
        ("session-a", "make dir aa"),
        ("session-b", "show history selector preview"),
    ]


def test_exit_command_warns_while_running(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()

    result = registry.execute(
        "/exit",
        runtime=fake_runtime,
        project=fake_project,
        session_id="session-a",
        turn_state="running",
    )

    assert result.warning_message == "system now in runtime, please wait for the work end"
    assert result.should_exit is False


def test_model_command_updates_runtime_and_registry(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()

    result = registry.execute(
        "/model deepseek-reasoner",
        runtime=fake_runtime,
        project=fake_project,
        session_id="session-a",
        turn_state="idle",
    )

    assert result.updated_model_name == "deepseek-reasoner"
    assert fake_runtime["config"].model_name == "deepseek-reasoner"
    assert fake_runtime["registry"].default_model() == "deepseek-reasoner"
