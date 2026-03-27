# Layered Context History

Date: 2026-03-27
Branch: `feat/layered-context`

## Summary

This branch replaces the old append-all transcript model with a layered context system that stores lightweight journal metadata, exact evidence payloads, structured summaries, and tool artifacts separately.

The runtime now:

- persists journal, evidence, summaries, and artifacts in the filesystem session store
- records structured context events through `ContextManager`
- builds prompts from a rolling summary plus recent verbatim turns
- compacts older spans into model-generated summaries when prompt usage exceeds the configured budget
- exposes `search_history` for summary-first recall
- exposes `load_history_artifacts` for exact evidence and artifact expansion

## Implementation Timeline

### 1. Layered record primitives and persistence

Commits:

- `b54d460` `feat: add layered context record primitives`
- `147d734` `feat: persist layered context state in filesystem store`
- `f06d2b5` `feat: add structured layered context recording APIs`

Implemented:

- layered context budget fields on `RuntimeConfig`
- record helpers for journal, evidence, and summary entries
- filesystem persistence for `journal.jsonl`, `evidence.jsonl`, `summaries.jsonl`, and `artifacts.json`
- legacy `messages.jsonl` projection into layered records
- structured recording helpers on `ContextManager`

Edited files:

- `deep_coder/config.py`
- `deep_coder/context/records.py`
- `deep_coder/context/session.py`
- `deep_coder/context/stores/filesystem/store.py`
- `deep_coder/context/manager.py`
- `deep_coder/context/strategies/base.py`
- `deep_coder/context/strategies/simple_history/strategy.py`
- `tests/test_config.py`
- `tests/context/test_records.py`
- `tests/context/test_filesystem_store.py`
- `tests/context/test_simple_history_strategy.py`
- `tests/context/test_layered_context_manager.py`

### 2. Rolling summary strategy and model summarizer

Commit: `38d61ec` `feat: add layered history strategy with rolling summaries`

Implemented:

- `SummarizerBase` and `ModelSummarizer`
- `LayeredHistoryContextStrategy`
- rolling summary prompt assembly from summaries plus recent turns
- summary compaction for older journal spans
- default runtime wiring to layered history in `build_runtime()`

Edited files:

- `deep_coder/context/summarizers/base.py`
- `deep_coder/context/summarizers/model.py`
- `deep_coder/context/strategies/layered_history/strategy.py`
- `deep_coder/main.py`
- `tests/context/test_layered_history_strategy.py`
- `tests/test_main.py`

### 3. Harness integration and compaction events

Commit: `bb0cc35` `feat: wire harness into layered context compaction`

Implemented:

- typed harness writes through `record_user_message()`, `record_assistant_message()`, and `record_tool_result()`
- persisted `context_compacted` events when the strategy compacts after high prompt usage
- layered-context regression coverage around journal/evidence ordering and compaction

Edited files:

- `deep_coder/harness/deepcoder/harness.py`
- `tests/harness/test_deepcoder_harness.py`

### 4. History retrieval tools

Commit: `a917329` `feat: add layered history retrieval tools`

Implemented:

- `search_history` for summary-first history lookup with evidence fallback
- `load_history_artifacts` for exact artifact and evidence payload loading
- builtin registry wiring for both history tools

Edited files:

- `deep_coder/tools/history_search/tool.py`
- `deep_coder/tools/history_load/tool.py`
- `deep_coder/tools/registry.py`
- `tests/tools/test_registry.py`
- `tests/tools/test_history_tools.py`

### 5. Architecture and plan documentation

Commit: `38a6e68` `docs: document layered context architecture`

Implemented:

- architecture updates describing the three-layer session model
- request-flow updates for rolling-summary prompt assembly and retrieval tools
- tracked layered-context implementation plan with end-state notes

Edited files:

- `arch/arch.md`
- `docs/plans/2026-03-27-layered-context-storage.md`

## Verification

- `/home/wys/deep-code/.venv/bin/pytest -q tests/context tests/harness/test_deepcoder_harness.py tests/tools/test_registry.py tests/tools/test_history_tools.py tests/test_main.py tests/test_config.py`
- `/home/wys/deep-code/.venv/bin/pytest -q`
