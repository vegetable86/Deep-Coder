# Deep Coder V1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor `agentLoop.py` into a modular `Deep Coder` package with a single-agent harness, DeepSeek model adapter, pluggable tools, and pluggable context management.

**Architecture:** Build a package-based runtime around stable base classes. Keep the harness small, move DeepSeek SDK logic into a model adapter, move tool execution into tool classes plus a registry, and replace the old memory/compaction split with `ContextManager + SessionStore + ContextStrategy`.

**Tech Stack:** Python 3, OpenAI-compatible SDK, pytest, local filesystem persistence

---

### Task 1: Create the package skeleton and shared configuration

**Files:**
- Create: `deep_coder/__init__.py`
- Create: `deep_coder/config.py`
- Create: `deep_coder/main.py`
- Modify: `agentLoop.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
from deep_coder.config import RuntimeConfig


def test_runtime_config_has_deepseek_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = RuntimeConfig.from_env(workdir=tmp_path)

    assert config.model_provider == "deepseek"
    assert config.model_name == "deepseek-chat"
    assert config.state_dir.name == ".deepcode"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError` for `deep_coder`

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass
class RuntimeConfig:
    model_provider: str
    model_name: str
    api_key: str
    base_url: str
    workdir: Path
    state_dir: Path

    @classmethod
    def from_env(cls, workdir: Path | None = None):
        workdir = workdir or Path.cwd()
        return cls(
            model_provider="deepseek",
            model_name="deepseek-chat",
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
            workdir=workdir,
            state_dir=Path.home() / ".deepcode",
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agentLoop.py deep_coder/__init__.py deep_coder/config.py deep_coder/main.py tests/test_config.py
git commit -m "feat: add deep coder package skeleton"
```

### Task 2: Introduce the base-class contracts

**Files:**
- Create: `deep_coder/harness/base.py`
- Create: `deep_coder/models/base.py`
- Create: `deep_coder/tools/base.py`
- Create: `deep_coder/prompts/base.py`
- Create: `deep_coder/context/stores/base.py`
- Create: `deep_coder/context/strategies/base.py`
- Create: `deep_coder/context/manager.py`
- Test: `tests/test_base_contracts.py`

**Step 1: Write the failing test**

```python
from deep_coder.tools.base import ToolBase
from deep_coder.models.base import ModelBase


def test_tool_and_model_base_classes_define_required_methods():
    assert hasattr(ToolBase, "schema")
    assert hasattr(ToolBase, "exec")
    assert hasattr(ModelBase, "complete")
    assert hasattr(ModelBase, "manifest")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_base_contracts.py -v`
Expected: FAIL because the base modules do not exist

**Step 3: Write minimal implementation**

```python
from abc import ABC, abstractmethod


class ToolBase(ABC):
    @abstractmethod
    def __init__(self, config, workdir): ...

    @abstractmethod
    def exec(self, arguments: dict) -> str: ...

    @abstractmethod
    def schema(self) -> dict: ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_base_contracts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/harness/base.py deep_coder/models/base.py deep_coder/tools/base.py deep_coder/prompts/base.py deep_coder/context/stores/base.py deep_coder/context/strategies/base.py deep_coder/context/manager.py tests/test_base_contracts.py
git commit -m "feat: add deep coder base contracts"
```

### Task 3: Implement the DeepSeek model adapter

**Files:**
- Create: `deep_coder/models/deepseek/model.py`
- Test: `tests/models/test_deepseek_model.py`

**Step 1: Write the failing test**

```python
from deep_coder.models.deepseek.model import DeepSeekModel


def test_deepseek_manifest_identifies_provider():
    manifest = DeepSeekModel.manifest()

    assert manifest["provider"] == "deepseek"
    assert manifest["transport"] == "openai-compatible-sdk"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/models/test_deepseek_model.py -v`
Expected: FAIL because `DeepSeekModel` does not exist

**Step 3: Write minimal implementation**

```python
from openai import OpenAI


class DeepSeekModel(ModelBase):
    def __init__(self, config):
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    @staticmethod
    def manifest() -> dict:
        return {
            "provider": "deepseek",
            "transport": "openai-compatible-sdk",
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/models/test_deepseek_model.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/models/deepseek/model.py tests/models/test_deepseek_model.py
git commit -m "feat: add deepseek model adapter"
```

### Task 4: Implement the tool system and built-in coding tools

**Files:**
- Create: `deep_coder/tools/registry.py`
- Create: `deep_coder/tools/bash/tool.py`
- Create: `deep_coder/tools/read_file/tool.py`
- Create: `deep_coder/tools/write_file/tool.py`
- Create: `deep_coder/tools/edit_file/tool.py`
- Test: `tests/tools/test_registry.py`
- Test: `tests/tools/test_file_tools.py`

**Step 1: Write the failing test**

```python
from deep_coder.tools.registry import ToolRegistry


def test_registry_returns_tool_schemas(config, tmp_path):
    registry = ToolRegistry.from_builtin(config=config, workdir=tmp_path)

    names = [tool["function"]["name"] for tool in registry.schemas()]

    assert "bash" in names
    assert "read_file" in names
    assert "write_file" in names
    assert "edit_file" in names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_registry.py tests/tools/test_file_tools.py -v`
Expected: FAIL because the registry and tools do not exist

**Step 3: Write minimal implementation**

```python
class ToolRegistry:
    def __init__(self, tools):
        self._tools = {tool.schema()["function"]["name"]: tool for tool in tools}

    def schemas(self):
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        return self._tools[name].exec(arguments)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_registry.py tests/tools/test_file_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/tools/registry.py deep_coder/tools/bash/tool.py deep_coder/tools/read_file/tool.py deep_coder/tools/write_file/tool.py deep_coder/tools/edit_file/tool.py tests/tools/test_registry.py tests/tools/test_file_tools.py
git commit -m "feat: add builtin coding tools"
```

### Task 5: Implement the context stack

**Files:**
- Create: `deep_coder/context/stores/filesystem/store.py`
- Create: `deep_coder/context/strategies/rolling_window/strategy.py`
- Modify: `deep_coder/context/manager.py`
- Test: `tests/context/test_filesystem_store.py`
- Test: `tests/context/test_rolling_window_strategy.py`

**Step 1: Write the failing test**

```python
from deep_coder.context.manager import ContextManager
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore
from deep_coder.context.strategies.rolling_window.strategy import RollingWindowContextStrategy


def test_context_manager_lists_and_opens_sessions(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)
    strategy = RollingWindowContextStrategy(max_messages=6)
    manager = ContextManager(store=store, strategy=strategy)

    session = manager.open()

    assert session is not None
    assert manager.list_sessions() == [session.meta()]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/context/test_filesystem_store.py tests/context/test_rolling_window_strategy.py -v`
Expected: FAIL because the store and strategy do not exist

**Step 3: Write minimal implementation**

```python
class ContextManager:
    def __init__(self, store, strategy):
        self.store = store
        self.strategy = strategy

    def list_sessions(self):
        return self.store.list_sessions()

    def open(self, locator=None):
        return self.store.open(locator=locator)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/context/test_filesystem_store.py tests/context/test_rolling_window_strategy.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/context/stores/filesystem/store.py deep_coder/context/strategies/rolling_window/strategy.py deep_coder/context/manager.py tests/context/test_filesystem_store.py tests/context/test_rolling_window_strategy.py
git commit -m "feat: add context manager store and strategy"
```

### Task 6: Implement the prompt module and harness loop

**Files:**
- Create: `deep_coder/prompts/deepcoder/prompt.py`
- Create: `deep_coder/harness/deepcoder/harness.py`
- Modify: `deep_coder/main.py`
- Test: `tests/harness/test_deepcoder_harness.py`

**Step 1: Write the failing test**

```python
def test_harness_executes_tool_calls_until_final_answer(fake_runtime):
    result = fake_runtime.harness.run(session_locator=None, user_input="read README")

    assert result.final_text == "done"
    assert result.tool_results == ["file contents"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/harness/test_deepcoder_harness.py -v`
Expected: FAIL because the harness does not exist

**Step 3: Write minimal implementation**

```python
class DeepCoderHarness(HarnessBase):
    def run(self, session_locator, user_input: str):
        session = self.context.open(locator=session_locator)
        system_prompt = self.prompt.render(session_snapshot=session.meta(), tool_schemas=self.tools.schemas())
        messages = self.context.prepare_messages(session, system_prompt, user_input)
        return self.model.complete({"messages": messages, "tools": self.tools.schemas()})
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/harness/test_deepcoder_harness.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add deep_coder/prompts/deepcoder/prompt.py deep_coder/harness/deepcoder/harness.py deep_coder/main.py tests/harness/test_deepcoder_harness.py
git commit -m "feat: add deep coder harness loop"
```

### Task 7: Retire the prototype file safely

**Files:**
- Modify: `agentLoop.py`
- Create: `tests/test_legacy_entrypoint.py`

**Step 1: Write the failing test**

```python
def test_legacy_agentloop_points_to_new_entrypoint():
    import agentLoop

    assert hasattr(agentLoop, "main")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_legacy_entrypoint.py -v`
Expected: FAIL if the old file remains the only runtime path

**Step 3: Write minimal implementation**

```python
from deep_coder.main import main


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_legacy_entrypoint.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agentLoop.py tests/test_legacy_entrypoint.py
git commit -m "refactor: retire monolithic agent loop entrypoint"
```

### Task 8: Verify the full v1 path

**Files:**
- Modify: `README.md`
- Test: `tests/`

**Step 1: Write the failing test**

```python
def test_placeholder():
    assert False, "replace with end-to-end smoke check"
```

**Step 2: Run test to verify it fails**

Run: `pytest -v`
Expected: FAIL on the placeholder end-to-end check

**Step 3: Write minimal implementation**

```python
def test_cli_smoke(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    assert True
```

**Step 4: Run test to verify it passes**

Run: `pytest -v`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md tests/
git commit -m "test: verify deep coder v1 runtime"
```
