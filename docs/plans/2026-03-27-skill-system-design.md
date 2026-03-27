# Skill System Design

**Date:** 2026-03-27

## Goal

Design a global skill system for `deepcode` that stores reusable prompt overlays under `~/.deepcode/skills/`, exposes a compact skill index to the model on every turn, lets both users and the model activate skills dynamically, and keeps active skills stable across session compaction without polluting normal chat history.

## Product Scope

This design adds:

- global skill files under `~/.deepcode/skills/`
- a dedicated runtime skill subsystem under `deep_coder/skills/`
- a compact skill index injected into the model context on every turn
- dynamic model-driven skill loading through an explicit tool
- user-driven skill activation through `/skills` commands
- session-scoped active skill persistence
- request-time injection of active skill bodies above compacted conversation history
- timeline and replay visibility for skill activation and removal
- compaction rules that preserve active skills exactly

This design does not add:

- project-local skill stores
- remote skill registries or package installation
- automatic skill compaction or summarization
- advanced ranking or embedding-based skill retrieval
- a separate full-screen skill browser in the TUI

## Core Decisions

### Dedicated Skill Subsystem

The skill feature should live in a dedicated module family under `deep_coder/skills/`, not inside prompt code, command code, or context strategy code.

Recommended module split:

- `deep_coder/skills/base.py`
- `deep_coder/skills/registry.py`
- `deep_coder/skills/parser.py`
- `deep_coder/skills/models.py`

This keeps skill discovery, metadata parsing, and prompt assembly separate from the TUI and the harness.

### Global Storage Under `~/.deepcode/skills/`

Skills are global user assets, not repository assets. The canonical source of truth should be the filesystem under:

```text
~/.deepcode/skills/
```

Each skill should be one markdown file with a metadata header plus a prompt body.

Recommended shape:

```md
---
name: python-tests
title: Python Test Fixing
summary: Use when diagnosing or fixing pytest failures.
tags: [python, pytest, testing]
---

When this skill is active:
- reproduce the failure first
- isolate the failing test
- prefer the smallest fix that restores the intended contract
```

Required metadata:

- `name`
- `title`
- `summary`

Optional metadata:

- `tags`

### Skill Index Versus Skill Body

The model should always see a compact index of available skills, but it should not receive every full skill body by default.

The request should contain two distinct layers:

1. a compact skill index for discovery
2. full prompt bodies for session-active skills only

The index should include:

- `name`
- `title`
- short `summary`
- optional `tags`

This keeps discovery cheap while letting the model request more context only when useful.

### Explicit Skill Loading Contract

Skill selection should use an explicit runtime capability rather than a prompt-only convention.

Add a dedicated tool such as:

- `load_skill(name)`

Behavior:

- the model sees the skill index in the prompt
- when it determines a skill is useful, it calls `load_skill`
- the runtime resolves the skill file, returns the full body, and marks the skill active in the current session

This gives the model a clear contract and keeps replay/audit behavior explicit.

### Unified User And Model Activation

User-selected and model-selected skills should share one session state model.

Both paths should populate the same `active_skills` list. The only difference should be activation source metadata such as:

- `user`
- `model`

This keeps runtime behavior consistent and avoids two different code paths for prompt injection.

## Runtime Behavior

### Request Assembly Order

Each turn should build model messages in this order:

1. base system prompt
2. compact global skill index
3. full bodies of active skills as top-of-context overlay messages
4. compacted summary and recent conversation turns
5. current user message

This keeps active skills in the highest-attention region of the prompt without mixing them into normal transcript history.

### Model Guidance

The base system prompt should explicitly tell the model to:

- evaluate whether the current task needs a skill
- consult the skill index before acting on non-trivial work
- use the skill-loading tool when a listed skill is relevant
- avoid loading unnecessary skills

That keeps the model from treating skills as mandatory for every task.

### User Interaction

The first user-facing control surface should be the existing slash-command system.

Recommended commands:

- `/skills`
- `/skills use <name>`
- `/skills drop <name>`
- `/skills clear`
- `/skills show <name>` for optional preview

The existing command palette and completion behavior should surface matching skills after `/skills use ` and `/skills drop `.

### Skill Activation Semantics

Once a skill is loaded through either the user command path or the model tool path, it becomes active for the current session until removed.

That means:

- the current turn can use the loaded skill immediately
- future turns re-inject that skill automatically
- the user or runtime must explicitly remove the skill for it to stop applying

This matches the goal of remembering skills across the session while keeping the canonical text outside compacted conversation history.

## Session State And Persistence

### Session Metadata

Active skills should be stored as session metadata, not as repeated raw transcript messages.

Recommended `meta.json` additions:

```json
{
  "id": "session-abc123",
  "project_key": "repo-1234abcd",
  "workspace_path": "/abs/path/to/repo",
  "active_skills": [
    {
      "name": "python-tests",
      "title": "Python Test Fixing",
      "hash": "sha256:...",
      "activated_at": "2026-03-27T09:00:00Z",
      "source": "model"
    }
  ]
}
```

The session transcript files should remain conversation-oriented:

- `messages.jsonl` for user, assistant, and tool messages
- `events.jsonl` for timeline replay
- `journal.jsonl` and `evidence.jsonl` for layered context evidence

### Canonical Skill Source

The canonical skill body should always remain the file under `~/.deepcode/skills/`.

Session state should remember only:

- which skills are active
- activation source
- a content hash for debugging and change detection

The runtime should rebuild active skill prompt bodies from disk on each turn.

## Compaction And Context Policy

### Skills Must Not Be Compacted

Auto-compaction should operate only on conversation history. It must not:

- summarize active skill bodies
- rewrite active skill bodies
- drop active skills from session state

After compaction, the next request should still be rebuilt as:

1. base system prompt
2. skill index
3. active skill bodies from disk
4. compacted summary plus recent turns
5. current user input

This is the key rule that preserves skill fidelity across long sessions.

### Why Not Store Skill Bodies As Transcript Messages

Persisting full skill bodies as normal session messages would make the system harder to maintain because it would:

- clutter replay and transcript history
- force compaction logic to special-case transcript entries permanently
- duplicate the same prompt text across many turns
- make later prompt assembly changes harder

The skill system should therefore use request-time injection, not transcript duplication.

## Replay And Events

Replay should expose skill activity without dumping full skill bodies into the visible chat transcript every turn.

Recommended timeline events:

- `skill_loaded`
- `skill_activated`
- `skill_dropped`
- `skill_missing` when a previously active skill file cannot be loaded

Recommended event payload:

- `name`
- `title`
- `source`
- `hash`

This keeps replay auditable while avoiding repeated prompt noise.

## Failure Handling

### Unknown Skill

- `/skills use <name>` should return a warning message
- `load_skill(name)` should return a tool error

### Missing Active Skill File

If an already-active skill file disappears before a later turn:

- the runtime should skip injecting that skill body
- emit a warning event such as `skill_missing`
- continue the session instead of failing the whole turn

### Edited Skill File

If a skill file changes after activation, the next turn should use the latest file contents from disk.

The stored hash exists mainly for:

- debugging
- replay visibility
- future UX improvements

It should not freeze the session onto an old snapshot in v1.

## Testing Strategy

Add tests for:

- skill discovery from `~/.deepcode/skills/`
- skill metadata parsing and validation
- `/skills` listing and active-state indicators
- `/skills use`, `/skills drop`, and `/skills clear`
- `load_skill` activating a session skill
- prompt assembly placing active skills above conversation history
- compaction preserving active skill injection across later turns
- missing skill files failing safely with warning events

## Implementation Notes

- Keep `DeepCodeApp` thin. It should delegate skill state changes to a command/tool layer rather than parsing skill files directly.
- Extend existing session persistence instead of introducing a second session-state store.
- Keep the context strategy responsible for conversation history only; skill overlays should be assembled outside compaction logic.
- Reuse the current slash-command completion patterns rather than adding a new TUI selection surface in v1.
