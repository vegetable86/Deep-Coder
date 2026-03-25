# Deep Coder Design

**Goal:** Define the v1 architecture for `Deep Coder` as a single-agent coding runtime on top of DeepSeek with clean module boundaries and extensible base classes.

**Context:** The repository currently contains a single prototype file, `agentLoop.py`, which mixes SDK integration, tool execution, prompt construction, context handling, subagent flow, background tasks, and CLI logic.

## Decisions

### Product Scope

- Build a single-agent coder first
- Use DeepSeek only for the initial sample
- Use the OpenAI-compatible Python SDK
- Keep subagents, background jobs, and task graphs out of v1

### Architectural Principle

- `Harness` is the runtime vehicle
- `Model` is the driver adapter
- All extensible module families must have base classes

### Base-Class Rule

Each major module family exposes a base class with explicit machine-readable methods:

- tools use `schema()`
- models use `manifest()`
- prompts use `manifest()`

Comments are documentation only and are not parsed as runtime metadata.

### Context Design

The previous `SessionMemory` and `Compactor` split is replaced by a more flexible context design:

- `ContextManager` is the stable facade
- `SessionStoreBase` is the persistence plugin boundary
- `ContextStrategyBase` is the runtime context algorithm boundary

This keeps historical session listing stable while allowing advanced context algorithms internally.

### Storage Rule

Persistent runtime state lives outside the repository under `~/.deepcode/`, including:

- sessions
- prompt overrides
- TUI configuration

## Approved Module Shape

- `HarnessBase`
- `ModelBase`
- `ToolBase`
- `PromptBase`
- `SessionStoreBase`
- `ContextStrategyBase`
- `ContextManager`

## Approved Repository Layout

```text
deep_coder/
  main.py
  config.py
  harness/
  models/
  tools/
  prompts/
  context/
```

Concrete implementations live in their own implementation folders, for example:

- `models/deepseek/`
- `prompts/deepcoder/`
- `context/stores/filesystem/`
- `context/strategies/rolling_window/`

## Approved Runtime Layout

```text
~/.deepcode/
  config.toml
  tui.toml
  sessions/
  prompts/
```

## Why This Design

This design removes the monolithic structure of `agentLoop.py` without prematurely solving phase-2 problems. It also preserves the user’s intended extension model: adding a new provider later should require implementing a new concrete class and changing configuration, not rewriting the harness.

## Follow-Up

The next step is to create an implementation plan for splitting `agentLoop.py` into the new package structure, starting with the single-agent DeepSeek path and a default rolling-window context strategy.
