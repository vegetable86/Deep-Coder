from deep_coder.tui.commands.base import CommandBase, CommandResult


class ExitCommand(CommandBase):
    name = "exit"
    summary = "Close the TUI"

    def execute(self, context, args: str) -> CommandResult:
        return CommandResult(should_exit=True)
