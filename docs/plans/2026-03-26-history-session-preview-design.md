# History Session Preview Design

## Goal

Make `/history` show a readable one-line preview for each project session so users can choose a session by its opening prompt instead of only by the session id.

## Scope

- Keep `/history` project-scoped.
- Use the first user message in the session as the preview source.
- Show the preview on the same line as the session id.
- Preserve current session loading and replay behavior.

## Approach

Add a stable `preview` field to session metadata. For new or updated sessions, derive that preview from the first user message and persist it in `meta.json`. For older sessions that do not have a `preview`, the filesystem store should derive it from `messages.jsonl` during `list_sessions()` so existing history immediately becomes readable without a migration.

The TUI should keep using the same `/history` command boundary. `SessionSwitcher` should render one line per session with the id and normalized preview text, while still dismissing with the raw session id.

## Data Rules

- Preview source: first message where `role == "user"` and `content` is a non-empty string.
- Normalize to one line by collapsing whitespace.
- Truncate long previews for display.
- If no user message exists, fall back to the session id only.

## Files

- `deep_coder/context/session.py`
- `deep_coder/context/stores/filesystem/store.py`
- `deep_coder/tui/screens/session_switcher.py`
- `tests/context/test_filesystem_store.py`
- `tests/tui/test_session_switcher.py`
- `tests/tui/test_commands.py`
- `tests/tui/conftest.py`

## Verification

- Targeted context and TUI tests for preview persistence, fallback extraction, and rendered labels.
- Full test suite after implementation.
