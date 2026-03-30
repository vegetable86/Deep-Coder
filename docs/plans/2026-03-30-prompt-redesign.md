# Prompt Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the DeepCoder system prompt so it contains explicit trigger rules for retrieval, thinking, web search, and clarification.

**Architecture:** Keep the change isolated to the prompt renderer and prompt-focused tests. Extend `tests/prompts/test_deepcoder_prompt.py` with assertions that capture the exact trigger wording, then update `deep_coder/prompts/deepcoder/prompt.py` minimally so the rendered prompt matches the approved spec without restructuring the rest of the prompt.

**Tech Stack:** Python 3.10+, pytest, stdlib `textwrap`.

---

### Task 1: Add failing prompt trigger tests

**Files:**
- Modify: `tests/prompts/test_deepcoder_prompt.py`
- Modify: `deep_coder/prompts/deepcoder/prompt.py`

**Step 1: Write the failing tests**

Add prompt rendering assertions that verify:
- `# Session History Policy` tells the model to call `search_history` when a prior session reference appears
- `# Session History Policy` tells the model to call `search_history` when the task touches unseen code or context
- `# Tool Usage Policy` includes explicit `think` triggers for non-trivial implementation, complex debugging, and trade-off evaluation
- `# Tool Usage Policy` includes explicit `web_search` triggers for unfamiliar technology, time-sensitive questions, and official documentation lookups
- `# Proactiveness` tells the model to call `ask_user` when meaningful choices or significant assumptions would change the outcome

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/prompts/test_deepcoder_prompt.py`

Expected: FAIL because the current prompt text does not include the new trigger wording.

### Task 2: Update the rendered system prompt

**Files:**
- Modify: `deep_coder/prompts/deepcoder/prompt.py`
- Modify: `tests/prompts/test_deepcoder_prompt.py`

**Step 1: Write the minimal implementation**

Update the prompt text so that:
- the first two bullets in `# Session History Policy` are replaced with the approved retrieval trigger block
- `# Tool Usage Policy` gains the approved `think` trigger bullets
- `# Tool Usage Policy` gains the approved `web_search` trigger bullets
- `# Proactiveness` is replaced with the approved clarification trigger block

Keep the rest of the prompt structure unchanged.

**Step 2: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/prompts/test_deepcoder_prompt.py`

Expected: PASS.

### Task 3: Run regression verification

**Files:**
- Modify: `docs/plans/2026-03-30-prompt-redesign.md`

**Step 1: Run prompt-focused regression coverage**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/ -k prompt`

Expected: PASS.

**Step 2: Run the full suite**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`

Expected: PASS with no regressions.

**Step 3: Review the final diff**

Run: `git status --short && git diff -- deep_coder/prompts/deepcoder/prompt.py tests/prompts/test_deepcoder_prompt.py docs/plans/2026-03-30-prompt-redesign.md`

Expected: Only the planned prompt, test, and plan-file changes appear.
