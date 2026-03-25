from deep_coder.cli import resolve_launch_context


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
