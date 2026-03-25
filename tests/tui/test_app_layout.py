import asyncio

from deep_coder.tui.app import DeepCodeApp


def test_app_has_timeline_and_composer_shell(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            assert app.query_one("#timeline")
            assert app.query_one("#status-strip")
            assert app.query_one("#composer")

    asyncio.run(run())


def test_session_switcher_lists_only_project_sessions(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("ctrl+l")
            overlay = app.screen.query_one("#session-switcher")
            labels = [option.prompt for option in overlay.options]
            assert labels == ["session-a", "session-b"]

    asyncio.run(run())
