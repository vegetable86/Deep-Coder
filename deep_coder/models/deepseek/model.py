import json

from openai import OpenAI

from deep_coder.models.base import ModelBase


class DeepSeekModel(ModelBase):
    def __init__(self, config):
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def complete(self, request: dict) -> dict:
        response = self.client.chat.completions.create(
            model=self.config.model_name,
            messages=request["messages"],
            tools=request.get("tools"),
        )
        message = response.choices[0].message
        tool_calls = []
        if message.tool_calls:
            for call in message.tool_calls:
                tool_calls.append(
                    {
                        "id": call.id,
                        "name": call.function.name,
                        "arguments": _normalize_tool_arguments(call.function.arguments),
                    }
                )
        usage_raw = response.usage.model_dump() if response.usage else {}
        return {
            "content": message.content,
            "tool_calls": tool_calls,
            "usage": {
                "prompt_tokens": usage_raw.get("prompt_tokens", 0),
                "completion_tokens": usage_raw.get("completion_tokens", 0),
                "total_tokens": usage_raw.get("total_tokens", 0),
                "cache_hit_tokens": usage_raw.get("prompt_cache_hit_tokens", 0),
                "cache_miss_tokens": usage_raw.get("prompt_cache_miss_tokens", 0),
            },
            "finish_reason": response.choices[0].finish_reason,
            "raw_response": response,
        }

    @staticmethod
    def manifest() -> dict:
        return {
            "provider": "deepseek",
            "transport": "openai-compatible-sdk",
        }


def _normalize_tool_arguments(arguments):
    if isinstance(arguments, str):
        return json.loads(arguments or "{}")
    return arguments or {}
