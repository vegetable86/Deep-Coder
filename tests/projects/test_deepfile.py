from pathlib import Path
import json

from deep_coder.projects.deepfile import DeepFileService


def test_discover_sources_does_not_require_agents_file(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n")
    (workspace / "pyproject.toml").write_text("[project]\nname = 'demo'\n")

    service = DeepFileService(
        workspace=workspace,
        state_dir=tmp_path / ".deepcode" / "projects" / "demo",
    )

    result = service.discover_sources()

    assert "README.md" in [source.relative_path for source in result.sources]
    assert "AGENTS.md" not in [source.relative_path for source in result.sources]


def test_discover_sources_ignores_generated_and_dependency_directories(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "ignore.js").write_text("console.log('x')\n")
    (workspace / ".venv").mkdir()
    (workspace / ".venv" / "pyvenv.cfg").write_text("home = /tmp\n")
    (workspace / "README.md").write_text("# Demo\n")

    service = DeepFileService(
        workspace=workspace,
        state_dir=tmp_path / ".deepcode" / "projects" / "demo",
    )

    result = service.discover_sources()

    assert all("node_modules/" not in source.relative_path for source in result.sources)
    assert all(".venv/" not in source.relative_path for source in result.sources)


def test_discover_sources_stays_inside_active_workspace(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workspace = repo_root / "packages" / "app"
    workspace.mkdir(parents=True)
    (repo_root / "README.md").write_text("# Root docs\n")
    (workspace / "README.md").write_text("# App docs\n")

    service = DeepFileService(
        workspace=workspace,
        state_dir=tmp_path / ".deepcode" / "projects" / "app",
    )

    result = service.discover_sources()

    assert [source.relative_path for source in result.sources] == ["README.md"]


def test_refresh_writes_generated_block_and_human_notes_scaffold(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n")

    service = DeepFileService(
        workspace=workspace,
        state_dir=tmp_path / ".deepcode" / "projects" / "demo",
    )

    result = service.refresh()

    deep_file = (workspace / "DEEP.md").read_text()
    assert "<!-- deepcode:init:start -->" in deep_file
    assert "## Human Notes" in deep_file
    assert result.changed is True


def test_refresh_replaces_only_generated_block(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n")
    (workspace / "DEEP.md").write_text(
        "# DEEP.md\n\n"
        "<!-- deepcode:init:start -->\nold block\n<!-- deepcode:init:end -->\n\n"
        "## Human Notes\nkeep me\n"
    )

    service = DeepFileService(
        workspace=workspace,
        state_dir=tmp_path / ".deepcode" / "projects" / "demo",
    )

    service.refresh()

    deep_file = (workspace / "DEEP.md").read_text()
    assert "old block" not in deep_file
    assert "keep me" in deep_file


def test_refresh_persists_init_metadata(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n")

    state_dir = tmp_path / ".deepcode" / "projects" / "demo"
    service = DeepFileService(workspace=workspace, state_dir=state_dir)

    service.refresh()

    payload = json.loads((state_dir / "deep" / "init-state.json").read_text())
    assert payload["workspace_path"] == str(workspace)
    assert payload["deep_file_path"] == str(workspace / "DEEP.md")
    assert "README.md" in payload["sources"]