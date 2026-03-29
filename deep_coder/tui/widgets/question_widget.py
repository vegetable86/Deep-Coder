from textual.app import ComposeResult
from textual.containers import Container
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from deep_coder.tui.render import render_question_asked_block

_OTHER_LABEL = "Other"


class QuestionWidget(Widget):
    DEFAULT_CSS = """
    QuestionWidget {
        layout: vertical;
        border: round $primary;
        padding: 0 1;
    }

    QuestionWidget #question-form {
        layout: vertical;
    }

    QuestionWidget .question-item {
        layout: vertical;
        margin: 1 0;
    }

    QuestionWidget .question-prompt {
        text-style: bold;
    }

    QuestionWidget .question-selection {
        color: $text-muted;
    }

    QuestionWidget .question-other {
        height: 3;
    }

    QuestionWidget #question-error {
        color: $error;
    }
    """

    class Answered(Message):
        bubble = True

        def __init__(self, answers: dict[str, str]):
            self.answers = answers
            super().__init__()

    def __init__(self, event: dict):
        super().__init__()
        self._questions = _augment_questions(event["questions"])
        self._selected_labels: dict[int, str] = {}
        self._submitted_answers: dict[str, str] | None = None

    def compose(self) -> ComposeResult:
        with Container(id="question-form"):
            yield Static("Awaiting user input", classes="question-prompt")
            for index, question in enumerate(self._questions):
                with Container(classes="question-item"):
                    yield Static(question["question"], classes="question-prompt")
                    yield Static("Selected: none", id=self._selection_id(index), classes="question-selection")
                    yield OptionList(
                        *(
                            Option(
                                _option_prompt(option),
                                id=option["label"],
                            )
                            for option in question["options"]
                        ),
                        id=self._options_id(index),
                    )
                    other_input = TextArea(id=self._other_id(index), classes="question-other")
                    other_input.display = False
                    yield other_input
            error_block = Static("", id="question-error")
            error_block.display = False
            yield error_block
            yield Button("Submit", id="question-submit", variant="primary")
        summary = Static("", id="question-summary")
        summary.display = False
        yield summary

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_first_option)

    def _focus_first_option(self) -> None:
        if self._questions:
            self.query_one(f"#{self._options_id(0)}", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not event.option_list.id or not event.option_list.id.startswith("question-options-"):
            return
        event.stop()
        index = int(event.option_list.id.rsplit("-", 1)[-1])
        label = event.option_id or self._questions[index]["options"][event.option_index]["label"]
        self.select_option(index, label)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "question-submit":
            return
        event.stop()
        try:
            self.submit_answers()
        except ValueError as exc:
            error_block = _maybe_query_one(self, "#question-error", Static)
            if error_block is not None:
                error_block.update(str(exc))
                error_block.display = True

    def select_option(self, question_index: int, label: str) -> None:
        question = self._questions[question_index]
        if label not in {option["label"] for option in question["options"]}:
            raise ValueError(f"unknown option: {label}")
        self._selected_labels[question_index] = label
        selection = _maybe_query_one(
            self,
            f"#{self._selection_id(question_index)}",
            Static,
        )
        if selection is not None:
            selection.update(f"Selected: {label}")
        error_block = _maybe_query_one(self, "#question-error", Static)
        if error_block is not None:
            error_block.update("")
            error_block.display = False

        other_input = self.query_one(f"#{self._other_id(question_index)}", TextArea)
        if label == _OTHER_LABEL:
            other_input.display = True
            other_input.focus()
            return

        other_input.display = False
        other_input.load_text("")
        if question_index == len(self._questions) - 1:
            self.query_one("#question-submit", Button).focus()
            return
        self.query_one(f"#{self._options_id(question_index + 1)}", OptionList).focus()

    def collect_answers(self) -> dict[str, str]:
        answers = {}
        for index, question in enumerate(self._questions):
            label = self._selected_labels.get(index)
            if label is None:
                raise ValueError(f"Select an answer for: {question['question']}")
            if label == _OTHER_LABEL:
                custom_answer = self.query_one(
                    f"#{self._other_id(index)}",
                    TextArea,
                ).text.strip()
                if not custom_answer:
                    raise ValueError(f"Provide a custom answer for: {question['question']}")
                answers[question["question"]] = custom_answer
                continue
            answers[question["question"]] = label
        return answers

    def submit_answers(self) -> dict[str, str]:
        if self._submitted_answers is not None:
            return dict(self._submitted_answers)
        answers = self.collect_answers()
        self._submitted_answers = dict(answers)
        self.query_one("#question-form", Container).display = False
        summary = self.query_one("#question-summary", Static)
        summary.update(
            render_question_asked_block(
                {
                    "type": "question_asked",
                    "questions": self._questions,
                    "answers": answers,
                }
            )
        )
        summary.display = True
        message = self.Answered(dict(answers))
        if self.app is not None and hasattr(self.app, "on_question_widget_answered"):
            self.app.on_question_widget_answered(message)
        else:
            self.post_message(message)
        return answers

    @staticmethod
    def _options_id(index: int) -> str:
        return f"question-options-{index}"

    @staticmethod
    def _other_id(index: int) -> str:
        return f"question-other-{index}"

    @staticmethod
    def _selection_id(index: int) -> str:
        return f"question-selection-{index}"


def _option_prompt(option: dict) -> str:
    description = option.get("description", "")
    if description:
        return f"{option['label']} - {description}"
    return option["label"]


def _augment_questions(questions: list[dict]) -> list[dict]:
    augmented = []
    for question in questions:
        options = [dict(option) for option in question["options"]]
        if not any(option.get("label") == _OTHER_LABEL for option in options):
            options.append(
                {
                    "label": _OTHER_LABEL,
                    "description": "Type your own answer",
                }
            )
        augmented.append({"question": question["question"], "options": options})
    return augmented


def _maybe_query_one(widget: Widget, selector: str, expect_type):
    try:
        return widget.query_one(selector, expect_type)
    except NoMatches:
        return None
