# Skills Browser History

Date: 2026-03-27
Branch: `fix/skills-browser`

## Summary

This branch simplifies the TUI skill workflow down to two user-facing paths:

- `/skills` opens the installed-skill list
- `/skills show` opens a browse flow for skill content

The earlier command surface exposed `use`, `drop`, `clear`, and `show <name>`, which made the interaction model heavier than needed and left the `show` path broken for actual content viewing.

The implemented fix keeps skill activation session-scoped but moves it into the modal list itself:

- rows now render `√` for selected skills and `x` for unselected skills
- pressing `Enter` in the `/skills` list toggles the highlighted skill without closing the modal
- `/skills show` now lists all skills and lets the user open a full read-only content view from the list
- the old `/skills show <name>` status-line path is removed

## Implementation Timeline

### 1. Simplify skill commands and repair skill-content browsing

Implemented:

- reduced `SkillsCommand` completions and execution paths to `list` and `show`
- returned skill-list payloads for both toggle mode and browse mode instead of one-line `show` status messages
- extended the skill modal into two modes:
  - toggle mode for selection changes
  - browse mode for full skill-content viewing
- updated the list labels from `*` and `-` to `√` and `x`
- wired in-session skill toggling through the TUI app so selection changes emit the same timeline events and status updates as other skill actions
- added regression coverage for:
  - subcommand completion
  - rejecting removed legacy subcommands
  - list markers
  - enter-to-toggle behavior
  - enter-to-browse skill content

Edited files:

- `deep_coder/tui/app.py`
- `deep_coder/tui/commands/builtin/skills.py`
- `deep_coder/tui/screens/skill_list.py`
- `tests/tui/test_app_layout.py`
- `tests/tui/test_commands.py`

## Verification

- `/home/wys/deep-code/.venv/bin/pytest -q`
