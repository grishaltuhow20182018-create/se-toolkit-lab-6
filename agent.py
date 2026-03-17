#!/usr/bin/env python3
"""CLI agent that calls an LLM and returns a structured JSON answer."""

import asyncio
import json
import sys
from typing import Any

import httpx
from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """Environment settings for the agent."""

    llm_api_key: str
    llm_api_base: str
    llm_model: str = "qwen3-coder-plus"

    model_config = {"env_file": ".env.agent.secret", "env_file_encoding": "utf-8"}

async def call_llm(question: str, settings: AgentSettings) -> dict[str, Any]:
    """Call the LLM API and return the response."""
    url = f"{settings.llm_api_base}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.llm_api_key}",
    }

    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "user",
                "content": question,
            }
        ],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    return data


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
        response_data = asyncio.run(call_llm(question, settings))
    except Exception as e:
        print(f"Error calling LLM: {e}", file=sys.stderr)
        return 1

    # Extract answer from response
    try:
        answer = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        print(f"Error parsing LLM response: {e}", file=sys.stderr)
        return 1

    # Format output
    output = {
        "answer": answer,
        "tool_calls": [],
    }

    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
