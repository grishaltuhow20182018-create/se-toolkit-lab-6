# Task 1: Call an LLM from Code

## Implementation Plan

### LLM Provider and Model

**Provider:** Qwen Code API (deployed on VM)

**Model:** `qwen3-coder-plus`

**Rationale:**
- 1000 free requests per day
- Works from Russia without restrictions
- No credit card required
- Strong tool calling capabilities (needed for Task 2-3)
- OpenAI-compatible API endpoint

### Environment Configuration

The agent will read configuration from `.env.agent.secret`:
- `LLM_API_KEY` - API key for Qwen Code API
- `LLM_API_BASE` - Base URL (e.g., `http://<vm-ip>:<port>/v1`)
- `LLM_MODEL` - Model name (`qwen3-coder-plus`)

### Agent Architecture

**File:** `agent.py` (project root)

**Components:**

1. **Environment Loader**
   - Use `pydantic-settings` to load `.env.agent.secret`
   - Validate required fields (API key, base URL, model)

2. **HTTP Client**
   - Use `httpx` (already in dependencies) for async HTTP requests
   - POST to `{LLM_API_BASE}/chat/completions`
   - OpenAI-compatible request format

3. **CLI Interface**
   - Accept question as first command-line argument
   - Use `sys.argv` for simple argument parsing

4. **Response Parser**
   - Extract `content` from LLM response
   - Format as JSON: `{"answer": "...", "tool_calls": []}`

5. **Output Handler**
   - JSON to stdout (for piping)
   - Debug/logs to stderr

### Request Format

```json
{
  "model": "qwen3-coder-plus",
  "messages": [
    {
      "role": "user",
      "content": "What does REST stand for?"
    }
  ]
}
```

### Response Format (stdout)

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

### Error Handling

- Timeout: 60 seconds for API call
- Exit code 0 on success, non-zero on failure
- Error messages to stderr

### Testing Strategy

**Test file:** `backend/tests/unit/test_agent.py`

Single regression test:
1. Run `agent.py` as subprocess with a test question
2. Parse stdout as JSON
3. Assert `answer` field exists and is non-empty string
4. Assert `tool_calls` field exists and is empty list

### Dependencies

No new dependencies needed - using existing:
- `pydantic-settings` (environment loading)
- `httpx` (HTTP client)

### Security

- API key stored in `.env.agent.secret` (git-ignored)
- Never hardcode secrets in source code
