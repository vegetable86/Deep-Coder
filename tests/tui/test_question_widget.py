import asyncio

from textual.app import App, ComposeResult

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
