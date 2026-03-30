# Web Search Tool Design

**Date:** 2026-03-30

## Goal

Add a `web_search` tool to Deep Coder so the model has explicit, structured access to web search results. The tool is backed by a real search API (Google, Serper, or Brave), switchable via `~/.deepcode/config.toml`. Optionally fetches and cleans full page content per result.

---

## Architecture

A single `web_search` tool with a fixed schema. The active provider is resolved at startup from config and injected into the tool via `RuntimeConfig`. Each provider is a small adapter implementing a common `SearchProvider` abstract base class. If `[web_search]` is absent from config, the tool is not registered — no crash, no silent failure.

**Tech stack:** `httpx` (HTTP client), `beautifulsoup4` (HTML cleaning), `toml` (already used for config).

---

## Tool Interface

**Name:** `web_search`

**Input schema:**

```json
{
  "query": "string — the search query",
  "num_results": "integer, optional, default 5 — number of results to return",
  "fetch_content": "boolean, optional, default false — if true, fetches and cleans full page text for each result"
}
```

**Output:** JSON string returned as `output_text` to the model:

```json
[
  {
    "title": "Result Title",
    "url": "https://example.com/page",
    "snippet": "Short description from search index.",
    "content": "Full cleaned page text (only present if fetch_content=true)"
  }
]
```

If `fetch_content=true` and a page fetch fails (timeout, HTTP error, network error), the result's `content` field is set to `"fetch failed: <reason>"`. The result is still included — the model sees the failure and decides whether to retry, skip, or ask the user.

If the search API call itself fails, the tool returns an error string as `output_text` with `is_error=True` (following the existing `ToolExecutionResult` pattern). The model receives a clear failure signal and can decide how to handle it.

---

## Provider Architecture

**Abstract base:**

```python
# deep_coder/tools/web_search/providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

class SearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, num_results: int) -> list[SearchResult]:
        raise NotImplementedError
```

**Providers:**

| Provider | Config key | Required config fields |
|---|---|---|
| Google Custom Search | `"google"` | `api_key`, `cx` |
| Serper.dev | `"serper"` | `api_key` |
| Brave Search | `"brave"` | `api_key` |

Each provider lives in its own file:
- `deep_coder/tools/web_search/providers/google.py`
- `deep_coder/tools/web_search/providers/serper.py`
- `deep_coder/tools/web_search/providers/brave.py`

---

## Configuration

In `~/.deepcode/config.toml`:

```toml
[web_search]
provider = "serper"  # or "google" or "brave"

[web_search.serper]
api_key = "your-key"

[web_search.google]
api_key = "your-key"
cx = "your-cx-id"

[web_search.brave]
api_key = "your-key"
```

If `[web_search]` section is absent, `WebSearchTool` is not added to `ToolRegistry.from_builtin()`. No error is raised.

---

## Page Content Fetching

When `fetch_content=true`:

1. For each result URL, issue an `httpx.get()` with a 10-second timeout.
2. On success: parse HTML with `BeautifulSoup`, remove `<script>`, `<style>`, `<head>`, and HTML comments, then call `.get_text(separator=" ", strip=True)` to extract clean plain text. Normalize whitespace. Return the full cleaned text — no character truncation.
3. On failure (timeout, HTTP 4xx/5xx, connection error): set `content` to `"fetch failed: <reason>"` where `<reason>` is a short description (e.g., `"timeout"`, `"HTTP 404"`, `"connection refused"`).

Fetches are sequential (not concurrent) to keep implementation simple.

---

## File Structure

```
deep_coder/tools/web_search/
    __init__.py
    tool.py                  # WebSearchTool — ToolBase subclass
    fetch.py                 # fetch_and_clean(url) -> str
    providers/
        __init__.py
        base.py              # SearchProvider ABC + SearchResult dataclass
        google.py            # GoogleSearchProvider
        serper.py            # SerperProvider
        brave.py             # BraveSearchProvider
        factory.py           # build_provider(config) -> SearchProvider | None
```

`RuntimeConfig` gains an optional `web_search_provider: SearchProvider | None` field. `build_runtime()` calls `build_provider(config)` and passes the result to `ToolRegistry.from_builtin()`. If `None`, the tool is skipped.

---

## Error Handling

| Failure | Behavior |
|---|---|
| `[web_search]` absent from config | Tool not registered; model never sees it |
| Unknown provider name in config | `build_provider()` raises `ValueError` at startup with a clear message |
| Missing required config field (e.g., no `api_key`) | `build_provider()` raises `ValueError` at startup |
| Search API call fails (network, auth, rate limit) | `is_error=True`, `output_text` = `"web_search failed: <reason>"` |
| Individual page fetch fails | `content` = `"fetch failed: <reason>"`, result still included |

---

## Testing

All tests mock the HTTP layer — no live API calls.

- `tests/tools/web_search/test_google.py` — mock `httpx` responses, verify URL construction, headers, result parsing
- `tests/tools/web_search/test_serper.py` — same for Serper
- `tests/tools/web_search/test_brave.py` — same for Brave
- `tests/tools/web_search/test_fetch.py` — mock `httpx`, verify HTML stripping, whitespace normalization, error strings
- `tests/tools/web_search/test_tool.py` — mock provider, verify schema, `exec()` output format, `fetch_content` pipeline, `is_error` on search failure

---

## Integration Points

- `deep_coder/config.py` — add `web_search_provider: SearchProvider | None = None` to `RuntimeConfig`
- `deep_coder/main.py` — call `build_provider(config)` in `build_runtime()`, pass to `ToolRegistry.from_builtin()`
- `deep_coder/tools/registry.py` — conditionally register `WebSearchTool` if provider is not `None`
- `pyproject.toml` — add `httpx` and `beautifulsoup4` to dependencies
