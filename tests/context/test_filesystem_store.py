import json

from deep_coder.context.stores.filesystem.store import FileSystemSessionStore


def test_filesystem_store_creates_and_lists_sessions(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)

    session = store.open()
    store.save(session)

    session_dir = tmp_path / "sessions" / session.session_id
    assert store.list_sessions() == [session.meta()]
    assert (session_dir / "meta.json").exists()
    assert (session_dir / "messages.jsonl").exists()


def test_filesystem_store_persists_messages_and_strategy_state(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)

    session = store.open()
    session.append({"role": "user", "content": "hello"})
    session.strategy_name = "simple_history"
    session.strategy_state = {"message_count": 1}
    store.save(session)

    reopened = store.open(locator={"id": session.session_id})
    state_path = (
        tmp_path
        / "sessions"
        / session.session_id
        / "context"
        / "simple_history"
        / "state.json"
    )

    assert reopened.messages == [{"role": "user", "content": "hello"}]
    assert reopened.strategy_name == "simple_history"
    assert reopened.strategy_state == {"message_count": 1}
    assert json.loads(state_path.read_text()) == {"message_count": 1}
