# DeepCode System Prompt History

Date: 2026-03-27
Branch: `feat/system-prompt`

## Summary

This branch replaces the original placeholder system prompt with a DeepCode-specific runtime prompt that better matches the current product shape.

The earlier prompt only exposed the workspace path, session id, and a flat tool-name list. That was enough to prove wiring, but not enough to steer the model consistently once DeepCode gained project-scoped sessions, task tools, and layered history retrieval.

The implemented prompt now:

- defines DeepCode as a project-scoped coding agent for the current workspace and active session
- sets a reasoning-first, calm, pragmatic tone
- tells the model to briefly explain intent before taking non-trivial actions
- reminds the model to use the available tools when more information is needed instead of guessing
- prefers summary-first history recall and only expands raw artifacts when exact evidence matters
- anchors tone and workflow with short behavioral examples

## Implementation Timeline

### 1. Prompt design and implementation plan

Implemented:

- documented the approved prompt scope, non-goals, and section structure
- captured a TDD-oriented implementation plan for the prompt rewrite

Edited files:

- `docs/plans/2026-03-27-deepcode-system-prompt-design.md`
- `docs/plans/2026-03-27-deepcode-system-prompt.md`

### 2. Prompt renderer rewrite

Implemented:

- replaced the one-line placeholder prompt with a multi-section runtime prompt
- preserved dynamic runtime context by rendering the current workspace path, current session id, and a lightweight available-tool-name summary
- kept tool-schema handling out of the prompt body by treating tool names as hints rather than restating schemas

Edited files:

- `deep_coder/prompts/deepcoder/prompt.py`

### 3. Prompt regression coverage

Implemented:

- added prompt tests for role and session context
- added prompt tests for summary-first history guidance
- added prompt tests for the brief-intent-before-action behavior

Edited files:

- `tests/prompts/test_deepcoder_prompt.py`

## Verification

- `/home/wys/deep-code/.venv/bin/pytest -q tests/prompts/test_deepcoder_prompt.py`
- `/home/wys/deep-code/.venv/bin/pytest -q`
