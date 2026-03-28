# Think Tool Design

**Date:** 2026-03-28

## Goal

Add an agent-controlled `think` capability to Deep Code so the main `deepseek-chat` agent can make a one-shot call to `deepseek-reasoner`, capture the returned chain-of-thought locally, show it in the timeline, and reuse it through the layered context system without switching the entire session to the reasoning model.

## Product Scope

Version 1 should:

- keep the main session model as `deepseek-chat`
- add a builtin `think` tool that makes exactly one non-streaming call to `deepseek-reasoner`
- capture both `reasoning_content` and final `content` from the reasoning-model response
- persist the full reasoning trace locally in the project-scoped session store
- render the reasoning trace in the TUI timeline
- make recent think traces available to later `deepseek-chat` requests through the layered context strategy
- compact older think traces through the existing journal/evidence/summary flow
- surface structured DeepSeek/API errors in the timeline for both top-level model calls and `think` calls

Version 1 should not:

- switch the whole turn or session to `deepseek-reasoner`
- add a nested multi-step reasoner loop
- stream reasoning tokens
- expose raw `reasoning_content` as a first-class OpenAI-style message field in the outer chat transcript
- add automatic retry or backoff logic yet

## Core Decisions

### Main Session Model Stays On Chat

- The top-level harness loop continues to use `runtime["config"].model_name`, which will usually be `deepseek-chat`.
- Thinking is an explicit tool invocation chosen by the agent.
- The reasoner is used only for one-shot subrequests triggered by `think`.

This preserves the current product shape and avoids turning every turn into a reasoning-model turn.

### Think Is A One-Shot Tool

- Add a builtin tool named `think`.
- The tool sends one request to `deepseek-reasoner`.
- The request is non-streaming.
- The tool does not run its own nested local tool loop.
- The outer harness remains responsible for the real local tool loop.

This is intentionally narrower than a sub-harness design. The goal is to capture and reuse CoT, not to build a second orchestrator inside the tool system.

### CoT Is Stored Locally, Not As Raw Outer Chat Messages

- The full `reasoning_content` must be persisted locally.
- The outer session should not store raw `reasoning_content` as a dedicated field on assistant chat messages.
- Instead, CoT should be stored in the layered context system alongside tool-result artifacts and evidence.

This keeps the outer transcript structurally simple while still allowing the context layer to reuse the stored reasoning when building future working sets.

### Recent CoT Is Re-Injected Through Context Strategy

- Recent think traces should be surfaced back to `deepseek-chat` by the layered context strategy.
- The strategy should expand recent `think` artifacts into plain tool-result content when rebuilding the working set.
- Older think traces should eventually collapse into summaries like other historical context.

This matches the current three-layer context design better than permanently stuffing raw CoT into `session.messages`.

### Reasoning Errors Must Be First-Class Timeline Events

- DeepSeek/API failures should produce structured error events.
- The TUI should render those events directly.
- The user should be able to tell whether a failure came from the main model turn or from a one-shot `think` request.

## DeepSeek Behavior And Constraints

The design depends on the documented behavior of `deepseek-reasoner`:

- a response can include both `reasoning_content` and final `content`
- in non-streaming mode both are available after the request completes
- reasoning output is part of the generated response, so discarding it does not avoid token cost
- the documented tool-loop requirement to feed `reasoning_content` back applies to multi-step reasoning flows, which v1 intentionally avoids

Because Deep Code is using the one-shot path:

- the tool captures `reasoning_content`
- the tool persists it locally
- the outer chat model receives a normalized tool result derived from the think artifact

## Tool Contract

### Tool Schema

Recommended v1 schema:

```json
{
  "type": "function",
  "function": {
    "name": "think",
    "description": "Use deepseek-reasoner once for deep reasoning, store the reasoning trace locally, and return a reasoning result to the main chat model.",
    "parameters": {
      "type": "object",
      "properties": {
        "prompt": {
          "type": "string",
          "description": "The exact reasoning prompt to send to deepseek-reasoner."
        }
      },
      "required": ["prompt"]
    }
  }
}
```

### Tool Execution Flow

When the main model calls `think`:

1. execute one `deepseek-reasoner` completion request
2. capture:
   - final `content`
   - `reasoning_content`
   - usage counters, including reasoning-token metadata if present
3. persist the result into local artifact/evidence storage
4. emit a reasoning timeline event
5. return a normal tool result back into the outer harness loop

### Tool Result Shape

The outer harness should continue treating `think` as a normal tool. The returned tool result should include:

- `model_output`: the content that should be written into the outer tool message
- `output_text`: display-friendly content for the timeline
- `reasoning_content`: full CoT text for local persistence
- `is_error`: error flag when the reasoner request fails

The tool-result text sent back to the outer model should be plain text, for example:

```text
[think result]
final_answer:
...

reasoning_trace:
...
```

This avoids introducing unsupported message semantics into the outer chat model while still making the reasoning available to later turns.

## Model Adapter Changes

### Per-Request Model Override

`DeepSeekModel.complete(request)` should accept an optional request-level model override:

- default: `self.config.model_name`
- override: `request.get("model_name")`

This allows the outer runtime to stay on `deepseek-chat` while the `think` tool uses `deepseek-reasoner`.

### Response Normalization

The normalized response should grow to include:

```python
{
    "content": str | None,
    "reasoning_content": str | None,
    "tool_calls": list[dict],
    "usage": dict | None,
    "finish_reason": str | None,
    "raw_response": object,
}
```

Additional usage counters should be preserved when available:

- `reasoning_tokens`

Normal `deepseek-chat` behavior should remain unchanged when no reasoning field is present.

## Context And Persistence Design

### Session Messages

`session.messages` should remain valid outer-loop chat/tool messages.

The `think` result should still append a normal tool-role message to `session.messages`, but the full raw CoT should not live only there. It must also be stored in the richer context layers so:

- replay stays aligned with local artifact storage
- summaries can reason over old think traces
- future strategy changes do not depend on parsing one large tool string

### Artifact Storage

The think result should be persisted in `session.artifacts` as a first-class object. Recommended shape:

```json
{
  "artifact_type": "think_result",
  "tool_call_id": "tool-123",
  "tool_name": "think",
  "model_name": "deepseek-reasoner",
  "prompt": "...",
  "final_content": "...",
  "reasoning_content": "full cot text..."
}
```

This is the authoritative local storage for full CoT text.

### Evidence Storage

`session.evidence` should continue to carry compact, queryable content tied to journal entries. For think results, evidence should include:

- a compact tool-result summary
- final answer text
- optionally a short reasoning preview or a marker that full reasoning exists in the artifact

This keeps evidence readable for summarization without requiring every consumer to parse the full tool string.

### Journal Storage

The normal `tool_result` journal entry remains the chronological anchor for think results.

For a `think` entry:

- `kind` stays `tool_result`
- `role` stays `tool`
- `tool_name` is `think`
- `artifact_ids` points to the persisted think artifact

This allows the layered strategy to reconstruct think results cleanly from journal plus evidence plus artifact storage.

### Strategy Reconstruction

`LayeredHistoryContextStrategy._message_for_entry()` should special-case recent `think` tool results:

- load the linked artifact
- rebuild a plain-text tool message from:
  - final answer
  - reasoning trace
- inject that rebuilt text into the recent working set

Recommended reconstruction format:

```text
[think result]
final_answer:
...

reasoning_trace:
...
```

This lets `deepseek-chat` see the reasoning trace on later turns without teaching the outer model adapter about a custom `reasoning_content` field.

### Compaction

Think results should enter the existing compaction path.

When older turns are summarized:

- the summarizer should see the reconstructed think content or equivalent artifact-backed expansion
- the resulting summaries should carry any durable reasoning outcome
- raw old CoT should no longer need to remain verbatim in the prompt working set

### Prompt Budget Control

Reasoning traces can be large, so the strategy should enforce a limit when re-injecting CoT into rebuilt recent messages.

Recommended v1 rule:

- store full CoT in the artifact and event log
- inject only up to a configurable maximum into rebuilt working-set messages

This prevents a single `think` result from overwhelming the prompt budget.

## Timeline And Replay Design

### New Event Type

Add a new persisted timeline event:

```json
{
  "type": "reasoning_recorded",
  "session_id": "...",
  "turn_id": "...",
  "tool_call_id": "...",
  "name": "think",
  "model_name": "deepseek-reasoner",
  "final_content": "...",
  "reasoning_content": "full cot text..."
}
```

This event should be emitted after the think result is stored.

### Rendering

The TUI should render `reasoning_recorded` as a dedicated reasoning panel rather than as an ordinary assistant or tool-output block.

The panel should show:

- model name
- final answer
- reasoning trace

This keeps replay and live rendering aligned with the persisted event log.

### Existing Event Flow

The normal outer harness event flow remains intact:

- `tool_called`
- `tool_output`
- `reasoning_recorded`

That makes think behavior readable in the timeline without changing the basic turn lifecycle.

## Error Handling Design

### Shared Structured Error Event

Add a model/API error event for both top-level model calls and one-shot think requests:

```json
{
  "type": "model_error",
  "session_id": "...",
  "turn_id": "...",
  "scope": "main_model" | "think",
  "model_name": "deepseek-chat" | "deepseek-reasoner",
  "status_code": 429,
  "error_code": "rate_limit_reached",
  "message": "human-readable error",
  "retryable": true
}
```

### Classification

Based on DeepSeek's documented error codes:

- `400`, `401`, `402`, `422` -> non-retryable
- `429`, `500`, `503` -> retryable
- unknown client/library exceptions -> unclassified, no automatic retry in v1

### Main Turn Failure

If the top-level model call fails:

- emit `model_error` with `scope="main_model"`
- end the turn cleanly
- prefer a dedicated `turn_failed` event or a `turn_finished` event with `finish_reason="error"`

### Think Failure

If the one-shot `think` request fails:

- emit `model_error` with `scope="think"`
- return a normal tool error result
- do not persist partial reasoning unless a valid response body was actually received

### TUI Rendering

Render model/API errors as a dedicated error panel showing:

- model name
- scope
- status code
- error code
- message
- retryable vs non-retryable

Errors such as `401` and `402` should be especially explicit because the user can act on them immediately.

## Testing Plan

### Model Tests

- normalize `reasoning_content` from DeepSeek reasoning responses
- preserve current chat-model behavior when reasoning data is absent
- support request-level `model_name="deepseek-reasoner"`
- preserve `reasoning_tokens` when present in usage

### Tool Tests

- `think` makes exactly one reasoner request
- `think` stores final content and reasoning content separately
- `think` returns a normal tool result to the outer harness
- think failures become structured tool errors

### Context Tests

- think artifacts persist full CoT in `artifacts.json`
- journal/evidence entries link correctly to think artifacts
- layered-history reconstruction injects think traces into recent working-set messages
- summarization input includes think results
- prompt-budget truncation is enforced for rebuilt reasoning traces

### Harness Tests

- think calls produce `tool_called`, `tool_output`, and `reasoning_recorded`
- top-level model failures emit `model_error`
- think failures emit `model_error` with `scope="think"`
- persisted events replay correctly

### TUI Tests

- `reasoning_recorded` renders as a reasoning block
- `model_error` renders as an error block
- live event flow and replay render the same sequence

## Implementation Notes

Recommended modules to touch:

- `deep_coder/models/deepseek/model.py`
- `deep_coder/tools/registry.py`
- `deep_coder/tools/result.py`
- `deep_coder/tools/think/`
- `deep_coder/context/manager.py`
- `deep_coder/context/strategies/layered_history/strategy.py`
- `deep_coder/context/summarizers/model.py`
- `deep_coder/harness/deepcoder/harness.py`
- `deep_coder/tui/render.py`
- `deep_coder/tui/app.py`
- relevant tests under `tests/models/`, `tests/tools/`, `tests/context/`, `tests/harness/`, and `tests/tui/`

## Sources

- DeepSeek Thinking Mode: https://api-docs.deepseek.com/guides/thinking_mode
- DeepSeek Reasoning Model: https://api-docs.deepseek.com/guides/reasoning_model
- DeepSeek Chat Completion API: https://api-docs.deepseek.com/api/create-chat-completion
- DeepSeek Error Codes: https://api-docs.deepseek.com/quick_start/error_codes
