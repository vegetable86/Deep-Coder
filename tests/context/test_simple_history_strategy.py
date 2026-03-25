from deep_coder.context.manager import ContextManager
from deep_coder.context.session import Session
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore
from deep_coder.context.strategies.simple_history.strategy import (
    SimpleHistoryContextStrategy,
)


def test_simple_history_strategy_prepares_messages_from_session_history(tmp_path):
    strategy = SimpleHistoryContextStrategy()
    session = Session(session_id="s1", root=tmp_path)
    session.append({"role": "assistant", "content": "previous"})

    messages = strategy.prepare_messages(
        session=session,
        system_prompt="system text",
        user_input="next question",
    )

    assert messages == [
        {"role": "system", "content": "system text"},
        {"role": "assistant", "content": "previous"},
        {"role": "user", "content": "next question"},
    ]


def test_context_manager_records_events_and_flushes(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)
    strategy = SimpleHistoryContextStrategy()
    manager = ContextManager(store=store, strategy=strategy)

    session = manager.open()
    manager.record_event(session, {"role": "user", "content": "hello"})
    manager.record_event(session, {"role": "assistant", "content": "hi"})
    manager.flush(session)

    reopened = manager.open(locator={"id": session.session_id})

    assert reopened.messages == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
