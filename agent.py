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

    model_config = {"env_file": ".env.agent.secret", "env_file_encoding": "utf-8"}


SYSTEM_PROMPT = """You are a documentation assistant. You have access to tools to read files and list directories.

When asked a question:
1. Use `list_files` to discover files in the wiki/ directory
2. Use `read_file` to read relevant wiki files
3. Find the answer in the documentation
4. Include the source reference (file path and section anchor if applicable)

Be concise and accurate. Always cite your sources."""


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


# Tool definitions for LLM
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file from the project repository. Use this to read wiki files or source code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
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
                        "description": "Relative directory path from project root (e.g., 'wiki')",
                    }
                },
                "required": ["path"],
            },
        },
    },
]

TOOLS_MAP = {"read_file": read_file, "list_files": list_files}


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

    try:
        tool_func = TOOLS_MAP[tool_name]
        return tool_func(**args)
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
                    if path.startswith("wiki/"):
                        # Try to extract section from context
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
    max_iterations = 10

    for _ in range(max_iterations):
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

        # Execute tools
        for tc in tool_calls:
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
