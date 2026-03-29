import asyncio
import json
import signal

from textual.css.query import NoMatches

from deep_coder.tui.app import DeepCodeApp
from deep_coder.tui.widgets.question_widget import QuestionWidget
from tests.tui.conftest import render_widget_text


def test_submit_runs_turn_starter_and_appends_live_events(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "make dir aa"
            await pilot.press("enter")
            await pilot.pause()
            timeline_text = render_widget_text(app.query_one("#timeline"))
            assert fake_runtime["turn_starter"].calls[-1]["session_id"] is None
            assert fake_runtime["turn_starter"].calls[-1]["user_input"] == "make dir aa"
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


def test_live_markdown_events_render_without_raw_fences(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            app.emit(
                {
                    "type": "message_committed",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                    "role": "assistant",
                    "text": "**done**\n- item\n> note\n```py\nprint('x')\n```",
                }
            )
            await asyncio.sleep(0)

            timeline_text = render_widget_text(app.query_one("#timeline"))
            assert "done" in timeline_text
            assert "item" in timeline_text
            assert "note" in timeline_text
            assert "print('x')" in timeline_text
            assert "```" not in timeline_text

    asyncio.run(run())


def test_live_task_snapshot_event_renders_inline_in_timeline(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            app.emit(
                {
                    "type": "task_snapshot",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                    "tasks": [
                        {
                            "id": 1,
                            "subject": "inspect repo",
                            "status": "in_progress",
                            "blocked_by": [],
                            "blocks": [],
                        }
                    ],
                    "completed_count": 0,
                    "total_count": 1,
                }
            )
            await asyncio.sleep(0)

            timeline_text = render_widget_text(app.query_one("#timeline"))
            assert "[>] #1: inspect repo" in timeline_text

    asyncio.run(run())


def test_live_context_compaction_events_render_inline_and_pulse_status(
    fake_runtime,
    fake_project,
):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            app.emit(
                {
                    "type": "context_compacting",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                }
            )
            await asyncio.sleep(0)

            status_strip = app.query_one("#status-strip")
            status_text = render_widget_text(status_strip)
            timeline_text = render_widget_text(app.query_one("#timeline"))
            assert "compacting context" in timeline_text.lower()
            assert "compacting" in status_text.lower()
            assert status_strip.has_class("busy") is True

            app.emit(
                {
                    "type": "context_compacted",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                }
            )
            app.emit(
                {
                    "type": "turn_finished",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                    "finish_reason": "stop",
                }
            )
            await asyncio.sleep(0)

            status_text = render_widget_text(app.query_one("#status-strip"))
            timeline_text = render_widget_text(app.query_one("#timeline"))
            assert "context compacted" in timeline_text.lower()
            assert "idle" in status_text.lower()

    asyncio.run(run())


def test_live_skill_events_render_inline_in_timeline(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            app.emit(
                {
                    "type": "skill_activated",
                    "session_id": "session-a",
                    "turn_id": "command",
                    "name": "python-tests",
                    "title": "Python Test Fixing",
                    "source": "user",
                    "hash": "sha256:test",
                }
            )
            app.emit(
                {
                    "type": "skill_dropped",
                    "session_id": "session-a",
                    "turn_id": "command",
                    "name": "python-tests",
                }
            )
            app.emit(
                {
                    "type": "skill_missing",
                    "session_id": "session-a",
                    "turn_id": "command",
                    "name": "python-tests",
                }
            )
            await asyncio.sleep(0)

            timeline_text = render_widget_text(app.query_one("#timeline"))
            assert "Skill active: python-tests" in timeline_text
            assert "Skill removed: python-tests" in timeline_text
            assert "Skill missing: python-tests" in timeline_text

    asyncio.run(run())


def test_question_asked_event_locks_composer_and_submits_answer(
    fake_runtime,
    fake_project,
):
    class RecordingTurn:
        def __init__(self):
            self.answers = []

        def write_answer(self, answer_json: str) -> None:
            self.answers.append(json.loads(answer_json))

    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        app._active_turn = RecordingTurn()
        async with app.run_test(size=(120, 40)):
            app.emit(
                {
                    "type": "question_asked",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                    "questions": [
                        {
                            "question": "Which approach should I use?",
                            "options": [
                                {
                                    "label": "Option A",
                                    "description": "Fast but less accurate",
                                }
                            ],
                        }
                    ],
                }
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            composer = app.query_one("#composer")
            widget = app.query_one(QuestionWidget)
            assert composer.disabled is True

            other_input = None
            for _ in range(5):
                try:
                    other_input = widget.query_one("#question-other-0")
                    break
                except NoMatches:
                    await asyncio.sleep(0)
            assert other_input is not None

            widget.select_option(0, "Other")
            other_input.load_text("My custom answer")
            widget.submit_answers()
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            assert app._active_turn.answers == [
                {"answers": {"Which approach should I use?": "My custom answer"}}
            ]
            assert composer.disabled is False
            assert "My custom answer" in render_widget_text(app.query_one("#timeline"))

    asyncio.run(run())


def test_session_replay_renders_question_asked_summary(fake_runtime, fake_project):
    async def run():
        session = fake_runtime["context"].open({"id": "session-a"})
        session.events = [
            {
                "type": "question_asked",
                "questions": [
                    {
                        "question": "Which approach should I use?",
                        "options": [
                            {
                                "label": "Option A",
                                "description": "Fast but less accurate",
                            }
                        ],
                    }
                ],
                "answers": {"Which approach should I use?": "Option A"},
            }
        ]
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            app.load_session("session-a")
            await asyncio.sleep(0)

            timeline_text = render_widget_text(app.query_one("#timeline"))
            assert "Which approach should I use?" in timeline_text
            assert "Option A" in timeline_text

    asyncio.run(run())


def test_live_reasoning_and_model_error_events_render_and_turn_failed_resets_status(
    fake_runtime,
    fake_project,
):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            app.emit(
                {
                    "type": "turn_started",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                }
            )
            app.emit(
                {
                    "type": "reasoning_recorded",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                    "tool_call_id": "tool-1",
                    "name": "think",
                    "model_name": "deepseek-reasoner",
                    "final_content": "answer",
                    "reasoning_content": "cot",
                }
            )
            app.emit(
                {
                    "type": "model_error",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                    "scope": "think_tool",
                    "model_name": "deepseek-reasoner",
                    "status_code": 429,
                    "message": "rate limit reached",
                    "retryable": True,
                    "error_type": "RateLimitError",
                }
            )
            app.emit(
                {
                    "type": "turn_failed",
                    "session_id": "session-a",
                    "turn_id": "turn-live",
                    "reason": "model_error",
                }
            )
            await asyncio.sleep(0)

            timeline_text = render_widget_text(app.query_one("#timeline"))
            status_text = render_widget_text(app.query_one("#status-strip"))
            assert "deepseek-reasoner" in timeline_text
            assert "answer" in timeline_text
            assert "cot" in timeline_text
            assert "rate limit reached" in timeline_text
            assert "retryable" in timeline_text.lower()
            assert "idle" in status_text.lower()

    asyncio.run(run())


def test_interrupted_turn_renders_marker_without_final_assistant_message(
    fake_runtime,
    fake_project,
):
    async def run():
        fake_runtime["turn_starter"].mode = "blocking"
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "wait there"
            app.action_submit_composer()
            await asyncio.sleep(0.05)

            await app.run_action("interrupt_turn")
            await asyncio.sleep(0.15)

            timeline_text = render_widget_text(app.query_one("#timeline"))
            assert "interrupted" in timeline_text.lower()
            assert "done" not in timeline_text

    asyncio.run(run())


def test_sigint_interrupts_running_turn_and_renders_marker(
    fake_runtime,
    fake_project,
):
    async def run():
        fake_runtime["turn_starter"].mode = "blocking"
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            composer = app.query_one("#composer")
            composer.text = "wait there"
            app.action_submit_composer()
            await asyncio.sleep(0.05)

            app._handle_sigint(signal.SIGINT, None)
            await asyncio.sleep(0.2)

            status_text = render_widget_text(app.query_one("#status-strip"))
            timeline_text = render_widget_text(app.query_one("#timeline"))
            assert "idle" in status_text
            assert "interrupted" in timeline_text.lower()
            assert "done" not in timeline_text

    asyncio.run(run())


def test_timeline_arrow_keys_scroll_multiple_lines_when_focused(fake_runtime, fake_project):
    async def run():
        session = fake_runtime["context"].open({"id": "session-a"})
        long_block = "\n".join(f"line {index}" for index in range(220))
        session.events = [
            {"type": "message_committed", "role": "assistant", "text": long_block},
        ]

        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(80, 20)) as pilot:
            app.load_session("session-a")
            await pilot.pause()

            timeline_scroll = app.query_one("#timeline-scroll")
            timeline_scroll.scroll_to(y=0, animate=False, immediate=True)
            await pilot.pause()

            await app.run_action("focus_timeline")
            await pilot.pause()
            assert timeline_scroll.has_focus is True

            start_scroll_y = timeline_scroll.scroll_y
            await pilot.press("down")
            await pilot.pause()

            assert timeline_scroll.scroll_y >= start_scroll_y + 3
            if hasattr(timeline_scroll, "_user_scroll_interrupt"):
                assert timeline_scroll._user_scroll_interrupt is True

            timeline_scroll.scroll_to(y=40, animate=False, immediate=True)
            await pilot.pause()

            start_scroll_y = timeline_scroll.scroll_y
            await pilot.press("up")
            await pilot.pause()

            assert timeline_scroll.scroll_y <= start_scroll_y - 3

    asyncio.run(run())
