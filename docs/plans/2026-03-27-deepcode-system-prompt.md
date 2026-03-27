# DeepCode System Prompt Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current minimal DeepCode system prompt with a prompt that sets role, tone, brief-intent-before-action behavior, and summary-first history recall.

**Architecture:** Keep `DeepCoderPrompt.render()` as a pure renderer that derives the workspace path, session id, and tool-name summary from runtime inputs, but move the prompt body to a stable multi-section template. Do not duplicate tool schemas; only remind the model that tool schemas are provided separately and that it should use available tools when more information is required.

**Tech Stack:** Python 3, pytest, existing Deep Coder prompt module

**Execution Notes:** Follow `@test-driven-development` and `@verification-before-completion`. Use `/home/wys/deep-code/.venv/bin/pytest -q` for verification in this repository. This plan is written for worktree branch `feat/system-prompt`.

---

### Task 1: Expand prompt tests to cover the new guidance

**Files:**
- Modify: `tests/prompts/test_deepcoder_prompt.py`

**Step 1: Write the failing tests**

```python
def test_prompt_render_includes_role_and_session_context(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[{"function": {"name": "bash"}}],
    )

    assert "You are DeepCode, a project-scoped coding agent" in text
    assert str(config.workdir) in text
    assert "Current session: session-1" in text
```

```python
def test_prompt_render_prefers_summary_first_history_recall(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[{"function": {"name": "search_history"}}],
    )

    assert "Prefer summary first." in text
    assert "Only load original history artifacts" in text
```

```python
def test_prompt_render_requires_brief_intent_before_action(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = RuntimeConfig.from_env(workdir=tmp_path, state_dir=tmp_path / ".deepcode")
    prompt = DeepCoderPrompt(config=config)

    text = prompt.render(
        session_snapshot={"id": "session-1"},
        tool_schemas=[{"function": {"name": "read_file"}}],
    )

    assert "Before taking a non-trivial action" in text
    assert "briefly state your intent" in text
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/prompts/test_deepcoder_prompt.py`
Expected: FAIL because the current prompt only mentions workspace, session id, and tool names.

**Step 3: Write the minimal implementation**

```python
return (
    "You are DeepCode, a project-scoped coding agent ..."
    ...
    "Prefer summary first."
    ...
)
```

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/prompts/test_deepcoder_prompt.py`
Expected: PASS

### Task 2: Implement the prompt template in `DeepCoderPrompt`

**Files:**
- Modify: `deep_coder/prompts/deepcoder/prompt.py`

**Step 1: Refine the prompt body after green**

```python
sections = [
    f"You are DeepCode, a project-scoped coding agent ...",
    f"Current workspace: {self.config.workdir}",
    f"Current session: {session_id}",
    ...
]
return "\n\n".join(sections)
```

**Step 2: Keep dynamic runtime context in the rendered output**

```python
tool_names = ", ".join(...)
```

Use the tool-name summary only as a lightweight runtime hint, not as a schema replacement.

**Step 3: Re-run the targeted tests**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/prompts/test_deepcoder_prompt.py`
Expected: PASS

### Task 3: Final verification

**Files:**
- Modify: `deep_coder/prompts/deepcoder/prompt.py`
- Modify: `tests/prompts/test_deepcoder_prompt.py`
- Add docs: `docs/plans/2026-03-27-deepcode-system-prompt-design.md`
- Add docs: `docs/plans/2026-03-27-deepcode-system-prompt.md`

**Step 1: Run full suite**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`
Expected: PASS

**Step 2: Review working tree**

Run: `git status --short`
Expected: only the intended prompt and docs changes appear.

**Step 3: Commit**

```bash
git add deep_coder/prompts/deepcoder/prompt.py tests/prompts/test_deepcoder_prompt.py docs/plans/2026-03-27-deepcode-system-prompt-design.md docs/plans/2026-03-27-deepcode-system-prompt.md
git commit -m "feat: refine deepcode system prompt"
```
