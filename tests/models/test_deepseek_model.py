import json

from deep_coder.config import RuntimeConfig
from deep_coder.models.deepseek.model import DeepSeekModel


def test_deepseek_manifest_identifies_provider():
    manifest = DeepSeekModel.manifest()

    assert manifest["provider"] == "deepseek"
    assert manifest["transport"] == "openai-compatible-sdk"


def test_deepseek_complete_normalizes_tool_args_and_usage(monkeypatch, tmp_path):
    class FakeToolCall:
        id = "tool-1"
        function = type(
            "Fn",
            (),
            {"name": "read_file", "arguments": '{"path": "README.md"}'},
        )()

    class FakeUsage:
        def model_dump(self):
            return {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "prompt_cache_hit_tokens": 3,
                "prompt_cache_miss_tokens": 7,
            }

    class FakeResponse:
        choices = [
            type(
                "Choice",
                (),
                {
                    "message": type(
                        "Msg", (), {"content": None, "tool_calls": [FakeToolCall()]}
                    )(),
                    "finish_reason": "tool_calls",
                },
            )()
        ]
        usage = FakeUsage()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    model = DeepSeekModel(config=RuntimeConfig.from_env(workdir=tmp_path))
    model.client = type(
        "Client",
        (),
        {
            "chat": type(
                "Chat",
                (),
                {
                    "completions": type(
                        "Completions",
                        (),
                        {"create": staticmethod(lambda **_: FakeResponse())},
                    )()
                },
            )()
        },
    )()

    response = model.complete({"messages": [{"role": "user", "content": "read me"}]})

    assert response["tool_calls"][0]["arguments"] == {"path": "README.md"}
    assert response["usage"]["cache_hit_tokens"] == 3
    assert response["usage"]["cache_miss_tokens"] == 7


def test_deepseek_complete_serializes_assistant_tool_calls(monkeypatch, tmp_path):
    captured = {}

    class FakeResponse:
        choices = [
            type(
                "Choice",
                (),
                {
                    "message": type("Msg", (), {"content": "done", "tool_calls": []})(),
                    "finish_reason": "stop",
                },
            )()
        ]
        usage = None

    def fake_create(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    model = DeepSeekModel(config=RuntimeConfig.from_env(workdir=tmp_path))
    model.client = type(
        "Client",
        (),
        {
            "chat": type(
                "Chat",
                (),
                {
                    "completions": type(
                        "Completions",
                        (),
                        {"create": staticmethod(fake_create)},
                    )()
                },
            )()
        },
    )()

    model.complete(
        {
            "messages": [
                {"role": "user", "content": "read me"},
                {
                    "role": "assistant",
                    "content": "Looking up the file.",
                    "tool_calls": [
                        {
                            "id": "tool-1",
                            "name": "read_file",
                            "arguments": {"path": "README.md"},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "tool-1", "content": "file contents"},
            ]
        }
    )

    assert captured["messages"][1] == {
        "role": "assistant",
        "content": "Looking up the file.",
        "tool_calls": [
            {
                "id": "tool-1",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": json.dumps({"path": "README.md"}),
                },
            }
        ],
    }
    assert captured["messages"][2] == {
        "role": "tool",
        "tool_call_id": "tool-1",
        "content": "file contents",
    }


def test_deepseek_list_models_returns_model_ids(monkeypatch, tmp_path):
    class FakeModelItem:
        def __init__(self, model_id):
            self.id = model_id

    class FakeListResponse:
        data = [FakeModelItem("deepseek-chat"), FakeModelItem("deepseek-reasoner")]

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    model = DeepSeekModel(config=RuntimeConfig.from_env(workdir=tmp_path))
    model.client = type(
        "Client",
        (),
        {
            "models": type(
                "Models",
                (),
                {"list": staticmethod(lambda: FakeListResponse())},
            )()
        },
    )()

    assert model.list_models() == ["deepseek-chat", "deepseek-reasoner"]
