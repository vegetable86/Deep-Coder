import subprocess

from deep_coder.tools.base import ToolBase


class BashTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = workdir

    def exec(self, arguments: dict, session=None) -> str:
        command = arguments["command"]
        dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
        if any(item in command for item in dangerous):
            return "error: dangerous command blocked"

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return "error: command timed out"

        output = (result.stdout + result.stderr).strip()
        return output or "(no output)"

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Run a bash command inside the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                    },
                    "required": ["command"],
                },
            },
        }
