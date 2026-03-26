# History Session Preview Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `/history` show each session id together with a one-line preview derived from the session's opening user prompt.

**Architecture:** Extend session metadata with a persisted `preview` field and teach the filesystem store to backfill that field from stored messages when older sessions do not have it. Keep `/history` as a thin command that returns project sessions, and update the session switcher to render readable labels while still selecting by session id.

**Tech Stack:** Python, Textual, pytest

---

### Task 1: Persist session previews in metadata

**Files:**
- Modify: `deep_coder/context/session.py`
- Modify: `deep_coder/context/stores/filesystem/store.py`
- Test: `tests/context/test_filesystem_store.py`

**Step 1: Write the failing test**

Add a context-store test that saves a session with a first user message and expects `list_sessions()` plus reopened metadata to include a normalized preview.

**Step 2: Run test to verify it fails**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/context/test_filesystem_store.py::test_filesystem_store_lists_session_preview_from_first_user_message`
Expected: FAIL because `preview` is not persisted or listed yet.

**Step 3: Write minimal implementation**

Add preview derivation to `Session.meta()` and add a fallback extractor in the filesystem store for old sessions that have no stored preview.

**Step 4: Run test to verify it passes**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/context/test_filesystem_store.py::test_filesystem_store_lists_session_preview_from_first_user_message`
Expected: PASS.

### Task 2: Render readable `/history` labels

**Files:**
- Modify: `deep_coder/tui/screens/session_switcher.py`
- Modify: `tests/tui/conftest.py`
- Modify: `tests/tui/test_session_switcher.py`
- Modify: `tests/tui/test_commands.py`

**Step 1: Write the failing test**

Update the TUI history test to expect labels that include the session id and preview on one line, and ensure command results expose the preview field.

**Step 2: Run test to verify it fails**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tui/test_session_switcher.py::test_history_command_opens_project_session_list tests/tui/test_commands.py::test_history_command_returns_only_active_project_sessions`
Expected: FAIL because the switcher currently renders only the session id.

**Step 3: Write minimal implementation**

Render each option label as `"<id>  <preview>"` with truncation and keep dismissal based on the originating session record instead of the rendered label text.

**Step 4: Run test to verify it passes**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tui/test_session_switcher.py::test_history_command_opens_project_session_list tests/tui/test_commands.py::test_history_command_returns_only_active_project_sessions`
Expected: PASS.

### Task 3: Verify old-session fallback and full suite

**Files:**
- Modify: `tests/context/test_filesystem_store.py`

**Step 1: Write the failing test**

Add a store test covering an older session whose `meta.json` lacks `preview` but whose `messages.jsonl` contains a first user prompt.

**Step 2: Run test to verify it fails**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/context/test_filesystem_store.py::test_filesystem_store_backfills_preview_for_existing_session_metadata`
Expected: FAIL because old-session fallback is not implemented yet.

**Step 3: Write minimal implementation**

Keep or refine the filesystem-store fallback so list results include the derived preview without rewriting old files during listing.

**Step 4: Run test to verify it passes**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/context/test_filesystem_store.py::test_filesystem_store_backfills_preview_for_existing_session_metadata`
Expected: PASS.

### Task 4: Final verification

**Files:**
- Modify: none

**Step 1: Run targeted tests**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/context/test_filesystem_store.py tests/tui/test_session_switcher.py tests/tui/test_commands.py`
Expected: PASS.

**Step 2: Run the full suite**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`
Expected: PASS.
