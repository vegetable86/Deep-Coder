import os
import shlex
import signal
import sys
import time
from types import SimpleNamespace

from deep_coder.context.manager import ContextManager
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore
from deep_coder.context.strategies.simple_history.strategy import (
    SimpleHistoryContextStrategy,
)
from deep_coder.harness.deepcoder.harness import DeepCoderHarness
from deep_coder.harness.turn_subprocess import start_turn_subprocess
from deep_coder.projects.registry import ProjectRecord
from deep_coder.prompts.deepcoder.prompt import DeepCoderPrompt
from deep_coder.tools.bash.tool import BashTool
from deep_coder.tools.registry import ToolRegistry

_IGNORE_TERM_PID_FILE = "deepcoder-ignore-term.pid"


class _NoopTools:
    def schemas(self):
        return []

    def execute(self, name, arguments, session=None):  # pragma: no cover - defensive only
        raise AssertionError("tool execution should not be reached in these tests")


class _ImmediateModel:
    def complete(self, request):
        return {
            "content": "done",
            "tool_calls": [],
            "usage": None,
            "finish_reason": "stop",
            "raw_response": None,
        }


class _BlockingModel:
    def complete(self, request):
        time.sleep(60)
        return {
            "content": "done",
            "tool_calls": [],
            "usage": None,
            "finish_reason": "stop",
            "raw_response": None,
        }


class _BashToolModel:
    def __init__(self, command: str):
        self.command = command
        self.calls = 0

    def complete(self, request):
        self.calls += 1
        if self.calls == 1:
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": "tool-1",
                        "name": "bash",
                        "arguments": {"command": self.command},
                    }
                ],
                "usage": None,
                "finish_reason": "tool_calls",
                "raw_response": None,
            }
        return {
            "content": "done",
            "tool_calls": [],
            "usage": None,
            "finish_reason": "stop",
            "raw_response": None,
        }


def build_streaming_runtime(*, project, model_name):
    return _build_runtime(project=project, model=_ImmediateModel())


def build_blocking_model_runtime(*, project, model_name):
    return _build_runtime(project=project, model=_BlockingModel())


def build_ignore_term_bash_runtime(*, project, model_name):
    command = (
        f"{shlex.quote(sys.executable)} -c "
        "\"import os,pathlib,signal,time; "
        f"pathlib.Path('{_IGNORE_TERM_PID_FILE}').write_text(str(os.getpid())); "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "time.sleep(60)\""
    )
    return _build_runtime(
        project=project,
        model=_BashToolModel(command),
        tools=ToolRegistry(
            [BashTool(config=SimpleNamespace(), workdir=project.path)],
            workdir=project.path,
        ),
    )


def _build_runtime(*, project, model, tools=None):
    prompt = DeepCoderPrompt(config=SimpleNamespace(workdir=project.path))
    context = ContextManager(
        store=FileSystemSessionStore(
            root=project.state_dir,
            project_key=project.key,
            workspace_path=project.path,
        ),
        strategy=SimpleHistoryContextStrategy(),
    )
    harness = DeepCoderHarness(
        config=SimpleNamespace(),
        model=model,
        prompt=prompt,
        context=context,
        tools=tools or _NoopTools(),
    )
    return {"harness": harness}


def test_turn_subprocess_streams_events_to_parent(tmp_path):
    project = _project_record(tmp_path)
    turn = start_turn_subprocess(
        project=project,
        model_name="deepseek-chat",
        session_id=None,
        user_input="say hi",
        runtime_factory="tests.harness.test_turn_subprocess:build_streaming_runtime",
    )

    try:
        events = _collect_events(turn)
    finally:
        turn.close()

    assert [event["type"] for event in events] == [
        "turn_started",
        "message_committed",
        "message_committed",
        "turn_finished",
    ]
    assert turn.wait(timeout=1) == 0


def test_turn_subprocess_can_be_interrupted_during_model_wait(tmp_path):
    project = _project_record(tmp_path)
    turn = start_turn_subprocess(
        project=project,
        model_name="deepseek-chat",
        session_id=None,
        user_input="wait there",
        runtime_factory="tests.harness.test_turn_subprocess:build_blocking_model_runtime",
    )

    try:
        events = []
        deadline = time.time() + 5
        while time.time() < deadline:
            event = turn.read_event(timeout=0.2)
            if event is not None:
                events.append(event)
            if [item["type"] for item in events] == ["turn_started", "message_committed"]:
                break
        assert [event["type"] for event in events] == ["turn_started", "message_committed"]

        turn.interrupt()
        assert turn.wait(timeout=5) != 0

        session_id = events[0]["session_id"]
        reopened = FileSystemSessionStore(root=project.state_dir).open(
            locator={"id": session_id}
        )
        assert reopened.messages == [{"role": "user", "content": "wait there"}]
        assert [event["type"] for event in reopened.events] == [
            "turn_started",
            "message_committed",
        ]
    finally:
        turn.close()


def test_turn_subprocess_interrupt_stops_long_running_bash_tool(tmp_path):
    project = _project_record(tmp_path)
    _kill_pid_from_file(project.path / _IGNORE_TERM_PID_FILE)
    turn = start_turn_subprocess(
        project=project,
        model_name="deepseek-chat",
        session_id=None,
        user_input="stop the shell command",
        runtime_factory="tests.harness.test_turn_subprocess:build_ignore_term_bash_runtime",
    )

    try:
        events = []
        deadline = time.time() + 5
        while time.time() < deadline:
            event = turn.read_event(timeout=0.2)
            if event is not None:
                events.append(event)
            if [item["type"] for item in events] == ["turn_started", "message_committed"]:
                break

        assert [event["type"] for event in events] == ["turn_started", "message_committed"]

        deadline = time.time() + 5
        while time.time() < deadline:
            if (project.path / _IGNORE_TERM_PID_FILE).exists():
                break
            time.sleep(0.05)
        assert (project.path / _IGNORE_TERM_PID_FILE).exists()
        child_pid = int((project.path / _IGNORE_TERM_PID_FILE).read_text().strip())
        assert _pid_exists(child_pid) is True

        turn.interrupt()
        assert turn.wait(timeout=5) != 0
        time.sleep(0.2)
        assert _pid_exists(child_pid) is False

        session_id = events[0]["session_id"]
        reopened = FileSystemSessionStore(root=project.state_dir).open(
            locator={"id": session_id}
        )
        assert [event["type"] for event in reopened.events] == [
            "turn_started",
            "message_committed",
        ]
    finally:
        turn.close()
        _kill_pid_from_file(project.path / _IGNORE_TERM_PID_FILE)


def _collect_events(turn) -> list[dict]:
    events = []
    deadline = time.time() + 5
    while time.time() < deadline:
        event = turn.read_event(timeout=0.2)
        if event is not None:
            events.append(event)
            continue
        if turn.poll() is not None:
            break
    return events


def _project_record(tmp_path) -> ProjectRecord:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_dir = tmp_path / ".deepcode" / "projects" / "repo-abc123"
    state_dir.mkdir(parents=True)
    return ProjectRecord(
        path=workspace,
        name="workspace",
        key="repo-abc123",
        state_dir=state_dir,
        last_opened_at="2026-03-27T00:00:00Z",
    )


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _kill_pid_from_file(path) -> None:
    if not path.exists():
        return
    try:
        pid = int(path.read_text().strip())
    except ValueError:
        path.unlink()
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    path.unlink()
