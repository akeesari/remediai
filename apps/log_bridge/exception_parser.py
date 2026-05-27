"""Stateful parser that detects Python and .NET exceptions in a stream of log lines.

Supports three log formats out of the box:
  1. Plain-text lines (uvicorn, gunicorn, custom formatters)
  2. Pipe-separated lines with timestamp|LEVEL|Component|message prefix
  3. Structured JSON logs (Serilog, Winston, Python structlog, Azure Application
     Insights) — the message / exception field is extracted automatically before
     the normal regex matching runs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# Matches: "System.InvalidOperationException: message" or "NullReferenceException: message"
_DOTNET_EXCEPTION_START = re.compile(r"([\w\.]+?(?:Exception|Error|Fault|Failure|Exit)):\s*(.+)$")
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

# ---------------------------------------------------------------------------
# Structured / JSON log extraction
# ---------------------------------------------------------------------------
# Common field names used by popular structured logging libraries.
# We try each in order; the first non-empty value wins.
_JSON_MESSAGE_FIELDS = (
    # Serilog / .NET JSON formatter
    "RenderedMessage", "MessageTemplate", "message", "msg",
    # Winston (Node)
    "message",
    # Python structlog / python-json-logger
    "event", "message",
    # Azure Application Insights / Monitor
    "body", "formattedMessage",
)
_JSON_EXCEPTION_FIELDS = (
    # Serilog
    "Exception",
    # Python structlog
    "exception", "exc_info",
)



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

        # .NET traceback state variables
        self._in_dotnet_tb: bool = False
        self._dotnet_exc_type: str = ""
        self._dotnet_exc_msg: str = ""

    def feed(self, raw_line: str) -> DetectedExcepion | None:
        # Pre-process: unwrap structured JSON logs into plain text
        raw_line = _extract_from_json(raw_line)
        clean = _strip_prefixes(raw_line)

        # 1. Handle active .NET traceback
        if self._in_dotnet_tb:
            stripped = clean.strip()
            # In .NET stack trace, frames start with "at " or "---"
            if stripped.startswith("at ") or stripped.startswith("---"):
                self._tb_lines.append(clean)
                if len(self._tb_lines) > _MAX_TRACEBACK_LINES:
                    self._reset()
                return None
            else:
                # Traceback ended because we found a non-stack-frame line
                exc = DetectedExcepion(
                    exception_type=self._dotnet_exc_type,
                    exception_message=self._dotnet_exc_msg,
                    stack_trace="\n".join(self._tb_lines),
                    raw_lines=list(self._tb_lines),
                )
                self._reset()
                # Do not discard the current line! We process it as a fresh line.
                # Since the current line is a new log line, let's recursively process it.
                res = self.feed(raw_line)
                return exc or res

        # 2. Handle active Python traceback
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
                self._reset()
                return exc
            if len(self._tb_lines) > _MAX_TRACEBACK_LINES:
                self._reset()
            return None

        # 3. Detect Python traceback start
        if _TRACEBACK_START.search(clean):
            self._tb_lines = [clean]
            self._in_tb = True
            return None

        # 4. Single-line Python/generic exception
        m2 = _EXCEPTION_LINE.match(clean.strip())
        if m2 and not (m2.group(1).startswith("System.") or m2.group(1).startswith("Microsoft.")):
            return DetectedExcepion(
                exception_type=m2.group(1),
                exception_message=m2.group(2).strip(),
                stack_trace="",
                raw_lines=[clean],
            )

        # 5. Detect .NET exception start
        m_dotnet = _DOTNET_EXCEPTION_START.search(clean)
        if m_dotnet:
            self._in_dotnet_tb = True
            self._dotnet_exc_type = m_dotnet.group(1)
            self._dotnet_exc_msg = m_dotnet.group(2).strip()
            self._tb_lines = [clean]
            return None

        # 6. HTTP 5xx in uvicorn access log
        if _HTTP_5XX.search(raw_line):
            return DetectedExcepion(
                exception_type="HTTPException",
                exception_message=f"HTTP 5xx: {raw_line.strip()}",
                stack_trace="",
                raw_lines=[raw_line],
            )

        return None

    def _reset(self) -> None:
        self._tb_lines = []
        self._in_tb = False
        self._in_dotnet_tb = False
        self._dotnet_exc_type = ""
        self._dotnet_exc_msg = ""


def _strip_prefixes(line: str) -> str:
    line = _STRIP_TS.sub("", line)
    line = _STRIP_LEVEL.sub("", line)
    return line


def _extract_from_json(raw_line: str) -> str:
    """If *raw_line* is a JSON object, return its exception or message value.

    Handles common structured log schemas (Serilog, Winston, Python structlog,
    Azure Application Insights).  Falls back to the original line if it is not
    valid JSON or contains no recognised fields.

    Priority: embedded exception/stack-trace text > rendered message field.
    """
    stripped = raw_line.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return raw_line
    try:
        obj: dict = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return raw_line

    # 1. Prefer an explicit exception / stack-trace field
    for key in _JSON_EXCEPTION_FIELDS:
        val = obj.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()

    # 2. Fall back to the human-readable message field
    for key in _JSON_MESSAGE_FIELDS:
        val = obj.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()

    return raw_line

