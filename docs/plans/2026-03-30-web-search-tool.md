# Web Search Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a configurable `web_search` tool with provider-backed search results and optional page content fetching.

**Architecture:** Extend runtime config to carry parsed `web_search` settings from `~/.deepcode/config.toml`, build a provider during runtime setup, and conditionally register a new `WebSearchTool`. Keep provider adapters, fetch/clean logic, and tool execution isolated under `deep_coder/tools/web_search/` so runtime, config, and tool registry stay thin.

**Tech Stack:** Python 3.10+, `httpx`, `beautifulsoup4`, stdlib `tomllib`, pytest.

---

### Task 1: Add config parsing coverage for nested web search settings

**Files:**
- Modify: `tests/projects/test_registry.py`
- Modify: `tests/test_config.py`
- Modify: `deep_coder/projects/registry.py`
- Modify: `deep_coder/config.py`

**Step 1: Write the failing tests**

Add tests that:
- load nested TOML from `config.toml`
- preserve existing `projects` and context setting behavior
- expose `web_search_settings` on `RuntimeConfig`
- default `web_search_settings` to `None` when config is absent

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/projects/test_registry.py tests/test_config.py`

Expected: FAIL because `ProjectRegistry` cannot read TOML tables and `RuntimeConfig` has no web search settings field.

**Step 3: Write the minimal implementation**

Implement TOML-backed loading with `tomllib` in `ProjectRegistry`, preserve the current save format for projects/context/default model, and add an optional `web_search_settings` field to `RuntimeConfig` populated from project/global config data.

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/projects/test_registry.py tests/test_config.py`

Expected: PASS.

### Task 2: Add provider factory and HTML fetch coverage

**Files:**
- Create: `tests/tools/web_search/test_fetch.py`
- Create: `tests/tools/web_search/test_google.py`
- Create: `tests/tools/web_search/test_serper.py`
- Create: `tests/tools/web_search/test_brave.py`
- Create: `deep_coder/tools/web_search/__init__.py`
- Create: `deep_coder/tools/web_search/fetch.py`
- Create: `deep_coder/tools/web_search/providers/__init__.py`
- Create: `deep_coder/tools/web_search/providers/base.py`
- Create: `deep_coder/tools/web_search/providers/factory.py`
- Create: `deep_coder/tools/web_search/providers/google.py`
- Create: `deep_coder/tools/web_search/providers/serper.py`
- Create: `deep_coder/tools/web_search/providers/brave.py`

**Step 1: Write the failing tests**

Add tests that:
- verify each provider sends the right URL, params, and headers
- parse provider-specific payloads into normalized `SearchResult` values
- raise clear `ValueError` messages for unknown providers and missing required keys
- strip scripts/styles/comments/head content from fetched HTML
- normalize whitespace and surface fetch failures as `fetch failed: <reason>`

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tools/web_search/test_fetch.py tests/tools/web_search/test_google.py tests/tools/web_search/test_serper.py tests/tools/web_search/test_brave.py`

Expected: FAIL because the web search package does not exist yet.

**Step 3: Write the minimal implementation**

Add provider abstractions, concrete adapters, factory wiring, and sequential page fetch/clean helpers using `httpx` and `BeautifulSoup`.

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tools/web_search/test_fetch.py tests/tools/web_search/test_google.py tests/tools/web_search/test_serper.py tests/tools/web_search/test_brave.py`

Expected: PASS.

### Task 3: Add tool wiring and runtime integration

**Files:**
- Create: `tests/tools/web_search/test_tool.py`
- Modify: `tests/tools/test_registry.py`
- Modify: `tests/test_main.py`
- Create: `deep_coder/tools/web_search/tool.py`
- Modify: `deep_coder/tools/registry.py`
- Modify: `deep_coder/main.py`
- Modify: `pyproject.toml`

**Step 1: Write the failing tests**

Add tests that:
- verify `WebSearchTool.schema()` and output JSON shape
- verify `fetch_content` enriches results through the fetch helper
- return `is_error=True` and `web_search failed: <reason>` on provider failure
- register `web_search` only when a provider is configured
- attach the provider to runtime config/runtime setup

**Step 2: Run tests to verify they fail**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tools/web_search/test_tool.py tests/tools/test_registry.py tests/test_main.py`

Expected: FAIL because the tool and runtime wiring are not implemented yet.

**Step 3: Write the minimal implementation**

Add `WebSearchTool`, conditionally register it from `ToolRegistry.from_builtin()`, build the provider in `build_runtime()`, and declare the new dependencies in `pyproject.toml`.

**Step 4: Run tests to verify they pass**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/tools/web_search/test_tool.py tests/tools/test_registry.py tests/test_main.py`

Expected: PASS.

### Task 4: Run full verification and inspect final diff

**Files:**
- Modify: `docs/plans/2026-03-30-web-search-tool.md`

**Step 1: Run targeted regression coverage**

Run: `/home/wys/deep-code/.venv/bin/pytest -q tests/projects/test_registry.py tests/test_config.py tests/tools/web_search/test_fetch.py tests/tools/web_search/test_google.py tests/tools/web_search/test_serper.py tests/tools/web_search/test_brave.py tests/tools/web_search/test_tool.py tests/tools/test_registry.py tests/test_main.py`

Expected: PASS.

**Step 2: Run the full suite**

Run: `/home/wys/deep-code/.venv/bin/pytest -q`

Expected: PASS with no regressions.

**Step 3: Review the final diff**

Run: `git status --short && git diff --stat && git diff -- deep_coder tests pyproject.toml`

Expected: Only the planned web search files and test/config/runtime changes appear.
