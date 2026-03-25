from dataclasses import dataclass


@dataclass
class HarnessResult:
    final_text: str
    tool_results: list[str]
    session_id: str
