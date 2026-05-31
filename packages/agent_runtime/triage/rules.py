"""Language-aware triage classification for known exception types.

Rules are ordered by severity within each language table: higher-severity rules
appear first so a single exception type is never downgraded by a later generic rule.

To add a new language: add an entry to _RULES_BY_LANGUAGE — no pipeline changes needed.
To add rules for an existing language: extend the relevant list.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TriageRule:
    patterns: list[str]
    labels: list[str]
    priority: str


@dataclass
class RuleMatch:
    labels: list[str]
    priority: str
    matched: bool


# ---------------------------------------------------------------------------
# .NET rules (MVP)
# ---------------------------------------------------------------------------
_DOTNET_RULES: list[TriageRule] = [
    # --- critical ---
    TriageRule(
        patterns=["OutOfMemoryException", "StackOverflowException"],
        labels=["resource-exhaustion"],
        priority="critical",
    ),
    TriageRule(
        patterns=[
            "UnauthorizedAccessException",
            "AuthenticationException",
            "SecurityException",
            "ForbiddenException",
        ],
        labels=["authentication"],
        priority="critical",
    ),
    # --- high ---
    TriageRule(
        patterns=["TimeoutException", "TaskCanceledException", "OperationCanceledException"],
        labels=["timeout"],
        priority="high",
    ),
    TriageRule(
        patterns=["SqlException", "DbUpdateException", "DbUpdateConcurrencyException"],
        labels=["database"],
        priority="high",
    ),
    TriageRule(
        patterns=["HttpRequestException", "WebException", "SocketException"],
        labels=["network"],
        priority="high",
    ),
    TriageRule(
        patterns=["NullReferenceException"],
        labels=["null-reference"],
        priority="high",
    ),
    # --- medium ---
    TriageRule(
        patterns=["ArgumentNullException", "ArgumentException", "ArgumentOutOfRangeException"],
        labels=["argument-validation"],
        priority="medium",
    ),
    TriageRule(
        patterns=["InvalidOperationException"],
        labels=["invalid-operation"],
        priority="medium",
    ),
    TriageRule(
        patterns=["FileNotFoundException", "DirectoryNotFoundException", "IOException"],
        labels=["file-system"],
        priority="medium",
    ),
    TriageRule(
        patterns=["FormatException", "InvalidCastException", "OverflowException"],
        labels=["data-conversion"],
        priority="medium",
    ),
    TriageRule(
        patterns=["KeyNotFoundException"],
        labels=["missing-key"],
        priority="medium",
    ),
    TriageRule(
        patterns=["ObjectDisposedException"],
        labels=["object-disposed"],
        priority="medium",
    ),
    # --- low ---
    TriageRule(
        patterns=["NotImplementedException"],
        labels=["not-implemented"],
        priority="low",
    ),
]

# ---------------------------------------------------------------------------
# Python rules (Phase 27 — populated at Phase 27 implementation)
# ---------------------------------------------------------------------------
_PYTHON_RULES: list[TriageRule] = [
    TriageRule(patterns=["MemoryError"], labels=["resource-exhaustion"], priority="critical"),
    TriageRule(
        patterns=["PermissionError", "AuthenticationError"],
        labels=["authentication"],
        priority="critical",
    ),
    TriageRule(
        patterns=["TimeoutError", "asyncio.TimeoutError"],
        labels=["timeout"],
        priority="high",
    ),
    TriageRule(
        patterns=["sqlalchemy.exc", "psycopg2", "pymysql", "django.db"],
        labels=["database"],
        priority="high",
    ),
    TriageRule(
        patterns=["ConnectionError", "requests.exceptions", "httpx"],
        labels=["network"],
        priority="high",
    ),
    TriageRule(
        patterns=["AttributeError"],
        labels=["null-reference"],
        priority="high",
    ),
    TriageRule(
        patterns=["ValueError", "TypeError"],
        labels=["argument-validation"],
        priority="medium",
    ),
    TriageRule(
        patterns=["FileNotFoundError", "IsADirectoryError", "IOError", "OSError"],
        labels=["file-system"],
        priority="medium",
    ),
    TriageRule(patterns=["KeyError"], labels=["missing-key"], priority="medium"),
    TriageRule(patterns=["NotImplementedError"], labels=["not-implemented"], priority="low"),
]

# ---------------------------------------------------------------------------
# Node.js / JavaScript rules (Phase 28 — populated at Phase 28 implementation)
# ---------------------------------------------------------------------------
_NODEJS_RULES: list[TriageRule] = [
    TriageRule(
        patterns=["RangeError", "ENOMEM"], labels=["resource-exhaustion"], priority="critical"
    ),
    TriageRule(
        patterns=["JsonWebTokenError", "UnauthorizedError"],
        labels=["authentication"],
        priority="critical",
    ),
    TriageRule(
        patterns=["ETIMEDOUT", "ECONNABORTED", "AbortError"],
        labels=["timeout"],
        priority="high",
    ),
    TriageRule(
        patterns=["SequelizeError", "MongoError", "QueryFailedError"],
        labels=["database"],
        priority="high",
    ),
    TriageRule(
        patterns=["ECONNREFUSED", "ENOTFOUND", "FetchError"],
        labels=["network"],
        priority="high",
    ),
    TriageRule(
        patterns=["Cannot read properties", "Cannot read property", "is not a function"],
        labels=["null-reference"],
        priority="high",
    ),
    TriageRule(patterns=["ENOENT", "EISDIR"], labels=["file-system"], priority="medium"),
    TriageRule(patterns=["ReferenceError"], labels=["missing-key"], priority="medium"),
]

# ---------------------------------------------------------------------------
# Java rules (future)
# ---------------------------------------------------------------------------
_JAVA_RULES: list[TriageRule] = [
    TriageRule(
        patterns=["java.lang.OutOfMemoryError", "OutOfMemoryError"],
        labels=["resource-exhaustion"],
        priority="critical",
    ),
    TriageRule(
        patterns=["NullPointerException", "java.lang.NullPointerException"],
        labels=["null-reference"],
        priority="high",
    ),
    TriageRule(
        patterns=["java.sql.SQLException", "org.hibernate", "PersistenceException"],
        labels=["database"],
        priority="high",
    ),
    TriageRule(
        patterns=["SocketTimeoutException", "java.util.concurrent.TimeoutException"],
        labels=["timeout"],
        priority="high",
    ),
    TriageRule(
        patterns=["java.io.FileNotFoundException", "java.io.IOException"],
        labels=["file-system"],
        priority="medium",
    ),
    TriageRule(
        patterns=["IllegalArgumentException"],
        labels=["argument-validation"],
        priority="medium",
    ),
    TriageRule(
        patterns=["UnsupportedOperationException"],
        labels=["not-implemented"],
        priority="low",
    ),
]

_RULES_BY_LANGUAGE: dict[str, list[TriageRule]] = {
    "dotnet": _DOTNET_RULES,
    "python": _PYTHON_RULES,
    "nodejs": _NODEJS_RULES,
    "java": _JAVA_RULES,
}


def apply_rules(exception_type: str, language: str = "unknown") -> RuleMatch:
    """Return the first matching rule for *exception_type* in the *language* table.

    Falls back to the .NET table for ``"unknown"`` language so existing behaviour
    is preserved for incidents that pre-date Phase 36 language detection.
    """
    rules = _RULES_BY_LANGUAGE.get(language) or _DOTNET_RULES
    for rule in rules:
        if any(pattern in exception_type for pattern in rule.patterns):
            return RuleMatch(labels=list(rule.labels), priority=rule.priority, matched=True)
    return RuleMatch(labels=[], priority="medium", matched=False)
