import asyncio

from deep_coder.tui.app import DeepCodeApp


def test_submit_runs_harness_and_appends_live_events(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "make dir aa"
            await pilot.press("enter")
            await pilot.pause()
            timeline_text = app.query_one("#timeline").renderable.plain
            assert "mkdir aa" in timeline_text
            assert "prompt 10 | usage 15 | hit 3 | miss 7" in timeline_text
            assert "done" in timeline_text

    asyncio.run(run())
