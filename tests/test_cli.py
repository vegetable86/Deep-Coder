import deep_coder.cli as cli_module
from deep_coder.cli import resolve_launch_context
from deep_coder.projects.registry import ProjectRegistry


def test_cli_uses_pwd_to_select_project(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    workspace = tmp_path / "repo"
    workspace.mkdir()
    registry_root = tmp_path / ".deepcode"

    project, runtime = resolve_launch_context(
        cwd=workspace,
        registry_root=registry_root,
    )

    assert project.path == workspace.resolve()
    assert runtime["config"].project_key == project.key


def test_cli_loads_default_model_from_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    workspace = tmp_path / "repo"
    workspace.mkdir()
    registry_root = tmp_path / ".deepcode"
    registry = ProjectRegistry(root=registry_root)
    registry.set_default_model("deepseek-reasoner")

    project, runtime = resolve_launch_context(
        cwd=workspace,
        registry_root=registry_root,
    )

    assert project.path == workspace.resolve()
    assert runtime["config"].model_name == "deepseek-reasoner"
    assert runtime["registry"].default_model() == "deepseek-reasoner"


def test_cli_uses_registry_root_for_global_skills(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    workspace = tmp_path / "repo"
    workspace.mkdir()
    registry_root = tmp_path / ".deepcode"

    project, runtime = resolve_launch_context(
        cwd=workspace,
        registry_root=registry_root,
    )

    assert project.path == workspace.resolve()
    assert runtime["config"].skills_dir == registry_root / "skills"


def test_cli_loads_global_context_settings_from_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    workspace = tmp_path / "repo"
    workspace.mkdir()
    registry_root = tmp_path / ".deepcode"
    registry = ProjectRegistry(root=registry_root)
    registry.set_context_settings(
        {
            "context_recent_turns": 5,
            "context_working_token_budget": 7000,
            "context_max_tokens": 96000,
            "context_summary_max_tokens": 900,
        }
    )

    project, runtime = resolve_launch_context(
        cwd=workspace,
        registry_root=registry_root,
    )

    assert project.path == workspace.resolve()
    assert runtime["config"].context_recent_turns == 5
    assert runtime["config"].context_working_token_budget == 7000
    assert runtime["config"].context_max_tokens == 96000
    assert runtime["config"].context_summary_max_tokens == 900


def test_main_runs_app_with_mouse_disabled(monkeypatch):
    run_calls = []

    class FakeApp:
        def __init__(self, runtime, project):
            self.runtime = runtime
            self.project = project

        def run(self, **kwargs):
            run_calls.append(kwargs)

    fake_project = object()
    fake_runtime = {"config": object()}

    monkeypatch.setattr(
        cli_module,
        "resolve_launch_context",
        lambda: (fake_project, fake_runtime),
    )
    monkeypatch.setattr(cli_module, "DeepCodeApp", FakeApp)

    result = cli_module.main()

    assert result == 0
    assert run_calls == [{"mouse": False}]
