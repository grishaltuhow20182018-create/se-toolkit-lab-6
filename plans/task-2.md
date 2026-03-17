# Task 2: The Documentation Agent

## Implementation Plan

### Tool Schemas

I will define two tools as function-calling schemas for the LLM:

**1. `read_file`**
- **Purpose:** Read contents of a file from the project repository
- **Parameters:** `path` (string) — relative path from project root
- **Returns:** File contents as string, or error message
- **Security:** Block `../` path traversal attempts

**2. `list_files`**
- **Purpose:** List files and directories at a given path
- **Parameters:** `path` (string) — relative directory path from project root
- **Returns:** Newline-separated listing of entries
- **Security:** Block `../` path traversal attempts

### Agentic Loop

The loop will:
1. Send user question + tool definitions to LLM
2. If LLM returns `tool_calls`:
   - Execute each tool
   - Append results as `tool` role messages
   - Send back to LLM
   - Repeat (max 10 iterations)
3. If LLM returns text answer (no tool calls):
   - Extract answer and source
   - Output JSON and exit

### System Prompt Strategy

The system prompt will instruct the LLM to:
1. Use `list_files` to discover wiki files in `wiki/` directory
2. Use `read_file` to read relevant wiki sections
3. Include source reference (file path + section anchor) in the answer
4. Be concise and accurate

### Path Security

Both tools will validate paths:
- Must not start with `/` or contain `../`
- Must resolve to within project directory
- Return error message for invalid paths

### Output Format

```json
{
  "answer": "...",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

### Testing

Add 2 regression tests:
1. Question about merge conflicts → expects `read_file` in tool_calls
2. Question about wiki files → expects `list_files` in tool_calls
