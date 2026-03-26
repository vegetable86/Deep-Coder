import asyncio
from types import SimpleNamespace

import pytest
from textual.css.query import NoMatches

from deep_coder.tui.app import DeepCodeApp


def test_reopening_session_replays_persisted_events(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            app.load_session("session-a")
            timeline_text = app.query_one("#timeline").renderable.plain
            assert "mkdir aa" in timeline_text
            assert "prompt 10 | usage 14 | hit 0 | miss 10" in timeline_text

    asyncio.run(run())


def test_history_command_opens_project_session_list(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "/history"
            await app.run_action("refresh_command_palette")
            await pilot.press("enter")
            overlay = app.screen.query_one("#session-switcher")
            labels = [option.prompt for option in overlay.options]
            assert labels == [
                "session-a  make dir aa",
                "session-b  show history selector preview",
            ]

    asyncio.run(run())


def test_session_switcher_selection_uses_session_id(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "/history"
            await app.run_action("refresh_command_palette")
            await pilot.press("enter")
            await pilot.press("enter")

            assert app.session_id == "session-a"

    asyncio.run(run())


def test_history_command_shows_empty_state_when_project_has_no_sessions(
    fake_runtime, fake_project
):
    async def run():
        empty_project = SimpleNamespace(
            name=fake_project.name,
            key="missing-project",
            path=fake_project.path,
        )
        app = DeepCodeApp(runtime=fake_runtime, project=empty_project)
        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "/history"
            await app.run_action("refresh_command_palette")
            await pilot.press("enter")
            overlay = app.screen.query_one("#session-switcher")
            labels = [option.prompt for option in overlay.options]
            assert labels == ["No stored sessions for this project"]

    asyncio.run(run())


def test_empty_history_modal_can_be_closed_with_escape(fake_runtime, fake_project):
    async def run():
        empty_project = SimpleNamespace(
            name=fake_project.name,
            key="missing-project",
            path=fake_project.path,
        )
        app = DeepCodeApp(runtime=fake_runtime, project=empty_project)
        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "/history"
            await app.run_action("refresh_command_palette")
            await pilot.press("enter")
            await pilot.press("escape")
            await pilot.pause()

            with pytest.raises(NoMatches):
                app.screen.query_one("#session-switcher")
            assert composer.has_focus is True

    asyncio.run(run())
