from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from deep_coder.projects.registry import ProjectRecord


@dataclass
class FakeSession:
    session_id: str
    events: list[dict] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    project_key: str | None = None
    workspace_path: str | None = None

    def meta(self) -> dict:
        return {
            "id": self.session_id,
            "project_key": self.project_key,
            "workspace_path": self.workspace_path,
        }


class FakeContext:
    def __init__(self, sessions: list[FakeSession]):
        self._sessions = {session.session_id: session for session in sessions}

    def list_sessions(self) -> list[dict]:
        return [session.meta() for session in self._sessions.values()]

    def open(self, locator: dict | None = None):
        session_id = locator["id"] if locator else "session-a"
        return self._sessions[session_id]


@pytest.fixture
def fake_project(tmp_path: Path) -> ProjectRecord:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    return ProjectRecord(
        path=workspace,
        name="repo",
        key="repo-abc123",
        state_dir=tmp_path / ".deepcode" / "projects" / "repo-abc123",
        last_opened_at="2026-03-25T00:00:00Z",
    )


@pytest.fixture
def fake_runtime(fake_project: ProjectRecord):
    session_a = FakeSession(
        session_id="session-a",
        project_key=fake_project.key,
        workspace_path=str(fake_project.path),
        events=[
            {"type": "message_committed", "role": "user", "text": "make dir aa"},
            {
                "type": "tool_called",
                "name": "bash",
                "display_command": "bash: mkdir aa",
                "arguments": {"command": "mkdir aa"},
            },
            {
                "type": "usage_reported",
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "total_tokens": 14,
                "cache_hit_tokens": 0,
                "cache_miss_tokens": 10,
            },
        ],
    )
    session_b = FakeSession(
        session_id="session-b",
        project_key=fake_project.key,
        workspace_path=str(fake_project.path),
        events=[],
    )
    session_other = FakeSession(
        session_id="session-other",
        project_key="other-project",
        workspace_path=str(fake_project.path.parent / "other"),
        events=[],
    )
    context = FakeContext([session_a, session_b, session_other])
    return {
        "config": SimpleNamespace(model_name="deepseek-chat"),
        "context": context,
    }
