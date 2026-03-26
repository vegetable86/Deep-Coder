# Conversation Interruption Design

## Goal

Allow the TUI user to immediately interrupt the currently running turn, including time spent waiting on the model and time spent inside tool execution, without rolling back any work that has already completed.

## Required Behavior

- Interrupting a turn stops only the active request.
- Any tool effects that completed before the interrupt remain in the workspace.
- Any session messages and timeline events that were already persisted remain in the session.
- The interrupted turn is marked explicitly in the timeline and in replay.
- The runtime must not fabricate a final assistant answer after an interrupt.
- Live rendering and replay must stay aligned.

This is intentionally not transactional rollback. It is in-place cancellation with durable partial progress.

## Current Constraints

The current runtime cannot satisfy the feature:

- `deep_coder/tui/app.py` runs one `@work(thread=True)` job per turn and calls the harness directly.
- `deep_coder/harness/deepcoder/harness.py` is synchronous and only flushes the session at the end of a tool round or at the final assistant answer.
- `deep_coder/models/deepseek/model.py` blocks in one SDK call.
- `deep_coder/tools/bash/tool.py` blocks in one `subprocess.run(...)` call.

An in-thread cancel flag would only stop work between blocking calls. It would not interrupt a model request or a long-running shell command immediately.

## Chosen Approach

Run each turn inside a dedicated subprocess and treat the parent TUI process as the controller.

### Why This Approach

- The parent can terminate the entire turn process group immediately.
- The same mechanism stops a blocking model request and any child processes started by tools.
- Already completed work can stay durable by flushing incrementally during the turn.
- Cancellation policy stays in runtime orchestration instead of being spread across every tool implementation.

## Architecture

### 1. Turn Runner Subprocess

Each composer submission starts a turn runner subprocess instead of calling the harness directly inside the Textual worker thread.

The subprocess is responsible for:

- opening or creating the target session
- building the normal runtime
- running the existing harness
- streaming timeline events back to the parent process

The parent process is responsible for:

- starting the subprocess in its own process group
- reading streamed events
- updating TUI state
- interrupting the process group on user request
- appending a final `turn_interrupted` event after the subprocess is stopped

### 2. Incremental Durability

The harness must flush the session after each durable step instead of only at the end of the turn.

Flush points:

- after recording the user message
- after recording the assistant tool-call message
- after recording each tool output message
- after appending each persisted timeline event
- after recording the final assistant message

This preserves completed progress if the subprocess is terminated during a later step.

### 3. Atomic Session Store Writes

`FileSystemSessionStore.save(...)` currently rewrites the session files directly. If the turn process is killed during a write, the session can be left partially written.

The store should switch to atomic replace semantics:

- write content to sibling temporary files in the same directory
- `os.replace(...)` each file into place after the write succeeds

This keeps interrupted saves from corrupting session history.

### 4. Event Streaming Contract

The turn runner should stream timeline events to the TUI as newline-delimited JSON or an equivalent simple transport. The payloads should keep the existing event shape so the TUI render path does not need a second event schema.

New persisted event type:

- `turn_interrupted`

Payload:

- `session_id`
- `turn_id`
- optional `reason`, defaulting to `user_interrupt`

The event is written by the parent controller after it confirms that the turn subprocess has stopped.

### 5. TUI Turn Control

`DeepCodeApp` needs explicit turn control state:

- active turn id
- active subprocess handle
- worker state for reading subprocess events
- `running`, `interrupting`, and `idle` status values

Recommended interaction:

- keep submit behavior unchanged when idle
- while busy, bind `ctrl+c` to interrupt the active turn
- after interrupt, status changes to `interrupting` until the subprocess exits
- once the process is gone and `turn_interrupted` is recorded, return to `idle`

### 6. Tool Execution Semantics

No rollback is attempted.

If a tool already finished and its output was flushed:

- file changes stay
- task updates stay
- timeline entries stay

If the process is interrupted before a tool finishes:

- the tool does not produce a completed output event
- the harness does not continue to later tool calls or to the final assistant response

For `bash`, the parent must terminate the entire turn process group so shell children do not outlive the runner process.

## Data Flow

### Normal Completion

1. TUI creates turn id and launches the turn subprocess in a new process group.
2. The subprocess runs the harness and streams events.
3. The harness records messages/events and flushes incrementally.
4. The parent updates the live timeline from streamed events.
5. The subprocess exits normally.
6. The parent clears active turn state and returns the TUI to `idle`.

### User Interrupt

1. User triggers interrupt while a turn is active.
2. The TUI marks status as `interrupting`.
3. The parent sends termination to the turn process group.
4. The event reader exits once the subprocess pipe closes.
5. The parent reopens the active session, appends `turn_interrupted`, saves it, emits it locally, and clears active turn state.
6. The TUI returns to `idle`.

## Error Handling

- If the subprocess exits unexpectedly without a final assistant answer, the parent still records `turn_interrupted` when the exit was user initiated.
- If the parent cannot append the interruption marker, the TUI should still return to `idle` and surface the error in the status strip.
- If no turn is active, the interrupt action is a no-op.
- Session switching and slash commands should remain blocked while a turn is active or interrupting.

## Non-Goals

- rollback of partial filesystem changes
- rollback of external side effects from shell commands
- multiple concurrent turns
- provider-specific streaming cancellation

## Testing Strategy

### Harness / Store

- verify partial progress is saved before later work starts
- verify store writes remain readable if save is interrupted between files

### Turn Runner

- verify live events are streamed to the parent
- verify interrupt stops the subprocess during a long model wait
- verify interrupt stops the subprocess during a long bash tool call

### TUI

- verify busy state exposes the interrupt binding
- verify interrupt transitions `running -> interrupting -> idle`
- verify `turn_interrupted` appears in the live timeline and in replay
- verify no final assistant message is appended after interrupt
