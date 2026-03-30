# TUI Status Strip Spinner Animation Design

**Date:** 2026-03-30
**Status:** Approved

## Problem

The `StatusStrip` in `deep_coder/tui/app.py` uses a 4-step color-cycling pulse animation (600ms interval) to indicate busy state. The coarse stepping makes it feel jerky rather than smooth. Users also expect a visible "thinking" indicator when the `think` tool is running — the status strip already shows `tool:think` but the animation quality undermines the signal.

## Goal

Replace the stepped color pulse with a braille spinner that cycles smoothly at ~12fps. No timeline widget changes needed — the status strip alone is sufficient.

## Design

### Changes to `StatusStrip` in `deep_coder/tui/app.py`

**Remove:**
- `_PULSE_STYLES` tuple (4 hardcoded Rich background-color style strings)
- `_pulse_index: int` instance variable
- `_advance_pulse` method
- `set_interval(0.6, self._advance_pulse)` call in `_sync_busy_state`

**Add:**
- `_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")`
- `_spinner_index: int = 0` instance variable
- `_advance_spinner` method: increments `_spinner_index % 10`, calls `self.refresh()`
- `set_interval(0.08, self._advance_spinner)` in `_sync_busy_state` (80ms interval, ~12fps)

**Render change:**
When busy, prepend the current spinner frame to the turn state label:

```python
frame = self._SPINNER_FRAMES[self._spinner_index]
label = f"{frame} {turn_state}"
```

No background color change. When not busy, reset `_spinner_index = 0` and stop the timer as before.

### No other changes

- `_sync_busy_state` logic (start/stop timer on state transitions) is unchanged
- No new event types
- No timeline widget changes
- No CSS changes

## Scope

Single file: `deep_coder/tui/app.py` — `StatusStrip` class only.
