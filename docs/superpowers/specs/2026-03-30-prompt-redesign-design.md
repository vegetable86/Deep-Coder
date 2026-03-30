# System Prompt Redesign — Behavioral Trigger Additions

**Date:** 2026-03-30

## Goal

Strengthen three weak behavioral areas in the Deep Coder system prompt by adding explicit trigger rules: proactive retrieval, proactive thinking, and proactive clarification. Also strengthen `web_search` triggers which currently have none.

## Approach

Targeted additions to the existing prompt structure — no restructuring, no rewrites. Each fix is a small block of "when X, do Y" rules inserted into the relevant existing section.

---

## Changes

### 1. Session History Policy — Retrieval Triggers

**Problem:** Current wording says "if prior session context *may* matter, use search_history" — too permissive, model treats retrieval as optional.

**Fix:** Replace the first two bullets of `# Session History Policy` with explicit triggers:

```
- If the user references something from a prior session (a decision, a file, an error, a task), call search_history before answering — do not guess.
- If the current task touches code or context you haven't seen in this turn, call search_history to check whether prior work is relevant.
- Only skip retrieval when the current message and visible context are fully sufficient.
```

Keep the remaining bullets (load_history_artifacts guidance, "ask one short clarifying question" fallback) unchanged.

---

### 2. Tool Usage Policy — Think Triggers

**Problem:** `think` has no explicit triggers. The model has to infer when to use it.

**Fix:** Add to `# Tool Usage Policy`:

```
- Before implementing any non-trivial feature, architectural change, or multi-step task, call think to plan your approach first.
- When debugging a complex issue with multiple possible causes, call think to reason through them before acting.
- When you need to evaluate trade-offs between approaches, call think before responding.
```

---

### 3. Tool Usage Policy — Web Search Triggers

**Problem:** `web_search` has no triggers at all. The model has to decide on its own whether to use it.

**Fix:** Add to `# Tool Usage Policy`:

```
- When you encounter an unfamiliar library, API, error message, or technology, call web_search before guessing.
- When the user asks about something that may have changed since your training (versions, current best practices, recent releases), call web_search to verify.
- When official documentation would resolve ambiguity faster than reasoning from memory, call web_search.
```

---

### 4. Proactiveness — Clarification Triggers

**Problem:** Current rule "be proactive only when the user asks" actively suppresses clarification. Model never calls `ask_user` on its own.

**Fix:** Replace the current `# Proactiveness` section body with:

```
- Be proactive only when the user asks you to do something.
- If the user's request requires choosing between approaches and the choice meaningfully affects the outcome, call ask_user before acting.
- If a task is ambiguous in a way that would cause you to make a significant assumption, call ask_user to resolve it first.
- Do not ask for clarification on trivial details — only when the answer would change what you do.
```

---

## Files Modified

- `deep_coder/prompts/deepcoder/prompt.py` — the only file changed

## Testing

- Read the rendered prompt and verify all four trigger blocks appear correctly
- Run existing prompt tests: `pytest tests/ -q -k prompt`

## Success Criteria

- Model calls `search_history` when prior context is plausibly relevant
- Model calls `think` before non-trivial implementation tasks
- Model calls `ask_user` when user faces a real choice
- Model calls `web_search` for unfamiliar tech, version questions, and documentation lookups
- No existing behavior regressed (conciseness, code style, task management)
