import json

from openai import OpenAI

from deep_coder.models.base import ModelBase


class DeepSeekModel(ModelBase):
    def __init__(self, config):
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def list_models(self) -> list[str]:
        response = self.client.models.list()
        models = []
        for item in getattr(response, "data", []):
            model_id = getattr(item, "id", None)
            if model_id:
                models.append(model_id)
        return sorted(models)

    def complete(self, request: dict) -> dict:
        response = self.client.chat.completions.create(
            model=self.config.model_name,
            messages=_serialize_messages(request["messages"]),
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


def _serialize_messages(messages: list[dict]) -> list[dict]:
    return [_serialize_message(message) for message in messages]


def _serialize_message(message: dict) -> dict:
    if message.get("role") != "assistant" or not message.get("tool_calls"):
        return message
    serialized = dict(message)
    serialized["tool_calls"] = [
        _serialize_tool_call(tool_call) for tool_call in message["tool_calls"]
    ]
    return serialized


def _serialize_tool_call(tool_call: dict) -> dict:
    function = tool_call.get("function")
    if function is not None:
        return {
            "id": tool_call["id"],
            "type": tool_call.get("type", "function"),
            "function": {
                "name": function["name"],
                "arguments": _serialize_outbound_tool_arguments(
                    function.get("arguments")
                ),
            },
        }
    return {
        "id": tool_call["id"],
        "type": "function",
        "function": {
            "name": tool_call["name"],
            "arguments": _serialize_outbound_tool_arguments(
                tool_call.get("arguments")
            ),
        },
    }


def _serialize_outbound_tool_arguments(arguments) -> str:
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments or {})
