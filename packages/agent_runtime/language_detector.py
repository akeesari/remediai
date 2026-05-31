"""Detect the programming language of an exception from its type and stack trace.

Detection is heuristic — it is intentionally conservative.  When the evidence
is ambiguous the function returns ``"unknown"`` so downstream agents fall back
to LLM-based analysis rather than mis-classifying.
"""

from __future__ import annotations

import re

# Python stack traces contain lines like:
#   File "/app/src/module.py", line 42, in method_name
_PYTHON_FILE_RE = re.compile(r'File\s+"[^"]+\.py",\s+line\s+\d+')

# .NET stack traces contain lines like:
#   at Namespace.Class.Method(params) in File.cs:line 42
_DOTNET_AT_RE = re.compile(r"\s+at\s+\S.*\.cs:line\s+\d+")

# Node.js/V8 stack traces contain lines like:
#   at ClassName.method (/app/src/file.js:42:18)
#   at async handler (/app/src/routes/api.ts:42:18)
_NODEJS_AT_RE = re.compile(r"\s+at\s+.*\(.*\.[jt]s:\d+:\d+\)")

# Java stack traces contain lines like:
#   at com.example.Class.method(File.java:42)
_JAVA_AT_RE = re.compile(r"\s+at\s+[\w.$]+\([\w.]+\.java:\d+\)")

# .NET exception types are PascalCase and end in "Exception" (no dots for most)
_DOTNET_TYPE_RE = re.compile(r"^[A-Z][A-Za-z0-9]*Exception$")

# Java fully-qualified class names always start with well-known Java package roots
_JAVA_TYPE_RE = re.compile(
    r"^(com|org|net|io|java|javax|sun|edu)\.[a-z][a-z0-9_.]+\.[A-Z][A-Za-z0-9]*$"
)


def detect_language(exception_type: str, stack_trace: str) -> str:
    """Return the most likely language tag: dotnet | python | nodejs | java | unknown."""
    trace = stack_trace or ""
    etype = exception_type or ""

    # Stack trace signals are the most reliable — check these first.
    if _PYTHON_FILE_RE.search(trace):
        return "python"
    if _DOTNET_AT_RE.search(trace):
        return "dotnet"
    if _JAVA_AT_RE.search(trace):
        return "java"
    if _NODEJS_AT_RE.search(trace):
        return "nodejs"

    # Fall back to exception type patterns.
    if _JAVA_TYPE_RE.match(etype):
        return "java"
    # Well-known short names that are unambiguous without a stack trace.
    _DOTNET_KNOWN = {
        "NullReferenceException",
        "ArgumentNullException",
        "InvalidOperationException",
        "NotImplementedException",
        "OutOfMemoryException",
        "StackOverflowException",
        "ObjectDisposedException",
    }
    _PYTHON_KNOWN = {
        "AttributeError",
        "TypeError",
        "ValueError",
        "KeyError",
        "IndexError",
        "RuntimeError",
        "ImportError",
        "OSError",
        "IOError",
        "FileNotFoundError",
        "PermissionError",
        "TimeoutError",
        "NotImplementedError",
        "MemoryError",
        "RecursionError",
        "StopIteration",
        "GeneratorExit",
        "Exception",
    }
    _JAVA_KNOWN = {
        "NullPointerException",  # Java only (.NET uses NullReferenceException)
        "ClassCastException",
        "ArrayIndexOutOfBoundsException",
        "IllegalArgumentException",  # Java only (.NET uses ArgumentException)
        "IllegalStateException",
        "UnsupportedOperationException",
        "ConcurrentModificationException",
        "StackOverflowError",  # Java uses Error suffix, not Exception
        "OutOfMemoryError",
    }

    # Check unambiguous known names (Java first, since some Java names look .NET)
    if etype in _JAVA_KNOWN:
        return "java"
    if etype in _DOTNET_KNOWN:
        return "dotnet"
    if etype in _PYTHON_KNOWN:
        return "python"

    # Last resort: simple PascalCase+Exception is likely .NET
    if _DOTNET_TYPE_RE.match(etype):
        return "dotnet"

    return "unknown"
