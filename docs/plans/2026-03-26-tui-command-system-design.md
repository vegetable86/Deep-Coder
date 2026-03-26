# TUI Command System Design

**Date:** 2026-03-26

## Goal

Design the next TUI milestone so `deepcode` supports built-in slash commands for model selection, project-scoped session history, and exit behavior, while keeping command data logic out of the UI layer and simplifying token-usage display.

## Product Scope

This design adds:

- slash-command discovery from the composer with `/`
- dynamic prefix filtering for commands
- `Tab` completion for the selected command
- built-in `/model`, `/history`, and `/exit`
- idle-only command execution with a clear warning while a turn is running
- global model persistence in `~/.deepcode/config.toml`
- project-only session history in the command flow
- a compact one-line usage block in the timeline

This design does not add:

- command recording into session history
- a global cross-project history browser
- command execution during model/tool runtime
- a permanent side pane for commands or history
- a more complex grouped assistant-plus-usage rendering model

## Core Decisions

### Dedicated Command Subsystem

The command feature should be implemented as a dedicated subsystem under `deep_coder/tui/commands/`, not as ad hoc parsing inside `DeepCodeApp`.

Recommended module split:

- `base.py`
- `parser.py`
- `registry.py`
- `builtin/model.py`
- `builtin/history.py`
- `builtin/exit.py`

This keeps future command growth modular. Most new commands should only require a new plugin file plus optional UI rendering changes.

### UI Layer Versus Command Layer

The TUI remains responsible for UI behavior only:

- composer interaction
- palette visibility
- focus and selection state
- timeline rendering
- modal/screen presentation
- status and warning display

The command layer owns data and command policy:

- slash parsing
- prefix matching
- command availability
- global config reads and writes
- project session lookup
- idle-only execution rules
- command result payloads

The UI should consume structured command results instead of touching storage or config files directly.

## Command UX

### Entry And Filtering

- When the composer text starts with `/`, the app enters command mode.
- A command palette appears under the composer.
- The palette shows all commands when the input is just `/`.
- As the user types, the command list filters by prefix dynamically.
- Matching should be simple and predictable: command name prefix first, then aliases if added later.

### Selection And Completion

- The highlighted command row is keyboard-selectable.
- `Tab` fills the currently selected command into the composer.
- Arrow keys move the highlight.
- `Enter` executes the selected command when the app is idle.
- Non-command composer input keeps the current chat-submission behavior.

### Initial Built-In Commands

- `/model`
- `/history`
- `/exit`

Each command should expose a summary string so the palette can show both the command name and a short description.

## Command Behavior

### `/model`

- Shows available model options from the command layer.
- Selecting a model updates the live runtime model immediately.
- The selected model is persisted globally in `~/.deepcode/config.toml`.
- The next `deepcode` launch uses that persisted default model.
- The status strip refreshes to show the active model name.

Global model persistence should stay in the existing config file rather than creating a second config store.

### `/history`

- Shows stored session history for the active project only.
- The list should not include sessions from other projects.
- A fresh empty session that has no persisted messages/events should not appear.
- Selecting a history entry switches the visible timeline to that stored session.
- Command execution itself is not recorded as a chat message.

### `/exit`

- Quits the TUI only when the app is idle.
- If a turn is running, the command must not execute.
- In that case the user sees the exact warning:
  - `system now in runtime, please wait for the work end`

The same idle-only rule applies to the other built-in commands.

## Config And Persistence

### Global Config

`~/.deepcode/config.toml` already stores project registry data. It should also store one global model default.

Recommended shape:

```toml
current_project = "/abs/path/to/repo"
default_model = "deepseek-chat"

[[projects]]
path = "/abs/path/to/repo"
name = "repo"
key = "repo-abc123"
last_opened_at = "2026-03-26T01:00:00Z"
```

The project registry should round-trip both:

- top-level global settings such as `default_model`
- the existing `[[projects]]` records

### Session Persistence

- Session files stay under `~/.deepcode/projects/<project-key>/sessions/...`
- Empty fresh sessions remain in-memory only
- Storage should continue to happen only after a real harness turn records messages/events
- `/history` reads only persisted project sessions

This keeps the command system aligned with current persistence semantics.

## TUI Rendering Changes

### Usage Block

The `usage_reported` event should remain its own timeline block. The change is formatting only.

The usage block should render on one line with simplified labels:

- `prompt`
- `usage`
- `hit`
- `miss`

Recommended output:

```text
prompt 10 | usage 15 | hit 3 | miss 7
```

This keeps replay and live-event rendering simple because the event model does not change.

### Command Feedback

Warnings or local command feedback should appear in TUI-owned UI state such as the status strip or command feedback area. They should not be appended into session history.

## Testing Strategy

### Command Layer Tests

Add tests for:

- parsing slash input
- dynamic prefix filtering
- `Tab` completion targets
- idle-only command availability
- `/history` returning only current-project persisted sessions
- `/model` updating config plus live runtime state
- `/exit` returning a quit action only while idle

### TUI Tests

Add tests for:

- `/` opening the command palette
- dynamic filtered command rows
- `Tab` filling the selected command
- `/history` showing the active project’s stored sessions
- idle-only warning display
- one-line usage rendering in replay and live-event views

### Config Tests

Add tests that `config.toml` round-trips:

- `current_project`
- `default_model`
- project records

## Implementation Notes

- Keep `DeepCodeApp` thin. It should dispatch to the command layer, not own slash-command business logic.
- Prefer extending the existing project registry/config path instead of inventing a second global settings layer.
- Preserve alignment between replay and live rendering paths.
- Keep command data local to the TUI/runtime boundary and out of session chat history.
