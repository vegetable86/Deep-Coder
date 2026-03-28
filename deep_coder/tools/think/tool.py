from pathlib import Path

from deep_coder.models.deepseek.model import DeepSeekModel
from deep_coder.tools.base import ToolBase
from deep_coder.tools.result import ToolExecutionResult


class ThinkTool(ToolBase):
    def __init__(self, config, workdir, model=None):
        self.config = config
        self.workdir = Path(workdir)
        self.model = model or DeepSeekModel(config=config)

    def exec(self, arguments: dict, session=None) -> ToolExecutionResult:
        response = self.model.complete(
            {
                "model_name": "deepseek-reasoner",
                "messages": [{"role": "user", "content": arguments["prompt"]}],
                "tools": [],
            }
        )
        final_content = response.get("content") or ""
        reasoning_content = response.get("reasoning_content") or ""
        return ToolExecutionResult(
            name="think",
            display_command="think",
            model_output=_format_think_result(final_content, reasoning_content),
            output_text=final_content,
            reasoning_content=reasoning_content,
            metadata={
                "model_name": "deepseek-reasoner",
                "prompt": arguments["prompt"],
                "final_content": final_content,
            },
        )

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "think",
                "description": "Use deepseek-reasoner once for deep reasoning, store the reasoning trace locally, and return a reasoning result to the main chat model.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The exact reasoning prompt to send to deepseek-reasoner.",
                        }
                    },
                    "required": ["prompt"],
                },
            },
        }


def _format_think_result(final_content: str, reasoning_content: str) -> str:
    return "\n".join(
        [
            "[think result]",
            "final_answer:",
            final_content,
            "",
            "reasoning_trace:",
            reasoning_content,
        ]
    )
