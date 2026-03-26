# Conversation Interruption Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add immediate user interruption for the active TUI turn so the current request stops during model waits or tool execution, while already completed edits, task updates, and persisted timeline history remain unchanged.

**Architecture:** Each submitted turn runs in a dedicated subprocess started by the TUI in its own process group. The harness flushes session state incrementally, the session store writes atomically, and the parent TUI app owns interrupting the subprocess and appending a persisted `turn_interrupted` event after the process stops.

**Tech Stack:** Python 3, Textual, subprocess/process-group control, JSON session storage, pytest

---

### Task 1: Make Session Persistence Durable Mid-Turn

**Files:**
- Modify: `deep_coder/harness/deepcoder/harness.py`
- Modify: `deep_coder/context/stores/filesystem/store.py`
- Test: `tests/harness/test_deepcoder_harness.py`
- Test: `tests/context/test_filesystem_store.py`

**Step 1: Write the failing harness durability test**

Add a test to `tests/harness/test_deepcoder_harness.py` that uses a fake model returning a tool call followed by a fake tools implementation that blocks the second phase long enough to inspect the saved session after the first flush point. Assert that the reopened session already contains the user message, assistant tool-call message, tool message, and timeline events before the turn fully finishes.

**Step 2: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/harness/test_deepcoder_harness.py::test_harness_flushes_partial_progress_before_turn_completion`

Expected: FAIL because the harness only saves at the end of the tool round or final response.

**Step 3: Write the failing atomic store test**

Add a test to `tests/context/test_filesystem_store.py` that monkeypatches the low-level write path so one target file write raises after the temp file is written. Assert that the previous session files are still readable and unchanged.

**Step 4: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/context/test_filesystem_store.py::test_filesystem_store_save_is_atomic_when_write_fails`

Expected: FAIL because `save(...)` writes directly into the target files.

**Step 5: Write minimal implementation**

- In `deep_coder/harness/deepcoder/harness.py`, flush after each persisted message/event boundary instead of only at the end of the turn.
- In `deep_coder/context/stores/filesystem/store.py`, add a small helper that writes to a sibling temp file and then replaces the real file with `os.replace(...)`.

**Step 6: Run targeted tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/harness/test_deepcoder_harness.py tests/context/test_filesystem_store.py`

Expected: PASS for the new tests and existing related tests.

**Step 7: Commit**

```bash
git add deep_coder/harness/deepcoder/harness.py deep_coder/context/stores/filesystem/store.py tests/harness/test_deepcoder_harness.py tests/context/test_filesystem_store.py
git commit -m "feat: persist partial turn progress safely"
```

### Task 2: Add a Turn Runner Subprocess That Streams Events

**Files:**
- Create: `deep_coder/harness/turn_runner.py`
- Create: `deep_coder/harness/turn_subprocess.py`
- Modify: `deep_coder/harness/__init__.py`
- Modify: `deep_coder/main.py`
- Test: `tests/harness/test_turn_subprocess.py`

**Step 1: Write the failing turn runner streaming test**

Create `tests/harness/test_turn_subprocess.py` with a test that launches a fake turn subprocess against a temporary session root, reads streamed events from the parent side, and asserts the event order includes `turn_started`, `message_committed`, and `turn_finished`.

**Step 2: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/harness/test_turn_subprocess.py::test_turn_subprocess_streams_events_to_parent`

Expected: FAIL because no subprocess runner exists.

**Step 3: Write the failing interrupt test**

In the same file, add a test that launches a subprocess whose fake model blocks. Interrupt it from the parent controller, wait for exit, and assert that the process terminates without producing a final assistant message.

**Step 4: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/harness/test_turn_subprocess.py::test_turn_subprocess_can_be_interrupted_during_model_wait`

Expected: FAIL because there is no parent-controlled turn process.

**Step 5: Write minimal implementation**

- Add a small subprocess protocol module that starts a Python child process in its own process group.
- Add a turn runner entrypoint that rebuilds the runtime for the project/session, runs the harness, and writes each emitted event as a JSON line back to the parent.
- Keep the protocol narrow: start, iterate events, wait, interrupt.

**Step 6: Run targeted tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/harness/test_turn_subprocess.py`

Expected: PASS.

**Step 7: Commit**

```bash
git add deep_coder/harness/turn_runner.py deep_coder/harness/turn_subprocess.py deep_coder/harness/__init__.py deep_coder/main.py tests/harness/test_turn_subprocess.py
git commit -m "feat: add interruptible turn subprocess runner"
```

### Task 3: Wire Turn Control Into the TUI

**Files:**
- Modify: `deep_coder/tui/app.py`
- Modify: `deep_coder/tui/styles.tcss`
- Test: `tests/tui/test_live_events.py`
- Test: `tests/tui/test_app_layout.py`
- Test: `tests/tui/conftest.py`

**Step 1: Write the failing TUI interrupt-state test**

Add a test to `tests/tui/test_app_layout.py` that starts a fake active turn, triggers the interrupt action, and asserts the status strip shows `interrupting` before settling back to `idle`.

**Step 2: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_app_layout.py::test_interrupt_action_transitions_status_from_running_to_idle`

Expected: FAIL because the app has no interrupt action or turn controller state.

**Step 3: Write the failing live timeline test**

Add a test to `tests/tui/test_live_events.py` that simulates an interrupted turn and asserts the timeline shows completed earlier blocks plus a rendered interruption marker, with no final assistant message appended.

**Step 4: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_live_events.py::test_interrupted_turn_renders_marker_without_final_assistant_message`

Expected: FAIL because `turn_interrupted` is not recognized.

**Step 5: Write minimal implementation**

- Replace the direct harness call path in `deep_coder/tui/app.py` with the turn subprocess controller.
- Track the active turn handle and add an interrupt action and binding while busy.
- Update status handling to support `interrupting`.
- Render the new interruption event in the timeline.
- Extend fake TUI fixtures to simulate the new control flow.

**Step 6: Run targeted tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_app_layout.py tests/tui/test_live_events.py`

Expected: PASS.

**Step 7: Commit**

```bash
git add deep_coder/tui/app.py deep_coder/tui/styles.tcss tests/tui/test_app_layout.py tests/tui/test_live_events.py tests/tui/conftest.py
git commit -m "feat: add tui turn interruption controls"
```

### Task 4: Persist and Replay Explicit Interruption Events

**Files:**
- Modify: `deep_coder/harness/events.py`
- Modify: `deep_coder/tui/render.py`
- Modify: `tests/tui/test_render.py`
- Modify: `tests/harness/test_deepcoder_harness.py`

**Step 1: Write the failing render test**

Add a test to `tests/tui/test_render.py` that renders a `turn_interrupted` event and asserts the output text clearly shows that the turn was interrupted by the user.

**Step 2: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_render.py::test_render_turn_interrupted_block`

Expected: FAIL because the renderer does not handle the event.

**Step 3: Write the failing persistence test**

Add a test to `tests/harness/test_deepcoder_harness.py` or a nearby harness/controller test that appends `turn_interrupted`, saves the session, reloads it, and asserts replay contains the event in order after the last completed step.

**Step 4: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/harness/test_deepcoder_harness.py::test_interruption_event_is_persisted_for_replay`

Expected: FAIL because no such event path exists.

**Step 5: Write minimal implementation**

- Add a shared helper or constant for interruption event naming if needed.
- Extend `deep_coder/tui/render.py` and `deep_coder/tui/app.py` to append and display the interruption marker.
- Ensure the parent controller persists the marker after a user-triggered stop.

**Step 6: Run targeted tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_render.py tests/harness/test_deepcoder_harness.py`

Expected: PASS.

**Step 7: Commit**

```bash
git add deep_coder/harness/events.py deep_coder/tui/render.py tests/tui/test_render.py tests/harness/test_deepcoder_harness.py
git commit -m "feat: persist interrupted turn markers"
```

### Task 5: Verify Real Tool Interruption and Full Regression Coverage

**Files:**
- Modify: `tests/tools/test_file_tools.py`
- Modify: `tests/harness/test_turn_subprocess.py`
- Modify: `docs/plans/2026-03-26-conversation-interruption-design.md`
- Modify: `docs/plans/2026-03-26-conversation-interruption.md`

**Step 1: Write the failing long-running bash interruption test**

Add a subprocess-level test that starts a turn executing a deliberately slow shell command, interrupts it from the parent, and asserts the child process exits before the command completes and does not emit a completed tool output event after the stop.

**Step 2: Run test to verify it fails**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/harness/test_turn_subprocess.py::test_turn_subprocess_interrupt_stops_long_running_bash_tool`

Expected: FAIL until the controller kills the process group correctly.

**Step 3: Write minimal implementation**

- Tighten process-group termination behavior if the previous tasks do not already kill shell descendants.
- Update docs if the exact controller behavior differs slightly from the original draft.

**Step 4: Run targeted tests to verify they pass**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/harness/test_turn_subprocess.py tests/tools/test_file_tools.py`

Expected: PASS.

**Step 5: Run the full suite**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q`

Expected: PASS with all tests green.

**Step 6: Commit**

```bash
git add tests/harness/test_turn_subprocess.py tests/tools/test_file_tools.py docs/plans/2026-03-26-conversation-interruption-design.md docs/plans/2026-03-26-conversation-interruption.md
git commit -m "feat: finish conversation interruption flow"
```
