from __future__ import annotations

from packages.agent_runtime.language_internals import is_framework_internal
from packages.agent_runtime.root_cause.stack_parser import StackFrame

_MAX_APP_FRAMES = 5
_FALLBACK_FRAMES = 3


def filter_frames(
    frames: list[StackFrame],
    path_prefix: str = "",
) -> list[StackFrame]:
    """Select application-code frames, excluding framework internals.

    1. Keep only frames marked as user code with a valid file path and line number.
    2. Apply language-aware framework prefix denial (via language_internals).
    3. Prioritise frames whose file_path starts with *path_prefix* (if given).
    4. Limit to *_MAX_APP_FRAMES*; fallback to *_FALLBACK_FRAMES* if all denied.
    """
    qualifying = [
        f
        for f in frames
        if f.is_user_code and f.file_path is not None and f.line_number is not None
    ]

    allowed = [f for f in qualifying if not _is_internal(f)]

    if not allowed and qualifying:
        return qualifying[:_FALLBACK_FRAMES]

    if path_prefix:
        priority = [f for f in allowed if f.file_path and f.file_path.startswith(path_prefix)]
        rest = [f for f in allowed if f not in priority]
        allowed = priority + rest

    return allowed[:_MAX_APP_FRAMES]


def _is_internal(frame: StackFrame) -> bool:
    """Return True when the frame looks like framework/library internals."""
    language = frame.language or "unknown"
    # For Python and Node.js, internals are identified by file path.
    # For .NET and Java, internals are identified by method/class name.
    if language in ("python", "nodejs"):
        return is_framework_internal(frame.file_path or "", language)
    return is_framework_internal(frame.method or "", language)
