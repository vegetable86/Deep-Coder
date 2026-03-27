import json
import os
import uuid
from pathlib import Path

from deep_coder.context.records import make_evidence_record, make_journal_entry
from deep_coder.context.session import Session, derive_session_preview
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
                meta = json.loads(meta_path.read_text())
                if not meta.get("preview"):
                    preview = self._load_preview(session_dir / "messages.jsonl")
                    if preview:
                        meta["preview"] = preview
                sessions.append(meta)
        return sessions

    def open(self, locator: dict | None = None):
        session_id = locator["id"] if locator else uuid.uuid4().hex[:12]
        session_dir = self.sessions_dir / session_id
        meta_path = session_dir / "meta.json"
        messages_path = session_dir / "messages.jsonl"
        events_path = session_dir / "events.jsonl"
        journal_path = session_dir / "journal.jsonl"
        evidence_path = session_dir / "evidence.jsonl"
        summaries_path = session_dir / "summaries.jsonl"
        artifacts_path = session_dir / "artifacts.json"
        strategy_name = "simple_history"
        strategy_state = {}
        messages = []
        events = []
        journal = []
        evidence = []
        summaries = []
        artifacts = {}
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
        if journal_path.exists():
            journal = [
                json.loads(line)
                for line in journal_path.read_text().splitlines()
                if line.strip()
            ]
        if evidence_path.exists():
            evidence = [
                json.loads(line)
                for line in evidence_path.read_text().splitlines()
                if line.strip()
            ]
        if summaries_path.exists():
            summaries = [
                json.loads(line)
                for line in summaries_path.read_text().splitlines()
                if line.strip()
            ]
        if artifacts_path.exists():
            artifacts = json.loads(artifacts_path.read_text())

        if messages and not journal:
            journal, evidence = _project_legacy_messages(messages)

        state_path = session_dir / "context" / strategy_name / "state.json"
        if state_path.exists():
            strategy_state = json.loads(state_path.read_text())
        task_state = strategy_state.pop("task_system", {})

        return Session(
            session_id=session_id,
            root=session_dir,
            messages=messages,
            events=events,
            journal=journal,
            evidence=evidence,
            summaries=summaries,
            artifacts=artifacts,
            next_task_id=task_state.get("next_task_id", 1),
            tasks=task_state.get("tasks", []),
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

        state = dict(session.strategy_state)
        state["task_system"] = {
            "next_task_id": session.next_task_id,
            "tasks": session.tasks,
        }
        _write_atomic_batch(
            {
                session_dir / "meta.json": json.dumps(session.meta(), indent=2),
                session_dir / "messages.jsonl": "".join(
                    json.dumps(message) + "\n" for message in session.messages
                ),
                session_dir / "events.jsonl": "".join(
                    json.dumps(event) + "\n" for event in session.events
                ),
                session_dir / "journal.jsonl": "".join(
                    json.dumps(entry) + "\n" for entry in session.journal
                ),
                session_dir / "evidence.jsonl": "".join(
                    json.dumps(record) + "\n" for record in session.evidence
                ),
                session_dir / "summaries.jsonl": "".join(
                    json.dumps(record) + "\n" for record in session.summaries
                ),
                session_dir / "artifacts.json": json.dumps(session.artifacts, indent=2),
                context_dir / "state.json": json.dumps(state, indent=2),
            }
        )

    @staticmethod
    def _load_preview(messages_path: Path) -> str | None:
        if not messages_path.exists():
            return None
        messages = [
            json.loads(line)
            for line in messages_path.read_text().splitlines()
            if line.strip()
        ]
        return derive_session_preview(messages)


def _write_atomic_batch(paths_to_content: dict[Path, str]) -> None:
    temp_paths = {
        path: path.with_name(f"{path.name}.tmp")
        for path in paths_to_content
    }
    try:
        for path, content in paths_to_content.items():
            temp_paths[path].write_text(content)
        for path, temp_path in temp_paths.items():
            os.replace(temp_path, path)
    except Exception:
        for temp_path in temp_paths.values():
            if temp_path.exists():
                temp_path.unlink()
        raise


def _project_legacy_messages(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    journal = []
    evidence = []
    for index, message in enumerate(messages, start=1):
        role = message.get("role", "assistant")
        event_id = f"legacy-event-{index}"
        kind = _legacy_kind_for_role(role)
        journal.append(
            make_journal_entry(
                event_id=event_id,
                turn_id=f"legacy-turn-{index}",
                kind=kind,
                role=role,
                tool_name=message.get("name"),
            )
        )
        evidence.append(
            make_evidence_record(
                evidence_id=f"legacy-evidence-{index}",
                event_id=event_id,
                role=role,
                content=message.get("content", ""),
            )
        )
    return journal, evidence


def _legacy_kind_for_role(role: str) -> str:
    if role == "user":
        return "user_message"
    if role == "tool":
        return "tool_result"
    return "assistant_message"
