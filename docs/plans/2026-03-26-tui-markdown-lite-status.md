# TUI Markdown-Lite And Busy Status Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Render markdown-lite for chat messages in the TUI and add a slow breathing effect to the status strip only while the agent is busy.

**Architecture:** Move the timeline from one flat `Static` into a block container so message events can mount richer renderables without changing harness events. Keep tool and usage events on the current simple render path, and isolate the breathing effect inside a dedicated status widget that reacts to turn-state changes.

**Tech Stack:** Python 3, Textual, Rich, pytest, existing Deep Coder TUI modules

**Execution Notes:** Follow `@test-driven-development` and `@verification-before-completion`. Use `/home/wys/Deep-Coder/.venv/bin/pytest -q` in this repository.

---

### Task 1: Add failing render and status tests

**Files:**
- Modify: `tests/tui/test_render.py`
- Modify: `tests/tui/test_app_layout.py`
- Modify: `tests/tui/test_live_events.py`

**Step 1: Write the failing tests**

```python
def test_message_blocks_render_markdown_lite_markup():
    block = render_message_block(
        role="assistant",
        text="**bold** `code`\n- item\n> note\n```py\nprint('x')\n```",
    )

    plain = renderable_plain_text(block)
    assert "bold" in plain
    assert "item" in plain
    assert "note" in plain
    assert "print('x')" in plain
```

```python
def test_status_widget_animates_only_while_busy(fake_runtime, fake_project):
    app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
    ...
    app._turn_state = "running"
    app._update_status_strip()
    assert app.query_one("#status-strip").has_class("busy")
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_app_layout.py tests/tui/test_live_events.py`
Expected: FAIL because message rendering is still plain text and the status strip is still a raw `Static`

**Step 3: Write the minimal implementation**

```python
def render_message_block(role: str, text: str):
    return MessageBlock(role=role, text=text)
```

```python
class StatusStrip(Static):
    def set_state(...):
        ...
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_app_layout.py tests/tui/test_live_events.py`
Expected: PASS

### Task 2: Refactor the timeline to mount per-event blocks

**Files:**
- Modify: `deep_coder/tui/app.py`
- Modify: `deep_coder/tui/render.py`
- Modify: `deep_coder/tui/styles.tcss`
- Modify: `tests/tui/test_session_switcher.py`
- Modify: `tests/tui/test_live_events.py`

**Step 1: Write the failing test**

```python
def test_loaded_session_replays_markdown_message_blocks(fake_runtime, fake_project):
    session = fake_runtime["context"].open({"id": "session-a"})
    session.events = [
        {"type": "message_committed", "role": "assistant", "text": "- item\n> note"},
    ]
    ...
    assert "item" in render_widget_text(app.query_one("#timeline"))
```

**Step 2: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_session_switcher.py tests/tui/test_live_events.py`
Expected: FAIL because the flat timeline renderer cannot mount richer message blocks

**Step 3: Write the minimal implementation**

```python
with VerticalScroll(id="timeline-scroll"):
    yield Vertical(id="timeline")
```

```python
def _refresh_timeline(...):
    timeline = self.query_one("#timeline")
    timeline.remove_children()
    for block in self._timeline_blocks:
        timeline.mount(block)
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_session_switcher.py tests/tui/test_live_events.py`
Expected: PASS

### Task 3: Implement markdown-lite parsing and breathing animation polish

**Files:**
- Modify: `deep_coder/tui/render.py`
- Modify: `deep_coder/tui/app.py`
- Modify: `deep_coder/tui/styles.tcss`
- Modify: `tests/tui/test_render.py`
- Modify: `tests/tui/test_app_layout.py`

**Step 1: Write the failing tests**

```python
def test_message_blocks_preserve_code_fences_and_quotes():
    ...
```

```python
def test_status_widget_returns_to_static_style_when_idle(fake_runtime, fake_project):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_app_layout.py`
Expected: FAIL because markdown-lite coverage is incomplete and busy styling does not shut off cleanly

**Step 3: Write the minimal implementation**

```python
def parse_markdown_lite(text: str) -> list[RenderableType]:
    ...
```

```python
def set_busy(self, is_busy: bool) -> None:
    ...
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_app_layout.py`
Expected: PASS

### Task 4: Run verification and finalize

**Files:**
- Modify: `deep_coder/tui/app.py`
- Modify: `deep_coder/tui/render.py`
- Modify: `deep_coder/tui/styles.tcss`
- Modify: `tests/tui/test_render.py`
- Modify: `tests/tui/test_app_layout.py`
- Modify: `tests/tui/test_live_events.py`
- Modify: `tests/tui/test_session_switcher.py`

**Step 1: Run targeted TUI tests**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui`
Expected: PASS

**Step 2: Run full suite**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q`
Expected: PASS
