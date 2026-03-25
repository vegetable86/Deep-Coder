from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.widgets import Static, TextArea

from deep_coder.tui.render import (
    render_diff_block,
    render_message_block,
    render_tool_call_block,
    render_tool_output,
    render_usage_block,
)
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
        self.push_screen(SessionSwitcher(self._project_sessions()), self._on_session_selected)

    def load_session(self, session_id: str) -> None:
        session = self.runtime["context"].open(locator={"id": session_id})
        self.session_id = session_id
        self._timeline_blocks.clear()
        for event in session.events:
            self._append_event_block(event)
        self._refresh_timeline()
        self._update_status_strip()

    def _project_sessions(self) -> list[dict]:
        return [
            session
            for session in self.runtime["context"].list_sessions()
            if session.get("project_key") == self.project.key
        ]

    def _on_session_selected(self, session_id: str | None) -> None:
        if session_id:
            self.load_session(session_id)

    def _append_event_block(self, event: dict) -> None:
        event_type = event["type"]
        if event_type == "message_committed":
            block = render_message_block(event["role"], event["text"])
        elif event_type == "tool_called":
            block = render_tool_call_block(event["display_command"])
        elif event_type == "tool_output":
            block = render_tool_output(event["output_text"])
        elif event_type == "tool_diff":
            block = render_diff_block(event.get("path") or event["name"], event["diff_text"])
        elif event_type == "usage_reported":
            block = render_usage_block(event)
        else:
            return
        self._timeline_blocks.append(block)

    def _refresh_timeline(self) -> None:
        timeline = Text()
        for index, block in enumerate(self._timeline_blocks):
            if index:
                timeline.append("\n\n")
            timeline.append_text(block)
        self.query_one("#timeline", Static).update(timeline)

    def _update_status_strip(self) -> None:
        self.query_one("#status-strip", Static).update(
            f"{self.project.name} | {self.session_id or 'new'} | "
            f"{self.runtime['config'].model_name} | idle"
        )
