from __future__ import annotations

import re
from dataclasses import dataclass

# .NET: "   at Namespace.Class.Method(params) in File.cs:line 42"
_DOTNET_RE = re.compile(r"^\s*at\s+(.+?)(?:\s+in\s+(.+?):line\s+(\d+))?\s*$")
# Python: '  File "src/service.py", line 42, in method_name'
_PYTHON_RE = re.compile(r'^\s*File\s+"(.+?)",\s+line\s+(\d+),\s+in\s+(.+?)\s*$')

_INTERNAL_PREFIXES: tuple[str, ...] = (
    "System.",
    "Microsoft.AspNetCore.",
    "Microsoft.Extensions.",
    "Microsoft.EntityFrameworkCore.",
    "Microsoft.Azure.",
    "Azure.",
    "lambda_method",
)


@dataclass
class StackFrame:
    method: str
    file_path: str | None
    line_number: int | None
    is_user_code: bool


def parse_stack_frames(stack_trace: str, max_frames: int = 5) -> list[StackFrame]:
    """Return up to *max_frames* significant frames from *stack_trace*.

    Tries .NET format first, then Python format. Framework-internal frames are
    filtered; if no user-code frames remain, falls back to all parsed frames.
    """
    if not stack_trace:
        return []

    frames: list[StackFrame] = []
    for line in stack_trace.splitlines():
        frame = _try_parse_dotnet(line) or _try_parse_python(line)
        if frame is not None:
            frames.append(frame)

    user_frames = [f for f in frames if f.is_user_code]
    candidates = user_frames if user_frames else frames
    return candidates[:max_frames]


def _is_user_code(method: str) -> bool:
    return not any(method.startswith(prefix) for prefix in _INTERNAL_PREFIXES)


def _try_parse_dotnet(line: str) -> StackFrame | None:
    m = _DOTNET_RE.match(line)
    if not m:
        return None
    method = m.group(1).strip()
    file_path = m.group(2)
    line_no = int(m.group(3)) if m.group(3) else None
    return StackFrame(
        method=method,
        file_path=file_path,
        line_number=line_no,
        is_user_code=_is_user_code(method),
    )


def _try_parse_python(line: str) -> StackFrame | None:
    m = _PYTHON_RE.match(line)
    if not m:
        return None
    file_path = m.group(1)
    line_no = int(m.group(2))
    func_name = m.group(3)
    method = f"{file_path}::{func_name}"
    return StackFrame(
        method=method,
        file_path=file_path,
        line_number=line_no,
        is_user_code=_is_user_code(file_path),
    )
