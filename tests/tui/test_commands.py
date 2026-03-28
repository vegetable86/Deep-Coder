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


def test_registry_lists_skills_command():
    registry = CommandRegistry.with_builtin_commands()

    matches = registry.match("/")

    assert "skills" in [match.name for match in matches]


def test_registry_lists_init_command():
    registry = CommandRegistry.with_builtin_commands()

    matches = registry.match("/")

    assert "init" in [match.name for match in matches]


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


def test_skills_command_completes_only_list_and_show_subcommands(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()

    matches = registry.match(
        "/skills ",
        runtime=fake_runtime,
        project=fake_project,
        session_id="session-a",
        turn_state="idle",
    )

    assert [match.name for match in matches] == ["list", "show"]


def test_skills_command_lists_available_skills(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()
    (fake_runtime["config"].skills_dir / "javascript-tests.md").write_text(
        "---\n"
        "name: javascript-tests\n"
        "title: JavaScript Test Fixing\n"
        "summary: Use when diagnosing jest failures.\n"
        "---\n\n"
        "Skill body.\n"
    )

    session = fake_runtime["context"].open(locator={"id": "session-a"})
    session.active_skills.append({"name": "python-tests"})

    result = registry.execute(
        "/skills",
        runtime=fake_runtime,
        project=fake_project,
        session_id="session-a",
        turn_state="idle",
    )

    assert result.list_kind == "skills"
    assert result.status_message is None
    assert [(item["name"], item["is_active"]) for item in result.list_items] == [
        ("javascript-tests", False),
        ("python-tests", True),
    ]


def test_skills_show_returns_all_skills_for_browsing(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()
    (fake_runtime["config"].skills_dir / "javascript-tests.md").write_text(
        "---\n"
        "name: javascript-tests\n"
        "title: JavaScript Test Fixing\n"
        "summary: Use when diagnosing jest failures.\n"
        "---\n\n"
        "JavaScript skill body.\n"
    )

    result = registry.execute(
        "/skills show",
        runtime=fake_runtime,
        project=fake_project,
        session_id="session-a",
        turn_state="idle",
    )

    assert result.list_kind == "skills_show"
    assert [(item["name"], item["body"]) for item in result.list_items] == [
        ("javascript-tests", "JavaScript skill body.\n"),
        ("python-tests", "Skill body.\n"),
    ]


def test_skills_command_rejects_removed_use_subcommand(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()

    result = registry.execute(
        "/skills use python-tests",
        runtime=fake_runtime,
        project=fake_project,
        session_id="session-a",
        turn_state="idle",
    )

    assert result.warning_message == "unknown /skills subcommand: use"


def test_init_command_refreshes_deep_file(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()
    (fake_project.path / "README.md").write_text("# Demo\n")

    result = registry.execute(
        "/init",
        runtime=fake_runtime,
        project=fake_project,
        session_id=None,
        turn_state="idle",
    )

    assert result.warning_message is None
    assert result.status_message == "DEEP.md refreshed"
    assert (fake_project.path / "DEEP.md").exists()


def test_init_command_warns_when_generation_fails(fake_runtime, fake_project, monkeypatch):
    registry = CommandRegistry.with_builtin_commands()

    def raise_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("deep_coder.tui.commands.builtin.init.DeepFileService.refresh", raise_error)

    result = registry.execute(
        "/init",
        runtime=fake_runtime,
        project=fake_project,
        session_id=None,
        turn_state="idle",
    )

    assert result.warning_message == "failed to refresh DEEP.md: boom"
