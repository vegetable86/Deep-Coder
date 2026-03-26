from deep_coder.tui.commands.base import ParsedCommand


def parse_command_text(text: str) -> ParsedCommand:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return ParsedCommand(is_command=False)

    body = stripped[1:]
    if not body:
        return ParsedCommand(is_command=True)

    name, _, args = body.partition(" ")
    return ParsedCommand(
        is_command=True,
        name=name.strip(),
        args=args.strip(),
    )
