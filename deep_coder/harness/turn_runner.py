import importlib
import json
import sys
from pathlib import Path

from deep_coder.main import build_runtime
from deep_coder.projects.registry import ProjectRecord


class JsonLineEventSink:
    def __init__(self, stream):
        self.stream = stream

    def emit(self, event: dict) -> None:
        self.stream.write(json.dumps(event) + "\n")
        self.stream.flush()


def main() -> int:
    try:
        request = json.loads(sys.stdin.readline() or "{}")
        run_turn_request(request, stream=sys.stdout)
        return 0
    except Exception as exc:  # pragma: no cover - exercised via subprocess tests
        print(str(exc), file=sys.stderr)
        return 1


def run_turn_request(request: dict, stream) -> None:
    project = _load_project(request["project"])
    runtime_factory = _load_runtime_factory(request.get("runtime_factory"))
    runtime = runtime_factory(
        project=project,
        model_name=request.get("model_name"),
    )
    runtime["harness"].run(
        session_locator=_session_locator(request.get("session_id")),
        user_input=request["user_input"],
        event_sink=JsonLineEventSink(stream),
    )


def _load_project(data: dict) -> ProjectRecord:
    return ProjectRecord(
        path=Path(data["path"]),
        name=data["name"],
        key=data["key"],
        state_dir=Path(data["state_dir"]),
        last_opened_at=data["last_opened_at"],
    )


def _load_runtime_factory(import_path: str | None):
    if not import_path:
        return build_runtime
    module_name, _, attribute = import_path.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attribute)


def _session_locator(session_id: str | None) -> dict | None:
    if not session_id:
        return None
    return {"id": session_id}


if __name__ == "__main__":
    raise SystemExit(main())
