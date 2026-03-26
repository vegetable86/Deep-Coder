from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console
from textual.visual import RichVisual

from deep_coder.projects.registry import ProjectRecord


@dataclass
class FakeSession:
    session_id: str
    events: list[dict] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    project_key: str | None = None
    workspace_path: str | None = None

    def meta(self) -> dict:
        meta = {
            "id": self.session_id,
            "project_key": self.project_key,
            "workspace_path": self.workspace_path,
        }
        for message in self.messages:
            if message.get("role") != "user":
                continue
            content = message.get("content")
            if not isinstance(content, str):
                continue
            preview = " ".join(content.split())
            if preview:
                meta["preview"] = preview
                break
        return meta


class FakeContext:
    def __init__(self, sessions: list[FakeSession]):
        self._sessions = {session.session_id: session for session in sessions}
        self._new_session_index = 0

    def list_sessions(self) -> list[dict]:
        return [session.meta() for session in self._sessions.values()]

    def open(self, locator: dict | None = None):
        if locator:
            session_id = locator["id"]
        else:
            self._new_session_index += 1
            session_id = f"session-new-{self._new_session_index}"
            seed = next(iter(self._sessions.values()))
            self._sessions[session_id] = FakeSession(
                session_id=session_id,
                project_key=seed.project_key,
                workspace_path=seed.workspace_path,
            )
        return self._sessions[session_id]


class FakeHarness:
    def __init__(self, context: FakeContext):
        self.context = context
        self.calls: list[dict] = []

    def run(self, session_locator, user_input: str, event_sink=None):
        self.calls.append(
            {
                "session_locator": session_locator,
                "user_input": user_input,
            }
        )
        session = self.context.open(locator=session_locator)
        turn_id = "turn-live"
        events = [
            {
                "type": "turn_started",
                "session_id": session.session_id,
                "turn_id": turn_id,
            },
            {
                "type": "message_committed",
                "session_id": session.session_id,
                "turn_id": turn_id,
                "role": "user",
                "text": user_input,
            },
            {
                "type": "tool_called",
                "session_id": session.session_id,
                "turn_id": turn_id,
                "name": "bash",
                "display_command": "bash: mkdir aa",
                "arguments": {"command": "mkdir aa"},
            },
            {
                "type": "usage_reported",
                "session_id": session.session_id,
                "turn_id": turn_id,
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "cache_hit_tokens": 3,
                "cache_miss_tokens": 7,
            },
            {
                "type": "message_committed",
                "session_id": session.session_id,
                "turn_id": turn_id,
                "role": "assistant",
                "text": "done",
            },
            {
                "type": "turn_finished",
                "session_id": session.session_id,
                "turn_id": turn_id,
                "finish_reason": "stop",
            },
        ]
        session.events.extend(events)
        for event in events:
            if event_sink is not None:
                event_sink.emit(event)
        return SimpleNamespace(session_id=session.session_id, final_text="done")


class FakeRegistry:
    def __init__(self, default_model: str = "deepseek-chat"):
        self._default_model = default_model

    def default_model(self) -> str:
        return self._default_model

    def set_default_model(self, model_name: str) -> None:
        self._default_model = model_name


class FakeModel:
    def __init__(self, config, models: tuple[str, ...] = ("deepseek-chat", "deepseek-reasoner")):
        self.config = config
        self._models = models

    def list_models(self) -> list[str]:
        return list(self._models)


def render_plain_text(renderable, width: int = 120) -> str:
    if isinstance(renderable, RichVisual):
        renderable = renderable._renderable
    capture = StringIO()
    console = Console(
        file=capture,
        force_terminal=False,
        color_system=None,
        width=width,
    )
    console.print(renderable, end="")
    return capture.getvalue().rstrip("\n")


def render_widget_text(widget, width: int = 120) -> str:
    children = list(getattr(widget, "children", []))
    if children:
        return "\n".join(
            chunk
            for chunk in (render_widget_text(child, width=width) for child in children)
            if chunk
        )
    return render_plain_text(widget.render(), width=width)


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
        messages=[{"role": "user", "content": "make dir aa"}],
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
        messages=[{"role": "user", "content": "show history selector preview"}],
        events=[],
    )
    session_other = FakeSession(
        session_id="session-other",
        project_key="other-project",
        workspace_path=str(fake_project.path.parent / "other"),
        messages=[{"role": "user", "content": "other project prompt"}],
        events=[],
    )
    context = FakeContext([session_a, session_b, session_other])
    config = SimpleNamespace(model_name="deepseek-chat")
    return {
        "config": config,
        "model": FakeModel(config=config),
        "context": context,
        "harness": FakeHarness(context),
        "registry": FakeRegistry(default_model=config.model_name),
    }
