import difflib
from pathlib import Path

from deep_coder.tools.bash.tool import BashTool
from deep_coder.tools.edit_file.tool import EditFileTool
from deep_coder.tools.history_load.tool import HistoryLoadTool
from deep_coder.tools.history_search.tool import HistorySearchTool
from deep_coder.tools.read_file.tool import ReadFileTool
from deep_coder.tools.read_file.tool import _safe_path
from deep_coder.tools.result import ToolExecutionResult
from deep_coder.tools.tasks.tool import (
    TaskCreateTool,
    TaskGetTool,
    TaskListTool,
    TaskUpdateTool,
)
from deep_coder.tools.write_file.tool import WriteFileTool


class ToolRegistry:
    def __init__(self, tools, workdir):
        self._tools = {tool.schema()["function"]["name"]: tool for tool in tools}
        self.workdir = Path(workdir)

    @classmethod
    def from_builtin(cls, config, workdir):
        return cls(
            [
                BashTool(config=config, workdir=workdir),
                ReadFileTool(config=config, workdir=workdir),
                WriteFileTool(config=config, workdir=workdir),
                EditFileTool(config=config, workdir=workdir),
                TaskCreateTool(config=config, workdir=workdir),
                TaskUpdateTool(config=config, workdir=workdir),
                TaskListTool(config=config, workdir=workdir),
                TaskGetTool(config=config, workdir=workdir),
                HistorySearchTool(config=config, workdir=workdir),
                HistoryLoadTool(config=config, workdir=workdir),
            ],
            workdir=workdir,
        )

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(
        self,
        name: str,
        arguments: dict,
        session=None,
    ) -> ToolExecutionResult:
        before = _maybe_read_target(self.workdir, name, arguments)
        try:
            output = self._tools[name].exec(arguments, session=session)
        except Exception as exc:
            output = ToolExecutionResult(
                name=name,
                display_command=_display_command(name, arguments),
                model_output=str(exc),
                output_text=str(exc),
                is_error=True,
            )
        after = _maybe_read_target(self.workdir, name, arguments)
        return _normalize_result(name, arguments, output, before, after)


def _display_command(name: str, arguments: dict) -> str:
    if name == "bash":
        return f"bash: {arguments['command']}"
    if "path" in arguments:
        return f"{name} {arguments['path']}"
    return name


def _maybe_read_target(workdir: Path, name: str, arguments: dict) -> str | None:
    if name not in {"write_file", "edit_file"}:
        return None
    path = _safe_path(workdir, arguments["path"])
    if not path.exists():
        return None
    return path.read_text()


def _build_diff(
    name: str,
    arguments: dict,
    before: str | None,
    after: str | None,
) -> str | None:
    if name not in {"write_file", "edit_file"}:
        return None
    if before == after:
        return None
    path = arguments["path"]
    before_lines = [] if before is None else before.splitlines(keepends=True)
    after_lines = [] if after is None else after.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _normalize_result(
    name: str,
    arguments: dict,
    output,
    before: str | None,
    after: str | None,
) -> ToolExecutionResult:
    display_command = _display_command(name, arguments)
    diff_text = _build_diff(name, arguments, before, after)
    if isinstance(output, ToolExecutionResult):
        return ToolExecutionResult(
            name=name,
            display_command=display_command,
            model_output=output.model_output,
            output_text=output.output_text,
            diff_text=output.diff_text if output.diff_text is not None else diff_text,
            is_error=output.is_error,
            timeline_events=_normalize_timeline_events(output.timeline_events),
        )
    return ToolExecutionResult(
        name=name,
        display_command=display_command,
        model_output=output,
        output_text=output,
        diff_text=diff_text,
        is_error=output.startswith("error:"),
    )


def _normalize_timeline_events(events: list[dict]) -> list[dict]:
    normalized = []
    for event in events:
        if "payload" in event:
            normalized.append(event)
            continue
        payload = {key: value for key, value in event.items() if key != "type"}
        normalized.append({"type": event["type"], "payload": payload})
    return normalized
