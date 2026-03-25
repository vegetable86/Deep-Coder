from dataclasses import dataclass

from deep_coder.tools.result import ToolExecutionResult


@dataclass
class HarnessResult:
    final_text: str
    tool_results: list[ToolExecutionResult]
    session_id: str
