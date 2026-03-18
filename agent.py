#!/usr/bin/env python3
"""CLI agent that calls an LLM and returns a structured JSON answer with tool calls."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """Environment settings for the agent."""

    llm_api_key: str
    llm_api_base: str
    llm_model: str = "openrouter/hunter-alpha"
    lms_api_key: str = ""
    agent_api_base_url: str = "http://localhost:42002"

    model_config = {
        "env_file": [".env.agent.secret", ".env.docker.secret"],
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


SYSTEM_PROMPT = """You are a documentation and system assistant. Answer questions using the available tools.

TOOL USAGE GUIDE:
- **Wiki/Documentation questions** (e.g., "how to protect a branch", "SSH setup"): 
  → Use `read_file` directly on wiki files: `wiki/git-workflow.md`, `wiki/setup.md`, `wiki/ssh.md`
  → DO NOT use `list_files` - go directly to the relevant wiki file
  
- **Source code questions** (e.g., "how does auth work", "show me the router"):
  → Use `read_file` on backend files: `backend/app/main.py`, `backend/app/routers/*.py`
  
- **Runtime data questions** (e.g., "how many items", "what is the pass rate", "status codes"):
  → Use `query_api` with GET method
  → Common endpoints: `/items/`, `/analytics/completion-rate`, `/analytics/groups`, `/analytics/timeline`
  → **IMPORTANT:** Always check the actual `status_code` in the API response before answering!

- **SSH/VM questions**:
  → Read `wiki/setup.md` or `wiki/ssh.md` for SSH instructions

RULES:
1. Be direct - call the right tool immediately, don't waste iterations
2. For wiki questions, read the file directly (e.g., `wiki/git-workflow.md`)
3. **For API questions, ALWAYS check the response status_code and body** - don't assume!
4. Keep answers concise but complete
5. Always include the source file path in your answer
6. Maximum 5 tool calls - prioritize the most relevant files first

EXAMPLES:
- "How to protect a branch?" → read_file("wiki/git-workflow.md")
- "SSH to VM?" → read_file("wiki/setup.md") or read_file("wiki/ssh.md")
- "How many items?" → query_api(method="GET", path="/items/") → check response.body
- "What status code?" → query_api(method="GET", path="/items/") → check response.status_code
"""


def read_file(path: str) -> str:
    """Read a file from the project repository.

    Args:
        path: Relative path from project root

    Returns:
        File contents or error message
    """
    # Security: block path traversal
    if ".." in path or path.startswith("/"):
        return "Error: Invalid path (path traversal not allowed)"

    # Get project root (where agent.py is)
    project_root = Path(__file__).parent
    file_path = project_root / path

    # Security: ensure path is within project
    try:
        file_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return "Error: Path must be within project directory"

    if not file_path.exists():
        return f"Error: File not found: {path}"

    try:
        return file_path.read_text()
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """List files and directories at a given path.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated listing or error message
    """
    # Security: block path traversal
    if ".." in path or path.startswith("/"):
        return "Error: Invalid path (path traversal not allowed)"

    # Get project root
    project_root = Path(__file__).parent
    dir_path = project_root / path

    # Security: ensure path is within project
    try:
        dir_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return "Error: Path must be within project directory"

    if not dir_path.exists():
        return f"Error: Directory not found: {path}"

    if not dir_path.is_dir():
        return f"Error: Not a directory: {path}"

    entries = []
    for entry in dir_path.iterdir():
        suffix = "/" if entry.is_dir() else ""
        entries.append(f"{entry.name}{suffix}")

    return "\n".join(sorted(entries))


def query_api(method: str, path: str, body: str = "") -> str:
    """Call the backend API.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., /items/, /analytics/completion-rate)
        body: Optional JSON request body for POST/PUT

    Returns:
        JSON string with status_code and body, or error message
    """
    api_base = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
    lms_api_key = os.environ.get("LMS_API_KEY", "")

    # Ensure path starts with /
    if not path.startswith("/"):
        path = "/" + path

    url = f"{api_base}{path}"

    headers = {
        "Content-Type": "application/json",
    }

    if lms_api_key:
        headers["Authorization"] = f"Bearer {lms_api_key}"

    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = client.post(
                    url, headers=headers, data=body if body else "{}"
                )
            else:
                return f"Error: Unsupported method: {method}"

        result = {
            "status_code": response.status_code,
            "body": response.text[:2000],  # Limit response size
        }
        return json.dumps(result)
    except Exception as e:
        return f"Error: {str(e)}"


# Tool definitions for LLM
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file from the project repository. Use this for wiki documentation (wiki/*.md), source code (*.py), or config files (*.yml, *.json). For SSH questions, read wiki/setup.md. For git questions, read wiki/git-workflow.md.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md', 'backend/app/main.py')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. Use this to discover files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki', 'backend/app/routers')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API to get runtime data. Use this for questions about item counts, scores, status codes, or API behavior. For GET requests, use method='GET'. For POST, include a JSON body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST)",
                    },
                    "path": {
                        "type": "string",
                        "description": "API path (e.g., '/items/', '/analytics/completion-rate?lab=lab-06')",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST requests",
                    },
                },
                "required": ["method", "path"],
            },
        },
    },
]

TOOLS_MAP = {"read_file": read_file, "list_files": list_files, "query_api": query_api}

# Cache for tool results to avoid redundant calls
_tool_cache: dict[str, str] = {}


async def call_llm(
    messages: list[dict[str, Any]], settings: AgentSettings
) -> dict[str, Any]:
    """Call the LLM API and return the response."""
    url = f"{settings.llm_api_base}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.llm_api_key}",
    }

    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    return data


def execute_tool(tool_name: str, args: dict[str, Any]) -> str:
    """Execute a tool and return the result."""
    if tool_name not in TOOLS_MAP:
        return f"Error: Unknown tool: {tool_name}"

    # Create cache key
    cache_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"

    # Check cache
    if cache_key in _tool_cache:
        return _tool_cache[cache_key]

    try:
        tool_func = TOOLS_MAP[tool_name]
        result = tool_func(**args)

        # Cache the result
        _tool_cache[cache_key] = result

        return result
    except Exception as e:
        return f"Error executing tool: {e}"


def extract_source_from_messages(messages: list[dict[str, Any]]) -> str:
    """Extract source reference from tool calls in messages."""
    for msg in messages:
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                if tc["function"]["name"] == "read_file":
                    args = json.loads(tc["function"]["arguments"])
                    path = args.get("path", "")
                    if (
                        path.startswith("wiki/")
                        or path.endswith(".py")
                        or path.endswith(".yml")
                    ):
                        return path
    return ""


async def run_agent(question: str, settings: AgentSettings) -> dict[str, Any]:
    """Run the agentic loop and return the result."""
    # Initialize messages with system prompt
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    all_tool_calls = []
    max_iterations = 5  # Limit to avoid timeout

    for i in range(max_iterations):
        # Call LLM
        response = await call_llm(messages, settings)

        # Get assistant message
        assistant_msg = response["choices"][0]["message"]
        messages.append(assistant_msg)

        # Check for tool calls
        tool_calls = assistant_msg.get("tool_calls", [])

        if not tool_calls:
            # No tool calls - we have the final answer
            answer = assistant_msg.get("content", "")
            source = extract_source_from_messages(messages)

            return {"answer": answer, "source": source, "tool_calls": all_tool_calls}

        # Execute tools (only first 2 per iteration to stay under timeout)
        for tc in tool_calls[:2]:
            tool_name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])

            # Execute the tool
            result = execute_tool(tool_name, args)

            # Record the tool call
            all_tool_calls.append({"tool": tool_name, "args": args, "result": result})

            # Add tool result to messages
            messages.append(
                {"role": "tool", "tool_call_id": tc["id"], "content": result}
            )

    # Max iterations reached
    answer = messages[-1].get("content", "") if messages else ""
    source = extract_source_from_messages(messages)

    return {"answer": answer, "source": source, "tool_calls": all_tool_calls}


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py <question>", file=sys.stderr)
        return 1

    question = sys.argv[1]

    try:
        settings = AgentSettings()
    except Exception as e:
        print(f"Error loading settings: {e}", file=sys.stderr)
        return 1

    try:
        result = asyncio.run(run_agent(question, settings))
    except Exception as e:
        print(f"Error running agent: {e}", file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
