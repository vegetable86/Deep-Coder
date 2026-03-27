from deep_coder.tui.render import (
    render_diff_block,
    render_message_block,
    render_task_snapshot_block,
    render_turn_interrupted_block,
    render_tool_output,
    render_usage_block,
)
from tests.tui.conftest import render_plain_text


def test_message_blocks_do_not_render_speaker_labels():
    user = render_message_block(role="user", text="make dir aa")
    assistant = render_message_block(role="assistant", text="done")

    assert "User Message" not in render_plain_text(user)
    assert "Assistant" not in render_plain_text(assistant)


def test_message_blocks_render_markdown_lite_without_raw_markers():
    block = render_message_block(
        role="assistant",
        text="**bold** `code`\n- item\n> quote\n```py\nprint('x')\n```",
    )

    rendered = render_plain_text(block)

    assert "bold" in rendered
    assert "code" in rendered
    assert "item" in rendered
    assert "quote" in rendered
    assert "print('x')" in rendered
    assert "```" not in rendered


def test_message_blocks_render_headings_without_raw_hashes():
    block = render_message_block(role="assistant", text="### Title\nbody")
    rendered = render_plain_text(block)

    assert "Title" in rendered
    assert "###" not in rendered


def test_tool_output_truncates_long_plain_output():
    block = render_tool_output("x" * 600, max_chars=40)
    assert block.plain.endswith("...")


def test_diff_block_keeps_all_changed_hunks_with_line_numbers():
    diff = """--- a/notes.txt
+++ b/notes.txt
@@ -1,2 +1,2 @@
-hello world
+hello runtime
 keep
"""
    block = render_diff_block(path="notes.txt", diff_text=diff)

    assert "notes.txt" in block.plain
    assert "1" in block.plain
    assert "hello runtime" in block.plain


def test_usage_block_renders_on_one_line():
    block = render_usage_block(
        {
            "prompt_tokens": 10,
            "total_tokens": 15,
            "cache_hit_tokens": 3,
            "cache_miss_tokens": 7,
        }
    )

    assert block.plain == "prompt 10 | usage 15 | hit 3 | miss 7"


def test_render_task_snapshot_block_shows_status_markers_and_progress():
    block = render_task_snapshot_block(
        {
            "tasks": [
                {
                    "id": 1,
                    "subject": "inspect repo",
                    "status": "completed",
                    "blocked_by": [],
                    "blocks": [2],
                },
                {
                    "id": 2,
                    "subject": "edit app",
                    "status": "pending",
                    "blocked_by": [1],
                    "blocks": [],
                },
            ],
            "completed_count": 1,
            "total_count": 2,
        }
    )

    text = render_plain_text(block)
    assert "[x] #1: inspect repo" in text
    assert "[ ] #2: edit app" in text
    assert "(1/2 completed)" in text


def test_render_turn_interrupted_block():
    block = render_turn_interrupted_block({"reason": "user_interrupt"})

    assert "interrupted" in render_plain_text(block).lower()
