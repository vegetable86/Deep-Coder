from abc import ABC, abstractmethod
from dataclasses import dataclass, field


RUNTIME_BUSY_WARNING = "system now in runtime, please wait for the work end"


@dataclass(frozen=True)
class ParsedCommand:
    is_command: bool
    name: str = ""
    args: str = ""


@dataclass(frozen=True)
class CommandContext:
    runtime: dict
    project: object
    session_id: str | None
    turn_state: str


@dataclass(frozen=True)
class CommandMatch:
    name: str
    summary: str
    argument_hint: str = ""
    is_available: bool = True
    disabled_reason: str | None = None
    label: str | None = None
    command_text: str | None = None
    kind: str = "command"


@dataclass
class CommandResult:
    status_message: str | None = None
    warning_message: str | None = None
    list_items: list[dict] = field(default_factory=list)
    list_kind: str | None = None
    reset_session: bool = False
    selected_session_id: str | None = None
    updated_model_name: str | None = None
    should_exit: bool = False
    timeline_events: list[dict] = field(default_factory=list)


class CommandBase(ABC):
    name = ""
    summary = ""
    argument_hint = ""
    aliases: tuple[str, ...] = ()
    requires_idle = True

    def match(self, query: str) -> bool:
        return self.name.startswith(query) or any(alias.startswith(query) for alias in self.aliases)

    def availability(self, context: CommandContext) -> tuple[bool, str | None]:
        if self.requires_idle and context.turn_state != "idle":
            return False, RUNTIME_BUSY_WARNING
        return True, None

    def complete(self, context: CommandContext, args: str) -> list[CommandMatch] | None:
        return None

    def to_match(self, context: CommandContext) -> CommandMatch:
        is_available, disabled_reason = self.availability(context)
        return CommandMatch(
            name=self.name,
            summary=self.summary,
            argument_hint=self.argument_hint,
            is_available=is_available,
            disabled_reason=disabled_reason,
            label=f"/{self.name}",
            command_text=f"/{self.name}",
        )

    @abstractmethod
    def execute(self, context: CommandContext, args: str) -> CommandResult:
        raise NotImplementedError
