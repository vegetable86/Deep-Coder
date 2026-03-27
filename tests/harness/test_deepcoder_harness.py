import threading
from types import SimpleNamespace

from deep_coder.context.manager import ContextManager
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore
from deep_coder.context.strategies.layered_history.strategy import (
    LayeredHistoryContextStrategy,
)
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

        def execute(self, name, arguments, session=None):
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

        def execute(self, name, arguments, session=None):
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


def test_harness_passes_active_session_to_tools_and_emits_task_snapshot(tmp_path):
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
                            "name": "task_list",
                            "arguments": {},
                        }
                    ],
                    "usage": None,
                    "finish_reason": "tool_calls",
                    "raw_response": None,
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
            return [{"function": {"name": "task_list"}}]

        def execute(self, name, arguments, session=None):
            assert session is not None
            return ToolExecutionResult(
                name=name,
                display_command="task_list",
                model_output="(0/1 completed)",
                output_text="(0/1 completed)",
                timeline_events=[
                    {
                        "type": "task_snapshot",
                        "payload": {
                            "tasks": [
                                {
                                    "id": 1,
                                    "subject": "inspect repo",
                                    "status": "pending",
                                    "blocked_by": [],
                                    "blocks": [],
                                }
                            ],
                            "completed_count": 0,
                            "total_count": 1,
                        },
                    }
                ],
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

    harness.run(None, "show tasks", event_sink=CapturingSink())

    assert [event["type"] for event in events] == [
        "turn_started",
        "message_committed",
        "tool_called",
        "tool_output",
        "task_snapshot",
        "message_committed",
        "turn_finished",
    ]


def test_harness_flushes_completed_tool_results_before_later_tool_finishes(tmp_path):
    session_state = {}
    second_tool_started = threading.Event()
    release_second_tool = threading.Event()
    thread_errors = []
    result_holder = {}

    class CapturingSink:
        def emit(self, event):
            session_state["session_id"] = event["session_id"]

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
                            "name": "read_file",
                            "arguments": {"path": "README.md"},
                        },
                        {
                            "id": "tool-2",
                            "name": "read_file",
                            "arguments": {"path": "NOTES.md"},
                        },
                    ],
                    "usage": None,
                    "finish_reason": "tool_calls",
                    "raw_response": None,
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

        def execute(self, name, arguments, session=None):
            if arguments["path"] == "README.md":
                return ToolExecutionResult(
                    name=name,
                    display_command="read_file README.md",
                    model_output="first file",
                    output_text="first file",
                )
            second_tool_started.set()
            release_second_tool.wait(timeout=5)
            return ToolExecutionResult(
                name=name,
                display_command="read_file NOTES.md",
                model_output="second file",
                output_text="second file",
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

    def run_harness():
        try:
            result_holder["result"] = harness.run(
                None,
                "read both files",
                event_sink=CapturingSink(),
            )
        except Exception as exc:  # pragma: no cover - test cleanup path
            thread_errors.append(exc)
            release_second_tool.set()

    worker = threading.Thread(target=run_harness)
    worker.start()
    assert second_tool_started.wait(timeout=5) is True

    try:
        reopened = context.open(locator={"id": session_state["session_id"]})
        assert reopened.messages == [
            {"role": "user", "content": "read both files"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "tool-1",
                        "name": "read_file",
                        "arguments": {"path": "README.md"},
                    },
                    {
                        "id": "tool-2",
                        "name": "read_file",
                        "arguments": {"path": "NOTES.md"},
                    },
                ],
            },
            {"role": "tool", "tool_call_id": "tool-1", "content": "first file"},
        ]
        assert [event["type"] for event in reopened.events] == [
            "turn_started",
            "message_committed",
            "tool_called",
            "tool_output",
        ]
    finally:
        release_second_tool.set()
        worker.join(timeout=5)

    assert not thread_errors
    assert worker.is_alive() is False
    assert result_holder["result"].final_text == "done"


def test_harness_records_tool_calls_and_results_into_layered_context(tmp_path):
    class FakeSummarizer:
        def summarize_span(self, session, entries: list[dict]) -> dict:
            return {"goal": "summarized history"}

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
                            "name": "read_file",
                            "arguments": {"path": "README.md"},
                        }
                    ],
                    "usage": None,
                    "finish_reason": "tool_calls",
                    "raw_response": None,
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

        def execute(self, name, arguments, session=None):
            return ToolExecutionResult(
                name=name,
                display_command="read_file README.md",
                model_output="file contents",
                output_text="file contents",
            )

    prompt = DeepCoderPrompt(config=SimpleNamespace(workdir=tmp_path))
    context = ContextManager(
        store=FileSystemSessionStore(root=tmp_path),
        strategy=LayeredHistoryContextStrategy(
            config=SimpleNamespace(
                context_recent_turns=2,
                context_compact_threshold=4500,
                context_summary_max_tokens=1200,
            ),
            summarizer=FakeSummarizer(),
        ),
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

    assert [entry["kind"] for entry in reopened.journal] == [
        "user_message",
        "assistant_tool_call",
        "tool_result",
        "assistant_message",
    ]
    assert reopened.evidence[2]["content"] == "file contents"


def test_harness_triggers_compaction_after_large_prompt_usage(tmp_path):
    events = []

    class FakeSummarizer:
        def summarize_span(self, session, entries: list[dict]) -> dict:
            return {
                "goal": "inspect repo",
                "open_questions": ["next step"],
            }

    class CapturingSink:
        def emit(self, event):
            events.append(event)

    class FakeModel:
        def complete(self, request):
            return {
                "content": "done",
                "tool_calls": [],
                "usage": {
                    "prompt_tokens": 9000,
                    "completion_tokens": 10,
                    "total_tokens": 9010,
                    "cache_hit_tokens": 0,
                    "cache_miss_tokens": 9000,
                },
                "finish_reason": "stop",
                "raw_response": None,
            }

    class FakeTools:
        def schemas(self):
            return []

    prompt = DeepCoderPrompt(config=SimpleNamespace(workdir=tmp_path))
    context = ContextManager(
        store=FileSystemSessionStore(root=tmp_path),
        strategy=LayeredHistoryContextStrategy(
            config=SimpleNamespace(
                context_recent_turns=1,
                context_compact_threshold=4500,
                context_summary_max_tokens=1200,
            ),
            summarizer=FakeSummarizer(),
        ),
    )
    session = context.open(locator={"id": "session-a"})
    context.record_user_message(session, turn_id="turn-1", text="inspect repository")
    context.record_assistant_message(session, turn_id="turn-1", text="look at cli.py")
    context.flush(session)
    harness = DeepCoderHarness(
        config=SimpleNamespace(),
        model=FakeModel(),
        prompt=prompt,
        context=context,
        tools=FakeTools(),
    )

    result = harness.run(
        session_locator={"id": "session-a"},
        user_input="continue",
        event_sink=CapturingSink(),
    )
    reopened = context.open(locator={"id": result.session_id})

    assert any(event["type"] == "context_compacted" for event in events)
    assert reopened.summaries[-1]["covered_event_ids"] == [
        reopened.journal[0]["event_id"],
        reopened.journal[1]["event_id"],
    ]
