# Deep Coder Architecture

## Goal

`Deep Coder` is a single-agent coding runtime built on the DeepSeek API through the OpenAI-compatible Python SDK.

The design principle is:

- `Harness` is the car.
- `Model` is the driver.

The harness owns runtime orchestration. The model layer only knows how to talk to DeepSeek. Tools, prompts, and context management are separate modules so the runtime can be extended without rewriting the loop.

## Scope

Version 1 includes:

- Single-agent coding loop
- DeepSeek as the only model provider
- OpenAI-compatible SDK integration
- Local coding tools such as bash and file operations
- Persistent local sessions
- Pluggable runtime context strategies
- Config and prompt storage under `~/.deepcode/`

Version 1 does not include:

- Parent/subagent orchestration
- Task graph management
- Background job manager
- Multi-provider support in production

The architecture still leaves room for those later, but they are not part of the first implementation target.

## Core Principles

### 1. Abstract base classes define extension points

Every major module family exposes a base class. Concrete implementations inherit from that base class and can be swapped with minimal code changes.

### 2. Machine-readable contracts are explicit

Comments and docstrings are for humans. Runtime discovery must use explicit methods such as `schema()` or `manifest()` that return dictionaries.

### 3. Harness does not own business details

The harness coordinates the loop but does not know DeepSeek SDK details, tool internals, or context storage internals.

### 4. User-facing session listing is stable

Users should always be able to list historical sessions. Internally, different context algorithms may store extra state, but that complexity is hidden behind stable session APIs.

### 5. Local state is outside the repository

Runtime sessions, prompt overrides, and TUI config are stored under `~/.deepcode/` so the project repository stays focused on source code.

## Top-Level Modules

### Harness

`Harness` owns the single-agent runtime loop:

1. Load config
2. Load prompt profile
3. Open or create a session
4. Build request messages through the context layer
5. Call the model
6. Execute tool calls
7. Record tool outputs and assistant messages
8. Stop when the model returns a final answer

The harness is the only place where these modules meet.

### Model

The model layer wraps the OpenAI-compatible SDK for DeepSeek.

Responsibilities:

- Initialize the SDK client
- Set `base_url`
- Select model id
- Send normalized chat completion requests
- Return normalized responses
- Extract usage and finish state
- Apply retry policy for transient errors such as `429`, `500`, and `503`

The model module must not know how tools execute on the local machine.

### Tools

Each tool is an isolated capability such as:

- `bash`
- `read_file`
- `write_file`
- `edit_file`

Tools expose a schema to the model and an execution entrypoint to the harness.

### Prompt

Prompt modules generate the active system prompt.

This layer supports:

- built-in prompt profiles in the repository
- future alternate prompt styles
- user prompt overrides stored under `~/.deepcode/`

### Context

The context layer replaces the previous split between `SessionMemory` and `Compactor`.

It is responsible for:

- session persistence
- session listing
- message history assembly
- runtime context-window control
- algorithm-specific compaction or abstraction

To avoid hardcoding one storage or compaction style, the context layer is split into a stable manager plus two pluggable sublayers:

- `SessionStoreBase`
- `ContextStrategyBase`

## Base-Class Contracts

### HarnessBase

```python
class HarnessBase(ABC):
    @abstractmethod
    def __init__(self, config, model, prompt, context, tools): ...

    @abstractmethod
    def run(self, session_locator, user_input: str): ...
```

Purpose:

- owns orchestration only
- depends on abstractions, not implementations

### ModelBase

```python
class ModelBase(ABC):
    @abstractmethod
    def __init__(self, config): ...

    @abstractmethod
    def complete(self, request: dict) -> dict: ...

    @abstractmethod
    def manifest(self) -> dict: ...
```

Expected response shape:

```python
{
    "content": str | None,
    "tool_calls": list[dict],
    "usage": dict | None,
    "finish_reason": str | None,
    "raw_response": object,
}
```

### ToolBase

```python
class ToolBase(ABC):
    @abstractmethod
    def __init__(self, config, workdir): ...

    @abstractmethod
    def exec(self, arguments: dict) -> str: ...

    @abstractmethod
    def schema(self) -> dict: ...
```

The schema is passed directly to the model request as part of the `tools` payload.

### PromptBase

```python
class PromptBase(ABC):
    @abstractmethod
    def __init__(self, config): ...

    @abstractmethod
    def render(self, session_snapshot: dict, tool_schemas: list[dict]) -> str: ...

    @abstractmethod
    def manifest(self) -> dict: ...
```

### SessionStoreBase

```python
class SessionStoreBase(ABC):
    @abstractmethod
    def list_sessions(self) -> list[dict]: ...

    @abstractmethod
    def open(self, locator: dict | None = None): ...

    @abstractmethod
    def save(self, session) -> None: ...
```

This is the persistence boundary. It keeps the user-visible session list stable.

### ContextStrategyBase

```python
class ContextStrategyBase(ABC):
    @abstractmethod
    def prepare_messages(self, session, system_prompt: str, user_input: str) -> list[dict]: ...

    @abstractmethod
    def record_event(self, session, event: dict) -> None: ...

    @abstractmethod
    def maybe_compact(self, session, usage: dict | None = None) -> None: ...

    @abstractmethod
    def manifest(self) -> dict: ...
```

This is the algorithm boundary. A rolling-window strategy and a hierarchical-abstraction strategy can both plug in here without changing the harness API.

### ContextManager

`ContextManager` is a stable facade composed from store and strategy implementations.

```python
class ContextManager:
    def __init__(self, store: SessionStoreBase, strategy: ContextStrategyBase): ...
    def list_sessions(self) -> list[dict]: ...
    def open(self, locator: dict | None = None): ...
    def prepare_messages(self, session, system_prompt: str, user_input: str) -> list[dict]: ...
    def record_event(self, session, event: dict) -> None: ...
    def flush(self, session) -> None: ...
```

This keeps the harness API small while allowing advanced context algorithms internally.

## Directory Layout

The repository should move from a single-file prototype to a package layout:

```text
deep_coder/
  main.py
  config.py
  harness/
    base.py
    deepcoder/
      harness.py
  models/
    base.py
    deepseek/
      model.py
  tools/
    base.py
    registry.py
    bash/
      tool.py
    read_file/
      tool.py
    write_file/
      tool.py
    edit_file/
      tool.py
  prompts/
    base.py
    deepcoder/
      prompt.py
  context/
    manager.py
    stores/
      base.py
      filesystem/
        store.py
    strategies/
      base.py
      rolling_window/
        strategy.py
      hierarchy/
        strategy.py
```

This layout supports the current DeepSeek-only sample while preserving a clean future path for additional implementations.

## Runtime Storage Layout

Local runtime state lives under `~/.deepcode/`:

```text
~/.deepcode/
  config.toml
  tui.toml
  sessions/
    <session-key>/
      meta.json
      messages.jsonl
      context/
        <strategy-name>/
          state.json
  prompts/
    active_prompt.txt
    overrides/
```

Meaning:

- `config.toml` stores global app configuration
- `tui.toml` stores CLI or TUI preferences
- `sessions/` stores persistent history and per-strategy state
- `prompts/` stores selected prompt overrides outside the repo

## Request and Response Flow

The v1 loop is:

1. CLI receives user input
2. Harness opens the selected session through `ContextManager`
3. Prompt module renders the active system prompt
4. Context strategy builds request messages
5. Harness asks `ToolRegistry` for all tool schemas
6. Harness calls `DeepSeekModel`
7. If the model emits tool calls, harness executes the requested tools
8. Harness records tool events through `ContextManager`
9. Harness repeats until the model returns a final answer
10. Harness flushes the session to persistent storage

## DeepSeek Integration Notes

The current local DeepSeek docs show that the first implementation only needs:

- `POST /chat/completions`
- tool calls on chat completions
- `GET /models`

Operational concerns to handle inside the DeepSeek model implementation:

- `429` rate limits
- `500` server faults
- `503` busy server responses
- long-lived HTTP connections before inference begins

These concerns belong in the model implementation, not in the harness.

## Mapping From agentLoop.py

The current `agentLoop.py` mixes many concerns in one file:

- prompt text
- SDK client creation
- tool definitions
- tool execution
- context compaction
- background task management
- task management
- subagent logic
- CLI loop

For v1, the split should keep only the single-agent essentials:

- DeepSeek SDK client
- prompt generation
- tool registry and built-in coding tools
- context manager with pluggable strategy
- harness loop
- CLI entrypoint

The following prototype parts should not be carried into v1 core:

- `TaskManager`
- `BackgroundManager`
- `run_subagent`
- parent versus child tool split

They can return in later phases as separate architecture work.

## Future Expansion

This design leaves clear expansion points:

- add `models/gpt/` later without changing the harness contract
- add more prompt profiles under `prompts/`
- add new context strategies under `context/strategies/`
- add tool packages under `tools/`
- add multi-agent orchestration as a new layer above the single-agent harness

## Recommended First Concrete Classes

Version 1 should start with:

- `DeepCoderHarness`
- `DeepSeekModel`
- `DeepCoderPrompt`
- `FileSystemSessionStore`
- `RollingWindowContextStrategy`
- `BashTool`
- `ReadFileTool`
- `WriteFileTool`
- `EditFileTool`

This is the minimum shape that turns the prototype into a clean, extensible architecture.
