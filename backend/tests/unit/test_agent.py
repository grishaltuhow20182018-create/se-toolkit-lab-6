"""Unit tests for the CLI agent."""

import json
import subprocess


def test_agent_returns_valid_json_with_answer_and_tool_calls() -> None:
    """Test that agent.py returns valid JSON with required fields."""
    result = subprocess.run(
        ["uv", "run", "python", "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"

    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"
    assert output["tool_calls"] == [], "'tool_calls' must be empty for Task 1"
