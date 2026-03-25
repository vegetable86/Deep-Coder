from deep_coder.config import RuntimeConfig
from deep_coder.tools.bash.tool import BashTool
from deep_coder.tools.edit_file.tool import EditFileTool
from deep_coder.tools.read_file.tool import ReadFileTool
from deep_coder.tools.write_file.tool import WriteFileTool


def test_bash_tool_executes_simple_command(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path)
    tool = BashTool(config=config, workdir=tmp_path)

    assert tool.exec({"command": "printf runtime-ok"}) == "runtime-ok"


def test_file_tools_round_trip_content(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path)
    writer = WriteFileTool(config=config, workdir=tmp_path)
    reader = ReadFileTool(config=config, workdir=tmp_path)
    editor = EditFileTool(config=config, workdir=tmp_path)

    writer.exec({"path": "notes.txt", "content": "hello world"})
    editor.exec({"path": "notes.txt", "old_text": "world", "new_text": "runtime"})

    assert reader.exec({"path": "notes.txt"}) == "hello runtime"
