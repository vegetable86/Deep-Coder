# TUI Keyboard Scroll And Terminal Selection Design

**Date:** 2026-03-26

## Goal

Restore normal terminal drag-to-select behavior by disabling Textual mouse capture, while keeping the timeline fast to navigate with the keyboard and extending markdown-lite to style headings.

## Approved Behavior

- The launched terminal app should run with mouse support disabled so the terminal can handle text selection and copy normally.
- The composer remains the default focus target on startup.
- Users can switch focus to the timeline with a keyboard action.
- When the timeline has focus:
  - `Up` and `Down` should scroll faster than the Textual default
  - `PageUp`, `PageDown`, `Home`, and `End` keep their existing scroll semantics
- `Escape` should return focus from the timeline back to the composer.
- Markdown-lite should style heading lines such as `#`, `##`, and `###` instead of showing the raw heading markers.

## Design

### Launch Behavior

Update the checked-in launcher flow to run the Textual app with `mouse=False`.

That change should be limited to the real CLI path so tests can continue to use `run_test(...)` without changing their harness.

### Focus Model

Add a dedicated keyboard action on `DeepCodeApp` to focus the timeline scroll view.

Recommended interaction:

- `ctrl+j` focuses the timeline
- `escape` returns focus to the composer when the timeline is focused

This avoids conflicting with existing slash-command usage and keeps the focus model explicit when the mouse is disabled.

### Faster Timeline Scrolling

Wrap the current `VerticalScroll` in a small subclass that overrides the line-scroll actions.

The subclass should keep Textual's built-in page and edge bindings, but replace one-line `Up` / `Down` behavior with multi-line jumps, for example 4 lines per press. This preserves familiar keys while making keyboard-only navigation practical.

### Markdown Headings

Extend the existing markdown-lite parser in `deep_coder/tui/render.py` with a heading rule.

Supported heading lines should:

- strip the raw `#` markers
- style the text with stronger emphasis based on depth
- remain cheap renderables consistent with the current markdown-lite strategy

## Testing Strategy

Add or update tests for:

- heading lines rendering without raw `#` markers
- timeline focus action moving focus from composer to timeline
- `Escape` returning focus to the composer
- timeline `Up` / `Down` moving by more than one line per keypress
- CLI launching the app with `mouse=False`
