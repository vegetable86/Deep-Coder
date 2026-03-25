from pathlib import Path

from deep_coder.tools.base import ToolBase
from deep_coder.tools.read_file.tool import _safe_path


class EditFileTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = Path(workdir)

    def exec(self, arguments: dict) -> str:
        path = _safe_path(self.workdir, arguments["path"])
        old_text = arguments["old_text"]
        new_text = arguments["new_text"]
        content = path.read_text()
        if old_text not in content:
            return f"error: text not found in {arguments['path']}"
        path.write_text(content.replace(old_text, new_text, 1))
        return f"updated {arguments['path']}"

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "Replace one text span in a file inside the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_text": {"type": "string"},
                        "new_text": {"type": "string"},
                    },
                    "required": ["path", "old_text", "new_text"],
                },
            },
        }
