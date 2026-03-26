import asyncio

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
            assert labels == ["session-a", "session-b"]

    asyncio.run(run())
