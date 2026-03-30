# ask_user Tool Design

**Date:** 2026-03-29
**Status:** Approved

## Overview

Add an `ask_user` tool that lets the model pause a turn and present the user with one or more questions, each with a list of selectable options plus a free-form "Other" fallback. The turn blocks until the user responds; the answers are returned to the model as the tool result.

## Architecture

The harness runs in a **subprocess** (`turn_runner.py`). Events flow one-way from subprocess stdout to the TUI. The answer flows back via the subprocess's **stdin pipe**, which is kept open for the lifetime of the turn.

```
Model calls ask_user
  → tool emits question_asked timeline event (via stdout JSON line)
  → tool blocks on sys.stdin.readline()
  ← TUI renders QuestionWidget inline in timeline
  ← user selects options / types free-form answers
  ← TUI writes { "answers": {...} } JSON line to subprocess stdin
  → tool unblocks, reads answers, returns output_text to model
```

## Components

### 1. `ask_user` Tool — `deep_coder/tools/ask_user/tool.py`

- Implements `ToolBase`
- Schema parameter: `questions` — array of question objects
  - Each question: `{ "question": str, "options": [{ "label": str, "description": str }] }`
- On `exec`:
  1. Emit a `question_asked` timeline event via `timeline_events` on a preliminary result (not possible mid-exec — see Harness note below)
  2. Write the `question_asked` event directly to `sys.stdout` as a JSON line, then flush
  3. Block on `sys.stdin.readline()` waiting for `{ "answers": { "<question_text>": "<chosen_label_or_custom>" } }`
  4. Return `ToolExecutionResult` with `output_text` = JSON-encoded answers dict
- Each question's options list is always augmented with one implicit extra entry: `{ "label": "Other", "description": "Type your own answer" }`
- `display_command`: `ask_user`

**Why write directly to stdout:** The tool runs inside `turn_runner.py` which uses `JsonLineEventSink` writing to `sys.stdout`. The tool must emit the `question_asked` event *before* blocking, but `ToolExecutionResult.timeline_events` are published *after* `exec` returns. So the tool writes the event directly to stdout and flushes, bypassing the normal event pipeline for this one event.

### 2. `start_turn_subprocess` — `deep_coder/harness/turn_subprocess.py`

- Remove the `process.stdin.close()` call after writing the initial request
- Add `write_answer(answer_json: str)` method to `TurnSubprocess` that writes a JSON line to `process.stdin` and flushes
- `close()` closes stdin if not already closed

### 3. TUI — `deep_coder/tui/app.py`

- On `question_asked` event:
  - Set `_turn_state = "waiting_for_user"`
  - Render a `QuestionWidget` inline in the timeline (appended as a timeline block)
  - Lock the Composer (ignore submit while `_turn_state == "waiting_for_user"`)
- On `QuestionWidget` submission:
  - Collect answers dict `{ question_text: chosen_label_or_custom }`
  - Call `self._active_turn.write_answer(json.dumps({"answers": answers}))`
  - Remove / freeze the `QuestionWidget` block (replace with a static summary)
  - Set `_turn_state = "running"`, unlock Composer

### 4. `QuestionWidget` — `deep_coder/tui/widgets/question_widget.py`

A Textual `Widget` rendered inline in the timeline scroll area.

- Renders each question as a labeled `OptionList`
- Selecting "Other" on any question reveals a `TextArea` below that question's list for free-form input
- A "Submit" button (or `Enter` on the last question) submits all answers at once
- Emits a `QuestionWidget.Answered` message with `answers: dict[str, str]`
- After submission, replaces itself with a static read-only summary of the answers

### 5. Tool Registry — `deep_coder/tools/registry.py`

- Import and register `AskUserTool` in `ToolRegistry.from_builtin()`

### 6. Render — `deep_coder/tui/render.py`

- Add `render_question_asked_block(event)` for the static summary shown after answers are submitted (and for session replay)
- The live interactive widget is not rendered via `render.py` — it's a live Textual widget managed by `DeepCodeApp`

## Data Flow Detail

### question_asked event shape
```json
{
  "type": "question_asked",
  "session_id": "...",
  "turn_id": "...",
  "questions": [
    {
      "question": "Which approach should I use?",
      "options": [
        { "label": "Option A", "description": "Fast but less accurate" },
        { "label": "Option B", "description": "Slower but more accurate" }
      ]
    }
  ]
}
```

### answer payload (TUI → subprocess stdin)
```json
{ "answers": { "Which approach should I use?": "Option A" } }
```

### tool output_text (returned to model)
```json
{ "Which approach should I use?": "Option A" }
```

## Error Handling

- If stdin closes unexpectedly (user interrupts), the tool raises an exception; the harness catches it and emits `turn_failed` as normal
- If the answer JSON is malformed, the tool returns an error result without blocking again
- The Composer lock is always released when `_turn_state` leaves `"waiting_for_user"` (including on `turn_failed` / `turn_interrupted`)

## Session Replay

`question_asked` events are persisted to `events.jsonl` like all other events. On replay, `_append_event_block` renders a static summary block (via `render_question_asked_block`) showing the question and the answer that was given. The live `QuestionWidget` is never shown during replay.

## Testing

- Unit test `AskUserTool.exec()` by mocking `sys.stdin` / `sys.stdout`
- Unit test `TurnSubprocess.write_answer()` with a mock process
- Unit test `QuestionWidget` answer collection and "Other" reveal behavior
- Integration test: full turn with `ask_user` call using an in-process harness with a fake stdin/stdout pipe
