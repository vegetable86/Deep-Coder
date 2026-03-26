from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option


class SessionSwitcher(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "close", "Close", show=False)]
    EMPTY_LABEL = "No stored sessions for this project"

    def __init__(self, sessions: list[dict]):
        super().__init__()
        self._sessions = sessions

    def compose(self) -> ComposeResult:
        if not self._sessions:
            yield OptionList(
                Option(self.EMPTY_LABEL, disabled=True),
                id="session-switcher",
            )
            return
        yield OptionList(
            *(Option(self._label_for(session), id=session["id"]) for session in self._sessions),
            id="session-switcher",
        )

    def on_mount(self) -> None:
        self.query_one("#session-switcher", OptionList).focus()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        self.dismiss(event.option_id or self._sessions[event.option_index]["id"])

    def action_close(self) -> None:
        self.dismiss(None)

    @staticmethod
    def _label_for(session: dict) -> str:
        preview = session.get("preview")
        if not isinstance(preview, str):
            return session["id"]
        preview = " ".join(preview.split())
        if not preview:
            return session["id"]
        label = f'{session["id"]}  {preview}'
        if len(label) <= 96:
            return label
        return f"{label[:93].rstrip()}..."
