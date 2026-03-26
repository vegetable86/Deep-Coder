import asyncio

from deep_coder.tui.app import DeepCodeApp
from tests.tui.conftest import render_widget_text


def test_submit_runs_harness_and_appends_live_events(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "make dir aa"
            await pilot.press("enter")
            await pilot.pause()
            timeline_text = render_widget_text(app.query_one("#timeline"))
            assert "mkdir aa" in timeline_text
            assert "prompt 10 | usage 15 | hit 3 | miss 7" in timeline_text
            assert "done" in timeline_text

    asyncio.run(run())


def test_live_events_keep_timeline_pinned_when_already_at_bottom(fake_runtime, fake_project):
    async def run():
        session = fake_runtime["context"].open({"id": "session-a"})
        long_block = "\n".join(f"line {index}" for index in range(80))
        session.events = [
            {"type": "message_committed", "role": "assistant", "text": long_block},
            {"type": "message_committed", "role": "assistant", "text": long_block},
        ]

        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(80, 20)) as pilot:
            app.load_session("session-a")
            await pilot.pause()

            timeline_scroll = app.query_one("#timeline-scroll")
            timeline_scroll.scroll_end(animate=False, immediate=True, x_axis=False)
            await pilot.pause()

            start_scroll_y = timeline_scroll.scroll_y
            start_max_scroll_y = timeline_scroll.max_scroll_y
            assert timeline_scroll.is_vertical_scroll_end

            app.emit(
                {
                    "type": "message_committed",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                    "role": "assistant",
                    "text": "\n".join(f"new line {index}" for index in range(40)),
                }
            )
            await pilot.pause()
            await pilot.pause()

            assert timeline_scroll.max_scroll_y > start_max_scroll_y
            assert timeline_scroll.scroll_y > start_scroll_y
            assert timeline_scroll.is_vertical_scroll_end

    asyncio.run(run())


def test_live_events_do_not_force_scroll_when_user_moved_up(fake_runtime, fake_project):
    async def run():
        session = fake_runtime["context"].open({"id": "session-a"})
        long_block = "\n".join(f"line {index}" for index in range(80))
        session.events = [
            {"type": "message_committed", "role": "assistant", "text": long_block},
            {"type": "message_committed", "role": "assistant", "text": long_block},
        ]

        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(80, 20)) as pilot:
            app.load_session("session-a")
            await pilot.pause()

            timeline_scroll = app.query_one("#timeline-scroll")
            timeline_scroll.scroll_to(y=60, animate=False, immediate=True)
            await pilot.pause()

            start_scroll_y = timeline_scroll.scroll_y
            start_max_scroll_y = timeline_scroll.max_scroll_y
            assert not timeline_scroll.is_vertical_scroll_end

            app.emit(
                {
                    "type": "message_committed",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                    "role": "assistant",
                    "text": "\n".join(f"new line {index}" for index in range(40)),
                }
            )
            await pilot.pause()
            await pilot.pause()

            assert timeline_scroll.max_scroll_y > start_max_scroll_y
            assert timeline_scroll.scroll_y == start_scroll_y
            assert not timeline_scroll.is_vertical_scroll_end

    asyncio.run(run())
