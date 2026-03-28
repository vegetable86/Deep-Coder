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


def test_discover_sources_prunes_generated_and_dependency_directories(tmp_path, monkeypatch):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "README.md").write_text("# Vendored\n")
    (workspace / ".venv").mkdir()
    (workspace / ".venv" / "README.md").write_text("# Virtualenv\n")
    (workspace / "README.md").write_text("# Demo\n")

    service = DeepFileService(
        workspace=workspace,
        state_dir=tmp_path / ".deepcode" / "projects" / "demo",
    )

    original_is_file = Path.is_file

    def guarded_is_file(path: Path):
        if "node_modules/README.md" in path.as_posix() or ".venv/README.md" in path.as_posix():
            raise AssertionError(f"ignored path was inspected: {path}")
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", guarded_is_file)

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


def test_refresh_generates_repo_specific_editing_guide(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "README.md").write_text(
        "# Demo\n\n"
        "The current product is the package runtime under `demo_pkg/` plus the `demo` launcher.\n"
        "`legacy_runner.py` remains in the repository as a legacy prototype and reference file, not the main entrypoint.\n"
    )
    (workspace / "pyproject.toml").write_text(
        "[project]\n"
        "name = 'demo'\n\n"
        "[project.scripts]\n"
        "demo = \"demo_pkg.cli:main\"\n"
    )
    (workspace / "pytest.ini").write_text("[pytest]\n")
    (workspace / "demo").write_text("#!/usr/bin/env bash\n")
    package_dir = workspace / "demo_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("")
    (package_dir / "cli.py").write_text("def main():\n    return 0\n")
    (package_dir / "main.py").write_text("def build():\n    return 0\n")
    tests_dir = workspace / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_demo.py").write_text("def test_demo():\n    assert True\n")

    service = DeepFileService(
        workspace=workspace,
        state_dir=tmp_path / ".deepcode" / "projects" / "demo",
    )

    service.refresh()

    deep_file = (workspace / "DEEP.md").read_text()
    assert "## Project Map" in deep_file
    assert "## Start Here" in deep_file
    assert "## Common Edits" in deep_file
    assert "## Verification" in deep_file
    assert "## Boundaries" in deep_file
    assert "TODO:" not in deep_file
    assert "`demo`" in deep_file
    assert "`demo_pkg/cli.py`" in deep_file
    assert "`demo_pkg/`" in deep_file
    assert "`tests/`" in deep_file
    assert "`python3 -m pytest -q`" in deep_file
    assert "`legacy_runner.py`" in deep_file


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


def test_refresh_migrates_unmanaged_deep_file_into_single_human_notes_section(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n")
    (workspace / "DEEP.md").write_text(
        "# Existing notes\n\n"
        "## Human Notes\n\n"
        "Keep this\n"
    )

    service = DeepFileService(
        workspace=workspace,
        state_dir=tmp_path / ".deepcode" / "projects" / "demo",
    )

    service.refresh()

    deep_file = (workspace / "DEEP.md").read_text()
    assert deep_file.count("## Human Notes") == 1
    assert "Keep this" in deep_file


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
