from deep_coder.tools.bash.tool import BashTool
from deep_coder.tools.edit_file.tool import EditFileTool
from deep_coder.tools.read_file.tool import ReadFileTool
from deep_coder.tools.write_file.tool import WriteFileTool


class ToolRegistry:
    def __init__(self, tools):
        self._tools = {tool.schema()["function"]["name"]: tool for tool in tools}

    @classmethod
    def from_builtin(cls, config, workdir):
        return cls(
            [
                BashTool(config=config, workdir=workdir),
                ReadFileTool(config=config, workdir=workdir),
                WriteFileTool(config=config, workdir=workdir),
                EditFileTool(config=config, workdir=workdir),
            ]
        )

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        return self._tools[name].exec(arguments)
