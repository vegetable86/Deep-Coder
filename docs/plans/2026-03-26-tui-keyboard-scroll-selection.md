# TUI Keyboard Scroll And Terminal Selection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Disable app mouse capture for normal terminal text selection, add keyboard focus switching for the timeline, speed up timeline arrow-key scrolling, and render markdown headings in the TUI.

**Architecture:** Keep the current TUI structure but introduce a focusable timeline scroll subclass with faster line-step actions and explicit focus helpers on `DeepCodeApp`. Limit mouse disabling to the real CLI launch path, and extend the existing markdown-lite parser with a heading branch rather than switching to a full markdown renderer.

**Tech Stack:** Python 3, Textual, Rich, pytest, existing Deep Coder TUI modules

**Execution Notes:** Follow `@test-driven-development` and `@verification-before-completion`. Use `/home/wys/Deep-Coder/.venv/bin/pytest -q` for verification in this repository.

---

### Task 1: Add failing tests for headings and keyboard focus flow

**Files:**
- Modify: `tests/tui/test_render.py`
- Modify: `tests/tui/test_app_layout.py`
- Modify: `tests/tui/test_live_events.py`

**Step 1: Write the failing tests**

```python
def test_message_blocks_render_headings_without_raw_hashes():
    block = render_message_block(role="assistant", text="### Title\nbody")
    rendered = render_plain_text(block)
    assert "Title" in rendered
    assert "###" not in rendered
```

```python
def test_timeline_focus_action_moves_focus_from_composer(fake_runtime, fake_project):
    ...
    await app.run_action("focus_timeline")
    assert app.query_one("#timeline-scroll").has_focus is True
```

```python
def test_escape_returns_focus_to_composer_from_timeline(fake_runtime, fake_project):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_app_layout.py`
Expected: FAIL because headings are still raw and there is no explicit timeline focus action

**Step 3: Write the minimal implementation**

```python
class TimelineScroll(VerticalScroll):
    ...
```

```python
def action_focus_timeline(self) -> None:
    self.query_one("#timeline-scroll").focus()
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_app_layout.py`
Expected: PASS

### Task 2: Speed up keyboard-only timeline scrolling

**Files:**
- Modify: `deep_coder/tui/app.py`
- Modify: `tests/tui/test_live_events.py`
- Modify: `tests/tui/test_app_layout.py`

**Step 1: Write the failing test**

```python
def test_timeline_arrow_keys_scroll_multiple_lines_when_focused(fake_runtime, fake_project):
    ...
    await app.run_action("focus_timeline")
    start_scroll_y = timeline_scroll.scroll_y
    await pilot.press("down")
    assert timeline_scroll.scroll_y >= start_scroll_y + 3
```

**Step 2: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_live_events.py::test_timeline_arrow_keys_scroll_multiple_lines_when_focused`
Expected: FAIL because the default `VerticalScroll` only scrolls one line per keypress

**Step 3: Write the minimal implementation**

```python
class TimelineScroll(VerticalScroll):
    LINE_SCROLL_STEP = 4

    def action_scroll_down(self) -> None:
        self.scroll_to(y=self.scroll_target_y + self.LINE_SCROLL_STEP, immediate=True)
```

```python
def action_scroll_up(self) -> None:
    self.scroll_to(y=self.scroll_target_y - self.LINE_SCROLL_STEP, immediate=True)
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_live_events.py tests/tui/test_app_layout.py`
Expected: PASS

### Task 3: Disable mouse in the real launcher path

**Files:**
- Modify: `deep_coder/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
def test_main_runs_app_with_mouse_disabled(monkeypatch):
    ...
    assert run_calls == [{"mouse": False}]
```

**Step 2: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/test_cli.py::test_main_runs_app_with_mouse_disabled`
Expected: FAIL because `DeepCodeApp.run()` is still called with default mouse behavior

**Step 3: Write the minimal implementation**

```python
def main() -> int:
    project, runtime = resolve_launch_context()
    DeepCodeApp(runtime=runtime, project=project).run(mouse=False)
    return 0
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/test_cli.py`
Expected: PASS

### Task 4: Run verification and finalize

**Files:**
- Modify: `deep_coder/cli.py`
- Modify: `deep_coder/tui/app.py`
- Modify: `deep_coder/tui/render.py`
- Modify: `tests/tui/test_render.py`
- Modify: `tests/tui/test_app_layout.py`
- Modify: `tests/tui/test_live_events.py`
- Modify: `tests/test_cli.py`

**Step 1: Run targeted tests**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_app_layout.py tests/tui/test_live_events.py tests/test_cli.py`
Expected: PASS

**Step 2: Run full TUI suite**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui`
Expected: PASS

**Step 3: Run full suite**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q`
Expected: PASS
