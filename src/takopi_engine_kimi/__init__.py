"""Kimi CLI runner plugin for Takopi."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import msgspec

from takopi.backends import EngineBackend, EngineConfig
from takopi.events import EventFactory
from takopi.logging import get_logger
from takopi.model import Action, ActionKind, EngineId, ResumeToken, TakopiEvent
from takopi.runner import JsonlSubprocessRunner, ResumeTokenMixin, Runner
from takopi.runners.run_options import get_run_options
from takopi.runners.tool_actions import tool_input_path, tool_kind_and_title

logger = get_logger(__name__)

ENGINE: EngineId = "kimi"
DEFAULT_ALLOWED_TOOLS = ["Bash", "Read", "Edit", "Write"]

_RESUME_RE = re.compile(
    r"(?im)^\s*`?kimi\s+(?:--resume|-r)\s+(?P<token>[^`\s]+)`?\s*$"
)


# =============================================================================
# Schema (msgspec models for Kimi CLI stream-json output)
# =============================================================================

class ToolCallFunction(msgspec.Struct, forbid_unknown_fields=False):
    name: str
    arguments: str


class ToolCall(msgspec.Struct, forbid_unknown_fields=False):
    type: str
    id: str
    function: ToolCallFunction


class TextContent(msgspec.Struct, tag="text", tag_field="type", forbid_unknown_fields=False):
    text: str


class ThinkContent(msgspec.Struct, tag="think", tag_field="type", forbid_unknown_fields=False):
    think: str
    encrypted: str | None = None


class ToolResultContent(msgspec.Struct, tag="text", tag_field="type", forbid_unknown_fields=False):
    text: str


class ToolMessage(msgspec.Struct, forbid_unknown_fields=False):
    role: str
    content: list[ToolResultContent]
    tool_call_id: str


class AssistantMessage(msgspec.Struct, forbid_unknown_fields=False):
    role: str
    content: list[TextContent | ThinkContent]
    tool_calls: list[ToolCall] | None = None
    encrypted: str | None = None


def decode_stream_json_line(line: str | bytes) -> dict[str, Any]:
    """Decode a JSON line from Kimi CLI."""
    if isinstance(line, bytes):
        line = line.decode("utf-8", errors="replace")
    import json
    return json.loads(line)


# =============================================================================
# Runner Implementation
# =============================================================================

@dataclass(slots=True)
class KimiStreamState:
    factory: EventFactory = field(default_factory=lambda: EventFactory(ENGINE))
    pending_actions: dict[str, Action] = field(default_factory=dict)
    last_assistant_text: str | None = None
    note_seq: int = 0
    session_id: str | None = None


def _normalize_tool_result(content: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def _coerce_comma_list(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        parts = [str(item) for item in value if item is not None]
        joined = ",".join(part for part in parts if part)
        return joined or None
    text = str(value)
    return text or None


def _tool_kind_and_title(
    name: str, tool_input: dict[str, Any]
) -> tuple[ActionKind, str]:
    return tool_kind_and_title(name, tool_input, path_keys=("file_path", "path"))


def _extract_tool_input(arguments: str) -> dict[str, Any]:
    """Parse tool arguments from JSON string."""
    import json
    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return {"raw": arguments}


def translate_kimi_event(
    event: dict[str, Any],
    *,
    title: str,
    state: KimiStreamState,
    factory: EventFactory,
) -> list[TakopiEvent]:
    role = event.get("role")
    
    if role == "assistant":
        out: list[TakopiEvent] = []
        content = event.get("content", [])
        
        # Extract thinking blocks
        for item in content:
            if isinstance(item, dict) and item.get("type") == "think":
                think_text = item.get("think", "")
                if think_text:
                    state.note_seq += 1
                    action_id = f"kimi.thinking.{state.note_seq}"
                    out.append(
                        factory.action_completed(
                            action_id=action_id,
                            kind="note",
                            title=think_text,
                            ok=True,
                            detail={},
                        )
                    )
            elif isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                if text:
                    state.last_assistant_text = text
        
        # Extract tool calls
        tool_calls = event.get("tool_calls", [])
        if tool_calls:
            for tool_call in tool_calls:
                if isinstance(tool_call, dict):
                    tool_id = tool_call.get("id", "unknown")
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "tool")
                    arguments = function.get("arguments", "{}")
                    tool_input = _extract_tool_input(arguments)
                    
                    kind, title_str = _tool_kind_and_title(tool_name, tool_input)
                    detail: dict[str, Any] = {
                        "name": tool_name,
                        "input": tool_input,
                    }
                    
                    if kind == "file_change":
                        path = tool_input_path(tool_input, path_keys=("file_path", "path"))
                        if path:
                            detail["changes"] = [{"path": path, "kind": "update"}]
                    
                    action = Action(id=tool_id, kind=kind, title=title_str, detail=detail)
                    state.pending_actions[tool_id] = action
                    out.append(
                        factory.action_started(
                            action_id=tool_id,
                            kind=kind,
                            title=title_str,
                            detail=detail,
                        )
                    )
        
        return out
    
    elif role == "tool":
        tool_call_id = event.get("tool_call_id", "unknown")
        content = event.get("content", [])
        result_text = _normalize_tool_result(content)
        
        action = state.pending_actions.pop(tool_call_id, None)
        if action is None:
            action = Action(
                id=tool_call_id,
                kind="tool",
                title="tool result",
                detail={},
            )
        
        detail = action.detail | {
            "tool_use_id": tool_call_id,
            "result_preview": result_text[:500],
            "result_len": len(result_text),
        }
        
        return [
            factory.action_completed(
                action_id=action.id,
                kind=action.kind,
                title=action.title,
                ok=True,
                detail=detail,
            )
        ]
    
    return []


@dataclass(slots=True)
class KimiRunner(ResumeTokenMixin, JsonlSubprocessRunner):
    engine: EngineId = ENGINE
    resume_re: re.Pattern[str] = _RESUME_RE

    kimi_cmd: str = "kimi"
    model: str | None = None
    allowed_tools: list[str] | None = None
    yolo: bool = False
    use_api_billing: bool = False
    session_title: str = "kimi"
    logger = logger

    def format_resume(self, token: ResumeToken) -> str:
        if token.engine != ENGINE:
            raise RuntimeError(f"resume token is for engine {token.engine!r}")
        return f"`kimi --resume {token.value}`"

    def _build_args(self, prompt: str, resume: ResumeToken | None) -> list[str]:
        run_options = get_run_options()
        # --print is required for --output-format to work
        # -p passes the prompt
        args: list[str] = ["--print", "--output-format", "stream-json"]
        
        if resume is not None:
            args.extend(["--resume", resume.value])
        
        model = self.model
        if run_options is not None and run_options.model:
            model = run_options.model
        if model is not None:
            args.extend(["--model", str(model)])
        
        # Note: kimi doesn't have --allowedTools, tools are configured via config
        
        if self.yolo is True:
            args.append("--yolo")
        
        # Pass prompt via -p
        args.extend(["-p", prompt])
        return args

    def command(self) -> str:
        return self.kimi_cmd

    def build_args(
        self,
        prompt: str,
        resume: ResumeToken | None,
        *,
        state: Any,
    ) -> list[str]:
        return self._build_args(prompt, resume)

    def stdin_payload(
        self,
        prompt: str,
        resume: ResumeToken | None,
        *,
        state: Any,
    ) -> bytes | None:
        return None

    def env(self, *, state: Any) -> dict[str, str] | None:
        if self.use_api_billing is not True:
            env = dict(os.environ)
            env.pop("MOONSHOT_API_KEY", None)
            return env
        return None

    def new_state(self, prompt: str, resume: ResumeToken | None) -> KimiStreamState:
        return KimiStreamState()

    def start_run(
        self,
        prompt: str,
        resume: ResumeToken | None,
        *,
        state: KimiStreamState,
    ) -> None:
        pass

    def decode_jsonl(
        self,
        *,
        line: bytes,
    ) -> dict[str, Any]:
        return decode_stream_json_line(line)

    def decode_error_events(
        self,
        *,
        raw: str,
        line: str,
        error: Exception,
        state: KimiStreamState,
    ) -> list[TakopiEvent]:
        if isinstance(error, msgspec.DecodeError):
            self.get_logger().warning(
                "jsonl.msgspec.invalid",
                tag=self.tag(),
                error=str(error),
                error_type=error.__class__.__name__,
            )
            return []
        return super().decode_error_events(
            raw=raw,
            line=line,
            error=error,
            state=state,
        )

    def invalid_json_events(
        self,
        *,
        raw: str,
        line: str,
        state: KimiStreamState,
    ) -> list[TakopiEvent]:
        return []

    def translate(
        self,
        data: dict[str, Any],
        *,
        state: KimiStreamState,
        resume: ResumeToken | None,
        found_session: ResumeToken | None,
    ) -> list[TakopiEvent]:
        # Emit started event on first assistant message if not started
        if state.session_id is None and data.get("role") == "assistant":
            state.session_id = "kimi-session"
            started = state.factory.started(
                resume=ResumeToken(engine=ENGINE, value=state.session_id),
                title=self.session_title,
            )
            events = translate_kimi_event(
                data,
                title=self.session_title,
                state=state,
                factory=state.factory,
            )
            return [started, *events]
        
        return translate_kimi_event(
            data,
            title=self.session_title,
            state=state,
            factory=state.factory,
        )

    def process_error_events(
        self,
        rc: int,
        *,
        resume: ResumeToken | None,
        found_session: ResumeToken | None,
        state: KimiStreamState,
    ) -> list[TakopiEvent]:
        message = f"kimi failed (rc={rc})."
        resume_for_completed = found_session or resume
        return [
            self.note_event(message, state=state, ok=False),
            state.factory.completed_error(
                error=message,
                resume=resume_for_completed,
            ),
        ]

    def stream_end_events(
        self,
        *,
        resume: ResumeToken | None,
        found_session: ResumeToken | None,
        state: KimiStreamState,
    ) -> list[TakopiEvent]:
        if not found_session:
            message = "kimi finished but no session_id was captured"
            resume_for_completed = resume
            return [
                state.factory.completed_error(
                    error=message,
                    resume=resume_for_completed,
                )
            ]

        message = "kimi finished"
        return [
            state.factory.completed_ok(
                answer=state.last_assistant_text or "",
                resume=found_session,
            )
        ]


def build_runner(config: EngineConfig, _config_path: Path) -> Runner:
    kimi_cmd = shutil.which("kimi") or "kimi"

    # Default to kimi-for-coding model
    model = config.get("model") or "kimi-for-coding"
    if "allowed_tools" in config:
        allowed_tools = config.get("allowed_tools")
    else:
        allowed_tools = DEFAULT_ALLOWED_TOOLS
    # Kimi CLI uses --yolo flag for auto-approving actions
    yolo = config.get("yolo") is True
    use_api_billing = config.get("use_api_billing") is True
    title = str(model) if model is not None else "kimi"

    return KimiRunner(
        kimi_cmd=kimi_cmd,
        model=model,
        allowed_tools=allowed_tools,
        yolo=yolo,
        use_api_billing=use_api_billing,
        session_title=title,
    )


BACKEND = EngineBackend(
    id="kimi",
    build_runner=build_runner,
    install_cmd="pip install kimi-cli",
)
