from dataclasses import dataclass, field


@dataclass
class ToolExecutionResult:
    name: str
    display_command: str
    model_output: str
    output_text: str
    diff_text: str | None = None
    is_error: bool = False
    timeline_events: list[dict] = field(default_factory=list)
