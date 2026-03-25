# Deep Coder Backend Runtime Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the package-based Deep Coder backend runtime that a future TUI can call, with a real harness, tool system, prompt module, and persistent local session storage.

**Architecture:** Keep the boundaries from `arch/arch.md` intact: `Harness`, `Model`, `ToolRegistry`, `Prompt`, `ContextManager`, `SessionStore`, and `ContextStrategy`. Use thin concrete implementations in v1: four built-in coding tools, a filesystem-backed session store under `~/.deepcode/`, and an append-only context strategy that records messages in the same order as the prototype loop.

**Tech Stack:** Python 3, pytest, OpenAI-compatible SDK, local filesystem persistence

---

### Task 1: Implement the tool registry and four built-in coding tools

**Files:**
- Create: `deep_coder/tools/registry.py`
- Create: `deep_coder/tools/bash/tool.py`
- Create: `deep_coder/tools/read_file/tool.py`
- Create: `deep_coder/tools/write_file/tool.py`
- Create: `deep_coder/tools/edit_file/tool.py`
- Modify: `deep_coder/tools/__init__.py`
- Test: `tests/tools/test_registry.py`
- Test: `tests/tools/test_file_tools.py`

**Step 1: Write the failing tests**

```python
from deep_coder.tools.registry import ToolRegistry


def test_registry_returns_builtin_tool_schemas(config, tmp_path):
    registry = ToolRegistry.from_builtin(config=config, workdir=tmp_path)

    names = [schema["function"]["name"] for schema in registry.schemas()]

    assert names == ["bash", "read_file", "write_file", "edit_file"]
```

```python
from deep_coder.tools.read_file.tool import ReadFileTool
from deep_coder.tools.write_file.tool import WriteFileTool
from deep_coder.tools.edit_file.tool import EditFileTool


def test_file_tools_round_trip_content(config, tmp_path):
    writer = WriteFileTool(config=config, workdir=tmp_path)
    reader = ReadFileTool(config=config, workdir=tmp_path)
    editor = EditFileTool(config=config, workdir=tmp_path)

    writer.exec({"path": "notes.txt", "content": "hello world"})
    editor.exec({"path": "notes.txt", "old_text": "world", "new_text": "runtime"})

    assert reader.exec({"path": "notes.txt"}) == "hello runtime"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_registry.py tests/tools/test_file_tools.py -v`
Expected: FAIL because the registry and tool modules do not exist

**Step 3: Write minimal implementation**

```python
class ToolRegistry:
    def __init__(self, tools):
        self._tools = {tool.schema()["function"]["name"]: tool for tool in tools}

    @classmethod
    def from_builtin(cls, config, workdir):
        return cls(
            [
                BashTool(config=config, workdir=workdir),
                ReadFileTool(config=config, workdir=workdir),
                WriteFileTool(config=config, workdir=workdir),
                EditFileTool(config=config, workdir=workdir),
            ]
        )

    def schemas(self):
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        return self._tools[name].exec(arguments)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_registry.py tests/tools/test_file_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tools/__init__.py deep_coder/tools/registry.py deep_coder/tools/bash/tool.py deep_coder/tools/read_file/tool.py deep_coder/tools/write_file/tool.py deep_coder/tools/edit_file/tool.py tests/tools/test_registry.py tests/tools/test_file_tools.py
git commit -m "feat: add builtin runtime tools"
```

### Task 2: Implement filesystem-backed session storage

**Files:**
- Create: `deep_coder/context/session.py`
- Create: `deep_coder/context/stores/filesystem/store.py`
- Modify: `deep_coder/context/stores/__init__.py`
- Test: `tests/context/test_filesystem_store.py`

**Step 1: Write the failing tests**

```python
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore


def test_filesystem_store_creates_and_lists_sessions(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)

    session = store.open()
    store.save(session)

    listed = store.list_sessions()

    assert listed == [session.meta()]
```

```python
def test_filesystem_store_persists_messages(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)

    session = store.open()
    session.append({"role": "user", "content": "hello"})
    store.save(session)

    reopened = store.open(locator={"id": session.session_id})

    assert reopened.messages == [{"role": "user", "content": "hello"}]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/context/test_filesystem_store.py -v`
Expected: FAIL because the session and filesystem store modules do not exist

**Step 3: Write minimal implementation**

```python
class Session:
    def __init__(self, session_id: str, root: Path, messages=None, strategy_state=None):
        self.session_id = session_id
        self.root = root
        self.messages = messages or []
        self.strategy_state = strategy_state or {}

    def append(self, event: dict) -> None:
        self.messages.append(event)

    def meta(self) -> dict:
        return {"id": self.session_id}
```

```python
class FileSystemSessionStore(SessionStoreBase):
    def __init__(self, root: Path):
        self.root = Path(root)
        self.sessions_dir = self.root / "sessions"

    def list_sessions(self) -> list[dict]:
        ...

    def open(self, locator: dict | None = None):
        ...

    def save(self, session) -> None:
        ...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/context/test_filesystem_store.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/context/session.py deep_coder/context/stores/__init__.py deep_coder/context/stores/filesystem/store.py tests/context/test_filesystem_store.py
git commit -m "feat: add filesystem session store"
```

### Task 3: Implement the simple append-only context strategy

**Files:**
- Create: `deep_coder/context/strategies/simple_history/strategy.py`
- Modify: `deep_coder/context/manager.py`
- Modify: `deep_coder/context/strategies/__init__.py`
- Test: `tests/context/test_simple_history_strategy.py`

**Step 1: Write the failing tests**

```python
from deep_coder.context.session import Session
from deep_coder.context.strategies.simple_history.strategy import SimpleHistoryContextStrategy


def test_simple_history_strategy_prepares_messages_from_session_history(tmp_path):
    strategy = SimpleHistoryContextStrategy()
    session = Session(session_id="s1", root=tmp_path)
    session.append({"role": "assistant", "content": "previous"})

    messages = strategy.prepare_messages(
        session=session,
        system_prompt="system text",
        user_input="next question",
    )

    assert messages == [
        {"role": "system", "content": "system text"},
        {"role": "assistant", "content": "previous"},
        {"role": "user", "content": "next question"},
    ]
```

```python
def test_context_manager_records_events_and_flushes(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)
    strategy = SimpleHistoryContextStrategy()
    manager = ContextManager(store=store, strategy=strategy)

    session = manager.open()
    manager.record_event(session, {"role": "user", "content": "hello"})
    manager.flush(session)

    reopened = manager.open(locator={"id": session.session_id})
    assert reopened.messages == [{"role": "user", "content": "hello"}]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/context/test_simple_history_strategy.py -v`
Expected: FAIL because the strategy module does not exist

**Step 3: Write minimal implementation**

```python
class SimpleHistoryContextStrategy(ContextStrategyBase):
    def prepare_messages(self, session, system_prompt: str, user_input: str) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt},
            *session.messages,
            {"role": "user", "content": user_input},
        ]

    def record_event(self, session, event: dict) -> None:
        session.append(event)

    def maybe_compact(self, session, usage: dict | None = None) -> None:
        return None

    def manifest(self) -> dict:
        return {"name": "simple_history"}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/context/test_simple_history_strategy.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/context/manager.py deep_coder/context/strategies/__init__.py deep_coder/context/strategies/simple_history/strategy.py tests/context/test_simple_history_strategy.py
git commit -m "feat: add simple history context strategy"
```

### Task 4: Implement the prompt module and runtime factory

**Files:**
- Create: `deep_coder/prompts/deepcoder/prompt.py`
- Modify: `deep_coder/prompts/__init__.py`
- Modify: `deep_coder/main.py`
- Test: `tests/prompts/test_deepcoder_prompt.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing tests**

```python
from deep_coder.prompts.deepcoder.prompt import DeepCoderPrompt


def test_prompt_render_mentions_workdir_and_tool_names(config):
    prompt = DeepCoderPrompt(config=config)
    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[
            {"function": {"name": "bash"}},
            {"function": {"name": "read_file"}},
        ],
    )

    assert str(config.workdir) in text
    assert "bash" in text
    assert "read_file" in text
```

```python
from deep_coder.main import build_runtime


def test_build_runtime_returns_expected_components(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    runtime = build_runtime(workdir=tmp_path, state_dir=tmp_path / ".deepcode")

    assert runtime["model"].manifest()["provider"] == "deepseek"
    assert runtime["prompt"].manifest()["name"] == "deepcoder"
    assert runtime["context"].strategy.manifest()["name"] == "simple_history"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/prompts/test_deepcoder_prompt.py tests/test_main.py -v`
Expected: FAIL because the prompt module and runtime builder do not exist

**Step 3: Write minimal implementation**

```python
class DeepCoderPrompt(PromptBase):
    def __init__(self, config):
        self.config = config

    def render(self, session_snapshot: dict, tool_schemas: list[dict]) -> str:
        tool_names = ", ".join(schema["function"]["name"] for schema in tool_schemas)
        return f"You are Deep Coder working in {self.config.workdir}. Available tools: {tool_names}"

    def manifest(self) -> dict:
        return {"name": "deepcoder"}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/prompts/test_deepcoder_prompt.py tests/test_main.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/prompts/__init__.py deep_coder/prompts/deepcoder/prompt.py deep_coder/main.py tests/prompts/test_deepcoder_prompt.py tests/test_main.py
git commit -m "feat: add runtime prompt and factory"
```

### Task 5: Implement the harness loop

**Files:**
- Create: `deep_coder/harness/result.py`
- Create: `deep_coder/harness/deepcoder/harness.py`
- Modify: `deep_coder/harness/__init__.py`
- Test: `tests/harness/test_deepcoder_harness.py`

**Step 1: Write the failing tests**

```python
from types import SimpleNamespace

from deep_coder.harness.deepcoder.harness import DeepCoderHarness


def test_harness_executes_tool_calls_until_final_answer(tmp_path):
    class FakeModel:
        def __init__(self):
            self.calls = 0

        def complete(self, request):
            self.calls += 1
            if self.calls == 1:
                return {
                    "content": None,
                    "tool_calls": [{"id": "tool-1", "name": "read_file", "arguments": {"path": "README.md"}}],
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

    class FakeTools:
        def schemas(self):
            return [{"function": {"name": "read_file"}}]

        def execute(self, name, arguments):
            assert name == "read_file"
            return "file contents"

    session = Session(session_id="s1", root=tmp_path)
    store = FileSystemSessionStore(root=tmp_path)
    context = ContextManager(store=store, strategy=SimpleHistoryContextStrategy())
    prompt = DeepCoderPrompt(config=SimpleNamespace(workdir=tmp_path))
    harness = DeepCoderHarness(
        config=SimpleNamespace(),
        model=FakeModel(),
        prompt=prompt,
        context=context,
        tools=FakeTools(),
    )

    result = harness.run(session_locator={"id": session.session_id}, user_input="read README")

    assert result.final_text == "done"
    assert result.tool_results == ["file contents"]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/harness/test_deepcoder_harness.py -v`
Expected: FAIL because the harness module does not exist

**Step 3: Write minimal implementation**

```python
class DeepCoderHarness(HarnessBase):
    def run(self, session_locator, user_input: str):
        session = self.context.open(locator=session_locator)
        tool_results = []

        while True:
            system_prompt = self.prompt.render(
                session_snapshot=session.meta(),
                tool_schemas=self.tools.schemas(),
            )
            messages = self.context.prepare_messages(session, system_prompt, user_input)
            response = self.model.complete({"messages": messages, "tools": self.tools.schemas()})

            if response["tool_calls"]:
                self.context.record_event(session, {"role": "assistant", "content": response["content"] or "", "tool_calls": response["tool_calls"]})
                for tool_call in response["tool_calls"]:
                    output = self.tools.execute(tool_call["name"], tool_call["arguments"])
                    tool_results.append(output)
                    self.context.record_event(session, {"role": "tool", "tool_call_id": tool_call["id"], "content": output})
                self.context.flush(session)
                continue

            self.context.record_event(session, {"role": "assistant", "content": response["content"] or ""})
            self.context.flush(session)
            return HarnessResult(final_text=response["content"] or "", tool_results=tool_results, session_id=session.session_id)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/harness/test_deepcoder_harness.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/harness/__init__.py deep_coder/harness/result.py deep_coder/harness/deepcoder/harness.py tests/harness/test_deepcoder_harness.py
git commit -m "feat: add deep coder harness runtime"
```

### Task 6: Verify the backend runtime integration

**Files:**
- Create: `tests/integration/test_runtime_smoke.py`
- Modify: `agentLoop.py`

**Step 1: Write the failing tests**

```python
def test_agentloop_remains_reference_example():
    import agentLoop

    assert hasattr(agentLoop, "client")
```

```python
from deep_coder.main import build_runtime


def test_runtime_smoke_builds_full_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    runtime = build_runtime(workdir=tmp_path, state_dir=tmp_path / ".deepcode")

    assert runtime["tools"].schemas()
    assert runtime["harness"] is not None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_runtime_smoke.py -v`
Expected: FAIL because the runtime builder does not yet assemble the full backend

**Step 3: Write minimal implementation**

```python
def build_runtime(workdir=None, state_dir=None):
    ...
    return {
        "config": config,
        "model": model,
        "tools": tools,
        "context": context,
        "prompt": prompt,
        "harness": harness,
    }
```

**Step 4: Run tests to verify they pass**

Run: `pytest -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agentLoop.py tests/integration/test_runtime_smoke.py
git commit -m "test: verify backend runtime integration"
```
