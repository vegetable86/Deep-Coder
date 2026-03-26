from pathlib import Path

from deep_coder.tools.base import ToolBase


def _safe_path(workdir: Path, path: str) -> Path:
    resolved = (Path(workdir) / path).resolve()
    if not resolved.is_relative_to(Path(workdir).resolve()):
        raise ValueError(f"path escapes workspace: {path}")
    return resolved


class ReadFileTool(ToolBase):
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = Path(workdir)

    def exec(self, arguments: dict, session=None) -> str:
        limit = arguments.get("limit")
        text = _safe_path(self.workdir, arguments["path"]).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)[:5000]

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a text file from the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["path"],
                },
            },
        }
