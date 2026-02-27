"""Tests for takopi-engine-kimi."""

import json
from pathlib import Path

import pytest

from takopi_engine_kimi import (
    BACKEND,
    KimiRunner,
    KimiStreamState,
    decode_stream_json_line,
    translate_kimi_event,
)
from takopi.model import ActionEvent, CompletedEvent, ResumeToken, StartedEvent


def test_backend_attributes() -> None:
    assert BACKEND.id == "kimi"
    assert BACKEND.install_cmd == "pip install kimi-cli"
    assert BACKEND.build_runner is not None


def test_decode_assistant_message() -> None:
    data = {
        "role": "assistant",
        "content": [
            {"type": "think", "think": "Let me analyze this."},
            {"type": "text", "text": "I'll help you!"},
        ],
    }
    line = json.dumps(data).encode()
    event = decode_stream_json_line(line)
    assert event["role"] == "assistant"
    assert len(event["content"]) == 2


def test_translate_assistant_with_think() -> None:
    state = KimiStreamState()
    data = {
        "role": "assistant",
        "content": [
            {"type": "think", "think": "Analyzing the request."},
            {"type": "text", "text": "Done!"},
        ],
    }

    result = translate_kimi_event(
        data,
        title="kimi",
        state=state,
        factory=state.factory,
    )

    # Should have thinking note + text storage (no events for text)
    assert len(result) == 1
    assert isinstance(result[0], ActionEvent)
    assert result[0].action.kind == "note"
    assert result[0].action.title == "Analyzing the request."


def test_translate_assistant_with_tool_call() -> None:
    state = KimiStreamState()
    data = {
        "role": "assistant",
        "content": [{"type": "text", "text": "I'll run a command."}],
        "tool_calls": [
            {
                "type": "function",
                "id": "tool_abc123",
                "function": {
                    "name": "Bash",
                    "arguments": json.dumps({"command": "ls -la"}),
                },
            }
        ],
    }

    result = translate_kimi_event(
        data,
        title="kimi",
        state=state,
        factory=state.factory,
    )

    assert len(result) == 1
    assert isinstance(result[0], ActionEvent)
    assert result[0].action.kind == "command"
    assert result[0].action.id == "tool_abc123"
    assert result[0].phase == "started"


def test_translate_tool_result() -> None:
    state = KimiStreamState()
    # First add a pending action
    from takopi.model import Action

    state.pending_actions["tool_abc123"] = Action(
        id="tool_abc123",
        kind="command",
        title="ls -la",
        detail={"name": "Bash", "input": {"command": "ls -la"}},
    )

    data = {
        "role": "tool",
        "tool_call_id": "tool_abc123",
        "content": [{"type": "text", "text": "file1.py\nfile2.py"}],
    }

    result = translate_kimi_event(
        data,
        title="kimi",
        state=state,
        factory=state.factory,
    )

    assert len(result) == 1
    assert isinstance(result[0], ActionEvent)
    assert result[0].phase == "completed"
    assert result[0].ok is True
    assert "tool_abc123" not in state.pending_actions


def test_runner_build_args() -> None:
    runner = KimiRunner(kimi_cmd="kimi", model="kimi-k2", yolo=True)
    args = runner.build_args("test prompt", None, state=KimiStreamState())

    assert "--print" in args
    assert "--output-format" in args
    assert "stream-json" in args
    assert "--model" in args
    assert "kimi-k2" in args
    assert "--yolo" in args
    assert "-p" in args
    assert "test prompt" in args


def test_runner_resume_format() -> None:
    runner = KimiRunner(kimi_cmd="kimi")
    token = ResumeToken(engine="kimi", value="session-abc")

    formatted = runner.format_resume(token)
    assert formatted == "`kimi --resume session-abc`"


def test_build_runner_from_config() -> None:
    config = {"model": "kimi-k2", "allowed_tools": ["Bash"]}
    runner = BACKEND.build_runner(config, Path("test.toml"))

    assert isinstance(runner, KimiRunner)
    assert runner.model == "kimi-k2"
    assert runner.allowed_tools == ["Bash"]


def test_build_runner_defaults() -> None:
    """Test that sensible defaults are applied."""
    config = {}
    runner = BACKEND.build_runner(config, Path("test.toml"))

    assert isinstance(runner, KimiRunner)
    assert runner.model == "kimi-for-coding"  # Default model
    assert runner.yolo is False  # Default to False for safety


def test_build_runner_with_yolo() -> None:
    """Test that yolo config is passed through."""
    config = {"yolo": True}
    runner = BACKEND.build_runner(config, Path("test.toml"))

    assert isinstance(runner, KimiRunner)
    assert runner.yolo is True
