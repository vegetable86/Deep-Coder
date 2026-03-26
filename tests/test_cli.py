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
