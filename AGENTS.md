# Deep Coder Agent Guide

## Source Of Truth

- The active product now includes both the backend runtime and the first project-scoped TUI.
- Authoritative code lives under `deep_coder/` plus the checked-in launcher script `deepcode`.
- `agentLoop.py` is still a legacy prototype and reference file. It is not the main entrypoint and it is not the authoritative implementation.
- When behavior in `agentLoop.py` and `deep_coder/` differ, follow `deep_coder/`.

## Current Product Shape

The current shipped flow is:

1. User `cd`s into a workspace.
2. User launches `deepcode`.
3. `deep_coder/cli.py` resolves the current directory into a project record.
4. Runtime state is rooted under `~/.deepcode/projects/<project-key>/`.
5. The Textual app renders one timeline plus a bottom composer/status strip.
6. Submitting from the composer runs the harness and streams live events into the timeline.
7. Session replay and session switching are limited to the active project.

The product is no longer just a backend runtime. It is now a terminal application built on top of that runtime.

## Current Architecture

The project is a package-based single-agent coding runtime with a TUI layer on top of clear module boundaries:

- `deep_coder/cli.py`
  - Launch bootstrap.
  - Resolves `pwd` into a project and starts the TUI.
- `deepcode`
  - Checked-in launcher script.
- `deep_coder/main.py`
  - Composition root.
  - Builds config, model, tools, prompt, context manager, and harness.
- `deep_coder/projects/`
  - Project registry and workspace identity.
  - Maps a workspace path to a persistent `project_key` and `state_dir`.
- `deep_coder/tui/`
  - Textual application, timeline rendering, and modal screens.
  - Owns composer submission, replay, and live event display.
- `deep_coder/harness/`
  - Runtime orchestration.
  - Opens sessions, prepares messages, calls the model, runs tools, records chat history, and emits timeline events.
- `deep_coder/models/`
  - Model adapters.
  - Current provider is DeepSeek through the OpenAI-compatible Python SDK.
- `deep_coder/tools/`
  - Tool contracts plus builtin local coding tools.
  - Current builtin tools: `bash`, `read_file`, `write_file`, `edit_file`.
- `deep_coder/prompts/`
  - System prompt rendering.
- `deep_coder/context/`
  - Session persistence and message assembly.
  - Includes a stable `ContextManager`, a filesystem session store, and a simple append-only history strategy.

## Runtime Flow

The intended current flow is:

1. Resolve the active workspace and register or reopen it through `ProjectRegistry`.
2. Build runtime from `deep_coder.main.build_runtime(project=...)`.
3. Start `DeepCodeApp`.
4. Open or create a project-scoped session through the context layer.
5. Render the active system prompt.
6. Assemble request messages from session history plus current user input.
7. Call the model adapter.
8. Execute returned tool calls through the tool registry.
9. Record assistant/tool chat messages into session history.
10. Emit structured timeline events for replay and live TUI updates.
11. Flush the session to storage.
12. Stop when the model returns a final assistant answer.

## Design Principles

- `Harness` is the orchestrator and should stay thin.
- `Model` only handles provider communication and normalized responses.
- `Tools` expose machine-readable schemas and local execution entrypoints.
- `Prompt` modules render the active system prompt without owning runtime orchestration.
- `Context` owns session persistence and message history assembly.
- `Projects` own workspace identity and project-scoped state roots.
- `TUI` owns presentation, replay, session switching, and user interaction wiring, not backend policy.
- Extension points should be added by implementing concrete classes behind the existing base contracts, not by collapsing boundaries back into one file.
- Machine-readable metadata belongs in methods like `schema()` and `manifest()`, not in comments.

## Current Boundaries

What exists now:

- single-agent runtime
- DeepSeek model adapter
- OpenAI-compatible SDK integration
- local coding tools
- project registry under `~/.deepcode/config.toml`
- project-scoped session storage
- persisted chat history and persisted timeline events
- Textual TUI with:
  - top timeline
  - bottom composer/status strip
  - modal session switcher
  - live harness event streaming
  - session replay
- checked-in `deepcode` launcher

What is intentionally still thin or out of scope:

- no packaged install flow or console-script entrypoint beyond `deepcode`
- no global mixed-project session browser
- no advanced timeline folding, pagination, or virtualization
- no advanced context compaction yet
- no retry/backoff policy yet in the DeepSeek adapter
- no package-level subagent orchestration
- no background job manager
- no task graph runtime

Some of those ideas appear in `agentLoop.py`, but they are prototype ideas, not current product behavior.

## Persistence And Config

- The runtime expects `DEEPSEEK_API_KEY` in the environment.
- Default runtime state lives under `~/.deepcode/`.
- The project registry lives at:
  - `~/.deepcode/config.toml`
- Project-scoped state lives at:
  - `~/.deepcode/projects/<project-key>/`
- Session storage currently uses:
  - `sessions/<session-id>/meta.json`
  - `sessions/<session-id>/messages.jsonl`
  - `sessions/<session-id>/events.jsonl`
  - `sessions/<session-id>/context/<strategy-name>/state.json`

## Development Rules

- Do not treat `agentLoop.py` as the main entrypoint.
- Prefer changes inside `deep_coder/` and `deepcode` unless the task is explicitly about the prototype.
- Preserve the existing package boundaries when adding features.
- Add new tools, providers, prompts, stores, strategies, screens, or registry behavior as modular implementations instead of folding logic into the app shell.
- Keep file and command access workspace-bounded unless a task explicitly requires broader access.
- Keep runtime state out of the repository; use `~/.deepcode/` or explicit overrides.
- When changing TUI behavior, make sure replay and live event paths stay aligned.

## Git Worktree Convention

When doing branch-based development:

1. Do not work directly from the repository root working tree.
2. Create dedicated worktrees under `.worktrees/` at the repository root.
3. Use concise task-oriented branch names such as `feat/...` or `fix/...`.
4. Remove worktrees after merge.

Commands:

```bash
git worktree add -b <branch-name> .worktrees/<branch-name> HEAD
cd .worktrees/<branch-name>
git worktree remove .worktrees/<branch-name>
git branch -d <branch-name>
```

## Environment And Verification

- Use the project venv, not the system Python:
  - `source /home/wys/deep-code/.venv/bin/activate`
  - or call `/home/wys/deep-code/.venv/bin/python` and `/home/wys/deep-code/.venv/bin/pytest` directly
- In this repository, plain `pytest` on `PATH` may resolve to system Python and miss `textual`.
- Preferred verification commands:
  - `python3 -m pytest -q`
  - `/home/wys/deep-code/.venv/bin/pytest -q`
- Run the full suite after meaningful runtime or TUI changes.

## Practical Guidance For Future Agents

- Start by reading:
  - `deep_coder/cli.py`
  - `deep_coder/tui/app.py`
  - `deep_coder/main.py`
  - `deep_coder/harness/deepcoder/harness.py`
  - `deep_coder/projects/registry.py`
  - `arch/arch.md`
- Use `agentLoop.py` only as a roadmap for future capabilities or historical context.
- If you need to add a feature that exists in the prototype but not in the package runtime, implement it as a modular `deep_coder/` feature instead of copying prototype structure forward.
- For branch history and implementation context, read:
  - `docs/history/2026-03-25-deep-coder-backend-runtime-history.md`
  - `docs/history/2026-03-26-harness-backend-tui-history.md`
