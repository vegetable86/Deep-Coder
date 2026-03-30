# Question System Design

## Overview
A harness-level question capability that allows the model to present structured choices to users when it determines a question requires convergence of ideas. The system presents 2-3 recommended approaches plus a user-inputtable option in a navigable TUI interface. This is distinct from normal assistant clarifying questions and is used for decision points requiring user direction.

## When to Use This vs Normal Assistant Questions

**Normal Assistant Questions** (current prompt):
- Simple clarifying questions
- Single answer expected
- Model continues immediately after user responds
- Used when "current view plus compact history plus evidence are still not enough"

**Question System** (new capability):
- When model judges question should "converge ideas"
- Multiple approach options (2-3) plus user-inputtable option
- Structured choice presentation with navigation
- Model pauses execution, waits for structured response
- Used for decision points requiring user direction

## Architecture

### Core Components

1. **Bidirectional IPC Channel** (`deep_coder/harness/turn_subprocess.py`)
   - Extend subprocess to accept events via stdin
   - Maintain stdout event stream for harness → TUI
   - New `TurnSubprocessClient` in TUI for sending responses

2. **Harness Pause/Resume API** (`deep_coder/harness/deepcoder/harness.py`)
   - `harness.ask_question()` method for structured questions
   - Pauses execution, yields control to TUI
   - Resumes with user selection

3. **AskQuestionTool** (`deep_coder/tools/ask_question/`)
   - Tool interface for models to request structured user input
   - Parameters: `question_text`, `options` (2-3 items), `allow_custom` (default: true)
   - Returns: JSON string with `question_id` and `status`

4. **QuestionScreen** (`deep_coder/tui/screens/question_screen.py`)
   - TUI screen for displaying structured questions
   - Navigable list with arrow keys
   - Custom input field when `allow_custom=true`
   - Similar UI pattern to CommandPalette

### Event Types

1. **question_presented** (persisted, replayable)
   - `question_id`: unique identifier for correlation
   - `question_text`: the question to display
   - `options`: array of 2-3 choice strings
   - `allow_custom`: boolean for custom input

2. **question_answered** (persisted, replayable)
   - `question_id`: matches presented question
   - `selected_option`: chosen option text
   - `is_custom`: boolean indicating custom input
   - `custom_text`: custom input if applicable

### Data Flow

**Live Session:**
```
Model → AskQuestionTool → harness.ask_question() → question_presented event → TUI
TUI → QuestionScreen → user selects → question_answered event → harness resumes → Model
```

**Replay Session:**
```
Load events → question_presented → show question → question_answered (from storage) → continue
```

### Tool Interface

```python
# Tool call format
{
  "question_text": "How should we implement the authentication system?",
  "options": ["Use OAuth with Google", "Implement email/password", "Use API keys"],
  "allow_custom": true
}

# Return format (JSON string)
{
  "question_id": "abc123",
  "status": "awaiting_user_input"
}
```

**User Response Format** (as next user message):
```json
{
  "question_id": "abc123",
  "selected_option": "Use OAuth with Google",
  "is_custom": false
}
```

## Implementation Details

### Bidirectional IPC Protocol
```python
# Turn subprocess reads stdin for incoming events
while True:
    line = sys.stdin.readline()
    if line:
        event = json.loads(line)
        if event["type"] == "question_answered":
            handle_question_response(event)

# TUI sends responses via TurnSubprocessClient
client = TurnSubprocessClient(process)
client.send_question_response(question_id, selection, is_custom)
```

### Harness Pause/Resume API
```python
class DeepCoderHarness:
    def ask_question(self, question_text, options, allow_custom=True):
        question_id = generate_id()
        # Emit question_presented event (persisted)
        self._publish(session, event_sink, {
            "type": "question_presented",
            "question_id": question_id,
            "question_text": question_text,
            "options": options,
            "allow_custom": allow_custom
        })
        
        # Pause execution, wait for response
        response = self._wait_for_question_response(question_id, timeout=30)
        
        # Emit question_answered event (persisted)
        self._publish(session, event_sink, {
            "type": "question_answered",
            "question_id": question_id,
            "selected_option": response["selected_option"],
            "is_custom": response["is_custom"],
            "custom_text": response.get("custom_text", "")
        })
        
        return response
```

### AskQuestionTool
- Validates options (must be 2-3 items)
- Calls `harness.ask_question()` with parameters
- Returns JSON string with `question_id` and `status`
- Model sees this as tool output, knows execution is paused

### QuestionScreen
- Displays question text prominently
- Shows options as selectable list items
- If `allow_custom=true`, includes "Enter custom approach" option
- Custom input field appears when custom option selected
- Navigation with arrow keys, selection with Enter
- Sends response via TurnSubprocessClient

### Event Persistence & Replay
- Both `question_presented` and `question_answered` events are persisted
- During replay: show question, but selection comes from stored answer
- Events must be in correct order for deterministic replay
- TUI renderer must handle both event types

## Integration Points

1. **Bidirectional IPC** (`deep_coder/harness/turn_subprocess.py`)
   - Extend subprocess to read stdin for incoming events
   - Create `TurnSubprocessClient` for TUI to send responses
   - Maintain existing stdout event stream

2. **Harness Extension** (`deep_coder/harness/deepcoder/harness.py`)
   - Add `ask_question()` method to DeepCoderHarness
   - Implement pause/resume mechanism
   - Handle question response waiting with timeout

3. **Tool Registration** (`deep_coder/tools/registry.py:from_builtin`)
   ```python
   # Add to tool list
   AskQuestionTool(config=config, workdir=workdir)
   ```

4. **TUI Event Handling** (`deep_coder/tui/app.py`)
   - Add handler for `question_presented` events
   - Show QuestionScreen when event received
   - Send response via TurnSubprocessClient
   - Handle `question_answered` events during replay

5. **Event System** (`deep_coder/harness/events.py`)
   - Add new event types to event registry
   - Ensure proper serialization/deserialization

## Error Handling

1. **User Cancellation**: If user cancels (ESC), harness returns `{"error": "user_cancelled"}`
2. **Invalid Options**: Tool validates before calling harness, returns `{"error": "invalid_options"}`
3. **Timeout**: 30-second timeout, harness returns `{"error": "timeout"}`
4. **Custom Input Validation**: Basic non-empty validation, returns `{"error": "empty_custom_input"}`
5. **TUI Disconnect**: Detect broken IPC connection, return `{"error": "tui_disconnected"}`
6. **Replay Consistency**: Ensure question/answer pairs match during replay, log mismatch

## Testing Strategy

1. **Unit Tests**: Tool validation, event parsing, harness pause/resume logic
2. **Integration Tests**: Bidirectional IPC, tool-harness-TUI communication
3. **UI Tests**: QuestionScreen navigation and input
4. **Replay Tests**: Ensure question/answer events replay correctly
5. **Model Tests**: Example model prompts using the tool
6. **Subprocess Tests**: Cross-process communication and error handling

## Success Criteria

1. Model can present structured questions with 2-3 options via harness API
2. Users can navigate and select options with arrow keys in TUI
3. Users can enter custom approaches when allowed
4. Harness pauses execution, waits for user response via bidirectional IPC
5. User response flows back to harness, execution resumes
6. All events are persisted and replayable
7. System handles edge cases (cancellation, timeout, errors)
8. Replay sessions show questions and use stored answers

## Dependencies

- Existing TUI framework (Textual)
- Current tool execution system
- Event communication infrastructure
- Subprocess management for bidirectional IPC
- Session persistence for replay support

## Open Questions

1. **IPC Protocol Details**: JSONL over stdin/stdout vs separate socket channel
2. **Blocking Implementation**: Thread-based waiting vs async/await in harness
3. **Model Training**: When should model use this vs normal clarifying questions?
4. **Error Recovery**: Should model retry with different options on cancellation?
5. **Timeout Handling**: Should there be a default fallback option on timeout?
6. **Custom Input Validation**: Beyond non-empty, any format requirements?
7. **Question ID Generation**: UUID vs incremental vs hash-based
8. **Replay UI**: Should questions be interactive during replay or read-only?

## Implementation Phases

### Phase 1: Bidirectional IPC Foundation
1. Extend `turn_subprocess.py` to read stdin for incoming events
2. Create `TurnSubprocessClient` for TUI to send responses
3. Test basic cross-process communication

### Phase 2: Harness Pause/Resume API
1. Add `ask_question()` method to DeepCoderHarness
2. Implement event waiting with timeout
3. Add `question_presented` and `question_answered` event types
4. Test harness-level question flow

### Phase 3: Tool Implementation
1. Create AskQuestionTool that calls harness API
2. Add tool to registry
3. Test tool validation and error cases

### Phase 4: TUI Integration
1. Create QuestionScreen component
2. Add event handlers in app.py
3. Implement TurnSubprocessClient usage
4. Test UI navigation and input

### Phase 5: Replay Support
1. Ensure events are persisted correctly
2. Handle replay path in TUI renderer
3. Test replay consistency

### Phase 6: Error Handling & Polish
1. Add comprehensive error handling
2. Test edge cases (timeout, cancellation, disconnect)
3. Documentation and examples