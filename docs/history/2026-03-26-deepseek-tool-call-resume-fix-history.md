# DeepSeek Tool Call Resume Fix History

Date: 2026-03-26
Branch: `fix/deepseek-tool-call-shape`

## Summary

This branch fixes resumed harness turns against DeepSeek after a tool call has already been recorded in session history.

The failing request path replayed assistant tool calls from internal runtime history using a shape like `{id, name, arguments}`. DeepSeek's OpenAI-compatible `/chat/completions` endpoint instead expects typed tool call objects with a `type` field and nested `function` payload, which caused the 400 error:

- `messages[2]: missing field type`

The implemented fix keeps the runtime's stored message history unchanged and translates assistant tool calls only at the DeepSeek adapter boundary before sending the outbound request.

## Implementation Timeline

### 1. Serialize assistant tool calls for outbound DeepSeek requests

Commit: `f3588c0` `fix: serialize deepseek replay tool calls`

Implemented:

- added outbound message serialization in `DeepSeekModel.complete()`
- converted assistant tool calls from the runtime's internal shape into provider-compatible `{id, type, function}` objects
- stringified non-string tool arguments before request dispatch
- preserved existing inbound tool-argument normalization for tool execution
- added a regression test that captures the outbound payload for a resumed tool-call conversation

Edited files:

- `deep_coder/models/deepseek/model.py`
- `tests/models/test_deepseek_model.py`

## Verification

- `/home/wys/deep-code/.venv/bin/pytest -q`
