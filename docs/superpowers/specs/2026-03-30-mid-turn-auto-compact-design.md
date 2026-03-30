# Mid-Turn Auto-Compact Design

**Date:** 2026-03-30
**Status:** Approved

## Problem

The existing auto-compaction fires only after a successful model response, using a soft token threshold (`context_compact_threshold`, default 4500). This threshold is far below the model's hard context window (128k tokens for deepseek-chat), so it triggers compaction for routine housekeeping but provides no protection against context overflow.

In long sessions with many tool calls (e.g. reading large files, long outputs), the context can grow past 128k tokens within a single turn. The API then returns a context-length error. The harness catches this as a generic exception, emits `turn_failed`, and the turn dies — even though compaction could have prevented it.

## Goal

Compact the context automatically mid-turn, before the context window is exhausted, so long-running turns complete without hitting the model's hard limit.

## Design

### Trigger: 90% ceiling check

After each successful model response, if `prompt_tokens >= context_max_tokens * 0.9`, compact immediately before the next model call in the same turn. The 90% threshold provides ~12,800 tokens of headroom for the next response.

This replaces the old `context_compact_threshold` soft trigger entirely.

### Config changes

Remove `context_compact_threshold` from `RuntimeConfig` and `DEFAULT_CONTEXT_SETTINGS`.

Add `context_max_tokens: int` with default `128000`.

```toml
# ~/.deepcode/config.toml
[context]
context_max_tokens = 128000   # model's hard context window
```

### Strategy changes (`LayeredHistoryContextStrategy`)

`should_compact` becomes:

```python
def should_compact(self, session, usage: dict | None = None) -> bool:
    if not usage:
        return False
    prompt_tokens = usage.get("prompt_tokens", 0)
    if prompt_tokens < self.config.context_max_tokens * 0.9:
        return False
    return bool(self._summarizable_entries(session))
```

No changes to `maybe_compact`, `_summarizable_entries`, or the harness loop.

### Incremental compaction (existing behavior, preserved)

`_summarizable_entries` already excludes entries that carry a `summary_ids` field, so each compaction only covers unsummarized entries older than the `context_recent_turns` window. Content is never summarized twice. This invariant is unchanged.

### Harness (no changes)

The harness already calls `maybe_compact` after every successful model response. With the updated `should_compact`, mid-turn compaction fires automatically whenever the 90% ceiling is crossed. The existing `context_compacting` / `context_compacted` events cover this case — no new event types needed.

## Cleanup scope

- Remove `context_compact_threshold` from:
  - `deep_coder/config.py` — `DEFAULT_CONTEXT_SETTINGS`, `RuntimeConfig`, `_resolve_context_settings`, `from_env`, `from_project`
  - `deep_coder/context/strategies/layered_history/strategy.py` — `should_compact`
  - Any tests referencing `context_compact_threshold`
- Add `context_max_tokens` in all the same locations

## Testing

Update existing `should_compact` tests to use `context_max_tokens` instead of `context_compact_threshold`. Verify:

- Compaction does not trigger below 90% of `context_max_tokens`
- Compaction triggers at or above 90% when summarizable entries exist
- Compaction does not trigger when no summarizable entries exist (nothing to compact)
- A second compaction in the same session only covers entries not already summarized
