from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.widgets import Static, TextArea

from deep_coder.tui.screens.session_switcher import SessionSwitcher


class DeepCodeApp(App):
    CSS_PATH = "styles.tcss"
    BINDINGS = [Binding("ctrl+l", "open_session_switcher", "Sessions")]

    def __init__(self, runtime, project):
        super().__init__()
        self.runtime = runtime
        self.project = project
        self.session_id = None
        self._timeline_blocks = []

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="timeline-scroll"):
            yield Static("", id="timeline")
        with Container(id="bottom-pane"):
            yield Static(id="status-strip")
            yield TextArea(id="composer")

    def on_mount(self) -> None:
        self._update_status_strip()

    def action_open_session_switcher(self) -> None:
        self.push_screen(SessionSwitcher(self._project_sessions()))

    def _project_sessions(self) -> list[dict]:
        return [
            session
            for session in self.runtime["context"].list_sessions()
            if session.get("project_key") == self.project.key
        ]

    def _update_status_strip(self) -> None:
        self.query_one("#status-strip", Static).update(
            f"{self.project.name} | {self.session_id or 'new'} | "
            f"{self.runtime['config'].model_name} | idle"
        )
