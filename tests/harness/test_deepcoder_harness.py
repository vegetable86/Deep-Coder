from types import SimpleNamespace

from deep_coder.context.manager import ContextManager
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore
from deep_coder.context.strategies.simple_history.strategy import (
    SimpleHistoryContextStrategy,
)
from deep_coder.harness.deepcoder.harness import DeepCoderHarness
from deep_coder.prompts.deepcoder.prompt import DeepCoderPrompt
from deep_coder.tools.result import ToolExecutionResult


def test_harness_executes_tool_calls_until_final_answer(tmp_path):
    class FakeModel:
        def __init__(self):
            self.calls = 0

        def complete(self, request):
            self.calls += 1
            if self.calls == 1:
                assert request["messages"][-1] == {
                    "role": "user",
                    "content": "read README",
                }
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tool-1",
                            "name": "read_file",
                            "arguments": {"path": "README.md"},
                        }
                    ],
                    "usage": None,
                    "finish_reason": "tool_calls",
                    "raw_response": None,
                }

            assert request["messages"][-1] == {
                "role": "tool",
                "tool_call_id": "tool-1",
                "content": "file contents",
            }
            return {
                "content": "done",
                "tool_calls": [],
                "usage": None,
                "finish_reason": "stop",
                "raw_response": None,
            }

    class FakeTools:
        def schemas(self):
            return [{"function": {"name": "read_file"}}]

        def execute(self, name, arguments):
            assert name == "read_file"
            assert arguments == {"path": "README.md"}
            return ToolExecutionResult(
                name=name,
                display_command="read_file README.md",
                model_output="file contents",
                output_text="file contents",
            )

    prompt = DeepCoderPrompt(
        config=SimpleNamespace(workdir=tmp_path),
    )
    context = ContextManager(
        store=FileSystemSessionStore(root=tmp_path),
        strategy=SimpleHistoryContextStrategy(),
    )
    harness = DeepCoderHarness(
        config=SimpleNamespace(),
        model=FakeModel(),
        prompt=prompt,
        context=context,
        tools=FakeTools(),
    )

    result = harness.run(session_locator=None, user_input="read README")
    reopened = context.open(locator={"id": result.session_id})

    assert result.final_text == "done"
    assert [tool.model_output for tool in result.tool_results] == ["file contents"]
    assert reopened.messages == [
        {"role": "user", "content": "read README"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "tool-1",
                    "name": "read_file",
                    "arguments": {"path": "README.md"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "tool-1", "content": "file contents"},
        {"role": "assistant", "content": "done"},
    ]


def test_harness_emits_and_persists_timeline_events(tmp_path):
    events = []

    class CapturingSink:
        def emit(self, event):
            events.append(event)

    class FakeModel:
        def __init__(self):
            self.calls = 0

        def complete(self, request):
            self.calls += 1
            if self.calls == 1:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tool-1",
                            "name": "edit_file",
                            "arguments": {
                                "path": "notes.txt",
                                "old_text": "world",
                                "new_text": "runtime",
                            },
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                        "cache_hit_tokens": 1,
                        "cache_miss_tokens": 9,
                    },
                    "finish_reason": "tool_calls",
                    "raw_response": None,
                }
            return {
                "content": "done",
                "tool_calls": [],
                "usage": {
                    "prompt_tokens": 7,
                    "completion_tokens": 3,
                    "total_tokens": 10,
                    "cache_hit_tokens": 0,
                    "cache_miss_tokens": 7,
                },
                "finish_reason": "stop",
                "raw_response": None,
            }

    class FakeTools:
        def schemas(self):
            return [{"function": {"name": "edit_file"}}]

        def execute(self, name, arguments):
            return ToolExecutionResult(
                name=name,
                display_command="edit_file notes.txt",
                model_output="updated notes.txt",
                output_text="updated notes.txt",
                diff_text="@@ -1 +1 @@\n-hello world\n+hello runtime\n",
            )

    prompt = DeepCoderPrompt(
        config=SimpleNamespace(workdir=tmp_path),
    )
    context = ContextManager(
        store=FileSystemSessionStore(root=tmp_path),
        strategy=SimpleHistoryContextStrategy(),
    )
    harness = DeepCoderHarness(
        config=SimpleNamespace(),
        model=FakeModel(),
        prompt=prompt,
        context=context,
        tools=FakeTools(),
    )

    result = harness.run(None, "fix note", event_sink=CapturingSink())
    reopened = context.open(locator={"id": result.session_id})

    assert [event["type"] for event in events] == [
        "turn_started",
        "message_committed",
        "usage_reported",
        "tool_called",
        "tool_output",
        "tool_diff",
        "usage_reported",
        "message_committed",
        "turn_finished",
    ]
    assert reopened.events == events
