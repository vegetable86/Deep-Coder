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


def build_streaming_runtime(*, project, model_name):
    return _build_runtime(project=project, model=_ImmediateModel())


def build_blocking_model_runtime(*, project, model_name):
    return _build_runtime(project=project, model=_BlockingModel())


def _build_runtime(*, project, model):
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
        tools=_NoopTools(),
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
