# Harness Backend TUI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a project-scoped terminal UI for the `deep_coder` runtime that launches with `deepcode`, isolates sessions by workspace, and renders live harness activity plus replayable timeline history in one top/bottom layout.

**Architecture:** Add a small project-registry layer under `~/.deepcode/`, keep the existing harness/model/context split, and persist a second per-session event log for TUI replay. Build the UI with Textual so the app can render a single scrollable timeline, a bottom composer, and a modal session switcher while consuming live harness events from a worker thread.

**Tech Stack:** Python 3, Textual, Rich, pytest, stdlib `tomllib`, stdlib `difflib`, OpenAI-compatible SDK

**Execution Notes:** Follow `@test-driven-development` and `@verification-before-completion` throughout. If the Textual worker/event flow misbehaves, stop and use `@systematic-debugging`.

---

### Task 1: Add the project registry under `~/.deepcode/config.toml`

**Files:**
- Create: `deep_coder/projects/__init__.py`
- Create: `deep_coder/projects/registry.py`
- Test: `tests/projects/test_registry.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/projects/test_registry.py -v`
Expected: FAIL because the `deep_coder.projects` package does not exist

**Step 3: Write the minimal implementation**

```python
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class ProjectRecord:
    path: Path
    name: str
    key: str
    state_dir: Path
    last_opened_at: str


class ProjectRegistry:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.config_path = self.root / "config.toml"
        self.projects_dir = self.root / "projects"

    def open_workspace(self, workspace: Path) -> ProjectRecord:
        workspace = Path(workspace).resolve()
        data = self._load()
        record = self._find_existing(data, workspace) or self._new_record(workspace)
        data["current_project"] = str(workspace)
        data["projects"] = [
            project for project in data["projects"] if project["path"] != str(workspace)
        ] + [self._dump_record(record)]
        self._save(data)
        return record

    def current_project(self) -> ProjectRecord | None:
        data = self._load()
        current = data.get("current_project")
        if not current:
            return None
        return self._find_existing(data, Path(current))
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/projects/test_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/projects/__init__.py deep_coder/projects/registry.py tests/projects/test_registry.py
git commit -m "feat: add project registry"
```

### Task 2: Make runtime config and session storage project-scoped

**Files:**
- Modify: `deep_coder/config.py`
- Modify: `deep_coder/main.py`
- Modify: `deep_coder/context/session.py`
- Modify: `deep_coder/context/stores/filesystem/store.py`
- Test: `tests/context/test_filesystem_store.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing tests**

```python
from deep_coder.projects.registry import ProjectRecord
from deep_coder.main import build_runtime


def test_build_runtime_uses_project_state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    workspace = tmp_path / "repo"
    workspace.mkdir()
    project = ProjectRecord(
        path=workspace,
        name="repo",
        key="repo-abc123",
        state_dir=tmp_path / ".deepcode" / "projects" / "repo-abc123",
        last_opened_at="2026-03-25T00:00:00Z",
    )

    runtime = build_runtime(project=project)

    assert runtime["config"].project_key == "repo-abc123"
    assert runtime["config"].state_dir == project.state_dir
```

```python
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore


def test_filesystem_store_persists_events_and_project_meta(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    store = FileSystemSessionStore(
        root=tmp_path,
        project_key="repo-abc123",
        workspace_path=workspace,
    )

    session = store.open()
    session.events.append({"type": "turn_started", "turn_id": "t1"})
    store.save(session)

    reopened = store.open(locator={"id": session.session_id})

    assert reopened.events == [{"type": "turn_started", "turn_id": "t1"}]
    assert reopened.meta()["project_key"] == "repo-abc123"
    assert reopened.meta()["workspace_path"] == str(workspace)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/context/test_filesystem_store.py tests/test_main.py -v`
Expected: FAIL because runtime config and session storage do not yet carry project or event-log metadata

**Step 3: Write the minimal implementation**

```python
@dataclass
class RuntimeConfig:
    model_provider: str
    model_name: str
    api_key: str
    base_url: str
    workdir: Path
    state_dir: Path
    project_path: Path
    project_key: str
    project_name: str

    @classmethod
    def from_project(cls, project):
        return cls(
            model_provider="deepseek",
            model_name="deepseek-chat",
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
            workdir=project.path,
            state_dir=project.state_dir,
            project_path=project.path,
            project_key=project.key,
            project_name=project.name,
        )
```

```python
@dataclass
class Session:
    session_id: str
    root: Path
    messages: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    project_key: str | None = None
    workspace_path: str | None = None

    def meta(self) -> dict:
        return {
            "id": self.session_id,
            "project_key": self.project_key,
            "workspace_path": self.workspace_path,
        }
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/context/test_filesystem_store.py tests/test_main.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/config.py deep_coder/main.py deep_coder/context/session.py deep_coder/context/stores/filesystem/store.py tests/context/test_filesystem_store.py tests/test_main.py
git commit -m "feat: scope runtime state by project"
```

### Task 3: Normalize tool execution metadata and model usage for the TUI

**Files:**
- Create: `deep_coder/tools/result.py`
- Modify: `deep_coder/tools/registry.py`
- Modify: `deep_coder/models/deepseek/model.py`
- Test: `tests/tools/test_file_tools.py`
- Test: `tests/tools/test_registry.py`
- Test: `tests/models/test_deepseek_model.py`

**Step 1: Write the failing tests**

```python
from deep_coder.config import RuntimeConfig
from deep_coder.tools.registry import ToolRegistry


def test_registry_returns_display_command_and_diff_for_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    registry = ToolRegistry.from_builtin(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
    )
    (tmp_path / "notes.txt").write_text("hello world\n")

    result = registry.execute(
        "edit_file",
        {"path": "notes.txt", "old_text": "world", "new_text": "runtime"},
    )

    assert result.display_command == "edit_file notes.txt"
    assert "@@" in result.diff_text
    assert "-hello world" in result.diff_text
    assert "+hello runtime" in result.diff_text
```

```python
from deep_coder.config import RuntimeConfig
from deep_coder.models.deepseek.model import DeepSeekModel


def test_deepseek_complete_normalizes_tool_args_and_usage(monkeypatch, tmp_path):
    class FakeToolCall:
        id = "tool-1"
        function = type(
            "Fn",
            (),
            {"name": "read_file", "arguments": '{"path": "README.md"}'},
        )()

    class FakeUsage:
        def model_dump(self):
            return {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "prompt_cache_hit_tokens": 3,
                "prompt_cache_miss_tokens": 7,
            }

    class FakeResponse:
        choices = [type("Choice", (), {
            "message": type("Msg", (), {"content": None, "tool_calls": [FakeToolCall()]})(),
            "finish_reason": "tool_calls",
        })()]
        usage = FakeUsage()

    model = DeepSeekModel(config=RuntimeConfig.from_env(workdir=tmp_path))
    model.client = type("Client", (), {
        "chat": type("Chat", (), {
            "completions": type("Completions", (), {
                "create": staticmethod(lambda **_: FakeResponse())
            })()
        })()
    })()

    response = model.complete({"messages": [{"role": "user", "content": "read me"}]})

    assert response["tool_calls"][0]["arguments"] == {"path": "README.md"}
    assert response["usage"]["cache_hit_tokens"] == 3
    assert response["usage"]["cache_miss_tokens"] == 7
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_registry.py tests/tools/test_file_tools.py tests/models/test_deepseek_model.py -v`
Expected: FAIL because the registry still returns a raw string and the model adapter does not normalize arguments or cache counters

**Step 3: Write the minimal implementation**

```python
from dataclasses import dataclass


@dataclass
class ToolExecutionResult:
    name: str
    display_command: str
    model_output: str
    output_text: str
    diff_text: str | None = None
    is_error: bool = False
```

```python
def execute(self, name: str, arguments: dict) -> ToolExecutionResult:
    before = _maybe_read_target(self.workdir, name, arguments)
    output = self._tools[name].exec(arguments)
    after = _maybe_read_target(self.workdir, name, arguments)
    return ToolExecutionResult(
        name=name,
        display_command=_display_command(name, arguments),
        model_output=output,
        output_text=output,
        diff_text=_build_diff(name, arguments, before, after),
        is_error=output.startswith("error:"),
    )
```

```python
arguments = json.loads(call.function.arguments or "{}")
usage_raw = response.usage.model_dump() if response.usage else {}
usage = {
    "prompt_tokens": usage_raw.get("prompt_tokens", 0),
    "completion_tokens": usage_raw.get("completion_tokens", 0),
    "total_tokens": usage_raw.get("total_tokens", 0),
    "cache_hit_tokens": usage_raw.get("prompt_cache_hit_tokens", 0),
    "cache_miss_tokens": usage_raw.get("prompt_cache_miss_tokens", 0),
}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_registry.py tests/tools/test_file_tools.py tests/models/test_deepseek_model.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tools/result.py deep_coder/tools/registry.py deep_coder/models/deepseek/model.py tests/tools/test_registry.py tests/tools/test_file_tools.py tests/models/test_deepseek_model.py
git commit -m "feat: normalize tool metadata for tui"
```

### Task 4: Emit and persist live harness timeline events

**Files:**
- Create: `deep_coder/harness/events.py`
- Modify: `deep_coder/harness/base.py`
- Modify: `deep_coder/harness/result.py`
- Modify: `deep_coder/harness/deepcoder/harness.py`
- Test: `tests/harness/test_deepcoder_harness.py`

**Step 1: Write the failing tests**

```python
def test_harness_emits_and_persists_timeline_events(tmp_path):
    events = []

    class CapturingSink:
        def emit(self, event):
            events.append(event)

    class FakeModel:
        def __init__(self):
            self.calls = 0

        def complete(self, request):
            self.calls += 1
            if self.calls == 1:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tool-1",
                            "name": "edit_file",
                            "arguments": {
                                "path": "notes.txt",
                                "old_text": "world",
                                "new_text": "runtime",
                            },
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                        "cache_hit_tokens": 1,
                        "cache_miss_tokens": 9,
                    },
                    "finish_reason": "tool_calls",
                    "raw_response": None,
                }
            return {
                "content": "done",
                "tool_calls": [],
                "usage": {
                    "prompt_tokens": 7,
                    "completion_tokens": 3,
                    "total_tokens": 10,
                    "cache_hit_tokens": 0,
                    "cache_miss_tokens": 7,
                },
                "finish_reason": "stop",
                "raw_response": None,
            }

    class FakeTools:
        def schemas(self):
            return [{"function": {"name": "edit_file"}}]

        def execute(self, name, arguments):
            return ToolExecutionResult(
                name=name,
                display_command="edit_file notes.txt",
                model_output="updated notes.txt",
                output_text="updated notes.txt",
                diff_text="@@ -1 +1 @@\n-hello world\n+hello runtime\n",
            )

    # build prompt/context/harness as in the existing harness test
    result = harness.run(None, "fix note", event_sink=CapturingSink())
    reopened = context.open(locator={"id": result.session_id})

    assert [event["type"] for event in events] == [
        "turn_started",
        "message_committed",
        "usage_reported",
        "tool_called",
        "tool_output",
        "tool_diff",
        "usage_reported",
        "message_committed",
        "turn_finished",
    ]
    assert reopened.events == events
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/harness/test_deepcoder_harness.py -v`
Expected: FAIL because the harness has no event sink and sessions do not persist timeline events

**Step 3: Write the minimal implementation**

```python
class HarnessEventSinkBase(ABC):
    @abstractmethod
    def emit(self, event: dict) -> None: ...


class NullHarnessEventSink(HarnessEventSinkBase):
    def emit(self, event: dict) -> None:
        return None
```

```python
def _publish(self, session, event_sink, event):
    session.events.append(event)
    event_sink.emit(event)


def run(self, session_locator, user_input: str, event_sink=None):
    event_sink = event_sink or NullHarnessEventSink()
    turn_id = uuid.uuid4().hex[:12]
    self._publish(session, event_sink, {"type": "turn_started", ...})
    self._publish(session, event_sink, {"type": "message_committed", "role": "user", ...})
    ...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/harness/test_deepcoder_harness.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/harness/events.py deep_coder/harness/base.py deep_coder/harness/result.py deep_coder/harness/deepcoder/harness.py tests/harness/test_deepcoder_harness.py
git commit -m "feat: add harness timeline events"
```

### Task 5: Build the Textual app shell, styles, and session-switcher overlay

**Files:**
- Create: `requirements.txt`
- Create: `deep_coder/tui/__init__.py`
- Create: `deep_coder/tui/app.py`
- Create: `deep_coder/tui/styles.tcss`
- Create: `deep_coder/tui/screens/__init__.py`
- Create: `deep_coder/tui/screens/session_switcher.py`
- Create: `tests/tui/conftest.py`
- Test: `tests/tui/test_app_layout.py`

**Step 1: Write the failing tests**

```python
import asyncio

from deep_coder.tui.app import DeepCodeApp


def test_app_has_timeline_and_composer_shell(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            assert app.query_one("#timeline")
            assert app.query_one("#status-strip")
            assert app.query_one("#composer")

    asyncio.run(run())
```

```python
import asyncio


def test_session_switcher_lists_only_project_sessions(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("ctrl+l")
            overlay = app.screen.query_one("#session-switcher")
            labels = [option.prompt for option in overlay.options]
            assert labels == ["session-a", "session-b"]

    asyncio.run(run())
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/tui/test_app_layout.py -v`
Expected: FAIL because the TUI package and Textual app do not exist

**Step 3: Write the minimal implementation**

```python
class DeepCodeApp(App):
    CSS_PATH = "styles.tcss"
    BINDINGS = [("ctrl+l", "open_session_switcher", "Sessions")]

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="timeline")
        with Container(id="bottom-pane"):
            yield Static(id="status-strip")
            yield TextArea(id="composer")
```

```python
class SessionSwitcher(ModalScreen[str | None]):
    def __init__(self, sessions: list[dict]):
        super().__init__(id="session-switcher")
        self._sessions = sessions
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/tui/test_app_layout.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add requirements.txt deep_coder/tui/__init__.py deep_coder/tui/app.py deep_coder/tui/styles.tcss deep_coder/tui/screens/__init__.py deep_coder/tui/screens/session_switcher.py tests/tui/conftest.py tests/tui/test_app_layout.py
git commit -m "feat: add textual tui shell"
```

### Task 6: Render timeline blocks, diff hunks, truncation, and session replay

**Files:**
- Create: `deep_coder/tui/render.py`
- Modify: `deep_coder/tui/app.py`
- Test: `tests/tui/test_render.py`
- Test: `tests/tui/test_session_switcher.py`

**Step 1: Write the failing tests**

```python
from deep_coder.tui.render import render_message_block, render_tool_output, render_diff_block


def test_message_blocks_do_not_render_speaker_labels():
    user = render_message_block(role="user", text="make dir aa")
    assistant = render_message_block(role="assistant", text="done")

    assert "User Message" not in user.plain
    assert "Assistant" not in assistant.plain


def test_tool_output_truncates_long_plain_output():
    block = render_tool_output("x" * 600, max_chars=40)
    assert block.plain.endswith("...")


def test_diff_block_keeps_all_changed_hunks_with_line_numbers():
    diff = """--- a/notes.txt
+++ b/notes.txt
@@ -1,2 +1,2 @@
-hello world
+hello runtime
 keep
"""
    block = render_diff_block(path="notes.txt", diff_text=diff)

    assert "notes.txt" in block.plain
    assert "1" in block.plain
    assert "hello runtime" in block.plain
```

```python
import asyncio


def test_reopening_session_replays_persisted_events(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            app.load_session("session-a")
            timeline_text = app.query_one("#timeline").renderable.plain
            assert "mkdir aa" in timeline_text
            assert "prompt_tokens" in timeline_text

    asyncio.run(run())
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/tui/test_render.py tests/tui/test_session_switcher.py -v`
Expected: FAIL because the render helpers and replay path do not exist

**Step 3: Write the minimal implementation**

```python
def render_tool_output(text: str, max_chars: int = 400) -> Text:
    if len(text) <= max_chars:
        return Text(text)
    return Text(text[: max_chars - 3] + "...")
```

```python
def load_session(self, session_id: str) -> None:
    session = self.runtime["context"].open(locator={"id": session_id})
    self._timeline_blocks.clear()
    for event in session.events:
        self._append_event_block(event)
```

```python
def render_diff_block(path: str, diff_text: str) -> Group:
    # Parse unified diff hunks and render old/new line numbers plus
    # add/delete/context line styles.
    ...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/tui/test_render.py tests/tui/test_session_switcher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tui/render.py deep_coder/tui/app.py tests/tui/test_render.py tests/tui/test_session_switcher.py
git commit -m "feat: render timeline blocks and session replay"
```

### Task 7: Launch the TUI with `deepcode` and stream live harness events into the timeline

**Files:**
- Create: `deep_coder/cli.py`
- Create: `deepcode`
- Modify: `deep_coder/tui/app.py`
- Test: `tests/test_cli.py`
- Test: `tests/tui/test_live_events.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

from deep_coder.cli import resolve_launch_context


def test_cli_uses_pwd_to_select_project(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    registry_root = tmp_path / ".deepcode"

    project, runtime = resolve_launch_context(
        cwd=workspace,
        registry_root=registry_root,
    )

    assert project.path == workspace.resolve()
    assert runtime["config"].project_key == project.key
```

```python
import asyncio


def test_submit_runs_harness_and_appends_live_events(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "make dir aa"
            await pilot.press("enter")
            await pilot.pause()
            timeline_text = app.query_one("#timeline").renderable.plain
            assert "mkdir aa" in timeline_text
            assert "cache_hit_tokens" in timeline_text
            assert "done" in timeline_text

    asyncio.run(run())
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py tests/tui/test_live_events.py -v`
Expected: FAIL because there is no CLI bootstrap and the app does not yet run the harness in a worker

**Step 3: Write the minimal implementation**

```python
def resolve_launch_context(cwd: Path | None = None, registry_root: Path | None = None):
    cwd = (cwd or Path.cwd()).resolve()
    registry = ProjectRegistry(root=registry_root or (Path.home() / ".deepcode"))
    project = registry.open_workspace(cwd)
    runtime = build_runtime(project=project)
    return project, runtime
```

```python
#!/usr/bin/env python3
from deep_coder.cli import main


raise SystemExit(main())
```

```python
@work(thread=True)
def run_turn(self, user_input: str) -> None:
    self.runtime["harness"].run(
        session_locator={"id": self.session_id} if self.session_id else None,
        user_input=user_input,
        event_sink=self,
    )


def emit(self, event: dict) -> None:
    self.post_message(TimelineEvent(event))
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py tests/tui/test_live_events.py -v`
Expected: PASS

**Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS

**Step 6: Commit**

```bash
chmod +x deepcode
git add deep_coder/cli.py deepcode deep_coder/tui/app.py tests/test_cli.py tests/tui/test_live_events.py
git commit -m "feat: launch project-scoped deepcode tui"
```
