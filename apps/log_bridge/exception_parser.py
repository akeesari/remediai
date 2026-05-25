"""Stateful parser that detects Python exceptions in a stream of log lines."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_TRACEBACK_START = re.compile(r"Traceback \(most recent call last\):")
# Matches lines like "ValueError: some message" or "app.errors.CustomError: msg"
_EXCEPTION_LINE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning|Fault|Failure|Exit))" r":\s*(.+)$"
)
# Strip common Docker log prefixes: ISO timestamp + optional log level
_STRIP_TS = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s*"
)
_STRIP_LEVEL = re.compile(r"^(?:DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*:?\s*")
_HTTP_5XX = re.compile(r'"(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) \S+ HTTP/[^"]*" 5\d\d ')
_MAX_TRACEBACK_LINES = 60


@dataclass
class DetectedExcepion:
    exception_type: str
    exception_message: str
    stack_trace: str
    raw_lines: list[str] = field(default_factory=list)


class ExceptionParser:
    """Feed log lines one at a time; returns a DetectedExcepion when one is complete."""

    def __init__(self) -> None:
        self._tb_lines: list[str] = []
        self._in_tb: bool = False

    def feed(self, raw_line: str) -> DetectedExcepion | None:
        clean = _strip_prefixes(raw_line)

        if _TRACEBACK_START.search(clean):
            self._tb_lines = [clean]
            self._in_tb = True
            return None

        if self._in_tb:
            self._tb_lines.append(clean)
            m = _EXCEPTION_LINE.match(clean.strip())
            if m:
                exc = DetectedExcepion(
                    exception_type=m.group(1),
                    exception_message=m.group(2).strip(),
                    stack_trace="\n".join(self._tb_lines),
                    raw_lines=list(self._tb_lines),
                )
                self._tb_lines = []
                self._in_tb = False
                return exc
            if len(self._tb_lines) > _MAX_TRACEBACK_LINES:
                self._tb_lines = []
                self._in_tb = False
            return None

        # Single-line exception (no preceding traceback)
        m2 = _EXCEPTION_LINE.match(clean.strip())
        if m2:
            return DetectedExcepion(
                exception_type=m2.group(1),
                exception_message=m2.group(2).strip(),
                stack_trace="",
                raw_lines=[clean],
            )

        # HTTP 5xx in uvicorn access log
        if _HTTP_5XX.search(raw_line):
            return DetectedExcepion(
                exception_type="HTTPException",
                exception_message=f"HTTP 5xx: {raw_line.strip()}",
                stack_trace="",
                raw_lines=[raw_line],
            )

        return None


def _strip_prefixes(line: str) -> str:
    line = _STRIP_TS.sub("", line)
    line = _STRIP_LEVEL.sub("", line)
    return line
