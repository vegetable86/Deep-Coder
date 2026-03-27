from collections.abc import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option


class SkillListScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", "Close", show=False)]
    EMPTY_LABEL = "No skills installed"

    def __init__(
        self,
        skills: list[dict],
        *,
        mode: str = "toggle",
        on_toggle: Callable[[str], bool] | None = None,
    ):
        super().__init__()
        self._skills = skills
        self._mode = mode
        self._on_toggle = on_toggle
        self._showing_content = False

    def compose(self) -> ComposeResult:
        yield OptionList(
            *self._options(),
            id="skill-list",
        )
        with VerticalScroll(id="skill-content-scroll"):
            yield Static("", id="skill-content")

    def on_mount(self) -> None:
        self.query_one("#skill-content-scroll", VerticalScroll).display = False
        self.query_one("#skill-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if not self._skills:
            return
        skill = self._skills[event.option_index]
        if self._mode == "browse":
            self._show_skill_content(skill)
            return
        self._toggle_skill(event.option_index, skill)

    def action_close(self) -> None:
        if self._showing_content:
            self._show_skill_list()
            return
        self.dismiss(None)

    def _toggle_skill(self, index: int, skill: dict) -> None:
        if self._on_toggle is None:
            return
        skill["is_active"] = self._on_toggle(skill["name"])
        self.query_one("#skill-list", OptionList).replace_option_prompt_at_index(
            index,
            self._label_for(skill),
        )

    def _show_skill_content(self, skill: dict) -> None:
        self._showing_content = True
        self.query_one("#skill-list", OptionList).display = False
        self.query_one("#skill-content-scroll", VerticalScroll).display = True
        self.query_one("#skill-content", Static).update(self._content_for(skill))

    def _show_skill_list(self) -> None:
        self._showing_content = False
        self.query_one("#skill-content-scroll", VerticalScroll).display = False
        skill_list = self.query_one("#skill-list", OptionList)
        skill_list.display = True
        skill_list.focus()

    def _options(self) -> list[Option]:
        if not self._skills:
            return [Option(self.EMPTY_LABEL, disabled=True)]
        return [Option(self._label_for(skill), id=skill["name"]) for skill in self._skills]

    @staticmethod
    def _content_for(skill: dict) -> str:
        title = skill.get("title")
        summary = skill.get("summary")
        body = skill.get("body") or ""
        heading = f"{title} ({skill['name']})" if title else skill["name"]
        sections = [heading]
        if isinstance(summary, str) and summary:
            sections.append(summary)
        if body:
            sections.extend(["", body.rstrip()])
        return "\n".join(sections)

    @staticmethod
    def _label_for(skill: dict) -> str:
        marker = "√" if skill.get("is_active") else "x"
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
