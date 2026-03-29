# ask_user Tool History

Date: 2026-03-29
Branch: `feat/ask-user-tool`

## Summary

This branch adds an `ask_user` tool that lets the model pause mid-turn, present one or more structured questions in the TUI, wait for the user to answer, and then resume the same turn with those answers returned as tool output.

The feature spans the tool layer, turn subprocess plumbing, and the Textual app:

- the tool emits a live `question_asked` event before blocking
- the turn subprocess keeps stdin open so the TUI can send answers back to the runner
- the TUI shows an inline interactive question widget while locking the composer
- replay renders a static summary of the answered question block from persisted events

## Implementation Timeline

### 1. Add the `ask_user` tool and registry wiring

Implemented:

- added `AskUserTool` as a built-in tool
- defined a `questions` schema with labeled options
- appended an implicit `Other` option to each question
- emitted a live `question_asked` JSON line directly to stdout before waiting for input
- parsed the returned `{ "answers": ... }` JSON payload from stdin
- persisted replayable `question_asked` events with final answers into session storage

Edited files:

- `deep_coder/tools/ask_user/__init__.py`
- `deep_coder/tools/ask_user/tool.py`
- `deep_coder/tools/registry.py`

### 2. Keep the turn subprocess open for user answers

Implemented:

- kept the subprocess stdin pipe open after the initial request write
- added `TurnSubprocess.write_answer()` for TUI-to-runner answer delivery
- changed `turn_runner.py` to read only the initial request line instead of consuming all stdin
- exposed the current turn id on the active session so the tool can stamp live/persisted question events correctly

Edited files:

- `deep_coder/harness/turn_subprocess.py`
- `deep_coder/harness/turn_runner.py`
- `deep_coder/harness/deepcoder/harness.py`

### 3. Add interactive TUI question handling and replay rendering

Implemented:

- added `QuestionWidget` for inline question rendering, option selection, `Other` free-form entry, and answer submission
- added a dedicated question slot in the timeline scroll area for live interactive blocks
- locked the composer while the app is in `waiting_for_user`
- wrote selected answers back to the active turn and converted the live interaction into a static summary block
- added `render_question_asked_block()` so replay shows the recorded question plus chosen answer

Edited files:

- `deep_coder/tui/widgets/__init__.py`
- `deep_coder/tui/widgets/question_widget.py`
- `deep_coder/tui/app.py`
- `deep_coder/tui/render.py`
- `deep_coder/tui/styles.tcss`

### 4. Add regression coverage and implementation plan documentation

Implemented:

- added tool-level tests for stdout emission, answer parsing, and malformed payload handling
- added subprocess coverage for `write_answer()`
- added harness coverage for pause/resume behavior through `ask_user`
- added TUI coverage for static rendering, widget behavior, composer locking, answer submission, and replay rendering
- documented the implementation plan used for the branch

Edited files:

- `tests/tools/test_ask_user_tool.py`
- `tests/tools/test_registry.py`
- `tests/harness/test_turn_subprocess.py`
- `tests/harness/test_deepcoder_harness.py`
- `tests/tui/test_render.py`
- `tests/tui/test_question_widget.py`
- `tests/tui/test_live_events.py`
- `docs/plans/2026-03-29-ask-user-tool.md`

## Verification

- `/home/wys/deep-code/.venv/bin/pytest -q tests/tools/test_ask_user_tool.py tests/tools/test_registry.py tests/harness/test_turn_subprocess.py tests/harness/test_deepcoder_harness.py tests/tui/test_render.py tests/tui/test_question_widget.py tests/tui/test_live_events.py`
- `/home/wys/deep-code/.venv/bin/pytest -q`
