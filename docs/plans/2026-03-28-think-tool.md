# Think Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a one-shot `think` tool that calls `deepseek-reasoner`, stores full reasoning traces in layered local context, reuses recent reasoning in future `deepseek-chat` turns, renders reasoning and API errors in the timeline, and preserves replay.

**Architecture:** Keep the outer harness on `deepseek-chat` and treat `think` as a normal builtin tool. Extend the DeepSeek adapter to support request-level model overrides plus normalized `reasoning_content`, store the full CoT in artifacts/evidence tied to the tool result, and let the layered-history strategy rebuild recent think traces back into the working set. Emit dedicated timeline events for reasoning capture and model/API errors so live rendering and replay stay aligned.

**Tech Stack:** Python 3, Textual, OpenAI-compatible DeepSeek SDK, pytest, layered local session store under `~/.deepcode/projects/<project-key>/`.

---

### Task 1: Extend The DeepSeek Model Adapter For Reasoning Responses

**Files:**
- Modify: `deep_coder/models/deepseek/model.py`
- Test: `tests/models/test_deepseek_model.py`

**Step 1: Write the failing tests**

Add tests for:

```python
def test_deepseek_complete_uses_request_level_model_override(...):
    model.complete(
        {
            "model_name": "deepseek-reasoner",
            "messages": [{"role": "user", "content": "think"}],
        }
    )
    assert captured["model"] == "deepseek-reasoner"


def test_deepseek_complete_normalizes_reasoning_content_and_reasoning_tokens(...):
    response = model.complete({"messages": [{"role": "user", "content": "think"}]})
    assert response["reasoning_content"] == "step by step"
    assert response["usage"]["reasoning_tokens"] == 11
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/models/test_deepseek_model.py
```

Expected:

- FAIL because `DeepSeekModel.complete()` ignores request-level `model_name`
- FAIL because normalized responses do not expose `reasoning_content` or `usage.reasoning_tokens`

**Step 3: Write the minimal implementation**

Update `deep_coder/models/deepseek/model.py` so:

```python
def complete(self, request: dict) -> dict:
    response = self.client.chat.completions.create(
        model=request.get("model_name") or self.config.model_name,
        messages=_serialize_messages(request["messages"]),
        tools=request.get("tools"),
    )
    message = response.choices[0].message
    usage_raw = response.usage.model_dump() if response.usage else {}
    return {
        "content": message.content,
        "reasoning_content": getattr(message, "reasoning_content", None),
        "tool_calls": tool_calls,
        "usage": {
            "prompt_tokens": usage_raw.get("prompt_tokens", 0),
            "completion_tokens": usage_raw.get("completion_tokens", 0),
            "total_tokens": usage_raw.get("total_tokens", 0),
            "cache_hit_tokens": usage_raw.get("prompt_cache_hit_tokens", 0),
            "cache_miss_tokens": usage_raw.get("prompt_cache_miss_tokens", 0),
            "reasoning_tokens": usage_raw.get("reasoning_tokens", 0),
        },
        "finish_reason": response.choices[0].finish_reason,
        "raw_response": response,
    }
```

Keep existing chat-model tool-call behavior unchanged.

**Step 4: Run the tests to verify they pass**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/models/test_deepseek_model.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add tests/models/test_deepseek_model.py deep_coder/models/deepseek/model.py
git commit -m "feat: normalize deepseek reasoning responses"
```

### Task 2: Add The `think` Builtin Tool And Registry Wiring

**Files:**
- Create: `deep_coder/tools/think/__init__.py`
- Create: `deep_coder/tools/think/tool.py`
- Modify: `deep_coder/tools/registry.py`
- Modify: `deep_coder/tools/result.py`
- Test: `tests/tools/test_registry.py`

**Step 1: Write the failing tests**

Add tests for:

```python
def test_registry_returns_think_schema(...):
    names = [schema["function"]["name"] for schema in registry.schemas()]
    assert "think" in names


def test_registry_executes_think_and_returns_reasoning_result(...):
    result = registry.execute("think", {"prompt": "plan the fix"}, session=session)
    assert result.name == "think"
    assert result.reasoning_content == "step by step"
    assert "final_answer" in result.model_output


def test_registry_wraps_think_failures_as_tool_errors(...):
    result = registry.execute("think", {"prompt": "plan the fix"}, session=session)
    assert result.is_error is True
```

Stub the tool-level model dependency so the tests do not hit the network.

**Step 2: Run the tests to verify they fail**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/tools/test_registry.py
```

Expected:

- FAIL because no `think` tool exists in builtin registry
- FAIL because `ToolExecutionResult` has no `reasoning_content`

**Step 3: Write the minimal implementation**

Create `deep_coder/tools/think/tool.py` with a standard builtin-tool shape:

```python
class ThinkTool:
    def __init__(self, config, workdir, model=None):
        self.config = config
        self.workdir = Path(workdir)
        self.model = model or DeepSeekModel(config=config)

    def schema(self) -> dict:
        return {... "name": "think", ...}

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        response = self.model.complete(
            {
                "model_name": "deepseek-reasoner",
                "messages": [{"role": "user", "content": arguments["prompt"]}],
                "tools": [],
            }
        )
        return ToolExecutionResult(
            name="think",
            display_command="think",
            model_output=_format_think_result(response),
            output_text=response.get("content") or "",
            reasoning_content=response.get("reasoning_content") or "",
            metadata={
                "model_name": "deepseek-reasoner",
                "prompt": arguments["prompt"],
                "final_content": response.get("content") or "",
            },
        )
```

Extend `ToolExecutionResult` to support:

```python
reasoning_content: str | None = None
metadata: dict = field(default_factory=dict)
```

Register the tool in `ToolRegistry.from_builtin()`.

**Step 4: Run the tests to verify they pass**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/tools/test_registry.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add deep_coder/tools/think/__init__.py deep_coder/tools/think/tool.py deep_coder/tools/registry.py deep_coder/tools/result.py tests/tools/test_registry.py
git commit -m "feat: add think builtin tool"
```

### Task 3: Persist Think Results In Layered Context Artifacts And Evidence

**Files:**
- Modify: `deep_coder/context/manager.py`
- Modify: `deep_coder/context/records.py`
- Modify: `deep_coder/context/stores/filesystem/store.py`
- Test: `tests/context/test_layered_context_manager.py`
- Test: `tests/context/test_filesystem_store.py`

**Step 1: Write the failing tests**

Add tests for:

```python
def test_context_manager_persists_reasoning_content_inside_tool_artifact(...):
    manager.record_tool_result(..., output=ToolExecutionResult(..., reasoning_content="cot"))
    artifact = next(iter(session.artifacts.values()))
    assert artifact["reasoning_content"] == "cot"
    assert artifact["artifact_type"] == "think_result"


def test_filesystem_store_round_trips_reasoning_artifacts(...):
    store.save(session)
    reopened = store.open(locator={"id": session.session_id})
    artifact = next(iter(reopened.artifacts.values()))
    assert artifact["reasoning_content"] == "cot"
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/context/test_layered_context_manager.py tests/context/test_filesystem_store.py
```

Expected:

- FAIL because the context manager does not persist reasoning-specific fields

**Step 3: Write the minimal implementation**

Update `ContextManager.record_tool_result()` to persist extra think metadata:

```python
session.artifacts[artifact_id] = {
    "artifact_type": "think_result" if tool_name == "think" else "tool_result",
    "tool_call_id": tool_call_id,
    "tool_name": tool_name,
    "arguments": arguments or {},
    "model_output": model_output or "",
    "output_text": output_text or model_output or "",
    "reasoning_content": getattr(output, "reasoning_content", "") if output else reasoning_content or "",
    "metadata": getattr(output, "metadata", {}) if output else {},
    ...
}
```

Keep `messages.jsonl` format stable. No schema migration is needed beyond round-tripping the new artifact payload through `artifacts.json`.

**Step 4: Run the tests to verify they pass**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/context/test_layered_context_manager.py tests/context/test_filesystem_store.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add deep_coder/context/manager.py deep_coder/context/records.py deep_coder/context/stores/filesystem/store.py tests/context/test_layered_context_manager.py tests/context/test_filesystem_store.py
git commit -m "feat: persist think artifacts in layered context"
```

### Task 4: Rebuild Recent Think Traces Through Layered History And Summarization

**Files:**
- Modify: `deep_coder/context/strategies/layered_history/strategy.py`
- Modify: `deep_coder/context/summarizers/model.py`
- Modify: `deep_coder/config.py`
- Test: `tests/context/test_layered_history_strategy.py`

**Step 1: Write the failing tests**

Add tests for:

```python
def test_layered_history_rebuilds_recent_think_result_from_artifact(...):
    message = strategy._message_for_entry(entry, evidence, session)
    assert message["role"] == "tool"
    assert "reasoning_trace" in message["content"]
    assert "final_answer" in message["content"]


def test_layered_history_truncates_reinjected_reasoning_trace(...):
    strategy = LayeredHistoryContextStrategy(config=_config(context_reasoning_max_chars=20), ...)
    message = strategy._message_for_entry(entry, evidence, session)
    assert len(message["content"]) < len(full_reasoning_text)


def test_model_summarizer_includes_think_content_in_transcript(...):
    payload = fake_model.calls[0]["messages"][-1]["content"]
    assert "reasoning_trace" in payload
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/context/test_layered_history_strategy.py
```

Expected:

- FAIL because layered history does not special-case `think`
- FAIL because no reasoning-trace reinjection limit exists

**Step 3: Write the minimal implementation**

Add a new config field:

```python
DEFAULT_CONTEXT_SETTINGS["context_reasoning_max_chars"] = 4000
```

In `LayeredHistoryContextStrategy._message_for_entry()`:

```python
if role == "tool" and entry.get("tool_name") == "think":
    artifact = session.artifacts.get(artifact_id or "", {})
    reasoning = _truncate_reasoning(
        artifact.get("reasoning_content", ""),
        max_chars=self.config.context_reasoning_max_chars,
    )
    return {
        "role": "tool",
        "tool_call_id": (evidence or {}).get("tool_call_id"),
        "content": _format_think_result_text(
            final_content=artifact.get("metadata", {}).get("final_content", ""),
            reasoning_content=reasoning,
        ),
    }
```

In `ModelSummarizer.summarize_span()`, expand think entries using their linked artifacts instead of relying only on `evidence.content`.

**Step 4: Run the tests to verify they pass**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/context/test_layered_history_strategy.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add deep_coder/context/strategies/layered_history/strategy.py deep_coder/context/summarizers/model.py deep_coder/config.py tests/context/test_layered_history_strategy.py
git commit -m "feat: reinject think traces through layered history"
```

### Task 5: Emit Reasoning And Model Error Events From Harness And Tools

**Files:**
- Modify: `deep_coder/harness/deepcoder/harness.py`
- Modify: `deep_coder/harness/result.py`
- Modify: `deep_coder/tools/result.py`
- Modify: `deep_coder/tools/think/tool.py`
- Test: `tests/harness/test_deepcoder_harness.py`

**Step 1: Write the failing tests**

Add tests for:

```python
def test_harness_emits_reasoning_recorded_for_think_results(...):
    assert [event["type"] for event in events] == [
        "turn_started",
        "message_committed",
        "tool_called",
        "tool_output",
        "reasoning_recorded",
        "message_committed",
        "turn_finished",
    ]


def test_harness_emits_model_error_and_finishes_turn_when_model_call_fails(...):
    assert events[2]["type"] == "model_error"
    assert events[-1]["type"] in {"turn_failed", "turn_finished"}
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/harness/test_deepcoder_harness.py
```

Expected:

- FAIL because no `reasoning_recorded` or `model_error` events exist

**Step 3: Write the minimal implementation**

In `DeepCoderHarness.run()`:

```python
try:
    response = self.model.complete({...})
except Exception as exc:
    error_event = _model_error_event(
        session=session,
        turn_id=turn_id,
        scope="main_model",
        model_name=self.config.model_name,
        error=exc,
    )
    self._publish(session, event_sink, error_event)
    self._publish(session, event_sink, self._event(session, turn_id, "turn_failed", reason="model_error"))
    return HarnessResult(final_text="", tool_results=tool_results, session_id=session.session_id)
```

After each tool result:

```python
if output.reasoning_content:
    self._publish(
        session,
        event_sink,
        self._event(
            session,
            turn_id,
            "reasoning_recorded",
            tool_call_id=tool_call["id"],
            name=tool_call["name"],
            model_name=output.metadata.get("model_name", "deepseek-reasoner"),
            final_content=output.metadata.get("final_content", ""),
            reasoning_content=output.reasoning_content,
        ),
    )
```

In `ThinkTool.exec()`, wrap DeepSeek exceptions as a tool error result and attach a `model_error` timeline event in `timeline_events`.

**Step 4: Run the tests to verify they pass**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/harness/test_deepcoder_harness.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add deep_coder/harness/deepcoder/harness.py deep_coder/harness/result.py deep_coder/tools/result.py deep_coder/tools/think/tool.py tests/harness/test_deepcoder_harness.py
git commit -m "feat: emit reasoning and model error events"
```

### Task 6: Render Reasoning And Error Blocks In The TUI

**Files:**
- Modify: `deep_coder/tui/render.py`
- Modify: `deep_coder/tui/app.py`
- Test: `tests/tui/test_render.py`
- Test: `tests/tui/test_live_events.py`

**Step 1: Write the failing tests**

Add tests for:

```python
def test_render_reasoning_block_shows_model_name_and_trace():
    block = render_reasoning_block(
        {
            "model_name": "deepseek-reasoner",
            "final_content": "answer",
            "reasoning_content": "cot",
        }
    )
    text = render_plain_text(block)
    assert "deepseek-reasoner" in text
    assert "answer" in text
    assert "cot" in text


def test_render_model_error_block_shows_retryability():
    block = render_model_error_block(
        {
            "model_name": "deepseek-reasoner",
            "status_code": 429,
            "message": "rate limit reached",
            "retryable": True,
        }
    )
    assert "retryable" in render_plain_text(block).lower()
```

Also add live-event tests asserting that `reasoning_recorded`, `model_error`, and `turn_failed` appear in the timeline and update state correctly.

**Step 2: Run the tests to verify they fail**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_live_events.py
```

Expected:

- FAIL because no reasoning/error renderers or event handling exist

**Step 3: Write the minimal implementation**

In `deep_coder/tui/render.py`, add:

```python
def render_reasoning_block(event: dict) -> RenderableType: ...
def render_model_error_block(event: dict) -> RenderableType: ...
```

In `DeepCodeApp._append_event_block()` and `on_timeline_event()`:

```python
elif event_type == "reasoning_recorded":
    block = render_reasoning_block(event)
elif event_type == "model_error":
    block = render_model_error_block(event)
elif event_type == "turn_failed":
    self._turn_state = "idle"
```

Keep replay and live-event handling symmetrical.

**Step 4: Run the tests to verify they pass**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_live_events.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add deep_coder/tui/render.py deep_coder/tui/app.py tests/tui/test_render.py tests/tui/test_live_events.py
git commit -m "feat: render reasoning and api error events"
```

### Task 7: Run Focused Integration Verification Then Full Regression Suite

**Files:**
- Modify: `tests/tools/test_registry.py`
- Modify: `tests/context/test_layered_context_manager.py`
- Modify: `tests/context/test_layered_history_strategy.py`
- Modify: `tests/harness/test_deepcoder_harness.py`
- Modify: `tests/tui/test_render.py`
- Modify: `tests/tui/test_live_events.py`

**Step 1: Run the focused feature suite**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q \
  tests/models/test_deepseek_model.py \
  tests/tools/test_registry.py \
  tests/context/test_layered_context_manager.py \
  tests/context/test_layered_history_strategy.py \
  tests/context/test_filesystem_store.py \
  tests/harness/test_deepcoder_harness.py \
  tests/tui/test_render.py \
  tests/tui/test_live_events.py
```

Expected:

- PASS

**Step 2: Fix any remaining failures before broad verification**

If anything fails:

- update only the smallest relevant implementation/test file
- rerun only the failing test node until green

**Step 3: Run the full suite**

Run:

```bash
/home/wys/deep-code/.venv/bin/pytest -q
```

Expected:

- PASS

**Step 4: Review the diff**

Run:

```bash
git status --short
git diff --stat
git diff -- docs/plans/2026-03-28-think-tool.md deep_coder tests
```

Expected:

- only the planned files changed
- no accidental unrelated edits

**Step 5: Commit the final verification pass**

```bash
git add deep_coder tests
git commit -m "test: verify think tool reasoning flow"
```

## Notes For Execution

- Use `@superpowers:test-driven-development` for each task.
- Use `@superpowers:verification-before-completion` before claiming the feature is done.
- Do not build a nested reasoner loop. The `think` tool is one-shot only.
- Do not inject raw DeepSeek `reasoning_content` as a custom assistant message field in outer-session messages.
- Keep replay and live timeline behavior aligned by persisting the same event payloads that the TUI renders.
