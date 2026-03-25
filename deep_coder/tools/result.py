from dataclasses import dataclass


@dataclass
class ToolExecutionResult:
    name: str
    display_command: str
    model_output: str
    output_text: str
    diff_text: str | None = None
    is_error: bool = False
