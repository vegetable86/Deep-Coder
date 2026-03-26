# Session Task System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a session-scoped, model-driven task system with dependencies, persisted in session context, exposed through builtin task tools, and rendered inline in the existing timeline.

**Architecture:** Add structured task state to the session/context layer and centralize task-graph mutations in a dedicated task manager. Expose `task_create`, `task_update`, `task_list`, and `task_get` as builtin tools, extend tool execution so tools can read and mutate the active session, and let task tools return structured `task_snapshot` timeline payloads that the harness relays without adding any planning policy of its own. Keep the current TUI shell unchanged and render task snapshots as checklist blocks directly in the timeline.

**Tech Stack:** Python 3, Textual, pytest, existing Deep Coder context / harness / tool modules

**Execution Notes:** Follow `@test-driven-development` and `@verification-before-completion`. Use `/home/wys/deep-code/.venv/bin/pytest -q` for verification in this repository.

---

### Task 1: Add session-backed task state and task-graph helpers

**Files:**
- Create: `deep_coder/tasks/__init__.py`
- Create: `deep_coder/tasks/manager.py`
- Modify: `deep_coder/context/session.py`
- Modify: `deep_coder/context/stores/filesystem/store.py`
- Create: `tests/tasks/test_manager.py`
- Modify: `tests/context/test_filesystem_store.py`

**Step 1: Write the failing tests**

```python
from deep_coder.context.session import Session
from deep_coder.tasks.manager import TaskManager


def test_session_starts_with_empty_task_state(tmp_path):
    session = Session(session_id="session-a", root=tmp_path)

    assert session.next_task_id == 1
    assert session.tasks == []


def test_task_manager_updates_dependencies_and_clears_blockers_on_completion(tmp_path):
    session = Session(session_id="session-a", root=tmp_path)
    manager = TaskManager(session)

    first = manager.create(subject="inspect repo")
    second = manager.create(subject="edit app")
    manager.update(first["id"], add_blocks=[second["id"]])
    updated = manager.update(first["id"], status="completed")

    assert updated["status"] == "completed"
    assert manager.get(second["id"])["blocked_by"] == []
```

```python
def test_filesystem_store_persists_task_state(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)
    session = store.open()
    session.next_task_id = 3
    session.tasks = [
        {"id": 1, "subject": "inspect repo", "description": "", "status": "completed", "blocked_by": [], "blocks": [2]},
        {"id": 2, "subject": "edit app", "description": "", "status": "pending", "blocked_by": [], "blocks": []},
    ]

    store.save(session)
    reopened = store.open(locator={"id": session.session_id})

    assert reopened.next_task_id == 3
    assert reopened.tasks[1]["subject"] == "edit app"
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tasks/test_manager.py tests/context/test_filesystem_store.py`

Expected: FAIL because the session has no task state yet and the task manager module does not exist.

**Step 3: Write the minimal implementation**

```python
@dataclass
class Session:
    ...
    next_task_id: int = 1
    tasks: list[dict] = field(default_factory=list)
```

```python
class TaskManager:
    def __init__(self, session):
        self.session = session

    def create(self, subject: str, description: str = "") -> dict: ...
    def get(self, task_id: int) -> dict: ...
    def update(self, task_id: int, status=None, add_blocked_by=None, add_blocks=None) -> dict: ...
    def list_all(self) -> list[dict]: ...
```

```python
state = dict(session.strategy_state)
state["task_system"] = {
    "next_task_id": session.next_task_id,
    "tasks": session.tasks,
}
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tasks/test_manager.py tests/context/test_filesystem_store.py`

Expected: PASS

### Task 2: Add builtin task tools and session-aware tool execution

**Files:**
- Create: `deep_coder/tools/tasks/__init__.py`
- Create: `deep_coder/tools/tasks/tool.py`
- Modify: `deep_coder/tools/base.py`
- Modify: `deep_coder/tools/result.py`
- Modify: `deep_coder/tools/registry.py`
- Create: `tests/tools/test_task_tools.py`
- Modify: `tests/tools/test_registry.py`

**Step 1: Write the failing tests**

```python
from deep_coder.context.session import Session
from deep_coder.tools.registry import ToolRegistry


def test_registry_exposes_task_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    registry = ToolRegistry.from_builtin(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
    )

    names = [schema["function"]["name"] for schema in registry.schemas()]
    assert names == [
        "bash",
        "read_file",
        "write_file",
        "edit_file",
        "task_create",
        "task_update",
        "task_list",
        "task_get",
    ]


def test_task_create_tool_updates_session_and_returns_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    registry = ToolRegistry.from_builtin(
        config=RuntimeConfig.from_env(workdir=tmp_path),
        workdir=tmp_path,
    )
    session = Session(session_id="session-a", root=tmp_path)

    result = registry.execute("task_create", {"subject": "inspect repo"}, session=session)

    assert session.tasks[0]["subject"] == "inspect repo"
    assert result.timeline_events[0]["type"] == "task_snapshot"
```

```python
def test_task_update_rejects_self_dependency(tmp_path, monkeypatch):
    ...
    registry.execute("task_create", {"subject": "inspect repo"}, session=session)

    result = registry.execute(
        "task_update",
        {"task_id": 1, "add_blocks": [1]},
        session=session,
    )

    assert result.is_error is True
    assert "self" in result.output_text
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tools/test_registry.py tests/tools/test_task_tools.py`

Expected: FAIL because the task tools do not exist and the tool registry cannot pass the active session into tool execution.

**Step 3: Write the minimal implementation**

```python
class ToolBase(ABC):
    @abstractmethod
    def exec(self, arguments: dict, session=None) -> str:
        raise NotImplementedError
```

```python
@dataclass
class ToolExecutionResult:
    ...
    timeline_events: list[dict] = field(default_factory=list)
```

```python
class TaskCreateTool(ToolBase):
    def exec(self, arguments: dict, session=None) -> str:
        if session is None:
            raise ValueError("task_create requires an active session")
        task = TaskManager(session).create(arguments["subject"], arguments.get("description", ""))
        return render_task_detail(task)
```

```python
result = self._tools[name].exec(arguments, session=session)
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tools/test_registry.py tests/tools/test_task_tools.py`

Expected: PASS

### Task 3: Relay task snapshots through the harness and persist them in session history

**Files:**
- Modify: `deep_coder/harness/deepcoder/harness.py`
- Modify: `tests/harness/test_deepcoder_harness.py`

**Step 1: Write the failing tests**

```python
def test_harness_passes_active_session_to_tools_and_emits_task_snapshot(tmp_path):
    class FakeTools:
        def schemas(self):
            return [{"function": {"name": "task_list"}}]

        def execute(self, name, arguments, session=None):
            assert session is not None
            return ToolExecutionResult(
                name=name,
                display_command="task_list",
                model_output="(0/1 completed)",
                output_text="(0/1 completed)",
                timeline_events=[
                    {
                        "type": "task_snapshot",
                        "tasks": [
                            {"id": 1, "subject": "inspect repo", "status": "pending", "blocked_by": [], "blocks": []}
                        ],
                        "completed_count": 0,
                        "total_count": 1,
                    }
                ],
            )

    ...
    assert [event["type"] for event in events] == [
        "turn_started",
        "message_committed",
        "tool_called",
        "tool_output",
        "task_snapshot",
        "message_committed",
        "turn_finished",
    ]
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/harness/test_deepcoder_harness.py`

Expected: FAIL because the harness does not pass `session` into the tool registry and does not relay tool-provided timeline events.

**Step 3: Write the minimal implementation**

```python
output = self.tools.execute(tool_call["name"], tool_call["arguments"], session=session)
```

```python
for extra_event in output.timeline_events:
    self._publish(
        session,
        event_sink,
        self._event(session, turn_id, extra_event["type"], **extra_event["payload"]),
    )
```

Note: if `timeline_events` stores flat dictionaries, normalize them once in the registry so the harness only publishes them.

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/harness/test_deepcoder_harness.py`

Expected: PASS

### Task 4: Render task snapshots inline in the existing timeline

**Files:**
- Modify: `deep_coder/tui/render.py`
- Modify: `deep_coder/tui/app.py`
- Modify: `tests/tui/test_render.py`
- Modify: `tests/tui/test_live_events.py`

**Step 1: Write the failing tests**

```python
def test_render_task_snapshot_block_shows_status_markers_and_progress():
    block = render_task_snapshot_block(
        {
            "tasks": [
                {"id": 1, "subject": "inspect repo", "status": "completed", "blocked_by": [], "blocks": [2]},
                {"id": 2, "subject": "edit app", "status": "pending", "blocked_by": [1], "blocks": []},
            ],
            "completed_count": 1,
            "total_count": 2,
        }
    )

    text = render_plain_text(block)
    assert "[x] #1: inspect repo" in text
    assert "[ ] #2: edit app" in text
    assert "(1/2 completed)" in text
```

```python
def test_live_task_snapshot_event_renders_inline_in_timeline(fake_runtime, fake_project):
    ...
    app.emit(
        {
            "type": "task_snapshot",
            "session_id": "session-a",
            "turn_id": "turn-live",
            "tasks": [
                {"id": 1, "subject": "inspect repo", "status": "in_progress", "blocked_by": [], "blocks": []}
            ],
            "completed_count": 0,
            "total_count": 1,
        }
    )

    timeline_text = render_widget_text(app.query_one("#timeline"))
    assert "[>] #1: inspect repo" in timeline_text
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_live_events.py`

Expected: FAIL because there is no `task_snapshot` renderer and the app ignores that event type.

**Step 3: Write the minimal implementation**

```python
def render_task_snapshot_block(event: dict) -> RenderableType:
    lines = []
    for task in event["tasks"]:
        marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}[task["status"]]
        lines.append(f"{marker} #{task['id']}: {task['subject']}")
    lines.append(f"({event['completed_count']}/{event['total_count']} completed)")
    return Panel(Text("\n".join(lines)), border_style="cyan")
```

```python
elif event_type == "task_snapshot":
    block = render_task_snapshot_block(event)
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_live_events.py`

Expected: PASS

### Task 5: Run integrated verification

**Files:**
- Modify: `deep_coder/context/session.py`
- Modify: `deep_coder/context/stores/filesystem/store.py`
- Modify: `deep_coder/harness/deepcoder/harness.py`
- Modify: `deep_coder/tools/base.py`
- Modify: `deep_coder/tools/result.py`
- Modify: `deep_coder/tools/registry.py`
- Create: `deep_coder/tasks/__init__.py`
- Create: `deep_coder/tasks/manager.py`
- Create: `deep_coder/tools/tasks/__init__.py`
- Create: `deep_coder/tools/tasks/tool.py`
- Create: `tests/tasks/test_manager.py`
- Create: `tests/tools/test_task_tools.py`
- Modify: `tests/context/test_filesystem_store.py`
- Modify: `tests/harness/test_deepcoder_harness.py`
- Modify: `tests/tools/test_registry.py`
- Modify: `tests/tui/test_render.py`
- Modify: `tests/tui/test_live_events.py`
- Modify: `deep_coder/tui/render.py`
- Modify: `deep_coder/tui/app.py`

**Step 1: Run targeted verification**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tasks/test_manager.py tests/context/test_filesystem_store.py tests/tools/test_registry.py tests/tools/test_task_tools.py tests/harness/test_deepcoder_harness.py tests/tui/test_render.py tests/tui/test_live_events.py`

Expected: PASS

**Step 2: Run the full suite**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`

Expected: PASS
