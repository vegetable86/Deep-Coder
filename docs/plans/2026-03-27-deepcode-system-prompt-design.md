# DeepCode System Prompt Design

## Goal

Replace the current minimal system prompt with a DeepCode-specific runtime prompt that sets the model role, reasoning style, retrieval behavior, and communication tone without duplicating tool schemas that are already injected separately.

## Scope

- Keep the prompt project-scoped to the current workspace and active session.
- Define DeepCode as a reasoning-first coding agent.
- Instruct the model to briefly explain intent before taking non-trivial actions.
- Tell the model to use available tools when more information is needed.
- Prefer summary-first history recall and expand to original artifacts only when exact detail matters.
- Use a few short examples to anchor tone and workflow.

## Non-Goals

- Do not restate full tool schemas in the prompt.
- Do not describe TUI widgets, replay mechanics, or timeline rendering behavior.
- Do not claim capabilities that do not exist, such as global memory, cross-project browsing, web access, or subagents.
- Do not add vendor-style branding or long policy boilerplate.

## Approach

Render a structured prompt with six parts:

1. Identity and mission
2. Behavior and action style
3. Information-gathering guidance
4. Session history policy
5. Reasoning and response style
6. Short examples

The prompt should remain compact enough to be sent on every turn, but explicit enough to stabilize behavior across code-editing, debugging, and explanation tasks.

## Prompt Rules

- Include the current workspace path.
- Include the current session id.
- Mention that tool schemas are provided separately.
- State that the model should not guess when it can inspect or retrieve.
- State that non-trivial actions should be preceded by one short intent sentence.
- State that repository patterns and nearby implementations are the default template.
- State that session task tools should be used for multi-step work.
- State that summary-first history retrieval is preferred over loading raw artifacts.
- State that raw history should be loaded only when summary is insufficient or exact evidence matters.
- Keep the model tone analytical, calm, pragmatic, direct, and concise.

## Files

- `deep_coder/prompts/deepcoder/prompt.py`
- `tests/prompts/test_deepcoder_prompt.py`

## Verification

- Prompt-specific tests should assert workspace/session context plus key behavioral guidance.
- Run targeted prompt tests during TDD.
- Run the full suite after the prompt change.
