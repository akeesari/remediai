from __future__ import annotations

import re
from dataclasses import dataclass, field

from packages.agent_runtime.language_internals import is_framework_internal

# ---------------------------------------------------------------------------
# Language-specific frame regexes
# ---------------------------------------------------------------------------

# .NET: "   at Namespace.Class.Method(params) in File.cs:line 42"
_DOTNET_RE = re.compile(r"^\s*at\s+(.+?)(?:\s+in\s+(.+?):line\s+(\d+))?\s*$")

# Python: '  File "src/service.py", line 42, in method_name'
_PYTHON_RE = re.compile(r'^\s*File\s+"(.+?)",\s+line\s+(\d+),\s+in\s+(.+?)\s*$')

# Node.js / V8 — two forms:
#   at ClassName.method (/app/src/file.js:42:18)
#   at /app/src/utils/helper.js:42:18
_NODEJS_RE = re.compile(
    r"^\s*at\s+(?:async\s+)?(?P<method>[^\s(]+)\s+\((?P<path>[^)]+):(?P<line>\d+):\d+\)"
    r"|^\s*at\s+(?P<path2>[^:]+\.[jt]sx?):(?P<line2>\d+):\d+"
)

# Java: "   at com.example.services.UserService.getById(UserService.java:42)"
_JAVA_RE = re.compile(r"^\s*at\s+([\w.$]+)\(([\w.]+\.java):(\d+)\)")

# ---------------------------------------------------------------------------
# Docker / build-system path-prefix stripping
# ---------------------------------------------------------------------------
_DOCKER_PATH_PREFIXES: tuple[str, ...] = (
    "/app/",
    "/src/",
    "/code/",
    "/workspace/",
    "/usr/src/app/",
    "/home/app/",
    "/build/",
    "/opt/app/",  # Java containers
    "/usr/local/app/",  # Node.js containers
)


@dataclass
class StackFrame:
    method: str
    file_path: str | None
    line_number: int | None
    is_user_code: bool
    language: str = field(default="unknown")


def parse_stack_frames(stack_trace: str, max_frames: int = 5) -> list[StackFrame]:
    """Return up to *max_frames* significant user-code frames from *stack_trace*.

    Tries all supported parsers (.NET, Python, Node.js, Java) on each line.
    Framework-internal frames are filtered; if none remain, falls back to all
    parsed frames so the caller always gets something useful.
    """
    if not stack_trace:
        return []

    frames: list[StackFrame] = []
    for line in stack_trace.splitlines():
        frame = (
            _try_parse_dotnet(line)
            or _try_parse_python(line)
            or _try_parse_nodejs(line)
            or _try_parse_java(line)
        )
        if frame is not None:
            frames.append(frame)

    user_frames = [f for f in frames if f.is_user_code]
    candidates = user_frames if user_frames else frames
    return candidates[:max_frames]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_path(path: str | None) -> str | None:
    """Strip Docker container path prefixes so the result is repo-relative."""
    if not path:
        return path
    for prefix in _DOCKER_PATH_PREFIXES:
        if path.startswith(prefix):
            return path[len(prefix) :]
    return path


def _try_parse_dotnet(line: str) -> StackFrame | None:
    m = _DOTNET_RE.match(line)
    if not m:
        return None
    method = m.group(1).strip()
    file_path = _clean_path(m.group(2))
    line_no = int(m.group(3)) if m.group(3) else None
    return StackFrame(
        method=method,
        file_path=file_path,
        line_number=line_no,
        is_user_code=not is_framework_internal(method, "dotnet"),
        language="dotnet",
    )


def _try_parse_python(line: str) -> StackFrame | None:
    m = _PYTHON_RE.match(line)
    if not m:
        return None
    file_path = _clean_path(m.group(1))
    line_no = int(m.group(2))
    func_name = m.group(3)
    method = f"{file_path}::{func_name}"
    return StackFrame(
        method=method,
        file_path=file_path,
        line_number=line_no,
        is_user_code=not is_framework_internal(file_path or "", "python"),
        language="python",
    )


def _try_parse_nodejs(line: str) -> StackFrame | None:
    m = _NODEJS_RE.match(line)
    if not m:
        return None
    # Named-group alternation: one of two patterns matched
    if m.group("path"):
        method = m.group("method") or "<anonymous>"
        file_path = _clean_path(m.group("path"))
        line_no = int(m.group("line"))
    else:
        method = "<anonymous>"
        file_path = _clean_path(m.group("path2"))
        line_no = int(m.group("line2"))
    return StackFrame(
        method=method,
        file_path=file_path,
        line_number=line_no,
        is_user_code=not is_framework_internal(file_path or "", "nodejs"),
        language="nodejs",
    )


def _try_parse_java(line: str) -> StackFrame | None:
    m = _JAVA_RE.match(line)
    if not m:
        return None
    method = m.group(1)
    file_path = m.group(2)  # just the filename, e.g. UserService.java
    line_no = int(m.group(3))
    return StackFrame(
        method=method,
        file_path=file_path,
        line_number=line_no,
        is_user_code=not is_framework_internal(method, "java"),
        language="java",
    )
