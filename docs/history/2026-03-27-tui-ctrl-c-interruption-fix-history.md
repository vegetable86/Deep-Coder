# TUI Ctrl-C Interruption Fix History

Date: 2026-03-27
Branch: `fix/ctrl-c-sigint`

## Summary

This branch fixes the TUI interruption flow when the user presses `Ctrl+C` in a real terminal session while a turn is running.

The earlier conversation-interruption work already stopped the active turn subprocess correctly once `interrupt_turn` executed, and the existing tests covered that internal action path. The remaining gap was input delivery: in some live terminal sessions `Ctrl+C` did not reliably arrive as the app-level binding while focus stayed inside the composer `TextArea`, so the turn kept running and nothing visible happened.

The implemented fix keeps the existing interruption behavior but closes the terminal-input gap in two ways:

- it promotes the app-level `Ctrl+C` interrupt binding so it wins before focused widget bindings while a turn is active
- it adds a SIGINT fallback inside the TUI so terminals that still deliver `Ctrl+C` as a signal are bridged back into the same interruption flow

Idle `Ctrl+C` is still treated as a non-interrupt path and falls through to Textual's existing quit-help behavior instead of fabricating a fake interruption.

## Implementation Timeline

### 1. Bridge terminal `Ctrl+C` into the existing interruption flow

Commit: `9479bce` `fix: handle terminal ctrl-c interruption`

Implemented:

- promoted `ctrl+c` to a priority app binding for the interrupt action
- changed idle `interrupt_turn` attempts to raise `SkipAction` so non-busy fallback behavior can proceed
- installed and restored a TUI-local SIGINT handler on mount and unmount
- converted pending SIGINTs into the same `interrupt_turn` path on the next UI tick
- added a regression test covering the SIGINT-driven interruption path

Edited files:

- `deep_coder/tui/app.py`
- `tests/tui/test_live_events.py`

## Verification

- `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/tui/test_app_layout.py tests/tui/test_live_events.py tests/tui/test_render.py tests/harness/test_turn_subprocess.py`
- `/home/wys/Deep-Coder/.venv/bin/pytest -q`
