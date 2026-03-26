from rich.console import Group, RenderableType
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import Static, TextArea

from deep_coder.tui.commands import CommandRegistry
from deep_coder.tui.commands.parser import parse_command_text
from deep_coder.tui.render import (
    render_diff_block,
    render_message_block,
    render_tool_call_block,
    render_tool_output,
    render_usage_block,
)
from deep_coder.tui.screens.command_palette import CommandPalette
from deep_coder.tui.screens.session_switcher import SessionSwitcher


class TimelineEvent(Message):
    def __init__(self, event: dict):
        self.event = event
        super().__init__()


class Composer(TextArea):
    async def _on_key(self, event) -> None:
        if event.key == "escape" and self.app.is_command_active:
            event.stop()
            event.prevent_default()
            self.app.action_cancel_command()
            return
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.app.action_submit_composer()
            return
        if event.key == "tab" and self.app.in_command_mode:
            event.stop()
            event.prevent_default()
            self.app.action_complete_command()
            return
        if event.key == "down" and self.app.in_command_mode:
            event.stop()
            event.prevent_default()
            self.app.action_move_command_selection(1)
            return
        if event.key == "up" and self.app.in_command_mode:
            event.stop()
            event.prevent_default()
            self.app.action_move_command_selection(-1)
            return
        if event.key == "shift+enter":
            event.stop()
            event.prevent_default()
            start, end = self.selection
            self._replace_via_keyboard("\n", start, end)
            return
        await super()._on_key(event)


class TimelineScroll(VerticalScroll):
    can_focus = True
    LINE_SCROLL_STEP = 4

    def action_scroll_down(self) -> None:
        self._prepare_fast_scroll()
        self.scroll_to(
            y=self.scroll_target_y + self.LINE_SCROLL_STEP,
            animate=False,
            immediate=True,
        )

    def action_scroll_up(self) -> None:
        self._prepare_fast_scroll()
        self.scroll_to(
            y=self.scroll_target_y - self.LINE_SCROLL_STEP,
            animate=False,
            immediate=True,
        )

    def _prepare_fast_scroll(self) -> None:
        # Keep behavior aligned with Textual internals across versions.
        if hasattr(self, "_user_scroll_interrupt"):
            self._user_scroll_interrupt = True
        clear_anchor = getattr(self, "_clear_anchor", None)
        if callable(clear_anchor):
            clear_anchor()
            return
        release_anchor = getattr(self, "release_anchor", None)
        if callable(release_anchor):
            release_anchor()


class StatusStrip(Static):
    _PULSE_STYLES = (
        "black on rgb(88,124,144)",
        "black on rgb(102,148,170)",
        "black on rgb(122,178,204)",
        "black on rgb(102,148,170)",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._project_name = ""
        self._session_id = "new"
        self._model_name = ""
        self._turn_state = "idle"
        self._command_feedback = ""
        self._pulse_index = 0
        self._pulse_timer = None

    def set_state(
        self,
        *,
        project_name: str,
        session_id: str | None,
        model_name: str,
        turn_state: str,
        command_feedback: str = "",
    ) -> None:
        self._project_name = project_name
        self._session_id = session_id or "new"
        self._model_name = model_name
        self._turn_state = turn_state
        self._command_feedback = command_feedback
        self._sync_busy_state()
        self.update(self._build_text())

    def _sync_busy_state(self) -> None:
        is_busy = self._turn_state == "running" or self._turn_state.startswith("tool:")
        self.set_class(is_busy, "busy")
        if is_busy:
            if self._pulse_timer is None:
                self._pulse_timer = self.set_interval(0.6, self._advance_pulse)
        else:
            self._pulse_index = 0
            if self._pulse_timer is not None:
                self._pulse_timer.stop()
                self._pulse_timer = None

    def _advance_pulse(self) -> None:
        if not self.has_class("busy"):
            return
        self._pulse_index = (self._pulse_index + 1) % len(self._PULSE_STYLES)
        self.update(self._build_text())

    def _build_text(self) -> Text:
        text = Text()
        text.append(self._project_name, style="bold white")
        text.append(" | ", style="dim")
        text.append(self._session_id, style="cyan")
        text.append(" | ", style="dim")
        text.append(self._model_name, style="magenta")
        text.append(" | ", style="dim")
        text.append(self._turn_state, style=self._turn_state_style())
        if self._command_feedback:
            text.append(" | ", style="dim")
            text.append(self._command_feedback, style="yellow")
        return text

    def _turn_state_style(self) -> str:
        if self.has_class("busy"):
            return self._PULSE_STYLES[self._pulse_index]
        return "bold white on rgb(58,58,58)"


class DeepCodeApp(App):
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("ctrl+l", "open_session_switcher", "Sessions"),
        Binding("ctrl+j", "focus_timeline", "Timeline"),
    ]

    def __init__(self, runtime, project):
        super().__init__()
        self.runtime = runtime
        self.project = project
        self.session_id = None
        self._timeline_blocks = []
        self._turn_state = "idle"
        self._command_feedback = ""
        self._command_registry = CommandRegistry.with_builtin_commands()

    def compose(self) -> ComposeResult:
        with TimelineScroll(id="timeline-scroll"):
            yield Static("", id="timeline")
        with Container(id="bottom-pane"):
            yield StatusStrip(id="status-strip")
            yield CommandPalette()
            yield Composer(id="composer")

    def on_mount(self) -> None:
        self.query_one("#composer", Composer).focus()
        self.query_one("#command-palette", CommandPalette).display = False
        self._update_status_strip()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "composer":
            self.action_refresh_command_palette()

    def on_key(self, event) -> None:
        if event.key != "escape":
            return
        timeline = self.query_one("#timeline-scroll", TimelineScroll)
        if self.focused is timeline:
            event.stop()
            event.prevent_default()
            self.set_focus(self.query_one("#composer", Composer))

    @property
    def in_command_mode(self) -> bool:
        if not self.is_mounted:
            return False
        return self.query_one("#composer", Composer).text.strip().startswith("/")

    @property
    def is_command_active(self) -> bool:
        if not self.is_mounted:
            return False
        palette = self.query_one("#command-palette", CommandPalette)
        return self.in_command_mode or bool(palette.display)

    def action_open_session_switcher(self) -> None:
        self.push_screen(SessionSwitcher(self._project_sessions()), self._on_session_selected)

    def action_focus_timeline(self) -> None:
        self.set_focus(self.query_one("#timeline-scroll", TimelineScroll))

    def action_submit_composer(self) -> None:
        composer = self.query_one("#composer", Composer)
        user_input = composer.text.rstrip("\n")
        if not user_input.strip():
            return
        if self.in_command_mode:
            outcome = self._resolve_command_submission(user_input)
            if outcome["action"] == "complete":
                composer.load_text(outcome["text"])
                self.action_refresh_command_palette()
                return
            self._run_command(outcome["text"])
            composer.load_text("")
            self.action_refresh_command_palette()
            return
        composer.load_text("")
        self._command_feedback = ""
        self._turn_state = "running"
        self._update_status_strip()
        self.run_turn(user_input)

    def action_refresh_command_palette(self) -> None:
        if not self.is_mounted:
            return
        try:
            composer = self.query_one("#composer", Composer)
            palette = self.query_one("#command-palette", CommandPalette)
        except NoMatches:
            return
        if not composer.text.strip().startswith("/"):
            palette.set_matches([])
            return
        matches = self._command_registry.match(
            composer.text,
            runtime=self.runtime,
            project=self.project,
            session_id=self.session_id,
            turn_state=self._turn_state,
        )
        palette.set_matches(matches)

    def action_complete_command(self) -> None:
        palette = self.query_one("#command-palette", CommandPalette)
        match = palette.current_match()
        if match is None:
            return
        composer = self.query_one("#composer", Composer)
        filled = match.command_text or f"/{match.name}"
        if match.kind == "command" and match.argument_hint:
            filled = f"{filled} "
        composer.load_text(filled)

    def action_move_command_selection(self, delta: int) -> None:
        palette = self.query_one("#command-palette", CommandPalette)
        if not palette.display or palette.option_count == 0:
            return
        current = palette.highlighted or 0
        palette.highlighted = (current + delta) % palette.option_count

    def action_cancel_command(self) -> None:
        composer = self.query_one("#composer", Composer)
        palette = self.query_one("#command-palette", CommandPalette)
        composer.load_text("")
        palette.set_matches([])
        self._command_feedback = ""
        self._update_status_strip()

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

    @work(thread=True)
    def run_turn(self, user_input: str) -> None:
        self.runtime["harness"].run(
            session_locator={"id": self.session_id} if self.session_id else None,
            user_input=user_input,
            event_sink=self,
        )

    def emit(self, event: dict) -> None:
        self.post_message(TimelineEvent(event))

    def on_timeline_event(self, message: TimelineEvent) -> None:
        event = message.event
        self.session_id = event.get("session_id", self.session_id)
        event_type = event["type"]
        if event_type == "turn_started":
            self._turn_state = "running"
        elif event_type == "tool_called":
            self._turn_state = f"tool:{event['name']}"
        elif event_type == "turn_finished":
            self._turn_state = "idle"

        follow_tail = self._timeline_is_at_end()
        self._append_event_block(event)
        self._refresh_timeline(follow_tail=follow_tail)
        self._update_status_strip()

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

    def _refresh_timeline(self, *, follow_tail: bool = False) -> None:
        self.query_one("#timeline", Static).update(self._compose_timeline_renderable())
        if follow_tail:
            self.query_one("#timeline-scroll", TimelineScroll).scroll_end(
                animate=False,
                x_axis=False,
            )

    def _timeline_is_at_end(self) -> bool:
        if not self.is_mounted:
            return False
        return self.query_one("#timeline-scroll", TimelineScroll).is_vertical_scroll_end

    def _update_status_strip(self) -> None:
        self.query_one("#status-strip", StatusStrip).set_state(
            project_name=self.project.name,
            session_id=self.session_id,
            model_name=self.runtime["config"].model_name,
            turn_state=self._turn_state,
            command_feedback=self._command_feedback,
        )

    def _run_command(self, command_text: str) -> None:
        result = self._command_registry.execute(
            command_text,
            runtime=self.runtime,
            project=self.project,
            session_id=self.session_id,
            turn_state=self._turn_state,
        )
        self._command_feedback = result.warning_message or result.status_message or ""
        if result.list_kind == "sessions":
            self.push_screen(SessionSwitcher(result.list_items), self._on_session_selected)
        if result.reset_session:
            self._reset_session_view()
        if result.should_exit:
            self.exit()
            return
        self._update_status_strip()

    def _resolve_command_submission(self, user_input: str) -> dict:
        palette = self.query_one("#command-palette", CommandPalette)
        match = palette.current_match() if palette.display else None
        if match is None:
            return {"action": "execute", "text": user_input}

        parsed = parse_command_text(user_input)
        if match.kind == "model":
            return {"action": "execute", "text": match.command_text or user_input}

        exact_command = parsed.name == match.name
        has_args = bool(parsed.args.strip())
        if match.argument_hint and not has_args:
            return {"action": "complete", "text": f"/{match.name} "}
        if not exact_command:
            return {"action": "execute", "text": match.command_text or f"/{match.name}"}
        return {"action": "execute", "text": user_input}

    def _reset_session_view(self) -> None:
        self.session_id = None
        self._timeline_blocks.clear()
        self._turn_state = "idle"
        self._refresh_timeline()
        self._update_status_strip()

    def _compose_timeline_renderable(self) -> RenderableType:
        if not self._timeline_blocks:
            return Text("")
        blocks: list[RenderableType] = []
        for index, block in enumerate(self._timeline_blocks):
            blocks.append(block)
            if index < len(self._timeline_blocks) - 1:
                blocks.append(Text(""))
        return Group(*blocks)
