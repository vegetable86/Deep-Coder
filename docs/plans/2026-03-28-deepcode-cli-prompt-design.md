# DeepCode CLI Prompt Design

## Goal

Rewrite the DeepCode system prompt so it matches the actual CLI runtime: a terse project-scoped coding agent with layered session context, structured local tools, and a timeline that already shows operational detail.

## Scope

- Keep the strict CLI communication style from the new prompt draft.
- Preserve project-scoped identity using the current workspace and current session id.
- Teach the model to judge whether the current message is already sufficient before retrieving more context.
- Encode the three-layer history policy:
  - current visible context first
  - compact summary-first retrieval next
  - exact evidence expansion last
- Tell the model to prefer stronger evidence over guessing when information is vague.
- Align tool guidance with real builtin tools only.
- Keep the prompt compact enough to send on every turn.

## Non-Goals

- Do not restate full tool schemas in the prompt.
- Do not describe unsupported capabilities such as web access, cross-project browsing, subagents, or package managers the runtime does not own.
- Do not rely on generic agent conventions that conflict with the TUI timeline.
- Do not remove the strict CLI style in favor of a more verbose assistant voice.

## Current Gaps To Fix

1. The renderer currently returns malformed output because it joins a single string character-by-character.
2. The file mixes two prompt drafts at once, which leaves conflicting policy in one renderer.
3. The prompt does not describe the actual layered retrieval order used by the runtime.
4. The prompt tells the model to use “search tools extensively” without teaching the specific difference between `search_history` and `load_history_artifacts`.
5. The prompt does not teach the model to search with concrete anchors such as files, functions, errors, decisions, constraints, or task subjects.
6. The prompt over-explains task-tool usage for a CLI that should stay quiet unless the task is genuinely multi-step.
7. The prompt does not tell the model to rely on the timeline for tool-call and diff detail, which risks chat over-narration.
8. The prompt lacks a final fallback for unclear context after retrieval; it should ask one short clarifying question instead of guessing.

## Approach

Render one coherent prompt body with six parts:

1. Identity and strict CLI style
2. Action policy and non-trivial intent line
3. Tool usage policy aligned to real DeepCode tools
4. Context sufficiency and three-layer retrieval policy
5. Task and verification policy tuned for CLI noise control
6. DeepCode-specific examples

The prompt should explicitly tell the model:

- answer directly if the current message and visible context are enough
- avoid unnecessary tool calls when the answer is already clear
- search compact history first when prior context may matter
- expand to exact evidence only when summary recall is insufficient or exact wording, arguments, output, diffs, or evidence matter
- prefer precise retrieval terms over vague queries
- ask one short clarifying question if current context plus compact recall plus evidence still do not support a strong answer

## Prompt Rules

- Keep responses terse by default.
- Avoid filler, long preambles, and long post-action summaries.
- Before a non-trivial action, send one short intent sentence.
- Do not guess about code, prior session decisions, or filesystem state when the tools can inspect them.
- Prefer `read_file` for targeted reading, `edit_file` or `write_file` for workspace edits, and `bash` for commands, tests, or inspection that file tools do not cover cleanly.
- Use task tools for genuine multi-step work, not for one-shot answers.
- Let the TUI timeline carry tool-call, output, diff, usage, and task detail.
- When history matters, prefer compact retrieval via `search_history` before exact expansion via `load_history_artifacts`.
- Search compact history with concrete anchors when possible.
- Escalate to evidence only when compact history is ambiguous or exact detail is required.
- Ask a short clarification question instead of inventing missing context.

## Files

- `deep_coder/prompts/deepcoder/prompt.py`
- `tests/prompts/test_deepcoder_prompt.py`
- `tests/harness/test_deepcoder_harness.py`

## Verification

- Add targeted prompt assertions for context sufficiency, summary-first recall, evidence escalation, and CLI-specific task/tool guidance.
- Run the prompt tests first during TDD.
- Re-run the harness prompt-injection regression test because it depends on prompt output.
- Run the full suite after the rewrite.
