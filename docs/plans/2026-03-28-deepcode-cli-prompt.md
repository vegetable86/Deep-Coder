# DeepCode CLI Prompt Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite the DeepCode system prompt so it fits the strict CLI style and the real three-layer context architecture without claiming unsupported behavior.

**Architecture:** Keep `DeepCoderPrompt.render()` as a pure renderer driven by runtime inputs, but replace the mixed prompt drafts with one compact multi-section template. The new template should teach context sufficiency judgment, summary-first history search through `search_history`, exact evidence escalation through `load_history_artifacts`, and CLI-specific response discipline that relies on the timeline for operational detail.

**Tech Stack:** Python 3, pytest, existing Deep Coder prompt module and harness tests

**Execution Notes:** Follow `@test-driven-development` and `@verification-before-completion`. Use `/home/wys/deep-code/.venv/bin/pytest -q` for verification in this repository. This plan is written for worktree branch `feat/prompt-cli-context`.

---

### Task 1: Expand the prompt regression tests around CLI and layered-context policy

**Files:**
- Modify: `tests/prompts/test_deepcoder_prompt.py`

**Step 1: Write the failing tests**

```python
def test_prompt_render_checks_context_sufficiency_before_history_lookup(...):
    ...
    assert "If the current message and visible context are enough" in text
    assert "answer directly" in text
```

```python
def test_prompt_render_searches_compact_history_before_loading_evidence(...):
    ...
    assert "search_history" in text
    assert "compact history" in text
    assert "load_history_artifacts" in text
    assert "exact wording" in text
```

```python
def test_prompt_render_keeps_task_tools_for_multi_step_work(...):
    ...
    assert "Use task tools for multi-step work" in text
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/prompts/test_deepcoder_prompt.py`
Expected: FAIL because the current renderer is malformed and the new CLI-specific assertions are missing.

**Step 3: Write the minimal implementation later**

Leave production code unchanged until the new tests fail for the intended reasons.

**Step 4: Re-run the targeted tests to confirm the red baseline**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/prompts/test_deepcoder_prompt.py`
Expected: FAIL

### Task 2: Rewrite `DeepCoderPrompt.render()` into one coherent template

**Files:**
- Modify: `deep_coder/prompts/deepcoder/prompt.py`

**Step 1: Replace the mixed drafts with one section list**

```python
sections = [
    "... strict CLI identity ...",
    f"Current workspace: {self.config.workdir}",
    f"Current session: {session_id}",
    "... context sufficiency policy ...",
    "... search_history before load_history_artifacts ...",
]
return "\n\n".join(sections)
```

**Step 2: Keep tool references grounded in the real runtime**

```python
tool_names = ", ".join(schema["function"]["name"] for schema in tool_schemas)
```

Use tool names only as a lightweight runtime hint. Do not invent generic capabilities beyond the actual builtin tools.

**Step 3: Re-run prompt tests**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/prompts/test_deepcoder_prompt.py`
Expected: PASS

### Task 3: Re-run the harness regression that depends on prompt output

**Files:**
- Modify: `deep_coder/prompts/deepcoder/prompt.py`
- Test: `tests/harness/test_deepcoder_harness.py`

**Step 1: Run the targeted harness test**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/harness/test_deepcoder_harness.py::test_harness_injects_skill_index_and_active_skill_bodies`
Expected: PASS

**Step 2: Refine prompt wording only if the harness assertion still fails**

The rendered system prompt must still mention `load_skill` when that tool exists.

### Task 4: Final verification

**Files:**
- Modify: `deep_coder/prompts/deepcoder/prompt.py`
- Modify: `tests/prompts/test_deepcoder_prompt.py`
- Add docs: `docs/plans/2026-03-28-deepcode-cli-prompt-design.md`
- Add docs: `docs/plans/2026-03-28-deepcode-cli-prompt.md`

**Step 1: Run full suite**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`
Expected: PASS

**Step 2: Review working tree**

Run: `git status --short`
Expected: only the prompt, tests, and docs changes appear in the worktree.

**Step 3: Commit**

```bash
git add deep_coder/prompts/deepcoder/prompt.py tests/prompts/test_deepcoder_prompt.py docs/plans/2026-03-28-deepcode-cli-prompt-design.md docs/plans/2026-03-28-deepcode-cli-prompt.md
git commit -m "feat: align deepcode prompt with cli context flow"
```
