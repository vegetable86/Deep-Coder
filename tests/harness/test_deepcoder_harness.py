from types import SimpleNamespace

from deep_coder.context.manager import ContextManager
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore
from deep_coder.context.strategies.simple_history.strategy import (
    SimpleHistoryContextStrategy,
)
from deep_coder.harness.deepcoder.harness import DeepCoderHarness
from deep_coder.prompts.deepcoder.prompt import DeepCoderPrompt


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
            return "file contents"

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
    assert result.tool_results == ["file contents"]
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
