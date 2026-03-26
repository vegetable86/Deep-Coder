# Harness Backend TUI History

Date: 2026-03-26
Branch: `feat/harness-tui`
Merged into: `master` via `aaa17c9`

## Summary

This branch turned the backend runtime into a project-scoped terminal application that launches with `deepcode`, keeps session state isolated by workspace, and renders both replayable history and live harness activity in a single timeline.

The implemented TUI/runtime work now has:

- a project registry under `~/.deepcode/config.toml`
- project-scoped runtime state rooted at `~/.deepcode/projects/<project-key>/`
- normalized tool execution metadata for readable tool blocks and diffs
- persisted harness timeline events for replay and live streaming
- a Textual app shell with a top timeline and bottom composer/status strip
- a modal session switcher limited to the active project
- timeline render helpers for messages, tool output, diffs, and usage blocks
- a `deepcode` launcher that resolves the current workspace into a project and starts the TUI
- live composer submission that runs the harness and appends events into the timeline

The implementation plan file was intentionally kept out of git history during feature work and later preserved locally at `docs/plans/2026-03-25-harness-backend-tui-implementation.md`.

## Implementation Timeline

### 1. TUI design doc

Commits:

- `9b18803` `docs: add harness backend tui design`
- `73d23a2` `docs: persist tui timeline events in design`

Implemented:

- initial design for the project-scoped TUI
- explicit timeline event contract for replay and live rendering
- storage layout and launch flow for `deepcode`

Edited files:

- `docs/plans/2026-03-25-harness-backend-tui-design.md`

### 2. Project registry

Commit: `0b7f41e` `feat: add project registry`

Implemented:

- `ProjectRegistry`
- `ProjectRecord`
- workspace registration and current-project tracking under `~/.deepcode/config.toml`

Edited files:

- `deep_coder/projects/__init__.py`
- `deep_coder/projects/registry.py`
- `tests/projects/test_registry.py`

### 3. Project-scoped runtime state

Commit: `2078b1f` `feat: scope runtime state by project`

Implemented:

- project identity fields on `RuntimeConfig`
- `build_runtime(project=...)`
- project metadata and event persistence in filesystem sessions

Edited files:

- `deep_coder/config.py`
- `deep_coder/context/session.py`
- `deep_coder/context/stores/filesystem/store.py`
- `deep_coder/main.py`
- `tests/context/test_filesystem_store.py`
- `tests/test_main.py`

### 4. Tool metadata normalization

Commit: `837e679` `feat: normalize tool metadata for tui`

Implemented:

- `ToolExecutionResult`
- display-command and diff generation in `ToolRegistry`
- normalized DeepSeek tool arguments and cache-token usage counters

Edited files:

- `deep_coder/models/deepseek/model.py`
- `deep_coder/tools/registry.py`
- `deep_coder/tools/result.py`
- `tests/models/test_deepseek_model.py`
- `tests/tools/test_registry.py`

### 5. Test collection fix for duplicate test basenames

Commit: `e2685a1` `test: avoid duplicate pytest module collisions`

Implemented:

- project-level `pytest` import mode to allow `tests/projects/test_registry.py` and `tests/tools/test_registry.py` to coexist

Edited files:

- `pytest.ini`

### 6. Harness timeline events

Commit: `18cd3d6` `feat: add harness timeline events`

Implemented:

- `HarnessEventSinkBase` and `NullHarnessEventSink`
- persisted `turn_started`, `message_committed`, `tool_called`, `tool_output`, `tool_diff`, `usage_reported`, and `turn_finished` events
- separation between chat messages and timeline event log

Edited files:

- `deep_coder/harness/base.py`
- `deep_coder/harness/deepcoder/harness.py`
- `deep_coder/harness/events.py`
- `deep_coder/harness/result.py`
- `tests/harness/test_deepcoder_harness.py`

### 7. Textual shell and session switcher

Commit: `2c80873` `feat: add textual tui shell`

Implemented:

- `DeepCodeApp` shell
- session-switcher modal
- initial TUI stylesheet
- TUI test fixtures and layout tests

Edited files:

- `deep_coder/tui/__init__.py`
- `deep_coder/tui/app.py`
- `deep_coder/tui/screens/__init__.py`
- `deep_coder/tui/screens/session_switcher.py`
- `deep_coder/tui/styles.tcss`
- `requirements.txt`
- `tests/tui/conftest.py`
- `tests/tui/test_app_layout.py`

### 8. Timeline rendering and session replay

Commit: `7ab0b76` `feat: render timeline blocks and session replay`

Implemented:

- render helpers for messages, tool calls, tool output, usage, and diffs
- replay of persisted session events into the timeline
- timeline refresh/update path in the app

Edited files:

- `deep_coder/tui/app.py`
- `deep_coder/tui/render.py`
- `tests/tui/test_render.py`
- `tests/tui/test_session_switcher.py`

### 9. CLI bootstrap and live event streaming

Commit: `c6ec4c7` `feat: launch project-scoped deepcode tui`

Implemented:

- `resolve_launch_context()`
- `deepcode` launcher script
- `Enter`-to-submit composer behavior
- threaded harness execution from the TUI
- live event delivery from the harness into the timeline

Edited files:

- `deep_coder/cli.py`
- `deep_coder/tui/app.py`
- `deepcode`
- `tests/test_cli.py`
- `tests/tui/conftest.py`
- `tests/tui/test_live_events.py`

## Current TUI Shape

Main user-facing entrypoints:

- `deepcode`
- `deep_coder/cli.py`
- `deep_coder/tui/app.py`

Main project/TUI runtime modules:

- `deep_coder/projects/registry.py`
- `deep_coder/config.py`
- `deep_coder/main.py`
- `deep_coder/harness/events.py`
- `deep_coder/harness/deepcoder/harness.py`
- `deep_coder/tools/result.py`
- `deep_coder/tools/registry.py`
- `deep_coder/tui/render.py`
- `deep_coder/tui/screens/session_switcher.py`

Main test coverage added or expanded for this branch:

- `tests/projects/test_registry.py`
- `tests/context/test_filesystem_store.py`
- `tests/test_main.py`
- `tests/models/test_deepseek_model.py`
- `tests/tools/test_registry.py`
- `tests/harness/test_deepcoder_harness.py`
- `tests/test_cli.py`
- `tests/tui/test_app_layout.py`
- `tests/tui/test_render.py`
- `tests/tui/test_session_switcher.py`
- `tests/tui/test_live_events.py`

## What Was Intentionally Left Thin

The first TUI slice is working, but several areas remain intentionally minimal:

- no packaged install flow or console-script entrypoint beyond the checked-in `deepcode` launcher
- no advanced timeline virtualization, folding, or output pagination
- no persistent global session browser across all projects
- no richer status model beyond `idle`, `running`, and `tool:<name>`
- no prompt/config override system beyond existing runtime defaults
- no more advanced worker/error-retry behavior in the TUI loop

## Verification Snapshot

Latest merged verification after landing on `master`:

- command: `/home/wys/deep-code/.venv/bin/pytest -q`
- result: `29 passed in 1.28s`

This report describes the TUI/runtime state after feature branch `feat/harness-tui` was merged into `master`.
