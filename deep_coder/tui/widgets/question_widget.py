from textual import events
from textual.app import ComposeResult
from textual.containers import VerticalGroup
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import OptionList, Static, TextArea
from textual.widgets.option_list import Option

from deep_coder.tui.render import render_question_asked_block

_OTHER_LABEL = "Other"
_MAX_QUESTIONS = 3
_MAX_OPTIONS = 4
_PLACEHOLDER_QUESTION = "Placeholder question"
_PLACEHOLDER_OPTION = "Placeholder option"


class QuestionWidget(VerticalGroup):
    DEFAULT_CSS = """
    QuestionWidget {
        border: round $primary;
        padding: 0 1;
    }

    QuestionWidget #question-form {
        width: 1fr;
    }

    QuestionWidget .question-item {
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

    def __init__(
        self,
        event: dict,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._questions = _augment_questions(event["questions"])
        self._selected_labels: dict[int, str] = {}
        self._submitted_answers: dict[str, str] | None = None

    def compose(self) -> ComposeResult:
        with VerticalGroup(id="question-form"):
            yield Static("Awaiting user input", classes="question-prompt")
            with VerticalGroup(id="question-items"):
                for index in range(_MAX_QUESTIONS):
                    yield _QuestionItem(index)
            error_block = Static("", id="question-error")
            error_block.display = False
            yield error_block
        summary = Static("", id="question-summary")
        summary.display = False
        yield summary

    def on_mount(self) -> None:
        if not self._questions:
            return
        self._sync_question_items()
        self.call_after_refresh(self._focus_first_option)

    def load_event(self, event: dict) -> None:
        self._questions = _augment_questions(event["questions"])
        self._selected_labels = {}
        self._submitted_answers = None
        self.query_one("#question-form", VerticalGroup).display = True
        self._clear_error()
        summary = self.query_one("#question-summary", Static)
        summary.update("")
        summary.display = False
        self._sync_question_items()
        self._focus_first_option()

    def _sync_question_items(self) -> None:
        for index in range(_MAX_QUESTIONS):
            item = self.query_one(f"#question-item-{index}", VerticalGroup)
            if index >= len(self._questions):
                item.display = False
                continue

            item.display = True
            question = self._questions[index]
            self.query_one(f"#question-prompt-{index}", Static).update(question["question"])
            self.query_one(f"#{self._selection_id(index)}", Static).update("Selected: none")

            other_input = self.query_one(f"#{self._other_id(index)}", TextArea)
            other_input.display = False
            other_input.load_text("")

            options = self.query_one(f"#{self._options_id(index)}", OptionList)
            for option_index in range(_MAX_OPTIONS):
                option_id = self._option_slot_id(index, option_index)
                if option_index < len(question["options"]):
                    options.replace_option_prompt(
                        option_id,
                        _option_prompt(question["options"][option_index]),
                    )
                    options.enable_option(option_id)
                    continue
                options.replace_option_prompt(option_id, "")
                options.disable_option(option_id)
            options.highlighted = 0 if question["options"] else None

    def _focus_first_option(self) -> None:
        if self._questions:
            first_option_list = _maybe_query_one(
                self,
                f"#{self._options_id(0)}",
                OptionList,
            )
            if first_option_list is not None:
                self._set_focus(first_option_list)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not event.option_list.id or not event.option_list.id.startswith("question-options-"):
            return
        event.stop()
        index = int(event.option_list.id.rsplit("-", 1)[-1])
        if event.option_index >= len(self._questions[index]["options"]):
            return
        label = self._questions[index]["options"][event.option_index]["label"]
        self.select_option(index, label)

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
        self._clear_error()

        other_input = self.query_one(f"#{self._other_id(question_index)}", TextArea)
        if label == _OTHER_LABEL:
            other_input.display = True
            self._set_focus(other_input)
            return

        other_input.display = False
        other_input.load_text("")
        if question_index == len(self._questions) - 1:
            self._attempt_submit()
            return
        self._set_focus(self.query_one(f"#{self._options_id(question_index + 1)}", OptionList))

    def dismiss_other_input(self, question_index: int) -> None:
        other_input = self.query_one(f"#{self._other_id(question_index)}", TextArea)
        if question_index == len(self._questions) - 1 and other_input.text.strip():
            if self._attempt_submit():
                return

        current_options = _maybe_query_one(
            self,
            f"#{self._options_id(question_index)}",
            OptionList,
        )
        if current_options is not None:
            self._set_focus(current_options)

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
        self.query_one("#question-form", VerticalGroup).display = False
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

    def _attempt_submit(self) -> bool:
        try:
            self.submit_answers()
        except ValueError as exc:
            self._show_error(str(exc))
            self._focus_first_incomplete_question()
            return False
        return True

    def _focus_first_incomplete_question(self) -> None:
        for index, question in enumerate(self._questions):
            label = self._selected_labels.get(index)
            if label is None:
                self._set_focus(self.query_one(f"#{self._options_id(index)}", OptionList))
                return
            if label != _OTHER_LABEL:
                continue
            other_input = self.query_one(f"#{self._other_id(index)}", TextArea)
            if other_input.text.strip():
                continue
            other_input.display = True
            self._set_focus(other_input)
            self._show_error(f"Provide a custom answer for: {question['question']}")
            return

    def _clear_error(self) -> None:
        error_block = self.query_one("#question-error", Static)
        error_block.update("")
        error_block.display = False

    def _show_error(self, message: str) -> None:
        error_block = self.query_one("#question-error", Static)
        error_block.update(message)
        error_block.display = True

    def _set_focus(self, widget: Widget) -> None:
        if self.app is not None:
            self.app.set_focus(widget)
            return
        widget.focus()

    @staticmethod
    def _options_id(index: int) -> str:
        return f"question-options-{index}"

    @staticmethod
    def _other_id(index: int) -> str:
        return f"question-other-{index}"

    @staticmethod
    def _selection_id(index: int) -> str:
        return f"question-selection-{index}"

    @staticmethod
    def _option_slot_id(question_index: int, option_index: int) -> str:
        return f"question-option-{question_index}-{option_index}"


def _option_prompt(option: dict) -> str:
    description = option.get("description", "")
    if description:
        return f"{option['label']} - {description}"
    return option["label"]


def _augment_questions(questions: list[dict]) -> list[dict]:
    augmented = []
    for question in questions[:_MAX_QUESTIONS]:
        options = [dict(option) for option in question["options"][: _MAX_OPTIONS - 1]]
        if not any(option.get("label") == _OTHER_LABEL for option in options):
            options.append(
                {
                    "label": _OTHER_LABEL,
                    "description": "Type your own answer",
                }
            )
        options = options[:_MAX_OPTIONS]
        augmented.append({"question": question["question"], "options": options})
    return augmented


def _maybe_query_one(widget: Widget, selector: str, expect_type):
    try:
        return widget.query_one(selector, expect_type)
    except NoMatches:
        return None


class _QuestionItem(VerticalGroup):
    def __init__(self, index: int):
        super().__init__(id=f"question-item-{index}", classes="question-item")
        self._index = index

    def compose(self) -> ComposeResult:
        yield Static(
            _PLACEHOLDER_QUESTION,
            id=f"question-prompt-{self._index}",
            classes="question-prompt",
        )
        yield Static(
            "Selected: none",
            id=QuestionWidget._selection_id(self._index),
            classes="question-selection",
        )
        yield OptionList(
            *(
                Option(
                    _PLACEHOLDER_OPTION,
                    id=QuestionWidget._option_slot_id(self._index, option_index),
                )
                for option_index in range(_MAX_OPTIONS)
            ),
            id=QuestionWidget._options_id(self._index),
        )
        other_input = _QuestionOtherInput(self._index)
        other_input.display = False
        yield other_input


class _QuestionOtherInput(TextArea):
    def __init__(self, question_index: int):
        super().__init__(
            id=QuestionWidget._other_id(question_index),
            classes="question-other",
        )
        self._question_index = question_index

    async def _on_key(self, event: events.Key) -> None:
        if event.key in ("escape", "enter"):
            event.stop()
            event.prevent_default()
            widget = self._question_widget()
            if widget is not None:
                widget.call_later(widget.dismiss_other_input, self._question_index)
            return
        await super()._on_key(event)

    def _question_widget(self) -> QuestionWidget | None:
        node = self.parent
        while node is not None and not isinstance(node, QuestionWidget):
            node = node.parent
        if isinstance(node, QuestionWidget):
            return node
        return None
