# TUI Command System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated slash-command subsystem to the Deep Coder TUI with global model persistence, project-scoped history access, idle-only built-in commands, and a compact single-line usage block.

**Architecture:** Extend the existing `ProjectRegistry` config file to round-trip a global `default_model`, thread that value into runtime construction, and add a new `deep_coder/tui/commands/` subsystem that owns parsing, filtering, command availability, and command execution results. Keep `DeepCodeApp` focused on UI state, palette rendering, and applying structured command results from the command layer.

**Tech Stack:** Python 3, Textual, Rich, pytest, stdlib filesystem APIs, existing Deep Coder runtime modules

**Execution Notes:** Follow `@test-driven-development` and `@verification-before-completion` throughout. If Textual keyboard handling or screen transitions become unclear, stop and use `@systematic-debugging`.

---

### Task 1: Persist the global default model in the existing registry config

**Files:**
- Modify: `deep_coder/projects/registry.py`
- Modify: `deep_coder/config.py`
- Modify: `deep_coder/main.py`
- Modify: `deep_coder/cli.py`
- Test: `tests/projects/test_registry.py`
- Test: `tests/test_main.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing tests**

```python
def test_registry_round_trips_default_model(tmp_path):
    root = tmp_path / ".deepcode"
    workspace = (tmp_path / "workspace").resolve()
    workspace.mkdir()
    registry = ProjectRegistry(root=root)

    registry.set_default_model("deepseek-reasoner")
    registry.open_workspace(workspace)

    reloaded = ProjectRegistry(root=root)
    assert reloaded.default_model() == "deepseek-reasoner"
```

```python
def test_build_runtime_uses_explicit_model_name(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    project = ProjectRecord(
        path=tmp_path,
        name="repo",
        key="repo-abc123",
        state_dir=tmp_path / ".deepcode" / "projects" / "repo-abc123",
        last_opened_at="2026-03-26T00:00:00Z",
    )

    runtime = build_runtime(project=project, model_name="deepseek-reasoner")

    assert runtime["config"].model_name == "deepseek-reasoner"
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/projects/test_registry.py tests/test_main.py tests/test_cli.py -q`
Expected: FAIL because the registry does not yet persist `default_model` and runtime construction does not accept a model override

**Step 3: Write the minimal implementation**

```python
class ProjectRegistry:
    def default_model(self) -> str | None:
        return self._load().get("default_model")

    def set_default_model(self, model_name: str) -> None:
        data = self._load()
        data["default_model"] = model_name
        self._save(data)
```

```python
def build_runtime(..., model_name: str | None = None) -> dict:
    config = RuntimeConfig.from_project(project, model_name=model_name)
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/projects/test_registry.py tests/test_main.py tests/test_cli.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/projects/registry.py deep_coder/config.py deep_coder/main.py deep_coder/cli.py tests/projects/test_registry.py tests/test_main.py tests/test_cli.py
git commit -m "feat: persist global default model"
```

### Task 2: Add the command parser and registry contracts

**Files:**
- Create: `deep_coder/tui/commands/__init__.py`
- Create: `deep_coder/tui/commands/base.py`
- Create: `deep_coder/tui/commands/parser.py`
- Create: `deep_coder/tui/commands/registry.py`
- Create: `deep_coder/tui/commands/builtin/__init__.py`
- Test: `tests/tui/test_commands.py`

**Step 1: Write the failing tests**

```python
from deep_coder.tui.commands.parser import parse_command_text


def test_parse_command_text_extracts_name_and_args():
    parsed = parse_command_text("/model deepseek-chat")

    assert parsed.is_command is True
    assert parsed.name == "model"
    assert parsed.args == "deepseek-chat"
```

```python
from deep_coder.tui.commands.registry import CommandRegistry


def test_registry_filters_commands_by_prefix():
    registry = CommandRegistry.with_builtin_commands()

    matches = registry.match("/hi")

    assert [match.name for match in matches] == ["history"]
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_commands.py -q`
Expected: FAIL because the command package does not exist

**Step 3: Write the minimal implementation**

```python
@dataclass(frozen=True)
class ParsedCommand:
    is_command: bool
    name: str
    args: str
```

```python
class CommandRegistry:
    def match(self, composer_text: str) -> list[CommandMatch]:
        parsed = parse_command_text(composer_text)
        ...
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_commands.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tui/commands/__init__.py deep_coder/tui/commands/base.py deep_coder/tui/commands/parser.py deep_coder/tui/commands/registry.py deep_coder/tui/commands/builtin/__init__.py tests/tui/test_commands.py
git commit -m "feat: add tui command registry"
```

### Task 3: Implement built-in `/model`, `/history`, and `/exit`

**Files:**
- Create: `deep_coder/tui/commands/builtin/model.py`
- Create: `deep_coder/tui/commands/builtin/history.py`
- Create: `deep_coder/tui/commands/builtin/exit.py`
- Modify: `deep_coder/tui/commands/base.py`
- Modify: `deep_coder/tui/commands/registry.py`
- Test: `tests/tui/test_commands.py`

**Step 1: Write the failing tests**

```python
def test_history_command_returns_only_active_project_sessions(fake_runtime, fake_project):
    registry = CommandRegistry.with_builtin_commands()

    result = registry.execute(
        "/history",
        runtime=fake_runtime,
        project=fake_project,
        session_id=None,
        turn_state="idle",
    )

    assert [item["id"] for item in result.list_items] == ["session-a", "session-b"]
```

```python
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
```

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_commands.py -q`
Expected: FAIL because builtin commands and execution results do not exist yet

**Step 3: Write the minimal implementation**

```python
if turn_state != "idle":
    return CommandResult(
        warning_message="system now in runtime, please wait for the work end"
    )
```

```python
runtime["registry"].set_default_model(model_name)
runtime["config"].model_name = model_name
runtime["model"].config.model_name = model_name
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_commands.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tui/commands/base.py deep_coder/tui/commands/registry.py deep_coder/tui/commands/builtin/model.py deep_coder/tui/commands/builtin/history.py deep_coder/tui/commands/builtin/exit.py tests/tui/test_commands.py
git commit -m "feat: add built-in tui commands"
```

### Task 4: Add the command palette screen and composer integration

**Files:**
- Create: `deep_coder/tui/screens/command_palette.py`
- Modify: `deep_coder/tui/screens/__init__.py`
- Modify: `deep_coder/tui/app.py`
- Modify: `deep_coder/tui/styles.tcss`
- Test: `tests/tui/test_app_layout.py`
- Test: `tests/tui/test_live_events.py`
- Test: `tests/tui/test_session_switcher.py`

**Step 1: Write the failing tests**

```python
async with app.run_test(size=(120, 40)) as pilot:
    composer = app.query_one("#composer")
    composer.text = "/"
    await pilot.pause()
    assert app.screen.query_one("#command-palette")
```

```python
async with app.run_test(size=(120, 40)) as pilot:
    composer = app.query_one("#composer")
    composer.text = "/hi"
    await pilot.pause()
    await pilot.press("tab")
    assert composer.text == "/history"
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_app_layout.py tests/tui/test_live_events.py tests/tui/test_session_switcher.py -q`
Expected: FAIL because there is no command palette or slash-command integration

**Step 3: Write the minimal implementation**

```python
if composer.text.startswith("/"):
    matches = self._command_registry.match(composer.text)
    self._show_command_palette(matches)
```

```python
if event.key == "tab" and self.app.in_command_mode:
    self.app.action_complete_command()
    return
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_app_layout.py tests/tui/test_live_events.py tests/tui/test_session_switcher.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tui/screens/command_palette.py deep_coder/tui/screens/__init__.py deep_coder/tui/app.py deep_coder/tui/styles.tcss tests/tui/test_app_layout.py tests/tui/test_live_events.py tests/tui/test_session_switcher.py
git commit -m "feat: integrate slash command palette"
```

### Task 5: Wire `/history` into project-scoped session switching

**Files:**
- Modify: `deep_coder/tui/screens/session_switcher.py`
- Modify: `deep_coder/tui/app.py`
- Test: `tests/tui/test_session_switcher.py`

**Step 1: Write the failing tests**

```python
async with app.run_test(size=(120, 40)) as pilot:
    composer = app.query_one("#composer")
    composer.text = "/history"
    await pilot.press("enter")
    overlay = app.screen.query_one("#session-switcher")
    labels = [option.prompt for option in overlay.options]
    assert labels == ["session-a", "session-b"]
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_session_switcher.py -q`
Expected: FAIL because `/history` does not yet open the session list

**Step 3: Write the minimal implementation**

```python
if result.list_items:
    self.push_screen(SessionSwitcher(result.list_items), self._on_session_selected)
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_session_switcher.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tui/screens/session_switcher.py deep_coder/tui/app.py tests/tui/test_session_switcher.py
git commit -m "feat: open history from slash commands"
```

### Task 6: Simplify usage rendering to one compact line

**Files:**
- Modify: `deep_coder/tui/render.py`
- Modify: `tests/tui/conftest.py`
- Modify: `tests/tui/test_render.py`
- Modify: `tests/tui/test_live_events.py`
- Modify: `tests/tui/test_session_switcher.py`

**Step 1: Write the failing tests**

```python
from deep_coder.tui.render import render_usage_block


def test_usage_block_renders_on_one_line():
    block = render_usage_block(
        {
            "prompt_tokens": 10,
            "total_tokens": 15,
            "cache_hit_tokens": 3,
            "cache_miss_tokens": 7,
        }
    )

    assert block.plain == "prompt 10 | usage 15 | hit 3 | miss 7"
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_render.py tests/tui/test_live_events.py tests/tui/test_session_switcher.py -q`
Expected: FAIL because usage still renders as multiple long-form lines

**Step 3: Write the minimal implementation**

```python
def render_usage_block(usage: dict) -> Text:
    return Text(
        f"prompt {usage.get('prompt_tokens', 0)} | "
        f"usage {usage.get('total_tokens', 0)} | "
        f"hit {usage.get('cache_hit_tokens', 0)} | "
        f"miss {usage.get('cache_miss_tokens', 0)}",
        style="magenta",
    )
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest tests/tui/test_render.py tests/tui/test_live_events.py tests/tui/test_session_switcher.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tui/render.py tests/tui/conftest.py tests/tui/test_render.py tests/tui/test_live_events.py tests/tui/test_session_switcher.py
git commit -m "feat: simplify tui usage block"
```

### Task 7: Run the full verification suite

**Files:**
- Verify only: `tests/`

**Step 1: Run the full test suite**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`
Expected: PASS with all tests green

**Step 2: Review the final diff**

Run: `git status --short`
Expected: Only the planned TUI command and config changes are present

**Step 3: Commit**

```bash
git add deep_coder docs/plans tests
git commit -m "feat: add tui slash command system"
```
