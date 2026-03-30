# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable dev mode)
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e ".[dev]"

# Run tests
./.venv/bin/pytest -q

# Run a single test file
./.venv/bin/pytest tests/path/to/test_file.py -q

# Run the agent (requires DEEPSEEK_API_KEY)
export DEEPSEEK_API_KEY="your-key"
cd /path/to/workspace && deepcode
```

No linting tools are configured.

## Architecture

**Deep Coder** is a project-scoped terminal coding agent powered by the DeepSeek API. It launches as a Textual TUI, streams tool activity into a replayable timeline, and persists all state under `~/.deepcode/` (outside the repo).

**Core principle: Harness is the orchestrator; Model is the driver.**

### Module Map

| Module | Responsibility |
|---|---|
| `deep_coder/cli.py` | Entry point — resolve workspace → project, launch TUI |
| `deep_coder/main.py` | `build_runtime()` composition root |
| `deep_coder/config.py` | `RuntimeConfig` dataclass |
| `deep_coder/harness/deepcoder/harness.py` | Main turn loop orchestration |
| `deep_coder/models/deepseek/model.py` | DeepSeek API client (OpenAI SDK wrapper) |
| `deep_coder/tools/` | `ToolRegistry` + built-in tools (incl. `ask_user`, `web_search`) |
| `deep_coder/prompts/deepcoder/prompt.py` | System prompt renderer |
| `deep_coder/context/` | Session persistence + message assembly |
| `deep_coder/projects/registry.py` | Workspace → project mapping (`~/.deepcode/config.toml`) |
| `deep_coder/tui/app.py` | `DeepCodeApp` (Textual TUI) |
| `deep_coder/skills/registry.py` | Skill loader (markdown files from `~/.deepcode/skills/`) |
| `deep_coder/tasks/manager.py` | Session-scoped task tracking |

`agentLoop.py` in the repo root is a legacy prototype — do not treat it as authoritative.

### Turn Flow

```
User submits in TUI Composer
  → start_turn_subprocess(runtime, session_locator, user_input)
  → Harness.run():
      1. context.open(locator) → Session
      2. prompt.render(session_snapshot, tool_schemas) → system_prompt
      3. context.prepare_messages(...) → messages[]
      4. model.complete({"messages": [...], "tools": [...]}) → response
      5. For each tool_call: tools.execute(name, args) → ToolExecutionResult
      6. context.record_*(...)  +  emit TimelineEvent to TUI
      7. Repeat until final assistant response
      8. context.flush(session) → persist to filesystem

ask_user tool special flow:
  → tool writes question_asked event directly to sys.stdout (JSON line), flushes
  → tool blocks on sys.stdin.readline() waiting for answer
  ← TUI receives question_asked event, renders QuestionWidget inline in timeline
  ← user selects options (+ optional free-form "Other" input per question)
  ← TUI writes {"answers": {...}} JSON line to subprocess stdin
  → tool unblocks, returns answers as output_text to model
```

### Pluggable Abstractions

All major subsystems have base classes in `*/base.py`. New implementations can be added without touching the harness:

- `HarnessBase` → `DeepCoderHarness`
- `ModelBase` → `DeepSeekModel`
- `ToolBase` → built-in tools (ask_user uses stdin/stdout pipe for blocking user interaction; web_search is conditionally registered based on config)
- `PromptBase` → `DeepCoderPrompt`
- `SessionStoreBase` → `FileSystemSessionStore`
- `ContextStrategyBase` → `LayeredHistoryContextStrategy`

### Context Strategy

`LayeredHistoryContextStrategy` assembles request messages from:
1. A rolling summary of older turns (if compaction has run)
2. Recent N turns verbatim (default 3)
3. Current user input

Compaction uses the model itself (`ModelSummarizer`) to summarize older turns. It triggers automatically mid-turn when `prompt_tokens >= context_max_tokens * 0.9` (default: 128000). Only unsummarized entries older than the recent-turns window are compacted — content is never summarized twice. Configurable via `context_max_tokens` in `~/.deepcode/config.toml`.

### Session Persistence

Each session lives at `~/.deepcode/projects/<project-key>/sessions/<session-id>/`:

- `messages.jsonl` — chat history
- `events.jsonl` — timeline events (for TUI replay)
- `journal.jsonl` — chronological event log
- `evidence.jsonl` — tool call arguments + outputs
- `summaries.jsonl` — context compaction summaries
- `context/layered_history/state.json` — strategy state

### TUI

`DeepCodeApp` (Textual) has two main panes:
- **Composer** (bottom): TextArea for input — locked while `_turn_state == "waiting_for_user"`
- **Timeline** (top): streams `TimelineEvent`s rendered via `render.py`; hosts live `QuestionWidget` during `ask_user` calls

Key bindings: `Enter` submit, `Shift+Enter` newline, `/` command palette, `Ctrl+L` session switcher, `Ctrl+C` interrupt.

Slash commands: `/history`, `/session`, `/new`, `/model`, `/exit`.

**Status strip animation:** The `StatusStrip` shows a braille spinner (`⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`) at 80ms intervals (~12fps) when the turn is active. The spinner frame is prepended to the turn state label (e.g. `⠹ tool:think`). When idle, the spinner resets and the timer stops. Implemented in `StatusStrip._advance_spinner` / `_SPINNER_FRAMES` in `deep_coder/tui/app.py`.

### ask_user Tool

`deep_coder/tools/ask_user/tool.py` — model calls this to pause and ask the user one or more questions.

- Schema: `{ "questions": [{ "question": str, "options": [{ "label": str, "description": str }] }] }`
- Each question gets an implicit "Other — type your own answer" option appended
- Writes `question_asked` event directly to `sys.stdout` before blocking on `sys.stdin`
- `TurnSubprocess.write_answer(json_str)` sends the answer back; stdin stays open for the turn lifetime
- TUI renders `QuestionWidget` (in `deep_coder/tui/widgets/question_widget.py`) inline in the timeline
- Session replay renders a static summary via `render_question_asked_block()` in `render.py`

### web_search Tool

`deep_coder/tools/web_search/tool.py` — model calls this to search the web via a configured third-party provider.

- Schema: `{ "query": str, "num_results": int (default 5), "fetch_content": bool (default false) }`
- Returns a JSON array of `{ title, url, snippet, content? }` objects as `output_text`
- If `fetch_content=true`, fetches each result URL with `httpx`, strips HTML tags/scripts/styles via `BeautifulSoup`, returns cleaned plain text in `content`; fetch failures set `content` to `"fetch failed: <reason>"`
- Search API failures return `is_error=True` with `output_text = "web_search failed: <reason>"`
- **Conditionally registered** — only added to `ToolRegistry` if `[web_search]` section exists in `~/.deepcode/config.toml`
- Provider is resolved at startup via `build_provider(config)` in `main.py` and stored in `RuntimeConfig.web_search_provider`

**Supported providers** (set `provider` key under `[web_search]` in config):

| Provider key | Class | Required config fields |
|---|---|---|
| `"google"` | `GoogleSearchProvider` | `api_key`, `cx` |
| `"serper"` | `SerperProvider` | `api_key` |
| `"brave"` | `BraveSearchProvider` | `api_key` |

**Config example (`~/.deepcode/config.toml`):**

```toml
[web_search]
provider = "serper"

[web_search.serper]
api_key = "your-key"
```

## Extending the Runtime

**New tool:** add `deep_coder/tools/<name>/tool.py` implementing `ToolBase`, register in `ToolRegistry.from_builtin()`.

**New model provider:** add `deep_coder/models/<provider>/model.py` implementing `ModelBase`, wire in `build_runtime()`.

**New context strategy:** add `deep_coder/context/strategies/<name>/strategy.py` implementing `ContextStrategyBase`, wire in `build_runtime()`.

## Key Docs

- `AGENTS.md` — developer guide, design principles, git worktree convention
- `arch/arch.md` — detailed architecture and base-class contracts
- `docs/history/` — implementation notes per feature
