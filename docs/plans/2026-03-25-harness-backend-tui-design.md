# Harness Backend TUI Design

**Date:** 2026-03-25

## Goal

Design the first terminal UI for the `deep_coder` backend runtime so users can launch it with `deepcode`, work inside the current workspace, and inspect project-scoped session history plus live harness activity in one structured timeline.

## Product Scope

Version 1 of the TUI should:

- launch from one command: `deepcode`
- treat the current `pwd` as the active workspace
- isolate session history by workspace/project
- show one top-to-bottom timeline for the current session
- keep the input composer in a bottom section
- stream tool calls, tool output, diffs, usage, and assistant responses live

Version 1 should not add:

- a permanent side pane
- multiple layout modes
- global mixed-project session history
- full-file before/after diff views

## Core Decisions

### Launch And Project Identity

- The user starts the app with `deepcode`.
- On startup, the app reads `pwd`.
- That exact resolved path is the project identity in v1.
- The runtime is built with `workdir=<pwd>`.
- The app registers the workspace in `~/.deepcode/config.toml` and marks it as the current project.

The design intentionally does not auto-jump to git root in v1. The active workspace is whatever directory the user launched from.

### Project Isolation

- One project owns multiple sessions.
- A session belongs to exactly one project.
- When the user launches `deepcode` inside a workspace, the TUI shows only sessions for that workspace's project.
- Different workspaces must not mix session history.

Project isolation should happen at the storage boundary, not only in the UI.

### Screen Layout

The screen has only two vertical sections:

- Top section: the main timeline, taking most of the height
- Bottom section: the composer and status strip

There is no permanent left or right pane. Session switching uses an overlay, not a fixed layout region.

## Timeline Design

### General Behavior

- The top area is one continuous timeline from top to bottom.
- New content appends at the bottom.
- The timeline auto-follows new content while the user remains at the bottom.
- If the user scrolls upward, auto-follow pauses until they return to the bottom.

### Chat Message Styling

- User and assistant messages do not render visible speaker labels such as `User Message` or `Assistant`.
- User messages use a distinct background pattern or tint.
- Assistant messages use a neutral surface distinct from user messages.
- The conversation should read naturally without explicit speaker badges.

### Structured Runtime Blocks

Runtime artifacts appear inline inside the same timeline as compact structured blocks:

- tool call
- tool output
- diff
- usage
- error

These blocks may have small headers because they are event types, not speaker labels.

### Tool Call Presentation

The timeline should show the action the model decided to take, not an abstract tool name alone.

Examples:

- `bash: mkdir aa`
- `read_file: README.md`
- `edit_file: deep_coder/main.py`

If a tool has output, the output appears directly beneath the tool call block.

### Long Output Rule

For normal tool output:

- show full output when it is reasonably short
- if it is too long, show a useful leading portion followed by `...`

Normal output should not be split into multiple timeline blocks just for pagination in v1.

### Diff Rule

For file edits:

- show only the changed hunks, like `git diff`
- do not show a full old-file/new-file dump
- show all changed hunks for the edit
- show old and new line numbers
- show deleted lines with red background
- show added lines with green background
- show unchanged context lines in a neutral/dim style

This keeps diffs complete for the edited regions while staying compact enough for a terminal timeline.

### Usage Block

Each model request should render a compact usage block with:

- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `cache_hit_tokens`
- `cache_miss_tokens`

The usage block belongs to one request and appears inline in the same timeline after that request completes.

## Bottom Section

The bottom section contains:

- one multiline composer
- one thin status strip

The status strip should show:

- current project name
- current session id
- model name
- turn state, such as `idle`, `running`, or `tool:<name>`

Default composer behavior:

- `Enter` submits
- `Shift+Enter` inserts a newline

## Session Switching

- There is no permanent session list pane in the default layout.
- The user opens a session switcher overlay from the main screen.
- The overlay lists only sessions owned by the active project.
- Selecting a session closes the overlay and redraws the current timeline from that session history.

## Color Direction

Recommended default color roles:

- user message: blue or cyan-tinted patterned background
- assistant message: neutral surface
- active tool call: yellow accent
- tool output: neutral/dim surface
- success accent: green
- error accent: red
- diff additions: green background
- diff deletions: red background
- diff context lines: dim neutral
- usage block: teal or magenta accent

The colors should distinguish information types clearly without turning the screen into a noisy log viewer.

## Backend Runtime Contract

### Project-Scoped Runtime

When `deepcode` launches:

1. resolve `pwd`
2. load or register the project in `~/.deepcode/config.toml`
3. compute a project storage root under `~/.deepcode/projects/<project-key>/`
4. build the runtime with:
   - `workdir=<pwd>`
   - `state_dir=~/.deepcode/projects/<project-key>`

`RuntimeConfig` should grow to carry project identity:

- `project_path`
- `project_key`
- `project_name`

### Live Event Stream

The harness should emit structured live events while a turn runs so the TUI can render the timeline directly from runtime activity.

Recommended event set:

- `turn_started`
- `message_committed`
- `tool_called`
- `tool_output`
- `tool_diff`
- `usage_reported`
- `turn_finished`

Each event should include enough identity for the TUI to map it to the active session and turn.

### Event Semantics

- `message_committed` carries ordinary user/assistant text
- `tool_called` carries the tool identity plus a readable command/action string
- `tool_output` carries plain tool output and whether it was truncated for display
- `tool_diff` carries a unified patch for edited hunks only
- `usage_reported` carries prompt/completion/total/cache hit/cache miss counters
- `turn_finished` marks the end of the active turn

## Persistence Design

Recommended runtime layout:

```text
~/.deepcode/
  config.toml
  projects/
    <project-key>/
      sessions/
        <session-id>/
          meta.json
          messages.jsonl
          context/
            simple_history/
              state.json
```

`config.toml` stores the project registry, for example:

```toml
current_project = "/home/wys/Deep-Coder"

[[projects]]
path = "/home/wys/Deep-Coder"
name = "Deep-Coder"
key = "deep-coder-a1b2c3"
last_opened_at = "2026-03-25T22:30:00Z"
```

Session metadata should include at least:

```json
{
  "id": "abc123def456",
  "project_key": "deep-coder-a1b2c3",
  "workspace_path": "/home/wys/Deep-Coder"
}
```

## Error Handling

Errors should render as timeline events, not modal interruptions.

- Model request failure:
  - append an error block
  - return the composer to editable state
- Tool execution failure:
  - append an error-styled tool output block
- Project registration/config failure:
  - fail before entering the TUI loop
  - print a clear terminal startup error and exit non-zero
- Diff formatting failure:
  - fall back to plain tool output
  - do not crash the TUI

## Testing Strategy

Backend coverage should verify:

- project registry creates and reopens projects by workspace path
- runtime factory builds project-scoped `state_dir`
- session store remains isolated per project root
- harness emits the expected event sequence
- edit operations produce changed-hunk unified diffs
- usage events include all required token counters

TUI coverage should verify:

- user and assistant messages render with different styles and no speaker labels
- tool call blocks show readable action strings
- long plain output truncates with `...`
- diff blocks render all changed hunks with colors and line numbers
- session switcher lists only sessions from the active project
- auto-follow pauses when the user scrolls away from the bottom

## Result

This design keeps the existing backend architecture intact:

- the harness remains the runtime orchestrator
- the session store remains the persistence boundary
- the TUI becomes a project-scoped frontend over a live event stream

The main architectural additions are:

- project registration and project-scoped storage roots
- harness event emission
- TUI rendering for a single structured timeline plus bottom composer
