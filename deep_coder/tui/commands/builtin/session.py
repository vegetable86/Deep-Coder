from deep_coder.tui.commands.base import CommandBase, CommandResult


class SessionCommand(CommandBase):
    name = "session"
    summary = "Start a new empty session"

    def execute(self, context, args: str) -> CommandResult:
        return CommandResult(status_message="new session", reset_session=True)
