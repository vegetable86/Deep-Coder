# Deep Coder Backend Runtime History

Date: 2026-03-25
Branch: `feat/deep-coder-v1`

## Summary

This branch moved the project from a single-file prototype toward the package architecture described in `arch/arch.md`.

The implemented backend runtime now has:

- package-level config and runtime factory
- abstract base contracts for harness, model, tools, prompts, and context
- a DeepSeek model adapter through the OpenAI-compatible SDK
- a builtin tool registry with `bash`, `read_file`, `write_file`, and `edit_file`
- a filesystem-backed local session store under `~/.deepcode`
- a simple append-only context strategy
- a prompt module
- a harness loop that executes tool calls until a final answer

`agentLoop.py` was kept as a prototype/example reference and was not turned into the main runtime entrypoint.

## Implementation Timeline

### 1. Package skeleton and shared config

Commit: `54bf266` `feat: add deep coder package skeleton`

Implemented:

- created the `deep_coder` package
- added `RuntimeConfig`
- added an initial `main.py`
- added import-path bootstrap for tests

Edited files:

- `agentLoop.py`
- `deep_coder/__init__.py`
- `deep_coder/config.py`
- `deep_coder/main.py`
- `tests/conftest.py`
- `tests/test_config.py`

### 2. Base architecture contracts

Commit: `6fcb8ac` `feat: add deep coder base contracts`

Implemented:

- base abstractions for harness, model, tool, prompt, session store, and context strategy
- initial `ContextManager` facade

Edited files:

- `deep_coder/context/__init__.py`
- `deep_coder/context/manager.py`
- `deep_coder/context/stores/__init__.py`
- `deep_coder/context/stores/base.py`
- `deep_coder/context/strategies/__init__.py`
- `deep_coder/context/strategies/base.py`
- `deep_coder/harness/__init__.py`
- `deep_coder/harness/base.py`
- `deep_coder/models/__init__.py`
- `deep_coder/models/base.py`
- `deep_coder/prompts/__init__.py`
- `deep_coder/prompts/base.py`
- `deep_coder/tools/__init__.py`
- `deep_coder/tools/base.py`
- `tests/test_base_contracts.py`

### 3. DeepSeek model adapter

Commit: `b3ebe73` `feat: add deepseek model adapter`

Implemented:

- concrete `DeepSeekModel`
- normalized manifest for provider identification

Edited files:

- `deep_coder/models/deepseek/__init__.py`
- `deep_coder/models/deepseek/model.py`
- `tests/models/test_deepseek_model.py`

### 4. Updated backend runtime plan

Commit: `b6a7e0a` `docs: add backend runtime implementation plan`

Implemented:

- replaced the earlier execution direction with a backend-runtime-first plan aligned to the future TUI direction

Edited files:

- `docs/plans/2026-03-25-deep-coder-backend-runtime-implementation.md`

### 5. Builtin runtime tools

Commit: `79d0a56` `feat: add builtin runtime tools`

Implemented:

- `ToolRegistry`
- builtin tool packages for `bash`, `read_file`, `write_file`, and `edit_file`
- workspace-bounded file access semantics

Edited files:

- `deep_coder/tools/__init__.py`
- `deep_coder/tools/bash/__init__.py`
- `deep_coder/tools/bash/tool.py`
- `deep_coder/tools/edit_file/__init__.py`
- `deep_coder/tools/edit_file/tool.py`
- `deep_coder/tools/read_file/__init__.py`
- `deep_coder/tools/read_file/tool.py`
- `deep_coder/tools/registry.py`
- `deep_coder/tools/write_file/__init__.py`
- `deep_coder/tools/write_file/tool.py`
- `tests/tools/test_file_tools.py`
- `tests/tools/test_registry.py`

### 6. Filesystem session store

Commit: `1131289` `feat: add filesystem session store`

Implemented:

- `Session` object
- `FileSystemSessionStore`
- persistent session layout:
  - `sessions/<session-id>/meta.json`
  - `sessions/<session-id>/messages.jsonl`
  - `sessions/<session-id>/context/<strategy-name>/state.json`

Edited files:

- `deep_coder/context/session.py`
- `deep_coder/context/stores/__init__.py`
- `deep_coder/context/stores/filesystem/__init__.py`
- `deep_coder/context/stores/filesystem/store.py`
- `tests/context/test_filesystem_store.py`

### 7. Simple history context strategy

Commit: `ee2ddfb` `feat: add simple history context strategy`

Implemented:

- append-only context strategy
- request assembly as `system + history + current user input`
- event recording by appending directly into session history

Edited files:

- `deep_coder/context/strategies/__init__.py`
- `deep_coder/context/strategies/simple_history/__init__.py`
- `deep_coder/context/strategies/simple_history/strategy.py`
- `tests/context/test_simple_history_strategy.py`

### 8. Prompt module and runtime factory

Commit: `8e68896` `feat: add runtime prompt and factory`

Implemented:

- `DeepCoderPrompt`
- `build_runtime()` factory
- `state_dir` override support in config for testable local storage wiring

Edited files:

- `deep_coder/config.py`
- `deep_coder/main.py`
- `deep_coder/prompts/__init__.py`
- `deep_coder/prompts/deepcoder/__init__.py`
- `deep_coder/prompts/deepcoder/prompt.py`
- `tests/prompts/test_deepcoder_prompt.py`
- `tests/test_main.py`

### 9. Harness runtime

Commit: `d9f541f` `feat: add deep coder harness runtime`

Implemented:

- `HarnessResult`
- `DeepCoderHarness`
- runtime wiring from `build_runtime()` to `harness`
- tool-call execution loop until final assistant answer
- user-message recording without duplicate user turns during tool-call loops

Edited files:

- `deep_coder/context/strategies/simple_history/strategy.py`
- `deep_coder/harness/__init__.py`
- `deep_coder/harness/deepcoder/__init__.py`
- `deep_coder/harness/deepcoder/harness.py`
- `deep_coder/harness/result.py`
- `deep_coder/main.py`
- `tests/harness/test_deepcoder_harness.py`

## Current Runtime Shape

Main runtime modules:

- `deep_coder/config.py`
- `deep_coder/main.py`
- `deep_coder/models/deepseek/model.py`
- `deep_coder/tools/registry.py`
- `deep_coder/tools/bash/tool.py`
- `deep_coder/tools/read_file/tool.py`
- `deep_coder/tools/write_file/tool.py`
- `deep_coder/tools/edit_file/tool.py`
- `deep_coder/context/session.py`
- `deep_coder/context/stores/filesystem/store.py`
- `deep_coder/context/strategies/simple_history/strategy.py`
- `deep_coder/prompts/deepcoder/prompt.py`
- `deep_coder/harness/deepcoder/harness.py`
- `deep_coder/harness/result.py`

Main test coverage added:

- `tests/test_config.py`
- `tests/test_base_contracts.py`
- `tests/models/test_deepseek_model.py`
- `tests/tools/test_registry.py`
- `tests/tools/test_file_tools.py`
- `tests/context/test_filesystem_store.py`
- `tests/context/test_simple_history_strategy.py`
- `tests/prompts/test_deepcoder_prompt.py`
- `tests/test_main.py`
- `tests/harness/test_deepcoder_harness.py`

## What Was Intentionally Left Thin

The architecture exists, but some areas remain intentionally minimal:

- no TUI yet
- no prompt override loading from `~/.deepcode/prompts/`
- no `config.toml` or `tui.toml` support yet
- no advanced context compaction strategy yet
- no retry/backoff policy yet in the DeepSeek adapter
- no CLI/TUI session browser yet, although the session store supports stable listing

## Verification Snapshot

Latest backend verification during implementation:

- command: `pytest -v`
- result: `14 passed in 0.54s`

This report describes the backend runtime state after the harness/runtime implementation commit `d9f541f`.
