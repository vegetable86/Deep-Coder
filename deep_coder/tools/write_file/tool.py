from pathlib import Path

from deep_coder.tools.base import ToolBase
from deep_coder.tools.read_file.tool import _safe_path


class WriteFileTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = Path(workdir)

    def exec(self, arguments: dict, session=None) -> str:
        path = _safe_path(self.workdir, arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        content = arguments["content"]
        path.write_text(content)
        return f"wrote {len(content)} bytes to {arguments['path']}"

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write a text file inside the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        }
