from deep_coder.context.session import Session
from deep_coder.tasks.manager import TaskManager


def test_session_starts_with_empty_task_state(tmp_path):
    session = Session(session_id="session-a", root=tmp_path)

    assert session.next_task_id == 1
    assert session.tasks == []


def test_task_manager_updates_dependencies_and_clears_blockers_on_completion(tmp_path):
    session = Session(session_id="session-a", root=tmp_path)
    manager = TaskManager(session)

    first = manager.create(subject="inspect repo")
    second = manager.create(subject="edit app")
    manager.update(first["id"], add_blocks=[second["id"]])
    updated = manager.update(first["id"], status="completed")

    assert updated["status"] == "completed"
    assert manager.get(second["id"])["blocked_by"] == []
