# Init Command Design

**Date:** 2026-03-28

## Goal

Design a project-scoped `/init` command for the Deep Coder TUI that generates or refreshes a concise `DEEP.md` file. `DEEP.md` should act as a human-editable project editing guide that helps the model navigate a stranger codebase, find the right files to inspect or edit, and avoid non-authoritative paths.

## Product Scope

Version 1 of `/init` should:

- exist as a built-in TUI slash command: `/init`
- operate on the active workspace already resolved by `deep_coder/cli.py`
- create or refresh `DEEP.md` in the workspace root
- keep `DEEP.md` concise and map-like instead of writing a full project summary
- preserve human notes outside the generated block
- persist lightweight refresh metadata under the project state root

Version 1 should not:

- auto-run on the first user turn
- mutate `AGENTS.md`
- require `AGENTS.md` to exist
- attempt to explain project implementation in depth
- recursively summarize the entire repository
- add a separate non-TUI bootstrap path before the command behavior is stable

## Core Decisions

### `/init` Is A Built-In Project Command

- `/init` belongs in the existing TUI command system.
- It should run only while the runtime is idle, like the other built-in commands.
- The initial surface area is one command with no required arguments.
- A later `deepcode init` alias can be added once the behavior is proven in the TUI, but that is not needed for v1.

This keeps initialization aligned with the current shipped product shape instead of inventing a second top-level workflow.

### `DEEP.md` Is A Project Editing Guide

`DEEP.md` is not a design document, architecture deep dive, or implementation summary. It is a concise editing map for the agent and for humans.

It should help answer:

- where the real entrypoint is
- where to start reading for a given kind of change
- where new code should go
- where tests for a subsystem likely live
- what paths are legacy, generated, or otherwise non-authoritative
- what commands should be used to verify changes

It should not attempt to preserve all implementation details or historical context.

### Workspace Scope Wins Over Git Root

- The command should operate on the active workspace path from `ProjectRecord.path`.
- It should write `DEEP.md` at that workspace root.
- If the workspace is inside a larger git repository, `/init` should not silently climb upward and redefine the project scope.

This matches the existing product rule that the current `pwd` is the active project boundary.

### `AGENTS.md` Is Optional Input

- `AGENTS.md` may be consulted if present.
- `AGENTS.md` must not be required.
- Missing `AGENTS.md` must not count as an error or confidence loss on its own.
- `/init` must never update `AGENTS.md`.

`DEEP.md` should be generated from repository evidence first, not from agent-specific files.

## Evidence And Attention Model

When scanning a stranger project, `/init` should bias attention in this order:

1. existing `DEEP.md`
2. `README*`, `CONTRIBUTING*`, `docs/`, `arch/`
3. manifests, build files, test config, and CI workflows
4. actual launch scripts, entrypoints, and composition roots
5. optional `AGENTS.md`
6. heuristic source inspection outward from the most likely entrypoints

The scan should prioritize evidence that answers:

- what users actually run
- where the authoritative code lives
- how changes are verified here
- what files should not be treated as source of truth

The model should not begin with a recursive tree summary. It should first locate instruction, execution, verification, and boundary signals.

## Scan Strategy

### High-Signal Inputs

Expected high-value inputs include:

- `DEEP.md`
- `README*`
- `CONTRIBUTING*`
- `docs/`
- `arch/`
- `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`
- `Makefile`, `justfile`, `Taskfile`
- `pytest.ini`, `tox.ini`, typecheck and lint config
- `.github/workflows/`
- checked-in launchers such as scripts in `bin/`, `scripts/`, or project root

### Default Ignore Set

The scan should ignore directories and outputs that are unlikely to be useful for a concise editing guide, including:

- `.git/`
- `node_modules/`
- `.venv/`, `venv/`
- `dist/`, `build/`, `.next/`
- coverage and cache directories
- large generated artifacts and vendored dependencies

### Stop Rule

`/init` should stop scanning once it has enough evidence to populate a correct editing map for:

- project shape
- real entrypoints
- common edit locations
- verification commands
- edit boundaries and paths to avoid
- unresolved uncertainties

The command is not a repo summarizer. It should stop once it can produce a useful navigation guide with reasonable confidence.

## `DEEP.md` Contract

`DEEP.md` should be concise, current, and flexible. It should not be rigidly confined to one permanent outline because the project will change over time.

The generated content should live inside an explicit managed block:

```md
# DEEP.md

<!-- deepcode:init:start -->
Last refreshed: 2026-03-28

## Project Map
- `deep_coder/cli.py`: launch bootstrap
- `deep_coder/tui/`: TUI shell and slash commands

## Start Here
- Launch flow starts at `deepcode`

## Common Edits
- Change runtime loop: `deep_coder/harness/deepcoder/harness.py`

## Verification
- `/home/wys/deep-code/.venv/bin/pytest -q`

## Boundaries
- `agentLoop.py` is legacy reference, not the main entrypoint
<!-- deepcode:init:end -->

## Human Notes
```

Rules for the generated block:

- keep it short, typically around 15-40 lines
- prefer bullets over long prose
- include only repo-specific guidance
- choose headings based on the repo instead of enforcing one fixed schema
- mark uncertainty explicitly instead of guessing
- focus on edit navigation, not implementation explanation

## Refresh And Merge Semantics

Refreshing `DEEP.md` should:

- create the file if it does not exist
- replace only the managed generated block if it already exists
- preserve manual notes outside the managed block
- re-check old claims against current repository evidence instead of trusting prior generated text
- remove stale generated claims rather than accumulating historical noise

The output should be a living brief of the current workspace, not an archive of every previous repository shape.

## Conflict And Confidence Rules

When sources disagree, `/init` should prefer:

1. explicit repository docs and maintained instruction files
2. checked-in launch, test, and build configuration
3. checked-in README and architecture notes
4. optional `AGENTS.md`
5. heuristic inference from source layout

If ambiguity remains after those checks, `DEEP.md` should record the ambiguity briefly instead of inventing certainty.

## Persistence

`/init` should persist only minimal refresh metadata under the project state directory, for example under:

- `<project.state_dir>/deep/init-state.json`

Suggested fields:

- `last_refreshed_at`
- `workspace_path`
- `deep_file_path`
- `sources`
- `source_mtimes` or hashes
- `uncertainties`

This state is for refresh decisions only. It should not become a second project brief.

## User Feedback

For v1, `/init` should keep feedback lightweight:

- update the TUI status strip with a short success or failure message
- optionally report which sources were used and whether `DEEP.md` was created or refreshed

Explicit preview and confirmation flows are out of scope for the first slice unless later UX work justifies them.

## Testing Strategy

Coverage should include:

- source discovery without `AGENTS.md`
- workspace-bounded scanning behavior
- ignore rules for generated and dependency directories
- `DEEP.md` block replacement while preserving human notes
- refresh metadata persistence
- `/init` command registry behavior
- TUI command execution that creates or refreshes `DEEP.md`
