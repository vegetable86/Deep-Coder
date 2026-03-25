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
