# ask_user Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an `ask_user` tool that pauses a turn, renders interactive questions in the TUI, accepts a user response through the subprocess stdin pipe, and returns the answers to the model.

**Architecture:** Keep the harness subprocess model intact. The tool emits a live `question_asked` JSON line directly to stdout before blocking, persists the matching event into the active session for replay, then resumes after reading a JSON answer line from stdin. The TUI handles the live interactive widget locally and appends a static summary into the timeline after submission.

**Tech Stack:** Python, Textual, Rich, pytest

---

### Task 1: Plan And Baseline

**Files:**
- Create: `docs/plans/2026-03-29-ask-user-tool.md`
- Verify: `tests/`

**Step 1: Verify the baseline suite is clean**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`
Expected: `161 passed`

**Step 2: Confirm the implementation surfaces**

Inspect:
- `deep_coder/harness/turn_subprocess.py`
- `deep_coder/harness/turn_runner.py`
- `deep_coder/harness/deepcoder/harness.py`
- `deep_coder/tools/registry.py`
- `deep_coder/tui/app.py`
- `deep_coder/tui/render.py`

### Task 2: Add Failing Tests

**Files:**
- Create: `tests/tools/test_ask_user_tool.py`
- Create: `tests/tui/test_question_widget.py`
- Modify: `tests/tools/test_registry.py`
- Modify: `tests/harness/test_turn_subprocess.py`
- Modify: `tests/harness/test_deepcoder_harness.py`
- Modify: `tests/tui/test_render.py`
- Modify: `tests/tui/test_live_events.py`

**Step 1: Write the failing tool tests**

Cover:
- stdout `question_asked` emission
- implicit `Other` option
- answers returned as JSON text
- malformed answer handling

**Step 2: Write the failing subprocess test**

Cover:
- `TurnSubprocess.write_answer()` writes one JSON line and flushes stdin

**Step 3: Write the failing harness integration test**

Cover:
- live `question_asked` line appears before the answer is provided
- the session stores a replayable `question_asked` event with answers
- the model receives the tool result on the next completion call

**Step 4: Write the failing render and TUI tests**

Cover:
- static question summary rendering
- `QuestionWidget` "Other" reveal and answer collection
- `DeepCodeApp` waiting state, composer lock, answer write, and replay rendering

### Task 3: Implement The ask_user Tool And Registry

**Files:**
- Create: `deep_coder/tools/ask_user/__init__.py`
- Create: `deep_coder/tools/ask_user/tool.py`
- Modify: `deep_coder/tools/registry.py`

**Step 1: Add the tool schema and execution logic**

Implement:
- `questions` schema
- option augmentation with implicit `Other`
- direct stdout JSON line emission
- stdin answer parsing
- session event persistence for replay

**Step 2: Register the tool**

Add `AskUserTool` to `ToolRegistry.from_builtin()`

### Task 4: Keep The Subprocess Pipe Open

**Files:**
- Modify: `deep_coder/harness/turn_subprocess.py`
- Modify: `deep_coder/harness/turn_runner.py`
- Modify: `deep_coder/harness/deepcoder/harness.py`

**Step 1: Read only the initial request line in `turn_runner.py`**

Implement:
- `sys.stdin.readline()` instead of consuming the full stream

**Step 2: Add answer writes in `turn_subprocess.py`**

Implement:
- keep stdin open after the initial request
- add `write_answer()`
- close stdin during `close()`

**Step 3: Expose the active turn id to tools**

Implement:
- assign the current turn id onto the session object before tool execution

### Task 5: Add Interactive TUI Support

**Files:**
- Create: `deep_coder/tui/widgets/__init__.py`
- Create: `deep_coder/tui/widgets/question_widget.py`
- Modify: `deep_coder/tui/app.py`
- Modify: `deep_coder/tui/render.py`
- Modify: `deep_coder/tui/styles.tcss`

**Step 1: Add the question widget**

Implement:
- per-question option list
- `Other` free-form input reveal
- submit handling and static summary mode

**Step 2: Wire the app state**

Implement:
- `waiting_for_user` turn state
- composer disable/enable while waiting
- live question widget mount in the timeline scroll area
- answer write to the active subprocess
- local summary append after submission
- replay rendering for persisted `question_asked` events

### Task 6: Verify

**Files:**
- Verify: `tests/`

**Step 1: Run focused tests**

Run:
- `/home/wys/deep-code/.venv/bin/pytest -q tests/tools/test_ask_user_tool.py`
- `/home/wys/deep-code/.venv/bin/pytest -q tests/harness/test_turn_subprocess.py tests/harness/test_deepcoder_harness.py`
- `/home/wys/deep-code/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_question_widget.py tests/tui/test_live_events.py`

**Step 2: Run the full suite**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`
Expected: all tests pass
