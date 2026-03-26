# TUI Session Command Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a lazy `/session` slash command that clears the TUI timeline immediately and defers actual new-session creation until the next non-command prompt.

**Architecture:** Extend the TUI command result contract with a reset-session action, add a new builtin `SessionCommand`, and keep all visible state resets inside `DeepCodeApp`. Do not change context persistence semantics; the next harness run should continue to create the real session when `session_id` is `None`.

**Tech Stack:** Python 3, Textual, pytest, existing Deep Coder TUI command subsystem

**Execution Notes:** Follow `@test-driven-development` and `@verification-before-completion`. Use `/home/wys/Deep-Coder/.venv/bin/pytest -q` for verification in this repository.

---

### Task 1: Add failing tests for the new command contract

**Files:**
- Modify: `tests/tui/test_commands.py`
- Modify: `tests/tui/test_app_layout.py`
- Modify: `tests/tui/conftest.py`

**Step 1: Write the failing tests**

```python
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
```

```python
def test_session_command_clears_loaded_timeline(fake_runtime, fake_project):
    ...
    app.load_session("session-a")
    composer.text = "/session"
    await pilot.press("enter")

    assert app.session_id is None
    assert render_widget_text(app.query_one("#timeline")) == ""
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_commands.py tests/tui/test_app_layout.py`
Expected: FAIL because `/session` does not exist yet and the app cannot apply a reset action

**Step 3: Write the minimal implementation**

```python
@dataclass
class CommandResult:
    ...
    reset_session: bool = False
```

```python
class SessionCommand(CommandBase):
    name = "session"
    summary = "Start a new empty session"

    def execute(self, context, args: str) -> CommandResult:
        return CommandResult(status_message="new session", reset_session=True)
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_commands.py tests/tui/test_app_layout.py`
Expected: PASS

### Task 2: Verify lazy new-session creation behavior

**Files:**
- Modify: `tests/tui/conftest.py`
- Modify: `tests/tui/test_app_layout.py`

**Step 1: Write the failing test**

```python
def test_next_prompt_after_session_command_uses_new_session_locator(fake_runtime, fake_project):
    ...
    composer.text = "/session"
    await pilot.press("enter")
    composer.text = "follow up"
    await pilot.press("enter")

    assert fake_runtime["harness"].calls[-1]["session_locator"] is None
```

**Step 2: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_app_layout.py::test_next_prompt_after_session_command_uses_new_session_locator`
Expected: FAIL because the fake harness does not record calls yet or the app does not reset the active session

**Step 3: Write the minimal implementation**

```python
def _reset_session_view(self) -> None:
    self.session_id = None
    self._timeline_blocks.clear()
    self._turn_state = "idle"
    self._refresh_timeline()
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_app_layout.py`
Expected: PASS

### Task 3: Run final verification

**Files:**
- Modify: `deep_coder/tui/app.py`
- Modify: `deep_coder/tui/commands/base.py`
- Modify: `deep_coder/tui/commands/registry.py`
- Modify: `deep_coder/tui/commands/builtin/__init__.py`
- Create: `deep_coder/tui/commands/builtin/session.py`

**Step 1: Run targeted tests**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_commands.py tests/tui/test_app_layout.py`
Expected: PASS

**Step 2: Run full suite**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q`
Expected: PASS
