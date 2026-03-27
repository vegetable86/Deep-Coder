from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option


class SkillListScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", "Close", show=False)]
    EMPTY_LABEL = "No skills installed"

    def __init__(self, skills: list[dict]):
        super().__init__()
        self._skills = skills

    def compose(self) -> ComposeResult:
        if not self._skills:
            yield OptionList(
                Option(self.EMPTY_LABEL, disabled=True),
                id="skill-list",
            )
            return
        yield OptionList(
            *(Option(self._label_for(skill)) for skill in self._skills),
            id="skill-list",
        )

    def on_mount(self) -> None:
        self.query_one("#skill-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    @staticmethod
    def _label_for(skill: dict) -> str:
        marker = "*" if skill.get("is_active") else "-"
        parts = [f"{marker} {skill['name']}"]
        title = skill.get("title")
        summary = skill.get("summary")
        if isinstance(title, str) and title:
            parts.append(title)
        if isinstance(summary, str) and summary:
            parts.append(summary)
        label = "  ".join(parts)
        if len(label) <= 96:
            return label
        return f"{label[:93].rstrip()}..."
