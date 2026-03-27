from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
import time
from types import SimpleNamespace

import pytest
from rich.console import Console
from textual.content import Content
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

    def flush(self, session) -> None:
        self._sessions[session.session_id] = session


class FakeTurnSubprocess:
    def __init__(
        self,
        events: list[dict],
        *,
        exit_code: int = 0,
        block_after_events: bool = False,
    ):
        self._events = list(events)
        self._completed_exit_code = exit_code
        self._exit_code = None
        self._block_after_events = block_after_events

    def read_event(self, timeout: float | None = None):
        if self._events:
            return self._events.pop(0)
        if not self._block_after_events and self._exit_code is None:
            self._exit_code = self._completed_exit_code
        if timeout:
            time.sleep(min(timeout, 0.01))
        return None

    def poll(self):
        if self._events:
            return None
        if not self._block_after_events and self._exit_code is None:
            self._exit_code = self._completed_exit_code
        return self._exit_code

    def wait(self, timeout: float | None = None):
        start = time.time()
        while self.poll() is None:
            if timeout is not None and (time.time() - start) >= timeout:
                raise TimeoutError("fake turn subprocess did not exit in time")
            time.sleep(0.01)
        return self._exit_code

    def interrupt(self):
        self._block_after_events = False
        self._exit_code = 130

    def close(self):
        return None


class FakeTurnStarter:
    def __init__(self, context: FakeContext):
        self.context = context
        self.calls: list[dict] = []
        self.mode = "complete"

    def __call__(
        self,
        *,
        project,
        model_name: str,
        session_id: str | None,
        user_input: str,
        runtime_factory: str | None = None,
    ):
        self.calls.append(
            {
                "project": project,
                "model_name": model_name,
                "session_id": session_id,
                "user_input": user_input,
            }
        )
        session = self.context.open(locator={"id": session_id} if session_id else None)
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
        ]
        session.messages.append({"role": "user", "content": user_input})

        if self.mode == "complete":
            events.extend(
                [
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
            )
            session.messages.append({"role": "assistant", "content": "done"})
            session.events.extend(events)
            return FakeTurnSubprocess(events, exit_code=0)

        session.events.extend(events)
        return FakeTurnSubprocess(events, exit_code=130, block_after_events=True)


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
    if isinstance(renderable, Content):
        return renderable.plain.rstrip("\n")
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
    turn_starter = FakeTurnStarter(context)
    return {
        "config": config,
        "model": FakeModel(config=config),
        "context": context,
        "turn_starter": turn_starter,
        "registry": FakeRegistry(default_model=config.model_name),
    }
