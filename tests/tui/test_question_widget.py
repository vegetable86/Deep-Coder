import asyncio

import pytest
from textual.app import App, ComposeResult
from textual.css.query import NoMatches

from deep_coder.tui.widgets.question_widget import QuestionWidget


class QuestionWidgetHarness(App):
    def __init__(self, widget: QuestionWidget):
        super().__init__()
        self._widget = widget

    def compose(self) -> ComposeResult:
        yield self._widget


def test_question_widget_reveals_other_and_collects_answers():
    async def run():
        widget = QuestionWidget(
            {
                "questions": [
                    {
                        "question": "Which approach should I use?",
                        "options": [
                            {"label": "Option A", "description": "Fast but less accurate"},
                        ],
                    }
                ]
            }
        )
        app = QuestionWidgetHarness(widget)
        async with app.run_test(size=(120, 40)):
            await asyncio.sleep(0)
            other_input = widget.query_one("#question-other-0")
            assert other_input.display is False

            widget.select_option(0, "Other")
            await asyncio.sleep(0)

            assert other_input.display is True
            other_input.load_text("My custom answer")

            answers = widget.submit_answers()

            assert answers == {"Which approach should I use?": "My custom answer"}
            assert widget.query_one("#question-summary").display is True

    asyncio.run(run())


def test_question_widget_auto_submits_last_selected_option():
    async def run():
        widget = QuestionWidget(
            {
                "questions": [
                    {
                        "question": "Which approach should I use?",
                        "options": [
                            {"label": "Option A", "description": "Fast but less accurate"},
                        ],
                    }
                ]
            }
        )
        app = QuestionWidgetHarness(widget)
        async with app.run_test(size=(120, 40)):
            await asyncio.sleep(0)

            with pytest.raises(NoMatches):
                widget.query_one("#question-submit")

            widget.select_option(0, "Option A")
            await asyncio.sleep(0)

            assert widget.query_one("#question-summary").display is True
            assert widget._submitted_answers == {"Which approach should I use?": "Option A"}

    asyncio.run(run())


def test_question_widget_escape_leaves_other_input_and_focuses_current_option_list():
    async def run():
        widget = QuestionWidget(
            {
                "questions": [
                    {
                        "question": "Which approach should I use first?",
                        "options": [
                            {"label": "Option A", "description": "Fast but less accurate"},
                        ],
                    },
                    {
                        "question": "Which approach should I use second?",
                        "options": [
                            {"label": "Option B", "description": "Slower but more accurate"},
                        ],
                    },
                ]
            }
        )
        app = QuestionWidgetHarness(widget)
        async with app.run_test(size=(120, 40)) as pilot:
            await asyncio.sleep(0)

            widget.select_option(0, "Other")
            await asyncio.sleep(0)

            other_input = widget.query_one("#question-other-0")
            other_input.load_text("My custom answer")
            assert app.focused is other_input

            await pilot.press("escape")
            await asyncio.sleep(0)

            assert app.focused is widget.query_one("#question-options-0")

    asyncio.run(run())


def test_question_widget_escape_submits_last_custom_answer():
    async def run():
        widget = QuestionWidget(
            {
                "questions": [
                    {
                        "question": "Which approach should I use?",
                        "options": [
                            {"label": "Option A", "description": "Fast but less accurate"},
                        ],
                    }
                ]
            }
        )
        app = QuestionWidgetHarness(widget)
        async with app.run_test(size=(120, 40)) as pilot:
            await asyncio.sleep(0)

            widget.select_option(0, "Other")
            await asyncio.sleep(0)

            other_input = widget.query_one("#question-other-0")
            other_input.load_text("My custom answer")
            assert app.focused is other_input

            await pilot.press("escape")
            await asyncio.sleep(0)

            assert widget.query_one("#question-summary").display is True
            assert widget._submitted_answers == {"Which approach should I use?": "My custom answer"}

    asyncio.run(run())
