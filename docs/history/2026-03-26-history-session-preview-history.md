# History Session Preview History

Date: 2026-03-26
Branch: `feat/history-preview`

## Summary

This branch improves the project-scoped `/history` flow so users can choose sessions by reading a one-line preview of the session's opening user prompt instead of only seeing opaque session ids.

The implementation keeps the existing project/session boundaries intact. Session metadata now carries a stable `preview` field derived from the first user message, older stored sessions are backfilled from `messages.jsonl` during listing, and the TUI session switcher renders a readable single-line label while still selecting by the real session id.

The branch also fixes two usability regressions in the empty-history path:

- `/history` now still opens the selector when the project has no stored sessions
- the empty-state modal can be dismissed with `Escape`, returning focus to the composer

## Implementation Timeline

### 1. Improve `/history` session discovery and selection

Commit: `6043742` `feat: improve history session selector`

Implemented:

- derived session previews from the first user prompt and stored them in session metadata
- backfilled previews for older sessions that only had `messages.jsonl`
- rendered session switcher rows as `session-id  preview` with truncation
- preserved selection by raw session id instead of the rendered label text
- showed an explicit empty-state row when a project has no stored sessions
- added an `Escape` close path so the empty-state modal does not trap focus
- added regression coverage for preview persistence, old-session fallback, empty-history display, empty-history dismissal, and normal session selection

Edited files:

- `deep_coder/context/session.py`
- `deep_coder/context/stores/filesystem/store.py`
- `deep_coder/tui/app.py`
- `deep_coder/tui/screens/session_switcher.py`
- `tests/context/test_filesystem_store.py`
- `tests/tui/conftest.py`
- `tests/tui/test_app_layout.py`
- `tests/tui/test_commands.py`
- `tests/tui/test_session_switcher.py`

## Verification

- `/home/wys/deep-code/.venv/bin/pytest -q`
