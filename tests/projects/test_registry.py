import tomllib

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


def test_registry_round_trips_default_model(tmp_path):
    root = tmp_path / ".deepcode"
    workspace = (tmp_path / "workspace").resolve()
    workspace.mkdir()
    registry = ProjectRegistry(root=root)

    registry.set_default_model("deepseek-reasoner")
    registry.open_workspace(workspace)

    reloaded = ProjectRegistry(root=root)

    assert reloaded.default_model() == "deepseek-reasoner"


def test_registry_round_trips_global_context_settings(tmp_path):
    root = tmp_path / ".deepcode"
    registry = ProjectRegistry(root=root)

    registry.set_context_settings(
        {
            "context_recent_turns": 5,
            "context_working_token_budget": 7000,
            "context_max_tokens": 96000,
            "context_summary_max_tokens": 900,
        }
    )

    reloaded = ProjectRegistry(root=root)

    assert reloaded.context_settings() == {
        "context_recent_turns": 5,
        "context_working_token_budget": 7000,
        "context_max_tokens": 96000,
        "context_summary_max_tokens": 900,
    }


def test_registry_preserves_web_search_tables_when_updating_projects(tmp_path):
    root = tmp_path / ".deepcode"
    workspace = (tmp_path / "workspace").resolve()
    workspace.mkdir()
    root.mkdir()
    (root / "config.toml").write_text(
        "\n".join(
            [
                '[web_search]',
                'provider = "serper"',
                "",
                "[web_search.serper]",
                'api_key = "serper-key"',
                "",
            ]
        )
    )
    registry = ProjectRegistry(root=root)

    project = registry.open_workspace(workspace)

    assert project.path == workspace

    saved = tomllib.loads((root / "config.toml").read_text())
    assert saved["web_search"]["provider"] == "serper"
    assert saved["web_search"]["serper"]["api_key"] == "serper-key"
    assert saved["projects"][0]["path"] == str(workspace)
