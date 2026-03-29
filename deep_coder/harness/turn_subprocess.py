import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time


class TurnSubprocess:
    def __init__(self, process: subprocess.Popen[str]):
        self._process = process
        self._process_group_id = process.pid

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

    def write_answer(self, answer_json: str) -> None:
        stdin = self._process.stdin
        if stdin is None or stdin.closed:
            raise RuntimeError("turn subprocess is not accepting input")
        stdin.write(answer_json)
        if not answer_json.endswith("\n"):
            stdin.write("\n")
        stdin.flush()

    def interrupt(self, *, grace_period: float = 0.2) -> None:
        if not self._process_group_exists() and self.poll() is not None:
            return
        self._signal_process_group(signal.SIGTERM)
        deadline = time.time() + grace_period
        while time.time() < deadline:
            if not self._process_group_exists():
                return
            time.sleep(0.05)
        self._signal_process_group(signal.SIGKILL)
        kill_deadline = time.time() + grace_period
        while time.time() < kill_deadline:
            if not self._process_group_exists():
                return
            time.sleep(0.05)

    def close(self) -> None:
        if self._process.stdin is not None and not self._process.stdin.closed:
            self._process.stdin.close()
        if self._process.stdout is not None and not self._process.stdout.closed:
            self._process.stdout.close()
        if self._process.stderr is not None and not self._process.stderr.closed:
            self._process.stderr.close()

    def _signal_process_group(self, sig: int) -> None:
        try:
            os.killpg(self._process_group_id, sig)
        except ProcessLookupError:
            return

    def _process_group_exists(self) -> bool:
        try:
            os.killpg(self._process_group_id, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


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
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()
    return TurnSubprocess(process)
