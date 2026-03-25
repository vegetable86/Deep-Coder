import asyncio

from deep_coder.tui.app import DeepCodeApp


def test_reopening_session_replays_persisted_events(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            app.load_session("session-a")
            timeline_text = app.query_one("#timeline").renderable.plain
            assert "mkdir aa" in timeline_text
            assert "prompt_tokens" in timeline_text

    asyncio.run(run())
