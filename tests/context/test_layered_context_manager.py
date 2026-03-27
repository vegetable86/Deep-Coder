from deep_coder.context.manager import ContextManager
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore
from deep_coder.context.strategies.simple_history.strategy import (
    SimpleHistoryContextStrategy,
)
from deep_coder.tools.result import ToolExecutionResult


def test_context_manager_records_user_message_into_journal_and_evidence(tmp_path):
    manager = ContextManager(
        store=FileSystemSessionStore(root=tmp_path),
        strategy=SimpleHistoryContextStrategy(),
    )
    session = manager.open()

    manager.record_user_message(session, turn_id="turn-1", text="show files")

    assert session.journal[0]["kind"] == "user_message"
    assert session.evidence[0]["content"] == "show files"


def test_context_manager_records_tool_result_as_metadata_plus_artifact(tmp_path):
    manager = ContextManager(
        store=FileSystemSessionStore(root=tmp_path),
        strategy=SimpleHistoryContextStrategy(),
    )
    session = manager.open()

    manager.record_tool_result(
        session,
        turn_id="turn-1",
        tool_call_id="tool-1",
        tool_name="bash",
        arguments={"command": "tree ."},
        model_output="large output",
        output_text="large output",
    )

    assert session.journal[-1]["tool_name"] == "bash"
    assert session.journal[-1]["artifact_ids"]
    assert session.evidence[-1]["content"] == "large output"


def test_context_manager_records_tool_result_from_tool_execution_result(tmp_path):
    manager = ContextManager(
        store=FileSystemSessionStore(root=tmp_path),
        strategy=SimpleHistoryContextStrategy(),
    )
    session = manager.open()

    manager.record_tool_result(
        session,
        turn_id="turn-1",
        tool_call={
            "id": "tool-1",
            "name": "bash",
            "arguments": {"command": "tree ."},
        },
        output=ToolExecutionResult(
            name="bash",
            display_command="bash tree .",
            model_output="large output",
            output_text="large output",
        ),
    )

    assert session.artifacts
    assert session.evidence[-1]["content"] == "large output"
