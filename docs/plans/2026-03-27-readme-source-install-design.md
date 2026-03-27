# README And Source Install Design

**Date:** 2026-03-27

## Goal

Prepare Deep Coder for a public GitHub repository by adding a top-level `README.md` that explains the current product clearly and by adding a real source-install flow that exposes `deepcode` as a command after installation.

## Product Scope

This design adds:

- a repository-root `README.md`
- a Mermaid architecture diagram
- installation instructions for source installs that expose `deepcode`
- a package metadata file so `pip install .`, `pip install -e .`, and `pip install --user .` work

This design does not add:

- a PyPI release flow
- alternate model providers
- a packaged binary distribution
- a broader product restructure

## Core Decisions

### Source Install Becomes The Supported Onboarding Path

The repository currently ships a checked-in `deepcode` launcher script, but it does not expose a proper package install path. For an open-source repository, the README should document a supported install flow that works from a clean clone.

The minimal compatible approach is:

- add `pyproject.toml`
- publish a `deepcode = deep_coder.cli:main` console entrypoint
- keep the checked-in `deepcode` script for local development and historical continuity

This preserves current runtime behavior while making installation credible for outside users.

### README Prioritizes Quick Use, Then Contributor Context

The README should work as a GitHub landing page:

1. explain what Deep Coder is
2. show how to install and launch it quickly
3. explain the module boundaries and persistence model
4. document the current user-facing workflow

This fits the approved balanced audience: quick-start users first, contributors second.

### Mermaid Diagram Reflects The Shipped Product

The architecture diagram should follow `deepcode` through the actual runtime path:

- `deepcode`
- `deep_coder.cli`
- `ProjectRegistry`
- `build_runtime`
- `DeepCodeApp`
- `DeepCoderHarness`
- `DeepSeekModel`
- `ToolRegistry`
- `ContextManager`
- project state under `~/.deepcode/projects/<project-key>/`

The diagram should not present `agentLoop.py` as an active path.

## Documentation Structure

Recommended README sections:

- title and short description
- highlights
- installation
- quick start
- architecture
- user manual
- project state layout
- development and testing

## Testing Strategy

Add regression tests that prove:

- `pyproject.toml` exists and defines the `deepcode` console script
- runtime dependencies are declared in package metadata
- `README.md` exists, includes a Mermaid block, and documents source installation plus the key TUI commands

This keeps the packaging and documentation promises anchored to repository tests.
