from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Session:
    session_id: str
    root: Path
    messages: list[dict] = field(default_factory=list)
    strategy_name: str = "simple_history"
    strategy_state: dict = field(default_factory=dict)

    def append(self, event: dict) -> None:
        self.messages.append(event)

    def meta(self) -> dict:
        return {"id": self.session_id}
