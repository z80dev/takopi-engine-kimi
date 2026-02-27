"""Tests for takopi-kimi-runner."""

from pathlib import Path

import pytest

from takopi_kimi_runner import (
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


def test_decode_system_init() -> None:
    line = b'{"type":"system","subtype":"init","session_id":"test-123","model":"kimi-k2"}'
    event = decode_stream_json_line(line)
    assert event.subtype == "init"
    assert event.session_id == "test-123"
    assert event.model == "kimi-k2"


def test_translate_system_init_emits_started() -> None:
    state = KimiStreamState()
    line = b'{"type":"system","subtype":"init","session_id":"test-123","model":"kimi-k2","cwd":"/home/test"}'
    event = decode_stream_json_line(line)

    result = translate_kimi_event(
        event,
        title="kimi",
        state=state,
        factory=state.factory,
    )

    assert len(result) == 1
    assert isinstance(result[0], StartedEvent)
    started = result[0]
    assert started.resume.value == "test-123"
    assert started.title == "kimi-k2"


def test_translate_assistant_with_tool_use() -> None:
    state = KimiStreamState()
    line = b'''{"type":"assistant","session_id":"test-123","message":{"role":"assistant","model":"kimi-k2","content":[{"type":"tool_use","id":"tool_1","name":"Bash","input":{"command":"ls -la"}}]}}'''
    event = decode_stream_json_line(line)

    result = translate_kimi_event(
        event,
        title="kimi",
        state=state,
        factory=state.factory,
    )

    assert len(result) == 1
    assert isinstance(result[0], ActionEvent)
    assert result[0].action.kind == "command"
    assert result[0].action.id == "tool_1"


def test_translate_result_success() -> None:
    state = KimiStreamState()
    state.last_assistant_text = "Done!"
    line = b'{"type":"result","subtype":"success","session_id":"test-123","is_error":false,"duration_ms":1000,"duration_api_ms":800,"num_turns":1,"result":"Done!"}'
    event = decode_stream_json_line(line)

    result = translate_kimi_event(
        event,
        title="kimi",
        state=state,
        factory=state.factory,
    )

    assert len(result) == 1
    assert isinstance(result[0], CompletedEvent)
    completed = result[0]
    assert completed.ok is True
    assert completed.answer == "Done!"
    assert completed.resume.value == "test-123"


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
