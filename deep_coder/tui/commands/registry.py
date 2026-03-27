from types import SimpleNamespace

from deep_coder.tui.commands.base import CommandContext, CommandResult, RUNTIME_BUSY_WARNING
from deep_coder.tui.commands.builtin.exit import ExitCommand
from deep_coder.tui.commands.builtin.history import HistoryCommand
from deep_coder.tui.commands.builtin.model import ModelCommand
from deep_coder.tui.commands.builtin.session import SessionCommand
from deep_coder.tui.commands.builtin.skills import SkillsCommand
from deep_coder.tui.commands.parser import parse_command_text


class CommandRegistry:
    def __init__(self, commands):
        self._commands = list(commands)

    @classmethod
    def with_builtin_commands(cls):
        return cls(
            [ModelCommand(), HistoryCommand(), SessionCommand(), SkillsCommand(), ExitCommand()]
        )

    def match(self, composer_text: str, **context_kwargs) -> list:
        parsed = parse_command_text(composer_text)
        if not parsed.is_command:
            return []

        context = self._context_from_kwargs(**context_kwargs)
        command = self._find_command(parsed.name) if parsed.name else None
        if command is not None:
            completions = command.complete(context, parsed.args)
            if completions is not None:
                return completions

        query = parsed.name
        matches = [
            command.to_match(context)
            for command in self._commands
            if command.match(query)
        ]
        return sorted(matches, key=lambda match: match.name)

    def execute(self, composer_text: str, **context_kwargs) -> CommandResult:
        parsed = parse_command_text(composer_text)
        if not parsed.is_command or not parsed.name:
            return CommandResult(warning_message="unknown command")

        context = self._context_from_kwargs(**context_kwargs)
        command = self._find_command(parsed.name)
        if command is None:
            return CommandResult(warning_message="unknown command")

        is_available, disabled_reason = command.availability(context)
        if not is_available:
            return CommandResult(warning_message=disabled_reason or RUNTIME_BUSY_WARNING)
        return command.execute(context, parsed.args)

    def _find_command(self, name: str):
        for command in self._commands:
            if command.name == name or name in command.aliases:
                return command
        return None

    @staticmethod
    def _context_from_kwargs(**context_kwargs) -> CommandContext:
        return CommandContext(
            runtime=context_kwargs.get("runtime", {}),
            project=context_kwargs.get("project", SimpleNamespace(key=None)),
            session_id=context_kwargs.get("session_id"),
            turn_state=context_kwargs.get("turn_state", "idle"),
        )
