from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import OptionList


class SessionSwitcher(ModalScreen[str | None]):
    def __init__(self, sessions: list[dict]):
        super().__init__()
        self._sessions = sessions

    def compose(self) -> ComposeResult:
        yield OptionList(*(session["id"] for session in self._sessions), id="session-switcher")

    def on_mount(self) -> None:
        self.query_one("#session-switcher", OptionList).focus()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        self.dismiss(str(event.option.prompt))
