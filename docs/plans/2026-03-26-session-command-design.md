# TUI Session Command Design

**Date:** 2026-03-26

## Goal

Add a built-in `/session` slash command that clears the visible timeline and resets the active TUI session so the next prompt starts in a fresh session.

## Approved Behavior

- `/session` is an idle-only built-in command.
- Running `/session` clears the current timeline immediately.
- Running `/session` resets the active `session_id` to `None`.
- `/session` does not create or persist a new session record by itself.
- The next normal composer submission creates the real new session through the existing harness/context flow.
- Existing stored sessions remain untouched.

## Design

### Command Layer

Add a dedicated `SessionCommand` under `deep_coder/tui/commands/builtin/`.

The command should return a structured result that tells the TUI to reset local session state. The command layer should not directly mutate UI fields or open context sessions.

Recommended command summary:

- `Start a new empty session`

### TUI Layer

`DeepCodeApp` should keep ownership of UI state changes:

- clear `_timeline_blocks`
- refresh the timeline widget to blank content
- set `session_id` to `None`
- keep `_turn_state` at `idle`
- refresh the status strip

The command feedback can use a short local status such as `new session`.

### Persistence

No persistence changes are needed.

- `/session` should not call into the context store
- `/history` should continue to show only persisted sessions
- the next harness turn should continue to pass `session_locator=None` when no active session exists

## Testing Strategy

Add coverage for:

- command registry exposing `/session`
- `/session` returning the structured reset action
- the TUI clearing the timeline and resetting `session_id`
- the next normal prompt after `/session` running with `session_locator=None`
