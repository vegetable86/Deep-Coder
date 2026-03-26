# TUI Markdown-Lite Status History

Date: 2026-03-26
Branch: `feat/tui-markdown-lite-status`
Merged into: `master` via `b64007b`

## Summary

This branch improves the project-scoped TUI so model output is rendered as markdown-lite instead of raw markdown text, the busy status strip has a pulsing animation, and keyboard-only timeline navigation is practical after mouse capture is disabled in the real launcher path.

The merged UI behavior now includes:

- markdown-lite rendering for message blocks, including headings, bullets, blockquotes, inline code, and fenced code blocks
- preserved low-cost rendering for tool calls, tool output, usage rows, and diffs
- a pulsing busy state in the bottom status strip while the agent is `running` or inside `tool:<name>`
- explicit keyboard focus handoff from the composer to the timeline and back
- faster `Up` and `Down` scrolling when the timeline has focus
- `deepcode` launch behavior that disables Textual mouse capture so the terminal can handle normal drag-to-select text copying

The branch also added the design and implementation plan history for both the markdown/status slice and the keyboard-scroll/selection slice under `docs/plans/`.

## Implementation Timeline

### 1. Capture the design and execution plans

Commits:

- `9043395` `docs: add tui markdown-lite design and plan`
- `5b0ecb0` `docs: add keyboard scroll and selection plan`

Implemented:

- approved design doc and implementation plan for markdown-lite message rendering plus busy-status animation
- approved design doc and implementation plan for keyboard timeline focus, faster scrolling, and terminal text selection

Edited files:

- `docs/plans/2026-03-26-tui-markdown-lite-status-design.md`
- `docs/plans/2026-03-26-tui-markdown-lite-status.md`
- `docs/plans/2026-03-26-tui-keyboard-scroll-selection-design.md`
- `docs/plans/2026-03-26-tui-keyboard-scroll-selection.md`

### 2. Render markdown-lite message blocks and pulse busy status

Commit: `bd6b3c6` `feat: render markdown-lite messages and pulse status`

Implemented:

- switched message blocks from flat `Text` output to richer Rich renderables
- added markdown-lite parsing for paragraphs, bullets, blockquotes, inline code, and fenced code blocks
- introduced a dedicated `StatusStrip` widget with a breathing pulse while the harness is busy
- updated TUI test helpers to render nested Rich/Textual output correctly
- added regression coverage for markdown-lite rendering and busy-status behavior

Edited files:

- `deep_coder/tui/app.py`
- `deep_coder/tui/render.py`
- `tests/tui/conftest.py`
- `tests/tui/test_app_layout.py`
- `tests/tui/test_live_events.py`
- `tests/tui/test_render.py`

### 3. Add heading rendering and explicit timeline focus flow

Commit: `f6fdb1a` `feat: add heading render and timeline focus flow`

Implemented:

- heading parsing for `#` through `######` in markdown-lite output
- timeline focus action on `ctrl+j`
- `Escape` return path from focused timeline back to the composer
- coverage for heading rendering, focus transfer, and focus return behavior

Edited files:

- `deep_coder/tui/app.py`
- `deep_coder/tui/render.py`
- `tests/tui/test_app_layout.py`
- `tests/tui/test_render.py`

### 4. Speed up focused timeline arrow scrolling

Commits:

- `acf4d14` `feat: speed up focused timeline arrow scrolling`
- `a5b88dc` `fix: preserve timeline scroll action semantics`

Implemented:

- multi-line `Up` and `Down` scrolling for the focused timeline
- preserved Textual scroll-side effects such as user-scroll interruption and anchor clearing before fast scrolling
- regression coverage for accelerated `Down` and `Up` behavior on the focused timeline

Edited files:

- `deep_coder/tui/app.py`
- `tests/tui/test_live_events.py`

### 5. Disable mouse capture in the real launcher path

Commit: `b64007b` `fix: disable mouse in cli launch`

Implemented:

- updated the CLI launch path to run the TUI with `mouse=False`
- added a CLI regression test proving `main()` passes `mouse=False` into `DeepCodeApp.run()`

Edited files:

- `deep_coder/cli.py`
- `tests/test_cli.py`

## Current User-Facing Shape

Main modules changed by this branch:

- `deep_coder/cli.py`
- `deep_coder/tui/app.py`
- `deep_coder/tui/render.py`

Main test coverage added or expanded by this branch:

- `tests/test_cli.py`
- `tests/tui/conftest.py`
- `tests/tui/test_app_layout.py`
- `tests/tui/test_live_events.py`
- `tests/tui/test_render.py`

## Verification Snapshot

Latest verification after merge on `master`:

- command: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_render.py tests/tui/test_app_layout.py tests/tui/test_live_events.py tests/test_cli.py`
- result: `29 passed in 5.06s`
- command: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui`
- result: `39 passed in 5.24s`
- command: `/home/wys/Deep-Coder/.venv/bin/pytest -q`
- result: `69 passed in 7.02s`
