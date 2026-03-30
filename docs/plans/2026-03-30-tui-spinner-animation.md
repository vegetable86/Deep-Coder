# TUI Spinner Animation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the status-strip pulse animation with a smooth braille spinner exactly as defined in the approved spinner animation spec.

**Architecture:** Keep the change isolated to `StatusStrip` in `deep_coder/tui/app.py`. Add TUI tests that assert the busy indicator shows a spinner-prefixed label, that spinner ticks advance the frame while busy, and that the widget resets to the plain idle label when no longer busy.

**Tech Stack:** Python, Textual, pytest

---

### Task 1: Lock in spinner behavior with tests

**Files:**
- Modify: `tests/tui/test_app_layout.py`
- Modify: `deep_coder/tui/app.py`

**Step 1: Write the failing test**

Add focused tests that:
- set the app turn state to `running` and assert the status strip text includes the first braille spinner frame before `running`
- call the status-strip animation tick and assert the next frame is rendered while still busy
- return the app to `idle` and assert the label no longer contains a spinner and the index resets

**Step 2: Run test to verify it fails**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tui/test_app_layout.py -k spinner`
Expected: FAIL because `StatusStrip` still uses `_PULSE_STYLES` and does not render braille spinner frames.

**Step 3: Write minimal implementation**

In `deep_coder/tui/app.py`:
- replace pulse styles and pulse index with spinner frames and spinner index
- replace `_advance_pulse` with `_advance_spinner`
- keep busy start/stop logic intact while swapping the interval to `0.08`
- prepend the active spinner frame to the busy turn-state label
- reset the spinner index when leaving busy state

**Step 4: Run test to verify it passes**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tui/test_app_layout.py -k spinner`
Expected: PASS

**Step 5: Run broader verification**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tui/test_app_layout.py tests/tui/test_live_events.py`
Expected: PASS

**Step 6: Run full verification**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`
Expected: PASS
