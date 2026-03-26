# Timeline Auto Scroll Fix History

Date: 2026-03-26
Branch: `fix/timeline-auto-scroll`

## Summary

This branch fixes the TUI timeline behavior when live events append new content while the viewport is already sitting at the bottom of the scroll region.

The failing path refreshed the `#timeline` widget but never advanced `#timeline-scroll` to the new `max_scroll_y`. As a result, the timeline stayed stuck on the old bottom position and stopped following live output until the user scrolled again.

The implemented fix records whether the timeline is already at the end before appending a new event and only re-applies `scroll_end()` in that case. That preserves the expected "follow live output" behavior without forcing users back to the bottom if they intentionally scrolled upward.

## Implementation Timeline

### 1. Keep the timeline pinned only when the user is already at the end

Commit: `7d97599` `fix: keep timeline pinned at scroll end`

Implemented:

- captured the pre-update tail-follow state from `#timeline-scroll`
- refreshed the timeline with an optional follow-tail path that calls `scroll_end()` after new content is rendered
- kept the behavior conditional so manual upward scrolling is respected
- added a regression test for the pinned-at-bottom case
- added a regression test for the user-scrolled-up case

Edited files:

- `deep_coder/tui/app.py`
- `tests/tui/test_live_events.py`

## Verification

- `/home/wys/deep-code/.venv/bin/pytest -q`
