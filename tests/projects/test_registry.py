from deep_coder.projects.registry import ProjectRegistry


def test_registry_registers_workspace_and_sets_current_project(tmp_path):
    root = tmp_path / ".deepcode"
    workspace = (tmp_path / "workspace").resolve()
    workspace.mkdir()
    registry = ProjectRegistry(root=root)

    project = registry.open_workspace(workspace)

    assert project.path == workspace
    assert project.name == "workspace"
    assert project.state_dir == root / "projects" / project.key
    assert registry.current_project().path == workspace


def test_registry_reuses_existing_project_for_same_workspace(tmp_path):
    root = tmp_path / ".deepcode"
    workspace = (tmp_path / "workspace").resolve()
    workspace.mkdir()
    registry = ProjectRegistry(root=root)

    first = registry.open_workspace(workspace)
    second = registry.open_workspace(workspace)

    assert second.key == first.key
