# Session Task System History

Date: 2026-03-26
Branch: `feat/session-task-system-docs`
Merged into: `master` via `2dd8849`

## Summary

This branch adds a session-scoped task system to Deep Coder so the model can create, inspect, and update structured tasks during a session, while the existing TUI shows the live task graph inline in the same timeline as messages and tool output.

The implementation keeps planning policy out of the harness and UI layers:

- task state is persisted on the active session and stored under the existing context state
- task-graph mutations are centralized in a dedicated `TaskManager`
- builtin task tools expose the task system to the model through the normal tool registry
- tool execution can now receive the active session and emit extra structured timeline events
- the TUI renders task snapshots directly from those timeline events instead of owning separate task state

The resulting behavior is model-driven but session-bounded. Tasks live only inside the active session context, survive replay through persisted events and state, and remain aligned between live harness updates and reopened sessions.

## Implementation Timeline

### 1. Add session-backed task state, task tools, and timeline rendering

Commit: `2dd8849` `Add session task system`

Implemented:

- added `next_task_id` and `tasks` to `Session`
- persisted task state in the filesystem session store under `strategy_state["task_system"]`
- introduced `TaskManager` to create tasks, manage dependencies, and clear blockers when prerequisite tasks complete
- added builtin `task_create`, `task_update`, `task_list`, and `task_get` tools
- extended tool execution so tools can receive the active session and return structured `timeline_events`
- taught the harness to pass the active session into tool execution and relay tool-supplied `task_snapshot` events
- rendered `task_snapshot` events inline in the timeline with status markers and completion counts
- added regression coverage for session persistence, task-manager dependency updates, task tools, harness event relay, and TUI rendering/live updates
- preserved the implementation plan in `docs/plans/2026-03-26-session-task-system.md`

Edited files:

- `deep_coder/context/session.py`
- `deep_coder/context/stores/filesystem/store.py`
- `deep_coder/harness/deepcoder/harness.py`
- `deep_coder/tasks/__init__.py`
- `deep_coder/tasks/manager.py`
- `deep_coder/tools/base.py`
- `deep_coder/tools/bash/tool.py`
- `deep_coder/tools/edit_file/tool.py`
- `deep_coder/tools/read_file/tool.py`
- `deep_coder/tools/registry.py`
- `deep_coder/tools/result.py`
- `deep_coder/tools/tasks/__init__.py`
- `deep_coder/tools/tasks/tool.py`
- `deep_coder/tools/write_file/tool.py`
- `deep_coder/tui/app.py`
- `deep_coder/tui/render.py`
- `tests/context/test_filesystem_store.py`
- `tests/harness/test_deepcoder_harness.py`
- `tests/tasks/test_manager.py`
- `tests/tools/test_registry.py`
- `tests/tools/test_task_tools.py`
- `tests/tui/test_live_events.py`
- `tests/tui/test_render.py`
- `docs/plans/2026-03-26-session-task-system.md`

## Current User-Facing Shape

Main runtime behavior added by this branch:

- the model can create and update session tasks through builtin task tools
- task dependencies are tracked as `blocked_by` and `blocks` edges
- completing a task automatically unblocks downstream tasks
- task snapshots are emitted as structured timeline events during live turns
- reopened sessions replay the same task snapshots inline in the timeline

Main modules changed by this branch:

- `deep_coder/tasks/manager.py`
- `deep_coder/tools/tasks/tool.py`
- `deep_coder/harness/deepcoder/harness.py`
- `deep_coder/tui/render.py`
- `deep_coder/tui/app.py`

Main test coverage added or expanded by this branch:

- `tests/tasks/test_manager.py`
- `tests/tools/test_task_tools.py`
- `tests/harness/test_deepcoder_harness.py`
- `tests/context/test_filesystem_store.py`
- `tests/tui/test_render.py`
- `tests/tui/test_live_events.py`

## Verification Snapshot

Latest verification performed while landing the feature:

- command: `/home/wys/deep-code/.venv/bin/pytest -q tests/tasks/test_manager.py tests/context/test_filesystem_store.py tests/tools/test_registry.py tests/tools/test_task_tools.py tests/harness/test_deepcoder_harness.py tests/tui/test_render.py tests/tui/test_live_events.py`
- result: `28 passed in 1.47s`
- command: `/home/wys/deep-code/.venv/bin/pytest -q`
- result: `77 passed in 6.46s`

