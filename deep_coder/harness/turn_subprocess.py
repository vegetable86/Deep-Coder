import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys


class TurnSubprocess:
    def __init__(self, process: subprocess.Popen[str]):
        self._process = process

    def read_event(self, timeout: float | None = None) -> dict | None:
        stdout = self._process.stdout
        if stdout is None:
            return None
        if timeout is not None:
            ready, _, _ = select.select([stdout], [], [], timeout)
            if not ready:
                return None
        line = stdout.readline()
        if not line:
            return None
        return json.loads(line)

    def poll(self) -> int | None:
        return self._process.poll()

    def wait(self, timeout: float | None = None) -> int:
        return self._process.wait(timeout=timeout)

    def interrupt(self) -> None:
        if self.poll() is not None:
            return
        try:
            os.killpg(self._process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return

    def close(self) -> None:
        if self._process.stdin is not None and not self._process.stdin.closed:
            self._process.stdin.close()
        if self._process.stdout is not None and not self._process.stdout.closed:
            self._process.stdout.close()
        if self._process.stderr is not None and not self._process.stderr.closed:
            self._process.stderr.close()


def start_turn_subprocess(
    *,
    project,
    model_name: str,
    session_id: str | None,
    user_input: str,
    runtime_factory: str | None = None,
) -> TurnSubprocess:
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{repo_root}{os.pathsep}{python_path}" if python_path else str(repo_root)
    )
    request = {
        "project": {
            "path": str(project.path),
            "name": project.name,
            "key": project.key,
            "state_dir": str(project.state_dir),
            "last_opened_at": project.last_opened_at,
        },
        "model_name": model_name,
        "session_id": session_id,
        "user_input": user_input,
    }
    if runtime_factory:
        request["runtime_factory"] = runtime_factory

    process = subprocess.Popen(
        [sys.executable, "-m", "deep_coder.harness.turn_runner"],
        cwd=project.path,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    assert process.stdin is not None
    process.stdin.write(json.dumps(request))
    process.stdin.close()
    return TurnSubprocess(process)
