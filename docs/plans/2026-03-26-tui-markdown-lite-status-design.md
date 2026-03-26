# TUI Markdown-Lite And Busy Status Design

**Date:** 2026-03-26

## Goal

Render common markdown formatting in chat messages without taking on full-markdown cost, and add a subtle breathing effect to the agent status while the harness is busy.

## Approved Behavior

- Chat messages should render markdown-lite for the common cases:
  - paragraphs
  - bullet lists
  - bold / italic
  - inline code
  - fenced code blocks
  - blockquotes
- Unsupported markdown should remain readable plain text instead of attempting full Rich markdown support.
- Tool call, tool output, diff, and usage blocks should keep the current low-cost rendering path.
- The busy animation should appear only while the agent is working:
  - `running`
  - `tool:*`
- Idle status should stay static.

## Design

### Timeline Structure

Replace the current single flat text timeline with a block container that mounts one widget per timeline event.

This keeps replay and live event handling aligned while letting message blocks use richer rendering than tool blocks. The TUI still owns presentation concerns; the harness event contract remains unchanged.

### Message Rendering

Add a dedicated message widget for `message_committed` events.

The widget should:

- render user messages with the existing role distinction
- parse markdown-lite only for message text
- convert supported markdown patterns into Rich renderables that Textual can mount efficiently
- preserve whitespace where fenced code blocks and quotes need it

Parsing should happen once when the event block is appended or replayed. The app should store widgets/renderables per block instead of rebuilding a single concatenated `Text` value on every update.

### Status Animation

Replace the raw `Static` status strip text with a small dedicated widget that tracks:

- project name
- session id
- model name
- turn state
- optional command feedback

Only the turn-state segment should animate. When the state becomes busy, the widget should start a low-frequency timer that alternates between two nearby visual intensities to simulate a slow breathing pulse. When the state returns to idle, the timer should stop and the static style should be restored immediately.

## Testing Strategy

Add or update tests for:

- markdown-lite parsing of inline styles, bullets, fences, and quotes
- loaded-session replay still showing existing events
- live events still append correctly and keep scroll-pin behavior
- busy state enabling the status animation
- idle state disabling the status animation
