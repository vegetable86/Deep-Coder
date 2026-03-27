# README And Source Install Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a real source-install flow that exposes `deepcode` as a command and write a top-level README that covers introduction, Mermaid architecture, installation, and usage.

**Architecture:** Keep the current runtime entrypoint in `deep_coder.cli:main` and package it through a console-script entry. Document the shipped project shape in `README.md` without changing the runtime module boundaries or launch flow.

**Tech Stack:** Python 3, setuptools via `pyproject.toml`, pytest, Markdown, Mermaid

**Execution Notes:** Follow `@test-driven-development` and `@verification-before-completion`. Use `/home/wys/Deep-Coder/.venv/bin/pytest -q` for verification in this repository. This plan is written for worktree branch `feat/readme-source-install`.

---

### Task 1: Add failing tests for packaging and README requirements

**Files:**
- Add: `tests/test_packaging.py`

**Step 1: Write the failing tests**

```python
def test_pyproject_declares_deepcode_console_script():
    data = load_pyproject()
    assert data["project"]["scripts"]["deepcode"] == "deep_coder.cli:main"


def test_readme_documents_source_install_and_core_usage():
    text = Path("README.md").read_text()
    assert "```mermaid" in text
    assert "python3 -m pip install --user ." in text
    assert "/history" in text
```

**Step 2: Run tests to verify they fail**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/test_packaging.py`
Expected: FAIL because the repository does not yet contain `pyproject.toml` or `README.md`.

**Step 3: Write minimal implementation**

Create `pyproject.toml` and `README.md` with the promised content.

**Step 4: Re-run tests**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/test_packaging.py`
Expected: PASS

### Task 2: Add package metadata for source installs

**Files:**
- Add: `pyproject.toml`

**Step 1: Define build metadata**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

**Step 2: Define project metadata and console script**

```toml
[project]
name = "deep-coder"
...

[project.scripts]
deepcode = "deep_coder.cli:main"
```

**Step 3: Declare package discovery and dev extras**

```toml
[tool.setuptools.packages.find]
include = ["deep_coder*"]
```

### Task 3: Write the public README

**Files:**
- Add: `README.md`

**Step 1: Document the product and highlights**

Explain the current terminal-app product shape and call out project-scoped sessions, timeline replay, live tool streaming, task snapshots, and layered history.

**Step 2: Document installation**

Include:

- `python3 -m pip install --user .`
- `python3 -m pip install -e ".[dev]"`
- `DEEPSEEK_API_KEY`
- launch with `deepcode`

**Step 3: Add Mermaid architecture**

Use a Mermaid flowchart that matches the shipped runtime.

**Step 4: Add the user manual**

Include:

- submit prompts in the composer
- `/history`, `/session`, `/model`, `/exit`
- `Ctrl+L`, `Ctrl+J`, `Ctrl+C`
- project state under `~/.deepcode/`
- note that `agentLoop.py` is legacy

### Task 4: Verify install flow and full repository health

**Files:**
- Add: `pyproject.toml`
- Add: `README.md`
- Add: `tests/test_packaging.py`
- Add docs: `docs/plans/2026-03-27-readme-source-install-design.md`
- Add docs: `docs/plans/2026-03-27-readme-source-install.md`

**Step 1: Run targeted tests**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q tests/test_packaging.py`
Expected: PASS

**Step 2: Verify editable install creates the command**

Run: `/home/wys/Deep-Coder/.venv/bin/python -m pip install -e .`
Expected: PASS and create `/home/wys/Deep-Coder/.venv/bin/deepcode`

**Step 3: Run the full suite**

Run: `/home/wys/Deep-Coder/.venv/bin/pytest -q`
Expected: PASS

**Step 4: Review working tree**

Run: `git status --short`
Expected: only the intended packaging, README, tests, and plan docs appear.
