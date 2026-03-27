import re

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text


def render_message_block(role: str, text: str) -> RenderableType:
    border_style = "cyan" if role == "user" else "rgb(90,90,90)"
    body = _render_markdown_lite(text)
    return Panel(
        body,
        border_style=border_style,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def render_tool_call_block(display_command: str) -> Text:
    return Text(display_command, style="yellow")


def render_tool_output(text: str, max_chars: int = 400) -> Text:
    if len(text) <= max_chars:
        return Text(text, style="dim")
    return Text(text[: max_chars - 3] + "...", style="dim")


def render_usage_block(usage: dict) -> Text:
    return Text(
        " | ".join(
            [
                f"prompt {usage.get('prompt_tokens', 0)}",
                f"usage {usage.get('total_tokens', 0)}",
                f"hit {usage.get('cache_hit_tokens', 0)}",
                f"miss {usage.get('cache_miss_tokens', 0)}",
            ]
        ),
        style="magenta",
    )


def render_task_snapshot_block(event: dict) -> RenderableType:
    marker_by_status = {
        "pending": "[ ]",
        "in_progress": "[>]",
        "completed": "[x]",
    }
    lines = []
    for task in event["tasks"]:
        marker = marker_by_status.get(task["status"], "[?]")
        lines.append(f"{marker} #{task['id']}: {task['subject']}")
    lines.append(f"({event['completed_count']}/{event['total_count']} completed)")
    return Panel(
        Text("\n".join(lines)),
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
    )


def render_turn_interrupted_block(event: dict) -> RenderableType:
    reason = event.get("reason", "user_interrupt").replace("_", " ")
    return Panel(
        Text(f"Turn interrupted: {reason}", style="bold yellow"),
        border_style="yellow",
        box=box.ROUNDED,
        padding=(0, 1),
    )


def render_context_compaction_block(event: dict) -> RenderableType:
    if event["type"] == "context_compacting":
        text = Text("Compacting context...", style="bold yellow")
        border_style = "yellow"
    else:
        text = Text("Context compacted", style="bold cyan")
        border_style = "cyan"
    return Panel(
        text,
        border_style=border_style,
        box=box.ROUNDED,
        padding=(0, 1),
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


def _render_markdown_lite(text: str) -> RenderableType:
    lines = text.splitlines()
    blocks: list[RenderableType] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        heading = _parse_heading(line)
        if heading is not None:
            level, title = heading
            blocks.append(_render_heading(level, title))
            index += 1
            continue

        if line.startswith("```"):
            language = line[3:].strip()
            index += 1
            code_lines: list[str] = []
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines) and lines[index].startswith("```"):
                index += 1
            blocks.append(_render_code_block(language, "\n".join(code_lines)))
            continue

        if _is_quote_line(line):
            quote_lines: list[str] = []
            while index < len(lines) and _is_quote_line(lines[index]):
                quote_lines.append(_strip_quote(lines[index]))
                index += 1
            blocks.append(_render_quote_block(quote_lines))
            continue

        if _is_bullet_line(line):
            items: list[str] = []
            while index < len(lines) and _is_bullet_line(lines[index]):
                items.append(_strip_bullet(lines[index]))
                index += 1
            blocks.append(_render_list_block(items))
            continue

        paragraph_lines = [line.strip()]
        index += 1
        while index < len(lines):
            next_line = lines[index]
            if not next_line.strip() or _starts_special_block(next_line):
                break
            paragraph_lines.append(next_line.strip())
            index += 1
        blocks.append(_render_paragraph(paragraph_lines))

    if not blocks:
        return Text("")
    if len(blocks) == 1:
        return blocks[0]
    return Group(*_with_spacing(blocks))


def _render_code_block(language: str, code: str) -> RenderableType:
    code_text = Text(code or " ", style="rgb(230,230,230) on rgb(28,28,28)")
    title = language or None
    return Panel(
        code_text,
        title=title,
        border_style="rgb(70,70,70)",
        box=box.SQUARE,
        padding=(0, 1),
    )


def _render_quote_block(lines: list[str]) -> Text:
    quote = Text()
    for index, line in enumerate(lines):
        if index:
            quote.append("\n")
        quote.append("▎ ", style="bold rgb(120,120,120)")
        quote.append_text(_render_inline(line, base_style="italic dim"))
    return quote


def _render_list_block(items: list[str]) -> Text:
    bullet_list = Text()
    for index, item in enumerate(items):
        if index:
            bullet_list.append("\n")
        bullet_list.append("• ", style="bold cyan")
        bullet_list.append_text(_render_inline(item))
    return bullet_list


def _render_paragraph(lines: list[str]) -> Text:
    paragraph = Text()
    for index, line in enumerate(lines):
        if index:
            paragraph.append("\n")
        paragraph.append_text(_render_inline(line))
    return paragraph


def _render_heading(level: int, title: str) -> Text:
    styles = {
        1: "bold underline white",
        2: "bold white",
        3: "bold rgb(220,220,220)",
        4: "bold rgb(200,200,200)",
        5: "bold dim",
        6: "dim",
    }
    return Text(title, style=styles.get(level, "bold"))


def _render_inline(source: str, base_style: str = "") -> Text:
    text = Text()
    index = 0

    while index < len(source):
        if source.startswith("`", index):
            end = source.find("`", index + 1)
            if end != -1:
                text.append(
                    source[index + 1 : end],
                    style=_merge_styles(base_style, "bold black on rgb(200,200,200)"),
                )
                index = end + 1
                continue

        if source.startswith("**", index):
            end = source.find("**", index + 2)
            if end != -1:
                text.append_text(
                    _render_inline(
                        source[index + 2 : end],
                        base_style=_merge_styles(base_style, "bold"),
                    )
                )
                index = end + 2
                continue

        if source[index] in {"*", "_"}:
            marker = source[index]
            end = source.find(marker, index + 1)
            if end != -1:
                text.append_text(
                    _render_inline(
                        source[index + 1 : end],
                        base_style=_merge_styles(base_style, "italic"),
                    )
                )
                index = end + 1
                continue

        text.append(source[index], style=base_style or None)
        index += 1

    if base_style:
        text.stylize(base_style)
    return text


def _with_spacing(blocks: list[RenderableType]) -> list[RenderableType]:
    spaced: list[RenderableType] = []
    for index, block in enumerate(blocks):
        spaced.append(block)
        if index < len(blocks) - 1:
            spaced.append(Text(""))
    return spaced


def _starts_special_block(line: str) -> bool:
    return (
        line.startswith("```")
        or _is_quote_line(line)
        or _is_bullet_line(line)
        or _parse_heading(line) is not None
    )


def _is_quote_line(line: str) -> bool:
    return bool(re.match(r"^\s*>\s?", line))


def _strip_quote(line: str) -> str:
    return re.sub(r"^\s*>\s?", "", line)


def _is_bullet_line(line: str) -> bool:
    return bool(re.match(r"^\s*[-*]\s+", line))


def _strip_bullet(line: str) -> str:
    return re.sub(r"^\s*[-*]\s+", "", line)


def _parse_heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
    if match is None:
        return None
    return len(match.group(1)), match.group(2)


def _merge_styles(*styles: str) -> str:
    return " ".join(style for style in styles if style)
