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
    assert json.loads(state_path.read_text()) == {
        "message_count": 1,
        "task_system": {
            "next_task_id": 1,
            "tasks": [],
        },
    }


def test_filesystem_store_persists_events_and_project_meta(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    store = FileSystemSessionStore(
        root=tmp_path,
        project_key="repo-abc123",
        workspace_path=workspace,
    )

    session = store.open()
    session.events.append({"type": "turn_started", "turn_id": "t1"})
    store.save(session)

    reopened = store.open(locator={"id": session.session_id})

    assert reopened.events == [{"type": "turn_started", "turn_id": "t1"}]
    assert reopened.meta()["project_key"] == "repo-abc123"
    assert reopened.meta()["workspace_path"] == str(workspace)


def test_filesystem_store_lists_session_preview_from_first_user_message(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)

    session = store.open()
    session.append(
        {
            "role": "user",
            "content": "  make   history\nselector   readable  ",
        }
    )
    session.append({"role": "assistant", "content": "ok"})
    store.save(session)

    listed = store.list_sessions()
    reopened = store.open(locator={"id": session.session_id})

    assert listed[0]["preview"] == "make history selector readable"
    assert reopened.meta()["preview"] == "make history selector readable"


def test_filesystem_store_backfills_preview_for_existing_session_metadata(tmp_path):
    session_dir = tmp_path / "sessions" / "session-a"
    session_dir.mkdir(parents=True)
    (session_dir / "meta.json").write_text(json.dumps({"id": "session-a"}, indent=2))
    (session_dir / "messages.jsonl").write_text(
        json.dumps(
            {
                "role": "user",
                "content": "show me the first prompt in history",
            }
        )
        + "\n"
    )

    store = FileSystemSessionStore(root=tmp_path)

    listed = store.list_sessions()

    assert listed == [
        {
            "id": "session-a",
            "preview": "show me the first prompt in history",
        }
    ]


def test_filesystem_store_persists_task_state(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)
    session = store.open()
    session.next_task_id = 3
    session.tasks = [
        {
            "id": 1,
            "subject": "inspect repo",
            "description": "",
            "status": "completed",
            "blocked_by": [],
            "blocks": [2],
        },
        {
            "id": 2,
            "subject": "edit app",
            "description": "",
            "status": "pending",
            "blocked_by": [],
            "blocks": [],
        },
    ]

    store.save(session)
    reopened = store.open(locator={"id": session.session_id})

    assert reopened.next_task_id == 3
    assert reopened.tasks[1]["subject"] == "edit app"
