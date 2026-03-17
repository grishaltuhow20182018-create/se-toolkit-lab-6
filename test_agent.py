"""Unit tests for the CLI agent."""

import json
import subprocess
import sys


def test_agent_returns_valid_json_with_answer_and_tool_calls() -> None:
    """Test that agent.py returns valid JSON with required fields."""
    result = subprocess.run(
        [sys.executable, "-m", "uv", "run", "agent.py", "What is 2+2?"],
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


def test_agent_uses_read_file_for_wiki_question() -> None:
    """Test that agent uses read_file tool for wiki questions."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "How do you resolve a merge conflict?",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = json.loads(result.stdout)

    # Check that tool_calls is populated
    assert len(output["tool_calls"]) > 0, "Expected tool calls for wiki question"

    # Check that read_file was used
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Check that source is present
    assert "source" in output, "Missing 'source' field"


def test_agent_uses_list_files_for_directory_question() -> None:
    """Test that agent uses list_files tool for directory questions."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "What files are in the wiki directory?",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = json.loads(result.stdout)

    # Check that tool_calls is populated
    assert len(output["tool_calls"]) > 0, "Expected tool calls for directory question"

    # Check that list_files was used
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "list_files" in tool_names, "Expected list_files to be called"


def test_agent_uses_query_api_for_data_question() -> None:
    """Test that agent uses query_api for runtime data questions."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "How many items are in the database?",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = json.loads(result.stdout)

    # Check that tool_calls is populated (agent should try to query API)
    # Note: May fail if backend is not running, but should attempt query_api
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "query_api" in tool_names, (
        "Expected query_api to be called for data question"
    )


def test_agent_uses_query_api_for_status_code_question() -> None:
    """Test that agent uses query_api for HTTP status code questions."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "What HTTP status code does the API return without authentication?",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = json.loads(result.stdout)

    # Check that query_api was used
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "query_api" in tool_names, (
        "Expected query_api to be called for status code question"
    )
