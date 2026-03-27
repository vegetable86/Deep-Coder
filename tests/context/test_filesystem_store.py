import pytest
from pathlib import Path
from deep_coder.context.session import Session
from deep_coder.context.stores.filesystem.store import FileSystemSessionStore


def test_session_meta_includes_active_skills(tmp_path):
    session = Session(
        session_id="session-1",
        root=tmp_path,
        active_skills=[
            {
                "name": "python-tests",
                "title": "Python Test Fixing",
                "hash": "sha256:test",
                "activated_at": "2026-03-27T00:00:00Z",
                "source": "user",
            }
        ],
    )

    assert session.meta()["active_skills"][0]["name"] == "python-tests"


def test_filesystem_store_round_trips_active_skills(tmp_path):
    store = FileSystemSessionStore(root=tmp_path)
    session = store.open(locator={"id": "session-a"})
    session.active_skills = [
        {
            "name": "python-tests",
            "title": "Python Test Fixing",
            "hash": "sha256:test",
            "activated_at": "2026-03-27T00:00:00Z",
            "source": "model",
        }
    ]

    store.save(session)
    reloaded = store.open(locator={"id": "session-a"})

    assert reloaded.active_skills[0]["source"] == "model"