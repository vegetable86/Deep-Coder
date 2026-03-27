from dataclasses import dataclass, field
from pathlib import Path


def derive_session_preview(messages: list[dict]) -> str | None:
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        preview = " ".join(content.split())
        if preview:
            return preview
    return None


@dataclass
class Session:
    session_id: str
    root: Path
    messages: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    journal: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    summaries: list[dict] = field(default_factory=list)
    artifacts: dict[str, dict] = field(default_factory=dict)
    next_task_id: int = 1
    tasks: list[dict] = field(default_factory=list)
    project_key: str | None = None
    workspace_path: str | None = None
    strategy_name: str = "simple_history"
    strategy_state: dict = field(default_factory=dict)

    def append(self, event: dict) -> None:
        self.messages.append(event)

    def meta(self) -> dict:
        meta = {
            "id": self.session_id,
            "project_key": self.project_key,
            "workspace_path": self.workspace_path,
        }
        preview = derive_session_preview(self.messages)
        if preview:
            meta["preview"] = preview
        return meta
