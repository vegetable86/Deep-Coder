import json
import uuid
from pathlib import Path

from deep_coder.context.session import Session
from deep_coder.context.stores.base import SessionStoreBase


class FileSystemSessionStore(SessionStoreBase):
    def __init__(
        self,
        root: Path,
        project_key: str | None = None,
        workspace_path: Path | None = None,
    ):
        self.root = Path(root)
        self.project_key = project_key
        self.workspace_path = str(workspace_path.resolve()) if workspace_path else None
        self.sessions_dir = self.root / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def list_sessions(self) -> list[dict]:
        sessions = []
        for session_dir in sorted(self.sessions_dir.iterdir()):
            meta_path = session_dir / "meta.json"
            if meta_path.exists():
                sessions.append(json.loads(meta_path.read_text()))
        return sessions

    def open(self, locator: dict | None = None):
        session_id = locator["id"] if locator else uuid.uuid4().hex[:12]
        session_dir = self.sessions_dir / session_id
        meta_path = session_dir / "meta.json"
        messages_path = session_dir / "messages.jsonl"
        events_path = session_dir / "events.jsonl"
        strategy_name = "simple_history"
        strategy_state = {}
        messages = []
        events = []
        project_key = self.project_key
        workspace_path = self.workspace_path

        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            project_key = meta.get("project_key")
            workspace_path = meta.get("workspace_path")

        context_root = session_dir / "context"
        if context_root.exists():
            strategy_dirs = sorted(path for path in context_root.iterdir() if path.is_dir())
            if strategy_dirs:
                strategy_name = strategy_dirs[0].name

        if messages_path.exists():
            messages = [
                json.loads(line)
                for line in messages_path.read_text().splitlines()
                if line.strip()
            ]
        if events_path.exists():
            events = [
                json.loads(line)
                for line in events_path.read_text().splitlines()
                if line.strip()
            ]

        state_path = session_dir / "context" / strategy_name / "state.json"
        if state_path.exists():
            strategy_state = json.loads(state_path.read_text())

        return Session(
            session_id=session_id,
            root=session_dir,
            messages=messages,
            events=events,
            project_key=project_key,
            workspace_path=workspace_path,
            strategy_name=strategy_name,
            strategy_state=strategy_state,
        )

    def save(self, session) -> None:
        session_dir = self.sessions_dir / session.session_id
        context_dir = session_dir / "context" / session.strategy_name
        session_dir.mkdir(parents=True, exist_ok=True)
        context_dir.mkdir(parents=True, exist_ok=True)

        (session_dir / "meta.json").write_text(json.dumps(session.meta(), indent=2))
        (session_dir / "messages.jsonl").write_text(
            "".join(json.dumps(message) + "\n" for message in session.messages)
        )
        (session_dir / "events.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in session.events)
        )
        (context_dir / "state.json").write_text(
            json.dumps(session.strategy_state, indent=2)
        )
