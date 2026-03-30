# ask_user Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `ask_user` tool that lets the model pause a turn, present the user with one or more questions (each with selectable options + free-form "Other"), and block until the user responds via an inline TUI widget.

**Architecture:** The tool writes a `question_asked` JSON event directly to `sys.stdout` then blocks on `sys.stdin.readline()`. The TUI receives the event, renders a `QuestionWidget` inline in the timeline, and writes the answer back to the subprocess stdin pipe. `TurnSubprocess` keeps stdin open for the turn lifetime and gains a `write_answer()` method.

**Tech Stack:** Python stdlib (`threading`, `sys`, `json`), Textual (OptionList, TextArea, Widget, Message), existing `ToolBase` / `ToolExecutionResult` patterns.

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `deep_coder/tools/ask_user/__init__.py` | package marker |
| Create | `deep_coder/tools/ask_user/tool.py` | `AskUserTool` implementation |
| Modify | `deep_coder/tools/registry.py` | register `AskUserTool` |
| Modify | `deep_coder/harness/turn_subprocess.py` | keep stdin open; add `write_answer()` |
| Create | `deep_coder/tui/widgets/__init__.py` | package marker |
| Create | `deep_coder/tui/widgets/question_widget.py` | `QuestionWidget` Textual widget |
| Modify | `deep_coder/tui/app.py` | handle `question_asked` event; lock Composer; wire widget |
| Modify | `deep_coder/tui/render.py` | add `render_question_asked_block()` for replay |
| Create | `tests/tools/test_ask_user_tool.py` | unit tests for tool |
| Create | `tests/harness/test_ask_user_subprocess.py` | subprocess stdin/answer tests |
| Create | `tests/tui/test_question_widget.py` | widget unit tests |
| Modify | `tests/tui/test_live_events.py` | integration test for question_asked TUI flow |
| Modify | `tests/tui/test_render.py` | test render_question_asked_block |

---

## Task 1: ask_user tool — failing tests

**Files:**
- Create: `tests/tools/test_ask_user_tool.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tools/test_ask_user_tool.py
import json
import sys
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from deep_coder.tools.ask_user.tool import AskUserTool


def _make_tool():
    return AskUserTool(config=SimpleNamespace(), workdir="/tmp")


def _run_tool(questions, stdin_answer):
    tool = _make_tool()
    fake_stdin = StringIO(json.dumps({"answers": stdin_answer}) + "\n")
    fake_stdout = StringIO()
    with patch("sys.stdin", fake_stdin), patch("sys.stdout", fake_stdout):
        result = tool.exec({"questions": questions})
    return result, fake_stdout.getvalue()


def test_ask_user_tool_schema_has_questions_array():
    tool = _make_tool()
    schema = tool.schema()
    assert schema["function"]["name"] == "ask_user"
    props = schema["function"]["parameters"]["properties"]
    assert "questions" in props
    assert props["questions"]["type"] == "array"


def test_ask_user_tool_emits_question_asked_event_to_stdout():
    questions = [{"question": "Pick one", "options": [{"label": "A", "description": "first"}]}]
    _, stdout = _run_tool(questions, {"Pick one": "A"})
    event = json.loads(stdout.strip().splitlines()[0])
    assert event["type"] == "question_asked"
    assert event["questions"][0]["question"] == "Pick one"


def test_ask_user_tool_appends_other_option_to_each_question():
    questions = [{"question": "Pick one", "options": [{"label": "A", "description": "first"}]}]
    _, stdout = _run_tool(questions, {"Pick one": "A"})
    event = json.loads(stdout.strip().splitlines()[0])
    labels = [o["label"] for o in event["questions"][0]["options"]]
    assert "Other" in labels


def test_ask_user_tool_returns_answers_as_output_text():
    questions = [{"question": "Pick one", "options": [{"label": "A", "description": "first"}]}]
    result, _ = _run_tool(questions, {"Pick one": "A"})
    answers = json.loads(result.output_text)
    assert answers == {"Pick one": "A"}


def test_ask_user_tool_supports_multiple_questions():
    questions = [
        {"question": "Q1", "options": [{"label": "Yes", "description": ""}]},
        {"question": "Q2", "options": [{"label": "No", "description": ""}]},
    ]
    result, _ = _run_tool(questions, {"Q1": "Yes", "Q2": "No"})
    answers = json.loads(result.output_text)
    assert answers == {"Q1": "Yes", "Q2": "No"}


def test_ask_user_tool_returns_error_on_malformed_stdin():
    tool = _make_tool()
    questions = [{"question": "Q", "options": [{"label": "A", "description": ""}]}]
    fake_stdin = StringIO("not json\n")
    fake_stdout = StringIO()
    with patch("sys.stdin", fake_stdin), patch("sys.stdout", fake_stdout):
        result = tool.exec({"questions": questions})
    assert result.is_error is True
```

- [ ] **Step 2: Run to confirm red**

```bash
./.venv/bin/pytest tests/tools/test_ask_user_tool.py -q
```
Expected: `ModuleNotFoundError: No module named 'deep_coder.tools.ask_user'`

---

## Task 2: ask_user tool — implementation

**Files:**
- Create: `deep_coder/tools/ask_user/__init__.py`
- Create: `deep_coder/tools/ask_user/tool.py`

- [ ] **Step 1: Create package marker**

```python
# deep_coder/tools/ask_user/__init__.py
```
(empty file)

- [ ] **Step 2: Write tool implementation**

```python
# deep_coder/tools/ask_user/tool.py
import json
import sys
from pathlib import Path

from deep_coder.tools.base import ToolBase
from deep_coder.tools.result import ToolExecutionResult

_OTHER_OPTION = {"label": "Other", "description": "Type your own answer"}


class AskUserTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = Path(workdir)

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        questions = arguments["questions"]
        questions_with_other = [
            {**q, "options": list(q["options"]) + [_OTHER_OPTION]}
            for q in questions
        ]
        event = {"type": "question_asked", "questions": questions_with_other}
        sys.stdout.write(json.dumps(event) + "\n")
        sys.stdout.flush()

        raw = sys.stdin.readline()
        try:
            payload = json.loads(raw)
            answers = payload["answers"]
        except Exception as exc:
            error_text = f"error: malformed answer payload: {exc}"
            return ToolExecutionResult(
                name="ask_user",
                display_command="ask_user",
                model_output=error_text,
                output_text=error_text,
                is_error=True,
            )

        output = json.dumps(answers)
        return ToolExecutionResult(
            name="ask_user",
            display_command="ask_user",
            model_output=output,
            output_text=output,
        )

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "ask_user",
                "description": (
                    "Pause the turn and ask the user one or more questions. "
                    "Each question has a list of options; the user may also type a custom answer. "
                    "Returns a JSON object mapping each question to the user's chosen answer."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "questions": {
                            "type": "array",
                            "description": "List of questions to ask.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {
                                        "type": "string",
                                        "description": "The question text.",
                                    },
                                    "options": {
                                        "type": "array",
                                        "description": "Selectable options.",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "label": {"type": "string"},
                                                "description": {"type": "string"},
                                            },
                                            "required": ["label", "description"],
                                        },
                                    },
                                },
                                "required": ["question", "options"],
                            },
                        }
                    },
                    "required": ["questions"],
                },
            },
        }
```

- [ ] **Step 3: Run tests — expect green**

```bash
./.venv/bin/pytest tests/tools/test_ask_user_tool.py -q
```
Expected: `6 passed`

- [ ] **Step 4: Commit**

```bash
git add deep_coder/tools/ask_user/ tests/tools/test_ask_user_tool.py
git commit -m "feat: add ask_user tool with stdin/stdout blocking protocol"
```

---

## Task 3: Register tool + subprocess stdin changes — failing tests

**Files:**
- Create: `tests/harness/test_ask_user_subprocess.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/harness/test_ask_user_subprocess.py
import json
import time
from types import SimpleNamespace

from deep_coder.context.manager import ContextManager
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore
from deep_coder.context.strategies.simple_history.strategy import SimpleHistoryContextStrategy
from deep_coder.harness.deepcoder.harness import DeepCoderHarness
from deep_coder.harness.turn_subprocess import start_turn_subprocess, TurnSubprocess
from deep_coder.projects.registry import ProjectRecord
from deep_coder.prompts.deepcoder.prompt import DeepCoderPrompt
from deep_coder.tools.registry import ToolRegistry


def _project_record(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_dir = tmp_path / ".deepcode" / "projects" / "repo-abc123"
    state_dir.mkdir(parents=True)
    return ProjectRecord(
        path=workspace,
        name="workspace",
        key="repo-abc123",
        state_dir=state_dir,
        last_opened_at="2026-03-30T00:00:00Z",
    )


class _AskUserModel:
    """Model that calls ask_user once then finishes."""
    def __init__(self):
        self.calls = 0

    def complete(self, request):
        self.calls += 1
        if self.calls == 1:
            return {
                "content": None,
                "tool_calls": [{
                    "id": "tool-1",
                    "name": "ask_user",
                    "arguments": {
                        "questions": [{
                            "question": "Which approach?",
                            "options": [
                                {"label": "Option A", "description": "fast"},
                                {"label": "Option B", "description": "slow"},
                            ],
                        }]
                    },
                }],
                "usage": None,
                "finish_reason": "tool_calls",
                "raw_response": None,
            }
        return {
            "content": "done",
            "tool_calls": [],
            "usage": None,
            "finish_reason": "stop",
            "raw_response": None,
        }


def build_ask_user_runtime(*, project, model_name):
    prompt = DeepCoderPrompt(config=SimpleNamespace(workdir=project.path))
    context = ContextManager(
        store=FileSystemSessionStore(
            root=project.state_dir,
            project_key=project.key,
            workspace_path=project.path,
        ),
        strategy=SimpleHistoryContextStrategy(),
    )
    harness = DeepCoderHarness(
        config=SimpleNamespace(),
        model=_AskUserModel(),
        prompt=prompt,
        context=context,
        tools=ToolRegistry.from_builtin(
            config=SimpleNamespace(
                workdir=project.path,
                skills_dir=project.state_dir / "skills",
            ),
            workdir=project.path,
        ),
    )
    return {"harness": harness}


def test_turn_subprocess_write_answer_sends_to_stdin(tmp_path):
    project = _project_record(tmp_path)
    turn = start_turn_subprocess(
        project=project,
        model_name="deepseek-chat",
        session_id=None,
        user_input="ask me something",
        runtime_factory="tests.harness.test_ask_user_subprocess:build_ask_user_runtime",
    )

    try:
        events = []
        deadline = time.time() + 10
        question_event = None
        while time.time() < deadline:
            event = turn.read_event(timeout=0.2)
            if event is not None:
                events.append(event)
                if event["type"] == "question_asked":
                    question_event = event
                    break
            if turn.poll() is not None:
                break

        assert question_event is not None, f"no question_asked event, got: {[e['type'] for e in events]}"
        assert question_event["questions"][0]["question"] == "Which approach?"

        # Answer the question
        turn.write_answer(json.dumps({"answers": {"Which approach?": "Option A"}}))

        # Collect remaining events
        deadline = time.time() + 5
        while time.time() < deadline:
            event = turn.read_event(timeout=0.2)
            if event is not None:
                events.append(event)
            if turn.poll() is not None:
                break

        event_types = [e["type"] for e in events]
        assert "turn_finished" in event_types
        assert turn.wait(timeout=2) == 0
    finally:
        turn.close()


def test_ask_user_tool_registered_in_tool_registry(tmp_path):
    project = _project_record(tmp_path)
    registry = ToolRegistry.from_builtin(
        config=SimpleNamespace(workdir=project.path, skills_dir=project.state_dir / "skills"),
        workdir=project.path,
    )
    names = [s["function"]["name"] for s in registry.schemas()]
    assert "ask_user" in names
```

- [ ] **Step 2: Run to confirm red**

```bash
./.venv/bin/pytest tests/harness/test_ask_user_subprocess.py -q
```
Expected: failures — `ask_user` not in registry, `write_answer` not on `TurnSubprocess`

---

## Task 4: Register tool + subprocess write_answer — implementation

**Files:**
- Modify: `deep_coder/tools/registry.py`
- Modify: `deep_coder/harness/turn_subprocess.py`

- [ ] **Step 1: Register AskUserTool in registry**

In `deep_coder/tools/registry.py`, add import at top with other tool imports:
```python
from deep_coder.tools.ask_user.tool import AskUserTool
```

In `ToolRegistry.from_builtin()`, add after `SkillLoadTool(...)`:
```python
AskUserTool(config=config, workdir=workdir),
```

- [ ] **Step 2: Keep stdin open and add write_answer to TurnSubprocess**

In `deep_coder/harness/turn_subprocess.py`, in `start_turn_subprocess()`, remove the line:
```python
process.stdin.close()
```
(stdin must stay open so the tool can read answers)

Add `write_answer` method to `TurnSubprocess` class after `interrupt()`:
```python
def write_answer(self, answer_json: str) -> None:
    if self._process.stdin is None or self._process.stdin.closed:
        return
    self._process.stdin.write(answer_json + "\n")
    self._process.stdin.flush()
```

Also update `close()` to close stdin if not already closed. The existing `close()` body already handles this — it checks `not self._process.stdin.closed` before closing. No change needed.

- [ ] **Step 3: Run tests — expect green**

```bash
./.venv/bin/pytest tests/harness/test_ask_user_subprocess.py -q
```
Expected: `2 passed`

- [ ] **Step 4: Run full suite to check no regressions**

```bash
./.venv/bin/pytest -q
```
Expected: all previously passing tests still pass

- [ ] **Step 5: Commit**

```bash
git add deep_coder/tools/registry.py deep_coder/harness/turn_subprocess.py tests/harness/test_ask_user_subprocess.py
git commit -m "feat: register ask_user tool and add write_answer to TurnSubprocess"
```

---

## Task 5: render_question_asked_block — failing test

**Files:**
- Modify: `tests/tui/test_render.py`

- [ ] **Step 1: Add failing test**

Add to `tests/tui/test_render.py`:
```python
from deep_coder.tui.render import render_question_asked_block

def test_render_question_asked_block_shows_questions_and_answers():
    block = render_question_asked_block({
        "questions": [
            {
                "question": "Which approach?",
                "options": [
                    {"label": "Option A", "description": "fast"},
                    {"label": "Option B", "description": "slow"},
                    {"label": "Other", "description": "Type your own answer"},
                ],
                "answer": "Option A",
            }
        ]
    })
    text = render_plain_text(block)
    assert "Which approach?" in text
    assert "Option A" in text
```

- [ ] **Step 2: Run to confirm red**

```bash
./.venv/bin/pytest tests/tui/test_render.py::test_render_question_asked_block_shows_questions_and_answers -q
```
Expected: `ImportError` — `render_question_asked_block` not defined

---

## Task 6: render_question_asked_block — implementation

**Files:**
- Modify: `deep_coder/tui/render.py`

- [ ] **Step 1: Read current render.py to find insertion point**

Read `deep_coder/tui/render.py` and locate the end of the file.

- [ ] **Step 2: Add render_question_asked_block**

Add at the end of `deep_coder/tui/render.py`:
```python
def render_question_asked_block(event: dict) -> Text:
    lines = []
    for q in event.get("questions", []):
        lines.append(f"? {q['question']}")
        answer = q.get("answer")
        if answer:
            lines.append(f"  > {answer}")
        else:
            for opt in q.get("options", []):
                desc = f" — {opt['description']}" if opt.get("description") else ""
                lines.append(f"  • {opt['label']}{desc}")
    return Text("\n".join(lines))
```

- [ ] **Step 3: Run test — expect green**

```bash
./.venv/bin/pytest tests/tui/test_render.py -q
```
Expected: all render tests pass

- [ ] **Step 4: Commit**

```bash
git add deep_coder/tui/render.py tests/tui/test_render.py
git commit -m "feat: add render_question_asked_block for session replay"
```

---

## Task 7: QuestionWidget — failing tests

**Files:**
- Create: `tests/tui/test_question_widget.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tui/test_question_widget.py
import asyncio

import pytest

from deep_coder.tui.widgets.question_widget import QuestionWidget
from tests.tui.conftest import render_widget_text


SAMPLE_QUESTIONS = [
    {
        "question": "Which approach?",
        "options": [
            {"label": "Option A", "description": "fast"},
            {"label": "Option B", "description": "slow"},
            {"label": "Other", "description": "Type your own answer"},
        ],
    }
]


def test_question_widget_renders_question_text(fake_runtime, fake_project):
    async def run():
        from textual.app import App, ComposeResult

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield QuestionWidget(SAMPLE_QUESTIONS)

        async with TestApp().run_test(size=(80, 20)) as pilot:
            text = render_widget_text(pilot.app.query_one(QuestionWidget))
            assert "Which approach?" in text
            assert "Option A" in text
            assert "Option B" in text
            assert "Other" in text

    asyncio.run(run())


def test_question_widget_selecting_option_emits_answered_message(fake_runtime, fake_project):
    async def run():
        from textual.app import App, ComposeResult

        answered = []

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield QuestionWidget(SAMPLE_QUESTIONS)

            def on_question_widget_answered(self, message: QuestionWidget.Answered):
                answered.append(message.answers)

        async with TestApp().run_test(size=(80, 20)) as pilot:
            # Select first option (Option A) and submit
            await pilot.press("down")  # highlight Option A
            await pilot.press("enter")  # select it / submit
            await pilot.pause()
            assert len(answered) == 1
            assert answered[0]["Which approach?"] == "Option A"

    asyncio.run(run())


def test_question_widget_other_option_reveals_text_input(fake_runtime, fake_project):
    async def run():
        from textual.app import App, ComposeResult
        from textual.widgets import TextArea

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield QuestionWidget(SAMPLE_QUESTIONS)

        async with TestApp().run_test(size=(80, 20)) as pilot:
            widget = pilot.app.query_one(QuestionWidget)
            # Select "Other" option (index 2)
            option_list = widget.query("OptionList").first()
            option_list.highlighted = 2
            await pilot.press("enter")
            await pilot.pause()
            # TextArea should now be visible
            text_areas = widget.query(TextArea)
            assert len(text_areas) > 0

    asyncio.run(run())
```

- [ ] **Step 2: Run to confirm red**

```bash
./.venv/bin/pytest tests/tui/test_question_widget.py -q
```
Expected: `ModuleNotFoundError: No module named 'deep_coder.tui.widgets'`

---

## Task 8: QuestionWidget — implementation

**Files:**
- Create: `deep_coder/tui/widgets/__init__.py`
- Create: `deep_coder/tui/widgets/question_widget.py`

- [ ] **Step 1: Create package marker**

```python
# deep_coder/tui/widgets/__init__.py
```
(empty file)

- [ ] **Step 2: Write QuestionWidget**

```python
# deep_coder/tui/widgets/question_widget.py
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, OptionList, TextArea
from textual.widgets.option_list import Option


class QuestionWidget(Widget):
    """Inline widget rendered in the timeline when ask_user is called."""

    class Answered(Message):
        def __init__(self, answers: dict[str, str]) -> None:
            self.answers = answers
            super().__init__()

    def __init__(self, questions: list[dict]) -> None:
        super().__init__()
        self._questions = questions
        # Track per-question state: selected label or None
        self._selections: list[str | None] = [None] * len(questions)
        self._other_active: list[bool] = [False] * len(questions)

    def compose(self) -> ComposeResult:
        for idx, q in enumerate(self._questions):
            yield Label(f"? {q['question']}", id=f"q-label-{idx}")
            yield OptionList(
                *[Option(f"{o['label']}  {o['description']}", id=f"q{idx}-opt{i}")
                  for i, o in enumerate(q["options"])],
                id=f"q-list-{idx}",
            )
            ta = TextArea(id=f"q-other-{idx}")
            ta.display = False
            yield ta

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        list_id = event.option_list.id or ""
        if not list_id.startswith("q-list-"):
            return
        idx = int(list_id.removeprefix("q-list-"))
        q = self._questions[idx]
        selected_label = q["options"][event.option_index]["label"]

        if selected_label == "Other":
            self._other_active[idx] = True
            self._selections[idx] = None
            ta = self.query_one(f"#q-other-{idx}", TextArea)
            ta.display = True
            ta.focus()
            return

        self._other_active[idx] = False
        self._selections[idx] = selected_label
        ta = self.query_one(f"#q-other-{idx}", TextArea)
        ta.display = False
        self._maybe_submit()

    def _maybe_submit(self) -> None:
        answers = {}
        for idx, q in enumerate(self._questions):
            if self._other_active[idx]:
                ta = self.query_one(f"#q-other-{idx}", TextArea)
                custom = ta.text.strip()
                if not custom:
                    return
                answers[q["question"]] = custom
            elif self._selections[idx] is not None:
                answers[q["question"]] = self._selections[idx]
            else:
                return
        self.post_message(self.Answered(answers))
        self.remove()
```

- [ ] **Step 3: Run widget tests — expect green**

```bash
./.venv/bin/pytest tests/tui/test_question_widget.py -q
```
Expected: `3 passed`

- [ ] **Step 4: Commit**

```bash
git add deep_coder/tui/widgets/ tests/tui/test_question_widget.py
git commit -m "feat: add QuestionWidget for inline ask_user TUI interaction"
```

---

## Task 9: TUI app wiring — failing tests

**Files:**
- Modify: `tests/tui/test_live_events.py`

- [ ] **Step 1: Add failing TUI integration test**

Add to `tests/tui/test_live_events.py`:
```python
def test_question_asked_event_renders_widget_and_locks_composer(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            app.emit({
                "type": "question_asked",
                "session_id": "session-a",
                "turn_id": "turn-live",
                "questions": [{
                    "question": "Which approach?",
                    "options": [
                        {"label": "Option A", "description": "fast"},
                        {"label": "Option B", "description": "slow"},
                        {"label": "Other", "description": "Type your own answer"},
                    ],
                }],
            })
            await pilot.pause()

            # Composer should be locked
            assert app._turn_state == "waiting_for_user"

            # Widget should be visible in timeline
            from deep_coder.tui.widgets.question_widget import QuestionWidget
            assert len(app.query(QuestionWidget)) > 0

            timeline_text = render_widget_text(app.query_one("#timeline-scroll"))
            assert "Which approach?" in timeline_text

    asyncio.run(run())


def test_question_widget_answer_unlocks_composer(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)

        # Attach a fake turn with write_answer support
        class FakeTurnWithAnswer:
            def __init__(self):
                self.answers_written = []
            def write_answer(self, json_str):
                self.answers_written.append(json_str)
            def interrupt(self): pass
            def close(self): pass

        fake_turn = FakeTurnWithAnswer()

        async with app.run_test(size=(120, 40)) as pilot:
            app._active_turn = fake_turn
            app._turn_state = "waiting_for_user"

            app.emit({
                "type": "question_asked",
                "session_id": "session-a",
                "turn_id": "turn-live",
                "questions": [{
                    "question": "Which approach?",
                    "options": [
                        {"label": "Option A", "description": "fast"},
                        {"label": "Option B", "description": "slow"},
                        {"label": "Other", "description": "Type your own answer"},
                    ],
                }],
            })
            await pilot.pause()

            from deep_coder.tui.widgets.question_widget import QuestionWidget
            widget = app.query_one(QuestionWidget)
            widget.post_message(QuestionWidget.Answered({"Which approach?": "Option A"}))
            await pilot.pause()

            assert app._turn_state == "running"
            assert len(fake_turn.answers_written) == 1
            import json
            payload = json.loads(fake_turn.answers_written[0])
            assert payload["answers"] == {"Which approach?": "Option A"}

    asyncio.run(run())
```

- [ ] **Step 2: Run to confirm red**

```bash
./.venv/bin/pytest tests/tui/test_live_events.py::test_question_asked_event_renders_widget_and_locks_composer tests/tui/test_live_events.py::test_question_widget_answer_unlocks_composer -q
```
Expected: failures — `question_asked` not handled in app

---

## Task 10: TUI app wiring — implementation

**Files:**
- Modify: `deep_coder/tui/app.py`

- [ ] **Step 1: Add import for QuestionWidget at top of app.py**

Add to the imports section of `deep_coder/tui/app.py`:
```python
from deep_coder.tui.widgets.question_widget import QuestionWidget
```
Also add `render_question_asked_block` to the render imports:
```python
from deep_coder.tui.render import (
    ...
    render_question_asked_block,
    ...
)
```

- [ ] **Step 2: Handle question_asked in on_timeline_event**

In `on_timeline_event`, add a branch for `question_asked` in the state machine block (before the `follow_tail` line):
```python
elif event_type == "question_asked" and self._turn_state != "interrupting":
    self._turn_state = "waiting_for_user"
```

- [ ] **Step 3: Handle question_asked in _append_event_block**

In `_append_event_block`, add a branch (for replay — renders static summary):
```python
elif event_type == "question_asked":
    # During replay, render static summary. Live widget is added separately.
    block = render_question_asked_block(event)
```

But for the live case, we need to mount the widget instead of appending a static block. Modify `on_timeline_event` to mount the widget after the state update:

```python
def on_timeline_event(self, message: TimelineEvent) -> None:
    event = message.event
    self.session_id = event.get("session_id", self.session_id)
    event_type = event["type"]
    if event_type == "turn_started" and self._turn_state != "interrupting":
        self._turn_state = "running"
    elif event_type == "tool_called" and self._turn_state != "interrupting":
        self._turn_state = f"tool:{event['name']}"
    elif event_type == "question_asked" and self._turn_state != "interrupting":
        self._turn_state = "waiting_for_user"
    elif event_type == "context_compacting" and self._turn_state != "interrupting":
        self._turn_state = "compacting"
    elif event_type == "context_compacted" and self._turn_state == "compacting":
        self._turn_state = "running"
    elif event_type in {"turn_finished", "turn_interrupted", "turn_failed"}:
        self._turn_state = "idle"

    follow_tail = self._timeline_is_at_end()

    if event_type == "question_asked" and self._turn_state == "waiting_for_user":
        widget = QuestionWidget(event["questions"])
        self.query_one("#timeline-scroll", TimelineScroll).mount(widget)
        if follow_tail:
            self.query_one("#timeline-scroll", TimelineScroll).scroll_end(
                animate=False, x_axis=False
            )
    else:
        self._append_event_block(event)
        self._refresh_timeline(follow_tail=follow_tail)

    self._update_status_strip()
```

- [ ] **Step 4: Handle QuestionWidget.Answered message**

Add handler to `DeepCodeApp`:
```python
def on_question_widget_answered(self, message: QuestionWidget.Answered) -> None:
    import json
    if self._active_turn is not None:
        self._active_turn.write_answer(json.dumps({"answers": message.answers}))
    self._turn_state = "running"
    self._update_status_strip()
```

- [ ] **Step 5: Lock Composer during waiting_for_user**

In `action_submit_composer`, the existing guard is:
```python
if self._turn_state != "idle":
    return
```
This already blocks submission during `waiting_for_user` since it's not `"idle"`. No change needed.

- [ ] **Step 6: Run new TUI tests — expect green**

```bash
./.venv/bin/pytest tests/tui/test_live_events.py::test_question_asked_event_renders_widget_and_locks_composer tests/tui/test_live_events.py::test_question_widget_answer_unlocks_composer -q
```
Expected: `2 passed`

- [ ] **Step 7: Run full suite**

```bash
./.venv/bin/pytest -q
```
Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add deep_coder/tui/app.py tests/tui/test_live_events.py
git commit -m "feat: wire ask_user question_asked event into TUI with QuestionWidget and composer lock"
```

---

## Task 11: Update StatusStrip for waiting_for_user state

**Files:**
- Modify: `deep_coder/tui/app.py`

- [ ] **Step 1: Make StatusStrip show busy during waiting_for_user**

In `StatusStrip._sync_busy_state`, the `is_busy` check is:
```python
is_busy = (
    self._turn_state in {"running", "interrupting", "compacting"}
    or self._turn_state.startswith("tool:")
)
```

Add `"waiting_for_user"` to the set:
```python
is_busy = (
    self._turn_state in {"running", "interrupting", "compacting", "waiting_for_user"}
    or self._turn_state.startswith("tool:")
)
```

- [ ] **Step 2: Run full suite**

```bash
./.venv/bin/pytest -q
```
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add deep_coder/tui/app.py
git commit -m "feat: pulse status strip while waiting for user answer"
```

