# Prompt Tool Guidance Enhancement Design

## Overview
Enhance the Deep Coder prompt with specific tool usage examples and decision criteria, focusing on `think` and `web_search` tools while maintaining conciseness.

## Current State
The prompt has a "Tool Usage Policy" section with general guidelines but lacks concrete examples and specific decision criteria for key tools.

## Design

### Enhanced Tool Usage Policy
1. **Keep existing structure** - Maintain current section organization
2. **Add specific examples** - Include 2-3 concrete examples for each key tool
3. **Add decision criteria** - Clear guidance on when to use `think` vs `web_search`

### Specific Enhancements

#### think tool
- **When to use**: Complex reasoning tasks, architectural decisions, multi-step planning
- **Examples**:
  - "Before implementing a multi-step feature, use think to plan the approach"
  - "When debugging complex issues, use think to analyze root causes"
  - "For architectural design decisions, use think to evaluate trade-offs"

#### web_search tool
- **When to use**: External verification needed, unfamiliar concepts, API documentation
- **Examples**:
  - "When API documentation is unclear, web_search for official documentation"
  - "When encountering unfamiliar errors, web_search for solutions"
  - "For version-specific syntax or libraries, web_search for current best practices"

#### File tools
- **Decision flow**: read_file → understand → edit_file/write_file
- **Examples**:
  - "read_file to understand existing code before making edits"
  - "edit_file for targeted changes to existing files"
  - "write_file for creating new files from scratch"

### Decision Flow (Text-based)
```
Need deep reasoning? → think
Need external information? → web_search  
Need to understand code? → read_file
Making changes? → edit_file/write_file
Need system info? → bash
```

## Implementation Plan

### Task 1: Modify Tool Usage Policy Section

**Files:**
- Modify: `deep_coder/prompts/deepcoder/prompt.py:106-130`

**Steps:**
1. Locate the Tool Usage Policy section (lines 106-130)
2. Replace current bullet points with enhanced version including examples
3. Add specific examples for think and web_search tools
4. Add decision criteria flow
5. Keep total addition under 200 words

**Enhanced Tool Usage Policy Content:**
```
# Tool Usage Policy
- Available tool names: {tool_names}
- The available tool schemas are provided separately. Use tools when they improve certainty or are required to act.
- Prefer read_file for targeted reading.
- Prefer edit_file or write_file for workspace edits.
- Use bash for commands, tests, or inspection that file tools do not cover cleanly.
- If the answer is already clear from the current context, respond directly without unnecessary tool calls.
- You can call multiple tools in a single response when independent information can be gathered in parallel.
- Do not guess about code, files, or prior session state when you can inspect or retrieve them.

**Specific Tool Examples:**
- **think tool**: Use for complex reasoning before implementation decisions. Examples: planning multi-step features, analyzing root causes of complex bugs, evaluating architectural trade-offs.
- **web_search tool**: Use when external verification is needed. Examples: checking official API documentation, researching unfamiliar errors, verifying current best practices.
- **File tools**: read_file to understand existing code, edit_file for targeted changes, write_file for new files.

**Decision Flow:** Need deep reasoning? → think | Need external information? → web_search | Need to understand code? → read_file | Making changes? → edit_file/write_file
```

### Task 2: Verify Prompt Renders Correctly

**Files:**
- Test: `deep_coder/prompts/deepcoder/prompt.py`

**Steps:**
1. Run a quick test to ensure prompt renders without syntax errors
2. Verify the enhanced section appears correctly in output
3. Check that total prompt length remains reasonable

## Success Criteria
- Clear guidance on when to use think vs web_search
- Concrete examples that demonstrate proper tool usage
- Maintains prompt conciseness
- Improves model's tool selection accuracy