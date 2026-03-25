import re

from rich.text import Text


def render_message_block(role: str, text: str) -> Text:
    style = "black on cyan" if role == "user" else "white on rgb(40,40,40)"
    return Text(text, style=style)


def render_tool_call_block(display_command: str) -> Text:
    return Text(display_command, style="yellow")


def render_tool_output(text: str, max_chars: int = 400) -> Text:
    if len(text) <= max_chars:
        return Text(text, style="dim")
    return Text(text[: max_chars - 3] + "...", style="dim")


def render_usage_block(usage: dict) -> Text:
    return Text(
        "\n".join(
            [
                f"prompt_tokens: {usage.get('prompt_tokens', 0)}",
                f"completion_tokens: {usage.get('completion_tokens', 0)}",
                f"total_tokens: {usage.get('total_tokens', 0)}",
                f"cache_hit_tokens: {usage.get('cache_hit_tokens', 0)}",
                f"cache_miss_tokens: {usage.get('cache_miss_tokens', 0)}",
            ]
        ),
        style="magenta",
    )


def render_diff_block(path: str, diff_text: str) -> Text:
    block = Text(f"{path}\n", style="bold")
    old_line = None
    new_line = None

    for line in diff_text.splitlines():
        if line.startswith(("--- ", "+++ ")):
            continue
        if line.startswith("@@"):
            match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if match:
                old_line = int(match.group(1))
                new_line = int(match.group(2))
            block.append(f"{line}\n", style="bold")
            continue
        if line.startswith("\\"):
            block.append(f"{line}\n", style="dim")
            continue

        if old_line is None or new_line is None:
            block.append(f"{line}\n")
            continue

        if line.startswith("-"):
            block.append(f"{old_line:>4} {'':>4} {line}\n", style="black on red")
            old_line += 1
            continue
        if line.startswith("+"):
            block.append(f"{'':>4} {new_line:>4} {line}\n", style="black on green")
            new_line += 1
            continue

        block.append(f"{old_line:>4} {new_line:>4} {line}\n", style="dim")
        old_line += 1
        new_line += 1

    return block
