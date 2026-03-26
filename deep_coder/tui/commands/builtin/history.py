from deep_coder.tui.commands.base import CommandBase, CommandResult


class HistoryCommand(CommandBase):
    name = "history"
    summary = "Show stored sessions for this project"

    def execute(self, context, args: str) -> CommandResult:
        sessions = [
            session
            for session in context.runtime["context"].list_sessions()
            if session.get("project_key") == context.project.key
        ]
        return CommandResult(list_items=sessions, list_kind="sessions")
