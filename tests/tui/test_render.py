from deep_coder.tui.render import (
    render_diff_block,
    render_message_block,
    render_tool_output,
)


def test_message_blocks_do_not_render_speaker_labels():
    user = render_message_block(role="user", text="make dir aa")
    assistant = render_message_block(role="assistant", text="done")

    assert "User Message" not in user.plain
    assert "Assistant" not in assistant.plain


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
