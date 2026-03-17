# Task 3: The System Agent

## Implementation Plan

### Tool Schema: `query_api`

I will add a new tool to call the deployed backend API:

**Parameters:**
- `method` (string) — HTTP method (GET, POST, etc.)
- `path` (string) — API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional) — JSON request body for POST/PUT

**Returns:** JSON string with `status_code` and `body`

**Authentication:** Uses `LMS_API_KEY` from environment variables

### Environment Variables

The agent will read:
- `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` from `.env.agent.secret`
- `LMS_API_KEY` from `.env.docker.secret` (for API auth)
- `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)

### System Prompt Update

Update the system prompt to guide the LLM on when to use each tool:
- `list_files` / `read_file` — for wiki documentation and source code
- `query_api` — for runtime data (item count, scores, status codes)

### Benchmark Strategy

Run `uv run run_eval.py` and iterate:
1. First run — identify failing questions
2. Fix tool descriptions or system prompt
3. Re-run until all 10 questions pass

### Expected Failures and Fixes

| Issue | Fix |
|-------|-----|
| Agent doesn't call `query_api` for data questions | Improve tool description |
| API calls fail auth | Ensure `LMS_API_KEY` is passed correctly |
| Answer doesn't match keywords | Adjust system prompt for precision |

### Testing

Add 2 regression tests:
1. `"How many items are in the database?"` → expects `query_api`
2. `"What HTTP status code without auth?"` → expects `query_api`

### Deliverables

- [ ] `plans/task-3.md` with plan and benchmark results
- [ ] `agent.py` with `query_api` tool
- [ ] `AGENT.md` updated (200+ words)
- [ ] 2 new tests (5 total)
- [ ] `run_eval.py` passes 10/10
