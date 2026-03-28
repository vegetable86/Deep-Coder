# Init Command Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a built-in `/init` command that scans the active workspace and creates or refreshes a concise `DEEP.md` editing guide plus lightweight init metadata under the project state directory.

**Architecture:** Add a small project-level guide service under `deep_coder/projects/` so repo scanning, `DEEP.md` rendering, and refresh metadata stay outside the TUI. Wire that service into a new built-in `/init` command that reuses the existing command registry and returns a short status message without changing harness behavior.

**Tech Stack:** Python 3, Textual, pytest, stdlib `json`, stdlib `pathlib`, stdlib `fnmatch`

**Execution Notes:** Follow `@test-driven-development` and `@verification-before-completion`. Keep the scan workspace-bounded and do not let the new feature mutate `AGENTS.md`.

---

### Task 1: Add workspace-bounded source discovery for `DEEP.md`

**Files:**
- Create: `deep_coder/projects/deepfile.py`
- Modify: `deep_coder/projects/__init__.py`
- Test: `tests/projects/test_deepfile.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

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
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/projects/test_deepfile.py -q`
Expected: FAIL because `deep_coder.projects.deepfile` does not exist

**Step 3: Write the minimal implementation**

```python
from dataclasses import dataclass
from pathlib import Path


PRIORITY_PATTERNS = (
    "DEEP.md",
    "README*",
    "CONTRIBUTING*",
    "docs/**",
    "arch/**",
    "pyproject.toml",
    "package.json",
    "pytest.ini",
    "Makefile",
)
IGNORE_DIR_NAMES = {".git", "node_modules", ".venv", "venv", "dist", "build", ".next"}


@dataclass(frozen=True)
class DeepFileSource:
    relative_path: str
    category: str


@dataclass(frozen=True)
class DiscoveryResult:
    sources: list[DeepFileSource]


class DeepFileService:
    def __init__(self, *, workspace: Path, state_dir: Path):
        self.workspace = Path(workspace).resolve()
        self.state_dir = Path(state_dir)

    def discover_sources(self) -> DiscoveryResult:
        discovered: list[DeepFileSource] = []
        for path in sorted(self.workspace.rglob("*")):
            if path.is_dir() and path.name in IGNORE_DIR_NAMES:
                continue
            if not path.is_file():
                continue
            rel = path.relative_to(self.workspace).as_posix()
            if _is_priority_match(rel):
                discovered.append(DeepFileSource(relative_path=rel, category=_category(rel)))
        discovered.sort(key=lambda source: _priority_key(source.relative_path))
        return DiscoveryResult(sources=discovered)
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/projects/test_deepfile.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/projects/__init__.py deep_coder/projects/deepfile.py tests/projects/test_deepfile.py
git commit -m "feat: add init source discovery"
```

### Task 2: Render and refresh `DEEP.md` while preserving manual notes

**Files:**
- Modify: `deep_coder/projects/deepfile.py`
- Test: `tests/projects/test_deepfile.py`

**Step 1: Write the failing tests**

```python
import json

from deep_coder.projects.deepfile import DeepFileService


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
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/projects/test_deepfile.py -q`
Expected: FAIL because `DeepFileService` does not yet render or persist refresh output

**Step 3: Write the minimal implementation**

```python
from dataclasses import dataclass
from datetime import datetime, timezone
import json


START_MARKER = "<!-- deepcode:init:start -->"
END_MARKER = "<!-- deepcode:init:end -->"


@dataclass(frozen=True)
class RefreshResult:
    changed: bool
    source_paths: list[str]
    deep_file_path: Path


class DeepFileService:
    def refresh(self) -> RefreshResult:
        discovery = self.discover_sources()
        rendered_block = self._render_generated_block(discovery)
        deep_file_path = self.workspace / "DEEP.md"
        existing = deep_file_path.read_text() if deep_file_path.exists() else ""
        updated = _merge_generated_block(existing, rendered_block)
        deep_file_path.write_text(updated)
        self._write_state(discovery.sources, deep_file_path)
        return RefreshResult(
            changed=updated != existing,
            source_paths=[source.relative_path for source in discovery.sources],
            deep_file_path=deep_file_path,
        )

    def _write_state(self, sources: list[DeepFileSource], deep_file_path: Path) -> None:
        state_path = self.state_dir / "deep" / "init-state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "last_refreshed_at": datetime.now(timezone.utc).isoformat(),
                    "workspace_path": str(self.workspace),
                    "deep_file_path": str(deep_file_path),
                    "sources": [source.relative_path for source in sources],
                },
                indent=2,
            )
        )
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/projects/test_deepfile.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/projects/deepfile.py tests/projects/test_deepfile.py
git commit -m "feat: generate DEEP.md editing guide"
```

### Task 3: Add the `/init` built-in command and registry wiring

**Files:**
- Create: `deep_coder/tui/commands/builtin/init.py`
- Modify: `deep_coder/tui/commands/registry.py`
- Test: `tests/tui/test_commands.py`

**Step 1: Write the failing tests**

```python
def test_registry_lists_init_command():
    registry = CommandRegistry.with_builtin_commands()

    matches = registry.match("/")

    assert "init" in [match.name for match in matches]


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
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_commands.py -q`
Expected: FAIL because the `/init` command does not exist

**Step 3: Write the minimal implementation**

```python
from deep_coder.projects.deepfile import DeepFileService
from deep_coder.tui.commands.base import CommandBase, CommandResult


class InitCommand(CommandBase):
    name = "init"
    summary = "Generate or refresh DEEP.md for this workspace"

    def execute(self, context, args: str) -> CommandResult:
        service = DeepFileService(
            workspace=context.project.path,
            state_dir=context.project.state_dir,
        )
        try:
            service.refresh()
        except Exception as exc:
            return CommandResult(warning_message=f"failed to refresh DEEP.md: {exc}")
        return CommandResult(status_message="DEEP.md refreshed")
```

```python
class CommandRegistry:
    @classmethod
    def with_builtin_commands(cls):
        return cls(
            [
                InitCommand(),
                ModelCommand(),
                HistoryCommand(),
                SessionCommand(),
                SkillsCommand(),
                ExitCommand(),
            ]
        )
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_commands.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tui/commands/builtin/init.py deep_coder/tui/commands/registry.py tests/tui/test_commands.py
git commit -m "feat: add init command"
```

### Task 4: Cover command-palette and app-level `/init` behavior

**Files:**
- Modify: `tests/tui/test_app_layout.py`
- Modify: `tests/tui/conftest.py`

**Step 1: Write the failing tests**

```python
def test_slash_palette_lists_init_command(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            composer = app.query_one("#composer")
            composer.text = "/"
            await app.run_action("refresh_command_palette")
            palette = app.query_one("#command-palette")
            labels = [option.prompt for option in palette.options]
            assert "/init" in labels

    asyncio.run(run())


def test_init_command_updates_status_strip_and_writes_file(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        (fake_project.path / "README.md").write_text("# Demo\n")

        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "/init"
            await app.run_action("refresh_command_palette")
            await pilot.press("enter")

            status = render_widget_text(app.query_one("#status-strip"))
            assert "DEEP.md refreshed" in status
            assert (fake_project.path / "DEEP.md").exists()

    asyncio.run(run())
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_app_layout.py -q`
Expected: FAIL because the palette and app flow do not yet know about `/init`

**Step 3: Write the minimal implementation**

```python
@pytest.fixture
def fake_project(tmp_path: Path) -> ProjectRecord:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_dir = tmp_path / ".deepcode" / "projects" / "workspace-abc123"
    state_dir.mkdir(parents=True)
    return ProjectRecord(
        path=workspace,
        name="workspace",
        key="workspace-abc123",
        state_dir=state_dir,
        last_opened_at="2026-03-28T00:00:00Z",
    )
```

No TUI production code should be required beyond the command registration if the command returns a normal `CommandResult`.

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_app_layout.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/tui/conftest.py tests/tui/test_app_layout.py
git commit -m "test: cover init command in tui"
```

### Task 5: Run full verification and record the feature docs

**Files:**
- Modify: `docs/plans/2026-03-28-init-command-design.md`
- Modify: `docs/plans/2026-03-28-init-command.md`

**Step 1: Run focused verification**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/projects/test_deepfile.py tests/tui/test_commands.py tests/tui/test_app_layout.py -q`
Expected: PASS

**Step 2: Run full verification**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`
Expected: PASS with no regressions

**Step 3: Review generated files and docs**

```bash
git diff -- deep_coder/projects/deepfile.py deep_coder/tui/commands/builtin/init.py deep_coder/tui/commands/registry.py tests/projects/test_deepfile.py tests/tui/test_commands.py tests/tui/test_app_layout.py docs/plans/2026-03-28-init-command-design.md docs/plans/2026-03-28-init-command.md
```

Expected: Diff shows only the project guide service, `/init` command wiring, tests, and the approved docs

**Step 4: Commit final documentation updates**

```bash
git add docs/plans/2026-03-28-init-command-design.md docs/plans/2026-03-28-init-command.md
git commit -m "docs: add init command design and plan"
```
