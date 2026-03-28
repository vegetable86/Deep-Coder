from deep_coder.projects.deepfile import DeepFileService
from deep_coder.tui.commands.base import CommandBase, CommandResult


class InitCommand(CommandBase):
    name = "init"
    summary = "Generate or refresh DEEP.md for this workspace"

    def execute(self, context, args: str) -> CommandResult:
        service = DeepFileService(
            workspace=context.project.path,
            state_dir=context.project.state_dir,
        )
        try:
            service.refresh()
        except Exception as exc:
            return CommandResult(warning_message=f"failed to refresh DEEP.md: {exc}")
        return CommandResult(status_message="DEEP.md refreshed")